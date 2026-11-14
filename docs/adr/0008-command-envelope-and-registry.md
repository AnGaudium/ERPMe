# ADR-0008: Command envelope and registry

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. [ADR-0013](0013-outbox-and-events.md) rule 9: internal calls from consumers and system jobs run in execute mode inside the caller's transaction without `expected_plan_hash` (an exception to rule 13). [ADR-0017](0017-permission-envelope.md) rule 4: the registry also declares capabilities, permissions that are not command names. Design item: DS-04. Related decisions: D2, D4, D13, D14. Principles 1, 2, 3, 4, 9, 10, 12, 13. Build principles B3, B7. ADR-0004, ADR-0005, ADR-0006, ADR-0007. Rule 4 annotated by [ADR-0022](0022-repository-and-engineering-conventions.md) (posting interfaces).

## Decision

Every write goes through one command registry. A command is a pydantic payload wrapped in one envelope (`command_type`, `schema_version`, `company_id`, `idempotency_key`, `mode`, `expected_plan_hash`, `payload`). The actor, and for agents, integrations and system jobs the accountable human (`on_behalf_of`), come from the credential, never from the envelope. The same envelope is sent twice: first with `mode: simulate`, which runs the real handler in a transaction that is rolled back and returns the plan and its `plan_hash`; then with `mode: execute` and the `expected_plan_hash`, which runs it again and commits only if the hash is equal. An execution claims its idempotency key first and stores its response in the same transaction; a retry returns the stored response. Command batches use the same envelope around an ordered list of items. Queries use the envelope without the write fields. Handlers are deterministic and touch only the database. Errors have one shape on every transport. REST and MCP are generated from the registry. The field-level specification is [DS-04-command-envelope.md](../design/DS-04-command-envelope.md).

### Rules

**Registry**

1. Each command type is registered once with: `command_type` (ADR-0004 rule 17), `schema_version` (semver), scope (`company` or `installation`), payload model, result model, handler, the error codes it can return, the permission it needs (DS-15) and `human_only`. Queries (`Get<Noun>`, `List<Noun>`, ADR-0004 rule 21) are registered the same way, with a result model and no handler effects, idempotency key or plan. Each command type also declares `effect_class` (`posting`, `master_data_change`, `outbound_send`, `other`), required with no default; CI fails when a `Post<Type>` or `Reverse<Type>` command is not `posting` ([ADR-0027](0027-cross-cutting-ownership.md) rule 17). Commands may also be registered `is_proposal_bound`: agents reach them only through change proposals ([ADR-0029](0029-proposals-and-agent-safety.md) rules 2, 4). A command whose policy inputs are read under locks is registered `is_policy_in_handler` ([ADR-0030](0030-commercial-seams-and-imports.md) rule 7).
2. `human_only` marks actions the spec says agents may not take (closing periods, reversing posted documents; [14-agent-workflows.md](../spec/14-agent-workflows.md)). The dispatcher refuses to execute such a command when the actor is an agent; agents may simulate it to prepare a human's decision. Whether integrations may execute `human_only` commands is an open question for the author; until answered they are refused too. System jobs act as the spec defines (e.g. closing entries by actor `system` on behalf of the human who triggered the close, [07](../spec/07-shared-foundation.md#document-lifecycle-numbering-and-posting-periods)).
3. Payload and result models are pydantic models with unknown fields rejected (`extra="forbid"`), using the `erpme.numeric` and `erpme.clock` types (ADR-0006 rule 13, ADR-0007 rule 3) and references by `id` only (ADR-0006 rule 5).
4. A handler is a function `handle(context, payload) -> result`. It reads and writes only through the database connection, ID generator, clock and lock helpers in `context`. It makes no network call, reads no file, calls no LLM and starts no job directly; anything outside the database happens after commit through the outbox (DS-13). So a handler gives the same result for the same database state, payload and business date (D2, Principle 13). Queries it runs whose order affects the plan use `ORDER BY` on stable keys. Posting interfaces of other modules (e.g. `ledger.contract.write_journal_entry`) take this `context` and run inside the handler's transaction and plan, with no permission or idempotency step of their own ([ADR-0022](0022-repository-and-engineering-conventions.md) rule 4).
5. For every command and every query, before anything else runs (including an idempotent replay), the dispatcher checks permissions, record visibility and `human_only` (DS-15). Before a handler that posts runs, it also asks the policy engine (DS-28; until then a stub that allows). Handlers never do these checks themselves. A record the actor may not see is reported as `record_not_found`. The sentence "Before a handler that posts runs, it also asks the policy engine" is replaced by the policy points of [ADR-0029](0029-proposals-and-agent-safety.md) rule 6; allowed-target commands from agents are rejected with `proposal_required` (rule 4).
6. REST endpoints, MCP tools, JSON Schema and TypeScript types are generated from the registry (Principle 10). Nothing is hand-written per command. MCP tool names are the `snake_case` form of the command type or query (ADR-0004 rule 19). Which tools each agent type sees is a fixed list (DS-32, [03-agent-safety.md](../spec/03-agent-safety.md) rule 2).

**Envelope and actor**

7. The command envelope fields are `command_type`, `schema_version` (the major version the client was built for, an integer), `company_id` (required for company-scoped commands, absent for installation-scoped ones), `idempotency_key`, `mode` (`simulate` or `execute`), `expected_plan_hash` (required when `mode` is `execute`) and `payload`. No other field is accepted.
8. The dispatcher builds the actor context from the authenticated credential: actor kind (human, agent, integration, system) and `id`; for agents, integrations and system jobs, `on_behalf_of` (the accountable human bound to the credential, agent run or job when it was started); for agents, also `agent_run_id` ([03-agent-safety.md](../spec/03-agent-safety.md) rules 3, 7). None of these can be sent by a client, so text an agent has read cannot change whom it acts for. Whether that actor may act for that human is checked by DS-15.

**Simulation and `plan_hash`**

9. `mode: simulate` runs the same dispatcher and handler as `execute` in a transaction that is always rolled back (Principle 2; [10-roadmap.md](../spec/10-roadmap.md#lean-scope-for-phases-0-and-1), "built thin"). There is no separate simulation code in handlers. In both modes, `SET CONSTRAINTS ALL IMMEDIATE` runs before the plan is hashed, so deferred constraints fail in simulation as they would at commit. Handler and trigger paths use no sequence, no session-level advisory lock and no non-`LOCAL` `SET`, because these survive a rollback.
10. Simulation takes no lock on serialized rows (stock balance per item and warehouse, numbering counters) and consumes no document number. These tables are read and written only through the lock helpers in `context`; no other SQL, trigger or constraint reads them (CI check, DS-18). In simulate mode the helpers take no row lock and keep new values in memory for the rest of the run, and numbering returns a placeholder number unique within the run. Other writes still take ordinary row and unique-index locks until the rollback, so a simulation can briefly delay a real execution that touches the same document; it never holds stock or numbering locks. `open_item` is such a table ([ADR-0026](0026-open-item-core.md) rule 3).
11. Both modes run with `transaction_timeout` and `lock_timeout` (values in DS-18); exceeding them returns a retryable error.
12. The plan of a command is its journal lines and stock movements, in the order the handler produced them, plus its result; a command with no journal or stock effect has a plan of its result only. `plan_hash` is the lowercase hexadecimal SHA-256 of the canonical JSON of the plan: keys sorted, no whitespace, UTF-8, numbers and dates in their canonical string forms (ADR-0006 rule 13, ADR-0007 rule 3). Before hashing: every ID created through `context.new_id(table)` during the run (the only way a handler creates IDs) is replaced by a token `new:<table>:<n>` in creation order; values of the types `DocumentNumber` and `SystemInstant` (system-set `_at` fields) are removed. Rows that appear in a plan never get their `id` from a trigger or column default (ADR-0006 rule 2 allows those only for rows outside plans); a test checks this. IDs of rows that existed before the run, client-supplied IDs and client-supplied instants stay (ADR-0007 rule 11). The hash is computed over the full plan; the plan returned to the client is filtered by the actor's field permissions (DS-15). Warehouse task proposals (target and source bins) are listed like events and never hashed ([ADR-0023](0023-warehouse-management.md) rule 11). Planning run results (hashes, planned orders, messages, exceptions) are listed the same way ([ADR-0024](0024-planning.md) rule 17).
13. `mode: execute` requires `expected_plan_hash`, except for internal callers (consumers and system jobs calling the dispatcher in process, never over REST or MCP), which execute inside their own transaction under the same checks ([ADR-0013](0013-outbox-and-events.md) rule 9). The command runs again; if its `plan_hash` differs, the transaction is rolled back and `plan_hash_mismatch` returns the new plan and hash, so the client can review and resend. A human using the UI and an agent follow the same two calls.

**Idempotency**

14. `idempotency_key` is required in both modes; a client builds one envelope and changes only `mode`. It is a string of 1–128 characters from `A-Z a-z 0-9 _ - . :`; a UUID version 7 is recommended. Its scope is (actor, command type), and `command_batch` for batches (Principle 9).
15. The request hash is the SHA-256 of the canonical JSON of the validated request (envelope without `mode` and `expected_plan_hash`, plus the validated payload), so `"1.50"` and `"1.5"` give the same hash.
16. An execution's first statement, after the checks of rule 5, is `INSERT … ON CONFLICT DO NOTHING` of (actor, scope, key, request hash) into `idempotency_record`, which has a unique constraint on (actor, scope, key). If the row is inserted, the command runs and the response is written into that row before commit; if the command fails, the whole transaction, row included, rolls back, so a retry runs again. If a concurrent request holds the key, the insert waits (bounded by `lock_timeout`). If a committed row exists: same request hash → the stored response is returned; different hash → `idempotency_key_reused`.
17. A simulation never writes `idempotency_record`. If the key already has a committed row with the same request hash, a simulation returns that stored response instead of running.
18. A replayed response is the stored response with `replayed: true`; everything else, including `mode: execute`, is as stored. The DS-16 invariant compares responses ignoring `replayed`.
19. `idempotency_record` is not partitioned. A daily job deletes rows older than the retention (`retention_days` in installation settings, default 90); rows are kept at least that long. These rows are not the audit log, which is never deleted (DS-36).

**Command batches**

20. A command batch has the envelope with `command_type` and `schema_version` replaced by `items`, an ordered list of `{command_type, schema_version, payload}`, all for the same company and actor. Its REST endpoint is `POST /api/command-batches` and its MCP tool is `command_batch`. All items are validated first and every validation error is reported (field paths `items[<n>].payload.<field>`); then the items run in order in one transaction, all or nothing, stopping at the first handler error, which names its item. Its plan is the list of item plans, hashed as one; one `expected_plan_hash` and one idempotency key cover the batch. An item refers to a record created by an earlier item through the client-supplied `id` (ADR-0006 rule 3). A batch is not a command type, so no verb is needed.
21. A batch response returns, per item, its index, command type, result, number of journal lines, number of stock movements and the sum of its debit amounts in company currency (debit as DS-06 defines it), plus the batch `plan_hash`; the full plan is returned only when the request sets `include_plan: true`. The idempotency record stores the same summary, and a batch `plan_hash_mismatch` carries the same summary in `details` unless `include_plan` is true. The maximum number of items is an installation setting, default 1,000.

**Queries**

22. A query is sent as `POST /api/queries/<snake_case query>` (or its MCP tool) with `schema_version`, `company_id` and `payload` (the filters); it has no `idempotency_key`, `mode` or `expected_plan_hash`. Filters travel in the body, never in the URL, so personal data does not reach access logs. `List<Noun>` returns at most `limit` rows (default 100, maximum 1,000), ordered by `id` unless the query defines another stable order, with a cursor for the next page. Queries read the same database as commands, so a committed execution is visible to the next query.

**Schema versioning**

23. Each command type's and query's schema has a semver version. A change that only adds optional fields or new error codes is a minor version. Any other change is a new major version. `schema_version` names the major version; the registry serves the current major and the previous one until the next LTS release (DS-37), then removes the old one. A request for a major version that is not served is rejected with `schema_version_unsupported`, naming the versions served.

**Errors**

24. Every error, on every transport, is a response `{"errors": [ … ]}` where each item has `code` (a stable `snake_case` identifier from the registry's error catalog), `message` (English; the UI translates by `code`), `rule` (the reference that failed, e.g. `ADR-0007 rule 22`), `field` (path in the request, or null), `fix` (what the client should do), `retryable` (true or false, fixed per code in the catalog) and `details` (an object, may be empty, filtered by field permissions). Validation reports every field error it finds at once.
25. Each error code belongs to one category with a fixed HTTP status: `malformed` 400, `unauthenticated` 401, `permission` 403, `not_found` 404, `conflict` 409, `too_large` 413, `validation` 422, `precondition` 422 (a business rule failed), `rate_limited` 429, `internal` 500, `unavailable` 503. Over MCP the same body is returned as a tool error. An `internal` error never exposes stack traces or SQL. Rate limits themselves are set by DS-18 and DS-32.

## Context

DS-04 is the contract every module, client and agent uses ([04-architecture.md](../spec/04-architecture.md); Principles 1, 2, 9, 10). Constraints:

- Commands are pydantic schemas, the single source for JSON Schema, REST, MCP and TypeScript types (ADR-0001, ADR-0002, [10-roadmap.md](../spec/10-roadmap.md)).
- Simulation runs the real command and rolls back; `plan_hash` hashes the resulting journal lines and stock movements; execute is rejected if the hash differs; simulation must not hold stock locks (Principle 2, 10-roadmap "built thin", backlog DS-04).
- Idempotency key per (actor, command type) with retention; the same key with a different payload is rejected (Principle 9). Imports are simulated command batches (D16, step 2). Imports above 1,000 rows are staged and posted as a sequence of batches ([ADR-0030](0030-commercial-seams-and-imports.md) rule 9).
- `actor` and `on_behalf_of` on every command; actor kinds human, agent, integration, system; untrusted content must not widen what an agent run can do ([03-agent-safety.md](../spec/03-agent-safety.md) rules 1, 3, 5).
- The command layer asks the policy engine before posting ([04-architecture.md](../spec/04-architecture.md)). Command schemas are a versioned public API ([07-shared-foundation.md](../spec/07-shared-foundation.md#extensibility-and-upgrades)).
- ADR-0005: among correct options, the one easiest for AI agents wins.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One envelope, sent twice with `mode` (chosen) | One request shape for both calls; agents change one field | Every write runs twice |
| `expected_plan_hash` optional | Faster for simple writes | Two behaviors; an agent could skip the review step Principle 2 requires |
| Separate simulation code per handler | Simulation could be cheaper | Two code paths that drift; the spec says run and roll back |
| Simulation takes row locks like execution | No special helpers | A simulation would block real stock postings, against Principle 2 |
| Actor or `on_behalf_of` sent in the envelope | Simpler credentials | A prompt-injected agent could pick another human to act for |
| Write the idempotency record at the end | One statement fewer | A concurrent duplicate runs the handler and fails instead of replaying |
| Partition `idempotency_record` by month | Drop old rows cheaply | PostgreSQL cannot enforce a unique key without the partition key in it |
| Store failed executions under the key too | Retries of failures are instant | A failure caused by state (a locked period) could never succeed on retry |
| Batch as a command type (`RunCommandBatch`) | Fits the verb list | A command containing commands; separate idempotency and plan rules anyway |
| Queries as `GET` with URL filters | Cacheable | No room for the envelope fields; personal data in access logs |
| One generic MCP tool `run_command` | Few tools | Agents get no schema per command; fixed tool lists per agent type become impossible |

## Constraints that come with the decision

- DS-05, DS-09: numbering and stock posting use the lock helpers in `context`; their tables are not read by other SQL (rule 10).
- DS-06: journal lines and stock movements expose their canonical form, with `DocumentNumber` and `SystemInstant` types (rule 12).
- DS-13: anything outside the database runs after commit from the outbox (rule 4).
- DS-15: permission and visibility checks for every command and query, field filtering of plans and error details, `human_only`, `on_behalf_of` binding in credentials and agent runs (rules 2, 5, 8, 12).
- DS-16: invariants for idempotent retry and simulated equals executed (rules 13, 18).
- DS-18: `transaction_timeout` and `lock_timeout` values; rate limits; CI checks for rules 4, 9, 10; generation of REST, MCP, JSON Schema and TypeScript from the registry.
- DS-28: the policy engine call before posting handlers (rule 5).
- DS-30: forms are generated from the same JSON Schemas.
- DS-32: agent runs bind `on_behalf_of` and `agent_run_id` (rule 8).
- DS-36: the audit log is separate from idempotency records (rule 19).

## Revisit when

- Running every write twice costs more than 30% of measured throughput on the medium replay: allow execute-only for command types with no journal or stock effect.
- A client needs a retry window longer than 90 days.
- More than 10% of executions fail with `plan_hash_mismatch` in normal use: look at what changes between the two calls.

## Documents updated

- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): new, field-level specification and examples.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for envelope, mode, plan, expected plan hash, command registry, error code, idempotency record, `human_only`, command scope; the verb note on command batches.
- [docs/design/backlog.md](../design/backlog.md): DS-04 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): the command-schema question answered for REST and MCP (forms stay with DS-30); new question on integrations and `human_only`.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
