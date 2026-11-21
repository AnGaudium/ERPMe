Module: outbox    Chunk: whole    Source ADRs: ADR-0013, ADR-0031
Build step(s): 0, 1, 2    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: outbox

## Purpose

`outbox` owns the transactional outbox: the events a committed command produced, their per-subject sequence, the
registered consumers, and one delivery row per subscribed consumer. Its delivery workers claim deliveries strictly in
event order per consumer and subject, retry them, and hold a delivery that keeps failing for a human, so nothing
overtakes and nothing is silently dropped. Its workers and queues also run the system jobs, the scheduled jobs and the
PDF worker (R41). It does not own the event types and payload models (each emitting module registers its own), the
consumers' business logic, the lock order (ADR-0027.R10), the database roles and row-level security policies
(ADR-0017.R18, ADR-0017.R19) or the audit log.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`. The module owns <!-- count:tables -->4<!-- /count --> tables.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `outbox_event` | One event, with its subject, sequence, payload, actor context and causation chain; partitioned by month on `id` | `id` | company, or none for an installation-scoped event | `outbox` |
| `event_subject` | Last sequence of one subject; the only ordering of events; unpartitioned installation data | `id`; unique (`subject_table`, `subject_id`) | none | `outbox` |
| `event_consumer` | One registered consumer: kind, queue, pause flag, `max_attempts`, `lease_seconds`; installation data | `id`; unique (`consumer`) | none | `outbox` |
| `event_delivery` | One delivery of one event to one consumer, with its state and timers; unpartitioned | `id`; unique (`consumer`, `event_id`) | `outbox_event`, `event_consumer` | `outbox` |

Every table carries `recorded_at`, and `outbox_event` has a guard trigger as an append-only table (ADR-0007.R9.N2).
`outbox_event` and `event_subject` receive INSERT, UPDATE and DELETE only from their helper's module (ADR-0073.R12).

Reads: `company`.

## Commands and queries

"Not stated" means the sources fill no value for the cell.

| Name | Actor and authorization | Input | Effect | Events | Errors |
| --- | --- | --- | --- | --- | --- |
| `RetryEventDelivery` | `human_only`; company-scoped for a delivery with a `company_id`, installation-scoped otherwise; permissions in DS-15 | a `held` delivery | sets it back to `pending` (R21) | not stated | not stated |
| `SkipEventDelivery` | `human_only`; company-scoped for a delivery with a `company_id`, installation-scoped otherwise; permissions in DS-15 | a `held` delivery and a reason | sets it to `skipped` (R21) | not stated | not stated |
| `ReplayEvents` | `human_only` | consumer, event types, date range | creates `pending` deliveries for retained events the consumer has no delivery for and unpauses the consumer (R23) | not stated | not stated |

Not registered commands: the contract function `context.emit(event_type, subject, payload)` (R3); the delivery claim, a
security-definer function owned by `nativeflows_claim` (ADR-0017.R19); the daily job that deletes old deliveries and
creates and drops `outbox_event` partitions (R44, R45; ADR-0022.R12); the worker process
`nativeflows worker --queue events|integrations|jobs|pdf|agents` (ADR-0022.R12, ADR-0022.R12.N1).

Error code bound to no named command: `tainted_run_not_allowed`, returned by the dispatcher (R36).

## Rules

### Principle

R1. A command writes its state changes, its journal and stock rows, its events and one delivery row per subscribed
consumer in one database transaction (D4). Events live in `outbox_event` and deliveries in `event_delivery`, an ordinary
table in our own database, so an event is delivered if and only if its command commits, simulation rolls everything
back, and no third-party API is needed inside the transaction. There is no event sourcing and no message broker.
Source: ADR-0013.D0

### Events

R2. An event is a fact that a committed command produced (ADR-0004.R22: `PascalCase` noun + event form, e.g.
`GoodsReceiptPosted`). Each event type is registered once, with a pydantic payload model, a semver `schema_version` and
the module that emits it; the registry rejects duplicate event types across modules (ADR-0008).
Source: ADR-0013.R1

R3. Command handlers emit events with `context.emit(event_type, subject, payload)`; queries never emit. An event is
emitted for every document transition (ADR-0009.R22), every posting period state change (ADR-0012.R9) and every other
change another module or a client must react to.
Source: ADR-0013.R1

R4. `outbox_event` columns:
- `id` (UUID version 7, server-generated), `company_id` (null for installation-scoped events), `event_type`,
  `schema_version` (major), `subject_table`, `subject_id`, `subject_sequence`;
- `payload` (JSON in the canonical forms of ADR-0006.R13 and ADR-0007.R3);
- the actor context `actor_kind`, `actor_id`, `on_behalf_of_id`, `agent_run_id` (ADR-0008.R8);
- `origin_agent_run_id`: the command's `agent_run_id`, or the origin it inherited as a consumer command (ADR-0017.R16);
- `is_tainted` (R35);
- `business_date`: the company's business date when the command ran, `clock.today` (ADR-0007.R15);
- `command_type`, `trace_id` (OpenTelemetry) and `recorded_at`;
- `causation_chain_id`, `causation_depth` (0 to 3, no default, a database check) and `automation_rule_version_id`, with
  a depth of at least 1 where a rule version is named (ADR-0058.R12).
Source: ADR-0013.R2, ADR-0013.R2.N1

R5. `outbox_event` is partitioned by month by `id` range (ADR-0006.R22) and has no unique index other than its key.
Source: ADR-0013.R2

R6. `subject_sequence` numbers the events of one subject 1, 2, 3, and so on. It comes from `event_subject`
(`subject_table`, `subject_id`, `last_sequence`), an unpartitioned table whose row the emitting transaction creates or
locks and increments, so the sequence follows commit order for that subject and never restarts, for any subject: a
document, a posting period, an installation-level record. The `event_subject` rows are the last class of the lock order
(ADR-0027.R10).
Source: ADR-0013.R3

R7. `subject_sequence` is the only ordering of events; `id` and `recorded_at` are not ordering keys (ADR-0006.R6,
ADR-0007.R10). There is no ordering across subjects: a consumer reads current state, and if something it needs is
missing it fails retryably (R20).
Source: ADR-0013.R3

R8. A payload carries the facts of the change and the IDs needed to look up the rest (e.g. for `GoodsReceiptPosted`: the
document `id`, `number`, `posting_date`, `version`), never a snapshot, and never a field labeled personal or sensitive
personal (Principle 7; spec 17, data classification and routing). The registry's CI check compares payload fields with
their data labels. A consumer that needs more reads it through a query, under its own permissions.
Source: ADR-0013.R4

R9. Events and deliveries are written in simulation too and roll back with it (ADR-0008.R9). They are not part of the
plan or `plan_hash`; a simulation's response lists the event types it would emit (DS-04).
Source: ADR-0013.R5

R10. A payload change that only adds optional fields is a minor version; anything else is a new major version. The
registry keeps an upcaster from each older major to the current one, and consumers always receive the current major,
including for events written before a deploy and still in retention. Events for outside subscribers (webhooks, after
Phase 1) will need their own deprecation policy.
Source: ADR-0013.R17

### Consumers and deliveries

R11. A consumer is a registered handler with:
- a `consumer` name (`snake_case`, at most 48 characters);
- the event types it subscribes to;
- a `kind`: `transactional`, the default, or `external` for calls to outside systems (R31);
- the queue whose workers run it: `events`, `integrations`, `jobs` for long-job consumers (R42), `pdf` for the render
  worker (R14) or `agents` for `agent_runner` (ADR-0050.R16);
- `is_paused`. A new consumer is registered paused (R23).
Source: ADR-0013.R6, ADR-0013.R6.N1, ADR-0013.R6.N2

R12. When an event is emitted, the dispatcher inserts, in the same transaction, one `event_delivery` row per subscribed
consumer: `id`, `consumer`, `event_id`, `subject_table`, `subject_id`, `subject_sequence`, `company_id`, `state`
(`pending`, `running`, `done`, `held`, `skipped`), `attempts`, `next_attempt_at`, `locked_until`, `last_error`; unique
on (`consumer`, `event_id`); unpartitioned.
Source: ADR-0013.R6

R13. A transactional `NOTIFY` wakes the delivery workers after commit. With each event the dispatcher also sends the UI
header on channel `nativeflows_ui` (ADR-0040.R13).
Source: ADR-0013.R6

R14. The consumer `render_worker` on queue `pdf` follows the shape of R31: it renders with no transaction open and
records the outcome by a command. It sets a 30-minute lease and 3 attempts in place of the defaults of R15 and R20 (5
minutes and 10), because its read may take the 15-minute long-job timeout (ADR-0022.R9) and a render that failed twice
rarely succeeds (ADR-0049.R20).
Source: ADR-0013.R6.N1

R15. A delivery worker of the consumer's queue claims a delivery in a short committed transaction, using
`FOR UPDATE SKIP LOCKED`. It takes a `pending` delivery of a consumer that is not paused, whose `next_attempt_at` has
passed and that has no earlier delivery (lower `subject_sequence`) for the same consumer and subject in any state other
than `done` or `skipped`. It sets `running` and `locked_until` (now plus the consumer's lease, default 5 minutes),
increments `attempts` and sets `next_attempt_at` by exponential backoff (ADR-0022.R12).
Source: ADR-0013.R7

R16. After the claim the worker runs the consumer: a `transactional` consumer runs in a second transaction that also
sets the delivery `done`, so its effect is applied once.
Source: ADR-0013.R7

R17. A worker that crashes leaves the delivery `running`; when `locked_until` passes it returns to `pending` and the
attempt counts. `locked_until` and `next_attempt_at` are technical timers of the worker, not business conditions
(ADR-0007.R10).
Source: ADR-0013.R7

R18. The `agent_runner` consumer extends `locked_until` every 60 seconds while alive, a heartbeat on its 5-minute lease
(ADR-0050.R16).
Source: ADR-0013.R7

R19. A consumer handles an event in one transaction and changes data only through commands run inside it (R24).
Deliveries are handled strictly in event order per consumer and subject (R15).
Source: ADR-0013.D0

R20. On a handled failure the consumer's transaction rolls back and the delivery returns to `pending` with
`last_error`. After `max_attempts` (per consumer, default 10) the delivery becomes `held`: it is shown on the operations
dashboard (DS-36), and a consumer whose failure matters to the business (e.g. an e-invoice not issued) also creates a
work item (DS-29). A `held` delivery keeps blocking later deliveries of its subject for its consumer.
Source: ADR-0013.R8

R21. A human releases a `held` delivery with `RetryEventDelivery` (back to `pending`) or `SkipEventDelivery` (to
`skipped`, with a reason). Both are `human_only` (ADR-0008.R2), company-scoped for deliveries with a `company_id` and
installation-scoped for the others (permissions in DS-15).
Source: ADR-0013.R8

R22. Delivery rows and events carry `company_id`, and row-level security and the consumer's company context follow
DS-15 (ADR-0017.R19). Installation-scoped events (`company_id` null) are delivered only to installation-scoped
consumers. Consumer spans in OpenTelemetry link to the event's `trace_id` (DS-36). Telemetry rules: ADR-0038.R10 and
ADR-0038.R11.
Source: ADR-0013.R14

R23. `ReplayEvents` (consumer, event types, date range; `human_only`) creates `pending` deliveries for retained events
that the consumer has no delivery for, and unpauses the consumer, in one transaction. A new consumer is paused until
then, so live deliveries wait behind the replayed older ones and subject order holds (R15); the unique key prevents
duplicates.
Source: ADR-0013.R16

### Consumer commands

R24. A consumer changes data only through commands, run inside the delivery transaction as actor `system` on behalf of
the event's `on_behalf_of_id`, or its `actor_id` when that actor was a human, under the event's company and
`business_date`.
Source: ADR-0013.R9

R25. Consumer commands are internal calls: they run in execute mode without a prior simulation or `expected_plan_hash`,
because no client reviews between the two; permissions, `human_only`, the policy engine and approvals apply as for any
command. Internal callers are only in-process calls through the dispatcher by consumers and system jobs; they cannot be
reached over REST or MCP. This amends ADR-0008.R13. Exception: the consumer that executes an approved change proposal
passes the stored plan hash (ADR-0029.R3).
Source: ADR-0013.R9

R26. Consumer commands carry the event's `origin_agent_run_id`, or its `agent_run_id` when that is set, as their own
`origin_agent_run_id`, so segregation of duties covers drafts made in reaction to an agent (ADR-0017.R16). They inherit
their event's causation chain and depth (ADR-0058.R12).
Source: ADR-0013.R9, ADR-0013.R9.N2

R27. The idempotency keys of consumer commands are `<consumer>:<event id>:<n>`, numbering the commands of one handling.
Source: ADR-0013.R9

R28. If a condition that an ADR sets on the human a consumer command acts for fails (e.g. ADR-0012.R5), the command
fails and the delivery is eventually held; deactivating the human later does not block events already committed
(ADR-0017.R13).
Source: ADR-0013.R9

R29. Exception to R24: `StartAgentRun` of `agent_wake_up` acts for the agent type setting's `workflow_owner_id`, not for
the event's human, because a wake-up is that workflow's intake (ADR-0017.R12; ADR-0050.R15).
Source: ADR-0013.R9.N1

R30. Exception to R24: the consumer `automation_dispatch` runs each rule's actions as `system` on behalf of the rule's
owner, not the event's human, with keys `automation:<rule version id>:<event id>:<n>` and depth plus one, because a
rule is its owner's standing instruction. The event's human still counts as a writer of the drafts it makes
(ADR-0058.R9, ADR-0058.R10, ADR-0058.R17).
Source: ADR-0013.R9.N2

### Calls to outside systems

R31. Calls to outside systems (e-invoice providers, email, bank APIs) are never made inside a transaction that holds
locks. A transactional consumer records the intent by a command (with our own reference, e.g. an e-invoice submission),
which emits an event; an `external` consumer on the `integrations` queue claims that delivery (R15), makes the call with
no transaction open, then records the outcome by a command and sets the delivery `done` in one transaction. Integration
consumers can recover from an unknown outcome (R32).
Source: ADR-0013.R10, ADR-0013.D0

R32. An unknown outcome (a crash or timeout after the call) is settled before anything is sent again:
- Our reference as the key: where the provider supports an idempotency key, every call, first or repeated, sends our
  reference as that key.
- Settle delay: the retry waits `integrations.<provider>.status_settle_delay_minutes` (company, default 10, bounds 1 to
  1,440) after the unknown call before it asks the provider for the status of our reference; the wait is the delivery's
  `next_attempt_at`, a declared technical timer (ADR-0007.R10).
- Status queries: it sends again only when a first and a second status query of our reference, at least that delay
  apart, both report that the provider holds nothing. A query that finds the reference records its outcome; a query that
  fails or times out ends the round as unknown.
- Rounds: after `integrations.<provider>.max_unknown_rounds` unknown rounds (company, default 3, bounds 1 to 10) the
  consumer stops, holds the delivery (R20) and raises the integration's own kind where it has one
  (`outbound_message_failed` for mail), otherwise `external_call_outcome_unknown` for the document's owner. A person
  checks with the provider and releases the delivery with `RetryEventDelivery` or `SkipEventDelivery`.
- State: the document stays in `issuing` (ADR-0028.R10) or `sending` (ADR-0052.R28) meanwhile.
- The placeholder `<provider>` takes the registered provider adapters (DS-24, DS-37).
Source: ADR-0013.R10, ADR-0013.R10.N1

R33. Rate limits per provider are designed with each integration (DS-24). For e-invoices the outcome is recorded by
`RecordEInvoiceOutcome`, which always succeeds; posting follows by a consumer (ADR-0028.R7).
Source: ADR-0013.R10

R34. The notification e-mail of ADR-0076 follows R31 with one departure: SMTP has no status query, so an `unknown`
outcome is recorded once and never resent, and a temporary refusal fails after three attempts; the in-app inbox still
holds every notification (ADR-0076.R7).
Source: ADR-0013.R10.N2

### Taint and agents

R35. An event emitted by an agent run that has read untrusted content carries `is_tainted = true` (spec 03 agent safety,
rule 1). A consumer may act on a tainted event only by creating drafts and work items; it may not post, change master
data or send anything out (DS-32). Events emitted by commands that a consumer runs for a tainted event are tainted too.
Taint also lives on document versions and `is_untrusted` fields, and a run becomes tainted by what it reads
(ADR-0029.R8 to ADR-0029.R10).
Source: ADR-0013.R11

R36. The dispatcher enforces R35: a consumer command for an event whose `is_tainted` is true must be registered
`is_draft_only` (work item raises and notes inside it are allowed); any other is refused with `tainted_run_not_allowed`
at step 2 of the check order, with a denial record (DS-04, dispatcher check order). `CompleteAgentRun` is exempt: it
records the run's end and changes no business data. `INV-216` checks it (ADR-0050.R55).
Source: ADR-0013.R11.N1

R37. `CreateWorkCase` and `LinkWorkCaseTarget` count with work item raises in R36: they change no document, master
data, setting or right, so a consumer of a tainted event may run them. They are not `is_draft_only`, so no tainted agent
run gains them. The consumer `work_case_opener` skips events that carry an origin agent run (ADR-0066.R6,
ADR-0066.R13).
Source: ADR-0013.R11.N2

R38. `agent_wake_up` skips events with an origin agent run, so nothing in an agent's chain wakes an agent; a run on a
tainted item, or on a subject that is outside content, starts tainted (ADR-0050.R15, ADR-0050.R16).
Source: ADR-0013.R11

R39. Every consumer works with the LLM off (Principle 12). Live updates to open UI screens are not a consumer: the
dispatcher sends a header with each event and web processes forward it over Server-Sent Events (ADR-0040.R13).
Source: ADR-0013.R12, ADR-0040.R13

R40. Agent runs start from work items (DS-32), never directly from an event: the wake-up consumer `agent_wake_up`
reacts to `WorkItemRaised` for kinds an agent type declares (ADR-0042.R14) and dispatches `StartAgentRun`; the run
executes in the external consumer `agent_runner` (ADR-0050.R15, ADR-0050.R16). An agent type may declare a claimable
kind `configurable`, or a configurable trigger; only a company's automation rule with action `start_agent` then starts
it there, and `agent_wake_up` skips that kind (ADR-0058.R7).
Source: ADR-0013.R12, ADR-0013.R12.N1, ADR-0040.R13

### Queues and jobs

R41. The delivery workers and the system jobs run on the outbox workers (ADR-0022.R12), on these queues: `events`
(delivery workers), `jobs` (system jobs such as costing, revaluation, close tasks and scheduled jobs; ADR-0012),
`integrations` (calls to outside systems), `pdf` (the PDF worker in its own process, ADR-0002) and `agents` (the
`agent_runner` consumer, with a 5-minute lease that the live runner extends every 60 seconds, a heartbeat; R18;
ADR-0050.R16). Procrastinate is dropped (OPT-08, decided 2026-11-19). A spike at step 0 confirms it; if the spike needs
more than one small module, Procrastinate on PostgreSQL (ADR-0002) stays as the technical queue for these queues, with
its periodic tasks for scheduled jobs.
Source: ADR-0013.R13, ADR-0013.R13.N1

R42. The consumer queue `jobs` stands beside `events` and `integrations` for consumers that do long-job work; the import
chunks of ADR-0030.R9 are the first. Such a consumer has a lease of its 15-minute timeout (ADR-0022.R9) plus one minute.
System jobs, scheduled jobs and the PDF worker run on the outbox workers and queues that already exist, under the spike
condition of R41.
Source: ADR-0031.R15, ADR-0031.R15.N1

R43. A job's arguments are JSON in canonical forms and include the business date and the actor context it runs under
(ADR-0007.R17); a delivery takes both from its event row. If Procrastinate stays (R41), its jobs are never enqueued on a
command handler's path, so its job sequences are never touched by a simulation (ADR-0008.R9). Jobs are technical work,
distinct from business work items.
Source: ADR-0013.R13

### Retention

R44. `outbox_event` partitions are dropped after `outbox.event_retention_days` (installation setting, a deployment
value, default 400; ADR-0063.R2, ADR-0063.R29), except a partition that still has `pending`, `running` or `held`
deliveries, which is kept and shown on the operations dashboard.
Source: ADR-0013.R15, ADR-0013.R15.N1

R45. `done` and `skipped` deliveries older than the retention of R44 are deleted by a daily job; `held` deliveries are
never deleted automatically. If Procrastinate stays (R41), its finished jobs are deleted after 30 days. Events are not
the audit log, which is never deleted (DS-36), and are never used to rebuild state (D4).
Source: ADR-0013.R15

## Invariants

- `INV-216` `tainted_commands_draft_only` (area `safety`; check point `day`; first step 5; keys `audit_record`): every
  audit record of a command run by an agent run tainted at the record's `recorded_at`, or by a consumer whose origin run
  was tainted at the origin event's `recorded_at` (the instant `INV-210` uses), has `is_draft_only` true as registered
  at the time, except `CompleteAgentRun`. Protects R36.

## Edge cases

None: the edge case catalog holds no `EC` row for this module, and no unit of the module names one.

## Settings

| Key | Value type | Scope | Core default | Bounds | Direction | Rule |
| --- | --- | --- | --- | --- | --- | --- |
| `integrations.<provider>.status_settle_delay_minutes` | integer | company | 10 | 1..1440 | `higher_tighter` | R32 |
| `integrations.<provider>.max_unknown_rounds` | integer | company | 3 | 1..10 | `lower_tighter` | R32 |
| `outbox.event_retention_days` | integer | installation (storage `deployment`) | 400 | 1.. | `neutral` | R44 |

The per-consumer values `max_attempts` (default 10) and `lease_seconds` (default 300) are columns of `event_consumer`,
not settings (R15, R20).

## UI annotations

The sources state no floorplan, title, facet, field annotation or tile for the module. Work item kind of `outbox`:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `external_call_outcome_unknown` | `document` | `document_owner` | `same_day` | `system`: when the delivery is retried and records an outcome, is skipped, or the document is recalled | R32 |

It is not agent-resolvable. `held` deliveries and kept partitions are shown on the operations dashboard (DS-36; R20,
R44).

## Conflicts

CONFLICT ADR-0013.R12: its closing text and ADR-0040.R13 govern: live updates are not a consumer, and agent wake-ups react to `WorkItemRaised` and dispatch `StartAgentRun` (R39, R40); the sentence that wake-ups create or update work items is not restated.
CONFLICT ADR-0013.R13.N1: the note governs over the Procrastinate text of ADR-0013.R13: the queues run on the outbox workers, with Procrastinate kept only if the step 0 spike fails (R41).
CONFLICT ADR-0031.R15.N1: the note decides the OPT-08 question that ADR-0031.R15 left to the author: Procrastinate is dropped under the spike condition (R42).
CONFLICT ADR-0013.R15: ADR-0031.R15.N1 and ADR-0022.R12.N2 make its sentence on finished Procrastinate jobs conditional on the step 0 spike (R45); ADR-0013.R15.N1 gives the setting its dotted key (R44).
CONFLICT ADR-0013.R10: ADR-0013.R10.N1 governs the resend after an unknown outcome: a settle delay and a first and a second status query replace the single status request (R32).
FALSE-POSITIVE ADR-0013.R6.N1: "instead of" only states that `render_worker` sets its own lease and attempts as per-consumer values; the defaults of the claim and failure rules stay for every other consumer.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0007.R9.N2 | ref: ADR-0007.R9.N2 |
| ADR-0013.D0 | R1, R19, R31 |
| ADR-0013.R1 | R2, R3 |
| ADR-0013.R2 | R4, R5 |
| ADR-0013.R2.N1 | R4 |
| ADR-0013.R3 | R6, R7 |
| ADR-0013.R4 | R8 |
| ADR-0013.R5 | R9 |
| ADR-0013.R6 | R11, R12, R13 |
| ADR-0013.R6.N1 | R11, R14 |
| ADR-0013.R6.N2 | R11 |
| ADR-0013.R7 | R15-R18 |
| ADR-0013.R8 | R20, R21 |
| ADR-0013.R9 | R24-R28 |
| ADR-0013.R9.N1 | R29 |
| ADR-0013.R9.N2 | R26, R30 |
| ADR-0013.R10 | R31, R32, R33 |
| ADR-0013.R10.N1 | R32 |
| ADR-0013.R10.N2 | R34 |
| ADR-0013.R11 | R35, R38 |
| ADR-0013.R11.N1 | R36 |
| ADR-0013.R11.N2 | R37 |
| ADR-0013.R12 | R39, R40 |
| ADR-0013.R12.N1 | R40 |
| ADR-0013.R13 | R41, R43 |
| ADR-0013.R13.N1 | R41 |
| ADR-0013.R14 | R22 |
| ADR-0013.R15 | R44, R45 |
| ADR-0013.R15.N1 | R44 |
| ADR-0013.R16 | R23 |
| ADR-0013.R17 | R10 |
| ADR-0017.R18 | ref: ADR-0017.R18 |
| ADR-0017.R18.N1 | ref: ADR-0017.R18.N1 |
| ADR-0017.R18.N2 | ref: ADR-0017.R18.N2 |
| ADR-0017.R19 | ref: ADR-0017.R19 |
| ADR-0017.R19.N1 | ref: ADR-0017.R19.N1 |
| ADR-0017.R19.N2 | ref: ADR-0017.R19.N2 |
| ADR-0022.R10 | ref: ADR-0022.R10 |
| ADR-0022.R12 | ref: ADR-0022.R12 |
| ADR-0022.R12.N1 | ref: ADR-0022.R12.N1 |
| ADR-0022.R12.N2 | ref: ADR-0022.R12.N2 |
| ADR-0023.R10 | ref: ADR-0023.R10 |
| ADR-0027.R10 | ref: ADR-0027.R10 |
| ADR-0027.R10.N1 | ref: ADR-0027.R10.N1 |
| ADR-0027.R10.N2 | ref: ADR-0027.R10.N2 |
| ADR-0031.R15 | R42 |
| ADR-0031.R15.N1 | R42 |
| ADR-0052.R33 | ref: ADR-0052.R33 |
| ADR-0058.R1 | ref: ADR-0058.R1 |
| ADR-0058.R12 | ref: ADR-0058.R12 |
| ADR-0073.R12 | ref: ADR-0073.R12 |
