Module: app    Chunk: 2 of 2    Source ADRs: ADR-0040, ADR-0066, ADR-0077
Build step(s): 0, 1, 5, 9    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `app` compiled spec, chunk 2: source tree, renderer v1, case view, floorplans, annotation vocabulary, list variants, checks, component library, custom components

## Purpose

`app` is the browser client: the generated renderer, its floorplans and its component library. It owns no table and
computes no business value; every screen is rendered from registered commands, queries and their annotations. This chunk
states the frontend source tree and CI job, renderer v1, the screens owned elsewhere, the case view, and the UI law of
ADR-0077 that `app` is primary for: floorplans, keyboard model, fast data entry, small screens, accessibility, the
annotation vocabulary, user-saved list variants, the mechanical checks, the component library, design tokens, custom
components and the sequence. Chunk 1 states the client rules ADR-0040.R1 to ADR-0040.R17. The assist panel, the command
bar and provenance display (ADR-0077.R13 to ADR-0077.R18) are law of other modules and are only cited.

## Entities and tables

None: `app` owns no table.

Reads: `list_variant` (DDL `docs/design/DS-30-ui.sql`, owner `registry`; R232 to R234), `document`, `reason`.

## Commands and queries

The sources of this chunk register no command or query for `app`. The rules state these commands and this query over
`list_variant`, a table of `registry`:

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateListVariant` | Personal variant: `general_access`. Shared variant: capability `share_list_variant` at `edit` on the leaf `list_variant` under Administration (R233) | Filters, columns, sort and grouping for one `List<Noun>` query; personal or shared with a role (R232) | Stores the variant in `list_variant` | not stated | not stated |
| `UpdateListVariant` | As `CreateListVariant` | not stated | not stated | not stated | not stated |
| `DeleteListVariant` | As `CreateListVariant` | not stated | not stated | not stated | not stated |
| `ListListVariant` | not stated | not stated | Returns the caller's personal variants and those shared with the caller's roles (R234) | not stated | not stated |

Queries and commands of other modules that the rules of this chunk render or call: `ListWorkItem`, `ListWorkCase`,
`ListWorkCaseTimeline`, `GetApprovalProgress`, `EvaluateBarcode`, `ListAllowedCommand`, `ListCustomFieldDefinitions`,
`Approve<Type>`.

Not commands: the checks of `nativeflows-dev check` (R237) and the CI job `frontend` (R203, R238).

## Rules

### Frontend source tree and CI

R201. `frontend/src/` holds:
- `generated/` (types, annotated schemas, catalogs; never edited);
- `routes/` (TanStack Router file routes);
- `renderer/`, `screens/` (the registered custom components, one directory `frontend/src/screens/<name>/` each, R243), `pwa/` (DS-31);
- `decimal/`, `i18n/` and `lib/`.
Source: ADR-0040.R18

R202. File names are kebab-case except where the router fixes them (ADR-0022.R24), which settles ADR-0004.R23.
Source: ADR-0040.R18

R203. Tests and CI:
- The CI job `frontend` runs typecheck, lint, build, Vitest, the checks of ADR-0040.R5, the Vietnamese key check and the size budgets.
- Playwright flows run nightly against the test server's synthetic data, outside the 15-minute limit.
- A frontend dependency in a new category needs an ADR (ADR-0005). ADR-0022.R14, ADR-0022.R17 and ADR-0022.R24 carry notes on this.
Source: ADR-0040.R18

### Renderer v1

R204. Renderer v1 (step 1) holds:
- Shell: sign-in (password with TOTP, or OIDC; ADR-0017) and the session bootstrap, company switch, menu and command bar (ADR-0040.R7.N1).
- Screens: list, record view, command form and query result views, as the floorplans R245 names.
- Flow: simulate, plan, execute, errors, checks and live updates.
- Languages: English and Vietnamese. Vietnamese is a UI language shipped by the core (D8), not an overlay (ADR-0053.R16).
It is enough to operate and test every command (spec 11, B6). From step 5 it also hosts, as generated screens, the desktop warehouse task confirmation (ADR-0023.R22), the work queue (a list of work items) and change proposals.
Source: ADR-0040.R19, ADR-0040.R19.N1

### Screens owned elsewhere

R205. The step 9 entry screens (sales invoice, goods receipt, goods issue, cash receipt, cash payment, journal entry) are generated create and edit forms with the editable line grid (R225), not hand-built screens. Their UX spec is annotation tuning; it is written before step 9 and builds on DS-22 and DS-25, which define those documents. It follows these rules: header fields in keyboard order, the line editor, the review shortcut, and lookups that type ahead. The MISA measure is unchanged.
Source: ADR-0040.R20, ADR-0040.R20.N2

R206. The data grid is the in-repo TanStack Table grid, not AG Grid (R223, R239).
Source: ADR-0040.R20, ADR-0040.R20.N3

R207. Production and planning screens are generated over their queries (ADR-0034.R18; ADR-0024). Owned elsewhere: shop-floor and warehouse flows (DS-31), print (DS-27), list export (DS-33). The extraction verification screen, the work-order tablet, the analysis view and the PWA scanning flows are registered custom components (R243, R244).
Source: ADR-0040.R20, ADR-0040.R20.N2

R208. DS-31 builds the PWA's scanning on ADR-0061:
- BarcodeDetector for EAN/UPC and ITF only, until the scanner check page proves on a device that it passes GS through;
- a WebAssembly decoder for Code 128, GS1-128, DataMatrix and QR;
- wedge capture, the shipped scanner profiles and the check page.
The WebAssembly modules load on first use and are measured apart from the JavaScript budget of ADR-0040.R17 (ADR-0061.R22, ADR-0061.R23).
Source: ADR-0040.R20, ADR-0040.R20.N1

### Case view and case list

R209. The case view is a generated screen kind beside those of ADR-0040.R6. It is the `worklist` floorplan (R212, R218):
- The left pane holds the timeline of ADR-0066.R17, with untrusted text in the "external content" style (ADR-0040.R17).
- The right pane holds the selected artifact as an object page (its record view), an edit form (its command form with the plan panel) or an approval view.
- Editing a draft there is an ordinary update command: Review simulates, and the client computes nothing (ADR-0040.R2).
- The pending commands of ADR-0066.R16 sit above the panes.
The Centers ADR builds on the worklist and overview floorplans (R212 to R219).
Source: ADR-0066.R21, ADR-0066.R21.N1

R210. The case list is a generated screen kind: a list over `ListWorkCase`, beside the work queue list.
Source: ADR-0066.R21

R211. `work.landing_page.<role_template>` chooses a role's home (ADR-0066.R4). Lists, record views, command forms and the keyboard model are unchanged by the case view and the case list.
Source: ADR-0066.R21

### Floorplans

R212. Every route renders exactly one primary floorplan, named by the annotation `x-nativeflows-floorplan` or derived (R214). The floorplans follow SAP Fiori Elements as patterns only; no Fiori or UI5 code is used (R239). Floorplan, code and source:
- List report, `list_report`: a `List<Noun>` query, or a computed query with a row result.
- Object page, `object_page`: a `Get<Noun>` query, or a computed query with a single-object result.
- Create and edit form, `edit_form`: any command; wizard variant for long documents.
- Worklist, `worklist`: `ListWorkItem`, filtered for one Center or one person; for the case view, `ListWorkCaseTimeline` (R209).
- Overview, `overview`: saved analyses (ADR-0060) shown as KPI tiles and charts.
- Plan panel, `plan_panel`: the `simulate` response of the command a form or action sends (ADR-0040.R9).
- Approval view, `approval_view`: a document in `pending_approval` with its approval progress.
Source: ADR-0077.R1

R213. The plan panel is a floorplan of its own because every write in every other floorplan passes through it. It is an overlay, never a route: it opens as a side panel on desktop and as a full-screen sheet on small screens. The assist panel (ADR-0077.R17) is an overlay too.
Source: ADR-0077.R1

R214. Derivation, so that most declarations need no floorplan annotation:
- `List<Noun>` gives `list_report`, and `Get<Noun>` gives `object_page`.
- A command gives `edit_form`; it is a wizard when its payload declares more than one field group and is annotated `wizard: true`.
- `ListWorkItem` gives `worklist`; for the case view, `ListWorkCaseTimeline` does (R209).
- A computed query gives `list_report` for an array result and `object_page` otherwise.
- A subject in state `pending_approval`, opened from its `approval_pending` work item or from an `Approve<Type>` action, gives `approval_view`.
- An overview is declared by its Center (the Centers ADR), which names its saved analyses.
- Every `simulate` of a form or action opens `plan_panel` over the current route.
- A route annotated `custom:<name>` renders the registered custom component of R243.
The screen kinds of ADR-0040.R6 map onto these: List to list report, Record view to object page, Command form to create and edit form, Query result view to list report or object page by result shape.
Source: ADR-0077.R2

### Regions and annotation sources per floorplan

R215. List report. Regions: a filter bar with variant switch, the table, a bulk-action toolbar and a scope banner (`is_scope_filtered`, ADR-0040.R6). Annotations used: `list-defaults` (columns, sort, filters, variants), `search`, `actions` (bulk-capable ones), `title` (row title), `importance`.
Source: ADR-0077.R3

R216. Object page. Regions: a header (title, description, state badge, header facets, primary actions); sections from field groups; line-item tables from `line-columns`; related objects from `links`; the version history, attachments and audit link of ADR-0040.R6; and the assist panel. Annotations used: `title`, `header-facets`, `group`, `order`, `line-columns`, `links`, `actions`, `importance`, `hidden-when`, `read-only-when`.
Source: ADR-0077.R3

R217. Create and edit form. Regions: header field groups in keyboard order; the editable line grid (R223); the plan panel; and errors and checks beside their fields (ADR-0040.R10, ADR-0040.R11). The wizard variant shows one field group per step, with a final review step that is the plan panel. Annotations used: `group`, `order`, `lookup`, `default-from`, `hidden-when`, `read-only-when`, `scan`, `ai-fillable`, `line-columns`.
Source: ADR-0077.R3

R218. Worklist. Regions: queue filters (kind, owner, due, taint), the item list, a right pane that opens the subject as an object page, edit form or approval view, and bulk actions within `work.bulk_review_max_items` (ADR-0066.R16; ADR-0042 bulk review). Annotations used: the item kind's `title` and `header-facets`, and the subject's own annotations in the pane.
Source: ADR-0077.R3

R219. Overview. Regions: KPI tiles, charts and tables of saved analyses, each linking to its list report. Tiles plot server cells only (ADR-0040.R2.N1), so the overview has no field annotations; it names saved analyses.
Source: ADR-0077.R3

R220. Plan panel. Regions: the journal lines and stock movements filtered by field class, versions, events, side information, check results, the policy outcome and review reasons (ADR-0067); after a plan change, the diff against the reviewed plan (ADR-0040.R9). For a draft or proposal written by an agent, it adds a field-level diff against the previous version and the taint badge (ADR-0077.R15).
Source: ADR-0077.R3

R221. Approval view. Regions: the document summary (the object page header and sections), `GetApprovalProgress`, the diff of this version against the last approved one, the taint badge and clearance record, and Approve and Reject with a reason field. Reject takes a reason of kind `reject` (`reject_reason_id`, ADR-0074.R14), required while `documents.reason_required.reject` is true, and the text `reason`, which stays required for both decisions (ADR-0055.R9). Approve stays subject to segregation of duties (ADR-0017.R16).
Source: ADR-0077.R3

### Keyboard model

R222. ADR-0040.R16 stays the global keyboard model, and each floorplan adds:
- List report: `/` focuses search; arrow keys move between rows; `Space` selects a row; `Enter` opens it; `Shift+arrow` extends the selection; `Alt+A` opens bulk actions.
- Object page: `Alt+1` to `Alt+9` jump to sections; `e` opens the edit form; `Alt+.` opens the action menu.
- Create and edit form: `Enter` moves to the next field and `Shift+Enter` back; `F2` opens value help; `Ctrl+Enter` reviews, then confirms. In a wizard, `Alt+PageDown` goes to the next step and `Alt+PageUp` back.
- Worklist: `j` and `k` move between items; `Enter` opens the item in the pane; `c` claims it; `Esc` returns to the list.
- Overview: `Tab` moves between tiles, and `Enter` opens a tile's list report.
- Plan panel: `Ctrl+Enter` confirms; `Esc` returns to the form with the edits kept.
- Approval view: `Alt+Y` approves and `Alt+R` rejects; both ask for a reason when the command requires one.
- Everywhere: `Ctrl+/` opens the assist panel and `Ctrl/Cmd+K` the command bar (ADR-0077.R18).
All shortcuts go into the one shortcut map of ADR-0040.R16, which a check keeps free of conflicts (R237).
Source: ADR-0077.R4

### Fast data entry

R223. Fast data entry is part of the create and edit form, not of hand-built screens. A line array with `line-columns` editor `grid` renders as `line_grid`, an editable grid component written in the repository on TanStack Table, keyboard first, with barcode-capable cells and within the 150 KB route budget (R239). Its keyboard model is that of ADR-0040.R16:
- `Enter` goes down the column and `Tab` across;
- `Alt+N` adds a line and `Alt+Delete` removes one;
- typing in a reference cell opens value help;
- a cell of a field annotated `scan` takes wedge and camera scans as a scan input does;
- pasting a block of cells is parsed by the grid's own paste handler.
Totals and line amounts come from simulation only (ADR-0040.R2).
Source: ADR-0077.R5

R224. Barcode input. A field annotated `scan` takes wedge scans on desktop and camera scans in the PWA, and resolves them with `EvaluateBarcode` for the field's expected type (ADR-0061.R12, ADR-0061.R17, ADR-0061.R22). The annotation also carries the GS1 Application Identifier to field mapping that ADR-0061.R17 leaves unnamed.
Source: ADR-0077.R5

R225. The step 9 measure. The step 9 entry screens of R205 are generated create and edit forms with a line grid, and their UX spec is annotation tuning. The measure against MISA is unchanged (ADR-0003.R9).
Source: ADR-0077.R5

### Small screens and accessibility

R226. Small screens and the PWA. The widths are desktop (1024 px and wider), tablet (600 to 1023 px) and phone (below 600 px).
- Importance: fields of `importance` `low` are hidden below desktop width, and `medium` ones below tablet width. A hidden field stays reachable through the record's "all fields" section. An update that does not mention a hidden field keeps its value, as for field-class placeholders (ADR-0040.R17).
- A list report becomes cards showing the title and the high fields.
- Object page sections become an accordion.
- The line grid becomes line cards with an edit sheet.
- The plan panel, the approval view and the assist panel open as full-screen sheets.
- The worklist shows the list, and the pane opens over it.
- Warehouse and shop floor: the PWA (ADR-0071; DS-31) uses the same floorplans at `touch` density (R242) with camera scan inputs. Scanning flows and the work-order tablet are custom components (R243).
Source: ADR-0077.R6

R227. Accessibility is WCAG 2.2 AA (ADR-0040.R17), built into the components:
- The WAI-ARIA Authoring Practices patterns are the reference for each component (grid, combobox, dialog, tabs, tree).
- Focus order follows field order; every control has a programmatic label from its i18n key.
- Status is never shown by color alone: state, taint and AI provenance carry an icon and text.
- Targets are at least 24 by 24 CSS pixels at `compact` density and 44 by 44 at `touch` density.
- Motion respects `prefers-reduced-motion`.
- The generated Playwright tests run axe-core on every floorplan (R238).
Source: ADR-0077.R7

### Annotation vocabulary

R228. Annotations are written in the Python declarations: on payload and result fields, and on the `CommandDeclaration` or `QueryDeclaration` object (ADR-0073.R1). `generate` emits them as `x-nativeflows-*` keys in the annotated JSON Schemas (ADR-0022.R17). The vocabulary is closed: a key outside R229 and R230 fails `check`; every key has one renderer, listed in the renderer's key map, and `check` compares the map with this vocabulary. Labels and help never travel in annotations: they come from the generated i18n keys of ADR-0040.R15.
Source: ADR-0077.R8

R229. Per-field keys. The keys of ADR-0040.R4 stay; key, status and meaning:
- `x-nativeflows-widget` (derived; extended): semantic type from the field's type: Amount, Quantity, UnitPrice, ExchangeRate, Percent, BusinessDate, enums, references, plus `State` for a lifecycle `state` column.
- `x-nativeflows-scale-from` (derived; required): the sibling currency field of a money field, or unit field of a quantity field.
- `x-nativeflows-ref` (derived): the referenced table, so partner and item references render as references.
- `x-nativeflows-field-class` (derived): `cost`, `margin` and the other field classes (ADR-0017.R10): masked by the server, shown as "restricted".
- `x-nativeflows-untrusted` (derived): external content style (ADR-0029; ADR-0040.R17).
- `x-nativeflows-group`, `x-nativeflows-order` (hint): field group and order.
- `x-nativeflows-hidden-when`, `x-nativeflows-read-only-when` (hint; extended): simple conditions on other payload fields, and also on the subject's `state`.
- `x-nativeflows-lookup` (hint; extended): value help: the `List<Noun>` query, its display columns, and `depends_on`, filters taken from other fields of the payload.
- `x-nativeflows-importance` (new): `high`, `medium` (default) or `low`; drives the responsive display of R226.
- `x-nativeflows-default-from` (new): a context path the form fills before the user types, such as `subject.partner_id` when a form opens from an object page. It never invents a value (ADR-0040.R3): server defaults keep coming from the server.
- `x-nativeflows-scan` (new): the field accepts scans: expected barcode type, and the GS1 Application Identifier mapping (R224).
- `x-nativeflows-ai-fillable` (new): `true` lets the assist panel and document intake propose a value for this field into a draft; default `false`. It is a UI and intake hint, checked by `check` (R237); the dispatcher adds no floor for it, because taint, drafts only, human confirmation and the permission intersection already bound agent writes.
How provenance is shown is not an annotation: it comes from the data (ADR-0077.R15).
Source: ADR-0077.R9

R230. Per-entity and per-floorplan keys; key, status, where it is written and meaning:
- `x-nativeflows-list-defaults` (hint; extended; `List<Noun>` result): default columns (at most 8, R237), sort and filters, plus named `variants` declared in code. Users also save variants (R232).
- `x-nativeflows-line-columns` (hint; extended; line array): line-item table: columns, and `editor` `grid` or `table`.
- `x-nativeflows-floorplan` (new; declaration): floorplan code where derivation (R214) is not enough; `custom:<name>`; `wizard: true`.
- `x-nativeflows-title` (new; `Get<Noun>`, `List<Noun>` result): the title field and the description field.
- `x-nativeflows-header-facets` (new; `Get<Noun>` result): key facts in the object page header: up to 6 fields, each with an optional facet group.
- `x-nativeflows-actions` (new; `Get<Noun>`, `List<Noun>` result): command types offered on the subject: their order, which one is primary, and which are bulk-capable.
- `x-nativeflows-links` (new; `Get<Noun>` result): related objects: a `List<Noun>` query with the filter that binds it to this subject.
- `x-nativeflows-search` (new; `List<Noun>` result): the fields the `search` filter matches, as the query declares them.
- `x-nativeflows-assist` (new; declaration): suggested question keys and agent actions for the assist panel (ADR-0077.R17).
- `x-nativeflows-custom-values` (kept, ADR-0074; `Get<Noun>`, `List<Noun>` result, command payload): the table whose company-defined fields the renderer reads through `ListCustomFieldDefinitions`.
Source: ADR-0077.R10

R231. The closed vocabulary is the keys of ADR-0040 and ADR-0074 plus the new keys of R229 and R230. Of the kept keys, `widget`, `hidden-when`, `read-only-when`, `lookup`, `list-defaults` and `line-columns` are extended and `scale-from` is required.
Source: ADR-0077.R10

### User-saved list variants

R232. User-saved variants are in Phase 1, because the list report has a variant switch. A variant is personal, or shared with a role. It stores filters, columns, sort and grouping for one `List<Noun>` query, server-side in `list_variant` (`docs/design/DS-30-ui.sql`, owner `registry`). A variant may be the default of its owner or of its role.
Source: ADR-0077.R10a

R233. The commands are `CreateListVariant`, `UpdateListVariant` and `DeleteListVariant`. A personal variant is checked on `general_access`. A shared one needs the capability `share_list_variant` at `edit` on the leaf `list_variant` under Administration, which `owner` and `it_administrator` hold through Administration `full`; a company may grant it to other roles.
Source: ADR-0077.R10a

R234. `ListListVariant` returns the caller's personal variants and those shared with the caller's roles. A variant never widens what the query returns: its filters run inside the caller's permission and record scope. A personal variant name is unique per owner and query (`ux_list_variant_name`). A shared variant name is unique per role and query, whoever owns it (`ux_list_variant_shared_name`). Declared variants of `list-defaults` stay and show beside the saved ones; column choice is not only a browser-storage convenience (ADR-0040.R6).
Source: ADR-0077.R10a

### What is not annotated; required annotations

R235. Not annotated, because the registry already declares it:
- Actions per state. An action's availability comes from the command's `subject_table` and `allowed_states` and from `ListAllowedCommand` (ADR-0040.R8). `actions` orders them but never adds one.
- Confirmation level. Every write goes through the plan panel. `ui.post_review` decides when it is skipped (ADR-0067). A command that needs a reason asks for it. There is no other confirmation level, so none is annotated.
- Field-class masking is done by the server; the renderer only shows the placeholder.
Source: ADR-0077.R11

R236. Required annotations, checked by R237:
- every `List<Noun>` result has `title` and `list-defaults`;
- every `Get<Noun>` result has `title` and `header-facets`;
- every money or quantity field has `scale-from`;
- every reference field in a payload has `lookup`.
Anything else is optional. Fields without `group` fall into the generated group "General", and the renderer falls back to declaration order.
Source: ADR-0077.R12

### Mechanical consistency

R237. These checks join `nativeflows-dev check` (ADR-0022.R13; ADR-0073.R2), each named after the rule it enforces:
- required annotations are present (R236);
- every annotation key is in the vocabulary, and every key has a renderer (R228);
- every label and suggested-question key exists in the English catalog (ADR-0040.R5);
- money is paired with currency and quantity with unit (`scale-from`);
- a list has at most 8 default columns, and an object page header at most 6 facets;
- every action names a registered command whose `subject_table` is the subject's table;
- every value help names a registered query, and each `depends_on` names a payload field;
- every assist action names an `is_draft_only` command;
- `ai-fillable` appears only on payload fields of commands that create or update drafts;
- every `custom:<name>` names a registered custom component (R243);
- the shortcut map has no conflicts within a floorplan and uses no key the browser reserves.
The limits on default columns and header facets live in `.github/assurance.toml` (ADR-0073.R16).
Source: ADR-0077.R19

R238. Generated UI tests, run by the `frontend` job:
- one Playwright test per floorplan and declaration, against the renderer with recorded responses;
- a keyboard path through the floorplan;
- axe-core;
- visual regression with Playwright's screenshot comparison, one baseline per floorplan, density and width, not per screen.
The nightly Playwright flows of R203 stay.
Source: ADR-0077.R19

### Component library and design tokens

R239. The component library is shadcn/ui with Tailwind CSS on Base UI, version pinned. Around it:
- TanStack Table for lists and for `line_grid`, the editable line grid written in the repository (R223);
- react-hook-form under the renderer's own form builder;
- i18next (ADR-0040.R15);
- `@axe-core/playwright` for tests.
Tailwind CSS and Base UI are the foundations of shadcn/ui, and TanStack Table joins the TanStack family of ADR-0002, so neither opens a new dependency category. AG Grid is not in the stack; it comes back only through an ADR, if a measured need appears. `@axe-core/playwright` opens the accessibility-testing category (ADR-0005).
Source: ADR-0077.R20

R240. Rejected component libraries: MUI, Ant Design, Fluent, PrimeReact, SAP UI5 Web Components, Carbon, react-admin, RJSF and Formily. They bring their own data models, add bundle weight against the 250 KB budget, or have paid tiers.
Source: ADR-0077.R20

R241. The generator composes only from this library and the renderer's domain components (amount, quantity, reference, state badge, provenance mark, scan input, line grid, plan panel, assist panel). A component outside them fails the `frontend` lint.
Source: ADR-0077.R20

R242. Design tokens are CSS variables, which Tailwind reads:
- color roles: surface, text, primary, danger, warning, success, focus, plus `provenance-ai`, `provenance-document` and `taint`;
- a type scale and a spacing scale;
- radius and elevation.
The densities are `compact` (32 px rows and 8 px spacing step, the desktop default) and `touch` (44 px targets and 12 px spacing step, the default in the PWA and on coarse pointers). The viewer's density choice is a per-viewer convenience in browser storage (ADR-0040.R17). Light and dark themes share the roles, and every text pair meets WCAG AA contrast, which the token check verifies. A theme changes only token values, never components.
Source: ADR-0077.R21

### Custom components

R243. A custom component is a screen that no floorplan fits. Each one:
- is registered by name, with its defining ADR or design item;
- lives in `frontend/src/screens/<name>/`;
- is reached through `custom:<name>`;
- uses the tokens, the provenance style, the assist panel and the trust rules;
- calls only registered commands and queries.
`check` reports the share of generated routes. Below 85% the next custom component needs the author's look.
Source: ADR-0077.R22

R244. Registered custom components:
- `extraction_verification` (ADR-0057.R22);
- `work_order_tablet` (ADR-0071.R14);
- `analysis_view` (ADR-0060.R17);
- `scan_flow`, the PWA scanning flows (ADR-0061; DS-31);
- `conversation_view` and `notification_inbox` (ADR-0076.R8).
The work-center queue of ADR-0071 is not a kanban component in Phase 1: it renders as a worklist grouped by state. An MRP planning board or a warehouse bin map would each need a new ADR.
Source: ADR-0077.R22

### Sequence

R245. Sequence:
- Declaration format. The annotation slots of R229 and R230 are fields of the declaration format (ADR-0073 defines it), so that Sonnet drafts them with every declaration.
- Renderer v1 (R204, step 1) renders the list report (with variants), object page, create and edit form (with `line_grid`) and plan panel. It is the test harness during the headless steps 0–5.
- The worklist and approval view follow with the work queue at step 5. The overview follows with the Centers.
- The `assistant` agent, the assist panel, natural-language filters and the command bar's `resolve_command` arrive at step 5, with the work queue; the evaluation set of ADR-0077.R13 is a step 5 gate item (`docs/runbook/steps-5-9.md`).
- The assistant is one of the Phase 1 agent types (`assistant`, `analysis`, `bank_matching`, `purchase_invoice`, `document_reader`, `planning`). It routes questions that need figures to `analysis`, and on request drafts what the deferred agents would help with, such as gateway settings (no advisor in Phase 1), mappings and artifacts (ADR-0078.R1, ADR-0078.R8).
Source: ADR-0077.R23, ADR-0077.R23.N1

## Invariants

None: the dossier of `app` holds no `INV` row; no invariant has the area `app` and no unit of the module names one.

## Edge cases

None: the dossier of `app` holds no `EC` row; no edge case has the area `app` and no unit of the module names one.

## Settings

The rules of this chunk use these keys of `settings.csv`. The area is the catalog's `area` column; no key has the area `app`.

| Key | Area | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- | --- |
| `ui.post_review` | `ui` | enum `always`, `on_exceptions` | company | `always` | R16, R235 |
| `work.landing_page.<role_template>` | `work` | enum `work_queue`, `case_list` | company | `work_queue` | R12, R211 |
| `work.bulk_review_max_items` | `work` | integer, bounds `1..500` | company | `50` | R218 |
| `documents.reason_required.reject` | `documents` | boolean | company | `true` | R221 |

## UI annotations

None: the sources hold no ADR-0077 annotation for this module; `app` declares no command or query. The annotation
vocabulary itself is law of this chunk (R228 to R231, R236), as are the floorplan codes (R212) and the registered custom
components (R244). The rules name one work item kind of another module, `approval_pending` (R214).

## Conflicts

CONFLICT ADR-0040.R18: the directory `screens/` holds registered custom components, not hand-built screens; ADR-0077.R22 governs (R201, R243).
CONFLICT ADR-0040.R19: the command form of renderer v1 carries the editable `line_grid` in place of plain line tables; ADR-0077.R23 governs (R245). The palette of the shell is the command bar; ADR-0040.R7.N1 governs (R204).
CONFLICT ADR-0040.R20: the step 9 entry screens are generated forms and the grid is TanStack Table; ADR-0040.R20.N2, ADR-0040.R20.N3 and ADR-0077.R5 govern (R205, R206).
CONFLICT ADR-0040.R20.N2: this later note of 2026-11-21 is applied over the rule text on hand-built screens and their UX spec; it is the governing text of R205 and R207.
CONFLICT ADR-0066.R21: the closing sentence that the hand-built screens stay unchanged no longer holds for the step 9 entry screens; ADR-0077.R5 governs (R225), and the right pane also shows an approval view by ADR-0066.R21.N1.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0040.R18 | R201, R202, R203 |
| ADR-0040.R19 | R204 |
| ADR-0040.R19.N1 | R204 |
| ADR-0040.R20 | R205, R206, R207, R208 |
| ADR-0040.R20.N1 | R208 |
| ADR-0040.R20.N2 | R205, R207 |
| ADR-0040.R20.N3 | R206 |
| ADR-0066.R21 | R209, R210, R211 |
| ADR-0066.R21.N1 | R209 |
| ADR-0077.R1 | R212, R213 |
| ADR-0077.R2 | R214 |
| ADR-0077.R3 | R215, R216, R217, R218, R219, R220, R221 |
| ADR-0077.R4 | R222 |
| ADR-0077.R5 | R223, R224, R225 |
| ADR-0077.R6 | R226 |
| ADR-0077.R7 | R227 |
| ADR-0077.R8 | R228 |
| ADR-0077.R9 | R229 |
| ADR-0077.R10 | R230, R231 |
| ADR-0077.R10a | R232, R233, R234 |
| ADR-0077.R11 | R235 |
| ADR-0077.R12 | R236 |
| ADR-0077.R19 | R237, R238 |
| ADR-0077.R20 | R239, R240, R241 |
| ADR-0077.R21 | R242 |
| ADR-0077.R22 | R243, R244 |
| ADR-0077.R23 | R245 |
| ADR-0077.R23.N1 | R245 |
