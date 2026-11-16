# Research: the production agent (DS-57)

Date: 2026-11-15. Input for DS-57 (backlog row: plan proposals, component reservations, shortages and variances, the capture agent's drafted confirmations, drafting bills of materials and routings with release proposals; drafts and change proposals only). Read against base-integrated: ADR-0024, 0032 to 0037, 0043, 0050, 0051, 0057 to 0062 and DS-43-54-planning-production.sql. ADR-0063 has no draft yet (`drafts/ds-settings/` is empty), so the setting names below are proposals that follow the existing `production.*` and `planning.*` keys (ADR-0035 rule 17 note; `planning_setting`). No Vietnam-specific content.

## 1. Summary

Every vendor surveyed keeps the planning and execution engines deterministic. They put AI in three places: summarising and ranking exceptions, proposing a resolution from candidates the engine has computed, and capturing shop-floor facts. Releasing, rescheduling and reassigning wait for a person's confirmation everywhere; the only automatic exception is an explicit setting such as D365's auto-firming time fence. NativeFlows's rules already say the same thing, more strictly. DS-57 therefore needs little new safety machinery. What it needs is deterministic functions that the design still lacks: a cross-order shortage list, a release readiness check, exceptions on real production orders, shortage resolution candidates, an in-flight usage variance and variance drivers, and an extraction purpose for shop-floor reports.

Recommended capabilities (section 4):

| # | Capability | Output | Runs without a person? |
| --- | --- | --- | --- |
| C1 | Release readiness and shortage triage | explanation + work item note | yes (read-only) |
| C2 | Component reservation sweep | reservations via `ReserveProductionOrderComponent` | yes, the only direct command (ADR-0034 rule 9) |
| C3 | Shortage resolution proposals | change proposal or draft change order | no |
| C4 | Order exceptions and rescheduling | draft update or change order | no |
| C5 | Technical completion proposals and stalled orders | change proposal (`CompleteProductionOrder`) | no |
| C6 | Shop-floor capture (drafted confirmations, issues, scrap) | draft posting documents, tainted | no; a person posts |
| C7 | Variance explanation and ranking | explanation (analysis layer) | yes (read-only) |
| C8 | Standards feedback (scrap %, times, lead times) | `product_engineering` drafts or parameter proposals | no |

Recommendation on structure: use three agent types instead of one, so taint and promotion stay clean:
- `production` (C1 to C5, C8): declares `may_read_untrusted: false` and is never tainted, so it may run C2;
- `production_capture` (C6): tainted, scope `subject` = one production order;
- `production_variance` (C7): on the analysis layer (ADR-0060), with that layer's promotion exception.

Planned production orders stay with the `planning` agent (ADR-0051 rules 23–25). The `production` agent starts at `CreateProductionOrder`. This boundary is an open question (section 8).

## 2. Survey findings

### 2.1 What vendors automate and what they only suggest

| Action | SAP | Microsoft | Oracle / others | Pattern |
| --- | --- | --- | --- | --- |
| MRP run, re-explosion, availability check | Deterministic, scheduled (MRP Live); availability check at save or release | Planning Optimization, deterministic | Deterministic everywhere | Automated, no AI |
| Firming planned orders, conversion | Planner action; Manage Material Coverage gives solution proposals | Planner approves planned orders; firming can be automated inside a firming time fence | Kinaxis and o9: agents recommend, planners decide | Suggested; automatic only under an explicit time-fence setting |
| Reschedule in/out, cancel | Exception messages 10, 15, 20, filtered by rescheduling horizon and tolerances; apps add reschedule and cancel actions | Action messages advance, postpone, increase, decrease, derived; the planner applies them | Business Central: "Accept Action Message" per line; lines with warnings are not pre-accepted | Suggested; the person applies them |
| Release with missing parts | Configurable: user decides, release despite missing parts, or no release; Fiori and API cannot ask the user, so they refuse | n/a | Joule Production Planning and Operations agent checks material, capacity and scheduling, suggests alternatives and releases after the planner approves | Check automated; release approved |
| Shortage resolution (substitute, reserve, expedite) | Missing parts list (CO24) | Copilot traces late purchase orders to production orders that cannot start | Oracle production exceptions: request substitute, reserve short material, reschedule the operation | Suggested from a deterministic shortage list |
| Dispatch and resequencing | PP/DS heuristics; Shop Floor Supervisor agent proposes resequencing | n/a | Oracle Operations Assignment Assistant: assign, reassign, resequence with its reasons; changes apply only after the supervisor confirms | Suggested, then applied on confirmation |
| Variance | Deterministic variance categories at period end | Deterministic | Epicor Prism analyses MRP data and flags risks; Plex analytics agent | AI ranks and explains; numbers deterministic |

Sources: SAP exception messages and rescheduling horizon [1–4], release control [5–6], Joule agents [7–9]; D365 action messages [10–11], Copilot impact summaries [12]; Business Central [13]; Oracle [14–16]; Kinaxis [17–18]; o9 [19]; Epicor [20]; Plex [21].

o9's published principles put the safety pattern most clearly [19]. Agents are "autonomous within boundaries, auditable by default, and accountable to human owners". Recommendation, action and approval can be separate duties. Tool permissions are checked before execution, and "a global halt" returns workflows to human-only control. NativeFlows already has each of these:
- fixed tool lists (ADR-0050 rule 29);
- the approver differs from the drafter (ADR-0017 rule 16);
- modes `off`, `shadow` and `assisted`, with demotion always allowed (ADR-0051 rule 4);
- `agent_run` records.

Kinaxis likewise describes its Maestro Agents as planning "with you, not for you", with human-in-the-loop guardrails and visible reasoning [17].

### 2.2 How confirmations are captured and validated

- **Sources.** Vendors capture confirmations from MES terminals (D365 production floor execution: report progress, scrap with a reason code [22]), from sensor counts (D365 Sensor Data Intelligence "production auto report" [23]) and from barcode scans of order and operation. Generative capture from photos and voice is mostly shop-floor guidance today (Siemens Industrial Copilot for Operations [24]), not transaction entry. NativeFlows's `production_capture` would go beyond common practice, so the design is right to make its runs tainted and draft-only (ADR-0034 rule 12).
- **Validation.** Validation is deterministic in every system surveyed:
  - under- and over-delivery tolerances on the yield, set to warn or reject (SAP order confirmation parameters [25]);
  - a mandatory scrap reason;
  - the previous operation's yield;
  - goods-movement error queues for failed backflush (SAP COGI);
  - consumption control: Odoo had Allowed / Allowed with warning / Blocked per bill of materials and removed it in Odoo 20 in favour of flexible consumption [26].

  The trend is toward flexible capture with warnings, not hard blocks. That matches the author's direction.
- **ISA-95.** ERP (level 4) sends the production schedule down. MES (level 3) returns production performance (actuals) and refines the shift-level sequence the ERP cannot see [27]. NativeFlows is a level-4 system with a thin built-in level 3: confirmations, issues and receipts. An MES feed should be a deterministic import of production performance, not an agent's job.

### 2.3 Exception message types

| Family | SAP [1–3] | D365 / BC [10, 13] | NativeFlows today (ADR-0024 rule 21) |
| --- | --- | --- | --- |
| Reschedule in | 10 | Advance | `expedite`, on purchase and transfer supply |
| Reschedule out | 15 | Postpone | `postpone`, later slice |
| Reduce / increase | — | Decrease / Increase | `reduce`, later slice |
| Cancel | 20 | Delete (cancel) | `cancel`, purchase and transfer only |
| Start date in past | 06 (03 for a new proposal) | Calculated delay | `shortage_inside_lead_time` (planned orders only) |
| Finish date in past / past due | 07 | Calculated delay | `firmed_order_overdue` (planned orders only) |
| Shortage / below safety | 96 | Futures date | `below_safety_stock`, `component_shortage` check result |
| Master data | 52 (no BOM), 69 (recursive) | — | `planning_parameter_missing` |

The gap: real production orders get no reschedule, cancel, start-overdue or past-due messages. `cancel` is limited to purchase and transfer lines, and `firmed_order_overdue` covers only planned orders.

### 2.4 Thresholds and defaults that vendors make configurable

Vendor dampening thresholds:
- SAP rescheduling horizon per plant or MRP group (no horizon, no check), with backward and forward tolerances inside which no message is raised [3, 4];
- D365 advance and postpone margins (days), action-message time fence (0 turns messages off) and freeze fence [10, 11];
- Business Central dampener period (falls back to a setup default) and dampener quantity [13].

Other configurable controls:
- release with missing parts: three options, per plant and order type [5];
- confirmation tolerances: per material, with the warn or error level configurable [25];
- consumption control: per bill of materials (Odoo up to 19) [26].

No vendor publishes defaults that would suit NativeFlows. Most default the tolerances to zero, which means every deviation is shown. NativeFlows should do the same where hiding a deviation is the risk, and dampen only where the noise is in the planner's own direction (postpone).

### 2.5 How variances are explained

SAP's variance categories split input variances into price, resource-usage, quantity, scrap and remaining input, and output variances into lot size and others [28]. NativeFlows's `GetProductionOrderVariance` already uses this split (ADR-0035 rule 15). Vendors and research keep computing deterministic; the AI ranks, links and narrates. The scheduling research says the same: LLM agents translate optimiser output into explanations that people review, and the optimiser computes [29, 30].

## 3. What the design already fixes (constraints for DS-57)

The design already fixes these points, and DS-57 must keep them:
- No `Submit`, `Post`, `Approve` or posting command on any tool list. In Phase 1 people release production orders (ADR-0050 rule 30; ADR-0034 rule 5).
- `CompleteProductionOrder`, `ReopenProductionOrder` and the planned-order commands are proposal-bound (ADR-0034 rule 17; ADR-0036 rule 12).
- The production agent may run `ReserveProductionOrderComponent` directly (ADR-0034 rule 9).
- Capture runs are tainted, so a person posts their drafts (ADR-0034 rule 12; ADR-0043 rule 9, floors 3–5).
- Shop-floor documents have `is_approval_hold_allowed: false`, so they never wait in a pool.
- `has_component_shortage`, `is_content_edited` and `is_rework` are already `policy_input` booleans. A company can already use its policy table to raise the approval rank for releases with shortages, so no new release-with-shortage setting is needed.
- The variance split is stored in `production_order_variance` and read through `production_variance_overview` (ADR-0060).
- Bill of materials and routing drafting is `product_engineering` (ADR-0062). DS-57 only references it.

## 4. Recommended capabilities

Common to all: deterministic first (ADR-0051 rule 1). Every number in LLM text must appear in the step's input (ADR-0050 rule 36). Every command is simulated first. The modes run `off` → `shadow` → `assisted`. Owner for scheduled runs: `planning_setting.planning_owner_id`, or a new `production_owner_id`.

### C1 Release readiness and shortage triage (`production`)
- **Trigger:** the event of a production order entering `pending_approval`; a daily schedule over orders whose `planned_start_date` lies within `production.agent.readiness_horizon_days`; on demand by a planner.
- **Deterministic:**
  - new `GetProductionOrderReleaseCheck`: material per component (ATP, reserved, staged), work-center load in the order's buckets, version and revision validity, cost-object subledger active, serials assigned, external-operation supplier and route;
  - new `ListComponentShortage`;
  - `GetProductionOrderStatus`, `ListWorkCenterLoad`, `GetAvailableToPromise`;
  - new `GetProductionOrderPegging`, which walks up to the customer demand at risk.
- **LLM:** classifies each blocker into a closed reason code (material, capacity, master data, accounting gate), ranks the orders by consequence from computed fields (pegged customer due date, days late), and writes a summary of at most 1,200 characters.
- **Output:** an explanation in the order's work item note and a readiness verdict (code-computed) shown to the releaser. No command.
- **Approves:** nothing; it informs the person who submits.
- **Settings:**
  - `production.agent.readiness_horizon_days`: company, default 14, bounds 0–90;
  - `production.agent.readiness_schedule`: company, default daily at 06:00 company time, bounds hourly to weekly.
- **Hard lock:** the verdict is code. The LLM cannot turn "not ready" into "ready".
- **Metric:** readiness verdict equals an independent recompute (100%, CI); explanation number-check pass rate 100%; shadow agreement on top-ranked blocker ≥ 90% over 30 orders.

### C2 Component reservation sweep (`production`)
- **Trigger:** events `GoodsReceiptPosted`, `StockReservationCanceled`, `ProductionOrderCompleted` (frees stock), `TransferReceived`; a daily schedule.
- **Deterministic:** `ListComponentShortage`, then `ReserveProductionOrderComponent` per order, in the order of a new deterministic priority function (requested date, then make-to-order pegged due date, then order number). Reservations only take available-to-promise; they never take stock from another demand (`stock_reserved` stays).
- **LLM:** none. This is pure workflow code. It is an agent type step only so that it carries budgets, records and modes.
- **Output:** reservations, and one work item note per order listing what was reserved and what is still short.
- **Approves:** no one per run. It is accountable to the owner. ADR-0034 rule 9 already allows it.
- **Settings:**
  - `production.reservation.timing`: company or production warehouse, `at_release` (current) or `days_before_start`, default `at_release`;
  - `production.reservation.lead_days`: default 0, bounds 0–180; answers the open question on reserving months ahead;
  - `production.agent.reservation_sweep.enabled`: default false, under the mode ladder.
- **Hard lock:** never reallocate a reservation from another order or a sales order. That is a proposal (C3), because it moves a shortage onto someone else.
- **Metric:** invariant checks (no over-reservation, no reservation taken from others, 100%); shortage lines closed per run; zero denials (ADR-0050 rule 33).

### C3 Shortage resolution proposals (`production`)
- **Trigger:** work item `production_exception` with reason `component_shortage` (new, raised by C1 or at `Submit`); a planner's request.
- **Deterministic:** new `GetShortageResolutionCandidates`. Each candidate carries its computed effect on the order's start date and on pegged demand:
  1. expedite existing supply, linking the planning `expedite` message (the buyer acts);
  2. a stock transfer from a warehouse whose ATP covers the shortage;
  3. reallocate a reservation from a lower-priority order (new proposal-bound command);
  4. an alternative production version, valid on the date, that does not use the short component (ADR-0033 versions; substitute components are later than Phase 1);
  5. reschedule the order to the earliest covering date;
  6. release with partial staging (operations whose components are covered) under the policy's shortage rank;
  7. split the order (a change order reducing G, plus a new draft for the rest; order splitting as such is later than Phase 1, open question).
- **LLM:** picks one candidate handle or `none`, with reason codes and an explanation. It never writes a quantity or date.
- **Output:** one change proposal or draft (change order, transfer draft, reallocation proposal), with candidates and effects as evidence.
- **Approves:** an eligible approver of the proposal's pool, never the human acted for. Releasing a split stays the releaser's `Submit`.
- **Settings:**
  - `production.agent.shortage.candidate_kinds`: company, the enabled subset of 1–7, default 1, 2, 4, 5;
  - `production.agent.shortage.max_candidates`: agent version constant, 5.
- **Hard lock:**
  - reallocation and splitting always go through approval;
  - the alternative version is chosen only from the version selection function's valid set;
  - no candidate the code did not produce.
- **Metric:** shadow agreement ≥ 90% on (candidate kind, target order, document) over 30 shortages; defects found later (proposals reversed); handling time against the baseline.

### C4 Order exceptions and rescheduling (`production`)
- **Trigger:** new exception kinds on real orders, raised by the planning run or a daily production job:
  - `production_order_start_overdue`: approved, `not_started`, start date + grace passed;
  - `production_order_overdue`: not technically complete, end date + grace passed;
  - `expedite` and `postpone` messages on production-order output lines, and `cancel` and `reduce` on `not_started` orders;
  - existing `capacity_overload` limited to real orders.
- **Deterministic:** the planning projection with new tolerances; `GetCapacityLevelingProposal`; `plan_production` in mode `fixed` to recompute dates for a proposed new start; `ListPegging` and `GetProductionOrderPegging`.
- **LLM:** groups related messages (one root cause across levels), applies the D365 rule of bottom-up order (components before parents), ranks, and explains.
- **Output:** draft update (in `draft`) or change order (released) with the new start; cancellation proposals for `not_started` orders.
- **Approves:** pool approver. A change order follows ADR-0028.
- **Settings:**
  - `planning.reschedule_in_tolerance_days`: company, per node override, default 0, bounds 0–30; never hide a lateness;
  - `planning.reschedule_out_tolerance_days`: default 3, bounds 0–60;
  - `planning.rescheduling_horizon_days`: default 60, bounds 0–365, 0 = no check;
  - `production.order.start_grace_days`: default 1, bounds 0–30;
  - `production.order.overdue_grace_days`: default 0, bounds 0–30;
  - `planning.production_action_messages.enabled`: default true.
- **Hard lock:**
  - the snapshot version and revisions of a released order never change (ADR-0034 rule 8);
  - dates come only from `plan_production`;
  - `Cancel` after the first posting is impossible (existing rule).
- **Metric:** agreement with the planner's action ≥ 90% (action, order, date) over 30 exceptions; noise ratio (messages closed with no action) trending down.

### C5 Technical completion and stalled orders (`production`)
- **Trigger:** daily job. Candidates are orders whose main-output receipts reach `production.completion.propose_at_percent` of G with no open operations, and orders `in_progress` without postings for `production.order.stalled_days`.
- **Deterministic:** `GetProductionOrderStatus`; open reservations and staged stock; abnormal-cost preview through the variance function (quantities only).
- **LLM:** classifies the likely state from codes and posting gaps (finished-but-not-closed, waiting for material, abandoned), and summarises.
- **Output:** a change proposal for `CompleteProductionOrder` (proposal-bound), or a work item asking the shop floor lead.
- **Approves:** pool approver (`mo` pool).
- **Settings:**
  - `production.completion.propose_at_percent`: version or company, default 100, bounds 80–100; under-delivery tolerance, the SAP/Odoo pattern;
  - `production.order.stalled_days`: default 5 working days, bounds 1–60.
- **Hard lock:** completion cancels reservations and frees serials, so it stays proposal-bound. The automatic path already exists only as the deterministic version flag `is_complete_on_full_receipt`.
- **Metric:** agreement ≥ 90%; completions reopened within 30 days (defects).

### C6 Shop-floor capture (`production_capture`, tainted)
- **Trigger:** a verified extraction of the new purpose `production_report` (photo of a traveller or worksheet, spreadsheet, later voice), or an inbound message matched to a shop-floor user. A person operating NativeFlows's own shop-floor screen or scanner needs no agent: the production order barcode is already registered (ADR-0061 rule 9).
- **Deterministic:**
  - the ADR-0057 ladder (barcode or QR of order and operation first, then OCR, vision last);
  - the order resolves from a trusted, closed-shape order number, which sets the run's `subject` scope, else the report goes to a person;
  - validation rules:
    - order released and not complete;
    - operation `internal` and confirmable;
    - yield + scrap within `production.confirmation.yield_tolerance_percent` of the previous operation and of Q;
    - scrap reason in the catalog when scrap > 0;
    - posting date in an open period;
    - duplicate check (same order, operation and quantities within `production.capture.duplicate_window_minutes`).
  - activities default to standards. Backflush quantities come from the confirmation command.
- **LLM:** maps free-text reasons to reason codes from a closed list, chooses the operation among the order's operations when the report names it ambiguously (at most 5 candidates), and writes the note. Yield, scrap and lot are stated values, copied and span-checked, never inferred.
- **Output:** draft `operation_confirmation`, `production_issue` or `production_receipt`, tainted.
- **Approves:** a person posts (floor 3). Policy cannot lower this.
- **Settings:**
  - `production.confirmation.yield_tolerance_percent`: version or company, default 0, bounds 0–100;
  - `production.confirmation.over_tolerance_action`: `warn` (default) or `reject`;
  - `production.confirmation.activity_tolerance_percent`: default 25, bounds 0–500, new check result `activity_above_standard`;
  - `production.capture.duplicate_window_minutes`: default 120, bounds 0–1,440;
  - `production.capture.enabled_sources`: `barcode`, `spreadsheet`, `photo`, `voice`; default barcode and spreadsheet; photo and voice need the personal-data processing policy (ADR-0057).
- **Hard lock:**
  - tainted drafts are posted only by a person;
  - the run reads only its subject order;
  - quantities only as stated;
  - no posting on a closed order.
- **Metric:** field agreement ≥ 95% over 50 reports per source (as `document_reader`); drafts posted unedited; confirmations reversed within 7 days (defects); deterministic share rising.

### C7 Variance explanation (`production_variance`, analysis layer)
- **Trigger:** `ProductionCostSettled` (period close) for valued variances; a weekly schedule for in-flight quantity variances; a controller's question.
- **Deterministic:**
  - `production_variance_overview` (valued, by category);
  - new `GetProductionOrderUsageVariance`: quantities only, any time, by component and operation (issued vs target at progress, activity vs standard, scrap vs planned, by reason code);
  - new `ListProductionOrderVarianceDriver`: the document lines behind each category, such as over-issue lines with `reason_code`, confirmations with scrap reasons, and price differences per component;
  - a new deterministic ranking function (absolute and relative thresholds).
- **LLM:** the narrative plan of ADR-0060: claim-template codes with fact handles, for example "scrap at operation 30, reason code X, accounts for most of the scrap variance". Code renders every number.
- **Output:** explanation, linked to orders and documents; optionally raises a C8 work item.
- **Approves:** nothing; information only.
- **Settings:**
  - `production.variance.rank_threshold_percent`: company or item group, default 5, bounds 0–100;
  - `production.variance.rank_threshold_amount`: company currency, default 0 = off;
  - `production.variance.top_n`: default 20, bounds 1–200.

  An order ranks when it exceeds either threshold.
- **Hard lock:** no model-written number; no postings (the variance posts nothing, ADR-0035 rule 15).
- **Metric:** ADR-0060 thresholds (90% equal, ≤ 2% wrong, abstention 90%); precision@10 against the orders the controller investigated.

### C8 Standards feedback (`production`, using `product_engineering`)
- **Trigger:** C7 finds a persistent driver: the same component, operation or scrap reason over `production.feedback.min_orders` orders (default 5) or `production.feedback.min_periods` (default 2).
- **Deterministic:** statistics of actual scrap percent, run time per unit and lead time per version (median and spread), computed by code.
- **LLM:** chooses which standard the evidence concerns, from candidates, and explains.
- **Output:** a `product_engineering` run request for a new draft revision (scrap %, run duration), or a planning-parameter proposal.
- **Approves:** release through an approved change proposal (ADR-0062).
- **Settings:** the two minimums above; `production.feedback.enabled`, default false.
- **Hard lock:** released revisions are immutable; changes only by a new revision through approval.
- **Metric:** proposals accepted; variance in the following periods.

### Budgets (proposal, flagged)

| Agent type | LLM calls | Tool calls | Input tokens | Output tokens | USD/run | Seconds | Rows | USD/day | Runs/day |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `production` | 10 | 120 | 200,000 | 10,000 | 1.00 | 600 | 10,000 | 15 | 400 |
| `production_capture` | 6 | 30 | 80,000 | 5,000 | 0.40 | 180 | 500 | 10 | 500 |
| `production_variance` | as ADR-0060 `analysis` | | | | | | | | |

C2 sweeps use no LLM calls, so they consume only tool-call and row budgets.

## 5. Hard locks, kept to the minimum

1. No release, posting, approval or sending by an agent. This is a structural rule in the registry and tool lists, and no setting can change it.
2. No model-originated quantity, date, price or cost. Quantities come from deterministic functions, or are stated values with source spans.
3. Tainted capture drafts are posted by a person (floor 3).
4. Proposal-bound commands stay proposal-bound: completion, reopen, planned orders, master data, and the new reallocation command.
5. No reservation reallocation and no change to a released order's structure snapshot without approval.
6. Exceptions close only when a deterministic run no longer raises them. Agents never close them.

Everything else is a setting, a policy rule or a decision table: release with shortages, reservation timing, tolerances, grace days, thresholds, enabled candidate kinds and capture sources.

## 6. Deterministic functions and queries the design still lacks

1. **`ListComponentShortage`** (production): across orders, per component line: required, reserved, staged, issued and backflushed, short quantity, requested date, earliest covering supply and its date from the projection, and the pegged end demand. This is SAP's missing parts list.
2. **`GetProductionOrderReleaseCheck`**: one verdict with reason codes for material, capacity, version validity, the subledger gate, serials and external operations.
3. **Exceptions and messages on real production orders** in ADR-0024 rule 21: `production_order_start_overdue`, `production_order_overdue`, and `expedite`, `postpone`, `cancel` and `reduce` on production-order supply. They need the tolerance and horizon settings, a work item kind `production_exception` (owner `planning_owner` or `shop_floor_lead`), and new `planning_exception.kind` values in DS-43-54.
4. **`GetShortageResolutionCandidates`**, with a computed effect per candidate (C3).
5. **A reallocation command** (`ReallocateStockReservation`, proposal-bound) and the deterministic priority function C2 and C3 use.
6. **`GetProductionOrderPegging`**: upward pegging from a real order, or a component shortage, to end demand. `ListPegging` covers planned orders. Real orders link to demand only for make-to-order.
7. **`GetProductionOrderUsageVariance`**: quantity variance before settlement.
8. **`ListProductionOrderVarianceDriver`**, and the variance split by category × cost component. `production_order_variance` is keyed by category only.
9. **ADR-0057 purpose `production_report`**: required fields, validation rules, risk order on the verification screen. ADR-0057 lists no production purpose. `delivery_note` and voice are later.
10. **Confirmation tolerances and checks**: yield tolerance and its action, `activity_above_standard`, `operation_confirmation_duplicate_suspected`. Today only the receipt has a tolerance (`overdelivery_tolerance_percent`).
11. **Production views** for the query layer, which ADR-0050 rule 51 left to DS-52 to DS-54: `production_order_overview`, `production_order_component_overview` (with shortage columns), `production_operation_overview`, `work_center_load_overview`. Each needs declared scope columns. A production order has no partner column, so a tainted capture run needs scope `subject` on the order.
12. **A stalled-order detector and a completion-candidate query** (C5).
13. **A production equivalent of `planning_owner_id`** (`production_owner_id`) for scheduled runs, or a confirmation that the planning owner serves.
14. **A deterministic MES or production-performance import** (an import batch to draft confirmations by `system`), if the author wants level-3 integration in Phase 1.

## 7. Edge cases for the lab

1. A shortage cleared by a goods receipt while C3's proposal is pending: the proposal must fail on `expected_version` or be closed by the next readiness run.
2. Two sweeps racing for the same receipt: no over-reservation (parallel test).
3. A reservation sweep when ATP is consumed by a sales reservation: no stock taken.
4. A multi-level lateness: a component's reschedule must be proposed before the parent's (bottom-up order), and no conflicting dates.
5. An alternative version valid on the end date but not on the recomputed start (the ADR-0033 rule 5 note).
6. Reschedule-out tolerance hides a 2-day postponement but never a 1-day lateness.
7. A capture photo naming an order number that exists in another branch outside the human's scope: refused, no leak in the redacted response.
8. A capture report with yield above the previous operation, inside and outside tolerance: warn vs reject.
9. A duplicate report (same photo sent twice; same numbers re-typed in chat).
10. A capture whose text says "post this now" or names another order: the run stays draft-only and in scope.
11. A capture report for a milestone operation: the generated earlier confirmations appear in the draft's plan, not chosen by the model.
12. Backflush failing for missing stock in the supply bin: the draft's simulate shows `negative_stock`, and C1 explains it.
13. A completion proposal at 97% received under a 95% setting, then a late receipt: the reopen path.
14. Variance explanation where completion falls in a period without receipts (the negative residual, ADR-0035 rule 10): the claim must not call it a saving.
15. A rework order and a disassembly order in the shortage and variance queries (no main output; co-products).
16. A make-to-order order whose sales line is cancelled: a `cancel` message on a `not_started` order, a proposal, never automatic.
17. A tainted capture draft that a policy rule tries to auto-approve: floor 3 holds.
18. The global halt: setting every production agent type to `off` mid-sweep stops at the next call boundary.

## 8. Open questions for the author

1. **Agent types.** Three types (`production`, `production_capture`, `production_variance`) as recommended, or one type with steps? Three keep taint and promotion evidence separate.
2. **Boundary with planning.** Do planned production orders stay with the `planning` agent, with `production` taking over at `CreateProductionOrder`?
3. **Scheduled reservation sweep.** ADR-0034 allows the agent to run `ReserveProductionOrderComponent` directly. Is a scheduled sweep without a person per run acceptable, accountable to the production owner?
4. **Reservation timing default.** `at_release` (current interim) or a lead-days window?
5. **Substitute components.** They are later than Phase 1 (ADR-0033 rule 17), so C3 can only offer alternative versions. Is that enough for the target segment?
6. **Order split as two documents.** Is a change order reducing G plus a new draft acceptable before order splitting exists?
7. **Operators' own input.** Is a shop-floor user's chat message to NativeFlows outside content (tainted) or a person's own entry? Recommended: messages and pictures are tainted; the NativeFlows screen and scanner are a person's entry and need no agent.
8. **MES and sensor feeds.** May a deterministic production-performance import post confirmations as `system` under a policy rule with shadow evidence (as the bank cascade may), or must a person always post?
9. **Setting home.** Should these keys go into ADR-0063's registry once drafted, with the scope levels proposed here (company, production warehouse, work center, item or version)?

## Sources

1. SAP Help, Creation of Exception Messages: https://help.sap.com/SAPHelp_46c/helpdata/EN/f4/7d2c8a44af11d182b40000e829fbfe/content.htm
2. SAP Community, exception 10 vs 20 and rescheduling horizon: https://answers.sap.com/t5/enterprise-resource-planning-q-a/differences-between-exception-20-and-10-in-md04/m-p/10399920 ; past-date messages: https://answers.sap.com/questions/7825062/exception-messages--opening-date-in-the-past-resch.html
3. SAP Help, Rescheduling Check: https://help.sap.com/SAPHelp_46c/helpdata/EN/f4/7d2c9744af11d182b40000e829fbfe/content.htm
4. Define Rescheduling Horizon (IMG): https://www.sapdatasheet.org/abap/cus0/simg_cfmenuolmdomdw.html
5. SAP Community, release with missing parts (OPJK): https://community.sap.com/t5/enterprise-resource-planning-q-a/blocking-the-release-of-production-order/qaq-p/12811926 ; KBA 2841597: https://userapps.support.sap.com/sap/support/knowledge/en/2841597
6. SAP Learning, Releasing Production Orders: https://learning.sap.com/courses/exploring-business-processes-in-sap-s4-hana-discrete-shopfloor-control/releasing-production-orders_b51cd721-9423-454d-85f7-36021999996b
7. SAP, Production Planning and Operations Agent: https://www.sap.com/products/erp/production-planning-and-operations-agent.html
8. SAP, Production Planning Order Progress Agent: https://www.sap.com/sweden/products/scm/production-planning-order-progress-agent.html
9. SAP Business AI release highlights Q3 2025: https://news.sap.com/2025/10/sap-business-ai-release-highlights-q3-2025/ ; Manage Material Coverage reschedule and cancel actions: https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-sap/what-s-new-for-production-planning-in-sap-s-4hana-private-cloud-2025/ba-p/14267425
10. Microsoft Learn, Action messages: https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/action-messages
11. Microsoft Learn, Master plans (time fences): https://learn.microsoft.com/en-my/dynamics365/supply-chain/master-planning/master-plans ; Coverage time fences: https://learn.microsoft.com/hr-hr/dynamics365/supply-chain/master-planning/planning-optimization/coverage-time-fence
12. Microsoft Learn, Copilot summary of purchase order changes and production impact: https://learn.microsoft.com/en-us/dynamics365/release-plan/2023wave2/finance-supply-chain/dynamics365-supply-chain-management/summarize-purchase-order-changes-better-decision-making
13. Microsoft Learn, Business Central planning parameters (dampener, rescheduling period): https://learn.microsoft.com/dynamics365/business-central/design-details-planning-parameters ; Run planning and accept action messages: https://learn.microsoft.com/en-us/dynamics365/business-central/production-how-to-run-mps-and-mrp
14. Oracle, Overview of Production Exceptions: https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/faumf/overview-of-production-exceptions.html ; Production Supervisor Workbench: https://docs.oracle.com/en/cloud/saas/readiness/scm/24d/mfg24d/24D-mfg-wn-f34297.htm
15. Oracle, AI Agent: Operations Assignment Assistant (26A): https://docs.oracle.com/en/cloud/saas/readiness/scm/26a/mfg26a/26A-mfg-wn-f41690.htm
16. Oracle, AI agents in Fusion SCM (2025): https://www.oracle.com/news/announcement/oracle-ai-agents-help-transform-supply-chain-workflows-2025-01-30/
17. Kinaxis Maestro Agents launch (2025): https://www.businesswire.com/news/home/20251017746583/en ; https://news.microsoft.com/source/canada/features/ai/kinaxis-supply-chain/
18. SCMR, agentic AI in exception management: https://www.scmr.com/article/agentic-ai-supply-chain-exception-management/cloud
19. o9, approach to responsible AI: https://o9solutions.com/articles/o9s-approach-to-responsible-ai
20. Epicor Prism agents: https://www.epicor.com/en/blog/supply-chain-management/understanding-vertical-ai-agents-in-manufacturing-erp/ ; https://www.epicor.com/en/newsroom/news-releases/epicor-expands-ai-for-supply-chain/
21. Rockwell Automation Fair 2025 (Plex agents): https://www.verdantix.com/venture/blog/rockwell-automation-fair-2025-shows-how-autonomous-operations-can-truly-scale
22. Microsoft Learn, production floor execution use: https://docs.microsoft.com/en-us/dynamics365/supply-chain/production-control/production-floor-execution-use
23. Microsoft Learn, Sensor Data Intelligence production auto report: https://learn.microsoft.com/en-ie/dynamics365/supply-chain/sensor-data-intelligence/sdi-scenario-production-auto-report
24. Siemens Industrial Copilot for operations: https://www.manufacturing.net/operations/news/22926249/siemens-expands-generative-aipowered-industrial-copilot
25. SAP confirmation tolerances (community): https://archive.sap.com/discussions/thread/530705 ; https://www.erpqna.com/?p=73709
26. Odoo bill of materials (flexible consumption): https://www.odoo.com/documentation/saas-18.4/applications/inventory_and_mrp/manufacturing/basic_setup/bill_configuration.html ; Odoo 20 notes: https://iventureteam.com/odoo-20-release-notes/manufacturing/
27. ISA-95 level 3/4 boundary: https://book.st-hakky.com/en/industry/mes-erp-boundary-isa95-level3-4 ; https://www.symestic.com/en-us/what-is/isa-95
28. SAP Help, Variance Categories: https://help.sap.com/saphelp_46c/helpdata/en/90/ba624f446711d189420000e829fbbd/content.htm ; https://help.sap.com/saphelp_erp60_sp/helpdata/en/25/9142530fafff4fe10000000a44176d/content.htm
29. Human-centric agentic scheduling with LLM explanations (Aalborg, ETFA): https://vbn.aau.dk/ws/files/845502503/Conference_Manuscript_FIXED.pdf
30. LLM explanations for dynamic rescheduling (arXiv 2601.09100): https://arxiv.org/pdf/2601.09100v2 ; LLM multi-agent shop floor (arXiv 2405.16887): https://arxiv.org/abs/2405.16887v1

Caveats: several vendor agent pages (SAP Joule agents, Kinaxis, Epicor, Plex) are marketing or trade coverage, and some SAP configuration details come from community posts; they were used for patterns, not for exact behaviour.
