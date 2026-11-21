-- DS-28 settings: DDL draft for the settings registry and its values (ADR-0063 rules 1-4) and the extension point
-- registry (ADR-0063 rule 19). Named after DS-28 (policy and configuration).
-- A file of its own, so the settings tables load and change apart from DS-05-platform.sql and the configuration
-- artifacts of DS-28-34-configuration-artifacts.sql.
-- PostgreSQL 18. Loaded with every other design/*.sql file by load_all.py (docs/reviews/2026-11-14-design-validation,
-- t24_settings.py with --load). The ADRs win if this file disagrees.
-- Conventions of DS-20, DS-15 and DS-05: tables in schema nativeflows, domains in types; IDs are UUIDv7 from context.new_id,
-- no ID defaults; references between company tables are composite on (company_id, id); recorded_at on every row.
-- setting_definition, extension_point, setting_preset and setting_preset_item are installation data written by the
-- registry at startup (like agent_type),
-- without company_id and without row-level security; application roles get SELECT only on them, so no command or trigger
-- path can rewrite a definition. setting_value holds company rows and, with company_id null, the
-- installation values; the last section writes out its row-level security with the installation exception of rls_v1
-- (ADR-0022 rule 8; ADR-0017 rule 19), and those of company_setup_acknowledgement (ADR-0067 rule 8) and module_activation.
-- Referenced tables defined elsewhere: company (DS-20); user_account (DS-15); change_proposal (DS-05).
-- Functions of DS-05-platform.sql used here: platform_reject_change.
-- Owner module (ADR-0022 rule 2): registry owns every table here; agents and configuration read them through its contract.
-- Rules that need the registry or other tables (a loosening's direction, the scope reference naming a company record,
-- a period start, the outdated evidence) are enforced by commands and named in ADR-0063; the rules a row can hold are
-- checks here.
-- New tables follow the recorded_at convention of D13 (DS-06-universal-journal.sql header; ADR-0007 rule 16 note); the labs
-- load subsets of the design files, so this file defines the shared function itself.
CREATE OR REPLACE FUNCTION set_recorded_at() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    NEW.recorded_at := now();
    RETURN NEW;
END $$;

-- ===== Setting definitions [registry] (ADR-0063 rule 1) =====
CREATE TABLE setting_definition (                          -- installation data; one row per registered key, written at startup
    setting_key       text PRIMARY KEY CONSTRAINT ck_setting_definition_key CHECK (setting_key ~ '^([a-z][a-z0-9_]*|<[a-z][a-z0-9_]*>)(\.([a-z0-9_]+|<[a-z][a-z0-9_]*>))+$'),
    area              text NOT NULL CONSTRAINT ck_setting_definition_area CHECK (area ~ '^[a-z][a-z0-9_]*$'),
    scopes            text[] NOT NULL CONSTRAINT ck_setting_definition_scopes CHECK (cardinality(scopes) >= 1 AND scopes <@ ARRAY[
                          'installation', 'regime', 'company', 'product_category', 'money_account', 'scanner_profile', 'agent_type', 'rule_version']),
    storage           text NOT NULL CONSTRAINT ck_setting_definition_storage CHECK (storage IN (
                          'setting_value', 'regime_setting', 'agent_type_setting', 'data_processing_permission', 'rule_version', 'deployment')),
    value_type        text NOT NULL CONSTRAINT ck_setting_definition_value_type CHECK (value_type IN (
                          'boolean', 'integer', 'decimal', 'percent', 'amount', 'enum', 'code', 'code_list', 'field_list', 'object')),   -- code: one code of the table the bounds name, checked by the command (ADR-0069 rule 13)
    default_kind      text NOT NULL CONSTRAINT ck_setting_definition_default_kind CHECK (default_kind IN ('value', 'unset', 'fail_closed')),
    core_default      jsonb,                                -- the value when default_kind is value
    min_value         numeric,                              -- numeric types: the hard bounds; max null means open (rule 4)
    max_value         numeric,
    allowed_values    text[],                               -- boolean and enum: the allowed values
    direction         text NOT NULL CONSTRAINT ck_setting_definition_direction CHECK (direction IN (
                          'higher_tighter', 'lower_tighter', 'true_tighter', 'false_tighter', 'subset_tighter', 'superset_tighter', 'order', 'neutral')),
    direction_order   text[],                               -- order: values from loosest to tightest (rule 3)
    leaf_code         text NOT NULL CONSTRAINT ck_setting_definition_leaf CHECK (leaf_code ~ '^[a-z][a-z0-9_]*$'),   -- an authorization leaf, package or operator
    change_effect     text NOT NULL CONSTRAINT ck_setting_definition_change_effect CHECK (change_effect IN ('immediate', 'period_start', 'package_release', 'deployment')),
    outdates          text NOT NULL CONSTRAINT ck_setting_definition_outdates CHECK (outdates IN ('auto_post', 'promotion', 'none')),
    source            text NOT NULL,
    registry_version  text NOT NULL CONSTRAINT ck_setting_definition_registry_version CHECK (registry_version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
    recorded_at       timestamptz NOT NULL,
    CONSTRAINT ck_setting_definition_default CHECK ((default_kind = 'value') = (core_default IS NOT NULL)),
    CONSTRAINT ck_setting_definition_numeric CHECK ((value_type IN ('integer', 'decimal', 'percent', 'amount')) = (min_value IS NOT NULL)
        AND (max_value IS NULL OR min_value <= max_value)),
    CONSTRAINT ck_setting_definition_allowed CHECK ((value_type IN ('boolean', 'enum')) = (allowed_values IS NOT NULL)
        AND (allowed_values IS NULL OR cardinality(allowed_values) >= 1)
        AND (value_type <> 'boolean' OR allowed_values <@ ARRAY['true', 'false'])),
    -- a core default lies within the bounds (ADR-0063 rule 1)
    CONSTRAINT ck_setting_definition_default_in_bounds CHECK (core_default IS NULL OR CASE
        WHEN value_type IN ('integer', 'decimal', 'percent', 'amount') THEN jsonb_typeof(core_default) = 'number'
            AND (core_default #>> '{}')::numeric >= min_value AND (max_value IS NULL OR (core_default #>> '{}')::numeric <= max_value)
            AND (value_type <> 'integer' OR (core_default #>> '{}')::numeric = trunc((core_default #>> '{}')::numeric))
        WHEN value_type = 'boolean' THEN jsonb_typeof(core_default) = 'boolean' AND (core_default #>> '{}') = ANY (allowed_values)
        WHEN value_type = 'enum' THEN jsonb_typeof(core_default) = 'string' AND (core_default #>> '{}') = ANY (allowed_values)
        WHEN value_type = 'code' THEN jsonb_typeof(core_default) = 'string'
        WHEN value_type IN ('code_list', 'field_list') THEN jsonb_typeof(core_default) = 'array'
        ELSE jsonb_typeof(core_default) = 'object' END),
    CONSTRAINT ck_setting_definition_order CHECK ((direction = 'order') = (direction_order IS NOT NULL)
        AND (direction_order IS NULL OR (value_type = 'enum' AND allowed_values <@ direction_order))),
    CONSTRAINT ck_setting_definition_direction_type CHECK (CASE direction
        WHEN 'higher_tighter' THEN value_type IN ('integer', 'decimal', 'percent', 'amount')
        WHEN 'lower_tighter' THEN value_type IN ('integer', 'decimal', 'percent', 'amount')
        WHEN 'true_tighter' THEN value_type = 'boolean'
        WHEN 'false_tighter' THEN value_type = 'boolean'
        WHEN 'subset_tighter' THEN value_type IN ('code_list', 'field_list')
        WHEN 'superset_tighter' THEN value_type IN ('code_list', 'field_list')
        ELSE true END),
    -- fail-closed keys are regime keys (rule 1); storage names where a key's non-company values live, while company-held values
    -- of every key, company regime options included, live in setting_value (rule 2)
    CONSTRAINT ck_setting_definition_fail_closed CHECK (default_kind <> 'fail_closed' OR 'regime' = ANY (scopes)),
    CONSTRAINT ck_setting_definition_effect CHECK ((change_effect = 'package_release') = (storage = 'regime_setting' AND NOT ('company' = ANY (scopes)))
        AND (change_effect <> 'deployment' OR storage = 'deployment'))
);

-- ===== Operating presets and setup acknowledgements [registry] (ADR-0067 rules 2-9) =====
-- A preset is a named, versioned bundle of items: parameters entered when applying, registry settings at company scope,
-- policy rule templates, company settings with their own commands, and setup defaults for new records. Applying one runs
-- the ordinary commands; no business code reads a preset code (ADR-0067 rule 1). That a setting item names a registered
-- company-scope key stored in setting_value, with outdates none and a value within its bounds, and that standard covers the
-- other presets' keys, is checked by the registry at startup (INV-802); the rows hold the shape.
CREATE TABLE setting_preset (                              -- installation data; one row per preset version, written at startup
    preset_code          text NOT NULL CONSTRAINT ck_setting_preset_code CHECK (preset_code ~ '^[a-z][a-z0-9_]*$'),
    preset_version       integer NOT NULL CONSTRAINT ck_setting_preset_version CHECK (preset_version >= 1),
    registry_version     text NOT NULL CONSTRAINT ck_setting_preset_registry_version CHECK (registry_version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
    recorded_at          timestamptz NOT NULL,
    PRIMARY KEY (preset_code, preset_version)
);
CREATE TABLE setting_preset_item (                         -- installation data; one row per preset version, kind and key
    preset_code          text NOT NULL,
    preset_version       integer NOT NULL,
    item_kind            text NOT NULL CONSTRAINT ck_setting_preset_item_kind CHECK (item_kind IN (
                             'parameter', 'setting', 'policy_rule', 'command_setting', 'record_default')),
    item_key             text NOT NULL CONSTRAINT ck_setting_preset_item_key CHECK (item_key ~ '^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$'),
    value                jsonb,                                -- the item's value; null for a parameter and for a setting filled by one
    parameter_ref        text,                                 -- a setting filled by a parameter of the same preset version
    parameter_value_type text CONSTRAINT ck_setting_preset_item_parameter_type CHECK (parameter_value_type IN ('integer', 'decimal', 'percent', 'amount')),
    parameter_min        numeric,                              -- a parameter's bounds, within the bounds of every key it fills
    parameter_max        numeric,
    recorded_at          timestamptz NOT NULL,
    PRIMARY KEY (preset_code, preset_version, item_kind, item_key),
    FOREIGN KEY (preset_code, preset_version) REFERENCES setting_preset (preset_code, preset_version),
    CONSTRAINT ck_setting_preset_item_parameter CHECK ((item_kind = 'parameter') = (parameter_value_type IS NOT NULL AND parameter_min IS NOT NULL)
        AND (parameter_max IS NULL OR parameter_min <= parameter_max)),
    CONSTRAINT ck_setting_preset_item_value CHECK (CASE item_kind
        WHEN 'parameter' THEN value IS NULL AND parameter_ref IS NULL
        WHEN 'setting' THEN (value IS NULL) <> (parameter_ref IS NULL)
        ELSE value IS NOT NULL AND parameter_ref IS NULL END),
    -- a preset never lifts a non-human baseline or lets a non-human post (ADR-0067 rule 3; ADR-0043 rule 7)
    CONSTRAINT ck_setting_preset_item_policy_rule CHECK (item_kind <> 'policy_rule'
        OR (jsonb_typeof(value) = 'object' AND value ->> 'effect' IN ('require_approval', 'require_human_post', 'deny')))
);
-- The owner's acknowledgement of the implementer who may set loosenings without a second approver before go-live
-- (ADR-0067 rules 8-9). Never deleted; only revoked_at and revoked_by_user_id are set, once.
CREATE TABLE company_setup_acknowledgement (               -- company data
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    owner_user_id        uuid NOT NULL REFERENCES user_account (id),   -- holds an assignment of the owner role template (checked by the command)
    implementer_user_id  uuid NOT NULL REFERENCES user_account (id),   -- may be the owner
    reason               text NOT NULL CONSTRAINT ck_company_setup_acknowledgement_reason CHECK (length(btrim(reason)) > 0),
    acknowledged_at      timestamptz NOT NULL,
    revoked_at           timestamptz,
    revoked_by_user_id   uuid REFERENCES user_account (id),
    recorded_at          timestamptz NOT NULL,
    UNIQUE (company_id, id),
    CONSTRAINT ck_company_setup_acknowledgement_revoked CHECK ((revoked_at IS NULL) = (revoked_by_user_id IS NULL)
        AND (revoked_at IS NULL OR revoked_at >= acknowledged_at))
);
CREATE FUNCTION company_setup_acknowledgement_guard() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    IF TG_OP = 'DELETE' OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
       OR (NEW.id, NEW.company_id, NEW.owner_user_id, NEW.implementer_user_id, NEW.reason, NEW.acknowledged_at, NEW.recorded_at)
          IS DISTINCT FROM (OLD.id, OLD.company_id, OLD.owner_user_id, OLD.implementer_user_id, OLD.reason, OLD.acknowledged_at, OLD.recorded_at) THEN
        RAISE EXCEPTION 'company_setup_acknowledgement is only revoked, once (ADR-0067 rule 8)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_company_setup_acknowledgement_guard BEFORE UPDATE OR DELETE ON company_setup_acknowledgement
    FOR EACH ROW EXECUTE FUNCTION company_setup_acknowledgement_guard();

-- ===== Setting values [registry] (ADR-0063 rules 2-4) =====
-- Append-only: a change is a new row, effective from its date; the value in force for a key, scope, scope reference and
-- placeholder values is the row with the latest effective_from on or before the date, the latest recorded among equals.
-- The row copies the definition's type, bounds, allowed values and direction; the trigger setting_value_check_insert below
-- ties every copy to setting_definition, checks the scope and the placeholder keys, refuses a value looser than the
-- installation value in force, derives the replaced value itself (filling it when absent, refusing a different one) and
-- derives change_kind from the direction and that value, so a loosening needs a proposal whatever label or replaced value
-- the row carries. Left to the command and the invariants: that the proposal was approved and executed (INV-701), that
-- effective_from is not backdated or off a period start (INV-702), and that a scope reference names a record of the company.
CREATE TABLE setting_value (                               -- company data (installation values with company_id null); never updated or deleted
    id                    uuid PRIMARY KEY,
    company_id            uuid REFERENCES company (id),
    setting_key           text NOT NULL REFERENCES setting_definition (setting_key),
    scope_kind            text NOT NULL CONSTRAINT ck_setting_value_scope_kind CHECK (scope_kind IN (
                              'installation', 'company', 'product_category', 'money_account', 'scanner_profile', 'agent_type')),
    scope_ref             text NOT NULL DEFAULT '',            -- the record's id, or a code (scanner profile, agent type); empty for company and installation
    placeholder_values    jsonb NOT NULL DEFAULT '{}' CONSTRAINT ck_setting_value_placeholders CHECK (jsonb_typeof(placeholder_values) = 'object'),   -- e.g. {"agent_type": "quotation", "kind": "inbound_message_matched"}
    value_type            text NOT NULL CONSTRAINT ck_setting_value_value_type CHECK (value_type IN (
                              'boolean', 'integer', 'decimal', 'percent', 'amount', 'enum', 'code', 'code_list', 'field_list', 'object')),   -- code: one code of the table the bounds name, checked by the command (ADR-0069 rule 13)
    value                 jsonb NOT NULL,
    min_value             numeric,                              -- copies of the definition, checked by the trigger
    max_value             numeric,
    allowed_values        text[],
    direction             text NOT NULL,
    direction_order       text[],
    replaced_value        jsonb,                                -- the value in force this row replaces, derived by the trigger: the row for the same scope, else the company row, else the core default; null only where there was none
    change_kind           text NOT NULL CONSTRAINT ck_setting_value_change_kind CHECK (change_kind IN ('tighten', 'loosen', 'neutral')),   -- derived by the trigger
    reason                text NOT NULL CONSTRAINT ck_setting_value_reason CHECK (length(btrim(reason)) > 0),
    effective_from        date NOT NULL,
    changed_by_user_id    uuid NOT NULL REFERENCES user_account (id),   -- the person who made the change, submitted the loosening, or (installation) the operator named in the deployment change
    change_proposal_id    uuid,                                 -- the executed proposal of a loosening
    approved_by_user_id   uuid REFERENCES user_account (id),    -- for an installation loosening: the second operator who approved the deployment change
    setup_acknowledgement_id uuid,                             -- a loosening set before go-live under the owner's acknowledgement, without a proposal (ADR-0067 rule 9)
    preset_code           text,                                 -- the operating preset whose application wrote the row (ADR-0067 rule 4); never read to decide anything
    preset_version        integer,
    registry_version      text NOT NULL CONSTRAINT ck_setting_value_registry_version CHECK (registry_version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
    recorded_at           timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, change_proposal_id) REFERENCES change_proposal (company_id, id),
    FOREIGN KEY (company_id, setup_acknowledgement_id) REFERENCES company_setup_acknowledgement (company_id, id),
    FOREIGN KEY (preset_code, preset_version) REFERENCES setting_preset (preset_code, preset_version),
    CONSTRAINT ck_setting_value_preset CHECK ((preset_code IS NULL) = (preset_version IS NULL)),
    CONSTRAINT ck_setting_value_installation CHECK ((scope_kind = 'installation') = (company_id IS NULL)),
    CONSTRAINT ck_setting_value_scope_ref CHECK ((scope_kind IN ('installation', 'company')) = (scope_ref = '')),
    -- a loosening is executed from an approved proposal (an installation value: from the operators' approved change), approved
    -- by someone other than its submitter (rule 3), or, before go-live, set under the owner's setup acknowledgement with no
    -- proposal (ADR-0067 rule 9; the trigger checks the acknowledgement and the setup phase)
    CONSTRAINT ck_setting_value_loosen CHECK (change_kind <> 'loosen' OR ((change_proposal_id IS NOT NULL OR company_id IS NULL)
        AND approved_by_user_id IS NOT NULL AND approved_by_user_id <> changed_by_user_id AND setup_acknowledgement_id IS NULL)
        OR (setup_acknowledgement_id IS NOT NULL AND company_id IS NOT NULL AND change_proposal_id IS NULL AND approved_by_user_id IS NULL)),
    CONSTRAINT ck_setting_value_setup_loosen_only CHECK (setup_acknowledgement_id IS NULL OR change_kind = 'loosen'),
    CONSTRAINT ck_setting_value_numeric CHECK ((value_type IN ('integer', 'decimal', 'percent', 'amount')) = (min_value IS NOT NULL)
        AND (max_value IS NULL OR min_value <= max_value)),
    CONSTRAINT ck_setting_value_allowed CHECK ((value_type IN ('boolean', 'enum')) = (allowed_values IS NOT NULL)),
    -- setting_out_of_bounds, held by the database (rule 4)
    CONSTRAINT ck_setting_value_in_bounds CHECK (CASE
        WHEN value_type IN ('integer', 'decimal', 'percent', 'amount') THEN jsonb_typeof(value) = 'number'
            AND (value #>> '{}')::numeric >= min_value AND (max_value IS NULL OR (value #>> '{}')::numeric <= max_value)
            AND (value_type <> 'integer' OR (value #>> '{}')::numeric = trunc((value #>> '{}')::numeric))
        WHEN value_type = 'boolean' THEN jsonb_typeof(value) = 'boolean' AND (value #>> '{}') = ANY (allowed_values)
        WHEN value_type = 'enum' THEN jsonb_typeof(value) = 'string' AND (value #>> '{}') = ANY (allowed_values)
        WHEN value_type = 'code' THEN jsonb_typeof(value) = 'string'
        WHEN value_type IN ('code_list', 'field_list') THEN jsonb_typeof(value) = 'array'
        ELSE jsonb_typeof(value) = 'object' END)
);
CREATE INDEX ix_setting_value_lookup ON setting_value (company_id, setting_key, scope_kind, scope_ref, placeholder_values, effective_from DESC, recorded_at DESC);

-- ===== Extension points [registry] (ADR-0063 rule 19) =====
CREATE TABLE extension_point (                             -- installation data; declared by a module, written at startup; no runtime in Phase 1
    code                       text PRIMARY KEY CONSTRAINT ck_extension_point_code CHECK (code ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'),
    module                     text NOT NULL CONSTRAINT ck_extension_point_module CHECK (module ~ '^[a-z][a-z0-9_]*$'),
    -- never an approval, posting, rights or settings decision (hard lock of rule 19)
    decision_kind              text NOT NULL CONSTRAINT ck_extension_point_decision_kind CHECK (decision_kind IN ('score', 'classification', 'derivation', 'validation')),
    input_schema               jsonb NOT NULL CONSTRAINT ck_extension_point_input_schema CHECK (jsonb_typeof(input_schema) = 'object'),
    output_schema              jsonb NOT NULL CONSTRAINT ck_extension_point_output_schema CHECK (jsonb_typeof(output_schema) = 'object'),
    code_default               jsonb NOT NULL,                  -- returned on a trap, exhausted fuel or a timeout
    max_fuel_ceiling           bigint NOT NULL CONSTRAINT ck_extension_point_fuel CHECK (max_fuel_ceiling BETWEEN 100000 AND 50000000),
    max_memory_bytes_ceiling   bigint NOT NULL CONSTRAINT ck_extension_point_memory CHECK (max_memory_bytes_ceiling BETWEEN 1048576 AND 16777216),
    deadline_ms_ceiling        integer NOT NULL CONSTRAINT ck_extension_point_deadline CHECK (deadline_ms_ceiling BETWEEN 5 AND 250),
    is_gate_feeding            boolean NOT NULL DEFAULT false,   -- whether the output may feed a gate
    registry_version           text NOT NULL CONSTRAINT ck_extension_point_registry_version CHECK (registry_version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
    recorded_at                timestamptz NOT NULL
);

-- ===== Module activation [registry] (ADR-0022 rule 2 note; ADR-0052 note, CRM-only deployment profile) =====
-- Which modules of the one product run for a company. A deployment profile, such as CRM-only, is a set of these rows that
-- CreateCompany writes from the chosen operating preset (ADR-0067); a module with no row, or with is_active false, is not
-- activated for the company. Written by ActivateModule and DeactivateModule (registry, human_only, change-tracked,
-- ADR-0038 rule 3); the command refuses to deactivate a module that has postings or open documents (module_in_use) and
-- checks the module code against the registry. Commands read it to decide what applies, e.g. the partner commands require
-- the profile accounts while ledger is activated (ADR-0015 rule 11 note; INV-38).
CREATE TABLE module_activation (                           -- company data, updated in place
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    module       text NOT NULL CONSTRAINT ck_module_activation_module CHECK (module ~ '^[a-z][a-z0-9_]*$'),   -- a module of ADR-0022 rule 2
    is_active    boolean NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, module)
);
CREATE TRIGGER trg_module_activation_set_recorded_at BEFORE UPDATE ON module_activation
    FOR EACH ROW EXECUTE FUNCTION set_recorded_at();

-- ===== Guards =====
-- Values are a history: never updated or deleted (rule 2).
CREATE TRIGGER trg_setting_value_immutable BEFORE UPDATE OR DELETE ON setting_value
    FOR EACH ROW EXECUTE FUNCTION platform_reject_change();
-- Whether value a is looser than value b under a direction (rule 3). Lists compare as sets.
CREATE FUNCTION setting_is_looser(p_direction text, p_order text[], a jsonb, b jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE p_direction
        WHEN 'higher_tighter' THEN (a #>> '{}')::numeric < (b #>> '{}')::numeric
        WHEN 'lower_tighter' THEN (a #>> '{}')::numeric > (b #>> '{}')::numeric
        WHEN 'true_tighter' THEN (a #>> '{}') = 'false' AND (b #>> '{}') = 'true'
        WHEN 'false_tighter' THEN (a #>> '{}') = 'true' AND (b #>> '{}') = 'false'
        WHEN 'subset_tighter' THEN NOT (b @> a)
        WHEN 'superset_tighter' THEN NOT (a @> b)
        WHEN 'order' THEN array_position(p_order, a #>> '{}') < array_position(p_order, b #>> '{}')
        ELSE false END
$$;
-- The installation value in force for a key and placeholder values on a date (rule 1), for get_setting and the trigger
-- below. Installation rows stay visible only under nativeflows.company_id = 'installation' (ADR-0017 rule 19); this function
-- returns only the key, the value and its effective date, never the operators' accounts or reasons. In the pattern of
-- nativeflows_claim (ADR-0017 rules 18-19): it is owned by a no-login role nativeflows_setting_reader whose only policy on
-- setting_value sees rows with company_id null, and no role gains BYPASSRLS; the role, its policy and the ownership are
-- created with the database roles, not here. The roles step also revokes EXECUTE on it from PUBLIC and grants it to the
-- application roles. Like the trigger function below, it names its tables with the schema and pins
-- search_path = nativeflows, pg_temp, so a temporary table cannot stand in for setting_value or setting_definition; application
-- roles get no TEMPORARY privilege on the database either (ADR-0017 rule 18 note).
CREATE FUNCTION setting_installation_value(p_key text, p_placeholder_values jsonb, p_date date)
    RETURNS TABLE (setting_key text, value jsonb, effective_from date)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = nativeflows, pg_temp AS $$
    SELECT v.setting_key, v.value, v.effective_from FROM nativeflows.setting_value v
     WHERE v.company_id IS NULL AND v.setting_key = p_key AND v.placeholder_values = p_placeholder_values AND v.effective_from <= p_date
     ORDER BY v.effective_from DESC, v.recorded_at DESC LIMIT 1
$$;
-- Ties a value to its definition and derives its change kind (rules 2-4): type, bounds, allowed values and direction equal
-- the definition's (copied when left null); the scope is one the definition declares; a value looser than the installation
-- value in force for the key is refused (the installation value is a maximum); the replaced value is the value in force for
-- the same company, key, scope, scope reference and placeholder values (rule 2's order), else the company row for a narrower
-- scope, else the core default, and a given replaced value must equal it (JSON null included); change_kind is loosen when
-- the value is looser than the replaced value, tighten when tighter, otherwise neutral, and a given label must agree.
-- The installation maximum checked here is a convenience at write time: a company row dated before a later installation row
-- passes it, and the control is get_setting, which applies the maximum in force at read time (backdating is INV-702).
-- Changes are serialized per company and key: the trigger takes a transaction-level advisory lock on a 64-bit hash of
-- (company, key) before it reads the definition and the value in force, so two concurrent changes of one key cannot both
-- compare with the same replaced value. It needs no privilege on setting_definition beyond SELECT (a row lock would need
-- UPDATE), and transaction-level advisory locks are allowed on trigger paths (ADR-0022 rule 13 note).
CREATE FUNCTION setting_value_check_insert() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
DECLARE
    d        nativeflows.setting_definition%ROWTYPE;
    v_max    jsonb;
    v_kind   text;
    v_in     jsonb;
    v_found  boolean := false;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('setting_value:' || coalesce(NEW.company_id::text, 'installation') || ':' || NEW.setting_key, 0));
    SELECT * INTO d FROM nativeflows.setting_definition WHERE setting_key = NEW.setting_key;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'setting_scope_invalid: key % is not registered', NEW.setting_key USING ERRCODE = 'check_violation';
    END IF;
    IF NOT (NEW.scope_kind = ANY (d.scopes)) THEN
        RAISE EXCEPTION 'setting_scope_invalid: % is not a scope of %', NEW.scope_kind, NEW.setting_key USING ERRCODE = 'check_violation';
    END IF;
    IF (SELECT coalesce(array_agg(m[1] ORDER BY m[1]), '{}') FROM regexp_matches(NEW.setting_key, '<([a-z][a-z0-9_]*)>', 'g') AS m)
       IS DISTINCT FROM (SELECT coalesce(array_agg(k ORDER BY k), '{}') FROM jsonb_object_keys(NEW.placeholder_values) AS k) THEN
        RAISE EXCEPTION 'setting_scope_invalid: the placeholder values % do not name the placeholders of %', NEW.placeholder_values, NEW.setting_key USING ERRCODE = 'check_violation';
    END IF;
    NEW.value_type := coalesce(NEW.value_type, d.value_type);
    NEW.direction := coalesce(NEW.direction, d.direction);
    IF NEW.min_value IS NULL AND NEW.max_value IS NULL AND NEW.allowed_values IS NULL AND NEW.direction_order IS NULL THEN
        NEW.min_value := d.min_value; NEW.max_value := d.max_value; NEW.allowed_values := d.allowed_values; NEW.direction_order := d.direction_order;
    END IF;
    IF NEW.value_type IS DISTINCT FROM d.value_type OR NEW.min_value IS DISTINCT FROM d.min_value OR NEW.max_value IS DISTINCT FROM d.max_value
       OR NEW.allowed_values IS DISTINCT FROM d.allowed_values OR NEW.direction IS DISTINCT FROM d.direction
       OR NEW.direction_order IS DISTINCT FROM d.direction_order THEN
        RAISE EXCEPTION 'setting_out_of_bounds: the copied type, bounds or direction of % differ from its definition', NEW.setting_key USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.scope_kind <> 'installation' AND 'installation' = ANY (d.scopes) THEN
        SELECT i.value INTO v_max FROM nativeflows.setting_installation_value(NEW.setting_key, NEW.placeholder_values, NEW.effective_from) AS i;
        IF v_max IS NOT NULL AND nativeflows.setting_is_looser(d.direction, d.direction_order, NEW.value, v_max) THEN
            RAISE EXCEPTION 'setting_out_of_bounds: % is looser than the installation value % of %', NEW.value, v_max, NEW.setting_key USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    SELECT v.value, true INTO v_in, v_found FROM nativeflows.setting_value v
     WHERE v.company_id IS NOT DISTINCT FROM NEW.company_id AND v.setting_key = NEW.setting_key AND v.scope_kind = NEW.scope_kind
       AND v.scope_ref = NEW.scope_ref AND v.placeholder_values = NEW.placeholder_values AND v.effective_from <= NEW.effective_from
     ORDER BY v.effective_from DESC, v.recorded_at DESC LIMIT 1;
    IF NOT coalesce(v_found, false) AND NEW.scope_kind NOT IN ('company', 'installation') THEN
        SELECT v.value, true INTO v_in, v_found FROM nativeflows.setting_value v
         WHERE v.company_id = NEW.company_id AND v.setting_key = NEW.setting_key AND v.scope_kind = 'company'
           AND v.placeholder_values = NEW.placeholder_values AND v.effective_from <= NEW.effective_from
         ORDER BY v.effective_from DESC, v.recorded_at DESC LIMIT 1;
    END IF;
    IF NOT coalesce(v_found, false) THEN
        v_in := d.core_default;
    END IF;
    IF NEW.replaced_value IS NULL THEN
        NEW.replaced_value := v_in;
    ELSIF NEW.replaced_value IS DISTINCT FROM v_in THEN
        RAISE EXCEPTION 'setting_value replaced_value % is not the value in force %', NEW.replaced_value, v_in USING ERRCODE = 'check_violation';
    END IF;
    v_kind := CASE
        WHEN NEW.replaced_value IS NULL OR d.direction = 'neutral' OR NEW.value = NEW.replaced_value THEN 'neutral'
        WHEN nativeflows.setting_is_looser(d.direction, d.direction_order, NEW.value, NEW.replaced_value) THEN 'loosen'
        WHEN nativeflows.setting_is_looser(d.direction, d.direction_order, NEW.replaced_value, NEW.value) THEN 'tighten'
        ELSE 'neutral' END;
    IF NEW.change_kind IS NOT NULL AND NEW.change_kind <> v_kind THEN
        RAISE EXCEPTION 'setting_value change_kind % differs from the derived %', NEW.change_kind, v_kind USING ERRCODE = 'check_violation';
    END IF;
    NEW.change_kind := v_kind;
    -- ADR-0067 rule 9: a setup-path loosening needs an active acknowledgement of the same company naming the person as its
    -- implementer, a key that outdates no evidence, a scope other than installation, and a company still in its setup phase.
    -- No auto_post.* key (cash.auto_post.* included) is on the setup path, even when it outdates nothing, such as a mode: every
    -- gateway loosening needs a second person (ADR-0067 rule 9; ADR-0065 rule 8).
    -- The command read the company row FOR SHARE first (rule 7), so the first operating posting cannot overlap it.
    IF NEW.setup_acknowledgement_id IS NOT NULL AND v_kind = 'loosen' THEN
        IF d.outdates <> 'none' OR NEW.scope_kind = 'installation' OR NEW.setting_key ~ '(^|\.)auto_post\.' THEN
            RAISE EXCEPTION 'setup_acknowledgement_invalid: % is not on the setup path', NEW.setting_key USING ERRCODE = 'check_violation';
        END IF;
        PERFORM 1 FROM nativeflows.company_setup_acknowledgement a
         WHERE a.company_id = NEW.company_id AND a.id = NEW.setup_acknowledgement_id AND a.revoked_at IS NULL
           AND a.implementer_user_id = NEW.changed_by_user_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'setup_acknowledgement_invalid: no active acknowledgement names % as implementer', NEW.changed_by_user_id USING ERRCODE = 'check_violation';
        END IF;
        IF EXISTS (SELECT 1 FROM nativeflows.company c WHERE c.id = NEW.company_id AND c.first_operating_posting_at IS NOT NULL) THEN
            RAISE EXCEPTION 'setup_phase_closed: the company has posted outside the migration period' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_setting_value_check_insert BEFORE INSERT ON setting_value
    FOR EACH ROW EXECUTE FUNCTION setting_value_check_insert();

-- ===== Row-level security (ADR-0017 rule 19; ADR-0022 rule 8) =====
-- rls_v1: the company policy, compared as text and failing closed; null-company (installation) rows only under the setting
-- value installation; and the read-only company_ids policy for registered cross-company queries. Company sessions read
-- installation maxima only through setting_installation_value (ADR-0063 rule 1).
ALTER TABLE setting_value ENABLE ROW LEVEL SECURITY;
ALTER TABLE setting_value FORCE ROW LEVEL SECURITY;
CREATE POLICY company_policy ON setting_value USING (company_id::text = current_setting('nativeflows.company_id', true)
    OR (company_id IS NULL AND current_setting('nativeflows.company_id', true) = 'installation'));
CREATE POLICY company_ids_policy ON setting_value FOR SELECT USING (company_id::text = ANY (string_to_array(current_setting('nativeflows.company_ids', true), ',')));
ALTER TABLE company_setup_acknowledgement ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_setup_acknowledgement FORCE ROW LEVEL SECURITY;
CREATE POLICY company_policy ON company_setup_acknowledgement USING (company_id::text = current_setting('nativeflows.company_id', true));
CREATE POLICY company_ids_policy ON company_setup_acknowledgement FOR SELECT USING (company_id::text = ANY (string_to_array(current_setting('nativeflows.company_ids', true), ',')));
ALTER TABLE module_activation ENABLE ROW LEVEL SECURITY;
ALTER TABLE module_activation FORCE ROW LEVEL SECURITY;
CREATE POLICY company_policy ON module_activation USING (company_id::text = current_setting('nativeflows.company_id', true));
CREATE POLICY company_ids_policy ON module_activation FOR SELECT USING (company_id::text = ANY (string_to_array(current_setting('nativeflows.company_ids', true), ',')));
