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
    recorded_at          timestamptz NOT NULL,
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
    recorded_at          timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, shared_role_id) REFERENCES role (company_id, id),
    CONSTRAINT ck_list_variant_shapes CHECK (jsonb_typeof(filters) = 'object' AND jsonb_typeof(columns) = 'array'
        AND jsonb_typeof(sort) = 'array' AND jsonb_typeof(grouping) = 'array' AND jsonb_array_length(columns) <= 40)
);
CREATE UNIQUE INDEX ux_list_variant_name ON list_variant (company_id, query_name, owner_user_id, coalesce(shared_role_id, owner_user_id), lower(name)) WHERE state = 'active';
CREATE UNIQUE INDEX ux_list_variant_shared_name ON list_variant (company_id, query_name, shared_role_id, lower(name)) WHERE state = 'active' AND shared_role_id IS NOT NULL;
CREATE UNIQUE INDEX ux_list_variant_default_personal ON list_variant (company_id, query_name, owner_user_id) WHERE state = 'active' AND is_default AND shared_role_id IS NULL;
CREATE UNIQUE INDEX ux_list_variant_default_shared ON list_variant (company_id, query_name, shared_role_id) WHERE state = 'active' AND is_default AND shared_role_id IS NOT NULL;

-- ===== Row-level security (ADR-0017 rule 19; the rls_v1 helper of ADR-0022 rule 8, as DS-05-platform.sql) =====
DO $$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY['assist_request', 'list_variant'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', v_table);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', v_table);
        EXECUTE format('CREATE POLICY company_policy ON %I USING (company_id::text = current_setting(''nativeflows.company_id'', true))', v_table);
        EXECUTE format('CREATE POLICY company_ids_policy ON %I FOR SELECT USING (company_id::text = ANY (string_to_array(current_setting(''nativeflows.company_ids'', true), '','')))', v_table);
    END LOOP;
END
$$;
