-- DS-20 master data: DDL draft for ADR-0018, ADR-0019, ADR-0020, ADR-0023, ADR-0024, ADR-0027 rule 5, ADR-0031,
-- ADR-0033, ADR-0037 and ADR-0045, with the columns ADR-0046 (product configuration) adds; its tables are in DS-56-product-configuration.sql.
-- PostgreSQL 18. Loaded together with DS-06 and tested in the design lab (docs/reviews/2026-11-14-design-validation,
-- t05_master_data.py). The ADRs win if this file disagrees.
-- Tables live in schema `erpme` (ADR-0022 rule 7); domains in schema `types` (ADR-0006 rule 8). Keys are shown inline;
-- in migrations they get names from the MetaData naming convention (ADR-0004 rule 15). btree_gist is installed (ADR-0022 rule 8).
-- Every table carries company_id, FORCE ROW LEVEL SECURITY and the generated company policy (ADR-0022 rule 8), except
-- the global catalogs currency, uom (core rows have a null company_id and are readable by all), uom_conversion, and
-- company itself, whose policy compares its own id. The lab checks this list (ADR-0045 rule 14).
-- Owner module per table in brackets (ADR-0022 rule 2). Referenced tables defined elsewhere: user_account (DS-15),
-- account and payment_term (DS-06, ledger), tax groups' matrix (ADR-0041, tax).
-- IDs are UUIDv7 from context.new_id or the client (ADR-0006 rule 3); no ID defaults.
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
    is_active      boolean NOT NULL DEFAULT true
);
CREATE TABLE company_currency_activation (                 -- a company activates the currencies it uses (ADR-0011 rule 7)
    company_id  uuid NOT NULL REFERENCES company (id),
    currency    text NOT NULL REFERENCES currency (code),
    PRIMARY KEY (company_id, currency)
);
CREATE TABLE uom (                                         -- ADR-0018 rule 8; core rows have company_id null
    id              uuid PRIMARY KEY,
    company_id      uuid REFERENCES company (id),
    code            text NOT NULL,
    quantity_kind   text NOT NULL CONSTRAINT ck_uom_quantity_kind CHECK (quantity_kind IN ('count', 'mass', 'length', 'area', 'volume', 'time')),
    decimal_places  smallint NOT NULL CONSTRAINT ck_uom_decimal_places CHECK (decimal_places BETWEEN 0 AND 6),
    is_active       boolean NOT NULL DEFAULT true,
    CONSTRAINT ck_uom_company_code CHECK ((company_id IS NULL) = (code NOT LIKE 'x-%'))
);
CREATE UNIQUE INDEX ux_uom_core_code ON uom (code) WHERE company_id IS NULL;
CREATE UNIQUE INDEX ux_uom_company_code ON uom (company_id, code) WHERE company_id IS NOT NULL;
CREATE TABLE uom_conversion (                              -- units of one kind, exact ratio of two positive integers (ADR-0006 rule 11; ADR-0018 rule 8)
    from_uom_id  uuid NOT NULL REFERENCES uom (id),
    to_uom_id    uuid NOT NULL REFERENCES uom (id),
    numerator    bigint NOT NULL CONSTRAINT ck_uom_conversion_numerator CHECK (numerator > 0),       -- 1 from = numerator/denominator to
    denominator  bigint NOT NULL CONSTRAINT ck_uom_conversion_denominator CHECK (denominator > 0),
    PRIMARY KEY (from_uom_id, to_uom_id),
    CONSTRAINT ck_uom_conversion_distinct CHECK (from_uom_id <> to_uom_id)
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
    valuation_area_level      text NOT NULL CONSTRAINT ck_company_valuation_area_level CHECK (valuation_area_level IN ('company', 'warehouse')),
    fiscal_calendar_owner_id  uuid NOT NULL REFERENCES user_account (id),
    fiscal_year_lead_days     integer NOT NULL DEFAULT 30,
    default_language          text NOT NULL,                       -- BCP 47, set at company creation from the package; documents and partners may override (ADR-0016 rule 19)
    is_active                 boolean NOT NULL DEFAULT true
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
    UNIQUE NULLS NOT DISTINCT (company_id, branch_id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id)
);
CREATE TABLE cost_center (
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    code        text NOT NULL,
    name        text NOT NULL,
    kind        text NOT NULL CONSTRAINT ck_cost_center_kind CHECK (kind IN ('production', 'production_service', 'selling', 'administration', 'other')),
    parent_id   uuid,
    branch_id   uuid,
    is_active   boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id)
);
CREATE TABLE working_calendar (                            -- ADR-0024 rule 4
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    code              text NOT NULL,
    name              text NOT NULL,
    working_weekdays  smallint[] NOT NULL CONSTRAINT ck_working_calendar_weekdays CHECK (working_weekdays <@ ARRAY[1,2,3,4,5,6,7]::smallint[]),  -- ISO weekdays
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
CREATE TABLE working_calendar_holiday (                    -- copied from a package template entry, or added by the company (ADR-0045 rule 10)
    company_id           uuid NOT NULL,
    working_calendar_id  uuid NOT NULL,
    holiday_date         date NOT NULL,
    name                 text,
    basis                jsonb NOT NULL,
    PRIMARY KEY (working_calendar_id, holiday_date),
    FOREIGN KEY (company_id, working_calendar_id) REFERENCES working_calendar (company_id, id)
);
CREATE TABLE data_translation (                            -- ADR-0018 rule 17
    company_id  uuid NOT NULL REFERENCES company (id),
    table_name  text NOT NULL,
    row_id      uuid NOT NULL,
    field       text NOT NULL,
    language    text NOT NULL,
    text        text NOT NULL,
    PRIMARY KEY (company_id, table_name, row_id, field, language)
);

-- ===== Groups copied from package templates [master_data] =====
CREATE TABLE partner_group (
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code)
);
CREATE TABLE partner_tax_group (                           -- read by the tax matrix (ADR-0041 rule 3)
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    directions text[] NOT NULL CONSTRAINT ck_partner_tax_group_directions CHECK (directions <@ ARRAY['sale','purchase']::text[] AND cardinality(directions) > 0),
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code)
);
CREATE TABLE item_group (
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code)
);
CREATE TABLE valuation_class (
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code)
);
CREATE TABLE item_tax_group (                              -- read by the tax matrix (ADR-0041 rule 3)
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    basis jsonb NOT NULL, is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code)
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
    partner_group_id          uuid REFERENCES partner_group (id),
    partner_tax_group_id      uuid REFERENCES partner_tax_group (id),
    preferred_language        text,
    superseded_by_partner_id  uuid,                               -- ADR-0019 rule 19 (interim)
    is_active                 boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, superseded_by_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_partner_not_own_parent CHECK (parent_partner_id IS NULL OR parent_partner_id <> id)
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
    UNIQUE (company_id, code),
    FOREIGN KEY (company_id, customer_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_project_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);
CREATE TABLE partner_role (
    company_id  uuid NOT NULL,
    partner_id  uuid NOT NULL,
    role        text NOT NULL CONSTRAINT ck_partner_role_role CHECK (role IN ('customer', 'supplier', 'employee')),
    is_active   boolean NOT NULL DEFAULT true,
    PRIMARY KEY (partner_id, role),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id)
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
    company_id                         uuid NOT NULL,
    partner_id                         uuid PRIMARY KEY,
    receivable_account_id              uuid NOT NULL REFERENCES account (id),
    payment_term_id                    uuid REFERENCES payment_term (id),
    credit_limit                       types.amount,
    credit_limit_currency              text REFERENCES currency (code),
    price_list_id                      uuid,
    price_list_kind                    text NOT NULL DEFAULT 'sale' CONSTRAINT ck_customer_profile_price_list_kind CHECK (price_list_kind = 'sale'),
    salesperson_id                     uuid,                          -- a partner with the employee role (ADR-0027 rule 6)
    currency                           text REFERENCES currency (code),
    minimum_remaining_shelf_life_days  integer,
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT fk_customer_profile_price_list FOREIGN KEY (company_id, price_list_id, price_list_kind) REFERENCES price_list (company_id, id, kind),
    FOREIGN KEY (company_id, salesperson_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_customer_profile_credit_limit CHECK (credit_limit IS NULL OR (credit_limit >= 0 AND credit_limit_currency IS NOT NULL))
);
CREATE INDEX ix_customer_profile_price_list_id ON customer_profile (price_list_id);
CREATE TABLE supplier_profile (
    company_id           uuid NOT NULL,
    partner_id           uuid PRIMARY KEY,
    payable_account_id   uuid NOT NULL REFERENCES account (id),
    payment_term_id      uuid REFERENCES payment_term (id),
    buyer_id             uuid,
    price_list_id        uuid,                                    -- the supplier's purchase prices (ADR-0045 rule 2)
    price_list_kind      text NOT NULL DEFAULT 'purchase' CONSTRAINT ck_supplier_profile_price_list_kind CHECK (price_list_kind = 'purchase'),
    currency             text REFERENCES currency (code),
    working_calendar_id  uuid,                                    -- supplier processing days (ADR-0024 rule 4)
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, price_list_id, price_list_kind) REFERENCES price_list (company_id, id, kind),
    FOREIGN KEY (company_id, buyer_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, working_calendar_id) REFERENCES working_calendar (company_id, id)
);
CREATE INDEX ix_supplier_profile_price_list_id ON supplier_profile (price_list_id);
CREATE TABLE employee_profile (                            -- personal data (ADR-0019 rule 7)
    company_id             uuid NOT NULL,
    partner_id             uuid PRIMARY KEY,
    user_account_id        uuid UNIQUE REFERENCES user_account (id),
    receivable_account_id  uuid REFERENCES account (id),           -- advances (receivable_employee_advance)
    branch_id              uuid,
    cost_center_id         uuid,
    job_title              text,
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id)
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
    parent_id                  uuid REFERENCES product_category (id),
    default_item_group_id      uuid REFERENCES item_group (id),
    default_valuation_class_id uuid REFERENCES valuation_class (id),
    default_item_tax_group_id  uuid REFERENCES item_tax_group (id),
    default_inventory_uom_id   uuid REFERENCES uom (id),
    basis                      jsonb NOT NULL,
    is_active                  boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code)
);
CREATE TABLE storage_condition (                           -- ADR-0023 rule 3
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    is_active boolean NOT NULL DEFAULT true, UNIQUE (company_id, code)
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
    UNIQUE (company_id, code),
    CONSTRAINT ck_handling_unit_type_weight_uom CHECK (tare_weight IS NULL OR weight_uom_id IS NOT NULL),
    CONSTRAINT ck_handling_unit_type_dimension_uom CHECK ((length IS NULL AND width IS NULL AND height IS NULL) OR dimension_uom_id IS NOT NULL)
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
    product_category_id            uuid REFERENCES product_category (id),
    buyer_id                       uuid,                            -- an employee partner (ADR-0018 rule 3)
    item_group_id                  uuid NOT NULL REFERENCES item_group (id),
    valuation_class_id             uuid REFERENCES valuation_class (id),
    inventory_uom_id               uuid NOT NULL REFERENCES uom (id),
    purchase_uom_id                uuid NOT NULL REFERENCES uom (id),
    sales_uom_id                   uuid NOT NULL REFERENCES uom (id),
    -- catch_weight_uom_id is reserved by ADR-0018 rule 3 and not created in Phase 1.
    tracking                       text NOT NULL DEFAULT 'none' CONSTRAINT ck_product_tracking CHECK (tracking IN ('none', 'lot', 'serial')),
    item_tax_group_id              uuid NOT NULL REFERENCES item_tax_group (id),
    is_item_created_on_order       boolean NOT NULL DEFAULT false,  -- a document line may name a new combination of variant values (ADR-0045 rule 16)
    is_configurable                boolean NOT NULL DEFAULT false,  -- sold through a configuration model; its items are configured items (ADR-0046 rule 2)
    last_item_number               integer NOT NULL DEFAULT 0,      -- counter for codes of items created on order, under the product row lock
    price_control                  text NOT NULL DEFAULT 'periodic_average' CONSTRAINT ck_product_price_control CHECK (price_control IN ('periodic_average')),
    is_inspection_required         boolean NOT NULL DEFAULT false,  -- ADR-0023 rule 3
    removal_strategy               text CONSTRAINT ck_product_removal_strategy CHECK (removal_strategy IN ('fefo', 'fifo')),
    storage_condition_id           uuid REFERENCES storage_condition (id),
    default_handling_unit_type_id  uuid REFERENCES handling_unit_type (id),
    hs_code                        text,                            -- ADR-0021 rule 13
    country_of_origin              text CONSTRAINT ck_product_country_of_origin CHECK (country_of_origin ~ '^[A-Z]{2}$'),
    is_active                      boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, buyer_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_product_valuation_class CHECK ((product_type = 'stock') = (valuation_class_id IS NOT NULL)),
    CONSTRAINT ck_product_tracking_stock CHECK (tracking = 'none' OR product_type = 'stock'),
    CONSTRAINT ck_product_configurable CHECK (NOT is_configurable OR (is_item_created_on_order AND product_type = 'stock'))
);
CREATE TABLE product_uom (                                 -- other units of one product (ADR-0018 rule 10)
    company_id   uuid NOT NULL,
    product_id   uuid NOT NULL,
    uom_id       uuid NOT NULL REFERENCES uom (id),
    numerator    bigint NOT NULL CONSTRAINT ck_product_uom_numerator CHECK (numerator > 0),       -- 1 uom = numerator/denominator inventory units (ADR-0006 rule 11)
    denominator  bigint NOT NULL CONSTRAINT ck_product_uom_denominator CHECK (denominator > 0),
    PRIMARY KEY (product_id, uom_id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id)
);
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
    UNIQUE (variant_attribute_id, code),
    UNIQUE (variant_attribute_id, id),
    UNIQUE (variant_attribute_id, numeric_value),
    UNIQUE (company_id, variant_attribute_id, variant_mode, id),
    CONSTRAINT fk_variant_attribute_value_attribute FOREIGN KEY (company_id, variant_attribute_id, variant_mode, value_type)
        REFERENCES variant_attribute (company_id, id, variant_mode, value_type),
    CONSTRAINT ck_variant_attribute_value_custom CHECK (NOT is_custom OR variant_mode = 'line_option'),
    CONSTRAINT ck_variant_attribute_value_number CHECK ((value_type = 'number') = (numeric_value IS NOT NULL) AND (value_type = 'list' OR variant_mode = 'variant'))
);
CREATE TABLE product_variant_attribute (                  -- the attributes of a product, of either mode
    company_id            uuid NOT NULL,
    product_id            uuid NOT NULL,
    variant_attribute_id  uuid NOT NULL,
    position              integer NOT NULL,
    is_required           boolean NOT NULL DEFAULT false,      -- line options: a line must choose a value
    PRIMARY KEY (product_id, variant_attribute_id),
    UNIQUE (product_id, position) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    FOREIGN KEY (company_id, variant_attribute_id) REFERENCES variant_attribute (company_id, id)
);
CREATE TABLE product_attribute_value (                    -- values a product allows for an attribute, of either mode; none listed = every value (ADR-0045 rule 15)
    company_id                  uuid NOT NULL,
    product_id                  uuid NOT NULL,
    variant_attribute_id        uuid NOT NULL,
    variant_attribute_value_id  uuid NOT NULL,
    PRIMARY KEY (product_id, variant_attribute_id, variant_attribute_value_id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT fk_product_attribute_value_attribute FOREIGN KEY (product_id, variant_attribute_id) REFERENCES product_variant_attribute (product_id, variant_attribute_id),
    CONSTRAINT fk_product_attribute_value_value FOREIGN KEY (variant_attribute_id, variant_attribute_value_id) REFERENCES variant_attribute_value (variant_attribute_id, id)
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
    CONSTRAINT fk_item_product FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    UNIQUE (id, product_id),
    UNIQUE (product_id, variant_key),
    CONSTRAINT ck_item_dimension_uom CHECK ((length IS NULL AND width IS NULL AND height IS NULL) OR dimension_uom_id IS NOT NULL),
    CONSTRAINT ck_item_weight_uom CHECK ((net_weight IS NULL AND gross_weight IS NULL) OR weight_uom_id IS NOT NULL),
    CONSTRAINT ck_item_dimensions_positive CHECK (coalesce(length, 1) > 0 AND coalesce(width, 1) > 0 AND coalesce(height, 1) > 0
                                                   AND coalesce(net_weight, 1) > 0 AND coalesce(gross_weight, 1) > 0),
    CONSTRAINT ck_item_gross_weight CHECK (net_weight IS NULL OR gross_weight IS NULL OR gross_weight >= net_weight)
);
CREATE TABLE item_variant_value (                         -- one per variant-mode attribute of the item's product
    company_id                  uuid NOT NULL,
    item_id                     uuid NOT NULL,
    product_id                  uuid NOT NULL,
    variant_attribute_id        uuid NOT NULL,
    variant_attribute_value_id  uuid NOT NULL,
    variant_mode                text NOT NULL DEFAULT 'variant' CONSTRAINT ck_item_variant_value_mode CHECK (variant_mode = 'variant'),
    PRIMARY KEY (item_id, variant_attribute_id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (item_id, product_id) REFERENCES item (id, product_id),
    CONSTRAINT fk_item_variant_value_product_attribute FOREIGN KEY (product_id, variant_attribute_id) REFERENCES product_variant_attribute (product_id, variant_attribute_id),
    CONSTRAINT fk_item_variant_value_value FOREIGN KEY (company_id, variant_attribute_id, variant_mode, variant_attribute_value_id)
        REFERENCES variant_attribute_value (company_id, variant_attribute_id, variant_mode, id)        -- line options never make items
);
CREATE INDEX ix_item_variant_value_value ON item_variant_value (variant_attribute_value_id);
CREATE TABLE item_barcode (
    company_id  uuid NOT NULL,
    item_id     uuid NOT NULL,
    uom_id      uuid NOT NULL REFERENCES uom (id),
    barcode     text NOT NULL,
    PRIMARY KEY (company_id, barcode),
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
    UNIQUE (partner_id, partner_item_code),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id)
);
CREATE INDEX ix_partner_item_item_id ON partner_item (item_id);
CREATE TABLE classification_scheme (
    id uuid PRIMARY KEY, company_id uuid NOT NULL REFERENCES company (id), code text NOT NULL, name text NOT NULL,
    is_hierarchical boolean NOT NULL DEFAULT false, is_protected boolean NOT NULL DEFAULT false, UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
CREATE TABLE classification_value (
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    classification_scheme_id  uuid NOT NULL,
    code                      text NOT NULL,
    name                      text NOT NULL,
    parent_id                 uuid REFERENCES classification_value (id),
    UNIQUE (classification_scheme_id, code),
    UNIQUE (classification_scheme_id, id),
    FOREIGN KEY (company_id, classification_scheme_id) REFERENCES classification_scheme (company_id, id)
);
CREATE TABLE product_classification (                      -- one value per scheme per product (ADR-0018 rule 15)
    company_id                uuid NOT NULL,
    product_id                uuid NOT NULL,
    classification_scheme_id  uuid NOT NULL,
    classification_value_id   uuid NOT NULL,
    PRIMARY KEY (product_id, classification_scheme_id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    FOREIGN KEY (company_id, classification_scheme_id) REFERENCES classification_scheme (company_id, id),
    FOREIGN KEY (classification_scheme_id, classification_value_id) REFERENCES classification_value (classification_scheme_id, id)
);

-- ===== Warehouses and bins [master_data owns warehouses; inventory owns zones and bins] (ADR-0020, ADR-0023, ADR-0031, ADR-0037) =====
CREATE TABLE warehouse (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL REFERENCES company (id),
    code                       text NOT NULL,
    name                       text NOT NULL,
    kind                       text NOT NULL CONSTRAINT ck_warehouse_kind CHECK (kind IN ('physical', 'transit', 'goods_sent')),
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
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, valuation_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, processor_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, working_calendar_id) REFERENCES working_calendar (company_id, id),
    CONSTRAINT ck_warehouse_valuation_warehouse CHECK ((kind = 'physical') = (valuation_warehouse_id IS NULL)),
    CONSTRAINT ck_warehouse_processor CHECK (processor_partner_id IS NULL OR (kind = 'physical' AND NOT is_bin_managed)),
    CONSTRAINT ck_warehouse_bin_managed CHECK (NOT is_bin_managed OR (kind = 'physical' AND default_receiving_bin_id IS NOT NULL AND default_shipping_bin_id IS NOT NULL))
);
-- One active processor warehouse per processor (ADR-0037 rule 1).
CREATE UNIQUE INDEX ux_warehouse_processor ON warehouse (company_id, processor_partner_id) WHERE is_active AND processor_partner_id IS NOT NULL;
CREATE TABLE zone (
    id uuid PRIMARY KEY, company_id uuid NOT NULL, warehouse_id uuid NOT NULL,
    code text NOT NULL, name text NOT NULL, UNIQUE (warehouse_id, code), UNIQUE (id, warehouse_id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id)
);
CREATE TABLE bin (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    warehouse_id             uuid NOT NULL,
    zone_id                  uuid NOT NULL,
    code                     text NOT NULL,
    barcode                  text NOT NULL,
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
    UNIQUE (warehouse_id, code),
    UNIQUE (company_id, barcode),
    UNIQUE (id, warehouse_id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_bin_zone FOREIGN KEY (zone_id, warehouse_id) REFERENCES zone (id, warehouse_id)
);
ALTER TABLE warehouse ADD CONSTRAINT fk_warehouse_default_bin FOREIGN KEY (default_bin_id, id) REFERENCES bin (id, warehouse_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE warehouse ADD CONSTRAINT fk_warehouse_default_receiving_bin FOREIGN KEY (default_receiving_bin_id, id) REFERENCES bin (id, warehouse_id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE warehouse ADD CONSTRAINT fk_warehouse_default_shipping_bin FOREIGN KEY (default_shipping_bin_id, id) REFERENCES bin (id, warehouse_id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE lot (                                         -- ADR-0020 rule 17 [inventory]
    id uuid PRIMARY KEY, company_id uuid NOT NULL, item_id uuid NOT NULL,
    code text NOT NULL, expiry_date date, manufacture_date date, UNIQUE (item_id, code),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT ck_lot_dates CHECK (expiry_date IS NULL OR manufacture_date IS NULL OR expiry_date >= manufacture_date)
);
CREATE TABLE serial_number (                               -- ADR-0020 rule 17 [inventory]
    id uuid PRIMARY KEY, company_id uuid NOT NULL, item_id uuid NOT NULL,
    code text NOT NULL, UNIQUE (item_id, code),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id)
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
    FOREIGN KEY (company_id, price_list_id) REFERENCES price_list (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT fk_price_list_option_extra_value FOREIGN KEY (company_id, variant_attribute_id, variant_mode, variant_attribute_value_id)
        REFERENCES variant_attribute_value (company_id, variant_attribute_id, variant_mode, id),
    CONSTRAINT ck_price_list_option_extra_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ex_price_list_option_extra_overlap EXCLUDE USING gist (
        price_list_id WITH =, (coalesce(product_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        variant_attribute_value_id WITH =, daterange(start_date, end_date, '[]') WITH &&)
);
