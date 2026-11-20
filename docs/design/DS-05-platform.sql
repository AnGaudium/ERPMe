-- DS-05 platform: DDL draft for the layer-2 platform tables and the cash tables that the six business flows need.
-- Named after DS-05 (document lifecycle, ADR-0009 and ADR-0028), the item whose `document` row every other table here
-- refers to. The file also carries the tables of DS-13 (outbox, ADR-0013), DS-23 (document taxes and the tax subledger,
-- ADR-0041), DS-25 (money accounts, bank statements and payments, ADR-0048), DS-28 (policy and approvals, ADR-0043 and
-- ADR-0055; the pool tables themselves are in DS-15-access.sql), DS-29 (work queue, ADR-0042), DS-32 (agent runs,
-- ADR-0050), DS-36 (audit and attachments, ADR-0038) and DS-47 (change proposals and taint, ADR-0029).
-- DS-22-09-42-commercial-inventory.sql (commercial documents and inventory) refers to document, document_line_tax and
-- the cash tables here, and defines material_document, which the lab stubs until both files are in design/.
-- PostgreSQL 18. Loaded with DS-15, DS-20, DS-35, DS-56 and DS-06 in the design lab, and also together with the two
-- other holistic drafts (docs/reviews/2026-11-14-design-validation, t15_platform_ddl.py). The ADRs win if this file
-- disagrees.
-- Conventions of DS-20 and DS-15: tables in schema `nativeflows`, domains in `types`; keys inline, named by the MetaData naming
-- convention in migrations (ADR-0004 rule 15); IDs are UUIDv7 from context.new_id (ADR-0006 rule 3), no ID defaults;
-- references between company tables are composite on (company_id, id); recorded_at on every row (ADR-0007 rule 9).
-- Every table with company_id gets FORCE ROW LEVEL SECURITY and the company policy of ADR-0017 rule 19; the last
-- section writes them as the rls_v1 helper would (ADR-0022 rule 8). Tables whose company_id is nullable
-- (outbox_event, event_delivery, audit_record, audit_change, audit_denial, agent_budget_usage) show their null rows only
-- under the setting value `installation` (ADR-0017 rule 19; ADR-0013 rule 14).
-- Installation tables, without company_id: event_subject, event_consumer, agent_type, agent_type_version. The lab
-- checks this list.
-- payment_method_money_account (ADR-0068 rule 16) refers to payment_method and branch, and payment and payment_line to
-- payment_method and business_unit, all in DS-20-master-data.sql.
-- The configuration and artifact tables (ADR-0058, ADR-0059) are in DS-28-34-configuration-artifacts.sql; this file carries
-- only their causation columns on outbox_event and audit_record and the match parameter columns of bank_statement_line.
-- Referenced tables defined elsewhere: company, branch, partner, partner_bank_account, warehouse, cost_center, project,
-- currency (DS-20); user_account, role, approval_pool, approval_stage, segregation_exception (DS-15); inbound_message,
-- interaction_summary (DS-35); journal_entry, open_item, derivation_trace (DS-06); account, fiscal_year, posting_period,
-- tax_code (no DDL draft yet; lab stubs). The tables of other files that this file changes are in "Keys closed after
-- their tables".
-- Columns that no ADR states are marked "interim: not stated in ADR-xxxx"; a later ADR note or design item decides them.
-- Owner module per section in brackets (ADR-0022 rule 2; ADR-0027 rule 1).
-- Rules that need other rows or the registry (allowed targets of a proposal, stage eligibility, the matching cascade,
-- the supplier-invoice key across tables) are enforced by commands and named in their ADRs; the rules a row can hold are
-- checks here, and a few cross-row rules that the database can hold cheaply are triggers at the end.

-- ===== Agent types [agent_runs] (ADR-0050 rules 12, 14; ADR-0027 rule 1) =====
-- Written by the registry at startup from the workflow declarations; nobody edits them (rule 12).
CREATE TABLE agent_type (                                  -- installation data
    id           uuid PRIMARY KEY,
    code         text NOT NULL UNIQUE CONSTRAINT ck_agent_type_code CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    name         text NOT NULL,
    is_active    boolean NOT NULL DEFAULT true,
    recorded_at  timestamptz NOT NULL
);
CREATE TABLE agent_type_version (                          -- installation data; immutable (trigger below)
    id                 uuid PRIMARY KEY,
    agent_type_code    text NOT NULL REFERENCES agent_type (code),
    version            text NOT NULL CONSTRAINT ck_agent_type_version_version CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),   -- semver
    content_hash       text NOT NULL CONSTRAINT ck_agent_type_version_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    behavior_hash      text NOT NULL CONSTRAINT ck_agent_type_version_behavior_hash CHECK (behavior_hash ~ '^[0-9a-f]{64}$'),   -- content hash without budget maximums (rule 14)
    declaration        jsonb NOT NULL,                     -- steps, tool list (= declared permissions), claimable kinds, scope_kind, subject tables, may_read_untrusted, seats, templates, schemas, budget maximums, evaluation suite (rule 12)
    field_classes      text[] NOT NULL DEFAULT '{}' CONSTRAINT ck_agent_type_version_field_classes CHECK (field_classes <@ ARRAY['cost', 'margin']::text[]),   -- default none; no record scope (rule 12 note, platform review 11); never sensitive_personal (ADR-0079 rule 11)
    recorded_at        timestamptz NOT NULL,
    UNIQUE (agent_type_code, version)
);

-- ===== Work queue [work] (ADR-0042; ADR-0055 rule 12; ADR-0054 rule 11; work cases ADR-0066, proposed) =====
CREATE TABLE work_item (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    kind                     text NOT NULL CONSTRAINT ck_work_item_kind CHECK (kind ~ '^[a-z][a-z0-9_]*$'),   -- work-item-kinds.csv (rule 1)
    subject_table            text NOT NULL,
    subject_id               uuid NOT NULL,
    open_key                 text NOT NULL,                -- default the subject ID; a kind may compose it (rule 4)
    state                    text NOT NULL CONSTRAINT ck_work_item_state CHECK (state IN ('open', 'claimed', 'done', 'canceled')),
    owner_kind               text NOT NULL CONSTRAINT ck_work_item_owner_kind CHECK (owner_kind IN ('user', 'role', 'approval_stage')),
    owner_user_id            uuid REFERENCES user_account (id),
    owner_role               text,                         -- the symbolic rule: a role template code or company_owner; holders resolved at read time (rule 7, platform review 4)
    branch_id                uuid,                         -- record scope of a role owner (rule 2)
    warehouse_id             uuid,
    owner_approval_stage_id  uuid,                         -- ADR-0055 rule 12
    due_date                 date NOT NULL,                -- a business date (rule 8)
    priority                 text NOT NULL DEFAULT 'normal' CONSTRAINT ck_work_item_priority CHECK (priority IN ('low', 'normal', 'high')),
    details                  jsonb NOT NULL DEFAULT '{}' CONSTRAINT ck_work_item_details CHECK (jsonb_typeof(details) = 'object'),   -- IDs and amounts only, never personal free text (rule 2)
    is_tainted               boolean NOT NULL DEFAULT false,   -- OR over the raises (rule 5)
    origin_event_id          uuid,                         -- no key: outbox partitions are dropped after retention (ADR-0013 rule 15)
    origin_agent_run_id      uuid,                         -- kept from the first raise (rule 5); key added after agent_run
    work_case_id             uuid,                         -- set once, kept by a re-raise (ADR-0066 rule 10); key added after work_case
    claimed_by_kind          text CONSTRAINT ck_work_item_claimed_by_kind CHECK (claimed_by_kind IN ('user', 'agent_run')),
    claimed_by_id            uuid,
    claimed_at               timestamptz,
    claim_expires_at         timestamptz,                  -- agent claims only (rule 9)
    resolution               text,
    resolved_at              timestamptz,
    version                  integer NOT NULL CONSTRAINT ck_work_item_version CHECK (version >= 1),
    recorded_at              timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, owner_approval_stage_id) REFERENCES approval_stage (company_id, id),
    CONSTRAINT ck_work_item_owner CHECK (
        (owner_kind = 'user') = (owner_user_id IS NOT NULL)
        AND (owner_kind = 'role') = (owner_role IS NOT NULL)
        AND (owner_kind = 'approval_stage') = (owner_approval_stage_id IS NOT NULL)),
    -- A template code (role:<template> without its prefix, warehouse_role as warehouse_keeper) or company_owner (platform review 4).
    CONSTRAINT ck_work_item_owner_role CHECK (owner_role ~ '^[a-z][a-z0-9_]*$'),
    CONSTRAINT ck_work_item_scope CHECK (owner_kind = 'role' OR (branch_id IS NULL AND warehouse_id IS NULL)),
    CONSTRAINT ck_work_item_claim CHECK (
        (state = 'claimed') = (claimed_by_kind IS NOT NULL)
        AND (claimed_by_kind IS NULL) = (claimed_by_id IS NULL)
        AND (claimed_by_kind IS NULL) = (claimed_at IS NULL)
        AND (claimed_by_kind IS NOT DISTINCT FROM 'agent_run') = (claim_expires_at IS NOT NULL)),
    CONSTRAINT ck_work_item_resolved CHECK ((state IN ('done', 'canceled')) = (resolved_at IS NOT NULL)
        AND (state <> 'done' OR resolution IS NOT NULL))
);
-- Rule 4: one open item per exception.
CREATE UNIQUE INDEX ux_work_item_open_key ON work_item (company_id, kind, open_key) WHERE state IN ('open', 'claimed');
CREATE INDEX ix_work_item_subject ON work_item (company_id, subject_table, subject_id);
CREATE INDEX ix_work_item_owner_user_id ON work_item (owner_user_id) WHERE state IN ('open', 'claimed');
CREATE TABLE work_item_link (                              -- evidence and what was done about it (rule 3)
    id            uuid PRIMARY KEY,
    company_id    uuid NOT NULL,
    work_item_id  uuid NOT NULL,
    target_table  text NOT NULL,
    target_id     uuid NOT NULL,
    link_kind     text NOT NULL CONSTRAINT ck_work_item_link_kind CHECK (link_kind IN ('evidence', 'draft', 'result')),
    recorded_at   timestamptz NOT NULL,
    UNIQUE (work_item_id, target_table, target_id, link_kind),
    FOREIGN KEY (company_id, work_item_id) REFERENCES work_item (company_id, id)
);
CREATE TABLE work_item_note (                              -- append-only (rule 3; trigger below); created_at of rule 3 is recorded_at
    id            uuid PRIMARY KEY,
    company_id    uuid NOT NULL,
    work_item_id  uuid NOT NULL,
    author_kind   text NOT NULL CONSTRAINT ck_work_item_note_author_kind CHECK (author_kind IN ('user', 'agent_run', 'system')),   -- interim: not stated in ADR-0042 (rule 3 says "author")
    author_id     uuid,                                    -- interim: not stated in ADR-0042; a user or an agent run, null for system
    body_text     text NOT NULL,
    is_untrusted  boolean NOT NULL DEFAULT false,          -- an agent's note from outside content (rule 3; ADR-0029 rule 10)
    recorded_at   timestamptz NOT NULL,
    FOREIGN KEY (company_id, work_item_id) REFERENCES work_item (company_id, id),
    CONSTRAINT ck_work_item_note_author CHECK ((author_kind = 'system') = (author_id IS NULL))
);
CREATE INDEX ix_work_item_note_work_item_id ON work_item_note (work_item_id);
CREATE TABLE work_case (                                   -- one business intent; links only, documents stay the source of truth (ADR-0066 rules 1-2)
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    kind              text NOT NULL CONSTRAINT ck_work_case_kind CHECK (kind ~ '^[a-z][a-z0-9_]*$'),   -- work-case-kinds.csv (rule 3)
    open_key          text NOT NULL,                       -- the origin's ID unless the kind composes it (rule 5)
    state             text NOT NULL CONSTRAINT ck_work_case_state CHECK (state IN ('open', 'resolved', 'canceled')),
    owner_kind        text NOT NULL CONSTRAINT ck_work_case_owner_kind CHECK (owner_kind IN ('user', 'role')),
    owner_user_id     uuid REFERENCES user_account (id),
    owner_role        text CONSTRAINT ck_work_case_owner_role CHECK (owner_role ~ '^[a-z][a-z0-9_]*$'),   -- a template code or company_owner, as work_item
    branch_id         uuid,
    warehouse_id      uuid,
    due_date          date NOT NULL,
    priority          text NOT NULL DEFAULT 'normal' CONSTRAINT ck_work_case_priority CHECK (priority IN ('low', 'normal', 'high')),
    title_key         text NOT NULL,                       -- the kind's i18n message; never text from outside content (rule 2)
    title_details     jsonb NOT NULL DEFAULT '{}' CONSTRAINT ck_work_case_title_details CHECK (jsonb_typeof(title_details) = 'object'),   -- IDs, numbers and codes only
    partner_id        uuid,                                -- only from a trusted source: a deterministic match or a person (rule 2)
    origin_table      text,
    origin_id         uuid,
    resolution        text,
    resolved_at       timestamptz,
    cancel_reason     text,
    version           integer NOT NULL CONSTRAINT ck_work_case_version CHECK (version >= 1),
    recorded_at       timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_work_case_owner CHECK (
        (owner_kind = 'user') = (owner_user_id IS NOT NULL)
        AND (owner_kind = 'role') = (owner_role IS NOT NULL)),
    CONSTRAINT ck_work_case_scope CHECK (owner_kind = 'role' OR (branch_id IS NULL AND warehouse_id IS NULL)),
    CONSTRAINT ck_work_case_origin CHECK ((origin_table IS NULL) = (origin_id IS NULL)),
    CONSTRAINT ck_work_case_final CHECK (
        (state IN ('resolved', 'canceled')) = (resolved_at IS NOT NULL)
        AND (state <> 'resolved' OR resolution IS NOT NULL)
        AND (state = 'canceled') = (cancel_reason IS NOT NULL))
);
-- Rule 2: one open case per origin and kind.
CREATE UNIQUE INDEX ux_work_case_open_key ON work_case (company_id, kind, open_key) WHERE state = 'open';
CREATE INDEX ix_work_case_partner_id ON work_case (company_id, partner_id) WHERE state = 'open';
CREATE INDEX ix_work_case_owner_user_id ON work_case (owner_user_id) WHERE state = 'open';
CREATE TABLE work_case_link (                              -- append-only; unlinking sets unlinked_at once (ADR-0066 rule 8)
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL,
    work_case_id     uuid NOT NULL,
    target_table     text NOT NULL,
    target_id        uuid NOT NULL,
    link_kind        text NOT NULL CONSTRAINT ck_work_case_link_kind CHECK (link_kind IN ('origin', 'evidence', 'artifact', 'related')),
    linked_by_kind   text NOT NULL CONSTRAINT ck_work_case_link_linked_by_kind CHECK (linked_by_kind IN ('user', 'system')),
    linked_by_id     uuid,                                 -- the user; null for system (the opener consumer, an automation rule)
    unlinked_at      timestamptz,
    recorded_at      timestamptz NOT NULL,
    FOREIGN KEY (company_id, work_case_id) REFERENCES work_case (company_id, id),
    CONSTRAINT ck_work_case_link_linked_by CHECK ((linked_by_kind = 'system') = (linked_by_id IS NULL))
);
-- One live link per target and kind; an unlinked row may be followed by a new link.
CREATE UNIQUE INDEX ux_work_case_link_live ON work_case_link (work_case_id, target_table, target_id, link_kind) WHERE unlinked_at IS NULL;
CREATE INDEX ix_work_case_link_target ON work_case_link (company_id, target_table, target_id) WHERE unlinked_at IS NULL;
ALTER TABLE work_item ADD CONSTRAINT fk_work_item_work_case_id FOREIGN KEY (company_id, work_case_id) REFERENCES work_case (company_id, id);
CREATE INDEX ix_work_item_work_case_id ON work_item (work_case_id) WHERE work_case_id IS NOT NULL;

-- ===== Agent settings, runs and budgets [agent_runs] (ADR-0050 rules 14, 18-19, 22-23) =====
CREATE TABLE agent_type_setting (                          -- company data, change-tracked (rule 14)
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL REFERENCES company (id),
    agent_type_code       text NOT NULL REFERENCES agent_type (code),
    mode                  text NOT NULL DEFAULT 'off' CONSTRAINT ck_agent_type_setting_mode CHECK (mode IN ('off', 'shadow', 'assisted', 'active')),   -- active: ADR-0065 rule 11
    workflow_owner_id     uuid REFERENCES user_account (id),
    -- budget values are setting_value rows of scope agent_type (rule 14 and 22 notes); no lowered_budget column
    promoted_version      text,
    promoted_seat_models  jsonb,                           -- (seat, model) pairs the evidence covered
    active_document_types text[],                          -- ADR-0065 rule 11: the document types whose drafts may pass the auto-post gateway as tainted drafts
    recorded_at           timestamptz NOT NULL,
    UNIQUE (company_id, agent_type_code),
    FOREIGN KEY (agent_type_code, promoted_version) REFERENCES agent_type_version (agent_type_code, version),
    CONSTRAINT ck_agent_type_setting_owner CHECK (mode = 'off' OR workflow_owner_id IS NOT NULL),
    CONSTRAINT ck_agent_type_setting_promoted CHECK ((promoted_version IS NULL) = (promoted_seat_models IS NULL)
        AND (mode NOT IN ('assisted', 'active') OR promoted_version IS NOT NULL)),
    -- ADR-0065 rule 11: active names at least one document type; no other mode names any.
    CONSTRAINT ck_agent_type_setting_active CHECK ((mode = 'active') = (active_document_types IS NOT NULL)
        AND (active_document_types IS NULL OR cardinality(active_document_types) >= 1))
);
CREATE TABLE agent_run (                                   -- company data, not partitioned (rule 18)
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL REFERENCES company (id),
    agent_type_code        text NOT NULL,
    agent_type_version     text NOT NULL,
    seatmap_hash           text NOT NULL,
    mode                   text NOT NULL CONSTRAINT ck_agent_run_mode CHECK (mode IN ('live', 'shadow', 'replay', 'evaluation')),
    replay_of_run_id       uuid,
    trigger_kind           text NOT NULL CONSTRAINT ck_agent_run_trigger_kind CHECK (trigger_kind IN ('work_item', 'person', 'schedule')),
    work_item_id           uuid,                           -- the item, or the run's own agent_task item (ADR-0042 rule 11)
    subject_table          text,
    subject_id             uuid,
    started_by_kind        text NOT NULL CONSTRAINT ck_agent_run_started_by_kind CHECK (started_by_kind IN ('human', 'system')),
    started_by_id          uuid,
    on_behalf_of_id        uuid NOT NULL REFERENCES user_account (id),   -- the human acted for (rule 15)
    scope_kind             text NOT NULL CONSTRAINT ck_agent_run_scope_kind CHECK (scope_kind IN ('partner', 'import_batch', 'subject')),
    scope_partner_id       uuid,
    scope_import_batch_id  uuid,                           -- key added with the imports module (ADR-0044)
    tainted_at             timestamptz,                    -- set once, never cleared (rule 25; trigger below)
    taint_source_kind      text CONSTRAINT ck_agent_run_taint_source_kind CHECK (taint_source_kind IN ('work_item', 'outside_subject', 'untrusted_field', 'tainted_row', 'outside_attachment')),
    taint_source_table     text,
    taint_source_id        uuid,
    budget                 jsonb NOT NULL,                 -- the limits in force at start
    llm_call_count         integer NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_llm_call_count CHECK (llm_call_count >= 0),
    tool_call_count        integer NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_tool_call_count CHECK (tool_call_count >= 0),
    input_token_count      bigint NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_input_token_count CHECK (input_token_count >= 0),     -- input_tokens of rule 18, named by ADR-0004 rule 13
    output_token_count     bigint NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_output_token_count CHECK (output_token_count >= 0),
    cache_token_count      bigint NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_cache_token_count CHECK (cache_token_count >= 0),
    row_read_count         bigint NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_row_read_count CHECK (row_read_count >= 0),
    denial_count           smallint NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_denial_count CHECK (denial_count BETWEEN 0 AND 3),   -- the third denial stops the run (rule 33)
    cost_amount            types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_cost_amount CHECK (cost_amount >= 0),
    reserved_amount        types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_agent_run_reserved_amount CHECK (reserved_amount >= 0),   -- open reservations (rule 23; INV-212)
    cost_currency          text NOT NULL DEFAULT 'USD' CONSTRAINT ck_agent_run_cost_currency CHECK (cost_currency = 'USD'),
    state                  text NOT NULL CONSTRAINT ck_agent_run_state CHECK (state IN ('queued', 'running', 'completed', 'stopped', 'canceled')),
    outcome                text,
    started_at             timestamptz NOT NULL,
    ended_at               timestamptz,
    duration_ms            bigint,
    input_refs             jsonb NOT NULL DEFAULT '[]',    -- typed references: table, ID, role
    output_refs            jsonb NOT NULL DEFAULT '[]',
    trace_id               text,
    recorded_at            timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (agent_type_code, agent_type_version) REFERENCES agent_type_version (agent_type_code, version),
    FOREIGN KEY (company_id, replay_of_run_id) REFERENCES agent_run (company_id, id),
    FOREIGN KEY (company_id, work_item_id) REFERENCES work_item (company_id, id),
    FOREIGN KEY (company_id, scope_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_agent_run_replay CHECK (mode <> 'replay' OR replay_of_run_id IS NOT NULL),
    CONSTRAINT ck_agent_run_work_item CHECK (mode NOT IN ('live', 'shadow') OR work_item_id IS NOT NULL),
    CONSTRAINT ck_agent_run_subject CHECK ((subject_table IS NULL) = (subject_id IS NULL)),
    CONSTRAINT ck_agent_run_scope CHECK ((scope_kind = 'partner') = (scope_partner_id IS NOT NULL)
        AND (scope_kind = 'import_batch') = (scope_import_batch_id IS NOT NULL)),
    CONSTRAINT ck_agent_run_taint CHECK ((tainted_at IS NULL) = (taint_source_kind IS NULL)),
    -- Rule 17's table of outcomes by state.
    CONSTRAINT ck_agent_run_outcome CHECK (CASE state
        WHEN 'completed' THEN outcome IN ('drafted', 'no_action', 'not_applicable', 'routing_blocked',
                                          'answered', 'ambiguous_term', 'ambiguous_member', 'out_of_coverage', 'not_permitted',
                                          'data_not_ready', 'too_broad')   -- the analysis outcomes (ADR-0060 rule 24)
        WHEN 'stopped' THEN outcome IN ('claim_lost', 'budget_exceeded', 'time_exceeded', 'output_invalid', 'provider_unavailable',
                                        'resume_diverged', 'crashed', 'denials_repeated')
        WHEN 'canceled' THEN outcome = 'canceled'
        ELSE outcome IS NULL END),
    CONSTRAINT ck_agent_run_ended CHECK ((state IN ('completed', 'stopped', 'canceled')) = (ended_at IS NOT NULL)),
    -- Rule 23 and INV-212: totals never exceed the start snapshot; an ended run holds no reservation.
    CONSTRAINT ck_agent_run_within_budget CHECK (
        llm_call_count <= COALESCE((budget ->> 'max_llm_calls')::integer, llm_call_count)
        AND tool_call_count <= COALESCE((budget ->> 'max_tool_calls')::integer, tool_call_count)
        AND row_read_count <= COALESCE((budget ->> 'max_rows_read')::bigint, row_read_count)
        AND cost_amount + reserved_amount <= COALESCE((budget ->> 'max_cost')::numeric, cost_amount + reserved_amount)),
    CONSTRAINT ck_agent_run_reservation_settled CHECK (state IN ('queued', 'running') OR reserved_amount = 0)
);
CREATE INDEX ix_agent_run_work_item_id ON agent_run (work_item_id);
CREATE INDEX ix_agent_run_company_id_agent_type_code ON agent_run (company_id, agent_type_code, started_at);
-- Rule 19: append-only, partitioned by month on id (partitions in the last section). A request row is committed before
-- its call, the response or result row after it.
CREATE TABLE agent_run_step (
    id                      uuid NOT NULL,
    company_id              uuid NOT NULL,
    agent_run_id            uuid NOT NULL,
    ordinal                 integer NOT NULL CONSTRAINT ck_agent_run_step_ordinal CHECK (ordinal >= 1),
    step_code               text NOT NULL,
    kind                    text NOT NULL CONSTRAINT ck_agent_run_step_kind CHECK (kind IN ('llm_request', 'llm_response', 'tool_request', 'tool_result')),
    request_step_id         uuid,
    attempt                 smallint NOT NULL DEFAULT 1 CONSTRAINT ck_agent_run_step_attempt CHECK (attempt >= 1),
    duration_ms             bigint,
    seat                    text,
    provider                text,
    model                   text,
    template_code           text,
    template_version        text,
    template_hash           text,
    output_schema_version   text,
    request_hash            text CONSTRAINT ck_agent_run_step_request_hash CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    reserved_amount         types.amount,                  -- the worst case reserved before the call (rule 23)
    request_body            jsonb,                         -- as sent, after redaction; blanked by erasure (rule 20)
    response_body           jsonb,
    context_refs            jsonb,
    validation_errors       jsonb,
    input_token_count       bigint,
    output_token_count      bigint,
    cache_read_token_count  bigint,
    cache_write_token_count bigint,
    cost_amount             types.amount,
    personal_fields_sent    jsonb,
    redacted_fields         jsonb,
    personal_subject_refs   jsonb,
    tool_name               text,
    schema_version          integer,
    mode                    text CONSTRAINT ck_agent_run_step_mode CHECK (mode IN ('simulate', 'execute', 'query')),
    request_refs            jsonb,
    result_refs             jsonb,
    error_code              text,
    plan_hash               text,
    audit_record_id         uuid,                          -- no key: audit_record is created later in the file and partitioned; checked by INV-211's query
    erased_at               timestamptz,                   -- interim: not stated in ADR-0050 (rule 20 blanks the bodies; this records when)
    recorded_at             timestamptz NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id, agent_run_id) REFERENCES agent_run (company_id, id),
    CONSTRAINT ck_agent_run_step_pairing CHECK ((kind IN ('llm_request', 'tool_request')) = (request_step_id IS NULL)),
    CONSTRAINT ck_agent_run_step_llm CHECK (kind NOT IN ('llm_request', 'llm_response')
        OR (seat IS NOT NULL AND provider IS NOT NULL AND model IS NOT NULL AND tool_name IS NULL)),
    CONSTRAINT ck_agent_run_step_tool CHECK (kind NOT IN ('tool_request', 'tool_result') OR (tool_name IS NOT NULL AND seat IS NULL)),
    CONSTRAINT ck_agent_run_step_bodies CHECK ((request_body IS NULL OR kind = 'llm_request') AND (response_body IS NULL OR kind = 'llm_response')),
    CONSTRAINT ck_agent_run_step_reservation CHECK ((kind = 'llm_request') = (reserved_amount IS NOT NULL) OR erased_at IS NOT NULL)
) PARTITION BY RANGE (id);
-- Rule 23: one row per (company, agent type, business date), (company, business date), (company, outside-content pool,
-- business date; rule 23 note) and (installation, day). Each
-- reservation is one guarded UPDATE; the check below is the guard, so a failed reservation reserves nothing.
CREATE TABLE agent_budget_usage (
    id               uuid PRIMARY KEY,
    scope_kind       text NOT NULL CONSTRAINT ck_agent_budget_usage_scope_kind CHECK (scope_kind IN ('company_agent_type', 'company', 'company_outside_content', 'installation')),
    company_id       uuid REFERENCES company (id),
    agent_type_code  text REFERENCES agent_type (code),
    business_date    date NOT NULL,                        -- the company's business date; the installation row uses the UTC day (rule 22)
    limit_amount     types.amount NOT NULL CONSTRAINT ck_agent_budget_usage_limit CHECK (limit_amount >= 0),
    reserved_amount  types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_agent_budget_usage_reserved CHECK (reserved_amount >= 0),
    spent_amount     types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_agent_budget_usage_spent CHECK (spent_amount >= 0),
    run_count        integer NOT NULL DEFAULT 0 CONSTRAINT ck_agent_budget_usage_run_count CHECK (run_count >= 0),
    run_limit_count  integer,                              -- a run count limit; Phase 1 sets none (ADR-0078 rule 7)
    currency         text NOT NULL DEFAULT 'USD' CONSTRAINT ck_agent_budget_usage_currency CHECK (currency = 'USD'),
    recorded_at      timestamptz NOT NULL,
    CONSTRAINT uq_agent_budget_usage_key UNIQUE NULLS NOT DISTINCT (scope_kind, company_id, agent_type_code, business_date),
    CONSTRAINT ck_agent_budget_usage_scope CHECK (
        (scope_kind = 'installation') = (company_id IS NULL)
        AND (scope_kind = 'company_agent_type') = (agent_type_code IS NOT NULL)
        AND (run_limit_count IS NULL OR scope_kind = 'company_agent_type')),
    CONSTRAINT ck_agent_budget_usage_guard CHECK (reserved_amount + spent_amount <= limit_amount
        AND (run_limit_count IS NULL OR run_count <= run_limit_count))
);

-- ===== Policy rules and procedures [policy] (ADR-0043 rules 1-3, 18; ADR-0055 rule 5) =====
CREATE TABLE approval_procedure (                          -- named ranks; approver role and scope binding moved to stages (ADR-0055 rule 5)
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    code         text NOT NULL,
    name         text NOT NULL,
    rank         integer NOT NULL CONSTRAINT ck_approval_procedure_rank CHECK (rank > 0),
    basis        jsonb NOT NULL,                           -- interim: not stated in ADR-0043; seeded rows keep their template basis as DS-20 does
    is_active    boolean NOT NULL DEFAULT true,
    recorded_at  timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, rank),
    UNIQUE (company_id, id)
);
CREATE TABLE policy_rule (                                 -- the identity of a versioned rule; ties go to the lowest ID (rule 7)
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    code         text NOT NULL,                            -- interim: not stated in ADR-0043
    recorded_at  timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
-- Rule 3: a change writes a new version with effective_from; a new version of a rule that loosens starts disabled.
-- interim: not stated in ADR-0043 as a table (rule 3 says the rule is versioned and decisions record the version used).
CREATE TABLE policy_rule_version (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    policy_rule_id          uuid NOT NULL,
    version                 integer NOT NULL CONSTRAINT ck_policy_rule_version_version CHECK (version >= 1),
    effective_from          date NOT NULL,
    action                  text NOT NULL CONSTRAINT ck_policy_rule_version_action CHECK (action IN ('submit', 'post', 'issue', 'direct_master_data_change')),
    document_type           text,                          -- empty for all
    command_type            text,                          -- direct_master_data_change only (rule 12)
    actor_kind              text CONSTRAINT ck_policy_rule_version_actor_kind CHECK (actor_kind IN ('human', 'agent', 'integration', 'system')),   -- empty for all
    amount_company_min      types.amount CONSTRAINT ck_policy_rule_version_amount_min CHECK (amount_company_min >= 0),
    amount_company_max      types.amount,
    discount_percent_min    types.percent CONSTRAINT ck_policy_rule_version_discount CHECK (discount_percent_min BETWEEN 0 AND 100),
    margin_percent_max      types.percent,
    -- Boolean conditions: true matches only true, so they are null or true (rule 3).
    is_price_below_cost     boolean CONSTRAINT ck_policy_rule_version_price_below_cost CHECK (is_price_below_cost),
    is_price_outside_list   boolean CONSTRAINT ck_policy_rule_version_price_outside_list CHECK (is_price_outside_list),
    is_credit_exceeded      boolean CONSTRAINT ck_policy_rule_version_credit_exceeded CHECK (is_credit_exceeded),
    is_match_exceeded       boolean CONSTRAINT ck_policy_rule_version_match_exceeded CHECK (is_match_exceeded),        -- ADR-0047 rule 14
    is_direct_expense       boolean CONSTRAINT ck_policy_rule_version_direct_expense CHECK (is_direct_expense),        -- ADR-0048 rule 3
    is_bank_account_recent  boolean CONSTRAINT ck_policy_rule_version_bank_account_recent CHECK (is_bank_account_recent),
    is_rate_unusual         boolean CONSTRAINT ck_policy_rule_version_rate_unusual CHECK (is_rate_unusual),            -- ADR-0048 rule 12
    is_cost_unknown         boolean CONSTRAINT ck_policy_rule_version_cost_unknown CHECK (is_cost_unknown),            -- interim: not stated in ADR-0043 (ADR-0046 rule 14's unknown cost; commercial review S18)
    effect                  text NOT NULL CONSTRAINT ck_policy_rule_version_effect CHECK (effect IN ('deny', 'require_approval', 'require_human_post', 'allow')),
    approval_procedure_id   uuid,
    is_confirmation_required boolean NOT NULL DEFAULT false,
    owner_user_id           uuid REFERENCES user_account (id),
    is_enabled              boolean NOT NULL DEFAULT false,
    shadow_evidence         jsonb,                         -- stored on the rule version by EnablePolicyRule (rule 14)
    -- ADR-0059 rule 6: the demotion, rollback, invalidation or failed re-evaluation of the cascade's parameter set that made the
    -- stored evidence outdated, set once in that transaction; no key: the configuration file is loaded after this one.
    -- ADR-0063 rules 3 and 10: also the setting_value row of a loosening that outdates auto-post evidence, or the audit record
    -- of a reversal or wrong confirmation of a system posting.
    shadow_evidence_outdated_by uuid CONSTRAINT ck_policy_rule_version_outdated CHECK (shadow_evidence_outdated_by IS NULL OR shadow_evidence IS NOT NULL),
    -- ADR-0063 rule 3 and ADR-0043 rule 14, notes of the final simulation review: the registered keys (outdates auto_post)
    -- the evidence was judged under, set once with shadow_evidence by EnablePolicyRule, which keeps their values in
    -- shadow_evidence.settings. The executing transaction of a loosening of key k marks exactly the dependent evidence:
    --   UPDATE policy_rule_version SET shadow_evidence_outdated_by = <the setting_value row> WHERE company_id = <company>
    --      AND is_enabled AND shadow_evidence_outdated_by IS NULL AND k = ANY (evidence_setting_keys)
    evidence_setting_keys   text[] CONSTRAINT ck_policy_rule_version_evidence_settings CHECK ((evidence_setting_keys IS NULL) = (shadow_evidence IS NULL)
        AND (evidence_setting_keys IS NULL OR cardinality(evidence_setting_keys) >= 1)),
    recorded_at             timestamptz NOT NULL,
    UNIQUE (policy_rule_id, version),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, policy_rule_id) REFERENCES policy_rule (company_id, id),
    FOREIGN KEY (company_id, approval_procedure_id) REFERENCES approval_procedure (company_id, id),
    CONSTRAINT ck_policy_rule_version_amount_range CHECK (amount_company_max IS NULL OR amount_company_max > COALESCE(amount_company_min, 0)),
    CONSTRAINT ck_policy_rule_version_procedure CHECK ((effect = 'require_approval') = (approval_procedure_id IS NOT NULL)),
    CONSTRAINT ck_policy_rule_version_confirmation CHECK (NOT is_confirmation_required OR effect = 'allow'),
    -- Rule 12: direct_master_data_change names a command type and only denies, for humans.
    CONSTRAINT ck_policy_rule_version_direct_change CHECK (CASE WHEN action = 'direct_master_data_change'
        THEN command_type IS NOT NULL AND document_type IS NULL AND effect = 'deny' AND actor_kind IS NOT DISTINCT FROM 'human'
        ELSE command_type IS NULL END),
    -- Rule 3: a rule that allows a non-human actor needs an owner and a maximum, and confirmation at post and issue.
    CONSTRAINT ck_policy_rule_version_loosening CHECK (effect <> 'allow' OR actor_kind IS NOT DISTINCT FROM 'human'
        OR (owner_user_id IS NOT NULL AND amount_company_max IS NOT NULL
            AND (action NOT IN ('post', 'issue') OR is_confirmation_required)))
);
CREATE INDEX ix_policy_rule_version_evidence_setting_keys ON policy_rule_version USING gin (evidence_setting_keys) WHERE shadow_evidence_outdated_by IS NULL;

-- ===== Documents [documents] (ADR-0009; ADR-0028; ADR-0030 rule 11; ADR-0052 rule 18; ADR-0054 rule 14) =====
CREATE TABLE numbering_configuration (                     -- per document type: prefix, per-branch series, format (ADR-0009 rule 15)
    id             uuid PRIMARY KEY,                       -- interim: not stated in ADR-0009 as a table (rule 15 says "a company configures")
    company_id     uuid NOT NULL REFERENCES company (id),
    document_type  text NOT NULL,
    prefix         text NOT NULL,
    is_per_branch  boolean NOT NULL DEFAULT false,
    format         text NOT NULL CONSTRAINT ck_numbering_configuration_format CHECK (format LIKE '%{counter:%}%'),   -- placeholders of rule 15
    recorded_at    timestamptz NOT NULL,
    UNIQUE (company_id, document_type)
);
CREATE TABLE numbering_series (                            -- created on first use; the counter moves only through the numbering lock helper (rule 15)
    id              uuid PRIMARY KEY,
    company_id      uuid NOT NULL REFERENCES company (id),
    document_type   text NOT NULL,
    fiscal_year_id  uuid NOT NULL REFERENCES fiscal_year (id),
    branch_id       uuid,
    prefix          text NOT NULL,
    next_value      bigint NOT NULL CONSTRAINT ck_numbering_series_next_value CHECK (next_value >= 1),
    format          text NOT NULL,
    recorded_at     timestamptz NOT NULL,
    CONSTRAINT uq_numbering_series_key UNIQUE NULLS NOT DISTINCT (company_id, document_type, fiscal_year_id, branch_id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id)
);
CREATE TABLE document (
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL REFERENCES company (id),
    document_type         text NOT NULL CONSTRAINT ck_document_document_type CHECK (document_type ~ '^[a-z][a-z0-9_]*$'),
    state                 text NOT NULL CONSTRAINT ck_document_state CHECK (state IN (
                              'draft', 'pending_approval', 'approved', 'issuing', 'sending', 'posted', 'reversed', 'closed', 'canceled')),
    version               integer NOT NULL CONSTRAINT ck_document_version CHECK (version >= 1),   -- the version in force (ADR-0028 rule 4)
    number                text,                            -- null until numbered (rules 8, 13)
    is_barcoded           boolean NOT NULL DEFAULT false,  -- from the type's registry flag at Create, never changed; numbered: the number is a barcode (ADR-0061 rule 9)
    branch_id             uuid,
    reversal_of_id        uuid,
    correction_of_id      uuid,                            -- set at Create, never changed (rule 23)
    partner_id            uuid,                            -- equal to the header (ADR-0052 rule 18)
    document_date         date,
    owner_employee_id     uuid,                            -- an employee partner (ADR-0054 rule 14)
    created_by_user_id    uuid NOT NULL REFERENCES user_account (id),
    origin_work_item_id   uuid,                            -- agent drafts (ADR-0030 rule 11); key added below
    workflow_step         text,
    draft_ordinal         integer,
    pending_version       integer,                         -- ADR-0028 rule 4
    change_state          text NOT NULL DEFAULT 'none' CONSTRAINT ck_document_change_state CHECK (change_state IN ('none', 'drafting', 'pending_approval')),
    posted_at             timestamptz,                     -- rule 13
    closed_reason         text CONSTRAINT ck_document_closed_reason CHECK (closed_reason IN ('fulfilled', 'manual')),   -- ADR-0047 rule 2; interim: value manual not stated in ADR-0047
    canceled_reason_id    uuid,                            -- reason, kind cancel; a person's reason for a canceled draft or pending document (ADR-0074 rules 13, 14)
    canceled_reason_kind  text NOT NULL DEFAULT 'cancel' CONSTRAINT ck_document_canceled_reason_kind CHECK (canceled_reason_kind = 'cancel'),
    canceled_note         text,
    FOREIGN KEY (company_id, canceled_reason_id, canceled_reason_kind) REFERENCES reason (company_id, id, kind),
    CONSTRAINT ck_document_canceled CHECK ((canceled_reason_id IS NULL AND canceled_note IS NULL) OR state = 'canceled'),
    recorded_at           timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, document_type),
    CONSTRAINT uq_document_company_id_document_type_number UNIQUE (company_id, document_type, number),
    CONSTRAINT uq_document_reversal_of_id UNIQUE (reversal_of_id),   -- reversed at most once, in full (rule 18)
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, owner_employee_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, reversal_of_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, correction_of_id) REFERENCES document (company_id, id),
    CONSTRAINT ck_document_not_own_original CHECK (reversal_of_id IS DISTINCT FROM id AND correction_of_id IS DISTINCT FROM id),
    CONSTRAINT ck_document_reversal_or_correction CHECK (reversal_of_id IS NULL OR correction_of_id IS NULL),
    -- INV-43.
    CONSTRAINT ck_document_pending_version CHECK ((pending_version IS NULL) = (change_state = 'none')
        AND (pending_version IS NULL OR pending_version > version)),
    -- INV-44: a document in issuing has no number (nor journal entry or open item, checked by the invariant).
    CONSTRAINT ck_document_issuing_number CHECK (state <> 'issuing' OR number IS NULL),
    CONSTRAINT ck_document_posted_at CHECK ((state IN ('posted', 'reversed')) = (posted_at IS NOT NULL)),
    CONSTRAINT ck_document_closed CHECK (closed_reason IS NULL OR state = 'closed'),
    CONSTRAINT ck_document_draft_key CHECK ((origin_work_item_id IS NULL) = (workflow_step IS NULL)
        AND (origin_work_item_id IS NULL) = (draft_ordinal IS NULL))
);
-- ADR-0030 rule 11: agent drafts are unique per work item, step and ordinal among documents not canceled.
CREATE UNIQUE INDEX ux_document_draft_key ON document (company_id, document_type, origin_work_item_id, workflow_step, draft_ordinal)
    WHERE origin_work_item_id IS NOT NULL AND state <> 'canceled';
CREATE INDEX ix_document_company_id_partner_id ON document (company_id, partner_id) WHERE partner_id IS NOT NULL;
CREATE INDEX ix_document_correction_of_id ON document (correction_of_id) WHERE correction_of_id IS NOT NULL;
CREATE INDEX ix_document_company_id_state ON document (company_id, document_type, state);
-- Rule 9: one row per version, never updated; deleted only with its draft (trigger below).
CREATE TABLE document_version (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    document_id              uuid NOT NULL,
    version                  integer NOT NULL CONSTRAINT ck_document_version_version CHECK (version >= 1),
    content                  jsonb NOT NULL,               -- canonical JSON without IDs, state, version, number, timestamps
    version_hash             text NOT NULL CONSTRAINT ck_document_version_version_hash CHECK (version_hash ~ '^[0-9a-f]{64}$'),
    actor_kind               text NOT NULL CONSTRAINT ck_document_version_actor_kind CHECK (actor_kind IN ('human', 'agent', 'integration', 'system')),
    actor_id                 uuid NOT NULL,
    on_behalf_of_id          uuid REFERENCES user_account (id),
    agent_run_id             uuid,
    origin_agent_run_id      uuid,
    is_tainted               boolean NOT NULL,             -- set at insert, never changed (ADR-0029 rule 8; trigger below holds INV-88)
    derived_from_version_id  uuid,                         -- the version in force for a change, or the source version of version 1
    erased_at                timestamptz,                  -- set by the destruction path of ADR-0079 rule 6; version_hash is then no longer compared with content (INV-10)
    recorded_at              timestamptz NOT NULL,
    UNIQUE (document_id, version),
    UNIQUE (company_id, id),
    UNIQUE (company_id, document_id, id),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, agent_run_id) REFERENCES agent_run (company_id, id),
    FOREIGN KEY (company_id, origin_agent_run_id) REFERENCES agent_run (company_id, id),
    FOREIGN KEY (company_id, derived_from_version_id) REFERENCES document_version (company_id, id),
    CONSTRAINT ck_document_version_derived CHECK (derived_from_version_id IS DISTINCT FROM id),
    CONSTRAINT ck_document_version_agent CHECK ((actor_kind = 'agent') = (agent_run_id IS NOT NULL))
);
CREATE TABLE taint_clearance (                             -- immutable; one per version (ADR-0029 rule 8)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    document_version_id uuid NOT NULL,
    cleared_by_user_id  uuid NOT NULL REFERENCES user_account (id),   -- a human (ClearTaint is human_only)
    reason              text NOT NULL CONSTRAINT ck_taint_clearance_reason CHECK (length(reason) > 0),
    cleared_at          timestamptz NOT NULL,
    recorded_at         timestamptz NOT NULL,
    CONSTRAINT uq_taint_clearance_document_version_id UNIQUE (document_version_id),   -- interim: not stated in ADR-0029 (one clearance per version)
    FOREIGN KEY (company_id, document_version_id) REFERENCES document_version (company_id, id)
);

-- ===== Policy decisions and approvals [policy, documents] (ADR-0029 rules 6-7, 13; ADR-0043 rules 7-8, 13-14;
-- ADR-0055 rules 6, 9; ADR-0028 rule 14) =====
CREATE TABLE policy_decision (                             -- never updated or deleted (ADR-0009 rule 14)
    id                            uuid PRIMARY KEY,
    company_id                    uuid NOT NULL,
    document_id                   uuid NOT NULL,           -- interim: not stated in ADR-0029 (rule 7 binds to the version; the document is kept for lookup)
    document_version_id           uuid NOT NULL,
    action                        text NOT NULL CONSTRAINT ck_policy_decision_action CHECK (action IN ('submit', 'post', 'issue')),
    actor_kind                    text NOT NULL CONSTRAINT ck_policy_decision_actor_kind CHECK (actor_kind IN ('human', 'agent', 'integration', 'system')),   -- interim: not stated in ADR-0043 (the actor evaluated, rule 5)
    actor_id                      uuid NOT NULL,           -- interim: not stated in ADR-0043
    on_behalf_of_id               uuid REFERENCES user_account (id),   -- interim: not stated in ADR-0043
    outcome                       text NOT NULL CONSTRAINT ck_policy_decision_outcome CHECK (outcome IN ('allowed', 'approval_required', 'human_only', 'denied')),
    policy_rule_id                uuid,                    -- the rule that set the rank, else human post, else confirmation (rule 7)
    policy_rule_version           integer,
    matching_rules                jsonb NOT NULL DEFAULT '[]' CONSTRAINT ck_policy_decision_matching_rules CHECK (jsonb_typeof(matching_rules) = 'array'),   -- every matching rule ID and version
    is_confirmation_required      boolean NOT NULL DEFAULT false,
    approval_procedure_id         uuid,
    required_rank                 integer,
    human_post                    boolean NOT NULL DEFAULT false,
    policy_input_hash             text NOT NULL CONSTRAINT ck_policy_decision_policy_input_hash CHECK (policy_input_hash ~ '^[0-9a-f]{64}$'),
    policy_input                  jsonb,                   -- interim: not stated in ADR-0043 (approval_context_changed details give the approved amounts, ADR-0028 rule 14)
    approval_pool_id              uuid,                    -- ADR-0055 rule 6
    approval_plan                 jsonb,                   -- required stages as in force on clock.today: id, sequence, code, min_rank, k, scope_binding, escalation_role_id, due_days
    continues_policy_decision_id  uuid,                    -- a resubmission that continues the round (ADR-0055 rule 11)
    -- ADR-0065 rule 6: the auto-post gateway's decision and the checker's evidence; all null for other decisions.
    auto_post_decision            text CONSTRAINT ck_policy_decision_auto_post_decision CHECK (auto_post_decision IN ('auto_post', 'require_human', 'reject')),
    auto_post_mode                text CONSTRAINT ck_policy_decision_auto_post_mode CHECK (auto_post_mode IN ('shadow', 'live')),
    auto_post_reason_code         text,                    -- the first failed rule in the gateway's order; null for auto_post
    auto_post_checker_code        text,                    -- the registry declaration of the checker (ADR-0065 rule 2)
    auto_post_checker_version     text,
    auto_post_plan_hash           text CONSTRAINT ck_policy_decision_auto_post_plan_hash CHECK (auto_post_plan_hash ~ '^[0-9a-f]{64}$'),   -- the simulated plan; the posting must reproduce it
    auto_post_as_of_date          date,                    -- the simulated business date the execution is pinned to
    auto_post_evidence            jsonb,                   -- settings read (key, value, source), decision table and parameter set versions with hashes, every rule's code,
                                                           -- outcome and values, value bases, taint, drafting run, agent type, behavior hash, effective mode, rule version
    decided_at                    timestamptz NOT NULL,
    recorded_at                   timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, document_version_id),
    UNIQUE (company_id, id, approval_pool_id),
    FOREIGN KEY (company_id, document_id, document_version_id) REFERENCES document_version (company_id, document_id, id),
    FOREIGN KEY (company_id, policy_rule_id) REFERENCES policy_rule (company_id, id),
    FOREIGN KEY (policy_rule_id, policy_rule_version) REFERENCES policy_rule_version (policy_rule_id, version),
    FOREIGN KEY (company_id, approval_procedure_id) REFERENCES approval_procedure (company_id, id),
    FOREIGN KEY (company_id, approval_pool_id) REFERENCES approval_pool (company_id, id),
    FOREIGN KEY (company_id, continues_policy_decision_id) REFERENCES policy_decision (company_id, id),
    -- ADR-0043 rule 8: the stored outcome follows the two dimensions.
    CONSTRAINT ck_policy_decision_rank CHECK ((outcome = 'approval_required') = (required_rank IS NOT NULL)
        AND (required_rank IS NULL) = (approval_procedure_id IS NULL)),
    CONSTRAINT ck_policy_decision_human_post CHECK ((outcome <> 'human_only' OR human_post) AND (outcome <> 'allowed' OR NOT human_post)),
    CONSTRAINT ck_policy_decision_confirmation CHECK (NOT is_confirmation_required OR outcome = 'allowed'),
    CONSTRAINT ck_policy_decision_rule_version CHECK ((policy_rule_id IS NULL) = (policy_rule_version IS NULL)),
    -- INV-230 and ADR-0055 rule 5: a rank always has a pool and a non-empty plan; no rank, no plan.
    CONSTRAINT ck_policy_decision_plan CHECK (CASE WHEN required_rank IS NULL
        THEN approval_pool_id IS NULL AND approval_plan IS NULL AND continues_policy_decision_id IS NULL
        ELSE approval_pool_id IS NOT NULL
             AND CASE WHEN jsonb_typeof(approval_plan) = 'array' THEN jsonb_array_length(approval_plan) > 0 ELSE false END END),
    CONSTRAINT ck_policy_decision_continues CHECK (continues_policy_decision_id IS DISTINCT FROM id),
    -- ADR-0065 rules 4 and 6: the gateway's columns come together, only for a post or issue by system or integration; a live auto_post is
    -- allowed with confirmation, a live require_human human_only, a live reject denied, and a shadow decision human_only.
    CONSTRAINT ck_policy_decision_auto_post CHECK (
        (auto_post_decision IS NULL) = (auto_post_mode IS NULL)
        AND (auto_post_decision IS NULL) = (auto_post_checker_code IS NULL)
        AND (auto_post_decision IS NULL) = (auto_post_checker_version IS NULL)
        AND (auto_post_decision IS NULL) = (auto_post_evidence IS NULL)
        AND (auto_post_decision IS NULL OR (action IN ('post', 'issue') AND actor_kind IN ('system', 'integration')))
        AND (auto_post_decision IS NULL OR (auto_post_decision = 'auto_post') = (auto_post_reason_code IS NULL))
        AND (auto_post_decision IS DISTINCT FROM 'auto_post' OR (auto_post_plan_hash IS NOT NULL AND auto_post_as_of_date IS NOT NULL))
        AND (auto_post_mode IS DISTINCT FROM 'shadow' OR outcome = 'human_only')
        AND (auto_post_mode IS DISTINCT FROM 'live' OR CASE auto_post_decision
                WHEN 'auto_post' THEN outcome = 'allowed' AND is_confirmation_required
                WHEN 'require_human' THEN outcome = 'human_only'
                ELSE outcome = 'denied' END))
);
CREATE INDEX ix_policy_decision_document_version_id ON policy_decision (document_version_id);
CREATE TABLE approval (                                    -- owned by documents; one immutable row per decision at a stage (ADR-0055 rule 1)
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    document_id             uuid NOT NULL,                 -- interim: not stated in ADR-0009 (rule 11 binds to the version)
    document_version_id     uuid NOT NULL,
    policy_decision_id      uuid NOT NULL,                 -- the decision it satisfies (ADR-0028 rule 14)
    decision                text NOT NULL CONSTRAINT ck_approval_decision CHECK (decision IN ('approved', 'rejected')),
    reason                  text NOT NULL CONSTRAINT ck_approval_reason CHECK (length(reason) > 0),   -- required, the comment (ADR-0055 rule 9)
    actor_kind              text NOT NULL CONSTRAINT ck_approval_actor_kind CHECK (actor_kind = 'human'),   -- agents never approve (ADR-0017 rule 15)
    actor_id                uuid NOT NULL REFERENCES user_account (id),
    on_behalf_of_id         uuid REFERENCES user_account (id),
    approval_stage_id       uuid,
    approval_pool_id        uuid,
    delegated_from_user_id  uuid REFERENCES user_account (id),
    is_escalated            boolean NOT NULL DEFAULT false,
    decided_at              timestamptz NOT NULL,
    reject_reason_id        uuid,                          -- reason, kind reject; the comment above stays required (ADR-0074 rules 13, 14)
    reject_reason_kind      text NOT NULL DEFAULT 'reject' CONSTRAINT ck_approval_reject_reason_kind CHECK (reject_reason_kind = 'reject'),
    FOREIGN KEY (company_id, reject_reason_id, reject_reason_kind) REFERENCES reason (company_id, id, kind),
    CONSTRAINT ck_approval_reject_reason CHECK (reject_reason_id IS NULL OR decision = 'rejected'),
    recorded_at             timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, document_id, document_version_id) REFERENCES document_version (company_id, document_id, id),
    FOREIGN KEY (company_id, policy_decision_id, document_version_id) REFERENCES policy_decision (company_id, id, document_version_id),
    FOREIGN KEY (company_id, policy_decision_id, approval_pool_id) REFERENCES policy_decision (company_id, id, approval_pool_id),
    CONSTRAINT ck_approval_stage CHECK ((approval_stage_id IS NULL) = (approval_pool_id IS NULL)),
    CONSTRAINT ck_approval_delegated CHECK (delegated_from_user_id IS DISTINCT FROM actor_id),
    -- ADR-0055 rule 7: escalation is used only when no delegation applies.
    CONSTRAINT ck_approval_escalated CHECK (NOT (is_escalated AND delegated_from_user_id IS NOT NULL))
);
-- ADR-0055 rule 7 condition 6, within one decision: a person counts once.
CREATE UNIQUE INDEX ux_approval_policy_decision_id_actor_id ON approval (policy_decision_id, actor_id) WHERE decision = 'approved';
CREATE INDEX ix_approval_document_version_id ON approval (document_version_id);
CREATE TABLE auto_post_confirmation (                      -- immutable (ADR-0029 rule 13; ADR-0043 rule 14)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    policy_decision_id  uuid NOT NULL,
    confirmed_by_id     uuid NOT NULL REFERENCES user_account (id),   -- the owner of the rule's latest version (command check)
    confirmed_at        timestamptz NOT NULL,
    recorded_at         timestamptz NOT NULL,
    CONSTRAINT uq_auto_post_confirmation_policy_decision_id UNIQUE (policy_decision_id),
    FOREIGN KEY (company_id, policy_decision_id) REFERENCES policy_decision (company_id, id)
);
CREATE TABLE period_unlock_request (                       -- typed header of a non-posting document type (ADR-0043 rule 16)
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    posting_period_id  uuid NOT NULL REFERENCES posting_period (id),
    area               text NOT NULL CONSTRAINT ck_period_unlock_request_area CHECK (area IN ('general', 'inventory', 'receivable', 'payable')),
    reason             text NOT NULL,
    recorded_at        timestamptz NOT NULL,
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id)
);

-- ===== Posting intents [documents] (ADR-0028 rules 6-7, 10-11) =====
-- One per Issue attempt, never reused; the frozen plan, rates and hash are immutable (trigger below).
CREATE TABLE posting_intent (
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    document_id            uuid NOT NULL,
    document_version_id    uuid NOT NULL,                  -- interim: not stated in ADR-0028 (the version issued)
    policy_decision_id     uuid,                           -- the decision taken at Issue
    state                  text NOT NULL CONSTRAINT ck_posting_intent_state CHECK (state IN ('pending', 'posted', 'reopened', 'recalled')),
    posting_date           date NOT NULL,                  -- frozen at Issue; equal to the content's
    plan                   jsonb NOT NULL,                 -- the prospective journal and open items
    plan_hash              text NOT NULL CONSTRAINT ck_posting_intent_plan_hash CHECK (plan_hash ~ '^[0-9a-f]{64}$'),   -- expected_plan_hash of the completing Post
    rates                  jsonb NOT NULL,                 -- the rates resolved at Issue (ADR-0011 rule 1)
    is_e_invoice_required  boolean NOT NULL,               -- INV-46
    e_invoice_record_id    uuid,                           -- tax's record (DS-24 add-on); no key until its DDL exists
    issued_at              timestamptz NOT NULL,           -- interim: not stated in ADR-0028
    ended_at               timestamptz,                    -- interim: not stated in ADR-0028
    recorded_at            timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, document_id, document_version_id) REFERENCES document_version (company_id, document_id, id),
    FOREIGN KEY (company_id, policy_decision_id) REFERENCES policy_decision (company_id, id),
    CONSTRAINT ck_posting_intent_ended CHECK ((state = 'pending') = (ended_at IS NULL))
);
CREATE UNIQUE INDEX ux_posting_intent_pending ON posting_intent (document_id) WHERE state = 'pending';

-- ===== Change proposals [documents] (ADR-0029 rules 1-3) =====
CREATE TABLE change_proposal (                             -- typed header of a non-posting document type (rule 1)
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL,
    plan             jsonb NOT NULL,                       -- the simulated plan of the whole batch, server-computed
    plan_hash        text NOT NULL CONSTRAINT ck_change_proposal_plan_hash CHECK (plan_hash ~ '^[0-9a-f]{64}$'),
    evidence         jsonb NOT NULL DEFAULT '[]' CONSTRAINT ck_change_proposal_evidence CHECK (jsonb_typeof(evidence) = 'array'),   -- attachments, interactions, derivation traces, the agent run
    reason           text NOT NULL,
    document_date    date NOT NULL,
    execution_error  jsonb,                                -- the non-retryable error of the last execution attempt (rule 3, Failure)
    recorded_at      timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id)
);
-- The items of rule 1, an ADR-0008 rule 20 batch: one row per item, in batch order. "Items" is ADR-0029's word for the
-- lines of this header (ADR-0004 rule 10).
CREATE TABLE change_proposal_item (
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    change_proposal_id  uuid NOT NULL,
    item_index          integer NOT NULL CONSTRAINT ck_change_proposal_item_index CHECK (item_index >= 0),
    command_type        text NOT NULL CONSTRAINT ck_change_proposal_item_command_type CHECK (command_type ~ '^[A-Z][A-Za-z0-9]+$'),
    schema_version      integer NOT NULL CONSTRAINT ck_change_proposal_item_schema_version CHECK (schema_version >= 1),
    payload             jsonb NOT NULL,
    target_table        text NOT NULL,
    target_id           uuid,
    expected_version    text CONSTRAINT ck_change_proposal_item_expected_version CHECK (expected_version ~ '^[0-9a-f]{64}$'),   -- absent when the command creates the record
    field_changes       jsonb NOT NULL CONSTRAINT ck_change_proposal_item_field_changes CHECK (jsonb_typeof(field_changes) = 'array'),   -- before and after per field
    recorded_at         timestamptz NOT NULL,
    UNIQUE (change_proposal_id, item_index),
    FOREIGN KEY (company_id, change_proposal_id) REFERENCES change_proposal (company_id, id),
    CONSTRAINT ck_change_proposal_item_target CHECK (expected_version IS NULL OR target_id IS NOT NULL)
);
CREATE TABLE change_proposal_execution (                   -- immutable; written by the executing consumer (rule 3, Success)
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    change_proposal_id   uuid NOT NULL,
    document_version_id  uuid NOT NULL,                    -- the proposal version executed
    executed_at          timestamptz NOT NULL,
    recorded_at          timestamptz NOT NULL,
    UNIQUE (company_id, id),
    CONSTRAINT uq_change_proposal_execution_change_proposal_id UNIQUE (change_proposal_id),   -- executed once, then closed
    FOREIGN KEY (company_id, change_proposal_id) REFERENCES change_proposal (company_id, id),
    FOREIGN KEY (company_id, change_proposal_id, document_version_id) REFERENCES document_version (company_id, document_id, id)
);
-- The audit row of each executed item (rule 3, Success). interim: not stated in ADR-0029 as a table.
CREATE TABLE change_proposal_execution_item (
    company_id                    uuid NOT NULL,
    change_proposal_execution_id  uuid NOT NULL,
    item_index                    integer NOT NULL,
    audit_record_id               uuid NOT NULL,           -- key added after audit_record
    recorded_at                   timestamptz NOT NULL,
    PRIMARY KEY (change_proposal_execution_id, item_index),
    FOREIGN KEY (company_id, change_proposal_execution_id) REFERENCES change_proposal_execution (company_id, id)
);

-- ===== Outbox and delivery [outbox] (ADR-0013 rules 2-3, 6-8, 14-16) =====
CREATE TABLE event_subject (                               -- installation data, unpartitioned; the only ordering of events (rule 3)
    subject_table  text NOT NULL,
    subject_id     uuid NOT NULL,
    last_sequence  bigint NOT NULL CONSTRAINT ck_event_subject_last_sequence CHECK (last_sequence >= 1),
    recorded_at    timestamptz NOT NULL,
    PRIMARY KEY (subject_table, subject_id)
);
-- The pause state of a registered consumer (rules 6, 16): a new consumer is registered paused and ReplayEvents unpauses it.
-- interim: not stated in ADR-0013 as a table (the registration is code; only the runtime state is stored here).
CREATE TABLE event_consumer (                              -- installation data
    consumer       text PRIMARY KEY CONSTRAINT ck_event_consumer_consumer CHECK (consumer ~ '^[a-z][a-z0-9_]*$' AND length(consumer) <= 48),
    kind           text NOT NULL CONSTRAINT ck_event_consumer_kind CHECK (kind IN ('transactional', 'external')),
    queue          text NOT NULL CONSTRAINT ck_event_consumer_queue CHECK (queue IN ('events', 'integrations', 'jobs', 'pdf', 'agents')),
    is_paused      boolean NOT NULL DEFAULT true,
    max_attempts   smallint NOT NULL DEFAULT 10 CONSTRAINT ck_event_consumer_max_attempts CHECK (max_attempts >= 1),
    lease_seconds  integer NOT NULL DEFAULT 300 CONSTRAINT ck_event_consumer_lease CHECK (lease_seconds > 0),
    recorded_at    timestamptz NOT NULL
);
CREATE TABLE outbox_event (                                -- partitioned by month on id (rule 2); no unique index but its key
    id                   uuid NOT NULL,
    company_id           uuid REFERENCES company (id),     -- null for installation-scoped events
    event_type           text NOT NULL CONSTRAINT ck_outbox_event_event_type CHECK (event_type ~ '^[A-Z][A-Za-z0-9]+$'),
    schema_version       integer NOT NULL CONSTRAINT ck_outbox_event_schema_version CHECK (schema_version >= 1),
    subject_table        text NOT NULL,
    subject_id           uuid NOT NULL,
    subject_sequence     bigint NOT NULL CONSTRAINT ck_outbox_event_subject_sequence CHECK (subject_sequence >= 1),
    payload              jsonb NOT NULL,
    actor_kind           text NOT NULL CONSTRAINT ck_outbox_event_actor_kind CHECK (actor_kind IN ('human', 'agent', 'integration', 'system')),
    actor_id             uuid NOT NULL,
    on_behalf_of_id      uuid,
    agent_run_id         uuid,
    origin_agent_run_id  uuid,
    causation_chain_id   uuid NOT NULL,                    -- ADR-0058 rule 12: new at a transport's, person's or scheduled job's command; inherited by consumers, automation actions and agent runs started from an event
    causation_depth      smallint NOT NULL CONSTRAINT ck_outbox_event_causation_depth CHECK (causation_depth BETWEEN 0 AND 3),   -- automation actions in the chain so far; no default, the writer sets it
    automation_rule_version_id uuid CONSTRAINT ck_outbox_event_automation_depth CHECK (automation_rule_version_id IS NULL OR causation_depth >= 1),   -- the rule version whose action emitted it (no key: the configuration file is loaded after)
    is_tainted           boolean NOT NULL DEFAULT false,   -- rule 11
    business_date        date NOT NULL,
    command_type         text NOT NULL,
    trace_id             text,
    recorded_at          timestamptz NOT NULL,
    PRIMARY KEY (id)
) PARTITION BY RANGE (id);
CREATE TABLE event_delivery (                              -- one per subscribed consumer, unpartitioned (rule 6)
    id                uuid PRIMARY KEY,
    consumer          text NOT NULL REFERENCES event_consumer (consumer),
    event_id          uuid NOT NULL REFERENCES outbox_event (id),   -- done and skipped rows are deleted before their partition is dropped (rule 15)
    subject_table     text NOT NULL,
    subject_id        uuid NOT NULL,
    subject_sequence  bigint NOT NULL,
    company_id        uuid REFERENCES company (id),
    state             text NOT NULL DEFAULT 'pending' CONSTRAINT ck_event_delivery_state CHECK (state IN ('pending', 'running', 'done', 'held', 'skipped')),
    attempts          integer NOT NULL DEFAULT 0 CONSTRAINT ck_event_delivery_attempts CHECK (attempts >= 0),
    next_attempt_at   timestamptz NOT NULL,
    locked_until      timestamptz,
    last_error        text,
    recorded_at       timestamptz NOT NULL,
    CONSTRAINT uq_event_delivery_consumer_event_id UNIQUE (consumer, event_id),
    CONSTRAINT ck_event_delivery_running CHECK (state <> 'running' OR locked_until IS NOT NULL)
);
-- Rule 7's claim: the earliest delivery per consumer and subject that is not done or skipped.
CREATE INDEX ix_event_delivery_consumer_subject ON event_delivery (consumer, subject_table, subject_id, subject_sequence) WHERE state NOT IN ('done', 'skipped');
CREATE INDEX ix_event_delivery_pending ON event_delivery (consumer, next_attempt_at) WHERE state = 'pending';

-- ===== Audit [audit] (ADR-0038 rules 1-6; ADR-0054 rule 21; platform review 16) =====
CREATE TABLE audit_record (                                -- one per executed command or batch item; partitioned by month on id (rule 6)
    id                      uuid NOT NULL,
    company_id              uuid REFERENCES company (id),  -- null for installation scope
    business_date           date NOT NULL,
    command_type            text NOT NULL,
    schema_version          integer NOT NULL,
    effect_class            text NOT NULL CONSTRAINT ck_audit_record_effect_class CHECK (effect_class IN ('posting', 'master_data_change', 'outbound_send', 'other')),
    -- Registry attributes as registered at the time, so old rows are judged by the rules then in force (rule 2).
    is_human_only           boolean NOT NULL,
    is_proposal_bound       boolean NOT NULL,
    is_draft_only           boolean NOT NULL,              -- platform review 16 (ADR-0050 rule 26; the invariant on tainted runs)
    is_internal_only        boolean NOT NULL,              -- interim: not stated in ADR-0038 (platform review 9 adds the attribute, not its storage)
    idempotency_key         text,
    request_id              uuid,
    batch_id                uuid,                          -- the batch's idempotency record ID, no key (rule 1)
    batch_item_index        integer,
    reason                  text,                          -- masked by erasure (rule 4)
    actor_kind              text NOT NULL CONSTRAINT ck_audit_record_actor_kind CHECK (actor_kind IN ('human', 'agent', 'integration', 'system')),
    actor_id                uuid NOT NULL,
    on_behalf_of_id         uuid,
    agent_run_id            uuid,
    origin_agent_run_id     uuid,
    causation_chain_id      uuid NOT NULL,                 -- ADR-0058 rule 12, as on outbox_event
    causation_depth         smallint NOT NULL CONSTRAINT ck_audit_record_causation_depth CHECK (causation_depth BETWEEN 0 AND 3),
    automation_rule_version_id uuid CONSTRAINT ck_audit_record_automation_depth CHECK (automation_rule_version_id IS NULL OR causation_depth >= 1),   -- an automation action's rule version (INV-670)
    policy_decision_id      uuid,
    delegated_from_user_id  uuid,                          -- ADR-0054 rule 21
    is_review_skipped       boolean NOT NULL DEFAULT false, -- a person's Post executed without the plan panel under ui.post_review on_exceptions (ADR-0067 rule 13)
    subject_table           text,
    subject_id              uuid,
    document_id             uuid,                          -- no key: a deleted draft keeps its audit rows
    document_version        integer,
    branch_id               uuid,                          -- scope dimensions for record scope (rule 7)
    warehouse_id            uuid,
    plan_hash               text,
    trace_id                text,
    check_codes             text[] NOT NULL DEFAULT '{}',
    erased_at               timestamptz,                   -- rule 4
    recorded_at             timestamptz NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_audit_record_batch CHECK ((batch_id IS NULL) = (batch_item_index IS NULL)),
    CONSTRAINT ck_audit_record_document CHECK ((document_id IS NULL) = (document_version IS NULL)),
    CONSTRAINT ck_audit_record_draft_only CHECK (NOT is_draft_only OR effect_class NOT IN ('posting', 'master_data_change', 'outbound_send'))
) PARTITION BY RANGE (id);
CREATE INDEX ix_audit_record_subject ON audit_record (subject_table, subject_id);
CREATE INDEX ix_audit_record_actor ON audit_record (company_id, actor_kind, actor_id);
CREATE INDEX ix_audit_record_agent_run_id ON audit_record (agent_run_id) WHERE agent_run_id IS NOT NULL;
CREATE INDEX ix_audit_record_idempotency_key ON audit_record (idempotency_key, actor_id, command_type);
CREATE TABLE audit_change (                                -- field changes of change-tracked tables; partitioned by month on id (rules 3, 6)
    id               uuid NOT NULL,
    company_id       uuid REFERENCES company (id),
    audit_record_id  uuid NOT NULL,
    subject_table    text NOT NULL,
    row_id           uuid NOT NULL,
    field            text NOT NULL,
    before           jsonb,                                -- null for a personal field at creation or erasure (rule 3)
    after            jsonb,
    erased_at        timestamptz,
    recorded_at      timestamptz NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (audit_record_id) REFERENCES audit_record (id)
) PARTITION BY RANGE (id);
CREATE INDEX ix_audit_change_subject ON audit_change (subject_table, row_id);
CREATE INDEX ix_audit_change_audit_record_id ON audit_change (audit_record_id);
-- Rule 5: coalesced, written outside the refused transaction; only denial_count and last_at move, upward (trigger below).
CREATE TABLE audit_denial (
    id                   uuid PRIMARY KEY,
    company_id           uuid REFERENCES company (id),
    command_type         text NOT NULL,                    -- the command or query type
    mode                 text NOT NULL CONSTRAINT ck_audit_denial_mode CHECK (mode IN ('simulate', 'execute', 'query')),
    actor_kind           text NOT NULL CONSTRAINT ck_audit_denial_actor_kind CHECK (actor_kind IN ('human', 'agent', 'integration', 'system')),
    actor_id             uuid NOT NULL,
    on_behalf_of_id      uuid,
    agent_run_id         uuid,
    origin_agent_run_id  uuid,
    request_id           uuid,
    idempotency_key      text,
    subject_table        text,
    subject_id           uuid,
    error_code           text NOT NULL CONSTRAINT ck_audit_denial_error_code CHECK (error_code IN (
                             'permission_denied', 'human_only', 'proposal_required', 'policy_denied', 'outbound_content_out_of_scope',
                             'segregation_of_duties', 'tool_not_allowed', 'tainted_read_out_of_scope', 'untrusted_read_not_allowed',
                             'tainted_run_not_allowed', 'automatic_send_not_allowed')),
    policy_rule_id       uuid,                             -- policy_denied only: the decision row was rolled back
    policy_input_hash    text,
    window_start         timestamptz NOT NULL,
    denial_count         integer NOT NULL DEFAULT 1 CONSTRAINT ck_audit_denial_denial_count CHECK (denial_count >= 1),   -- count of rule 5, named by ADR-0004 rule 13
    first_at             timestamptz NOT NULL,
    last_at              timestamptz NOT NULL,
    trace_id             text,
    recorded_at          timestamptz NOT NULL,
    CONSTRAINT ck_audit_denial_window CHECK (extract(epoch FROM window_start)::bigint % 600 = 0),   -- 10-minute windows
    CONSTRAINT ck_audit_denial_times CHECK (first_at <= last_at),
    CONSTRAINT ck_audit_denial_policy CHECK (error_code = 'policy_denied' OR (policy_rule_id IS NULL AND policy_input_hash IS NULL))
);
CREATE UNIQUE INDEX ux_audit_denial_window ON audit_denial (company_id, actor_kind, actor_id, agent_run_id, command_type, error_code, subject_table, subject_id, window_start) NULLS NOT DISTINCT;

-- ===== Attachments [attachments] (ADR-0027 rule 2; ADR-0038 rules 13-15; ADR-0049 rule 28) =====
CREATE TABLE attachment (
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL REFERENCES company (id),
    sha256                         text NOT NULL CONSTRAINT ck_attachment_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    media_type                     text NOT NULL,          -- detected from the bytes (ADR-0038 rule 13)
    byte_count                     bigint NOT NULL CONSTRAINT ck_attachment_byte_count CHECK (byte_count > 0),
    storage_key                    text NOT NULL,          -- object store key; bytes never in the database
    data_label                     text NOT NULL CONSTRAINT ck_attachment_data_label CHECK (data_label IN ('public', 'internal', 'personal', 'sensitive_personal')),
    source_kind                    text NOT NULL CONSTRAINT ck_attachment_source_kind CHECK (source_kind IN ('upload', 'email', 'import', 'integration', 'generated')),   -- interim: values other than generated not stated in ADR-0027
    state                          text NOT NULL CONSTRAINT ck_attachment_state CHECK (state IN ('pending_scan', 'clean', 'rejected')),
    is_accounting_evidence         boolean NOT NULL DEFAULT false,   -- set by Post, never unset (ADR-0038 rule 15)
    generated_kind                 text,                   -- ADR-0049 rule 28; set at creation, never changed
    generated_audience             text CONSTRAINT ck_attachment_generated_audience CHECK (generated_audience IN ('internal', 'external')),
    generated_subject_document_id  uuid,
    contains_untrusted             boolean NOT NULL DEFAULT false,
    last_link_ended_at             timestamptz,            -- interim: not stated in ADR-0038 (retention counts from the last link's end, rule 15)
    bytes_released_at              timestamptz,            -- the bytes are no longer needed or served; physical deletion waits attachments.delete_grace_days (ADR-0038 rule 15 note)
    bytes_deleted_at               timestamptz,            -- set by RunAttachmentOrphanSweep after the grace period (ADR-0038 rule 15 note)
    recorded_at                    timestamptz NOT NULL,
    CONSTRAINT uq_attachment_company_id_sha256 UNIQUE (company_id, sha256),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, generated_subject_document_id) REFERENCES document (company_id, id),
    CONSTRAINT ck_attachment_generated CHECK ((source_kind = 'generated') = (generated_kind IS NOT NULL)
        AND (source_kind = 'generated') = (generated_audience IS NOT NULL)
        AND (generated_subject_document_id IS NULL OR source_kind = 'generated')
        AND (source_kind <> 'generated' OR state = 'clean')),
    CONSTRAINT ck_attachment_bytes_deleted CHECK (bytes_deleted_at IS NULL OR bytes_released_at IS NOT NULL)
);
CREATE TABLE attachment_link (                             -- polymorphic target, checked by INV-83
    id             uuid PRIMARY KEY,
    company_id     uuid NOT NULL,
    attachment_id  uuid NOT NULL,
    target_table   text NOT NULL,
    target_id      uuid NOT NULL,
    ended_at       timestamptz,                            -- interim: not stated in ADR-0027 (links end rather than disappear, for retention)
    recorded_at    timestamptz NOT NULL,
    FOREIGN KEY (company_id, attachment_id) REFERENCES attachment (company_id, id)
);
CREATE UNIQUE INDEX ux_attachment_link_current ON attachment_link (attachment_id, target_table, target_id) WHERE ended_at IS NULL;
CREATE INDEX ix_attachment_link_target ON attachment_link (company_id, target_table, target_id);

-- ===== Taxes [tax] (ADR-0041 rules 6, 11-13; ADR-0053 rule 3) =====
-- Part of the document's content: replaced by Create and Update while the document can change, frozen with it.
-- A line is (document_id, line_number): line numbers are line identity (ADR-0028 rule 1).
-- base, tax and computed_tax of rule 6 are named by ADR-0004 rule 13, in document (transaction) currency.
CREATE TABLE document_line_tax (
    id                               uuid PRIMARY KEY,
    company_id                       uuid NOT NULL,
    document_id                      uuid NOT NULL,
    line_number                      integer NOT NULL CONSTRAINT ck_document_line_tax_line_number CHECK (line_number > 0),
    tax_code_id                      uuid NOT NULL REFERENCES tax_code (id),
    tax_rate_id                      uuid,                 -- tax_rate is package data without DDL yet
    rate_percent                     types.percent,        -- null for none and assessed codes
    derivation_trace_id              uuid REFERENCES derivation_trace (id),   -- the matrix row used (ADR-0027 rule 3)
    base_transaction_amount          types.amount NOT NULL,
    tax_transaction_amount           types.amount NOT NULL,   -- the amount used: the stated tax when there is one
    computed_tax_transaction_amount  types.amount NOT NULL,
    input_use                        text CONSTRAINT ck_document_line_tax_input_use CHECK (input_use IN ('taxable', 'non_taxable', 'shared')),   -- purchase lines (rule 6)
    recorded_at                      timestamptz NOT NULL,
    UNIQUE (document_id, line_number, tax_code_id),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id)
);
CREATE TABLE tax_line (                                    -- the immutable tax subledger, written at posting (rule 11)
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    declaring_branch_id      uuid,                         -- the declaring unit: null for the company, or a branch with is_declaring_unit
    document_id              uuid NOT NULL,
    line_number              integer NOT NULL,
    journal_entry_id         uuid NOT NULL REFERENCES journal_entry (id),
    partner_tax_id           text,                         -- from the partner snapshot (ADR-0028 rule 16)
    tax_code_id              uuid NOT NULL REFERENCES tax_code (id),
    tax_rate_id              uuid,
    direction                text NOT NULL CONSTRAINT ck_tax_line_direction CHECK (direction IN ('sale', 'purchase', 'import')),
    input_use                text CONSTRAINT ck_tax_line_input_use CHECK (input_use IN ('taxable', 'non_taxable', 'shared')),
    rate_percent             types.percent,
    transaction_currency     text NOT NULL REFERENCES currency (code),
    base_transaction_amount  types.amount NOT NULL,
    tax_transaction_amount   types.amount NOT NULL,
    base_company_amount      types.amount NOT NULL,
    tax_company_amount       types.amount NOT NULL,        -- spread from the journal tax line by largest remainder (rule 12)
    tax_date                 date NOT NULL,
    declaration_date         date NOT NULL,
    initial_deductibility    text CONSTRAINT ck_tax_line_initial_deductibility CHECK (initial_deductibility IN ('deductible', 'conditional', 'not_deductible')),
    deductibility_rule_id    uuid,                         -- the package rule row in force on the tax date (ADR-0053 rule 3)
    recorded_at              timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, declaring_branch_id) REFERENCES branch (company_id, id),
    CONSTRAINT ck_tax_line_purchase CHECK ((direction = 'sale') = (initial_deductibility IS NULL)
        AND (input_use IS NULL OR direction <> 'sale') AND (deductibility_rule_id IS NULL OR direction <> 'sale'))
);
CREATE INDEX ix_tax_line_declaration ON tax_line (company_id, declaring_branch_id, declaration_date);
CREATE INDEX ix_tax_line_document_id ON tax_line (document_id);
CREATE TABLE tax_line_adjustment (                         -- append-only (rule 13 as amended by ADR-0053 rule 3)
    id                                  uuid PRIMARY KEY,
    company_id                          uuid NOT NULL,
    adjusts_tax_line_id                 uuid NOT NULL,
    kind                                text NOT NULL CONSTRAINT ck_tax_line_adjustment_kind CHECK (kind IN ('condition_met', 'condition_failed', 'apportionment', 'period_move', 'reversal_of_adjustment')),
    deductible_delta_transaction_amount types.amount NOT NULL,   -- positive raises deductible tax
    deductible_delta_company_amount     types.amount NOT NULL,
    declaration_date                    date NOT NULL,
    reason                              text,              -- the condition type's reason for condition_failed (failing_method, lapsed)
    journal_entry_id                    uuid REFERENCES journal_entry (id),
    reversal_of_id                      uuid,              -- interim: not stated in ADR-0041 (the adjustment a reversal_of_adjustment undoes)
    recorded_at                         timestamptz NOT NULL,
    FOREIGN KEY (company_id, adjusts_tax_line_id) REFERENCES tax_line (company_id, id),
    FOREIGN KEY (reversal_of_id) REFERENCES tax_line_adjustment (id),
    CONSTRAINT ck_tax_line_adjustment_reason CHECK (kind <> 'condition_failed' OR reason IS NOT NULL),
    CONSTRAINT ck_tax_line_adjustment_reversal CHECK ((kind = 'reversal_of_adjustment') = (reversal_of_id IS NOT NULL))
);

-- ===== Agent promotion evidence [agent_runs] (ADR-0050 rule 14) =====
CREATE TABLE agent_promotion_evidence (                    -- immutable; computed once by CreateAgentPromotionEvidence
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL REFERENCES company (id),
    agent_type_code     text NOT NULL REFERENCES agent_type (code),
    start_date          date NOT NULL,
    end_date            date NOT NULL,
    behavior_hash       text NOT NULL CONSTRAINT ck_agent_promotion_evidence_behavior_hash CHECK (behavior_hash ~ '^[0-9a-f]{64}$'),
    seat_models         jsonb NOT NULL,
    figures             jsonb NOT NULL,
    thresholds          jsonb NOT NULL,
    is_sufficient       boolean NOT NULL,
    target_mode         text NOT NULL DEFAULT 'assisted' CONSTRAINT ck_agent_promotion_evidence_target_mode CHECK (target_mode IN ('assisted', 'active')),   -- ADR-0065 rule 11
    document_type       text,                              -- ADR-0065 rule 11: the document type an active promotion covers (GetAgentDraftAcceptance)
    attachment_id       uuid,                              -- the data migration rehearsal report (ADR-0051 rule 28)
    created_by_user_id  uuid NOT NULL REFERENCES user_account (id),   -- interim: not stated in ADR-0050 (a person's command)
    recorded_at         timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, attachment_id) REFERENCES attachment (company_id, id),
    CONSTRAINT ck_agent_promotion_evidence_dates CHECK (start_date <= end_date),
    CONSTRAINT ck_agent_promotion_evidence_document_type CHECK ((target_mode = 'active') = (document_type IS NOT NULL))
);

-- ===== Money accounts, statements and payments [cash] (ADR-0048 rules 2-3, 8-9, 16; ADR-0030 rule 10) =====
CREATE TABLE money_account (                               -- company data, master_data_change, change-tracked (rule 2)
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL REFERENCES company (id),
    code                  text NOT NULL,
    name                  text NOT NULL,
    kind                  text NOT NULL CONSTRAINT ck_money_account_kind CHECK (kind IN ('cash', 'bank')),
    currency              text NOT NULL REFERENCES currency (code),
    account_id            uuid NOT NULL REFERENCES account (id),   -- cash_on_hand or cash_in_bank in its hierarchy, same currency (command check)
    bank_name             text,
    bank_code             text,
    bank_account_number   text,
    bank_branch           text,
    is_overdraft_allowed  boolean NOT NULL DEFAULT false,  -- Phase 1: bank accounts in company currency only (command check, overdraft_not_allowed)
    is_active             boolean NOT NULL DEFAULT true,
    recorded_at           timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, kind, currency),
    UNIQUE (company_id, id, currency),                  -- target of payment_method_money_account's key (ADR-0068 rule 16)
    CONSTRAINT uq_money_account_account_id UNIQUE (account_id),   -- each operational account serves at most one money account
    CONSTRAINT ck_money_account_bank CHECK (CASE kind
        WHEN 'bank' THEN bank_name IS NOT NULL AND bank_account_number IS NOT NULL
        ELSE bank_name IS NULL AND bank_code IS NULL AND bank_account_number IS NULL AND bank_branch IS NULL AND NOT is_overdraft_allowed END)
);
CREATE TABLE payment_method_money_account (                -- [cash] ADR-0068 rule 16; company data, master_data_change, change-tracked
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL REFERENCES company (id),
    payment_method_id  uuid NOT NULL,
    money_account_id   uuid NOT NULL,
    currency           text NOT NULL,                       -- the money account's currency, held by the key below
    branch_id          uuid,                                -- null: every branch without a row of its own
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    -- one default per method, branch and currency; selection: the document's branch, else the null branch (rule 16)
    CONSTRAINT uq_payment_method_money_account_key UNIQUE NULLS NOT DISTINCT (company_id, payment_method_id, branch_id, currency),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id),
    CONSTRAINT fk_payment_method_money_account_money_account FOREIGN KEY (company_id, money_account_id, currency) REFERENCES money_account (company_id, id, currency),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id)
);
-- Kinds (command check, payment_method_money_account_mismatch): a cash method to a cash money account, every other
-- method to a bank money account, and no row for an offset method.
CREATE TABLE bank_statement (
    id                           uuid PRIMARY KEY,
    company_id                   uuid NOT NULL,
    money_account_id             uuid NOT NULL,
    statement_number             text NOT NULL,
    period_start_date            date NOT NULL,
    period_end_date              date NOT NULL,
    transaction_opening_balance  types.amount NOT NULL,    -- in the money account's currency (DS-06's balance naming)
    transaction_closing_balance  types.amount NOT NULL,
    source_attachment_id         uuid NOT NULL,
    reader_code                  text NOT NULL,            -- the package's BankStatementReader (DS-14)
    has_gap                      boolean NOT NULL DEFAULT false,
    imported_by_user_id          uuid NOT NULL REFERENCES user_account (id),   -- interim: not stated in ADR-0048 (drafts act on behalf of the importer, rule 9)
    recorded_at                  timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, money_account_id),
    CONSTRAINT uq_bank_statement_money_account_id_statement_number UNIQUE (money_account_id, statement_number),   -- interim: not stated in ADR-0048
    FOREIGN KEY (company_id, money_account_id) REFERENCES money_account (company_id, id),
    FOREIGN KEY (company_id, source_attachment_id) REFERENCES attachment (company_id, id),
    CONSTRAINT ck_bank_statement_period CHECK (period_start_date <= period_end_date)
);
-- Append-only except the match, proposal and suggestion columns (trigger below). Descriptions, counterparty fields and
-- suggestions are is_untrusted (ADR-0029 rule 10); descriptions and counterparty fields are personal (ADR-0050 rule 9).
CREATE TABLE bank_statement_line (
    id                            uuid PRIMARY KEY,
    company_id                    uuid NOT NULL,
    bank_statement_id             uuid NOT NULL,
    money_account_id              uuid NOT NULL,           -- the statement's; part of the natural key (rule 2)
    line_number                   integer NOT NULL CONSTRAINT ck_bank_statement_line_line_number CHECK (line_number > 0),
    booking_date                  date NOT NULL,
    value_date                    date NOT NULL,
    transaction_amount            types.amount NOT NULL CONSTRAINT ck_bank_statement_line_amount CHECK (transaction_amount <> 0),   -- signed: inflow positive
    bank_reference                text,
    counterparty_name             text,
    counterparty_bank_code        text,
    counterparty_account_number   text,
    bank_transaction_code         text,                    -- ADR-0063 rule 9: the bank's code for the line (an ISO 20022 family and sub-family, or the bank's own), from the statement reader
    description                   text,
    match_state                   text NOT NULL DEFAULT 'unmatched' CONSTRAINT ck_bank_statement_line_match_state CHECK (match_state IN ('unmatched', 'proposed', 'matched', 'ignored')),
    ignore_reason                 text,
    matched_document_id           uuid,
    -- The cascade's proposal (flows review A9): a draft or posted document, its score and basis; matched only at Post.
    proposed_document_id          uuid,
    proposal_score                smallint CONSTRAINT ck_bank_statement_line_proposal_score CHECK (proposal_score BETWEEN 0 AND 100),
    -- ADR-0059 rule 6: the parameters of cash.match_bank_line the proposal was made under, the function version, the parameter
    -- set version and its state (core_default, assisted, active); a tied match never acts. No key to parameter_set_version: the
    -- configuration file is loaded after this one.
    match_parameters_hash         text CONSTRAINT ck_bank_statement_line_match_parameters_hash CHECK (match_parameters_hash ~ '^[0-9a-f]{64}$'),
    match_function_version        text,
    match_parameter_set_version_id uuid,
    match_parameter_state         text CONSTRAINT ck_bank_statement_line_match_parameter_state CHECK (match_parameter_state IN ('core_default', 'assisted', 'active')),
    match_is_tied                 boolean NOT NULL DEFAULT false,
    match_basis                   text CONSTRAINT ck_bank_statement_line_match_basis CHECK (match_basis IN (
                                      'already_posted', 'reference', 'account_amount', 'account_subset', 'company_rule', 'bank_charge_rule', 'llm_suggestion', 'manual')),   -- bank_charge_rule: ADR-0063 rule 9   -- interim: values not stated in ADR-0048 (cascade steps of rule 9)
    -- RecordBankLineSuggestion (ADR-0051 rule 17): tokens, name, purpose and run, all is_untrusted. interim: column names not stated in ADR-0051.
    suggested_reference_tokens    text[] CONSTRAINT ck_bank_statement_line_suggested_tokens CHECK (cardinality(suggested_reference_tokens) <= 5),
    suggested_payer_name_text     text,
    suggested_stable_payer_token  text,
    suggested_purpose             text CONSTRAINT ck_bank_statement_line_suggested_purpose CHECK (suggested_purpose IN (
                                      'invoice_payment', 'advance', 'refund', 'salary', 'tax', 'bank_charge', 'internal_transfer', 'loan', 'unknown')),
    suggestion_agent_run_id       uuid,
    recorded_at                   timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (bank_statement_id, line_number),
    FOREIGN KEY (company_id, bank_statement_id, money_account_id) REFERENCES bank_statement (company_id, id, money_account_id),
    FOREIGN KEY (company_id, matched_document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, proposed_document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, suggestion_agent_run_id) REFERENCES agent_run (company_id, id),
    CONSTRAINT ck_bank_statement_line_matched CHECK ((match_state = 'matched') = (matched_document_id IS NOT NULL)
        AND (match_state = 'ignored') = (ignore_reason IS NOT NULL)),
    -- A proposed line names the cascade's proposed document and becomes matched when it posts (ADR-0048 rule 8 note;
    -- rule 9 note F1; simulation review 2026-11-15).
    CONSTRAINT ck_bank_statement_line_proposed CHECK (match_state <> 'proposed' OR proposed_document_id IS NOT NULL),
    -- An LLM suggestion never counts in a score (rule 9).
    CONSTRAINT ck_bank_statement_line_proposal CHECK ((proposed_document_id IS NULL) = (match_basis IS NULL)
        AND (proposal_score IS NULL OR proposed_document_id IS NOT NULL)
        AND (match_basis IS DISTINCT FROM 'llm_suggestion' OR proposal_score IS NULL)),
    CONSTRAINT ck_bank_statement_line_suggestion CHECK ((suggestion_agent_run_id IS NULL) = (suggested_purpose IS NULL)),
    -- ADR-0059 rule 6: the match parameters are recorded together, and a set version exactly when one was in force.
    CONSTRAINT ck_bank_statement_line_match_parameters CHECK ((match_parameters_hash IS NULL) = (match_function_version IS NULL)
        AND (match_parameters_hash IS NULL) = (match_parameter_state IS NULL)
        AND (match_parameter_set_version_id IS NULL) = (match_parameter_state IS DISTINCT FROM 'assisted' AND match_parameter_state IS DISTINCT FROM 'active'))
);
-- ADR-0030 rule 10: bank account, bank reference, value date and amount; without a reference no key applies.
CREATE UNIQUE INDEX ux_bank_statement_line_natural_key ON bank_statement_line (company_id, money_account_id, bank_reference, value_date, transaction_amount)
    WHERE bank_reference IS NOT NULL;
CREATE INDEX ix_bank_statement_line_unmatched ON bank_statement_line (company_id, money_account_id) WHERE match_state = 'unmatched';
-- The typed header of the four payment types (rule 3). One header serves the four types, which share their fields;
-- document_type is copied from the document row and held by the composite key. interim: ADR-0048 names the types, not
-- their tables (ADR-0009 rule 1 names a typed header per type).
CREATE TABLE payment (
    id                           uuid PRIMARY KEY,
    company_id                   uuid NOT NULL,
    document_type                text NOT NULL CONSTRAINT ck_payment_document_type CHECK (document_type IN ('cash_receipt', 'cash_payment', 'bank_receipt', 'bank_payment')),
    money_account_kind           text NOT NULL GENERATED ALWAYS AS (CASE WHEN document_type LIKE 'cash%' THEN 'cash' ELSE 'bank' END) STORED,
    money_account_id             uuid NOT NULL,
    transaction_currency         text NOT NULL,            -- the document's currency, the money account's (rule 3)
    document_date                date NOT NULL,
    posting_date                 date NOT NULL,
    value_date                   date,                     -- bank documents
    partner_id                   uuid,                     -- optional when every line is an account line
    partner_name                 text,                     -- partner snapshot (ADR-0028 rule 16)
    partner_tax_id               text,
    partner_address              jsonb,
    counterparty_name            text,                     -- cash documents: the payer's or payee's name, a snapshot
    settlement_exchange_rate     types.exchange_rate,      -- rate type settlement, for a foreign currency (ADR-0011 rule 12)
    payment_method_id            uuid,                     -- the method used, copied from the invoice a payment is drafted from; suggests only (ADR-0068 rules 15, 17)
    reference                    text,
    partner_bank_account_id      uuid,                     -- bank_payment to a partner (ADR-0028 rule 15)
    bank_statement_line_id       uuid,                     -- interim: not stated in ADR-0048 (the line it was drafted from, for UnmatchBankLine, rule 9)
    print_language               text,                     -- ADR-0049 rule 27
    recorded_at                  timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id, document_type) REFERENCES document (company_id, id, document_type),
    -- money_account_kind_mismatch and the currency rule, held by the key (rule 3).
    FOREIGN KEY (company_id, money_account_id, money_account_kind, transaction_currency) REFERENCES money_account (company_id, id, kind, currency),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, bank_statement_line_id) REFERENCES bank_statement_line (company_id, id),
    CONSTRAINT ck_payment_value_date CHECK ((money_account_kind = 'bank') = (value_date IS NOT NULL)),
    CONSTRAINT ck_payment_counterparty CHECK (counterparty_name IS NULL OR money_account_kind = 'cash'),
    CONSTRAINT ck_payment_partner_bank_account CHECK (partner_bank_account_id IS NULL
        OR (document_type = 'bank_payment' AND partner_id IS NOT NULL)),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id)
);
CREATE INDEX ix_payment_money_account_id ON payment (company_id, money_account_id, posting_date);
CREATE TABLE payment_line (
    id                           uuid PRIMARY KEY,
    company_id                   uuid NOT NULL,
    payment_id                   uuid NOT NULL,
    line_number                  integer NOT NULL CONSTRAINT ck_payment_line_line_number CHECK (line_number > 0),
    line_kind                    text NOT NULL CONSTRAINT ck_payment_line_line_kind CHECK (line_kind IN ('settle', 'advance', 'on_account', 'account', 'bank_charge')),
    transaction_amount           types.amount NOT NULL CONSTRAINT ck_payment_line_amount CHECK (transaction_amount > 0),   -- in the document's currency
    open_item_id                 uuid REFERENCES open_item (id),   -- settle lines
    open_item_transaction_amount types.amount,             -- settle lines: the amount in the item's currency
    exchange_rate                types.exchange_rate,      -- settle lines in another currency: the bank's rate
    discount_transaction_amount  types.amount CONSTRAINT ck_payment_line_discount CHECK (discount_transaction_amount >= 0),   -- rule 7, in the item's currency
    is_paid_by_third_party       boolean NOT NULL DEFAULT false,   -- paid_by_third_party of rule 3
    evidence_method              text CONSTRAINT ck_payment_line_evidence_method CHECK (evidence_method IN ('cash', 'bank_transfer', 'card', 'third_party')),   -- rule 18
    account_id                   uuid REFERENCES account (id),   -- account lines
    cost_center_id               uuid,
    project_id                   uuid REFERENCES project (id),
    supplier_partner_id          uuid,                     -- taxed account lines: a partner, or a tax ID and name snapshot
    supplier_tax_id              text,
    supplier_name                text,
    supplier_invoice_key         jsonb,                    -- the regime's supplier-invoice key fields (ADR-0030 rule 10)
    supplier_invoice_date        date,
    business_unit_id             uuid,                     -- account lines: the explicit unit (ADR-0069 rule 8; command check)
    description                  text,
    recorded_at                  timestamptz NOT NULL,
    UNIQUE (payment_id, line_number),
    FOREIGN KEY (company_id, payment_id) REFERENCES payment (company_id, id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, supplier_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_payment_line_kind_columns CHECK (
        (line_kind = 'settle') = (open_item_id IS NOT NULL)
        AND (line_kind = 'settle') = (open_item_transaction_amount IS NOT NULL)
        AND (line_kind = 'account') = (account_id IS NOT NULL)
        AND (exchange_rate IS NULL OR line_kind = 'settle')
        AND (discount_transaction_amount IS NULL OR line_kind = 'settle')),
    -- Rule 3, Evidence: lines that settle or create an item carry the method; third party only on settle lines.
    CONSTRAINT ck_payment_line_evidence CHECK ((line_kind IN ('settle', 'advance', 'on_account')) = (evidence_method IS NOT NULL)
        AND (is_paid_by_third_party = (evidence_method IS NOT DISTINCT FROM 'third_party'))
        AND (NOT is_paid_by_third_party OR line_kind = 'settle')),
    CONSTRAINT ck_payment_line_supplier CHECK ((supplier_partner_id IS NULL AND supplier_tax_id IS NULL AND supplier_invoice_key IS NULL)
        OR line_kind = 'account'),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE INDEX ix_payment_line_open_item_id ON payment_line (open_item_id) WHERE open_item_id IS NOT NULL;
-- ADR-0048 rule 17 (and its note of the final simulation review): the collection side table of an open item (ADR-0026
-- rule 1), owned by cash. One row per open item that has collection data, written with the first of them; no row reads as
-- level 0, no reminder, not blocked, not disputed. ADR-0063 rule 27 sets the payment block of a suspected near-duplicate
-- purchase invoice in the transaction that posts it, and clears it when a person records not a duplicate. The key to
-- open_item is closed below (open_item gains a key with its company).
CREATE TABLE open_item_collection (                        -- change-tracked (ADR-0038), so INV-98 reads the block at a posting
    open_item_id          uuid PRIMARY KEY,
    company_id            uuid NOT NULL,
    dunning_level         integer NOT NULL DEFAULT 0 CONSTRAINT ck_open_item_collection_dunning_level CHECK (dunning_level >= 0),   -- the level of cash.dunning.levels last reminded
    last_reminder_date    date,
    is_payment_blocked    boolean NOT NULL DEFAULT false,
    payment_block_reason  text CONSTRAINT ck_open_item_collection_payment_block_reason CHECK (payment_block_reason IN ('duplicate_review', 'manual')),   -- interim: not stated in ADR-0048 (why the item is held)
    is_disputed           boolean NOT NULL DEFAULT false,
    dispute_reason        text,
    recorded_at           timestamptz NOT NULL,
    CONSTRAINT ck_open_item_collection_payment_block CHECK (is_payment_blocked = (payment_block_reason IS NOT NULL)),
    CONSTRAINT ck_open_item_collection_dispute CHECK (is_disputed = (dispute_reason IS NOT NULL)),
    CONSTRAINT ck_open_item_collection_reminder CHECK ((dunning_level = 0) = (last_reminder_date IS NULL))
);
CREATE INDEX ix_open_item_collection_held ON open_item_collection (company_id) WHERE is_payment_blocked OR is_disputed;
-- ADR-0063 rule 27 note: a settle line of an outgoing payment (cash_payment, bank_payment) never names an open item blocked
-- for payment. Post of these types repeats the check, so a block set after the draft also holds. Receipts are not held.
CREATE FUNCTION payment_line_check_payment_block() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.line_kind = 'settle' AND EXISTS (
        SELECT 1 FROM open_item_collection oc JOIN payment p ON p.id = NEW.payment_id
         WHERE oc.open_item_id = NEW.open_item_id AND oc.is_payment_blocked AND p.document_type IN ('cash_payment', 'bank_payment')) THEN
        RAISE EXCEPTION 'open item % is blocked for payment (open_item_payment_blocked)', NEW.open_item_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

-- ===== Keys closed after their tables (cycles and tables of other design items) =====
-- work_item -> agent_run -> work_item and document -> work_item would be cycles in a top-down load.
ALTER TABLE work_item ADD CONSTRAINT fk_work_item_origin_agent_run_id FOREIGN KEY (company_id, origin_agent_run_id) REFERENCES agent_run (company_id, id);
ALTER TABLE document ADD CONSTRAINT fk_document_origin_work_item_id FOREIGN KEY (company_id, origin_work_item_id) REFERENCES work_item (company_id, id);
ALTER TABLE change_proposal_execution_item ADD CONSTRAINT fk_change_proposal_execution_item_audit_record_id FOREIGN KEY (audit_record_id) REFERENCES audit_record (id);
ALTER TABLE audit_record ADD CONSTRAINT fk_audit_record_policy_decision_id FOREIGN KEY (company_id, policy_decision_id) REFERENCES policy_decision (company_id, id);
-- DS-15: an approval's stage belongs to its pool (ADR-0055 rule 9). approval_stage gains a key with its pool.
ALTER TABLE approval_stage ADD CONSTRAINT uq_approval_stage_company_id_approval_pool_id_id UNIQUE (company_id, approval_pool_id, id);
ALTER TABLE approval ADD CONSTRAINT fk_approval_approval_stage_id FOREIGN KEY (company_id, approval_pool_id, approval_stage_id) REFERENCES approval_stage (company_id, approval_pool_id, id);
-- DS-15: segregation exceptions name a document and an audit record (ADR-0054 rule 20).
ALTER TABLE segregation_exception ADD CONSTRAINT fk_segregation_exception_document_id FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id);
ALTER TABLE segregation_exception ADD CONSTRAINT fk_segregation_exception_audit_record_id FOREIGN KEY (audit_record_id) REFERENCES audit_record (id);
-- DS-20: a payment's beneficiary account belongs to its partner (ADR-0028 rule 15; ADR-0048 rule 3).
ALTER TABLE partner_bank_account ADD CONSTRAINT uq_partner_bank_account_company_id_partner_id_id UNIQUE (company_id, partner_id, id);
ALTER TABLE payment ADD CONSTRAINT fk_payment_partner_bank_account_id FOREIGN KEY (company_id, partner_id, partner_bank_account_id) REFERENCES partner_bank_account (company_id, partner_id, id);
-- DS-06: an open item's collection row belongs to the item's company (ADR-0048 rule 17 note). open_item gains a key with its company.
ALTER TABLE open_item ADD CONSTRAINT uq_open_item_company_id_id UNIQUE (company_id, id);
ALTER TABLE open_item_collection ADD CONSTRAINT fk_open_item_collection_open_item_id FOREIGN KEY (company_id, open_item_id) REFERENCES open_item (company_id, id);
-- DS-35 refers to attachment and agent_run by ID until their DDL exists; this file is that DDL.
ALTER TABLE inbound_message ADD CONSTRAINT fk_inbound_message_raw_attachment_id FOREIGN KEY (company_id, raw_attachment_id) REFERENCES attachment (company_id, id);
ALTER TABLE interaction_summary ADD CONSTRAINT fk_interaction_summary_agent_run_id FOREIGN KEY (company_id, agent_run_id) REFERENCES agent_run (company_id, id);

-- ===== Guards =====
-- Arguments: columns that may change; columns that may be set once from null; columns only the erasure command may
-- change (nativeflows.erasure_command_id, set by the dispatcher for EraseDataSubject alone, ADR-0038 rule 4; DS-36 adds the
-- check that it names an idempotency record of that command in this transaction). Deletes are refused.
CREATE FUNCTION platform_check_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_mutable       text[] := TG_ARGV[0]::text[];
    v_set_once      text[] := TG_ARGV[1]::text[];
    v_erasure_only  text[] := TG_ARGV[2]::text[];
    v_is_erasing    boolean := coalesce(current_setting('nativeflows.erasure_command_id', true), '') <> '';
    v_old           jsonb;
    v_new           jsonb;
    v_key           text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '% rows are never deleted (append-only)', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
    END IF;
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    FOR v_key IN SELECT jsonb_object_keys(v_new) LOOP
        CONTINUE WHEN (v_old -> v_key) IS NOT DISTINCT FROM (v_new -> v_key);
        CONTINUE WHEN v_key = ANY (v_mutable);
        CONTINUE WHEN v_key = ANY (v_set_once) AND jsonb_typeof(v_old -> v_key) = 'null';
        CONTINUE WHEN v_key = ANY (v_erasure_only) AND v_is_erasing;
        RAISE EXCEPTION '%.% is append-only', TG_TABLE_NAME, v_key USING ERRCODE = 'restrict_violation';
    END LOOP;
    RETURN NEW;
END
$$;
CREATE FUNCTION platform_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% rows are never updated or deleted', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
END
$$;

-- ADR-0009 rule 14: a document row in a final state never changes, except Reverse moving posted to reversed and nothing
-- else; only a draft is deleted (rule 4). Identity columns never change, and a number once given stays.
CREATE FUNCTION document_check_row_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state <> 'draft' THEN
            RAISE EXCEPTION 'only a draft document is deleted (ADR-0009 rule 4)' USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.state IN ('posted', 'reversed', 'canceled', 'closed') THEN
        IF OLD.state = 'posted' AND NEW.state = 'reversed' AND (to_jsonb(OLD) - 'state') = (to_jsonb(NEW) - 'state') THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'document in state % is immutable (ADR-0009 rule 14)', OLD.state USING ERRCODE = 'restrict_violation';
    END IF;
    -- is_barcoded is fixed at Create too (ADR-0061 rule 9)
    IF (NEW.company_id, NEW.document_type, NEW.reversal_of_id, NEW.correction_of_id, NEW.created_by_user_id, NEW.is_barcoded)
       IS DISTINCT FROM (OLD.company_id, OLD.document_type, OLD.reversal_of_id, OLD.correction_of_id, OLD.created_by_user_id, OLD.is_barcoded)
       OR (OLD.number IS NOT NULL AND NEW.number IS DISTINCT FROM OLD.number) THEN
        RAISE EXCEPTION 'document identity and number are immutable (ADR-0009 rules 15, 23)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0009 rule 14; ADR-0028 rule 6; ADR-0052 rule 27: header, line and content rows of a document in a final state, or
-- in the frozen states issuing and sending, never change. The argument names the column holding the document ID.
CREATE FUNCTION document_check_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_ids    uuid[] := ARRAY[]::uuid[];
    v_state  text;
BEGIN
    IF TG_OP <> 'INSERT' THEN v_ids := v_ids || (to_jsonb(OLD) ->> TG_ARGV[0])::uuid; END IF;
    IF TG_OP <> 'DELETE' THEN v_ids := v_ids || (to_jsonb(NEW) ->> TG_ARGV[0])::uuid; END IF;
    FOR v_state IN SELECT state FROM document WHERE id = ANY (v_ids) LOOP
        IF v_state IN ('posted', 'reversed', 'canceled', 'closed', 'issuing', 'sending') THEN
            RAISE EXCEPTION '% of a document in state % is immutable (ADR-0009 rule 14)', TG_TABLE_NAME, v_state
                USING ERRCODE = 'restrict_violation';
        END IF;
    END LOOP;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END
$$;
-- ADR-0009 rule 14: versions are never updated. The generated Delete of a draft removes them with the draft: the
-- dispatcher sets nativeflows.document_delete_id to that document's ID for Delete alone (the pattern of DS-35).
CREATE FUNCTION document_version_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE'
       AND coalesce(current_setting('nativeflows.document_delete_id', true), '') = OLD.document_id::text
       AND EXISTS (SELECT 1 FROM document d WHERE d.id = OLD.document_id AND d.state = 'draft') THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'document versions are never updated or deleted (ADR-0009 rule 14)' USING ERRCODE = 'restrict_violation';
END
$$;
-- ADR-0029 rules 8-9 and INV-88: a version is written tainted when a run tainted at that time wrote it (directly or as the
-- origin of a consumer chain), or when the version it derives from was effectively tainted when it was written. It
-- derives from derived_from_version_id when set, else from the previous version.
CREATE FUNCTION document_version_check_taint() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.is_tainted THEN
        RETURN NEW;
    END IF;
    IF EXISTS (SELECT 1 FROM document_version v
                WHERE (CASE WHEN NEW.derived_from_version_id IS NOT NULL THEN v.id = NEW.derived_from_version_id
                            ELSE v.document_id = NEW.document_id AND v.version = NEW.version - 1 END)
                  AND v.is_tainted
                  AND NOT EXISTS (SELECT 1 FROM taint_clearance c WHERE c.document_version_id = v.id AND c.cleared_at <= NEW.recorded_at)) THEN
        RAISE EXCEPTION 'version derives from an effectively tainted version and must be tainted (ADR-0029 rule 8; INV-88)'
            USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (SELECT 1 FROM agent_run r WHERE r.id IN (NEW.agent_run_id, NEW.origin_agent_run_id)
                  AND r.tainted_at IS NOT NULL AND r.tainted_at <= NEW.recorded_at) THEN
        RAISE EXCEPTION 'version written by a tainted run must be tainted (ADR-0029 rule 8; INV-88)' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0055 rules 6-9: a stage approval names a stage of the plan its decision recorded, and a decision with a plan is
-- approved only at stages.
CREATE FUNCTION approval_check_plan() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_plan  jsonb;
BEGIN
    SELECT approval_plan INTO v_plan FROM policy_decision WHERE id = NEW.policy_decision_id;
    IF v_plan IS NOT NULL AND (NEW.approval_stage_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(v_plan) e WHERE e ->> 'id' = NEW.approval_stage_id::text)) THEN
        RAISE EXCEPTION 'approval_stage_not_in_plan: the approval must name a stage of its decision''s plan (ADR-0055 rules 6, 9)'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0028 rule 7: an intent's frozen plan never changes; only a pending intent ends, once.
CREATE FUNCTION posting_intent_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' OR OLD.state <> 'pending'
       OR (to_jsonb(NEW) - 'state' - 'ended_at' - 'e_invoice_record_id') <> (to_jsonb(OLD) - 'state' - 'ended_at' - 'e_invoice_record_id')
       OR (OLD.e_invoice_record_id IS NOT NULL AND NEW.e_invoice_record_id IS DISTINCT FROM OLD.e_invoice_record_id) THEN
        RAISE EXCEPTION 'a posting intent is frozen; only a pending one ends (ADR-0028 rule 7)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0042 rules 2, 5: identity never changes; taint is an OR over raises and never drops; the first origin run is kept.
CREATE FUNCTION work_item_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'work items are never deleted (ADR-0042 rule 12)' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (NEW.company_id, NEW.kind, NEW.subject_table, NEW.subject_id, NEW.open_key, NEW.origin_event_id)
       IS DISTINCT FROM (OLD.company_id, OLD.kind, OLD.subject_table, OLD.subject_id, OLD.open_key, OLD.origin_event_id)
       OR (OLD.is_tainted AND NOT NEW.is_tainted)
       OR (OLD.origin_agent_run_id IS NOT NULL AND NEW.origin_agent_run_id IS DISTINCT FROM OLD.origin_agent_run_id)
       OR (OLD.work_case_id IS NOT NULL AND NEW.work_case_id IS DISTINCT FROM OLD.work_case_id)
       OR OLD.state IN ('done', 'canceled') THEN
        RAISE EXCEPTION 'work item identity, taint, case or end state changed (ADR-0042 rules 2, 5; ADR-0066 rule 10)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0066 rule 2: a case is never deleted; identity and origin never change; resolved and canceled are final.
CREATE FUNCTION work_case_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'work cases are never deleted (ADR-0066 rule 2)' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (NEW.company_id, NEW.kind, NEW.open_key, NEW.origin_table, NEW.origin_id)
       IS DISTINCT FROM (OLD.company_id, OLD.kind, OLD.open_key, OLD.origin_table, OLD.origin_id)
       OR OLD.state IN ('resolved', 'canceled') THEN
        RAISE EXCEPTION 'work case identity, origin or final state changed (ADR-0066 rule 2)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0038 rule 6: audit_denial moves only denial_count and last_at, upward.
CREATE FUNCTION audit_denial_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' OR (to_jsonb(NEW) - 'denial_count' - 'last_at') <> (to_jsonb(OLD) - 'denial_count' - 'last_at')
       OR NEW.denial_count < OLD.denial_count OR NEW.last_at < OLD.last_at THEN
        RAISE EXCEPTION 'audit denials only count up (ADR-0038 rule 6)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0027 rule 2; ADR-0038 rules 14-15; ADR-0049 rule 28: scan state moves only from pending_scan; accounting evidence is
-- never unset; generated columns never change; a second creation keeps the stricter label and contains_untrusted.
CREATE FUNCTION attachment_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_labels text[] := ARRAY['public', 'internal', 'personal', 'sensitive_personal'];
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'attachment rows are never deleted; their bytes are (ADR-0038 rule 15)' USING ERRCODE = 'restrict_violation';
    END IF;
    IF (NEW.company_id, NEW.sha256, NEW.source_kind, NEW.generated_kind, NEW.generated_audience, NEW.generated_subject_document_id)
       IS DISTINCT FROM (OLD.company_id, OLD.sha256, OLD.source_kind, OLD.generated_kind, OLD.generated_audience, OLD.generated_subject_document_id)
       OR (OLD.is_accounting_evidence AND NOT NEW.is_accounting_evidence)
       OR (OLD.contains_untrusted AND NOT NEW.contains_untrusted)
       OR array_position(v_labels, NEW.data_label) < array_position(v_labels, OLD.data_label)
       OR (NEW.state <> OLD.state AND OLD.state <> 'pending_scan') THEN
        RAISE EXCEPTION 'attachment change not allowed (ADR-0027 rule 2; ADR-0038 rules 14-15)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0048 rule 8 and INV-95 as amended by the flows review (A9): a line becomes matched only to a posted document, and
-- for a payment only to one of the line's money account.
CREATE FUNCTION bank_statement_line_check_match() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.match_state = 'matched' AND (TG_OP = 'INSERT' OR OLD.matched_document_id IS DISTINCT FROM NEW.matched_document_id) THEN
        IF NOT EXISTS (SELECT 1 FROM document d WHERE d.id = NEW.matched_document_id AND d.state = 'posted') THEN
            RAISE EXCEPTION 'bank_statement_line_not_posted: a line is matched only to a posted document (ADR-0048 rule 8; INV-95)'
                USING ERRCODE = 'check_violation';
        END IF;
        IF EXISTS (SELECT 1 FROM payment p WHERE p.id = NEW.matched_document_id AND p.money_account_id <> NEW.money_account_id) THEN
            RAISE EXCEPTION 'matched payment is on another money account (INV-95)' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$$;
-- ADR-0048 rule 8: opening balance plus the lines equals the closing balance, at commit (bank_statement_unbalanced).
CREATE FUNCTION bank_statement_check_balance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_id  uuid;
BEGIN
    IF TG_TABLE_NAME = 'bank_statement' THEN
        v_id := NEW.id;
    ELSE
        v_id := NEW.bank_statement_id;
    END IF;
    IF EXISTS (SELECT 1 FROM bank_statement s
                WHERE s.id = v_id
                  AND s.transaction_opening_balance + coalesce((SELECT sum(l.transaction_amount) FROM bank_statement_line l WHERE l.bank_statement_id = s.id), 0)
                      <> s.transaction_closing_balance) THEN
        RAISE EXCEPTION 'bank_statement_unbalanced: opening balance plus lines differs from closing balance (ADR-0048 rule 8)'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END
$$;
-- ADR-0050 rule 25: tainted_at and its source are set once and never cleared; a run's identity never changes.
CREATE TRIGGER trg_agent_run_append_only BEFORE UPDATE OR DELETE ON agent_run FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{work_item_id,llm_call_count,tool_call_count,input_token_count,output_token_count,cache_token_count,row_read_count,denial_count,cost_amount,reserved_amount,state,outcome,ended_at,duration_ms,input_refs,output_refs,trace_id}', '{tainted_at,taint_source_kind,taint_source_table,taint_source_id}', '{}');
CREATE TRIGGER trg_agent_run_step_append_only BEFORE UPDATE OR DELETE ON agent_run_step FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{request_body,response_body,erased_at}');
CREATE TRIGGER trg_agent_type_version_immutable BEFORE UPDATE OR DELETE ON agent_type_version FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_agent_promotion_evidence_immutable BEFORE UPDATE OR DELETE ON agent_promotion_evidence FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_work_item_check_change BEFORE UPDATE OR DELETE ON work_item FOR EACH ROW EXECUTE FUNCTION work_item_check_change();
CREATE TRIGGER trg_work_item_note_immutable BEFORE UPDATE OR DELETE ON work_item_note FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_work_case_check_change BEFORE UPDATE OR DELETE ON work_case FOR EACH ROW EXECUTE FUNCTION work_case_check_change();
CREATE TRIGGER trg_work_case_link_append_only BEFORE UPDATE OR DELETE ON work_case_link FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{unlinked_at}', '{}');
CREATE TRIGGER trg_document_check_row_change BEFORE UPDATE OR DELETE ON document FOR EACH ROW EXECUTE FUNCTION document_check_row_change();
CREATE TRIGGER trg_document_version_check_change BEFORE UPDATE OR DELETE ON document_version FOR EACH ROW EXECUTE FUNCTION document_version_check_change();
CREATE TRIGGER trg_document_version_check_taint BEFORE INSERT ON document_version FOR EACH ROW EXECUTE FUNCTION document_version_check_taint();
CREATE TRIGGER trg_taint_clearance_immutable BEFORE UPDATE OR DELETE ON taint_clearance FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_policy_decision_immutable BEFORE UPDATE OR DELETE ON policy_decision FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_approval_immutable BEFORE UPDATE OR DELETE ON approval FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_approval_check_plan BEFORE INSERT ON approval FOR EACH ROW EXECUTE FUNCTION approval_check_plan();
CREATE TRIGGER trg_auto_post_confirmation_immutable BEFORE UPDATE OR DELETE ON auto_post_confirmation FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_posting_intent_check_change BEFORE UPDATE OR DELETE ON posting_intent FOR EACH ROW EXECUTE FUNCTION posting_intent_check_change();
CREATE TRIGGER trg_change_proposal_execution_immutable BEFORE UPDATE OR DELETE ON change_proposal_execution FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_change_proposal_execution_item_immutable BEFORE UPDATE OR DELETE ON change_proposal_execution_item FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_policy_rule_version_append_only BEFORE UPDATE OR DELETE ON policy_rule_version FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{is_enabled}', '{shadow_evidence,shadow_evidence_outdated_by,evidence_setting_keys}', '{}');
CREATE TRIGGER trg_change_proposal_frozen BEFORE INSERT OR UPDATE OR DELETE ON change_proposal FOR EACH ROW EXECUTE FUNCTION document_check_frozen('id');
CREATE TRIGGER trg_change_proposal_item_frozen BEFORE INSERT OR UPDATE OR DELETE ON change_proposal_item FOR EACH ROW EXECUTE FUNCTION document_check_frozen('change_proposal_id');
CREATE TRIGGER trg_period_unlock_request_frozen BEFORE INSERT OR UPDATE OR DELETE ON period_unlock_request FOR EACH ROW EXECUTE FUNCTION document_check_frozen('id');
CREATE TRIGGER trg_document_line_tax_frozen BEFORE INSERT OR UPDATE OR DELETE ON document_line_tax FOR EACH ROW EXECUTE FUNCTION document_check_frozen('document_id');
CREATE TRIGGER trg_payment_frozen BEFORE INSERT OR UPDATE OR DELETE ON payment FOR EACH ROW EXECUTE FUNCTION document_check_frozen('id');
CREATE TRIGGER trg_payment_line_frozen BEFORE INSERT OR UPDATE OR DELETE ON payment_line FOR EACH ROW EXECUTE FUNCTION document_check_frozen('payment_id');
CREATE TRIGGER trg_payment_line_payment_block BEFORE INSERT OR UPDATE OF open_item_id, line_kind, payment_id ON payment_line FOR EACH ROW EXECUTE FUNCTION payment_line_check_payment_block();
CREATE TRIGGER trg_tax_line_immutable BEFORE UPDATE OR DELETE ON tax_line FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_tax_line_adjustment_immutable BEFORE UPDATE OR DELETE ON tax_line_adjustment FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
CREATE TRIGGER trg_audit_record_append_only BEFORE UPDATE OR DELETE ON audit_record FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{reason,erased_at}');
CREATE TRIGGER trg_audit_change_append_only BEFORE UPDATE OR DELETE ON audit_change FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{before,after,erased_at}');
CREATE TRIGGER trg_audit_denial_check_change BEFORE UPDATE OR DELETE ON audit_denial FOR EACH ROW EXECUTE FUNCTION audit_denial_check_change();
CREATE TRIGGER trg_attachment_check_change BEFORE UPDATE OR DELETE ON attachment FOR EACH ROW EXECUTE FUNCTION attachment_check_change();
CREATE TRIGGER trg_bank_statement_line_append_only BEFORE UPDATE OR DELETE ON bank_statement_line FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{match_state,ignore_reason,matched_document_id,proposed_document_id,proposal_score,match_parameters_hash,match_function_version,match_parameter_set_version_id,match_parameter_state,match_is_tied,match_basis,suggested_reference_tokens,suggested_payer_name_text,suggested_stable_payer_token,suggested_purpose,suggestion_agent_run_id}', '{}', '{description,counterparty_name,counterparty_account_number,suggested_payer_name_text}');
CREATE TRIGGER trg_bank_statement_line_check_match BEFORE INSERT OR UPDATE ON bank_statement_line FOR EACH ROW EXECUTE FUNCTION bank_statement_line_check_match();
CREATE TRIGGER trg_bank_statement_append_only BEFORE UPDATE OR DELETE ON bank_statement FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{}');
CREATE CONSTRAINT TRIGGER trg_bank_statement_balance AFTER INSERT ON bank_statement DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION bank_statement_check_balance();
CREATE CONSTRAINT TRIGGER trg_bank_statement_line_balance AFTER INSERT ON bank_statement_line DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION bank_statement_check_balance();

-- ===== Document actors [documents] (ADR-0055 rules 1, 7; ADR-0017 rule 16; platform review 17) =====
-- The definition of the document-actors function that documents registers with the dispatcher: the humans who wrote a
-- version (its human actor, its on_behalf_of, the on_behalf_of of its run or origin run) and the humans who submitted
-- it. Stage eligibility (condition 5) and INV-225 read the writers; the reference implementation is this query.
CREATE FUNCTION document_actor(p_document_id uuid) RETURNS TABLE (user_account_id uuid, actor_role text)
    LANGUAGE sql STABLE AS $$
    SELECT DISTINCT u, 'writer' FROM (
        SELECT CASE WHEN v.actor_kind = 'human' THEN v.actor_id END AS u FROM document_version v WHERE v.document_id = p_document_id
        UNION ALL SELECT v.on_behalf_of_id FROM document_version v WHERE v.document_id = p_document_id
        UNION ALL SELECT r.on_behalf_of_id FROM document_version v JOIN agent_run r ON r.id IN (v.agent_run_id, v.origin_agent_run_id)
                   WHERE v.document_id = p_document_id) w
     WHERE u IS NOT NULL
    UNION
    SELECT DISTINCT u, 'submitter' FROM (
        SELECT CASE WHEN p.actor_kind = 'human' THEN p.actor_id END AS u FROM policy_decision p WHERE p.document_id = p_document_id AND p.action = 'submit'
        UNION ALL SELECT p.on_behalf_of_id FROM policy_decision p WHERE p.document_id = p_document_id AND p.action = 'submit') s
     WHERE u IS NOT NULL
$$;

-- ===== Partitions and row-level security (ADR-0006 rules 22-23; ADR-0022 rule 8; ADR-0017 rule 19) =====
-- The daily job of ADR-0022 creates monthly partitions three months ahead; the default partition catches the rest
-- (ADR-0038 rule 6). Partitions are named <table>_<yyyy>_<mm> (ADR-0004 rule 16); the default is <table>_default.
DO $$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY['outbox_event', 'audit_record', 'audit_change', 'agent_run_step'] LOOP
        EXECUTE format('CREATE TABLE %I PARTITION OF %I DEFAULT', v_table || '_default', v_table);
    END LOOP;
END
$$;
-- rls_v1 as ADR-0022 rule 8 describes it: the company policy, compared as text and failing closed; null-company rows
-- only under the setting value installation; and the read-only company_ids policy for registered cross-company queries.
DO $$
DECLARE
    v_table     text;
    v_nullable  text[] := ARRAY['outbox_event', 'event_delivery', 'audit_record', 'audit_change', 'audit_denial', 'agent_budget_usage'];
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'work_item', 'work_item_link', 'work_item_note', 'work_case', 'work_case_link', 'agent_type_setting', 'agent_run', 'agent_run_step', 'agent_budget_usage',
        'approval_procedure', 'policy_rule', 'policy_rule_version', 'numbering_configuration', 'numbering_series', 'document',
        'document_version', 'taint_clearance', 'policy_decision', 'approval', 'auto_post_confirmation', 'period_unlock_request',
        'posting_intent', 'change_proposal', 'change_proposal_item', 'change_proposal_execution', 'change_proposal_execution_item',
        'outbox_event', 'event_delivery', 'audit_record', 'audit_change', 'audit_denial', 'attachment', 'attachment_link',
        'document_line_tax', 'tax_line', 'tax_line_adjustment', 'agent_promotion_evidence', 'money_account', 'bank_statement',
        'bank_statement_line', 'payment', 'payment_line', 'open_item_collection', 'payment_method_money_account'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', v_table);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', v_table);
        IF v_table = ANY (v_nullable) THEN
            EXECUTE format('CREATE POLICY company_policy ON %I USING (company_id::text = current_setting(''nativeflows.company_id'', true)'
                           ' OR (company_id IS NULL AND current_setting(''nativeflows.company_id'', true) = ''installation''))', v_table);
        ELSE
            EXECUTE format('CREATE POLICY company_policy ON %I USING (company_id::text = current_setting(''nativeflows.company_id'', true))', v_table);
        END IF;
        EXECUTE format('CREATE POLICY company_ids_policy ON %I FOR SELECT USING (company_id::text = ANY (string_to_array(current_setting(''nativeflows.company_ids'', true), '','')))', v_table);
    END LOOP;
END
$$;
-- The company's barcode registry (DS-20, ADR-0061 rule 9): the number of a barcoded document is registered in upper case
-- when it is set, so it is unique across every barcode type of the company.
CREATE TRIGGER trg_document_register AFTER INSERT OR UPDATE OF number, is_barcoded OR DELETE ON document
    FOR EACH ROW EXECUTE FUNCTION barcode_register('document', 'number', 'id');
