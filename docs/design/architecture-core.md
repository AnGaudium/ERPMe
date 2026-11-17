# NativeFlows architecture: coder core

Read this before every coding task. It summarizes rules and creates none. If it disagrees with an ADR, the ADR wins; report the difference in [open-questions.md](../open-questions.md). Full overview: [architecture-overview.md](architecture-overview.md).

## A1. NativeFlows in five lines

1. NativeFlows is an ERP with a deterministic core. AI only drafts and proposes (D2).
2. Every write is a command. A client sends it twice: simulate, then execute with the same `plan_hash` ([ADR-0008](../adr/0008-command-envelope-and-registry.md)).
3. One Python distribution `nativeflows`, one PostgreSQL database, all tables in schema `nativeflows` ([ADR-0022](../adr/0022-repository-and-engineering-conventions.md) rules 1, 7).
4. Modules sit in six layers and import downward (ADR-0022 rule 2).
5. Events go to a transactional outbox, delivered after commit ([ADR-0013](../adr/0013-outbox-and-events.md)).

### Layer table (ADR-0022 rule 2)

| Layer | Modules |
| --- | --- |
| 6 Composition | `app` |
| 5 Interfaces | `api`, `query`, `agents`, `sdk`, `imports`, `automation` |
| 4 Commercial | `sales`, `purchasing`, `cash`, `reporting`, `crm`, `planning` |
| 3 Core business | `ledger`, `inventory`, `master_data`, `tax`, `production`, `assets` (Phase 3) |
| 2 Platform | `registry`, `documents`, `periods`, `permissions`, `outbox`, `audit`, `localization`, `db`, `agent_runs`, `work`, `attachments`, `policy`, `configuration` |
| 1 Foundation | `numeric`, `clock`, `ids`, `i18n`, `errors` |

Import rules (ADR-0022 rules 2, 5, 6; [ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 1):
- Another module is imported only through its `contract.py`, from any layer (rule 3). Foundation modules and `db` publish through `__init__`. Rule 6 keeps modules of layers 3 and 4 independent except their `contract`; rule 2 names one same-layer exception, `tax` to `ledger` (`ledger` never imports `tax`; see the overview's findings). `reporting` imports no other layer-4 module (rule 2 note).
- Layer 2: `registry` imports `work` and `policy`, and the `agent_runs` contract. `documents`, `outbox`, `permissions`, `attachments`, `agent_runs` and `policy` import `work`. `documents` and `permissions` may import the `agent_runs` contract; `documents` may import the `attachments` contract. `configuration` imports the `registry` contract and `work`.
- Layer 5 modules import no layer-5 peer. `query` imports `db`, `registry`, `agent_runs` and the `work` contract. `agents` imports `registry` and the `agent_runs` and `work` contracts, plus the contracts of the layer 3–4 modules whose subjects its agent types declare ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 1). `automation` imports `registry` and the `configuration`, `work` and `permissions` contracts (ADR-0022 rule 2 note).
- `nativeflows.registry.dispatch` loads `app` through an entry point, never a static import.
- Sideways or up: use a hook. A module declares it; a module of the same or a higher layer registers it; `app` wires it.
- `nativeflows` imports no tool package and no `l10n_*`. `l10n_*` imports only `nativeflows.sdk`. Only `nativeflows.agents.gateway.adapters` imports an LLM provider library.

The complete list is the import-linter contracts in the root `pyproject.toml` (ADR-0022 rules 1, 6). This section names the exceptions the ADRs state.

## A2. Where code goes

Rules: ADR-0022 rules 3, 4, 7, 8, 17, 23 unless named.

| Thing | Place |
| --- | --- |
| Schemas, posting interfaces, interfaces packages implement | `backend/src/nativeflows/<module>/contract.py` |
| Command handler | `<module>/handlers/`, function in `snake_case` (`post_goods_receipt`, [ADR-0004](../adr/0004-naming-conventions.md) rule 19) |
| Consumer | Registered handler of the owning module; `app` registers it ([ADR-0013](../adr/0013-outbox-and-events.md) rule 6; ADR-0022 rule 5). No ADR names its folder: ask first |
| Query | Schema in `contract.py`; `app` registers it (ADR-0008 rule 1; ADR-0022 rule 5). No ADR names its folder |
| Table | `<module>/tables.py`, private, exactly one owner module |
| Private logic | `<module>/services/` |
| Local rules; tests | `<module>/AGENTS.md` (≤ 40 lines); `backend/tests/<module>/` |
| Migration; RLS (`rls_v1`), triggers, functions, grants by hand | `backend/migrations/`, one linear Alembic history |
| Views for agents and reports | Schema `query`, owner `nativeflows_query_owner` |
| Generated files (never edit) | `backend/generated/`, `frontend/src/generated/` |
| Setting | Settings registry ([ADR-0063](../adr/0063-configurable-policy-settings.md) rule 1); seed `docs/catalogs/settings.csv` |
| Operating preset | Registry reference data ([ADR-0067](../adr/0067-quickflows-operating-presets.md) rule 2, proposed); seed `docs/catalogs/setting-presets.csv`; applied by ordinary commands; no business code reads a preset code |
| Work item kind | Registered like a command ([ADR-0042](../adr/0042-work-queue.md) rule 1); seed `docs/catalogs/work-item-kinds.csv` |
| Work case kind | Registered like a work item kind ([ADR-0066](../adr/0066-work-cases.md) rule 3, proposed); seed `docs/catalogs/work-case-kinds.csv`; turned on per company by `work_case.<kind>.mode` |
| Country rule | `l10n/l10n_<country>/`, never the core ([ADR-0016](../adr/0016-localization-package-structure.md); [ADR-0053](../adr/0053-core-neutrality.md)) |

## A3. The life of a command

### Envelope and actor

- Envelope fields: `command_type`, `schema_version`, `company_id`, `idempotency_key`, `mode`, `expected_plan_hash`, `payload` (and `include_canonical_plan`, `as_of_date`, `is_review_skipped`). No others (ADR-0008 rule 7 and its notes; `is_review_skipped`: [ADR-0067](../adr/0067-quickflows-operating-presets.md) rule 13, proposed).
- The actor, `on_behalf_of` and `agent_run_id` come from the credential, never the client. `idempotency_key` is required in both modes, scoped to (actor, command type) (ADR-0008 rules 8, 14).
- `simulate` runs the real handler and rolls back; `execute` commits only if the plan hash equals `expected_plan_hash`, else `plan_hash_mismatch` (ADR-0008 rules 9, 13).
- Only consumers and system jobs (internal callers, in process) execute without a simulation and `expected_plan_hash`; every other actor simulates first (ADR-0013 rule 9; ADR-0008 rule 13 note).
- `as_of_date`: the simulation returns the business date it used; send it on execute and every `clock.today(company)` returns it, so the plan hash survives midnight. More than one day off returns `as_of_date_out_of_range`. Never use it as `posting_date` ([ADR-0007](../adr/0007-time-model.md) rule 15 note).

### Dispatcher steps, in order

ADR-0008 rule 5; [DS-04](DS-04-command-envelope.md#dispatcher-check-order). Simulate is a mode of the whole run, not a step. A step runs only if the earlier ones passed.

1. **Credential and actor context**, causation chain and depth.
2. **Run gates.** `tool_not_allowed`, then `tainted_run_not_allowed`, then the tainted reference scope. Automation depth and allowed-command checks.
3. **`human_only` and agent-chain refusals.** `human_only`, `proposal_required`, `origin_run_submit_not_allowed`.
4. **Permission.** `permission_denied`, `proposal_required`; the `direct_master_data_change` deny.
5. **Record visibility.** Company, record scope, owner scope. A hidden record is `record_not_found`.
6. **Idempotency.** Execute inserts `idempotency_record` first. Same key and request hash: stored response (`replayed: true`), steps 7–10 skipped; different hash: `idempotency_key_reused`. Simulate only looks up.
7. **Work item claim** of an agent run's bound item (`FOR KEY SHARE`). Shadow runs skip it.
8. **State-dependent authorization.** `segregation_of_duties`, `approver_not_eligible`, `approval_already_given`, `approval_would_strand_stage`.
9. **Policy point and floors.** `policy_denied`, `approval_required`; inside the handler for `is_policy_in_handler`, and for a `system` or `integration` post of a document type with an auto-post checker, where the gateway reads the built plan ([ADR-0065](../adr/0065-deterministic-auto-post-gateway.md) rule 3, proposed).
10. **Handler, audit record, events.** The handler runs; the dispatcher writes the audit record, events, deliveries and stored response.

Steps 6 to 10 are for commands only. In a batch, steps 1 to 5, 7 and 8 run per item; step 6 runs once (DS-04).

### Handler contract

- A handler is `handle(context, payload) -> result` (ADR-0008 rule 4).
- `context` holds: the database connection, `new_id(table)`, the clock (`now()`, `today(company)`), the lock helpers, and `emit(event_type, subject, payload)` (DS-04, Handler context). Also: the write helpers for change-tracked tables ([ADR-0038](../adr/0038-audit-and-observability.md) rule 3); `evaluate_policy(input)`, called exactly once by an `is_policy_in_handler` handler ([ADR-0030](../adr/0030-commercial-seams-and-imports.md) rule 7); `change_proposal_execution` when the proposal executor calls (DS-04).
- A handler reads and writes only through `context`. No network, file, LLM or job. Same state, payload and business date give the same result. Order-sensitive queries use `ORDER BY` on stable keys (ADR-0008 rule 4).
- IDs come only from `context.new_id(table)` (ADR-0008 rule 12).
- Locks follow one global order ([ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 10): documents; period area state (share); planning state or `production_structure` or `configuration_state`; warehouse tasks; handling units; `stock_value`; `stock_quantity`; bins; partners; `money_account_balance`; open items; numbering counters; `event_subject`. The idempotency record is taken before all of these. Work item rows a command raises are the last class, in (`kind`, `open_key`) order. The lock helper raises in tests on a wrong order (ADR-0022 rule 10).
- A document command carries `version` and locks the `document` row first. A stale version is `version_conflict` ([ADR-0009](../adr/0009-document-lifecycle.md) rule 10).
- Simulation takes no lock on serialized rows and consumes no number (ADR-0008 rule 10).

### Posting interfaces

- A posting interface is a plain function in `contract.py` taking the caller's `context`: `ledger.contract.write_journal_entry`, `inventory.contract.move_stock`, `documents.contract.assign_number`, `periods.contract.check_posting`. It runs in the caller's transaction and plan, with no permission, idempotency or policy step, and is never on REST or MCP.
- Synchronous cross-module writes use posting interfaces; asynchronous reactions use events and consumers (ADR-0022 rule 4).

### Skeleton

Names marked `# shape` are not fixed by an ADR. The rest is.

```python
# backend/src/nativeflows/inventory/handlers/post_goods_receipt.py   # shape: file name
from nativeflows.documents import contract as documents   # layer 2: downward
from nativeflows.ledger import contract as ledger         # layer 3: another module's contract only
from nativeflows.periods import contract as periods       # layer 2: downward
from nativeflows.inventory.contract import (
    GoodsReceiptPosted, PostGoodsReceipt, PostGoodsReceiptResult, move_stock)
from nativeflows.inventory.services import receipts       # private to inventory

def post_goods_receipt(context, payload: PostGoodsReceipt) -> PostGoodsReceiptResult:
    doc = documents.lock_document(context, payload.id, payload.version)  # shape; ADR-0009 rule 10
    periods.check_posting(context, payload.posting_date)                 # ADR-0022 rule 4
    lines = receipts.load_lines(context, doc)            # shape; ORDER BY line_number
    move_stock(context, receipts.movements(lines))       # stock locks via the helper
    ledger.write_journal_entry(context, receipts.entry(lines, payload.posting_date))
    number = documents.assign_number(context, doc)       # numbering lock after stock
    documents.mark_posted(context, doc)                  # shape; state 'posted', posted_at
    context.emit(
        "GoodsReceiptPosted", ("document", doc.id),      # shape: subject form
        GoodsReceiptPosted(id=doc.id, number=number,
                           posting_date=payload.posting_date, version=doc.version))
    return PostGoodsReceiptResult(id=doc.id, number=number)

# Registration (shape): the fields of ADR-0008 rule 1, e.g. effect_class="posting"; `app` registers it.
```

The dispatcher, not the handler, writes the audit record and the deliveries.

### Outbox and `event_delivery`

- `context.emit` records the event. After the handler returns, the dispatcher locks `event_subject`, writes `outbox_event` and adds one `event_delivery` per subscribed consumer, in the same transaction (ADR-0013 rules 1, 3, 6; ADR-0022 rule 10).
- `subject_sequence` (from `event_subject`) is the only event order (ADR-0013 rule 3).
- After commit, workers claim deliveries in subject order with `SKIP LOCKED` (ADR-0013 rule 7; details in overview B7).
- A transactional consumer runs in a second transaction that also marks the delivery `done`. It writes only through commands, as `system` on behalf of the event's human, key `<consumer>:<event id>:<n>` (ADR-0013 rules 7, 9).
- Every agent run starts through `StartAgentRun` and is bound to a work item. Callers: the consumer `agent_wake_up` on `WorkItemRaised`, a schedule, a person, or an automation rule's `start_agent`. For a subject without an item the handler creates and claims an `agent_task` item. It emits `AgentRunStarted`; the consumer `agent_runner` runs it on queue `agents` (ADR-0013 rules 12, 13; ADR-0050 rules 15–16; [ADR-0058](../adr/0058-configurable-workflows.md) rule 7).
- A tainted event's consumer may run only `is_draft_only` commands (plus work item raises; `CompleteAgentRun` is exempt) (ADR-0013 rule 11).
- Unattended postings go only through the auto-post gateway: `RunAutoPostGateway` simulates `Post<Type>` as `system` in its own chain, then executes with `expected_plan_hash` and `as_of_date` when the decision is `auto_post`. A consumer never posts a draft for an agent, and a checker never calls an LLM or writes ([ADR-0065](../adr/0065-deterministic-auto-post-gateway.md) rules 3, 7, proposed).

## A4. Data rules every table follows

**IDs and keys** ([ADR-0006](../adr/0006-id-and-numeric-model.md) rules 1–7)
- Primary key: one column `id uuid`, UUID v7; never composite. Core catalog rows: UUID v5 from `"<table>:<code>"`.
- `Create` accepts an optional client `id` (UUID v7). Commands refer to records by `id` only, never by `code` or number. Foreign keys end in `_id` (ADR-0004 rule 12).

**Company and RLS** ([ADR-0017](../adr/0017-permission-envelope.md) rules 18–19)
- Company tables have `company_id` and `FORCE ROW LEVEL SECURITY`. Each transaction sets `nativeflows.company_id`; without it no row is visible. Null-company rows need the value `installation`.
- In `master_data` and `crm`, references between company tables are composite on (`company_id`, `id`) wherever the parent has that key; other references are validated by the handler under RLS ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 1; [ADR-0052](../adr/0052-minimal-crm.md) rule 3). No ADR states this for the other modules; follow the module's DDL.

**Time** ([ADR-0007](../adr/0007-time-model.md))
- Business dates are `date` named `_date`; system instants are UTC `timestamptz` named `_at` (rules 1–2).
- `recorded_at` is on every row, set by the system; one transaction has one instant; never order by an `_at` column (rules 9–10).
- Business date from `clock.today(company)` or input; durations are integers with a unit in the name; `posting_date` explicit at posting (rules 5, 8, 15–16).

**Append-only and immutable** (ADR-0009 rule 14)
- Final states `posted`, `reversed`, `canceled`, `closed` are immutable. Triggers reject changes to the header, lines and `document` row. One exception: `Reverse` changes `document.state` from `posted` to `reversed`. The same immutability applies in `issuing` ([ADR-0028](../adr/0028-document-lifecycle-hardening.md) rule 6).
- `document_version`, `policy_decision` and `approval` rows are never updated or deleted.
- Journal and material document rows are append-only (DS-06; [ADR-0020](../adr/0020-inventory-and-costing-model.md) rule 3).
- Data that arrives after posting goes into its own table that refers to the document.

**Corrections and reversals** (ADR-0009 rules 18–23)
- A posted document is corrected by a correction document (`correction_of_id`): a return, credit or debit note, adjustment or replacement invoice.
- `is_reversible` is set per document type, default false (ADR-0009 rule 19). Internal types are reversible. Documents from or to an outside party (goods receipts, deliveries, payments, purchase invoices) are reversible under a flagged interim rule while no live document refers to them. Sales invoices and e-invoiced documents are never reversed. `Reverse<Type>` is `human_only`, and a reversal document is never reversed (rules 18, 21).

**Numbers** (ADR-0006 rules 8–21)
- Domains `types.amount` (24,4), `types.quantity` (24,6), `types.unit_price` (28,10), `types.exchange_rate` (30,15), `types.percent` (9,6); Python types `Amount`, `Quantity`, `UnitPrice`, `ExchangeRate`, `Percent` in `nativeflows.numeric`.
- JSON carries them as canonical strings; a JSON number is rejected. Amounts are stored at the currency's minor unit; extra input decimals are rejected, never rounded.
- Rounding goes only through `round_amount`, `round_quantity`, `round_unit_price`, `round_exchange_rate`, `round_percent`. Conversion only through `convert_amount`.
- Line amount: `round_amount(quantity × unit_price, currency)`; totals sum rounded lines. Conversion differences go to one rounding line on `rounding_gain` or `rounding_loss`. `_percent` columns hold 8 for 8%.
- A document line stores its unit conversion as a snapshot (`uom_numerator`, `uom_denominator`, `uom_factor_source`) and never reads it again (ADR-0006 rule 11 note; [ADR-0056](../adr/0056-multiple-units-of-measure.md)).

**Secrets and change tracking**
- `is_secret` fields never reach a view, an agent's query result or a prompt ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rule 11).
- Change-tracked tables (master data, settings, role assignments, period state, production structures) are written only by `context`'s write helpers (ADR-0038 rule 3).

Some DDL drafts break these rules ([findings](architecture-overview.md#findings-for-the-review)). Do not copy them; follow the ADR.

## A5. Never do this

"check: X" is the `nativeflows-dev check` custom check X of ADR-0022 rule 13.

| Never | Rule | Check |
| --- | --- | --- |
| Call the network, a file, an LLM or the job queue in a handler (record an intent; overview B7) | ADR-0008 rule 4; ADR-0013 rules 10, 13 | import-linter `forbidden` contract (ADR-0022 rule 6) |
| Write the database outside `context` | ADR-0008 rule 4; ADR-0038 rule 3 | check: Serialized tables; change-tracked guard (ADR-0038 rule 3; not yet in ADR-0022 rule 13) |
| Read or write a serialized table (stock balances, numbering counters, open items) outside its lock helper | ADR-0008 rule 10; ADR-0026 rule 3 | check: Serialized tables |
| Take locks out of the registered order | ADR-0027 rule 10 | Lock helper raises in tests (ADR-0022 rule 10) |
| Use a float for money, quantities, prices, rates or percentages | ADR-0006 rule 12 | check: Floats |
| Round or convert outside `nativeflows.numeric` | ADR-0006 rules 10, 15 | check: Rounding and conversion |
| Compute money in the client | ADR-0040 rule 2 | no check exists yet (finding) |
| Call `datetime.now`, `date.today`, `time.time`; use `current_date`, `clock_timestamp()` in SQL | ADR-0007 rule 16 | ruff `TID251`, `DTZ`; check: Database time functions |
| Import upward or sideways | ADR-0022 rules 2, 6 | import-linter layers and independence contracts |
| Import a tool package, a lab script or `l10n_*` from `nativeflows` | ADR-0022 rule 6; [lab README](../reviews/2026-11-14-design-validation/README.md):5 | import-linter for tools and `l10n_*`; no check exists yet for lab code (finding) |
| Edit a document in a final state | ADR-0009 rules 14, 23 | Database triggers (ADR-0009 rule 14); trigger tests |
| Let an agent submit, post, issue, approve or send | ADR-0050 rule 30; ADR-0017 rule 15 | Registry CI check and INV-214 |
| Post as `system` or `integration` outside the auto-post gateway, or change a draft or call an LLM in a checker | [ADR-0065](../adr/0065-deterministic-auto-post-gateway.md) rules 3, 7 (proposed) | INV-760, INV-762; no check exists yet (finding) |
| Check permissions or policy inside a handler, except the one `context.evaluate_policy` call of an `is_policy_in_handler` command | ADR-0008 rule 5; ADR-0030 rule 7 | no check exists yet (finding) |
| Give a plan row its `id` from a column default, trigger or sequence | ADR-0008 rule 12; ADR-0006 rule 2 | Test named in ADR-0008 rule 12 |
| Use sequences, session advisory locks or non-`LOCAL` `SET` on handler or trigger paths | ADR-0008 rule 9; ADR-0022 rule 13 note | check: Session locks and settings |
| Refer to a record by `code` or number in a command | ADR-0006 rule 5 | no check exists yet (finding) |
| Use camelCase, aliases, `status`, a PostgreSQL `ENUM`, or a name over 63 bytes | ADR-0004 rules 3, 6, 13, 14 | ruff `N`; check: Identifiers; no check exists yet for `status` and `ENUM` (finding) |
| Hard-code a country rule or an unverified legal rule in the core | ADR-0053; ADR-0016; AGENTS.md | no check exists yet (finding); review |
| Put personal data or a snapshot in an event payload | ADR-0013 rule 4 | Registry CI check of payload fields against data labels |
| Edit a generated file | ADR-0022 rules 17, 24 | `nativeflows-dev generate --check` |
| Write separate simulation code | ADR-0008 rule 9; ADR-0004 rule 18 | INV-12 `executed_equals_simulated` |
| Execute over a transport without simulating first, or change `as_of_date` between simulate and execute | ADR-0008 rules 12, 13 and notes; Principle 2 | Dispatcher: `expected_plan_hash` required; `plan_hash_mismatch` |
| Omit `company_id` on a company table | ADR-0017 rule 19 | RLS policy test against `pg_policies` (ADR-0022 rule 8) |

## A6. Error model and check results

- Every error on every transport is `{"errors": [ … ]}`, each item with `code`, `message`, `rule`, `field`, `fix`, `retryable`, `details` (ADR-0008 rule 24). `code` comes from the registry's catalog; a command declares the codes it returns (ADR-0008 rule 1).
- Categories and HTTP status: `malformed` 400, `unauthenticated` 401, `permission` 403, `not_found` 404, `conflict` 409, `too_large` 413, `validation` 422, `precondition` 422, `rate_limited` 429, `internal` 500, `unavailable` 503 (ADR-0008 rule 25).
- `retryable` is fixed per code. `concurrent_update` and `timeout` are retryable (DS-04 catalog; ADR-0022 rule 9).
- Validation reports every field error at once. `internal` errors show no stack trace or SQL (ADR-0008 rules 24–25).
- A hidden record is `record_not_found` (ADR-0008 rule 5). An unknown `id` names its table and `List<Noun>` query (ADR-0006 rule 5). A wrong state is `invalid_state_transition` with the allowed commands (ADR-0009 rule 5).
- Check results do not stop a command. They return in `checks` as `{code, message, rule, field, details}`; their `[code, field]` pairs are hashed unless the code is listed unhashed ([ADR-0040](../adr/0040-ui-architecture.md) rule 10; DS-04).
- No ADR defines how a handler raises an error. `errors` is a layer-1 module (ADR-0022 rule 2); its API is not designed yet.

## A7. Testing on one page

- **Real database:** PostgreSQL as the product roles, via testcontainers (ADR-0022 rules 7, 14).
- **Invariants.** [invariants.csv](../catalogs/invariants.csv) lists INV-xx, one check each (`@invariant("INV-nn")`). A row at or below `build_step` without a check fails CI. Checks use plain SQL as `nativeflows_check`, never core code ([DS-16](DS-16-invariants-and-harness.md) rules 2, 4–5).
- **One protocol.** Each harness command is simulated, executed with the plan hash (INV-12), and checked for outcome (INV-19), field classes (INV-15) and events (INV-18); retries reuse the key (INV-11) (DS-16 rule 15).
- **Synthetic data.** The simulator writes business events; per-step adapters turn them into commands; generated tax IDs carry the fictional prefix ([DS-17](DS-17-synthetic-dataset.md) rules 1, 7, 19).
- **Edge cases** EC-xx in [edge-cases.csv](../catalogs/edge-cases.csv) (DS-17 section 7); parallel tests `PAR-nn` (DS-16 rule 31).
- The design lab is not an acceptance test. State machines, recomputation and coverage: overview B16.
- **Done means** `nativeflows-dev ci --json` passes (every CI job's subcommands). Its summary goes into the pull request (ADR-0022 rules 14, 22).

## A8. Pointers

- **Coding-rules gate:** no product code until `nativeflows-dev check` passes on the empty skeleton with every contract and check; limits, suppressions, lock order and the two check speeds are in the note on [ADR-0022](../adr/0022-repository-and-engineering-conventions.md) rule 13 (2026-11-16).
- Root [AGENTS.md](../../AGENTS.md) first; then the module's `AGENTS.md` and the task's skill in `.claude/skills/` (`new-command`, `new-migration`, `posting-change-review`, …; ADR-0022 rule 23).
- [Glossary](../spec/00-reading-guide.md); [DS-04](DS-04-command-envelope.md) (envelope, errors); [backlog](backlog.md); [escalation](../runbook/escalation.md).
- Generated: [data map](generated/data-map.md), [module cards](generated/module-cards.md), [events](generated/event-matrix.md), [ADRs](generated/adr-index.md).
