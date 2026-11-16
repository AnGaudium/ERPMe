-- DS-28-34 configuration artifacts: DDL draft for configurable workflows (ADR-0058: automation rules, decision tables,
-- execution records) and for the lifecycle of AI- or human-drafted decision artifacts (ADR-0059: parameter sets,
-- transitions, promotion evidence, shadow outcomes, golden case labels, monitor snapshots). Named after DS-28 (policy and
-- configuration) and DS-34 (artifact evidence and promotion).
-- A file of its own (ADR-0058 rule 1), so the configuration tables load and change apart from DS-05-platform.sql; that
-- file carries the causation columns of outbox_event and audit_record (ADR-0058 rule 12) and
-- bank_statement_line.match_parameters_hash (ADR-0059 rule 6).
-- PostgreSQL 18. Loaded with every other design/*.sql file by load_all.py (docs/reviews/2026-11-14-design-validation,
-- t22_workflows.py and t23_ai_artifacts.py with --load). The ADRs win if this file disagrees.
-- Conventions of DS-20, DS-15 and DS-05: tables in schema nativeflows, domains in types; IDs are UUIDv7 from context.new_id,
-- no ID defaults; references between company tables are composite on (company_id, id); recorded_at on every row.
-- Every table here has company_id NOT NULL and gets FORCE ROW LEVEL SECURITY and the company policy of ADR-0017 rule 19;
-- the last section writes them out as DS-05-platform.sql does (the rls_v1 pattern of ADR-0022 rule 8).
-- Referenced tables defined elsewhere: company (DS-20); user_account (DS-15); agent_run, change_proposal (DS-05).
-- Functions of DS-05-platform.sql used here: platform_reject_change, platform_check_append_only.
-- Owner module per section in brackets (ADR-0022 rule 2): configuration (layer 2) owns every table; automation (layer 5)
-- writes through configuration's contract.
-- Revised after review round 1 (2026-11-15): versions are inserted only as drafts; leaving shadow and retiring clear the
-- pointers; drafting windows are required; evidence holds minimum counts and window reuse; executions hold per-action
-- outcomes, the readers' scope dimensions and the business date; the company's configuration_state row serializes
-- activations (ADR-0058 rule 15). Round 2: the owner's consent names the owner; out-of-scope subjects are counted per
-- rule and day; pinned decision table versions are in force and not retired while pinned; re-evaluations of core
-- defaults have no version and may be written by the monitor job.
-- Polymorphic artifact references (artifact_kind, artifact_id, artifact_version_id) carry no key; INV-677 to INV-685
-- check them. Rules that need the registry (vocabulary, ladders per kind, the graph check, bounds per function version)
-- are enforced by commands and named in the ADRs; the rules a row can hold are checks here, and the immutability rules
-- are triggers at the end.

-- ===== Automation rules [configuration] (ADR-0058 rules 8-17) =====
CREATE TABLE automation_rule (                             -- company data; the identity of a versioned rule (rule 8)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL REFERENCES company (id),
    code                text NOT NULL CONSTRAINT ck_automation_rule_code CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    name                text NOT NULL,
    owner_user_id       uuid NOT NULL REFERENCES user_account (id),   -- actions run as system on behalf of this user (rule 9)
    owner_confirmed_at  timestamptz,                       -- the owner's consent: submitter of the activation, or ConfirmAutomationRuleOwnership (rule 9)
    owner_confirmed_user_id uuid REFERENCES user_account (id),   -- who consented; cleared with owner_confirmed_at on every owner change
    owner_scope         jsonb CONSTRAINT ck_automation_rule_owner_scope CHECK (jsonb_typeof(owner_scope) = 'object'),   -- per rule: a set of cells, one per assignment granting the condition source's read, split to (branch or all, warehouse or all, level, units, employees) (rule 9)
    current_version_id  uuid,                              -- the version in force; key and state check below (ADR-0059 rule 12)
    shadow_version_id   uuid,                              -- at most one version in shadow
    disabled_at         timestamptz,                       -- rules 9, 16, 25
    disabled_reason     text CONSTRAINT ck_automation_rule_disabled_reason CHECK (disabled_reason IN ('circuit_breaker', 'owner_inactive', 'upgrade_invalid', 'person')),
    recorded_at         timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    CONSTRAINT ck_automation_rule_disabled CHECK ((disabled_at IS NULL) = (disabled_reason IS NULL)),
    CONSTRAINT ck_automation_rule_pointers CHECK (current_version_id IS NULL OR current_version_id IS DISTINCT FROM shadow_version_id),
    CONSTRAINT ck_automation_rule_owner_consent CHECK ((owner_confirmed_at IS NULL) = (owner_confirmed_user_id IS NULL)),
    -- automation_owner_not_confirmed: a version in force needs the consent of the current owner, not of an earlier one.
    CONSTRAINT ck_automation_rule_owner_confirmed CHECK (current_version_id IS NULL
        OR (owner_confirmed_user_id IS NOT NULL AND owner_confirmed_user_id = owner_user_id))
);
-- Immutable once out of draft (trigger below; ADR-0058 rule 21). The lifecycle columns, from state to change_proposal_id,
-- are the same on the three version tables (ADR-0059 rule 12).
CREATE TABLE automation_rule_version (
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    automation_rule_id     uuid NOT NULL,
    version                integer NOT NULL CONSTRAINT ck_automation_rule_version_version CHECK (version >= 1),
    trigger_event_type     text NOT NULL CONSTRAINT ck_automation_rule_version_trigger CHECK (trigger_event_type ~ '^[A-Z][A-Za-z0-9]+$'),
    trigger_discriminator  text,                           -- the event type's declared discriminator value, e.g. a work item kind (rule 15)
    watched_fields         text[] NOT NULL DEFAULT '{}',   -- required for update events (rule 14)
    conditions             jsonb NOT NULL DEFAULT '[]',    -- [{field, operator, value}], all must hold (rule 8)
    actions                jsonb NOT NULL,                 -- 1 to 5 of create_draft, raise_work_item, notify, start_agent, set_hold (rule 8)
    tests                  jsonb NOT NULL DEFAULT '[]',    -- stored tests (rule 22)
    decision_table_version_ids uuid[] NOT NULL DEFAULT '{}',   -- the pinned table versions it uses (rule 20); inside the content hash
    state                  text NOT NULL DEFAULT 'draft' CONSTRAINT ck_automation_rule_version_state CHECK (state IN ('draft', 'backtested', 'shadow', 'assisted', 'active', 'retired')),
    content_hash           text NOT NULL CONSTRAINT ck_automation_rule_version_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    registry_version       text NOT NULL,                  -- the vocabulary it was validated against (rule 25)
    effective_from         date,                           -- set once at activation (rule 21)
    drafted_by_kind        text NOT NULL CONSTRAINT ck_automation_rule_version_drafted_by_kind CHECK (drafted_by_kind IN ('human', 'agent', 'system')),
    drafted_by_id          uuid NOT NULL,
    on_behalf_of_id        uuid NOT NULL REFERENCES user_account (id),   -- the drafting person, or the human its run or consumer acted for
    origin_agent_run_id    uuid,
    is_tainted             boolean NOT NULL DEFAULT false, -- drafted by a tainted run or from untrusted text (ADR-0059 rule 13)
    drafting_window_from   date,                           -- ADR-0059 rule 15; null: from the beginning
    drafting_window_to     date NOT NULL,                  -- every draft has one; a person's defaults to the draft's date
    change_proposal_id     uuid,                           -- the approved proposal that last raised its state
    recorded_at            timestamptz NOT NULL,
    UNIQUE (automation_rule_id, version),
    UNIQUE (company_id, id),
    UNIQUE (company_id, automation_rule_id, id),
    FOREIGN KEY (company_id, automation_rule_id) REFERENCES automation_rule (company_id, id),
    FOREIGN KEY (company_id, origin_agent_run_id) REFERENCES agent_run (company_id, id),
    FOREIGN KEY (company_id, change_proposal_id) REFERENCES change_proposal (company_id, id),
    CONSTRAINT ck_automation_rule_version_conditions CHECK (jsonb_typeof(conditions) = 'array'),
    CONSTRAINT ck_automation_rule_version_actions CHECK (jsonb_typeof(actions) = 'array' AND jsonb_array_length(actions) BETWEEN 1 AND 5),
    CONSTRAINT ck_automation_rule_version_tests CHECK (jsonb_typeof(tests) = 'array'),
    CONSTRAINT ck_automation_rule_version_no_assisted CHECK (state <> 'assisted'),   -- rules have no assisted stage (ADR-0059 rule 9)
    CONSTRAINT ck_automation_rule_version_effective CHECK (state NOT IN ('assisted', 'active') OR effective_from IS NOT NULL),
    CONSTRAINT ck_automation_rule_version_agent CHECK (drafted_by_kind <> 'agent' OR origin_agent_run_id IS NOT NULL),
    CONSTRAINT ck_automation_rule_version_window CHECK (drafting_window_from IS NULL OR drafting_window_from <= drafting_window_to)
);
-- One row per matched rule version and event and mode, never updated or deleted (rules 11, 17; ADR-0059 rule 23).
-- Non-matches are not recorded (rule 11).
CREATE TABLE automation_execution (
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL,
    automation_rule_id          uuid NOT NULL,
    automation_rule_version_id  uuid NOT NULL,
    mode                        text NOT NULL CONSTRAINT ck_automation_execution_mode CHECK (mode IN ('live', 'shadow')),
    event_id                    uuid NOT NULL,             -- outbox_event, partitioned and dropped after retention, so no key
    event_type                  text NOT NULL,
    business_date               date NOT NULL,             -- the event's; the breaker's window (rule 16)
    subject_table               text NOT NULL,
    subject_id                  uuid NOT NULL,
    subject_version             integer,                   -- the document version the conditions read (rule 10)
    branch_id                   uuid,                      -- the subject's scope dimensions, for readers' record and owner scope (rule 11)
    warehouse_id                uuid,
    document_id                 uuid,
    causation_chain_id          uuid NOT NULL,             -- the triggering event's chain and depth (rule 12)
    causation_depth             smallint NOT NULL CONSTRAINT ck_automation_execution_depth CHECK (causation_depth BETWEEN 0 AND 3),
    outcome                     text NOT NULL CONSTRAINT ck_automation_execution_outcome CHECK (outcome IN (
                                    'acted', 'partial', 'skipped', 'would_act', 'skipped_same_target', 'depth_exceeded', 'refused', 'failed', 'rate_limited')),   -- rate_limited: ADR-0063 rule 21
    condition_results           jsonb NOT NULL,            -- per condition: field, operator, field class, label, value read (personal: HMAC under the company key, or omitted), result; readers lacking a class get value and result omitted

    input_hash                  text NOT NULL CONSTRAINT ck_automation_execution_input_hash CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    action_results              jsonb NOT NULL DEFAULT '[]',   -- per action: kind, command, key, outcome (done, skipped, refused, failed), audit record or error
    error_code                  text,
    is_tainted                  boolean NOT NULL,
    origin_agent_run_id         uuid,
    on_behalf_of_id             uuid NOT NULL REFERENCES user_account (id),   -- the rule's owner at execution (rule 9)
    recorded_at                 timestamptz NOT NULL,
    UNIQUE (automation_rule_version_id, event_id, mode),  -- rule 17
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, automation_rule_id, automation_rule_version_id) REFERENCES automation_rule_version (company_id, automation_rule_id, id),
    FOREIGN KEY (company_id, origin_agent_run_id) REFERENCES agent_run (company_id, id),
    CONSTRAINT ck_automation_execution_conditions CHECK (jsonb_typeof(condition_results) = 'array'),
    CONSTRAINT ck_automation_execution_action_results CHECK (jsonb_typeof(action_results) = 'array'),
    -- Rule 10: refused, failed and partial name the first refusal or failure; skips by design carry no error.
    CONSTRAINT ck_automation_execution_error CHECK ((outcome IN ('refused', 'failed', 'partial')) = (error_code IS NOT NULL)),
    CONSTRAINT ck_automation_execution_mode_outcome CHECK ((mode = 'shadow' OR outcome <> 'would_act')
        AND (mode = 'live' OR outcome IN ('would_act', 'skipped', 'skipped_same_target', 'depth_exceeded'))),
    CONSTRAINT ck_automation_execution_acted CHECK (outcome NOT IN ('acted', 'partial', 'would_act', 'skipped') OR jsonb_array_length(action_results) >= 1),
    -- Rule 12: an action runs at the event's depth plus one, which is at most 3; depth_exceeded only at 3.
    CONSTRAINT ck_automation_execution_acted_depth CHECK (outcome IN ('skipped_same_target', 'depth_exceeded') OR causation_depth <= 2),
    CONSTRAINT ck_automation_execution_depth_exceeded CHECK (outcome <> 'depth_exceeded' OR causation_depth = 3)
);
-- Rule 13: a rule acts at most once per chain and subject.
CREATE UNIQUE INDEX ux_automation_execution_chain_target ON automation_execution (automation_rule_id, causation_chain_id, subject_table, subject_id)
    WHERE mode = 'live' AND outcome IN ('acted', 'partial');
-- Rule 16: the breaker counts refusals and failures in a window of business date and time, and in a row.
CREATE INDEX ix_automation_execution_rule_recorded ON automation_execution (company_id, automation_rule_id, business_date, recorded_at);
-- ADR-0058 rule 9: subjects outside the owner's scope are not evaluated; a value-free count per rule and business date.
CREATE TABLE automation_scope_skip (
    company_id          uuid NOT NULL,
    automation_rule_id  uuid NOT NULL,
    business_date       date NOT NULL,
    skipped_count       integer NOT NULL CONSTRAINT ck_automation_scope_skip_count CHECK (skipped_count >= 1),
    recorded_at         timestamptz NOT NULL,
    PRIMARY KEY (automation_rule_id, business_date),
    FOREIGN KEY (company_id, automation_rule_id) REFERENCES automation_rule (company_id, id)
);
-- ADR-0058 rule 15: one row per company, locked by every activation, enable, rollback and demotion (ADR-0027 rule 10, class 3).
CREATE TABLE configuration_state (
    company_id        uuid PRIMARY KEY REFERENCES company (id),
    registry_version  text NOT NULL,                       -- the registry the active set was last checked against
    last_checked_at   timestamptz,
    recorded_at       timestamptz NOT NULL
);

-- ===== Decision tables [configuration] (ADR-0058 rules 18-20) =====
CREATE TABLE decision_table (                              -- company data; the identity of a versioned table
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL REFERENCES company (id),
    code                text NOT NULL CONSTRAINT ck_decision_table_code CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    name                text NOT NULL,
    owner_user_id       uuid NOT NULL REFERENCES user_account (id),
    current_version_id  uuid,
    shadow_version_id   uuid,
    recorded_at         timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    CONSTRAINT ck_decision_table_pointers CHECK (current_version_id IS NULL OR current_version_id IS DISTINCT FROM shadow_version_id)
);
CREATE TABLE decision_table_version (                      -- immutable once out of draft (trigger below)
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    decision_table_id      uuid NOT NULL,
    version                integer NOT NULL CONSTRAINT ck_decision_table_version_version CHECK (version >= 1),
    hit_policy             text NOT NULL CONSTRAINT ck_decision_table_version_hit_policy CHECK (hit_policy IN ('unique', 'monotone')),   -- rule 19
    inputs                 jsonb NOT NULL,                 -- [{code, type, domain}]: code values, a half-open numeric range, or boolean (rule 18)
    outputs                jsonb NOT NULL,                 -- [{code, type, aggregator}]; aggregator for monotone: max, min, any, all, union, intersection
    tests                  jsonb NOT NULL DEFAULT '[]',
    state                  text NOT NULL DEFAULT 'draft' CONSTRAINT ck_decision_table_version_state CHECK (state IN ('draft', 'backtested', 'shadow', 'assisted', 'active', 'retired')),
    content_hash           text NOT NULL CONSTRAINT ck_decision_table_version_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    registry_version       text NOT NULL,
    effective_from         date,
    drafted_by_kind        text NOT NULL CONSTRAINT ck_decision_table_version_drafted_by_kind CHECK (drafted_by_kind IN ('human', 'agent', 'system')),
    drafted_by_id          uuid NOT NULL,
    on_behalf_of_id        uuid NOT NULL REFERENCES user_account (id),
    origin_agent_run_id    uuid,
    is_tainted             boolean NOT NULL DEFAULT false,
    drafting_window_from   date,
    drafting_window_to     date NOT NULL,
    change_proposal_id     uuid,
    recorded_at            timestamptz NOT NULL,
    UNIQUE (decision_table_id, version),
    UNIQUE (company_id, id),
    UNIQUE (company_id, decision_table_id, id),
    FOREIGN KEY (company_id, decision_table_id) REFERENCES decision_table (company_id, id),
    FOREIGN KEY (company_id, origin_agent_run_id) REFERENCES agent_run (company_id, id),
    FOREIGN KEY (company_id, change_proposal_id) REFERENCES change_proposal (company_id, id),
    -- Rule 18: at most 6 inputs (and 200 rows).
    CONSTRAINT ck_decision_table_version_inputs CHECK (jsonb_typeof(inputs) = 'array' AND jsonb_array_length(inputs) BETWEEN 1 AND 6),
    CONSTRAINT ck_decision_table_version_outputs CHECK (jsonb_typeof(outputs) = 'array' AND jsonb_array_length(outputs) >= 1),
    CONSTRAINT ck_decision_table_version_tests CHECK (jsonb_typeof(tests) = 'array'),
    CONSTRAINT ck_decision_table_version_effective CHECK (state NOT IN ('assisted', 'active') OR effective_from IS NOT NULL),
    CONSTRAINT ck_decision_table_version_agent CHECK (drafted_by_kind <> 'agent' OR origin_agent_run_id IS NOT NULL),
    CONSTRAINT ck_decision_table_version_window CHECK (drafting_window_from IS NULL OR drafting_window_from <= drafting_window_to)
);
CREATE TABLE decision_table_row (                          -- frozen with its version (trigger below)
    company_id                 uuid NOT NULL,
    decision_table_version_id  uuid NOT NULL,
    row_number                 integer NOT NULL CONSTRAINT ck_decision_table_row_row_number CHECK (row_number BETWEEN 1 AND 200),   -- rule 18
    cells                      jsonb NOT NULL,             -- per input code: {"in": [...]}, {"min": x, "max": y} (half-open) or {"is": true|false}; absent means any
    outputs                    jsonb NOT NULL,             -- per output code: a typed value
    recorded_at                timestamptz NOT NULL,
    PRIMARY KEY (decision_table_version_id, row_number),
    FOREIGN KEY (company_id, decision_table_version_id) REFERENCES decision_table_version (company_id, id),
    CONSTRAINT ck_decision_table_row_cells CHECK (jsonb_typeof(cells) = 'object'),
    CONSTRAINT ck_decision_table_row_outputs CHECK (jsonb_typeof(outputs) = 'object')
);

-- ===== Parameter sets [configuration] (ADR-0059 rules 3-8) =====
CREATE TABLE parameter_set (                               -- company data; one per company and tunable function (rule 4)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL REFERENCES company (id),
    function_code       text NOT NULL CONSTRAINT ck_parameter_set_function_code CHECK (function_code ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'),   -- e.g. cash.match_bank_line
    owner_user_id       uuid NOT NULL REFERENCES user_account (id),
    current_version_id  uuid,                              -- null: the core defaults of the registry are in force
    shadow_version_id   uuid,
    recorded_at         timestamptz NOT NULL,
    UNIQUE (company_id, function_code),
    UNIQUE (company_id, id),
    CONSTRAINT ck_parameter_set_pointers CHECK (current_version_id IS NULL OR current_version_id IS DISTINCT FROM shadow_version_id)
);
CREATE TABLE parameter_set_version (                       -- immutable once out of draft (trigger below)
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    parameter_set_id       uuid NOT NULL,
    version                integer NOT NULL CONSTRAINT ck_parameter_set_version_version CHECK (version >= 1),
    function_version       text NOT NULL CONSTRAINT ck_parameter_set_version_function_version CHECK (function_version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),   -- semver of the declaration (rule 3)
    parameters_hash        text NOT NULL CONSTRAINT ck_parameter_set_version_parameters_hash CHECK (parameters_hash ~ '^[0-9a-f]{64}$'),   -- rule 4: function code and values, without the function version
    state                  text NOT NULL DEFAULT 'draft' CONSTRAINT ck_parameter_set_version_state CHECK (state IN ('draft', 'backtested', 'shadow', 'assisted', 'active', 'retired')),
    content_hash           text NOT NULL CONSTRAINT ck_parameter_set_version_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    registry_version       text NOT NULL,
    effective_from         date,
    drafted_by_kind        text NOT NULL CONSTRAINT ck_parameter_set_version_drafted_by_kind CHECK (drafted_by_kind IN ('human', 'agent', 'system')),
    drafted_by_id          uuid NOT NULL,
    on_behalf_of_id        uuid NOT NULL REFERENCES user_account (id),
    origin_agent_run_id    uuid,
    is_tainted             boolean NOT NULL DEFAULT false,
    drafting_window_from   date,
    drafting_window_to     date NOT NULL,
    change_proposal_id     uuid,
    recorded_at            timestamptz NOT NULL,
    UNIQUE (parameter_set_id, version),
    UNIQUE (company_id, id),
    UNIQUE (company_id, parameter_set_id, id),
    FOREIGN KEY (company_id, parameter_set_id) REFERENCES parameter_set (company_id, id),
    FOREIGN KEY (company_id, origin_agent_run_id) REFERENCES agent_run (company_id, id),
    FOREIGN KEY (company_id, change_proposal_id) REFERENCES change_proposal (company_id, id),
    CONSTRAINT ck_parameter_set_version_effective CHECK (state NOT IN ('assisted', 'active') OR effective_from IS NOT NULL),
    CONSTRAINT ck_parameter_set_version_agent CHECK (drafted_by_kind <> 'agent' OR origin_agent_run_id IS NOT NULL),
    CONSTRAINT ck_parameter_set_version_window CHECK (drafting_window_from IS NULL OR drafting_window_from <= drafting_window_to)
);
-- One per declared parameter, with the declaration's type, default and bounds copied at the version's function version;
-- frozen with its version (trigger below).
CREATE TABLE parameter_set_value (
    company_id                uuid NOT NULL,
    parameter_set_version_id  uuid NOT NULL,
    parameter_code            text NOT NULL CONSTRAINT ck_parameter_set_value_code CHECK (parameter_code ~ '^[a-z][a-z0-9_]*$'),
    value_type                text NOT NULL CONSTRAINT ck_parameter_set_value_type CHECK (value_type IN ('integer', 'decimal', 'score', 'percent', 'days')),
    value                     numeric,                     -- null means off, where the declaration allows it
    is_nullable               boolean NOT NULL DEFAULT false,
    default_value             numeric,                     -- the core default; null where the default is off
    min_value                 numeric NOT NULL,
    max_value                 numeric NOT NULL,
    is_safety_cap             boolean NOT NULL DEFAULT false,   -- lowered only and never off: the maximum is the core default (rule 3)
    recorded_at               timestamptz NOT NULL,
    PRIMARY KEY (parameter_set_version_id, parameter_code),
    FOREIGN KEY (company_id, parameter_set_version_id) REFERENCES parameter_set_version (company_id, id),
    CONSTRAINT ck_parameter_set_value_bounds CHECK (min_value <= max_value),
    CONSTRAINT ck_parameter_set_value_in_bounds CHECK (value IS NULL OR value BETWEEN min_value AND max_value),   -- parameter_out_of_bounds
    CONSTRAINT ck_parameter_set_value_nullable CHECK (value IS NOT NULL OR is_nullable),
    CONSTRAINT ck_parameter_set_value_default CHECK (default_value IS NULL OR default_value BETWEEN min_value AND max_value),
    CONSTRAINT ck_parameter_set_value_whole CHECK (value_type NOT IN ('integer', 'score', 'days') OR value IS NULL OR value = trunc(value)),
    CONSTRAINT ck_parameter_set_value_score CHECK (value_type <> 'score' OR (min_value >= 0 AND max_value <= 100)),
    CONSTRAINT ck_parameter_set_value_percent CHECK (value_type <> 'percent' OR (min_value >= 0 AND max_value <= 100)),
    CONSTRAINT ck_parameter_set_value_cap CHECK (NOT is_safety_cap OR (default_value IS NOT NULL AND max_value = default_value)),
    CONSTRAINT ck_parameter_set_value_cap_set CHECK (NOT is_safety_cap OR (NOT is_nullable AND value IS NOT NULL))
);

-- ===== Lifecycle, evidence and shadow outcomes [configuration] (ADR-0059 rules 12-19) =====
CREATE TABLE artifact_promotion_evidence (                 -- immutable; computed once by CreateArtifactEvidence (rule 14)
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    artifact_kind            text NOT NULL CONSTRAINT ck_artifact_promotion_evidence_kind CHECK (artifact_kind IN (
                                 'parameter_set', 'decision_table', 'automation_rule', 'matching_rule', 'report_definition', 'analysis_definition', 'extraction_mapping')),
    artifact_id              uuid,                         -- null only for a re-evaluation of core defaults (rule 4)
    artifact_version_id      uuid,
    function_code            text,                         -- the tunable function, for parameter sets and their core defaults
    stage                    text NOT NULL CONSTRAINT ck_artifact_promotion_evidence_stage CHECK (stage IN ('backtest', 'preview', 'live', 'reevaluation')),
    content_hash             text NOT NULL CONSTRAINT ck_artifact_promotion_evidence_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    engine_version           text NOT NULL,                -- the function version, or the registry version for rules and tables
    baseline_version_id      uuid,                         -- the version in force at creation; null: core defaults, or none
    baseline_hash            text NOT NULL CONSTRAINT ck_artifact_promotion_evidence_baseline_hash CHECK (baseline_hash ~ '^[0-9a-f]{64}$'),
    drafting_window_from     date,                         -- null: from the beginning
    drafting_window_to       date NOT NULL,                -- the version's (rule 15)
    evaluation_window_from   date NOT NULL,
    evaluation_window_to     date NOT NULL,
    case_count               integer NOT NULL CONSTRAINT ck_artifact_promotion_evidence_case_count CHECK (case_count >= 0),
    min_case_count           integer NOT NULL CONSTRAINT ck_artifact_promotion_evidence_min_case_count CHECK (min_case_count >= 1),   -- the function's or kind's (rule 18)
    window_reuse_count       integer NOT NULL CONSTRAINT ck_artifact_promotion_evidence_window_reuse CHECK (window_reuse_count >= 0),   -- earlier rows with overlapping windows (rule 15)
    data_window_hash         text NOT NULL CONSTRAINT ck_artifact_promotion_evidence_data_window_hash CHECK (data_window_hash ~ '^[0-9a-f]{64}$'),   -- SHA-256 of the sorted case IDs
    golden_set_hash          text CONSTRAINT ck_artifact_promotion_evidence_golden_set_hash CHECK (golden_set_hash ~ '^[0-9a-f]{64}$'),
    held_out_case_count      integer NOT NULL DEFAULT 0 CONSTRAINT ck_artifact_promotion_evidence_held_out_count CHECK (held_out_case_count >= 0),
    held_out_seen_count      integer NOT NULL DEFAULT 0 CONSTRAINT ck_artifact_promotion_evidence_held_out_seen CHECK (held_out_seen_count >= 0),   -- rule 16
    drafting_reads_hash      text CONSTRAINT ck_artifact_promotion_evidence_reads_hash CHECK (drafting_reads_hash ~ '^[0-9a-f]{64}$'),   -- the drafting run's read references, frozen (rule 14)
    figures                  jsonb NOT NULL,               -- against the baseline; a scorer's precision and coverage curve (rule 20)
    changed_sample           jsonb NOT NULL DEFAULT '[]',  -- at most 20 changed decisions (rule 17)
    thresholds               jsonb NOT NULL,
    is_sufficient            boolean NOT NULL,
    drafted_by_filtered_run  boolean NOT NULL DEFAULT false,   -- the version came from a held-out-filtered drafting run, not a person (rule 16)
    created_by_kind          text NOT NULL DEFAULT 'human' CONSTRAINT ck_artifact_promotion_evidence_created_by_kind CHECK (created_by_kind IN ('human', 'system')),
    created_by_user_id       uuid REFERENCES user_account (id),   -- null when the monitor job wrote a re-evaluation
    recorded_at              timestamptz NOT NULL,
    UNIQUE (company_id, id),
    CONSTRAINT ck_artifact_promotion_evidence_windows CHECK (evaluation_window_from <= evaluation_window_to
        AND (drafting_window_from IS NULL OR drafting_window_from <= drafting_window_to)),
    -- Rule 15: a backtest or preview is out of sample: its window starts after the drafting window ends (backtest_window_not_after_drafting).
    CONSTRAINT ck_artifact_promotion_evidence_out_of_sample CHECK (stage NOT IN ('backtest', 'preview') OR evaluation_window_from > drafting_window_to),
    -- Rule 14: sufficient evidence is non-empty and reaches the minimum; previews and re-evaluations never suffice.
    CONSTRAINT ck_artifact_promotion_evidence_minimum CHECK (NOT is_sufficient OR case_count >= min_case_count),
    CONSTRAINT ck_artifact_promotion_evidence_stage_sufficient CHECK (stage IN ('backtest', 'live') OR NOT is_sufficient),
    -- Rule 16: evidence whose drafting run saw a held-out case is never sufficient (held_out_case_seen).
    CONSTRAINT ck_artifact_promotion_evidence_held_out CHECK (held_out_seen_count = 0 OR NOT is_sufficient),
    CONSTRAINT ck_artifact_promotion_evidence_sample CHECK (jsonb_typeof(changed_sample) = 'array' AND jsonb_array_length(changed_sample) <= 20),
    -- Rule 4: only a re-evaluation of a company's core defaults has no artifact; it names the function.
    CONSTRAINT ck_artifact_promotion_evidence_subject CHECK ((artifact_id IS NULL) = (artifact_version_id IS NULL)
        AND (artifact_version_id IS NOT NULL OR (stage = 'reevaluation' AND artifact_kind = 'parameter_set' AND function_code IS NOT NULL))),
    -- Rule 13: a person creates evidence; only the monitor job writes re-evaluations.
    CONSTRAINT ck_artifact_promotion_evidence_creator CHECK ((created_by_kind = 'human') = (created_by_user_id IS NOT NULL)
        AND (created_by_kind = 'human' OR stage = 'reevaluation'))
);
CREATE TABLE artifact_transition (                         -- immutable; one per lifecycle or pointer move (rule 13)
    id                           uuid PRIMARY KEY,
    company_id                   uuid NOT NULL REFERENCES company (id),
    artifact_kind                text NOT NULL CONSTRAINT ck_artifact_transition_kind CHECK (artifact_kind IN (
                                     'parameter_set', 'decision_table', 'automation_rule', 'matching_rule', 'report_definition', 'analysis_definition', 'extraction_mapping')),
    artifact_id                  uuid NOT NULL,
    artifact_version_id          uuid,                     -- null for a pointer move to core defaults or none, and for disable and enable
    move                         text NOT NULL CONSTRAINT ck_artifact_transition_move CHECK (move IN (
                                     'backtested', 'promoted', 'demoted', 'retired', 'rolled_back', 'disabled', 'enabled', 'invalidated', 'deprecation_found')),
    from_state                   text CONSTRAINT ck_artifact_transition_from_state CHECK (from_state IN ('draft', 'backtested', 'shadow', 'assisted', 'active')),
    to_state                     text CONSTRAINT ck_artifact_transition_to_state CHECK (to_state IN ('backtested', 'shadow', 'assisted', 'active', 'retired')),
    previous_current_version_id  uuid,
    new_current_version_id       uuid,
    evidence_id                  uuid,
    change_proposal_id           uuid,
    reason                       text,
    actor_kind                   text NOT NULL CONSTRAINT ck_artifact_transition_actor_kind CHECK (actor_kind IN ('human', 'agent', 'integration', 'system')),
    actor_id                     uuid NOT NULL,
    on_behalf_of_id              uuid REFERENCES user_account (id),
    recorded_at                  timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, evidence_id) REFERENCES artifact_promotion_evidence (company_id, id),
    FOREIGN KEY (company_id, change_proposal_id) REFERENCES change_proposal (company_id, id),
    -- Rule 13: raising a state names evidence and runs from an approved change proposal; a backtested move names evidence.
    CONSTRAINT ck_artifact_transition_promoted CHECK (move <> 'promoted' OR (evidence_id IS NOT NULL AND change_proposal_id IS NOT NULL
        AND to_state IN ('shadow', 'assisted', 'active'))),
    CONSTRAINT ck_artifact_transition_backtested CHECK (move <> 'backtested' OR (evidence_id IS NOT NULL AND from_state = 'draft' AND to_state = 'backtested')),
    CONSTRAINT ck_artifact_transition_demoted CHECK (move <> 'demoted' OR (from_state IN ('assisted', 'active') AND to_state = 'shadow')),
    CONSTRAINT ck_artifact_transition_retired CHECK (move <> 'retired' OR to_state = 'retired'),
    CONSTRAINT ck_artifact_transition_deprecation CHECK (move <> 'deprecation_found' OR (from_state IS NULL AND to_state IS NULL))
);
-- Rule 12: a shadow version's outcome beside the version in force, per live case; automation rules use
-- automation_execution in mode shadow instead.
CREATE TABLE artifact_shadow_outcome (
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    artifact_kind        text NOT NULL CONSTRAINT ck_artifact_shadow_outcome_kind CHECK (artifact_kind IN (
                             'parameter_set', 'decision_table', 'matching_rule', 'extraction_mapping')),
    artifact_id          uuid NOT NULL,
    artifact_version_id  uuid NOT NULL,
    case_table           text NOT NULL,
    case_id              uuid NOT NULL,
    shadow_outcome       jsonb NOT NULL,
    current_outcome      jsonb NOT NULL,                   -- what the version in force (or the core defaults) decided
    current_hash         text NOT NULL CONSTRAINT ck_artifact_shadow_outcome_current_hash CHECK (current_hash ~ '^[0-9a-f]{64}$'),
    recorded_at          timestamptz NOT NULL,
    UNIQUE (artifact_version_id, case_table, case_id)
);

-- ===== Golden case labels and monitoring [configuration] (ADR-0059 rules 16, 21-22) =====
CREATE TABLE golden_case_label (                           -- company data; append-only, retired_at set once (rule 22)
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    function_code        text NOT NULL,                    -- the deterministic function or artifact kind the case labels
    case_table           text NOT NULL,
    case_id              uuid NOT NULL,
    expected             jsonb NOT NULL,                   -- the correct outcome, e.g. {"partner_id": ..., "open_item_ids": [...]}
    is_held_out          boolean NOT NULL,                 -- rule 16, held below
    labelled_by_user_id  uuid NOT NULL REFERENCES user_account (id),
    labelled_on          date NOT NULL,
    retired_at           timestamptz,                      -- set once when a later label replaces it
    recorded_at          timestamptz NOT NULL,
    UNIQUE (company_id, id),
    -- Rule 16: held out when the first byte of SHA-256 of the UTF-8 text '<company_id>:<case_id>' (canonical UUIDs) is below 51.
    CONSTRAINT ck_golden_case_label_held_out CHECK (is_held_out = (get_byte(sha256(convert_to(company_id::text || ':' || case_id::text, 'UTF8')), 0) < 51))
);
CREATE UNIQUE INDEX ux_golden_case_label_current ON golden_case_label (company_id, function_code, case_table, case_id) WHERE retired_at IS NULL;
CREATE TABLE artifact_monitor_snapshot (                   -- immutable; one per artifact version in force and day (rule 21)
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL REFERENCES company (id),
    artifact_kind           text NOT NULL CONSTRAINT ck_artifact_monitor_snapshot_kind CHECK (artifact_kind IN (
                                'parameter_set', 'decision_table', 'automation_rule', 'matching_rule', 'report_definition', 'analysis_definition', 'extraction_mapping')),
    artifact_id             uuid NOT NULL,
    artifact_version_id     uuid NOT NULL,
    window_from             date NOT NULL,
    window_to               date NOT NULL,
    decision_count          integer NOT NULL CONSTRAINT ck_artifact_monitor_snapshot_decisions CHECK (decision_count >= 0),
    override_count          integer NOT NULL,
    baseline_override_rate  numeric NOT NULL CONSTRAINT ck_artifact_monitor_snapshot_baseline CHECK (baseline_override_rate BETWEEN 0 AND 1),   -- from the version's evidence
    acted_share             numeric CONSTRAINT ck_artifact_monitor_snapshot_acted_share CHECK (acted_share BETWEEN 0 AND 1),
    baseline_acted_share    numeric CONSTRAINT ck_artifact_monitor_snapshot_baseline_acted CHECK (baseline_acted_share BETWEEN 0 AND 1),
    thresholds              jsonb NOT NULL,
    result                  text NOT NULL CONSTRAINT ck_artifact_monitor_snapshot_result CHECK (result IN ('within', 'breached', 'too_few_decisions')),
    transition_id           uuid,                          -- the demotion a breach caused
    recorded_at             timestamptz NOT NULL,
    UNIQUE (artifact_version_id, window_to),
    FOREIGN KEY (company_id, transition_id) REFERENCES artifact_transition (company_id, id),
    CONSTRAINT ck_artifact_monitor_snapshot_window CHECK (window_from <= window_to),
    CONSTRAINT ck_artifact_monitor_snapshot_overrides CHECK (override_count BETWEEN 0 AND decision_count),
    CONSTRAINT ck_artifact_monitor_snapshot_breach CHECK ((result = 'breached') = (transition_id IS NOT NULL))
);

-- ===== Keys closed after their tables (pointers form cycles with the version tables) =====
-- ADR-0059 rule 12: a pointer names a version of the same artifact; its state is checked by the trigger below.
ALTER TABLE automation_rule ADD CONSTRAINT fk_automation_rule_current_version
    FOREIGN KEY (company_id, id, current_version_id) REFERENCES automation_rule_version (company_id, automation_rule_id, id);
ALTER TABLE automation_rule ADD CONSTRAINT fk_automation_rule_shadow_version
    FOREIGN KEY (company_id, id, shadow_version_id) REFERENCES automation_rule_version (company_id, automation_rule_id, id);
ALTER TABLE decision_table ADD CONSTRAINT fk_decision_table_current_version
    FOREIGN KEY (company_id, id, current_version_id) REFERENCES decision_table_version (company_id, decision_table_id, id);
ALTER TABLE decision_table ADD CONSTRAINT fk_decision_table_shadow_version
    FOREIGN KEY (company_id, id, shadow_version_id) REFERENCES decision_table_version (company_id, decision_table_id, id);
ALTER TABLE parameter_set ADD CONSTRAINT fk_parameter_set_current_version
    FOREIGN KEY (company_id, id, current_version_id) REFERENCES parameter_set_version (company_id, parameter_set_id, id);
ALTER TABLE parameter_set ADD CONSTRAINT fk_parameter_set_shadow_version
    FOREIGN KEY (company_id, id, shadow_version_id) REFERENCES parameter_set_version (company_id, parameter_set_id, id);

-- ===== Guards =====
-- ADR-0058 rule 21; ADR-0059 rule 12. A version is inserted only as a draft and changes freely in draft. Once out of draft
-- only state, effective_from (set once) and change_proposal_id move; the content never changes. From draft a version moves
-- only to backtested; then forward (skipping only what the kind allows, a command check), back from assisted or active to
-- shadow (demotion), or to retired; never back to draft, never out of retired. A version in force is demoted only after
-- the pointer moved off it. Leaving shadow clears a shadow pointer that names the version; retiring clears both pointers.
-- Only drafts are deleted. Arguments: the identity table and the version's column naming it.
CREATE FUNCTION artifact_version_check_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.state <> 'draft' THEN
        RAISE EXCEPTION '% rows are inserted only as drafts, not % (artifact_version_not_eligible)', TG_TABLE_NAME, NEW.state USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE FUNCTION artifact_version_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_rank     jsonb := '{"draft": 0, "backtested": 1, "shadow": 2, "assisted": 3, "active": 4}';
    v_mutable  text[] := ARRAY['state', 'effective_from', 'change_proposal_id'];
    v_parent   uuid;
    v_in_force boolean;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state <> 'draft' THEN
            RAISE EXCEPTION '% rows are deleted only in draft (artifact_version_immutable)', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.state = 'draft' AND NEW.state = 'draft' THEN
        RETURN NEW;
    END IF;
    IF (to_jsonb(OLD) - v_mutable) IS DISTINCT FROM (to_jsonb(NEW) - v_mutable) THEN
        RAISE EXCEPTION '% content is immutable once out of draft (artifact_version_immutable)', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
    END IF;
    IF OLD.effective_from IS NOT NULL AND NEW.effective_from IS DISTINCT FROM OLD.effective_from THEN
        RAISE EXCEPTION '%.effective_from is set once', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.state IS NOT DISTINCT FROM OLD.state THEN
        RETURN NEW;
    END IF;
    IF OLD.state = 'retired' THEN
        RAISE EXCEPTION '% version % is retired, which is final', TG_TABLE_NAME, OLD.id USING ERRCODE = 'restrict_violation';
    ELSIF NEW.state = 'draft' THEN
        RAISE EXCEPTION '% version % cannot return to draft', TG_TABLE_NAME, OLD.id USING ERRCODE = 'restrict_violation';
    ELSIF OLD.state = 'draft' AND NEW.state = 'retired' THEN
        RAISE EXCEPTION '% drafts are deleted, not retired', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
    ELSIF OLD.state = 'draft' AND NEW.state <> 'backtested' THEN
        RAISE EXCEPTION '% version % leaves draft only to backtested, not %', TG_TABLE_NAME, OLD.id, NEW.state USING ERRCODE = 'restrict_violation';
    ELSIF NOT (NEW.state = 'retired'
               OR (NEW.state = 'shadow' AND OLD.state IN ('assisted', 'active'))
               OR (v_rank ->> NEW.state)::int > (v_rank ->> OLD.state)::int) THEN
        RAISE EXCEPTION '% version % may not move from % to %', TG_TABLE_NAME, OLD.id, OLD.state, NEW.state USING ERRCODE = 'restrict_violation';
    END IF;
    v_parent := (to_jsonb(NEW) ->> TG_ARGV[1])::uuid;
    IF NEW.state = 'shadow' AND OLD.state IN ('assisted', 'active') THEN
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I WHERE id = $1 AND current_version_id = $2)', TG_ARGV[0])
            INTO v_in_force USING v_parent, NEW.id;
        IF v_in_force THEN
            RAISE EXCEPTION '% version % is in force; move the current pointer first', TG_TABLE_NAME, OLD.id USING ERRCODE = 'restrict_violation';
        END IF;
    END IF;
    IF OLD.state = 'shadow' OR NEW.state = 'retired' THEN
        EXECUTE format('UPDATE %I SET shadow_version_id = NULL WHERE id = $1 AND shadow_version_id = $2', TG_ARGV[0]) USING v_parent, NEW.id;
    END IF;
    IF NEW.state = 'retired' THEN
        EXECUTE format('UPDATE %I SET current_version_id = NULL WHERE id = $1 AND current_version_id = $2', TG_ARGV[0]) USING v_parent, NEW.id;
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0058 rule 20 and its note of the final simulation review: a rule version leaves draft only when every pinned decision
-- table version exists in the company and is frozen (backtested, shadow, assisted or active), so its replay can be stored
-- against a table not yet in force; it becomes active only when every pinned version is assisted or active, so a rule in
-- force never pins anything else. One change proposal may raise the table version and then the rule version in one
-- transaction (rule 24 note). A pinned version is neither retired nor demoted to shadow while a current or shadow rule
-- version pins it.
CREATE FUNCTION automation_rule_version_check_pins() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_bad uuid;
BEGIN
    IF OLD.state = 'draft' AND NEW.state <> 'draft' THEN
        SELECT p INTO v_bad FROM unnest(NEW.decision_table_version_ids) AS p
         WHERE NOT EXISTS (SELECT 1 FROM decision_table_version d WHERE d.id = p AND d.company_id = NEW.company_id
                             AND d.state IN ('backtested', 'shadow', 'assisted', 'active'))
         LIMIT 1;
        IF v_bad IS NOT NULL THEN
            RAISE EXCEPTION 'automation_rule_version % pins decision table version %, which is not an assisted or active version of the company, nor a backtested or shadow one a proposal may raise first (artifact_invalid)', NEW.id, v_bad
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF NEW.state = 'active' AND OLD.state IS DISTINCT FROM 'active' THEN
        SELECT p INTO v_bad FROM unnest(NEW.decision_table_version_ids) AS p
         WHERE NOT EXISTS (SELECT 1 FROM decision_table_version d WHERE d.id = p AND d.company_id = NEW.company_id AND d.state IN ('assisted', 'active'))
         LIMIT 1;
        IF v_bad IS NOT NULL THEN
            RAISE EXCEPTION 'automation_rule_version % pins decision table version %, which is not an assisted or active version of the company (artifact_invalid)', NEW.id, v_bad
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$$;
CREATE FUNCTION decision_table_version_check_in_use() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.state IS DISTINCT FROM OLD.state AND (NEW.state = 'retired' OR (NEW.state = 'shadow' AND OLD.state IN ('assisted', 'active'))) AND EXISTS (
        SELECT 1 FROM automation_rule_version v JOIN automation_rule r ON r.id = v.automation_rule_id
         WHERE NEW.id = ANY (v.decision_table_version_ids) AND (r.current_version_id = v.id OR r.shadow_version_id = v.id)) THEN
        RAISE EXCEPTION 'decision table version % is pinned by a rule version in force or in shadow (decision_table_version_in_use)', NEW.id USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0058 rule 9: the scope count only rises; rows are never deleted.
CREATE FUNCTION automation_scope_skip_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' OR NEW.automation_rule_id <> OLD.automation_rule_id OR NEW.business_date <> OLD.business_date
       OR NEW.company_id <> OLD.company_id OR NEW.skipped_count < OLD.skipped_count THEN
        RAISE EXCEPTION 'automation_scope_skip counts only rise' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
-- Child rows (decision table rows, parameter values) change only while their version is a draft.
-- Arguments: the version table and the child's column naming it.
CREATE FUNCTION artifact_child_check_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_ids    uuid[];
    v_id     uuid;
    v_state  text;
BEGIN
    v_ids := ARRAY[CASE WHEN TG_OP <> 'INSERT' THEN (to_jsonb(OLD) ->> TG_ARGV[1])::uuid END,
                   CASE WHEN TG_OP <> 'DELETE' THEN (to_jsonb(NEW) ->> TG_ARGV[1])::uuid END];
    FOREACH v_id IN ARRAY v_ids LOOP
        CONTINUE WHEN v_id IS NULL;
        EXECUTE format('SELECT state FROM %I WHERE id = $1', TG_ARGV[0]) INTO v_state USING v_id;
        IF v_state IS NOT NULL AND v_state <> 'draft' THEN
            RAISE EXCEPTION '% rows are frozen with their version (state %) (artifact_version_immutable)', TG_TABLE_NAME, v_state USING ERRCODE = 'restrict_violation';
        END IF;
    END LOOP;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0059 rule 12: the current pointer names a version in state assisted or active, the shadow pointer one in shadow.
-- Argument: the version table.
CREATE FUNCTION artifact_pointer_check() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_state  text;
BEGIN
    IF NEW.current_version_id IS NOT NULL AND (TG_OP = 'INSERT' OR NEW.current_version_id IS DISTINCT FROM OLD.current_version_id) THEN
        EXECUTE format('SELECT state FROM %I WHERE id = $1', TG_ARGV[0]) INTO v_state USING NEW.current_version_id;
        IF v_state IS DISTINCT FROM 'assisted' AND v_state IS DISTINCT FROM 'active' THEN
            RAISE EXCEPTION '%.current_version_id must name an assisted or active version, not % (artifact_version_not_eligible)', TG_TABLE_NAME, coalesce(v_state, 'none')
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF NEW.shadow_version_id IS NOT NULL AND (TG_OP = 'INSERT' OR NEW.shadow_version_id IS DISTINCT FROM OLD.shadow_version_id) THEN
        EXECUTE format('SELECT state FROM %I WHERE id = $1', TG_ARGV[0]) INTO v_state USING NEW.shadow_version_id;
        IF v_state IS DISTINCT FROM 'shadow' THEN
            RAISE EXCEPTION '%.shadow_version_id must name a shadow version, not % (artifact_version_not_eligible)', TG_TABLE_NAME, coalesce(v_state, 'none')
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_automation_rule_version_check_insert BEFORE INSERT ON automation_rule_version FOR EACH ROW EXECUTE FUNCTION artifact_version_check_insert();
CREATE TRIGGER trg_decision_table_version_check_insert BEFORE INSERT ON decision_table_version FOR EACH ROW EXECUTE FUNCTION artifact_version_check_insert();
CREATE TRIGGER trg_parameter_set_version_check_insert BEFORE INSERT ON parameter_set_version FOR EACH ROW EXECUTE FUNCTION artifact_version_check_insert();
CREATE TRIGGER trg_automation_rule_version_check_change BEFORE UPDATE OR DELETE ON automation_rule_version FOR EACH ROW
    EXECUTE FUNCTION artifact_version_check_change('automation_rule', 'automation_rule_id');
CREATE TRIGGER trg_decision_table_version_check_change BEFORE UPDATE OR DELETE ON decision_table_version FOR EACH ROW
    EXECUTE FUNCTION artifact_version_check_change('decision_table', 'decision_table_id');
CREATE TRIGGER trg_parameter_set_version_check_change BEFORE UPDATE OR DELETE ON parameter_set_version FOR EACH ROW
    EXECUTE FUNCTION artifact_version_check_change('parameter_set', 'parameter_set_id');
CREATE TRIGGER trg_decision_table_row_frozen BEFORE INSERT OR UPDATE OR DELETE ON decision_table_row FOR EACH ROW
    EXECUTE FUNCTION artifact_child_check_frozen('decision_table_version', 'decision_table_version_id');
CREATE TRIGGER trg_parameter_set_value_frozen BEFORE INSERT OR UPDATE OR DELETE ON parameter_set_value FOR EACH ROW
    EXECUTE FUNCTION artifact_child_check_frozen('parameter_set_version', 'parameter_set_version_id');
CREATE TRIGGER trg_automation_rule_pointer BEFORE INSERT OR UPDATE ON automation_rule FOR EACH ROW
    EXECUTE FUNCTION artifact_pointer_check('automation_rule_version');
CREATE TRIGGER trg_decision_table_pointer BEFORE INSERT OR UPDATE ON decision_table FOR EACH ROW
    EXECUTE FUNCTION artifact_pointer_check('decision_table_version');
CREATE TRIGGER trg_parameter_set_pointer BEFORE INSERT OR UPDATE ON parameter_set FOR EACH ROW
    EXECUTE FUNCTION artifact_pointer_check('parameter_set_version');
CREATE TRIGGER trg_automation_rule_version_pins BEFORE UPDATE ON automation_rule_version FOR EACH ROW EXECUTE FUNCTION automation_rule_version_check_pins();
CREATE TRIGGER trg_decision_table_version_in_use BEFORE UPDATE ON decision_table_version FOR EACH ROW EXECUTE FUNCTION decision_table_version_check_in_use();
CREATE TRIGGER trg_automation_scope_skip_check_change BEFORE UPDATE OR DELETE ON automation_scope_skip FOR EACH ROW EXECUTE FUNCTION automation_scope_skip_check_change();
CREATE TRIGGER trg_automation_execution_immutable BEFORE UPDATE OR DELETE ON automation_execution FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_artifact_promotion_evidence_immutable BEFORE UPDATE OR DELETE ON artifact_promotion_evidence FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_artifact_transition_immutable BEFORE UPDATE OR DELETE ON artifact_transition FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_artifact_shadow_outcome_immutable BEFORE UPDATE OR DELETE ON artifact_shadow_outcome FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_artifact_monitor_snapshot_immutable BEFORE UPDATE OR DELETE ON artifact_monitor_snapshot FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_golden_case_label_append_only BEFORE UPDATE OR DELETE ON golden_case_label FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{retired_at}', '{}');

-- ===== Row-level security (ADR-0017 rule 19; ADR-0022 rule 8) =====
-- rls_v1 as DS-05-platform.sql writes it: the company policy, compared as text and failing closed, and the read-only
-- company_ids policy for registered cross-company queries. No table here has installation-scoped rows.
DO $$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'automation_rule', 'automation_rule_version', 'automation_execution', 'automation_scope_skip', 'configuration_state', 'decision_table',
        'decision_table_version', 'decision_table_row', 'parameter_set', 'parameter_set_version', 'parameter_set_value',
        'artifact_promotion_evidence', 'artifact_transition', 'artifact_shadow_outcome', 'golden_case_label',
        'artifact_monitor_snapshot'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', v_table);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', v_table);
        EXECUTE format('CREATE POLICY company_policy ON %I USING (company_id::text = current_setting(''nativeflows.company_id'', true))', v_table);
        EXECUTE format('CREATE POLICY company_ids_policy ON %I FOR SELECT USING (company_id::text = ANY (string_to_array(current_setting(''nativeflows.company_ids'', true), '','')))', v_table);
    END LOOP;
END
$$;
