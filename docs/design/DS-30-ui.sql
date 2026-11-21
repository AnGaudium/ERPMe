-- DS-30 UI: DDL draft for the company data of ADR-0077 (UI floorplans, annotation vocabulary and embedded agent). PostgreSQL 18.
-- assist_request is owned by agents (layer 5; ADR-0077 rule 14); list_variant is owned by registry (layer 2; ADR-0077 rule 10a).
-- Loaded after DS-05-platform.sql (agent_run) and DS-15 (user_account, role) by the design lab's load_all.py
-- (docs/reviews/2026-11-14-design-validation). The ADRs win if this file disagrees.
-- Conventions of DS-20 and DS-05-platform: tables in schema nativeflows, keys inline, references between company tables
-- composite on (company_id, id), UUIDv7 IDs from context.new_id, no ID defaults, recorded_at on every row
-- (ADR-0007 rule 9); every table carries company_id, FORCE ROW LEVEL SECURITY and the company policy of ADR-0017
-- rule 19 (last section). Filters, columns and context are JSON validated by the command against the query's schema.

-- ===== Assist requests [agents] (ADR-0077 rules 13, 14) =====
CREATE TABLE assist_request (                              -- the subject of an assistant run (scope kind subject); an act run starts tainted (ADR-0077 rule 13) [agents]
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    requested_by_user_id uuid NOT NULL REFERENCES user_account (id),
    purpose              text NOT NULL CONSTRAINT ck_assist_request_purpose CHECK (purpose IN ('ask', 'act', 'resolve_command', 'resolve_filter')),
    request_text         text CONSTRAINT ck_assist_request_text CHECK (length(btrim(request_text)) BETWEEN 1 AND 2000),   -- personal; null once erased
    language             text NOT NULL,                        -- IETF language tag of the request (ADR-0050 rule 13)
    floorplan            text NOT NULL CONSTRAINT ck_assist_request_floorplan CHECK (floorplan IN ('list_report', 'object_page', 'edit_form',
                             'worklist', 'overview', 'plan_panel', 'approval_view') OR floorplan ~ '^custom:[a-z][a-z0-9_]*$'),
    context_subject_table text,                                -- the record the panel was scoped to, if any
    context_subject_id   uuid,
    selected_table       text,                                 -- the table of the selected rows
    selected_ids         uuid[] NOT NULL DEFAULT '{}' CONSTRAINT ck_assist_request_selected CHECK (cardinality(selected_ids) <= 100),
    active_filters       jsonb,                                -- the list's filters as sent to its query
    previous_request_id  uuid,                                 -- a follow-up names a previous request of the same person (key below; ADR-0078 rule 11)
    agent_run_id         uuid,                                 -- the run that answered; null until StartAgentRun binds it
    state                text NOT NULL DEFAULT 'open' CONSTRAINT ck_assist_request_state CHECK (state IN ('open', 'answered', 'failed')),
    answer               jsonb,                                -- answer handles and record IDs (ask), proposed invocation (resolve_command), structured filter (resolve_filter)
    failure_reason       text CONSTRAINT ck_assist_request_failure_reason CHECK (failure_reason IN ('budget_exceeded', 'time_exceeded', 'output_invalid',
                             'provider_unavailable', 'crashed', 'denials_repeated', 'canceled', 'out_of_scope')),
    requested_at         timestamptz NOT NULL,
    answered_at          timestamptz,
    erased_at            timestamptz,                          -- request text blanked by retention or erasure
    recorded_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, requested_by_user_id, id),
    FOREIGN KEY (company_id, agent_run_id) REFERENCES agent_run (company_id, id),
    FOREIGN KEY (company_id, requested_by_user_id, previous_request_id) REFERENCES assist_request (company_id, requested_by_user_id, id),
    CONSTRAINT ck_assist_request_context CHECK ((context_subject_table IS NULL) = (context_subject_id IS NULL)),
    CONSTRAINT ck_assist_request_selected_table CHECK ((cardinality(selected_ids) = 0) = (selected_table IS NULL)),
    CONSTRAINT ck_assist_request_closed CHECK ((state = 'open') = (answered_at IS NULL)
        AND (state = 'failed') = (failure_reason IS NOT NULL)
        AND (state = 'answered' OR answer IS NULL)),
    CONSTRAINT ck_assist_request_erased CHECK (erased_at IS NULL OR request_text IS NULL),
    CONSTRAINT ck_assist_request_text_present CHECK (erased_at IS NOT NULL OR request_text IS NOT NULL)
);
CREATE INDEX ix_assist_request_requested_by_user_id ON assist_request (requested_by_user_id);

-- ===== List variants [registry] (ADR-0077 rule 10a) =====
CREATE TABLE list_variant (                                -- a saved view of one List<Noun> query, personal or shared with a role [registry]
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    query_name           text NOT NULL CONSTRAINT ck_list_variant_query CHECK (query_name ~ '^List[A-Z][A-Za-z0-9]*$'),
    name                 text NOT NULL CONSTRAINT ck_list_variant_name CHECK (length(btrim(name)) BETWEEN 1 AND 80),
    owner_user_id        uuid NOT NULL REFERENCES user_account (id),   -- the creator; edits a personal variant
    shared_role_id       uuid,                                 -- null: personal; set: shared with the holders of this role
    filters              jsonb NOT NULL DEFAULT '{}',
    columns              jsonb NOT NULL DEFAULT '[]',          -- result field names in display order
    sort                 jsonb NOT NULL DEFAULT '[]',          -- [{field, direction}]
    grouping             jsonb NOT NULL DEFAULT '[]',          -- result field names
    is_default           boolean NOT NULL DEFAULT false,       -- the owner's (personal) or the role's (shared) default for the query
    state                text NOT NULL DEFAULT 'active' CONSTRAINT ck_list_variant_state CHECK (state IN ('active', 'deleted')),
    recorded_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, shared_role_id) REFERENCES role (company_id, id),
    CONSTRAINT ck_list_variant_shapes CHECK (jsonb_typeof(filters) = 'object' AND jsonb_typeof(columns) = 'array'
        AND jsonb_typeof(sort) = 'array' AND jsonb_typeof(grouping) = 'array' AND jsonb_array_length(columns) <= 40)
);
CREATE UNIQUE INDEX ux_list_variant_name ON list_variant (company_id, query_name, owner_user_id, coalesce(shared_role_id, owner_user_id), lower(name)) WHERE state = 'active';
CREATE UNIQUE INDEX ux_list_variant_shared_name ON list_variant (company_id, query_name, shared_role_id, lower(name)) WHERE state = 'active' AND shared_role_id IS NOT NULL;
CREATE UNIQUE INDEX ux_list_variant_default_personal ON list_variant (company_id, query_name, owner_user_id) WHERE state = 'active' AND is_default AND shared_role_id IS NULL;
CREATE UNIQUE INDEX ux_list_variant_default_shared ON list_variant (company_id, query_name, shared_role_id) WHERE state = 'active' AND is_default AND shared_role_id IS NOT NULL;

-- ===== recorded_at on insert and update; TRUNCATE refused (ADR-0007 rules 9, 16 and their notes) =====
-- Every table of this file has recorded_at timestamptz NOT NULL DEFAULT now(). The DO block attaches the trigger
-- trg_<table>_set_recorded_at (function set_recorded_at) to every table of v_tables: BEFORE INSERT OR UPDATE on tables
-- updated in place, BEFORE INSERT on the append-only tables of v_append_only. recorded_at is so the instant of the last
-- write, set by the system and never taken from a client (ADR-0007 rule 9 and its notes; S2 adversarial review S2).
-- Append-only tables are those whose guard trigger refuses every update outside an erasure, and pure logs.
-- Row guards without UPDATE OF on in-place tables sort before set_recorded_at, so they compare rows before it runs; a
-- BEFORE INSERT trigger whose function reads NEW.recorded_at sorts after it, so it sees the system's value.
-- TRUNCATE skips row triggers and row-level security, so every table with company_id, every append-only table and every
-- table with a BEFORE DELETE guard, unless it has a TRUNCATE trigger of its own, is listed in v_refuse_truncate (default
-- partitions with their parent) and gets trg_<table>_refuse_truncate (BEFORE TRUNCATE, function refuse_truncate; S2
-- adversarial review N4; S2 schema review R6-N2). Retention drops partitions and never truncates (ADR-0017 rule 19 note).
-- Lab gen_overview.py --check compares this section with what schema_phase_b.py writes from the table definitions and
-- triggers of the design files. The functions are defined in every file because the labs load subsets.
CREATE OR REPLACE FUNCTION set_recorded_at() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    NEW.recorded_at := now();
    RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION refuse_truncate() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    RAISE EXCEPTION '% is never truncated (company, append-only or guarded rows)', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
END $$;
DO $$
DECLARE
    v_tables            text[] := ARRAY['assist_request', 'list_variant'];
    v_append_only       text[] := ARRAY[]::text[];
    v_refuse_truncate   text[] := ARRAY['assist_request', 'list_variant']::text[];
    v_table             text;
BEGIN
    FOREACH v_table IN ARRAY v_tables LOOP
        CONTINUE WHEN to_regclass(v_table) IS NULL;
        EXECUTE format('CREATE OR REPLACE TRIGGER %I BEFORE ' || CASE WHEN v_table = ANY (v_append_only) THEN 'INSERT' ELSE 'INSERT OR UPDATE' END
                       || ' ON %I FOR EACH ROW EXECUTE FUNCTION set_recorded_at()', 'trg_' || v_table || '_set_recorded_at', v_table);
    END LOOP;
    FOREACH v_table IN ARRAY v_refuse_truncate LOOP
        CONTINUE WHEN to_regclass(v_table) IS NULL;
        EXECUTE format('CREATE OR REPLACE TRIGGER %I BEFORE TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION refuse_truncate()',
                       'trg_' || v_table || '_refuse_truncate', v_table);
    END LOOP;
END $$;
-- ===== end of recorded_at and TRUNCATE =====

-- ===== Row-level security, generated (ADR-0017 rule 19; the rls_v1 helper of ADR-0022 rule 8) =====
-- Every table of this file with company_id gets ENABLE and FORCE ROW LEVEL SECURITY, the company policy company_policy
-- (company_id compared as text with nativeflows.company_id, failing closed) and the read-only company_ids_policy for
-- registered cross-company queries (ADR-0017 rule 19). Tables whose company_id is nullable (v_nullable) show their null
-- rows only under the setting value installation. Default partitions are listed with their parent. Exceptions are in
-- lab gen_overview.RLS_ALLOWLIST with their reasons; this file has none.
-- Lab gen_overview.py --check compares this section with what schema_phase_b.py writes.
DO $$
DECLARE
    v_tables    text[] := ARRAY['assist_request', 'list_variant'];
    v_nullable  text[] := ARRAY[]::text[];
    v_table     text;
BEGIN
    FOREACH v_table IN ARRAY v_tables LOOP
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
END $$;
-- ===== end of row-level security =====
