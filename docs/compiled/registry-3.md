Module: registry    Chunk: 3 of 5    Source ADRs: ADR-0050, ADR-0058, ADR-0059, ADR-0063
Build step(s): 1, 2, 3, 4    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `registry` compiled spec, chunk 3: tainted runs and tool lists, automation and tuning attributes, the settings registry

## Purpose

This chunk states the part of `registry` law on: what a tainted agent run may run and read, untrusted fields, agent tool lists, the registry attributes that automation rules and tunable functions need, the causation chain, and the settings registry with its tables `setting_definition` and `setting_value`. The tightening and loosening paths, bounds, hard locks and presets of settings are in the other chunks, as are the command envelope and the dispatcher. `registry` holds the declarations; the modules that own agents, queries, automation rules and parameter sets apply them.

## Entities and tables

DDL: `docs/design/DS-28-settings.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `setting_definition` | One row per registered setting key; installation data, written at startup, edited by nobody (R432, R436) | `id` (a uuid5 computed by the loader); `setting_key` unique | none | `registry` |
| `setting_value` | Every company-held setting value and the installation values (`company_id` null); never updated or deleted (R437, R441) | `id`; (`company_id`, `id`) unique | `company`; `setting_definition` by `setting_key` | `registry` |

Named by rules or notes of this chunk, with their rows in other chunks of this module: `company_setup_acknowledgement`, `setting_preset`, `module_activation`, `extension_point`, `list_variant`.

Reads: `outbox_event` (`outbox`); `audit_record` (`audit`); `regime_setting` (`localization`); `agent_type_setting`, `data_processing_permission`, `assist_request` (`agents`); `change_proposal`, `user_account`, `company`.

## Commands and queries

The query `ListSettingDefinition` (R436), through which agents read definitions as reference data, has its row in chunk 4.

Contract functions and database objects, not registered commands: `registry.contract.get_setting(company, key, scope_ref, date)` (R434, fails with `regime_configuration_missing` for a `fail_closed` key without a value, R433); the security-definer function `setting_installation_value` (R434); the trigger `setting_value_check_insert` and the index `ix_setting_value_lookup` (R437, R441). `UpdateCompanyRegimeOption` (ADR-0016.R11, area `regime_option` of `localization`) writes `setting_value` rows (R438).

Error codes bound to no named command of this module: the dispatcher returns `tainted_run_not_allowed` (R402), `tainted_read_out_of_scope` (R405), `untrusted_read_not_allowed` (R414), `tool_not_allowed` (R418) and `automation_depth_exceeded` (R429); a tunable parameter declaration is checked with `parameter_order_violated` (R430); the insert trigger of `setting_value` refuses with `serialization_failure` (R441).

## Rules

### Tainted runs: commands

R401. `is_draft_only` is a registry attribute (ADR-0008.R1) of commands that only create or update drafts, change proposals, work item notes or suggestion fields. Such a command is never of effect class `posting`, `master_data_change` or `outbound_send`, and never a `Submit`, `Post` or `Issue`; CI checks this. `UpdateAnalysisAnswer` is registered `is_draft_only` although it writes no draft: it writes once to the run's own question row, which only the asker reads, and changes no document, master data or outside party. `UpdateAssistAnswer` is registered `is_draft_only`, is on the `assistant` tool list for workflow code only, and writes only the answer fields of its own `assist_request`, as `UpdateAnalysisAnswer` does (ADR-0077.R14).
Source: ADR-0050.R26, .N1, .N2

R402. A tainted run may run only commands registered `is_draft_only`. The dispatcher rejects any other command from a tainted run with `tainted_run_not_allowed`, before policy, with a denial record. This adds to the structural guards: such commands are not on agent tool lists (R419), agents' posts are `human_post` (ADR-0043.R9, floor 4) and master data needs a proposal (ADR-0029.R4).
Source: ADR-0050.R26

R403. The writes of a tainted run are tainted: document versions (`INV-88`), events (ADR-0013.R11), work item raises and notes (`INV-210`).
Source: ADR-0050.R26

### Tainted runs: read scope

R404. The tainted read scope is the literal spec 03 rule 1 (ADR-0029.R14). A tainted run reads only:
- item 1, rows in its scope: rows whose partner column equals `scope_partner_id` (scope `partner`), rows of `scope_import_batch_id` (scope `import_batch`), or the run's subject row (scope `subject`);
- item 2, its work item, the item's evidence links and its notes;
- item 3, documents and change proposals that it or an earlier run of the same work item and agent type wrote, with their plans and check results;
- item 4, reference data: the core catalogs (system accounts, transaction keys, movement types, work item kinds, currencies, units), the active package's data (chart template, administrative units, settings), and registry metadata (schemas, view declarations).
Source: ADR-0050.R27

R405. Everything outside the scope of R404 returns `tainted_read_out_of_scope`, with a denial record. Company master data outside the scope (other partners, the item catalog, price lists, the company's chart) is not reference data.
Source: ADR-0050.R27

R406. Item 4 of R404 also covers declared projections (`tainted_projection` on a query's result model: closed shapes and internal names only, at most 20 rows per call and 10 calls per run) while `agents.tainted_reference_reads` reads `declared_projections`, the default; the run stays tainted (ADR-0063.R16).
Source: ADR-0050.R27, .N1

R407. Work cases do not widen item 2 of R404: a run reads its work item, the item's evidence links and its notes, never the work case the item belongs to. `GetWorkCase` and `ListWorkCaseTimeline` are on no agent tool list in Phase 1 (ADR-0066.R19).
Source: ADR-0050.R27, .N2

R408. For the `assistant`, scope kind `subject` covers the run's `assist_request`, its context subject row (`context_subject_table`, `context_subject_id`) and the rows of `selected_table` named in `selected_ids`, each only where the requesting user's record scope allows it. These are the records the run was started on (spec 03 rule 1). The same scope applies to an `ask` or resolve run once it becomes tainted. The runtime's provenance check and the dispatcher's reference check of ADR-0050.R25 accept these rows as in scope.
Source: ADR-0050.R27, .N3

R409. Every view and every query result model declares its partner column and import batch column, or none. A query without the run's scope column is refused for a tainted run.
Source: ADR-0050.R27

R410. In responses of commands to a tainted run, check details and plan parts that name records outside the scope are replaced by `{"redacted": true}` with counts (for example, `partner_duplicate_suspected` gives `{"redacted": true, "candidate_count": 2}`). The plan hash is still computed over the full plan (ADR-0008.R12).
Source: ADR-0050.R27

R411. The same scope bounds what a tainted run may put into a prompt or a command (ADR-0050.R25), so rows read before the taint cannot be used after it.
Source: ADR-0050.R27

R412. Scope kind `subject`, items 2, 3 and 4 of R404, and the data migration agent's reading of its migration's mapping profile (ADR-0051.R26) are readings of the literal spec 03 rule 1 by ADR-0050, and they stand as written: ADR-0063.R16.N1 confirms the readings (a) to (r) of the cited ADRs as readings of ADR-0050.R27. Through item 3 a tainted run also sees the server-computed prices and taxes in its own draft's plan.
Source: ADR-0050.R27

R413. Spec 03 rule 1 names R404 to R412 as the tainted read scope, and the scope is not widened: the whole item catalog, the partner's price lists and available to promise are not readable by a tainted run. A workflow that needs one more read for a tainted run (for example item candidates for matching) gets it only as a declared projection of a registered query (`tainted_projection`: closed shapes, internal names, row and call limits; R406 and ADR-0063.R16), added by an ADR note for that workflow.
Source: ADR-0050.R27, .N4, .N5

### Untrusted fields

R414. Views and query result models omit `is_untrusted` columns unless the request sets `include_untrusted: true` (ADR-0029.R10). Listing documents therefore does not taint. Agent types that must stay clean declare `may_read_untrusted: false` (for example `planning`). For their runs, `include_untrusted` returns `untrusted_read_not_allowed`, and rows that would taint them are left out, with `is_taint_filtered: true` in the response.
Source: ADR-0050.R28

R415. `ListPegging` and `demand_supply_overview` return rows of tainted versions as a numeric-only projection: IDs, quantities, dates and states, no free text. Like aggregates (ADR-0050.R25), such rows do not taint, so the clean planning agent is not filtered on them (reading (g), confirmed by ADR-0063.R16.N1). The projection applies only to agent-run callers; people see full rows within their permissions. `ListAnalysisCellRow` returns a numeric projection to agent runs as `ListPegging` does: IDs, document numbers and types, dates, accounts and contributions, no free text; such rows do not taint and are not filtered from a clean run, so a cell still equals its drill rows (ADR-0060.R16).
Source: ADR-0050.R28, .N1

### Tool lists

R416. An agent type version's tool list names registered queries and commands (spec 03 rule 2; ADR-0008.R6). Nothing is inferred from a prompt.
Source: ADR-0050.R29

R417. Tool definitions are generated from the registry with the same names (`snake_case`, ADR-0004.R19) and JSON Schemas as the MCP tools. They state each tool's side-effect class (`read` for queries, `draft` for `is_draft_only` commands, the only classes agents get) and its allowed states as preconditions; the dispatcher enforces them, not the description. NativeFlows's own runs call the dispatcher in process; outside MCP clients use the MCP transport with their own credentials.
Source: ADR-0050.R29, .N2

R418. The dispatcher checks every call against the run token's tool list and rejects others with `tool_not_allowed`, with a denial record. The tool list is step 2 of the dispatcher's check order, first after the credential and before `human_only`, `proposal_required` and permission (DS-04, dispatcher check order). Allowed-target commands of ADR-0029.R2 (effect class `master_data_change` or `is_proposal_bound`) are kept off tool lists too, a registry check that `INV-214` covers: agents reach them only through `CreateChangeProposal`, so an agent run that calls one directly gets `tool_not_allowed`, and `proposal_required` is met by consumer commands carrying an origin run (`EC-56`).
Source: ADR-0050.R29, .N1

R419. Never on a tool list (a registry CI check and `INV-214`):
- commands of effect class `posting`, and every `Submit<Type>`, `Post<Type>` and `Issue<Type>`: people submit, post and issue agent drafts, which in Phase 1 also covers the release of production orders by `Submit` (ADR-0034.R5). Agents create change proposals as drafts; a person submits them (ADR-0029.R3), and a person other than the human the run acted for approves them (ADR-0017.R16);
- commands registered `human_only` or of effect class `outbound_send`;
- `Approve<Type>`, `Reject<Type>`, `ClearTaint`, `ConfirmAutoPost`, `UpdateAgentTypeSetting`, `CreateAgentPromotionEvidence`, policy rule and procedure commands, role assignments;
- `StartAgentRun`, `CancelAgentRun`, `CompleteAgentRun` (no agent starts agents), and claim, assign and resolve commands of work items (the runtime manages the run's claim);
- audit queries (ADR-0038.R7), `ListAgentRun`, `GetAgentRun`, `ListAllowedCommand`, `GetSessionContext`, `GetPolicyEvaluation`, and `CreateListExport` (ADR-0050.R54).
Source: ADR-0050.R30

R420. Also never on a tool list:
- `SetDataProcessingPermission` and `EndDataProcessingPermission`; `CreateExtractionFields` is on the list of `document_reader` for workflow code only (ADR-0057.R11, ADR-0057.R20);
- `CreateArtifactEvidence`, `SetArtifactVersionState`, `SetArtifactCurrentVersion`, `RecordGoldenCaseLabel`, `ListGoldenCaseLabel`, `CreateAutomationRule`, `UpdateAutomationRule`, `ConfirmAutomationRuleOwnership`, `CreateDecisionTable`, `CreateParameterSet`, `DisableAutomationRule` and `EnableAutomationRule`; agents draft artifact versions only (ADR-0059.R27; ADR-0058.R27);
- `ListAnalysisResultRow`, the list query through which people export analysis results, and `ListAnalysisQuestion` (ADR-0060.R14, ADR-0060.R17);
- `TransferStockReservation` (accepted only from a change proposal's execution), `ImportOperationConfirmation` (an integration's command) and `RunProductionOrderCheck` (a system job) (ADR-0064.R12, ADR-0064.R24, ADR-0064.R25; `INV-730`);
- `CreateAssistRequest` and `GetAgentBudgetStatus` (ADR-0077.R14, ADR-0077.R17);
- the queries `ListConversation`, `ListMessage`, `ListNotification` and `ListNotificationPreference`; no agent type's tool list may name them.
Source: ADR-0050.R30, .N1, .N2, .N3, .N4, .N5, .N6

R421. In Phase 1 an agent type's tool list lives in its `AgentTypeDeclaration`, and `check` refuses any entry on the list of R419 and R420 or any command not registered `is_draft_only` (ADR-0078.R3, ADR-0078.R4).
Source: ADR-0050.R30, .N7

### Registry attributes for automation

R422. An event type is usable as a trigger of an automation rule only when its registration declares:
- `is_automation_trigger` and its condition source: a registered query that takes the subject's ID, and its version for documents, and returns the condition fields; its permission, record scope and owner scope are the owner's test in ADR-0058.R9;
- condition fields: name, type (`amount`, `quantity`, `percent`, `integer`, `date`, `boolean`, `code`, `reference`), data label and field class. Only fields that the registry declares `is_gate_field` may be condition fields: an allowlist of deterministic fields, never a field fed by an LLM step's output directly or through computation (ADR-0059.R20). A field marked `is_untrusted` (ADR-0029.R10) or labelled `sensitive_personal` is never declared one, so outside text and model output never steer a rule;
- optionally a discriminator field (such as a work item's `kind`), which makes (event type, value) a node of the rule graph (ADR-0058.R15);
- for an update event, its watchable fields, which the payload reports in `changed_fields` by name only (ADR-0058.R14);
- `is_replayable`: the condition source reads an immutable version, so the replay of ADR-0058.R23 sees the facts as they were.
Source: ADR-0058.R4

R423. `is_automation_allowed` is a registry attribute. A command so registered is a `Create<Type>` that creates a draft (never an update or delete of one), is also `is_draft_only` (R401), is never of effect class `posting`, `master_data_change` or `outbound_send`, never `human_only` or `is_proposal_bound`, and never a command of `configuration` or `automation` other than `RaiseAutomationWorkItem`. `CreateChangeProposal` is not automation-allowed: a rule never proposes master data changes. CI checks this. `StartAgentRun` and hold commands are reached only through their own action kinds (ADR-0058.R6, ADR-0058.R7).
Source: ADR-0058.R5

R424. Every command declares the event types it may emit and, for an event type with a discriminator, the discriminator values; a declaration without values counts as able to emit every value, which reaches every discriminated trigger of that type (conservative). Registered consumers and scheduled jobs declare the same for the commands they run. A registry check compares the declarations with the handlers' emits in tests. The graph check of ADR-0058.R15 reads them.
Source: ADR-0058.R5

R425. The payload of an automation action is built from the rule's payload template: each field is a literal, a condition field of the trigger, or an output of a pinned decision table version (ADR-0058.R20). Validation type-checks it against the command's schema at the registry version, so an action never carries a free string from outside content.
Source: ADR-0058.R5

R426. Hold interfaces: a module may register a command `is_hold` for a subject table: effect class `other`, it only sets a block that a later step respects (a delivery or payment block), it never releases one, and a person releases it with the module's own release command. Phase 1 registers none yet; the open item payment block of DS-25 and a delivery block on sales orders are the first candidates. Until a module registers one, the action `set_hold` has no vocabulary.
Source: ADR-0058.R6

### Causation chain

R427. Every `outbox_event` and `audit_record` carries `causation_chain_id`, `causation_depth` (no default; the writer always sets it) and `automation_rule_version_id`; the database requires a depth of at least 1 where a rule version is named.
Source: ADR-0058.R12

R428. The dispatcher assigns the chain, never the request:
- a command from a transport, a person or a scheduled job starts a chain (a new UUIDv7, depth 0);
- a consumer command inherits its event's chain and depth (ADR-0013.R9);
- an automation action inherits the triggering event's chain with depth plus one and names its rule version;
- an agent run started from an event (a wake-up, or `start_agent`) inherits that event's chain and depth, and every tool call of the run and every event of its drafts carries them;
- a run a person starts begins a chain, also on an item a rule raised, which is intended: a person is in the loop.
Source: ADR-0058.R12

R429. The depth cap is 3. The dispatcher refuses an automation action whose depth would exceed 3 with `automation_depth_exceeded` (DS-04 check order, step 2), and the consumer records `depth_exceeded` without trying. The database holds it too: a check keeps `causation_depth` between 0 and 3 on `outbox_event` and on `audit_record`. The cap is a core constant, not a setting.
Source: ADR-0058.R12

### Tunable parameter declarations

R430. A deterministic function may declare in the registry (ADR-0008.R1):
- its `function_code` (such as `cash.match_bank_line`), `function_version` (semver, bumped by any change of its code or declaration), its authorization leaf (for golden labels, ADR-0059.R22), its case tables (the rows its decisions are about) and its case-reference paths (columns of other tables that point at a case directly, or through a declared path of foreign keys, such as a payment line through its payment to the bank statement line), both for held-out filtering (ADR-0059.R16); a CI check derived from the schema refuses a foreign key to a declared case table that is not a declared case-reference column, and a property test checks that a filtered query returns no row tied to a held-out case; each L2 kind declares the same;
- each parameter: `code`, type (`integer`, `decimal`, `score`, `percent`, `days`), core default, minimum and maximum, `is_nullable` (null means off), and `is_safety_cap`: a cap whose maximum is the core default, which is never off and can only be lowered;
- order constraints between parameters (`a > b`), checked with the bounds (`parameter_order_violated`);
- its stages and thresholds (ADR-0059.R18), with the small-company minimums below which no company may set them;
- its synthetic golden set (ADR-0050.R39), which every parameter set version must pass at the function's threshold.
Not tunable: hard floors, guards and shapes (the reference-token shape of ADR-0048.R9, the routing switch, taint, the rule that a tied match never acts), and anything spec 03 fixes. Bounds and constraints are part of the declaration and change only by a release.
Source: ADR-0059.R3

### The settings registry

R431. The registration of regime setting keys (ADR-0016.R10) is the one settings registry for every scope, and the leaf `company_setting` covers company settings such as `automation.breaker_failures`. Agent type settings, data-processing permissions, parameter sets and package rows keep their own tables; the registry points at them. A company starts on safe defaults, and country packages fill neutral settings: the core names no country's law, example or value. One person holding the leaf tightens a setting at once, and a loosening is a change proposal a second person approves (ADR-0063.R3); the hard locks are those of ADR-0063.R6; a new setting whose default changes behavior raises a work item at the upgrade (ADR-0063.R5).
Source: ADR-0063.D0

R432. Every setting the core reads is registered in code with:
- `key`: lowercase dotted segments; a segment in angle brackets, such as `<agent_type>`, is a declared placeholder whose values the registry lists (column `setting_key`);
- `area`: the setup group;
- `scope`: one or more of `installation`, `regime`, `company`, `product_category`, `money_account`, `scanner_profile`, `agent_type`, `rule_version` (column `scopes`);
- `storage`: where the key's non-company values live, one of `setting_value`, `regime_setting`, `agent_type_setting`, `data_processing_permission`, `rule_version`, `deployment`; company-held values of every key live in `setting_value` (R437);
- `value_type`: one of `boolean`, `integer`, `decimal`, `percent`, `amount`, `enum`, `code`, `code_list`, `field_list`, `object`; a value of type `code` is one code of the table the bounds name, checked by the command, first used by `ledger.business_unit.default`;
- `core_default`: a value, `unset` for "no value, no limit", or `fail_closed` (columns `default_kind` and `core_default`);
- hard `bounds` (columns `min_value`, `max_value`, `allowed_values`);
- `direction` (ADR-0063.R3; columns `direction` and `direction_order`);
- `leaf`: an authorization leaf of ADR-0054.R7, or `package` for package rows and `operator` for deployment values (column `leaf_code`);
- `change_effect`: `immediate`, `period_start`, `package_release` or `deployment`;
- `outdates`: `auto_post`, `promotion` or `none` (ADR-0063.R3).
Source: ADR-0063.R1, .N1

R433. A key whose content is a regime's law or accounting rule has no core default (`fail_closed`), as ADR-0053 requires: reading it without a value fails with `regime_configuration_missing` (ADR-0016.R10), as `data_processing.policy` and the purchase return keys do. Every other key has a core default that a company can run on.
Source: ADR-0063.R1

R434. `registry.contract.get_setting(company, key, scope_ref, date)` returns the value in force on the date by the key's date rule: the narrowest declared scope that holds a row (product category, money account, scanner profile or agent type before company), then the regime's row, then the core default; an installation value, where declared, is a maximum that narrower scopes may only tighten. Installation rows stay visible only under the setting value `installation` (ADR-0017.R19); company sessions read an installation maximum only through the security-definer function `setting_installation_value`, in the pattern of `nativeflows_claim`, which returns the key, the value and its effective date and nothing else (the roles step revokes EXECUTE on it from PUBLIC and grants it to the application roles). `get_setting` applies the maximum at read time, and the insert trigger also refuses a company value looser than the installation value in force. It returns the value with its source (`core_default`, `regime`, `company`, or the narrow scope), so every decision records which value it used.
Source: ADR-0063.R1

R435. The catalog `settings.csv` (owner DS-28) lists every setting ADR-0063 registers or touches, one row per definition, with the attributes of R432 plus `source`, `added_in` and `meaning`. It is seeded now and generated from the registry once `registry` exists, like the work item kinds. The lab checks it (ADR-0063.R30).
Source: ADR-0063.R1

R436. Definitions are installation data: the registry writes one `setting_definition` row per key at startup, nobody edits them, and agents read them through `ListSettingDefinition` as reference data (item 4 of R404).
Source: ADR-0063.R1

### Where setting values live

R437. `setting_value` (owner `registry`, company data, append-only) holds every company-held value of scope `company`, `product_category`, `money_account`, `scanner_profile` or `agent_type`, and the installation values (company null, readable only under the setting value `installation`, ADR-0017.R19). A row carries:
- the key (`setting_key`), scope (`scope_kind`), scope reference (`scope_ref`) and placeholder values (`placeholder_values`), the value and `effective_from`;
- the replaced value (`replaced_value`), the value in force it replaces: the row for the same company, key, scope, scope reference and placeholder values, else the company row for a narrower scope, else the core default;
- `change_kind` (`tighten`, `loosen`, `neutral`), the reason, the human who made the change (`changed_by_user_id`), and for a loosening the change proposal (`change_proposal_id`) and its approver (`approved_by_user_id`);
- copies of the definition's type, bounds, allowed values and direction;
- `setup_acknowledgement_id`, for a loosening set before go-live under the owner's acknowledgement without a proposal (ADR-0067.R9), and `preset_code` with `preset_version`, the operating preset whose application wrote the row, never read to decide anything (ADR-0067.R4).
A `BEFORE INSERT` trigger ties every copy to `setting_definition`, checks the scope and that the placeholder values name exactly the key's placeholders, refuses a value looser than the installation value in force, derives the replaced value itself (filling it when absent and refusing a different one, JSON null included) after taking a transaction-level advisory lock on (company, key), so changes of one key in a company are serialized, and derives `change_kind` from the direction and that value. The database then refuses a value outside the bounds, a loosening that has neither a proposal nor a setup acknowledgement (whatever label or replaced value the row carries, a first value looser than the core default included), and a loosening approved by the person who proposed it. Left to the command and the invariants: that the proposal was approved and executed (`INV-701`), that the date is valid (`INV-702`), and that a scope reference names a record of the company.
Source: ADR-0063.R2

R438. Company regime options (ADR-0016.R11) are `setting_value` rows of scope `company`; `UpdateCompanyRegimeOption` writes them under the checks of R437 and the path of ADR-0063.R3.
Source: ADR-0063.R2

R439. The trigger and the read function name every table with the schema and pin `search_path = nativeflows, pg_temp`, so a temporary table cannot stand in for `setting_definition` or `setting_value`; application roles get no `TEMPORARY` privilege on the database and SELECT only on `setting_definition` (ADR-0017.R18); the advisory lock is transaction-level, allowed on trigger paths (ADR-0022.R13).
Source: ADR-0063.R2

R440. Kept in their own tables, with the `storage` attribute of the registry naming them: package rows (`regime_setting`, ADR-0016.R9), agent type settings (`agent_type_setting`, ADR-0050.R14), data-processing permissions (`data_processing_permission`, ADR-0057.R20), the parameter sets of tunable functions (ADR-0059.R4), per-rule overrides inside an automation rule version's content (ADR-0058, hashed with the version), and installation values from the deployment configuration (DS-37), which the startup step records as `setting_value` rows when they change: `changed_by_user_id` is the operator account named in the deployment change and, for a loosening, `approved_by_user_id` a second operator account that approved it.
Source: ADR-0063.R2

R441. History is the audit trail: `setting_value` rows are never updated or deleted, and each change is also an audit record of its command (ADR-0038). The value in force on a date, for a key, scope, scope reference and placeholder values, is the row with the latest `effective_from` on or before it; among rows of the same key, scope, scope reference, placeholder values and `effective_from` it is the row with the greatest `id` (UUIDv7), never `recorded_at`, which rows of one transaction share (ADR-0007.R10). The trigger `setting_value_check_insert` refuses a row whose `id` does not exceed every `id` already written for the same key, scope and date, under the per-company-and-key advisory lock it already takes, so the order is the write order by construction; the lookups and `ix_setting_value_lookup` order by `effective_from DESC, id DESC`. The refusal is `serialization_failure` (SQLSTATE 40001), not `check_violation`: the id is generated before the lock is taken, so two concurrent writers of one key and date, or an import in another id order, are retried by the command envelope of ADR-0008 with a fresh, greater id.
Source: ADR-0063.R2, .N1

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-214` | day | `agent_tool_lists_safe`: No agent type version's tool list holds a command of effect class `posting`, a `Submit`, `Post` or `Issue` command, a `human_only`, `outbound_send` or `is_internal_only` command, an allowed-target command of ADR-0029.R2 (effect class `master_data_change` or `is_proposal_bound`), an approval, taint clearing, auto-post confirmation, policy, role, agent-setting or promotion-evidence command, an agent run command or query, a work item claim, assign or resolve command, an audit query, `ListAllowedCommand`, `GetSessionContext`, `GetPolicyEvaluation` or `CreateListExport`. | R418, R419 |
| `INV-700` | day | `settings_registered`: Every `setting_value` names a registered key at a scope its definition declares, its type, bounds, allowed values and direction equal its definition's, its value lies within them, and its `change_kind` is the one its direction and replaced value give (database checks and the insert trigger). | R432, R437 |

Named by rules of this chunk, with their rows in other chunks of this module: `INV-210` (R403; chunk 2), `INV-701`, `INV-702` (R437; chunk 4), `EC-56` (R418; chunk 2). Cited and not written in this module, their catalog sources being rules of other modules: `INV-88` (R403; ADR-0029.R8) and `INV-730` (R420; ADR-0064.R1, ADR-0064.R4).

## Settings

None: of the settings this chunk names, `agents.tainted_reference_reads` (R406; ADR-0063.R16) and `extensions.wasm_enabled` (ADR-0059.R24.N1) have their rows in chunk 4; `data_processing.policy` (R433, a `fail_closed` regime key) and `automation.breaker_failures` (R431) are rows of the modules that state their rules (`agents`, `automation`).

Source finding: settings that the core reads, which R432 and R435 require in `settings.csv`, but that `settings.csv` lacks: `routing_switch` (the routing switch of R430; a company setting of ADR-0050.R9), `llm_provider` (an installation setting of ADR-0050.R5) and `list_export_max_rows` (an installation setting of ADR-0050.R54, the cap of `CreateListExport`, R419).

Reads: `ledger.business_unit.default` (`ledger`; ADR-0069.R13).

## Conflicts

CONFLICT ADR-0050.R27: the mark "Flagged" and the sentence that the author's answer may change scope kind `subject`, items 2, 3 and 4 and the migration mapping reading are dropped, because ADR-0063.R16.N1 confirms the readings (a) to (r) as readings of this rule (R412).
CONFLICT ADR-0050.R28: the mark "(flagged, open question)" on the numeric projections of `ListPegging` and `demand_supply_overview` is dropped; reading (g) is confirmed by ADR-0063.R16.N1 (R415).
CONFLICT ADR-0050.R27.N4: ADR-0050.R27.N5 decides the conflict the note recorded for the author; the wider wording of the author's decision item 2 of 2026-11-19 is withdrawn and R413 states the scope as not widened.
CONFLICT ADR-0050.R27.N5: this note governs over the wider reading of the author's decision; ADR-0050.R27 stays as written, with its readings stated in R412 (confirmed by ADR-0063.R16.N1), and a further read comes only as a declared projection (R413).
CONFLICT ADR-0063.R2: the DS-28 DDL with ADR-0067.R9 and ADR-0067.R4 governs the columns and the loosening check of `setting_value`; R437 adds `setup_acknowledgement_id`, `preset_code` and `preset_version`, and the database refuses a loosening only when it has neither a proposal nor a setup acknowledgement.
FALSE-POSITIVE ADR-0063.R2.N1: "instead of" describes a retry that replaces a failure of the insert; the note defines the order among rows of equal `effective_from` and contradicts no text of the rule (R441).

## Trace

| Source | Where |
| --- | --- |
| ADR-0050.R26 | R401-R403 |
| ADR-0050.R26.N1 | R401 |
| ADR-0050.R26.N2 | R401 |
| ADR-0050.R27 | R404-R413 |
| ADR-0050.R27.N1 | R406 |
| ADR-0050.R27.N2 | R407 |
| ADR-0050.R27.N3 | R408 |
| ADR-0050.R27.N4 | R413 |
| ADR-0050.R27.N5 | R413 |
| ADR-0050.R28 | R414, R415 |
| ADR-0050.R28.N1 | R415 |
| ADR-0050.R29 | R416-R418 |
| ADR-0050.R29.N1 | R418 |
| ADR-0050.R29.N2 | R417 |
| ADR-0050.R30 | R419-R421 |
| ADR-0050.R30.N1 | R420 |
| ADR-0050.R30.N2 | R420 |
| ADR-0050.R30.N3 | R420 |
| ADR-0050.R30.N4 | R420 |
| ADR-0050.R30.N5 | R420 |
| ADR-0050.R30.N6 | R420 |
| ADR-0050.R30.N7 | R421 |
| ADR-0052.R1.N1 | ref: ADR-0052.R1.N1 |
| ADR-0054.R11.N10 | ref: ADR-0054.R11.N10 |
| ADR-0058.R4 | R422 |
| ADR-0058.R5 | R423-R425 |
| ADR-0058.R6 | R426 |
| ADR-0058.R12 | R427-R429 |
| ADR-0059.R3 | R430 |
| ADR-0059.R23.N1 | ref: ADR-0059.R23.N1 |
| ADR-0059.R24.N1 | ref: ADR-0059.R24.N1 |
| ADR-0063.D0 | R431 |
| ADR-0063.R1 | R432-R436 |
| ADR-0063.R1.N1 | R432 |
| ADR-0063.R2 | R437-R441 |
| ADR-0063.R2.N1 | R441 |
