Module: production    Chunk: 6 of 7    Source ADRs: ADR-0064, ADR-0065, ADR-0068, ADR-0071
Build step(s): 2, 6    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `production`, chunk 6

## Purpose

`production` owns production master data, production orders, shop-floor postings and production costing (ADR-0022.R2).
This chunk states the confirmation checks, the production settings, the production import and its auto-post checker, the
shop-floor report extraction, resource groups and moving an operation inside one, and the execution layer of work orders
(MO and WO labels, repeated postings, receipt scrap, execution state, time logs, stop reasons, assignment, the work-center
queue and `TransferOperation`). The WO tablet query belongs to `query`, the MO tree to `planning`, the usage decision to
`quality`, presets to `registry` and the site and payment master data to `master_data`; their units are traced `ref:`.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`. Every table has the key `id` and is unique on (`company_id`, `id`).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `operation_execution` | Execution record of one internal operation (a WO): `run_state`, block reason and note, execution `work_center_id` (R1052) | `id`; unique `production_order_operation_id` | `production_order_operation` | `production` |
| `operation_time_log` | One clock interval of a person, team or machine on a WO, UI label "WO time log" (R1058, R1059) | `id`; unique (`company_id`, `id`, `production_order_operation_id`) | `operation_execution` | `production` |
| `operation_confirmation_time_log` | Link of a confirmation to the time logs it proposes from (R1061) | `id`; unique (`operation_confirmation_id`, `operation_time_log_id`) | `operation_confirmation` | `production` |
| `operation_assignment` | People and teams assigned to a WO, with `assigned_at` and `ended_at` (R1065) | `id`; one open row (`ended_at` null) per WO and person or team | `operation_execution` | `production` |
| `stop_reason` | Company list of stop reasons with an OEE `loss_class` (R1060) | `id`; unique (`company_id`, `code`) | company | `production` |
| `resource_group` | Work centers of one site that can stand in for each other (R1029) | `id`; unique (`company_id`, `code`) | company | `production` |

Columns this chunk adds to tables whose rows stand in other chunks: `operation_confirmation` (`entry_source`,
`external_reference`, R1025; `work_center_id`, R1069), `operation_confirmation_activity` (`proposed_quantity`, R1063),
`production_receipt` (`scrap_quantity`, `scrap_reason_id`, R1046), `work_center` (`resource_group_id`, R1029) and
`activity_type` (`time_log_basis`, R1062).

Reads: `production_order`, `production_order_operation`, `production_order_component`, `work_center_activity`,
`planning_exception`, `stock_reservation`, `document_reader`, `document_extraction`, `extraction_mapping_rule`, `mailbox`,
`policy_decision`, `setting_value`, `reason`, `team`, `partner`; settings `auto_post.max_error_rate`,
`documents.reason_required.scrap`, `documents.reason_required.return`, `ui.post_review` and `ui.post_review_max_amount`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ImportOperationConfirmation` | Actor `integration`; verb Import, effect class `other`; drafting needs `operation_confirmation` at `edit`, auto-posting needs the credential to hold `post` on `operation_confirmation`; on no tool list | Rows: order number, operation number, yield, scrap, reason code, posting date, `external_reference` | Drafts a confirmation per row; auto-posts a clean draft (R1012 to R1017) | not stated | `duplicate_external_document`, `yield_tolerance_exceeded` |
| `StartOperation` | Leaf `shop_floor_execution` at `edit`; not `human_only`, not proposal-bound (actors: ADR-0071.R17) | WO, kind `setup` or `run` (default `run`), people or team (default the actor's employee partner) | `run_state` to `in_progress`; closes an open stop log, opens logs (R1055) | `OperationStarted` | `operation_not_ready`, `operation_done` |
| `PauseOperation` | Leaf `shop_floor_execution` at `edit` | WO, optional people, optional stop reason | Closes logs; `paused` when no setup or run log stays open (R1055) | `OperationPaused` | `stop_reason_required` |
| `BlockOperation` | Leaf `shop_floor_execution` at `edit` | WO, stop reason (required), note | `blocked`; closes every open log, opens a stop log, raises `operation_blocked` (R1055) | `OperationBlocked` | `operation_done` |
| `CreateOperationTimeLog`, `UpdateOperationTimeLog` | Leaf `shop_floor_execution` at `edit`; `is_draft_only` | A closed interval with both instants | An agent run's log is `draft`, anyone else's `recorded` (R1059) | not stated | `time_log_already_confirmed` |
| `CancelOperationTimeLog` | Leaf `shop_floor_execution` at `edit` | Log, reason | State `canceled` (R1059) | not stated | `time_log_already_confirmed` |
| `ConfirmOperationTimeLog` | Leaf `shop_floor_execution` at `post`; `human_only` | Log | An agent's `draft` becomes `recorded` (R1059) | not stated | not stated |
| `CreateStopReason`, `UpdateStopReason` | `master_data_change`, leaf `production_structure` | Code, name, `loss_class`, `is_planned`, `is_active` | Writes `stop_reason` (R1060) | not stated | not stated |
| `AssignOperation` | Leaf `shop_floor_execution` at `edit` | WO, the whole list of people and teams | Replaces the list in `operation_assignment` (R1065) | `OperationAssigned` | not stated |
| `TransferOperation` | Leaf `shop_floor_execution` at `post`; effect class `other` | WO, target work center | Sets the execution work center; redirects reservations (R1067 to R1070) | `OperationTransferred` | `operation_already_started`, `work_center_not_in_resource_group` |
| `ListWorkCenterQueue` (computed query) | `production_order` at `read`; record scope on `production_warehouse_id` | Work center or resource group, date range for `done` | One row per WO (R1066) | none | not stated |
| `CreateResourceGroup`, `UpdateResourceGroup`, `ListResourceGroup` | `master_data_change`, leaf `resource_group` (under `production_structure`); agents through change proposals (ADR-0068.R23, ADR-0068.R25) | `code`, `name`, `is_active` | Writes or lists `resource_group`; members are set by `UpdateWorkCenter` (R1029, R1030) | not stated | not stated |

Not registered commands: the pure function `production.derive_operation_state` (R1053); the evidence hook
`GetProductionImportShadowEvaluation` and the auto-post gateway checker for `operation_confirmation` (R1015, R1017).
`ListWorkCenterLoad` and `ListCapacityLoad` accept a resource group (R1032); `UpdateWorkCenter` and the work center activity
commands check group membership (R1030).

Codes raised by the rules of this chunk outside the table: `yield_tolerance_exceeded` and `operation_time_log_open` refuse a
confirmation (R1001, R1064); `receipt_scrap_not_allowed` refuses a receipt (R1047); `work_center_outside_warehouse` refuses a
move (R1034); `resource_group_site_mismatch` and `resource_group_activity_mismatch` refuse a member (R1030);
`setting_out_of_bounds` refuses a code list value (R1006). Check results: `yield_above_tolerance`, `activity_above_standard`,
`operation_confirmation_duplicate_suspected`, `reservation_deferred`, `operation_waiting`, `issue_above_requirement`.

## Rules

### Confirmation checks

R1001. The confirmation checks run on `operation_confirmation` at create, update and post, for every entry source. Yield: the base is the previous internal operation's cumulative yield, or Q for the first. When cumulative yield + scrap is above base × (1 + `production.confirmation.yield_tolerance_percent` / 100), the result is the check result `yield_above_tolerance` while `production.confirmation.over_tolerance_action` is `warn`, and the error `yield_tolerance_exceeded` while it is `reject`. Under `warn` it is raised for the first internal operation, or for any operation while the tolerance is above 0, so it never repeats `yield_above_previous_operation`, which is unchanged (ADR-0034.R12).
Source: ADR-0064.R22

R1002. Activity: an actual activity quantity above its standard at the confirmed quantity × (1 + `production.confirmation.activity_tolerance_percent` / 100) gives the check result `activity_above_standard`.
Source: ADR-0064.R22

R1003. Duplicate: another draft or posted, not reversed confirmation of the same order and operation with the same yield, scrap and scrap reason, recorded within `production.confirmation.duplicate_window_minutes`, gives `operation_confirmation_duplicate_suspected`. Two confirmations with yield and scrap 0 are duplicates only when their activity quantities are equal too (ADR-0071.R2). The window has a lower bound of 10 minutes, so the check cannot be switched off. The same photo sent twice is already one extraction (ADR-0057.R15).
Source: ADR-0064.R22, ADR-0064.R22.N1

### Production settings

R1004. The production settings are definitions of ADR-0063's settings registry, in its vocabulary: storage `setting_value`, change effect `immediate`, and area `production`, `planning` or `agents` by the key's first segment. Section Settings lists each key with its scope, value type, core default, bounds, direction, leaf and outdates marker.
Source: ADR-0064.R23

R1005. Tightening a setting is immediate by one person with `edit` on its leaf; loosening is accepted only from an approved change proposal; a `neutral` row is changed directly with a reason (ADR-0063's asymmetric path). Loosening a row whose outdates marker is `auto_post` marks the production import's auto-post evidence outdated; `promotion` means the agent type's stored promotion evidence does not cover the looser value.
Source: ADR-0064.R23

R1006. The `code_list` bounds are `codes`, closed lists of ADR-0064: for `production.agent.shortage_candidate_kinds` the candidate kinds of ADR-0064.R16 (`expedite_supply`, `stock_transfer`, `alternative_version`, `reschedule`, `transfer_reservation`, `split_order`, `partial_staging`), and for `production.capture.enabled_sources` the codes `spreadsheet`, `photo` and `message_text`. A value outside them is `setting_out_of_bounds`.
Source: ADR-0064.R23

R1007. A `product_category` value applies to the category of the order's main output product; for a disassembly order, to the category of the order's item.
Source: ADR-0064.R23

R1008. Import evidence follows the rule of three: `production.mes_import.min_evidence_drafts` is at least ⌈3 / `auto_post.max_error_rate`⌉ (ADR-0063's error ceiling: 300 at its default 1%), a declared order between it and `auto_post.max_error_rate`; `production.mes_import.min_unchanged_percent` is at least 100 − that rate.
Source: ADR-0064.R23

R1009. The core defaults reproduce ADR-0034: reservation at release, yield deviations as check results only, and no automatic posting of shop-floor documents. `production.variance.rank_threshold_amount` 0 means off.
Source: ADR-0064.R23

R1010. Reservation modes (`production.reservation.mode`): `off`: neither release nor the sweep reserves, and people run `ReserveProductionOrderComponent`; `on_release`: release reserves up to available to promise (ADR-0034.R9) and the sweep fills shortfalls of released orders; `scheduled`: release reserves only lines whose requested date lies within `production.reservation.window_days`, with the check result `reservation_deferred` for the others, and the sweep reserves each line as it enters the window.
Source: ADR-0064.R23

R1011. The registry, `setting_value`, `UpdateCompanySetting`, the asymmetric path, the evidence marker and the catalog `settings.csv` are ADR-0063's. The production rows are appended to that catalog with `source` naming ADR-0064, and ADR-0063's lab reads the catalog's own rows instead of a fixed list.
Source: ADR-0064.R23

### Production import

R1012. `ImportOperationConfirmation` is the production import: module `production`, verb Import, effect class `other`, actor `integration` (an integration, not an agent, on no tool list). Drafting needs `operation_confirmation` at `edit`; auto-posting needs the integration credential to hold `post` on `operation_confirmation`.
Source: ADR-0064.R25

R1013. A row holds the order number, operation number, yield, scrap, reason code, posting date and `external_reference`, which is unique per company (`duplicate_external_document` names the existing confirmation). Each row first becomes a draft confirmation with `entry_source` `production_import`, checked by R1001 to R1003.
Source: ADR-0064.R25

R1014. A draft is auto-posted as `integration` only when all hold: `production.mes_import.auto_post` is true; the draft's simulated plan has no check result at all (none of `yield_above_previous_operation`, `yield_above_tolerance`, `activity_above_standard`, `operation_confirmation_duplicate_suspected`, `component_shortage` or any other) and passes the state and period checks; and a policy rule allows `post` of `operation_confirmation` for actor kind `integration`, enabled by `EnablePolicyRule` with shadow evidence (ADR-0043.R14). Confirmation-required postings add to `auto_post_unconfirmed`.
Source: ADR-0064.R25

R1015. `production` registers the evidence hook `GetProductionImportShadowEvaluation`: at least `production.mes_import.min_evidence_drafts` import drafts over at least `production.mes_import.min_evidence_months` calendar months, at least `production.mes_import.min_unchanged_percent` of them posted unchanged by people, and none posted to another order or operation than its row named.
Source: ADR-0064.R25

R1016. Otherwise the draft stays for a person, with the work item `production_import_review`. No LLM touches the path, so ADR-0043.R9 floor 5 is not engaged.
Source: ADR-0064.R25

R1017. The production import is an instance of the auto-post gateway with `runner: own`, and keeps its behavior: `production` registers a checker for `operation_confirmation` (actor `integration`, `accepts_tainted: false`) whose rules are those of R1014 (no check result at all, `production.mes_import.auto_post` true), with `GetProductionImportShadowEvaluation` as its evidence function; its trigger stays `ImportOperationConfirmation`, and its decisions are written in the gateway's columns of `policy_decision`.
Source: ADR-0064.R25.N1, ADR-0065.R20

R1018. The bank cascade is an instance of the same gateway, with `runner: own`, and keeps its behavior: `cash` registers checkers for `bank_receipt`, `bank_payment`, `cash_receipt` and `cash_payment` (actor `system`, `accepts_tainted: false`) whose rules are today's `auto_post_eligibility` conditions (ADR-0043.R14 note; ADR-0059.R6) and the `bank_charge` gates (ADR-0063.R9), with `GetAutoPostShadowEvaluation` as their evidence function. Their trigger stays the cascade (ADR-0048.R9; ADR-0051.R18), their settings stay `cash.*` and `auto_post.max_error_rate`, and `llm_suggestion` drafts stay out (ADR-0063.R6).
Source: ADR-0065.R20

R1019. For both instances, decisions are written in the gateway's columns (ADR-0065.R6), and they share the hard rules of ADR-0065.R7 and the document-type suspension of ADR-0065.R16. The placeholder `<document_type>` of ADR-0065.R8 does not list them, so the generic settings do not apply to them.
Source: ADR-0065.R20

### Shop-floor report capture

R1020. Extraction purpose `shop_floor_report` (ADR-0057.R2) has leaf `operation_confirmation` and consumer `production`. Fields: `production_order_number` (code, resolved to one production order), `operation_number` (code, resolved on that order), `yield_quantity` (quantity), `scrap_quantity` (quantity), `scrap_reason_text` (text, never trusted), `lot_code` (code), `posting_date` (date). Required: the order number, the yield and the posting date.
Source: ADR-0064.R26

R1021. Its rules: `shape` per type; yield + scrap > 0; the posting date not after the business date. Risk order on the verification screen: order number, operation, yield, scrap, date.
Source: ADR-0064.R26

R1022. Sources, selected by `production.capture.enabled_sources`: `spreadsheet` (document kind `spreadsheet`), `photo` (`image`, `pdf_image`; vision values need the seat permission of ADR-0057.R21 and stay untrusted until confirmed) and `message_text` (an operator's message, document kind `email`). A mailbox may carry `document_intake_purpose` `shop_floor_report`. Voice stays later (ADR-0057.R29).
Source: ADR-0064.R26

R1023. The capture agent is Phase 2 (ADR-0078.R2). In Phase 1, mobile capture in the UI is photo and text without it: a photo is attached to a draft or sent through document intake's deterministic ladder (ADR-0057), and text goes to the assistant. Voice stays after Phase 1, and the capture intake keeps a seam to accept an audio attachment later (ADR-0077.R18).
Source: ADR-0064.R26.N1, ADR-0064.R26.N2

R1024. `planning_exception` has the kinds `production_order_start_overdue` and `production_order_overdue`, and a column `production_order_id` with its company key, set exactly for those kinds (DDL: `docs/design/DS-43-54-planning-production.sql`).
Source: ADR-0064.R27

R1025. `operation_confirmation` has `entry_source` (`person`, `capture_agent`, `production_import`; default `person`) and `external_reference`, set exactly for `production_import`, not blank, and unique per company.
Source: ADR-0064.R27

R1026. `stock_reservation` has `transferred_from_reservation_id`, a company key to `stock_reservation`, never the row itself, with the trigger of ADR-0064.R24 (DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`).
Source: ADR-0064.R27

R1027. The purpose value `shop_floor_report` is allowed in `document_reader.purposes`, `document_extraction.purpose`, `extraction_mapping_rule.purpose` (DDL: `docs/design/DS-36-document-intake.sql`) and `mailbox.document_intake_purpose` (DDL: `docs/design/DS-35-crm.sql`).
Source: ADR-0064.R27

### Plant and resource groups

R1028. The plant is the site of the production warehouse (ADR-0033.R11). No new columns: production versions, work centers and orders still name a production warehouse, and `work_center` gets no `site_id`, because the site is derived through `production_warehouse_id`, so there is one source of truth.
Source: ADR-0068.R10

R1029. `resource_group` is company data of `production`, effect class `master_data_change`, change-tracked, with `code`, `name`, `is_active` and `recorded_at`; `work_center.resource_group_id` is nullable. A work center with `capacity_units` is already a pool of identical machines or people; a resource group adds the level above: separate work centers that can stand in for each other.
Source: ADR-0068.R12

R1030. All members of a resource group lie in one site, derived through their production warehouses (`resource_group_site_mismatch`), and record the same set of activity types in `work_center_activity` (ADR-0033.R12; `resource_group_activity_mismatch`). `UpdateWorkCenter` and the work center activity commands check both. To change a member's activity types, remove it from the group first. `INV-811` checks the result.
Source: ADR-0068.R12

R1031. An inactive resource group takes no new members; its members stay grouped until they are removed.
Source: ADR-0068.R12

R1032. Routing operations keep their primary work center (ADR-0033.R10). `ListWorkCenterLoad` (ADR-0034.R3) and `ListCapacityLoad` (ADR-0036.R11) accept a resource group in place of a work center and return the load and the available hours, each summed over the members, with each member's hours computed by ADR-0033.R11.
Source: ADR-0068.R13

R1033. `capacity_overload` stays per work center, and its evidence adds the group's spare hours. `GetCapacityLevelingProposal` (ADR-0036.R12) may propose moving operations to a member with spare hours; a proposal is never applied without approval.
Source: ADR-0068.R13

R1034. An operation moves inside its resource group by either route: a change order on a draft order (ADR-0034.R2) or on a released one (ADR-0034.R8, which refuses moving a confirmed operation), which moves the planned work center and, before start, also resets the execution work center; or `TransferOperation` for a WO not yet started, with no new version (R1067). An internal operation's work center may change to another active member of its group, in the order's production warehouse (otherwise `work_center_outside_warehouse`, as for routings).
Source: ADR-0068.R14, ADR-0068.R14.N1, ADR-0068.R14.N2

R1035. On a move, the operation's standard values carry over as copied: durations and activity quantities. Scheduling uses the target's calendar, `capacity_units`, `hours_per_day` and `efficiency_percent`.
Source: ADR-0068.R14

R1036. Actual cost follows the work center on the operation when it is confirmed, which is `operation_confirmation.work_center_id`, the execution work center, with that work center's cost center and activity rates (ADR-0035.R7, ADR-0035.R14). A confirmed operation cannot move, so one operation's cost never splits across work centers.
Source: ADR-0068.R14, ADR-0068.R14.N1, ADR-0068.R14.N2

R1037. Moves outside the group stay the ordinary edits of ADR-0034. Named individual resources, such as a specific machine, operator or tool with its own calendar or skills, are not Phase 1; they are an open question with a seam: `capacity_units` already covers counting.
Source: ADR-0068.R14

### Work orders: labels and postings

R1038. The execution layer sits on top of ADR-0034 and changes none of its postings. One production order per run, with partial and repeated postings; no backorder orders and no order splitting; corrections by reversible posting documents, never by unlocking a done order; cost only from issues, receipts and confirmations (ADR-0035). A WO's execution state is `waiting`, `ready`, `in_progress`, `paused`, `blocked` or `done`; `in_progress`, `paused` and `blocked` are stored declarations, the others are derived from facts that already exist.
Source: ADR-0071.D0

R1039. **MO** is the UI label of `production_order`; **WO** is the UI label of an internal `production_order_operation`. External operations show as subcontracting steps (ADR-0037), not WOs. No new document type.
Source: ADR-0071.R1

R1040. Code keeps one noun per thing (ADR-0004): new tables and commands use `operation`, as `operation_confirmation` does, so the author's `work_order_time_log` is `operation_time_log`, with the UI label "WO time log".
Source: ADR-0071.R1

R1041. No backorders: receiving less than G leaves the rest open on the same MO, and technical completion closes it (ADR-0034.R6). The UI never offers a split.
Source: ADR-0071.R1

R1042. Receipts (ADR-0034.R13), issues and returns (ADR-0034.R11), time and scrap may each be posted any number of times per MO, each posting a reversible internal document.
Source: ADR-0071.R2

R1043. A confirmation with yield and scrap 0 and only activity quantities is valid: a time-only confirmation, for setup or a shift without finished parts. Two time-only confirmations are duplicates (R1003) only when their activity quantities are equal too.
Source: ADR-0071.R2

R1044. A confirmation with yield 0 and scrap above 0 records scrap alone, and creates no in-process inspection lot (ADR-0070.R8). Component scrap and over-issue are an issue line with `scrap_reason_id` (ADR-0034.R11's column), and the confirmation's scrap reason is `scrap_reason_id` too, each a reference to a reason of kind `scrap` (ADR-0074.R14). Receipt scrap: R1046.
Source: ADR-0071.R2, ADR-0071.R2.N1

R1045. Issuing a component from the tablet's "issue extra component": an issue above the open requirement of a line on the MO keeps `issue_above_requirement` (ADR-0034.R11). For a component not on the MO, the client sends one command batch (ADR-0008.R20): the change order that adds the component line (ADR-0028.R4; ADR-0034.R8), then `CreateProductionIssue` and `PostProductionIssue`. The line's required quantity is 0 unless the person states one, so ADR-0035.R10 treats the consumption as above norms. When policy requires approval of the change, the batch fails as a whole and the issue waits for it.
Source: ADR-0071.R3

R1046. Receipt scrap, for an MO without internal operations: `production_receipt` has `scrap_quantity` (main output, inventory unit, default 0) and `scrap_reason_id`, a reason of kind `scrap` (ADR-0074.R14). A receipt may hold only scrap and no lines; it then posts no material document, like a confirmation.
Source: ADR-0071.R4, ADR-0071.R4.N1

R1047. Receipt scrap is refused with `receipt_scrap_not_allowed` when the MO has an internal operation (scrap belongs on the WO's confirmation, so it is never counted twice) or has no main output (disassembly).
Source: ADR-0071.R4

R1048. Backflush at receipt: the progress share is max(R / G, (R + S) / Q), where R is cumulative net receipts of the main output and S cumulative net receipt scrap; planned assembly scrap is never consumed twice.
Source: ADR-0071.R4

R1049. Receipt scrap carries no value. Tolerance, completion and abnormal cost read receipts only; the scrap variance reads it (ADR-0035; ADR-0064.R10).
Source: ADR-0071.R4

R1050. A production version's routing is optional and a routing may have no operations (ADR-0033.R10, ADR-0033.R13); for such an MO backflush at operation becomes backflush at receipt (ADR-0034.R2), scheduling uses the fixed lead time (ADR-0034.R3), and receipts go to the putaway bin (ADR-0034.R13). Issue, receive and record receipt scrap may each happen any number of times with no WO; the MO screen offers these three buttons.
Source: ADR-0071.R5

R1051. An MO without operations records no activity; conversion cost reaches it through pools with a constant basis (ADR-0035.R7). A workshop that wants labor time adds one internal operation on the MO (ADR-0034.R2), which makes it a one-WO order.
Source: ADR-0071.R5

### WO execution state

R1052. `operation_execution` holds one row per internal operation, written by `production` at release and when a change order adds an internal operation; it is not version content (ADR-0009.R9). It stores `run_state` (`not_started`, `in_progress`, `paused` or `blocked`, with `block_stop_reason_id` and `block_note` while blocked) and `work_center_id`, the execution work center, initially the planned one (R1067). A start, pause or block is a declaration by a person or machine that no other data reveals.
Source: ADR-0071.R6

R1053. The pure function `production.derive_operation_state` derives a WO's state at read time, in this order:
- `done`: a posted, not reversed confirmation with `is_final` exists; a reversal reopens the WO without any write;
- the stored state when it is `in_progress`, `paused` or `blocked`;
- `waiting`, with every reason that applies: `previous_operation` (the previous operation is not done and its cumulative yield is not above this WO's cumulative yield + scrap, so no parts wait here); `components` (a component line of this WO, where lines without an operation number belong to the first internal operation, has a remaining requirement, required − net issued − backflushed, above the quantity ready for it: picked to the supply bin in a warehouse with tasks, reserved in one without, read through `inventory.contract`);
- `ready` otherwise.
Source: ADR-0071.R7

R1054. An open in-process inspection lot does not hold the next operation in Phase 1 (ADR-0070.R21); the tablet shows it under Inspection due. If that changes, its reason `inspection` joins the `waiting` reasons.
Source: ADR-0071.R7

R1055. The state commands (module `production`, effect class `other`, leaf `shop_floor_execution`, not `human_only`, not proposal-bound):
- `StartOperation` (kind `setup` or `run`, default `run`; people or team, default the actor's employee partner), from `not_started`, `paused`, `blocked` or `in_progress` to `in_progress`: closes an open stop log; opens a log per named person or team, or one machine log for an integration; in `in_progress` it adds people or switches their kind;
- `PauseOperation` (optional people, optional stop reason), from `in_progress` to `paused` when no setup or run log stays open: closes the named people's logs, or all; with a stop reason, opens one stop log once the WO is paused;
- `BlockOperation` (stop reason required, note), from any state but `done` to `blocked`: closes every open log, opens a stop log and raises `operation_blocked` (ADR-0071.R18).
Source: ADR-0071.R8

R1056. Start also resumes: there is no `ResumeOperation`, because the verb Resume means continuing a stopped job at level `post`, and an operator resumes at `edit`. Starting a `waiting` WO gives the check result `operation_waiting` with its reasons, or the error `operation_not_ready` when `production.operation.start_when_waiting` is `reject`. `StartOperation` or `BlockOperation` on a done WO is refused with `operation_done`.
Source: ADR-0071.R8

R1057. A stop reason on pause is required when `production.operation.stop_reason_on_pause` is true (`stop_reason_required`). A confirmation never requires a start: a lean workshop may only confirm. Each state command locks the `operation_execution` row; a confirmation still serializes on the order row (ADR-0034.R19). Events `OperationStarted`, `OperationPaused` and `OperationBlocked` feed live queues (ADR-0040.R13).
Source: ADR-0071.R8

### Time logs and stop reasons

R1058. `operation_time_log` (module `production`) holds one clock interval. Who: `employee_partner_id`, or `team_id` with `head_count` (people working, at least 1), or neither for a machine log (`head_count` 0); at most one open log per operation and person, team or machine. When: `started_at` and `ended_at` are instants (ADR-0007), never business dates; `ended_at` is null while open. What: `log_kind` `setup`, `run` or `stop`; `stop_reason_id` only on stop logs; the execution `work_center_id`. State: `draft` (written by an agent run), `recorded` or `canceled`; `entry_source` `person`, `agent` or `integration`.
Source: ADR-0071.R9

R1059. `CreateOperationTimeLog` and `UpdateOperationTimeLog` are `is_draft_only`: an agent run's log is always `draft`, anyone else's is `recorded`. `CancelOperationTimeLog` takes a reason. `ConfirmOperationTimeLog`, `human_only`, turns an agent's draft into `recorded`. Only the state commands of R1055 open logs; a created log has both instants. A log linked to a posted, not reversed confirmation cannot change (`time_log_already_confirmed`); the confirmation is reversed first.
Source: ADR-0071.R9

R1060. `stop_reason` is company data: `code`, `name`, `loss_class` (`availability`, `performance` or `quality`), `is_planned` for planned stops that OEE leaves out of availability, and `is_active`; with `CreateStopReason` and `UpdateStopReason` (`master_data_change`, leaf `production_structure`). OEE reporting comes later; this captures its data now.
Source: ADR-0071.R10

R1061. At create or update, a confirmation links the WO's `recorded`, closed logs not linked to another posted, not reversed confirmation (`operation_confirmation_time_log`). The person may remove or add such logs.
Source: ADR-0071.R11

R1062. `activity_type.time_log_basis` maps logs to activities: `none` (default: the standards), `labor` (sum of duration × `head_count`) or `machine` (length of the union of the intervals). A `per_order` activity reads `setup` logs, a `per_base_quantity` activity reads `run` logs; stop logs are never proposed. The result is converted to the activity type's time unit and rounded half up with `round_quantity` (ADR-0006.R15).
Source: ADR-0071.R11

R1063. The proposal is stored as `proposed_quantity` beside the person's `quantity`; the activity check of R1002 applies to the quantity. Costing reads only the posted quantity (ADR-0035.R7).
Source: ADR-0071.R11

R1064. A final confirmation is refused while a setup or run log of the WO is open (`operation_time_log_open`); the tablet sends `PauseOperation` first in the same batch. An open stop log is closed at its posting. Reversing a confirmation leaves its links, so its logs count as unconfirmed again and the next confirmation proposes them. This minimal form of labor time by clock events is Phase 1 (moved from ADR-0034.R21).
Source: ADR-0071.R11

### Assignment, queue and transfer

R1065. `AssignOperation` (leaf `shop_floor_execution` at `edit`) sets a WO's people and teams as a whole list in `operation_assignment`; replaced rows get `ended_at`, so the history stays. Assignment grants no right and gates no command. Event `OperationAssigned`.
Source: ADR-0071.R12

R1066. `ListWorkCenterQueue` (module `production`, computed query, `production_order` at `read`; record scope on `production_warehouse_id`) returns approved MOs not technically complete, one row per WO of the given work center or resource group, with: the derived state and reasons (the worklist groups `waiting`, `ready`, `in_progress`, `paused`, `blocked`, `done`, the last for a chosen date range); MO number, item, operation number and description, scheduled dates, expected, confirmed and open quantities; assigned people and teams, open logs and `is_assigned_to_me`. Order: scheduled start, then MO number, then operation number.
Source: ADR-0071.R13

R1067. `TransferOperation` (module `production`, `other`, leaf `shop_floor_execution` at `post`) moves a WO to another work center before work on it starts. Allowed when the WO's `run_state` is `not_started` or `blocked` (a machine down before start) and it has no setup or run log and no confirmation (`operation_already_started`); the target is active, in the same resource group as the planned work center (ADR-0068.R12) and in the MO's production warehouse (`work_center_not_in_resource_group`).
Source: ADR-0071.R16

R1068. `TransferOperation` sets `operation_execution.work_center_id`; the planned work center stays in the version, so no change order is needed and the estimate keeps its basis. The open reservations of the WO's components get the new supply bin as destination through `inventory.contract`; stock already staged gets a move task to it. Event `OperationTransferred`.
Source: ADR-0071.R16

R1069. The execution work center is read by the queue, the load view (ADR-0034.R3), the output bin of the last operation (ADR-0034.R13) and the confirmation, which copies it into `operation_confirmation.work_center_id`, so pools allocated by activity type count the work center that did the work (ADR-0035.R7).
Source: ADR-0071.R16

R1070. A change order still moves the planned work center (replanning, with the target's calendar and new dates); while the WO has not started it also sets the execution work center to the new planned one. `TransferOperation` is the floor's quick dispatch inside the group: no new version and no new dates. Either way, cost follows the work center on the confirmation.
Source: ADR-0071.R16

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk. Area `production`, except `INV-845` (`safety`).

| ID | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-741` | `scheduled_reservations_within_window` | day | In reservation mode `scheduled`, no reservation made by a release or a sweep is for a component line whose requested date lay beyond the window on that business date. | R1010; ADR-0064.R15 |
| `INV-811` | `resource_group_members_consistent` | day | The active work centers of a resource group have production warehouses of one site and record equal sets of activity types. | R1030 |
| `INV-840` | `time_log_confirmed_once` | day | Every operation time log is linked to at most one posted, not reversed operation confirmation, of the same operation, and every log so linked is recorded and closed. | R1061, R1064 |
| `INV-841` | `operation_run_state_matches_logs` | day | An operation has an open setup or run log exactly when its `run_state` is `in_progress`; a `blocked` operation that is not done has a stop reason and one open stop log; at most one log is open per operation and person, team or machine. | R1055, R1058 |
| `INV-842` | `operation_transfer_in_group` | day | Every `operation_execution.work_center_id` other than the operation's planned work center is a member of the planned one's resource group in the order's production warehouse, and was set before every setup or run log and every confirmation of the operation. | R1067 |
| `INV-843` | `confirmation_execution_work_center` | day | Every operation confirmation's `work_center_id` equals its operation's execution work center. | R1069 |
| `INV-844` | `receipt_scrap_scope` | day | Every production receipt with `scrap_quantity` above 0 belongs to an order with a main output and no internal operation. | R1047 |
| `INV-845` | `agent_time_logs_drafted` | day | Every time log written by an agent run stayed draft until a human confirmed it, and no confirmation links a draft or canceled log. | R1059; ADR-0071.R17 |

## Edge cases

| ID | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-207` | `capture_yield_tolerance` | A capture report with yield above the previous operation inside the tolerance drafts with a check result; outside it the draft carries `yield_above_tolerance` under `warn` and is refused under `reject`. | `must_reject:yield_tolerance_exceeded`, `must_succeed` | R1001 |
| `EC-208` | `capture_duplicate_report` | The same photo sent twice is one extraction; the same numbers typed again within the window give `operation_confirmation_duplicate_suspected`. | `must_reject:extraction_purpose_exists`, `must_succeed` | R1003; ADR-0057.R15 |
| `EC-218` | `production_import_auto_post_gate` | A production import with auto-post enabled posts a row whose plan has no check result as integration only once the policy rule is enabled with evidence (300 drafts over 2 months, 99% posted unchanged); a row with any check result stays a draft; a repeated reference is refused. | `must_reject:duplicate_external_document`, `must_succeed` | R1013, R1014, R1015 |
| `EC-262` | `resource_group_move_and_cost` | An unconfirmed operation of a released order moves by change order to another member of its resource group; its confirmation is costed at the target's cost center and rates, and a further move after confirmation is refused. | `must_succeed`, `must_reject:referenced_line_immutable` | R1034, R1036 |
| `EC-290` | `wo_many_postings` | An MO of 100 with two WOs: op 10 is started, paused with a stop reason, started again, confirmed for 40 with activities proposed from the logs and one adjusted, then scrap 2, then 58 final; receipts of 40, 30 and 28; an issue above requirement; costing reads only the confirmations. | `must_succeed` | R1042, R1055, R1062 |
| `EC-291` | `mo_without_operations_scrap` | An MO without routing gets two issues, three receipts and receipt scrap of 4 with a reason; backflush at receipt follows max(R / G, (R + S) / Q); receipt scrap on an MO with an internal operation is refused. | `must_succeed`, `must_reject:receipt_scrap_not_allowed` | R1046 to R1050 |
| `EC-292` | `wo_transfer_in_resource_group` | A WO moves to a sibling work center before start; its reservations point to the new supply bin; the confirmation carries the new work center and pool allocation counts it; a transfer after start and one outside the group are refused. | `must_succeed`, `must_reject:operation_already_started`, `must_reject:work_center_not_in_resource_group` | R1067 to R1069 |
| `EC-293` | `capture_agent_time_logs` | The capture agent drafts time logs and a confirmation from a shift sheet; the logs are not proposed until a person confirms them; the tainted run's `StartOperation` is refused. | `must_succeed`, `must_reject:tool_not_allowed` | R1059, R1061; ADR-0071.R17 |
| `EC-294` | `machine_signal_start_pause` | An integration starts and pauses a WO from machine signals while two operators log run time with overlaps; machine time is the union of the intervals and labor time the person logs times head count. | `must_succeed` | R1055, R1062; ADR-0071.R17 |
| `EC-296` | `final_with_open_log` | A final confirmation while a run log is open is refused; the tablet's batch pauses the WO first and succeeds, and the stop log left open is closed at posting. | `must_reject:operation_time_log_open`, `must_succeed` | R1064 |
| `EC-297` | `reversal_reopens_logs` | Reversing a final confirmation makes its logs unconfirmed and the WO no longer done; the next confirmation proposes the logs again. | `must_succeed` | R1053, R1064 |

## Settings

All rows: storage `setting_value`, change effect `immediate` (R1004, R1005).

| Key | Value type | Scopes | Core default | Bounds | Direction | Leaf | Outdates | Used by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `production.reservation.mode` | `enum` | `company` | `on_release` | `off\|on_release\|scheduled` | `neutral` | `production_structure` | `none` | R1009, R1010; ADR-0034.R9.N1, ADR-0064.R12 |
| `production.reservation.window_days` | `integer` | `company` | `14` | `0..180` | `neutral` | `production_structure` | `none` | R1010; ADR-0034.R9.N1 |
| `production.agent.readiness_horizon_days` | `integer` | `company` | `14` | `0..90` | `neutral` | `agent_production` | `none` | R1004; ADR-0064.R12 |
| `production.agent.shortage_candidate_kinds` | `code_list` | `company` | `["expedite_supply", "stock_transfer", "alternative_version", "reschedule"]` | `codes` | `subset_tighter` | `agent_production` | `promotion` | R1006 |
| `planning.production_reschedule_in_tolerance_days` | `integer` | `company` | `0` | `0..30` | `lower_tighter` | `planning_run` | `none` | R1004 |
| `planning.production_reschedule_out_tolerance_days` | `integer` | `company` | `3` | `0..60` | `lower_tighter` | `planning_run` | `none` | R1004 |
| `planning.production_rescheduling_horizon_days` | `integer` | `company` | `60` | `1..365` | `neutral` | `planning_run` | `none` | R1004 |
| `production.order.start_grace_days` | `integer` | `company` | `1` | `0..30` | `neutral` | `production_structure` | `none` | R1004 |
| `production.order.overdue_grace_days` | `integer` | `company` | `0` | `0..30` | `neutral` | `production_structure` | `none` | R1004 |
| `production.order.stalled_days` | `integer` | `company` | `5` | `1..60` | `neutral` | `production_structure` | `none` | R1004; ADR-0064.R12 |
| `production.completion.propose_at_percent` | `percent` | `company;product_category` | `100` | `80..100` | `higher_tighter` | `production_structure` | `none` | R1004, R1007; ADR-0064.R12 |
| `production.confirmation.yield_tolerance_percent` | `percent` | `company;product_category` | `0` | `0..100` | `lower_tighter` | `operation_confirmation` | `auto_post` | R1001 |
| `production.confirmation.over_tolerance_action` | `enum` | `company` | `warn` | `warn\|reject` | `order:warn<reject` | `operation_confirmation` | `auto_post` | R1001 |
| `production.confirmation.activity_tolerance_percent` | `percent` | `company;product_category` | `25` | `0..500` | `lower_tighter` | `operation_confirmation` | `auto_post` | R1002 |
| `production.confirmation.duplicate_window_minutes` | `integer` | `company` | `120` | `10..1440` | `higher_tighter` | `operation_confirmation` | `auto_post` | R1003 |
| `production.capture.enabled_sources` | `code_list` | `company` | `["spreadsheet"]` | `codes` | `subset_tighter` | `agent_production_capture` | `promotion` | R1006, R1022 |
| `production.mes_import.auto_post` | `boolean` | `company` | `false` | `true\|false` | `false_tighter` | `operation_confirmation` | `none` | R1014, R1017 |
| `production.mes_import.min_evidence_drafts` | `integer` | `company` | `300` | `150..3000` | `higher_tighter` | `operation_confirmation` | `auto_post` | R1008, R1015 |
| `production.mes_import.min_unchanged_percent` | `percent` | `company` | `99` | `98..100` | `higher_tighter` | `operation_confirmation` | `auto_post` | R1008, R1015 |
| `production.mes_import.min_evidence_months` | `integer` | `company` | `2` | `1..12` | `higher_tighter` | `operation_confirmation` | `auto_post` | R1015 |
| `production.variance.rank_threshold_percent` | `percent` | `company;product_category` | `5` | `0..100` | `neutral` | `report_production` | `none` | R1004; ADR-0064.R11 |
| `production.variance.rank_threshold_amount` | `decimal` (company currency) | `company` | `0` | `0..` | `neutral` | `report_production` | `none` | R1009; ADR-0064.R11 |
| `production.variance.top_n` | `integer` | `company` | `20` | `1..200` | `neutral` | `report_production` | `none` | R1004; ADR-0064.R11 |
| `production.feedback.enabled` | `boolean` | `company` | `false` | `true\|false` | `neutral` | `agent_production` | `none` | R1004; ADR-0064.R12 |
| `production.feedback.min_orders` | `integer` | `company` | `5` | `3..100` | `neutral` | `agent_production` | `none` | R1004; ADR-0064.R12 |
| `production.feedback.min_periods` | `integer` | `company` | `2` | `1..12` | `neutral` | `agent_production` | `none` | R1004; ADR-0064.R12 |
| `production.operation.start_when_waiting` | `enum` | `company` | `warn` | `warn\|reject` | `order:warn<reject` | `production_structure` | `none` | R1056; ADR-0071.R19 |
| `production.operation.stop_reason_on_pause` | `boolean` | `company` | `false` | `true\|false` | `true_tighter` | `production_structure` | `none` | R1057; ADR-0071.R19 |

The last two rows are from `settings.csv` (source ADR-0071.R8); the others are the definitions of ADR-0064.R23. Area: R1004 gives each key the area of its first segment (`production` or `planning`), while `settings.csv` gives area `agents` to `production.agent.readiness_horizon_days` and `production.agent.shortage_candidate_kinds`; both are stated here as a source finding.

## UI annotations

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `production_import_review` | `document` | `role:shop_floor_lead` | `days:1` | `system`: closed when the draft confirmation of an import row is posted or canceled | R1016 |

`BlockOperation` raises the work item kind `operation_blocked` (R1055; its row stands in chunk 7 with ADR-0071.R18).
`ListWorkCenterQueue` is shown as a worklist grouped by derived state; ADR-0077.R22 has no kanban component in Phase 1 (R1066). The tablet is a hand-built PWA screen over it and `GetOperationWorkspace` (ADR-0071.R14). Phase 1 mobile capture is photo and text, without the capture agent (R1023).

## Conflicts

CONFLICT ADR-0064.R26.N2: the later ADR-0078 note moves the capture agent to Phase 2 (ADR-0078.R2); R1023 states Phase 1 mobile capture as photo and text without the agent.
CONFLICT ADR-0064.R26.N1: its capture through the agent when the source photo is enabled is overridden by ADR-0064.R26.N2 (ADR-0078.R2, higher ADR on the same date); R1023 keeps only its voice deferral and audio seam.
CONFLICT ADR-0064.R22: the ADR-0071 note ADR-0064.R22.N1 narrows the duplicate check, so zero-yield, zero-scrap confirmations need equal activity quantities; folded into R1003.
CONFLICT ADR-0068.R14: notes ADR-0068.R14.N1 and ADR-0068.R14.N2 add the TransferOperation route and make cost follow the execution work center on the confirmation; folded into R1034 and R1036.
CONFLICT ADR-0071.R2: note ADR-0071.R2.N1 (ADR-0074.R14) replaces the text scrap codes of issue lines and confirmations with `scrap_reason_id`; stated in R1044.
CONFLICT ADR-0071.R4: note ADR-0071.R4.N1 replaces the receipt's text field `scrap_reason_code` by the reference `production_receipt.scrap_reason_id` of kind scrap; stated in R1046.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0064.R22 | R1001-R1003 |
| ADR-0064.R22.N1 | R1003 |
| ADR-0064.R23 | R1004-R1011 |
| ADR-0064.R25 | R1012-R1016 |
| ADR-0064.R25.N1 | R1017 |
| ADR-0064.R26 | R1020-R1022 |
| ADR-0064.R26.N1 | R1023 |
| ADR-0064.R26.N2 | R1023 |
| ADR-0064.R27 | R1024-R1027 |
| ADR-0065.R20 | R1017-R1019 |
| ADR-0067.R6 | ref: ADR-0067.R6 |
| ADR-0068.R10 | R1028 |
| ADR-0068.R12 | R1029-R1031 |
| ADR-0068.R13 | R1032, R1033 |
| ADR-0068.R14 | R1034-R1037 |
| ADR-0068.R14.N1 | R1034, R1036 |
| ADR-0068.R14.N2 | R1034, R1036 |
| ADR-0068.R23 | ref: ADR-0068.R23 |
| ADR-0068.R25 | ref: ADR-0068.R25 |
| ADR-0070.R12 | ref: ADR-0070.R12 |
| ADR-0071.D0 | R1038 |
| ADR-0071.R1 | R1039-R1041 |
| ADR-0071.R2 | R1042-R1044 |
| ADR-0071.R2.N1 | R1044 |
| ADR-0071.R3 | R1045 |
| ADR-0071.R4 | R1046-R1049 |
| ADR-0071.R4.N1 | R1046 |
| ADR-0071.R5 | R1050, R1051 |
| ADR-0071.R6 | R1052 |
| ADR-0071.R7 | R1053, R1054 |
| ADR-0071.R8 | R1055-R1057 |
| ADR-0071.R9 | R1058, R1059 |
| ADR-0071.R10 | R1060 |
| ADR-0071.R11 | R1061-R1064 |
| ADR-0071.R12 | R1065 |
| ADR-0071.R13 | R1066 |
| ADR-0071.R14 | ref: ADR-0071.R14 |
| ADR-0071.R15 | ref: ADR-0071.R15 |
| ADR-0071.R16 | R1067-R1070 |
