# ERPMe design reconstruction (independent review, part 1)

Snapshot: `the read-only snapshot of commit 9ac727f` (AGENTS.md, README.md, docs/ without archive/ and prompts/). Reconstructed from the documents alone. Nothing below is invented: where the documents are silent, this report says so and marks the point MISSING or "not stated".

## 0. Conventions of this report

**Citations.** `ADR-0009 r11` = ADR-0009 rule 11. `spec 07` = `docs/spec/07-shared-foundation.md`. `RG` = `docs/spec/00-reading-guide.md` (glossary). `DS-04 §x` = section of a design file. `OQ` = `docs/open-questions.md` (quoted by its subject). `BL` = `docs/design/backlog.md`. `RB` = `docs/runbook/`. Catalogs: `system-accounts.csv`, `transaction-keys.csv`, `movement-types.csv`, `invariants.csv` (INV-xx), `edge-cases.csv` (EC-xx).

**Step status labels.**
- **DESIGNED**: an accepted ADR or DS file states the rule (possibly with a *flagged* interim value; flags are noted).
- **DEFERRED (DS-xx)**: assigned to a backlog item whose file is not written yet. Unwritten items in the snapshot: DS-19, DS-20 (rest: price lists, employees, cost centers, projects, warehouses beyond ADR-0020), DS-21, DS-22, DS-23, DS-24, DS-25, DS-26, DS-27, DS-28, DS-29, DS-30, DS-31, DS-32, DS-33, DS-34, DS-35 (beyond ADR-0019), DS-36, DS-37, DS-38, DS-39, DS-40; DS-09 algorithm spec and DS-11 logic spec ("step 3 spec"); DS-15 full model (step 5).
- **MISSING**: no ADR, DS item or backlog row owns it.
- **FLAGGED**: interim rule that is the author's (ADR-0005 reserved items 1, 11), listed in OQ.

**Table status labels (part B).** **D** = columns defined in a normative document; **P** = partially defined (some columns or keys named); **N** = named only, never defined.

---

## A. Architecture

### A.1 Overall shape

- One modular monolith, Python 3.14 + PostgreSQL 18, TypeScript UI (D13, D14; ADR-0001; ADR-0022 r11). No event sourcing: state tables + append-only journal + transactional outbox written in one transaction (D4; spec 07 "Data storage").
- All clients (UI, mobile/PWA, agents, integrations) are peers calling one command layer; no client writes data directly (spec 04; Principle 1).
- Command layer asks the policy engine before posting; the core appends to the books and emits events; events go to the work queue and wake the responsible agent or human (spec 04).
- Deliberately not used: ORMs, event sourcing, microservices, GraphQL, Kafka, Redis, Elasticsearch, agent frameworks, workflow engine (ADR-0002).

### A.2 Modules and layers (ADR-0022 r2–r6)

| Layer | Modules | Notes |
| --- | --- | --- |
| 6 Composition | `app` | Registers handlers, consumers, queries; startup checks; entry points `erpme serve`, `erpme worker --queue`, `erpme admin migrate`, `erpme admin bootstrap` (r5) |
| 5 Interfaces | `api` (REST + MCP generated), `query` (DS-33), `agents` (after step 4), `sdk` | `sdk` re-exports package-facing interfaces; its licence is an OQ (interim AGPL, r25) |
| 4 Commercial | `sales`, `purchasing`, `cash`, `crm`, `planning` | `planning` reads `inventory.contract`'s `demand_supply_line`, hands over through `inventory.contract.request_replenishment` |
| 3 Core business | `ledger` (journal, accounts, determination, multi-currency), `inventory` (material docs, stock, costing, landed cost, warehouse management tables), `master_data` (partners, products, warehouses, units, currencies), `tax` | |
| 2 Platform | `registry`, `documents`, `periods`, `permissions`, `outbox`, `audit`, `localization`, `db` | `db` holds the generic lock helper and the lock-order registry |
| 1 Foundation | `numeric`, `clock`, `ids`, `i18n`, `errors` | |

- A module imports only lower layers; layers 3–4 are independent except via `contract.py` (r6, import-linter). Handlers may not import network/file/LLM/job libraries (forbidden contract, r6; ADR-0008 r4).
- Each owning module: `contract.py` (schemas, posting interfaces, package interfaces), `handlers/`, private `tables.py`, `services/`, `AGENTS.md` ≤40 lines (r3).
- One schema `erpme`, domains in `types`, Procrastinate in `procrastinate`; every table owned by exactly one module's `tables.py`, CI-checked (r7).
- Test tooling packages outside `erpme`, never imported by product: `erpme_events`, `erpme_client`, `erpme_adapters`, `erpme_simulator`, `erpme_testkit`, `erpme_reference`, `erpme_dev` (r1, r6; DS-16 §1).

### A.3 Command envelope and dispatcher (ADR-0008; DS-04)

- **Registry** (r1): each command type registered once with `command_type`, semver `schema_version`, scope (`company`/`installation`), payload/result models, handler, error codes, permission, `human_only`. Queries (`Get<Noun>`, `List<Noun>`) registered the same way. REST/MCP/JSON Schema/TypeScript generated, nothing hand-written per command (r6; ADR-0022 r17).
- **Envelope** fields: `command_type`, `schema_version`, `company_id`, `idempotency_key`, `mode` (`simulate`|`execute`), `expected_plan_hash`, `payload`; nothing else accepted (r7). Actor, `on_behalf_of`, `agent_run_id` come only from the credential (r8).
- **Dispatcher order** (r5): permission, record visibility, `human_only` before anything (even replay) → for posting handlers, policy engine (DS-28; stub that allows until then) → handler.
- **Handler contract** (r4): `handle(context, payload)`; only DB connection, `new_id`, clock, lock helpers, `emit` from `context`; no network/file/LLM/job; deterministic for same DB state, payload and business date.
- **Simulation** (r9–r10): same handler in a transaction always rolled back; `SET CONSTRAINTS ALL IMMEDIATE` before hashing; no sequences/advisory locks/non-LOCAL SET; lock helpers take no stock/numbering locks in simulate mode and numbering returns placeholders.
- **plan_hash** (r12; DS-04 "Canonical plan"): SHA-256 over canonical JSON of journal lines + stock movements + result; new IDs tokenized `new:<table>:<n>`; `DocumentNumber` and `SystemInstant` removed. Warehouse task proposals and planning outputs are listed like events, never hashed (ADR-0023 r11; ADR-0024 r17). Events are listed in the simulate response, not hashed (ADR-0013 r5).
- **Execute** (r13): requires `expected_plan_hash`; mismatch → rollback + `plan_hash_mismatch` with new plan. Internal callers (consumers, system jobs, in-process only) execute without simulation (amended by ADR-0013 r9).
- **Idempotency** (r14–r19): scope (actor, command type | `command_batch`); first statement `INSERT … ON CONFLICT DO NOTHING` into `idempotency_record`; response stored in same tx; same hash → stored response (`replayed: true`), different hash → `idempotency_key_reused`; simulate never writes it; retention ≥90 days.
- **Batches** (r20–r21): ordered items, same company/actor, one transaction, one hash, one key; max 1,000 items.
- **Errors** (r24–r25; DS-04 catalog): one shape `{errors:[{code,message,rule,field,fix,retryable,details}]}`; categories with fixed HTTP status; "check results" are non-error findings returned on success (e.g. `partner_duplicate_suspected`, `no_pickable_stock`, `customs_assessment_differs`).
- **Transports** (DS-04): `POST /api/commands/<snake>`, `/api/command-batches`, `/api/queries/<snake>`; MCP tool per command/query; filters in body (r22).
- **Runtime limits** (ADR-0022 r9): `lock_timeout` 5 s; `transaction_timeout` 30 s commands/queries, 4 min consumers, 15 min long jobs (costing, planning, forecast, close tasks); rate limits per actor (human 20/s, agent 5/s, integration 50/s, system exempt).

### A.4 Documents, versions, approval, numbering (ADR-0009)

- Shared `document` row + typed header table sharing `id` + `<header>_line` lines (r1). Type registry flags `is_posting`, `is_approval_hold_allowed`, `is_reversible` (default false); commands generated from the verb list (r2).
- Posting types: `draft → (pending_approval →) approved → posted → reversed`; `canceled` from unposted states; `Delete` only for never-submitted unreferenced drafts (r4–r5). Non-posting types (orders, quotations, requests): `draft`, `pending_approval`, `approved`, `closed`, `canceled`; an order is in force only when `approved` (r6). Fulfilment is computed from referring documents, never stored as a state (r7).
- Every `Update` writes a new `document_version` (canonical content + SHA-256 `version_hash` + full actor context incl. `origin_agent_run_id`) and returns to `draft`, voiding approvals (r9; ADR-0017 r16). Commands carry `version`; stale → `version_conflict` (r10).
- `Submit` asks policy → `policy_decision` bound to `document_version_id` (allow / approval required / deny / human only); `approval` rows immutable, human only, with reason (r11; ADR-0017 r15).
- `is_approval_hold_allowed: false` for e-invoice-issued types; if policy requires approval, interim FLAGGED: treated as human only (r12).
- `Post<Type>`: period check, number, journal and/or material document, `state=posted`, `posted_at`, one transaction (r13). Final-state rows immutable by trigger (r14).
- Gapless `numbering_series` per (company, type, fiscal year, branch) incremented only via the numbering lock helper at posting (r15). Format/order FLAGGED (r16). Non-posting numbering FLAGGED: at first approval, by document_date fiscal year (r8).
- Reversal: `Reverse<Type>` `human_only`, new reversal doc with `reversal_of_id`, emits `<Type>Posted` + `<Type>Reversed` (r18). Only internal types reversible (author's decision); outside-party docs reversible while unreferenced (FLAGGED interim); sales invoices / e-invoices never (r19). Storno vs swapped, reversal date in locked period, reversed material value: package config, FLAGGED (r20). Reversal of a reversal not allowed (interim, r21).
- Correction documents (`sales_return`, `purchase_return`, `credit_note`, `debit_note`, adjustment/replacement invoice, `landed_cost_correction`, `customs_declaration_amendment`) with `correction_of_id`, created from the original; posting is `human_only` interim FLAGGED (r23).
- Every transition emits `<Type><EventForm>` through the outbox (r22).

### A.5 Posting interfaces (ADR-0022 r4; ADR-0008 r4)

In-process functions in `<module>.contract`, taking the caller's `context`, running in the caller's transaction and plan, with no own permission/idempotency/policy step, never exposed on REST/MCP. Named in the documents:

| Interface | Source |
| --- | --- |
| `ledger.contract.write_journal_entry` | ADR-0022 r4; ADR-0008 r4 |
| `inventory.contract.move_stock` | ADR-0022 r4 |
| `documents.contract.assign_number` | ADR-0022 r4 |
| `periods.contract.check_posting` | ADR-0022 r4 |
| `inventory.contract.create_warehouse_task` | ADR-0023 r11, r20 |
| `inventory.contract.create_stock_reservation`, `cancel_stock_reservation` | ADR-0023 r13 |
| `inventory.contract.request_replenishment` | ADR-0024 r22 |
| `demand_supply_line` writes "through posting interfaces" (name not given) | ADR-0024 r8 |
| Package interfaces: `ledger.contract.ExchangeRateFetcher`, `EInvoiceAdapter`, `BankStatementReader` | ADR-0022 r4; ADR-0016 r17 |

Global lock order (ADR-0022 r10 as extended by ADR-0023 r10): period area state rows (share) → warehouse task row → handling unit rows → `stock_value` rows (asc item, warehouse) → `stock_quantity` rows → bin rows → numbering counters → `event_subject` rows.

### A.6 Outbox, events, consumers, technical queue (ADR-0013; ADR-0022 r12)

- `context.emit(event_type, subject, payload)` writes `outbox_event` and, same tx, one `event_delivery` per subscribed consumer (r1, r6). Payload = facts + IDs, no snapshot, no personal fields (r4).
- Ordering only by `subject_sequence` from `event_subject` (r3). Workers claim with `FOR UPDATE SKIP LOCKED`, strictly in subject order per consumer; lease 5 min; exponential backoff min(2ⁿ s, 1 h); after `max_attempts` (10) → `held`, blocks later events of the subject; human `RetryEventDelivery`/`SkipEventDelivery` (`human_only`) (r7–r8; ADR-0022 r12).
- Consumers change data only via commands run in the delivery tx as actor `system` on behalf of the event's human, under the event's company and `business_date`, idempotency key `<consumer>:<event id>:<n>`, inheriting `origin_agent_run_id` (r9).
- External calls: transactional consumer records an intent by command → event → `external` consumer on `integrations` queue calls outside with no tx open, records outcome by command; unknown outcome → ask provider status first (r10).
- Taint: events from a run that read untrusted content carry `is_tainted`; consumers may only create drafts and work items for them; taint propagates (r11).
- Agent wake-ups are consumers creating/updating work items; agent runs start from work items, never directly from events (r12).
- Queues: `events`, `jobs`, `integrations`, `pdf` (Procrastinate) (r13). Retention 400 days, partitions by month; `ReplayEvents` for new consumers (paused at registration) (r15–r16). Upcasters for event majors (r17).

Named events: `GoodsReceiptPosted`, `SalesOrderClosed` (examples, ADR-0009 r22); `PostingPeriodRestricted/Opened/Locked/Unlocked` (ADR-0012 r9); `WarehouseTaskCreated`, `WarehouseTaskConfirmed`, `WarehouseTaskCanceled`, `StockReservationCreated`, `StockReservationCanceled` (ADR-0023 r20); `ForecastCompleted`, `PlanningCompleted`, `PlannedOrderFirmed`, `PlannedOrderConverted`, `ReplenishmentRequested` (ADR-0024 r24); `<Type>Posted`/`<Type>Reversed` (ADR-0009 r18); `<Job>Completed` for Run verbs (RG verb table).

Named consumers: `planning_work_items` on `PlanningCompleted` (ADR-0024 r21); the `purchasing` consumer of `ReplenishmentRequested` (ADR-0024 r22); agent wake-up consumers (DS-29/DS-32, ADR-0013 r12); live UI updates (DS-30); e-invoice, email and PDF integration consumers (DS-24, DS-27, ADR-0013 constraints); outgoing message send as intent consumer (ADR-0019 r17).

### A.7 Permissions (ADR-0017; spec 03)

- Actor kinds: `human` (`user_account`), `agent` (`agent_type` + `agent_run`), `integration` (`integration_client`), `system` (registered job/consumer) (r1). Password+TOTP or OIDC; TOTP mandatory for owner/chief accountant/operator (r2; OQ on all users).
- Permission = command/query name or registered capability (`post_in_soft_locked_period`, `start_agent:<agent_type>`); generated list (r4). Roles per company from templates `owner`, `chief_accountant`, `accountant`, `warehouse_keeper`, `sales`, `purchasing`, `viewer`; installation role `operator` (r5, r7).
- Role assignment with record scope (branch/warehouse header dimensions; rows outside → `record_not_found`, lists flag `is_scope_filtered`) and field classes (`cost`, `margin`; omitted from responses, plans, events, errors) (r6, r9, r10).
- Agent effective permissions = intersection of agent type and `on_behalf_of` human, re-evaluated per command (r11). `on_behalf_of` bound at start: starter / schedule owner / intake owner; never an email sender (r12).
- System jobs/consumers hold registered permissions; `on_behalf_of` for accountability, except where an ADR conditions on that human (r13).
- Hard floors: only humans approve (r15); `segregation_of_duties` if any version was written by an agent run (directly or through consumers, via `origin_agent_run_id`) on behalf of the approver (r16); agents never execute `human_only` (r14; ADR-0008 r2). Small-team rules are an OQ; interim: floors apply to all, policy stub allows posting without approval (r17).
- DB defense: roles `erpme_migration` (only BYPASSRLS), `erpme_app`, `erpme_worker`, `erpme_claim`, `erpme_readonly`, `erpme_check`; `FORCE ROW LEVEL SECURITY` on every `company_id` table; `set_config('erpme.company_id', …, true)`; fail closed; claim via security-definer function (r18–r19; ADR-0022 r7–r8).
- Full role/scope/policy model for step 5: DEFERRED (DS-15 full, DS-28).

### A.8 Localization packages (ADR-0016; DS-14; spec 06)

- `l10n/l10n_<cc>/` with `manifest.yaml`, regime folders, data files, `code/` (interfaces only), `i18n/`, `tests/golden/` (DS-14 layout).
- One package + one regime per company, chosen at `CreateCompany` (r2). Package templates copied into company rows (chart, determination, valuation classes, item groups, close checklist, period pattern, numbering, print templates) (r5, r7). Package rules read live and dated: `regime_setting` via `regime_setting(company, key, date)`; tax codes and rates; statutory reports; data labels (r5, r9–r10).
- Every entry carries a basis: `legal_source` (+`verified_by/on`), `author_decision`, `status: unverified` + `open_question`, or `company_decision` (r6). Only the author sets verification (ADR-0003 R10).
- `regime_configuration_missing` when no row; `regime_setting_unverified` refuses unverified rules in `production` (r10, r12). Used rows never change value; loader error `regime_setting_in_use` (r13).
- Core has no defaults for FX rules (ADR-0011 r13), reversal method (ADR-0009 r20), regime movement types (ADR-0020 r5), closed-period landed cost method (ADR-0021 r8), import treatment (ADR-0021 r11), count bin difference method (ADR-0023 r18), closing rules (ADR-0012 r18).
- Package code: `ExchangeRateFetcher`, `EInvoiceAdapter`, `BankStatementReader`, tax ID rule and lookup interface (ADR-0016 r17; ADR-0019 r4, r18). Formats of tax/e-invoice/bank/report/print components DEFERRED to DS-23/24/25/26/27 (DS-14 intro). The Vietnam TT99 content itself is DEFERRED (DS-19).

### A.9 Agents and safety rules

- Principles 3, 4, 8, 12, 13; spec 03 rules 1–9; spec 14 guardrail table; ADR-0019 r14–r20; ADR-0013 r11–r12; ADR-0017 r11–r16.
- Untrusted content: a run that read external content keeps read access scoped to the related partner (migration: the import batch) plus draft creation; may not send, change master data or post; no auto-post from such runs; LLM-contributed matches never auto-post (spec 03 r1, hard floor).
- Fixed tool list per agent type (spec 03 r2); run record (spec 03 r7); budgets with circuit breaker (r8); no hidden memory: learned facts are visible data (`partner_insight`, `interaction_summary`) (r9; ADR-0019 r20).
- Workflow cascade: stored rules/mappings → lookup → fuzzy match with deterministic score → LLM only for the rest; LLM output passes a deterministic check before becoming a draft; a resolution is proposed as a stored rule (Principle 13; spec 14).
- Guardrail defaults (spec 14): read/query automatic; drafts automatic, human confirms before posting; bank match auto-post only after shadow mode, no LLM contribution, below threshold; above-threshold posting and direct-to-expense need approval; sending: draft, human sends, auto-send only permitted types; master data changes need approval; period close and reversal human only.
- Agent auto-posts need an accountable human confirming in batches; unconfirmed auto-posts block close (core close task, ADR-0012 r13; spec 03 r6).
- Phase 1 agents: data migration (after step 4), quotation (after 5), bank matching (after 6), purchase invoices (after 7); planning agent with its phase (spec 11; RB steps-5-9; ADR-0024 r23). "Done" for step 10 = draft-only, replay eval green, hard-floor tests green, ≥90% exact drafts on synthetic data (ADR-0003 R8).
- Runtime (LLM gateway, seats, routing switch, run records, taint, budgets): DEFERRED (DS-32). Read-only query layer: DEFERRED (DS-33). Workflow designs: DEFERRED (DS-34). Seatmap reference (spec 17).
- Data labels and routing switch: off by default; when on, gateway strips personal fields and rejects requests still carrying them; logging of personal fields sent always on (spec 17; D12; ADR-0019 r7, r11).

### A.10 Time, numbers, IDs

- UUIDv7 single-column `id` everywhere; core catalog rows uuid5 from code; commands refer by `id` only (ADR-0006 r1–r7).
- Domains `types.amount numeric(24,4)`, `quantity (24,6)`, `unit_price (28,10)`, `exchange_rate (30,15)`, `percent (9,6)`; JSON strings in canonical form; rounding only in `erpme.numeric`, per-currency rounding mode; one rounding line per entry on `rounding_gain`/`rounding_loss` (ADR-0006 r8–r21).
- `document_date`, `posting_date` (explicit at posting, no default), `recorded_at`; company IANA time zone; `clock.today(company)` overridable only in test/simulation via `business_date_override`; fiscal calendar as data (ADR-0007).

### A.11 Test harness (DS-16, DS-17, ADR-0003, ADR-0022)

- Three reference layers: synthetic dataset replayed day by day; golden scenarios from the author's workbooks; naive recomputation (`erpme_reference`, stdlib only, `Fraction`) (spec 12; DS-16 §7).
- 43 invariants INV-01…INV-62 with check points `command`/`day`/`run`, checked as `erpme_check` role with plain SQL, never core code (DS-16 r2, r4–r13).
- Outcome oracle: each business event carries `must_succeed`/`must_reject`/`may_reject`, set by simulator, never core (INV-19; DS-16 r14).
- Command protocol for every harness command: simulate → execute with hash → outcome → field classes → events vs simulation → period rule; retries for `retry:true` (DS-16 r15).
- Hypothesis state machines drawing business events through step adapters (DS-16 r17); two installations (with/without group currency) (r18).
- Parallel tests PAR-01…PAR-09 (DS-16 r31).
- Simulator: seeded, day by day, business-event log (JSONL) + input files (e-invoice XML, bank CSV, .eml, migration files); per-step adapters; 45 edge cases EC-01…EC-45 with `first_executable_step`; profiles small/medium/large; locks of hashes (DS-17).
- CI via `erpme-dev`; nightly on the test server by timer; defects as GitHub issues (ADR-0003 R6–R7; ADR-0022 r14–r18).

---

## B. Data model

Grouped by owning module where ADR-0022 r2 or the defining ADR states the owner; "(owner inferred)" where only the module's described scope places it; "(owner not stated)" otherwise. Every `company_id` table has RLS (ADR-0017 r18). Every table has `id uuid` PK (ADR-0006 r1) and `recorded_at` (ADR-0007 r9); these are not repeated.

### B.1 Platform: registry, documents, periods, permissions, outbox, audit, localization, clock

| Table | Status | Key columns | Keys / uniques | Relations | Source |
| --- | --- | --- | --- | --- | --- |
| `idempotency_record` (registry) | P | actor, scope (command type or `command_batch`), key, request hash, stored response, `company_id` | UQ (actor, scope, key) | — | ADR-0008 r16–r19; ADR-0017 r19 |
| `document` (documents) | D | `company_id`, `document_type`, `state`, `version`, `number`, `branch_id`, `reversal_of_id`, `correction_of_id`, `posted_at` | UQ (company, document_type, number); `reversal_of_id` unique | typed header shares `id`; → `branch`, → `document` (reversal/correction) | ADR-0009 r1, r13, r15, r18, r23 |
| `<header>_line` per type | P | `line_number` unique per document | — | → typed header | ADR-0009 r1 |
| `document_version` | D | `document_id`, `version`, `content`, `version_hash`, `actor_kind`, `actor_id`, `on_behalf_of_id`, `agent_run_id`, `origin_agent_run_id` | UQ (document_id, version) | → `document` | ADR-0009 r9; ADR-0017 r16 |
| `policy_decision` | P | `document_version_id`, outcome (allow, deny, approval required, human only) | — | → `document_version` | ADR-0009 r11 |
| `approval` | D | `document_version_id`, decision (`approved`/`rejected`), `reason`, `actor_kind`, `actor_id`, `on_behalf_of_id`, `decided_at` | immutable | → `document_version` | ADR-0009 r11 |
| `numbering_series` (documents) | D | `company_id`, `document_type`, `fiscal_year_id`, `branch_id`, `prefix`, `next_value`, `format` | UQ (company, type, fiscal_year, branch) NULLS NOT DISTINCT | → `fiscal_year`, `branch` | ADR-0009 r15 |
| Company numbering configuration per type (prefix, per-branch flag, format) | N (unnamed) | — | — | — | ADR-0009 r15; ADR-0016 r5 |
| `policy` (threshold table) | N | — | — | — | RG; spec 10 "built thin"; DEFERRED DS-28 |
| `fiscal_year` (periods, owner inferred) | D | `company_id`, `start_date`, `end_date`, `code` | exclusion on daterange per company | — | ADR-0007 r18–r22 |
| `posting_period` | D | `fiscal_year_id`, `number`, `kind` (`regular`/`special`), `start_date`, `end_date` | exclusion (regular only) | → `fiscal_year` | ADR-0012 r1; ADR-0007 r18 |
| `posting_period_area_state` | D | `posting_period_id`, `area` (general/inventory/receivable/payable), `state` (open/soft_locked/locked) | (period, area) | → `posting_period` | ADR-0012 r4 |
| `close_task` | D | company, posting period, `code`, `area`, `kind` (job/check/manual), `is_required`, `is_sequential`, `depends_on`, `state`, `entry_count_at_done`, completing actor, time, evidence | — | → `posting_period`; referenced by `journal_entry.close_task_id` | ADR-0012 r11–r16 |
| Company close checklist template | N (unnamed) | — | — | copied from package | ADR-0016 r7; ADR-0012 r11 |
| `user_account` (permissions, owner inferred) | P | `is_active`; sessions server-side | — | ← `employee_profile.user_account_id` | ADR-0017 r1–r2; ADR-0019 r3 |
| `integration_client` | P | `is_active`, token hash, expiry, companies, accountable human | — | — | ADR-0017 r1–r3, r13 |
| `role` | P | `company_id`, `code`, `name`, permissions | — | — | ADR-0017 r5 |
| `role_assignment` | P | user, role, company, record scope, field classes | — | → `user_account`, `role` | ADR-0017 r6, r9, r10 |
| `installation_role_assignment` | N | — | — | — | ADR-0017 r7 |
| `agent_type` | N | fixed tool list, permissions (declared) | — | — | ADR-0017 r1, r11; DEFERRED DS-32 |
| `agent_run` | N | trigger, model, prompt version, tool calls, tokens, cost, commands, `on_behalf_of` | — | ← `agent_run_id` on versions/events | spec 03 r7; ADR-0017 r1; DEFERRED DS-32 |
| `outbox_event` (outbox) | D | `company_id`, `event_type`, `schema_version`, `subject_table`, `subject_id`, `subject_sequence`, `payload`, actor context, `origin_agent_run_id`, `is_tainted`, `business_date`, `command_type`, `trace_id` | partitioned monthly by id range; no other unique | — | ADR-0013 r2 |
| `event_subject` | D | `subject_table`, `subject_id`, `last_sequence` | (subject_table, subject_id) | — | ADR-0013 r3 |
| `event_delivery` | D | `consumer`, `event_id`, subject columns, `company_id`, `state`, `attempts`, `next_attempt_at`, `locked_until`, `last_error` | UQ (consumer, event_id) | → `outbox_event` | ADR-0013 r6 |
| Consumer registry (name, event types, kind, queue, `is_paused`) | P (registry; table or code not stated) | — | — | — | ADR-0013 r6, r16 |
| `business_date_override` (clock) | P | company, date | — | → company | ADR-0007 r15 |
| Installation settings (`environment`, `group_currency`, `group_exchange_rate_source_id`, retention days, batch limit, session timeouts) | P (table not named) | — | — | — | ADR-0022 r9; ADR-0011 r6, r8; ADR-0008 r19, r21; ADR-0013 r15; ADR-0017 r2 |
| `regime_setting` (localization) | D | `localization_package`, `accounting_regime`, `key`, `value`, `effective_from`, basis | identity (package, regime, key, effective_from) | — | ADR-0016 r9 |
| Company regime option rows | P (unnamed) | company, key, choice, `effective_from` | — | — | ADR-0016 r11 |
| Audit record | N | actor, time, reason, approval, denials | never deleted | — | ADR-0012 r9; ADR-0017 r8; DEFERRED DS-36 |
| `derivation_trace` | N | source lines, rules applied | — | ← `journal_line`, `material_document_line`, `landed_cost_allocation` | Principle 6; RG; DEFERRED DS-09 step 3 spec |

### B.2 Ledger

| Table | Status | Key columns | Keys / uniques | Relations | Source |
| --- | --- | --- | --- | --- | --- |
| `system_account` (global) | D | catalog columns `code`, `parent_code`, `account_type`, `normal_balance`, `is_contra`, `is_bilateral`, `control_kind`, `is_postable`, `added_in`, `name`, `meaning` | uuid5 id; code unique | tree | ADR-0010 r1–r9; system-accounts.csv (110 rows) |
| `account` | D | `company_id`, `code`, `name`, `parent_id`, `is_postable`, `system_account_id`, `currency`, `has_posting`, `is_active` | (company, code) implied | → `system_account`, `currency` | ADR-0010 r10–r12 |
| `transaction_key` (global) | D | `code`, `name`, `determinants`, `required_system_accounts`, `required_control_kind`, `added_in`, `meaning` | uuid5 | — | ADR-0015 r1–r4; transaction-keys.csv (35 rows) |
| `account_determination` | D | `company_id`, `transaction_key_id`, `valuation_class_id`, `warehouse_id`, `item_group_id`, `partner_group_id`, `tax_code_id`, `currency`, `account_id` | UQ (company, key, all determinants) NULLS NOT DISTINCT | → key, account, determinants | ADR-0015 r9–r12 |
| `valuation_class` | D | `company_id`, `code`, `name`, `is_active` | — | ← product | ADR-0015 r6 |
| `item_group` | P | company data | — | ← product | ADR-0015 r7 |
| `partner_group` | N | default reconciliation accounts | — | ← partner | RG; ADR-0015 r11 |
| `journal_entry` | D | `company_id`, `document_id`, `posting_date`, `document_date`, `posting_period_id`, `fiscal_year_id`, `is_closing_entry`, `close_task_id`, `database_transaction_number`, `line_count` | UQ document_id | → document, period, fiscal_year, close_task | ADR-0014 r1; DS-06 SQL |
| `journal_line` | D | keys, `account_id`, `system_account_id`, `transaction_key_id`, `side`, `is_storno`, 3×(currency, amount), `company_applied_rate_id`, `group_applied_rate_id`, dimensions `branch_id`, `partner_id`, `item_id`, `warehouse_id`, `cost_center_id`, `project_id`, `salesperson_id`, `tax_code_id`, links `material_document_line_id`, `open_item_id`, `derivation_trace_id`, `description` | UQ (entry, line_number) | → most tables above | ADR-0014 r5–r12; DS-06 SQL |
| `account_period_balance` | D | (company, account, period, transaction_currency, is_closing_entry), turnovers and closing balances in 3 currencies | UQ on that tuple | → account, period | ADR-0014 r18; DS-06 SQL |
| `currency` (master_data per ADR-0022 r2) | D | `code`, `minor_unit`, `rounding_mode`, `is_active` | PK code used as FK | — | ADR-0011 r7; ADR-0006 r14, r17 |
| `exchange_rate_source` | D | `code`, `reference_currency`, `company_id` (null=public), publication | — | — | ADR-0011 r8 |
| `exchange_rate` | D | source, `from_currency`, `to_currency`, `unit`, `quote_kind`, `effective_date`, `version`, `rate` | UQ (source, from, to, kind, date, version) | → source | ADR-0011 r9 |
| `applied_rate` | D | `from_currency`, `to_currency`, `rate`, `origin`, selection date, `first_exchange_rate_id`, `second_exchange_rate_id` | — | → exchange_rate; ← journal_line | ADR-0011 r3 |
| Rate type configuration (lookup kinds, selection date, `max_rate_age_days`, tolerance) | P (regime settings) | — | — | — | ADR-0011 r11–r13 |
| `open_item` | N | kind (invoice, advance, credit) | — | ← `journal_line.open_item_id` | ADR-0010 r15; ADR-0014 r10; DEFERRED DS-25 |
| `general_journal`, `balance_transfer` (document types) | P (types named, fields not) | — | — | → document | ADR-0014 r3 |
| Revaluation documents, costing adjustment documents, closing entries | P (types described, not registered) | — | — | — | ADR-0011 r17–r20; ADR-0020 r12; ADR-0012 r18 |

### B.3 Master data

| Table | Status | Key columns | Keys / uniques | Relations | Source |
| --- | --- | --- | --- | --- | --- |
| `company` | P (columns scattered, never defined as a table) | `company_currency`, `time_zone`, `localization_package`, `accounting_regime`, `valuation_area_level`, `future_posting_periods`, `fiscal_year_lead_days`, `fiscal_calendar_owner`, default exchange rate source, routing switch | — | — | ADR-0011 r6, r8; ADR-0007 r12; ADR-0016 r2; ADR-0015 r8; ADR-0012 r3, r6; spec 17 |
| `branch` | N | code (used in numbering format) | — | ← document, journal_line | spec 07; ADR-0009 r15; DS-06 SQL |
| `cost_center`, `project` | N | — | — | ← journal_line | ADR-0014 r9 ("DS-20 defines") |
| `employee` | N, and **conflicting**: DS-06 SQL `salesperson_id REFERENCES employee (id)`, while ADR-0019 r3 makes employees partners with role `employee` | — | — | — | DS-06 SQL; ADR-0014 r9; ADR-0019 r3 |
| `product` | D | `company_id`, `code`, `name`, `product_type`, `is_active`, `is_sellable`, `is_purchasable`, `product_category_id`, `buyer_id`, `item_group_id`, `valuation_class_id`, `inventory_uom_id`, `purchase_uom_id`, `sales_uom_id`, `tracking`, `item_tax_group_id`, `price_control`, reserved `catch_weight_uom_id`, `is_inspection_required`, `removal_strategy`, `storage_condition_id`, `default_handling_unit_type_id`, `hs_code`, `country_of_origin` | UQ (company, code) | → category, partner (buyer), item_group, valuation_class, uom, item_tax_group, storage_condition, handling_unit_type | ADR-0018 r1, r3; ADR-0023 r3; ADR-0021 r13 |
| `item` | D | `product_id`, `company_id`, `code`, `is_active`, `variant_key`, dimensions + `dimension_uom_id`, `net_weight`, `gross_weight`, `weight_uom_id` | UQ (company, code); UQ (product, variant_key) | → product | ADR-0018 r2, r4, r7 |
| `variant_attribute`, `variant_attribute_value` | P | `code`, `name` | — | — | ADR-0018 r6 |
| `product_variant_attribute` | D | `product_id`, `variant_attribute_id`, `position` | — | — | ADR-0018 r6 |
| `item_variant_value` | D | `item_id`, `variant_attribute_id`, `variant_attribute_value_id` | one per attribute | — | ADR-0018 r6 |
| `uom` (core catalog + company rows) | D | `code`, `quantity_kind`, `decimal_places`, `company_id` (null core) | company codes start `x-` | — | ADR-0018 r8 |
| `uom_conversion` | D | `from_uom_id`, `to_uom_id`, `numerator`, `denominator` | — | → uom | ADR-0018 r8 |
| `product_uom` | D | product, uom, `numerator`, `denominator` | — | → product, uom | ADR-0018 r10 |
| `item_barcode` | D | `item_id`, `uom_id`, `barcode` | UQ (company, barcode) | → item, uom | ADR-0018 r14 |
| `classification_scheme`, `classification_value`, `product_classification` | D | scheme `code`, `name`, `is_hierarchical`, `is_protected`; value `code`, `name`, parent; link one value per scheme per product | — | — | ADR-0018 r15 |
| `product_category` | P | built-in hierarchy proposing defaults | — | ← product | ADR-0018 r15 |
| `data_translation` | D | `table_name`, `row_id`, `field`, `language`, `text` | — | polymorphic | ADR-0018 r17 |
| `item_tax_group`, `partner_tax_group` | N | — | — | ← product, partner | ADR-0018 r16; DEFERRED DS-23 |
| `partner` | D | `company_id`, `code`, `name`, `legal_name`, `partner_kind`, `tax_id`, `parent_partner_id`, `represents_company_id`, `country`, `partner_group_id`, `partner_tax_group_id`, `preferred_language`, `is_active`, `superseded_by_partner_id` | UQ (company, code) | → partner, company, partner_group, partner_tax_group | ADR-0019 r1, r19 |
| `partner_role` | D | `partner_id`, `role` (customer, supplier, employee), `is_active` | — | → partner | ADR-0019 r2 |
| `customer_profile` | D | `receivable_account_id`, `payment_term_id`, `credit_limit` + currency, `price_list_id`, `salesperson_id`, `currency`, `minimum_remaining_shelf_life_days` | per partner | → account, payment_term, price_list, partner | ADR-0019 r3; ADR-0023 r3 |
| `supplier_profile` | D | `payable_account_id`, `payment_term_id`, `buyer_id`, `currency` | per partner | → account, payment_term, partner | ADR-0019 r3 |
| `employee_profile` | D | `user_account_id`, `receivable_account_id` (advances) | per partner | → user_account, account | ADR-0019 r3 |
| `partner_address` | D | `kind`, lines, `subdivision_code`, postal code, country | — | → partner | ADR-0019 r5 |
| `partner_bank_account` | D | bank, account number, holder | — | → partner | ADR-0019 r5 |
| `partner_item` | D | `partner_id`, `item_id`, partner code, name, unit | UQ (partner, code) | → partner, item | ADR-0019 r6 |
| `partner_email_domain` | N | domains for matching | — | → partner | ADR-0019 r15 |
| `price_list` | N | per item | — | ← customer_profile | ADR-0018 "elsewhere"; ADR-0019 r3; DEFERRED DS-20 |
| `payment_term` | N | — | — | ← profiles | ADR-0019 r3; DEFERRED DS-25 |
| `warehouse` (master_data per ADR-0022 r2) | D | `company_id`, `code`, `name`, `kind` (physical/transit/goods_sent), `branch_id`, address, `is_active`, `valuation_warehouse_id`, `is_bin_managed`, `outbound_flow`, `default_receiving_bin_id`, `default_shipping_bin_id`, `is_handling_unit_managed`, removal default (implied), calendar assignment | — | → warehouse, branch, bin, working_calendar | ADR-0020 r1; ADR-0023 r1; ADR-0024 r4 |
| `storage_condition` | P | company data | — | ← product | ADR-0023 r3 |
| `handling_unit_type` | P | company data, tare weight, dimensions | — | ← product, handling_unit | ADR-0023 r6 |
| Tax ID lookup snapshot | N (unnamed) | dated snapshot with source | — | → partner | ADR-0019 r18 |

### B.4 CRM (owner inferred `crm`, ADR-0022 r2 lists the module; ADR-0019 does not assign tables)

| Table | Status | Key columns | Relations | Source |
| --- | --- | --- | --- | --- |
| `contact` | D | `partner_id`, `name`, `job_title`, `email`, `phone`, `preferred_language`, `is_active` (all personal) | → partner | ADR-0019 r8 |
| `processing_basis` | D | data subject, `purpose`, `basis`, `valid_from`, `ended_at`, evidence interaction | → contact/partner, interaction | ADR-0019 r9 |
| `data_subject_request` (document) | P | kind, data subject, requester details, state, due date | → document | ADR-0019 r10 |
| `personal_data_processing_log` | P | processing events (LLM sends, lookups, exports, erasures) | — | ADR-0019 r11 |
| `interaction` | D | `partner_id`, `contact_id`, `kind`, `direction`, `occurred_at`, `subject`, `source` (mailbox, UID, Message-ID), `sender_authentication`, `is_untrusted`, related document IDs | → partner, contact, mailbox, document | ADR-0019 r12 |
| `interaction_content` | P | body, attachments (personal) | → interaction | ADR-0019 r12 |
| `mailbox` | P | company, owner (human), connector, size limit | → user_account | ADR-0019 r14 |
| `partner_insight` | D | name, value, method, computed date | → partner | ADR-0019 r20 |
| `interaction_summary` | D | text, agent run, model, prompt version, `is_untrusted`, last editor | → interaction/partner, agent_run | ADR-0019 r20 |
| Attachment store | N, **owner unassigned** | — | — | ADR-0018 "elsewhere"; ADR-0019 r12 |

### B.5 Inventory (ADR-0022 r2: material documents, stock, costing, landed cost, warehouse management)

| Table | Status | Key columns | Keys / uniques | Relations | Source |
| --- | --- | --- | --- | --- | --- |
| `movement_type` (global) | D | `code`, `name`, `direction`, `value_source`, `costing_role`, `offset_transaction_key`, `needs_reference`, `sap_analog`, `added_in`, `meaning` | uuid5 | → transaction_key | ADR-0020 r4; movement-types.csv (13 rows) |
| `material_document` | D | `document_id` | UQ document_id | → document | ADR-0020 r3 |
| `material_document_line` | D | `line_number`, `item_id`, `warehouse_id`, `movement_type_id`, `direction`, `is_reversal`, `quantity`, `lot_id`/`serial_number_id`, `company_amount`, `valuation_warehouse_id`, `derivation_trace_id`, `bin_id`, `stock_status`, `handling_unit_id`, reserved `catch_weight_quantity` | — | → material_document, item, warehouse, movement_type, lot, serial, bin, handling_unit; ← journal_line | ADR-0020 r3; ADR-0023 r7 |
| `stock_quantity` | D | (company, item, warehouse, bin, lot or serial, `stock_status`, `handling_unit_id`), quantity | that key | written only by stock lock helper | ADR-0020 r8; ADR-0023 r4 |
| `stock_value` | D | (company, item, warehouse), value | that key; locked first | lock helper | ADR-0020 r8–r9 |
| `preliminary_price` | P | (item, valuation area, posting period), price | — | → item, warehouse, period | ADR-0020 r11 |
| `lot` | D | company, item, `code`, `expiry_date`, `manufacture_date` | — | → item | ADR-0020 r17 |
| `serial_number` | D | company, item, `code` | — | → item | ADR-0020 r17 |
| `stock_count` (document) + lines | P | counted qty per item, warehouse, bin, lot/serial, status; stored book qty | — | → document; posts count movements | ADR-0020 r18; ADR-0023 r18 |
| `landed_cost` (document) | D | company currency | — | → document | ADR-0021 r1 |
| `landed_cost_line` | D | `line_number`, `cost_type`, `amount`, `allocation_method`, `source_journal_line_id`, `item_id`, `tax_code_id` | — | → journal_line, item, tax_code | ADR-0021 r1–r2 |
| `landed_cost_target` | D | target material document line, `manual_amount` | — | → landed_cost_line, material_document_line | ADR-0021 r1, r3 |
| `landed_cost_allocation` | D | target, basis snapshot, exact share, amount, mode (`open`/`closed`), `derivation_trace_id` | — | → target | ADR-0021 r1, r5–r7 |
| `landed_cost_correction` (correction type) | P | signed differences per cost line and target | `correction_of_id` | → landed_cost | ADR-0021 r9 |
| `customs_declaration` (document, owner not stated) | P | number, date, supplier, covered POs/receipts, `transaction_currency`; lines: item, quantity, unit, `hs_code`, `country_of_origin`, customs value, customs rate | — | → partner, POs/receipts | ADR-0021 r10 |
| `customs_declaration_tax` | P | tax code, base, assessed amount, recomputed amount | per declaration line | → tax_code | ADR-0021 r10 |
| `customs_declaration_amendment` (correction type) | N | — | `correction_of_id` | — | ADR-0021 r11 |
| `zone` | D | `warehouse_id`, `code`, `name` | — | → warehouse | ADR-0023 r2 |
| `bin` | D | `warehouse_id`, `zone_id`, `code`, `barcode`, `bin_type`, `pick_sequence`, capacities, mix/block flags, `is_active` | code unique in warehouse; barcode unique in company | → warehouse, zone | ADR-0023 r2 |
| `handling_unit` | D | `code`, `barcode`, `handling_unit_type_id`, `parent_handling_unit_id`, `warehouse_id`, `bin_id`, `state` (open/closed/shipped) | barcode unique in company | → type, self, warehouse, bin | ADR-0023 r6 |
| `warehouse_movement` | D | item, lot/serial, quantity, from/to bin, status, handling unit, `business_date`, `warehouse_task_id` or writing command | append-only | → warehouse_task | ADR-0023 r8 |
| `warehouse_task` | P | type (putaway, pick, replenishment, move, status_change, count), state (open, assigned, in_progress, confirmed, canceled), item, lot, handling unit, source bin, proposed target, quantity, demand line unit, assignee, `shortage_reason` | — | → demand line, bin, handling_unit | RG; ADR-0023 r11, r14, r15, r20 |
| `putaway_rule` | P | warehouse, `position` (unique), match (item, category, storage condition, status, HU type), target (zone/bin type), method | UQ position per warehouse | → warehouse | ADR-0023 r12 |
| `bin_item` | P | item, warehouse, bin, `minimum_quantity`, `maximum_quantity` | one per item per warehouse | → item, bin | ADR-0023 r17 |
| `stock_reservation` | D | demand line, item, warehouse, quantity, lot, `picked_quantity`, `fulfilled_quantity`, `state` | — | → demand line, item, warehouse, lot | ADR-0023 r13 |
| `pick_batch` | N (second slice) | — | — | — | RG; ADR-0023 r16 |
| Cycle-count plan | N (second slice) | — | — | — | ADR-0023 r18 |
| `demand_supply_line` (read model) | D | item, warehouse, `direction`, open quantity, `requested_date`, `ordered_date`, `source_kind`, source document line, `origin_planned_order_id`, `closed_reason` | — | → document line, planned_order | ADR-0024 r8 |
| `replenishment_request` (+ lines) | P | one line per planned order with `origin_planned_order_id` | — | → planned_order | ADR-0024 r22 |
| Transfer (posting document type) | P | lines `transfer_out`/`transfer_in` | reversible internal | → material_document | ADR-0020 r4, r6, r7 |
| Transfer order (non-posting demand document) | N, **owner not stated** | — | — | ← stock_reservation, demand_supply_line | RG "Demand line"; ADR-0023 r13; ADR-0024 r8, r22 |

### B.6 Planning (module `planning`; supplier tables' owner not stated)

| Table | Status | Key columns | Keys | Source |
| --- | --- | --- | --- | --- |
| `item_warehouse_planning` | D | `planning_method`, `replenishment_source`, route, `reorder_point`, min/max, safety stock fields, lot size fields, `firm_horizon_days`, `receiving_days` | (item, warehouse) | ADR-0024 r1 |
| `supplier_item` | D | (company, supplier partner, item), `supplier_processing_days`, `transit_days`, `minimum_order_quantity`, `order_multiple`, `is_preferred`, `start_date`, `end_date`, optional partner_item ref | key as stated | ADR-0024 r2 |
| `supplier_purchasing_term` | D | supplier partner, `minimum_order_amount` + currency, `container_volume`, `container_weight`, `order_cycle_days` | one per supplier | ADR-0024 r2 |
| `supplier_item_lead_time` | P | (supplier, item), mean, standard deviation | — | ADR-0024 r2 |
| `transfer_route` | D | source warehouse, destination warehouse, `lead_time_days` | no cycles | ADR-0024 r3 |
| `working_calendar` | P | working weekdays, holidays; assigned to warehouses and suppliers | — | ADR-0024 r4 |
| `planning_setting` | D | `planning_owner_id`, `planning_horizon_days`, `forecast_consumption_days`, `conversion_window_days`, `backtest_weeks` | per company | ADR-0024 r7 |
| Company planning state row (run lock) | N | — | — | ADR-0024 r17 |
| `sales_history` | D | item, warehouse, ISO week, quantity | — | ADR-0024 r10 |
| `demand_event` | P | code, date window per year | — | ADR-0024 r10 |
| `forecast`, `forecast_run` | N (glossary only) | weekly spread to days | — | RG; ADR-0024 r11 |
| `forecast_adjustment` | D | item, warehouse, `start_date`, `end_date`, quantity or factor, author, reason | — | ADR-0024 r12 |
| `planning_run` | P | counts, `input_hash`, `output_hash`, forecast run used | — | ADR-0024 r11, r17 |
| `planned_order` | D | item, warehouse, `order_type`, source, `need_date`, `sequence`, quantity, `release_date`, `state` | business key | ADR-0024 r18 |
| `pegging` | D | planned order, `pegging_target_kind`, target reference, quantity | sums to quantity (INV-60) | ADR-0024 r20 |
| `action_message`, planning exception | P | kind, projected effect | — | ADR-0024 r21 |

### B.7 Commercial, cash, tax, e-invoice, reports (tables named only or not at all)

| Table / document type | Status | Named in | Owner |
| --- | --- | --- | --- |
| `quotation`, `sales_order`, `delivery`, `sales_invoice`, `purchase_request`, `purchase_order`, `goods_receipt`, `purchase_invoice`, purchase cost invoice | N (types named; fields DS-22) | spec 11 step 5; ADR-0009 r1, r6, r19; ADR-0004 r4 (`sales_order`) | DEFERRED DS-22 |
| `sales_return`, `purchase_return`, `credit_note`, `debit_note`, adjustment/replacement invoice | N | ADR-0009 r23 | DEFERRED DS-22, DS-24 |
| Cash receipt, cash payment, cash count, bank statement / bank line, payment allocation, netting, advance, currency exchange document | N | spec 08; spec 11 step 6; Principle 1 (`MatchBankLine`); ADR-0011 r4 | DEFERRED DS-25 |
| `tax_code`, tax rates, tax matrix, VAT return mapping | N | ADR-0014 r9; ADR-0018 r16; ADR-0021 r10 | DEFERRED DS-23 |
| E-invoice form/symbol/number tables, submission intents, incoming invoice intake | N | ADR-0009 r14, r17; ADR-0013 r10 | DEFERRED DS-24 |
| Report definitions (B01–B03, books) | N | ADR-0016 r5 | DEFERRED DS-26 |
| Print templates, PDF cache by hash | N | ADR-0002 perf 1 | DEFERRED DS-27 |
| `work_item` | N | RG; Principle 8 | DEFERRED DS-29 |

### B.8 Relationship skeleton (from the rules above)

```
document 1─1 <typed header> 1─n <header>_line
document 1─n document_version 1─n policy_decision / approval
document 0..1─1 journal_entry 1─n journal_line ─> account ─> system_account
document 0..1─1 material_document 1─n material_document_line <─0..n journal_line
journal_line ─> applied_rate ─> exchange_rate ─> exchange_rate_source
journal_line ─> open_item (undefined), derivation_trace (undefined), transaction_key
material_document_line ─> movement_type ─> transaction_key (offset)
stock_value (item, warehouse)  ⇐ lock helper ⇒ stock_quantity (item, wh, bin, lot/serial, status, HU)
warehouse_movement ─> warehouse_task ─> stock_reservation ─> demand line (sales/transfer order line)
landed_cost_line ─> journal_line (purchase_cost_clearing source); landed_cost_target ─> material_document_line
planned_order 1─n pegging; planned_order ─> replenishment_request line ─> draft documents (origin_planned_order_id)
product 1─n item; item ─> partner_item, item_barcode, supplier_item, item_warehouse_planning
partner 1─n partner_role; partner 1─1 customer_/supplier_/employee_profile; partner 1─n contact, interaction
posting_period 1─n posting_period_area_state; posting_period 1─n close_task
```

---

## C. Dataflow per business flow

Columns: **Actor** (H human, A agent, S system job/consumer, I integration). **Status** per section 0.

### C.1 CPQ: request intake (email) → quotation → order

| # | Actor | Command / mechanism | Document and state | Tables written | Journal / stock | Events → consumers | Agent proposes / human or policy approves | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | I (intake job, `jobs` queue, on behalf of mailbox owner) | Scheduled fetch; records each message by command (name not given), dedup by mailbox+UID | `interaction` (inbound, `is_untrusted`) | `interaction`, `interaction_content` | none | interaction event (name not given) | — | ADR-0019 r12, r14; ADR-0017 r12 | DESIGNED (connector DEFERRED DS-24 / DS-35) |
| 2 | S (deterministic) | Matching: reply thread → contact email → partner domain, all requiring sender authentication | sets `partner_id` or none | `interaction` (match recorded; append-only correction rule r12) | none | — | unmatched → work item; agent may propose partner, human confirms | ADR-0019 r15 | DESIGNED; work item DEFERRED DS-29 |
| 3 | S consumer → work item; A run starts from work item | Agent wake-up consumer creates work item; run on behalf of intake owner, tainted | — | `work_item`, `agent_run` | none | tainted downstream | run limited to matched partner's data (spec 03 r1; ADR-0019 r15) | ADR-0013 r12; ADR-0017 r12 | DEFERRED DS-29, DS-32 |
| 4 | A (LLM only for free text) | Understand request; map item descriptions to item codes (stored mappings → fuzzy → LLM) | proposal stored with run | proposals; `interaction_summary` | none | — | mapping becomes `partner_item` row only after approval | spec 14 table; ADR-0019 r6, r16 | DEFERRED DS-34 (quotation workflow); mapping storage DESIGNED |
| 5 | A via queries | Item/price lookup: price list, purchase history, FX rate; stock via `GetAvailableToPromise`/`GetStockBalance`; margin, credit limit check | — | none | none | — | deterministic functions only (Principle 13) | spec 13 "Quotation"; spec 14; ADR-0023 r13, r23; ADR-0011 r14 | Price list DEFERRED DS-20; pricing rules DEFERRED DS-22; stock queries DESIGNED; query layer DEFERRED DS-33 |
| 6 | A | `CreateQuotation` (generated per ADR-0009 r2) | quotation `draft` v1 (non-posting) | `document`, quotation header/lines, `document_version` (with `agent_run_id`) | none | `QuotationCreated` (derived by ADR-0004 r22; type not registered) tainted | draft only | ADR-0009 r2, r6, r9 | Lifecycle DESIGNED; quotation type DEFERRED DS-22 |
| 7 | — | Pricing: price list, discounts, promotions, line rounding | quotation lines | — | none | — | deterministic (Principle 13) | ADR-0006 r18 (line rounding); DS-22 discounts/promotions | DEFERRED DS-20 (price lists), DS-22 (discounts, promotions); promotional goods tax treatment DEFERRED DS-23/DS-24 (spec 08) |
| 8 | H or A | `SubmitQuotation` → policy (`policy_decision`) | `pending_approval` or `approved` | `policy_decision` | none | `QuotationSubmitted` | Conditions (discount, margin, below cost, outside price list, credit limit) are approval-procedure conditions (spec 07); policy table DS-28; EC-22 (below cost) outcome undecided | ADR-0009 r11; spec 07 | Mechanism DESIGNED; policy DEFERRED DS-28 (stub allows all, ADR-0017 r17); EC-21/EC-22 FLAGGED (OQ) |
| 9 | H only | `ApproveQuotation` | `approved`; numbered at first approval (interim) | `approval`, `document`, `numbering_series` | none | `QuotationApproved` | hard floor: approver ≠ human the agent acted for (mailbox owner) | ADR-0017 r15–r16; ADR-0009 r8 | DESIGNED (numbering FLAGGED) |
| 10 | A drafts, H sends | Outgoing message to customer | outbound draft; send intent | outbound `interaction`; intent | none | intent event → `external` consumer (email) | draft by default; tainted run never auto-sends; recipients only stored contacts; consent check `consent_missing` | ADR-0019 r9, r17; ADR-0013 r10–r11; spec 13 p5 | DESIGNED (connector DEFERRED DS-24) |
| 11 | H | Follow-up reminders | — | — | — | — | agent drafts follow-ups | spec 13 stage table | DEFERRED DS-34 (not in Phase 1 list explicitly) |
| 12 | H or A | Quotation → sales order (`CreateSalesOrder` from quotation) | sales order `draft`; quotation `closed` | — | none | — | — | spec 09 "Quotation → order"; ADR-0009 r6 | **Conversion mechanism DEFERRED DS-22** (no rule on copying, closing the quotation, or reference) |

### C.2 O2C: sales order → delivery → invoice → receivable → payment → returns

| # | Actor | Command | Document and state | Tables written | Journal / stock | Events → consumers | Agent / approval | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | H/A | `CreateSalesOrder`, `UpdateSalesOrder` | sales order `draft` (non-posting) | `document`, header/lines (entered qty + inventory qty, ADR-0018 r11), `document_version` | none | `SalesOrderCreated/Updated` | agent drafts | ADR-0009 r6, r9; ADR-0018 r11 | Lifecycle DESIGNED; type DEFERRED DS-22 |
| 2 | S (deterministic) | Credit check: "credit limit including undelivered orders" on `customer_profile.credit_limit` | — | — | — | — | outcome over limit undecided: reject / warn / approval (EC-21) | spec 08; ADR-0019 r3; spec 07 approval conditions | DEFERRED DS-22, DS-28; FLAGGED (OQ EC-21, ADR-0005 item 11 example) |
| 3 | H/A → policy | `SubmitSalesOrder`, `ApproveSalesOrder` | `approved` = order in force; numbered (interim) | `policy_decision`, `approval`, `numbering_series` | none | `SalesOrderSubmitted/Approved` | human approves; SoD | ADR-0009 r6, r8, r11 | DESIGNED mechanism; DEFERRED DS-28 thresholds |
| 4 | S (inside the approving/order command) | `inventory.contract.create_stock_reservation` | `stock_reservation` `open` | `stock_reservation` (takes `stock_value` lock) | no stock change | `StockReservationCreated` (emitted by document command) | rules FLAGGED: no overbooking, FCFS, newest canceled | ADR-0023 r13; OQ reservations | Core DESIGNED; when the document calls it DEFERRED DS-22 |
| 5 | S | `demand_supply_line` write (demand) | — | `demand_supply_line` | none | — | which states count FLAGGED | ADR-0024 r8 | DESIGNED (interface name and call DEFERRED DS-22) |
| 6 | H/S | `RunPickRelease` (per demand document) | pick `warehouse_task`s `open` | `warehouse_task`; replenishment task if pick face < min | none (proposals unhashed) | `WarehouseTaskCreated` | — | ADR-0023 r14, r17 | DESIGNED (plain warehouses: no tasks, r16) |
| 7 | H (scan, PWA or desktop/paper) | `AssignWarehouseTask`, `StartWarehouseTask`, `ConfirmWarehouseTask` | task `confirmed`; goods moved to non-pickable shipping/staging bin | `warehouse_movement`, `stock_quantity`, reservation `picked_quantity` | quantity moves inside warehouse; no journal | `WarehouseTaskConfirmed` (shortage flag) | short pick → count task + exception (work item from step 5); after short pick FLAGGED: ship and backorder | ADR-0023 r15, r21; OQ short pick | DESIGNED; PWA DEFERRED DS-31; printing DEFERRED DS-27 |
| 8 | H | `PackHandlingUnit` (staged flow, second slice) | HU `closed` | `handling_unit`, `warehouse_movement` | none | — | — | ADR-0023 r6, r16 | DESIGNED (second slice) |
| 9 | H | `CreateDelivery` from confirmed picks; `SubmitDelivery`/approve if policy | delivery `draft`/`approved` (posting type) | `document`, delivery header/lines (lots, serials, bins, HUs) | none yet | `DeliveryCreated` | — | ADR-0023 r16; ADR-0009 r4 | Mechanism DESIGNED; delivery type fields DEFERRED DS-22 |
| 10 | H | `PostDelivery` | delivery `posted`, numbered | `material_document(_line)` `sales_issue` (or `transfer_out` to `goods_sent`), `stock_quantity`, `stock_value`, `journal_entry/line`, reservation `fulfilled`, HU `shipped`, `demand_supply_line` closed | Stock out at preliminary price (`revalued_issue`); Dr `cost_of_goods_sold` key (valuation class, warehouse, item group) / Cr `inventory_posting`; negative stock check | `DeliveryPosted` → consumers not named | value and ownership change only here | ADR-0020 r3–r4, r9–r11; ADR-0023 r16; movement-types.csv | Stock/journal DESIGNED; delivery document DEFERRED DS-22 |
| 11 | H (agents may draft) | `CreateSalesInvoice` → `PostSalesInvoice` | sales invoice `posted`; `is_approval_hold_allowed: false`; if policy needs approval → human only (FLAGGED) | `document`, invoice tables, `journal_entry/line`, `open_item` | Dr `receivable_reconciliation` (partner's account, open item) / Cr `revenue_posting` (item group) / Cr `output_tax` (tax code) | `SalesInvoicePosted` → e-invoice consumer | invoice timing = ownership transfer; approval may not delay issuance | ADR-0009 r12; ADR-0015 r11; transaction-keys.csv; spec 08 | Keys DESIGNED; invoice document DEFERRED DS-22; tax amounts DEFERRED DS-23; open item DEFERRED DS-25 |
| 12 | S → I | E-invoice issuance: transactional consumer records submission intent by command; `external` consumer calls provider (BKAV), records outcome; number/symbol in own tables | e-invoice data stored after posting | e-invoice tables (undefined) | none | intent event, outcome event; held delivery → work item | — | ADR-0013 r8, r10; ADR-0009 r14, r17 | Pattern DESIGNED; adapter DEFERRED DS-24 |
| 13 | — | Receivable: open item, payment terms, due date | `open_item` | — | — | — | — | ADR-0010 r15; ADR-0019 r3 | DEFERRED DS-25 |
| 14 | H (A drafts via bank matching) | Bank statement import, `MatchBankLine`, cash/bank receipt, payment allocation | payment document `posted` | bank lines, payment, open item matching | Dr cash/bank (account from master data, no key) / Cr receivable open item; realized FX via `fx_gain/loss_realized` keys; payment discounts via `payment_discount_given` | — | high-confidence deterministic match may auto-post after shadow mode, never if LLM contributed | ADR-0011 r15; ADR-0015 r5; spec 14; spec 03 r1 | DEFERRED DS-25, DS-34 (bank matching); FX book rate rules FLAGGED (OQ) |
| 15 | H/A drafts; H posts | `CreateSalesReturn` from posted delivery/invoice (`correction_of_id`); `PostSalesReturn` `human_only` interim | `sales_return` `posted` | material doc `sales_return_receipt` into `returns` bin, `blocked`; journal | stock in at regime value (interim: original issue cost), Dr inventory / Cr `cost_of_goods_sold` offset; revenue side via `revenue_deduction_return` key | `SalesReturnPosted` | disposition task: restock (putaway) / quality / draft scrap | ADR-0009 r23; ADR-0020 r5; ADR-0023 r7, r19 | Mechanism DESIGNED; return cost FLAGGED (OQ); document DEFERRED DS-22; EC-20 undecided |
| 16 | H | Credit note / adjustment or replacement e-invoice | correction document | — | revenue deductions, output tax reversal | — | — | ADR-0009 r19, r23; spec 08 | DEFERRED DS-22, DS-23, DS-24 |
| 17 | S (close) | Period-end costing revalues sales issues | costing adjustment document | journal (value-only), derivation trace | COGS adjusted with `cost_of_goods_sold` offset | `<Job>Completed` | human runs close task | ADR-0020 r12 | DESIGNED (algorithm spec DEFERRED DS-09 step 3) |

### C.3 Demand planning

| # | Actor | Command | State change | Tables | Journal / stock | Events → consumers | Approval | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | H (A proposes with approval) | Maintain parameters, supplier terms, routes, calendars, settings (commands not named) | master data | `item_warehouse_planning`, `supplier_item`, `supplier_purchasing_term`, `transfer_route`, `working_calendar`, `planning_setting` | none | — | agent changes need approval; cycle check `planning_network_cycle` | ADR-0024 r1–r7 | DESIGNED (phase is the author's: OQ DS-43) |
| 2 | S (DS-22 documents) | Documents write `demand_supply_line` through posting interfaces | open lines | `demand_supply_line` | none | — | what counts FLAGGED | ADR-0024 r8 | DESIGNED; writes DEFERRED DS-22 |
| 3 | H | `ImportSalesHistory` (DS-21 batch) | — | `sales_history` | none | — | — | ADR-0024 r10 | DESIGNED; format DEFERRED DS-21 |
| 4 | S (daily) or H | `RunForecast` (long job, internal caller, `planning_owner_id`) | forecast run | `forecast`, `forecast_run`, `supplier_item_lead_time` | none | `ForecastCompleted` | — | ADR-0024 r10–r11, r17 | DESIGNED (tables N/P) |
| 5 | H (A proposes) | Forecast adjustment (command not named) | adjustment recorded | `forecast_adjustment` | none | — | human approval; tainted proposals never policy-approved; policy approval of untainted FLAGGED | ADR-0024 r12 | DESIGNED |
| 6 | S or H | `RunPlanning` (regenerative; lock on planning state row) | planned orders proposed/updated/canceled by business key | `planning_run`, `planned_order`, `pegging`, `action_message`, exceptions | none (results unhashed) | `PlanningCompleted` → `planning_work_items` consumer (one work item per buyer) | — | ADR-0024 r13–r21 | DESIGNED; work item DEFERRED DS-29 |
| 7 | H | `FirmPlannedOrder`, `UpdatePlannedOrder`, `CancelPlannedOrder` | `firmed`/`canceled` | `planned_order` | none | `PlannedOrderFirmed` | — | ADR-0024 r19 | DESIGNED |
| 8 | H (policy auto-convert OQ) | `ConvertPlannedOrder` → `inventory.contract.request_replenishment` | `converted` | `planned_order`, `replenishment_request` | none | `PlannedOrderConverted`; `ReplenishmentRequested` → `purchasing` consumer | auto-conversion under threshold FLAGGED (DS-28) | ADR-0024 r22 | DESIGNED |
| 9 | S (purchasing consumer, actor system on behalf of converter) | Draft purchase requests grouped by supplier/warehouse/window (interim target FLAGGED); `inventory` creates draft transfer orders | drafts with `origin_planned_order_id` | purchase request / transfer order tables | none | document events | drafts follow own approval (DS-28); sending to supplier separate approved step | ADR-0024 r22 | Hand-over DESIGNED; purchase request DEFERRED DS-22; **transfer order document MISSING owner** |
| 10 | S | Exceptions (`shortage_inside_lead_time`, `stock_expiring`, …) and action messages | — | exception rows, work items | none | — | buyer reviews | ADR-0024 r21 | DESIGNED |
| 11 | A | Planning agent: explain, consolidate, propose parameter/lead-time/forecast changes | drafts | — | — | — | approval-bound | ADR-0024 r23 | DEFERRED DS-34 |

### C.4 P2P: purchase request → PO → goods receipt (incl. import) → supplier invoice → GR/IR → payment

| # | Actor | Command | Document and state | Tables | Journal / stock | Events → consumers | Agent / approval | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | H, S (planning) | `CreatePurchaseRequest` | non-posting `draft` → `approved` | document tables; `demand_supply_line` (supply) | none | `PurchaseRequestCreated` | DS-28 | spec 09; ADR-0024 r8, r22 | DEFERRED DS-22 |
| 2 | H/A | `CreatePurchaseOrder` (from request; request line open qty falls) | PO `approved` = in force | document tables; `demand_supply_line` | none | `PurchaseOrderApproved` | approval DS-28; sending to supplier: draft, human sends | Principle 1; ADR-0024 r8, r22; spec 14 | DEFERRED DS-22 |
| 3 | H (PWA from step 9) | `CreateGoodsReceipt`, `PostGoodsReceipt` | goods receipt `posted` | `material_document(_line)` `purchase_receipt` (receiving bin, `quality_inspection` if required), stock tables, journal; putaway task; `demand_supply_line` closed | Dr `inventory_posting` (or `inventory_in_transit_posting` for transit) / Cr `gr_ir_clearing`; value from the order | `GoodsReceiptPosted`; `WarehouseTaskCreated` | — | movement-types.csv; ADR-0020 r3–r4; ADR-0021 r12; ADR-0023 r7, r11 | Stock/journal DESIGNED; document DEFERRED DS-22; rate for import receipts FLAGGED (OQ) |
| 4 | H | Putaway (`ConfirmWarehouseTask`), quality release (`status_change` task) | stock to storage bin, `available` | `warehouse_movement`, `stock_quantity` | none | `WarehouseTaskConfirmed` | — | ADR-0023 r11–r12 | DESIGNED |
| 5 | H (agent may draft) | `CreateCustomsDeclaration`, post | `customs_declaration` `posted` (not reversible; amendment corrects) | declaration, `customs_declaration_tax`, journal | Cr tax payables via `import_export_duty`, `special_consumption_tax`, `import_tax`; Dr `purchase_cost_clearing` (capitalize) or `input_tax` (recoverable); customs rate only for tax bases | posted event | proposes a `landed_cost` per line; `customs_assessment_differs` check result | ADR-0021 r10–r11 | DESIGNED; `import_treatment` FLAGGED; tax codes DEFERRED DS-23; document fields partly DEFERRED DS-22 |
| 6 | H | Supplier freight/insurance/handling invoice | purchase cost invoice `posted` | journal, payable open item | Dr `purchase_cost_clearing` / Cr payable | — | — | ADR-0021 r12 | DEFERRED DS-22 (posting target DESIGNED) |
| 7 | H (system proposes) | `CreateLandedCost` / `PostLandedCost` | `landed_cost` `posted`; mode open/closed per target period | `landed_cost(_line/_target/_allocation)`, value-only journal lines, `stock_value`, derivation trace | open: Dr inventory key of target warehouse / Cr source clearing account; closed: consumer split (FLAGGED `consumer_split`) or `stock_coverage` | posted event | earlier-unlocked case FLAGGED; reversibility FLAGGED | ADR-0021 r1–r9 | DESIGNED (logic spec DEFERRED step 3) |
| 8 | A (purchase invoice workflow) or H | Incoming e-invoice intake (provider/T-VAN/mailbox): parse XML, signature, status, tax ID, map lines via `partner_item`, three-way match | purchase invoice `draft` (agent) | intake records, document tables | none | — | LLM suggests item for unmapped lines; approved mapping stored; human confirms before posting | spec 14; ADR-0019 r6 | DEFERRED DS-24, DS-34 |
| 9 | H (policy) | `PostPurchaseInvoice` | `posted` | journal, payable open item | Dr `gr_ir_clearing` / Dr `input_tax` / Cr `payable_reconciliation`; difference via `price_difference` key: to price difference account, or to `purchase_cost_clearing` + auto `landed_cost` (`price_difference` type) in same batch | posted event | three-way match tolerances; FX difference receipt vs invoice FLAGGED (OQ) | ADR-0021 r12; ADR-0015 r4; ADR-0011 r12 (invoice rate) | Price-difference path DESIGNED; matching and tolerances DEFERRED DS-22; tax DEFERRED DS-23 |
| 10 | — | GR/IR clearing analysis / clearing of residual GR/IR balances | — | — | — | — | — | ADR-0010 r5 (`gr_ir` control kind); spec 05 | DEFERRED DS-22; **no INV-xx for `gr_ir` control kind in invariants.csv 0.1.0** |
| 11 | H | Purchase return (correction of goods receipt) | `purchase_return` | material doc `purchase_return`, journal | out at regime value (interim: document value, negative receipt); offset `gr_ir_clearing` | — | landed-cost share on return FLAGGED | ADR-0020 r5; ADR-0021 r16 | DESIGNED core; DEFERRED DS-22 |
| 12 | H | Supplier payment; tax payments to state (no partner) | payment `posted` | open items | Dr payable / Cr bank; realized FX; payment discount received | — | agents never send money; posting above threshold approval | ADR-0019 r2; ADR-0011 r15; spec 14 | DEFERRED DS-25 |

### C.5 End-to-end information flow (inputs → outputs)

| Stage | Mechanism | Owner | Status |
| --- | --- | --- | --- |
| Input: email | Mailbox intake job → untrusted `interaction` → deterministic match → work item → tainted agent run | ADR-0019 r12–r16; ADR-0013 r11–r12 | DESIGNED (connector DEFERRED DS-24/DS-35) |
| Input: e-invoice XML (incoming) | Provider/T-VAN/mailbox; parse, verify, map | spec 08, 14 | DEFERRED DS-24, DS-34 |
| Input: bank files | `BankStatementReader` package code; 2–3 bank formats; generic CSV in simulator | ADR-0016 r17; DS-17 r20 | DEFERRED DS-25 |
| Input: exchange rates | `ExchangeRateFetcher` jobs per public source; manual rates into company source | ADR-0011 r8 | DESIGNED (fetchers DEFERRED DS-19) |
| Input: migration files | Excel template / reader → simulated `command_batch` | spec 15; ADR-0008 r20 | DEFERRED DS-21, DS-34, DS-40 |
| Input: user/agent/integration commands | REST/MCP → dispatcher (permission → visibility → human_only → policy → handler) → simulate/execute | ADR-0008 | DESIGNED |
| Processing: documents | `document` + versions + approvals + numbering | ADR-0009 | DESIGNED |
| Processing: ledger | `ledger.contract.write_journal_entry`, account determination, applied rates, triggers | ADR-0014, 0015, 0011 | DESIGNED |
| Processing: material ledger | `inventory.contract.move_stock`, stock lock helper, movement types | ADR-0020, 0023 | DESIGNED |
| Processing: events | outbox → deliveries → consumers (commands) / integration intents | ADR-0013 | DESIGNED |
| Read models (sync) | `stock_quantity`, `stock_value` (posting tx), `demand_supply_line` (document tx), `event_subject` | ADR-0020 r8; ADR-0024 r8 | DESIGNED |
| Read models (at lock) | `account_period_balance` written when general area locked | ADR-0014 r18 | DESIGNED |
| Read models (views) | AR/AP subledgers and inventory value as views over `journal_line` | ADR-0014 r17 | DESIGNED concept; views DEFERRED DS-33 |
| "State explicitly which read models update sync/async" | spec 07 requirement | spec 07 | Partially met in ADRs above; no consolidated list (**MISSING** as a deliverable) |
| Output: core queries | `GetTrialBalance`, `ListJournalLine`, `GetStockBalance`, `GetAvailableToPromise`, `GetProjectedAvailability`, `GetExchangeRate`, `GetAccountDetermination`, `ListPartnerTimeline`, `ListRegimeSetting` … | DS-16 r28; ADRs | Named; schemas per module |
| Output: semantic views, MCP resources, agent Q&A | read-only role, time limits | spec 02 P7; spec 17 "Data Q&A" seat | DEFERRED DS-33, DS-32 |
| Output: statutory books, B01/B02/B03 | report definitions in package over operational accounts | ADR-0010 r8, r14; ADR-0016 r5 | DEFERRED DS-26 |
| Output: management reports | system accounts | ADR-0010 r14 | **MISSING** (no DS item for management/BI reporting; OQ "management reporting and BI" partner question) |
| Output: e-invoices | intent consumer → `EInvoiceAdapter` (BKAV) | ADR-0013 r10 | DEFERRED DS-24 |
| Output: tax return 01/GTGT XML | export validated against XSD, filed by the customer | spec 08; RB step 7 | DEFERRED DS-23 |
| Output: print/PDF | Jinja2 → WeasyPrint in `pdf` queue, stored by version+template hash | ADR-0002 perf 1 | DEFERRED DS-27 |
| Output: emails/messages | draft → human send → intent consumer | ADR-0019 r17 | DESIGNED (connectors DEFERRED DS-24) |
| Output: data export ("what if we want to leave") | full export | spec 15; RB go-live | **MISSING** (no DS item owns export format; DS-40 covers cut-over only) |
| Output: audit trail | audit records, never deleted | ADR-0012 r9; ADR-0017 r8 | DEFERRED DS-36 |

### C.6 Goods flow in and out

| # | Movement | Mechanism | Journal effect | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Purchase receipt | `purchase_receipt`, value from document; receiving bin; QI status if required; putaway task | Dr inventory key / Cr GR/IR | ADR-0020 r4; ADR-0023 r7, r11 | DESIGNED |
| 2 | Other receipt | `other_receipt`, document value | Cr `other_receipt_offset` | ADR-0020 r4 | DESIGNED |
| 3 | Opening balance | `opening_balance` to final bin (DS-21) | Cr `opening_balance` key → `opening_balance_clearing` | ADR-0020 r4; ADR-0023 r7 | DESIGNED (format DEFERRED DS-21) |
| 4 | Putaway | Rule table (`fixed_bin`, `nearest_free`; second slice `consolidate`, `empty_bin`), capacity and mix checks; `GetPutawayPreview` | none | ADR-0023 r12 | DESIGNED |
| 5 | Stock statuses | `available`, `quality_inspection`, `blocked`; `status_change` tasks; no value | none | ADR-0023 r4, r11 | DESIGNED; statutory presentation OQ |
| 6 | Transfers (same/other valuation area) | `transfer_out` at preliminary price, `transfer_in` at issuing value, both journal lines even on same account | inventory to inventory; revalued at period end | ADR-0020 r6 | DESIGNED |
| 7 | Transit | Two-step transfer through `transit` warehouse; HU keeps identity; `inventory_in_transit_posting` | as transfer | ADR-0020 r1; ADR-0023 r7 | DESIGNED |
| 8 | Goods sent | `transfer_out` to `goods_sent`, later `sales_issue` from it | `inventory_goods_sent_posting` | ADR-0020 r1, r4 | DESIGNED; triggering commercial document DEFERRED DS-22 |
| 9 | Reservation, pick, pack, ship | As C.2 steps 4–10 | at `PostDelivery` | ADR-0023 r13–r16 | DESIGNED |
| 10 | Replenishment of pick faces | `bin_item` min/max; trigger at pick creation; daily job second slice | none | ADR-0023 r17 | DESIGNED |
| 11 | Counts | Count task blocks bins; blind count; confirmation creates draft `stock_count` with stored book qty; posting through lifecycle and policy; bin netting regime setting (FLAGGED `net`) | `inventory_count_shortage` / `_surplus` keys; valuation FLAGGED | ADR-0020 r5, r18; ADR-0023 r18 | DESIGNED |
| 12 | Scrap, internal consumption, other issue | movement types at preliminary price, revalued | `scrap`, `consumption`, `other_issue_offset` keys; 641/642 split OQ | ADR-0020 r4; ADR-0015 OQ | DESIGNED (commands/documents not named; owner of these internal documents not stated beyond ADR-0020 r7) |
| 13 | Returns | Customer: `sales_return_receipt` to `returns` bin blocked → disposition; supplier: `purchase_return` | regime value FLAGGED | ADR-0020 r5; ADR-0023 r19 | DESIGNED core; documents DEFERRED DS-22 |
| 14 | Reversal of stock documents | internal types only; refused if consumed; cancels open tasks | negated lines | ADR-0020 r7; ADR-0023 r9 | DESIGNED; value FLAGGED |
| 15 | Negative stock | dated end-of-day per (item, warehouse, lot/serial); physical keys current balance | — | ADR-0020 r10; ADR-0023 r5 | DESIGNED; time point FLAGGED |
| 16 | Costing during period | preliminary price lookup chain; `preliminary_price_missing`; `UpdatePreliminaryPrice` human only | — | ADR-0020 r11 | DESIGNED |
| 17 | Period-end actual costing | sequential close task; exact rational solve over areas linked by transfers; value-only adjustments with derivation trace; degenerate cases to `inventory_revaluation_offset` (FLAGGED) | adjustment documents | ADR-0020 r12–r14; ADR-0012 r16 | DESIGNED rule; algorithm spec DEFERRED DS-09 step 3 |
| 18 | Landed cost | C.4 step 7 | — | ADR-0021 | DESIGNED |
| 19 | Inventory write-down provision | keys exist; close task kind job | `inventory_write_down`, `_allowance` | transaction-keys.csv; ADR-0012 r13, r17 | DEFERRED DS-26 / regime (step 8) |
| 20 | Lots, serials, FEFO/FIFO, shelf life | no cost; FEFO skip below customer minimum (FLAGGED days, expired never picked) | — | ADR-0020 r17; ADR-0023 r3, r14 | DESIGNED |

### C.7 Finance flow: collection to disbursement

| # | Area | Mechanism | Owner | Status |
| --- | --- | --- | --- | --- |
| 1 | Receivables | open items per invoice, bilateral `receivable_trade` with advances split per open item kind | ADR-0010 r6, r15; spec 08 | DEFERRED DS-25 |
| 2 | Cash and bank | cash receipts/payments, cash count, cash book; bank statement import, manual matching, `MatchBankLine`; bank account from master data (no key) | spec 08; spec 11 step 6; ADR-0015 r5 | DEFERRED DS-25; bank matching agent DS-34 |
| 3 | Employee advances | `receivable_employee_advance` (141), `employee_profile.receivable_account_id`, settlement | ADR-0019 r3; system-accounts.csv | DEFERRED DS-25 |
| 4 | Customer/supplier advances | same account as trade, kind per open item; not revalued (non-monetary) | ADR-0015 r11; ADR-0011 r18; spec 07 | DEFERRED DS-25 |
| 5 | Netting | same partner receivable/payable | spec 08; ADR-0019 r2 | DEFERRED DS-25 |
| 6 | Payables | open items, payment terms, expenses without PO (expense account chosen on supplier invoice) | ADR-0015 r5; spec 08 | DEFERRED DS-22, DS-25 |
| 7 | General journal | `general_journal` internal, reversible; may not post to control accounts (FLAGGED); approval rules (who approves) is author's | ADR-0014 r3, r10; ADR-0005 item 11 | DESIGNED type; approval DEFERRED DS-28 |
| 8 | FX at recognition | lookup/document/invoice/customs rate types; applied rates; regime declares quote and date (FLAGGED posting date) | ADR-0011 r1–r14 | DESIGNED |
| 9 | Realized FX | carrying amounts per currency; `specific` or `moving_average`; `realized_fx_basis` | ADR-0011 r15–r16 | DESIGNED rule; logic DEFERRED DS-25; values FLAGGED |
| 10 | Currency exchange | balancing lines in each currency through a clearing account | ADR-0011 r4 | DEFERRED DS-25 (system account not yet in catalog) |
| 11 | Revaluation | system job per period/year end, per open item or balance, `reverse_and_repost` or `delta`, target P&L or `fx_difference_equity`; stale on backdating | ADR-0011 r17–r20 | DESIGNED rule; logic step 8; TT99 values FLAGGED |
| 12 | Period close | states per area, sequence, close tasks (job/check/manual), staleness, core task "agent auto-posts confirmed", closing entries to `income_summary`/`retained_earnings` every period (FLAGGED until TT99 verified) | ADR-0012 | DESIGNED framework; checklist content DEFERRED DS-26 + DS-19 |
| 13 | Provisions, prepaid amortization (242), bad debt by aging | close jobs | spec 08; ADR-0012 r13, r17 | DEFERRED DS-26 / regime (no DS item owns the algorithms explicitly) |
| 14 | VAT | tax codes, dated rates, matrix, line vs document rounding, input VAT deduction warning (VND 5m cash, unverified), 01/GTGT | spec 08; ADR-0018 r16 | DEFERRED DS-23 |
| 15 | E-invoice corrections | adjustment/replacement invoices linked to correction documents | spec 08; ADR-0009 r19, r23 | DEFERRED DS-24 |
| 16 | Statutory reporting | B01, B02, B03, books on operational accounts | ADR-0010 r14; spec 06 r6 | DEFERRED DS-26 |
| 17 | Fiscal year roll-over | system job `fiscal_year_lead_days` before end, on behalf of `fiscal_calendar_owner`; balances cumulative, no opening entry | ADR-0012 r3, r19 | DESIGNED |
| 18 | Opening balances | one simulated `command_batch` incl. FX and open items; `opening_balance_clearing` | spec 15; RB step 4; transaction-keys.csv | DEFERRED DS-21 |

---

## D. Gaps and inconsistencies found while reconstructing (factual, cited)

1. **`employee` table conflict.** DS-06 SQL declares `salesperson_id uuid REFERENCES employee (id)`; ADR-0019 r3 makes employees partners with role `employee` and says `salesperson_id` and `buyer_id` refer to partners; ADR-0014 r9 says "the employee record that DS-20 defines". The DS-06 SQL comment lists `employee` among tables "defined by their own design items", but none defines it.
2. **Tables referenced by FK but never defined**: `company` (columns scattered across five ADRs), `branch`, `cost_center`, `project`, `open_item`, `tax_code`, `derivation_trace`, `partner_group`, `item_tax_group`, `partner_tax_group`, `price_list`, `payment_term`, `work_item`, `agent_type`, `agent_run`, audit record, `policy`, `forecast`, `forecast_run`. Most are DEFERRED to an owner; `company`, `branch`, `cost_center`, `project` have no explicit DS owner other than ADR-0014 r9's pointer to DS-20, which BL's DS-20 row does not list.
3. **Open items needed before their owner.** INV-30 and INV-31 have `first_step` 4 and DS-21 imports AR/AP open items at step 4 (spec 15; RB step 4), but `open_item` belongs to DS-25 "needed by step 6" (BL).
4. **Transfer order has no owner.** It is a demand-line document (RG; ADR-0023 r13) and planning output (`inventory` "creates the draft transfer orders itself", ADR-0024 r22), but no DS item or ADR defines its type, lifecycle or relation to the posting transfer document of ADR-0020 r6.
5. **Customs declaration owning module not stated** (ADR-0021 r10 calls it a step 5 document; ADR-0022 r2 does not place it).
6. **Attachment store owner unassigned** (ADR-0018 "deliberately elsewhere": "no backlog item yet"; ADR-0019 r12).
7. **No invariant for the `gr_ir` control kind** although ADR-0010 r5 says `control_kind` says "which invariant checks it"; invariants.csv 0.1.0 has none for GR/IR or `purchase_cost_clearing` totals beyond INV-27.
8. **Quotation → order conversion, credit check timing, pricing and promotions** are named in spec 09/11 and spec 07's approval conditions, but every rule is DEFERRED to DS-20/22/28, and EC-20/21/22 outcomes are author decisions still open (OQ).
9. **Data export and management reporting** (spec 15 "full data export at any time"; OQ partner question "management reporting and BI") have no DS owner.
10. **Read-model sync/async list** required by spec 07 ("state explicitly which update synchronously and which asynchronously") exists only per ADR, not as a list.
11. **Doc-map staleness**: `docs/README.md` says "DS-01 to DS-40" while BL lists DS-42 and DS-43 (DS-41 excluded as being drafted per the task).
12. **Payment reminders / dunning, repeat-sales suggestions, period-close assistant** are "Next" agents (spec 14) with no backlog row; out of the Phase 1 list.
13. **Provision and amortization job algorithms** (bad debt by aging, inventory write-down, prepaid 242) are close-task jobs whose content goes to "step 8 (DS-26 and the regime)" (ADR-0012 r17); DS-26 is described as a reporting framework (BL), so ownership of the computations is implicit.
14. **Phase of planning and the warehouse feature list** remain the author's open decisions (OQ DS-42, DS-43), so C.3 and parts of C.2/C.6 are designed but not scoped.
