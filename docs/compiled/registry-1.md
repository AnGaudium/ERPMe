Module: registry    Chunk: 1 of 5    Source ADRs: ADR-0006, ADR-0008
Build step(s): 0, 1, 6    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `registry` compiled spec, chunk 1: command registry, envelope, dispatcher, simulation, plan hash, idempotency, batches, queries, errors

## Purpose

`registry` owns the one command registry through which every write goes, the dispatcher, the command and query envelope, the plan and its hash, the idempotency store `idempotency_record`, command batches, schema versions and the error shape. This chunk states that law (ADR-0008, with ADR-0006.R3 and ADR-0006.R5). Handlers belong to the modules that register them; permissions and record visibility are law of `permissions` (DS-15), policy points of `policy`, the outbox of `outbox`. Settings, presets, extension points, list variants and `module_activation` are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `idempotency_record` | One claimed idempotency key of an executed command or batch, with its request hash and stored response (R33-R36) | `id`; (`actor_kind`, `actor_id`, `scope`, `idempotency_key`) unique | `company` (`company_id` null for installation scope) | `registry` |

`module_activation` (`docs/design/DS-28-settings.sql`, owner `registry`) is named by ADR-0022.R2.N14 and ADR-0015.R11.N1; its row is in chunk 5.

Reads: `company` (`master_data`); `open_item` (`ledger`); `audit_record` (`audit`).

## Commands and queries

None: the units of this chunk register no command or query by name; they state how every command and query is registered, sent, checked and answered.

Transports, not registered commands: the batch endpoint `POST /api/command-batches` and its MCP tool `command_batch` (R37); the query endpoint `POST /api/queries/<snake_case query>` (R39); the hand-written exceptions of R18. Jobs: the daily deletion of `idempotency_record` rows past retention (R36).

Error codes bound to no named command: `unknown_command_type` (R7, R10), `declaration_violation` (R10, in tests), `tool_not_allowed`, `tainted_run_not_allowed`, `proposal_required` (R11, R15, R16), `record_not_found` (R15), `unknown_field` (R20), `plan_hash_mismatch` (R27, R28, R38), `as_of_date_out_of_range` (R29), `post_review_required` (R30), `idempotency_key_reused` (R33), `schema_version_unsupported` (R40). `invalid_state_transition` reads the registered `subject_table` and `allowed_states` (R5).

## Rules

### Registry and references

R1. Every write goes through one command registry. A command is a pydantic payload wrapped in one envelope; command batches use the same envelope around an ordered list of items, and queries use it without the write fields. A simulation returns the plan and its `plan_hash`. The field-level specification is `docs/design/DS-04-command-envelope.md`.
Source: ADR-0008.D0

R2. A `Create` command accepts an optional `id`. If given, it must be a UUID version 7, otherwise the command is rejected; if absent, the command layer generates it. So one command batch can refer to a record that an earlier command of the same batch creates. Idempotency (Principle 9) is unchanged. Rows of tables partitioned by `id` (ADR-0006.R22) always get server-generated IDs.
Source: ADR-0006.R3

R3. Commands refer to other records only by `id`; there is no second way to reference a record in a command. Human-readable keys (`code` for master data, the document number from DS-05; their uniqueness scope is set by DS-05 and DS-20) are used by queries: an agent finds an `id` with `List<Noun>` filtered by `code`, then sends the command. An error for an unknown `id` names the table and the `List<Noun>` query that finds valid IDs.
Source: ADR-0006.R5

R4. Each command type is registered once with: `command_type` (ADR-0004.R17), `schema_version` (semver), scope (`company` or `installation`), payload model, result model, handler, the error codes it can return, the permission it needs (DS-15) and `human_only`. Queries (`Get<Noun>`, `List<Noun>`, ADR-0004.R21) are registered the same way, with a result model and no handler effects, idempotency key or plan. Work item kinds are registered the same way (ADR-0042.R1).
Source: ADR-0008.R1

R5. Each command type declares `effect_class` (`posting`, `master_data_change`, `outbound_send`, `other`), required with no default; CI fails when a `Post<Type>` or `Reverse<Type>` command is not `posting` (ADR-0027.R17). Each command declares its `subject_table` and `allowed_states`, read by `invalid_state_transition` and `ListAllowedCommand`, and each check code declares `is_hashed` (ADR-0040.R8, ADR-0040.R10). Optional registrations of a command:
- `is_proposal_bound`: agents reach it only through change proposals (ADR-0029.R2, ADR-0029.R4);
- `is_policy_in_handler`: its policy inputs are read under locks (ADR-0030.R7);
- `is_consequence_posting` (ADR-0043.R5);
- `is_draft_only`: the only commands a tainted agent run may run (ADR-0050.R26).
Source: ADR-0008.R1

R6. Each command, query and capability declares its authorization leaf, and a command may declare a minimum level above its verb's. A query that totals over documents without returning them declares `is_owner_scoped: false` (ADR-0054.R7, ADR-0054.R8, ADR-0054.R15).
Source: ADR-0008.R1.N1

R7. A command may be registered `is_internal_only`: only a consumer or system job runs it, in process (R28). It gets no REST endpoint, MCP tool or tool definition (R18), and a request or batch item that names one over a transport returns `unknown_command_type`. The level expansion skips it, so no role holds it at any level; the job holds it by registration (ADR-0017.R13; ADR-0054.R8 note; DS-04).
Source: ADR-0008.R1.N2

R8. Registrations for automation (ADR-0058.R4 to ADR-0058.R6, ADR-0058.R18):
- A command may be registered `is_automation_allowed`: the `Create<Type>` commands of drafts an automation rule may create. Each is also `is_draft_only`, and never `posting`, `master_data_change`, `outbound_send`, `human_only`, `is_proposal_bound`, `CreateChangeProposal`, or a `Submit`, `Post`, `Issue`, `Approve`, `Reject` or `Reverse` (a CI check).
- Every command, consumer and scheduled job declares the event types it may emit, with discriminator values where the type has a discriminator; a declaration without values counts as every value.
- An event type may be registered `is_automation_trigger`, with a condition source query, typed condition fields taken only from the fields registered `is_gate_field`, an optional discriminator, watchable fields for update events and `is_replayable`.
- A command may be registered `is_hold`, and a module may declare decision points with input and output schemas and a code default for no match.
Source: ADR-0008.R1.N3

R9. Registrations for tunable functions (ADR-0059.R3, ADR-0059.R15, ADR-0059.R16, ADR-0059.R18, ADR-0059.R20):
- A deterministic function may declare tunable parameters: function code and version, authorization leaf, case tables, each parameter's type, default, bounds, `is_nullable` and `is_safety_cap`, order constraints between parameters, its stages and thresholds with small-company minimums, and its golden set.
- A field may be registered `is_gate_field`, an allowlist of deterministic fields; CI refuses it on any field with LLM lineage.
- Tables that backtests read declare their as-of date column. The function and each L2 kind declare their case tables and case-reference columns.
- A query may be registered held-out filtered; a drafting agent type's tool list holds only such queries (a CI check).
Source: ADR-0008.R1.N4

R10. Each command and query is declared in one Python module, `<module>/declarations/<snake_case type>.py`. The module holds its payload and result models and one typed `CommandDeclaration` or `QueryDeclaration`, with exactly the registry fields of R4 to R9: type, schema version, scope, subject table and allowed states, permission leaf, effect class and flags, error codes, check codes, the posting interfaces it calls, the events it emits, and the locks it takes by registered name. No field is declared anywhere else. Catalog values are generated `Literal` types, so pyright strict checks a declaration as it is written. `nativeflows-dev check` validates each declaration against the catalogs, the authorization areas and ADR-0004. In tests, `context` raises `declaration_violation` when a handler does something its declaration does not list. A declaration without a handler is not served (`unknown_command_type`) (ADR-0073.R1 to ADR-0073.R3).
Source: ADR-0008.R1.N5

R11. `human_only` marks actions the spec says agents may not take (closing periods, reversing posted documents; spec 14). The dispatcher refuses to execute such a command when the actor is an agent. Every agent actor runs under a fixed tool list, which never holds a `human_only` command (ADR-0050.R29, ADR-0050.R30), and the tool list is checked before `human_only`, so an agent run gets `tool_not_allowed` in both modes. Whether integrations may execute `human_only` commands is an open question for the author; until answered they are refused too. System jobs act as the spec defines (closing entries by actor `system` on behalf of the human who triggered the close, spec 07).
Source: ADR-0008.R2, ADR-0008.R2.N1

R12. Payload and result models are pydantic models with unknown fields rejected (`extra="forbid"`), using the `nativeflows.numeric` and `nativeflows.clock` types (ADR-0006.R13, ADR-0007.R3) and references by `id` only (R3).
Source: ADR-0008.R3

R13. A scan command carries each scanned field as a `scan` object (`raw` up to 512 characters, `symbology_identifier`, `source`: `wedge`, `camera` or `manual`, `decoder` for camera scans, `confirmed_as_read`) next to the field it fills. The handler parses and resolves `raw` again with the business date and the step's context and never trusts the client's own parse; `raw` and the free-text GS1 elements are untrusted text (ADR-0061.R16).
Source: ADR-0008.R3.N1

R14. A handler is a function `handle(context, payload) -> result`. It reads and writes only through the database connection, ID generator, clock and lock helpers in `context`. It makes no network call, reads no file, calls no LLM and starts no job directly; anything outside the database happens after commit through the outbox (DS-13). So a handler gives the same result for the same database state, payload and business date (D2, Principle 13). Queries it runs whose order affects the plan use `ORDER BY` on stable keys. Posting interfaces of other modules (such as `ledger.contract.write_journal_entry`) take this `context` and run inside the handler's transaction and plan, with no permission or idempotency step of their own (ADR-0022.R4).
Source: ADR-0008.R4

R15. For every command and every query the dispatcher checks permissions, record visibility and `human_only` (DS-15) before anything else runs, an idempotent replay included (steps 1 to 5 of R16). Handlers never do these checks themselves. A record the actor may not see is reported as `record_not_found`. Policy is asked at the policy points of ADR-0029.R6, and allowed-target commands from agents, or from any actor carrying an origin agent run, are rejected with `proposal_required` (ADR-0029.R4); an agent run's direct call meets `tool_not_allowed` first, because those commands are on no tool list (ADR-0029.R4.N2).
Source: ADR-0008.R5, ADR-0029.R6

R16. The dispatcher's checks run in one order (DS-04, dispatcher check order):
- (1) credential and actor context;
- (2) run gates that need no subject state: `tool_not_allowed`, then `tainted_run_not_allowed`, then the tainted reference scope;
- (3) `human_only` and `proposal_required`, by actor kind and origin agent run;
- (4) permission, with the `direct_master_data_change` deny;
- (5) record visibility: company, record scope, owner scope;
- (6) the idempotency replay lookup, which returns a stored response with no further check, otherwise the insert of R33;
- (7) the work item claim, skipped for shadow runs and at the same position in simulate mode;
- (8) state-dependent authorization (ADR-0017.R16, ADR-0054.R19, ADR-0055.R7);
- (9) the policy point and floors, inside the handler for `is_policy_in_handler`;
- (10) handler, audit and events. A replay skips steps 7 to 10.
Source: ADR-0008.R5.N1

R17. Before the checks of R16 the dispatcher assigns the causation chain and depth, from the caller and never from the request. It refuses an automation action above depth 3, one that is not automation-allowed, and an agent start on an agent's chain (DS-04, dispatcher check order, steps 1–2; ADR-0058.R12).
Source: ADR-0008.R5.N2

R18. REST endpoints, MCP tools, JSON Schema and TypeScript types are generated from the registry (Principle 10); nothing is hand-written per command. MCP tool names are the `snake_case` form of the command type or query (ADR-0004.R19). Which tools each agent type sees is a fixed list (DS-32, spec 03 rule 2): tool lists are fixed per agent type version, their definitions are generated from the registry like the MCP tools, LLM steps get queries only, and commands are run by workflow code after simulation (ADR-0050.R29 to ADR-0050.R32). The hand-written exceptions are the attachment upload endpoint, which streams bytes and then dispatches `CreateAttachment` (ADR-0038.R13), and the transport endpoints for sessions and the live stream (ADR-0040.R12).
Source: ADR-0008.R6

### Envelope and actor

R19. The command envelope fields are:
- `command_type`;
- `schema_version`: the major version the client was built for, an integer;
- `company_id`: required for company-scoped commands, absent for installation-scoped ones;
- `idempotency_key`;
- `mode`: `simulate` or `execute`;
- `expected_plan_hash`: required when `mode` is `execute`;
- `payload`;
- `include_canonical_plan`: like `mode`, not part of the request hash (ADR-0040.R9);
- `as_of_date`: optional, a `BusinessDate` (R20);
- `is_review_skipped`: optional, outside the request hash like `mode` (R30).
No other field is accepted.
Source: ADR-0008.R7, ADR-0008.R7.N1, ADR-0008.R13.N2

R20. `as_of_date` is the business date that every `clock.today(company)` read of the run returns (ADR-0007.R15 note). It is part of the request hash (R32). Every command response returns `as_of_date`, the date the run used. A client that executes after reviewing a simulation sends the simulation's `as_of_date` with `expected_plan_hash`. In a batch it covers every item. An installation-scoped command accepts no `as_of_date` (`unknown_field`); its response and canonical plan carry `as_of_date` null. Field-level: DS-04.
Source: ADR-0008.R7.N1, ADR-0008.R7.N2

R21. The dispatcher builds the actor context from the authenticated credential: actor kind (`human`, `agent`, `integration`, `system`) and `id`; for agents, integrations and system jobs, `on_behalf_of` (the accountable human bound to the credential, agent run or job when it was started); for agents, also `agent_run_id` (spec 03 rules 3, 7). None of these can be sent by a client, so text an agent has read cannot change whom it acts for. Whether that actor may act for that human is checked by DS-15. The dispatcher also derives an agent run's work item from the run, never from the request, and checks its claim (ADR-0042.R11).
Source: ADR-0008.R8

### Simulation and plan hash

R22. `mode: simulate` runs the same dispatcher and handler as `execute` in a transaction that is always rolled back (Principle 2). There is no separate simulation code in handlers. In both modes, `SET CONSTRAINTS ALL IMMEDIATE` runs before the plan is hashed, so deferred constraints fail in simulation as they would at commit. Handler and trigger paths use no sequence, no session-level advisory lock and no non-`LOCAL` `SET`, because these survive a rollback. A denial record is the one effect of a simulation that persists (ADR-0038.R5).
Source: ADR-0008.R9

R23. Simulation takes no lock on serialized rows (stock balance per item and warehouse, numbering counters) and consumes no document number. These tables are read and written only through the lock helpers in `context`; no other SQL, trigger or constraint reads them (CI check, DS-18). In simulate mode the helpers take no row lock and keep new values in memory for the rest of the run, and numbering returns a placeholder number unique within the run. Other writes still take ordinary row and unique-index locks until the rollback, so a simulation can briefly delay a real execution that touches the same document; it never holds stock or numbering locks. `open_item` is such a table (ADR-0026.R3).
Source: ADR-0008.R10

R24. Both modes run with `transaction_timeout` and `lock_timeout` (values in DS-18); exceeding them returns a retryable error.
Source: ADR-0008.R11

R25. The plan of a command is its journal lines and stock movements, in the order the handler produced them, plus its result; a command with no journal or stock effect has a plan of its result only. `plan_hash` is the lowercase hexadecimal SHA-256 of the canonical JSON of the plan: keys sorted, no whitespace, UTF-8, numbers and dates in their canonical string forms (ADR-0006.R13, ADR-0007.R3). The hash is computed over the full plan; the plan returned to the client is filtered by the actor's field permissions (DS-15).
Source: ADR-0008.R12

R26. Before hashing, every ID created through `context.new_id(table)` during the run (the only way a handler creates IDs) is replaced by a token `new:<table>:<n>` in creation order, and values of the types `DocumentNumber` and `SystemInstant` (system-set `_at` fields) are removed. Rows that appear in a plan never get their `id` from a trigger or column default (ADR-0006.R2 allows those only for rows outside plans); a test checks this. IDs of rows that existed before the run, client-supplied IDs and client-supplied instants stay (ADR-0007.R11).
Source: ADR-0008.R12

R27. Further plan content:
- Warehouse task proposals (target and source bins) are listed like events and never hashed (ADR-0023.R11); planning run results (hashes, planned orders, messages, exceptions) are listed the same way (ADR-0024.R17).
- The plan contains the canonical content of the document versions and records the command writes (ADR-0031.R1).
- The canonical plan has a key `checks`, the sorted `[code, field]` pairs of check results whose code is hashed; `include_canonical_plan` returns the canonical plan to the client (ADR-0040.R9, ADR-0040.R10).
- The canonical plan has a key `as_of_date`, the business date the run used. A simulation and an execution pinned to its date hash equally across midnight, and an execution without the pin on another business date returns `plan_hash_mismatch` with the new plan (DS-04, canonical plan for hashing).
Source: ADR-0008.R12, ADR-0008.R12.N1

R28. `mode: execute` requires `expected_plan_hash`. The command runs again and commits only if its `plan_hash` is equal; if it differs, the transaction is rolled back and `plan_hash_mismatch` returns the new plan and hash, so the client can review and resend. Only internal callers execute without a simulation: consumers and system jobs calling the dispatcher in process, never over REST or MCP, the change-proposal executor among them with its stored plan hash; they execute inside their own transaction under the same checks (ADR-0013.R9). Every other actor (people through the UI, agents, integrations and MCP clients) simulates first and executes with `expected_plan_hash` (Principle 2).
Source: ADR-0008.R13, ADR-0008.R13.N1

R29. The accepted range of `as_of_date` is the business date or the day before it; any other date returns `as_of_date_out_of_range`. Nothing needs a future date: `clock.today` is computed by the server. The dispatcher checks the range after step 6 of the check order (R16), so a replay of a committed execution still returns its stored response.
Source: ADR-0008.R13.N1, ADR-0008.R13.N3

R30. With the company setting `ui.post_review` at `on_exceptions`, a person's `Post<Type>` is still simulated and executed with `expected_plan_hash`. The client only skips showing the plan when the simulation's `review_reasons` is empty, and marks the execution with the envelope field `is_review_skipped`. The dispatcher recomputes the reasons before commit and refuses with `post_review_required` when any applies (ADR-0067.R12, ADR-0067.R13).
Source: ADR-0008.R13.N2

### Idempotency

R31. `idempotency_key` is required in both modes. A client builds one envelope; to execute it changes `mode` and adds `expected_plan_hash` and `as_of_date`. The key is a string of 1–128 characters from `A-Z a-z 0-9 _ - . :`; a UUID version 7 is recommended. Its scope is (actor, command type), and `command_batch` for batches (Principle 9).
Source: ADR-0008.R14, ADR-0008.R7.N1

R32. The request hash is the SHA-256 of the canonical JSON of the validated request (envelope without `mode`, `expected_plan_hash`, `is_review_skipped` and `include_canonical_plan`, plus the validated payload), so `"1.50"` and `"1.5"` give the same hash.
Source: ADR-0008.R15

R33. An execution's first statement, after the checks of R15, is `INSERT … ON CONFLICT DO NOTHING` of (actor, scope, key, request hash) into `idempotency_record`, which has a unique constraint on (actor, scope, key). If the row is inserted, the command runs and the response is written into that row before commit; if the command fails, the whole transaction, row included, rolls back, so a retry runs again. If a concurrent request holds the key, the insert waits (bounded by `lock_timeout`). If a committed row exists: same request hash, the stored response is returned; different hash, `idempotency_key_reused`. `idempotency_record` carries `company_id` (null for installation scope), compared null-safely by `INV-89` (ADR-0038.R8). Its DDL is in DS-05-platform.sql (owner `registry`) with `transaction_id xid8 NOT NULL DEFAULT pg_current_xact_id()`; the erasure guard of ADR-0038.R4 compares it with the current transaction, never `xmin`, which freezing rewrites.
Source: ADR-0008.R16, ADR-0008.R16.N1

R34. A simulation never writes `idempotency_record`. If the key already has a committed row with the same request hash, a simulation returns that stored response instead of running.
Source: ADR-0008.R17

R35. A replayed response is the stored response with `replayed: true`; everything else, including `mode: execute`, is as stored. The DS-16 invariant compares responses ignoring `replayed`.
Source: ADR-0008.R18

R36. `idempotency_record` is not partitioned. A daily job deletes rows older than the retention, the installation setting `commands.idempotency_retention_days` (a deployment value, default 90; dotted key as ADR-0063.R2 asks); rows are kept at least that long. These rows are not the audit log, which is never deleted (DS-36). Every executed command's record has an audit record (`INV-89`, ADR-0038.R8).
Source: ADR-0008.R19, ADR-0008.R19.N1

### Batches, queries, versions and errors

R37. A command batch has the envelope with `command_type` and `schema_version` replaced by `items`, an ordered list of `{command_type, schema_version, payload}`, all for the same company and actor. Its REST endpoint is `POST /api/command-batches` and its MCP tool is `command_batch`. All items are validated first and every validation error is reported (field paths `items[<n>].payload.<field>`); then the items run in order in one transaction, all or nothing, stopping at the first handler error, which names its item. Its plan is the list of item plans, hashed as one; one `expected_plan_hash` and one idempotency key cover the batch. An item refers to a record created by an earlier item through the client-supplied `id` (R2). A batch is not a command type, so no verb is needed.
Source: ADR-0008.R20

R38. A batch response returns, per item, its index, command type, result, number of journal lines, number of stock movements and the sum of its debit amounts in company currency (debit as DS-06 defines it), plus the batch `plan_hash`; the full plan is returned only when the request sets `include_plan: true`. The idempotency record stores the same summary, and a batch `plan_hash_mismatch` carries the same summary in `details` unless `include_plan` is true. The maximum number of items is an installation setting, default 1,000. Each item also carries `audit_record_id`, null in simulate mode (ADR-0038.R1). Command responses and batch items also carry `checks` (code, message, rule, field, details), stored with the response and summary (ADR-0040.R10).
Source: ADR-0008.R21

R39. A query is sent as `POST /api/queries/<snake_case query>` (or its MCP tool) with `schema_version`, `company_id` and `payload` (the filters); it has no `idempotency_key`, `mode` or `expected_plan_hash`. Filters travel in the body, never in the URL, so personal data does not reach access logs. `List<Noun>` returns at most `limit` rows (default 100, maximum 1,000), ordered by `id` unless the query defines another stable order, with a cursor for the next page. Queries read the same database as commands, so a committed execution is visible to the next query.
Source: ADR-0008.R22

R40. Each command type's and query's schema has a semver version. A change that only adds optional fields or new error codes is a minor version; any other change is a new major version. `schema_version` names the major version; the registry serves the current major and the previous one until the next LTS release (DS-37), then removes the old one. A request for a major version that is not served is rejected with `schema_version_unsupported`, naming the versions served.
Source: ADR-0008.R23

R41. Every error, on every transport, is a response `{"errors": [ … ]}` where each item has:
- `code`: a stable `snake_case` identifier from the registry's error catalog;
- `message`: English; the UI translates by `code`;
- `rule`: the reference that failed, such as `ADR-0007 rule 22`;
- `field`: path in the request, or null;
- `fix`: what the client should do;
- `retryable`: true or false, fixed per code in the catalog;
- `details`: an object, may be empty, filtered by field permissions.
Validation reports every field error it finds at once.
Source: ADR-0008.R24

R42. Each error code belongs to one category with a fixed HTTP status: `malformed` 400, `unauthenticated` 401, `permission` 403, `not_found` 404, `conflict` 409, `too_large` 413, `validation` 422, `precondition` 422 (a business rule failed), `rate_limited` 429, `internal` 500, `unavailable` 503. Over MCP the same body is returned as a tool error. An `internal` error never exposes stack traces or SQL. Rate limits themselves are set by DS-18 and DS-32. Agent budgets are set per run (the agent type version's declared ceilings), per company per day and per installation per day, and are reserved before each LLM call (ADR-0050.R22 to ADR-0050.R24); no per-agent-type daily limit binds in Phase 1 (ADR-0063.R29.N15); the rate limits of ADR-0022.R9 still apply.
Source: ADR-0008.R25

## Invariants

| Invariant | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-11` | command | A command retried with the same idempotency key returns the stored response, identical except for `replayed`, and the company's business-table fingerprints (DS-16 rule 9) are the same before and after the retry. | R28, R33, R35 |
| `INV-12` | command | Executing a command with the `plan_hash` of its simulation succeeds and produces the simulated plan. | R22, R28 |
| `INV-15` | command | No response, plan, delivered event or error detail holds a field of a field class the actor lacks (also ADR-0017.R10). | R25, R41 |
| `INV-81` | day | No audit row of a command registered `human_only` has actor kind agent, or integration while the interim holds (flagged: may integrations execute `human_only` commands). | R11 |
| `INV-89` | day | Every idempotency record of an executed command, within its retention, has an audit record with the same key, actor and command type, or the same `batch_id` for a batch; `company_id` is compared null-safely. | R33, R36 |

## Edge cases

| Edge case | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-04` | Any business event with retry true: sent twice with the same idempotency key. | `must_succeed` | R33, R35 |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `commands.idempotency_retention_days` | integer, bounds `1..` | installation (storage `deployment`) | 90 | R36 |

The maximum number of batch items (R38: an installation setting, default 1,000) has no key in `settings.csv`. `ui.post_review` (R30) has its row in chunk 5.

## Conflicts

CONFLICT ADR-0008.R5: the sentence on asking the policy engine before a posting handler is replaced by the policy points of ADR-0029.R6, which governs; R15 states only what still holds. Its clause on `proposal_required` for agents follows ADR-0029.R4.N2: an agent run's direct call gets `tool_not_allowed` first, and `proposal_required` meets actors carrying an origin agent run (R15).
CONFLICT ADR-0008.R25: the budget level "per company and agent type per day" no longer binds; ADR-0063.R29.N15 (with the ADR-0078 note on ADR-0050.R22) leaves the per-run ceilings of the agent type declaration and the company and installation daily caps (R42).
CONFLICT ADR-0008.R2: the clause that agents may simulate a `human_only` command is struck by ADR-0008.R2.N1; an agent run gets `tool_not_allowed` in both modes (R11).
CONFLICT ADR-0008.R7: the closed field list of the envelope gains `as_of_date` (ADR-0008.R7.N1) and `is_review_skipped` (ADR-0008.R13.N2); R19 lists the current fields.
CONFLICT ADR-0008.R15: the envelope exclusion list "without `mode` and `expected_plan_hash`" also leaves out `is_review_skipped` (ADR-0008.R13.N2) and `include_canonical_plan` (ADR-0008.R7, ADR-0040.R9), which are outside the hash (R19, R32).
CONFLICT ADR-0008.R14: the client no longer changes only `mode` between the calls; ADR-0008.R7.N1 governs, so execution also adds `expected_plan_hash` and `as_of_date` (R31).
CONFLICT ADR-0008.R13.N1: its range of `as_of_date`, within one day of the business date, is narrowed by the later ADR-0008.R13.N3 to the business date or the day before (R29).
CONFLICT ADR-0008.R19: the setting named `retention_days` has the registry key `commands.idempotency_retention_days` under ADR-0008.R19.N1 (R36).

## Trace

| Source | Where |
| --- | --- |
| ADR-0006.R3 | R2 |
| ADR-0006.R5 | R3 |
| ADR-0008.D0 | R1 |
| ADR-0008.R1 | R4, R5 |
| ADR-0008.R1.N1 | R6 |
| ADR-0008.R1.N2 | R7 |
| ADR-0008.R1.N3 | R8 |
| ADR-0008.R1.N4 | R9 |
| ADR-0008.R1.N5 | R10 |
| ADR-0008.R2 | R11 |
| ADR-0008.R2.N1 | R11 |
| ADR-0008.R3 | R12 |
| ADR-0008.R3.N1 | R13 |
| ADR-0008.R4 | R14 |
| ADR-0008.R5 | R15 |
| ADR-0008.R5.N1 | R16 |
| ADR-0008.R5.N2 | R17 |
| ADR-0008.R6 | R18 |
| ADR-0008.R7 | R19 |
| ADR-0008.R7.N1 | R19, R20, R31 |
| ADR-0008.R7.N2 | R20 |
| ADR-0008.R8 | R21 |
| ADR-0008.R9 | R22 |
| ADR-0008.R10 | R23 |
| ADR-0008.R11 | R24 |
| ADR-0008.R12 | R25, R26, R27 |
| ADR-0008.R12.N1 | R27 |
| ADR-0008.R13 | R28 |
| ADR-0008.R13.N1 | R28, R29 |
| ADR-0008.R13.N2 | R19, R30 |
| ADR-0008.R13.N3 | R29 |
| ADR-0008.R14 | R31 |
| ADR-0008.R15 | R32 |
| ADR-0008.R16 | R33 |
| ADR-0008.R16.N1 | R33 |
| ADR-0008.R17 | R34 |
| ADR-0008.R18 | R35 |
| ADR-0008.R19 | R36 |
| ADR-0008.R19.N1 | R36 |
| ADR-0008.R20 | R37 |
| ADR-0008.R21 | R38 |
| ADR-0008.R22 | R39 |
| ADR-0008.R23 | R40 |
| ADR-0008.R24 | R41 |
| ADR-0008.R25 | R42 |
| ADR-0015.R11.N1 | ref: ADR-0015.R11.N1 |
| ADR-0016.R11.N1 | ref: ADR-0016.R11.N1 |
| ADR-0017.R18.N1 | ref: ADR-0017.R18.N1 |
| ADR-0017.R19 | ref: ADR-0017.R19 |
| ADR-0017.R19.N1 | ref: ADR-0017.R19.N1 |
| ADR-0017.R19.N2 | ref: ADR-0017.R19.N2 |
| ADR-0022.R2.N14 | ref: ADR-0022.R2.N14 |
