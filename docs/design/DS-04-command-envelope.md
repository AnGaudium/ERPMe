# DS-04: Command envelope

Field-level specification for [ADR-0008](../adr/0008-command-envelope-and-registry.md). The ADR's rules win if this file disagrees. Depends on DS-01 ([ADR-0004](../adr/0004-naming-conventions.md)), DS-02 ([ADR-0006](../adr/0006-id-and-numeric-model.md)) and DS-03 ([ADR-0007](../adr/0007-time-model.md)). Open points are in [open-questions.md](../open-questions.md) under DS-04.

## Command request

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `command_type` | string | yes | Registered command type, e.g. `PostGoodsReceipt` |
| `schema_version` | integer | yes | Major version of the command's schema the client was built for |
| `company_id` | uuid | for company-scoped commands | Company the command acts in; absent for installation-scoped commands |
| `idempotency_key` | string, 1–128 of `A-Z a-z 0-9 _ - . :` | yes | Unique per (actor, command type) for at least 90 days |
| `mode` | `simulate` or `execute` | yes | Run and roll back, or run and commit |
| `expected_plan_hash` | 64 lowercase hex characters | when `mode` is `execute` | `plan_hash` returned by the simulation the client reviewed |
| `payload` | object | yes | The command's own schema; unknown fields rejected |

The actor, `on_behalf_of` and `agent_run_id` are never in the request; the dispatcher takes them from the credential (ADR-0008 rule 8).

## Command response

| Field | Present | Meaning |
| --- | --- | --- |
| `command_type`, `mode` | always | Echo of the request (a replay echoes the stored `mode: execute`) |
| `plan` | always | `{"journal_lines": [...], "stock_movements": [...]}` as produced by the handler, filtered by the actor's field permissions; generated IDs are real IDs here, tokens only inside the hash |
| `result` | always | The command's result model, e.g. the created document's `id` and, after execution, its number; also part of the hashed plan |
| `plan_hash` | always | SHA-256 of the canonical plan and result (ADR-0008 rule 12) |
| `recorded_at` | `execute` and replays | Instant of the transaction (ADR-0007 rule 10) |
| `events` | `simulate` | Event types the command would emit, in order; not part of `plan_hash` ([ADR-0013](../adr/0013-outbox-and-events.md) rule 5) |
| `replayed` | always | `true` when the response comes from `idempotency_record` (ADR-0008 rules 16–18), otherwise `false` |

## Command batch

Request: the command request with `command_type` and `schema_version` replaced by `items` (`[{"command_type", "schema_version", "payload"}]`, at most 1,000 by default) and an optional `include_plan` (boolean, default `false`). Idempotency scope: `command_batch`.

Response: `mode`, `plan_hash` (over all item plans), `replayed`, `recorded_at` (execute), and `items`: per item `index`, `command_type`, `result`, `journal_line_count`, `stock_movement_count` and `company_debit_total` (sum of its debit amounts in company currency, debit as DS-06 defines it). With `include_plan: true`, each item also carries its full `plan`.

Errors name the item: `field` is `items[<n>].payload.<field>`. All items are validated before any runs; the first handler error stops the batch. A batch `plan_hash_mismatch` carries this summary in `details`, with full plans only when `include_plan` is true.

## Query request and response

Request: `schema_version`, `company_id` (for company-scoped queries) and `payload` (the filters, plus `limit` and `cursor` for `List<Noun>`). No `idempotency_key`, `mode` or `expected_plan_hash`.

Response for `Get<Noun>`: `result`. For `List<Noun>`: `results` (at most `limit`, default 100, maximum 1,000, ordered by `id` unless the query defines another stable order) `next_cursor` (null on the last page) and `is_scope_filtered` (true when record scope left rows out, [ADR-0017](../adr/0017-permission-envelope.md) rule 9). Results are filtered by the actor's record and field permissions.

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
| `plan_hash_mismatch` | conflict | 409 | no | ADR-0008 rule 13; `details` has the new `plan` and `plan_hash` |
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
| `warehouse_not_bin_managed` | validation | 422 | no | A bin was given for a warehouse that does not manage bins ([ADR-0023](../adr/0023-warehouse-management.md) rule 1) |
| `bin_blocked` | precondition | 422 | no | The bin is blocked for putaway or picking, manually or by an open count ([ADR-0023](../adr/0023-warehouse-management.md) rule 2, 18) |
| `bin_not_empty` | precondition | 422 | no | A bin with stock cannot be deactivated ([ADR-0023](../adr/0023-warehouse-management.md) rule 2) |
| `bin_management_locked` | precondition | 422 | no | `is_bin_managed` cannot change after the first posting except by `ConvertWarehouse` ([ADR-0023](../adr/0023-warehouse-management.md) rule 1) |
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
| `planned_order_not_convertible` | precondition | 422 | no | The planned order is converted or canceled, or lacks a supplier or route ([ADR-0024](../adr/0024-planning.md) rule 22) |
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
| `control_dimension_missing` | precondition | 422 | no | A line on an account whose control kind is active lacks a required dimension (partner and open item, item and warehouse, cost object, fixed asset; loan: partner and open item); trigger-level failures map to it (ADR-0014 rule 10; [ADR-0025](../adr/0025-later-phase-seams.md) rule 4) |
| `subledger_activation_date_not_reached` | precondition | 422 | no | A line on an activated subledger account is dated before the company's activation date ([ADR-0025](../adr/0025-later-phase-seams.md) rule 4) |
| `partner_duplicate_suspected` | check result | — | — | Another partner of the company has the same tax ID; the command succeeds and a work item is created ([ADR-0019](../adr/0019-partners-and-crm-foundation.md) rule 4) |
| `capacity_not_checked` | check result | — | — | A bin capacity could not be checked because weight or dimensions are missing; `details` names the fields ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `bin_capacity_exceeded` | check result | — | — | A confirmed target bin exceeds its capacity; the fact is recorded ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `mixed_stock_not_allowed` | check result | — | — | A confirmed target bin breaks its mix rules; the fact is recorded ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `no_pickable_stock` | check result | — | — | No eligible stock for a pick (status, bin type, shelf life, open tasks); the line stays short and becomes an exception ([ADR-0023](../adr/0023-warehouse-management.md) rule 14) |
| `planning_parameter_missing` | check result | — | — | An item was skipped by the run: no supplier, route or lead time ([ADR-0024](../adr/0024-planning.md) rule 21) |
| `forecast_history_insufficient` | check result | — | — | Too little history for the forecast method ([ADR-0024](../adr/0024-planning.md) rule 11) |
| `customs_assessment_differs` | check result | — | — | Assessed import tax differs from the amount recomputed from the tax codes; the assessed amount is kept ([ADR-0021](../adr/0021-landed-cost.md) rule 10) |
| `consent_missing` | precondition | 422 | no | The message's purpose needs consent that the data subject has not given ([ADR-0019](../adr/0019-partners-and-crm-foundation.md) rule 9) |
| `approval_required` | precondition | 422 | no | The policy engine requires an approval first (DS-28) |
| `invalid_state_transition` | precondition | 422 | no | The command is not allowed in the document's or warehouse task's state; `details` lists the allowed commands ([ADR-0009](../adr/0009-document-lifecycle.md) rule 5) |
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
4. Serialize `{"journal_lines": …, "stock_movements": …, "result": …}` as JSON with keys sorted, separators `,` and `:` without spaces, UTF-8, no escaping of non-ASCII characters. Numbers, dates and instants are already strings in canonical form.
5. `plan_hash` = lowercase hex SHA-256 of those bytes. A batch hashes the list of item plans in item order the same way.
