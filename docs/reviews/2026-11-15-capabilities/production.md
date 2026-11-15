# Holistic review: production and planning (reviewer report at HEAD 5536f9c) + architect decisions

0 blocking, 22 should-fix, 7 nits. Decision per item ("accept" = apply the reviewer's proposed fix as a note on the named carrier).

- F0 short-history forecast (ADR-0024 r11, DS-04 row): accept tiers per (item, warehouse), n = non-event weeks since first history week: n=0 no forecast + forecast_history_insufficient; 1<=n<8 mean of n weeks unindexed + check result; n>=8 and <52 weeks: 8-week average unindexed + check result; >=52 weeks indexed; event with no past occurrence uses seasonal index or 1. Reword DS-04 row.
- 1 forecast is demand only for net_requirements; reorder_point/min_max position uses document demand (ADR-0024 r14): accept.
- 2 action messages/exceptions triggers (ADR-0024 r21): accept trigger table per kind + table names for messages, exceptions, forecast rows/runs/adjustments.
- 3 production version selection date (ADR-0033 r5, pointers 0034 r2, 0036 r3): accept single rule (select at end date for backward scheduling, require validity at resulting start, else next version or production_version_missing).
- 4 UpdatePlannedOrder runs forward once and stores version; later runs fixed (ADR-0036 r3): accept.
- 5 configured/MTO sales line outside production warehouse: BOTH reject the line and raise planning_parameter_missing for open demand on a node without a row (ADR-0036 r9, pointer 0046 r11).
- 6 product is a node in the cycle graph; configured item inherits product low-level code; INV-100 covers it (ADR-0033 r8, pointer 0046 r12): accept.
- 7 planning_exception owner: planning_owner when node source is production, else buyer (catalog row + ADR-0036 r11 or ADR-0042 r18): accept.
- 8 subcontract duration = processing days + return transit; return route row; missing -> planning_parameter_missing (ADR-0037 r3): accept.
- 9 processor_location_missing error (ADR-0037 r2, DS-04): accept.
- 10 B3 columns (production_order_component_id, production_order_output_id, for_demand_supply_line_id, production_order_operation_id, owner_partner_id): AUTHOR. Interim for sim/DDL: assume they exist, keep the flag; note at ADR-0028 r2 stating the interim.
- 11 backflush tables: one production-owned table operation_progress_component keyed by calling document for confirmations, service receipts and receipt backflush; drop operation_confirmation_component (and production_receipt_component if no conflict) (ADR-0034 r12; INV-112).
- 12 pools for shop floor: operation_confirmation, production_receipt and service_receipt are facts: is_approval_hold_allowed false. Pool mo = production_order. Pool consumption = production_issue plus internal consumption goods issues (the author explicitly asked for a Consumption pool; issues above requirement may wait). Check ADR-0055 r2 mapping and adjust by notes (ADR-0034 r17, ADR-0037 r11, ADR-0055 r2).
- 13 policy_input for production_order and production_issue: accept as proposed (amount = released estimate x G fallback components at preliminary price; has_component_shortage, is_content_edited, is_rework; issues is_above_requirement) (ADR-0034 r5).
- 14 seed production_planner as member of mo first stage with approve on production_order (ADR-0055 r5, ADR-0054 r11); author can change (flag).
- 15 service_receipt owner purchasing; registry row in ADR-0047 r1; grant post to buyer and warehouse_keeper; fix authorization-areas.csv (ADR-0037 r5).
- 16 disassembly: determinant header item valuation class; progress = net input issued (ADR-0035 r9, r19): accept.
- 17 E when no qualifying manual line: first operation cumulative yield + scrap for backflush_at_operation; cumulative received (U=0) when all backflush_at_receipt or no routing; add lab case (ADR-0035 r9). Accounting stays flagged for author.
- 18 costing_lot_quantity on cost_estimate; validity = latest released for the version with costing date <= date; preliminary price uses version selected for that lot at posting date (ADR-0035 r14): accept.
- 19 name settings production.abnormal_cost_tolerance_percent etc. with interim values (ADR-0035 r18): accept.
- 20 production step unnumbered: AUTHOR numbers the step; meanwhile add INV-100..112 catalog rows and DS-17 production event types and a vn_manufacturing profile, labelled "production core step (number pending author)".
- 21 no DDL for planning/production: write a DDL draft (design/DS-43-54-planning-production.sql or split) covering tables the six flows need; lab load test. No ADR (DDL of accepted ADRs).
- Nits 22-27: accept all (frozen = proposed inside fence; earliest_start note placement; capacity_overload clarify; median vs mean align to stored stats; configured_stock_available unhashed; cost_object closed state + production_cost_settlement registry; fix citations 0043:172 rule 5, 0032:90 accepted). 28: defer to DS-57 (backlog note).
