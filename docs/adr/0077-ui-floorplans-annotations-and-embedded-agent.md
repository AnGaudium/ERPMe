# ADR-0077: UI floorplans, annotation vocabulary and embedded agent interaction

Status: accepted (2026-11-21) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5; proposed 2026-11-19) after three review rounds, the fixes verified by Claude Opus 5.5. Design item: DS-30. Related decisions: D2, D8, D12, D14. Principles 1, 3, 6, 8, 12, 13. ADR-0002, ADR-0008, ADR-0016, ADR-0017, ADR-0022, ADR-0029, ADR-0040, ADR-0042, ADR-0043, ADR-0050, ADR-0051, ADR-0054, ADR-0055, ADR-0057, ADR-0060, ADR-0061, ADR-0063, ADR-0064, ADR-0065, ADR-0066, ADR-0067, ADR-0071, ADR-0073, ADR-0076.

## Decision

The UI is generated from metadata, not hand-built. Every screen is one of seven **floorplans**. The Python declarations of ADR-0073 carry a small, closed **annotation vocabulary**, which `generate` emits as `x-nativeflows-*` keys. The renderer composes each floorplan from **one component library** and its design tokens. Screens that fit no floorplan are **custom components**, registered by name, each with its own ADR; the target is that 85–90% of screens are generated.

**Embedded agent.** The agent inside the UI is an agent like any other:
- it calls the same registered commands and queries as external agents, through the same tool lists, and no endpoint exists only for the UI;
- it works in a side panel scoped to what the user is looking at, never as a separate chat application;
- it reads, explains and drafts. Only a person submits, posts, approves or sends. The assistant is never promoted to `active`, so its drafts never pass the ADR-0065 gateway.

**Mechanical consistency.** `nativeflows-dev check` enforces the vocabulary (ADR-0073 rule 2), so consistency never depends on a person reading code. Playwright tests are generated per floorplan, with visual regression.

**Why now.** The annotations must exist before Sonnet drafts the command and query declarations (ADR-0073 rule 4), so that each declaration carries them from the start. Build steps 0–5 run headless and are accepted through an agent over MCP. Meanwhile the generated UI serves as the test harness, and it becomes the product UI later without a rewrite. The Centers ADR (next) builds on the worklist and overview floorplans.

### Rules

**Floorplans**

1. Every route renders exactly one primary floorplan, named by the annotation `x-nativeflows-floorplan` or derived (rule 2). The seven floorplans, after SAP Fiori Elements, are used as patterns only; no Fiori or UI5 code is used (rule 20):

   | Floorplan | Code | Source |
   | --- | --- | --- |
   | List report | `list_report` | a `List<Noun>` query, or a computed query with a row result |
   | Object page | `object_page` | a `Get<Noun>` query, or a computed query with a single-object result |
   | Create and edit form | `edit_form` | any command; wizard variant for long documents |
   | Worklist | `worklist` | `ListWorkItem`, filtered for one Center or one person; for the case view, `ListWorkCaseTimeline` (ADR-0066 rule 21) (review note, 2026-11-21) |
   | Overview | `overview` | saved analyses ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md)) shown as KPI tiles and charts |
   | Plan panel | `plan_panel` | the `simulate` response of the command a form or action sends (ADR-0040 rule 9) |
   | Approval view | `approval_view` | a document in `pending_approval` with its approval progress |

   The plan panel is a floorplan of its own because every write in every other floorplan passes through it. It is an overlay, never a route: it opens as a side panel on desktop and as a full-screen sheet on small screens. The assist panel (rule 17) is an overlay too.

2. Derivation, so that most declarations need no floorplan annotation:
   - `List<Noun>` gives `list_report`, and `Get<Noun>` gives `object_page`.
   - A command gives `edit_form`; it is a wizard when its payload declares more than one field group and is annotated `wizard: true`.
   - `ListWorkItem` gives `worklist`; for the case view, `ListWorkCaseTimeline` does (ADR-0066 rule 21). (review note, 2026-11-21)
   - A computed query gives `list_report` for an array result and `object_page` otherwise.
   - A subject in state `pending_approval`, opened from its `approval_pending` work item or from an `Approve<Type>` action, gives `approval_view`.
   - An overview is declared by its Center (the Centers ADR), which names its saved analyses.
   - Every `simulate` of a form or action opens `plan_panel` over the current route.
   - A route annotated `custom:<name>` renders the registered custom component of rule 22.

   ADR-0040 rule 6's screen kinds map onto these: List to list report, Record view to object page, Command form to create and edit form, Query result view to list report or object page by result shape. The case view of ADR-0066 is a worklist with its right pane showing an object page or an edit form.

3. Regions and annotation sources of each floorplan:
   - **List report.**
     - Regions: a filter bar with variant switch, the table, a bulk-action toolbar and a scope banner (`is_scope_filtered`, ADR-0040 rule 6).
     - Annotations used: `list-defaults` (columns, sort, filters, variants), `search`, `actions` (bulk-capable ones), `title` (row title), `importance`.
   - **Object page.**
     - Regions: a header (title, description, state badge, header facets, primary actions); sections from field groups; line-item tables from `line-columns`; related objects from `links`; the version history, attachments and audit link of ADR-0040 rule 6; and the assist panel.
     - Annotations used: `title`, `header-facets`, `group`, `order`, `line-columns`, `links`, `actions`, `importance`, `hidden-when`, `read-only-when`.
   - **Create and edit form.**
     - Regions: header field groups in keyboard order; the editable line grid (rule 5); the plan panel; and errors and checks beside their fields (ADR-0040 rules 10, 11). The wizard variant shows one field group per step, with a final review step that is the plan panel.
     - Annotations used: `group`, `order`, `lookup`, `default-from`, `hidden-when`, `read-only-when`, `scan`, `ai-fillable`, `line-columns`.
   - **Worklist.**
     - Regions: queue filters (kind, owner, due, taint), the item list, a right pane that opens the subject as an object page, edit form or approval view, and bulk actions within `work.bulk_review_max_items` (ADR-0066 rule 16; ADR-0042 bulk review).
     - Annotations used: the item kind's `title` and `header-facets`, and the subject's own annotations in the pane.
   - **Overview.**
     - Regions: KPI tiles, charts and tables of saved analyses, each linking to its list report.
     - Tiles plot server cells only (ADR-0040 rule 2 note), so the overview has no field annotations; it names saved analyses.
   - **Plan panel.**
     - Regions: the journal lines and stock movements filtered by field class, versions, events, side information, check results, the policy outcome and review reasons (ADR-0067); after a plan change, the diff against the reviewed plan (ADR-0040 rule 9).
     - For a draft or proposal written by an agent, it adds a field-level diff against the previous version and the taint badge (rule 15).
   - **Approval view.**
     - Regions: the document summary (the object page header and sections), `GetApprovalProgress`, the diff of this version against the last approved one, the taint badge and clearance record, and Approve and Reject with a reason field. Reject takes a reason of kind `reject` (`reject_reason_id`, ADR-0074 rule 14), required while `documents.reason_required.reject` is true, and the text `reason`, which stays required for both decisions (ADR-0055 rule 9). (review note, 2026-11-21)
     - Approve stays subject to segregation of duties (ADR-0017 rule 16).

4. Keyboard model. ADR-0040 rule 16 stays the global model, and each floorplan adds:
   - **List report:** `/` focuses search; arrow keys move between rows; `Space` selects a row; `Enter` opens it; `Shift+arrow` extends the selection; `Alt+A` opens bulk actions.
   - **Object page:** `Alt+1` to `Alt+9` jump to sections; `e` opens the edit form; `Alt+.` opens the action menu.
   - **Create and edit form:** `Enter` moves to the next field and `Shift+Enter` back; `F2` opens value help; `Ctrl+Enter` reviews, then confirms. In a wizard, `Alt+PageDown` goes to the next step and `Alt+PageUp` back.
   - **Worklist:** `j` and `k` move between items; `Enter` opens the item in the pane; `c` claims it; `Esc` returns to the list.
   - **Overview:** `Tab` moves between tiles, and `Enter` opens a tile's list report.
   - **Plan panel:** `Ctrl+Enter` confirms; `Esc` returns to the form with the edits kept.
   - **Approval view:** `Alt+Y` approves and `Alt+R` rejects; both ask for a reason when the command requires one.
   - **Everywhere:** `Ctrl+/` opens the assist panel and `Ctrl/Cmd+K` the command bar (rule 18).

   All shortcuts go into the one shortcut map of ADR-0040 rule 16, which a check keeps free of conflicts (rule 19).

5. Fast data entry is part of the create and edit form, not of hand-built screens:
   - **The line grid.** A line array with `line-columns` editor `grid` renders as `line_grid`, an editable grid component written in the repository on TanStack Table, keyboard first, with barcode-capable cells and within the 150 KB route budget (rule 20). Its keyboard model is ADR-0040 rule 16's:
     - `Enter` goes down the column and `Tab` across;
     - `Alt+N` adds a line and `Alt+Delete` removes one;
     - typing in a reference cell opens value help;
     - a cell of a field annotated `scan` takes wedge and camera scans as a scan input does;
     - pasting a block of cells is parsed by the grid's own paste handler.

     Totals and line amounts come from simulation only (ADR-0040 rule 2).
   - **Barcode input.** A field annotated `scan` takes wedge scans on desktop and camera scans in the PWA, and resolves them with `EvaluateBarcode` for the field's expected type ([ADR-0061](0061-barcodes.md) rules 12, 17, 22). The annotation also carries the GS1 Application Identifier to field mapping that ADR-0061 rule 17 left unnamed.
   - **The step 9 measure.** The six step 9 entry screens of ADR-0040 rule 20 (sales invoice, goods receipt, goods issue, cash receipt, cash payment, journal entry) become generated create and edit forms with a line grid. Their UX spec becomes annotation tuning. The measure against MISA is unchanged (ADR-0003 R9).

6. Small screens and the PWA. Three widths: desktop (1024 px and wider), tablet (600 to 1023 px) and phone (below 600 px).
   - **Importance.** Fields of `importance` `low` are hidden below desktop width, and `medium` ones below tablet width. A hidden field stays reachable through the record's "all fields" section. An update that does not mention a hidden field keeps its value, as for field-class placeholders (ADR-0040 rule 17).
   - **Per floorplan:**
     - a list report becomes cards showing the title and the high fields;
     - object page sections become an accordion;
     - the line grid becomes line cards with an edit sheet;
     - the plan panel, the approval view and the assist panel open as full-screen sheets;
     - the worklist shows the list, and the pane opens over it.
   - **Warehouse and shop floor.** The PWA ([ADR-0071](0071-work-orders-and-shop-floor-execution.md); DS-31) uses the same floorplans at `touch` density (rule 21) with camera scan inputs. Scanning flows and the work-order tablet are custom components (rule 22).

7. Accessibility is WCAG 2.2 AA (ADR-0040 rule 17), built into the components:
   - The WAI-ARIA Authoring Practices patterns are the reference for each component (grid, combobox, dialog, tabs, tree).
   - Focus order follows field order; every control has a programmatic label from its i18n key.
   - Status is never shown by color alone: state, taint and AI provenance carry an icon and text.
   - Targets are at least 24 by 24 CSS pixels at `compact` density and 44 by 44 at `touch` density.
   - Motion respects `prefers-reduced-motion`.
   - The generated Playwright tests run axe-core on every floorplan (rule 19).

**Annotation vocabulary**

8. Annotations are written in the Python declarations: on payload and result fields, and on the `CommandDeclaration` or `QueryDeclaration` object (ADR-0073 rule 1). `generate` emits them as `x-nativeflows-*` keys in the annotated JSON Schemas (ADR-0022 rule 17). The vocabulary is closed:
   - a key outside the two tables below fails `check`;
   - every key has one renderer, listed in the renderer's key map, and `check` compares the map with this vocabulary.

   Labels and help never travel in annotations: they come from the generated i18n keys of ADR-0040 rule 15.

9. Per field. The keys of ADR-0040 rule 4 stay; some are extended, and four keys are new:

   | Key | Status | Meaning |
   | --- | --- | --- |
   | `x-nativeflows-widget` | derived; extended | Semantic type from the field's type: Amount, Quantity, UnitPrice, ExchangeRate, Percent, BusinessDate, enums, references, plus `State` for a lifecycle `state` column |
   | `x-nativeflows-scale-from` | derived; now required | The sibling currency field of a money field, or unit field of a quantity field |
   | `x-nativeflows-ref` | derived | The referenced table, so partner and item references render as references |
   | `x-nativeflows-field-class` | derived | `cost`, `margin` and the other field classes (ADR-0017 rule 10): masked by the server, shown as "restricted" |
   | `x-nativeflows-untrusted` | derived | External content style (ADR-0029; ADR-0040 rule 17) |
   | `x-nativeflows-group`, `x-nativeflows-order` | hint | Field group and order |
   | `x-nativeflows-hidden-when`, `x-nativeflows-read-only-when` | hint; extended | Simple conditions on other payload fields, and now also on the subject's `state` |
   | `x-nativeflows-lookup` | hint; extended | Value help: the `List<Noun>` query, its display columns, and `depends_on`, filters taken from other fields of the payload |
   | `x-nativeflows-importance` | new | `high`, `medium` (default) or `low`; drives the responsive display of rule 6 |
   | `x-nativeflows-default-from` | new | A context path the form fills before the user types, such as `subject.partner_id` when a form opens from an object page. It never invents a value (ADR-0040 rule 3): server defaults keep coming from the server |
   | `x-nativeflows-scan` | new | The field accepts scans: expected barcode type, and the GS1 Application Identifier mapping (rule 5) |
   | `x-nativeflows-ai-fillable` | new | `true` lets the assist panel and document intake propose a value for this field into a draft; default `false`. A UI and intake hint, checked by `check` (rule 19); the dispatcher adds no floor for it, because taint, drafts only, human confirmation and the permission intersection already bound agent writes |

   How provenance is shown is not an annotation: it comes from the data (rule 15).

10. Per entity or floorplan. Three keys are kept (two of them extended) and seven are new:

    | Key | Status | On | Meaning |
    | --- | --- | --- | --- |
    | `x-nativeflows-list-defaults` | hint; extended | `List<Noun>` result | Default columns (at most 8, rule 19), sort and filters, plus named `variants` declared in code. Users also save variants (rule 10a) |
    | `x-nativeflows-line-columns` | hint; extended | line array | Line-item table: columns, and `editor` `grid` or `table` |
    | `x-nativeflows-floorplan` | new | declaration | Floorplan code where derivation (rule 2) is not enough; `custom:<name>`; `wizard: true` |
    | `x-nativeflows-title` | new | `Get<Noun>`, `List<Noun>` result | The title field and the description field |
    | `x-nativeflows-header-facets` | new | `Get<Noun>` result | Key facts in the object page header: up to 6 fields, each with an optional facet group |
    | `x-nativeflows-actions` | new | `Get<Noun>`, `List<Noun>` result | Command types offered on the subject: their order, which one is primary, and which are bulk-capable |
    | `x-nativeflows-links` | new | `Get<Noun>` result | Related objects: a `List<Noun>` query with the filter that binds it to this subject |
    | `x-nativeflows-search` | new | `List<Noun>` result | The fields the `search` filter matches, as the query declares them |
    | `x-nativeflows-assist` | new | declaration | Suggested question keys and agent actions for the assist panel (rule 17) |
    | `x-nativeflows-custom-values` | kept (ADR-0074) | `Get<Noun>`, `List<Noun>` result, command payload | The table whose company-defined fields the renderer reads through `ListCustomFieldDefinitions` |

    **The vocabulary totals 24 keys:** the 13 of ADR-0040 and ADR-0074, six of them extended (`widget`, `hidden-when`, `read-only-when`, `lookup`, `list-defaults`, `line-columns`) and `scale-from` made required, plus 11 new.

10a. User-saved variants are in Phase 1, because the list report has a variant switch:
    - **Kinds.** A variant is personal, or shared with a role.
    - **Contents.** It stores filters, columns, sort and grouping for one `List<Noun>` query, server-side in `list_variant` ([DS-30-ui.sql](../design/DS-30-ui.sql), owner `registry`). A variant may be the default of its owner or of its role.
    - **Commands.** `CreateListVariant`, `UpdateListVariant` and `DeleteListVariant`. A personal variant is checked on `general_access`. A shared one needs the capability `share_list_variant` at `edit` on the leaf `list_variant` under Administration, which `owner` and `it_administrator` hold through Administration `full`; a company may grant it to other roles.
    - **Reading.** `ListListVariant` returns the caller's personal variants and those shared with the caller's roles. A variant never widens what the query returns: its filters run inside the caller's permission and record scope.
    - **Unique names.** A personal variant name is unique per owner and query (`ux_list_variant_name`). A shared variant name is unique per role and query, whoever owns it (`ux_list_variant_shared_name`). (review note, 2026-11-21)
    - **Declared variants** of `list-defaults` stay; they show beside the saved ones. Column choice is no longer only a browser-storage convenience (ADR-0040 rule 6 note).

11. What is not annotated, because the registry already declares it:
    - **Actions per state.** An action's availability comes from the command's `subject_table` and `allowed_states` and from `ListAllowedCommand` (ADR-0040 rule 8). `actions` orders them but never adds one.
    - **Confirmation level.** Every write goes through the plan panel. `ui.post_review` decides when it is skipped (ADR-0067). A command that needs a reason asks for it. There is no other confirmation level, so none is annotated.
    - **Field-class masking** is done by the server; the renderer only shows the placeholder.

12. Required annotations, checked by rule 19:
    - every `List<Noun>` result has `title` and `list-defaults`;
    - every `Get<Noun>` result has `title` and `header-facets`;
    - every money or quantity field has `scale-from`;
    - every reference field in a payload has `lookup`.

    Anything else is optional. Fields without `group` fall into the generated group "General", and the renderer falls back to declaration order.

**Embedded agent interaction**

13. One agent type, `assistant`, serves the UI. It is declared like the agent types of [ADR-0051](0051-agent-workflows.md):
    - **Rights.** Its effective rights are the intersection of its declared permissions and the user's, rechecked on every call ([ADR-0054](0054-users-roles-and-authorizations.md) rule 16; [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 31).
    - **Tool list.** Read queries that ADR-0050 rule 30 does not exclude, commands registered `is_draft_only`, and `UpdateAssistAnswer` for workflow code only (rule 14). The subset depends on the purpose: `ask`, `resolve_command` and `resolve_filter` runs get read queries only; only `act` runs get the `is_draft_only` commands. (review note, 2026-11-21)
    - **Starting a run.** A run is started by `StartAgentRun` with the user's `start_agent:assistant`, held at `edit` on the leaf `agent_assistant`, so it acts for that person in that person's own context. The seed gives the leaf to every role template with UI access except `it_administrator`, in line with the decision on `start_agent` of 2026-11-19 ([ADR-0054](0054-users-roles-and-authorizations.md) rule 11 note), and except `auditor`, which ADR-0054 rule 11 keeps at `read` everywhere and nothing else, while starting a run is a command; a company may withdraw the leaf from any role.
    - **Budgets.** Its budgets are the company's daily cap and the ceilings of its declaration ([ADR-0078](0078-agent-simplification-for-phase-1.md) rule 7; ADR-0050 rule 22). The company setting `assist.max_cost_per_run` (default USD 0.20, bounds 0.01 to 0.50, lower is tighter) may lower its cost ceiling.
    - **Scope.** The run's scope is scope kind `subject`: its `assist_request` plus the context subject and the selected rows, each checked against the user's record scope. ADR-0050 rule 27 carries a note that defines this scope for a tainted run, so an `act` run, which always starts tainted, can read these records. (review note, 2026-11-21)
    - **Taint.** A run of `purpose` `act` always starts tainted, because the user may have pasted untrusted content into the text: it starts with `taint_source_kind` `outside_subject` and source table `assist_request`. The registry marks `assist_request` as outside content only when `purpose` is `act` (note at ADR-0050 rule 15). (review note, 2026-11-21) A run of `ask`, `resolve_command` or `resolve_filter` starts untainted, and taint propagates as usual when it reads untrusted data (ADR-0050 rule 25). A tainted run may run only `is_draft_only` commands and reads only the tainted read scope (ADR-0050 rules 26, 27).
    - **Modes.** The assistant runs only in mode `assisted`; its default is `off`. It is never promoted to `active` (ADR-0065), so its drafts always need a person to confirm them. The evaluation set below is its promotion evidence (a step 5 gate item). The purposes `ask`, `resolve_command` and `resolve_filter` answer only the asking person and write nothing; they still require mode `assisted`. (review note, 2026-11-21)
    - **Grouping.** The assistant has three modes of use, named once here: ask, act and resolve. Resolve has two purposes, `resolve_command` and `resolve_filter`, so `assist_request.purpose` has four values. The evaluation set counts these three. The assist panel of rule 17 has three panel modes of its own (ask, act, proactive), and the resolve purposes serve the command bar and natural-language filters (rule 18). (review note, 2026-11-21)
    - **Evaluation.** Spec 17 requires every pair of seat and model to pass an evaluation. The set for the seats of rule 14 has about 50 tasks across the three modes: read answers with correct citations, drafts with correct field diffs, refusals outside its scope, and taint handling, pasted untrusted text included. It is built with the assistant and is a step 5 gate item.

14. Typed text reaches the agent through one row, as `analysis_question` does for the analysis agent (ADR-0060). `CreateAssistRequest` is `human_only` and writes an `assist_request` with these columns:
    - `purpose`: `ask`, `act`, `resolve_command` or `resolve_filter`;
    - `request_text`: up to 2,000 characters;
    - `language`: the language tag of the request;
    - the context: `context_subject_table` and `context_subject_id`, up to 100 `selected_ids` with `selected_table`, the table of the selected rows (required when `selected_ids` is not empty, null otherwise), `active_filters` as JSON, and the `floorplan` code (review note, 2026-11-21);
    - `requested_by_user_id`: the requesting user.

    **Personal data.** `request_text` is labeled personal (spec 17) and follows the routing switch as `analysis_question.question_text` does (ADR-0060 rule 21). It is blanked, which sets `erased_at`, when the requesting user's account is erased and by the retention job after `analysis_question_retention_days`, the same value as for analysis questions (ADR-0060 rule 21; no new setting). (review note, 2026-11-21)

    **Seats.** The LLM steps of the assistant use the spec 17 seat "Data Q&A" for `ask` and the resolve purposes, and "Drafting" for `act`. (review note, 2026-11-21)

    The UI then sends `StartAgentRun` with the row as subject. The run writes its answer to the row through `UpdateAssistAnswer`, registered `is_draft_only` and called only by workflow code, as `UpdateAnalysisAnswer` is (ADR-0050 rule 26 note); its drafts link to its `agent_task` work item (ADR-0042), and a live update tells the panel (ADR-0040 rule 13).

    Runs are asynchronous, and there is no multi-turn dialogue. A follow-up is a new request that names the previous one.

    The DDL is in [DS-30-ui.sql](../design/DS-30-ui.sql) (owner `agents`). The leaf `agent_assistant`, its seed and `assist.max_cost_per_run` are in the catalogs.

15. Trust. Every value an agent or document intake wrote shows where it came from. All of this is read from stored data, not from annotations:
    - **Source:** the actor kind and the agent run of the version that wrote it (ADR-0029 rule 8), or the extraction method of [ADR-0057](0057-document-intake-and-extraction.md) rule 8 (`parsed`, `ocr`, `vision_aligned`, and the others).
    - **Confidence:** only the extraction engine's `confidence_raw` or `confidence_calibrated`. A language model states no confidence (ADR-0050 rule 35), so an agent-written value shows "AI drafted" without a number.
    - **Taint:** the badge and the clearance record (ADR-0040 rule 17).
    - **Audit:** a link to the audit record, for holders of `GetAuditRecord`.

    Provenance has one visual style: an icon, a text label and a colored edge. Color is never the only signal (rule 7).

16. Hard rules of the embedded agent:
    - **No screen automation.** The agent never clicks, types into or reads the rendered UI. It works only through registered commands and queries on its tool list.
    - **Nothing is auto-submitted.** A draft or proposal written by the assistant opens in the plan panel with its field diff and taint badge, and a person confirms it. Only drafts of agent types promoted to `active` may reach the ADR-0065 gateway, and only for posting; the assistant is never one of them.
    - **No UI-only API.** The panel, the command bar and the inline affordances call registered commands and queries through the generated client (ADR-0040 rule 1).
    - **No pop-ups.** Agent outputs that need attention (exceptions, suggestions, drafted documents) arrive as work items in worklists ([ADR-0066](0066-work-cases.md); ADR-0042), and through the notification inbox of ADR-0076.
    - **No invented values.** A value the agent proposes for a price, tax, quantity, account or score follows ADR-0050 rule 36: it must equal a value in its input or the draft.

17. The assist panel. Every floorplan has one, opened with `Ctrl+/`.
    - **Scope.** It is scoped to the current context: the subject record, the selection, the active filters, or the Center's queue.
    - **Budget.** It shows the remaining daily agent budget of the user's company (ADR-0078 rule 7) through `GetAgentBudgetStatus`. This people-only query returns amounts, not run bodies, and is on no tool list.
    - **Three panel modes:**
      - **Ask and explain** (`ask`, read only). The answer cites records as links. Every reference in it is an ID or handle that the run read through the query layer (ADR-0050 rule 36), rendered as a link to that record's object page.
      - **Propose and act** (`act`, write as drafts). The run writes drafts or change proposals only (ADR-0029). They open in the plan panel with a field-level diff and a taint badge where it applies.
      - **Proactive.** The panel never starts a run unasked. Proactive outputs come from the scheduled and triggered agents of ADR-0051 as work items.
    - **Annotations.** `x-nativeflows-assist` on a declaration lists suggested question keys (i18n keys) and the `is_draft_only` commands offered as agent actions. `ai-fillable` marks the fields an `act` run may fill.

18. Inline affordances and the command bar:
    - **Fill from document.** Dropping a PDF or photo on a form uploads an attachment and calls `RequestDocumentExtraction` with the form's purpose. The intake ladder of ADR-0057 produces the extraction, and its verification follows ADR-0057 rule 22. Once verified, the resulting draft opens in the form. Fields filled from the document show their provenance (rule 15), and only `ai-fillable` fields are filled.
    - **AI suggestions in value help.** Value help may list candidates that an agent or intake already stored on the draft, such as matching candidates. They are marked AI and never selected automatically. No language model is called per keystroke.
    - **Natural-language filters.** A request with `purpose` `resolve_filter` returns a structured filter for the list's query, validated against its filter schema. The list shows it as editable chips before it runs, so the query itself stays deterministic.
    - **Mobile capture.** Phase 1 mobile capture is photo and text: a photo is attached to a draft or sent through document intake's deterministic ladder (ADR-0057), and text goes to the assistant. The capture agent of [ADR-0064](0064-production-agent.md) moves to Phase 2 (ADR-0078 rule 2). Voice stays after Phase 1, as ADR-0064 says. The seam is kept: the capture intake can accept an audio attachment later without a new path.
    - **The command bar.** `Ctrl/Cmd+K` extends the palette of ADR-0040 rule 7:
      - Typed names match commands, queries, lists and records as before.
      - Other text becomes a request with `purpose` `resolve_command`. Its answer is a proposed invocation: a registered command or query type, with a payload validated against its schema.
      - The bar shows the resolved command and its parameters. It opens the command's form prefilled, with provenance on the filled fields, and runs simulate before anything executes. It never executes by itself.

**Component library and tokens**

19. Mechanical consistency. These rules join `nativeflows-dev check` (ADR-0022 rule 13; ADR-0073 rule 2), each named after the rule it enforces:
    - required annotations are present (rule 12);
    - every annotation key is in the vocabulary, and every key has a renderer (rule 8);
    - every label and suggested-question key exists in the English catalog (ADR-0040 rule 5);
    - money is paired with currency and quantity with unit (`scale-from`);
    - a list has at most 8 default columns, and an object page header at most 6 facets;
    - every action names a registered command whose `subject_table` is the subject's table;
    - every value help names a registered query, and each `depends_on` names a payload field;
    - every assist action names an `is_draft_only` command;
    - `ai-fillable` appears only on payload fields of commands that create or update drafts;
    - every `custom:<name>` names a registered custom component (rule 22);
    - the shortcut map has no conflicts within a floorplan and uses no key the browser reserves.

    The limits (8 columns, 6 facets) live in `.github/assurance.toml` (ADR-0073 rule 16).

    **Generated UI tests.** The `frontend` job runs them:
    - one Playwright test per floorplan and declaration, against the renderer with recorded responses;
    - a keyboard path through the floorplan;
    - axe-core;
    - visual regression with Playwright's screenshot comparison, one baseline per floorplan, density and width. Baselines are not per screen, which keeps the number of baselines bounded.

    The nightly Playwright flows of ADR-0040 rule 18 stay.

20. The component library is shadcn/ui with Tailwind CSS on Base UI, version pinned. Around it:
    - TanStack Table for lists and for `line_grid`, the editable line grid written in the repository (rule 5);
    - react-hook-form under the renderer's own form builder;
    - i18next (ADR-0040 rule 15);
    - `@axe-core/playwright` for tests.

    Tailwind CSS and Base UI are shadcn/ui's own foundations, and TanStack Table joins the TanStack family of ADR-0002, so neither opens a new category. AG Grid leaves the stack (ADR-0002 note; the tool choice is delegated, 2026-11-19); it comes back only through an ADR, if a measured need appears. `@axe-core/playwright` opens the accessibility-testing category, by this ADR (ADR-0005).

    **Reasons** (from the UI library research of 2026-11-15):
    - the component source sits in the repository, where small models can read it;
    - it brings no data model that competes with the registry;
    - it fits the size budgets.

    **Rejected:** MUI, Ant Design, Fluent, PrimeReact, SAP UI5 Web Components, Carbon, react-admin, RJSF and Formily. They bring their own data models, add bundle weight (UI5 is about 105 KB gzipped against the 250 KB budget), or have paid tiers.

    **The generator** composes only from this library and the renderer's domain components (amount, quantity, reference, state badge, provenance mark, scan input, line grid, plan panel, assist panel). A component outside them fails the `frontend` lint.

21. Design tokens are CSS variables, which Tailwind reads:
    - color roles: surface, text, primary, danger, warning, success, focus, plus `provenance-ai`, `provenance-document` and `taint`;
    - a type scale and a spacing scale;
    - radius and elevation.

    **Two densities:**
    - `compact`: 32 px rows and 8 px spacing step, the desktop default;
    - `touch`: 44 px targets and 12 px spacing step, the default in the PWA and on coarse pointers.

    The viewer's density choice is a per-viewer convenience in browser storage (ADR-0040 rule 17). Light and dark themes share the roles, and every text pair meets WCAG AA contrast, which the token check verifies. A theme changes only token values, never components.

**Escape hatch and sequence**

22. A custom component is a screen that no floorplan fits. Each one:
    - is registered by name, with its defining ADR or design item;
    - lives in `frontend/src/screens/<name>/`;
    - is reached through `custom:<name>`;
    - uses the tokens, the provenance style, the assist panel and the trust rules;
    - calls only registered commands and queries.

    **Registered now:**
    - `extraction_verification` (ADR-0057 rule 22);
    - `work_order_tablet` ([ADR-0071](0071-work-orders-and-shop-floor-execution.md) rule 14);
    - `analysis_view` (ADR-0060 rule 17);
    - `scan_flow`, the PWA scanning flows (ADR-0061; DS-31);
    - `conversation_view` and `notification_inbox` (ADR-0076 rule 8). (review note, 2026-11-21)

    The work-center queue of ADR-0071 is not a kanban component in Phase 1: it renders as a worklist grouped by state. (review note, 2026-11-21)

    An MRP planning board or a warehouse bin map would each need a new ADR.

    `check` reports the share of generated routes. Below 85% the next custom component needs the author's look.

23. Sequence:
    - **Declaration format.** The annotation slots of rules 9 and 10 become fields of the declaration format defined next (ADR-0073 defines it), so that Sonnet drafts them with every declaration.
    - **Renderer v1** (ADR-0040 rule 19, step 1) renders the list report (with variants), object page, create and edit form (with `line_grid`) and plan panel. It is the test harness during the headless steps 0–5.
    - **Later floorplans.** The worklist and approval view follow with the work queue at step 5. The overview follows with the Centers.
    - **The `assistant` agent**, the assist panel, natural-language filters and the command bar's `resolve_command` arrive at step 5, with the work queue; the evaluation set of rule 13 is a step 5 gate item ([steps-5-9.md](../runbook/steps-5-9.md)).

    Note ([ADR-0078](0078-agent-simplification-for-phase-1.md), proposed 2026-11-19): the assistant is one of the six Phase 1 agent types (`assistant`, `analysis`, `bank_matching`, `purchase_invoice`, `document_reader`, `planning`); it routes questions that need figures to `analysis` and drafts what the deferred agents would help with, such as gateway settings (no advisor in Phase 1), mappings and artifacts, on request (ADR-0078 rules 1, 8).

24. The eight open questions of this ADR were decided by the chief architect on the author's delegation of 2026-11-19 and are applied above: the start leaf (rule 13), the taint of typed text (rule 13), `ai-fillable` as a hint (rule 9), the cost cap and DDL (rules 13, 14), voice (rule 18), the line grid without AG Grid (rules 5, 20), user-saved variants (rule 10a) and the evaluation set (rule 13).

## Context

The author decided on 2026-11-19 that build steps 0–5 are built headless and accepted by the author through an agent over MCP; a large synthetic-data test follows; then the UI, organized as flow-based Centers and generated from metadata the way SAP Fiori Elements renders Fiori apps. ADR-0040 already renders most screens from schema annotations, but it left the screen kinds open-ended, kept six hand-built entry screens for step 9, named eleven loose hints, and has no rule for agents inside the UI. ADR-0073 makes Sonnet draft every declaration from the Python declaration format, so the annotation slots must exist before that drafting starts, or each declaration would be touched twice.

The agent rules come from the accepted runtime: agents never submit, post, approve or send (ADR-0050, ADR-0051; ADR-0043 floors); runs are asynchronous and take no free text, except through a `human_only` row as `analysis_question` does (ADR-0060); taint follows content (ADR-0029); permissions are an intersection (ADR-0054); and agent outputs reach people as work items (ADR-0042, ADR-0066).

SAP Fiori Elements (list report, object page, worklist, overview page, analytical list page), Dynamics 365's form and grid patterns, and Odoo's views were surveyed. NativeFlows takes Fiori's floorplan idea and its draft handling as patterns. It derives the metadata from the command schemas, not from per-model XML views (Odoo) or OData annotation files (Fiori), so agents and people read one definition.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Seven floorplans, closed annotation vocabulary, generated screens (chosen) | One consistent UI; annotations drafted with each declaration; machine-checkable | Unusual screens need a custom component and an ADR |
| Keep ADR-0040's screen kinds plus hand-built screens | Free layout for the busiest screens | Hand-built screens drift from the schemas and need code review the author does not do (ADR-0073) |
| Per-screen layout files in the frontend | Full control | Drifts from the registry; against ADR-0040 rule 4 |
| Fiori Elements or UI5 Web Components as the library | Mature floorplans | OData model competes with the registry; about 105 KB gzipped; poor fit for small models |
| Embedded agent as a chat app with free dialogue | Familiar | Free text into an agent, no draft boundary, against ADR-0050's run model and spec 03 |
| Agent drives the rendered UI (screen automation) | Works for any screen | Bypasses the registry and the plan panel; not deterministic; unreviewable |
| Assist panel over registered commands with typed text in one `human_only` row (chosen) | Same tools as external agents; drafts only; asynchronous like every run | No live dialogue; each follow-up is a new request |
| Live LLM suggestions in every value help | Helpful while typing | Cost per keystroke; outside budgets; LLM values into fields |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0040 rules 4, 6, 7, 16, 17, 20: the vocabulary, floorplans, command bar, keyboard, density and the generated step 9 screens.
  - ADR-0022 rules 13, 17: the new checks and the emitted keys.
  - ADR-0073 rules 1, 2, 4: annotation slots in declarations, checks, and Sonnet drafting them.
  - ADR-0029 rule 8: provenance display.
  - ADR-0066 rule 21: the case view as a worklist.
  - ADR-0050 rules 15, 30 and ADR-0051: the `assistant` agent type, `assist_request` and the never-list.
  - ADR-0057 rule 22: the verification screen as a custom component.
  - ADR-0061 rule 17: the `scan` key.
  - ADR-0064: voice stays after Phase 1, with an audio-attachment seam.
  - ADR-0002: AG Grid leaves the stack.
  - ADR-0067: the plan panel floorplan.
- **Glossary rows:** floorplan, value help, assist panel, custom component, list variant.
- **DDL and catalogs:** [DS-30-ui.sql](../design/DS-30-ui.sql) (`assist_request`, `list_variant`); the leaves `agent_assistant` and `list_variant` and the seed in the authorization catalogs; `assist.max_cost_per_run` in `settings.csv`. `CreateAssistRequest` and `GetAgentBudgetStatus` join the never-list of ADR-0050 rule 30.
- **Runbook:** the assistant's evaluation set is a step 5 gate item.
- **Frontend dependencies:** Tailwind CSS, Base UI and TanStack Table within existing categories; `@axe-core/playwright` (accessibility testing, by this ADR).

## Revisit when

- More than 15% of routes need custom components.
- The step 9 measurement shows a generated entry form slower than the MISA reference.
- A required annotation is routinely filled with a meaningless value to pass `check`.
- Users ask for multi-turn dialogue often enough that single requests waste budget.

## Documents updated

- **ADRs:** [ADR-0040](0040-ui-architecture.md), [ADR-0022](0022-repository-and-engineering-conventions.md), [ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), [ADR-0029](0029-proposals-and-agent-safety.md), [ADR-0066](0066-work-cases.md), [ADR-0050](0050-agent-runtime-and-query-layer.md), [ADR-0051](0051-agent-workflows.md), [ADR-0057](0057-document-intake-and-extraction.md), [ADR-0061](0061-barcodes.md), [ADR-0064](0064-production-agent.md), [ADR-0067](0067-quickflows-operating-presets.md), each with a note.
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md) (rows only).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md).
