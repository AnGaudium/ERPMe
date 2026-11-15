# DS-04: Command envelope

Field-level specification for [ADR-0008](../adr/0008-command-envelope-and-registry.md). The ADR's rules win if this file disagrees. Depends on DS-01 ([ADR-0004](../adr/0004-naming-conventions.md)), DS-02 ([ADR-0006](../adr/0006-id-and-numeric-model.md)) and DS-03 ([ADR-0007](../adr/0007-time-model.md)). Open points are in [open-questions.md](../open-questions.md) under DS-04.

## Command request

Every registered command type also declares its `effect_class` (`posting`, `master_data_change`, `outbound_send`, `other`; ADR-0008 rule 1; [ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 17).

A command may be registered `is_internal_only`: only a consumer or system job runs it, in process ([ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 13). It has no REST endpoint, MCP tool or tool definition, so a request or batch item that names it over a transport gets `unknown_command_type`. No authorization level grants it; the job holds it by registration ([ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 1 note; [ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 8 note).

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
| `checks` | always | Check results as `{code, message, rule, field, details}`; `details` filtered by field class; the `[code, field]` pairs are part of `plan_hash` except for codes of unhashed side information (`capacity_not_checked`, `bin_capacity_exceeded`, `mixed_stock_not_allowed`, `no_pickable_stock`, `planning_parameter_missing`, `forecast_history_insufficient`, `configured_stock_available`); stored with the response ([ADR-0040](../adr/0040-ui-architecture.md) rule 10). In a batch, per item |
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

The consumer that executes an approved change proposal also passes `change_proposal_execution` (the proposal's ID and version) in `context`. A handler whose effect needs a proposal whatever the actor, such as `UpdateAgentTypeSetting` setting `assisted`, returns `proposal_required` without it ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 4 note).

## Dispatcher check order

The dispatcher runs its checks for every command, batch item and query in one order ([ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 5, which this section completes). A step runs only when the earlier ones passed, so a refusal names the first check that failed. Steps 6 to 10 apply to commands only; a query runs after step 5, and its result is then marked for taint ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 25).

1. **Credential and actor context** ([ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 8): `unauthenticated`, `user_account_locked`; the actor kind, `on_behalf_of`, the agent run with its work item, and the origin agent run come from the credential. A command registered `is_internal_only` named over a transport is `unknown_command_type`.
2. **Run gates that need no subject state**, for agent runs and for consumer commands that carry an origin agent run: `tool_not_allowed` (the run token's tool list, [ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 29); then `tainted_run_not_allowed` (a tainted run, or a consumer command for a tainted event, sending a command not registered `is_draft_only`; [ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 26, [ADR-0013](../adr/0013-outbox-and-events.md) rule 11); then the tainted reference scope of the payload (`tainted_read_out_of_scope`, [ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 25). For queries also `untrusted_read_not_allowed` and the refusal of a view without the run's scope column ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rules 27–28).
3. **`human_only` and the agent-chain refusals**, by actor kind and origin agent run: `human_only` ([ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 2); `proposal_required` for an allowed-target command from an agent actor or an actor carrying an origin run ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 4); `origin_run_submit_not_allowed` for a `Submit` from an actor carrying an origin run ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 6).
4. **Permission:** the actor's expanded permissions ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rules 8–9), the intersection for agent runs and for consumers on an agent chain ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 31; [ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 12), the capability checks of `StartAgentRun` and `CancelAgentRun` ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 24), and the `direct_master_data_change` deny ([ADR-0043](../adr/0043-policy-and-approval.md) rule 12): `permission_denied`, `proposal_required`.
5. **Record visibility:** company, record scope and owner scope ([ADR-0017](../adr/0017-permission-envelope.md) rule 9; [ADR-0054](../adr/0054-users-roles-and-authorizations.md) rules 13–15): `record_not_found`. Queries leave rows out with `is_scope_filtered`, and for tainted runs keep only rows in the taint scope ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 49).
6. **Idempotency:** in execute mode the lookup and insert of [ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 16; in simulate mode the lookup of rule 17 only. A committed row with the same request hash returns the stored response with `replayed: true` and no further check, so a replayed `Approve` returns its stored response, not `approval_already_given`. A different hash returns `idempotency_key_reused`.
7. **Work item claim** of an agent run's bound item ([ADR-0042](../adr/0042-work-queue.md) rules 9, 11): the `FOR KEY SHARE` lock and `work_item_claim_lost`. Shadow runs skip it. Simulations run it at the same position, although they write no idempotency record.
8. **State-dependent authorization**, which reads the subject: segregation of duties for `Approve` ([ADR-0017](../adr/0017-permission-envelope.md) rule 16), segregation pairs on related documents ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 19) and stage eligibility ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 7): `segregation_of_duties`, `approver_not_eligible`, `approval_already_given`, `approval_would_strand_stage`.
9. **Policy point and floors** ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 6; [ADR-0043](../adr/0043-policy-and-approval.md) rules 7–9): `policy_denied`, `approval_required`, and the stored decision. For commands registered `is_policy_in_handler` this step runs inside the handler.
10. **Handler, audit record and events:** the handler's own preconditions (such as `invalid_state_transition`), the audit record ([ADR-0038](../adr/0038-audit-and-observability.md) rule 1), events and deliveries, and the stored response.

- **Why this order.** Checks that read the subject's current state run after the replay lookup, so a retry gets what the first execution returned. The tool list runs before `human_only`, `proposal_required` and permission, so an agent run calling a command outside its list gets `tool_not_allowed` whatever the command is; no agent run simulates a `human_only` command. No check needs the result of a later one.
- **Batches.** Steps 1 to 5, 7 and 8 run for every item; step 6 runs once, for the batch.
- **Denials.** The codes that write denial records, and those that count toward an agent run's three-denial stop, are listed in [ADR-0038](../adr/0038-audit-and-observability.md) rule 5's note.
- **EC-56.** An agent run that calls the bank-account command directly gets `tool_not_allowed`, since allowed-target commands are on no tool list ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 29); a consumer command carrying the run as origin gets `proposal_required`; a change proposal approved by a second person succeeds.

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

Trigger-held immutability is one class, precondition with HTTP 422: `revision_released`, `configuration_immutable` and `referenced_line_immutable` mean that a stored row may no longer change, and the caller creates a new revision or document instead (catalog review, 2026-11-15).

Envelope-level codes are defined here and nowhere else: `malformed_request`, `unknown_command_type`, `unknown_field`, `internal_error`, `invalid_timestamp`, `too_many_decimal_places`, `record_not_found` and `timeout`. Where their row cites an ADR rule, that rule states the condition and this catalog names the code.

Outcome and violation enumerations are not error codes and are not catalogued here; the ADR that defines each owns it: the render job outcomes of [ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 31 (`render_failed`, `render_too_large`, `render_output_invalid`), the agent run outcomes of [ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) (`budget_exceeded`, `time_exceeded`, `output_invalid`, `provider_unavailable`, `resume_diverged`, `crashed`, and `replay_diverged` for replays), and the configuration violation codes of [ADR-0046](../adr/0046-product-configuration.md) rule 18 (`configuration_set_conflict`, `configuration_table_no_match` and the others listed there). Loader errors of the package loader are in [DS-14](DS-14-localization-package.md) (Loader errors).

| Code | Category | HTTP | Retryable | When |
| --- | --- | --- | --- | --- |
| `malformed_request` | malformed | 400 | no | The body is not valid JSON or not an object |
| `unauthenticated` | unauthenticated | 401 | no | No valid credential |
| `user_account_locked` | unauthenticated | 401 | no | Too many failed sign-ins; `details.locked_until` says when sign-in is possible again ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 4) |
| `permission_denied` | permission | 403 | no | DS-15 check failed |
| `human_only` | permission | 403 | no | ADR-0008 rule 2 |
| `segregation_of_duties` | permission | 403 | no | The approver, or the human it acts for, triggered an agent run that wrote a version of the draft, directly or through a consumer ([ADR-0017](../adr/0017-permission-envelope.md) rule 16); a stage approver or delegator who wrote a version ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 7); a segregation pair on related documents ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 19) |
| `grant_exceeds_own_rights` | permission | 403 | no | A role, assignment or delegation would give permissions the actor does not hold, or a name or e-mail change or password reset targets a user who holds permissions the actor lacks ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rules 3, 9, 10, 12, 21) |
| `segregation_conflict` | permission | 403 | no | In assignment mode `block`, the change would let a user's permissions hold both sides of an enabled segregation rule; `details` names the rules ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 18) |
| `approver_not_eligible` | permission | 403 | no | The person is neither a member holding `Approve<Type>` with the document in their read scope, nor a substitute of one, nor an escalation holder of an overdue stage; or the named delegator does not make them eligible ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 7) |
| `organization_self_change` | permission | 403 | no | An organization command would change the caller's own organization resolver result (their teams' employees or the employees under them); callers whose assignments all have owner scope `company` are exempt ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 6) |
| `policy_denied` | permission | 403 | no | The policy engine denied the action (DS-28) |
| `unknown_command_type` | not_found | 404 | no | No such command type or query, or a command registered `is_internal_only` named over a transport; `details` lists close matches, never internal-only commands |
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
| `make_to_order_warehouse_mismatch` | validation | 422 | no | A sales order line is in a warehouse where its item has no planning row while the item is planned `make_to_order` in another warehouse; use that warehouse ([ADR-0036](../adr/0036-multi-level-mrp.md) rule 9) |
| `movement_not_allowed_at_processor` | validation | 422 | no | Only transfers, production issues and returns, and count differences post at a processor location ([ADR-0037](../adr/0037-subcontracting.md) rule 1) |
| `service_receipt_without_operation` | validation | 422 | no | A service receipt line needs a purchase line tied to a production order operation ([ADR-0037](../adr/0037-subcontracting.md) rule 11) |
| `processor_location_missing` | precondition | 422 | no | An external operation with components names a supplier without an active processor location; `details` name the supplier ([ADR-0037](../adr/0037-subcontracting.md) rule 2) |
| `attachment_too_large` | too_large | 413 | no | The file exceeds `attachment_max_bytes` ([ADR-0038](../adr/0038-audit-and-observability.md) rule 13) |
| `attachment_type_not_allowed` | validation | 422 | no | The media type detected from the bytes is not on the allowed list ([ADR-0038](../adr/0038-audit-and-observability.md) rule 13) |
| `attachment_rejected` | precondition | 422 | no | The same bytes were rejected by the scanner before ([ADR-0038](../adr/0038-audit-and-observability.md) rule 14) |
| `attachment_not_available` | precondition | 422 | no | The attachment is not `clean` (pending scan or rejected): its bytes are not served, and a document linked to it cannot be posted ([ADR-0038](../adr/0038-audit-and-observability.md) rule 14) |
| `quantity_rounds_to_zero` | validation | 422 | no | The quantity converted to the inventory unit rounds to zero ([ADR-0018](../adr/0018-product-and-item-model.md) rule 11) |
| `invalid_timestamp` | validation | 422 | no | ADR-0007 rule 3 |
| `schema_version_unsupported` | validation | 422 | no | ADR-0008 rule 23; `details.served` lists the versions |
| `batch_too_large` | validation | 422 | no | More items than the installation's limit |
| `opening_control_account` | validation | 422 | no | An account opening line is on a receivable, payable or inventory account; those come from opening open items or opening stock ([ADR-0044](../adr/0044-data-migration-and-export.md) rule 7) |
| `opening_unit_value_differs` | validation | 422 | no | Opening stock lines of an item and valuation area have no total value to spread ([ADR-0044](../adr/0044-data-migration-and-export.md) rule 9) |
| `migration_not_open` | precondition | 422 | no | Opening documents post only while their migration is loading or reconciling, in its migration period ([ADR-0044](../adr/0044-data-migration-and-export.md) rule 2) |
| `migration_period_locked` | precondition | 422 | no | The migration period cannot be unlocked ([ADR-0044](../adr/0044-data-migration-and-export.md) rule 2) |
| `migration_incomplete` | precondition | 422 | no | `CompleteMigration` found an unposted batch, a company-currency clearing balance, an unaccepted difference or a failing invariant, before its group step and lock; `details` lists them ([ADR-0044](../adr/0044-data-migration-and-export.md) rule 12) |
| `uom_not_allowed` | validation | 422 | no | A price entry's unit, or a product's purchase or sales unit, is neither the product's inventory unit nor one of its product units; for a line, the unit has no product unit and no unit conversion to the inventory unit ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rules 3, 4, 13) |
| `price_list_entry_overlap` | validation | 422 | no | Entries of one list, item, unit and quantity break overlap in dates ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 3) |
| `price_list_currency_mismatch` | validation | 422 | no | The price list's currency differs from the document's (Phase 1, flagged; [ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 5) |
| `project_closed` | precondition | 422 | no | A posting names a closed project; drafts may still name it ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 9) |
| `partner_not_employee` | validation | 422 | no | A buyer or salesperson is not a partner with the active employee role ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 11) |
| `line_option_required` | validation | 422 | no | A required line option of the product has no value on the line ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 15) |
| `line_option_value_not_allowed` | validation | 422 | no | The line option value is not allowed for the product ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 15) |
| `negative_price` | validation | 422 | no | The list price plus the chosen options' extras is below zero ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 17) |
| `configuration_model_missing` | precondition | 422 | no | The configurable product has no released configuration model revision valid on the document date ([ADR-0046](../adr/0046-product-configuration.md) rule 2) |
| `configuration_value_out_of_range` | validation | 422 | no | A number is outside its characteristic's range or step, or a value is not allowed by the rules; `details` names the characteristic ([ADR-0046](../adr/0046-product-configuration.md) rules 3, 8) |
| `configuration_rule_invalid` | validation | 422 | no | A model revision's rule, table or default breaks the grammar or names a characteristic, value or number the product does not allow; `details` names it ([ADR-0046](../adr/0046-product-configuration.md) rule 4) |
| `configuration_incomplete` | validation | 422 | no | A configurable line leaves draft without a complete configuration; `details` lists the missing characteristics and the violations ([ADR-0046](../adr/0046-product-configuration.md) rule 10) |
| `configuration_invalid` | validation | 422 | no | A copied configuration is not valid under the model revision of the new document's date; `details` lists the violations ([ADR-0046](../adr/0046-product-configuration.md) rule 10) |
| `configuration_in_production` | precondition | 422 | no | A change order alters the configuration of a line linked to an open production order ([ADR-0046](../adr/0046-product-configuration.md) rule 10) |
| `configuration_warehouse_not_produced` | validation | 422 | no | A configurable line's warehouse is not a production warehouse of the product's product-level versions ([ADR-0046](../adr/0046-product-configuration.md) rule 10) |
| `configured_quantity_negative` | validation | 422 | no | Linear sizing of a component or operation would be negative at the characteristic's minimum or maximum ([ADR-0046](../adr/0046-product-configuration.md) rule 12) |
| `routing_conditions_shared` | validation | 422 | no | A routing with selection conditions would serve more than one configurable product ([ADR-0046](../adr/0046-product-configuration.md) rule 12) |
| `characteristic_in_use` | precondition | 422 | no | A used characteristic's mode, value type, unit, range, step or code, or a value's code, would change ([ADR-0046](../adr/0046-product-configuration.md) rule 3) |
| `item_configurable_product` | validation | 422 | no | `CreateItem` names a configurable product; its items are created only from configurations ([ADR-0046](../adr/0046-product-configuration.md) rule 2) |
| `configuration_immutable` | precondition | 422 | no | A configuration or its values would change (database trigger; [ADR-0046](../adr/0046-product-configuration.md) rule 9) |
| `configuration_characteristic_not_item_defining` | validation | 422 | no | A selection condition or sizing names a line option ([ADR-0046](../adr/0046-product-configuration.md) rule 12) |
| `option_extra_not_allowed` | validation | 422 | no | An option extra names a variant-mode value of a product that is not configurable, or is on a by-product list ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 13, [ADR-0046](../adr/0046-product-configuration.md) rule 15) |
| `quotation_expired` | precondition | 422 | no | A quotation is copied to an order after `valid_until` without `reprice` ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 3) |
| `quantity_exceeds_open` | validation | 422 | no | A copied or delivered quantity exceeds the source line's open quantity ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rules 2, 5) |
| `invoice_exceeds_delivered` | validation | 422 | no | A stock line would invoice more than its order line's delivered net less invoiced net ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 6) |
| `invoice_exceeds_ordered` | validation | 422 | no | A non-stock or service line would invoice more than its order line's open quantity ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 6) |
| `receipt_exceeds_order` | validation | 422 | no | A receipt exceeds the order line's open quantity beyond the receipt tolerance ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 11) |
| `purchase_order_required` | validation | 422 | no | A purchase invoice goods line for a stock item has no purchase order line ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 12) |
| `price_required` | validation | 422 | no | A line has neither a list price nor a manual price and is not free of charge ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 16) |
| `correction_exceeds_original` | validation | 422 | no | A return, credit or cumulative correction would exceed the original ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 20) |
| `demand_on_hold` | precondition | 422 | no | A line's demand row is on credit hold, at pick release or delivery ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 18) |
| `order_currency_mismatch` | validation | 422 | no | An invoice, return or note of order lines is not in the order's currency ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 2) |
| `reversal_not_latest` | precondition | 422 | no | A document's GR/IR postings on an order line are not the latest of their side; correct by a return or a credit ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 13) |
| `demand_supply_not_released` | precondition | 422 | no | A pick release, delivery or receipt names a demand or supply row whose document is not approved yet (hold reason `not_approved`) ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rules 18–19) |
| `sales_order_required` | validation | 422 | no | A delivery line or sales invoice line of a stock item has no sales order line; create the order first ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 6) |
| `source_not_approved` | precondition | 422 | no | `source_lines` name a document that is not approved or later (draft, pending approval, rejected or canceled); `details` name the source ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 2) |
| `partner_role_missing` | validation | 422 | no | The document's partner does not hold the active role its type needs, such as `customer` for a quotation ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 3) |
| `money_account_negative` | precondition | 422 | no | A money account without overdraft would be below zero at the posting date or a later date ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 12) |
| `money_account_kind_mismatch` | validation | 422 | no | A payment's money account is not of the document type's kind (cash or bank) ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 3) |
| `bank_statement_unbalanced` | validation | 422 | no | A statement's opening balance plus its lines does not equal its closing balance ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 8) |
| `bank_statement_line_posted` | precondition | 422 | no | The line's document was created from it and is posted; the fix is `Reverse<Type>`, which unmatches the line ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 9) |
| `overdraft_not_allowed` | validation | 422 | no | Overdraft is allowed only on bank money accounts in company currency in Phase 1 ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 2) |
| `netting_agreement_missing` | validation | 422 | no | The regime requires an attached netting agreement ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 10) |
| `manual_posting_to_control_account` | validation | 422 | no | A general journal line is on an account whose effective control kind is `receivable`, `payable` or `loan` and the regime does not allow it, or is `inventory`, `gr_ir`, `cost_object` or `fixed_asset`, which is never allowed ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 15; ADR-0014 rule 10) |
| `write_off_above_limit` | validation | 422 | no | A small-difference write-off exceeds `cash.small_difference_limit` ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 11) |
| `money_account_line_not_allowed` | validation | 422 | no | A payment's `account` line names a money account's operational account; use `money_transfer` or `currency_exchange` ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 12 note) |
| `money_transfer_currency_mismatch` | validation | 422 | no | The two money accounts of a money transfer are in different currencies; use `currency_exchange` ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 12 note) |
| `tax_return_not_filed` | precondition | 422 | no | The tax offset job found no filed return of the period for its form ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 23 note) |
| `report_definition_missing` | precondition | 422 | no | No report definition of that code is in force on the end date ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 2) |
| `report_definition_protected` | validation | 422 | no | A company definition may not use the code of a package definition of its regime ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 11) |
| `report_definition_invalid` | validation | 422 | no | A company definition breaks the grammar: a bad term, an unknown line or field, or a cycle; `details` names the line ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rules 4–11) |
| `report_scope_incomplete` | permission | 403 | no | Statutory reports and books need the whole company; the actor's record scope is limited ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 17) |
| `report_range_invalid` | validation | 422 | no | The report range or comparative range is invalid, e.g. `from` after `to` ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 13) |
| `report_range_before_opening` | precondition | 422 | no | The range reaches before the migration's opening date and has no stored values ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 14) |
| `report_not_fileable` | precondition | 422 | no | Only package statements with `is_fileable` can be filed ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 19) |
| `print_template_missing` | precondition | 422 | no | No print template for the subject and language, and no default ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 27) |
| `print_template_invalid` | validation | 422 | no | The template does not compile or does not render against the contract's example: unknown field, filter or tag; `details` give the position ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 24) |
| `print_template_audience_invalid` | validation | 422 | no | An external template declares a field class ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 24) |
| `print_contract_version_unsupported` | validation | 422 | no | The template's contract version is not served by this core ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 25) |
| `document_not_approved` | precondition | 422 | no | An external print of a document, or a message that links it or attaches its print, while the document is in `draft` or `pending_approval`; approve it first ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 28; [ADR-0052](../adr/0052-minimal-crm.md) rule 28) |
| `report_render_job_mismatch` | precondition | 422 | no | The render job named for filing is not a `done` report job of the same code, range and definition content hash as the version in force; `details` give the reason; render again ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 19) |
| `list_export_query_not_allowed` | precondition | 422 | no | `CreateListExport` named a query of module `reporting`; statutory reports and books are exported only by `RenderReport` ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 20) |
| `render_failed` | validation | 422 | no | Job outcome: the template or definition failed at run time; recorded on the render job ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 20) |
| `render_too_large` | too_large | 413 | no | Job outcome: the file exceeds `render_max_bytes`; narrow the range ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 20) |
| `render_output_invalid` | validation | 422 | no | Job outcome: the XML output fails the package's schema ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 21) |
| `agent_mode_off` | precondition | 422 | no | The agent type is `off` for the company, or the LLM is off ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rules 5, 15) |
| `agent_budget_exceeded` | precondition | 422 | no | A run or daily agent budget would be exceeded; `details` names the limit ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rules 22–24) |
| `agent_scope_unresolved` | precondition | 422 | no | The agent type's scope resolver found no scope for the subject, for example no single verified supplier; the wake-up consumer skips ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 15; [ADR-0051](../adr/0051-agent-workflows.md) rule 20) |
| `approver_is_submitter` | permission | 403 | no | The person who submitted a proposal promoting an agent type to assisted mode tried to approve it; a second person must approve ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 14) |
| `promotion_evidence_stale` | precondition | 422 | no | The agent type's behavior hash or seat models no longer equal the frozen promotion evidence the proposal names; create new evidence ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 14) |
| `workflow_owner_not_permitted` | precondition | 422 | no | `UpdateAgentTypeSetting` would leave a `workflow_owner_id` who does not hold `start_agent:<agent_type>` in the company ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 14; [ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 24) |
| `llm_provider_unavailable` | unavailable | 503 | yes | The LLM provider failed after retries and fallback, or its circuit is open ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 6) |
| `llm_output_invalid` | validation | 422 | no | An LLM output failed its schema or checks three times ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 35) |
| `llm_routing_refused` | permission | 403 | no | An LLM request still held a personal value with the routing switch on, or held a secret ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rules 9, 11) |
| `tool_not_allowed` | permission | 403 | no | The tool is not on the agent run's list ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 29) |
| `agent_kind_not_declared` | precondition | 422 | no | `StartAgentRun` names a work item kind or subject table the agent type does not accept ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 15) |
| `tainted_read_out_of_scope` | permission | 403 | no | A tainted agent run asked for rows outside its scope, its work item, its own drafts and reference data, or used such a row, even one read before the taint, in a prompt or a command input ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rules 25, 27) |
| `untrusted_read_not_allowed` | permission | 403 | no | A run of an agent type that must stay clean asked for untrusted fields ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 28) |
| `tainted_run_not_allowed` | permission | 403 | no | A tainted agent run, or a consumer command for a tainted event, sent a command not registered `is_draft_only`; `CompleteAgentRun` is exempt ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 26; [ADR-0013](../adr/0013-outbox-and-events.md) rule 11) |
| `list_export_too_large` | precondition | 422 | no | The list has more rows than `list_export_max_rows` ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 54) |
| `shadow_evidence_insufficient` | precondition | 422 | no | A promotion to assisted mode, or the enabling of an auto-post rule, lacks the shadow evidence its threshold requires ([ADR-0051](../adr/0051-agent-workflows.md) rules 4, 18) |
| `exchange_rate_missing` | precondition | 422 | no | No quote for the source, pair, kind and date, or the quote is too old; `details` names them and the commands that add a quote ([ADR-0011](../adr/0011-multi-currency.md) rule 10) |
| `document_rate_out_of_tolerance` | precondition | 422 | no | A rate entered on the document differs from the lookup rate by more than the regime allows ([ADR-0011](../adr/0011-multi-currency.md) rule 12) |
| `regime_configuration_missing` | precondition | 422 | no | The accounting regime does not declare a value the posting needs; `details` names the key, regime, date and fix ([ADR-0011](../adr/0011-multi-currency.md) rule 13, [ADR-0016](../adr/0016-localization-package-structure.md) rule 10) |
| `regime_setting_unverified` | precondition | 422 | no | The operation needs a rule or template entry flagged unverified, which this environment refuses ([ADR-0016](../adr/0016-localization-package-structure.md) rule 12) |
| `posting_period_not_open` | precondition | 422 | no | The period's area does not allow this actor to post; `details` names period, area, state and who may post ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 5) |
| `posting_date_too_far_ahead` | precondition | 422 | no | The posting date is beyond the periods that accept postings; `details` names the last allowed date ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 6) |
| `period_sequence_violation` | precondition | 422 | no | A period state change would break the period sequence; `details` names the blocking period ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 8) |
| `close_checklist_incomplete` | precondition | 422 | no | A required close task of the area is not done or no longer current; `details` lists them ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 12) |
| `account_determination_missing` | precondition | 422 | no | No determination row matches the key and determinants; `details` names them and the command that adds a row ([ADR-0015](../adr/0015-account-determination.md) rule 10) |
| `tax_matrix_missing` | precondition | 422 | no | No tax matrix row for the direction, partner tax group, item tax group and tax date; `details` names them ([ADR-0041](../adr/0041-tax-engine.md) rule 7) |
| `tax_rate_missing` | precondition | 422 | no | The tax code has no rate on the tax date ([ADR-0041](../adr/0041-tax-engine.md) rule 7) |
| `tax_matrix_row_invalid` | validation | 422 | no | A company tax matrix row would shadow a package key; company rows are allowed only for company-added groups ([ADR-0041](../adr/0041-tax-engine.md) rule 3) |
| `tax_inclusive_multiple_codes` | validation | 422 | no | Prices including tax are allowed only with one percent tax code on the line ([ADR-0041](../adr/0041-tax-engine.md) rule 9) |
| `account_determination_mismatch` | precondition | 422 | no | The determined account does not have a system account or control kind the key requires ([ADR-0015](../adr/0015-account-determination.md) rule 12) |
| `document_line_referenced` | precondition | 422 | no | A line another document refers to cannot be deleted ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 3) |
| `referenced_line_immutable` | precondition | 422 | no | A referenced line's item, unit or warehouse cannot change ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 3) |
| `quantity_below_fulfilled` | precondition | 422 | no | A line's quantity cannot go below what referring documents fulfilled ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 3) |
| `change_pending` | conflict | 409 | no | A change waits for approval; cancel the change first (`CancelChange<Type>`), or update after the decision ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 4) |
| `approval_context_changed` | precondition | 422 | no | The policy now requires a higher approval procedure than the approval obtained; `details` give approved and current amounts and procedures; submit again ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 14) |
| `work_item_claimed` | conflict | 409 | no | Another person or agent run holds the work item's claim ([ADR-0042](../adr/0042-work-queue.md) rule 11) |
| `work_item_claim_lost` | conflict | 409 | no | The agent run no longer holds the claim of its bound work item; a person took it or the lease expired ([ADR-0042](../adr/0042-work-queue.md) rules 9, 11) |
| `policy_rule_invalid` | validation | 422 | no | A rule allowing a non-human actor lacks an owner, confirmation or maximum, or the company's rule set would give a looser decision for a riskier input; `details` names the inputs ([ADR-0043](../adr/0043-policy-and-approval.md) rules 3, 11) |
| `e_invoice_invalid` | validation | 422 | no | The package's e-invoice validation failed; `details.package_code` names the package rule ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 8) |
| `e_invoice_record_unreadable` | validation | 422 | no | The package's `EInvoiceRecordReader` could not read the imported file (schema, encoding or a missing required field); `details.package_code` names the reader's rule ([ADR-0051](../adr/0051-agent-workflows.md) rule 20) |
| `e_invoice_supplier_mismatch` | validation | 422 | no | The supplier confirmed for an incoming e-invoice record does not have the record's seller tax ID ([ADR-0051](../adr/0051-agent-workflows.md) rule 20) |
| `proposal_required` | permission | 403 | no | An agent, or a command carrying an origin agent run, may reach this command only through an approved change proposal; the `fix` names `CreateChangeProposal` ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 4) |
| `origin_run_submit_not_allowed` | permission | 403 | no | `Submit<Type>` from an actor carrying an origin agent run; a person submits what an agent chain drafted ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 6; [ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 8) |
| `target_changed` | conflict | 409 | no | The target record changed since `expected_version` was read; for an approved change proposal, the proposal returns to draft with the new plan ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 3) |
| `outbound_content_out_of_scope` | precondition | 422 | no | A customer draft refers to another partner's records or carries cost or margin fields ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 14) |
| `duplicate_external_document` | conflict | 409 | no | An external document with the same business key exists in the company; `details` name the existing record ([ADR-0030](../adr/0030-commercial-seams-and-imports.md) rule 10) |
| `duplicate_draft` | conflict | 409 | no | A document for the same work item, workflow step, draft ordinal and document type exists, in any state except canceled; `details` name it ([ADR-0030](../adr/0030-commercial-seams-and-imports.md) rule 11) |
| `bill_of_materials_cycle` | validation | 422 | no | Releasing the revision would create a cycle through released bills of materials, outputs counted as children; `details.path` lists it ([ADR-0033](../adr/0033-production-master-data.md) rule 8) |
| `revision_released` | precondition | 422 | no | A released revision, or its content, would change; create a new revision (database trigger; [ADR-0033](../adr/0033-production-master-data.md) rule 3, [ADR-0046](../adr/0046-product-configuration.md) rule 4) |
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
| `cost_object_closed` | precondition | 422 | no | A line names a closed cost object; only the costing job's `production_cost_settlement` may still post to it ([ADR-0035](../adr/0035-production-costing.md) rule 1) |
| `open_item_mismatch` | validation | 422 | no | A line refers to an open item of another partner, account, currency or company ([ADR-0026](../adr/0026-open-item-core.md) rule 4) |
| `open_item_oversettled` | precondition | 422 | no | A settlement exceeds the item's open transaction amount, or the item is settled; post the excess as a payment on account (interim, flagged) ([ADR-0026](../adr/0026-open-item-core.md) rules 6, 8) |
| `open_item_settled` | precondition | 422 | no | The document's open items have settlements from other documents; reverse those first ([ADR-0026](../adr/0026-open-item-core.md) rule 11) |
| `payment_term_invalid` | validation | 422 | no | Payment term line percents do not sum to 100 ([ADR-0026](../adr/0026-open-item-core.md) rule 5) |
| `open_item_revaluation_later` | precondition | 422 | no | Unused: the check was dropped; a settlement or origin reversal dated before a revaluation takes its as-of carrying amount and makes the revaluation stale. Kept so the code is not reused ([ADR-0026](../adr/0026-open-item-core.md) rule 6 note) |
| `partner_has_open_items` | precondition | 422 | no | The partner's reconciliation account cannot change while it has open items; use `TransferPartnerOpenItems` ([ADR-0026](../adr/0026-open-item-core.md) rule 12) |
| `control_dimension_missing` | precondition | 422 | no | A line on an account whose control kind is active lacks a required dimension (partner and open item, item and warehouse, cost object, fixed asset; loan: partner and open item); trigger-level failures map to it (ADR-0014 rule 10; [ADR-0025](../adr/0025-later-phase-seams.md) rule 4) |
| `subledger_activation_date_not_reached` | precondition | 422 | no | A line on an activated subledger account is dated before the company's activation date ([ADR-0025](../adr/0025-later-phase-seams.md) rule 4) |
| `role_assignment_invalid` | validation | 422 | no | Owner scopes that do not fit: edit wider than read, `branch` without record scope, `company` with one, or an owner scope on a non-user assignment ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 13) |
| `delegation_invalid` | validation | 422 | no | A delegation to oneself, to an inactive user or one without an assignment in the company, of assignments that are not the delegator's, of delegated authority, or of a TOTP role to a substitute without TOTP ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 21) |
| `department_cycle` | validation | 422 | no | A department's parent chain would loop ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 6) |
| `employee_manager_cycle` | validation | 422 | no | An employee's chain of managers would loop ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 6) |
| `employee_organization_command_required` | validation | 422 | no | `CreatePartner`, `UpdatePartner` or a change proposal names an employee's `department_id`, `manager_partner_id` or `user_account_id`; only `UpdateEmployeeOrganization` changes them ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 6) |
| `approval_pool_invalid` | validation | 422 | no | An active pool without an active stage, stage minimum ranks that decrease, a rank that requires no stage, a stage without a member, a selector row naming an inactive pool, `general` deactivated, or a selector that sends a riskier document to a pool with fewer approvals ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rules 2–4) |
| `last_owner_required` | precondition | 422 | no | The change would leave the company without a user holding every permission of the template `owner` ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 12) |
| `user_shared_across_companies` | precondition | 422 | no | The user is linked to another company too (a current or future assignment that is not pending); only an operator disables the account, changes its name or e-mail, resets its password or clears its lockout ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 3) |
| `small_company_mode_not_allowed` | precondition | 422 | no | More than two active users hold a posting or approval permission ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 20) |
| `small_company_mode_active` | precondition | 422 | no | The change would give a third user a posting or approval permission while the small-company mode is on ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 20) |
| `approval_already_given` | precondition | 422 | no | The person, or the delegator they act for, already counts in an approval of this round ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 7) |
| `approval_would_strand_stage` | precondition | 422 | no | This approver is needed to fill a later required stage and nobody else can; another person approves this stage, or the author updates or cancels, or the stage members change ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 7) |
| `approval_plan_empty` | precondition | 422 | no | A decision requires a rank but the selected pool requires no stage for it ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 5) |
| `consent_missing` | precondition | 422 | no | The message's purpose needs consent that the data subject has not given ([ADR-0019](../adr/0019-partners-and-crm-foundation.md) rule 9) |
| `public_mail_domain` | validation | 422 | no | A public mail domain cannot identify a partner ([ADR-0052](../adr/0052-minimal-crm.md) rule 5) |
| `interaction_in_future` | validation | 422 | no | A call, meeting or chat is dated in the future; appointments come after Phase 1 ([ADR-0052](../adr/0052-minimal-crm.md) rule 6) |
| `interaction_already_matched` | precondition | 422 | no | The interaction already has a partner; `UnmatchInteraction` first ([ADR-0052](../adr/0052-minimal-crm.md) rule 10) |
| `link_partner_mismatch` | precondition | 422 | no | The interaction is unmatched, or the linked document or complaint has no partner or another partner than the interaction or complaint; also a match or unmatch that would conflict with an existing link ([ADR-0052](../adr/0052-minimal-crm.md) rule 9) |
| `recipient_not_partner_contact` | validation | 422 | no | A recipient is not a contact of the message's partner ([ADR-0052](../adr/0052-minimal-crm.md) rules 27, 28) |
| `recipient_address_missing` | precondition | 422 | no | The message has no `to` recipient, or a recipient contact is inactive or has no e-mail address ([ADR-0052](../adr/0052-minimal-crm.md) rule 28) |
| `mailbox_not_sending` | precondition | 422 | no | The sending mailbox has sending disabled ([ADR-0052](../adr/0052-minimal-crm.md) rule 28) |
| `automatic_send_not_allowed` | permission | 403 | no | A non-human actor tried to send: agents never send; a system job sends only the company's automatic types, untainted and without an origin agent run ([ADR-0052](../adr/0052-minimal-crm.md) rule 28) |
| `data_subject_kind_invalid` | validation | 422 | no | A processing basis, request or erasure names a partner that is an organization ([ADR-0052](../adr/0052-minimal-crm.md) rule 23) |
| `consent_evidence_missing` | validation | 422 | no | A consent basis needs the interaction that records it; silence is never consent ([ADR-0052](../adr/0052-minimal-crm.md) rule 23) |
| `approval_required` | precondition | 422 | no | The policy engine requires an approval first (DS-28) |
| `approval_hold_not_allowed` | precondition | 422 | no | `Submit`, `Approve` or `Reject` on a document whose type allows an approval hold only by regime, while the regime setting `documents.issuance_without_delay` is true for its date; `details` name the setting; issue or post it directly ([ADR-0053](../adr/0053-core-neutrality.md) rule 8) |
| `invalid_state_transition` | precondition | 422 | no | The command is not allowed in the document's (including `issuing` and change states, ADR-0028) or warehouse task's state; `details` lists the allowed commands ([ADR-0009](../adr/0009-document-lifecycle.md) rule 5) |
| `posting_date_mismatch` | validation | 422 | no | `Post` carries a `posting_date` different from the document's ([ADR-0009](../adr/0009-document-lifecycle.md) rule 9) |
| `document_referenced` | precondition | 422 | no | Delete, cancel or reverse of a document that other documents refer to ([ADR-0009](../adr/0009-document-lifecycle.md) rules 7, 19) |
| `rate_limited` | rate_limited | 429 | yes | `details.retry_after_seconds` says when to retry |
| `internal_error` | internal | 500 | no | Anything unexpected; the response carries only a reference for the logs |
| `timeout` | unavailable | 503 | yes | `transaction_timeout` reached (ADR-0008 rule 11) |

### Check results

The check-result catalog of [ADR-0040](../adr/0040-ui-architecture.md) rule 10: findings that do not stop a command, returned in `checks`. One catalog holds errors and check results, and their codes never collide; this table lists the check results apart from the errors above.

| Code | Category | HTTP | Retryable | When |
| --- | --- | --- | --- | --- |
| `partner_duplicate_suspected` | check result | — | — | Another partner of the company has the same tax ID; the command succeeds and a work item is created ([ADR-0019](../adr/0019-partners-and-crm-foundation.md) rule 4) |
| `e_invoice_signature_unverified` | check result | — | — | An imported incoming e-invoice record's signature check did not pass; the purchase invoice agent starts only after the importer confirms its supplier with `ConfirmEInvoiceSupplier` ([ADR-0051](../adr/0051-agent-workflows.md) rule 20) |
| `partner_snapshot_stale` | check result | — | — | The document's partner data differs from the partner master; warns (interim, flagged; for the tax ID on e-invoiced types `Issue` is rejected with `e_invoice_invalid`) ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 16) |
| `duplicate_suspected` | check result | — | — | A bank statement line without a reference, or an e-mail with a reused `Message-ID` and different content, equals an existing one; both are kept ([ADR-0030](../adr/0030-commercial-seams-and-imports.md) rule 10) |
| `interaction_unmatched` | check result | — | — | An inbound message matched no partner or several, or its sender was not authenticated; a work item lists the candidates ([ADR-0052](../adr/0052-minimal-crm.md) rule 15) |
| `email_domain_shared` | check result | — | — | The domain already belongs to another active partner; e-mails from it are never matched by domain ([ADR-0052](../adr/0052-minimal-crm.md) rule 5) |
| `component_shortage` | check result | — | — | Components could not be fully reserved; `details` list the missing quantities ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 9) |
| `issue_above_requirement` | check result | — | — | The issue exceeds the component line's open requirement ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 11) |
| `yield_above_previous_operation` | check result | — | — | Cumulative yield and scrap exceed the previous internal operation's cumulative yield ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md) rule 12) |
| `normal_capacity_missing` | check result | — | — | A cost center has fixed overhead but no normal capacity for the period; all of it was absorbed ([ADR-0035](../adr/0035-production-costing.md) rule 7) |
| `planned_wip_capped` | check result | — | — | An order's planned WIP exceeded its cost; WIP was capped and its outputs valued at zero ([ADR-0035](../adr/0035-production-costing.md) rule 9) |
| `capacity_not_checked` | check result | — | — | A bin capacity could not be checked because weight or dimensions are missing; `details` names the fields ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `bin_capacity_exceeded` | check result | — | — | A confirmed target bin exceeds its capacity; the fact is recorded ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `mixed_stock_not_allowed` | check result | — | — | A confirmed target bin breaks its mix rules; the fact is recorded ([ADR-0023](../adr/0023-warehouse-management.md) rule 12) |
| `no_pickable_stock` | check result | — | — | No eligible stock for a pick (status, bin type, shelf life, open tasks); the line stays short and becomes an exception ([ADR-0023](../adr/0023-warehouse-management.md) rule 14) |
| `planning_parameter_missing` | check result | — | — | The run could not plan a node, or a firmed order, from its parameters; `details.reason`: `planning_row_missing` (open demand on a node without a planning row), `supplier_missing`, `route_missing`, `lead_time_missing`, `phantom_demand`, `production_version_missing`, `production_version_invalid`, `processor_route_missing` or `processor_location_missing` ([ADR-0024](../adr/0024-planning.md) rule 21; [ADR-0036](../adr/0036-multi-level-mrp.md) rules 1, 4, 5; [ADR-0037](../adr/0037-subcontracting.md) rules 2, 3) |
| `forecast_history_insufficient` | check result | — | — | Fewer than 52 non-event weeks of history; `details.tier` is `none` (no history, no forecast), `short_mean` (under 8 weeks: their mean) or `unindexed` (8 to 51 weeks: the 8-week average without indices) ([ADR-0024](../adr/0024-planning.md) rule 11) |
| `customs_assessment_differs` | check result | — | — | Assessed import tax differs from the amount recomputed from the tax codes; the assessed amount is kept ([ADR-0021](../adr/0021-landed-cost.md) rule 10) |
| `scan_unavailable` | check result | — | — | No scanner is deployed and scan mode is `optional`; the attachment passed unscanned ([ADR-0038](../adr/0038-audit-and-observability.md) rule 14) |
| `audit_changes_summarized` | check result | — | — | The command changed more than 10,000 tracked rows; the audit record stores field names and hashes instead of values ([ADR-0038](../adr/0038-audit-and-observability.md) rule 3) |
| `quantity_rounded` | check result | — | — | A quantity was rounded to its unit's precision; `details` carry the entered and the rounded value so the user sees both ([ADR-0018](../adr/0018-product-and-item-model.md) rule 11) |
| `purchase_price_missing` | check result | — | — | A cost estimate asked for the purchase price, and the preferred supplier has none; the actual average was used ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 6) |
| `price_missing` | check result | — | — | `find_price` found no price for the line's item, unit, quantity and date; the line is outside the list ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rules 4, 5) |
| `configured_explosion_empty` | check result | — | — | The explosion of a configured item selected no component ([ADR-0046](../adr/0046-product-configuration.md) rule 13) |
| `configured_stock_available` | check result | — | — | A planning run planned an order for a configured line while free stock of the same configured item exists; a person may reserve it ([ADR-0046](../adr/0046-product-configuration.md) rule 14) |
| `match_quantity_exceeded` | check result | — | — | A purchase invoice line's invoiced net exceeds the ordered quantity beyond tolerance ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 14) |
| `match_price_difference` | check result | — | — | A purchase invoice unit price differs from the order price beyond tolerance ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 14) |
| `invoice_before_receipt` | check result | — | — | A purchase invoice line is invoiced before its goods are received (informational; [ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 14) |
| `price_list_currency_differs` | check result | — | — | The partner's list, or the default list of the kind, is in another currency than the document; the document carries no list and its prices are entered ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 5) |
| `bank_statement_gap` | check result | — | — | A statement's opening balance differs from the previous statement's closing balance ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 8) |
| `settlement_rate_unusual` | check result | — | — | A payment's rate is outside the tolerance of the transaction rate; it sets `is_rate_unusual` for the policy ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 12) |
| `settlement_rate_unchecked` | check result | — | — | No transaction-rate quote exists, so the payment's rate was not checked ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 12) |
| `report_check_failed` | check result | — | — | A check line of a statement is not zero; `details` name the line and value ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 9) |
| `report_account_not_covered` | check result | — | — | Accounts of a covered type have a balance or turnover that no term of the statement names ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 9) |
| `report_comparative_missing` | check result | — | — | A comparative cell or a `carry:` term has no computable value, no filing over the comparative range and no stored comparative value; the cell stays empty ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rules 5, 14) |
| `report_turnover_incomplete` | check result | — | — | A range straddling the cut-over reads turnover of an account without opening turnover, turnover that keeps closing entries, or a counterpart or cash-flow term, which opening turnover cannot pair ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 14) |
| `report_periods_open` | check result | — | — | A regular period of the range is not locked in `general`, so figures may still change ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 19) |
| `report_snapshot_stale` | check result | — | — | Stored on a filing: postings or stored comparative values changed after the render job ran; a best-effort signal, never a refusal; the difference view shows the drift ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 19) |
| `policy_no_eligible_approver` | check result | — | — | Retired: no command returns it; `approval_stage_unsatisfiable` replaces it ([ADR-0043](../adr/0043-policy-and-approval.md) rule 13; [ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 4) |
| `segregation_conflict_found` | check result | — | — | In assignment mode `warn`, the user's permissions hold both sides of an enabled segregation rule ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 18) |
| `approval_stage_unsatisfiable` | check result | — | — | On save, for some rank, or at `Submit`, for the document's plan: the required stages cannot be filled by distinct eligible people, keeping the preparer out unless the small-company mode is on ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 4) |
| `tax_code_differs_from_matrix` | check result | — | — | A line's tax code differs from the matrix's, where ADR-0018 rule 16 allows it ([ADR-0041](../adr/0041-tax-engine.md) rule 7) |
| `tax_amount_differs_from_computed` | check result | — | — | A supplier's stated tax differs from the computed one beyond `tax.stated_amount_tolerance`; the stated amount is used ([ADR-0041](../adr/0041-tax-engine.md) rule 10) |
| `outbound_content_flagged` | check result | — | — | A customer-facing draft refers to another partner's records or carries cost or margin fields; sending it would be refused with `outbound_content_out_of_scope` ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 36) |

## Canonical plan for hashing

Warehouse task proposals (target and source bins) and planning run results are listed like events and are not part of the hashed plan ([ADR-0023](../adr/0023-warehouse-management.md) rule 11; [ADR-0024](../adr/0024-planning.md) rule 17).

1. Take the full plan and result, before field filtering.
2. Replace each ID created by `context.new_id(table)` during the run with `new:<table>:<n>`, numbering per table from 1 in creation order. Keep IDs that existed before the run, client-supplied IDs and client-supplied instants.
3. Remove values of the types `DocumentNumber` and `SystemInstant`.
4. Serialize `{"journal_lines": …, "stock_movements": …, "document_versions": …, "record_versions": …, "result": …, "checks": …}` ([ADR-0031](../adr/0031-design-simplifications.md) rule 1; the two new lists hold canonical content, tokenized by steps 2–3) as JSON with keys sorted, separators `,` and `:` without spaces, UTF-8, no escaping of non-ASCII characters. Numbers, dates and instants are already strings in canonical form. `checks` is the list of `[code, field]` pairs of the check results whose code is hashed, a null field as `""`, duplicates removed, sorted by code then field ([ADR-0040](../adr/0040-ui-architecture.md) rule 10).
5. `plan_hash` = lowercase hex SHA-256 of those bytes. A batch hashes the list of item plans in item order the same way.
