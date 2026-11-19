# ADR-0040: UI architecture and schema-driven renderer

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-30. Related decisions: D8, D14. Principles 1, 2, 6, 7, 10, 13. ADR-0002, ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0013, ADR-0015, ADR-0016, ADR-0017, ADR-0022, ADR-0023, ADR-0024, ADR-0028, ADR-0029, ADR-0031, ADR-0034, ADR-0038; spec 02, 04, 10, 11, 15.

## Decision

The web UI is one more client of the command and query layer. It writes data only through registered commands and reads only through registered queries.

**Screens.** Almost every screen is rendered from the registry: lists from `List<Noun>` queries, record views from `Get<Noun>`, and forms from command schemas. Their small UI metadata travels as named `x-nativeflows-*` annotations in the generated JSON Schemas. A form shows the server's plan and check results before anything executes, and the client never computes money or quantities itself. The six hand-built entry screens of step 9 reuse the same components with their own layout and the AG Grid line editor.

**Transport.**
- **Sessions:** cookie sessions with a CSRF token.
- **Bootstrap:** a session query tells the client what the user may see.
- **Schemas and catalogs:** built into the frontend and loaded per screen.
- **Live updates:** the outbox's own transaction sends a small header through PostgreSQL `NOTIFY`, and web processes forward it over Server-Sent Events. Each header goes only to sessions that subscribed to the subject and may read it, and the client refetches.

**Registry additions:**
- a `checks` field in command responses, part of `plan_hash` by code and field;
- the computed query `ListAllowedCommand`, for people only in Phase 1;
- the session query `GetSessionContext`.

**Renderer v1** (step 1) covers sign-in, navigation, lists, record views, forms with line tables, simulate, plan, execute, errors, checks, live updates, English and Vietnamese, without AG Grid.

### Rules

**Client principles**

1. The UI calls only registered commands and queries through the generated client (ADR-0008 rule 6). Exceptions are the few transport endpoints of rule 12.
   - **No extra powers.** No screen gets a command, field or capability that agents lack.
   - **Screen needs.** A screen need the API cannot meet is solved in the API for every client, as a B2 change where it alters a command ([steps-5-9.md](../runbook/steps-5-9.md), step 9 fallback).
   - **The live stream** is a signal to refetch. It carries no data that a query would not give.
2. The client does no business arithmetic. Totals, taxes, prices, conversions and stock effects come from simulation; the client only formats them.
   - **Decimals.** They travel as canonical decimal strings (ADR-0006 rule 13) and are never parsed into floating-point numbers. A small self-written decimal-string module formats them by locale, at the scale of the field's currency or unit (`x-nativeflows-scale-from`, rule 4; ADR-0006 rule 14). It parses localized input back to the canonical form. Input with too many decimals is shown as the server's `too_many_decimal_places`, never rounded.

   Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): analysis charts and tables plot server cells only: totals, subtotals, other rows, shares, changes and contributions are cells of `EvaluateAnalysisPlan`; every figure of an answer is a key fact, and every sentence of its narrative, rendered by code with the formatter of this rule from fixed templates (rules 15, 23, 32).
3. Times and dates:
   - **Business dates.** Shown as stored (`YYYY-MM-DD`, formatted by locale).
   - **Instants.** Shown in the user's time zone (ADR-0007 rule 14).
   - **Defaults.** A field's default comes from the server: a package default posting date, or a draft's stored value. The client never invents one.

**UI metadata**

4. The registry emits UI metadata in the generated JSON Schemas, as these annotations:
   - **Derived from the model:**
     - `x-nativeflows-widget` (from the field's type: Amount, Quantity, UnitPrice, ExchangeRate, Percent, BusinessDate, enums, references);
     - `x-nativeflows-field-class` (ADR-0017 rule 10, emitted by ADR-0022 rule 17);
     - `x-nativeflows-untrusted` (ADR-0029);
     - `x-nativeflows-ref` (the referenced table of a `Ref[<table>]`);
     - `x-nativeflows-scale-from` (the sibling currency or unit field).
   - **Optional hints in `json_schema_extra`:**
     - `x-nativeflows-group` and `x-nativeflows-order`;
     - `x-nativeflows-line-columns` for line arrays;
     - `x-nativeflows-hidden-when` and `x-nativeflows-read-only-when` (simple conditions on other fields of the same payload);
     - `x-nativeflows-lookup` (the `List<Noun>` query with a `search` filter and the result fields to show);
     - `x-nativeflows-list-defaults` on a `List<Noun>` result model (default columns, sort and filters).
   - **Labels and help** come from i18n keys (rule 14), not from the schema.
   - **Not per screen.** Nothing is maintained per screen in the frontend. User-defined fields (after Phase 1) appear through the same schemas, so the renderer never hard-codes field lists.

    Note ([ADR-0074](0074-core-data-structure-additions.md), proposed 2026-11-19): the annotation `x-nativeflows-custom-values` names the table whose company-defined fields the renderer reads through `ListCustomFieldDefinitions`; user-defined fields (without tables) appear in the same schemas as that rule says (ADR-0074 rules 8 to 11).
5. CI checks the hints:
   - every hint names an existing field;
   - every `Ref` has a lookup query the registry knows;
   - every label key exists in the English catalog;
   - every placeholder in an error or check message exists in the code's `details` schema.

**Screens and navigation**

6. Generated screen kinds:
   - **List**, from `List<Noun>`: cursor paging, filters in the request body (ADR-0008 rule 22), and column choice. A banner shows when `is_scope_filtered` is true, so totals are not mistaken for complete ones.
     - **Column choice** is a per-viewer convenience kept in browser storage.
     - **Filters** are not saved; saved views come after Phase 1.
     - **Excel export** of a whole list is a registered command designed in DS-33. It runs as a job, is translated by the server, filtered by field class, limited in rows, and its file is an attachment.
   - **Record view**, from `Get<Noun>`:
     - the header, lines and links;
     - the state and version;
     - a version history with the actor kind, agent run, taint and clearance of each version (ADR-0029 rule 8);
     - attachments with their scan state;
     - actions from `ListAllowedCommand`.

     The audit link shows only to holders of `GetAuditRecord` (ADR-0038 rule 7).
   - **Command form** for any command: header fields, line tables (a plain keyboard table in v1; AG Grid on the hand-built screens), and the plan panel.
   - **Query result view** for computed queries (availability, pegging trees, production order status), rendered as tables or trees by result shape.

   The export is `CreateListExport`, with at most `list_export_max_rows` rows ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 54).

   Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): the extraction verification screen is a hand-built screen: the page beside the fields with evidence boxes, risky fields first, keyboard first, machine-checked fields apart from human-confirmed ones, unaligned values greyed and duplicates and flags at the top ([ADR-0057](0057-document-intake-and-extraction.md) rule 22).

   Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): a further screen kind, the analysis view: the builder with measure, dimension and filter chips from `ListAnalysisCatalog`; the answer view (restatement, table or chart, key facts with clickable figures, narrative sentences rendered by code with member chips and citation markers, plan chips and SQL, scope and truncation notes, badge, `as_of`); saved analyses with KPI tiles. Saved analyses are analysis plans, not saved list filters, which stay after Phase 1; results are exported through `ListAnalysisResultRow` and `CreateListExport` (rules 17, 32).

   Note ([ADR-0066](0066-work-cases.md), 2026-11-16 (proposed)): two further generated screen kinds. The case view shows a work case's timeline on the left, the selected artifact's record view or its command form with the plan panel on the right, and the case's pending commands above. The case list is a list over `ListWorkCase`. The company setting `work.landing_page` maps role templates to `work_queue` or `case_list` as their home. Cases serve unstructured and exception work; routine structured work keeps the screens above and the six hand-built screens, and nothing is computed in the client (rule 2) ([ADR-0066](0066-work-cases.md) rules 4, 21).

   Note ([ADR-0071](0071-work-orders-and-shop-floor-execution.md), proposed 2026-11-17): the WO tablet is a further hand-built PWA screen over `ListWorkCenterQueue` and `GetOperationWorkspace` (ADR-0071 rules 13, 14).
7. Navigation:
   - **The menu** is generated from the registry. Modules are grouped by area: accounting, inventory, sales, purchasing, production, warehouse, planning, work, settings. The user sees only nouns they may list, from `GetSessionContext`.
   - **The command palette** (`Ctrl/Cmd+K`) finds any permitted command, query, list or record by English or translated name.
   - **URLs:**
     - `/<company_code>/<noun>` for lists;
     - `/<company_code>/<noun>/<id>` for records;
     - `/<company_code>/run/<command_type>` and `/<company_code>/query/<query>` for forms and computed queries;
     - `/_installation/…` for installation-scoped ones.

     Command types and queries appear in their `snake_case` REST form (ADR-0004 rule 19). `run`, `query` and names starting with `_` are reserved: company codes cannot start with `_`, and no noun is called `run` or `query`. Filters never go into a URL (ADR-0008 rule 22).
8. `ListAllowedCommand` (subject table and ID) is a computed query, an exception to ADR-0004 rule 21 as in ADR-0015 rule 14. It returns `allowed_command` rows: each command applicable to the subject, with `is_allowed` and, when false, the error code the command would return.
   - **Single source.** Applicability comes from registry declarations the dispatcher itself uses: each command's `subject_table` and `allowed_states` (notes on ADR-0008 rule 1 and on ADR-0009 rule 5, whose `invalid_state_transition` reads the same declaration).
   - **Checks evaluated:** the caller's permission, `human_only`, `segregation_of_duties` for `Approve` (ADR-0017 rule 16), and a pending change (ADR-0028).
   - **Out of scope.** A subject outside the caller's record scope returns `record_not_found` (ADR-0008 rule 5).
   - **Advisory.** The answer returns the subject's version and writes no denial records. Policy outcomes that need a simulation come back from the command itself.
   - **Who may call it.** Its permission is in every role template. In Phase 1 it is on no agent tool list (open question), because a denial-free probe of permissions with reasons would weaken the denial signal of ADR-0038 rule 5.
   - **Testing.** A DS-16 property test checks that `is_allowed: true` implies that simulation never fails with `invalid_state_transition`, `permission_denied`, `human_only`, `segregation_of_duties` or `change_pending`.

   [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 34 proposes keeping it people-only: agents plan from their tool list and simulate mode.

   Note: its checks also read owner scope, delegations, segregation pairs and, for `Approve`, stage eligibility and the stranded-stage check ([ADR-0054](0054-users-roles-and-authorizations.md) rule 22; [ADR-0055](0055-approval-pools-and-stages.md) rule 7).

**Simulate, plan, execute**

9. A form submits in two steps, with one envelope and one idempotency key per intent (ADR-0008 rule 13):
   - **Review** (`Ctrl+Enter`) sends `mode: simulate` with `include_canonical_plan: true` and shows the plan panel:
     - journal lines and stock movements, filtered by field class;
     - document and record versions;
     - events;
     - side information such as warehouse task proposals;
     - check results;
     - the policy outcome when the plan carries one (approval or confirmation required, ADR-0029 rule 7).
   - **Confirm** (`Ctrl+Enter` again, or the button naming the command, such as "Post") sends `mode: execute` with `expected_plan_hash`.
   - **Plan changed.** On `plan_hash_mismatch` the panel shows the new plan and its differences from the reviewed one, computed on the two canonical plans (tokenized IDs, no numbers or system instants; ADR-0008 rule 12), and asks again.
   - **Retries.** A retryable error is retried with the same key, honoring `retry_after_seconds`.
   - **After execution.** The panel shows the assigned number and `recorded_at`.
   - **Canonical plans.** `include_canonical_plan` is a new optional envelope field (DS-04; a note on ADR-0008 rule 7).
     - **Request hash.** Like `mode`, it is left out of the request hash of ADR-0008 rule 15.
     - **Response.** The response then carries `canonical_plan`, filtered by field class like the plan. `plan_hash_mismatch` carries the new canonical plan in `details`.
     - **Batches.** In a batch, each item carries its canonical plan when `include_plan` and `include_canonical_plan` are both set.

   Note ([ADR-0067](0067-quickflows-operating-presets.md), 2026-11-17 (proposed)): under the company setting `ui.post_review` at `on_exceptions`, the Post button sends Review and, when the response's `review_reasons` is empty, Confirm at once with `is_review_skipped: true`; otherwise, or on `post_review_required`, the plan panel opens as above with the reasons listed. The client computes no reason itself (rule 2); the default `always` keeps this rule unchanged ([ADR-0067](0067-quickflows-operating-presets.md) rules 11–13).
10. Check results. Command responses gain `checks`: a list of `{code, message, rule, field, details}` from the check-result catalog (DS-04), in simulate and execute and per batch item.
    - **`message`** is English, as for errors.
    - **`details`** are filtered by field class.
    - **Hashing.** The canonical plan gains a key `checks`: the list of `[code, field]` pairs, with a null field as `""`, duplicates removed, sorted by code then field (DS-04 step 4; ADR-0031 rule 1). So `plan_hash` covers them, and a check that appears between review and execution forces a second review.
    - **Unhashed checks.** The registry declares `is_hashed` per check code, true by default. It is false for checks that come from side information that is itself unhashed, so they cannot cause the mismatch those rules avoid:
      - warehouse task proposals and bin contents that concurrent warehouse work changes (ADR-0023 rule 11): `capacity_not_checked`, `bin_capacity_exceeded`, `mixed_stock_not_allowed`, `no_pickable_stock`;
      - planning and forecast results (ADR-0024 rule 17): `planning_parameter_missing`, `forecast_history_insufficient`.

      Those are returned in `checks` but left out of the hashed pairs.
    - **Storage.** Checks are part of the stored response and batch summary (ADR-0008 rules 16–21), and `audit_record` keeps their codes in `check_codes` (ADR-0038 rule 2).
    - **Display.** The UI shows them in the plan panel and next to their field, and agents read the same list.
11. Errors and concurrent changes:
    - **Placement.** An error's `field` path (`payload.lines[3].quantity`, `items[2].payload.…`) puts the message on its control. Errors without a field go to the panel. All validation errors show at once.
    - **Text.** It comes from `error.<code>.message` and `.fix`, interpolated with `details`. An unknown code shows the English `message` and the code.
    - **Next steps.** Codes whose `details` name a next step show it as a link (`exchange_rate_missing`, `account_determination_missing`, `record_not_found`, `invalid_state_transition`).
    - **Records changed by someone else.** A live update on a record whose form is being edited never resets the form; it shows a "changed" banner. On `version_conflict` (ADR-0009 rule 10) the form reloads the current version and re-applies the user's edits to the fields that did not change on the server, showing the others as conflicts.

**Sessions, schemas, live updates**

12. Transport:
    - **Sessions** are server-side (ADR-0017 rule 2), in a cookie `__Host-nativeflows_session` (`Secure`, `HttpOnly`, `SameSite=Lax`).
    - **CSRF.** Every state-changing request from a cookie session carries the header `X-NativeFlows-CSRF` with the session's token, and its `Origin` must be the installation's. Integrations and agents use bearer tokens and need neither.
    - **Hand-written endpoints.** The transport endpoints, owned by `permissions` and `registry`, are the only hand-written ones besides the attachment upload: `POST /api/auth/sign-in`, `POST /api/auth/totp`, `POST /api/auth/sign-out`, `GET /api/auth/oidc/callback`, `GET /api/ui/stream`, and `POST /api/ui/stream/subscriptions`. ADR-0008 rule 6 and ADR-0038 rule 13 get a note.
    - **CSRF token.** The client gets it from the sign-in response and from `GetSessionContext`.
    - **Session bootstrap.** `GetSessionContext` is installation-scoped and needs only a valid credential, not a permission. This is an exception to ADR-0017 rule 8, which gets a note. It returns only the caller's own rights, and it is on no agent tool list. It returns, after sign-in:
      - the user;
      - their companies with role assignments, permissions, field classes and record scope;
      - their language and time zone;
      - the installation's environment.

      The menu, palette and company switch read it.
    - **Schemas and catalogs.** The annotated JSON Schemas and the i18n catalogs (core and every package's terminology) are generated into `frontend/src/generated/`, which is possible because packages ship with the build (ADR-0016 rule 3). They are loaded per screen and per language by dynamic import, so the shell stays within its size budget (rule 17).

    Note: a hand-written endpoint `POST /api/auth/password` consumes a one-time reset token or changes a password; `GetSessionContext` also returns owner scopes, the delegations in force and the user's pending invitations ([ADR-0054](0054-users-roles-and-authorizations.md) rules 3, 4, 22).
13. Live updates (ADR-0013 rule 12) work as follows:
    - **The header.** When the dispatcher inserts an event (ADR-0013 rule 6), it also sends `pg_notify('nativeflows_ui', header)` in the same transaction. The notification goes out only on commit and never from a simulation.
    - **Header contents:** event ID, event type, company, the subject's root (`subject_table` and `subject_id`, with child subjects resolved to their document), `subject_sequence`, and the subject's record-scope dimensions as the dispatcher's scope resolver computes them (the same values `audit_record` stores, ADR-0038 rule 2). It carries no payload values. This replaces the consumer that ADR-0013 rule 12 foresaw, so there are no delivery rows, pausing or retention to manage.
    - **Listening.** Each web process holds one dedicated `LISTEN` connection outside the pool; it reads no table. Because any database role can listen on a channel, headers carry only IDs, and the read-only query layer (DS-33) accepts nothing but `SELECT`.
    - **The stream.** A signed-in tab opens `GET /api/ui/stream` (Server-Sent Events over HTTP/2 through Caddy, heartbeat every 25 seconds, no buffering). Its first message gives a random `stream_id`.
    - **Subscriptions.** The tab posts the whole set of subjects and nouns it has open to `/api/ui/stream/subscriptions` with that `stream_id`, at most 100 entries. A list screen subscribes to its noun, not to its rows, so 100 is ample. A set whose relayed payload would exceed 7,500 bytes is rejected with `request_too_large`, keeping it under PostgreSQL's `NOTIFY` limit. A post replaces the stream's set, so it is idempotent.
      - **Routing.** The post may reach another web process, so the receiving process checks that the stream belongs to the session and relays `{stream_id, subscriptions}` with `pg_notify('nativeflows_ui_sub', …)` (IDs only). Every process listens there, and the one holding the stream applies it.
      - **Reconnects.** After a reconnect the tab gets a new `stream_id` and posts its set again.
    - **Forwarding.** The web process forwards a header only if all of these hold:
      - it matches a subscription;
      - the session still holds `Get<Noun>` or `List<Noun>` for the subject's table, checked against cached assignments that expire within 30 seconds;
      - the subject's scope dimensions are in the session's record scope.

      Installation-scoped events (no company) go only to installation-scoped sessions.
    - **Revocation.** Revoking a session closes its stream.
    - **The client** coalesces headers for 300 ms per query key, invalidates the subject's TanStack Query keys and refetches through queries, so permissions and field classes apply on the read.
    - **Delivery.** Best effort. After a reconnect, the client refetches what is open.

    The query builder emits one `SELECT` per statement, and `EXECUTE` on `pg_notify` is revoked from `PUBLIC` and granted to `nativeflows_app` and `nativeflows_worker` ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 44).

    Note: the header also carries the subject document's `owner_employee_id` and `created_by_user_id` (IDs), and a header is forwarded only when the session's read owner scope reaches the document, checked against the same cached assignments and organization data ([ADR-0054](0054-users-roles-and-authorizations.md) rule 15).

    Note ([ADR-0076](0076-internal-messaging-and-notifications.md), proposed 2026-11-19): a `MessageCreated` header (subject: the message) is resolved to its conversation and forwarded only to sessions whose user may read that conversation now, through messaging's registered visibility function, and a `NotificationCreated` header only to its recipient's sessions; no tab subscribes to the noun `message`; headers carry IDs, never text (ADR-0076 rule 8).
14. Notifications to people beyond live screens (e-mail, push) are after Phase 1 (spec 07).

    Note ([ADR-0076](0076-internal-messaging-and-notifications.md), proposed 2026-11-19): ADR-0076 (proposed; its Phase 1 placement is the author's decision) adds an in-app inbox fed by messages and work items, and notification e-mail grouped per person every 5 minutes or in a daily digest, without message text (rules 6, 7). Push stays after Phase 1.

**Language, keyboard, display**

15. i18n follows ADR-0016 rules 18–19 with i18next:
    - **Generated keys.** The core catalog's keys are generated from the registry, with English source:
      - `field.<table>.<field>` for columns, and `field.<command_type or query>.<field>` for payload and result fields that are not columns;
      - `enum.<enum>.<value>`;
      - `command.<command_type>` and `query.<query>`;
      - `error.<code>.message` and `.fix`, for errors and check results alike, as DS-04 keeps one catalog.
    - **Vietnamese.** It is drafted and reviewed in Weblate; CI fails on an empty Vietnamese key in the core catalog.
    - **Terminology.** Accounting terms in a package's terminology catalog carry a basis like other package content (ADR-0016 rule 6), so the author verifies them.
    - **Untranslated content.** User-entered text is never translated.

    Note: Vietnamese UI strings stay in the core catalog (D8). Vietnamese accounting names for system accounts and keys belong to `l10n_vn`'s terminology catalog, which also names `enum.partner_kind.sole_proprietorship` ([ADR-0053](0053-core-neutrality.md) rules 7, 16).
16. Keyboard model (step 9's measure is keyboard-first, ADR-0003 R9):
    - **Global:** `Ctrl/Cmd+K` palette; `g` then a letter to go to an area; `?` shows every shortcut; `Esc` closes.
    - **Forms:** `Enter` moves to the next field and `Shift+Enter` back. `F2` or typing opens a lookup. `Alt+N` adds a line and `Alt+Delete` removes one. `Ctrl+Enter` reviews, then confirms.
    - **Grids:** AG Grid's model, with the same `Alt` keys.
    - **Registration.** All shortcuts are registered in one map with translated labels, and every action works without a mouse.

    Note ([ADR-0061](0061-barcodes.md), proposed 2026-11-15): a keyboard-wedge scan into a focused code field ends with the scanner's Enter suffix, which moves to the next field as above. Every code field on desktop screens accepts wedge scans and resolves them with `EvaluateBarcode` for the field's expected type; a scan is told from typing by the AIM prefix, the suffix and its speed (rule 22).
17. Display and targets:
    - **Untrusted fields.** Shown as plain text in a marked "external content" style, never rendered as HTML, with links not clickable.
    - **Taint.** A badge on tainted versions and proposals, with the clearance record.
    - **Field classes.** Fields of a class the user lacks are omitted by the server; the form shows a "restricted" placeholder and leaves them out of updates, which keeps their values (ADR-0017 rule 10).
    - **Human-only actions** ask for a reason where the command requires one.
    - **Targets** (open question):
      - accessibility: WCAG 2.2 AA on desktop screens;
      - browsers: the last two versions of Chrome, Edge, Firefox and Safari, and Chrome on Android 10 or later for the warehouse PWA;
      - size: at most 250 KB gzipped of JavaScript for the shell and 150 KB for the PWA route. AG Grid loads only on the hand-built desktop screens (ADR-0002, performance rule 3).
    - **Storage.** Business and personal data never go into browser storage. An unsaved form lives in memory; a draft is a server-side document. Browser storage holds only per-viewer conveniences such as column choices.

    Note: the untrusted-field rule holds in printed files too: untrusted fields are escaped and never rendered as HTML ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 29).

**Structure, tests and scope**

18. `frontend/src/` holds:
    - `generated/` (types, annotated schemas, catalogs; never edited);
    - `routes/` (TanStack Router file routes);
    - `renderer/`, `screens/` (the hand-built screens), `pwa/` (DS-31);
    - `decimal/`, `i18n/` and `lib/`.

    **File names** are kebab-case except where the router fixes them (ADR-0022 rule 24), which settles ADR-0004 rule 23.

    **Tests and CI.**
    - The CI job `frontend` runs typecheck, lint, build, Vitest, the checks of rule 5, the Vietnamese key check and the size budgets.
    - Playwright flows run nightly against the test server's synthetic data, outside the 15-minute limit.
    - A frontend dependency in a new category needs an ADR (ADR-0005). ADR-0022 rules 14, 17 and 24 get notes.
19. Renderer v1 (step 1):
    - **Shell:** sign-in (password with TOTP, or OIDC; ADR-0017) and the session bootstrap, company switch, menu and palette.
    - **Screens:** list, record view, command form with plain line tables, and query result views.
    - **Flow:** simulate, plan, execute, errors, checks and live updates.
    - **Languages:** English and Vietnamese.

    It is enough to operate and test every command (spec 11, B6). From step 5 it also hosts, as generated screens, the desktop warehouse task confirmation (ADR-0023 rule 22), the work queue (a list of work items) and change proposals.

    Note: Vietnamese here is a UI language, shipped by the core (D8), not overlay ([ADR-0053](0053-core-neutrality.md) rule 16).
20. Owned elsewhere:
    - **Hand-built screens.** The UX spec of the six hand-built screens (sales invoice, goods receipt, goods issue, cash receipt, cash payment, journal entry) is written before step 9. It builds on DS-22 and DS-25, which define those documents. It follows these rules: header fields in keyboard order, the AG Grid line editor, the review shortcut, and lookups that type ahead.
    - **Production and planning screens** are generated over their queries (ADR-0034 rule 18; ADR-0024).
    - **Elsewhere:** shop-floor and warehouse flows (DS-31), print (DS-27), list export (DS-33).

    Note ([ADR-0061](0061-barcodes.md), proposed 2026-11-15): DS-31 builds the PWA's scanning on ADR-0061: BarcodeDetector for EAN/UPC and ITF only, until the scanner check page proves on a device that it passes GS through, and a WebAssembly decoder for Code 128, GS1-128, DataMatrix and QR; wedge capture, the shipped scanner profiles and the check page. The WebAssembly modules load on first use and are measured apart from the JavaScript budget of rule 17 (rules 22, 23).

## Context

DS-30's renderer part is a design item of step 1 ([steps-0-4.md](../runbook/steps-0-4.md)): the renderer is the operating UI from step 1 to step 8, and the six hand-built screens come at step 9, measured against MISA (ADR-0003 R9).

The stack is fixed by ADR-0002. These were defined nowhere and are decided here:
- the metadata format and navigation;
- the keyboard model;
- the session and stream transport;
- accessibility and browser targets;
- where check results travel.

Odoo and SAP Fiori both render most screens from metadata. Odoo's views are hand-written XML per model; NativeFlows derives its metadata from the command schemas, so agents and people see one definition.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Metadata as schema annotations (chosen) | One source with the API; agents read it too | Layout hints are limited |
| Per-screen layout files in the frontend | Full control | Drifts from the schemas; hand-written per command, against ADR-0008 rule 6 |
| `NOTIFY` in the emitting transaction (chosen) | No delivery rows; sent only on commit; nothing from simulations | Best effort only |
| An outbox consumer for live updates | Uses the existing delivery machinery | A delivery row, transaction and retention per event; paused registration; a held delivery blocks a best-effort signal |
| Server-Sent Events (chosen) | One-way, no library, works through proxies | One stream per tab, which needs HTTP/2 |
| WebSocket | Two-way | Not needed |
| Polling | Simplest | Latency, or load at short intervals |
| Client computes line totals | Instant feedback | Duplicates tax and rounding logic; drifts from the server |
| Simulation on explicit review (chosen) | Predictable load; one plan | One extra keystroke per document |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0004 rule 23: TypeScript file names;
  - ADR-0008 rules 1, 6, 7, 12, 21: `subject_table` and `allowed_states`; transport endpoints; `include_canonical_plan`; checks in the canonical plan; `checks` in responses;
  - ADR-0009 rule 5: the same allowed-states declaration;
  - ADR-0017 rule 8: `GetSessionContext` needs no permission;
  - ADR-0023 rule 11, ADR-0024 rule 17, ADR-0031 rule 1: unhashed checks; the `checks` key of the canonical plan;
  - ADR-0013 rules 6, 12: the UI header sent with event insertion instead of a consumer;
  - ADR-0016 rule 19: the generated keys;
  - ADR-0017 rule 4: `ListAllowedCommand` and `GetSessionContext`;
  - ADR-0022 rules 14, 17, 24: the frontend CI job, generated annotations and catalogs, layout;
  - ADR-0038 rules 2, 13: `check_codes`; the list of hand-written endpoints.
- **DS-04:**
  - the `checks` and `canonical_plan` response fields and `include_canonical_plan`; `checks` in hashing step 4; the unhashed check codes;
  - `ListAllowedCommand` and `GetSessionContext`;
  - `quantity_rounded` in the check-result catalog.
- **Other design items:**
  - DS-16: the allowed-command property test;
  - DS-22 and DS-25: document fields for the hand-built screens;
  - DS-31: PWA flows;
  - DS-33: list export and the read-only layer's `SELECT`-only rule;
  - DS-27: printing.
- **Open questions:**
  - the keyboard defaults;
  - agents' use of `ListAllowedCommand`;
  - accessibility and device targets.

## Revisit when

- The step 9 measurement shows the review step or the keyboard model is too slow.
- More than a few screens need layout the hints cannot express.
- Live updates need guaranteed delivery.

## Documents updated

- **ADRs:** [docs/adr/0004-naming-conventions.md](0004-naming-conventions.md), [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md), [docs/adr/0013-outbox-and-events.md](0013-outbox-and-events.md), [docs/adr/0016-localization-package-structure.md](0016-localization-package-structure.md), [docs/adr/0017-permission-envelope.md](0017-permission-envelope.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0038-audit-and-observability.md](0038-audit-and-observability.md): notes.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
