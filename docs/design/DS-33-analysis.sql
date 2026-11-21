-- DS-33 analysis: DDL draft for the company data of ADR-0060 (agent-assisted reporting and analysis). PostgreSQL 18.
-- Owner module: query (layer 5; ADR-0060 rule 1). The analysis catalog itself is code with the core catalogs
-- catalogs/analysis-measures.csv and catalogs/analysis-dimensions.csv, and the fact views live in schema query
-- (ADR-0050 rule 42); this file holds only the tables: questions with their answers, saved analyses and KPIs with their
-- versions, and analysis examples (the verified question and plan pairs, versioned).
-- Loaded after DS-05-platform.sql (agent_run) and DS-15 (user_account) by the design lab's load_all.py
-- (docs/reviews/2026-11-14-design-validation, t18_analysis.py). The ADRs win if this file disagrees.
-- Conventions of DS-20 and DS-05-platform: tables in schema nativeflows, keys inline, references between company tables
-- composite on (company_id, id), UUIDv7 IDs from context.new_id, no ID defaults, recorded_at on every row
-- (ADR-0007 rule 9); every table carries company_id, FORCE ROW LEVEL SECURITY and the company policy of ADR-0017
-- rule 19 (last section). Plans are JSON validated by the plan model of ADR-0060 rule 7 in the command; the database
-- holds hash formats, states and the shapes a row can hold. Rules that need the catalog or other rows (the badge, a
-- trigger question that clashes with an example, small-company mode for a self-release) are commands' and named in
-- ADR-0060. analysis_plan_hash is named apart from ADR-0008's command plan_hash (ADR-0060 rule 9).
-- Data labels (ADR-0060 rule 21): question_text, feedback_note, trigger_questions and the example questions are
-- personal; the stored result holds member keys, never labels; narrative plans hold claim codes, roles and handles only, never text (ADR-0060 rule 23). No column is untrusted, because only signed-in people of
-- the company write them (CreateAnalysisQuestion is human_only). Normalized questions are Unicode case-folded by the
-- command (query.contract.normalize_question); the database checks only their shape, since lower() differs from
-- casefold for a few scripts.

-- ===== Questions and answers [query] (ADR-0060 rules 21-24) =====
CREATE TABLE analysis_question (                           -- the subject of an analysis run (scope kind subject)
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL REFERENCES company (id),
    asked_by_user_id           uuid NOT NULL REFERENCES user_account (id),
    question_text              text CONSTRAINT ck_analysis_question_text CHECK (length(btrim(question_text)) BETWEEN 1 AND 2000),   -- personal; null once erased
    language                   text NOT NULL,              -- IETF language tag of the question (ADR-0050 rule 13)
    agent_run_id               uuid,                       -- the run that answered; null until StartAgentRun binds it
    state                      text NOT NULL DEFAULT 'open' CONSTRAINT ck_analysis_question_state CHECK (state IN ('open', 'answered', 'abstained', 'failed')),
    outcome                    text CONSTRAINT ck_analysis_question_outcome CHECK (outcome IN ('answered', 'ambiguous_term', 'ambiguous_member', 'out_of_coverage',
                                   'not_permitted', 'data_not_ready', 'too_broad', 'not_applicable', 'routing_blocked')),
    failure_reason             text CONSTRAINT ck_analysis_question_failure_reason CHECK (failure_reason IN ('budget_exceeded', 'time_exceeded', 'output_invalid',
                                   'provider_unavailable', 'resume_diverged', 'crashed', 'denials_repeated', 'canceled')),   -- the stopped run's outcome (rule 21)
    plan                       jsonb,                      -- canonical analysis plan (ADR-0060 rules 7, 9)
    analysis_plan_hash         text CONSTRAINT ck_analysis_question_plan_hash CHECK (analysis_plan_hash ~ '^[0-9a-f]{64}$'),
    analysis_resolved_hash     text CONSTRAINT ck_analysis_question_resolved_hash CHECK (analysis_resolved_hash ~ '^[0-9a-f]{64}$'),
    catalog_version            text,
    badge                      text CONSTRAINT ck_analysis_question_badge CHECK (badge IN ('verified', 'generated')),
    saved_analysis_version_id  uuid,                       -- the verified version a hit came from (rule 22, D2)
    analysis_example_id        uuid,                       -- or the verified example
    key_facts                  jsonb,                      -- the key facts code renders: template codes and cells (rule 23)
    narrative_plan             jsonb,                      -- the model's narrative plan: claim codes, roles and handles only (rule 23)
    narrative_dropped_steps    jsonb,                      -- steps whose precondition failed on the served cells, with claim and reason
    clarification_options      jsonb,                      -- ambiguous_term: 2-4 catalog codes; ambiguous_member: member keys of one lookup (rule 24)
    result                     jsonb,                      -- the envelope's rows and cells as shown, with member keys and no labels (rule 21)
    as_of                      timestamptz,                -- the snapshot of the result (rule 13)
    feedback                   text CONSTRAINT ck_analysis_question_feedback CHECK (feedback IN ('helpful', 'wrong')),
    feedback_note              text,                       -- personal
    feedback_at                timestamptz,
    asked_at                   timestamptz NOT NULL,
    answered_at                timestamptz,                -- when the run closed the question, whatever its state
    erased_at                  timestamptz,                -- question text and note blanked by retention or erasure (rule 21)
    recorded_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, agent_run_id) REFERENCES agent_run (company_id, id),
    -- states: open has nothing; answered has the answered outcome; abstained has an abstention, not_applicable or
    -- routing_blocked; failed has no outcome but the stopped run's reason
    CONSTRAINT ck_analysis_question_closed CHECK ((state = 'open') = (answered_at IS NULL)
        AND (state IN ('open', 'failed')) = (outcome IS NULL)
        AND (state = 'failed') = (failure_reason IS NOT NULL)
        AND (state = 'answered') = (outcome IS NOT DISTINCT FROM 'answered')
        AND (state = 'abstained') = coalesce(outcome IN ('ambiguous_term', 'ambiguous_member', 'out_of_coverage', 'not_permitted', 'data_not_ready',
                                                         'too_broad', 'not_applicable', 'routing_blocked'), false)),
    -- only an answer carries a plan, badge, result, key facts and narrative, and an answer carries all but the narrative
    CONSTRAINT ck_analysis_question_answer CHECK (
        (outcome IS DISTINCT FROM 'answered' OR (plan IS NOT NULL AND analysis_plan_hash IS NOT NULL AND analysis_resolved_hash IS NOT NULL
             AND badge IS NOT NULL AND result IS NOT NULL AND key_facts IS NOT NULL AND as_of IS NOT NULL AND catalog_version IS NOT NULL))
        AND (outcome IS NOT DISTINCT FROM 'answered' OR (badge IS NULL AND result IS NULL AND key_facts IS NULL AND narrative_plan IS NULL AND narrative_dropped_steps IS NULL))),
    CONSTRAINT ck_analysis_question_clarification CHECK ((clarification_options IS NOT NULL) = coalesce(outcome IN ('ambiguous_term', 'ambiguous_member'), false)),
    CONSTRAINT ck_analysis_question_verified_source CHECK (badge IS DISTINCT FROM 'verified'
        OR num_nonnulls(saved_analysis_version_id, analysis_example_id) = 1),
    -- the narrative plan of rule 23: an array of at most 8 steps; each step an object with a string claim and, when present,
    -- an object of facts (whose saved references may hold an object of members); every key at every depth a short identifier
    -- and every leaf a string, so no free text, number or other type can be stored (INV-413)
    CONSTRAINT ck_analysis_question_narrative_plan CHECK (narrative_plan IS NULL OR (jsonb_typeof(narrative_plan) = 'array' AND jsonb_array_length(narrative_plan) <= 8
        AND NOT jsonb_path_exists(narrative_plan, '$[*] ? (@.type() != "object" || !(exists(@.claim)) || !(@.claim.type() == "string"))')
        AND NOT jsonb_path_exists(narrative_plan, '$[*] ? (exists(@.facts) && !(@.facts.type() == "object"))')
        AND NOT jsonb_path_exists(narrative_plan, '$[*].facts.*.members ? (!(@.type() == "object"))')
        AND NOT jsonb_path_exists(narrative_plan, 'strict $[*] ? (@.type() == "object").keyvalue() ? (@.key != "claim" && @.key != "facts")')
        AND NOT jsonb_path_exists(narrative_plan, 'strict $.** ? (@.type() == "object").keyvalue() ? (!(@.key like_regex "^[A-Za-z0-9_:~.-]{1,64}$"))')
        AND NOT jsonb_path_exists(narrative_plan, 'strict $.** ? (@.type() == "number" || @.type() == "boolean" || @.type() == "null")')
        AND NOT jsonb_path_exists(narrative_plan, 'strict $.** ? (@.type() == "string" && !(@ like_regex "^[A-Za-z0-9_:~.-]{1,64}$"))'))),
    CONSTRAINT ck_analysis_question_feedback_shape CHECK ((feedback IS NULL) = (feedback_at IS NULL)
        AND (feedback_note IS NULL OR feedback IS NOT NULL) AND (feedback IS NULL OR state <> 'open')),
    CONSTRAINT ck_analysis_question_erased CHECK ((erased_at IS NULL) = (question_text IS NOT NULL) AND (erased_at IS NULL OR feedback_note IS NULL))
);
CREATE INDEX ix_analysis_question_asked_by ON analysis_question (company_id, asked_by_user_id, asked_at);
CREATE INDEX ix_analysis_question_agent_run ON analysis_question (company_id, agent_run_id);
CREATE INDEX ix_analysis_question_saved_analysis_version ON analysis_question (company_id, saved_analysis_version_id);
CREATE INDEX ix_analysis_question_analysis_example ON analysis_question (company_id, analysis_example_id);

-- ===== Saved analyses and KPIs [query] (ADR-0060 rules 26-27) =====
CREATE TABLE saved_analysis (                              -- company data, change-tracked
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    code              text NOT NULL CONSTRAINT ck_saved_analysis_code CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    name              text NOT NULL CONSTRAINT ck_saved_analysis_name CHECK (length(btrim(name)) > 0),
    kind              text NOT NULL CONSTRAINT ck_saved_analysis_kind CHECK (kind IN ('analysis', 'kpi')),
    state             text NOT NULL DEFAULT 'draft' CONSTRAINT ck_saved_analysis_state CHECK (state IN ('draft', 'verified', 'retired')),
    visibility        text NOT NULL DEFAULT 'private' CONSTRAINT ck_saved_analysis_visibility CHECK (visibility IN ('private', 'company')),
    latest_version    integer NOT NULL CONSTRAINT ck_saved_analysis_latest_version CHECK (latest_version >= 1),
    verified_version  integer,                             -- the released version in force (ReleaseSavedAnalysis); key below
    owner_user_id     uuid NOT NULL REFERENCES user_account (id),
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, kind),
    CONSTRAINT uq_saved_analysis_code UNIQUE (company_id, code),
    -- verified means a released version is in force; a draft has none; a retired analysis keeps its last one for history
    CONSTRAINT ck_saved_analysis_verified CHECK ((state <> 'verified' OR verified_version IS NOT NULL)
        AND (state <> 'draft' OR verified_version IS NULL)
        AND (verified_version IS NULL OR verified_version BETWEEN 1 AND latest_version))
);
CREATE TABLE saved_analysis_version (                      -- immutable once released; drafts are replaced by new versions
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL REFERENCES company (id),
    saved_analysis_id      uuid NOT NULL,
    kind                   text NOT NULL,                  -- copied from the saved analysis; the key below keeps them equal
    version                integer NOT NULL CONSTRAINT ck_saved_analysis_version_version CHECK (version >= 1),
    plan                   jsonb NOT NULL,
    analysis_plan_hash     text NOT NULL CONSTRAINT ck_saved_analysis_version_plan_hash CHECK (analysis_plan_hash ~ '^[0-9a-f]{64}$'),
    definition_hashes      jsonb NOT NULL,                 -- {catalog object code: definition hash} of every object the plan names (rule 9)
    catalog_version        text NOT NULL,
    presentation           jsonb NOT NULL DEFAULT '{}',    -- chart kind, layout, column order
    open_filters           text[] NOT NULL DEFAULT '{}',   -- dimension codes a viewer may filter without losing the badge
    trigger_questions      text[] NOT NULL DEFAULT '{}',   -- personal; normalized questions answered by this version without a model
    narrative_plan         jsonb,                          -- a person's narrative plan from the claim catalog; facts by role or by the full member coordinate (rule 26)
    kpi_measure            text,                           -- KPI fields (rule 27): one measure of the plan, entered by people
    kpi_time_grain         text CONSTRAINT ck_saved_analysis_version_kpi_time_grain CHECK (kpi_time_grain IN ('day', 'week', 'month', 'quarter', 'year', 'posting_period', 'fiscal_year')),
    favorable_direction    text CONSTRAINT ck_saved_analysis_version_favorable_direction CHECK (favorable_direction IN ('up', 'down')),
    target_value           numeric,                        -- in the measure's basis
    warning_threshold      numeric,
    critical_threshold     numeric,
    created_by_user_id     uuid NOT NULL REFERENCES user_account (id),
    origin_agent_run_id    uuid,                           -- set when an analysis run drafted it through a change proposal
    released_by_user_id    uuid REFERENCES user_account (id),
    released_at            timestamptz,
    is_self_released       boolean NOT NULL DEFAULT false, -- released by its author, allowed only in small-company mode (rule 26)
    recorded_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    CONSTRAINT uq_saved_analysis_version_version UNIQUE (company_id, saved_analysis_id, version),
    FOREIGN KEY (company_id, saved_analysis_id, kind) REFERENCES saved_analysis (company_id, id, kind),
    FOREIGN KEY (company_id, origin_agent_run_id) REFERENCES agent_run (company_id, id),
    CONSTRAINT ck_saved_analysis_version_released CHECK ((released_by_user_id IS NULL) = (released_at IS NULL)
        AND is_self_released = coalesce(released_by_user_id = created_by_user_id, false)),
    -- a KPI version holds its measure, grain, direction and target; an analysis version holds none of them
    CONSTRAINT ck_saved_analysis_version_kpi CHECK (
        (kind = 'kpi') = (kpi_measure IS NOT NULL)
        AND num_nulls(kpi_measure, kpi_time_grain, favorable_direction, target_value) IN (0, 4)
        AND (kind = 'kpi' OR (warning_threshold IS NULL AND critical_threshold IS NULL))),
    -- an agent drafts no KPI (rule 26)
    CONSTRAINT ck_saved_analysis_version_kpi_by_people CHECK (kind = 'analysis' OR origin_agent_run_id IS NULL),
    -- thresholds lie on the unfavourable side of the target, critical beyond warning
    CONSTRAINT ck_saved_analysis_version_thresholds CHECK (
        (favorable_direction IS DISTINCT FROM 'up' OR ((warning_threshold IS NULL OR warning_threshold <= target_value)
            AND (critical_threshold IS NULL OR critical_threshold <= coalesce(warning_threshold, target_value))))
        AND (favorable_direction IS DISTINCT FROM 'down' OR ((warning_threshold IS NULL OR warning_threshold >= target_value)
            AND (critical_threshold IS NULL OR critical_threshold >= coalesce(warning_threshold, target_value))))),
    -- the narrative plan of rule 23: an array of at most 8 steps; each step an object with a string claim and, when present,
    -- an object of facts (whose saved references may hold an object of members); every key at every depth a short identifier
    -- and every leaf a string, so no free text, number or other type can be stored (INV-413)
    CONSTRAINT ck_saved_analysis_version_narrative_plan CHECK (narrative_plan IS NULL OR (jsonb_typeof(narrative_plan) = 'array' AND jsonb_array_length(narrative_plan) <= 8
        AND NOT jsonb_path_exists(narrative_plan, '$[*] ? (@.type() != "object" || !(exists(@.claim)) || !(@.claim.type() == "string"))')
        AND NOT jsonb_path_exists(narrative_plan, '$[*] ? (exists(@.facts) && !(@.facts.type() == "object"))')
        AND NOT jsonb_path_exists(narrative_plan, '$[*].facts.*.members ? (!(@.type() == "object"))')
        AND NOT jsonb_path_exists(narrative_plan, 'strict $[*] ? (@.type() == "object").keyvalue() ? (@.key != "claim" && @.key != "facts")')
        AND NOT jsonb_path_exists(narrative_plan, 'strict $.** ? (@.type() == "object").keyvalue() ? (!(@.key like_regex "^[A-Za-z0-9_:~.-]{1,64}$"))')
        AND NOT jsonb_path_exists(narrative_plan, 'strict $.** ? (@.type() == "number" || @.type() == "boolean" || @.type() == "null")')
        AND NOT jsonb_path_exists(narrative_plan, 'strict $.** ? (@.type() == "string" && !(@ like_regex "^[A-Za-z0-9_:~.-]{1,64}$"))')))
);
CREATE INDEX ix_saved_analysis_version_origin_agent_run ON saved_analysis_version (company_id, origin_agent_run_id);

-- ===== Analysis examples: verified question and plan pairs, versioned [query] (ADR-0060 rules 25, 28-29) =====
CREATE TABLE analysis_example (                            -- company data, change-tracked; immutable once released
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL REFERENCES company (id),
    question_text               text NOT NULL CONSTRAINT ck_analysis_example_text CHECK (length(btrim(question_text)) BETWEEN 1 AND 2000),   -- personal
    normalized_question         text NOT NULL,             -- query.contract.normalize_question (rule 22, D2)
    language                    text NOT NULL,
    version                     integer NOT NULL DEFAULT 1 CONSTRAINT ck_analysis_example_version CHECK (version >= 1),
    supersedes_example_id       uuid,                      -- the verified example a new version replaces (rule 28)
    flow                        text NOT NULL CONSTRAINT ck_analysis_example_flow CHECK (flow IN ('sales', 'purchasing', 'inventory', 'production', 'open_items', 'ledger')),
    expected_outcome            text NOT NULL CONSTRAINT ck_analysis_example_expected_outcome CHECK (expected_outcome IN ('answered', 'ambiguous_term', 'ambiguous_member',
                                    'out_of_coverage', 'not_permitted', 'data_not_ready', 'too_broad')),
    plan                        jsonb,
    analysis_plan_hash          text CONSTRAINT ck_analysis_example_plan_hash CHECK (analysis_plan_hash ~ '^[0-9a-f]{64}$'),
    catalog_version             text,
    state                       text NOT NULL DEFAULT 'draft' CONSTRAINT ck_analysis_example_state CHECK (state IN ('draft', 'verified', 'retired')),
    source                      text NOT NULL CONSTRAINT ck_analysis_example_source CHECK (source IN ('person', 'feedback', 'agent_proposal')),
    origin_analysis_question_id uuid,
    created_by_user_id          uuid NOT NULL REFERENCES user_account (id),
    released_by_user_id         uuid REFERENCES user_account (id),
    released_at                 timestamptz,
    is_self_released            boolean NOT NULL DEFAULT false,
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    CONSTRAINT uq_analysis_example_version UNIQUE (company_id, normalized_question, language, version),
    FOREIGN KEY (company_id, origin_analysis_question_id) REFERENCES analysis_question (company_id, id),
    FOREIGN KEY (company_id, supersedes_example_id) REFERENCES analysis_example (company_id, id),
    -- an answerable example carries its plan; an abstention example carries none
    CONSTRAINT ck_analysis_example_plan CHECK ((expected_outcome = 'answered') = (plan IS NOT NULL)
        AND (plan IS NULL) = (analysis_plan_hash IS NULL) AND (plan IS NULL) = (catalog_version IS NULL)),
    CONSTRAINT ck_analysis_example_released CHECK ((released_by_user_id IS NULL) = (released_at IS NULL)
        AND (state <> 'verified' OR released_at IS NOT NULL)
        AND is_self_released = coalesce(released_by_user_id = created_by_user_id, false)),
    CONSTRAINT ck_analysis_example_versions CHECK ((version = 1) = (supersedes_example_id IS NULL)),
    CONSTRAINT ck_analysis_example_feedback_source CHECK ((source = 'feedback') = (origin_analysis_question_id IS NOT NULL)),
    CONSTRAINT ck_analysis_example_normalized CHECK (length(normalized_question) > 0 AND normalized_question = btrim(normalized_question)
        AND normalized_question !~ '\s\s')
);
-- One verified example per normalized question and language, so an exact match is never ambiguous (rule 22, D2).
CREATE UNIQUE INDEX ux_analysis_example_verified ON analysis_example (company_id, normalized_question, language) WHERE state = 'verified';
CREATE INDEX ix_analysis_example_origin_question ON analysis_example (company_id, origin_analysis_question_id);
CREATE INDEX ix_analysis_example_supersedes ON analysis_example (company_id, supersedes_example_id);

-- ===== Keys closed after their tables =====
ALTER TABLE analysis_question ADD FOREIGN KEY (company_id, saved_analysis_version_id) REFERENCES saved_analysis_version (company_id, id);
ALTER TABLE analysis_question ADD FOREIGN KEY (company_id, analysis_example_id) REFERENCES analysis_example (company_id, id);
-- The verified version in force exists (deferred: the release writes the version and the saved analysis in one command).
ALTER TABLE saved_analysis ADD CONSTRAINT fk_saved_analysis_verified_version FOREIGN KEY (company_id, id, verified_version)
    REFERENCES saved_analysis_version (company_id, saved_analysis_id, version) DEFERRABLE INITIALLY DEFERRED;

-- ===== Guards =====
-- A released saved analysis version never changes (rule 26): only the release itself may set released_by_user_id,
-- released_at and is_self_released, once, on a draft row.
CREATE FUNCTION saved_analysis_version_guard() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.released_at IS NOT NULL THEN
            RAISE EXCEPTION 'saved analysis version % is released and immutable', OLD.id USING ERRCODE = 'check_violation';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.released_at IS NOT NULL
       OR (to_jsonb(NEW) - 'released_by_user_id' - 'released_at' - 'is_self_released')
          <> (to_jsonb(OLD) - 'released_by_user_id' - 'released_at' - 'is_self_released') THEN
        RAISE EXCEPTION 'saved analysis version % is released and immutable, or only its release may change', OLD.id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_saved_analysis_version_guard BEFORE UPDATE OR DELETE ON saved_analysis_version
    FOR EACH ROW EXECUTE FUNCTION saved_analysis_version_guard();
-- A released example never changes (rule 28): a draft may change until its release; a released one may only be retired.
CREATE FUNCTION analysis_example_guard() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.released_at IS NOT NULL THEN
            RAISE EXCEPTION 'analysis example % is released and immutable', OLD.id USING ERRCODE = 'check_violation';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.released_at IS NOT NULL
       AND ((to_jsonb(NEW) - 'state') <> (to_jsonb(OLD) - 'state') OR NOT (OLD.state = 'verified' AND NEW.state IN ('verified', 'retired'))) THEN
        RAISE EXCEPTION 'analysis example % is released and immutable; it may only be retired', OLD.id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_analysis_example_guard BEFORE UPDATE OR DELETE ON analysis_example
    FOR EACH ROW EXECUTE FUNCTION analysis_example_guard();
-- A closed question is frozen (rule 21): after the run closes it, only the asker's feedback may be set, once, and retention
-- or erasure may blank the question text and the note.
CREATE FUNCTION analysis_question_guard() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state <> 'open' THEN
            RAISE EXCEPTION 'analysis question % is closed and kept', OLD.id USING ERRCODE = 'check_violation';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.state <> 'open'
       AND ((to_jsonb(NEW) - 'feedback' - 'feedback_note' - 'feedback_at' - 'question_text' - 'erased_at')
            <> (to_jsonb(OLD) - 'feedback' - 'feedback_note' - 'feedback_at' - 'question_text' - 'erased_at')
            OR (NEW.question_text IS NOT NULL AND NEW.question_text IS DISTINCT FROM OLD.question_text)
            OR (OLD.feedback IS NOT NULL AND (NEW.feedback IS DISTINCT FROM OLD.feedback OR NEW.feedback_at IS DISTINCT FROM OLD.feedback_at))) THEN
        RAISE EXCEPTION 'analysis question % is closed: only feedback and erasure may change it', OLD.id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_analysis_question_guard BEFORE UPDATE OR DELETE ON analysis_question
    FOR EACH ROW EXECUTE FUNCTION analysis_question_guard();

-- ===== recorded_at on insert and update; TRUNCATE refused (ADR-0007 rules 9, 16 and their notes) =====
-- Every table of this file has recorded_at timestamptz NOT NULL DEFAULT now(). The DO block attaches the trigger
-- trg_<table>_set_recorded_at (function set_recorded_at) to every table of v_tables: BEFORE INSERT OR UPDATE on tables
-- updated in place, BEFORE INSERT on the append-only tables of v_append_only. recorded_at is so the instant of the last
-- write, set by the system and never taken from a client (ADR-0007 rule 9 and its notes; S2 adversarial review S2).
-- Append-only tables are those whose guard trigger refuses every update outside an erasure, and pure logs.
-- Row guards without UPDATE OF on in-place tables sort before set_recorded_at, so they compare rows before it runs; a
-- BEFORE INSERT trigger whose function reads NEW.recorded_at sorts after it, so it sees the system's value.
-- TRUNCATE skips row triggers, so every append-only table and every table with a BEFORE DELETE guard, unless it has a
-- TRUNCATE trigger of its own, is listed in v_refuse_truncate (default partitions with their parent) and gets
-- trg_<table>_refuse_truncate (BEFORE TRUNCATE, function refuse_truncate; S2 adversarial review N4).
-- Lab gen_overview.py --check compares this section with what schema_phase_b.py writes from the table definitions and
-- triggers of the design files. The functions are defined in every file because the labs load subsets.
CREATE OR REPLACE FUNCTION set_recorded_at() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    NEW.recorded_at := now();
    RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION refuse_truncate() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    RAISE EXCEPTION '% is never truncated (append-only or guarded rows)', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
END $$;
DO $$
DECLARE
    v_tables            text[] := ARRAY['analysis_question', 'saved_analysis', 'saved_analysis_version', 'analysis_example'];
    v_append_only       text[] := ARRAY[]::text[];
    v_refuse_truncate   text[] := ARRAY['analysis_question', 'saved_analysis_version', 'analysis_example']::text[];
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
    v_tables    text[] := ARRAY['analysis_question', 'saved_analysis', 'saved_analysis_version', 'analysis_example'];
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
