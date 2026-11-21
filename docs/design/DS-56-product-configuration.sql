-- DS-56 product configuration: DDL draft for ADR-0046 (master_data tables). PostgreSQL 18.
-- Loaded with DS-20 and DS-06 in the design lab (t06_configuration.py). The ADR wins if this file disagrees.
-- Conventions as in DS-20-master-data.sql: schema nativeflows, company_id and row-level security on every table, composite
-- keys within a company, UUIDv7 IDs without defaults. Every model row carries product_id, so its characteristics are
-- keyed to the product's product_variant_attribute rows. The production columns of ADR-0046 rules 12-13
-- (product-level bills of materials and versions, selection conditions and sizing) belong to the production DDL,
-- DS-43-54-planning-production.sql.
-- Conditions, effects, cells and defaults are canonical JSON in the grammar of ADR-0046 rules 5-7, validated at release.
-- They name characteristics and list values by code; codes never change once used (ADR-0046 rule 3).

-- ===== Configuration models [master_data] (ADR-0046 rule 4) =====
CREATE TABLE configuration_model (
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL,
    product_id  uuid NOT NULL,
    code        text NOT NULL,
    name        text NOT NULL,
    is_active   boolean NOT NULL DEFAULT true,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id, product_id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id)
);
-- One active model per product.
CREATE UNIQUE INDEX ux_configuration_model_active ON configuration_model (product_id) WHERE is_active;
CREATE TABLE configuration_model_revision (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    configuration_model_id   uuid NOT NULL,
    product_id               uuid NOT NULL,
    revision                 integer NOT NULL CONSTRAINT ck_configuration_model_revision_revision CHECK (revision > 0),
    state                    text NOT NULL DEFAULT 'draft' CONSTRAINT ck_configuration_model_revision_state CHECK (state IN ('draft', 'released')),
    start_date               date NOT NULL,
    content_hash             text,                                  -- set at release
    released_at              timestamptz,
    copy_from_revision_id    uuid,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (configuration_model_id, revision),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, product_id),
    FOREIGN KEY (company_id, configuration_model_id, product_id) REFERENCES configuration_model (company_id, id, product_id),
    FOREIGN KEY (company_id, copy_from_revision_id) REFERENCES configuration_model_revision (company_id, id),
    CONSTRAINT ck_configuration_model_revision_released CHECK ((state = 'released') = (content_hash IS NOT NULL AND released_at IS NOT NULL))
);
-- At most one draft per model (as draft_revision_exists, ADR-0033 rule 3).
CREATE UNIQUE INDEX ux_configuration_model_revision_draft ON configuration_model_revision (configuration_model_id) WHERE state = 'draft';
CREATE TABLE configuration_rule (                           -- ADR-0046 rule 6
    id                                uuid PRIMARY KEY,
    company_id                        uuid NOT NULL,
    configuration_model_revision_id   uuid NOT NULL,
    product_id                        uuid NOT NULL,
    position                          integer NOT NULL,         -- for display only; evaluation is order-independent
    kind                              text NOT NULL CONSTRAINT ck_configuration_rule_kind CHECK (kind IN ('restrict', 'set', 'require', 'forbid')),
    condition                         jsonb NOT NULL DEFAULT '{}',   -- empty: always true
    target_attribute_id               uuid,
    effect                            jsonb NOT NULL DEFAULT '{}',   -- restrict: {"values": [...]} or {"min": n, "max": n}; set: {"value": v}
    message_code                      text NOT NULL,
    recorded_at                       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (configuration_model_revision_id, position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (company_id, configuration_model_revision_id, product_id) REFERENCES configuration_model_revision (company_id, id, product_id),
    FOREIGN KEY (company_id, product_id, target_attribute_id) REFERENCES product_variant_attribute (company_id, product_id, variant_attribute_id),
    CONSTRAINT ck_configuration_rule_target CHECK ((kind = 'forbid') = (target_attribute_id IS NULL))
);
CREATE TABLE configuration_table (                          -- ADR-0046 rule 7
    id                                uuid PRIMARY KEY,
    company_id                        uuid NOT NULL,
    configuration_model_revision_id   uuid NOT NULL,
    product_id                        uuid NOT NULL,
    code                              text NOT NULL,
    recorded_at                       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (configuration_model_revision_id, code),
    UNIQUE (company_id, id, product_id),
    FOREIGN KEY (company_id, configuration_model_revision_id, product_id) REFERENCES configuration_model_revision (company_id, id, product_id)
);
CREATE TABLE configuration_table_column (
    id                      uuid PRIMARY KEY,   -- uq_configuration_table_column_key named by hand: the convention name would exceed 63 bytes (ADR-0004 rule 6)
    company_id              uuid NOT NULL,
    configuration_table_id  uuid NOT NULL,
    product_id              uuid NOT NULL,
    column_number           integer NOT NULL CONSTRAINT ck_configuration_table_column_number CHECK (column_number > 0),
    variant_attribute_id    uuid NOT NULL,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_configuration_table_column_key UNIQUE (configuration_table_id, column_number),
    UNIQUE (configuration_table_id, variant_attribute_id),
    FOREIGN KEY (company_id, configuration_table_id, product_id) REFERENCES configuration_table (company_id, id, product_id),
    FOREIGN KEY (company_id, product_id, variant_attribute_id) REFERENCES product_variant_attribute (company_id, product_id, variant_attribute_id)
);
CREATE TABLE configuration_table_row (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    configuration_table_id  uuid NOT NULL,
    product_id              uuid NOT NULL,
    row_number              integer NOT NULL,
    cells                   jsonb NOT NULL CONSTRAINT ck_configuration_table_row_cells CHECK (jsonb_typeof(cells) = 'array'),   -- by column_number: a code, a number, "*" or {"min": n, "max": n}
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_configuration_table_row_configuration_table_id_row_number UNIQUE (configuration_table_id, row_number),
    FOREIGN KEY (company_id, configuration_table_id, product_id) REFERENCES configuration_table (company_id, id, product_id)
);
CREATE TABLE configuration_default (                        -- ADR-0046 rule 8
    id                                uuid PRIMARY KEY,   -- uq_configuration_default_key named by hand: the convention name would exceed 63 bytes (ADR-0004 rule 6)
    company_id                        uuid NOT NULL,
    configuration_model_revision_id   uuid NOT NULL,
    product_id                        uuid NOT NULL,
    position                          integer NOT NULL,
    target_attribute_id               uuid NOT NULL,
    value                             jsonb NOT NULL,             -- a value code or a number
    condition                         jsonb NOT NULL DEFAULT '{}',
    recorded_at                       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_configuration_default_key UNIQUE (configuration_model_revision_id, position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (company_id, configuration_model_revision_id, product_id) REFERENCES configuration_model_revision (company_id, id, product_id),
    FOREIGN KEY (company_id, product_id, target_attribute_id) REFERENCES product_variant_attribute (company_id, product_id, variant_attribute_id)
);

-- ===== Configurations [master_data] (ADR-0046 rule 9) =====
CREATE TABLE product_configuration (                        -- immutable, content-addressed; only complete, valid configurations
    id            uuid PRIMARY KEY,
    company_id    uuid NOT NULL,
    product_id    uuid NOT NULL,
    content_hash  text NOT NULL CONSTRAINT ck_product_configuration_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    created_at    timestamptz NOT NULL,
    created_xact_id  xid8 NOT NULL DEFAULT pg_current_xact_id(),   -- the top-level transaction, also inside savepoints
    recorded_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, product_id, content_hash),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, product_id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id)
);
CREATE TABLE product_configuration_value (
    id                          uuid PRIMARY KEY,   -- uq_product_configuration_value_key named by hand: the convention name would exceed 63 bytes (ADR-0004 rule 6)
    company_id                  uuid NOT NULL,
    product_configuration_id    uuid NOT NULL,
    product_id                  uuid NOT NULL,
    variant_attribute_id        uuid NOT NULL,
    value_type                  text NOT NULL,
    variant_attribute_value_id  uuid,                             -- list values
    numeric_value               types.quantity,                   -- numbers, in both modes; value rows appear only with items (ADR-0046 rule 11)
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_product_configuration_value_key UNIQUE (product_configuration_id, variant_attribute_id),
    FOREIGN KEY (company_id, product_configuration_id, product_id) REFERENCES product_configuration (company_id, id, product_id),
    FOREIGN KEY (company_id, product_id, variant_attribute_id) REFERENCES product_variant_attribute (company_id, product_id, variant_attribute_id),
    CONSTRAINT fk_product_configuration_value_type FOREIGN KEY (company_id, variant_attribute_id, value_type) REFERENCES variant_attribute (company_id, id, value_type),
    FOREIGN KEY (company_id, variant_attribute_id, variant_attribute_value_id) REFERENCES variant_attribute_value (company_id, variant_attribute_id, id),
    CONSTRAINT ck_product_configuration_value_one CHECK ((value_type = 'list') = (variant_attribute_value_id IS NOT NULL)
                                                         AND (value_type = 'number') = (numeric_value IS NOT NULL))
);

-- ===== Number rates [master_data] (ADR-0046 rule 15) =====
CREATE TABLE price_list_characteristic_rate (
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL,
    price_list_id         uuid NOT NULL,
    product_id            uuid NOT NULL,
    variant_attribute_id  uuid NOT NULL,
    value_type            text NOT NULL DEFAULT 'number' CONSTRAINT ck_price_list_characteristic_rate_type CHECK (value_type = 'number'),
    start_date            date NOT NULL,
    end_date              date,
    rate_per_value        types.unit_price NOT NULL,              -- per inventory unit, per unit of the characteristic
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id, price_list_id) REFERENCES price_list (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    FOREIGN KEY (company_id, product_id, variant_attribute_id) REFERENCES product_variant_attribute (company_id, product_id, variant_attribute_id),
    CONSTRAINT fk_price_list_characteristic_rate_type FOREIGN KEY (company_id, variant_attribute_id, value_type) REFERENCES variant_attribute (company_id, id, value_type),
    CONSTRAINT ck_price_list_characteristic_rate_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ex_price_list_characteristic_rate_overlap EXCLUDE USING gist (
        price_list_id WITH =, product_id WITH =, variant_attribute_id WITH =, daterange(start_date, end_date, '[]') WITH &&)
);

-- ===== Immutability (ADR-0046 rules 4, 9) =====
CREATE FUNCTION configuration_revision_guard() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    IF OLD.state = 'released' THEN RAISE EXCEPTION 'revision_released'; END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_configuration_model_revision_guard BEFORE UPDATE OR DELETE ON configuration_model_revision
    FOR EACH ROW EXECUTE FUNCTION configuration_revision_guard();
CREATE FUNCTION configuration_revision_of(j jsonb) RETURNS uuid LANGUAGE sql STABLE SET search_path = nativeflows, pg_temp AS $$
    SELECT coalesce((j ->> 'configuration_model_revision_id')::uuid,
                    (SELECT t.configuration_model_revision_id FROM configuration_table t WHERE t.id = (j ->> 'configuration_table_id')::uuid))
$$;
CREATE FUNCTION configuration_revision_content_guard() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    -- an update checks the revision the row leaves as well as the one it joins
    IF TG_OP IN ('UPDATE', 'DELETE') AND (SELECT r.state FROM configuration_model_revision r WHERE r.id = configuration_revision_of(to_jsonb(OLD))) = 'released' THEN
        RAISE EXCEPTION 'revision_released';
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') AND (SELECT r.state FROM configuration_model_revision r WHERE r.id = configuration_revision_of(to_jsonb(NEW))) = 'released' THEN
        RAISE EXCEPTION 'revision_released';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_configuration_rule_guard BEFORE INSERT OR UPDATE OR DELETE ON configuration_rule
    FOR EACH ROW EXECUTE FUNCTION configuration_revision_content_guard();
CREATE TRIGGER trg_configuration_table_guard BEFORE INSERT OR UPDATE OR DELETE ON configuration_table
    FOR EACH ROW EXECUTE FUNCTION configuration_revision_content_guard();
CREATE TRIGGER trg_configuration_table_column_guard BEFORE INSERT OR UPDATE OR DELETE ON configuration_table_column
    FOR EACH ROW EXECUTE FUNCTION configuration_revision_content_guard();
CREATE TRIGGER trg_configuration_table_row_guard BEFORE INSERT OR UPDATE OR DELETE ON configuration_table_row
    FOR EACH ROW EXECUTE FUNCTION configuration_revision_content_guard();
CREATE TRIGGER trg_configuration_default_guard BEFORE INSERT OR UPDATE OR DELETE ON configuration_default
    FOR EACH ROW EXECUTE FUNCTION configuration_revision_content_guard();
CREATE FUNCTION product_configuration_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- values may be added only in the transaction that created the configuration
        IF (SELECT pc.created_xact_id FROM product_configuration pc WHERE pc.id = NEW.product_configuration_id) <> pg_current_xact_id() THEN
            RAISE EXCEPTION 'configuration_immutable';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'configuration_immutable';
END $$;
CREATE TRIGGER trg_product_configuration_immutable BEFORE UPDATE OR DELETE ON product_configuration
    FOR EACH ROW EXECUTE FUNCTION product_configuration_immutable();
CREATE TRIGGER trg_product_configuration_value_immutable BEFORE INSERT OR UPDATE OR DELETE ON product_configuration_value
    FOR EACH ROW EXECUTE FUNCTION product_configuration_immutable();

-- ===== recorded_at on insert and update; TRUNCATE refused (ADR-0007 rules 9, 16 and their notes) =====
-- Every table of this file has recorded_at timestamptz NOT NULL DEFAULT now(). The DO block attaches the trigger
-- trg_<table>_set_recorded_at (function set_recorded_at) to every table of v_tables: BEFORE INSERT OR UPDATE on tables
-- updated in place, BEFORE INSERT on the append-only tables of v_append_only. recorded_at is so the instant of the last
-- write, set by the system and never taken from a client (ADR-0007 rule 9 and its notes; S2 adversarial review S2).
-- Append-only tables are those whose guard trigger refuses every update outside an erasure, and pure logs (here: product_configuration_immutable).
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
    v_tables            text[] := ARRAY['configuration_model', 'configuration_model_revision', 'configuration_rule', 'configuration_table',
        'configuration_table_column', 'configuration_table_row', 'configuration_default', 'product_configuration',
        'product_configuration_value', 'price_list_characteristic_rate'];
    v_append_only       text[] := ARRAY['product_configuration', 'product_configuration_value']::text[];
    v_refuse_truncate   text[] := ARRAY['configuration_model', 'configuration_model_revision', 'configuration_rule', 'configuration_table',
        'configuration_table_column', 'configuration_table_row', 'configuration_default', 'product_configuration',
        'product_configuration_value', 'price_list_characteristic_rate']::text[];
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
    v_tables    text[] := ARRAY['configuration_model', 'configuration_model_revision', 'configuration_rule', 'configuration_table',
        'configuration_table_column', 'configuration_table_row', 'configuration_default', 'product_configuration',
        'product_configuration_value', 'price_list_characteristic_rate'];
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
