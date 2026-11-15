# ERPMe architecture: coder core

Read this before every coding task. It summarizes rules. It creates none. If this file and an ADR disagree, the ADR wins. Report the difference in [docs/open-questions.md](../open-questions.md). The full overview is [architecture-overview.md](architecture-overview.md).

## A1. ERPMe in five lines

1. ERPMe is an ERP with a deterministic core. AI only drafts and proposes (D2).
2. Every write is a command. A client sends it twice: simulate, then execute with the same `plan_hash` ([ADR-0008](../adr/0008-command-envelope-and-registry.md)).
3. One Python distribution `erpme`, one PostgreSQL database, one schema `erpme` ([ADR-0022](../adr/0022-repository-and-engineering-conventions.md) rules 1, 7).
4. Modules sit in six layers. A module imports only from lower layers (ADR-0022 rule 2).
5. Events go to a transactional outbox. Workers deliver them after commit ([ADR-0013](../adr/0013-outbox-and-events.md)).

### Layer table (ADR-0022 rule 2)

| Layer | Modules |
| --- | --- |
| 6 Composition | `app` |
| 5 Interfaces | `api`, `query`, `agents`, `sdk`, `imports`, `automation` |
| 4 Commercial | `sales`, `purchasing`, `cash`, `reporting`, `crm`, `planning` |
| 3 Core business | `ledger`, `inventory`, `master_data`, `tax`, `production`, `assets` (Phase 3) |
| 2 Platform | `registry`, `documents`, `periods`, `permissions`, `outbox`, `audit`, `localization`, `db`, `agent_runs`, `work`, `attachments`, `policy`, `configuration` |
| 1 Foundation | `numeric`, `clock`, `ids`, `i18n`, `errors` |

`configuration` (layer 2) and `automation` (layer 5) come from a note on ADR-0022 rule 2 ([ADR-0058](../adr/0058-configurable-workflows.md)).

Import rules (ADR-0022 rules 2, 5, 6; [ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 1):
- In layers 3 and 4, import another module of the same layer only through its `contract.py`.
- `tax` may import the `ledger` contract; `ledger` never imports `tax`.
- Layer 2: `registry` imports `work` and `policy`. `documents`, `outbox`, `permissions`, `attachments`, `agent_runs` and `policy` import `work`. `documents` and `permissions` may import the `agent_runs` contract; `documents` may import the `attachments` contract. `configuration` imports the `registry` contract and `work`.
- `query` imports `db`, `registry`, `agent_runs` and the `work` contract.
- `erpme.registry.dispatch` loads `app` through an entry point, never a static import.
- Need to call sideways or up? Use a hook: a module declares it, a module of the same or a higher layer registers it, `app` wires it.
- `erpme` imports no tool package and no `l10n_*`. `l10n_*` imports only `erpme.sdk`. Only `erpme.agents.gateway.adapters` imports an LLM provider library.

The import-linter configuration will be the generated, complete list.

## A2. Where code goes

Rules: ADR-0022 rules 3, 4, 7, 8, 17, 23 unless named.

| Thing | Place |
| --- | --- |
| Command, query and event schemas; posting interfaces; interfaces packages implement | `backend/src/erpme/<module>/contract.py` |
| Command handler | `<module>/handlers/`, function in `snake_case` (`post_goods_receipt`, [ADR-0004](../adr/0004-naming-conventions.md) rule 19) |
| Consumer | A registered handler of the owning module, registered by `app` ([ADR-0013](../adr/0013-outbox-and-events.md) rule 6; folder: to verify) |
| Table | `<module>/tables.py`, private, exactly one owner module |
| Private logic | `<module>/services/` |
| Local rules | `<module>/AGENTS.md`, at most 40 lines |
| Tests | `backend/tests/<module>/` |
| Migration; RLS (`rls_v1`), triggers, functions, grants by hand | `backend/migrations/`, one linear Alembic history |
| Views for agents and reports | Schema `query`, owner `erpme_query_owner` |
| Generated files (never edit) | `backend/generated/`, `frontend/src/generated/` |
| Setting | Settings registry ([ADR-0063](../adr/0063-configurable-policy-settings.md) rule 1); seed `docs/catalogs/settings.csv` |
| Work item kind | Registered like a command ([ADR-0042](../adr/0042-work-queue.md) rule 1); seed `docs/catalogs/work-item-kinds.csv` |
| Country rule | `l10n/l10n_<country>/`, never the core ([ADR-0016](../adr/0016-localization-package-structure.md); [ADR-0053](../adr/0053-core-neutrality.md)) |

Foundation modules and `db` publish through `__init__` (ADR-0022 rule 3). Recipes: skills `new-command`, `new-migration`, `new-invariant`, `new-edge-case`, `new-adr`, `posting-change-review` (ADR-0022 rule 23).

## A3. The life of a command

### Envelope and actor

- Envelope fields: `command_type`, `schema_version`, `company_id`, `idempotency_key`, `mode`, `expected_plan_hash`, `payload` (and `include_canonical_plan`). No others (ADR-0008 rule 7).
- The actor, `on_behalf_of` and `agent_run_id` come from the credential, never from the client (ADR-0008 rule 8).
- `idempotency_key` is required in both modes; scope (actor, command type) (ADR-0008 rule 14).
- `simulate` runs the real handler and rolls back. `execute` runs it again and commits only if the plan hash equals `expected_plan_hash`, else `plan_hash_mismatch` (ADR-0008 rules 9, 13).
- Consumers and system jobs call the dispatcher in process, without `expected_plan_hash` (ADR-0013 rule 9).

### Dispatcher steps, in order

ADR-0008 rule 5; [DS-04](DS-04-command-envelope.md#dispatcher-check-order). Simulate is a mode of the whole run, not a step. A step runs only if the earlier ones passed.

1. **Credential and actor context.** Actor kind, `on_behalf_of`, agent run and work item, origin agent run. Causation chain and depth.
2. **Run gates.** `tool_not_allowed`, then `tainted_run_not_allowed`, then the tainted reference scope. Automation depth and allowed-command checks.
3. **`human_only` and agent-chain refusals.** `human_only`, `proposal_required`, `origin_run_submit_not_allowed`.
4. **Permission.** `permission_denied`; the `direct_master_data_change` deny.
5. **Record visibility.** Company, record scope, owner scope. A hidden record is `record_not_found`.
6. **Idempotency.** Execute inserts the `idempotency_record` row first. A committed row with the same request hash returns the stored response (`replayed: true`) and skips steps 7–10; a different hash is `idempotency_key_reused`. Simulate only looks up.
7. **Work item claim** of an agent run's bound item (`FOR KEY SHARE`).
8. **State-dependent authorization.** `segregation_of_duties`, `approver_not_eligible`.
9. **Policy point and floors.** `policy_denied`, `approval_required`. For `is_policy_in_handler` commands this runs inside the handler.
10. **Handler, audit record, events.** The handler runs; the dispatcher writes the audit record, events, deliveries and stored response.

Steps 6 to 10 are for commands only. In a batch, steps 1 to 5, 7 and 8 run per item; step 6 runs once (DS-04).

### Handler contract

- A handler is `handle(context, payload) -> result` (ADR-0008 rule 4).
- `context` holds: the database connection, `new_id(table)`, the clock (`now()`, `today(company)`), the lock helpers, and `emit(event_type, subject, payload)` (DS-04, Handler context).
- A handler reads and writes only through `context`. No network, file, LLM or job. Same state, payload and business date give the same result. Order-sensitive queries use `ORDER BY` on stable keys (ADR-0008 rule 4).
- IDs come only from `context.new_id(table)`. The plan hash replaces them with tokens (ADR-0008 rule 12).
- Locks follow one global order ([ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 10): documents; period area state (share); planning state or `production_structure` or `configuration_state`; warehouse tasks; handling units; `stock_value`; `stock_quantity`; bins; partners; `money_account_balance`; open items; numbering counters; `event_subject`. The lock helper raises in tests on a wrong order (ADR-0022 rule 10).
- A document command carries `version` and locks the `document` row first. A stale version is `version_conflict` ([ADR-0009](../adr/0009-document-lifecycle.md) rule 10).
- Simulation takes no lock on serialized rows and consumes no number (ADR-0008 rule 10).
- Timeouts: `lock_timeout` 5 s; `transaction_timeout` 30 s for commands, 4 min for consumers, 15 min for registered long jobs (ADR-0022 rule 9).

### Posting interfaces

ADR-0022 rule 4:
- A posting interface is a plain function in a module's `contract.py` that takes the caller's `context`: `ledger.contract.write_journal_entry`, `inventory.contract.move_stock`, `documents.contract.assign_number`, `periods.contract.check_posting`.
- It runs in the caller's transaction and plan, with no permission, idempotency or policy step of its own. It is never on REST or MCP.
- Synchronous cross-module writes use posting interfaces. Asynchronous reactions use events and consumers.

### Skeleton

Names marked `# shape` are not fixed by an ADR. The rest is.

```python
# backend/src/erpme/inventory/handlers/post_goods_receipt.py
from erpme.documents import contract as documents   # layer 2: downward
from erpme.ledger import contract as ledger         # layer 3: another module's contract only
from erpme.periods import contract as periods       # layer 2: downward
from erpme.inventory.contract import (
    GoodsReceiptPosted, PostGoodsReceipt, PostGoodsReceiptResult, move_stock)
from erpme.inventory.services import receipts       # private to inventory

def post_goods_receipt(context, payload: PostGoodsReceipt) -> PostGoodsReceiptResult:
    doc = documents.lock_document(context, payload.id, payload.version)  # shape; ADR-0009 rule 10
    periods.check_posting(context, payload.posting_date)                 # ADR-0022 rule 4
    lines = receipts.load_lines(context, doc)            # shape; ORDER BY line_number
    move_stock(context, receipts.movements(lines))       # stock locks via the helper
    ledger.write_journal_entry(context, receipts.entry(lines, payload.posting_date))
    number = documents.assign_number(context, doc)       # numbering lock after stock
    documents.mark_posted(context, doc)                  # shape; state 'posted', posted_at
    context.emit(
        "GoodsReceiptPosted", ("document", doc.id),      # subject: table, id
        GoodsReceiptPosted(id=doc.id, number=number,
                           posting_date=payload.posting_date, version=doc.version))
    return PostGoodsReceiptResult(id=doc.id, number=number)

# Registration (shape; fields of ADR-0008 rule 1): command_type, schema_version, scope, payload and
# result models, handler, error codes, permission, human_only, effect_class="posting",
# subject_table, allowed_states, emitted events. `app` imports handlers/ to register them.
```

The event payload carries facts and IDs, never a snapshot (ADR-0013 rule 4). The dispatcher, not the handler, writes the audit record and the deliveries.

### Outbox and `event_delivery`

- `context.emit` writes `outbox_event`; the dispatcher adds one `event_delivery` per subscribed consumer, in the same transaction (ADR-0013 rules 1, 6).
- `subject_sequence` (from `event_subject`) is the only event order (ADR-0013 rule 3).
- After commit, `NOTIFY erpme_outbox` wakes the workers; they also poll every 5 s (ADR-0022 rule 12).
- A worker claims a `pending` delivery with `FOR UPDATE SKIP LOCKED` when no earlier delivery of that consumer and subject is open; lease 5 min (ADR-0013 rule 7).
- A transactional consumer runs in a second transaction that also marks the delivery `done`. It writes only through commands, as `system`, key `<consumer>:<event id>:<n>` (ADR-0013 rules 7, 9).
- After `max_attempts` (default 10) a delivery is `held` and blocks its subject for that consumer until a human runs `RetryEventDelivery` or `SkipEventDelivery` (ADR-0013 rule 8).
- Outside calls: a command records the intent; an `external` consumer on `integrations` calls with no transaction open, then records the outcome by a command. After an unknown outcome it asks the provider first (ADR-0013 rule 10).
- Agents start only from work items: `WorkItemRaised` → consumer `agent_wake_up` → `StartAgentRun` → queue `agents` → consumer `agent_runner` (ADR-0013 rules 12, 13; [ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rules 15–16).
- A tainted event's consumer may run only `is_draft_only` commands (ADR-0013 rule 11).

## A4. Data rules every table follows

**IDs and keys** ([ADR-0006](../adr/0006-id-and-numeric-model.md) rules 1–7)
- Primary key: one column `id uuid`, UUID v7; never composite. Core catalog rows: UUID v5 from `"<table>:<code>"`.
- `Create` accepts an optional client `id` (UUID v7). Commands refer to records by `id` only, never by `code` or number. Foreign keys end in `_id` (ADR-0004 rule 12).

**Company and RLS** ([ADR-0017](../adr/0017-permission-envelope.md) rules 18–19)
- Company tables have `company_id` and `FORCE ROW LEVEL SECURITY`. Each transaction sets `erpme.company_id`; without it no row is visible. Null-company rows need the value `installation`.
- References inside a company are composite on (`company_id`, `id`) ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 1; [ADR-0052](../adr/0052-minimal-crm.md) rule 3).
- RLS is the second line of defense. The dispatcher is the first.

**Time** ([ADR-0007](../adr/0007-time-model.md))
- Business dates are `date`, named `_date`. System instants are `timestamptz` in UTC, named `_at` (rules 1–2).
- `recorded_at` is on every row and row version, set by the system. One transaction has one instant (`clock.now()`). Never order by an `_at` column (rules 9–10).
- The business date comes from `clock.today(company)` or input. Durations are integers with a unit in the name; no `interval`. `posting_date` is explicit at posting (rules 5, 8, 15–16).

**Append-only and immutable** (ADR-0009 rule 14)
- Final states `posted`, `reversed`, `canceled`, `closed` are immutable. Triggers reject changes to the header, lines and `document` row.
- `document_version`, `policy_decision` and `approval` rows are never updated or deleted.
- Journal and material document rows are append-only (DS-06; [ADR-0020](../adr/0020-inventory-and-costing-model.md) rule 3).
- Data that arrives after posting goes into its own table that refers to the document.

**Corrections and reversals** (ADR-0009 rules 18–23)
- A posted document is corrected by a correction document (`correction_of_id`): a return, credit or debit note, adjustment or replacement invoice.
- Only internal document types are reversed, by the `human_only` `Reverse<Type>`.

**Numbers** (ADR-0006 rules 8–21)
- Domains `types.amount` (24,4), `types.quantity` (24,6), `types.unit_price` (28,10), `types.exchange_rate` (30,15), `types.percent` (9,6); Python types `Amount`, `Quantity`, `UnitPrice`, `ExchangeRate`, `Percent` in `erpme.numeric`.
- JSON carries them as canonical strings; a JSON number is rejected. Amounts are stored at the currency's minor unit; extra input decimals are rejected, never rounded.
- Rounding goes only through `round_amount`, `round_quantity`, `round_unit_price`, `round_exchange_rate`, `round_percent`. Conversion only through `convert_amount`.
- Line amount: `round_amount(quantity × unit_price, currency)`; totals sum rounded lines. Conversion differences go to one rounding line on `rounding_gain` or `rounding_loss`. `_percent` columns hold 8 for 8%.
- A document line stores its unit conversion as a snapshot (`uom_numerator`, `uom_denominator`, `uom_factor_source`) and never reads it again (ADR-0006 rule 11 note; [ADR-0056](../adr/0056-multiple-units-of-measure.md)).

**Names** (ADR-0004 rules 3, 6, 13, 14): one identifier from column to TypeScript, no alias; `state`, never `status`; enums as `text` with `CHECK`; at most 63 bytes.

**Personal data and secrets**
- Event payloads never carry a field labeled personal or sensitive personal (ADR-0013 rule 4).
- Field classes (`cost`, `margin`) hide fields from actors who lack them. Data labels govern LLM routing. They are separate (ADR-0017 rule 10).
- `is_secret` fields never reach a view, an agent's query result or a prompt ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 11).
- Change-tracked tables (master data, settings, role assignments, period state, production structures) are written only by `context`'s write helpers, which record `audit_change` ([ADR-0038](../adr/0038-audit-and-observability.md) rule 3).
- A document records its owner: `owner_employee_id` and `created_by_user_id` ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 14).

The DDL drafts do not all follow these rules yet: `recorded_at` and primary-key deviations are listed in [architecture-overview.md, Findings](architecture-overview.md#findings-for-the-review). Do not copy them. Follow the ADR.

## A5. Never do this

"check: X" is the `erpme-dev check` custom check X of ADR-0022 rule 13.

| Never | Rule | Check |
| --- | --- | --- |
| Call the network, a file, an LLM or the job queue in a handler | ADR-0008 rule 4; ADR-0013 rule 13 | import-linter `forbidden` contract (ADR-0022 rule 6) |
| Write the database outside `context` | ADR-0008 rule 4; ADR-0038 rule 3 | check: Serialized tables; change-tracked guard (planned check) |
| Read or write a serialized table (stock balances, numbering counters, open items) outside its lock helper | ADR-0008 rule 10; ADR-0026 rule 3 | check: Serialized tables |
| Take locks out of the registered order | ADR-0027 rule 10 | Lock helper raises in tests (ADR-0022 rule 10) |
| Use a float for money, quantities, prices, rates or percentages | ADR-0006 rule 12 | check: Floats |
| Round or convert outside `erpme.numeric` | ADR-0006 rules 10, 15 | check: Rounding and conversion |
| Compute money in the client | ADR-0040 rule 2 | planned check |
| Call `datetime.now`, `date.today`, `time.time`; use `current_date`, `clock_timestamp()` in SQL | ADR-0007 rule 16 | ruff `TID251`, `DTZ`; check: Database time functions |
| Import upward or sideways | ADR-0022 rules 2, 6 | import-linter layers and independence contracts |
| Import a tool package, a lab script or `l10n_*` from `erpme` | ADR-0022 rule 6; lab README | import-linter for tools and `l10n_*`; planned check for lab code |
| Edit a document in a final state | ADR-0009 rules 14, 23 | Database triggers (ADR-0009 rule 14); trigger tests |
| Let an agent submit, post, issue, approve or send | ADR-0050 rule 30; ADR-0017 rule 15 | Registry CI check and INV-214 |
| Check permissions or policy inside a handler | ADR-0008 rule 5 | planned check |
| Give a plan row its `id` from a column default, trigger or sequence | ADR-0008 rule 12; ADR-0006 rule 2 | Test named in ADR-0008 rule 12 |
| Use sequences, session advisory locks or non-`LOCAL` `SET` on handler or trigger paths | ADR-0008 rule 9; ADR-0022 rule 13 note | check: Session locks and settings |
| Refer to a record by `code` or number in a command | ADR-0006 rule 5 | planned check |
| Use camelCase, aliases, `status`, a PostgreSQL `ENUM`, or a name over 63 bytes | ADR-0004 rules 3, 6, 13, 14 | ruff `N`; check: Identifiers; planned check for `status` and `ENUM` |
| Hard-code a country rule or an unverified legal rule in the core | ADR-0053; ADR-0016; AGENTS.md | planned check; review |
| Put personal data or a snapshot in an event payload | ADR-0013 rule 4 | Registry CI check of payload fields against data labels |
| Edit a generated file | ADR-0022 rules 17, 24 | `erpme-dev generate --check` |
| Write separate simulation code | ADR-0008 rule 9; ADR-0004 rule 18 | INV-12 `executed_equals_simulated` |
| Omit `company_id` or the composite company key on a company table | ADR-0017 rule 19; ADR-0045 rule 1 | RLS policy test against `pg_policies` (ADR-0022 rule 8); planned check for composite keys |

## A6. Error model and check results

- Every error on every transport is `{"errors": [ … ]}`, each item with `code`, `message`, `rule`, `field`, `fix`, `retryable`, `details` (ADR-0008 rule 24). `code` comes from the registry's catalog; a command declares the codes it returns (ADR-0008 rule 1).
- Categories and HTTP status: `malformed` 400, `unauthenticated` 401, `permission` 403, `not_found` 404, `conflict` 409, `too_large` 413, `validation` 422, `precondition` 422, `rate_limited` 429, `internal` 500, `unavailable` 503 (ADR-0008 rule 25).
- `retryable` is fixed per code. `concurrent_update` and `timeout` are retryable (DS-04 catalog; ADR-0022 rule 9).
- Validation reports every field error at once (ADR-0008 rule 24). A record the actor may not see is `record_not_found` (ADR-0008 rule 5). An unknown `id` names its table and `List<Noun>` query (ADR-0006 rule 5).
- A wrong state is `invalid_state_transition`, naming the current state and the allowed commands (ADR-0009 rule 5).
- `internal` errors never show stack traces or SQL (ADR-0008 rule 25).
- Check results are findings that do not stop a command. They are returned in `checks` as `{code, message, rule, field, details}`. Their `[code, field]` pairs are part of the plan hash unless the code is listed as unhashed ([ADR-0040](../adr/0040-ui-architecture.md) rule 10; DS-04, Check results).
- New codes go into the registry's catalog with the same columns. Envelope-level codes are defined only in DS-04 (DS-04, Error catalog).
- The raising API lives in `erpme.errors` (layer 1). Its signature is not fixed yet.

## A7. Testing on one page

- **Real database.** Tests run on PostgreSQL as the product roles, through testcontainers (ADR-0022 rules 7, 14).
- **Invariants.** [docs/catalogs/invariants.csv](../catalogs/invariants.csv) lists INV-xx. Each row has one check, `@invariant("INV-nn")` in `erpme_testkit.invariants`. A row at or below `build_step` without a check fails CI ([DS-16](DS-16-invariants-and-harness.md) rules 4–5).
- Checks read with plain SQL as `erpme_check` (SELECT only, under RLS), never through core code (DS-16 rule 2).
- **One command protocol.** Every harness command is simulated, executed with the plan hash (INV-12), compared with its outcome class (INV-19), checked for field classes (INV-15) and events (INV-18). Retries reuse the key (INV-11) (DS-16 rule 15).
- **State machines and recomputation.** Hypothesis state machines from `LedgerMachine` on (DS-16 rule 17). `erpme_reference` recomputes from files with the standard library only; equality is exact (DS-16 rules 3, 29–30).
- **Synthetic data.** The simulator writes business events. Per-step adapters turn them into commands. The simulator imports no core code. Generated tax IDs carry the fictional prefix ([DS-17](DS-17-synthetic-dataset.md) rules 1, 7, 19).
- **Edge cases.** [edge-cases.csv](../catalogs/edge-cases.csv) (EC-xx), with injectors (DS-17 section 7). Parallel tests: `PAR-nn` (DS-16 rule 31).
- **Coverage.** 90% branch coverage per package from `build_step` 1 on `ledger`, `inventory`, `registry`, `documents`, `tax`, `localization` (ADR-0022 rule 16).
- **Design lab.** `docs/reviews/2026-11-14-design-validation/lab/` is design evidence, never imported, and not a build-step acceptance test. Gates are in [spec 11](../spec/11-build-order.md).
- **Done means** `erpme-dev ci --json` passes (every CI job's subcommands). Its summary goes into the pull request (ADR-0022 rules 14, 22).

## A8. Pointers

- Entry point: root [AGENTS.md](../../AGENTS.md); this file details its architecture rules. Then the module's `AGENTS.md` and the task's skill in `.claude/skills/` (ADR-0022 rule 23).
- Glossary: [spec/00-reading-guide.md](../spec/00-reading-guide.md). Envelope and error catalog: [DS-04](DS-04-command-envelope.md). Design items: [backlog.md](backlog.md). Stop and ask: [runbook/escalation.md](../runbook/escalation.md).
- Generated: [data map](generated/data-map.md), [module cards](generated/module-cards.md), [event matrix](generated/event-matrix.md), [ADR index](generated/adr-index.md).
- No document defines a per-task context pack or a compiled spec yet.
