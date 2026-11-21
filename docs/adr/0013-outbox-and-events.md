# ADR-0013: Outbox and events

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Design item: DS-13. Related decisions: D2, D4, D14. Principles 1, 2, 7, 8, 9, 12, 13. ADR-0002, ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0012.

## Decision

A command writes its state changes, its journal and stock rows, its events and one delivery row per subscribed consumer in one database transaction (D4). Events live in the transactional outbox `outbox_event`; deliveries live in `event_delivery`, an ordinary table in our own database, so an event is delivered if and only if its command commits, simulation rolls everything back, and no third-party API is needed inside the transaction. Delivery workers pick deliveries with `SKIP LOCKED`, strictly in event order per consumer and subject: a delivery that keeps failing is held for a human and blocks the later events of that subject for that consumer, so nothing overtakes and nothing is silently dropped. A consumer handles an event in one transaction and changes data only through commands run inside it; calls to outside systems are recorded as intents and made afterwards by integration consumers that can recover from an unknown outcome. There is no event sourcing and no message broker.

### Rules

**Events**

1. An event is a fact that a committed command produced (ADR-0004 rule 22: `PascalCase` noun + event form, e.g. `GoodsReceiptPosted`). Each event type is registered once, with a pydantic payload model, a semver `schema_version` and the module that emits it; the registry rejects duplicate event types across modules (ADR-0008). Command handlers emit events with `context.emit(event_type, subject, payload)`; queries never emit. An event is emitted for every document transition (ADR-0009 rule 22), every posting period state change (ADR-0012 rule 9) and every other change another module or a client must react to.
2. `outbox_event` columns: `id` (UUID version 7, server-generated), `company_id` (null for installation-scoped events), `event_type`, `schema_version` (major), `subject_table`, `subject_id`, `subject_sequence`, `payload` (JSON in the canonical forms of ADR-0006 rule 13 and ADR-0007 rule 3), the actor context (`actor_kind`, `actor_id`, `on_behalf_of_id`, `agent_run_id`; ADR-0008 rule 8), `origin_agent_run_id` (the command's `agent_run_id`, or the origin it inherited as a consumer command; ADR-0017 rule 16), `is_tainted` (rule 11), `business_date` (the company's business date when the command ran, `clock.today`, ADR-0007 rule 15), `command_type`, `trace_id` (OpenTelemetry) and `recorded_at`. It is partitioned by month by `id` range (ADR-0006 rule 22) and has no unique index other than its key.

   Note ([ADR-0058](0058-configurable-workflows.md), 2026-11-15): `outbox_event` gains `causation_chain_id`, `causation_depth` (0 to 3, no default, a database check) and `automation_rule_version_id`, with a depth of at least 1 where a rule version is named (rule 12).
3. `subject_sequence` numbers the events of one subject 1, 2, 3, …. It comes from `event_subject` (`subject_table`, `subject_id`, `last_sequence`), an unpartitioned table whose row the emitting transaction creates or locks and increments, so the sequence follows commit order for that subject and never restarts, for any subject: a document, a posting period, an installation-level record. It is the only ordering of events; `id` and `recorded_at` are not ordering keys (ADR-0006 rule 6, ADR-0007 rule 10). There is no ordering across subjects: a consumer reads current state, and if something it needs is missing it fails retryably (rule 8).
4. A payload carries the facts of the change and the IDs needed to look up the rest (e.g. for `GoodsReceiptPosted`: the document `id`, `number`, `posting_date`, `version`), never a snapshot, and never a field labeled personal or sensitive personal (Principle 7, [17](../spec/17-seatmap-data-classification.md#data-classification-and-routing)); the registry's CI check compares payload fields with their data labels. A consumer that needs more reads it through a query, under its own permissions.
5. Events and deliveries are written in simulation too and roll back with it (ADR-0008 rule 9). They are not part of the plan or `plan_hash`; a simulation's response lists the event types it would emit (DS-04).

**Delivery**

6. A consumer is a registered handler with a `consumer` name (`snake_case`, at most 48 characters), the event types it subscribes to, a `kind` (`transactional`, the default, or `external` for calls to outside systems, rule 10), the queue whose workers run it (`events` or `integrations`; also `jobs` for long-job consumers, [ADR-0031](0031-design-simplifications.md) rule 15) and `is_paused`. A new consumer is registered paused (rule 16). When an event is emitted, the dispatcher inserts, in the same transaction, one `event_delivery` row per subscribed consumer: `id`, `consumer`, `event_id`, `subject_table`, `subject_id`, `subject_sequence`, `company_id`, `state` (`pending`, `running`, `done`, `held`, `skipped`), `attempts`, `next_attempt_at`, `locked_until`, `last_error`; unique on (`consumer`, `event_id`); unpartitioned. A transactional `NOTIFY` wakes the delivery workers after commit. With each event the dispatcher also sends the UI header on channel `nativeflows_ui` ([ADR-0040](0040-ui-architecture.md) rule 13).

   Note: queue `pdf` is also a consumer queue, for the render worker. It follows rule 10's shape: it renders with no transaction open and records the outcome by a command. Its consumer `render_worker` sets a 30-minute lease and 3 attempts instead of the defaults of rules 7 and 8 (5 minutes and 10), because its read may take the 15-minute long-job timeout ([ADR-0022](0022-repository-and-engineering-conventions.md) rule 9) and a render that failed twice rarely succeeds ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 20).

   Note: queue `agents` (rule 13) is a consumer queue too, for `agent_runner` ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 16).
7. A delivery worker of the consumer's queue claims a delivery in a short committed transaction: it takes a `pending` delivery of a consumer that is not paused, whose `next_attempt_at` has passed and that has no earlier delivery (lower `subject_sequence`) for the same consumer and subject in any state other than `done` or `skipped`, using `FOR UPDATE SKIP LOCKED`; it sets `running`, `locked_until` (now plus the consumer's lease, default 5 minutes), increments `attempts` and sets `next_attempt_at` by exponential backoff. It then runs the consumer: a `transactional` consumer runs in a second transaction that also sets the delivery `done`, so its effect is applied once. A worker that crashes leaves the delivery `running`; when `locked_until` passes it returns to `pending` and the attempt counts. `locked_until` and `next_attempt_at` are technical timers of the worker, not business conditions (ADR-0007 rule 10).

   The `agent_runner` consumer extends `locked_until` every 60 seconds while alive, a heartbeat on its 5-minute lease ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 16).
8. On a handled failure the consumer's transaction rolls back and the delivery returns to `pending` with `last_error`. After `max_attempts` (per consumer, default 10) the delivery becomes `held`: it is shown on the operations dashboard (DS-36), and a consumer whose failure matters to the business (e.g. an e-invoice not issued) also creates a work item (DS-29). A held delivery keeps blocking later deliveries of its subject for its consumer. A human releases it with `RetryEventDelivery` (back to `pending`) or `SkipEventDelivery` (to `skipped`, with a reason); both are `human_only` (ADR-0008 rule 2), company-scoped for deliveries with a `company_id` and installation-scoped for the others (permissions in DS-15).
9. A consumer changes data only through commands, run inside the delivery transaction as actor `system` on behalf of the event's `on_behalf_of_id`, or its `actor_id` when that actor was a human, under the event's company and `business_date`. These are internal calls: they run in execute mode without a prior simulation or `expected_plan_hash`, because no client reviews between the two; permissions, `human_only`, the policy engine and approvals apply as for any command. Internal callers are only in-process calls through the dispatcher by consumers and system jobs; they cannot be reached over REST or MCP. This amends ADR-0008 rule 13. They carry the event's `origin_agent_run_id`, or its `agent_run_id` when that is set, as their own `origin_agent_run_id`, so segregation of duties covers drafts made in reaction to an agent (ADR-0017 rule 16). Their idempotency keys are `<consumer>:<event id>:<n>`, numbering the commands of one handling. If a condition that an ADR sets on that human fails (e.g. ADR-0012 rule 5), the command fails and the delivery is eventually held; deactivating the human later does not block events already committed (ADR-0017 rule 13). Exception: the consumer that executes an approved change proposal passes the stored plan hash ([ADR-0029](0029-proposals-and-agent-safety.md) rule 3).

   Note: exception: `agent_wake_up`'s `StartAgentRun` acts for the agent type setting's `workflow_owner_id`, not for the event's human, because a wake-up is that workflow's intake ([ADR-0017](0017-permission-envelope.md) rule 12; [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 15).

   Note ([ADR-0058](0058-configurable-workflows.md), 2026-11-15): consumer commands inherit their event's causation chain and depth. The consumer `automation_dispatch` runs each rule's actions as `system` on behalf of the rule's owner, not the event's human, with keys `automation:<rule version id>:<event id>:<n>` and depth plus one; like `agent_wake_up`, it is an exception, because a rule is its owner's standing instruction. The event's human still counts as a writer of the drafts it makes (rules 9, 10, 17).
10. Calls to outside systems (e-invoice providers, email, bank APIs) are never made inside a transaction that holds locks. A transactional consumer records the intent by a command (with our own reference, e.g. an e-invoice submission), which emits an event; an `external` consumer on the `integrations` queue claims that delivery (rule 7), makes the call with no transaction open, then records the outcome by a command and sets the delivery `done` in one transaction. If the outcome is unknown (a crash or timeout after the call), the retry first asks the provider for the status of our reference and sends again only if the provider has nothing. Rate limits per provider are designed with each integration (DS-24). For e-invoices the outcome is recorded by `RecordEInvoiceOutcome`, which always succeeds; posting follows by a consumer ([ADR-0028](0028-document-lifecycle-hardening.md) rule 7).

    Note (Design hardening, 2026-11-16): an unknown outcome is settled before anything is sent again:
    - **Our reference as the key.** Where the provider supports an idempotency key, every call, first or repeated, sends our reference as that key.
    - **Settle delay.** The retry waits `integrations.<provider>.status_settle_delay_minutes` (company, default 10, bounds 1 to 1,440) after the unknown call before it asks for the status of our reference; the wait is the delivery's `next_attempt_at`, a declared technical timer (ADR-0007 rule 10).
    - **Two queries.** It sends again only when two status queries of our reference, at least that delay apart, both report that the provider holds nothing. A query that finds the reference records its outcome; a query that fails or times out ends the round as unknown.
    - **Rounds.** After `integrations.<provider>.max_unknown_rounds` unknown rounds (company, default 3, bounds 1 to 10) the consumer stops, holds the delivery (rule 8) and raises the integration's own kind where it has one (`outbound_message_failed` for mail), otherwise `external_call_outcome_unknown` for the document's owner. A person checks with the provider and releases the delivery with `RetryEventDelivery` or `SkipEventDelivery`.
    - **State.** The document stays in `issuing` ([ADR-0028](0028-document-lifecycle-hardening.md) rule 10 note) or `sending` ([ADR-0052](0052-minimal-crm.md) rule 28 note) meanwhile.

    The placeholder `<provider>` takes the registered provider adapters (DS-24, DS-37).

    Note ([ADR-0076](0076-internal-messaging-and-notifications.md), 2026-11-21): the notification e-mail of ADR-0076 follows this rule with one departure: SMTP has no status query, so an `unknown` outcome is recorded once and never resent, and a temporary refusal fails after three attempts; the in-app inbox still holds every notification (ADR-0076 rule 7).
11. An event emitted by an agent run that has read untrusted content carries `is_tainted = true` ([03-agent-safety.md](../spec/03-agent-safety.md) rule 1). A consumer may act on a tainted event only by creating drafts and work items; it may not post, change master data or send anything out (DS-32). Events emitted by commands that a consumer runs for a tainted event are tainted too. Taint also lives on document versions and `is_untrusted` fields, and a run becomes tainted by what it reads ([ADR-0029](0029-proposals-and-agent-safety.md) rules 8–10).

    `agent_wake_up` skips events with an origin agent run, so nothing in an agent's chain wakes an agent; a run on a tainted item, or on a subject that is outside content, starts tainted ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 15–16).

    Note: enforced by the dispatcher: a consumer command for an event whose `is_tainted` is true must be registered `is_draft_only` (work item raises and notes inside it are allowed); any other is refused with `tainted_run_not_allowed` at step 2 of the check order, with a denial record ([DS-04](../design/DS-04-command-envelope.md#dispatcher-check-order)). `CompleteAgentRun` is exempt: it records the run's end and changes no business data. INV-216 checks it ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 55 note).

    Note ([ADR-0066](0066-work-cases.md), 2026-11-21): `CreateWorkCase` and `LinkWorkCaseTarget` count with work item raises here: they change no document, master data, setting or right, so a consumer of a tainted event may run them. They are not `is_draft_only`, so no tainted agent run gains them. The consumer `work_case_opener` skips events that carry an origin agent run ([ADR-0066](0066-work-cases.md) rules 6, 13).
12. Every consumer works with the LLM off (Principle 12). Agent wake-ups are consumers that create or update work items (DS-29); agent runs start from work items (DS-32), never directly from an event. Live updates to open UI screens are a consumer designed in DS-30. Superseded by [ADR-0040](0040-ui-architecture.md) rule 13: live updates are not a consumer; the dispatcher sends a header with each event and web processes forward it over Server-Sent Events. Agent wake-ups react to `WorkItemRaised` for kinds an agent type declares ([ADR-0042](0042-work-queue.md) rule 14).

    The wake-up consumer `agent_wake_up` dispatches `StartAgentRun`; the run executes in the external consumer `agent_runner` ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 15–16).

    Note ([ADR-0058](0058-configurable-workflows.md), 2026-11-15): an agent type may declare a claimable kind `configurable`, or a configurable trigger. Only a company's automation rule with action `start_agent` then starts it there, and `agent_wake_up` skips that kind (rule 7).

**Technical queue**

13. The technical queue is Procrastinate on PostgreSQL (ADR-0002). It runs the delivery workers and the system jobs, on these queues: `events` (delivery workers), `jobs` (system jobs such as costing, revaluation, close tasks and scheduled jobs; ADR-0012), `integrations` (calls to outside systems) and `pdf` (the PDF worker in its own process, ADR-0002). Scheduled jobs use Procrastinate's periodic tasks. A job's arguments are JSON in canonical forms and include the business date and the actor context it runs under (ADR-0007 rule 17); a delivery takes both from its event row. Procrastinate jobs are never enqueued on a command handler's path, so its job sequences are never touched by a simulation (ADR-0008 rule 9). Jobs are technical work, distinct from business work items. The `jobs` queue also runs long-job consumers until the author decides OPT-08 ([ADR-0031](0031-design-simplifications.md) rule 15).

    A queue `agents` runs the `agent_runner` consumer, with a 5-minute lease that the live runner extends every 60 seconds, a heartbeat (rule 7; [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 16).
14. Delivery rows and events carry `company_id`, and row-level security and the consumer's company context follow DS-15; installation-scoped events (`company_id` null) are delivered only to installation-scoped consumers. Consumer spans in OpenTelemetry link to the event's `trace_id` (DS-36). Telemetry rules: [ADR-0038](0038-audit-and-observability.md) rules 10–11.

**Retention, replay and versions**

15. `outbox_event` partitions are dropped after `event_retention_days` (installation setting, default 400), except a partition that still has `pending`, `running` or `held` deliveries, which is kept and shown on the operations dashboard. `done` and `skipped` deliveries older than that are deleted by a daily job; `held` deliveries are never deleted automatically. Finished Procrastinate jobs are deleted after 30 days. Events are not the audit log, which is never deleted (DS-36), and are never used to rebuild state (D4).

    Note (S2 findings closure, 2026-11-21): the registry key of `event_retention_days` is `outbox.event_retention_days` (ADR-0063 rule 2 asks for dotted keys; installation, a deployment value, default 400; ADR-0063 rule 29 note of this date).

16. `ReplayEvents` (consumer, event types, date range; `human_only`) creates `pending` deliveries for retained events that the consumer has no delivery for, and unpauses the consumer, in one transaction. A new consumer is paused until then, so live deliveries wait behind the replayed older ones and subject order holds (rule 7); the unique key prevents duplicates.
17. A payload change that only adds optional fields is a minor version; anything else is a new major version. The registry keeps an upcaster from each older major to the current one, and consumers always receive the current major, including for events written before a deploy and still in retention. Events for outside subscribers (webhooks, after Phase 1) will need their own deprecation policy.

## Context

DS-13 is needed by DS-29 (work queue), DS-24 (e-invoices), DS-27 (PDF), DS-32 (agents) and every module that reacts to another. Constraints:

- No event sourcing: state tables, an append-only journal and a transactional outbox written in one transaction (D4, [07](../spec/07-shared-foundation.md#data-storage-and-synchronization)). Background jobs on a technical queue on PostgreSQL (`SKIP LOCKED`, reading the outbox), separate from the business work queue (07, ADR-0002). No Redis, RabbitMQ or Kafka (ADR-0002).
- The business core appends to the books and emits events; events go to the work queue and wake the responsible agent or human ([04-architecture.md](../spec/04-architecture.md); Principle 8). Untrusted content must not lead to outside effects ([03](../spec/03-agent-safety.md) rule 1).
- Modules call each other only through commands and events (07). Handlers touch only the database, use no sequences on their paths, and outside effects run after commit (ADR-0008 rules 4, 9). Unique keys on partitioned tables must include the partition key (PostgreSQL).
- ADR-0005: among correct options, the one easiest for AI agents wins.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Outbox plus our own delivery table read with `SKIP LOCKED` (chosen) | Delivered exactly when the command commits; strict per-subject order with held deliveries; no third-party API in the transaction; nothing in simulation leaks | Our own worker loop to write and test |
| Enqueue one Procrastinate job per consumer in the command's transaction | No delivery table | Not a public Procrastinate API; burns job sequences in simulation; a failed job lets later ones overtake |
| Outbox plus a relay that polls and enqueues Procrastinate jobs | Standard pattern | Two hops; the same ordering problem after a failed job |
| Fat events (snapshots) | Consumers need no query | Large rows; stale data; leaks fields that permissions or data labels would hide |
| Order by `id` or `recorded_at` | No extra table | Not commit order across transactions and servers; forbidden by ADR-0006 and ADR-0007 |
| Consumers call outside systems directly in the delivery transaction | Simple | Holds locks during network calls; a crash after the call repeats it |

## Constraints that come with the decision

- DS-04 / ADR-0008: `context.emit`; event registry with upcasters; internal command calls (rule 9) recorded in ADR-0008; simulation responses list emitted event types; verbs Retry and Replay.
- DS-15: consumers act on behalf of the event's human under its company; row-level security on outbox and delivery tables.
- DS-16: invariants that every committed command's events and deliveries exist and that each delivery is applied once.
- DS-18: delivery workers, `NOTIFY`, backoff, retention jobs, Procrastinate stalled-job handling for the worker loop; decided in [ADR-0022](0022-repository-and-engineering-conventions.md) rule 12.
- DS-24, DS-27: e-invoice, email and PDF integration consumers, intents and provider status queries; rate limits.
- DS-29, DS-32: work items from events; agent runs from work items; tainted events.
- DS-30: live UI updates. DS-36: held deliveries on the dashboard; spans linked to `trace_id`; audit separate from events.

## Revisit when

- Delivery throughput on the large dataset is measurably too low for one worker loop: partition workers by consumer.
- Outside subscribers (webhooks) are built.

## Documents updated

- [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md): note on internal command calls.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): `events` in the simulation response; `context.emit`.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for outbox event, event subject, subject sequence, consumer, event delivery, queues; verbs Retry and Replay.
- [docs/design/backlog.md](../design/backlog.md): DS-13 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
