-- DS-20 master data: DDL draft for ADR-0018, ADR-0019, ADR-0020, ADR-0023, ADR-0024, ADR-0027 rule 5, ADR-0031,
-- ADR-0033, ADR-0037, ADR-0045, ADR-0068 (sites, payment and delivery methods, Incoterms) and ADR-0069 (business units), with the
-- columns ADR-0046 (product configuration) and ADR-0070 (product.inspection_points) add; ADR-0046's tables are in
-- DS-56-product-configuration.sql.
-- PostgreSQL 18. Loaded together with DS-06 and tested in the design lab (docs/reviews/2026-11-14-design-validation,
-- t05_master_data.py). The ADRs win if this file disagrees.
-- Tables live in schema `nativeflows` (ADR-0022 rule 7); domains in schema `types` (ADR-0006 rule 8). Keys are shown inline;
-- in migrations they get names from the MetaData naming convention (ADR-0004 rule 15). btree_gist is installed (ADR-0022 rule 8).
-- Every table carries company_id, FORCE ROW LEVEL SECURITY and the generated company policy (ADR-0022 rule 8), except
-- the global catalogs currency, uom_conversion and incoterm; uom, whose core rows have a null company_id, takes the generated
-- shared-reference variant (every company reads core units, a company writes only its own); and company itself, whose
-- generated policies compare its own id (S2 closure, 2026-11-21). The lab checks this list (ADR-0045 rule 14).
-- Owner module per table in brackets (ADR-0022 rule 2). Referenced tables defined elsewhere: user_account and department (DS-15-access.sql, which adds employee_profile's department key),
-- account and payment_term (DS-06, ledger), tax groups' matrix (ADR-0041, tax).
-- IDs are UUIDv7 from context.new_id or the client (ADR-0006 rule 3); no ID defaults, except barcode.id, whose rows a trigger writes (ADR-0006 rule 2).
-- Template-copied company data keeps its package basis in `basis`, always set by the command: the template entry's
-- basis, or company_decision for a row the company adds (ADR-0016 rules 6-7, 12).
-- Uniqueness, checks and foreign keys that the database can hold are here, including composite keys that keep a
-- reference inside one company. Rules that need other rows (e.g. a product unit is not the inventory unit) are enforced
-- by commands and named in ADR-0045 rule 13; every other reference is validated by the handler, which loads the row
-- under row-level security.

-- ===== Currencies and units [master_data] =====
CREATE TABLE currency (
    code           text PRIMARY KEY CONSTRAINT ck_currency_code CHECK (code ~ '^[A-Z]{3}$'),     -- ISO 4217 (ADR-0011 rule 7)
    minor_unit     smallint NOT NULL CONSTRAINT ck_currency_minor_unit CHECK (minor_unit BETWEEN 0 AND 4),
    rounding_mode  text NOT NULL DEFAULT 'half_up' CONSTRAINT ck_currency_rounding_mode CHECK (rounding_mode IN ('half_up', 'half_even', 'down', 'up')),
    is_active      boolean NOT NULL DEFAULT true,
    recorded_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE company_currency_activation (                 -- a company activates the currencies it uses (ADR-0011 rule 7)
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    currency    text NOT NULL REFERENCES currency (code),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_company_currency_activation_company_id_currency UNIQUE (company_id, currency)
);
CREATE TABLE uom (                                         -- ADR-0018 rule 8; core rows have company_id null
    id              uuid PRIMARY KEY,
    company_id      uuid REFERENCES company (id),
    code            text NOT NULL,
    name            text NOT NULL,                          -- core: the English name of catalogs/units.csv; company: the company's text (ADR-0056 rule 2)
    quantity_kind   text NOT NULL CONSTRAINT ck_uom_quantity_kind CHECK (quantity_kind IN ('count', 'mass', 'length', 'area', 'volume', 'time')),
    decimal_places  smallint NOT NULL CONSTRAINT ck_uom_decimal_places CHECK (decimal_places BETWEEN 0 AND 6),
    is_active       boolean NOT NULL DEFAULT true,          -- false: retired, no new uses; history keeps it (ADR-0056 rule 2)
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_uom_company_code CHECK ((company_id IS NULL) = (code NOT LIKE 'x-%'))
);
CREATE UNIQUE INDEX ux_uom_core_code ON uom (code) WHERE company_id IS NULL;
CREATE UNIQUE INDEX ux_uom_company_code ON uom (company_id, code) WHERE company_id IS NOT NULL;
CREATE TABLE uom_conversion (                              -- core catalog unit-conversions.csv: units of one kind, exact ratio of two positive integers (ADR-0006 rule 11; ADR-0018 rule 8; ADR-0056 rule 3)
    id           uuid PRIMARY KEY,                         -- uuid5 of 'uom_conversion:<from code>:<to code>' (ADR-0006 rule 4)
    from_uom_id  uuid NOT NULL REFERENCES uom (id),
    to_uom_id    uuid NOT NULL REFERENCES uom (id),
    numerator    bigint NOT NULL CONSTRAINT ck_uom_conversion_numerator CHECK (numerator > 0),       -- 1 from = numerator/denominator to
    denominator  bigint NOT NULL CONSTRAINT ck_uom_conversion_denominator CHECK (denominator > 0),
    is_active    boolean NOT NULL DEFAULT true,            -- false: retired by a catalog version; immutable once used
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_uom_conversion_distinct CHECK (from_uom_id <> to_uom_id),
    -- direct pairs only, stored once from the larger unit (factor >= 1); the inverse is derived, never stored or chained
    CONSTRAINT ck_uom_conversion_direction CHECK (numerator >= denominator)
);
-- One row per pair of units in either direction (ADR-0056 rule 3).
CREATE UNIQUE INDEX ux_uom_conversion_pair ON uom_conversion (least(from_uom_id, to_uom_id), greatest(from_uom_id, to_uom_id));
CREATE TABLE uom_alias (                                   -- unit text as partners and old systems write it, for intake (ADR-0056 rule 19)
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    alias             text NOT NULL,                       -- as first entered, e.g. Thùng
    normalized_alias  text NOT NULL,                       -- master_data.contract.normalize_unit_text(alias), e.g. thung
    uom_id            uuid NOT NULL REFERENCES uom (id),   -- a core unit or a unit of the same company (command check)
    is_active         boolean NOT NULL DEFAULT true,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_uom_alias_normalized UNIQUE (company_id, normalized_alias),
    CONSTRAINT ck_uom_alias_normalized CHECK (length(normalized_alias) > 0 AND normalized_alias = lower(normalized_alias) AND normalized_alias !~ '\s')
);

-- ===== Organization [master_data] (ADR-0027 rule 5; moved here from DS-06) =====
CREATE TABLE company (
    id                        uuid PRIMARY KEY,
    code                      text NOT NULL UNIQUE,
    legal_name                text NOT NULL,
    tax_id                    text,
    company_currency          text NOT NULL REFERENCES currency (code),
    time_zone                 text NOT NULL,                       -- IANA name (ADR-0007 rule 12)
    localization_package      text NOT NULL,
    accounting_regime         text NOT NULL,
    legal_form                text,                                -- from the package's legal_forms; null where it declares none (ADR-0039 rule 5)
    valuation_area_level      text NOT NULL CONSTRAINT ck_company_valuation_area_level CHECK (valuation_area_level IN ('company', 'site', 'warehouse')),   -- ADR-0020 rule 2; ADR-0068 rule 7
    fiscal_calendar_owner_id  uuid NOT NULL REFERENCES user_account (id),
    fiscal_year_lead_days     integer NOT NULL DEFAULT 30,
    default_language          text NOT NULL,                       -- BCP 47, set at company creation from the package; documents and partners may override (ADR-0016 rule 19)
    is_active                 boolean NOT NULL DEFAULT true,
    first_operating_posting_at timestamptz,                         -- set once, by the first journal entry outside the migration fiscal year, which locks this row; null: the setup phase (ADR-0067 rule 7)
    recorded_at               timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE branch (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL REFERENCES company (id),
    code               text NOT NULL,
    name               text NOT NULL,
    tax_id             text,
    is_declaring_unit  boolean NOT NULL DEFAULT false,             -- files tax returns separately (ADR-0041 rule 11; ADR-0045 rule 8; ADR-0053 rule 14)
    address            jsonb,                                       -- the columns of partner_address as keys (ADR-0045 rule 8)
    is_active          boolean NOT NULL DEFAULT true,
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    CONSTRAINT ck_branch_declaring_unit_tax_id CHECK (NOT is_declaring_unit OR tax_id IS NOT NULL)
);
CREATE TABLE print_profile (                              -- print header of the company (branch_id null) or a branch (ADR-0049 rule 26)
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL REFERENCES company (id),
    branch_id                   uuid,                                -- a branch row's non-empty fields win over the company row's
    address                     jsonb,                               -- the columns of partner_address as keys (ADR-0045 rule 8)
    phone                       text,
    email                       text,
    website                     text,
    legal_representative_name   text,                                -- personal (spec 17)
    legal_representative_title  text,
    chief_accountant_name       text,                                -- personal (spec 17)
    bank_details                jsonb,                               -- list of {bank_name, account_number, branch}, printed as text
    logo_attachment_id          uuid,                                -- attachment (DS-36), PNG or JPEG
    seal_attachment_id          uuid,                                -- label internal; never printed on a document with a marker
    signature_attachment_id     uuid,                                -- label internal; never printed on a document with a marker
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (company_id, branch_id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id)
);
CREATE TABLE business_unit (                               -- [master_data] ADR-0069 rule 1; a line of business, an analysis dimension, not an entity
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    code         text NOT NULL,                       -- immutable once named anywhere (rule 1); group reporting matches on it
    name         text NOT NULL,                       -- translated through data_translation (ADR-0018 rule 17)
    parent_id    uuid,                                -- the reporting tree; no cycle (command, business_unit_invalid)
    is_active    boolean NOT NULL DEFAULT true,       -- deactivation refused while a default names it (business_unit_in_use, rule 2)
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_id) REFERENCES business_unit (company_id, id),
    CONSTRAINT ck_business_unit_not_own_parent CHECK (parent_id IS NULL OR parent_id <> id)
);
CREATE INDEX ix_business_unit_company_id_parent_id ON business_unit (company_id, parent_id) WHERE parent_id IS NOT NULL;
CREATE TABLE cost_center (
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    code        text NOT NULL,
    name        text NOT NULL,
    kind        text NOT NULL CONSTRAINT ck_cost_center_kind CHECK (kind IN ('production', 'production_service', 'selling', 'administration', 'other')),
    parent_id   uuid,
    branch_id   uuid,
    is_active   boolean NOT NULL DEFAULT true,
    business_unit_id uuid,                                    -- default unit of its profit-and-loss lines (ADR-0069 rule 7)
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE working_calendar (                            -- ADR-0024 rule 4
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    code              text NOT NULL,
    name              text NOT NULL,
    working_weekdays  smallint[] NOT NULL CONSTRAINT ck_working_calendar_weekdays CHECK (working_weekdays <@ ARRAY[1,2,3,4,5,6,7]::smallint[]),  -- ISO weekdays
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
CREATE TABLE working_calendar_holiday (                    -- copied from a package template entry, or added by the company (ADR-0045 rule 10)
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    working_calendar_id  uuid NOT NULL,
    holiday_date         date NOT NULL,
    name                 text,
    basis                jsonb NOT NULL,
    recorded_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_working_calendar_holiday_working_calendar_id_holiday_date UNIQUE (working_calendar_id, holiday_date),
    FOREIGN KEY (company_id, working_calendar_id) REFERENCES working_calendar (company_id, id)
);
CREATE TABLE site (                                        -- [master_data] ADR-0068 rule 1; SAP plant, Dynamics 365 site
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    code                 text NOT NULL,                       -- MAIN for the site CreateCompany creates (rule 3)
    name                 text NOT NULL,
    kind                 text NOT NULL CONSTRAINT ck_site_kind CHECK (kind IN ('factory', 'distribution', 'store', 'office')),   -- a label; no rule reads it
    branch_id            uuid,                                -- optional; its physical warehouses then carry the same branch (command check, site_branch_mismatch)
    address              jsonb,                               -- the columns of partner_address as keys (ADR-0045 rule 8)
    working_calendar_id  uuid,                                -- record default for new warehouses and work centers of the site
    business_unit_id     uuid,                                -- default unit of profit-and-loss lines from its warehouses (ADR-0069 rules 7, 9)
    is_active            boolean NOT NULL DEFAULT true,       -- deactivation refused while an active warehouse names the site (site_in_use)
    recorded_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, working_calendar_id) REFERENCES working_calendar (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE data_translation (                            -- ADR-0018 rule 17
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    table_name  text NOT NULL,
    row_id      uuid NOT NULL,
    field       text NOT NULL,
    language    text NOT NULL,
    text        text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_data_translation_company_id_table_name_row_id_field_language UNIQUE (company_id, table_name, row_id, field, language)
);

-- ===== Groups copied from package templates [master_data] =====
CREATE TABLE partner_group (
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_partner_group_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE partner_tax_group (                           -- read by the tax matrix (ADR-0041 rule 3)
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    directions text[] NOT NULL CONSTRAINT ck_partner_tax_group_directions CHECK (directions <@ ARRAY['sale','purchase']::text[] AND cardinality(directions) > 0),
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_partner_tax_group_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE item_group (
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code), UNIQUE (company_id, id),
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE valuation_class (
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_valuation_class_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE item_tax_group (                              -- read by the tax matrix (ADR-0041 rule 3)
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_item_tax_group_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);

-- ===== Partners [master_data] (ADR-0019) =====
CREATE TABLE partner (
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL REFERENCES company (id),
    code                      text NOT NULL,
    name                      text NOT NULL,
    legal_name                text,
    partner_kind              text NOT NULL CONSTRAINT ck_partner_kind CHECK (partner_kind IN ('organization', 'sole_proprietorship', 'individual')),   -- ADR-0019 rule 1; ADR-0053 rule 7
    tax_id                    text,                               -- normalized by the package rule (ADR-0019 rule 4)
    parent_partner_id         uuid,
    represents_company_id     uuid REFERENCES company (id),
    country                   text NOT NULL CONSTRAINT ck_partner_country CHECK (country ~ '^[A-Z]{2}$'),   -- ISO 3166-1 alpha-2
    partner_group_id          uuid,
    partner_tax_group_id      uuid,
    preferred_language        text,
    superseded_by_partner_id  uuid,                               -- ADR-0019 rule 19 (interim)
    is_active                 boolean NOT NULL DEFAULT true,
    custom_values    jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_partner_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, superseded_by_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_partner_not_own_parent CHECK (parent_partner_id IS NULL OR parent_partner_id <> id),
    FOREIGN KEY (company_id, partner_group_id) REFERENCES partner_group (company_id, id),   -- company key (ADR-0017 rule 19 note, 2026-11-21)
    FOREIGN KEY (company_id, partner_tax_group_id) REFERENCES partner_tax_group (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
-- Tax ID duplicates are a check result, not a unique constraint (ADR-0019 rule 4).
CREATE INDEX ix_partner_company_id_tax_id ON partner (company_id, tax_id) WHERE tax_id IS NOT NULL;
CREATE TABLE project (
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    code                 text NOT NULL,
    name                 text NOT NULL,
    customer_partner_id  uuid,
    start_date           date,
    end_date             date,
    state                text NOT NULL DEFAULT 'open' CONSTRAINT ck_project_state CHECK (state IN ('open', 'closed')),
    business_unit_id     uuid,                           -- default unit of its profit-and-loss lines (ADR-0069 rule 7)
    recorded_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),                         -- stock document lines name a project by company key (ADR-0075 rules 4, 5)
    FOREIGN KEY (company_id, customer_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_project_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE partner_role (
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL,
    partner_id  uuid NOT NULL,
    role        text NOT NULL CONSTRAINT ck_partner_role_role CHECK (role IN ('customer', 'supplier', 'employee')),
    is_active   boolean NOT NULL DEFAULT true,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_partner_role_partner_id_role UNIQUE (partner_id, role),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id)
);

-- ===== Payment and delivery methods, Incoterms [master_data] (ADR-0068 rules 15-22) =====
-- The profiles below and the commercial documents of DS-22 refer to them; none of them refers to a table of ledger, cash,
-- inventory, tax or production, so the CRM-only profile keeps them (ADR-0068). The default money account of a payment
-- method is cash's payment_method_money_account (DS-05-platform.sql).
CREATE TABLE payment_method (                              -- [master_data] ADR-0068 rule 15
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    code         text NOT NULL,
    name         text NOT NULL,
    kind         text NOT NULL CONSTRAINT ck_payment_method_kind CHECK (kind IN ('cash', 'bank_transfer', 'card', 'e_wallet', 'cheque', 'direct_debit', 'cash_on_delivery', 'offset', 'other')),   -- suggests only; no posting rule reads it (rule 17)
    is_active    boolean NOT NULL DEFAULT true,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
CREATE TABLE incoterm (                                    -- [master_data] ADR-0068 rule 18; global catalog incoterms.csv, natural key (E1, as currency)
    code                         text PRIMARY KEY CONSTRAINT ck_incoterm_code CHECK (code ~ '^[A-Z]{3}$'),
    version                      smallint NOT NULL CONSTRAINT ck_incoterm_version CHECK (version >= 2020),   -- the edition the row describes
    name                         text NOT NULL,
    transport_scope              text NOT NULL CONSTRAINT ck_incoterm_transport_scope CHECK (transport_scope IN ('any', 'sea_inland_waterway')),
    is_carriage_paid_by_seller   boolean NOT NULL,             -- the seller pays the main carriage
    is_insurance_paid_by_seller  boolean NOT NULL,             -- the seller insures the main carriage
    is_import_cleared_by_seller  boolean NOT NULL,             -- the seller clears import (DDP only)
    risk_transfer_point          text NOT NULL,                -- where risk passes from seller to buyer, in plain words
    is_active                    boolean NOT NULL DEFAULT true,   -- false: retired by a later edition; old documents keep it
    recorded_at                  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE delivery_method (                             -- [master_data] ADR-0068 rule 21
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL REFERENCES company (id),
    code                   text NOT NULL,
    name                   text NOT NULL,
    kind                   text NOT NULL CONSTRAINT ck_delivery_method_kind CHECK (kind IN ('own_fleet', 'carrier', 'courier', 'customer_pickup', 'supplier_delivery')),
    carrier_partner_id     uuid,                              -- an active supplier role (command check, partner_role_missing)
    tracking_url_template  text,                              -- https URL containing {tracking_number}; the link is computed, never stored
    is_active              boolean NOT NULL DEFAULT true,
    recorded_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, carrier_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_delivery_method_carrier CHECK ((kind IN ('carrier', 'courier')) = (carrier_partner_id IS NOT NULL)),
    CONSTRAINT ck_delivery_method_tracking_url_template CHECK (tracking_url_template IS NULL
        OR (tracking_url_template LIKE 'https://%' AND strpos(tracking_url_template, '{tracking_number}') > 0))
);
-- ===== Price lists [master_data] (ADR-0045) =====
CREATE TABLE price_list (
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL REFERENCES company (id),
    code             text NOT NULL,
    name             text NOT NULL,
    kind             text NOT NULL CONSTRAINT ck_price_list_kind CHECK (kind IN ('sale', 'purchase', 'by_product')),
    currency         text NOT NULL REFERENCES currency (code),
    is_tax_included  boolean NOT NULL DEFAULT false,               -- passed as prices_include_tax to ADR-0041 rule 9
    is_default       boolean NOT NULL DEFAULT false,
    is_active        boolean NOT NULL DEFAULT true,
    recorded_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, kind),
    CONSTRAINT ck_price_list_tax CHECK (NOT is_tax_included OR kind = 'sale'),
    CONSTRAINT ck_price_list_default_active CHECK (NOT is_default OR is_active)
);
-- One default list per kind; at most one active by-product list (ADR-0045 rules 2, 6).
CREATE UNIQUE INDEX ux_price_list_default ON price_list (company_id, kind) WHERE is_default;
CREATE UNIQUE INDEX ux_price_list_by_product ON price_list (company_id) WHERE kind = 'by_product' AND is_active;

CREATE TABLE customer_profile (
    id                                 uuid PRIMARY KEY,
    company_id                         uuid NOT NULL,
    partner_id                         uuid NOT NULL CONSTRAINT uq_customer_profile_partner_id UNIQUE,
    receivable_account_id              uuid,   -- required while ledger is activated (partner commands; INV-38; ADR-0015 rule 11 note); empty in the CRM-only profile
    payment_term_id                    uuid,
    credit_limit                       types.amount,
    credit_limit_currency              text REFERENCES currency (code),
    price_list_id                      uuid,
    price_list_kind                    text NOT NULL DEFAULT 'sale' CONSTRAINT ck_customer_profile_price_list_kind CHECK (price_list_kind = 'sale'),
    salesperson_id                     uuid,                          -- a partner with the employee role (ADR-0027 rule 6)
    currency                           text REFERENCES currency (code),
    minimum_remaining_shelf_life_days  integer,
    payment_method_id                  uuid,                          -- defaults copied to documents (ADR-0068 rules 15, 19, 22)
    delivery_method_id                 uuid,
    incoterm_code                      text REFERENCES incoterm (code),
    incoterm_place                     text,                          -- the named place; requires a code
    recorded_at                        timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT fk_customer_profile_price_list FOREIGN KEY (company_id, price_list_id, price_list_kind) REFERENCES price_list (company_id, id, kind),
    FOREIGN KEY (company_id, salesperson_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_customer_profile_credit_limit CHECK (credit_limit IS NULL OR (credit_limit >= 0 AND credit_limit_currency IS NOT NULL)),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id),
    FOREIGN KEY (company_id, delivery_method_id) REFERENCES delivery_method (company_id, id),
    CONSTRAINT ck_customer_profile_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, receivable_account_id) REFERENCES account (company_id, id),   -- company key (S2 schema phase B)
    FOREIGN KEY (company_id, payment_term_id) REFERENCES payment_term (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE INDEX ix_customer_profile_price_list_id ON customer_profile (price_list_id);
CREATE TABLE supplier_profile (
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    partner_id           uuid NOT NULL CONSTRAINT uq_supplier_profile_partner_id UNIQUE,
    payable_account_id   uuid,          -- required while ledger is activated (partner commands; INV-38; ADR-0015 rule 11 note); empty in the CRM-only profile
    payment_term_id      uuid,
    buyer_id             uuid,
    price_list_id        uuid,                                    -- the supplier's purchase prices (ADR-0045 rule 2)
    price_list_kind      text NOT NULL DEFAULT 'purchase' CONSTRAINT ck_supplier_profile_price_list_kind CHECK (price_list_kind = 'purchase'),
    currency             text REFERENCES currency (code),
    working_calendar_id  uuid,                                    -- supplier processing days (ADR-0024 rule 4)
    payment_method_id    uuid,                          -- defaults copied to documents (ADR-0068 rules 15, 19, 22)
    delivery_method_id   uuid,
    incoterm_code        text REFERENCES incoterm (code),
    incoterm_place       text,                          -- the named place; requires a code
    recorded_at          timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, price_list_id, price_list_kind) REFERENCES price_list (company_id, id, kind),
    FOREIGN KEY (company_id, buyer_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, working_calendar_id) REFERENCES working_calendar (company_id, id),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id),
    FOREIGN KEY (company_id, delivery_method_id) REFERENCES delivery_method (company_id, id),
    CONSTRAINT ck_supplier_profile_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, payable_account_id) REFERENCES account (company_id, id),   -- company key (S2 schema phase B)
    FOREIGN KEY (company_id, payment_term_id) REFERENCES payment_term (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE INDEX ix_supplier_profile_price_list_id ON supplier_profile (price_list_id);
CREATE TABLE employee_profile (                            -- personal data (ADR-0019 rule 7)
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    partner_id             uuid NOT NULL CONSTRAINT uq_employee_profile_partner_id UNIQUE,
    user_account_id        uuid REFERENCES user_account (id),           -- unique per company; set only by UpdateEmployeeOrganization (ADR-0054 rule 6)
    receivable_account_id  uuid,           -- advances (receivable_employee_advance)
    branch_id              uuid,
    cost_center_id         uuid,
    job_title              text,
    department_id          uuid,                                    -- key to department in DS-15-access.sql; set only by UpdateEmployeeOrganization (ADR-0054 rule 6)
    manager_partner_id     uuid,                                    -- the employee's manager; no loops (command, employee_manager_cycle); set only by UpdateEmployeeOrganization
    recorded_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, user_account_id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, manager_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_employee_profile_manager CHECK (manager_partner_id IS DISTINCT FROM partner_id),
    FOREIGN KEY (company_id, receivable_account_id) REFERENCES account (company_id, id)   -- company key (S2 schema phase B)
);
CREATE TABLE partner_address (
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL,
    partner_id        uuid NOT NULL,
    kind              text NOT NULL CONSTRAINT ck_partner_address_kind CHECK (kind IN ('legal', 'billing', 'delivery', 'other')),
    address_lines     text[] NOT NULL,
    subdivision_code  text,                                          -- package list of administrative units
    postal_code       text,
    country           text NOT NULL CONSTRAINT ck_partner_address_country CHECK (country ~ '^[A-Z]{2}$'),
    is_active         boolean NOT NULL DEFAULT true,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, partner_id, id),                             -- a document names its ship-to or bill-to address with its partner (ADR-0074 rules 1-3)
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id)
);
CREATE INDEX ix_partner_address_partner_id ON partner_address (partner_id);
CREATE TABLE partner_bank_account (                        -- changed only through change proposals (ADR-0029 rule 4)
    id              uuid PRIMARY KEY,
    company_id      uuid NOT NULL,
    partner_id      uuid NOT NULL,
    bank_name       text NOT NULL,
    bank_code       text,                                            -- e.g. a national bank code or BIC
    account_number  text NOT NULL,
    holder_name     text NOT NULL,
    currency        text REFERENCES currency (code),
    is_active       boolean NOT NULL DEFAULT true,
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    UNIQUE NULLS NOT DISTINCT (partner_id, bank_code, account_number)
);
CREATE TABLE contact (
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    partner_id          uuid NOT NULL,
    name                text NOT NULL,
    job_title           text,
    email               text,
    phone               text,
    preferred_language  text,
    is_active           boolean NOT NULL DEFAULT true,
    is_accounts_contact boolean NOT NULL DEFAULT false,      -- receives payment reminders (ADR-0052 rule 28)
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, partner_id, id),                     -- keeps a crm row's contact inside its partner (ADR-0052 rule 3)
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_contact_email_lower CHECK (email = lower(email))   -- commands normalize addresses (ADR-0052 rule 4)
);
CREATE INDEX ix_contact_partner_id ON contact (partner_id);
-- E-mail addresses and phones are stored normalized by the commands; crm matches and searches on them (ADR-0052 rules 4, 15, 17).
CREATE INDEX ix_contact_company_id_email ON contact (company_id, email) WHERE email IS NOT NULL;
CREATE INDEX ix_contact_company_id_phone ON contact (company_id, phone) WHERE phone IS NOT NULL;

-- ===== Products and items [master_data] (ADR-0018) =====
CREATE TABLE product_category (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL REFERENCES company (id),
    code                       text NOT NULL,
    name                       text NOT NULL,
    parent_id                  uuid,
    default_item_group_id      uuid,
    default_valuation_class_id uuid,
    default_item_tax_group_id  uuid,                           -- empty: inherited from the parent category, then the company default (ADR-0018 rule 3 note, 2026-11-21)
    default_inventory_uom_id   uuid REFERENCES uom (id),
    basis                      jsonb NOT NULL,
    is_active                  boolean NOT NULL DEFAULT true,
    recorded_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_id) REFERENCES product_category (company_id, id),   -- company key (S2 schema review S4)
    FOREIGN KEY (company_id, default_item_group_id) REFERENCES item_group (company_id, id),   -- company key (S2 schema review S4)
    FOREIGN KEY (company_id, default_valuation_class_id) REFERENCES valuation_class (company_id, id),   -- company key (ADR-0017 rule 19 note, 2026-11-21)
    FOREIGN KEY (company_id, default_item_tax_group_id) REFERENCES item_tax_group (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE storage_condition (                           -- ADR-0023 rule 3
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_storage_condition_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE handling_unit_type (                          -- ADR-0023 rule 6
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    code              text NOT NULL,
    name              text NOT NULL,
    tare_weight       types.quantity,
    weight_uom_id     uuid REFERENCES uom (id),
    length            types.quantity,
    width             types.quantity,
    height            types.quantity,
    dimension_uom_id  uuid REFERENCES uom (id),
    is_active         boolean NOT NULL DEFAULT true,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    CONSTRAINT ck_handling_unit_type_weight_uom CHECK (tare_weight IS NULL OR weight_uom_id IS NOT NULL),
    CONSTRAINT ck_handling_unit_type_dimension_uom CHECK ((length IS NULL AND width IS NULL AND height IS NULL) OR dimension_uom_id IS NOT NULL),
    CONSTRAINT uq_handling_unit_type_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE product (
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL REFERENCES company (id),
    code                           text NOT NULL,
    name                           text NOT NULL,                   -- in the company's language; others in data_translation
    description                    text,                            -- translated like name (ADR-0018 rule 17)
    product_type                   text NOT NULL CONSTRAINT ck_product_type CHECK (product_type IN ('stock', 'non_stock', 'service')),
    is_sellable                    boolean NOT NULL DEFAULT true,
    is_purchasable                 boolean NOT NULL DEFAULT true,
    product_category_id            uuid,
    buyer_id                       uuid,                            -- an employee partner (ADR-0018 rule 3)
    item_group_id                  uuid NOT NULL,
    valuation_class_id             uuid,
    inventory_uom_id               uuid NOT NULL REFERENCES uom (id),
    purchase_uom_id                uuid NOT NULL REFERENCES uom (id),
    sales_uom_id                   uuid NOT NULL REFERENCES uom (id),
    -- catch_weight_uom_id is reserved by ADR-0018 rule 3 and not created in Phase 1.
    tracking                       text NOT NULL DEFAULT 'none' CONSTRAINT ck_product_tracking CHECK (tracking IN ('none', 'lot', 'serial')),
    item_tax_group_id              uuid,                            -- empty: inherited from the category chain, then the company default (ADR-0018 rule 3 note, 2026-11-21; tax_effective_item_tax_group in DS-05)
    is_item_created_on_order       boolean NOT NULL DEFAULT false,  -- a document line may name a new combination of variant values (ADR-0045 rule 16)
    is_configurable                boolean NOT NULL DEFAULT false,  -- sold through a configuration model; its items are configured items (ADR-0046 rule 2)
    last_item_number               integer NOT NULL DEFAULT 0,      -- counter for codes of items created on order, under the product row lock
    price_control                  text NOT NULL DEFAULT 'periodic_average' CONSTRAINT ck_product_price_control CHECK (price_control IN ('periodic_average')),
    inspection_points              text[] NOT NULL DEFAULT '{}' CONSTRAINT ck_product_inspection_points CHECK (inspection_points <@ ARRAY['goods_receipt', 'in_process', 'production_output', 'customer_return', 'stock_recheck']::text[]),   -- ADR-0070 rule 2: the points at which the product is inspected; replaced is_inspection_required (ADR-0023 rule 3)
    removal_strategy               text CONSTRAINT ck_product_removal_strategy CHECK (removal_strategy IN ('fefo', 'fifo')),
    storage_condition_id           uuid,
    default_handling_unit_type_id  uuid,
    hs_code                        text,                            -- ADR-0021 rule 13
    country_of_origin              text CONSTRAINT ck_product_country_of_origin CHECK (country_of_origin ~ '^[A-Z]{2}$'),
    business_unit_id               uuid,                            -- default unit of its items' profit-and-loss lines, read through the item (ADR-0069 rule 7)
    is_active                      boolean NOT NULL DEFAULT true,
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_product_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at                    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, inventory_uom_id),             -- product_uom holds the inventory unit through it (ADR-0056 rule 4)
    FOREIGN KEY (company_id, buyer_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_product_valuation_class CHECK ((product_type = 'stock') = (valuation_class_id IS NOT NULL)),
    CONSTRAINT ck_product_tracking_stock CHECK (tracking = 'none' OR product_type = 'stock'),
    CONSTRAINT ck_product_configurable CHECK (NOT is_configurable OR (is_item_created_on_order AND product_type = 'stock')),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id),
    FOREIGN KEY (company_id, product_category_id) REFERENCES product_category (company_id, id),   -- company key (S2 schema review S4)
    FOREIGN KEY (company_id, item_group_id) REFERENCES item_group (company_id, id),   -- company key (S2 schema review S4)
    FOREIGN KEY (company_id, valuation_class_id) REFERENCES valuation_class (company_id, id),   -- company key (ADR-0017 rule 19 note, 2026-11-21)
    FOREIGN KEY (company_id, item_tax_group_id) REFERENCES item_tax_group (company_id, id),   -- company key (ADR-0017 rule 19 note, 2026-11-21)
    FOREIGN KEY (company_id, storage_condition_id) REFERENCES storage_condition (company_id, id),   -- company key (ADR-0017 rule 19 note, 2026-11-21)
    FOREIGN KEY (company_id, default_handling_unit_type_id) REFERENCES handling_unit_type (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE product_uom (                                 -- other units of one product, or of one item: the item master's conversions (ADR-0018 rule 10; ADR-0056 rules 4-5, 15)
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL,
    product_id            uuid NOT NULL,
    item_id               uuid,                            -- set: an item's own unit (a variant or configured item), resolved before the product's
    uom_id                uuid NOT NULL REFERENCES uom (id),
    inventory_uom_id      uuid NOT NULL,                   -- the product's inventory unit, held by the key below
    numerator             bigint NOT NULL CONSTRAINT ck_product_uom_numerator CHECK (numerator > 0),       -- 1 uom = numerator/denominator inventory units (ADR-0006 rule 11)
    denominator           bigint NOT NULL CONSTRAINT ck_product_uom_denominator CHECK (denominator > 0),
    factor_source         text NOT NULL DEFAULT 'stated' CONSTRAINT ck_product_uom_factor_source CHECK (factor_source IN ('stated', 'packaging', 'catalog', 'nominal')),
    is_exact              boolean NOT NULL,                -- computed at creation: numerator x 10^dI divisible by denominator x 10^dE (ADR-0056 rule 7)
    contains_uom_id       uuid REFERENCES uom (id),        -- packaging: one unit contains contains_quantity of this unit (ADR-0056 rule 15)
    contains_quantity     types.quantity,
    is_counting_unit      boolean NOT NULL DEFAULT false,  -- a count may be entered in it
    is_default_pick_unit  boolean NOT NULL DEFAULT false,  -- proposed on pick lists for a demand line in the inventory unit
    is_active             boolean NOT NULL DEFAULT true,   -- false: retired, no new uses; a new row for the same unit may replace it (ADR-0056 rule 5)
    retired_at            timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),   -- set once at insert: in force from created_at until retired_at (INV-603; ADR-0056 rule 4 note)
    recorded_at           timestamptz NOT NULL DEFAULT now(),   -- the last write, retirement included (ADR-0007 rule 9)
    CONSTRAINT fk_product_uom_inventory_unit FOREIGN KEY (company_id, product_id, inventory_uom_id) REFERENCES product (company_id, id, inventory_uom_id) ON UPDATE CASCADE,
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT fk_product_uom_item_product FOREIGN KEY (company_id, item_id, product_id) REFERENCES item (company_id, id, product_id),
    CONSTRAINT ck_product_uom_not_inventory CHECK (uom_id <> inventory_uom_id),
    -- the shape of the packaging hierarchy; its consistency with the factors is a command check (uom_packaging_inconsistent)
    CONSTRAINT ck_product_uom_packaging CHECK ((contains_uom_id IS NULL) = (contains_quantity IS NULL)
        AND (contains_quantity IS NULL OR (contains_quantity > 1 AND contains_quantity = trunc(contains_quantity) AND contains_uom_id <> uom_id))
        AND (factor_source <> 'packaging' OR contains_uom_id IS NOT NULL)),
    CONSTRAINT ck_product_uom_retired CHECK (is_active = (retired_at IS NULL) AND (is_active OR NOT is_default_pick_unit))
);
-- INV-603 reads created_at as the start of validity, so it never changes (S2 schema review note N2). The factor stays
-- correctable while nothing uses the row (ADR-0056 rule 5); that check needs other rows and is a command check.
CREATE FUNCTION product_uom_check_created_at() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    IF NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'product_uom.created_at is set once at insert (INV-603; ADR-0056 rule 4 note)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_product_uom_created_at_immutable BEFORE UPDATE OF created_at ON product_uom
    FOR EACH ROW EXECUTE FUNCTION product_uom_check_created_at();
-- At most one default pick unit per product, or per item for item-level rows (ADR-0056 rule 15).
CREATE UNIQUE INDEX ux_product_uom_default_pick_unit ON product_uom (company_id, product_id, item_id) NULLS NOT DISTINCT WHERE is_default_pick_unit;
-- At most one active row per product, item (a null item counting as one value) and unit; retired rows of the unit stay for
-- history and for the lines that snapshot them, and a replacement row keeps the unit code (ADR-0056 rules 4-5).
CREATE UNIQUE INDEX ux_product_uom_active_unit ON product_uom (company_id, product_id, item_id, uom_id) NULLS NOT DISTINCT WHERE is_active;
CREATE TABLE variant_attribute (                          -- ADR-0018 rule 6; variant_mode: ADR-0045 rule 15
    id            uuid PRIMARY KEY,
    company_id    uuid NOT NULL REFERENCES company (id),
    code          text NOT NULL,
    name          text NOT NULL,
    variant_mode  text NOT NULL DEFAULT 'variant' CONSTRAINT ck_variant_attribute_mode CHECK (variant_mode IN ('variant', 'line_option')),
    value_type    text NOT NULL DEFAULT 'list' CONSTRAINT ck_variant_attribute_value_type CHECK (value_type IN ('list', 'number')),   -- ADR-0046 rule 3
    uom_id          uuid REFERENCES uom (id),
    minimum_value   types.quantity,
    maximum_value   types.quantity,
    step_value      types.quantity CONSTRAINT ck_variant_attribute_step CHECK (step_value > 0),
    decimal_places  smallint CONSTRAINT ck_variant_attribute_decimal_places CHECK (decimal_places BETWEEN 0 AND 6),
    recorded_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, variant_mode),
    UNIQUE (company_id, id, variant_mode, value_type),
    UNIQUE (company_id, id, value_type),
    CONSTRAINT ck_variant_attribute_number CHECK ((value_type = 'number' AND minimum_value IS NOT NULL AND maximum_value IS NOT NULL AND step_value IS NOT NULL AND decimal_places IS NOT NULL)
                                               OR (value_type = 'list' AND uom_id IS NULL AND minimum_value IS NULL AND maximum_value IS NULL AND step_value IS NULL AND decimal_places IS NULL)),
    CONSTRAINT ck_variant_attribute_range CHECK (maximum_value IS NULL OR maximum_value >= minimum_value)
);
CREATE TABLE variant_attribute_value (                    -- carries its attribute's mode, so the mode cannot change once values exist
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL,
    variant_attribute_id  uuid NOT NULL,
    variant_mode          text NOT NULL,
    value_type            text NOT NULL DEFAULT 'list',
    code                  text NOT NULL,
    name                  text NOT NULL,
    numeric_value         types.quantity,                       -- a number of an item-defining characteristic, created with the item (ADR-0046 rules 3, 11)
    position              integer NOT NULL DEFAULT 0,
    is_custom             boolean NOT NULL DEFAULT false,      -- a line choosing it also gives free text (line options only)
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (variant_attribute_id, code),
    UNIQUE (variant_attribute_id, id),
    UNIQUE (variant_attribute_id, numeric_value),
    UNIQUE (company_id, variant_attribute_id, variant_mode, id),
    CONSTRAINT fk_variant_attribute_value_attribute FOREIGN KEY (company_id, variant_attribute_id, variant_mode, value_type)
        REFERENCES variant_attribute (company_id, id, variant_mode, value_type),
    CONSTRAINT ck_variant_attribute_value_custom CHECK (NOT is_custom OR variant_mode = 'line_option'),
    CONSTRAINT ck_variant_attribute_value_number CHECK ((value_type = 'number') = (numeric_value IS NOT NULL) AND (value_type = 'list' OR variant_mode = 'variant')),
    CONSTRAINT uq_variant_attribute_value_company_id_variant_attribute_id_id UNIQUE (company_id, variant_attribute_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE product_variant_attribute (                  -- the attributes of a product, of either mode
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL,
    product_id            uuid NOT NULL,
    variant_attribute_id  uuid NOT NULL,
    position              integer NOT NULL,
    is_required           boolean NOT NULL DEFAULT false,      -- line options: a line must choose a value
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_product_variant_attribute_product_id_variant_attribute_id UNIQUE (product_id, variant_attribute_id),
    UNIQUE (product_id, position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    FOREIGN KEY (company_id, variant_attribute_id) REFERENCES variant_attribute (company_id, id),
    CONSTRAINT uq_product_variant_attribute_company_key UNIQUE (company_id, product_id, variant_attribute_id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21); uq_product_variant_attribute_company_key named by hand: the convention name would exceed 63 bytes (ADR-0004 rule 6)
);
CREATE TABLE product_attribute_value (                    -- values a product allows for an attribute, of either mode; none listed = every value (ADR-0045 rule 15)
    id                          uuid PRIMARY KEY,   -- uq_product_attribute_value_key named by hand: the convention name would exceed 63 bytes (ADR-0004 rule 6)
    company_id                  uuid NOT NULL,
    product_id                  uuid NOT NULL,
    variant_attribute_id        uuid NOT NULL,
    variant_attribute_value_id  uuid NOT NULL,
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_product_attribute_value_key UNIQUE (product_id, variant_attribute_id, variant_attribute_value_id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT fk_product_attribute_value_attribute FOREIGN KEY (company_id, product_id, variant_attribute_id) REFERENCES product_variant_attribute (company_id, product_id, variant_attribute_id),
    CONSTRAINT fk_product_attribute_value_value FOREIGN KEY (company_id, variant_attribute_id, variant_attribute_value_id) REFERENCES variant_attribute_value (company_id, variant_attribute_id, id)
);
CREATE TABLE item (
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    product_id        uuid NOT NULL,
    code              text NOT NULL,                              -- the SKU
    variant_key       uuid[] NOT NULL DEFAULT '{}',               -- sorted value IDs (ADR-0018 rule 7)
    length            types.quantity,
    width             types.quantity,
    height            types.quantity,
    dimension_uom_id  uuid REFERENCES uom (id),
    net_weight        types.quantity,
    gross_weight      types.quantity,
    weight_uom_id     uuid REFERENCES uom (id),
    is_active         boolean NOT NULL DEFAULT true,
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_item_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_item_product FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    UNIQUE (id, product_id),
    UNIQUE (product_id, variant_key),
    CONSTRAINT ck_item_dimension_uom CHECK ((length IS NULL AND width IS NULL AND height IS NULL) OR dimension_uom_id IS NOT NULL),
    CONSTRAINT ck_item_weight_uom CHECK ((net_weight IS NULL AND gross_weight IS NULL) OR weight_uom_id IS NOT NULL),
    CONSTRAINT ck_item_dimensions_positive CHECK (coalesce(length, 1) > 0 AND coalesce(width, 1) > 0 AND coalesce(height, 1) > 0
                                                   AND coalesce(net_weight, 1) > 0 AND coalesce(gross_weight, 1) > 0),
    CONSTRAINT ck_item_gross_weight CHECK (net_weight IS NULL OR gross_weight IS NULL OR gross_weight >= net_weight),
    CONSTRAINT uq_item_company_id_id_product_id UNIQUE (company_id, id, product_id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE item_variant_value (                         -- one per variant-mode attribute of the item's product
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL,
    item_id                     uuid NOT NULL,
    product_id                  uuid NOT NULL,
    variant_attribute_id        uuid NOT NULL,
    variant_attribute_value_id  uuid NOT NULL,
    variant_mode                text NOT NULL DEFAULT 'variant' CONSTRAINT ck_item_variant_value_mode CHECK (variant_mode = 'variant'),
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_item_variant_value_item_id_variant_attribute_id UNIQUE (item_id, variant_attribute_id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, item_id, product_id) REFERENCES item (company_id, id, product_id),
    CONSTRAINT fk_item_variant_value_product_attribute FOREIGN KEY (company_id, product_id, variant_attribute_id) REFERENCES product_variant_attribute (company_id, product_id, variant_attribute_id),
    CONSTRAINT fk_item_variant_value_value FOREIGN KEY (company_id, variant_attribute_id, variant_mode, variant_attribute_value_id)
        REFERENCES variant_attribute_value (company_id, variant_attribute_id, variant_mode, id)        -- line options never make items
);
CREATE INDEX ix_item_variant_value_value ON item_variant_value (variant_attribute_value_id);
CREATE TABLE item_barcode (                              -- one barcode per packaging unit of an item (ADR-0018 rule 14)
    id          uuid PRIMARY KEY,                      -- a line or trace can name the row (ADR-0006 rule 1; ADR-0056 rule 25)
    company_id  uuid NOT NULL,
    item_id     uuid NOT NULL,
    uom_id      uuid NOT NULL REFERENCES uom (id),
    barcode     text NOT NULL,
    is_legacy_barcode  boolean NOT NULL DEFAULT false,   -- an old system's code kept on migration; set at creation (ADR-0061 rule 8)
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_item_barcode_barcode UNIQUE (company_id, barcode),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id)
);
CREATE INDEX ix_item_barcode_item_id ON item_barcode (item_id);
CREATE TABLE partner_item (                                -- a partner's own code, name and unit for an item (ADR-0019 rule 6)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    partner_id          uuid NOT NULL,
    item_id             uuid NOT NULL,
    partner_item_code   text NOT NULL,
    partner_item_name   text,
    partner_uom_text    text,                                    -- the unit as the partner writes it
    uom_id              uuid REFERENCES uom (id),                -- the matching unit of the item's product
    is_active           boolean NOT NULL DEFAULT true,
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (partner_id, partner_item_code),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT uq_partner_item_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE INDEX ix_partner_item_item_id ON partner_item (item_id);
CREATE TABLE item_manufacturer_part (                      -- a manufacturer's part number for an item, step 4 of component resolution (ADR-0062 rules 7, 19) [master_data]
    id                            uuid PRIMARY KEY,
    company_id                    uuid NOT NULL,
    item_id                       uuid NOT NULL,
    manufacturer_name             text NOT NULL,                -- as the manufacturer writes it
    normalized_manufacturer_name  text NOT NULL,                -- case folded, whitespace collapsed
    part_number                   text NOT NULL,
    normalized_part_number        text NOT NULL,                -- upper-cased, separators removed; letters and digits of any script
    is_active                     boolean NOT NULL DEFAULT true,
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    CONSTRAINT uq_item_manufacturer_part UNIQUE (company_id, normalized_manufacturer_name, normalized_part_number),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT ck_item_manufacturer_part_normalized CHECK (normalized_part_number ~ '^[[:alnum:]]+$' AND normalized_part_number = upper(normalized_part_number)
        AND normalized_manufacturer_name = lower(normalized_manufacturer_name))
);
CREATE TABLE code_series (                                 -- master-data code sequences, without fiscal year or branch (ADR-0062 rules 9, 19) [master_data]
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    record_kind          text NOT NULL CONSTRAINT ck_code_series_record_kind CHECK (record_kind IN ('product')),
    product_category_id  uuid,                                 -- a series of its own for one category, with its short code as prefix
    prefix               text NOT NULL DEFAULT '',
    next_value           bigint NOT NULL CONSTRAINT ck_code_series_next_value CHECK (next_value >= 1),   -- moved only by the numbering lock helper at execution
    format               text NOT NULL CONSTRAINT ck_code_series_format CHECK (format LIKE '%{counter:%}%'),
    recorded_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (company_id, record_kind, product_category_id),
    FOREIGN KEY (company_id, product_category_id) REFERENCES product_category (company_id, id)
);
CREATE TABLE product_category_requirement (                -- readiness rules per category, rules as data (ADR-0062 rules 9, 11, 19) [master_data]
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    product_category_id       uuid NOT NULL,
    requirement               text NOT NULL CONSTRAINT ck_product_category_requirement_requirement CHECK (requirement IN ('variant_attribute', 'dimensions', 'weights',
                                  'barcode', 'supplier_item', 'bill_of_materials', 'routing', 'production_version', 'cost_estimate', 'classification')),
    variant_attribute_id      uuid,
    classification_scheme_id  uuid,
    is_active                 boolean NOT NULL DEFAULT true,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (company_id, product_category_id, requirement, variant_attribute_id, classification_scheme_id),
    FOREIGN KEY (company_id, product_category_id) REFERENCES product_category (company_id, id),
    FOREIGN KEY (company_id, variant_attribute_id) REFERENCES variant_attribute (company_id, id),
    FOREIGN KEY (company_id, classification_scheme_id) REFERENCES classification_scheme (company_id, id),
    CONSTRAINT ck_product_category_requirement_target CHECK ((requirement = 'variant_attribute') = (variant_attribute_id IS NOT NULL)
        AND (requirement = 'classification') = (classification_scheme_id IS NOT NULL))
);
CREATE TABLE classification_scheme (
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    is_hierarchical boolean NOT NULL DEFAULT false, is_protected boolean NOT NULL DEFAULT false, UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE classification_value (
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    classification_scheme_id  uuid NOT NULL,
    code                      text NOT NULL,
    name                      text NOT NULL,
    parent_id                 uuid,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (classification_scheme_id, code),
    UNIQUE (classification_scheme_id, id),
    FOREIGN KEY (company_id, classification_scheme_id) REFERENCES classification_scheme (company_id, id),
    CONSTRAINT uq_classification_value_company_id_id UNIQUE (company_id, id),   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
    FOREIGN KEY (company_id, parent_id) REFERENCES classification_value (company_id, id),   -- company key (ADR-0017 rule 19 note, 2026-11-21)
    CONSTRAINT uq_classification_value_company_id_classification_scheme_id_id UNIQUE (company_id, classification_scheme_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE product_classification (                      -- one value per scheme per product (ADR-0018 rule 15)
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    product_id                uuid NOT NULL,
    classification_scheme_id  uuid NOT NULL,
    classification_value_id   uuid NOT NULL,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_product_classification_product_id_classification_scheme_id UNIQUE (product_id, classification_scheme_id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    FOREIGN KEY (company_id, classification_scheme_id) REFERENCES classification_scheme (company_id, id),
    FOREIGN KEY (company_id, classification_scheme_id, classification_value_id) REFERENCES classification_value (company_id, classification_scheme_id, id)
);

-- ===== Warehouses and bins [master_data owns warehouses; inventory owns zones and bins] (ADR-0020, ADR-0023, ADR-0031, ADR-0037) =====
CREATE TABLE warehouse (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL REFERENCES company (id),
    code                       text NOT NULL,
    name                       text NOT NULL,
    kind                       text NOT NULL CONSTRAINT ck_warehouse_kind CHECK (kind IN ('physical', 'transit', 'goods_sent')),
    site_id                    uuid,                                -- physical only, required (ADR-0068 rule 2); transit and goods_sent take the site of valuation_warehouse_id (master_data.contract.site_of_warehouse); fixed once the warehouse has a material document line (warehouse_site_fixed)
    branch_id                  uuid,
    address                    jsonb,                               -- the columns of partner_address as keys
    valuation_warehouse_id     uuid,                                -- transit and goods_sent only, naming a physical warehouse (ADR-0020 rule 2)
    processor_partner_id       uuid,                                -- physical only (ADR-0037 rule 1)
    working_calendar_id        uuid,
    is_bin_managed             boolean NOT NULL DEFAULT false,
    is_handling_unit_managed   boolean NOT NULL DEFAULT false,
    outbound_flow              text NOT NULL DEFAULT 'direct' CONSTRAINT ck_warehouse_outbound_flow CHECK (outbound_flow IN ('direct')),
    default_removal_strategy   text NOT NULL DEFAULT 'fifo' CONSTRAINT ck_warehouse_default_removal_strategy CHECK (default_removal_strategy IN ('fefo', 'fifo')),
    default_bin_id             uuid NOT NULL,                       -- every warehouse has one (ADR-0031 rule 7, INV-56); FK added below (cycle with bin)
    default_receiving_bin_id   uuid,
    default_shipping_bin_id    uuid,
    is_active                  boolean NOT NULL DEFAULT true,
    recorded_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, valuation_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, processor_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, working_calendar_id) REFERENCES working_calendar (company_id, id),
    CONSTRAINT ck_warehouse_valuation_warehouse CHECK ((kind = 'physical') = (valuation_warehouse_id IS NULL)),
    CONSTRAINT ck_warehouse_processor CHECK (processor_partner_id IS NULL OR (kind = 'physical' AND NOT is_bin_managed)),
    CONSTRAINT ck_warehouse_bin_managed CHECK (NOT is_bin_managed OR (kind = 'physical' AND default_receiving_bin_id IS NOT NULL AND default_shipping_bin_id IS NOT NULL)),
    FOREIGN KEY (company_id, site_id) REFERENCES site (company_id, id),
    CONSTRAINT ck_warehouse_site CHECK ((kind = 'physical') = (site_id IS NOT NULL))
);
-- One active processor warehouse per processor (ADR-0037 rule 1).
CREATE UNIQUE INDEX ux_warehouse_processor ON warehouse (company_id, processor_partner_id) WHERE is_active AND processor_partner_id IS NOT NULL;
-- The site roll-up and site_in_use (ADR-0068 rules 1, 5).
CREATE INDEX ix_warehouse_company_id_site_id ON warehouse (company_id, site_id) WHERE site_id IS NOT NULL;
CREATE TABLE zone (
    id uuid PRIMARY KEY, company_id uuid NOT NULL, warehouse_id uuid NOT NULL,
    code text NOT NULL, name text NOT NULL, UNIQUE (warehouse_id, code), UNIQUE (id, warehouse_id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_zone_company_id_id_warehouse_id UNIQUE (company_id, id, warehouse_id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE bin (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    warehouse_id             uuid NOT NULL,
    zone_id                  uuid NOT NULL,
    code                     text NOT NULL,
    barcode                  text NOT NULL,
    is_legacy_barcode        boolean NOT NULL DEFAULT false,   -- an old system's label code kept on migration; set at creation (ADR-0061 rule 8)
    bin_type                 text NOT NULL CONSTRAINT ck_bin_type CHECK (bin_type IN ('receiving', 'storage', 'picking', 'shipping', 'quality', 'returns', 'damage', 'production')),
    pick_sequence            integer NOT NULL DEFAULT 0,
    maximum_weight           types.quantity,
    maximum_volume           types.quantity,
    maximum_handling_units   integer,
    is_mixed_item_allowed    boolean NOT NULL DEFAULT true,
    is_mixed_lot_allowed     boolean NOT NULL DEFAULT true,
    is_blocked_for_putaway   boolean NOT NULL DEFAULT false,
    is_blocked_for_picking   boolean NOT NULL DEFAULT false,
    is_active                boolean NOT NULL DEFAULT true,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (warehouse_id, code),
    UNIQUE (company_id, barcode),
    UNIQUE (id, warehouse_id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_bin_zone FOREIGN KEY (company_id, zone_id, warehouse_id) REFERENCES zone (company_id, id, warehouse_id),
    CONSTRAINT uq_bin_company_id_id_warehouse_id UNIQUE (company_id, id, warehouse_id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
ALTER TABLE warehouse ADD CONSTRAINT fk_warehouse_default_bin FOREIGN KEY (company_id, default_bin_id, id) REFERENCES bin (company_id, id, warehouse_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE warehouse ADD CONSTRAINT fk_warehouse_default_receiving_bin FOREIGN KEY (company_id, default_receiving_bin_id, id) REFERENCES bin (company_id, id, warehouse_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE warehouse ADD CONSTRAINT fk_warehouse_default_shipping_bin FOREIGN KEY (company_id, default_shipping_bin_id, id) REFERENCES bin (company_id, id, warehouse_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE lot (                                         -- ADR-0020 rule 17 [inventory]
    id uuid PRIMARY KEY, company_id uuid NOT NULL, item_id uuid NOT NULL,
    code text NOT NULL, expiry_date date, manufacture_date date, UNIQUE (item_id, code),
    best_before_date date,                                 -- ADR-0063 rule 26: (15) best before, kept apart from expiry_date
    barcode text, UNIQUE (company_id, barcode),            -- the lot's own internal label code, registered across types (ADR-0061 rules 7-8)
    CONSTRAINT ck_lot_code_not_empty CHECK (code <> ''),   -- any code is kept as it comes, but never an empty one (ADR-0061 rule 8)
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT ck_lot_dates CHECK (expiry_date IS NULL OR manufacture_date IS NULL OR expiry_date >= manufacture_date),
    CONSTRAINT ck_lot_best_before CHECK (best_before_date IS NULL OR manufacture_date IS NULL OR best_before_date >= manufacture_date),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_lot_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE TABLE serial_number (                               -- ADR-0020 rule 17 [inventory]
    id uuid PRIMARY KEY, company_id uuid NOT NULL, item_id uuid NOT NULL,
    code text NOT NULL, UNIQUE (item_id, code),
    barcode text, UNIQUE (company_id, barcode),            -- the serial's own internal label code (ADR-0061 rules 7-8)
    CONSTRAINT ck_serial_number_code_not_empty CHECK (code <> ''),   -- any code is kept as it comes, but never an empty one (ADR-0061 rule 8)
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_serial_number_company_id_id UNIQUE (company_id, id)   -- target of company keys (ADR-0017 rule 19 note, 2026-11-21)
);

-- ===== Price list entries [master_data] (ADR-0045) =====
CREATE TABLE price_list_entry (
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL,
    price_list_id     uuid NOT NULL,
    item_id           uuid,
    product_id        uuid,                                          -- the base price of a configurable product's configured items (ADR-0046 rule 15)
    uom_id            uuid NOT NULL REFERENCES uom (id),
    minimum_quantity  types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_price_list_entry_minimum_quantity CHECK (minimum_quantity >= 0),
    start_date        date NOT NULL,
    end_date          date,                                          -- inclusive (ADR-0027 rule 12); null = open
    unit_price        types.unit_price NOT NULL CONSTRAINT ck_price_list_entry_unit_price CHECK (unit_price >= 0),
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_price_list_entry_list FOREIGN KEY (company_id, price_list_id) REFERENCES price_list (company_id, id),
    CONSTRAINT fk_price_list_entry_item FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT fk_price_list_entry_product FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT ck_price_list_entry_target CHECK ((item_id IS NULL) <> (product_id IS NULL)),
    CONSTRAINT ck_price_list_entry_dates CHECK (end_date IS NULL OR end_date >= start_date),
    -- Entries of one list, item (or product), unit and break never overlap in dates (ADR-0045 rule 3).
    CONSTRAINT ex_price_list_entry_overlap EXCLUDE USING gist (
        price_list_id WITH =, (coalesce(item_id, product_id)) WITH =, uom_id WITH =, minimum_quantity WITH =,
        daterange(start_date, end_date, '[]') WITH &&)
);
CREATE INDEX ix_price_list_entry_item_id ON price_list_entry (item_id);
CREATE INDEX ix_price_list_entry_product_id ON price_list_entry (product_id) WHERE product_id IS NOT NULL;
CREATE TABLE price_list_option_extra (                     -- extra per inventory unit for a chosen value: a line option, or any value of a configurable product (ADR-0045 rule 17; ADR-0046 rule 15)
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL,
    price_list_id               uuid NOT NULL,
    product_id                  uuid,                               -- null: every product with that option
    variant_attribute_id        uuid NOT NULL,
    variant_attribute_value_id  uuid NOT NULL,
    variant_mode                text NOT NULL DEFAULT 'line_option',   -- must match the value's mode; variant mode only for configurable products (command, option_extra_not_allowed)
    start_date                  date NOT NULL,
    end_date                    date,
    unit_price_extra            types.unit_price NOT NULL,          -- may be negative (a cheaper option)
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id, price_list_id) REFERENCES price_list (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT fk_price_list_option_extra_value FOREIGN KEY (company_id, variant_attribute_id, variant_mode, variant_attribute_value_id)
        REFERENCES variant_attribute_value (company_id, variant_attribute_id, variant_mode, id),
    CONSTRAINT ck_price_list_option_extra_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ex_price_list_option_extra_overlap EXCLUDE USING gist (
        price_list_id WITH =, (coalesce(product_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        variant_attribute_value_id WITH =, daterange(start_date, end_date, '[]') WITH &&)
);

-- ===== Barcode registry [master_data] (ADR-0061 rules 7-9, 11) =====
-- One row per barcode of a company across every type, so a scan never means two things. Rows are written only by the
-- trigger barcode_register on the typed tables (item_barcode, bin, lot and serial_number here; handling_unit in
-- DS-22-09-42-commercial-inventory.sql; document numbers of barcoded types in DS-05-platform.sql). Commands insert only
-- reserved rows (type internal without retired_type: CreateBarcodeReservation) and delete only reserved or retired rows
-- (DeleteBarcodeReservation). The registry is derived from the typed rows, so it has no surrogate ID. A barcode whose
-- owner row is deleted or changes its barcode stays as type internal with retired_type and retired_owner_id, so a stale
-- label never resolves to another object, and the same owner may take it back.
CREATE TABLE barcode (
    id                uuid PRIMARY KEY DEFAULT uuidv7(),   -- barcode_register inserts the rows (ADR-0006 rule 2)
    company_id        uuid NOT NULL REFERENCES company (id),
    barcode           text NOT NULL,                       -- normalized: a GTIN as 14 digits, an SSCC as 18, an internal code in upper case
    barcode_type      text NOT NULL CONSTRAINT ck_barcode_type CHECK (barcode_type IN ('item_unit', 'bin', 'handling_unit', 'lot', 'serial', 'document', 'internal')),
    encoding          text NOT NULL CONSTRAINT ck_barcode_encoding CHECK (encoding IN ('gtin', 'sscc', 'internal')),
    is_legacy         boolean NOT NULL DEFAULT false,      -- an old system's code: encoding internal, may start with a digit, never read as GS1 (rule 8)
    retired_type      text CONSTRAINT ck_barcode_retired_type CHECK (retired_type IN ('item_unit', 'bin', 'handling_unit', 'lot', 'serial', 'document')),
    retired_owner_id  uuid,                                -- the item of an item barcode, else the owner row itself; it may take the code back
    retired_at        timestamptz,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_barcode_company_id_barcode UNIQUE (company_id, barcode),
    -- GS1 keys are digits (check digits: the trigger); internal codes start with an upper-case letter; legacy codes with
    -- a letter or a digit (rule 8)
    CONSTRAINT ck_barcode_format CHECK ((encoding = 'gtin' AND NOT is_legacy AND barcode ~ '^[0-9]{14}$')
        OR (encoding = 'sscc' AND NOT is_legacy AND barcode ~ '^[0-9]{18}$')
        OR (encoding = 'internal' AND NOT is_legacy AND barcode ~ '^[A-Z][A-Z0-9./_-]{0,47}$')
        OR (encoding = 'internal' AND is_legacy AND barcode ~ '^[A-Z0-9][A-Z0-9./_-]{0,47}$')),
    CONSTRAINT ck_barcode_type_encoding CHECK (encoding = 'internal' OR barcode_type = 'internal'
        OR (barcode_type = 'item_unit' AND encoding = 'gtin') OR (barcode_type = 'handling_unit' AND encoding = 'sscc')),
    CONSTRAINT ck_barcode_retired CHECK ((retired_type IS NULL) = (retired_at IS NULL) AND (retired_type IS NULL) = (retired_owner_id IS NULL)
        AND (retired_type IS NULL OR barcode_type = 'internal'))
);
-- Codes of 1 to 14 digits are one code when their digits padded to 14 agree: a GTIN and a numeric legacy code, or two
-- numeric legacy codes, never mean the same digits. An index, not a test in the trigger, so concurrent inserts are held
-- too; the trigger maps its violation to barcode_taken (rule 7).
CREATE UNIQUE INDEX ux_barcode_numeric_padded ON barcode (company_id, lpad(barcode, 14, '0')) WHERE barcode ~ '^[0-9]{1,14}$';
CREATE TABLE gs1_company_prefix (                          -- the company's GS1 company prefixes (ADR-0061 rule 11)
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL REFERENCES company (id),
    prefix                text NOT NULL CONSTRAINT ck_gs1_company_prefix_prefix CHECK (prefix ~ '^[0-9]{4,12}$'),   -- the valid length range is unverified (rule 11)
    is_active             boolean NOT NULL DEFAULT true,   -- false: generates nothing new, stays the company's own (the SSCC cleanup job)
    is_generation_prefix  boolean NOT NULL DEFAULT false,  -- new GTIN-13s take this prefix; at most one per company, and active
    next_item_reference   bigint NOT NULL DEFAULT 0,       -- of the next generated GTIN-13; a prefix that generated one is never deleted
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, prefix),
    CONSTRAINT ck_gs1_company_prefix_reference CHECK (next_item_reference >= 0 AND next_item_reference <= 10 ^ (12 - length(prefix))),
    CONSTRAINT ck_gs1_company_prefix_generation_active CHECK (is_active OR NOT is_generation_prefix),
    -- no prefix starts another (rule 11; INV-624): each prefix covers a range of 12-digit numbers, and the ranges of one
    -- company never overlap, at every isolation level; btree_gist is installed (ADR-0022 rule 8). Commands report it as
    -- gs1_prefix_invalid. A prefix has at most 12 digits, so both bounds fit bigint.
    CONSTRAINT ex_gs1_company_prefix_overlap EXCLUDE USING gist (company_id WITH =,
        int8range(rpad(prefix, 12, '0')::bigint, rpad(prefix, 12, '9')::bigint, '[]') WITH &&)
);
CREATE UNIQUE INDEX ux_gs1_company_prefix_generation ON gs1_company_prefix (company_id) WHERE is_generation_prefix;
-- GS1 mod-10 check over the whole key, check digit included: weights 3, 1, 3, ... from the rightmost data digit (rule 4).
CREATE FUNCTION gs1_check_digit_valid(digits text) RETURNS boolean LANGUAGE sql IMMUTABLE SET search_path = nativeflows, pg_temp AS $$
    SELECT digits ~ '^[0-9]{8,18}$' AND (SELECT sum(substr(digits, i, 1)::int * CASE WHEN (length(digits) - i) % 2 = 1 THEN 3 ELSE 1 END)
                                           FROM generate_series(1, length(digits)) AS i) % 10 = 0
$$;
-- The normalized form (rule 7): GTIN-8, GTIN-12 and GTIN-13 padded to 14 digits; other digits as they are; letters upper case.
CREATE FUNCTION barcode_normalize(value text) RETURNS text LANGUAGE sql IMMUTABLE SET search_path = nativeflows, pg_temp AS $$
    SELECT CASE WHEN value ~ '^([0-9]{8}|[0-9]{12}|[0-9]{13})$' THEN lpad(value, 14, '0') WHEN value ~ '^[0-9]+$' THEN value ELSE upper(value) END
$$;
-- AFTER trigger of every typed table: TG_ARGV[0] is the barcode type, TG_ARGV[1] the column, TG_ARGV[2] the owner column
-- (item_id for an item barcode, id otherwise). A document registers its number in upper case, and only while
-- is_barcoded (rule 9); every other table must store the normalized form. A row with is_legacy_barcode registers a
-- legacy code: upper case, never padded or checked as a GTIN (rule 8); the flag never changes. A code retired from the
-- same type and owner comes back to it; any other collision is barcode_taken (rule 7).
CREATE FUNCTION barcode_register() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
DECLARE
    v_type   text := TG_ARGV[0];
    v_col    text := TG_ARGV[1];
    v_ocol   text := TG_ARGV[2];
    v_old    text;
    v_new    text;
    v_enc    text;
    v_norm   text;
    v_owner  uuid;
    v_legacy boolean := false;
BEGIN
    IF TG_OP = 'UPDATE' AND (to_jsonb(OLD) ->> 'is_legacy_barcode') IS DISTINCT FROM (to_jsonb(NEW) ->> 'is_legacy_barcode') THEN
        RAISE EXCEPTION 'is_legacy_barcode is set at creation and never changes (ADR-0061 rule 8)' USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP <> 'INSERT' THEN
        v_old := to_jsonb(OLD) ->> v_col;
        IF v_type = 'document' THEN
            v_old := CASE WHEN (to_jsonb(OLD) ->> 'is_barcoded')::boolean THEN upper(v_old) END;
        END IF;
    END IF;
    IF TG_OP <> 'DELETE' THEN
        v_new := to_jsonb(NEW) ->> v_col;
        v_legacy := coalesce((to_jsonb(NEW) ->> 'is_legacy_barcode')::boolean, false);
        IF v_type = 'document' THEN
            v_new := CASE WHEN (to_jsonb(NEW) ->> 'is_barcoded')::boolean THEN upper(v_new) END;
        END IF;
    END IF;
    IF v_old IS NOT DISTINCT FROM v_new THEN
        RETURN NULL;
    END IF;
    IF v_old IS NOT NULL THEN
        UPDATE barcode SET barcode_type = 'internal', retired_type = v_type, retired_owner_id = (to_jsonb(OLD) ->> v_ocol)::uuid, retired_at = now()
         WHERE company_id = OLD.company_id AND barcode = v_old AND barcode_type = v_type;
    END IF;
    IF v_new IS NOT NULL THEN
        v_norm := CASE WHEN v_legacy THEN upper(v_new) ELSE barcode_normalize(v_new) END;
        IF v_new <> v_norm THEN
            RAISE EXCEPTION 'barcode_not_normalized: % is stored as %', v_new, v_norm USING ERRCODE = 'check_violation';
        END IF;
        v_enc := CASE WHEN v_legacy THEN 'internal' WHEN v_new ~ '^[0-9]{14}$' THEN 'gtin' WHEN v_new ~ '^[0-9]{18}$' THEN 'sscc' ELSE 'internal' END;
        IF v_enc <> 'internal' AND NOT gs1_check_digit_valid(v_new) THEN
            RAISE EXCEPTION 'barcode_format_invalid: wrong check digit in %', v_new USING ERRCODE = 'check_violation';
        END IF;
        v_owner := (to_jsonb(NEW) ->> v_ocol)::uuid;
        UPDATE barcode SET barcode_type = v_type, retired_type = NULL, retired_owner_id = NULL, retired_at = NULL
         WHERE company_id = NEW.company_id AND barcode = v_new AND barcode_type = 'internal' AND retired_type = v_type
           AND retired_owner_id = v_owner AND is_legacy = v_legacy;
        IF NOT FOUND THEN
            BEGIN
                INSERT INTO barcode (company_id, barcode, barcode_type, encoding, is_legacy) VALUES (NEW.company_id, v_new, v_type, v_enc, v_legacy);
            EXCEPTION WHEN unique_violation THEN
                RAISE EXCEPTION 'barcode_taken: % or its digits padded to 14 are registered in the company already', v_new USING ERRCODE = 'unique_violation';
            END;
        END IF;
    END IF;
    RETURN NULL;
END
$$;
CREATE TRIGGER trg_item_barcode_register AFTER INSERT OR UPDATE OF barcode, is_legacy_barcode OR DELETE ON item_barcode
    FOR EACH ROW EXECUTE FUNCTION barcode_register('item_unit', 'barcode', 'item_id');
CREATE TRIGGER trg_bin_register AFTER INSERT OR UPDATE OF barcode, is_legacy_barcode OR DELETE ON bin
    FOR EACH ROW EXECUTE FUNCTION barcode_register('bin', 'barcode', 'id');
CREATE TRIGGER trg_lot_register AFTER INSERT OR UPDATE OF barcode OR DELETE ON lot
    FOR EACH ROW EXECUTE FUNCTION barcode_register('lot', 'barcode', 'id');
CREATE TRIGGER trg_serial_number_register AFTER INSERT OR UPDATE OF barcode OR DELETE ON serial_number
    FOR EACH ROW EXECUTE FUNCTION barcode_register('serial', 'barcode', 'id');

-- ===== Partner relationships, external IDs, custom fields and reasons [master_data] (ADR-0074) =====
-- Four small company tables that the commercial documents, the stock documents and the integrations read. They depend only
-- on company, partner and partner_address, so master data and crm stay independent of the ledger, tax, inventory, cash and
-- production (the CRM-only profile).
CREATE TABLE partner_relationship (                        -- [master_data] ADR-0074 rules 1-3; company data, change-tracked
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,                      -- the sold-to party (customers) or the ordered-from party (suppliers)
    related_partner_id uuid NOT NULL,                      -- the ship-to, bill-to, payer, invoicing party or payee
    role               text NOT NULL CONSTRAINT ck_partner_relationship_role CHECK (role IN ('ship_to', 'bill_to', 'payer', 'invoicing_party', 'payee')),
    address_id         uuid,                               -- the related partner's address to copy by default (ship_to, bill_to, invoicing_party)
    is_default         boolean NOT NULL DEFAULT false,     -- at most one active default per partner and role
    is_active          boolean NOT NULL DEFAULT true,
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, partner_id, related_partner_id, role),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, related_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, related_partner_id, address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_partner_relationship_not_self CHECK (partner_id <> related_partner_id),
    CONSTRAINT ck_partner_relationship_address CHECK (address_id IS NULL OR role IN ('ship_to', 'bill_to', 'invoicing_party')),
    CONSTRAINT ck_partner_relationship_default CHECK (NOT is_default OR is_active)
);
CREATE UNIQUE INDEX ux_partner_relationship_default ON partner_relationship (company_id, partner_id, role) WHERE is_default;
CREATE INDEX ix_partner_relationship_related_partner_id ON partner_relationship (company_id, related_partner_id);

CREATE TABLE external_id_map (                             -- [master_data] ADR-0074 rule 7; replaces the undefined import_key_map of ADR-0044 rule 5
    id            uuid PRIMARY KEY,   -- uq_external_id_map_key named by hand: the convention name would exceed 63 bytes (ADR-0004 rule 6)
    company_id    uuid NOT NULL REFERENCES company (id),
    source_system text NOT NULL CONSTRAINT ck_external_id_map_source_system CHECK (source_system ~ '^[a-z][a-z0-9_.-]{0,39}$'),
    table_name    text NOT NULL CONSTRAINT ck_external_id_map_table_name CHECK (table_name ~ '^[a-z][a-z0-9_]*$'),
    external_key  text NOT NULL CONSTRAINT ck_external_id_map_external_key CHECK (length(btrim(external_key)) > 0 AND length(external_key) <= 200),
    entity_id     uuid NOT NULL,                           -- polymorphic: the row of table_name; checked by INV-860
    recorded_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_external_id_map_key UNIQUE (company_id, source_system, table_name, external_key),
    CONSTRAINT uq_external_id_map_entity UNIQUE (company_id, source_system, table_name, entity_id),
    CONSTRAINT ck_external_id_map_source_system_reserved CHECK (source_system <> 'group')   -- reserved for the group key until the distribution command exists (rule 7 note; external_id_source_reserved)
);
CREATE INDEX ix_external_id_map_entity_id ON external_id_map (company_id, entity_id);
-- The lookup of ADR-0074 rule 7: the entity of an external key, and the external key of an entity, within one source system.
CREATE FUNCTION external_id_resolve(p_company_id uuid, p_source_system text, p_table_name text, p_external_key text) RETURNS uuid LANGUAGE sql STABLE SET search_path = nativeflows, pg_temp AS $$
    SELECT entity_id FROM external_id_map WHERE company_id = p_company_id AND source_system = p_source_system AND table_name = p_table_name AND external_key = p_external_key
$$;
CREATE FUNCTION external_key_of(p_company_id uuid, p_source_system text, p_table_name text, p_entity_id uuid) RETURNS text LANGUAGE sql STABLE SET search_path = nativeflows, pg_temp AS $$
    SELECT external_key FROM external_id_map WHERE company_id = p_company_id AND source_system = p_source_system AND table_name = p_table_name AND entity_id = p_entity_id
$$;

CREATE TABLE custom_field_definition (                     -- [master_data] ADR-0074 rules 8, 9; company data, change-tracked
    id            uuid PRIMARY KEY,
    company_id    uuid NOT NULL REFERENCES company (id),
    target_table  text NOT NULL CONSTRAINT ck_custom_field_definition_target_table CHECK (target_table IN (
                      'partner', 'product', 'item', 'quotation', 'sales_order', 'delivery', 'sales_invoice',
                      'purchase_order', 'goods_receipt', 'purchase_invoice', 'production_order')),   -- the tables with a custom_values column
    code          text NOT NULL CONSTRAINT ck_custom_field_definition_code CHECK (code ~ '^[a-z][a-z0-9_]{0,39}$'),   -- the key in custom_values; never changed
    label         text NOT NULL,                           -- in the company's language; others in data_translation (ADR-0018 rule 17)
    data_type     text NOT NULL CONSTRAINT ck_custom_field_definition_data_type CHECK (data_type IN ('text', 'integer', 'decimal', 'boolean', 'date', 'choice')),
    validation    jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_custom_field_definition_validation CHECK (jsonb_typeof(validation) = 'object'),   -- the data type's bounds, pattern or choices
    is_required   boolean NOT NULL DEFAULT false,
    field_class   text CONSTRAINT ck_custom_field_definition_field_class CHECK (field_class IN ('cost', 'margin', 'sensitive_personal')),   -- ADR-0017 rule 10; sensitive_personal: ADR-0079 rule 11
    is_personal_data boolean NOT NULL,                     -- no default: the command states it (ADR-0079 rule 2); ADR-0074 rule 8: personal-labeled for the LLM gateway (spec 17) and cleared on erasure (ADR-0038)
    is_active     boolean NOT NULL DEFAULT true,           -- a retired field keeps its values and is never deleted
    recorded_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, target_table, code),
    UNIQUE (company_id, id)
);

CREATE TABLE reason (                                      -- [master_data] ADR-0074 rules 13, 14; company data, change-tracked
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    kind        text NOT NULL CONSTRAINT ck_reason_kind CHECK (kind IN ('cancel', 'reject', 'return', 'scrap', 'count_difference', 'block', 'other_receipt', 'other_issue')),
    code        text NOT NULL CONSTRAINT ck_reason_code CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    name        text NOT NULL,                             -- in the company's language; others in data_translation (ADR-0018 rule 17)
    is_active   boolean NOT NULL DEFAULT true,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, kind, code),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, kind)                          -- a column that takes one kind names it, so the key holds the kind
);

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
    v_tables            text[] := ARRAY['currency', 'company_currency_activation', 'uom', 'uom_conversion', 'uom_alias', 'company', 'branch',
        'print_profile', 'business_unit', 'cost_center', 'working_calendar', 'working_calendar_holiday', 'site',
        'data_translation', 'partner_group', 'partner_tax_group', 'item_group', 'valuation_class', 'item_tax_group',
        'partner', 'project', 'partner_role', 'payment_method', 'incoterm', 'delivery_method', 'price_list',
        'customer_profile', 'supplier_profile', 'employee_profile', 'partner_address', 'partner_bank_account', 'contact',
        'product_category', 'storage_condition', 'handling_unit_type', 'product', 'product_uom', 'variant_attribute',
        'variant_attribute_value', 'product_variant_attribute', 'product_attribute_value', 'item', 'item_variant_value',
        'item_barcode', 'partner_item', 'item_manufacturer_part', 'code_series', 'product_category_requirement',
        'classification_scheme', 'classification_value', 'product_classification', 'warehouse', 'zone', 'bin', 'lot',
        'serial_number', 'price_list_entry', 'price_list_option_extra', 'barcode', 'gs1_company_prefix',
        'partner_relationship', 'external_id_map', 'custom_field_definition', 'reason'];
    v_append_only       text[] := ARRAY[]::text[];
    v_refuse_truncate   text[] := ARRAY[]::text[];
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
-- Shared reference catalogs (v_shared, gen_overview.RLS_SHARED_READ) also get shared_read_policy: every company reads
-- their null rows, which only the installation scope writes (S2 closure, 2026-11-21).
-- A table whose row is a company (v_self, gen_overview.RLS_SELF) compares its own id with the settings instead.
-- Lab gen_overview.py --check compares this section with what schema_phase_b.py writes.
DO $$
DECLARE
    v_tables    text[] := ARRAY['company_currency_activation', 'uom', 'uom_alias', 'branch', 'print_profile', 'business_unit', 'cost_center',
        'working_calendar', 'working_calendar_holiday', 'site', 'data_translation', 'partner_group', 'partner_tax_group',
        'item_group', 'valuation_class', 'item_tax_group', 'partner', 'project', 'partner_role', 'payment_method',
        'delivery_method', 'price_list', 'customer_profile', 'supplier_profile', 'employee_profile', 'partner_address',
        'partner_bank_account', 'contact', 'product_category', 'storage_condition', 'handling_unit_type', 'product',
        'product_uom', 'variant_attribute', 'variant_attribute_value', 'product_variant_attribute',
        'product_attribute_value', 'item', 'item_variant_value', 'item_barcode', 'partner_item', 'item_manufacturer_part',
        'code_series', 'product_category_requirement', 'classification_scheme', 'classification_value',
        'product_classification', 'warehouse', 'zone', 'bin', 'lot', 'serial_number', 'price_list_entry',
        'price_list_option_extra', 'barcode', 'gs1_company_prefix', 'partner_relationship', 'external_id_map',
        'custom_field_definition', 'reason'];
    v_nullable  text[] := ARRAY['uom']::text[];
    v_shared    text[] := ARRAY['uom']::text[];
    v_self      text[] := ARRAY['company']::text[];
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
        IF v_table = ANY (v_shared) THEN
            EXECUTE format('CREATE POLICY shared_read_policy ON %I FOR SELECT USING (company_id IS NULL)', v_table);
        END IF;
    END LOOP;
    FOREACH v_table IN ARRAY v_self LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', v_table);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', v_table);
        EXECUTE format('CREATE POLICY company_policy ON %I USING (id::text = current_setting(''nativeflows.company_id'', true))', v_table);
        EXECUTE format('CREATE POLICY company_ids_policy ON %I FOR SELECT USING (id::text = ANY (string_to_array(current_setting(''nativeflows.company_ids'', true), '','')))', v_table);
    END LOOP;
END $$;
-- ===== end of row-level security =====
