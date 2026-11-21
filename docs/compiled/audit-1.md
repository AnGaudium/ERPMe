Module: audit    Chunk: 1 of 2    Source ADRs: ADR-0019, ADR-0027, ADR-0029, ADR-0038, ADR-0052, ADR-0079
Build step(s): 0, 1, 2, 4, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `audit`, chunk 1

## Purpose

`audit` (layer 2, ADR-0022.R2) owns the audit records of executed commands, the field changes of change-tracked tables, the
denial records and the personal data processing log. This chunk states their columns, writing, storage, queries and
erasure exception, the telemetry rules (traces, metrics, logs) and the decision text of personal data protection. The
catalog, blocking, retention, destruction, read log and breach rules of ADR-0079 are in chunk 2. Attachments (ADR-0038.R13
to ADR-0038.R15) belong to `attachments`; `EraseDataSubject` is a command of `crm` (ADR-0052.R25).

## Entities and tables

DDL: `docs/design/DS-05-platform.sql` (`audit_record`, `audit_change`, `audit_denial`) and `docs/design/DS-35-crm.sql`
(`personal_data_processing_log`). The other owned tables (`personal_data_read_log`, `data_erasure_entry` and the tables of
`docs/design/DS-64-personal-data.sql`) have their rows in chunk 2.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `audit_record` | One row per executed command or batch item (R5 to R16). Partitioned by month on `id`. The DDL also holds `is_internal_only` as registered at the time, which no rule states (the DDL marks it interim). | `id` | `company` (null for installation scope) | `audit` |
| `audit_change` | Field changes of the change-tracked tables (R17 to R22). Partitioned by month on `id`. | `id` | `audit_record` | `audit` |
| `audit_denial` | Coalesced records of refused commands and queries (R32 to R40). Not partitioned. | `id`; unique coalescing key (R37) | `company` | `audit` |
| `personal_data_processing_log` | Every processing of personal data the law asks to log; IDs and field names, never values (R54 to R58). | `id` | `company` | `audit` |

The check `ck_audit_denial_error_code` of the DDL lists fewer codes than R32: it lacks `origin_run_submit_not_allowed` and
the codes only people meet.

Reads: `idempotency_record`, `document_version`, `policy_decision`, `period_unlock_request`, `custom_field_definition`, `journal_entry`, `journal_line`, `outbox_event`, `agent_run_step`, `company`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ListAuditRecord` (query) | Its own generated permission; leaf `audit` (the verb `List` is level `read`); record scope from the stored scope dimensions (R45) | not stated | Lists audit records | None (query) | not stated |
| `GetAuditRecord` (query) | Its own generated permission; leaf `audit`, verb level not stated; record scope as above | not stated | One audit record with its changes, filtered by field class per (table, field), failing closed on unknown fields (R45) | None (query) | not stated |
| `ListAuditDenial` (query) | Its own generated permission; leaf `audit` (the verb `List` is level `read`) | not stated | Lists denial records | None (query) | not stated |

Not commands: the contract function `audit.contract.log_personal_data_processing` (R55). The erasure scope of
`audit.contract` (R26) and the database functions `erasure_marker_valid()` and `erasure_column_change_allowed` (R25, R27,
R28) are listed under the table of chunk 2.
`DestroyRetainedPersonalData` (`system`, `is_internal_only`, module `audit`; ADR-0019.R10.N2) has its row in chunk 2.

Codes named by the rules of this chunk: the denial codes of R32, and the check result `audit_changes_summarized` (R21).

## Rules

### Ownership

R1. `audit` (layer 2, DS-36) owns the audit records, with one row per executed command: `command_type`, `actor_kind`, `actor_id`, `agent_run_id`, `idempotency_key` (needed by `INV-81`), and also `origin_agent_run_id`, `on_behalf_of_id` and `policy_decision_id`. The full columns, changes and denials are R5 to R47.
Source: ADR-0027.R8, ADR-0029.R15

R2. The same ownership list names, outside `audit`: `customs_declaration` and its tax rows, owned by `purchasing` from step 5 (ADR-0021.R10); e-invoice records and intents, owned by `tax` (DS-24), which also owns the computation of `document_line_tax`, the subledger `tax_line` with its adjustments, and filed `tax_return` snapshots (ADR-0041), with imports going downward (as ADR-0024.R22); the full data export `ExportCompanyData` (DS-21; ADR-0044.R17); management reporting, which is the analysis layer of `query` over the DS-33 semantic views and never documents, whose measures over accounts use system accounts and ADR-0049's turnover rules for closing and migration entries and equal ADR-0049's turnover for the same scope and range (`INV-411`; ADR-0060), while statutory reports stay DS-26; bad-debt provisions and prepaid amortization (DS-25, close tasks); the inventory write-down to net realizable value (DS-09, a close task). These computations are not DS-26's, whatever ADR-0012.R17 names.
Source: ADR-0027.R8, ADR-0027.R8.N1

R3. A sales document requests issuance through `tax.contract.request_e_invoice`, synchronously; it writes the e-invoice record and its intent. The external consumer then issues it asynchronously, and the document posts on acceptance (ADR-0028.R7).
Source: ADR-0027.R8

R4. `ExportCompanyData` writes a company package with master data, documents with all versions, journal and material lines, open items, stock, attachments and audit rows, as one JSON Lines file per table plus the attachment files. It is not the import batch format; contents, exclusions and download are ADR-0044.R17.
Source: ADR-0027.R8

### Audit record: writing

R5. `audit_record` (module `audit`, layer 2) is inserted by the dispatcher in the command's transaction after the handler succeeds. Every executed command leaves one immutable record.
Source: ADR-0038.R1

R6. The record is also written in simulate mode and rolled back with it, as events are (ADR-0013.R5), so a failure to insert shows in simulation.
Source: ADR-0038.R1

R7. No audit record is written for queries or idempotent replays (ADR-0008.R18). A read that returns a `sensitive_personal` column or a blocked subject's unmasked data, and every export with a personal column, writes a `personal_data_read_log` row with no values (ADR-0079.R12).
Source: ADR-0038.R1, ADR-0038.R1.N1

R8. A batch gets one record per batch item. `batch_id` is the idempotency record's ID for the batch. It is not a foreign key, because idempotency records are deleted after their retention (ADR-0008.R19).
Source: ADR-0038.R1

R9. The dispatch result carries `audit_record_id` per item, outside the plan and `plan_hash`, so a change proposal's execution can store them (ADR-0029.R3). It is null in simulate mode, because the row rolls back (DS-04 response fields; ADR-0008.R21).
Source: ADR-0038.R1

### Audit record: columns

R10. Identity columns: `id` (UUID version 7), `company_id` (null for installation scope), `recorded_at`, `business_date`. Committed rows are always from execute mode, so the record has no `mode` column.
Source: ADR-0038.R2

R11. Command columns: `command_type`, `schema_version`, and `effect_class` with `is_human_only`, `is_proposal_bound` and `is_draft_only` as registered at the time, so old rows are judged by the rules then in force (`INV-81`, `INV-86`; `INV-216` reads `is_draft_only`, ADR-0050.R55). Also `idempotency_key`, `request_id`, `batch_id`, `batch_item_index`, and `reason` when the command carries one (approvals, period state changes, ADR-0012.R9).
Source: ADR-0038.R2, ADR-0038.R2.N2

R12. `reason` is free text that must not hold personal data; the command schemas say so, and erasure masks it under R23. The commands of an operating preset's application carry the preset code and version in `reason` (ADR-0067.R4, ADR-0067.R13).
Source: ADR-0038.R2, ADR-0038.R2.N4

R13. Actor columns: `actor_kind`, `actor_id`, `on_behalf_of_id`, `agent_run_id`, `origin_agent_run_id`, `policy_decision_id` (ADR-0029.R15), and `delegated_from_user_id` when a substitute acts (ADR-0054.R21). `policy_decision_id` is null for commands at no policy point; period commands have one only for `UnlockPostingPeriod` (DS-28), where it comes from the approved `period_unlock_request` (ADR-0043.R16).
Source: ADR-0038.R2, ADR-0038.R2.N1

R14. Subject columns: `subject_table`, `subject_id`, `document_id` and `document_version` for documents, and the subject's scope dimensions (`branch_id`, `warehouse_id`) for record scope.
Source: ADR-0038.R2

R15. Result columns: `plan_hash`, `trace_id`, and `check_codes`, the codes of the command's check results (ADR-0040.R10). `is_review_skipped` is true when a person's `Post<Type>` executed without the plan panel under `ui.post_review` `on_exceptions`.
Source: ADR-0038.R2, ADR-0038.R2.N4

R16. Causation columns: `causation_chain_id`, `causation_depth` (0 to 3, no default, a database check) and `automation_rule_version_id`, with a depth of at least 1 where a rule version is named (ADR-0058.R12).
Source: ADR-0038.R2.N3

### Field changes

R17. Field changes are stored in `audit_change` (`id`, `company_id`, `audit_record_id`, `subject_table`, `row_id`, `field`, `before`, `after`, `erased_at`, `recorded_at`).
Source: ADR-0038.R3

R18. The tracked tables are a closed set, marked `is_change_tracked` in each module's table declarations and checked by CI: master data, settings including enabled regime settings (ADR-0016), role assignments, period area state and production structures. Documents rely on `document_version`. Balances, counters, open items and other derived rows are not tracked.
Source: ADR-0038.R3

R19. Only `context`'s write helpers capture changes. They read the before row and compute the diff with the canonical forms and diff code of ADR-0029.R1. Handlers never build changes by hand.
Source: ADR-0038.R3

R20. A DS-18 guard, like the one for serialized tables (ADR-0008.R10), fails CI when SQL outside the `context` helpers writes an `is_change_tracked` table, bulk `UPDATE … WHERE` included. A DS-16 property test checks that the before row plus its `audit_change` rows equals the after row.
Source: ADR-0038.R3

R21. A command records at most 10,000 rows in `audit_change`. Beyond that, the record stores the changed field names and a hash of the before and after values per row, with the check result `audit_changes_summarized`.
Source: ADR-0038.R3

R22. Personal fields keep their data labels (spec 17). Creating a record and erasing a data subject store field names without values for personal fields.
Source: ADR-0038.R3

### Erasure exception

R23. `audit_change` and `audit_record` are append-only, except that an erasure command replaces `before` and `after` of the subject's change rows, and `reason` on audit records whose subject is an erased record, with a marker and sets `erased_at`. The erasure commands are `EraseDataSubject` and `DestroyRetainedPersonalData`. An index on (`subject_table`, `row_id`) finds the rows.
Source: ADR-0038.R4, ADR-0038.R4.N2

R24. The exception extends to posted documents, document versions and the journal's text columns (`journal_entry.note`, `journal_line.description`), limited to the catalog columns of each table. Every rewrite appends a `data_erasure_entry` and, after commit, an erasure journal line outside the database (ADR-0079.R6, ADR-0079.R7).
Source: ADR-0038.R4.N2

R25. The dispatcher alone runs `SET LOCAL nativeflows.erasure_command_id` to the ID of the running command's `idempotency_record`, and only for a command registered as an erasure command. A consumer of an erasure command's event gets the marker only through the erasure scope of `audit.contract`, which sets it to the ID of the idempotency record that consumer wrote in its own transaction (ADR-0079.R7, ADR-0079.R7.N1). The trigger allows the update only when that setting is present and matches an idempotency record of an erasure command written in the same transaction, never any committed one, and no other column changes. `erasure_marker_valid()` in DS-05 is the check (ADR-0079.R7).
Source: ADR-0038.R4, ADR-0038.R4.N3

R26. Each module destroys its own tables in its consumer of the erasure commands' events, in the consumer's own transaction, inside an erasure scope opened through `audit.contract` with the originating command's ID. Each consumer's erasure scope writes its own idempotency record of the originating command's type in its transaction. `audit.contract` binds the scope to that command's subject and due classes, so no consumer rewrites rows of another subject or class under that ID.
Source: ADR-0038.R4.N2, ADR-0038.R4.N3

R27. The marker's record must belong to the current company (`nativeflows.company_id`) and to the company of the row being changed (`erasure_marker_valid(p_row)` in DS-05), so a marker of one company never validates under another. A record with no company (an installation-scoped subject such as a user account) is visible only under the setting `installation`, never under a company setting, so each consumer writes its own record in the company it erases.
Source: ADR-0038.R4.N3, ADR-0038.R4.N4

R28. Under the marker, a column may take only an erasure result of ADR-0079.R6, in every guard (`erasure_column_change_allowed`), and `clear_keys` removes only the keys its trigger lists.
Source: ADR-0038.R4.N3

R29. The database proves only that an erasure command's record of this company exists in this transaction. Who may run an erasure is the command layer's permission check (ADR-0079.R7).
Source: ADR-0038.R4.N4

R30. Erasure of a record also clears the keys of its `custom_values` whose `custom_field_definition.is_personal_data` is true, and masks the `audit_change` images of those keys. Values frozen in posted document versions follow the rule for personal data on posted documents (ADR-0079).
Source: ADR-0038.R4.N1

### Denial records

R31. Refusals that matter for safety leave coalesced denial records in `audit_denial`, written outside the refused transaction. The dispatcher classifies by error code, wherever the error was raised.
Source: ADR-0038.R5

R32. A command or query refused with one of these codes writes a denial record, in simulate and execute mode alike: `permission_denied`, `human_only`, `proposal_required`, `policy_denied`, `outbound_content_out_of_scope`, `segregation_of_duties`, `tool_not_allowed`, `tainted_read_out_of_scope`, `untrusted_read_not_allowed`, `tainted_run_not_allowed`, `automatic_send_not_allowed` and `origin_run_submit_not_allowed`, and the refusals only people meet: `approver_not_eligible`, `approver_is_submitter`, `grant_exceeds_own_rights`, `segregation_conflict` and `organization_self_change`. The list is complete.
Source: ADR-0038.R5, ADR-0038.R5.N1

R33. No denial record is written for `work_item_claim_lost` (a person took the item), `approval_already_given` or `approval_would_strand_stage` (preconditions), or `llm_routing_refused`, which the gateway records on the run step (ADR-0050.R19).
Source: ADR-0038.R5.N1

R34. The stop of a run after denials (ADR-0050.R33, ADR-0050.R55) counts every code of R32 returned to a run; the people-only codes cannot reach a run, whose tool list holds none of their commands. The CRM's reads outside a tainted run's scope use `tainted_read_out_of_scope` (ADR-0052.R34).
Source: ADR-0038.R5, ADR-0038.R5.N1

R35. Columns of `audit_denial`:
- company, command or query type, `mode`;
- actor columns, `agent_run_id`, `origin_agent_run_id`;
- `request_id`, `idempotency_key`, `subject_table`, `subject_id`, error code (no request hash: a plain hash of a small personal payload would survive erasure);
- for `policy_denied`, `policy_rule_id` and `policy_input_hash`, because the policy decision row is rolled back;
- `window_start`, `denial_count`, `first_at`, `last_at`, `trace_id`, and `recorded_at` (DDL).
Source: ADR-0038.R5, ADR-0038.R5.N2

R36. On the API path, the dispatcher writes the denial after the rollback through a small dedicated connection pool; when the pool is exhausted the denial is dropped with a metric. For internal callers (consumers, jobs) the worker buffers it and writes it after the delivery transaction ends; a worker crash loses its buffered denials.
Source: ADR-0038.R5

R37. Denials coalesce to one row per (company, actor, agent run, type, code, subject, `window_start`), with 10-minute windows. The writer upserts on a unique index over that key with `NULLS NOT DISTINCT`, adding to `denial_count` and moving `last_at`.
Source: ADR-0038.R5, ADR-0038.R5.N2

R38. A failed denial insert never fails the caller. It logs a structured error and raises a metric.
Source: ADR-0038.R5

R39. A denial record is the one effect of a simulation that persists (ADR-0008.R9).
Source: ADR-0038.R5

### Storage

R40. Audit and change records are protected by append-only triggers (the exception of R23 to R30 aside) and the generated company policy. The trigger on `audit_denial` allows only `denial_count` and `last_at` to change, and only upward.
Source: ADR-0038.R6, ADR-0038.R5.N2

R41. `audit_record` and `audit_change` are partitioned by month on `id` (ADR-0006.R22). The daily job of ADR-0022 creates partitions 3 months ahead, with a default partition. `audit_denial` is not partitioned, because its unique coalescing index cannot include `id`, and coalescing keeps it small.
Source: ADR-0038.R6

R42. Indexes of `audit_record`: on subject, actor, `agent_run_id`, and (`idempotency_key`, `actor_id`, `command_type`).
Source: ADR-0038.R6

R43. Nothing is dropped in Phase 1 (ADR-0002; ADR-0008.R19; ADR-0013.R15). `ExportCompanyData` includes the audit, change and denial records (R4).
Source: ADR-0038.R6

R44. Audit data is never deleted in Phase 1 (ADR-0002). Whether it may ever be dropped, and when, is the author's open question.
Source: ADR-0038.D0

### Queries

R45. The queries are `ListAuditRecord`; `GetAuditRecord`, with changes filtered by field class per (table, field), failing closed on unknown fields (ADR-0017.R10); and `ListAuditDenial`. Each has its own generated permission (ADR-0017.R4) and record scope from the stored scope dimensions.
Source: ADR-0038.R7

R46. These queries are on no agent tool list in Phase 1 (ADR-0008.R6; DS-32), and tainted runs never read audit data: reading denials would let an injected agent probe. `ListAgentRun`, `GetAgentRun` and every view over audit tables are on no agent tool list either (ADR-0050.R30, ADR-0050.R50).
Source: ADR-0038.R7

R47. A record whose subject is a document is shown only within that document's read owner scope (ADR-0054.R15).
Source: ADR-0038.R7.N1

### Invariant of executed commands

R48. `INV-89`: every idempotency record of an executed command (ADR-0008.R19), within its retention, has an audit record with the same key, actor and command type, or the same `batch_id` for batches. The company is compared null-safely, and idempotency records carry `company_id` (ADR-0008.R16). Area `platform`, first step 1. Group 80–89 is full: further safety and platform invariants use INV-200 to INV-299 (DS-16).
Source: ADR-0038.R8

### Duties assigned to DS-36

R49. Period state changes are recorded with `reason` (R11) and the approval through `policy_decision_id` (ADR-0012.R9).
Source: ADR-0038.R9

R50. Enabling unverified regime rules is audited as tracked changes of regime settings (R18; ADR-0016).
Source: ADR-0038.R9

R51. Exports and erasures write both an audit record and an entry in `personal_data_processing_log`, which `audit` owns (R54).
Source: ADR-0038.R9, ADR-0019.R11

R52. Breach handling: the signals raise the work item `personal_data_incident_suspected`, a person opens a work case of kind `personal_data_breach`, and the `personal_data_breach` row holds what an authority asks for (ADR-0079.R15, ADR-0079.R16). The notification deadline is the setting `data_protection.breach_notification_hours`, set per regime and company, for which a package may supply the regime value (ADR-0079.R16.N1, ADR-0079.R16.N2). Audit and denial records are its evidence. Who holds the data-protection role is assigned to DS-40 and is an open question.
Source: ADR-0038.R9, ADR-0038.R9.N1, ADR-0019.R11

R53. `nativeflows-check` against production (DS-16) may run, only with the read-only role, on a standby replica or with `statement_timeout`, and never with write rights.
Source: ADR-0038.R9

### Personal data processing log

R54. `personal_data_processing_log` is owned by `audit` (layer 2), because its writers sit in layers 2 to 5: the LLM gateway (DS-32), tax ID lookups, exports (ADR-0044) and erasure. It records every processing the law asks to log: personal fields sent to an LLM (DS-32; spec 17 logs this whether the routing switch is on or off), tax ID lookups of individuals and household businesses (ADR-0019.R18), exports and erasures (DS-36).
Source: ADR-0052.R26, ADR-0019.R11

R55. The log is written through `audit.contract.log_personal_data_processing`, in the caller's transaction. The gateway writes one entry per LLM call that sends personal values, before the call is made (ADR-0050.R10).
Source: ADR-0052.R26, ADR-0019.R11

R56. Columns of the log: `processing_kind` (`llm_send`, `tax_id_lookup`, `export`, `erasure`, `retention`), `subject_table` and `subject_id` (none for a whole-company export), `field_names`, `recipient` (provider and model, or lookup provider), `agent_run_id`, `audit_record_id`.
Source: ADR-0052.R26, ADR-0052.R26.N1

R57. `processing_kind` `retention` has one entry per subject and run of `RunPersonalDataRetention` (ADR-0079.R9; DS-35).
Source: ADR-0052.R26.N1

R58. The log is append-only. It holds IDs and field names, never values, so erasure keeps it. A trigger refuses every update and delete.
Source: ADR-0052.R26

### Telemetry

R59. Telemetry uses OpenTelemetry (ADR-0002). An allow-list keeps personal and business values out of it, and a CI test enforces the list (R65 to R69).
Source: ADR-0038.D0

R60. Spans are written for API requests, dispatched commands and queries, consumer deliveries (linked to the event's `trace_id`, ADR-0013.R14), job runs and LLM gateway calls (DS-32). Gateway and tool-call spans and the agent metrics are ADR-0050.R21.
Source: ADR-0038.R10

R61. Spans of agent runs, LLM calls, tool calls and automation executions use the OpenTelemetry GenAI attribute names where they exist, and carry the command request ID, agent run ID, work item ID and automation execution ID, never values (ADR-0059, X8).
Source: ADR-0038.R10.N1

R62. Metrics, exported as histograms and counters:
- latency by command and query type;
- error counts by code;
- `concurrent_update` and `timeout` counts;
- lock wait time per lock class;
- delivery lag and held deliveries per consumer;
- job durations;
- close-task staleness;
- invariant failures;
- dead tuples and autovacuum lag (ADR-0002);
- LLM tokens and cost per agent type (an amount exempt from R65 to R69, as an operational figure);
- analysis answers by outcome and badge, abstentions by code and model cost per answer, with codes as labels (ADR-0060.R26, ADR-0060.R27, ADR-0060.R32).
Source: ADR-0038.R10, ADR-0038.R12.N1

R63. Logs are structlog JSON with `trace_id` and `request_id`.
Source: ADR-0038.R10

R64. Decision records that name an artifact version, and the artifact tables, follow the retention of R43 and R44: never deleted in Phase 1; a regime may only lengthen it (ADR-0059.R23, ADR-0059.R26).
Source: ADR-0038.R10.N1

R65. No values in telemetry: span attributes and log fields come from an allow-list of keys (codes, types, counts, hashes). A structlog processor and a span processor drop everything else.
Source: ADR-0038.R11

R66. Exceptions are recorded in telemetry as type and error code only. SQL statement and parameter capture is off.
Source: ADR-0038.R11

R67. Metric labels hold no IDs; only low-cardinality codes.
Source: ADR-0038.R11

R68. A CI test seeds canary values in the scenario run and fails if any reaches emitted telemetry.
Source: ADR-0038.R11

R69. The allow-listed attributes of gateway spans are in ADR-0050.R21; prompts and outputs stay in `agent_run_step` only.
Source: ADR-0038.R11

R70. Telemetry goes through OTLP to a collector. The backend and the attachment scanner are new tool categories, chosen by ADR in DS-37, not from ADR-0002's list of tools not used. The byte-level media detection library is chosen by ADR at the first step that builds upload.
Source: ADR-0038.R12

R71. In Phase 1 the operations dashboard is the backend's, with panels generated from the metric names. Held deliveries and their `last_error` (ADR-0013.R8) are read through the delivery query, not the dashboard, because they carry values. A NativeFlows screen comes later.
Source: ADR-0038.R12

R72. Management dashboards are not the operations dashboard: they are saved analyses and KPI tiles of the analysis layer, run through `EvaluateAnalysisPlan` under the viewer's rights (ADR-0060).
Source: ADR-0038.R12.N1

### Attachments in the audit decision

R73. Attachments get a separate upload limit, a scan state machine driven by an event, and retention only for attachments that were ever linked to a posted accounting document; `attachments` states them (ADR-0038.R13 to ADR-0038.R15). The retention period is a legal rule the package supplies, flagged verified or unverified (ADR-0038.R15.N3); the strictness of scanning is decided (ADR-0038.R14.N5).
Source: ADR-0038.D0

### Personal data protection: the decision

R74. Personal data is protected by one mechanism for the whole core, not only on the path to an LLM. The core provides the mechanism; every period, deadline and legal basis is a package rule (ADR-0016), so the core holds no country's values (ADR-0053), except that retention periods and the breach notification deadline are set per company, with package defaults (ADR-0079.R9.N1, ADR-0079.R16.N1).
Source: ADR-0079.D0, ADR-0079.D0.N1

R75. The catalog `personal-data-fields.csv` lists every column that holds personal data. It is the single source for the access export, blocking and destruction, the LLM gateway labels, masking and the retention job.
Source: ADR-0079.D0

R76. A data subject whose purpose has ended is blocked: hidden from ordinary users and from all new processing, and kept only for the legal retention period. When that period ends, the subject's data is destroyed in place, in every store the catalog names, posted documents included.
Source: ADR-0079.D0

R77. Posted documents, document versions, the journal, audit rows and logs are rewritten only by the destruction path (`EraseDataSubject` on a request, `DestroyRetainedPersonalData` when a retention period ends), column by column as the catalog says, and every rewrite leaves an entry in an erasure journal that a restore re-applies.
Source: ADR-0079.D0

R78. Phase 1 has no per-subject encryption keys. Stores that cannot be rewritten are limited to backups, and backups expire.
Source: ADR-0079.D0

## Invariants

Sources are those of `invariants.csv`. The invariants of ADR-0079 are in chunk 2.

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-81` | day | `human_only_never_by_agent` (area `safety`): no audit row of a command registered `human_only` has actor kind agent, or integration while the interim holds. Flagged: ADR-0008.R2, may integrations execute `human_only` commands. | R1, R11; ADR-0008.R2 |
| `INV-86` | day | `proposal_targets_never_by_agent` (area `safety`): no audit row of a command whose effect class is `master_data_change` or that is registered `is_proposal_bound` has actor agent or an origin agent run. | R11; ADR-0029.R2, ADR-0029.R4 |
| `INV-89` | day | `executed_commands_audited` (area `platform`): every idempotency record of an executed command, within its retention, has an audit record with the same key, actor and command type, or the same `batch_id` for a batch; `company_id` is compared null-safely. | R48 |
| `INV-200` | day | `audit_rows_of_own_company` (area `platform`): an `audit_change` row and its `audit_record` have the same `company_id` (both null for an installation-scoped record), and a `change_proposal_execution_item` or `segregation_exception` names an `audit_record` of its own company. The keys stay single-column because `audit_record` has installation rows. The query is in `invariants.csv`. | R10, R17; ADR-0017.R19 |
| `INV-216` | day | `tainted_commands_draft_only` (area `safety`): every audit record of a command run by an agent run tainted at the record's `recorded_at`, or by a consumer whose origin run was tainted at the origin event's `recorded_at` (the instant INV-210 uses), has `is_draft_only` true as registered at the time, except `CompleteAgentRun`. | R11; ADR-0050.R26, ADR-0050.R55 |
| `INV-411` | run | `management_turnover_equals_report_turnover` (area `reporting`): for full scope, every range and every system account subtree, each ledger analysis measure equals ADR-0049.R6's turnover measure over the operational accounts mapped to that subtree for the same range and `special_periods` option (`change`, `debit_turnover` or `credit_turnover`), with `closing_entries=exclude` for the profit-and-loss measures and migration entries left out, in every regime. | Named by R2; it protects no rule of `audit` |

## UI annotations

None: see chunk 2, which carries the work item kind `personal_data_incident_suspected` and the work case kind `personal_data_breach` named by R52.

## Conflicts

CONFLICT ADR-0038.R4.N2: its clause that the trigger accepts any committed erasure command with that ID is superseded; ADR-0038.R4.N3 and ADR-0079.R7.N1 govern, and R25 requires an idempotency record written in the same transaction.
CONFLICT ADR-0038.R4: the rule names one erasure command and one transaction; ADR-0038.R4.N2 adds `DestroyRetainedPersonalData` and the consumers' erasure scopes, and ADR-0038.R4.N3 keeps the same-transaction check (R23, R25, R26); in a consumer the erasure scope, not the dispatcher's own command, sets the marker to the consumer's record (ADR-0079.R7.N1, R25).
CONFLICT ADR-0038.R5: the column `count` is named `denial_count` by ADR-0038.R5.N2 and the DDL, and the code list of the rule is replaced by the complete list of ADR-0038.R5.N1 (R32, R35, R37); R35 adds `recorded_at` from the DDL, for which no later ADR unit was found.
CONFLICT ADR-0038.R6: the denial trigger guards `denial_count`, not `count`, under the renaming of ADR-0038.R5.N2 (R40).
CONFLICT ADR-0038.R9: the breach notification procedure no longer waits for DS-40; ADR-0038.R9.N1 gives the mechanism of ADR-0079 rules 15 and 16 (R52).
CONFLICT ADR-0019.R11: its open question on the breach-notification process is settled by ADR-0038.R9.N1; only the holder of the data-protection role stays open (R52).
CONFLICT ADR-0038.D0: the flag on the strictness of attachment scanning is dropped by ADR-0038.R14.N5, and the retention period is package configuration under ADR-0038.R15.N3 (R73).
CONFLICT ADR-0038.R3: the DDL of `audit_change` also holds `recorded_at`, which the rule's column list lacks; R17 states the DDL's columns, no later ADR unit was found for it.

CONFLICT ADR-0038.R9.N1: its clause that breach deadlines are package rules is amended; ADR-0079.R16.N1 and ADR-0079.R16.N2 make the deadline the setting `data_protection.breach_notification_hours`, stated in R52 and R260.
CONFLICT ADR-0079.D0: its sentence that every period and deadline is a package rule is amended by ADR-0079.D0.N1 for retention periods and the breach notification deadline, which each company sets (R74; ADR-0079.R9.N1, ADR-0079.R16.N1).
CONFLICT ADR-0052.R30.N1: the reserved setting `crm.interaction_retention_days` is not registered; the retention class `crm_interaction` of `retention_rule` replaces it (ADR-0079.R9, R245), so R252 does not list it among the retention settings that stay.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0006.R22 | ref: ADR-0006.R22 |
| ADR-0006.R22.N1 | ref: ADR-0006.R22.N1 |
| ADR-0019.R10 | ref: ADR-0019.R10 |
| ADR-0019.R10.N1 | ref: ADR-0019.R10.N1 |
| ADR-0019.R10.N2 | ref: ADR-0019.R10.N2 |
| ADR-0019.R11 | R51, R52, R54, R55 |
| ADR-0027.R8 | R1-R4 |
| ADR-0027.R8.N1 | R2 |
| ADR-0029.R15 | R1 |
| ADR-0038.D0 | R44, R59, R73 |
| ADR-0038.R1 | R5-R9 |
| ADR-0038.R1.N1 | R7 |
| ADR-0038.R2 | R10-R15 |
| ADR-0038.R2.N1 | R13 |
| ADR-0038.R2.N2 | R11 |
| ADR-0038.R2.N3 | R16 |
| ADR-0038.R2.N4 | R12, R15 |
| ADR-0038.R3 | R17-R22 |
| ADR-0038.R4 | R23, R25 |
| ADR-0038.R4.N1 | R30 |
| ADR-0038.R4.N2 | R23, R24, R26 |
| ADR-0038.R4.N3 | R25-R28 |
| ADR-0038.R4.N4 | R27, R29 |
| ADR-0038.R5 | R31, R32, R34-R39 |
| ADR-0038.R5.N1 | R32-R34 |
| ADR-0038.R5.N2 | R35, R37, R40 |
| ADR-0038.R6 | R40-R43 |
| ADR-0038.R7 | R45, R46 |
| ADR-0038.R7.N1 | R47 |
| ADR-0038.R8 | R48 |
| ADR-0038.R9 | R49-R53 |
| ADR-0038.R9.N1 | R52 |
| ADR-0038.R10 | R60, R62, R63 |
| ADR-0038.R10.N1 | R61, R64 |
| ADR-0038.R11 | R65-R69 |
| ADR-0038.R12 | R70, R71 |
| ADR-0038.R12.N1 | R62, R72 |
| ADR-0040.R10 | ref: ADR-0040.R10 |
| ADR-0040.R13 | ref: ADR-0040.R13 |
| ADR-0040.R13.N1 | ref: ADR-0040.R13.N1 |
| ADR-0040.R13.N2 | ref: ADR-0040.R13.N2 |
| ADR-0041.R3.N2 | ref: ADR-0041.R3.N2 |
| ADR-0044.R17.N1 | ref: ADR-0044.R17.N1 |
| ADR-0050.R10 | ref: ADR-0050.R10 |
| ADR-0050.R50 | ref: ADR-0050.R50 |
| ADR-0052.R1 | ref: ADR-0052.R1 |
| ADR-0052.R1.N1 | ref: ADR-0052.R1.N1 |
| ADR-0052.R7 | ref: ADR-0052.R7 |
| ADR-0052.R25 | ref: ADR-0052.R25 |
| ADR-0052.R25.N1 | ref: ADR-0052.R25.N1 |
| ADR-0052.R25.N2 | ref: ADR-0052.R25.N2 |
| ADR-0052.R25.N3 | ref: ADR-0052.R25.N3 |
| ADR-0052.R26 | R54-R56, R58 |
| ADR-0052.R26.N1 | R56, R57 |
| ADR-0052.R30.N1 | ref: ADR-0052.R30.N1 |
| ADR-0058.R1 | ref: ADR-0058.R1 |
| ADR-0058.R12 | ref: ADR-0058.R12 |
| ADR-0067.R13 | ref: ADR-0067.R13 |
| ADR-0067.R20 | ref: ADR-0067.R20 |
| ADR-0074.R19 | ref: ADR-0074.R19 |
| ADR-0079.D0 | R74-R78 |
| ADR-0079.D0.N1 | R74 |
