Module: app    Chunk: 1 of 2    Source ADRs: ADR-0040
Build step(s): 9    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `app` compiled spec, chunk 1: UI architecture (client rules, metadata, screens, forms, transport, live updates, i18n, keyboard, display)

## Purpose

`app` is the web UI: one more client of the command and query layer. It writes data only through registered commands and reads only through registered queries, renders almost every screen from the registry, and computes no money or quantity itself. It owns no table. This chunk states, each with its notes, ADR-0040 rules 1 to 7, 9 and 11 to 17. ADR-0040 rules 18 to 20, the case screens of ADR-0066 and the floorplans, annotations and tests of ADR-0077 are in chunk 2. ADR-0040 rules 8 and 10 belong to `registry`.

## Entities and tables

None: `app` owns no table.

Reads: `list_variant` (`registry`), `assist_request` (`agents`), `audit_record` (`audit`), `message` (messaging, ADR-0076).

## Commands and queries

`app` is a client; the sources of this chunk state these registry additions and no authorization area for them. The catalog's verb levels apply: `List` needs `read`, `Delete` needs `edit`, computed queries need `read`.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `GetSessionContext` | session query, installation-scoped; any valid credential, no permission; on no agent tool list (R20) | not stated | Returns the caller's own rights and session data (R20) | none | not stated |
| `ListAllowedCommand` | computed query, for people only in Phase 1 (R1) | not stated | Gives the actions of a record view (R8) | none | not stated |

Commands and queries of other modules that this chunk's rules call: `CreateListExport`, `ListCustomFieldDefinitions`, `EvaluateAnalysisPlan`, `ListAnalysisCatalog`, `ListAnalysisResultRow`, `ListWorkCase`, `ListWorkCenterQueue`, `GetOperationWorkspace`, `GetAuditRecord`, `EvaluateBarcode`.

The list variant commands and query that R7 and R14 use (`ListListVariant`, `CreateListVariant`, `UpdateListVariant`, `DeleteListVariant`) have their rows in chunk 2.

Hand-written transport endpoints, not registered commands (R19): `POST /api/auth/sign-in`, `POST /api/auth/totp`, `POST /api/auth/sign-out`, `POST /api/auth/password`, `GET /api/auth/oidc/callback`, `GET /api/ui/stream`, `POST /api/ui/stream/subscriptions`.

Error codes bound to no command of this module: `too_many_decimal_places` (R3), `plan_hash_mismatch` and `post_review_required` (R16), `version_conflict`, `exchange_rate_missing`, `account_determination_missing`, `record_not_found` and `invalid_state_transition` (R18), `request_too_large` (R24).

## Rules

### Client principles

R1. The web UI is one more client of the command and query layer: it writes only through registered commands and reads only through registered queries. Almost every screen is rendered from the registry: lists from `List<Noun>` queries, record views from `Get<Noun>`, forms from command schemas; their UI metadata travels as named `x-nativeflows-*` annotations in the generated JSON Schemas. A form shows the server's plan and check results before anything executes. The step 9 entry screens are not hand-built: they are generated create and edit forms with the editable line grid `line_grid`, the in-repo TanStack Table grid (ADR-0040.R20.N2, ADR-0077.R5, ADR-0077.R20). Registry additions: a `checks` field in command responses, part of `plan_hash` by code and field; the computed query `ListAllowedCommand`, for people only in Phase 1; the session query `GetSessionContext`. Renderer v1 (step 1) covers sign-in, navigation, lists, record views, forms with `line_grid` line entry (ADR-0077.R23), simulate, plan, execute, errors, checks, live updates, English and Vietnamese.
Source: ADR-0040.D0, ADR-0040.D0.N1

R2. The UI calls only registered commands and queries through the generated client (ADR-0008.R6); the only exceptions are the transport endpoints of R19. No screen gets a command, field or capability that agents lack. A screen need the API cannot meet is solved in the API for every client, as a B2 change where it alters a command (step 9 fallback). The live stream is a signal to refetch and carries no data that a query would not give.
Source: ADR-0040.R1

R3. The client does no business arithmetic: totals, taxes, prices, conversions and stock effects come from simulation, and the client only formats them. Decimals travel as canonical decimal strings (ADR-0006.R13) and are never parsed into floating-point numbers. A small self-written decimal-string module formats them by locale at the scale of the field's currency or unit (`x-nativeflows-scale-from`, R5; ADR-0006.R14) and parses localized input back to the canonical form. Input with too many decimals is shown as the server's `too_many_decimal_places`, never rounded. Analysis charts and tables plot server cells only: totals, subtotals, other rows, shares, changes and contributions are cells of `EvaluateAnalysisPlan`; every figure of an answer is a key fact, and every sentence of its narrative is rendered by code with this formatter from fixed templates (ADR-0060.R15, ADR-0060.R23, ADR-0060.R32).
Source: ADR-0040.R2, ADR-0040.R2.N1

R4. Business dates are shown as stored (`YYYY-MM-DD`, formatted by locale). Instants are shown in the user's time zone (ADR-0007.R14). A field's default comes from the server (a package default posting date, or a draft's stored value); the client never invents one.
Source: ADR-0040.R3

### UI metadata

R5. The registry emits UI metadata in the generated JSON Schemas as annotations of a closed vocabulary of 24 keys; every key has one renderer, and a key outside the vocabulary fails `check` (ADR-0077.R8 to ADR-0077.R12).
- Derived from the model: `x-nativeflows-widget` (from the field's type: Amount, Quantity, UnitPrice, ExchangeRate, Percent, BusinessDate, enums, references, and `State`); `x-nativeflows-field-class` (ADR-0017.R10, emitted by ADR-0022.R17); `x-nativeflows-untrusted` (ADR-0029); `x-nativeflows-ref` (the referenced table of a `Ref[<table>]`); `x-nativeflows-scale-from` (the sibling currency or unit field; required on money and quantity).
- Optional hints in `json_schema_extra`: `x-nativeflows-group` and `x-nativeflows-order`; `x-nativeflows-line-columns` for line arrays, with `editor`; `x-nativeflows-hidden-when` and `x-nativeflows-read-only-when` (simple conditions on other fields of the same payload, or on the subject's `state`); `x-nativeflows-lookup` (the `List<Noun>` query with a `search` filter and the result fields to show, with `depends_on`); `x-nativeflows-list-defaults` on a `List<Noun>` result model (default columns, sort and filters, with declared `variants`).
- Further keys: `importance`, `default-from`, `scan`, `ai-fillable`, `floorplan`, `title`, `header-facets`, `actions`, `links`, `search` and `assist`.
- `x-nativeflows-custom-values` names the table whose company-defined fields the renderer reads through `ListCustomFieldDefinitions` (ADR-0074.R8 to ADR-0074.R11).
- Labels and help come from i18n keys (R28), not from the schema.
- Nothing is maintained per screen in the frontend. User-defined fields (after Phase 1, without tables) appear through the same schemas, so the renderer never hard-codes field lists.
Source: ADR-0040.R4, ADR-0040.R4.N1, ADR-0040.R4.N2

R6. CI checks the hints: every hint names an existing field; every `Ref` has a lookup query the registry knows; every label key exists in the English catalog; every placeholder in an error or check message exists in the code's `details` schema.
Source: ADR-0040.R5

### Screen kinds

R7. The generated list screen is rendered from `List<Noun>`: cursor paging, filters in the request body (ADR-0008.R22) and column choice. A banner shows when `is_scope_filtered` is true, so totals are not mistaken for complete ones. Filters, columns, sort and grouping are saved in list variants (R14); the browser keeps only the viewer's last column choice. Excel export of a whole list is the registered command `CreateListExport` (DS-33): it runs as a job, is translated by the server, filtered by field class, limited to at most `list_export_max_rows` rows (ADR-0050.R54), and its file is an attachment.
Source: ADR-0040.R6, ADR-0040.R6.N6

R8. The generated record view is rendered from `Get<Noun>` and shows: the header, lines and links; the state and version; a version history with the actor kind, agent run, taint and clearance of each version (ADR-0029.R8); attachments with their scan state; actions from `ListAllowedCommand`. The audit link shows only to holders of `GetAuditRecord` (ADR-0038.R7).
Source: ADR-0040.R6

R9. A generated command form exists for any command: header fields, line tables and the plan panel. A line array whose `x-nativeflows-line-columns` `editor` is `grid` renders as `line_grid`, the in-repo TanStack Table grid, in renderer v1 too; no screen is hand-built for it (ADR-0077.R5, ADR-0077.R20, ADR-0077.R23). A generated query result view serves computed queries (availability, pegging trees, production order status), rendered as tables or trees by result shape.
Source: ADR-0040.R6, ADR-0040.R6.N7

R10. Two screens are registered custom components, not floorplans and not hand-built screen kinds (ADR-0040.R20.N2, ADR-0077.R22). The extraction verification screen, `extraction_verification`, shows the page beside the fields with evidence boxes, risky fields first, keyboard first, machine-checked fields apart from human-confirmed ones, unaligned values greyed, and duplicates and flags at the top (ADR-0057.R22). The WO tablet, `work_order_tablet`, is a PWA screen over `ListWorkCenterQueue` and `GetOperationWorkspace` (ADR-0071.R13, ADR-0071.R14).
Source: ADR-0040.R6.N1, ADR-0040.R6.N4

R11. The analysis view is the registered custom component `analysis_view` (ADR-0040.R20.N2, ADR-0077.R22): the builder with measure, dimension and filter chips from `ListAnalysisCatalog`; the answer view (restatement, table or chart, key facts with clickable figures, narrative sentences rendered by code with member chips and citation markers, plan chips and SQL, scope and truncation notes, badge, `as_of`); saved analyses with KPI tiles. Saved analyses are analysis plans, not list variants. Results are exported through `ListAnalysisResultRow` and `CreateListExport` (ADR-0060.R17, ADR-0060.R32).
Source: ADR-0040.R6.N2

R12. The case view and the case list are further generated screen kinds. The case view is the `worklist` floorplan: it shows a work case's timeline on the left, the selected artifact as an object page (its record view), an edit form (its command form with the plan panel) or an approval view on the right (ADR-0066.R21.N1), and the case's pending commands above. The case list is a list over `ListWorkCase`. The company setting `work.landing_page.<role_template>` maps a role template to `work_queue` or `case_list` as its home. Cases serve unstructured and exception work; routine structured work keeps the screens of R7 to R9, among them the generated step 9 entry screens (ADR-0077.R5), and nothing is computed in the client (R3) (ADR-0066.R4, ADR-0066.R21).
Source: ADR-0040.R6.N3

R13. The screen kinds map onto seven floorplans: list report, object page, create and edit form (with a wizard variant), worklist, overview, plan panel and approval view. A route renders exactly one of them, or a registered custom component (ADR-0077.R1 to ADR-0077.R3, ADR-0077.R22).
Source: ADR-0040.R6.N5

R14. User-saved list variants are in Phase 1: personal or shared with a role, storing filters, columns, sort and grouping server-side in `list_variant`, through `ListListVariant`, `CreateListVariant`, `UpdateListVariant` and `DeleteListVariant`; sharing needs `share_list_variant` (ADR-0077.R10a).
Source: ADR-0040.R6.N6

### Navigation

R15. Navigation:
- The menu is generated from the registry. Modules are grouped by area: accounting, inventory, sales, purchasing, production, warehouse, planning, work, settings. The user sees only nouns they may list, from `GetSessionContext`.
- The command bar (`Ctrl/Cmd+K`) finds any permitted command, query, list or record by English or translated name. Text that matches no name becomes an `assist_request` with purpose `resolve_command`, whose answer is a proposed invocation shown with its parameters and opened as a prefilled form; it runs simulate first and never executes by itself (ADR-0077.R18).
- URLs: `/<company_code>/<noun>` for lists; `/<company_code>/<noun>/<id>` for records; `/<company_code>/run/<command_type>` and `/<company_code>/query/<query>` for forms and computed queries; `/_installation/…` for installation-scoped ones.
- Command types and queries appear in their `snake_case` REST form (ADR-0004.R19). `run`, `query` and names starting with `_` are reserved: company codes cannot start with `_`, and no noun is called `run` or `query`. Filters never go into a URL (ADR-0008.R22).
Source: ADR-0040.R7, ADR-0040.R7.N1

### Forms: review and confirm

R16. A form submits in two steps, with one envelope and one idempotency key per intent (ADR-0008.R13):
- Review (`Ctrl+Enter`) sends `mode: simulate` with `include_canonical_plan: true` and shows the plan panel: journal lines and stock movements, filtered by field class; document and record versions; events; side information such as warehouse task proposals; check results; the policy outcome when the plan carries one (approval or confirmation required, ADR-0029.R7).
- Confirm (`Ctrl+Enter` again, or the button naming the command, such as "Post") sends `mode: execute` with `expected_plan_hash`.
- On `plan_hash_mismatch` the panel shows the new plan and its differences from the reviewed one, computed on the two canonical plans (tokenized IDs, no numbers or system instants; ADR-0008.R12), and asks again.
- A retryable error is retried with the same key, honoring `retry_after_seconds`.
- After execution the panel shows the assigned number and `recorded_at`.
- Under the company setting `ui.post_review` at `on_exceptions`, the Post button sends Review and, when the response's `review_reasons` is empty, Confirm at once with `is_review_skipped: true`; otherwise, or on `post_review_required`, the plan panel opens with the reasons listed. The client computes no reason itself (R3). The default `always` shows the plan panel before every execution (ADR-0067.R11 to ADR-0067.R13).
Source: ADR-0040.R9, ADR-0040.R9.N1

R17. `include_canonical_plan` is an optional envelope field (DS-04; a note on ADR-0008.R7). Like `mode`, it is left out of the request hash of ADR-0008.R15. The response then carries `canonical_plan`, filtered by field class like the plan. `plan_hash_mismatch` carries the new canonical plan in `details`. In a batch, each item carries its canonical plan when `include_plan` and `include_canonical_plan` are both set.
Source: ADR-0040.R9

### Errors and concurrent changes

R18. Errors and concurrent changes:
- Placement: an error's `field` path (`payload.lines[3].quantity`, `items[2].payload.…`) puts the message on its control. Errors without a field go to the panel. All validation errors show at once.
- Text comes from `error.<code>.message` and `.fix`, interpolated with `details`. An unknown code shows the English `message` and the code.
- Codes whose `details` name a next step show it as a link (`exchange_rate_missing`, `account_determination_missing`, `record_not_found`, `invalid_state_transition`).
- A live update on a record whose form is being edited never resets the form; it shows a "changed" banner. On `version_conflict` (ADR-0009.R10) the form reloads the current version and re-applies the user's edits to the fields that did not change on the server, showing the others as conflicts.
Source: ADR-0040.R11

### Transport

R19. Sessions are server-side (ADR-0017.R2), in a cookie `__Host-nativeflows_session` (`Secure`, `HttpOnly`, `SameSite=Lax`). Every state-changing request from a cookie session carries the header `X-NativeFlows-CSRF` with the session's token, and its `Origin` must be the installation's; integrations and agents use bearer tokens and need neither. The client gets the CSRF token from the sign-in response and from `GetSessionContext`. The transport endpoints, owned by `permissions` and `registry`, are the only hand-written ones besides the attachment upload: `POST /api/auth/sign-in`, `POST /api/auth/totp`, `POST /api/auth/sign-out`, `GET /api/auth/oidc/callback`, `GET /api/ui/stream`, `POST /api/ui/stream/subscriptions`, and `POST /api/auth/password`, which consumes a one-time reset token or changes a password (ADR-0054.R3, ADR-0054.R4). ADR-0008.R6 and ADR-0038.R13 carry a note for them.
Source: ADR-0040.R12, ADR-0040.R12.N1

R20. `GetSessionContext` is installation-scoped and needs only a valid credential, not a permission; this is an exception to ADR-0017.R8. It returns only the caller's own rights, and it is on no agent tool list. After sign-in it returns: the user; their companies with role assignments, permissions, field classes and record scope; their language and time zone; the installation's environment; owner scopes, the delegations in force and the user's pending invitations (ADR-0054.R22). The menu, command bar and company switch read it.
Source: ADR-0040.R12, ADR-0040.R12.N1

R21. The annotated JSON Schemas and the i18n catalogs (core and every package's terminology) are generated into `frontend/src/generated/`, which is possible because packages ship with the build (ADR-0016.R3). They are loaded per screen and per language by dynamic import, so the shell stays within its size budget (R31).
Source: ADR-0040.R12

### Live updates

R22. Live updates (ADR-0013.R12): when the dispatcher inserts an event (ADR-0013.R6), it also sends `pg_notify('nativeflows_ui', header)` in the same transaction. The notification goes out only on commit and never from a simulation. The header holds: event ID, event type, company, the subject's root (`subject_table` and `subject_id`, with child subjects resolved to their document), `subject_sequence`, the subject's record-scope dimensions as the dispatcher's scope resolver computes them (the same values `audit_record` stores, ADR-0038.R2), and the subject document's `owner_employee_id` and `created_by_user_id` (IDs). It carries no payload values and never text. This header stands in place of the consumer that ADR-0013.R12 foresaw, so there are no delivery rows, pausing or retention to manage.
Source: ADR-0040.R13, ADR-0040.R13.N1, ADR-0040.R13.N2

R23. Each web process holds one dedicated `LISTEN` connection outside the pool; it reads no table. Because any database role can listen on a channel, headers carry only IDs, and the read-only query layer (DS-33) accepts nothing but `SELECT`: the query builder emits one `SELECT` per statement, and `EXECUTE` on `pg_notify` is revoked from `PUBLIC` and granted to `nativeflows_app` and `nativeflows_worker` (ADR-0050.R44). A signed-in tab opens `GET /api/ui/stream` (Server-Sent Events over HTTP/2 through Caddy, heartbeat every 25 seconds, no buffering); its first message gives a random `stream_id`.
Source: ADR-0040.R13

R24. Subscriptions: the tab posts the whole set of subjects and nouns it has open to `/api/ui/stream/subscriptions` with its `stream_id`, at most 100 entries; a list screen subscribes to its noun, not to its rows. A set whose relayed payload would exceed 7,500 bytes is rejected with `request_too_large`, keeping it under PostgreSQL's `NOTIFY` limit. A post replaces the stream's set, so it is idempotent. The post may reach another web process, so the receiving process checks that the stream belongs to the session and relays `{stream_id, subscriptions}` with `pg_notify('nativeflows_ui_sub', …)` (IDs only); every process listens there, and the one holding the stream applies it. After a reconnect the tab gets a new `stream_id` and posts its set again.
Source: ADR-0040.R13

R25. The web process forwards a header only if all of these hold:
- it matches a subscription;
- the session still holds `Get<Noun>` or `List<Noun>` for the subject's table, checked against cached assignments that expire within 30 seconds;
- the subject's scope dimensions are in the session's record scope;
- the session's read owner scope reaches the document, checked against the same cached assignments and organization data (ADR-0054.R15).
Installation-scoped events (no company) go only to installation-scoped sessions. A `MessageCreated` header (subject: the message) is resolved to its conversation and forwarded only to sessions whose user may read that conversation now, through messaging's registered visibility function; a `NotificationCreated` header goes only to its recipient's sessions; no tab subscribes to the noun `message` (ADR-0076.R8). Revoking a session closes its stream.
Source: ADR-0040.R13, ADR-0040.R13.N1, ADR-0040.R13.N2

R26. Per query key, the client coalesces headers for 300 ms; it invalidates the subject's TanStack Query keys and refetches through queries, so permissions and field classes apply on the read. Delivery is best effort; after a reconnect the client refetches what is open.
Source: ADR-0040.R13

### Notifications beyond live screens

R27. Phase 1 has an in-app inbox fed by messages and work items, and notification e-mail grouped per person every 5 minutes or in a daily digest, without message text (ADR-0076.R6, ADR-0076.R7). Push notifications are after Phase 1.
Source: ADR-0040.R14, ADR-0040.R14.N1

### i18n

R28. i18n follows ADR-0016.R18 and ADR-0016.R19 with i18next:
- The core catalog's keys are generated from the registry, with English source: `field.<table>.<field>` for columns, and `field.<command_type or query>.<field>` for payload and result fields that are not columns; `enum.<enum>.<value>`; `command.<command_type>` and `query.<query>`; `error.<code>.message` and `.fix`, for errors and check results alike, as DS-04 keeps one catalog.
- Vietnamese UI strings stay in the core catalog (D8); they are drafted and reviewed in Weblate, and CI fails on an empty Vietnamese key in the core catalog.
- Accounting terms in a package's terminology catalog carry a basis like other package content (ADR-0016.R6), so the author verifies them. Vietnamese accounting names for system accounts and keys belong to the terminology catalog of `l10n_vn`, which also names `enum.partner_kind.sole_proprietorship` (ADR-0053.R7, ADR-0053.R16).
- User-entered text is never translated.
Source: ADR-0040.R15, ADR-0040.R15.N1

### Keyboard model

R29. Keyboard model (step 9's measure is keyboard-first, ADR-0003.R9):
- Global: `Ctrl/Cmd+K` command bar; `g` then a letter to go to an area; `?` shows every shortcut; `Esc` closes.
- Forms: `Enter` moves to the next field and `Shift+Enter` back. `F2` or typing opens a lookup. `Alt+N` adds a line and `Alt+Delete` removes one. `Ctrl+Enter` reviews, then confirms.
- Grids: `line_grid`, the repository's TanStack Table grid, keeps the grid keyboard model with the same `Alt` keys (ADR-0077.R5).
- Floorplans add their own keys to the map: `/` search and `Space` select in lists, `Alt+1`–`Alt+9` sections on object pages, `j`/`k` and `c` in worklists, `Alt+Y`/`Alt+R` in the approval view, `Ctrl+/` the assist panel (ADR-0077.R4, ADR-0077.R19).
- Scans: a keyboard-wedge scan into a focused code field ends with the scanner's Enter suffix, which moves to the next field. Every code field on desktop screens accepts wedge scans and resolves them with `EvaluateBarcode` for the field's expected type; a scan is told from typing by the AIM prefix, the suffix and its speed (ADR-0061.R22).
- All shortcuts are registered in one map with translated labels, `check` keeps the map free of clashing keys, and every action works without a mouse.
Source: ADR-0040.R16, ADR-0040.R16.N1, ADR-0040.R16.N2, ADR-0040.R16.N3

### Display, targets and storage

R30. Display:
- Untrusted fields are shown as plain text in a marked "external content" style, never rendered as HTML, with links not clickable. In printed files too they are escaped and never rendered as HTML (ADR-0049.R29).
- Taint: a badge on tainted versions and proposals, with the clearance record.
- Field classes: fields of a class the user lacks are omitted by the server; the form shows a "restricted" placeholder and leaves them out of updates, which keeps their values (ADR-0017.R10).
- Human-only actions ask for a reason where the command requires one.
- Storage: business and personal data never go into browser storage. An unsaved form lives in memory; a draft is a server-side document. Browser storage holds only per-viewer conveniences such as the last column choice.
Source: ADR-0040.R17, ADR-0040.R17.N1

R31. Targets:
- Accessibility (accepted): WCAG 2.2 AA on desktop screens; touch targets of at least 24 by 24 CSS pixels on the PWA's key controls. The densities `compact` (desktop) and `touch` (PWA, coarse pointers) and the theme are design tokens; targets are at least 24 px at `compact` and 44 px at `touch`. axe-core runs on every floorplan in the generated tests (ADR-0077.R7, ADR-0077.R19, ADR-0077.R21).
- Browsers (accepted): the last two versions of Chrome, Edge, Firefox and Safari, and Chrome on Android 10 or later for the warehouse PWA.
- Size (interim, revisited when the Center framework is built): the initial route at most 250 KB of JavaScript gzipped, each further route chunk at most 150 KB gzipped, and the generated schema bundle loaded per area, not all at once. The size targets apply to generated routes.
- Line entry uses `line_grid`, an editable grid on TanStack Table written in the repository, keyboard first, with barcode-capable cells and within the route budget (ADR-0077.R5, ADR-0077.R20).
Source: ADR-0040.R17, ADR-0040.R17.N2, ADR-0040.R17.N3, ADR-0040.R17.N4, ADR-0040.R17.N5

## Invariants

None: the sources of `app` name no `INV` row, and no invariant has the area `app`.

## Edge cases

None: the sources of `app` name no `EC` row, and no edge case has the area `app`.

## Settings

`app` owns no setting key in this chunk.

Reads: `ui.post_review` (R16) and `work.landing_page.<role_template>` (R12); their rows are in the Settings table of chunk 2.

`list_export_max_rows` (R7) is named by ADR-0040 rule 6 and is not a key of `settings.csv`; ADR-0050.R54 states it.

## Conflicts

CONFLICT ADR-0040.D0: ADR-0040.D0.N1 governs, citing ADR-0077.R5 and ADR-0077.R20; the data grid is the in-repo TanStack Table grid. ADR-0040.R20.N2 and ADR-0077.R5 govern the step 9 entry screens, which are generated forms and not hand-built, and ADR-0077.R23 governs renderer v1, whose forms carry `line_grid` (R1).
CONFLICT ADR-0040.R6: ADR-0040.R6.N6 governs saved filters and column choice (list variants are in Phase 1, the browser keeps only the last choice; R7, R14) and ADR-0040.R6.N7, ADR-0077.R5 and ADR-0077.R23 govern the line tables of the command form: `line_grid` by the `editor` annotation, in renderer v1 too, with no hand-built screens (R9).
CONFLICT ADR-0040.R6.N1: ADR-0040.R20.N2 and ADR-0077.R22 govern; the extraction verification screen is the registered custom component `extraction_verification`, not a hand-built screen (R10).
CONFLICT ADR-0040.R6.N2: ADR-0040.R6.N6 is later and governs; saved list filters are list variants in Phase 1, so R11 keeps only that saved analyses are analysis plans. ADR-0040.R20.N2 and ADR-0077.R22 govern the kind: the analysis view is the registered custom component `analysis_view`, not a further screen kind.
CONFLICT ADR-0040.R6.N3: ADR-0066.R21.N1 governs the case view (the `worklist` floorplan, whose right pane also shows an approval view) and ADR-0040.R20.N2 with ADR-0077.R5 governs the step 9 entry screens, which are generated and not hand-built (R12).
CONFLICT ADR-0040.R6.N4: ADR-0040.R20.N2 and ADR-0077.R22 govern; the WO tablet is the registered custom component `work_order_tablet`, not a hand-built screen (R10).
CONFLICT ADR-0040.R7: ADR-0040.R7.N1 governs; the command palette is the command bar with the `resolve_command` assist path (R15, R20, R29).
CONFLICT ADR-0040.R14: ADR-0040.R14.N1 governs; the in-app inbox and notification e-mail are in Phase 1 and only push stays after Phase 1 (R27).
FALSE-POSITIVE ADR-0040.R16.N2: the flagged word describes the `check` that keeps the shortcut map free of clashing keys; the note only adds floorplan keys (R29).
CONFLICT ADR-0040.R16.N3: this note governs the grids bullet of ADR-0040.R16; `line_grid` takes the place of AG Grid and keeps the keyboard model (R29).
CONFLICT ADR-0040.R17: ADR-0040.R17.N2 and ADR-0040.R17.N3 govern the size targets and the grid; the shell and PWA-route sizes and the AG Grid loading clause are not restated (R31).
CONFLICT ADR-0040.R17.N5: this note governs the mark on the targets; accessibility and browser targets are accepted and no longer an open question, while the size targets keep the interim mark of ADR-0040.R17.N2 (R31).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0040.D0 | R1 |
| ADR-0040.D0.N1 | R1 |
| ADR-0040.R1 | R2 |
| ADR-0040.R2 | R3 |
| ADR-0040.R2.N1 | R3 |
| ADR-0040.R3 | R4 |
| ADR-0040.R4 | R5 |
| ADR-0040.R4.N1 | R5 |
| ADR-0040.R4.N2 | R5 |
| ADR-0040.R5 | R6 |
| ADR-0040.R6 | R7-R9 |
| ADR-0040.R6.N1 | R10 |
| ADR-0040.R6.N2 | R11 |
| ADR-0040.R6.N3 | R12 |
| ADR-0040.R6.N4 | R10 |
| ADR-0040.R6.N5 | R13 |
| ADR-0040.R6.N6 | R7, R14 |
| ADR-0040.R6.N7 | R9 |
| ADR-0040.R7 | R15 |
| ADR-0040.R7.N1 | R15 |
| ADR-0040.R9 | R16, R17 |
| ADR-0040.R9.N1 | R16 |
| ADR-0040.R11 | R18 |
| ADR-0040.R12 | R19-R21 |
| ADR-0040.R12.N1 | R19, R20 |
| ADR-0040.R13 | R22-R26 |
| ADR-0040.R13.N1 | R22, R25 |
| ADR-0040.R13.N2 | R22, R25 |
| ADR-0040.R14 | R27 |
| ADR-0040.R14.N1 | R27 |
| ADR-0040.R15 | R28 |
| ADR-0040.R15.N1 | R28 |
| ADR-0040.R16 | R29 |
| ADR-0040.R16.N1 | R29 |
| ADR-0040.R16.N2 | R29 |
| ADR-0040.R16.N3 | R29 |
| ADR-0040.R17 | R30, R31 |
| ADR-0040.R17.N1 | R30 |
| ADR-0040.R17.N2 | R31 |
| ADR-0040.R17.N3 | R31 |
| ADR-0040.R17.N4 | R31 |
| ADR-0040.R17.N5 | R31 |
