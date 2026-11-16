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
    UNIQUE (configuration_model_revision_id, position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (company_id, configuration_model_revision_id, product_id) REFERENCES configuration_model_revision (company_id, id, product_id),
    FOREIGN KEY (product_id, target_attribute_id) REFERENCES product_variant_attribute (product_id, variant_attribute_id),
    CONSTRAINT ck_configuration_rule_target CHECK ((kind = 'forbid') = (target_attribute_id IS NULL))
);
CREATE TABLE configuration_table (                          -- ADR-0046 rule 7
    id                                uuid PRIMARY KEY,
    company_id                        uuid NOT NULL,
    configuration_model_revision_id   uuid NOT NULL,
    product_id                        uuid NOT NULL,
    code                              text NOT NULL,
    UNIQUE (configuration_model_revision_id, code),
    UNIQUE (company_id, id, product_id),
    FOREIGN KEY (company_id, configuration_model_revision_id, product_id) REFERENCES configuration_model_revision (company_id, id, product_id)
);
CREATE TABLE configuration_table_column (
    company_id              uuid NOT NULL,
    configuration_table_id  uuid NOT NULL,
    product_id              uuid NOT NULL,
    column_number           integer NOT NULL CONSTRAINT ck_configuration_table_column_number CHECK (column_number > 0),
    variant_attribute_id    uuid NOT NULL,
    PRIMARY KEY (configuration_table_id, column_number),
    UNIQUE (configuration_table_id, variant_attribute_id),
    FOREIGN KEY (company_id, configuration_table_id, product_id) REFERENCES configuration_table (company_id, id, product_id),
    FOREIGN KEY (product_id, variant_attribute_id) REFERENCES product_variant_attribute (product_id, variant_attribute_id)
);
CREATE TABLE configuration_table_row (
    company_id              uuid NOT NULL,
    configuration_table_id  uuid NOT NULL,
    product_id              uuid NOT NULL,
    row_number              integer NOT NULL,
    cells                   jsonb NOT NULL CONSTRAINT ck_configuration_table_row_cells CHECK (jsonb_typeof(cells) = 'array'),   -- by column_number: a code, a number, "*" or {"min": n, "max": n}
    PRIMARY KEY (configuration_table_id, row_number),
    FOREIGN KEY (company_id, configuration_table_id, product_id) REFERENCES configuration_table (company_id, id, product_id)
);
CREATE TABLE configuration_default (                        -- ADR-0046 rule 8
    company_id                        uuid NOT NULL,
    configuration_model_revision_id   uuid NOT NULL,
    product_id                        uuid NOT NULL,
    position                          integer NOT NULL,
    target_attribute_id               uuid NOT NULL,
    value                             jsonb NOT NULL,             -- a value code or a number
    condition                         jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (configuration_model_revision_id, position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (company_id, configuration_model_revision_id, product_id) REFERENCES configuration_model_revision (company_id, id, product_id),
    FOREIGN KEY (product_id, target_attribute_id) REFERENCES product_variant_attribute (product_id, variant_attribute_id)
);

-- ===== Configurations [master_data] (ADR-0046 rule 9) =====
CREATE TABLE product_configuration (                        -- immutable, content-addressed; only complete, valid configurations
    id            uuid PRIMARY KEY,
    company_id    uuid NOT NULL,
    product_id    uuid NOT NULL,
    content_hash  text NOT NULL CONSTRAINT ck_product_configuration_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    created_at    timestamptz NOT NULL,
    created_xact_id  xid8 NOT NULL DEFAULT pg_current_xact_id(),   -- the top-level transaction, also inside savepoints
    UNIQUE (company_id, product_id, content_hash),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, product_id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id)
);
CREATE TABLE product_configuration_value (
    company_id                  uuid NOT NULL,
    product_configuration_id    uuid NOT NULL,
    product_id                  uuid NOT NULL,
    variant_attribute_id        uuid NOT NULL,
    value_type                  text NOT NULL,
    variant_attribute_value_id  uuid,                             -- list values
    numeric_value               types.quantity,                   -- numbers, in both modes; value rows appear only with items (ADR-0046 rule 11)
    PRIMARY KEY (product_configuration_id, variant_attribute_id),
    FOREIGN KEY (company_id, product_configuration_id, product_id) REFERENCES product_configuration (company_id, id, product_id),
    FOREIGN KEY (product_id, variant_attribute_id) REFERENCES product_variant_attribute (product_id, variant_attribute_id),
    CONSTRAINT fk_product_configuration_value_type FOREIGN KEY (company_id, variant_attribute_id, value_type) REFERENCES variant_attribute (company_id, id, value_type),
    FOREIGN KEY (variant_attribute_id, variant_attribute_value_id) REFERENCES variant_attribute_value (variant_attribute_id, id),
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
    FOREIGN KEY (company_id, price_list_id) REFERENCES price_list (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    FOREIGN KEY (product_id, variant_attribute_id) REFERENCES product_variant_attribute (product_id, variant_attribute_id),
    CONSTRAINT fk_price_list_characteristic_rate_type FOREIGN KEY (company_id, variant_attribute_id, value_type) REFERENCES variant_attribute (company_id, id, value_type),
    CONSTRAINT ck_price_list_characteristic_rate_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ex_price_list_characteristic_rate_overlap EXCLUDE USING gist (
        price_list_id WITH =, product_id WITH =, variant_attribute_id WITH =, daterange(start_date, end_date, '[]') WITH &&)
);

-- ===== Immutability (ADR-0046 rules 4, 9) =====
CREATE FUNCTION configuration_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state = 'released' THEN RAISE EXCEPTION 'revision_released'; END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_configuration_model_revision_guard BEFORE UPDATE OR DELETE ON configuration_model_revision
    FOR EACH ROW EXECUTE FUNCTION configuration_revision_guard();
CREATE FUNCTION configuration_revision_of(j jsonb) RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT coalesce((j ->> 'configuration_model_revision_id')::uuid,
                    (SELECT t.configuration_model_revision_id FROM configuration_table t WHERE t.id = (j ->> 'configuration_table_id')::uuid))
$$;
CREATE FUNCTION configuration_revision_content_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
CREATE FUNCTION product_configuration_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
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
