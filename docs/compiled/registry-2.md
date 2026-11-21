Module: registry    Chunk: 2 of 5    Source ADRs: ADR-0029, ADR-0031, ADR-0040, ADR-0042, ADR-0043, ADR-0050
Build step(s): 1, 2, 3, 4, 5, 9    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `registry` compiled spec, chunk 2: dispatcher safety checks, canonical plan, check results, UI metadata and transport

## Purpose

This chunk states the part of `registry` law that the dispatcher applies around a command beyond the envelope: the proposal carrier, the policy points, run taint, the work item claim check and the policy floors. It also states the canonical plan and its hash, check results, the UI metadata the registry emits in the generated JSON Schemas, `ListAllowedCommand`, the review-then-confirm form protocol, the transport endpoints and live updates. The envelope, idempotency and the registry itself are in chunk 1; the settings registry and the operating presets are in the later chunks. The policy table, approval and taint clearing belong to `policy`; agent runs belong to `agent_runs`.

## Entities and tables

The rules of this chunk define no owned table; the rows of the owned tables stand in the chunks whose rules define them (`idempotency_record` in chunk 1, `list_variant` and `setting_value` in the later chunks).

Reads: `agent_run`, `agent_type_setting` (`agent_runs`, `agents`); `audit_record`, `audit_change` (`audit`); `policy_decision`, `change_proposal` (`policy`); `work_item` (`work`); `outbox_event` (`outbox`); `attachment` (`attachments`); `partner_item`, `custom_field_definition` (`master_data`); `document`, `document_version` (`documents`).

## Commands and queries

Authorization: the function leaf `general_access` (catalog `authorization-areas.csv`, module `registry`) holds `ListAllowedCommand` at `read`; the verb `List` is at level `read` in `authorization-verb-levels.csv`, and computed queries also need `read`.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ListAllowedCommand` | computed query; area `general_access` at `read`; its permission is in every role template; on no agent tool list in Phase 1 | subject table and ID | Returns `allowed_command` rows with `is_allowed` and, when false, the error code; writes no denial records (R235-R238) | none | `record_not_found` |
| `GetSessionContext` | installation-scoped query; needs only a valid credential, no permission; on no agent tool list | none stated | Returns the caller's own rights and session data (R245) | none | not stated |

Hand-written transport endpoints, not registry commands (R244): `POST /api/auth/sign-in`, `POST /api/auth/totp`, `POST /api/auth/sign-out`, `POST /api/auth/password`, `GET /api/auth/oidc/callback`, `GET /api/ui/stream`, `POST /api/ui/stream/subscriptions`.

Contract functions and hooks, not registry commands: `context.evaluate_policy(input)` (R208, R259); `agent_runs.contract.mark_run_tainted` (R214).

Commands of other modules that the rules of this chunk name: `CreateChangeProposal`, `UpdateAgentTypeSetting`, `ClaimWorkItem`, `AssignWorkItem`, `ListCustomFieldDefinitions`.

Error codes bound to no command of this chunk: `proposal_required`, `tool_not_allowed`, `origin_run_submit_not_allowed`, `plan_hash_mismatch`, `version_conflict`, `human_only`, `work_item_claim_lost`, `work_item_claimed`, `tainted_read_out_of_scope`, `request_too_large`, `post_review_required`.

## Rules

### Proposal carrier

R201. The dispatcher rejects an allowed-target command with `proposal_required` when it comes from an agent actor, or from any actor carrying an `origin_agent_run_id`, in both simulate and execute mode; the error's fix names `CreateChangeProposal`. `proposal_required` is step 3 of the dispatcher's check order, after the tool list and before permission (DS-04, dispatcher check order). An agent run never reaches it, because allowed-target commands are on no tool list (note on ADR-0050.R29), so its direct call gets `tool_not_allowed`; a consumer command carrying an origin run gets `proposal_required` whatever its permissions (`EC-56`). The consumer that executes an approved proposal carries no origin, because the human `Approve` reset it (ADR-0013.R2).
Source: ADR-0029.R4, .N2

R202. A human with the permission may run an allowed-target command directly, unless policy (DS-28) requires a proposal for humans too. Policy may make people propose through a deny-only `direct_master_data_change` rule (ADR-0043.R12).
Source: ADR-0029.R4, .N1

R203. A change of a partner's bank account always goes through a proposal, also when a human starts it, approved by a human who wrote no version of it. This holds for every company, the small-company mode included, and is a policy floor (R258, the bank account floor).
Source: ADR-0029.R4

R204. Human-run DS-21 import batches are outside the proposal carrier.
Source: ADR-0029.R4

R205. A requirement for a proposal that depends on the payload is the handler's. The consumer executing an approved proposal passes `change_proposal_execution` (the proposal's ID and version) in the handler context, and the handler returns `proposal_required` without it, for people too (DS-04 handler context; note on ADR-0054.R2). So a person's direct `UpdateAgentTypeSetting` that sets `assisted` returns `proposal_required`: promotion of an agent type always goes through a proposal (ADR-0050.R14).
Source: ADR-0029.R4, .N2

### Policy points

R206. The dispatcher evaluates policy (DS-28) once per command at the policy points, and the handler stores the `policy_decision`. The policy points are:
- `Submit` of any document, including change proposals;
- `Post` from `draft`;
- `Issue` from `draft`, always (ADR-0028.R7);
- `Issue` from `approved` (ADR-0053.R8) and `Post` of an approved document, only when its `policy_input_hash` changed (ADR-0028.R14) or its actor is of another kind than its decision's (ADR-0043.R9; ADR-0055.R11).
Source: ADR-0029.R6, .N1, .N2

R207. `Submit` from any actor carrying an origin agent run is refused before policy with `origin_run_submit_not_allowed` (step 3 of the dispatcher check order, DS-04); the note on proposals at ADR-0029.R3 holds for every document.
Source: ADR-0029.R6.N2

R208. The policy points of ADR-0029.R6 stand in place of "before a handler that posts" in ADR-0008.R5 and of the separate statement of ADR-0009.R11. A replayed command (ADR-0008.R18) does not evaluate policy again. A handler whose policy inputs are read under locks calls the hook through `context.evaluate_policy(input)` after taking them, for example the credit check; such commands are registered `is_policy_in_handler`, and the dispatcher skips its own evaluation and asserts that the hook ran exactly once (ADR-0030.R7).
Source: ADR-0029.R6

### Run taint

R209. `is_untrusted` is a schema attribute separate from data labels (spec 17). It is set on fields filled from outside content: e-mail bodies, supplier e-invoice free text, bank statement texts and `interaction_summary` (ADR-0019.R20).
Source: ADR-0029.R10

R210. A run becomes tainted when the query layer (DS-33) returns to it any of: a non-null `is_untrusted` field; a row whose effective `is_tainted` is true (a row of an effectively tainted version); a work item with `is_tainted` (a work item created from a tainted event); the content of an attachment whose source kind is outside content. `agent_run.tainted_at` is set once and never cleared, with its source columns; it is set at the start of the run (ADR-0050.R15) or by the dispatcher's query path just before it returns such a result. A generated file (attachment source kind `generated`) whose rendered instance held a non-null `is_untrusted` field carries `contains_untrusted`; returning its content to a run taints the run as an attachment from outside content does, with `taint_source_kind` `untrusted_field` and source table `attachment` (ADR-0049.R28).
Source: ADR-0029.R10, ADR-0050.R25, ADR-0050.R25.N1

R211. DS-33 views omit `is_untrusted` fields unless they are asked for, so listing documents does not taint a run. Master data changed by an approved proposal is not tainted, because the human approval is the trust boundary. Work items carry `is_tainted` as an OR over their raises (ADR-0042.R5).
Source: ADR-0029.R10, .N1

R212. Value trust: an extraction field's normalized value is not untrusted when it fits its type's closed shape and passed every rule of the extraction's latest rule run from a deterministic reader, or a person confirmed it and its shape passed. Its raw text and evidence are always untrusted. Free text, URLs, e-mails, phones, codes and units that resolve to no record, vision values before confirmation, and every field of an extraction with a failed or mismatched signature or with suspected hidden text are untrusted. Trust is computed when the field is read, never stored on it, and means that the value carries no instruction, not that it is true. This is a reading of spec 03 rule 1, interim until the author answers (ADR-0057.R17).
Source: ADR-0029.R10.N2

R213. The dispatcher applies run taint to every query result returned to a run: views, module queries and the results and check details of commands, using the result model's field attributes. It does not depend on what the agent asks for.
Source: ADR-0029.R10, ADR-0050.R25

R214. Commit first: the dispatcher calls `agent_runs.contract.mark_run_tainted` in its own committed transaction, which commits `agent_run.tainted_at`, before it returns the result. If that commit fails, the result is not returned. So every later command of the run starts after `tainted_at`, and the `recorded_at` comparisons of `INV-88` hold.
Source: ADR-0029.R10, ADR-0050.R25

R215. Inputs after taint: from `tainted_at` on, the runtime refuses with `tainted_read_out_of_scope`, before the gateway call or the dispatch, a context item or a command input whose recorded source row (ADR-0050.R8; `context_refs`, `request_refs`) is outside the tainted read scope (ADR-0050.R27), also when the row was read before the taint. Only the runtime knows that provenance. A row reached through recorded provenance from a row in scope is in scope, for example the item behind the `item_id` of the partner's `partner_item` row.
Source: ADR-0050.R25

R216. As a second line, the dispatcher checks every reference-typed ID in a tainted run's payload whose table has a partner or import batch scope column, or is a document, against the run's scope and its drafts (ADR-0050.R27). References to tables without such a column (items, units) are covered by the runtime's provenance check. The command envelope of ADR-0008 does not change.
Source: ADR-0050.R25

R217. A deterministic aggregate (a sum, count or balance) computed over rows that include tainted versions does not taint the run: taint guards against untrusted text, and an aggregate carries none. Individual rows of tainted versions still taint. This reading is confirmed: it is reading (g) of the readings of ADR-0050.R27 that ADR-0063.R16.N1 confirms.
Source: ADR-0050.R25

### Canonical plan and plan hash

R218. The canonical plan (ADR-0008.R12; DS-04 "Canonical plan for hashing") has the keys `journal_lines`, `stock_movements`, `document_versions`, `record_versions`, `result` and `checks` (R228).
Source: ADR-0031.R1

R219. `document_versions` holds one entry per document version the command writes: the document ID, `version` and the version's canonical `content` (ADR-0009.R9). A pending version of a change order counts (ADR-0028.R4).
Source: ADR-0031.R1

R220. `record_versions` holds one entry per record written by an allowed-target command (ADR-0029.R2): table, ID and the record's canonical fields after the write.
Source: ADR-0031.R1

R221. Both lists are subject to DS-04 steps 2–3: IDs created in the run become `new:<table>:<n>`, and `DocumentNumber` and `SystemInstant` values are removed. They contain content, not precomputed hashes; the stored `version_hash` and `expected_version` remain hashes of stored values and are a different thing. Both lists are in the order the handler wrote the rows.
Source: ADR-0031.R1

R222. Results listed like events stay outside the hash (warehouse task proposals, ADR-0023.R11; planning run results, ADR-0024.R17). Tasks, reservations, `demand_supply_line` rows, open items and events are not in the plan either.
Source: ADR-0031.R1

R223. The response's `plan` carries `document_versions` and `record_versions`, so an agent sees the prices, discounts and taxes that execute will commit. As for journal lines, they are filtered by the actor's field classes, and generated IDs are real IDs outside the hash. Returning an `is_untrusted` field taints the run (R210). The uniform two-call protocol stays.
Source: ADR-0031.R2

R224. A concurrent edit of the same draft usually gives `version_conflict` first (ADR-0009.R10). When it gives `plan_hash_mismatch`, the agent reviews the returned plan and resends with its hash (ADR-0008.R13), or reads again and simulates again.
Source: ADR-0031.R3

R225. DS-16 holds a hash test: a batch whose first item creates a record with a server-generated ID and whose second item refers to it gives equal hashes in simulate and execute.
Source: ADR-0031.R4

### Check results

R226. Command responses carry `checks`: a list of `{code, message, rule, field, details}` from the check-result catalog (DS-04), in simulate and execute and per batch item. `message` is English, as for errors. `details` are filtered by field class.
Source: ADR-0040.R10

R227. Checks are part of the stored response and batch summary (ADR-0008.R16 to ADR-0008.R21), and `audit_record` keeps their codes in `check_codes` (ADR-0038.R2). The UI shows them in the plan panel and next to their field, and agents read the same list.
Source: ADR-0040.R10

R228. The canonical plan key `checks` is the list of `[code, field]` pairs, with a null field as `""`, duplicates removed, sorted by code then field (DS-04 step 4; ADR-0031.R1). So `plan_hash` covers them, and a check that appears between review and execution forces a second review.
Source: ADR-0040.R10

R229. The registry declares `is_hashed` per check code, true by default. It is false for checks that come from side information that is itself unhashed, so they cannot cause the mismatch that R222 avoids; those checks are returned in `checks` but left out of the hashed pairs:
- warehouse task proposals and bin contents that concurrent warehouse work changes (ADR-0023.R11): `capacity_not_checked`, `bin_capacity_exceeded`, `mixed_stock_not_allowed`, `no_pickable_stock`;
- planning and forecast results (ADR-0024.R17): `planning_parameter_missing`, `forecast_history_insufficient`.
Source: ADR-0040.R10

### UI metadata in the generated schemas

R230. The registry emits UI metadata in the generated JSON Schemas as annotations. Derived from the model:
- `x-nativeflows-widget`, from the field's type: Amount, Quantity, UnitPrice, ExchangeRate, Percent, BusinessDate, enums, references, and `State`;
- `x-nativeflows-field-class` (ADR-0017.R10, emitted by ADR-0022.R17);
- `x-nativeflows-untrusted` (ADR-0029);
- `x-nativeflows-ref`, the referenced table of a `Ref[<table>]`;
- `x-nativeflows-scale-from`, the sibling currency or unit field; `scale-from` is required on money and quantity.
Source: ADR-0040.R4, .N2

R231. Optional hints in `json_schema_extra`:
- `x-nativeflows-group` and `x-nativeflows-order`;
- `x-nativeflows-line-columns` for line arrays, with `editor`;
- `x-nativeflows-hidden-when` and `x-nativeflows-read-only-when`: simple conditions on other fields of the same payload, which may also name the subject's `state`;
- `x-nativeflows-lookup`: the `List<Noun>` query with a `search` filter and the result fields to show, with `depends_on`;
- `x-nativeflows-list-defaults` on a `List<Noun>` result model: default columns, sort and filters, and declared `variants`.
Source: ADR-0040.R4, .N2

R232. The annotation vocabulary is closed. Besides the keys of R230, R231 and R233 it holds the keys `importance`, `default-from`, `scan`, `ai-fillable`, `floorplan`, `title`, `header-facets`, `actions`, `links`, `search` and `assist`. Every key has one renderer, and a key outside the vocabulary fails `check` (ADR-0077.R8 to ADR-0077.R12).
Source: ADR-0040.R4.N2

R233. The annotation `x-nativeflows-custom-values` names the table whose company-defined fields the renderer reads through `ListCustomFieldDefinitions`; user-defined fields (without tables) appear in the same schemas (ADR-0074.R8 to ADR-0074.R11).
Source: ADR-0040.R4.N1

R234. Labels and help come from i18n keys (ADR-0040.R14), not from the schema. Nothing is maintained per screen in the frontend. User-defined fields (after Phase 1) appear through the same schemas, so the renderer never hard-codes field lists.
Source: ADR-0040.R4

### `ListAllowedCommand`

R235. `ListAllowedCommand` (subject table and ID) is a computed query, an exception to ADR-0004.R21 as in ADR-0015.R14. It returns `allowed_command` rows: each command applicable to the subject, with `is_allowed` and, when false, the error code the command would return. Applicability comes from registry declarations the dispatcher itself uses: each command's `subject_table` and `allowed_states` (notes on ADR-0008.R1 and on ADR-0009.R5, whose `invalid_state_transition` reads the same declaration).
Source: ADR-0040.R8

R236. Its checks are: the caller's permission, `human_only`, `segregation_of_duties` for `Approve` (ADR-0017.R16), a pending change (ADR-0028), owner scope, delegations, segregation pairs and, for `Approve`, stage eligibility and the stranded-stage check (ADR-0054.R22; ADR-0055.R7). A subject outside the caller's record scope returns `record_not_found` (ADR-0008.R5).
Source: ADR-0040.R8, .N1

R237. The answer is advisory: it returns the subject's version and writes no denial records. Policy outcomes that need a simulation come back from the command itself. Its permission is in every role template. In Phase 1 it is people-only and on no agent tool list (ADR-0050.R30), because a denial-free probe of permissions with reasons would weaken the denial signal of ADR-0038.R5; agents plan from their tool list and simulate mode (ADR-0050.R34).
Source: ADR-0040.R8

R238. A DS-16 property test checks that `is_allowed: true` implies that simulation never fails with `invalid_state_transition`, `permission_denied`, `human_only`, `segregation_of_duties` or `change_pending`.
Source: ADR-0040.R8

### Review and confirm

R239. A form submits by Review, then Confirm, with one envelope and one idempotency key per intent (ADR-0008.R13). Review (`Ctrl+Enter`) sends `mode: simulate` with `include_canonical_plan: true` and shows the plan panel:
- journal lines and stock movements, filtered by field class;
- document and record versions;
- events;
- side information such as warehouse task proposals;
- check results;
- the policy outcome when the plan carries one (approval or confirmation required, ADR-0029.R7).
Source: ADR-0040.R9

R240. Confirm (`Ctrl+Enter` again, or the button naming the command, such as "Post") sends `mode: execute` with `expected_plan_hash`. On `plan_hash_mismatch` the panel shows the new plan and its differences from the reviewed one, computed on the canonical plans of both (tokenized IDs, no numbers or system instants; ADR-0008.R12), and asks again. A retryable error is retried with the same key, honoring `retry_after_seconds`. After execution the panel shows the assigned number and `recorded_at`.
Source: ADR-0040.R9

R241. `include_canonical_plan` is an optional envelope field (DS-04; a note on ADR-0008.R7). Like `mode`, it is left out of the request hash of ADR-0008.R15. The response then carries `canonical_plan`, filtered by field class like the plan. `plan_hash_mismatch` carries the new canonical plan in `details`. In a batch, each item carries its canonical plan when `include_plan` and `include_canonical_plan` are both set.
Source: ADR-0040.R9

R242. Under the company setting `ui.post_review` at `on_exceptions`, the Post button sends Review and, when the response's `review_reasons` is empty, Confirm at once with `is_review_skipped: true`; otherwise, or on `post_review_required`, the plan panel opens as in R239 with the reasons listed. The client computes no reason itself (ADR-0040.R2). Under the default `always`, R239 to R241 apply unchanged (ADR-0067.R11 to ADR-0067.R13).
Source: ADR-0040.R9.N1

### Transport

R243. Sessions are server-side (ADR-0017.R2), in a cookie `__Host-nativeflows_session` (`Secure`, `HttpOnly`, `SameSite=Lax`). Every state-changing request from a cookie session carries the header `X-NativeFlows-CSRF` with the session's token, and its `Origin` must be the installation's. Integrations and agents use bearer tokens and need neither. The client gets the CSRF token from the sign-in response and from `GetSessionContext`.
Source: ADR-0040.R12

R244. The transport endpoints, owned by `permissions` and `registry`, are the only hand-written ones besides the attachment upload: `POST /api/auth/sign-in`, `POST /api/auth/totp`, `POST /api/auth/sign-out`, `GET /api/auth/oidc/callback`, `GET /api/ui/stream`, `POST /api/ui/stream/subscriptions`, and `POST /api/auth/password`, which consumes a one-time reset token or changes a password (ADR-0054.R3, ADR-0054.R4). ADR-0008.R6 and ADR-0038.R13 carry a note on them.
Source: ADR-0040.R12, .N1

R245. `GetSessionContext` is installation-scoped and needs only a valid credential, not a permission; this is an exception to ADR-0017.R8. It returns only the caller's own rights, and it is on no agent tool list. After sign-in it returns: the user; their companies with role assignments, permissions, field classes and record scope; their language and time zone; the installation's environment; owner scopes, the delegations in force and the user's pending invitations (ADR-0054.R22). The menu, palette and company switch read it.
Source: ADR-0040.R12, .N1

R246. The annotated JSON Schemas and the i18n catalogs (core and every package's terminology) are generated into `frontend/src/generated/`, which is possible because packages ship with the build (ADR-0016.R3). They are loaded per screen and per language by dynamic import, so the shell stays within its size budget (ADR-0040.R17).
Source: ADR-0040.R12

### Live updates

R247. Live updates (ADR-0013.R12): when the dispatcher inserts an event (ADR-0013.R6), it also sends `pg_notify('nativeflows_ui', header)` in the same transaction. The notification goes out only on commit and never from a simulation. This header stands in place of the consumer that ADR-0013.R12 foresaw, so there are no delivery rows, pausing or retention to manage.
Source: ADR-0040.R13

R248. The header holds: event ID, event type, company, the subject's root (`subject_table` and `subject_id`, with child subjects resolved to their document), `subject_sequence`, the subject's record-scope dimensions as the dispatcher's scope resolver computes them (the same values `audit_record` stores, ADR-0038.R2), and the subject document's `owner_employee_id` and `created_by_user_id` (IDs). It carries no payload values.
Source: ADR-0040.R13, .N1

R249. Each web process holds one dedicated `LISTEN` connection outside the pool; it reads no table. Because any database role can listen on a channel, headers carry only IDs, and the read-only query layer (DS-33) accepts nothing but `SELECT`. The query builder emits one `SELECT` per statement, and `EXECUTE` on `pg_notify` is revoked from `PUBLIC` and granted to `nativeflows_app` and `nativeflows_worker` (ADR-0050.R44).
Source: ADR-0040.R13

R250. A signed-in tab opens `GET /api/ui/stream` (Server-Sent Events over HTTP/2 through Caddy, heartbeat every 25 seconds, no buffering). Its first message gives a random `stream_id`. The tab posts the whole set of subjects and nouns it has open to `/api/ui/stream/subscriptions` with that `stream_id`, at most 100 entries; a list screen subscribes to its noun, not to its rows. A set whose relayed payload would exceed 7,500 bytes is rejected with `request_too_large`, keeping it under PostgreSQL's `NOTIFY` limit. A post replaces the stream's set, so it is idempotent.
Source: ADR-0040.R13

R251. The subscription post may reach another web process, so the receiving process checks that the stream belongs to the session and relays `{stream_id, subscriptions}` with `pg_notify('nativeflows_ui_sub', …)` (IDs only). Every process listens there, and the one holding the stream applies it. After a reconnect the tab gets a new `stream_id` and posts its set again.
Source: ADR-0040.R13

R252. The web process forwards a header only if all of these hold:
- it matches a subscription;
- the session still holds `Get<Noun>` or `List<Noun>` for the subject's table, checked against cached assignments that expire within 30 seconds;
- the subject's scope dimensions are in the session's record scope;
- the session's read owner scope reaches the document, checked against the same cached assignments and organization data (ADR-0054.R15).
Installation-scoped events (no company) go only to installation-scoped sessions. Revoking a session closes its stream.
Source: ADR-0040.R13, .N1

R253. A `MessageCreated` header (subject: the message) is resolved to its conversation and forwarded only to sessions whose user may read that conversation now, through messaging's registered visibility function, and a `NotificationCreated` header only to its recipient's sessions. No tab subscribes to the noun `message`; headers carry IDs, never text (ADR-0076.R8).
Source: ADR-0040.R13.N2

R254. The client invalidates the subject's TanStack Query keys and refetches through queries, so permissions and field classes apply on the read; it coalesces headers per query key, for 300 ms. Delivery is best effort; after a reconnect, the client refetches what is open.
Source: ADR-0040.R13

### Work item claims of agent runs

R255. Precedence and exclusion (Principle 8). A person's `ClaimWorkItem` on an item an agent run holds takes the claim; the dispatcher then rejects every later command of that run with `work_item_claim_lost`, so the agent stops and never works at the same time as a person. Taking a claim from another person needs `AssignWorkItem`. An agent run cannot take a held claim. A held claim makes a second claimant fail with `work_item_claimed`.
Source: ADR-0042.R11

R256. The run's work item is bound on `agent_run` when the run starts (DS-32). The dispatcher derives it from the credential, never from the request (ADR-0008.R8), and rejects any command of the run with `work_item_claim_lost` once the claim is gone. Shadow runs bind their work item without a claim, and the dispatcher skips the claim check for them because they only simulate (ADR-0050.R14).
Source: ADR-0042.R11

R257. A run a person or a schedule starts without an exception creates and claims an `agent_task` item for itself at its start, owned by the person the run acts for. No agent type may declare `agent_task`, so wake-ups cannot loop.
Source: ADR-0042.R11

### Policy floors

R258. The dispatcher applies these floors around the policy table:
- floor 1: permission, record scope and `human_only` commands, before anything (ADR-0008.R5);
- floor 2: segregation of duties for `Approve` (ADR-0017.R16);
- floor 3, taint: on an effectively tainted version (ADR-0029.R8 to ADR-0029.R11), a non-human `submit` gets at least the lowest rank, and a non-human `post` or `issue` gets `human_post` (`INV-84`);
- floor 4, agents only draft (ADR-0003.R8): an agent's `post` or `issue` gets `human_post`;
- floor 5, an LLM never contributes to an auto-post (spec 03 rule 1): a `system` posting of a document with a version written by an agent run, or carrying an origin agent run, gets `human_post`;
- floor 6: corrections (`correction_of_id`, ADR-0009.R23) by a non-human get `human_post` (interim, open question);
- floor 7, change proposals: their `submit` always gets at least the lowest rank (ADR-0043.R12);
- floor 8, submit of a type with no posting step (non-posting documents such as orders and production orders, ADR-0009.R6): a `human_post` from a non-human actor becomes the lowest rank, because human-only means nothing there;
- floor 9: reversals of posted documents and period closing are `human_only` commands with no policy step (ADR-0009.R18; open question);
- the bank account floor: a change of a partner's bank account always goes through a change proposal approved by a person other than its writer, in every company, the small-company mode included (R203; ADR-0054.R20); no policy rule or setting relaxes it.
Source: ADR-0043.R9, .N3

R259. For commands registered `is_policy_in_handler`, the floors run inside `context.evaluate_policy`. The dispatcher checks floors 3 to 6 on every `Post` and `Issue` command, including `Post` of an approved document, which asks no policy (ADR-0009.R11); a violation gives `human_only`. A `Post` of an approved document by an actor of another kind than the one its decision was made for is also a policy point (R206). So a document a person submitted is not posted by a non-human without its own decision. For an e-invoiced document, floors 3 to 6 and the actor-kind policy point are applied at `Issue`, and not again at the completion `Post` (note on ADR-0043.R5), which `system` may run although `Post<CorrectionType>` is `human_only` (note on ADR-0027.R12).
Source: ADR-0043.R9, .N1

R260. For corrections by non-humans the one rule is the registry flag of ADR-0009.R23: `Post<CorrectionType>` and `Issue<CorrectionType>` are `human_only`, refused to agents and, while the interim holds, integrations at step 3 of the check order (DS-04, dispatcher check order); `system` runs `Post<CorrectionType>` only as the completion of R259. Floor 6 and the tool list reach no further case; floor 6 stays as a defensive check with the same reach.
Source: ADR-0043.R9.N1

R261. A `system` posting whose gateway decision is `auto_post` with every tainted-draft condition met satisfies floors 3 and 5 through the gateway and is `allowed` with confirmation (author's decision of 2026-11-16; ADR-0065.R10 to ADR-0065.R12). The conditions are: `auto_post.allow_tainted_drafts` and `auto_post.<document_type>.allow_tainted` (the key of the document's `document_type`) true, the drafting agent type `active` for the document type, the checker passed, and every amount and quantity `trusted` or `cross_checked` while verification is required. In every other case floors 3 and 5 apply unchanged; floors 4 and 6 are untouched, and the wording of spec 03 rule 1 is the author's (open question).
Source: ADR-0043.R9.N2

## Invariants

| Invariant | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-86` | day | No audit row of a command whose effect class is `master_data_change` or that is registered `is_proposal_bound` has actor `agent` or an origin agent run. | R201 |
| `INV-205` | day | No command of an agent run bound to a work item is audited after a person claimed that item. | R255, R256 |
| `INV-210` | day | Every outbox event, work item raise and work item note written by an agent run tainted at the row's `recorded_at` (`tainted_at` at or before it, the instant `INV-88` uses), or by a consumer whose origin run was tainted at the origin event's `recorded_at`, has `is_tainted` true. | R210, R214 |

`INV-84` (floor 3 of R258) and `INV-88` (R214) are cited, not written in this module: their catalog sources (ADR-0029.R8, ADR-0029.R9, ADR-0029.R11, ADR-0065.R12) are rules of `documents` and `policy`.

## Edge cases

| Edge case | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-56` | `bank_account_change_by_email`: an e-mail asks to change a supplier's bank account; the agent run's direct call is rejected with `tool_not_allowed` (the command is on no tool list), a consumer command carrying the run as origin with `proposal_required`, and a change proposal approved by a second human succeeds (DS-04 dispatcher check order). | `must_reject:tool_not_allowed`, `must_reject:proposal_required`, `must_succeed` | R201, R203 |
| `EC-216` | `tainted_capture_draft_policy_auto_approve`: a policy rule would let a tainted capture draft through without a person; floor 3 makes it `human_post`. | `must_succeed` | R258 |
| `EC-319` | `payee_change_by_proposal`: an agent that changes a supplier's payee relationship directly is refused with `proposal_required`; its proposal executes after a person approves. | `must_reject:proposal_required`, `must_succeed` | R201, R202 |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `auto_post.allow_tainted_drafts` | boolean | company | `false` | R261 |
| `auto_post.<document_type>.allow_tainted` | boolean | company | `false` | R261 |

`ui.post_review` (R242) has its row in chunk 5.

Reads: `agents.installation_daily_max_cost`, `agents.company_daily_max_cost`, `agents.internal_reserve_share` (`agents`; ADR-0050.R22).

## Conflicts

CONFLICT ADR-0029.R4: an agent run's direct call gets `tool_not_allowed` before `proposal_required` is reached, and the payload-dependent requirement is the handler's; governed by ADR-0029.R4.N2 (R201, R205).
CONFLICT ADR-0029.R4: the bank account sentence drops its marks "interim, flagged", because the author's delegation of 2026-11-19 confirmed it as a policy floor; governed by ADR-0043.R9.N3 (R203, R258).
CONFLICT ADR-0029.R6: `Issue` from `approved` is a policy point only on a changed `policy_input_hash` or another actor kind, and `Issue` from `draft` always; governed by ADR-0029.R6.N2 (R206).
CONFLICT ADR-0029.R10: the list of results that taint a run is stated in the later wording of ADR-0050.R25 (non-null field, effective `is_tainted`, work item with `is_tainted`, attachment source kind), in R210.
CONFLICT ADR-0050.R25: the mark "flagged for the author (open question)" on aggregates that do not taint is dropped; ADR-0063.R16.N1 confirms the readings (a) to (r) of ADR-0050.R27, and reading (g) is this one (R217).
CONFLICT ADR-0040.R8: the "open question" on keeping `ListAllowedCommand` off agent tool lists is decided by the later ADR-0050.R30, which puts it on the list of commands and queries never on a tool list (R237).
CONFLICT ADR-0040.R4: the annotation vocabulary is closed, gains keys and makes `scale-from` required on money and quantity; governed by ADR-0040.R4.N2 (R230 to R232).
CONFLICT ADR-0040.R12: the list of hand-written endpoints gains `POST /api/auth/password` and `GetSessionContext` returns more; governed by ADR-0040.R12.N1 (R244, R245).
CONFLICT ADR-0043.R9: floors 3 to 6 are not applied again at the completion `Post` of an e-invoiced document; governed by ADR-0043.R9.N1 (R259).
CONFLICT ADR-0043.R9.N2: a `system` posting with gateway decision `auto_post` satisfies floors 3 and 5 through the gateway under the tainted-draft conditions; governed by ADR-0065.R10 as stated in R261.
CONFLICT ADR-0043.R9.N3: the floors gain the bank account floor, which no policy rule or setting relaxes; this note governs the list of ADR-0043.R9 (R258).

## Trace

| Source | Where |
| --- | --- |
| ADR-0029.R4 | R201-R205 |
| ADR-0029.R4.N1 | R202 |
| ADR-0029.R4.N2 | R201, R205 |
| ADR-0029.R6 | R206, R208 |
| ADR-0029.R6.N1 | R206 |
| ADR-0029.R6.N2 | R206, R207 |
| ADR-0029.R10 | R209-R211, R213, R214 |
| ADR-0029.R10.N1 | R211 |
| ADR-0029.R10.N2 | R212 |
| ADR-0031.R1 | R218-R222 |
| ADR-0031.R2 | R223 |
| ADR-0031.R3 | R224 |
| ADR-0031.R4 | R225 |
| ADR-0038.R4 | ref: ADR-0038.R4 |
| ADR-0038.R4.N1 | ref: ADR-0038.R4.N1 |
| ADR-0038.R4.N2 | ref: ADR-0038.R4.N2 |
| ADR-0038.R4.N3 | ref: ADR-0038.R4.N3 |
| ADR-0038.R4.N4 | ref: ADR-0038.R4.N4 |
| ADR-0040.R4 | R230, R231, R234 |
| ADR-0040.R4.N1 | R233 |
| ADR-0040.R4.N2 | R230-R232 |
| ADR-0040.R6.N6 | ref: ADR-0040.R6.N6 |
| ADR-0040.R8 | R235-R238 |
| ADR-0040.R8.N1 | R236 |
| ADR-0040.R9 | R239-R241 |
| ADR-0040.R9.N1 | R242 |
| ADR-0040.R10 | R226-R229 |
| ADR-0040.R12 | R243-R246 |
| ADR-0040.R12.N1 | R244, R245 |
| ADR-0040.R13 | R247-R252, R254 |
| ADR-0040.R13.N1 | R248, R252 |
| ADR-0040.R13.N2 | R253 |
| ADR-0042.R11 | R255-R257 |
| ADR-0043.R9 | R258, R259 |
| ADR-0043.R9.N1 | R259, R260 |
| ADR-0043.R9.N2 | R261 |
| ADR-0043.R9.N3 | R258 |
| ADR-0050.R14.N4 | ref: ADR-0050.R14.N4 |
| ADR-0050.R22.N2 | ref: ADR-0050.R22.N2 |
| ADR-0050.R22.N4 | ref: ADR-0050.R22.N4 |
| ADR-0050.R25 | R210, R213-R217 |
| ADR-0050.R25.N1 | R210 |
