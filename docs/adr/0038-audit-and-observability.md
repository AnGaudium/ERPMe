# ADR-0038: Audit log, observability and attachment handling

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-36. Related decisions: D2, D12. Principles 3, 6, 9, 12. ADR-0002, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0012, ADR-0013, ADR-0016, ADR-0017, ADR-0019, ADR-0022, ADR-0027, ADR-0029; spec 03, 17.

## Decision

**Audit records.**
- **What gets one.** Every executed command leaves one immutable audit record, written by the dispatcher in the command's own transaction. Commands on a closed, registered set of tables also record field-level changes in a child table, captured by the write helpers, as SAP's change documents do.
- **Denials.** Refusals that matter for safety leave coalesced denial records, written outside the refused transaction.
- **Retention.** Audit data is never deleted in Phase 1 (ADR-0002). Whether it may ever be dropped, and when, is the author's question.

**Telemetry** uses OpenTelemetry (ADR-0002). An allow-list keeps personal and business values out of it, and a CI test enforces the list.

**Attachments** get:
- a separate upload limit;
- a scan state machine driven by an event;
- retention only for attachments that were ever linked to a posted accounting document.

The retention periods and the strictness of scanning are flagged for the author.

### Rules

**Audit records**

1. `audit_record` (module `audit`, layer 2, ADR-0027 rule 8) is inserted by the dispatcher in the command's transaction after the handler succeeds.
   - **Simulate mode.** Also written in simulate mode and rolled back with it, as events are (ADR-0013 rule 5), so a failure to insert shows in simulation.
   - **Not written** for queries or idempotent replays (ADR-0008 rule 18).
   - **Batches.** One record per batch item. `batch_id` is the idempotency record's ID for the batch. It is not a foreign key, because idempotency records are deleted after their retention (ADR-0008 rule 19).
   - **The result.** The dispatch result carries `audit_record_id` per item, outside the plan and `plan_hash`, so a change proposal's execution can store them (ADR-0029 rule 3). It is null in simulate mode, because the row rolls back (DS-04 response fields; ADR-0008 rule 21).
2. Columns:
   - **Identity:** `id` (UUID version 7), `company_id` (null for installation scope), `recorded_at`, `business_date`. Committed rows are always from execute mode, so the record has no `mode` column.
   - **Command:** `command_type`, `schema_version`, and `effect_class` with `is_human_only` and `is_proposal_bound` as registered at the time, so old rows are judged by the rules then in force (INV-81, INV-86). Also `idempotency_key`, `request_id`, `batch_id`, `batch_item_index`, and `reason` when the command carries one (approvals, period state changes, ADR-0012 rule 9). `reason` is free text that must not hold personal data; the command schemas say so, and erasure masks it under rule 4.
   - **Actor:** `actor_kind`, `actor_id`, `on_behalf_of_id`, `agent_run_id`, `origin_agent_run_id`, `policy_decision_id` (ADR-0029 rule 15). `policy_decision_id` is null for commands at no policy point; period commands have one only for `UnlockPostingPeriod` (DS-28). It comes from the approved `period_unlock_request` ([ADR-0043](0043-policy-and-approval.md) rule 16).
   - **Subject:** `subject_table`, `subject_id`, `document_id` and `document_version` for documents, and the subject's scope dimensions (`branch_id`, `warehouse_id`) for record scope.
   - **Result:** `plan_hash`, `trace_id`, and `check_codes`, the codes of the command's check results ([ADR-0040](0040-ui-architecture.md) rule 10).

   Note: `delegated_from_user_id` when a substitute acts ([ADR-0054](0054-users-roles-and-authorizations.md) rule 21).

   Note: the command columns also hold `is_draft_only` as registered at the time, read by INV-216 ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 55 note).

   Note ([ADR-0058](0058-configurable-workflows.md), proposed 2026-11-15): `audit_record` gains `causation_chain_id`, `causation_depth` (0 to 3, no default, a database check) and `automation_rule_version_id`, with a depth of at least 1 where a rule version is named (rule 12).
3. Field changes, in `audit_change` (`id`, `company_id`, `audit_record_id`, `subject_table`, `row_id`, `field`, `before`, `after`, `erased_at`):
   - **Which tables.** A closed set, `is_change_tracked` in each module's table declarations and checked by CI: master data, settings including enabled regime settings (ADR-0016), role assignments, period area state and production structures. Documents rely on `document_version`. Balances, counters, open items and other derived rows are not tracked.
   - **How it is captured.** Only `context`'s write helpers capture it. They read the before row and compute the diff with the canonical forms and diff code of ADR-0029 rule 1. Handlers never build changes by hand.
   - **Enforcement.** A DS-18 guard, like the one for serialized tables (ADR-0008 rule 10), fails CI when SQL outside the `context` helpers writes an `is_change_tracked` table, bulk `UPDATE … WHERE` included. A DS-16 property test checks that the before row plus its `audit_change` rows equals the after row.
   - **Size bound.** At most 10,000 rows per command. Beyond that, the record stores the changed field names and a hash of the before and after values per row, with the check result `audit_changes_summarized`.
   - **Personal data.** Personal fields keep their data labels (spec 17). Creating a record and erasing a data subject store field names without values for personal fields.
4. Erasure (ADR-0019 rule 10, which gets a note):
   - **Who may update.** `audit_change` and `audit_record` are append-only, except that `EraseDataSubject` replaces `before` and `after` of the subject's change rows, and `reason` on audit records whose subject is an erased record, with a marker and sets `erased_at`.
   - **How the trigger knows.** The dispatcher alone runs `SET LOCAL nativeflows.erasure_command_id` to the ID of the running command's `idempotency_record`, and only for the command registered as the erasure command. The trigger allows the update only when that setting is present and matches an idempotency record of that command type in the same transaction, and no other column changes.
   - **Finding the rows.** An index on (`subject_table`, `row_id`).
5. Denial records, `audit_denial`:
   - **When.** A command or query refused with one of these codes writes a denial record, in simulate and execute mode alike: `permission_denied`, `human_only`, `proposal_required`, `policy_denied`, `outbound_content_out_of_scope` and `segregation_of_duties`. The dispatcher classifies by error code, wherever the error was raised.
   - **Columns.**
     - company, command or query type, `mode`;
     - actor columns, `agent_run_id`, `origin_agent_run_id`;
     - `request_id`, `idempotency_key`, `subject_table`, `subject_id`, error code (no request hash: a plain hash of a small personal payload would survive erasure);
     - for `policy_denied`, `policy_rule_id` and `policy_input_hash`, because the policy decision row is rolled back;
     - `window_start`, `count`, `first_at`, `last_at`, `trace_id`.
   - **Writing.** On the API path, the dispatcher writes it after the rollback through a small dedicated connection pool; when the pool is exhausted the denial is dropped with a metric. For internal callers (consumers, jobs) the worker buffers it and writes it after the delivery transaction ends; a worker crash loses its buffered denials.
   - **Coalescing.** One row per (company, actor, agent run, type, code, subject, `window_start`), with 10-minute windows. The writer upserts on a unique index over that key with `NULLS NOT DISTINCT`, adding to `count` and moving `last_at`.
   - **Failure.** A failed denial insert never fails the caller. It logs a structured error and raises a metric.
   - **Simulation.** A denial record is the one effect of a simulation that persists (ADR-0008 rule 9 gets a note).

   Also `tool_not_allowed`, `tainted_read_out_of_scope`, `untrusted_read_not_allowed` and `tainted_run_not_allowed`; three denials stop a run ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 33, 55). Also `automatic_send_not_allowed`; the CRM's reads outside a tainted run's scope use `tainted_read_out_of_scope` ([ADR-0052](0052-minimal-crm.md) rule 34).

   Note: the complete list of codes that write denial records: `permission_denied`, `human_only`, `proposal_required`, `policy_denied`, `outbound_content_out_of_scope`, `segregation_of_duties`, `tool_not_allowed`, `tainted_read_out_of_scope`, `untrusted_read_not_allowed`, `tainted_run_not_allowed`, `automatic_send_not_allowed` and `origin_run_submit_not_allowed`, and the refusals only people meet: `approver_not_eligible`, `approver_is_submitter`, `grant_exceeds_own_rights`, `segregation_conflict` and `organization_self_change`. None is written for `work_item_claim_lost` (a person took the item), `approval_already_given` or `approval_would_strand_stage` (preconditions), or `llm_routing_refused`, which the gateway records on the run step ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 19). The three-denial stop of [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 33 counts every code of the list returned to a run; the people-only codes cannot reach a run, whose tool list holds none of their commands.

   Note (catalog review, 2026-11-15): the column `count` is `denial_count` in `audit_denial` (DS-05-platform.sql; ADR-0004 rule 13); the coalescing writer adds to it.
6. Storage:
   - **Protection.** Audit and change records are protected by append-only triggers (rule 4's exception aside) and the generated company policy. The trigger on `audit_denial` allows only `count` and `last_at` to change, and only upward.
   - **Partitions.** `audit_record` and `audit_change` are partitioned by month on `id`; ADR-0006 rules 22 and 23 get a note. The daily job of ADR-0022 creates partitions three months ahead, with a default partition. `audit_denial` is not partitioned, because its unique coalescing index cannot include `id`, and coalescing keeps it small.
   - **Indexes.** On subject, actor, `agent_run_id`, and (`idempotency_key`, `actor_id`, `command_type`).
   - **No deletion.** Nothing is dropped in Phase 1 (ADR-0002; ADR-0008 rule 19; ADR-0013 rule 15).
   - **Export.** `ExportCompanyData` includes them (ADR-0027 rule 8).
7. Queries, each with its own generated permission (ADR-0017 rule 4), and record scope from the stored scope dimensions:
   - `ListAuditRecord`;
   - `GetAuditRecord`, with changes filtered by field class per (table, field), failing closed on unknown fields (ADR-0017 rule 10);
   - `ListAuditDenial`.

   **Agents.** These queries are on no agent tool list in Phase 1 (ADR-0008 rule 6; DS-32), and tainted runs never read audit data. Reading denials would let an injected agent probe.

   `ListAgentRun`, `GetAgentRun` and every view over audit tables are on no agent tool list either ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 30, 50).

   Note: a record whose subject is a document is shown only within that document's read owner scope ([ADR-0054](0054-users-roles-and-authorizations.md) rule 15).
8. INV-89: every idempotency record of an executed command (ADR-0008 rule 19), within its retention, has an audit record with the same key, actor and command type, or the same `batch_id` for batches. The company is compared null-safely, and ADR-0008 rule 16 gets `company_id` on idempotency records. Area `platform`, first step 1. Group 80–89 is now full: further safety and platform invariants use INV-200 to INV-299 (DS-16).

**Other audit duties**

9. Duties that other ADRs assigned to DS-36:
   - **Period state changes.** Recorded with `reason` (rule 2) and the approval through `policy_decision_id` (ADR-0012 rule 9).
   - **Enabling unverified regime rules.** Audited as tracked changes of regime settings (rule 3; ADR-0016).
   - **Exports and erasures.** Write both an audit record and an entry in the personal data processing log (ADR-0019 rule 11). The breach notification procedure belongs to DS-40 under the existing open question on Law 91/2025; audit and denial records are its evidence. The processing log is owned by `audit` ([ADR-0052](0052-minimal-crm.md) rule 26).
   - **`nativeflows-check` against production** (DS-16) may run, only with the read-only role, on a standby replica or with `statement_timeout`, and never with write rights.

**Observability**

10. Traces, metrics and logs:
    - **Spans.** For API requests, dispatched commands and queries, consumer deliveries (linked to the event's `trace_id`, ADR-0013 rule 14), job runs and LLM gateway calls (DS-32).
    - **Metrics,** exported as histograms and counters:
      - latency by command and query type;
      - error counts by code;
      - `concurrent_update` and `timeout` counts;
      - lock wait time per lock class;
      - delivery lag and held deliveries per consumer;
      - job durations;
      - close-task staleness;
      - invariant failures;
      - dead tuples and autovacuum lag (ADR-0002);
      - LLM tokens and cost per agent type (an amount exempt from rule 11, as an operational figure).
    - **Logs.** structlog JSON with `trace_id` and `request_id`.

    Gateway and tool-call spans and the agent metrics: [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 21.

    Note ([ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), proposed 2026-11-15): spans of agent runs, LLM calls, tool calls and automation executions use the OpenTelemetry GenAI attribute names where they exist, and carry the command request ID, agent run ID, work item ID and automation execution ID, never values (X8). Decision records that name an artifact version, and the artifact tables, follow this ADR's retention: never deleted in Phase 1; a regime may only lengthen it (rules 23, 26).
11. No values in telemetry, enforced:
    - **Allow-lists.** Span attributes and log fields come from an allow-list of keys (codes, types, counts, hashes). A structlog processor and a span processor drop everything else.
    - **Exceptions** are recorded as type and error code only.
    - **SQL.** Statement and parameter capture is off.
    - **Metric labels.** No IDs as labels; only low-cardinality codes.
    - **The check.** A CI test seeds canary values in the scenario run and fails if any reaches emitted telemetry.

    The allow-listed attributes of gateway spans are in [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 21; prompts and outputs stay in `agent_run_step` only.
12. Telemetry goes through OTLP to a collector:
    - **Tool choices.** The backend and the attachment scanner are new tool categories, chosen by ADR in DS-37, not from ADR-0002's list of tools not used. The byte-level media detection library is chosen by ADR at the first step that builds upload.
    - **Dashboard.** In Phase 1 the operations dashboard is the backend's, with panels generated from the metric names. Held deliveries and their `last_error` (ADR-0013 rule 8) are read through the delivery query, not the dashboard, because they carry values. An NativeFlows screen comes later.

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): management dashboards are not this operations dashboard: they are saved analyses and KPI tiles of the analysis layer, run through `EvaluateAnalysisPlan` under the viewer's rights. Metrics add analysis answers by outcome and badge, abstentions by code and model cost per answer, with codes as labels (rules 26, 27, 32).

**Attachments**

13. Upload:
    - **Endpoint.** Files go through a dedicated upload endpoint whose limit is `attachment_max_bytes` (default 25 MiB), separate from the 10 MiB request body limit (ADR-0022). It is a hand-written exception to ADR-0008 rule 6, with the session and stream endpoints of [ADR-0040](0040-ui-architecture.md) rule 12; ADR-0008 rule 6 gets a note.
    - **Flow.** The endpoint streams the bytes to the object store under a temporary key, then dispatches the registered command `CreateAttachment` (SHA-256, size, detected type, data label, source kind), which is audited and emits `AttachmentCreated`. A daily job sweeps temporary bytes that no attachment row references after 24 hours.
    - **Errors.** `attachment_too_large` (category `too_large`, HTTP 413) and `attachment_type_not_allowed`.
    - **Allowed types.** The list is installation data: PDF; PNG, JPEG and WebP (not SVG); XML; CSV; XLSX, recognised by its ZIP content types; and e-mail messages. The type is detected from the bytes.

    Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): the allowed types are unchanged; a vCard file is not one in Phase 1. Photos, business cards, delivery notes, voice and inquiry attachments, and every attachment from inbound e-mail, are labelled `personal` as a whole at creation, and the label is never lowered; extractions take it or a higher one ([ADR-0057](0057-document-intake-and-extraction.md) rules 3, 19).

    Note (Design hardening, 2026-11-16): bytes are stored write-once under the key `attachments/<company_id>/<sha256>`, in a store with object versioning or object lock where the store offers it (DS-37); an object is never overwritten or changed. The upload endpoint copies the temporary bytes to that key only when no object is there yet. The 24-hour sweep of temporary keys stays, because no attachment row ever names a temporary key.
14. Scan state machine, `attachment.state` (`pending_scan`, `clean`, `rejected`):
    - **Running the scan.** A new attachment emits `AttachmentCreated`. A consumer on `integrations` runs the scanner and records the outcome. A scanner outage retries and is eventually held (ADR-0013 rule 8).
    - **Rejected attachments.** Their bytes are deleted at once, and their links are removed with a work item. A new upload of the same SHA-256 as a rejected row is refused with `attachment_rejected`. An upload matching a pending row reuses it.
    - **Serving.** Bytes that are not `clean` are never served, to people or agents: download and parsing fail with `attachment_not_available`.
    - **Posting.** `Post` of a document with a linked attachment that is not `clean` is rejected with `attachment_not_available`. `documents` reads the state through `attachments.contract`, a new import inside layer 2 (ADR-0022 and ADR-0027 rule 1 get a note).
    - **Scan mode.** `attachment_scan_mode` is an installation setting: `required`, or `optional`, under which attachments pass with the check result `scan_unavailable` when no scanner is deployed. `production` requires `required` (flagged; open question).
    - **Untrusted content.** Attachments from outside content are untrusted (ADR-0029 rule 10).

    Note: generated files (source kind `generated`) are created `clean` without a malware scan: the render worker produces their bytes from company templates in a sandbox without network access. `clean` covers only the scan. A generated file whose rendered instance held an `is_untrusted` field carries `contains_untrusted`, and reading it taints a run ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 25; [ADR-0049](0049-statutory-reporting-and-printing.md) rule 28).

    Note: an attachment linked to a document follows that document's read owner scope ([ADR-0054](0054-users-roles-and-authorizations.md) rule 15).

    Note (Design hardening, 2026-11-16): "their bytes are deleted at once" now reads: a rejected attachment stops being served at once, and the transaction that records the rejection sets its `bytes_released_at`; its bytes are physically removed only by the orphan sweep of rule 15's note, after the grace period. Bytes that are not `clean` are never served in the meantime.
15. Retention:
    - **Accounting attachments.** `Post` sets `attachment.is_accounting_evidence` on every linked attachment; it is never unset. Bytes of such an attachment are kept `attachment_retention_years` after its last link ends. This is a regime setting, seeded `unverified` at 10 years for accounting vouchers. Under ADR-0016 rule 12 an unverified setting fails closed, so such bytes are not purged until the author verifies it. TT99 seed: package `settings.yaml` ([ADR-0039](0039-vietnam-package-tt99.md) rule 9).
    - **Erasure.** Erasure removes a subject's links except links to posted accounting documents, which stay as voucher evidence; ADR-0027 rule 2 gets a note.
    - **Other attachments.** Their bytes are deleted when the last link goes, including at erasure (ADR-0019 rule 10).

    Note: linking a generated file to a posted document, or to a statutory report filing as the submitted file, sets `is_accounting_evidence` ([ADR-0049](0049-statutory-reporting-and-printing.md) rules 19, 28).

    Note (Design hardening, 2026-11-16): the database and the attachment store share one restore point.
    - **No early delete.** No object is physically deleted while a database restore point could still name it. Where this ADR or another deletes bytes (a rejection, the last link of an ordinary attachment, an erasure, the end of retention), the transaction only sets `attachment.bytes_released_at`; the bytes are no longer served.
    - **Grace period.** `attachments.delete_grace_days` (installation, a deployment value, default 35, bounds 7 to 3,650) must be at least the database's point-in-time-recovery window that the deployment configures (DS-37); the startup step refuses to start when it is shorter.
    - **Orphan sweep.** `RunAttachmentOrphanSweep` (module `attachments`, effect class `other`, installation scope, a daily system job, `is_internal_only`) compares the store's objects with the attachment rows and deletes an object only when it is an orphan older than the grace period: every row naming its key set `bytes_released_at` more than the grace period ago, or no row names it and the object was written more than the grace period ago. It sets `bytes_deleted_at` on those rows. Attachment rows are never deleted.
    - **Restore procedure.** Restore the database to a time T inside the recovery window. Every object an attachment row named at T without a release still exists, because only objects released or written before now minus the grace period have been deleted. Objects written after T are orphans to the restored database, and the sweep deletes them once they are older than the grace period. The store's versioning or object lock covers operator error.
    - **Still immediate:** a rejected attachment stops being served at once (rule 14), and an erased subject's bytes stop being served at once; they are physically gone within the grace period, the window in which database backups still hold the erased rows.

    [DS-05-platform.sql](../design/DS-05-platform.sql) adds `attachment.bytes_released_at`; DS-37 ([backlog](../design/backlog.md)) chooses the store, its versioning or object lock, and the recovery window.

## Context

INV-81 and INV-85 to INV-87 query audit rows, change proposals link to them, and spec 03 links agent runs to audit. ADR-0002 already says audit data is never deleted. The first review of this ADR found that it had contradicted that rule, left the change capture unowned, and lacked a workable model for denials and attachment scanning. This version closes those gaps.

SAP's change documents record field-level changes of master data. NativeFlows does the same for a registered set of tables and leaves document history to versions.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Audit in the command transaction (chosen) | Atomic with effects | A row per command on the hot path |
| Audit through the outbox | Off the hot path | Can lag or be lost |
| Audit as views over immutable tables (assessment OPT-22) | No extra copy | Master data and settings are updated in place, so their history needs its own record |
| Changes in a child table with a registered set (chosen) | Indexable for erasure and filtering; bounded | One more table |
| Changes for every update | Complete | Counters and balances would flood it |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0006 rules 22, 23 (partitioned append-only audit tables; `audit_denial` unpartitioned);
  - ADR-0008 rules 6, 9, 16, 19, 21 (upload endpoint exception; denials persist from simulations; `company_id` on idempotency records; INV-89; `audit_record_id` per item);
  - ADR-0012 rule 9 (reason and approval);
  - ADR-0013 rule 14 (spans);
  - ADR-0016 rule 11 (audit of enabled rules);
  - ADR-0017 rule 8 (denials recorded);
  - ADR-0019 rules 10, 11 (erasure of changes; processing log; breach notification in DS-40);
  - ADR-0022 (partition job; upload limit; `documents` imports `attachments.contract`);
  - ADR-0027 rules 1, 2, 8 (the new layer-2 import; attachment details and erasure of links; audit columns);
  - ADR-0029 rules 3, 15 (audit record IDs in results; columns).
- **DS-04:**
  - response field `audit_record_id`;
  - errors `attachment_too_large` (category `too_large`), `attachment_type_not_allowed`, `attachment_rejected`, `attachment_not_available` (category `precondition`);
  - check results `scan_unavailable`, `audit_changes_summarized`.
- **DS-16:** INV-89 and the next code range; the production check rule; the change capture property test.
- **DS-18:** the guard on writes to change-tracked tables.
- **Glossary:** audit record, audit change, audit denial, change tracking, scan state.
- **Other design items:**
  - DS-32: tool lists and denial signals;
  - DS-33: no audit views for agents;
  - DS-37: the tool choices, collector and scanner;
  - DS-40: breach notification procedure.
- **Open questions:**
  - whether audit may ever be dropped, and after how long;
  - attachment retention;
  - scan mode in production.

## Revisit when

- Audit writes measurably slow the command path.
- The author decides retention.

## Documents updated

- **ADRs:** [docs/adr/0006-id-and-numeric-model.md](0006-id-and-numeric-model.md), [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0013-outbox-and-events.md](0013-outbox-and-events.md), [docs/adr/0016-localization-package-structure.md](0016-localization-package-structure.md), [docs/adr/0017-permission-envelope.md](0017-permission-envelope.md), [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0029-proposals-and-agent-safety.md](0029-proposals-and-agent-safety.md): notes.
- **Design and catalogs:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
