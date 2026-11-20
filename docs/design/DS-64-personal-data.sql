-- DS-64: personal data protection core (ADR-0079). Design draft, PostgreSQL 18. The ADR wins if this file disagrees.
-- Owner module: audit (layer 2), for all five tables. The reason is ADR-0052 rule 26's for personal_data_processing_log: the
-- readers and writers sit in layers 2 to 5 (the dispatcher's masking and refusals, the LLM gateway, every module's erasure
-- hook, the retention job, exports), so the tables belong to the lowest module that all of them may import.
-- Conventions as DS-20, DS-35 and DS-63: tables in schema nativeflows, keys inline, UUIDv7 IDs from context.new_id with no ID
-- defaults, recorded_at on every row (ADR-0007 rule 9), references inside a company composite on (company_id, id).
-- Every table carries company_id, FORCE ROW LEVEL SECURITY and the generated company policy (ADR-0017 rule 19; last section).
-- user_account (DS-15) is installation data without company_id, so data_subject_state and data_erasure_entry allow a null
-- company_id for a user account subject only, and show those rows only under the setting value installation, as
-- audit_record does (DS-05-platform.sql). The lab checks this list.
-- A data subject request (DS-35, module crm) is named through document (company_id, id) only: audit is layer 2 and refers to
-- no crm table (ADR-0022 rule 2); the command checks that the document is a data subject request.
-- Append-only tables use audit_refuse_change() of DS-35-crm.sql (owner audit). The erasure exception on posted documents,
-- versions, the journal and append-only rows (ADR-0079 rule 7) is written with the ledger and document DDL in session S2.
-- The erasure journal outside the database holds one line per data_erasure_entry with the same id (ADR-0079 rule 7);
-- ReapplyErasures, a step of the restore procedure, re-inserts a missing entry with that id (rule 14).
-- Nothing here holds a personal value: subjects and rows are named by table and ID, columns by name.

-- ===== Data subject state [audit] (ADR-0079 rules 4-6) =====
CREATE TABLE data_subject_state (                          -- [audit] ADR-0079 rules 4-5; one row per subject that is or was blocked; a later block updates the same row
    id                       uuid PRIMARY KEY,
    company_id               uuid REFERENCES company (id),        -- null only for a user account subject (installation data)
    subject_table            text NOT NULL CONSTRAINT ck_data_subject_state_subject_table CHECK (subject_table IN ('partner', 'contact', 'user_account')),
    subject_id               uuid NOT NULL,
    state                    text NOT NULL CONSTRAINT ck_data_subject_state_state CHECK (state IN ('blocked', 'released', 'destroyed')),   -- released: ReleaseDataSubject, only from blocked (rule 5)
    cause                    text NOT NULL CONSTRAINT ck_data_subject_state_cause CHECK (cause IN ('request', 'retention')),
    blocked_at               timestamptz NOT NULL,                -- every subject is blocked first (rule 7)
    destroy_due_date         date,                                -- the latest destruction date of the subject's retention classes; null when no verified rule gives one (rule 9)
    destroyed_at             timestamptz,
    released_at              timestamptz,                         -- set by ReleaseDataSubject; cleared by a later block
    data_subject_request_id  uuid,                                -- the request document, when the cause is a request
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (subject_table, subject_id),
    FOREIGN KEY (company_id, data_subject_request_id) REFERENCES document (company_id, id),
    CONSTRAINT ck_data_subject_state_company CHECK (company_id IS NOT NULL OR subject_table = 'user_account'),
    CONSTRAINT ck_data_subject_state_destroyed CHECK ((state = 'destroyed') = (destroyed_at IS NOT NULL)),
    CONSTRAINT ck_data_subject_state_released CHECK ((state = 'released') = (released_at IS NOT NULL)),
    CONSTRAINT ck_data_subject_state_dates CHECK ((destroyed_at IS NULL OR destroyed_at >= blocked_at) AND (released_at IS NULL OR released_at >= blocked_at))
);
CREATE INDEX ix_data_subject_state_company_id_state ON data_subject_state (company_id, state);
CREATE INDEX ix_data_subject_state_destroy_due_date ON data_subject_state (destroy_due_date) WHERE state = 'blocked' AND destroy_due_date IS NOT NULL;

-- ===== Retention rules [audit] (ADR-0079 rule 9) =====
CREATE TABLE retention_rule (                              -- [audit] ADR-0079 rule 9; seeded per company from the package's rules; the core seeds none
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    retention_class          text NOT NULL CONSTRAINT ck_retention_rule_retention_class CHECK (retention_class IN ('master_data', 'accounting_document', 'crm_interaction',
                                 'message', 'agent_log', 'intake', 'audit', 'access_account', 'analysis_text', 'data_subject_request')),
    start_event              text NOT NULL CONSTRAINT ck_retention_rule_start_event CHECK (start_event IN ('record_created', 'relationship_ended', 'last_document_posted', 'fiscal_year_closed')),
    block_after_months       integer CONSTRAINT ck_retention_rule_block_after_months CHECK (block_after_months >= 0),   -- null: the class is never blocked by the job
    destroy_after_months     integer CONSTRAINT ck_retention_rule_destroy_after_months CHECK (destroy_after_months >= 0),   -- null: nothing of the class is destroyed by the job
    source                   text NOT NULL CONSTRAINT ck_retention_rule_source CHECK (source IN ('package', 'company')),   -- company: the company adjusted the package's periods
    package_rule_ref         text NOT NULL,                       -- the package rule's key, flagged as ADR-0016 rule 12 says; kept when the company adjusts
    is_verified              boolean NOT NULL DEFAULT false,      -- no destruction without a verified rule (rule 9; INV-894)
    is_adjustable            boolean NOT NULL DEFAULT false,      -- the package allows the company to change the periods
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, retention_class),
    CONSTRAINT ck_retention_rule_order CHECK (block_after_months IS NULL OR destroy_after_months IS NULL OR destroy_after_months >= block_after_months),
    CONSTRAINT ck_retention_rule_adjusted CHECK (source = 'package' OR is_adjustable)
);

-- ===== Erasure entries [audit] (ADR-0079 rule 7) =====
CREATE TABLE data_erasure_entry (                          -- [audit] ADR-0079 rule 7; one row per rewritten row; names columns, holds no values; append-only (trigger below)
    id                       uuid PRIMARY KEY,
    company_id               uuid REFERENCES company (id),        -- the target row's company; null only for a user account subject's installation rows
    subject_table            text NOT NULL CONSTRAINT ck_data_erasure_entry_subject_table CHECK (subject_table IN ('partner', 'contact', 'user_account')),
    subject_id               uuid NOT NULL,
    target_table             text NOT NULL CONSTRAINT ck_data_erasure_entry_target_table CHECK (target_table ~ '^[a-z][a-z0-9_]*$'),   -- a table of the catalog (rule 1)
    target_row_id            uuid NOT NULL,                       -- the row's id, or the first key column for a table without id (interaction_content: its key interaction_id)
    target_row_key           text[],                              -- the whole primary key in key order, for a table without an id column; IDs, numbers and hashes only
    column_names             text[] NOT NULL CONSTRAINT ck_data_erasure_entry_column_names CHECK (cardinality(column_names) > 0),   -- catalog columns of target_table
    action                   text NOT NULL CONSTRAINT ck_data_erasure_entry_action CHECK (action IN ('tokenize', 'blank', 'clear_keys', 'delete_row')),
    cause                    text NOT NULL CONSTRAINT ck_data_erasure_entry_cause CHECK (cause IN ('request', 'retention')),
    data_subject_request_id  uuid,                                -- the request document, for cause request
    command_id               uuid NOT NULL,                       -- the idempotency record of EraseDataSubject or DestroyRetainedPersonalData; no foreign key, idempotency records expire (ADR-0008 rule 19)
    executed_at              timestamptz NOT NULL,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, data_subject_request_id) REFERENCES document (company_id, id),
    CONSTRAINT ck_data_erasure_entry_company CHECK (company_id IS NOT NULL OR subject_table = 'user_account'),
    CONSTRAINT ck_data_erasure_entry_row_key CHECK (target_row_key IS NULL OR cardinality(target_row_key) > 1)
);
CREATE INDEX ix_data_erasure_entry_subject_id ON data_erasure_entry (subject_table, subject_id);
CREATE INDEX ix_data_erasure_entry_executed_at ON data_erasure_entry (executed_at);

-- ===== Read log [audit] (ADR-0079 rule 12) =====
CREATE TABLE personal_data_read_log (                      -- [audit] ADR-0079 rule 12; query name, user, field names and row count, never values; append-only (trigger below)
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    user_account_id          uuid NOT NULL REFERENCES user_account (id),   -- the accountable person: the user, the run's human or the client's accountable user (ADR-0017)
    actor_kind               text NOT NULL CONSTRAINT ck_personal_data_read_log_actor_kind CHECK (actor_kind IN ('human', 'agent', 'integration', 'system')),
    integration_client_id    uuid REFERENCES integration_client (id),
    agent_run_id             uuid,
    query_name               text NOT NULL CONSTRAINT ck_personal_data_read_log_query_name CHECK (query_name ~ '^[A-Z][A-Za-z0-9]*$'),   -- the registered query or export command
    read_kind                text NOT NULL CONSTRAINT ck_personal_data_read_log_read_kind CHECK (read_kind IN ('sensitive_field', 'blocked_subject', 'export')),
    subject_table            text CONSTRAINT ck_personal_data_read_log_subject_table CHECK (subject_table IN ('partner', 'contact', 'user_account')),
    subject_id               uuid,
    row_count                integer NOT NULL CONSTRAINT ck_personal_data_read_log_row_count CHECK (row_count >= 0),
    field_names              text[] NOT NULL DEFAULT '{}',        -- table.column of the catalog columns returned
    read_at                  timestamptz NOT NULL,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, agent_run_id) REFERENCES agent_run (company_id, id),
    CONSTRAINT ck_personal_data_read_log_subject CHECK ((subject_table IS NULL) = (subject_id IS NULL)),
    CONSTRAINT ck_personal_data_read_log_actor CHECK ((actor_kind = 'integration') = (integration_client_id IS NOT NULL)
        AND (actor_kind = 'agent') = (agent_run_id IS NOT NULL))
);
CREATE INDEX ix_personal_data_read_log_user_account_id_read_at ON personal_data_read_log (company_id, user_account_id, read_at);
CREATE INDEX ix_personal_data_read_log_subject_id ON personal_data_read_log (subject_id) WHERE subject_id IS NOT NULL;

-- ===== Breach register [audit] (ADR-0079 rule 16) =====
CREATE TABLE personal_data_breach (                        -- [audit] ADR-0079 rule 16; what an authority asks for; the case's kind is personal_data_breach (checked by the command)
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    work_case_id             uuid NOT NULL,
    discovered_at            timestamptz NOT NULL,
    occurred_from            timestamptz,
    occurred_to              timestamptz,
    categories               text[] NOT NULL DEFAULT '{}' CONSTRAINT ck_personal_data_breach_categories CHECK (categories <@ ARRAY['identity', 'contact', 'financial',
                                 'online_identifier', 'credential', 'free_text', 'snapshot']::text[]),   -- the catalog's categories
    subject_kinds            text[] NOT NULL DEFAULT '{}' CONSTRAINT ck_personal_data_breach_subject_kinds CHECK (subject_kinds <@ ARRAY['partner', 'contact', 'user',
                                 'employee', 'requester', 'other']::text[]),   -- the catalog's subject kinds
    subject_count_estimate   integer CONSTRAINT ck_personal_data_breach_subject_count_estimate CHECK (subject_count_estimate >= 0),
    containment              text CONSTRAINT ck_personal_data_breach_containment CHECK (char_length(containment) <= 4000),   -- what was done; names no person
    notification_due_at      timestamptz,                         -- from the package rule breach_notification_hours; null when no rule applies
    authority_notified_at    timestamptz,
    subjects_notified_at     timestamptz,
    state                    text NOT NULL DEFAULT 'open' CONSTRAINT ck_personal_data_breach_state CHECK (state IN ('open', 'closed')),
    closed_at                timestamptz,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (work_case_id),
    FOREIGN KEY (company_id, work_case_id) REFERENCES work_case (company_id, id),
    CONSTRAINT ck_personal_data_breach_occurred CHECK (occurred_to IS NULL OR occurred_from IS NULL OR occurred_to >= occurred_from),
    CONSTRAINT ck_personal_data_breach_closed CHECK ((state = 'closed') = (closed_at IS NOT NULL))
);
CREATE INDEX ix_personal_data_breach_open ON personal_data_breach (company_id, notification_due_at) WHERE state = 'open';

-- ===== Append-only guard [audit] (ADR-0079 rules 7, 12; the function of DS-35-crm.sql) =====
CREATE TRIGGER trg_data_erasure_entry_append_only BEFORE UPDATE OR DELETE ON data_erasure_entry FOR EACH ROW
    EXECUTE FUNCTION audit_refuse_change();
CREATE TRIGGER trg_personal_data_read_log_append_only BEFORE UPDATE OR DELETE ON personal_data_read_log FOR EACH ROW
    EXECUTE FUNCTION audit_refuse_change();

-- ===== Row-level security (ADR-0017 rule 19; the rls_v1 helper of ADR-0022 rule 8, as DS-05-platform.sql) =====
DO $$
DECLARE
    v_table     text;
    v_nullable  text[] := ARRAY['data_subject_state', 'data_erasure_entry'];
BEGIN
    FOREACH v_table IN ARRAY ARRAY['data_subject_state', 'retention_rule', 'data_erasure_entry', 'personal_data_read_log', 'personal_data_breach'] LOOP
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
