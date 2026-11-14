# DS-04: Command envelope

Field-level specification for [ADR-0008](../adr/0008-command-envelope-and-registry.md). The ADR's rules win if this file disagrees. Depends on DS-01 ([ADR-0004](../adr/0004-naming-conventions.md)), DS-02 ([ADR-0006](../adr/0006-id-and-numeric-model.md)) and DS-03 ([ADR-0007](../adr/0007-time-model.md)). Open points are in [open-questions.md](../open-questions.md) under DS-04.

## Command request

Every registered command type also declares its `effect_class` (`posting`, `master_data_change`, `outbound_send`, `other`; ADR-0008 rule 1; [ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 17).

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `command_type` | string | yes | Registered command type, e.g. `PostGoodsReceipt` |
| `schema_version` | integer | yes | Major version of the command's schema the client was built for |
| `company_id` | uuid | for company-scoped commands | Company the command acts in; absent for installation-scoped commands |
| `idempotency_key` | string, 1–128 of `A-Z a-z 0-9 _ - . :` | yes | Unique per (actor, command type) for at least 90 days |
| `mode` | `simulate` or `execute` | yes | Run and roll back, or run and commit |
| `expected_plan_hash` | 64 lowercase hex characters | when `mode` is `execute` | `plan_hash` returned by the simulation the client reviewed |
| `include_canonical_plan` | boolean | no | Also return `canonical_plan`, the plan as hashed (tokenized IDs, no numbers or system instants), filtered by field class ([ADR-0040](../adr/0040-ui-architecture.md) rule 9) |
| `payload` | object | yes | The command's own schema; unknown fields rejected |

The actor, `on_behalf_of` and `agent_run_id` are never in the request; the dispatcher takes them from the credential (ADR-0008 rule 8).

## Command response

| Field | Present | Meaning |
| --- | --- | --- |
| `command_type`, `mode` | always | Echo of the request (a replay echoes the stored `mode: execute`) |
| `plan` | always | `{"journal_lines": [...], "stock_movements": [...], "document_versions": [...], "record_versions": [...]}` as produced by the handler ([ADR-0031](../adr/0031-design-simplifications.md) rules 1–2), filtered by the actor's field permissions; generated IDs are real IDs here, tokens only inside the hash |
| `result` | always | The command's result model, e.g. the created document's `id` and, after execution, its number; also part of the hashed plan |
| `plan_hash` | always | SHA-256 of the canonical plan and result (ADR-0008 rule 12) |
| `recorded_at` | `execute` and replays | Instant of the transaction (ADR-0007 rule 10) |
| `events` | `simulate` | Event types the command would emit, in order; not part of `plan_hash` ([ADR-0013](../adr/0013-outbox-and-events.md) rule 5) |
| `replayed` | always | `true` when the response comes from `idempotency_record` (ADR-0008 rules 16–18), otherwise `false` |
| `audit_record_id` | always | The audit record of the executed command; null in simulate mode ([ADR-0038](../adr/0038-audit-and-observability.md) rule 1). In a batch, per item |
| `checks` | always | Check results as `{code, message, rule, field, details}`; `details` filtered by field class; the `[code, field]` pairs are part of `plan_hash` except for codes of unhashed side information (`capacity_not_checked`, `bin_capacity_exceeded`, `mixed_stock_not_allowed`, `no_pickable_stock`, `planning_parameter_missing`, `forecast_history_insufficient`); stored with the response ([ADR-0040](../adr/0040-ui-architecture.md) rule 10). In a batch, per item |
| `canonical_plan` | when `include_canonical_plan` | The plan as hashed (tokenized IDs, no numbers or system instants, `checks` pairs), filtered by field class; per batch item when `include_plan` is also set ([ADR-0040](../adr/0040-ui-architecture.md) rule 9) |

## Command batch

Request: the command request with `command_type` and `schema_version` replaced by `items` (`[{"command_type", "schema_version", "payload"}]`, at most 1,000 by default) and an optional `include_plan` (boolean, default `false`). Idempotency scope: `command_batch`.

Response: `mode`, `plan_hash` (over all item plans), `replayed`, `recorded_at` (execute), and `items`: per item `index`, `command_type`, `result`, `journal_line_count`, `stock_movement_count`, `company_debit_total` (sum of its debit amounts in company currency, debit as DS-06 defines it) and `checks`. With `include_plan: true`, each item also carries its full `plan`.

Errors name the item: `field` is `items[<n>].payload.<field>`. All items are validated before any runs; the first handler error stops the batch. A batch `plan_hash_mismatch` carries this summary in `details`, with full plans only when `include_plan` is true.

## Query request and response

Request: `schema_version`, `company_id` (for company-scoped queries) and `payload` (the filters, plus `limit` and `cursor` for `List<Noun>`). No `idempotency_key`, `mode` or `expected_plan_hash`.

Response for `Get<Noun>`: `result`. For `List<Noun>`: `results` (at most `limit`, default 100, maximum 1,000, ordered by `id` unless the query defines another stable order) `next_cursor` (null on the last page) and `is_scope_filtered` (true when record scope left rows out, [ADR-0017](../adr/0017-permission-envelope.md) rule 9). Results are filtered by the actor's record and field permissions.

Two registry queries serve clients ([ADR-0040](../adr/0040-ui-architecture.md) rules 8, 12): `ListAllowedCommand` (subject table and ID; computed) returns `allowed_command` rows, each command applicable to the subject with `is_allowed` and, when false, the error code it would return; it writes no denial records and is on no agent tool list in Phase 1. `GetSessionContext` is installation-scoped, needs only a valid credential and is on no agent tool list; it returns the user, their companies with permissions, field classes and record scope, their language and time zone, and the environment.

## Handler context

A handler receives `context` with: the database connection, `new_id(table)`, the clock (`now()`, `today(company)`), the lock helpers for serialized rows, and `emit(event_type, subject, payload)` for events ([ADR-0013](../adr/0013-outbox-and-events.md) rule 1). Consumers and system jobs call the dispatcher in process; their commands execute without `expected_plan_hash` (ADR-0008 rule 13).

## Transports

| Transport | Command | Batch | Query |
| --- | --- | --- | --- |
| REST | `POST /api/commands/<snake_case command type>` | `POST /api/command-batches` | `POST /api/queries/<snake_case query>` |
| MCP | Tool `<snake_case command type>`, arguments = request fields except `command_type` | Tool `command_batch` | Tool `<snake_case query>` |

The generated OpenAPI document has one operation per command type and query, with its own payload and result schemas.

## Example: simulate, then execute

Simulate:

```json
{
  "command_type": "PostGoodsReceipt",
  "schema_version": 1,
  "company_id": "019a7c1e-5b2a-7d40-9c1e-3f2a1b0c4d5e",
  "idempotency_key": "019a7c20-1111-7222-8333-444455556666",
  "mode": "simulate",
  "payload": {
    "goods_receipt_id": "019a7c1f-0000-7abc-8def-000000000010",
    "posting_date": "2026-11-14"
  }
}
```

Response (shortened):

```json
{
  "command_type": "PostGoodsReceipt",
  "mode": "simulate",
  "plan": {"journal_lines": [{"account_id": "…", "company_amount": "2400000", "…": "…"}], "stock_movements": [{"item_id": "…", "quantity": "24", "…": "…"}]},
  "result": {"goods_receipt_id": "019a7c1f-0000-7abc-8def-000000000010"},
  "plan_hash": "9f2c…e1",
  "checks": [],
  "replayed": false
}
```

Execute: the same request with `"mode": "execute"` and `"expected_plan_hash": "9f2c…e1"`. The response adds `recorded_at` and the document number in `result`.

## Example: error

```json
{
  "errors": [
    {
      "code": "posting_date_outside_fiscal_year",
      "message": "Posting date 2027-01-03 is in no fiscal year of this company.",
      "rule": "ADR-0007 rule 22",
      "field": "payload.posting_date",
      "fix": "Create the fiscal year with CreateFiscalYear, or use a date inside an existing fiscal year.",
      "retryable": false,
      "details": {"posting_date": "2027-01-03"}
    }
  ]
}
```

## Error catalog (core codes)

Module-specific codes are added by the DS item that owns the module, in the registry's catalog, with the same columns.

| Code | Category | HTTP | Retryable | When |
| --- | --- | --- | --- | --- |
| `malformed_request` | malformed | 400 | no | The body is not valid JSON or not an object |
| `unauthenticated` | unauthenticated | 401 | no | No valid credential |
| `permission_denied` | permission | 403 | no | DS-15 check failed |
| `human_only` | permission | 403 | no | ADR-0008 rule 2 |
| `segregation_of_duties` | permission | 403 | no | The approver, or the human it acts for, triggered an agent run that wrote a version of the draft, directly or through a consumer ([ADR-0017](../adr/0017-permission-envelope.md) rule 16) |
| `policy_denied` | permission | 403 | no | The policy engine denied the action (DS-28) |
| `unknown_command_type` | not_found | 404 | no | No such command type or query; `details` lists close matches |
| `record_not_found` | not_found | 404 | no | A referenced `id` does not exist or is not visible to the actor; `details` names the table and the `List<Noun>` query (ADR-0006 rule 5) |
| `plan_hash_mismatch` | conflict | 409 | no | ADR-0008 rule 13; `details` has the new `plan` and `plan_hash`, and the new `canonical_plan` when `include_canonical_plan` was set ([ADR-0040](../adr/0040-ui-architecture.md) rule 9) |
| `idempotency_key_reused` | conflict | 409 | no | ADR-0008 rule 16 |
| `version_conflict` | conflict | 409 | no | The document changed since the client read it; `details.current_version` ([ADR-0009](../adr/0009-document-lifecycle.md) rule 10) |
| `concurrent_update` | conflict | 409 | yes | Lock timeout, deadlock or serialization failure |
| `request_too_large` | too_large | 413 | no | The body exceeds the size limit (DS-18) |
| `validation_failed` | validation | 422 | no | A field is missing, of the wrong type or out of range; one item per field |
| `unknown_field` | validation | 422 | no | The request or payload has a field the schema does not define |
| `too_many_decimal_places` | validation | 422 | no | ADR-0006 rule 14 |
| `negative_stock` | precondition | 422 | no | The posting would make a stock quantity negative: per (item, warehouse, lot or serial) at the end of its date or a later date ([ADR-0020](../adr/0020-inventory-and-costing-model.md) rule 10), or per bin, status and handling unit on the current balance ([ADR-0023](../adr/0023-warehouse-management.md) rule 5); `details` names the key and date |
| `preliminary_price_missing` | precondition | 422 | no | A line valued at the preliminary price (an issue or a count surplus) needs one and none exists for the item in the company; `details` names the item and valuation area; fix by posting a receipt or `UpdatePreliminaryPrice` ([ADR-0020](../adr/0020-inventory-and-costing-model.md) rule 11) |
| `allocation_basis_missing` | precondition | 422 | no | A landed cost allocation method lacks its basis, or the total basis is zero; `details` names the targets and the fix (set the item's weight, or choose another method) ([ADR-0021](../adr/0021-landed-cost.md) rule 4) |
| `allocation_manual_sum_mismatch` | validation | 422 | no | Manual allocation amounts do not sum to the cost line ([ADR-0021](../adr/0021-landed-cost.md) rule 4) |
| `landed_cost_source_invalid` | validation | 422 | no | The source is not a posted, unreversed line of the company on a `purchase_cost_clearing` account ([ADR-0021](../adr/0021-landed-cost.md) rule 2) |
| `landed_cost_source_exceeded` | precondition | 422 | no | A cost line would allocate more than its source journal line's unallocated rest; `details` gives the rest ([ADR-0021](../adr/0021-landed-cost.md) rule 2) |
| `landed_cost_target_invalid` | validation | 422 | no | A target is not an unreversed purchase or other receipt line, or not of the cost line's item ([ADR-0021](../adr/0021-landed-cost.md) rules 1, 3) |
| `landed_cost_period_mismatch` | precondition | 422 | no | The posting date does not fit the targets' receipt periods; `details` names the required period, its valid posting date range, or the groups to split ([ADR-0021](../adr/0021-landed-cost.md) rule 6) |
| `negative_stock_value` | precondition | 422 | no | A value-only inventory line would make a warehouse's stock value negative ([ADR-0021](../adr/0021-landed-cost.md) rule 9) |
| `bin_required` | validation | 422 | no | A line in a bin-managed warehouse has no bin ([ADR-0023](../adr/0023-warehouse-management.md) rule 4) |
| `bin_not_in_warehouse` | validation | 422 | no | The bin belongs to another warehouse ([ADR-0023](../adr/0023-warehouse-management.md) rule 2) |
| `warehouse_not_bin_managed` | validation | 422 | no | A bin was given for a warehouse that does not manage bins; omit it and the handler fills the default bin ([ADR-0023](../adr/0023-warehouse-management.md) rule 1; [ADR-0031](../adr/0031-design-simplifications.md) rule 8) |
| `bin_blocked` | precondition | 422 | no | The bin is blocked for putaway or picking, manually or by an open count ([ADR-0023](../adr/0023-warehouse-management.md) rule 2, 18) |
| `bin_not_empty` | precondition | 422 | no | A bin with stock cannot be deactivated ([ADR-0023](../adr/0023-warehouse-management.md) rule 2) |
| `stock_status_not_available` | precondition | 422 | no | The stock to reserve, pick or issue is not in an allowed status ([ADR-0023](../adr/0023-warehouse-management.md) rule 7, 14) |
| `stock_reserved` | precondition | 422 | no | A voluntary issue or block would cut into reserved stock ([ADR-0023](../adr/0023-warehouse-management.md) rule 13) |
| `reservation_exceeds_available` | precondition | 422 | no | A reservation would exceed available to promise ([ADR-0023](../adr/0023-warehouse-management.md) rule 13) |
| `handling_unit_mismatch` | validation | 422 | no | The scanned handling unit is not where the task expects or does not hold the item ([ADR-0023](../adr/0023-warehouse-management.md) rule 6) |
| `handling_unit_closed` | precondition | 422 | no | The handling unit is closed; unpack it first ([ADR-0023](../adr/0023-warehouse-management.md) rule 6) |
| `handling_unit_nesting_exceeded` | validation | 422 | no | Phase 1 allows one nesting level ([ADR-0023](../adr/0023-warehouse-management.md) rule 6) |
| `task_quantity_exceeded` | validation | 422 | no | A confirmed quantity exceeds the task quantity ([ADR-0023](../adr/0023-warehouse-management.md) rule 15) |
| `lot_shelf_life_too_short` | precondition | 422 | no | The scanned lot is below the customer's minimum remaining shelf life or expired ([ADR-0023](../adr/0023-warehouse-management.md) rule 14) |
| `serial_not_in_bin` | validation | 422 | no | A scanned serial is not in the source bin with an allowed status ([ADR-0023](../adr/0023-warehouse-management.md) rule 14) |
| `planning_network_cycle` | validation | 422 | no | The transfer sources would form a cycle; `details` names the warehouses ([ADR-0024](../adr/0024-planning.md) rule 3) |
| `planning_run_in_progress` | conflict | 409 | yes | A planning run of the company is already running ([ADR-0024](../adr/0024-planning.md) rule 17) |
| `planned_order_not_convertible` | precondition | 422 | no | The planned order is converted or canceled, lacks a supplier or route, or its production version is missing or inactive ([ADR-0024](../adr/0024-planning.md) rule 22; [ADR-0036](../adr/0036-multi-level-mrp.md) rule 8) |
| `make_to_order_not_allowed` | validation | 422 | no | `make_to_order` needs source `production`, method `net_requirements` and lot size `exact` ([ADR-0036](../adr/0036-multi-level-mrp.md) rule 9) |
| `movement_not_allowed_at_processor` | validation | 422 | no | Only transfers, production issues and returns, and count differences post at a processor location ([ADR-0037](../adr/0037-subcontracting.md) rule 1) |
| `service_receipt_without_operation` | validation | 422 | no | A service receipt line needs a purchase line tied to a production order operation ([ADR-0037](../adr/0037-subcontracting.md) rule 11) |
| `attachment_too_large` | too_large | 413 | no | The file exceeds `attachment_max_bytes` ([ADR-0038](../adr/0038-audit-and-observability.md) rule 13) |
| `attachment_type_not_allowed` | validation | 422 | no | The media type detected from the bytes is not on the allowed list ([ADR-0038](../adr/0038-audit-and-observability.md) rule 13) |
| `attachment_rejected` | precondition | 422 | no | The same bytes were rejected by the scanner before ([ADR-0038](../adr/0038-audit-and-observability.md) rule 14) |
| `attachment_not_available` | precondition | 422 | no | The attachment is not `clean` (pending scan or rejected): its bytes are not served, and a document linked to it cannot be posted ([ADR-0038](../adr/0038-audit-and-observability.md) rule 14) |
| `quantity_rounds_to_zero` | validation | 422 | no | The quantity converted to the inventory unit rounds to zero ([ADR-0018](../adr/0018-product-and-item-model.md) rule 11) |
| `invalid_timestamp` | validation | 422 | no | ADR-0007 rule 3 |
| `schema_version_unsupported` | validation | 422 | no | ADR-0008 rule 23; `details.served` lists the versions |
| `batch_too_large` | validation | 422 | no | More items than the installation's limit |
| `exchange_rate_missing` | precondition | 422 | no | No quote for the source, pair, kind and date, or the quote is too old; `details` names them and the commands that add a quote ([ADR-0011](../adr/0011-multi-currency.md) rule 10) |
| `document_rate_out_of_tolerance` | precondition | 422 | no | A rate entered on the document differs from the lookup rate by more than the regime allows ([ADR-0011](../adr/0011-multi-currency.md) rule 12) |
| `regime_configuration_missing` | precondition | 422 | no | The accounting regime does not declare a value the posting needs; `details` names the key, regime, date and fix ([ADR-0011](../adr/0011-multi-currency.md) rule 13, [ADR-0016](../adr/0016-localization-package-structure.md) rule 10) |
| `regime_setting_unverified` | precondition | 422 | no | The operation needs a rule or template entry flagged unverified, which this environment refuses ([ADR-0016](../adr/0016-localization-package-structure.md) rule 12) |
| `posting_period_not_open` | precondition | 422 | no | The period's area does not allow this actor to post; `details` names period, area, state and who may post ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 5) |
| `posting_date_too_far_ahead` | precondition | 422 | no | The posting date is beyond the periods that accept postings; `details` names the last allowed date ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 6) |
| `period_sequence_violation` | precondition | 422 | no | A period state change would break the period sequence; `details` names the blocking period ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 8) |
| `close_checklist_incomplete` | precondition | 422 | no | A required close task of the area is not done or no longer current; `details` lists them ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 12) |
| `account_determination_missing` | precondition | 422 | no | No determination row matches the key and determinants; `details` names them and the command that adds a row ([ADR-0015](../adr/0015-account-determination.md) rule 10) |
| `account_determination_mismatch` | precondition | 422 | no | The determined account does not have a system account or control kind the key requires ([ADR-0015](../adr/0015-account-determination.md) rule 12) |
| `document_line_referenced` | precondition | 422 | no | A line another document refers to cannot be deleted ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 3) |
| `referenced_line_immutable` | precondition | 422 | no | A referenced line's item, unit or warehouse cannot change ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 3) |
| `quantity_below_fulfilled` | precondition | 422 | no | A line's quantity cannot go below what referring documents fulfilled ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 3) |
| `change_pending` | conflict | 409 | no | A change waits for approval; cancel the change first (`CancelChange<Type>`), or update after the decision ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 4) |
| `approval_context_changed` | precondition | 422 | no | The policy now requires a higher approval procedure than the approval obtained; `details` give approved and current amounts and procedures; submit again ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 14) |
| `e_invoice_invalid` | validation | 422 | no | The package's e-invoice validation failed; `details.package_code` names the package rule ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 8) |
| `proposal_required` | permission | 403 | no | An agent, or a command carrying an origin agent run, may reach this command only through an approved change proposal; the `fix` names `CreateChangeProposal` ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 4) |
| `target_changed` | conflict | 409 | no | The target record changed since `expected_version` was read; for an approved change proposal, the proposal returns to draft with the new plan ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 3) |
| `outbound_content_out_of_scope` | precondition | 422 | no | A customer draft refers to another partner's records or carries cost or margin fields ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 14) |
| `duplicate_external_document` | conflict | 409 | no | An external document with the same business key exists in the company; `details` name the existing record ([ADR-0030](../adr/0030-commercial-seams-and-imports.md) rule 10) |
| `duplicate_draft` | conflict | 409 | no | A document for the same work item, workflow step, draft ordinal and document type exists, in any state except canceled; `details` name it ([ADR-0030](../adr/0030-commercial-seams-and-imports.md) rule 11) |
| `bill_of_materials_cycle` | validation | 422 | no | Releasing the revision would create a cycle through released bills of materials, outputs counted as children; `details.path` lists it ([ADR-0033](../adr/0033-production-master-data.md) rule 8) |
| `revision_released` | precondition | 422 | no | A released bill of materials or routing revision cannot change; create a new revision ([ADR-0033](../adr/0033-production-master-data.md) rule 3) |
| `revision_validity_gap` | validation | 422 | no | A production version's range is not covered by released revisions of an active bill of materials or routing ([ADR-0033](../adr/0033-production-master-data.md) rule 13) |
| `operation_not_in_routing` | validation | 422 | no | A component names an operation number that the valid routing revision does not contain ([ADR-0033](../adr/0033-production-master-data.md) rule 8) |
| `production_version_missing` | precondition | 422 | no | No active production version covers the item, warehouse, explosion date and quantity ([ADR-0033](../adr/0033-production-master-data.md) rule 13) |
| `draft_revision_exists` | conflict | 409 | no | The bill of materials or routing already has a draft revision ([ADR-0033](../adr/0033-production-master-data.md) rule 3) |
| `revision_retroactive` | validation | 422 | no | A release's start date is before the company's current date, and it is not the first revision ([ADR-0033](../adr/0033-production-master-data.md) rule 4) |
| `revision_start_date_order` | validation | 422 | no | A release's start date is before the latest released revision's ([ADR-0033](../adr/0033-production-master-data.md) rule 4) |
| `revision_in_use` | precondition | 422 | no | A revision that a production order or cost estimate refers to cannot be withdrawn ([ADR-0033](../adr/0033-production-master-data.md) rule 4) |
| `item_both_component_and_output` | validation | 422 | no | An item is both a component and an output of one revision ([ADR-0033](../adr/0033-production-master-data.md) rule 7) |
| `phantom_with_outputs` | validation | 422 | no | A phantom's bill of materials has co-products or by-products ([ADR-0033](../adr/0033-production-master-data.md) rule 7) |
| `work_center_outside_warehouse` | validation | 422 | no | A routing's work center is inactive or outside the production warehouse of a version that uses it ([ADR-0033](../adr/0033-production-master-data.md) rule 9) |
| `in_use_by_production_version` | precondition | 422 | no | An active production version uses the bill of materials or routing ([ADR-0033](../adr/0033-production-master-data.md) rule 9) |
| `production_order_complete` | precondition | 422 | no | The production order is technically complete or closed; reopen it, or reverse earlier postings while it is not closed ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 6) |
| `receipt_above_tolerance` | validation | 422 | no | Cumulative receipts of the main output would exceed the good quantity plus the overdelivery tolerance ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 13) |
| `serial_component_backflush` | validation | 422 | no | A serial-tracked component, or a tracked component under as-built, cannot be backflushed ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 2) |
| `as_built_serial_missing` | validation | 422 | no | The production version requires as-built links; name an assigned output serial on the issue line ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 16) |
| `subledger_not_active` | precondition | 422 | no | The `cost_object` subledger must be active before a production order is released (interim, flagged; [ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 15) |
| `operation_not_confirmable` | validation | 422 | no | The operation is not an internal operation of the order ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 12) |
| `return_above_issued` | validation | 422 | no | A return exceeds the net issued quantity of the component line and lot or serial ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 11) |
| `backflush_outside_production_warehouse` | validation | 422 | no | A backflush component must be issued from the production warehouse ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 2) |
| `production_cost_not_balanced` | internal | 500 | no | After the costing job's postings an order's WIP differs from its recorded closing amounts; the job fails and posts nothing ([ADR-0035](../adr/0035-production-costing.md) rule 12) |
| `by_product_price_missing` | precondition | 422 | no | A by-product receipt needs a by-product price for the item and period ([ADR-0035](../adr/0035-production-costing.md) rule 13) |
| `co_product_weights_zero` | validation | 422 | no | The co-product coefficients of an order sum to zero ([ADR-0035](../adr/0035-production-costing.md) rule 13) |
| `pool_allocation_rule_missing` | precondition | 422 | no | A cost pool group has cost but no allocation rule; the costing job fails ([ADR-0035](../adr/0035-production-costing.md) rule 7) |
| `material_on_cost_pool` | validation | 422 | no | Material cost cannot be posted to a cost pool; post indirect materials to production overhead ([ADR-0035](../adr/0035-production-costing.md) rule 7) |
| `open_item_mismatch` | validation | 422 | no | A line refers to an open item of another partner, account, currency or company ([ADR-0026](../adr/0026-open-item-core.md) rule 4) |
| `open_item_oversettled` | precondition | 422 | no | A settlement exceeds the item's open transaction amount, or the item is settled; post the excess as a payment on account (interim, flagged) ([ADR-0026](../adr/0026-open-item-core.md) rules 6, 8) |
| `open_item_settled` | precondition | 422 | no | The document's open items have settlements from other documents; reverse those first ([ADR-0026](../adr/0026-open-item-core.md) rule 11) |
| `payment_term_invalid` | validation | 422 | no | Payment term line percents do not sum to 100 ([ADR-0026](../adr/0026-open-item-core.md) rule 5) |
| `open_item_revaluation_later` | precondition | 422 | no | A settlement or origin reversal is dated before an unreversed revaluation of the item; reverse or rerun that revaluation first (interim, flagged) ([ADR-0026](../adr/0026-open-item-core.md) rules 6, 11) |
| `partner_has_open_items` | precondition | 422 | no | The partner's reconciliation account cannot change while it has open items; use `TransferPartnerOpenItems` ([ADR-0026](../adr/0026-open-item-core.md) rule 12) |
| `control_dimension_missing` | precondition | 422 | no | A line on an account whose control kind is active lacks a required dimension (partner and open item, item and warehouse, cost object, fixed asset; loan: partner and open item); trigger-level failures map to it (ADR-0014 rule 10; [ADR-0025](../adr/0025-later-phase-seams.md) rule 4) |
| `subledger_activation_date_not_reached` | precondition | 422 | no | A line on an activated subledger account is dated before the company's activation date ([ADR-0025](../adr/0025-later-phase-seams.md) rule 4) |
| `partner_duplicate_suspected` | check result | — | — | Another partner of the company has the same tax ID; the command succeeds and a work item is created ([ADR-0019](../adr/0019-partners-and-crm-foundation.md) rule 4) |
| `partner_snapshot_stale` | check result | — | — | The document's partner data differs from the partner master; warns (interim, flagged; for the tax ID on e-invoiced types `Issue` is rejected with `e_invoice_invalid`) ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 16) |
| `duplicate_suspected` | check result | — | — | A bank statement line without a reference, or an e-mail with a reused `Message-ID` and different content, equals an existing one; both are kept ([ADR-0030](../adr/0030-commercial-seams-and-imports.md) rule 10) |
| `component_shortage` | check result | — | — | Components could not be fully reserved; `details` list the missing quantities ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 9) |
| `issue_above_requirement` | check result | — | — | The issue exceeds the component line's open requirement ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 11) |
| `yield_above_previous_operation` | check result | — | — | Cumulative yield and scrap exceed the previous internal operation's cumulative yield ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 12) |
| `normal_capacity_missing` | check result | — | — | A cost center has fixed overhead but no normal capacity for the period; all of it was absorbed ([ADR-0035](../adr/0035-production-costing.md) rule 7) |
| `planned_wip_capped` | check result | — | — | An order's planned WIP exceeded its cost; WIP was capped and its outputs valued at zero ([ADR-0035](../adr/0035-production-costing.md) rule 9) |
| `capacity_not_checked` | check result | — | — | A bin capacity could not be checked because weight or dimensions are missing; `details` names the fields ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `bin_capacity_exceeded` | check result | — | — | A confirmed target bin exceeds its capacity; the fact is recorded ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `mixed_stock_not_allowed` | check result | — | — | A confirmed target bin breaks its mix rules; the fact is recorded ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `no_pickable_stock` | check result | — | — | No eligible stock for a pick (status, bin type, shelf life, open tasks); the line stays short and becomes an exception ([ADR-0023](../adr/0023-warehouse-management.md) rule 14) |
| `planning_parameter_missing` | check result | — | — | An item was skipped by the run: no supplier, route or lead time ([ADR-0024](../adr/0024-planning.md) rule 21) |
| `forecast_history_insufficient` | check result | — | — | Too little history for the forecast method ([ADR-0024](../adr/0024-planning.md) rule 11) |
| `customs_assessment_differs` | check result | — | — | Assessed import tax differs from the amount recomputed from the tax codes; the assessed amount is kept ([ADR-0021](../adr/0021-landed-cost.md) rule 10) |
| `scan_unavailable` | check result | — | — | No scanner is deployed and scan mode is `optional`; the attachment passed unscanned ([ADR-0038](../adr/0038-audit-and-observability.md) rule 14) |
| `audit_changes_summarized` | check result | — | — | The command changed more than 10,000 tracked rows; the audit record stores field names and hashes instead of values ([ADR-0038](../adr/0038-audit-and-observability.md) rule 3) |
| `quantity_rounded` | check result | — | — | A quantity was rounded to its unit's precision; `details` carry the entered and the rounded value so the user sees both ([ADR-0018](../adr/0018-product-and-item-model.md) rule 11) |
| `consent_missing` | precondition | 422 | no | The message's purpose needs consent that the data subject has not given ([ADR-0019](../adr/0019-partners-and-crm-foundation.md) rule 9) |
| `approval_required` | precondition | 422 | no | The policy engine requires an approval first (DS-28) |
| `invalid_state_transition` | precondition | 422 | no | The command is not allowed in the document's (including `issuing` and change states, ADR-0028) or warehouse task's state; `details` lists the allowed commands ([ADR-0009](../adr/0009-document-lifecycle.md) rule 5) |
| `posting_date_mismatch` | validation | 422 | no | `Post` carries a `posting_date` different from the document's ([ADR-0009](../adr/0009-document-lifecycle.md) rule 9) |
| `document_referenced` | precondition | 422 | no | Delete, cancel or reverse of a document that other documents refer to ([ADR-0009](../adr/0009-document-lifecycle.md) rules 7, 19) |
| `rate_limited` | rate_limited | 429 | yes | `details.retry_after_seconds` says when to retry |
| `internal_error` | internal | 500 | no | Anything unexpected; the response carries only a reference for the logs |
| `timeout` | unavailable | 503 | yes | `transaction_timeout` reached (ADR-0008 rule 11) |

## Canonical plan for hashing

Warehouse task proposals (target and source bins) and planning run results are listed like events and are not part of the hashed plan ([ADR-0023](../adr/0023-warehouse-management.md) rule 11; [ADR-0024](../adr/0024-planning.md) rule 17).

1. Take the full plan and result, before field filtering.
2. Replace each ID created by `context.new_id(table)` during the run with `new:<table>:<n>`, numbering per table from 1 in creation order. Keep IDs that existed before the run, client-supplied IDs and client-supplied instants.
3. Remove values of the types `DocumentNumber` and `SystemInstant`.
4. Serialize `{"journal_lines": …, "stock_movements": …, "document_versions": …, "record_versions": …, "result": …, "checks": …}` ([ADR-0031](../adr/0031-design-simplifications.md) rule 1; the two new lists hold canonical content, tokenized by steps 2–3) as JSON with keys sorted, separators `,` and `:` without spaces, UTF-8, no escaping of non-ASCII characters. Numbers, dates and instants are already strings in canonical form. `checks` is the list of `[code, field]` pairs of the check results whose code is hashed, a null field as `""`, duplicates removed, sorted by code then field ([ADR-0040](../adr/0040-ui-architecture.md) rule 10).
5. `plan_hash` = lowercase hex SHA-256 of those bytes. A batch hashes the list of item plans in item order the same way.
