-- DS-22, DS-09 and DS-42: DDL draft for the commercial documents and the pricing procedure (ADR-0047), inventory and
-- costing (ADR-0020, ADR-0030, ADR-0031) and warehouse management (ADR-0023) that the six business flows need. PostgreSQL 18.
-- Loaded with DS-20, DS-56, DS-06, DS-15 and DS-43-54 in the design lab (docs/reviews/2026-11-14-design-validation,
-- t14_commercial_inventory_ddl.py).
-- The ADRs win if this file disagrees.
-- Conventions as DS-20: tables in schema nativeflows, keys inline (migrations name them by the MetaData naming convention,
-- ADR-0004 rule 15), UUIDv7 IDs from context.new_id or the client, no ID defaults, recorded_at on every row (ADR-0007 rule 9).
-- Every table carries company_id, FORCE ROW LEVEL SECURITY and the generated company policy (ADR-0017 rule 19,
-- ADR-0022 rule 8), except the global catalog movement_type. The lab checks this list.
-- References inside a company are composite on (company_id, id) wherever the parent has that key; every line refers
-- to its header that way, and every header to the shared document row (ADR-0009 rule 1: document has a unique key on
-- (company_id, id)). Lines are identified by (header, line_number), never renumbered (ADR-0028 rule 1).
-- Typed line references follow ADR-0028 rule 2 and ADR-0047 rule 2. A correction line names its original line with
-- correction_of_line_id, also when the original is an invoice line of another table (ADR-0047 rule 2).
-- Tables shared by every line table (price steps, custom text, installments) key a line by (document_id,
-- line_number), the line identity of ADR-0028 rule 1, so one table serves every document type.
-- Owner module per table in brackets (ADR-0022 rule 2; ADR-0027 rule 13; ADR-0047 rule 1).
-- Not here: the line taxes document_line_tax (ADR-0041 rule 6) and the money accounts, payments and bank statements of
-- ADR-0048 are drafted in DS-05-platform.sql with the document row; invoices of this file carry their taxes there.
-- Referenced tables defined elsewhere: document (documents, ADR-0009; DS-05-platform.sql, lab stubs), company, partner,
-- contact, item, product, uom, warehouse, bin, lot, serial_number, price_list, handling_unit_type, item_group, site,
-- payment_method, delivery_method, incoterm (ADR-0068), business_unit (ADR-0069),
-- partner_group, cost_center, project, variant_attribute (DS-20), product_configuration and configuration_model_revision
-- (DS-56), account, payment_term, open_item, journal_line, derivation_trace, posting_period, tax_code, cost_object (DS-06
-- and its stubs), user_account (DS-15), and from DS-43-54-planning-production.sql the inventory read model
-- demand_supply_line (ADR-0024 rule 8), planned_order and production_order_operation. This file relies on
-- demand_supply_line's hold_reasons (a set of not_approved and credit_hold; a row is released when the set is empty) and
-- UNIQUE (company_id, id), and adds the step 5 keys of its sales order, purchase order and purchase request line
-- columns (ADR-0028 rule 2). work_item (DS-29) is keyed by (company_id, id) to DS-05-platform.sql; attachment (DS-36)
-- is referenced by ID only.
-- The final-state immutability of headers and lines (ADR-0009 rule 14, issuing of ADR-0028 rule 6) is the documents
-- module's generic trigger (document_check_frozen of DS-05, generated per header and line table with the table's catalog
-- columns as its second argument, ADR-0079 rule 7); material document, warehouse movement and GR/IR posting rows are
-- append-only here.
-- Partner snapshot columns partner_name, partner_tax_id and partner_address (ADR-0028 rule 16) are content of every
-- header with a partner. interim: those three column names are not stated in ADR-0028.
-- Rules that need other rows (open quantities, cumulative correction limits, the three-way match, credit exposure,
-- re-pricing, one source document per delivery) are enforced by commands and named in ADR-0047; the database holds
-- uniqueness, kinds, signs, and the keys that keep references inside one company.

-- ===== Movement types [inventory] (ADR-0020 rule 4; catalog docs/catalogs/movement-types.csv) =====
CREATE TABLE movement_type (                               -- global catalog, uuid5 IDs, loaded from the catalog file
    id                      uuid PRIMARY KEY,
    code                    text NOT NULL UNIQUE,
    name                    text NOT NULL,
    direction               text NOT NULL CONSTRAINT ck_movement_type_direction CHECK (direction IN ('in', 'out')),
    value_source            text NOT NULL CONSTRAINT ck_movement_type_value_source CHECK (value_source IN ('document', 'preliminary_price', 'issuing_value', 'regime')),
    costing_role            text NOT NULL CONSTRAINT ck_movement_type_costing_role CHECK (costing_role IN ('receipt', 'revalued_issue', 'transfer', 'regime', 'production_input', 'production_output')),
    offset_transaction_key  text,                          -- empty for transfers
    needs_reference         boolean NOT NULL,
    sap_analog              text,
    added_in                text NOT NULL,                 -- catalog version
    recorded_at             timestamptz NOT NULL DEFAULT now()
);

-- ===== Promotions [sales] (ADR-0047 rule 17; master data, change-tracked, proposal-bound) =====
CREATE TABLE promotion (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    code                     text NOT NULL,
    name                     text NOT NULL,
    priority                 integer NOT NULL,              -- highest wins, then the lowest code (rule 17)
    start_date               date NOT NULL,
    end_date                 date,                          -- inclusive (ADR-0027 rule 12)
    partner_id               uuid,                          -- optional customer
    partner_group_id         uuid REFERENCES partner_group (id),
    price_list_id            uuid,
    price_list_kind          text NOT NULL DEFAULT 'sale' CONSTRAINT ck_promotion_price_list_kind CHECK (price_list_kind = 'sale'),
    item_id                  uuid,                          -- scope: exactly one of item, product, item group
    product_id               uuid,
    item_group_id            uuid REFERENCES item_group (id),
    minimum_line_quantity    types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_promotion_minimum_line_quantity CHECK (minimum_line_quantity >= 0),
    kind                     text NOT NULL CONSTRAINT ck_promotion_kind CHECK (kind IN ('percent', 'amount_per_unit', 'free_goods')),
    discount_percent         types.percent,                 -- percent off the base price
    amount_per_unit          types.unit_price,              -- off the base price
    free_item_id             uuid,                          -- free_goods: item and quantity per multiple of the qualifying quantity
    free_quantity            types.quantity,
    qualifying_quantity      types.quantity,
    is_active                boolean NOT NULL DEFAULT true,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, price_list_id, price_list_kind) REFERENCES price_list (company_id, id, kind),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    FOREIGN KEY (company_id, free_item_id) REFERENCES item (company_id, id),
    CONSTRAINT ck_promotion_scope CHECK (num_nonnulls(item_id, product_id, item_group_id) = 1),
    CONSTRAINT ck_promotion_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ck_promotion_kind_fields CHECK (
        (kind = 'percent' AND discount_percent IS NOT NULL AND discount_percent > 0 AND discount_percent <= 100 AND amount_per_unit IS NULL AND free_item_id IS NULL)
        OR (kind = 'amount_per_unit' AND amount_per_unit IS NOT NULL AND amount_per_unit > 0 AND discount_percent IS NULL AND free_item_id IS NULL)
        OR (kind = 'free_goods' AND free_item_id IS NOT NULL AND free_quantity IS NOT NULL AND qualifying_quantity IS NOT NULL
            AND free_quantity > 0 AND qualifying_quantity > 0 AND discount_percent IS NULL AND amount_per_unit IS NULL))
);

-- ===== Sales: quotation [sales] (ADR-0047 rule 3; holistic review B1, S4) =====
CREATE TABLE quotation (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL,
    partner_id                 uuid NOT NULL,                 -- the customer (an active customer role, checked by the command)
    contact_id                 uuid,                          -- interim: not stated in ADR-0047 (the CPQ flow addresses a contact)
    partner_name               text NOT NULL,
    partner_tax_id             text,
    partner_address            jsonb,
    currency                   text NOT NULL REFERENCES currency (code),
    price_list_id              uuid,                          -- null when the default list's currency differs (holistic review S14)
    price_list_kind            text NOT NULL DEFAULT 'sale' CONSTRAINT ck_quotation_price_list_kind CHECK (price_list_kind = 'sale'),
    prices_include_tax         boolean NOT NULL DEFAULT false, -- from the list (ADR-0045 rule 5; ADR-0047 rule 16)
    payment_term_id            uuid REFERENCES payment_term (id),
    salesperson_id             uuid,
    document_date              date NOT NULL,
    valid_until                date NOT NULL,
    requested_delivery_date    date,
    document_discount_percent  types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_quotation_document_discount_percent CHECK (document_discount_percent BETWEEN 0 AND 100),
    print_language             text,                          -- ADR-0049 rule 27
    closed_reason              text CONSTRAINT ck_quotation_closed_reason CHECK (closed_reason IN ('fulfilled', 'short')),
    payment_method_id          uuid,                          -- copied from the profile, then from the source; suggests only (ADR-0068 rules 15, 17)
    incoterm_code              text REFERENCES incoterm (code),   -- advisory only (ADR-0068 rules 19, 20)
    incoterm_place             text,                          -- the named place; requires a code
    business_unit_id           uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    ship_to_partner_id uuid,
    ship_to_name text,
    ship_to_address_id uuid,
    ship_to_address jsonb,
    FOREIGN KEY (company_id, ship_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, ship_to_partner_id, ship_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_quotation_ship_to CHECK ((ship_to_partner_id IS NULL) = (ship_to_name IS NULL) AND (ship_to_partner_id IS NOT NULL OR (ship_to_address_id IS NULL AND ship_to_address IS NULL))),
    bill_to_partner_id uuid,
    bill_to_name text,
    bill_to_tax_id text,
    bill_to_address_id uuid,
    bill_to_address jsonb,
    FOREIGN KEY (company_id, bill_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, bill_to_partner_id, bill_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_quotation_bill_to CHECK ((bill_to_partner_id IS NULL) = (bill_to_name IS NULL) AND (bill_to_partner_id IS NOT NULL OR bill_to_tax_id IS NULL) AND (bill_to_partner_id IS NOT NULL OR (bill_to_address_id IS NULL AND bill_to_address IS NULL))),
    payer_partner_id uuid,
    payer_name text,
    FOREIGN KEY (company_id, payer_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_quotation_payer CHECK ((payer_partner_id IS NULL) = (payer_name IS NULL)),
    note text CONSTRAINT ck_quotation_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_quotation_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, partner_id, contact_id) REFERENCES contact (company_id, partner_id, id),
    FOREIGN KEY (company_id, price_list_id, price_list_kind) REFERENCES price_list (company_id, id, kind),
    FOREIGN KEY (company_id, salesperson_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_quotation_valid_until CHECK (valid_until >= document_date),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id),
    CONSTRAINT ck_quotation_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- A quotation line may have no item: a configurable product with its configuration (holistic review B1; ADR-0045 rule 16;
-- ADR-0046 rule 9). product_id is always set; an item, when set, belongs to it (the key item (id, product_id)), and so does
-- a configuration (the key product_configuration (company_id, id, product_id)). Quotations never create items (ADR-0047 rule 1).
CREATE TABLE quotation_line (
    id                               uuid PRIMARY KEY,
    company_id                       uuid NOT NULL,
    quotation_id                     uuid NOT NULL,
    line_number                      integer NOT NULL CONSTRAINT ck_quotation_line_line_number CHECK (line_number > 0),
    product_id                       uuid NOT NULL,
    item_id                          uuid,
    product_configuration_id         uuid,                    -- set once the chosen values are complete (ADR-0046 rule 9)
    configuration_values             jsonb,                   -- chosen values of a draft line, canonical JSON (ADR-0046 rule 9)
    configuration_model_revision_id  uuid,                    -- the revision the line was evaluated under (ADR-0046 rule 9)
    quantity                         types.quantity NOT NULL CONSTRAINT ck_quotation_line_quantity CHECK (quantity > 0),
    uom_id                           uuid NOT NULL REFERENCES uom (id),
    uom_numerator                    bigint NOT NULL,           -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator                  bigint NOT NULL,           -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source                text NOT NULL,             -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity               types.quantity NOT NULL CONSTRAINT ck_quotation_line_inventory_quantity CHECK (inventory_quantity > 0),
    warehouse_id                     uuid,                    -- optional on a quotation, checked at copy (holistic review S4)
    planned_delivery_date            date,
    list_unit_price                  types.unit_price,        -- price steps 1-6 of ADR-0047 rule 16, stored
    manual_unit_price                types.unit_price,
    is_price_manual                  boolean NOT NULL DEFAULT false,
    is_price_copied                  boolean NOT NULL DEFAULT false,   -- copied prices are exempt from re-pricing (ADR-0047 rule 16; holistic review S2)
    promotion_id                     uuid,
    manual_discount_percent          types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_quotation_line_manual_discount_percent CHECK (manual_discount_percent BETWEEN 0 AND 100),
    net_unit_price                   types.unit_price CONSTRAINT ck_quotation_line_net_unit_price CHECK (net_unit_price >= 0),
    line_amount                      types.amount CONSTRAINT ck_quotation_line_line_amount CHECK (line_amount >= 0),
    document_discount_amount         types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_quotation_line_document_discount_amount CHECK (document_discount_amount >= 0),
    is_free_of_charge                boolean NOT NULL DEFAULT false,
    free_goods_source_line_number    integer,                 -- the line a free goods line came from (rule 17)
    description                      text,
    recorded_at                      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (quotation_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, quotation_id) REFERENCES quotation (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT fk_quotation_line_item_product FOREIGN KEY (item_id, product_id) REFERENCES item (id, product_id),
    CONSTRAINT fk_quotation_line_configuration FOREIGN KEY (company_id, product_configuration_id, product_id) REFERENCES product_configuration (company_id, id, product_id),
    FOREIGN KEY (company_id, configuration_model_revision_id, product_id) REFERENCES configuration_model_revision (company_id, id, product_id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, promotion_id) REFERENCES promotion (company_id, id),
    CONSTRAINT ck_quotation_line_manual_price CHECK (is_price_manual = (manual_unit_price IS NOT NULL)),
    CONSTRAINT ck_quotation_line_free_of_charge CHECK (NOT is_free_of_charge OR coalesce(net_unit_price = 0 AND line_amount = 0 AND document_discount_amount = 0, false)),
    CONSTRAINT ck_quotation_line_free_goods_source CHECK (free_goods_source_line_number IS NULL OR (is_free_of_charge AND promotion_id IS NOT NULL AND free_goods_source_line_number <> line_number)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_quotation_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_quotation_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);

-- ===== Sales: sales order [sales] (ADR-0047 rule 4; change orders ADR-0028 rule 4) =====
CREATE TABLE sales_order (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL,
    partner_id                 uuid NOT NULL,
    contact_id                 uuid,                          -- interim: not stated in ADR-0047
    partner_name               text NOT NULL,
    partner_tax_id             text,
    partner_address            jsonb,
    currency                   text NOT NULL REFERENCES currency (code),
    price_list_id              uuid,
    price_list_kind            text NOT NULL DEFAULT 'sale' CONSTRAINT ck_sales_order_price_list_kind CHECK (price_list_kind = 'sale'),
    prices_include_tax         boolean NOT NULL DEFAULT false,
    payment_term_id            uuid REFERENCES payment_term (id),
    salesperson_id             uuid,
    document_date              date NOT NULL,
    requested_delivery_date    date,
    document_discount_percent  types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_sales_order_document_discount_percent CHECK (document_discount_percent BETWEEN 0 AND 100),
    print_language             text,
    closed_reason              text CONSTRAINT ck_sales_order_closed_reason CHECK (closed_reason IN ('fulfilled', 'short')),
    payment_method_id          uuid,                          -- copied from the profile, then from the source; suggests only (ADR-0068 rules 15, 17)
    delivery_method_id         uuid,                          -- ADR-0068 rule 22
    incoterm_code              text REFERENCES incoterm (code),   -- advisory only (ADR-0068 rules 19, 20)
    incoterm_place             text,                          -- the named place; requires a code
    business_unit_id           uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    ship_to_partner_id uuid,
    ship_to_name text,
    ship_to_address_id uuid,
    ship_to_address jsonb,
    FOREIGN KEY (company_id, ship_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, ship_to_partner_id, ship_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_sales_order_ship_to CHECK ((ship_to_partner_id IS NULL) = (ship_to_name IS NULL) AND (ship_to_partner_id IS NOT NULL OR (ship_to_address_id IS NULL AND ship_to_address IS NULL))),
    bill_to_partner_id uuid,
    bill_to_name text,
    bill_to_tax_id text,
    bill_to_address_id uuid,
    bill_to_address jsonb,
    FOREIGN KEY (company_id, bill_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, bill_to_partner_id, bill_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_sales_order_bill_to CHECK ((bill_to_partner_id IS NULL) = (bill_to_name IS NULL) AND (bill_to_partner_id IS NOT NULL OR bill_to_tax_id IS NULL) AND (bill_to_partner_id IS NOT NULL OR (bill_to_address_id IS NULL AND bill_to_address IS NULL))),
    payer_partner_id uuid,
    payer_name text,
    FOREIGN KEY (company_id, payer_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_sales_order_payer CHECK ((payer_partner_id IS NULL) = (payer_name IS NULL)),
    note text CONSTRAINT ck_sales_order_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_sales_order_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, partner_id, contact_id) REFERENCES contact (company_id, partner_id, id),
    FOREIGN KEY (company_id, price_list_id, price_list_kind) REFERENCES price_list (company_id, id, kind),
    FOREIGN KEY (company_id, salesperson_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id),
    FOREIGN KEY (company_id, delivery_method_id) REFERENCES delivery_method (company_id, id),
    CONSTRAINT ck_sales_order_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- item_id is empty only on a draft line of an item created on order; the item exists once the order leaves draft
-- (ADR-0045 rule 16; ADR-0046 rule 11; INV-113, checked by the command and the invariant, since state lives on document).
CREATE TABLE sales_order_line (
    id                               uuid PRIMARY KEY,
    company_id                       uuid NOT NULL,
    sales_order_id                   uuid NOT NULL,
    line_number                      integer NOT NULL CONSTRAINT ck_sales_order_line_line_number CHECK (line_number > 0),
    quotation_line_id                uuid,
    product_id                       uuid NOT NULL,
    item_id                          uuid,
    product_configuration_id         uuid,
    configuration_values             jsonb,
    configuration_model_revision_id  uuid,
    quantity                         types.quantity NOT NULL CONSTRAINT ck_sales_order_line_quantity CHECK (quantity > 0),
    uom_id                           uuid NOT NULL REFERENCES uom (id),
    uom_numerator                    bigint NOT NULL,           -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator                  bigint NOT NULL,           -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source                text NOT NULL,             -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity               types.quantity NOT NULL CONSTRAINT ck_sales_order_line_inventory_quantity CHECK (inventory_quantity > 0),
    warehouse_id                     uuid,                    -- required for stock lines (command; ADR-0046 rule 10 for configurable lines)
    planned_delivery_date            date,                    -- needed by FEFO (ADR-0023 rule 14)
    list_unit_price                  types.unit_price,
    manual_unit_price                types.unit_price,
    is_price_manual                  boolean NOT NULL DEFAULT false,
    is_price_copied                  boolean NOT NULL DEFAULT false,   -- copied prices are exempt from re-pricing (ADR-0047 rule 16; holistic review S2)
    promotion_id                     uuid,
    manual_discount_percent          types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_sales_order_line_manual_discount_percent CHECK (manual_discount_percent BETWEEN 0 AND 100),
    net_unit_price                   types.unit_price CONSTRAINT ck_sales_order_line_net_unit_price CHECK (net_unit_price >= 0),
    line_amount                      types.amount CONSTRAINT ck_sales_order_line_line_amount CHECK (line_amount >= 0),
    document_discount_amount         types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_sales_order_line_document_discount_amount CHECK (document_discount_amount >= 0),
    is_free_of_charge                boolean NOT NULL DEFAULT false,
    free_goods_source_line_number    integer,
    description                      text,
    recorded_at                      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sales_order_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, sales_order_id) REFERENCES sales_order (company_id, id),
    FOREIGN KEY (company_id, quotation_line_id) REFERENCES quotation_line (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT fk_sales_order_line_item_product FOREIGN KEY (item_id, product_id) REFERENCES item (id, product_id),
    CONSTRAINT fk_sales_order_line_configuration FOREIGN KEY (company_id, product_configuration_id, product_id) REFERENCES product_configuration (company_id, id, product_id),
    FOREIGN KEY (company_id, configuration_model_revision_id, product_id) REFERENCES configuration_model_revision (company_id, id, product_id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, promotion_id) REFERENCES promotion (company_id, id),
    CONSTRAINT ck_sales_order_line_manual_price CHECK (is_price_manual = (manual_unit_price IS NOT NULL)),
    CONSTRAINT ck_sales_order_line_free_of_charge CHECK (NOT is_free_of_charge OR coalesce(net_unit_price = 0 AND line_amount = 0 AND document_discount_amount = 0, false)),
    CONSTRAINT ck_sales_order_line_free_goods_source CHECK (free_goods_source_line_number IS NULL OR (is_free_of_charge AND promotion_id IS NOT NULL AND free_goods_source_line_number <> line_number)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_sales_order_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_sales_order_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE INDEX ix_sales_order_line_quotation_line_id ON sales_order_line (quotation_line_id) WHERE quotation_line_id IS NOT NULL;

-- ===== Credit holds [sales] (ADR-0047 rule 18; holistic review B2, S8) =====
-- One row per hold or release of an order. A hold is set by a sales command that raises exposure over the limit, and the
-- same command adds credit_hold to hold_reasons of the order's open demand rows through inventory.contract.set_demand_hold;
-- clearing or releasing the hold clears the rows. An order approved while is_credit_exceeded was true records that
-- approval as its release (release_kind approval, never held). ReleaseCreditHold is human_only, with a reason and
-- segregation from the order's author. A release lasts until a change order raises the order's value (state lapsed).
-- The work item kind credit_hold (holistic review S8) is resolved by the release or by clearing.
CREATE TABLE credit_hold (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    sales_order_id           uuid NOT NULL,
    partner_id               uuid NOT NULL,
    state                    text NOT NULL CONSTRAINT ck_credit_hold_state CHECK (state IN ('held', 'released', 'cleared', 'lapsed')),   -- interim: state names not stated in ADR-0047
    currency                 text NOT NULL REFERENCES currency (code),       -- the credit limit's currency
    credit_limit_amount      types.amount NOT NULL,
    credit_exposure_amount   types.amount NOT NULL,          -- with the order included, at the check (rule 18)
    held_at                  timestamptz,
    release_kind             text CONSTRAINT ck_credit_hold_release_kind CHECK (release_kind IN ('approval', 'manual')),
    released_at              timestamptz,
    released_by_user_id      uuid REFERENCES user_account (id),
    release_reason           text,
    released_order_amount    types.amount,                   -- interim: not stated in ADR-0047 (the order value the release covers)
    cleared_at               timestamptz,
    work_item_id             uuid,                           -- the credit_hold work item (DS-29, DS-05-platform.sql)
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, sales_order_id) REFERENCES sales_order (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, work_item_id) REFERENCES work_item (company_id, id),
    CONSTRAINT ck_credit_hold_held CHECK (state <> 'held' OR (held_at IS NOT NULL AND release_kind IS NULL AND cleared_at IS NULL)),
    CONSTRAINT ck_credit_hold_released CHECK ((release_kind IS NOT NULL) = (released_at IS NOT NULL)
        AND (state NOT IN ('released', 'lapsed') OR release_kind IS NOT NULL)),
    CONSTRAINT ck_credit_hold_manual_release CHECK (release_kind IS DISTINCT FROM 'manual' OR (released_by_user_id IS NOT NULL AND coalesce(length(btrim(release_reason)), 0) > 0)),
    CONSTRAINT ck_credit_hold_approval_release CHECK (release_kind IS DISTINCT FROM 'approval' OR held_at IS NULL),
    CONSTRAINT ck_credit_hold_cleared CHECK ((state = 'cleared') = (cleared_at IS NOT NULL))
);
-- At most one hold or standing release per order.
CREATE UNIQUE INDEX ux_credit_hold_current ON credit_hold (sales_order_id) WHERE state IN ('held', 'released');
CREATE INDEX ix_credit_hold_company_id_partner_id ON credit_hold (company_id, partner_id) WHERE state = 'held';

-- ===== Purchasing: purchase request and purchase order [purchasing] (ADR-0047 rules 9-10) =====
CREATE TABLE purchase_request (
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL,
    buyer_id         uuid,                                   -- interim: not stated in ADR-0047 (the request's buyer, an employee partner)
    document_date    date NOT NULL,
    closed_reason    text CONSTRAINT ck_purchase_request_closed_reason CHECK (closed_reason IN ('fulfilled', 'short')),
    print_language   text,
    business_unit_id uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    note text CONSTRAINT ck_purchase_request_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, buyer_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- Quantity may be zero: a draft line whose supply row carries origin_planned_order_id or pegging is not removed, its
-- quantity goes to zero (ADR-0047 rule 10; ADR-0028 rule 2).
CREATE TABLE purchase_request_line (
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL,
    purchase_request_id            uuid NOT NULL,
    line_number                    integer NOT NULL CONSTRAINT ck_purchase_request_line_line_number CHECK (line_number > 0),
    item_id                        uuid NOT NULL,
    quantity                       types.quantity NOT NULL CONSTRAINT ck_purchase_request_line_quantity CHECK (quantity >= 0),
    uom_id                         uuid NOT NULL REFERENCES uom (id),
    uom_numerator                  bigint NOT NULL,             -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator                bigint NOT NULL,             -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source              text NOT NULL,               -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity             types.quantity NOT NULL CONSTRAINT ck_purchase_request_line_inventory_quantity CHECK (inventory_quantity >= 0),
    warehouse_id                   uuid NOT NULL,           -- interim: not stated in ADR-0047 rule 9 (the supply row needs it, ADR-0024 rule 8)
    requested_date                 date NOT NULL,
    suggested_supplier_id          uuid,
    origin_planned_order_id        uuid,                    -- the planned order it was converted from (ADR-0024 rule 22)
    production_order_operation_id  uuid,                    -- subcontracted operation (ADR-0037 rule 4), a B3 column flagged for the author
    description                    text,
    recorded_at                    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (purchase_request_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, purchase_request_id) REFERENCES purchase_request (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, suggested_supplier_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, origin_planned_order_id) REFERENCES planned_order (company_id, id),
    FOREIGN KEY (company_id, production_order_operation_id) REFERENCES production_order_operation (company_id, id),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_purchase_request_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_purchase_request_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE TABLE purchase_order (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL,
    partner_id                 uuid NOT NULL,                 -- the supplier
    partner_name               text NOT NULL,
    partner_tax_id             text,
    partner_address            jsonb,
    currency                   text NOT NULL REFERENCES currency (code),
    price_list_id              uuid,                          -- the supplier's purchase list (holistic review S16 for the fallback)
    price_list_kind            text NOT NULL DEFAULT 'purchase' CONSTRAINT ck_purchase_order_price_list_kind CHECK (price_list_kind = 'purchase'),
    payment_term_id            uuid REFERENCES payment_term (id),
    buyer_id                   uuid,                          -- the supplier profile's default (ADR-0027 rule 6)
    document_date              date NOT NULL,
    document_discount_percent  types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_purchase_order_document_discount_percent CHECK (document_discount_percent BETWEEN 0 AND 100),
    print_language             text,
    closed_reason              text CONSTRAINT ck_purchase_order_closed_reason CHECK (closed_reason IN ('fulfilled', 'short')),
    payment_method_id          uuid,                          -- copied from the profile, then from the source; suggests only (ADR-0068 rules 15, 17)
    delivery_method_id         uuid,                          -- ADR-0068 rule 22
    incoterm_code              text REFERENCES incoterm (code),   -- advisory only (ADR-0068 rules 19, 20)
    incoterm_place             text,                          -- the named place; requires a code
    business_unit_id           uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    invoicing_party_partner_id uuid,
    invoicing_party_name text,
    invoicing_party_tax_id text,
    invoicing_party_address_id uuid,
    invoicing_party_address jsonb,
    FOREIGN KEY (company_id, invoicing_party_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, invoicing_party_partner_id, invoicing_party_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_purchase_order_invoicing_party CHECK ((invoicing_party_partner_id IS NULL) = (invoicing_party_name IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR invoicing_party_tax_id IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR (invoicing_party_address_id IS NULL AND invoicing_party_address IS NULL))),
    payee_partner_id uuid,
    payee_name text,
    FOREIGN KEY (company_id, payee_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_purchase_order_payee CHECK ((payee_partner_id IS NULL) = (payee_name IS NULL)),
    note text CONSTRAINT ck_purchase_order_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_purchase_order_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, price_list_id, price_list_kind) REFERENCES price_list (company_id, id, kind),
    FOREIGN KEY (company_id, buyer_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id),
    FOREIGN KEY (company_id, delivery_method_id) REFERENCES delivery_method (company_id, id),
    CONSTRAINT ck_purchase_order_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE purchase_order_line (
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL,
    purchase_order_id              uuid NOT NULL,
    line_number                    integer NOT NULL CONSTRAINT ck_purchase_order_line_line_number CHECK (line_number > 0),
    purchase_request_line_id       uuid,
    item_id                        uuid NOT NULL,           -- configurable products are made, not bought (ADR-0046 rule 2)
    quantity                       types.quantity NOT NULL CONSTRAINT ck_purchase_order_line_quantity CHECK (quantity >= 0),
    uom_id                         uuid NOT NULL REFERENCES uom (id),
    uom_numerator                  bigint NOT NULL,             -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator                bigint NOT NULL,             -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source              text NOT NULL,               -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity             types.quantity NOT NULL CONSTRAINT ck_purchase_order_line_inventory_quantity CHECK (inventory_quantity >= 0),
    warehouse_id                   uuid NOT NULL,           -- the receiving warehouse (rule 10)
    requested_date                 date NOT NULL,
    list_unit_price                types.unit_price,        -- price steps without promotions (rule 16)
    manual_unit_price              types.unit_price,
    is_price_manual                boolean NOT NULL DEFAULT false,
    is_price_copied                boolean NOT NULL DEFAULT false,   -- copied prices are exempt from re-pricing (ADR-0047 rule 16; holistic review S2)
    manual_discount_percent        types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_purchase_order_line_manual_discount_percent CHECK (manual_discount_percent BETWEEN 0 AND 100),
    net_unit_price                 types.unit_price CONSTRAINT ck_purchase_order_line_net_unit_price CHECK (net_unit_price >= 0),
    line_amount                    types.amount CONSTRAINT ck_purchase_order_line_line_amount CHECK (line_amount >= 0),
    document_discount_amount       types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_purchase_order_line_document_discount_amount CHECK (document_discount_amount >= 0),
    origin_planned_order_id        uuid,                    -- copied from the request (rule 10)
    production_order_operation_id  uuid,
    description                    text,
    recorded_at                    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (purchase_order_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, purchase_order_id) REFERENCES purchase_order (company_id, id),
    FOREIGN KEY (company_id, purchase_request_line_id) REFERENCES purchase_request_line (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, origin_planned_order_id) REFERENCES planned_order (company_id, id),
    FOREIGN KEY (company_id, production_order_operation_id) REFERENCES production_order_operation (company_id, id),
    CONSTRAINT ck_purchase_order_line_manual_price CHECK (is_price_manual = (manual_unit_price IS NOT NULL)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_purchase_order_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_purchase_order_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE INDEX ix_purchase_order_line_purchase_request_line_id ON purchase_order_line (purchase_request_line_id) WHERE purchase_request_line_id IS NOT NULL;

-- ===== Stock: handling units [inventory] (ADR-0023 rule 6) =====
CREATE TABLE handling_unit (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    code                     text NOT NULL,
    barcode                  text NOT NULL,                  -- an SSCC (18 digits) or an internal code, registered across types (ADR-0061 rule 7)
    is_legacy_barcode        boolean NOT NULL DEFAULT false, -- an old system's label code kept on migration; set at creation (ADR-0061 rule 8)
    handling_unit_type_id    uuid NOT NULL REFERENCES handling_unit_type (id),
    parent_handling_unit_id  uuid,                           -- one nesting level in Phase 1 (handling_unit_nesting_exceeded, command)
    warehouse_id             uuid NOT NULL,
    bin_id                   uuid NOT NULL,                  -- the default bin in transit and goods_sent warehouses (ADR-0031 rule 8)
    state                    text NOT NULL DEFAULT 'open' CONSTRAINT ck_handling_unit_state CHECK (state IN ('open', 'closed', 'shipped')),
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, barcode),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_handling_unit_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT ck_handling_unit_not_own_parent CHECK (parent_handling_unit_id IS DISTINCT FROM id)
);

-- ===== Stock documents [inventory] (ADR-0027 rule 13; ADR-0047 rules 5, 7, 11, 15) =====
-- Order line references are reserved at step 3 and filled from step 5 (ADR-0027 rule 7). Lots, serials, bins, statuses
-- and handling units of what actually moved are on the material document lines; the document lines carry the user's
-- entry. Each receipt or return line of an order line stores its GR/IR position range in inventory units (ADR-0047 rule 13).
CREATE TABLE goods_receipt (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,                        -- the supplier
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    partner_reference  text,                                 -- interim: not stated in ADR-0047 (the supplier's delivery note number)
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    print_language     text,
    delivery_method_id uuid,                          -- ADR-0068 rule 22
    carrier_partner_id uuid,                          -- copied from the method, changeable until posting; an active supplier role (partner_role_missing)
    tracking_number    text,
    vehicle_registration text,
    incoterm_code      text REFERENCES incoterm (code),   -- advisory only (ADR-0068 rules 19, 20)
    incoterm_place     text,                          -- the named place; requires a code
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    note text CONSTRAINT ck_goods_receipt_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_goods_receipt_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, delivery_method_id) REFERENCES delivery_method (company_id, id),
    FOREIGN KEY (company_id, carrier_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_goods_receipt_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- A receipt of an order line is rejected while its supply row is unreleased (demand_supply_not_released, holistic review B2)
-- and when received net would exceed the ordered inventory quantity times the receipt tolerance, plus the unit
-- rounding tolerance (receipt_exceeds_order, ADR-0047 rule 11; ADR-0056 rules 10, 11).
CREATE TABLE goods_receipt_line (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    goods_receipt_id        uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_goods_receipt_line_line_number CHECK (line_number > 0),
    purchase_order_line_id  uuid,                            -- required from step 5 for stock items (purchase_order_required, ADR-0047 rule 12)
    item_id                 uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_goods_receipt_line_quantity CHECK (quantity > 0),
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator         bigint NOT NULL,                    -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_goods_receipt_line_inventory_quantity CHECK (inventory_quantity > 0),
    warehouse_id            uuid NOT NULL,
    bin_id                  uuid,                            -- the line's bin, else the default receiving bin (ADR-0023 rule 7)
    lot_id                  uuid REFERENCES lot (id),
    gr_ir_position_from     types.quantity,                  -- positions [from, to) of the order line (ADR-0047 rule 13)
    gr_ir_position_to       types.quantity,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (goods_receipt_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, goods_receipt_id) REFERENCES goods_receipt (company_id, id),
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_goods_receipt_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT ck_goods_receipt_line_positions CHECK ((purchase_order_line_id IS NULL AND gr_ir_position_from IS NULL AND gr_ir_position_to IS NULL)
        OR (purchase_order_line_id IS NOT NULL AND gr_ir_position_from IS NOT NULL AND gr_ir_position_to IS NOT NULL AND gr_ir_position_from >= 0 AND gr_ir_position_to - gr_ir_position_from = inventory_quantity)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_goods_receipt_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_goods_receipt_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE INDEX ix_goods_receipt_line_purchase_order_line_id ON goods_receipt_line (purchase_order_line_id) WHERE purchase_order_line_id IS NOT NULL;
CREATE TABLE return_to_supplier (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    print_language     text,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    note text CONSTRAINT ck_return_to_supplier_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- correction_of_id on the document row is the goods receipt; returned <= received per receipt line (inventory, ADR-0047 rule 15).
CREATE TABLE return_to_supplier_line (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    return_to_supplier_id   uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_return_to_supplier_line_line_number CHECK (line_number > 0),
    goods_receipt_line_id   uuid NOT NULL,
    item_id                 uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_return_to_supplier_line_quantity CHECK (quantity > 0),
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator         bigint NOT NULL,                    -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_return_to_supplier_line_inventory_quantity CHECK (inventory_quantity > 0),
    warehouse_id            uuid NOT NULL,
    bin_id                  uuid,
    stock_status            text NOT NULL DEFAULT 'available' CONSTRAINT ck_return_to_supplier_line_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),   -- the status issued from (ADR-0023 rule 7; ADR-0070 rule 15)
    gr_ir_position_from     types.quantity,                  -- the GR/IR positions [from, to) the return actually debits: the order
    gr_ir_position_to       types.quantity,                  -- line's latest received positions (ADR-0047 rule 13 and its note); the
                                                             -- named receipt part, the part-as-source reference (ADR-0056 rule 10),
                                                             -- is goods_receipt_line_id
    return_reason_id uuid,
    return_reason_kind text NOT NULL DEFAULT 'return' CONSTRAINT ck_return_to_supplier_line_return_reason_kind CHECK (return_reason_kind = 'return'),
    FOREIGN KEY (company_id, return_reason_id, return_reason_kind) REFERENCES reason (company_id, id, kind),
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (return_to_supplier_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, return_to_supplier_id) REFERENCES return_to_supplier (company_id, id),
    FOREIGN KEY (company_id, goods_receipt_line_id) REFERENCES goods_receipt_line (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_return_to_supplier_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT ck_return_to_supplier_line_positions CHECK ((gr_ir_position_from IS NULL AND gr_ir_position_to IS NULL)
        OR (gr_ir_position_from IS NOT NULL AND gr_ir_position_to IS NOT NULL AND gr_ir_position_from >= 0 AND gr_ir_position_to - gr_ir_position_from = inventory_quantity)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_return_to_supplier_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_return_to_supplier_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE TABLE delivery (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,                        -- the customer
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    print_language     text,
    delivery_method_id uuid,                          -- ADR-0068 rule 22
    carrier_partner_id uuid,                          -- copied from the method, changeable until posting; an active supplier role (partner_role_missing)
    tracking_number    text,
    vehicle_registration text,
    incoterm_code      text REFERENCES incoterm (code),   -- advisory only (ADR-0068 rules 19, 20)
    incoterm_place     text,                          -- the named place; requires a code
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    ship_to_partner_id uuid,
    ship_to_name text,
    ship_to_address_id uuid,
    ship_to_address jsonb,
    FOREIGN KEY (company_id, ship_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, ship_to_partner_id, ship_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_delivery_ship_to CHECK ((ship_to_partner_id IS NULL) = (ship_to_name IS NULL) AND (ship_to_partner_id IS NOT NULL OR (ship_to_address_id IS NULL AND ship_to_address IS NULL))),
    note text CONSTRAINT ck_delivery_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_delivery_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, delivery_method_id) REFERENCES delivery_method (company_id, id),
    FOREIGN KEY (company_id, carrier_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_delivery_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- Created from confirmed picks or, in a warehouse without tasks, from order lines (ADR-0023 rule 16; ADR-0047 rule 5).
-- At most the demand row's open quantity (quantity_exceeds_open); rejected while the row is unreleased or held
-- (demand_supply_not_released while hold_reasons holds not_approved, demand_on_hold while it holds credit_hold), read from
-- demand_supply_line by inventory.
CREATE TABLE delivery_line (
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    delivery_id               uuid NOT NULL,
    line_number               integer NOT NULL CONSTRAINT ck_delivery_line_line_number CHECK (line_number > 0),
    sales_order_line_id       uuid,                          -- required from step 5 (holistic review S9: no stock sale without an order)
    item_id                   uuid NOT NULL,
    product_configuration_id  uuid,                          -- copied without re-evaluation (ADR-0046 rule 10)
    quantity                  types.quantity NOT NULL CONSTRAINT ck_delivery_line_quantity CHECK (quantity > 0),
    uom_id                    uuid NOT NULL REFERENCES uom (id),
    uom_numerator             bigint NOT NULL,                  -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator           bigint NOT NULL,                  -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source         text NOT NULL,                    -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity        types.quantity NOT NULL CONSTRAINT ck_delivery_line_inventory_quantity CHECK (inventory_quantity > 0),
    warehouse_id              uuid NOT NULL,
    is_free_of_charge         boolean NOT NULL DEFAULT false, -- reserved at step 3; posts free_goods_issue (ADR-0047 rule 17)
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (delivery_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, delivery_id) REFERENCES delivery (company_id, id),
    FOREIGN KEY (company_id, sales_order_line_id) REFERENCES sales_order_line (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, product_configuration_id) REFERENCES product_configuration (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_delivery_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_delivery_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE INDEX ix_delivery_line_sales_order_line_id ON delivery_line (sales_order_line_id) WHERE sales_order_line_id IS NOT NULL;
CREATE TABLE return_from_customer (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    print_language     text,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    note text CONSTRAINT ck_return_from_customer_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- correction_of_id on the document row is the delivery; returned <= delivered per delivery line (ADR-0047 rule 7).
-- Goods arrive in a returns bin as blocked (ADR-0023 rule 19).
CREATE TABLE return_from_customer_line (
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    return_from_customer_id   uuid NOT NULL,
    line_number               integer NOT NULL CONSTRAINT ck_return_from_customer_line_line_number CHECK (line_number > 0),
    delivery_line_id          uuid NOT NULL,                 -- returns of goods delivered before the cut-over are other_receipt (ADR-0047 rule 8)
    item_id                   uuid NOT NULL,
    product_configuration_id  uuid,
    quantity                  types.quantity NOT NULL CONSTRAINT ck_return_from_customer_line_quantity CHECK (quantity > 0),
    uom_id                    uuid NOT NULL REFERENCES uom (id),
    uom_numerator             bigint NOT NULL,                  -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator           bigint NOT NULL,                  -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source         text NOT NULL,                    -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity        types.quantity NOT NULL CONSTRAINT ck_return_from_customer_line_inventory_quantity CHECK (inventory_quantity > 0),
    warehouse_id              uuid NOT NULL,
    bin_id                    uuid,                          -- a returns bin (ADR-0023 rule 7)
    return_reason_id uuid,
    return_reason_kind text NOT NULL DEFAULT 'return' CONSTRAINT ck_return_from_customer_line_return_reason_kind CHECK (return_reason_kind = 'return'),
    FOREIGN KEY (company_id, return_reason_id, return_reason_kind) REFERENCES reason (company_id, id, kind),
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (return_from_customer_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, return_from_customer_id) REFERENCES return_from_customer (company_id, id),
    FOREIGN KEY (company_id, delivery_line_id) REFERENCES delivery_line (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, product_configuration_id) REFERENCES product_configuration (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_return_from_customer_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_return_from_customer_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_return_from_customer_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);

-- ===== Service receipt [purchasing] (ADR-0037 rules 5-6; ADR-0047 rule 1) =====
CREATE TABLE service_receipt (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,                        -- the processor
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    print_language     text,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    note text CONSTRAINT ck_service_receipt_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE service_receipt_line (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    service_receipt_id      uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_service_receipt_line_line_number CHECK (line_number > 0),
    purchase_order_line_id  uuid NOT NULL,                   -- a line that carries production_order_operation_id (ADR-0037 rule 5)
    quantity                types.quantity NOT NULL CONSTRAINT ck_service_receipt_line_quantity CHECK (quantity > 0),
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator         bigint NOT NULL,                    -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_service_receipt_line_inventory_quantity CHECK (inventory_quantity > 0),
    yield_quantity          types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_service_receipt_line_yield_quantity CHECK (yield_quantity >= 0),
    scrap_quantity          types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_service_receipt_line_scrap_quantity CHECK (scrap_quantity >= 0),
    is_final                boolean NOT NULL DEFAULT false,
    output_lot_id           uuid REFERENCES lot (id),        -- for automatic receipt
    gr_ir_position_from     types.quantity NOT NULL CONSTRAINT ck_service_receipt_line_position_from CHECK (gr_ir_position_from >= 0),
    gr_ir_position_to       types.quantity NOT NULL,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (service_receipt_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, service_receipt_id) REFERENCES service_receipt (company_id, id),
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id),
    CONSTRAINT ck_service_receipt_line_positions CHECK (gr_ir_position_to - gr_ir_position_from = inventory_quantity),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_service_receipt_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_service_receipt_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);

-- ===== Sales: invoice and its corrections [sales] (ADR-0047 rules 6-8) =====
-- Installments are content (document_installment, rule 6); taxes are document_line_tax rows (ADR-0041 rule 6; DS-05-platform.sql).
CREATE TABLE sales_invoice (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL,
    partner_id                 uuid NOT NULL,
    partner_name               text NOT NULL,
    partner_tax_id             text,
    partner_address            jsonb,
    currency                   text NOT NULL REFERENCES currency (code),
    prices_include_tax         boolean NOT NULL DEFAULT false,
    payment_term_id            uuid REFERENCES payment_term (id),
    salesperson_id             uuid,
    document_date              date NOT NULL,
    posting_date               date NOT NULL,             -- frozen at Issue (ADR-0028 rule 7)
    document_discount_percent  types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_sales_invoice_document_discount_percent CHECK (document_discount_percent BETWEEN 0 AND 100),
    print_language             text,
    payment_method_id          uuid,                          -- copied from the profile, then from the source; suggests only (ADR-0068 rules 15, 17)
    incoterm_code              text REFERENCES incoterm (code),   -- advisory only (ADR-0068 rules 19, 20)
    incoterm_place             text,                          -- the named place; requires a code
    business_unit_id           uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    bill_to_partner_id uuid,
    bill_to_name text,
    bill_to_tax_id text,
    bill_to_address_id uuid,
    bill_to_address jsonb,
    FOREIGN KEY (company_id, bill_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, bill_to_partner_id, bill_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_sales_invoice_bill_to CHECK ((bill_to_partner_id IS NULL) = (bill_to_name IS NULL) AND (bill_to_partner_id IS NOT NULL OR bill_to_tax_id IS NULL) AND (bill_to_partner_id IS NOT NULL OR (bill_to_address_id IS NULL AND bill_to_address IS NULL))),
    payer_partner_id uuid,
    payer_name text,
    FOREIGN KEY (company_id, payer_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_sales_invoice_payer CHECK ((payer_partner_id IS NULL) = (payer_name IS NULL)),
    note text CONSTRAINT ck_sales_invoice_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_sales_invoice_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, salesperson_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id),
    CONSTRAINT ck_sales_invoice_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- A stock line refers to a posted delivery line (invoice_exceeds_delivered); a non-stock or service line to an order
-- line or to nothing (rule 6). A stock sale needs an order (sales_order_required, holistic review S9).
CREATE TABLE sales_invoice_line (
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    sales_invoice_id          uuid NOT NULL,
    line_number               integer NOT NULL CONSTRAINT ck_sales_invoice_line_line_number CHECK (line_number > 0),
    sales_order_line_id       uuid,
    delivery_line_id          uuid,
    product_id                uuid NOT NULL,
    item_id                   uuid,
    product_configuration_id  uuid,
    quantity                  types.quantity NOT NULL CONSTRAINT ck_sales_invoice_line_quantity CHECK (quantity > 0),
    uom_id                    uuid NOT NULL REFERENCES uom (id),
    uom_numerator             bigint NOT NULL,                  -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator           bigint NOT NULL,                  -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source         text NOT NULL,                    -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity        types.quantity NOT NULL CONSTRAINT ck_sales_invoice_line_inventory_quantity CHECK (inventory_quantity > 0),
    list_unit_price           types.unit_price,
    manual_unit_price         types.unit_price,
    is_price_manual           boolean NOT NULL DEFAULT false,
    is_price_copied           boolean NOT NULL DEFAULT false,   -- copied prices are exempt from re-pricing (ADR-0047 rule 16; holistic review S2)
    promotion_id              uuid,
    manual_discount_percent   types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_sales_invoice_line_manual_discount_percent CHECK (manual_discount_percent BETWEEN 0 AND 100),
    net_unit_price            types.unit_price NOT NULL CONSTRAINT ck_sales_invoice_line_net_unit_price CHECK (net_unit_price >= 0),
    line_amount               types.amount NOT NULL CONSTRAINT ck_sales_invoice_line_line_amount CHECK (line_amount >= 0),
    document_discount_amount  types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_sales_invoice_line_document_discount_amount CHECK (document_discount_amount >= 0),
    is_free_of_charge         boolean NOT NULL DEFAULT false,
    description               text,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sales_invoice_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, sales_invoice_id) REFERENCES sales_invoice (company_id, id),
    FOREIGN KEY (company_id, sales_order_line_id) REFERENCES sales_order_line (company_id, id),
    FOREIGN KEY (company_id, delivery_line_id) REFERENCES delivery_line (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT fk_sales_invoice_line_item_product FOREIGN KEY (item_id, product_id) REFERENCES item (id, product_id),
    CONSTRAINT fk_sales_invoice_line_configuration FOREIGN KEY (company_id, product_configuration_id, product_id) REFERENCES product_configuration (company_id, id, product_id),
    FOREIGN KEY (company_id, promotion_id) REFERENCES promotion (company_id, id),
    CONSTRAINT ck_sales_invoice_line_manual_price CHECK (is_price_manual = (manual_unit_price IS NOT NULL)),
    CONSTRAINT ck_sales_invoice_line_free_of_charge CHECK (NOT is_free_of_charge OR (net_unit_price = 0 AND line_amount = 0 AND document_discount_amount = 0)),
    CONSTRAINT ck_sales_invoice_line_delivery_item CHECK (delivery_line_id IS NULL OR item_id IS NOT NULL),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_sales_invoice_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_sales_invoice_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE INDEX ix_sales_invoice_line_sales_order_line_id ON sales_invoice_line (sales_order_line_id) WHERE sales_order_line_id IS NOT NULL;
CREATE INDEX ix_sales_invoice_line_delivery_line_id ON sales_invoice_line (delivery_line_id) WHERE delivery_line_id IS NOT NULL;
-- correction_of_id on the document row is the sales invoice, or empty with external_original for an original from
-- before the migration cut-over (ADR-0047 rule 8; ADR-0044 rule 13): number, date, net amounts, tax date and rates.
CREATE TABLE sales_return (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    currency           text NOT NULL REFERENCES currency (code),
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    external_original  jsonb,
    print_language     text,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    bill_to_partner_id uuid,
    bill_to_name text,
    bill_to_tax_id text,
    bill_to_address_id uuid,
    bill_to_address jsonb,
    FOREIGN KEY (company_id, bill_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, bill_to_partner_id, bill_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_sales_return_bill_to CHECK ((bill_to_partner_id IS NULL) = (bill_to_name IS NULL) AND (bill_to_partner_id IS NOT NULL OR bill_to_tax_id IS NULL) AND (bill_to_partner_id IS NOT NULL OR (bill_to_address_id IS NULL AND bill_to_address IS NULL))),
    payer_partner_id uuid,
    payer_name text,
    FOREIGN KEY (company_id, payer_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_sales_return_payer CHECK ((payer_partner_id IS NULL) = (payer_name IS NULL)),
    note text CONSTRAINT ck_sales_return_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE sales_return_line (
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL,
    sales_return_id                uuid NOT NULL,
    line_number                    integer NOT NULL CONSTRAINT ck_sales_return_line_line_number CHECK (line_number > 0),
    correction_of_line_id          uuid,                     -- the sales invoice line credited; empty only with external_original
    return_from_customer_line_id   uuid NOT NULL,            -- the stock return line it credits (ADR-0047 rule 7)
    product_id                     uuid NOT NULL,
    item_id                        uuid NOT NULL,
    quantity                       types.quantity NOT NULL CONSTRAINT ck_sales_return_line_quantity CHECK (quantity > 0),
    uom_id                         uuid NOT NULL REFERENCES uom (id),
    uom_numerator                  bigint NOT NULL,             -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator                bigint NOT NULL,             -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source              text NOT NULL,               -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity             types.quantity NOT NULL CONSTRAINT ck_sales_return_line_inventory_quantity CHECK (inventory_quantity > 0),
    net_unit_price                 types.unit_price NOT NULL CONSTRAINT ck_sales_return_line_net_unit_price CHECK (net_unit_price >= 0),   -- the original's, after the document discount
    is_price_copied                boolean NOT NULL DEFAULT true,     -- the original line's price (ADR-0047 rules 7-8)
    line_amount                    types.amount NOT NULL CONSTRAINT ck_sales_return_line_line_amount CHECK (line_amount >= 0),
    return_reason_id uuid,
    return_reason_kind text NOT NULL DEFAULT 'return' CONSTRAINT ck_sales_return_line_return_reason_kind CHECK (return_reason_kind = 'return'),
    FOREIGN KEY (company_id, return_reason_id, return_reason_kind) REFERENCES reason (company_id, id, kind),
    recorded_at                    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sales_return_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, sales_return_id) REFERENCES sales_return (company_id, id),
    FOREIGN KEY (company_id, correction_of_line_id) REFERENCES sales_invoice_line (company_id, id),
    FOREIGN KEY (company_id, return_from_customer_line_id) REFERENCES return_from_customer_line (company_id, id),
    CONSTRAINT fk_sales_return_line_item_product FOREIGN KEY (item_id, product_id) REFERENCES item (id, product_id),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_sales_return_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_sales_return_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE TABLE credit_note (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    currency           text NOT NULL REFERENCES currency (code),
    reason             text NOT NULL CONSTRAINT ck_credit_note_reason CHECK (reason IN ('allowance', 'trade_discount', 'price_correction', 'cancellation')),   -- rule 8; returned goods only by sales_return
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    external_original  jsonb,
    print_language     text,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    bill_to_partner_id uuid,
    bill_to_name text,
    bill_to_tax_id text,
    bill_to_address_id uuid,
    bill_to_address jsonb,
    FOREIGN KEY (company_id, bill_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, bill_to_partner_id, bill_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_credit_note_bill_to CHECK ((bill_to_partner_id IS NULL) = (bill_to_name IS NULL) AND (bill_to_partner_id IS NOT NULL OR bill_to_tax_id IS NULL) AND (bill_to_partner_id IS NOT NULL OR (bill_to_address_id IS NULL AND bill_to_address IS NULL))),
    payer_partner_id uuid,
    payer_name text,
    FOREIGN KEY (company_id, payer_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_credit_note_payer CHECK ((payer_partner_id IS NULL) = (payer_name IS NULL)),
    note text CONSTRAINT ck_credit_note_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- A quantity credit is round_amount(quantity x original net unit price after the document discount) (rule 8).
CREATE TABLE credit_note_line (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    credit_note_id          uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_credit_note_line_line_number CHECK (line_number > 0),
    correction_of_line_id   uuid,                            -- the sales invoice line; empty only with external_original
    item_id                 uuid,                            -- set with a quantity, so a credit of an external original prints its unit (ADR-0056 rule 9)
    quantity                types.quantity CONSTRAINT ck_credit_note_line_quantity CHECK (quantity > 0),   -- null for an amount-only credit
    uom_id                  uuid REFERENCES uom (id),
    uom_numerator           bigint,                             -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator         bigint,                             -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source       text,                               -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity CONSTRAINT ck_credit_note_line_inventory_quantity CHECK (inventory_quantity > 0),
    net_unit_price          types.unit_price CONSTRAINT ck_credit_note_line_net_unit_price CHECK (net_unit_price >= 0),
    is_price_copied                boolean NOT NULL DEFAULT true,     -- the original line's price (ADR-0047 rules 7-8)
    line_amount             types.amount NOT NULL CONSTRAINT ck_credit_note_line_line_amount CHECK (line_amount > 0),
    description             text,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (credit_note_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, credit_note_id) REFERENCES credit_note (company_id, id),
    FOREIGN KEY (company_id, correction_of_line_id) REFERENCES sales_invoice_line (company_id, id),
    CONSTRAINT ck_credit_note_line_quantity_pair CHECK ((quantity IS NULL) = (inventory_quantity IS NULL) AND (quantity IS NULL OR net_unit_price IS NOT NULL)),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_credit_note_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_credit_note_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_credit_note_line_uom_snapshot CHECK (num_nulls(quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity) IN (0, 6) AND (quantity IS NULL OR item_id IS NOT NULL))
);
CREATE TABLE debit_note (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    currency           text NOT NULL REFERENCES currency (code),
    reason             text NOT NULL CONSTRAINT ck_debit_note_reason CHECK (reason IN ('price_correction', 'additional_charge')),
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    print_language     text,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    bill_to_partner_id uuid,
    bill_to_name text,
    bill_to_tax_id text,
    bill_to_address_id uuid,
    bill_to_address jsonb,
    FOREIGN KEY (company_id, bill_to_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, bill_to_partner_id, bill_to_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_debit_note_bill_to CHECK ((bill_to_partner_id IS NULL) = (bill_to_name IS NULL) AND (bill_to_partner_id IS NOT NULL OR bill_to_tax_id IS NULL) AND (bill_to_partner_id IS NOT NULL OR (bill_to_address_id IS NULL AND bill_to_address IS NULL))),
    payer_partner_id uuid,
    payer_name text,
    FOREIGN KEY (company_id, payer_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_debit_note_payer CHECK ((payer_partner_id IS NULL) = (payer_name IS NULL)),
    note text CONSTRAINT ck_debit_note_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE debit_note_line (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    debit_note_id           uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_debit_note_line_line_number CHECK (line_number > 0),
    correction_of_line_id   uuid NOT NULL,                   -- the sales invoice line
    line_amount             types.amount NOT NULL CONSTRAINT ck_debit_note_line_line_amount CHECK (line_amount > 0),
    description             text,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (debit_note_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, debit_note_id) REFERENCES debit_note (company_id, id),
    FOREIGN KEY (company_id, correction_of_line_id) REFERENCES sales_invoice_line (company_id, id)
);

-- ===== Purchasing: invoice and supplier corrections [purchasing] (ADR-0047 rules 12-15) =====
-- Duplicates: the regime's natural key, else supplier, partner_reference and the year of supplier_invoice_date; canceled
-- or reversed documents do not count, so the key is checked by the command (duplicate_external_document).
CREATE TABLE purchase_invoice (
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    partner_id             uuid NOT NULL,
    partner_name           text NOT NULL,
    partner_tax_id         text,
    partner_address        jsonb,
    partner_reference      text NOT NULL CONSTRAINT ck_purchase_invoice_partner_reference CHECK (length(btrim(partner_reference)) > 0),   -- the supplier's invoice number
    external_document_key  jsonb,                            -- interim: not stated in ADR-0047 (the regime's key fields, e.g. form, symbol, number)
    supplier_invoice_date  date NOT NULL,                    -- the tax date (ADR-0041 rule 7)
    document_date          date NOT NULL,
    posting_date           date NOT NULL,
    currency               text NOT NULL REFERENCES currency (code),
    invoice_rate           types.exchange_rate,              -- interim: column not named in ADR-0047 (the invoice rate of ADR-0011 rule 12; null in company currency)
    payment_term_id        uuid REFERENCES payment_term (id),
    document_discount_percent types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_purchase_invoice_document_discount_percent CHECK (document_discount_percent BETWEEN 0 AND 100),
    print_language         text,
    payment_method_id      uuid,                          -- copied from the profile, then from the source; suggests only (ADR-0068 rules 15, 17)
    incoterm_code          text REFERENCES incoterm (code),   -- advisory only (ADR-0068 rules 19, 20)
    incoterm_place         text,                          -- the named place; requires a code
    business_unit_id       uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    invoicing_party_partner_id uuid,
    invoicing_party_name text,
    invoicing_party_tax_id text,
    invoicing_party_address_id uuid,
    invoicing_party_address jsonb,
    FOREIGN KEY (company_id, invoicing_party_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, invoicing_party_partner_id, invoicing_party_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_purchase_invoice_invoicing_party CHECK ((invoicing_party_partner_id IS NULL) = (invoicing_party_name IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR invoicing_party_tax_id IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR (invoicing_party_address_id IS NULL AND invoicing_party_address IS NULL))),
    payee_partner_id uuid,
    payee_name text,
    FOREIGN KEY (company_id, payee_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_purchase_invoice_payee CHECK ((payee_partner_id IS NULL) = (payee_name IS NULL)),
    note text CONSTRAINT ck_purchase_invoice_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    custom_values jsonb NOT NULL DEFAULT '{}'::jsonb CONSTRAINT ck_purchase_invoice_custom_values CHECK (jsonb_typeof(custom_values) = 'object'),   -- ADR-0074 rules 8, 9
    recorded_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_purchase_invoice_invoice_rate CHECK (invoice_rate IS NULL OR invoice_rate > 0),
    FOREIGN KEY (company_id, payment_method_id) REFERENCES payment_method (company_id, id),
    CONSTRAINT ck_purchase_invoice_incoterm_place CHECK (incoterm_place IS NULL OR incoterm_code IS NOT NULL),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE INDEX ix_purchase_invoice_company_id_partner_id_partner_reference ON purchase_invoice (company_id, coalesce(invoicing_party_partner_id, partner_id), partner_reference);
CREATE TABLE purchase_invoice_line (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    purchase_invoice_id      uuid NOT NULL,
    line_number              integer NOT NULL CONSTRAINT ck_purchase_invoice_line_line_number CHECK (line_number > 0),
    line_kind                text NOT NULL CONSTRAINT ck_purchase_invoice_line_line_kind CHECK (line_kind IN ('goods', 'service', 'expense', 'landed_cost')),
    purchase_order_line_id   uuid,
    service_receipt_line_id  uuid,
    item_id                  uuid,
    account_id               uuid REFERENCES account (id), -- expense lines: key purchase_expense by item group, or entered
    cost_center_id           uuid,
    project_id               uuid,
    quantity                 types.quantity CONSTRAINT ck_purchase_invoice_line_quantity CHECK (quantity > 0),
    uom_id                   uuid REFERENCES uom (id),
    uom_numerator            bigint,                            -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator          bigint,                            -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source        text,                              -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity       types.quantity CONSTRAINT ck_purchase_invoice_line_inventory_quantity CHECK (inventory_quantity > 0),
    unit_price               types.unit_price CONSTRAINT ck_purchase_invoice_line_unit_price CHECK (unit_price >= 0),
    is_price_copied          boolean NOT NULL DEFAULT false,   -- copied from the order line (ADR-0047 rules 2, 16)
    line_amount              types.amount NOT NULL CONSTRAINT ck_purchase_invoice_line_line_amount CHECK (line_amount >= 0),
    document_discount_amount types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_purchase_invoice_line_document_discount_amount CHECK (document_discount_amount >= 0),
    input_use                text NOT NULL DEFAULT 'taxable' CONSTRAINT ck_purchase_invoice_line_input_use CHECK (input_use IN ('taxable', 'non_taxable', 'shared')),   -- ADR-0041 rule 6
    description              text,
    business_unit_id         uuid,                          -- the explicit unit of the line, first in the derivation (ADR-0069 rules 8, 9)
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (purchase_invoice_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, purchase_invoice_id) REFERENCES purchase_invoice (company_id, id),
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id),
    FOREIGN KEY (company_id, service_receipt_line_id) REFERENCES service_receipt_line (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    -- goods: an order line (purchase_order_required); service: optional order line and receipt; expense and landed cost: no order.
    CONSTRAINT ck_purchase_invoice_line_kind_reference CHECK (
        (line_kind = 'goods' AND purchase_order_line_id IS NOT NULL AND service_receipt_line_id IS NULL AND item_id IS NOT NULL AND quantity IS NOT NULL)
        OR (line_kind = 'service' AND (service_receipt_line_id IS NULL OR purchase_order_line_id IS NOT NULL))
        OR (line_kind IN ('expense', 'landed_cost') AND purchase_order_line_id IS NULL AND service_receipt_line_id IS NULL)),
    CONSTRAINT ck_purchase_invoice_line_quantity_pair CHECK ((quantity IS NULL) = (inventory_quantity IS NULL) AND (quantity IS NULL) = (uom_id IS NULL)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_purchase_invoice_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_purchase_invoice_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_purchase_invoice_line_uom_snapshot CHECK (num_nulls(quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity) IN (0, 6)),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE INDEX ix_purchase_invoice_line_purchase_order_line_id ON purchase_invoice_line (purchase_order_line_id) WHERE purchase_order_line_id IS NOT NULL;
CREATE TABLE purchase_return (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    partner_reference  text,                                 -- the supplier's credit number
    currency           text NOT NULL REFERENCES currency (code),
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    external_original  jsonb,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    invoicing_party_partner_id uuid,
    invoicing_party_name text,
    invoicing_party_tax_id text,
    invoicing_party_address_id uuid,
    invoicing_party_address jsonb,
    FOREIGN KEY (company_id, invoicing_party_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, invoicing_party_partner_id, invoicing_party_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_purchase_return_invoicing_party CHECK ((invoicing_party_partner_id IS NULL) = (invoicing_party_name IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR invoicing_party_tax_id IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR (invoicing_party_address_id IS NULL AND invoicing_party_address IS NULL))),
    payee_partner_id uuid,
    payee_name text,
    FOREIGN KEY (company_id, payee_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_purchase_return_payee CHECK ((payee_partner_id IS NULL) = (payee_name IS NULL)),
    note text CONSTRAINT ck_purchase_return_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- correction_of_id on the document row is the purchase invoice; a quantity credit on I by rule 13 (rule 15).
CREATE TABLE purchase_return_line (
    id                            uuid PRIMARY KEY,
    company_id                    uuid NOT NULL,
    purchase_return_id            uuid NOT NULL,
    line_number                   integer NOT NULL CONSTRAINT ck_purchase_return_line_line_number CHECK (line_number > 0),
    correction_of_line_id         uuid,                      -- the purchase invoice line; empty only with external_original
    return_to_supplier_line_id    uuid NOT NULL,
    item_id                       uuid NOT NULL,
    quantity                      types.quantity NOT NULL CONSTRAINT ck_purchase_return_line_quantity CHECK (quantity > 0),   -- as entered (ADR-0056 rule 9)
    uom_id                        uuid NOT NULL REFERENCES uom (id),
    uom_numerator                 bigint NOT NULL,              -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator               bigint NOT NULL,              -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source             text NOT NULL,                -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity            types.quantity NOT NULL CONSTRAINT ck_purchase_return_line_inventory_quantity CHECK (inventory_quantity > 0),
    is_price_copied               boolean NOT NULL DEFAULT true,   -- the original line's price (ADR-0047 rule 15)
    line_amount                   types.amount NOT NULL CONSTRAINT ck_purchase_return_line_line_amount CHECK (line_amount > 0),
    return_reason_id uuid,
    return_reason_kind text NOT NULL DEFAULT 'return' CONSTRAINT ck_purchase_return_line_return_reason_kind CHECK (return_reason_kind = 'return'),
    FOREIGN KEY (company_id, return_reason_id, return_reason_kind) REFERENCES reason (company_id, id, kind),
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (purchase_return_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, purchase_return_id) REFERENCES purchase_return (company_id, id),
    FOREIGN KEY (company_id, correction_of_line_id) REFERENCES purchase_invoice_line (company_id, id),
    FOREIGN KEY (company_id, return_to_supplier_line_id) REFERENCES return_to_supplier_line (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_purchase_return_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_purchase_return_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE TABLE purchase_credit_note (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    partner_reference  text,
    currency           text NOT NULL REFERENCES currency (code),
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    external_original  jsonb,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    invoicing_party_partner_id uuid,
    invoicing_party_name text,
    invoicing_party_tax_id text,
    invoicing_party_address_id uuid,
    invoicing_party_address jsonb,
    FOREIGN KEY (company_id, invoicing_party_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, invoicing_party_partner_id, invoicing_party_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_purchase_credit_note_invoicing_party CHECK ((invoicing_party_partner_id IS NULL) = (invoicing_party_name IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR invoicing_party_tax_id IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR (invoicing_party_address_id IS NULL AND invoicing_party_address IS NULL))),
    payee_partner_id uuid,
    payee_name text,
    FOREIGN KEY (company_id, payee_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_purchase_credit_note_payee CHECK ((payee_partner_id IS NULL) = (payee_name IS NULL)),
    note text CONSTRAINT ck_purchase_credit_note_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
-- Quantity lines are quantity credits on I (rule 13) within the invoice line's invoiced net; price lines are price-only.
CREATE TABLE purchase_credit_note_line (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    purchase_credit_note_id  uuid NOT NULL,
    line_number              integer NOT NULL CONSTRAINT ck_purchase_credit_note_line_line_number CHECK (line_number > 0),
    credit_kind              text NOT NULL CONSTRAINT ck_purchase_credit_note_line_credit_kind CHECK (credit_kind IN ('quantity', 'price')),   -- interim: column name not stated in ADR-0047
    correction_of_line_id    uuid,                           -- the purchase invoice line
    item_id                  uuid,                           -- quantity credits: the item, its entered quantity and unit (ADR-0056 rule 9)
    quantity                 types.quantity CONSTRAINT ck_purchase_credit_note_line_quantity CHECK (quantity > 0),
    uom_id                   uuid REFERENCES uom (id),
    uom_numerator            bigint,                            -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator          bigint,                            -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source        text,                              -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity       types.quantity CONSTRAINT ck_purchase_credit_note_line_inventory_quantity CHECK (inventory_quantity > 0),
    line_amount              types.amount NOT NULL CONSTRAINT ck_purchase_credit_note_line_line_amount CHECK (line_amount > 0),
    description              text,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (purchase_credit_note_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, purchase_credit_note_id) REFERENCES purchase_credit_note (company_id, id),
    FOREIGN KEY (company_id, correction_of_line_id) REFERENCES purchase_invoice_line (company_id, id),
    CONSTRAINT ck_purchase_credit_note_line_kind_quantity CHECK ((credit_kind = 'quantity') = (inventory_quantity IS NOT NULL)
        AND num_nulls(quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity, item_id) IN (0, 7)),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_purchase_credit_note_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_purchase_credit_note_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE TABLE purchase_debit_note (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    partner_name       text NOT NULL,
    partner_tax_id     text,
    partner_address    jsonb,
    partner_reference  text,
    currency           text NOT NULL REFERENCES currency (code),
    document_date      date NOT NULL,
    posting_date       date NOT NULL,
    business_unit_id   uuid,                          -- set by a person or an agent, copied from the source (ADR-0069 rule 8)
    invoicing_party_partner_id uuid,
    invoicing_party_name text,
    invoicing_party_tax_id text,
    invoicing_party_address_id uuid,
    invoicing_party_address jsonb,
    FOREIGN KEY (company_id, invoicing_party_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, invoicing_party_partner_id, invoicing_party_address_id) REFERENCES partner_address (company_id, partner_id, id),
    CONSTRAINT ck_purchase_debit_note_invoicing_party CHECK ((invoicing_party_partner_id IS NULL) = (invoicing_party_name IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR invoicing_party_tax_id IS NULL) AND (invoicing_party_partner_id IS NOT NULL OR (invoicing_party_address_id IS NULL AND invoicing_party_address IS NULL))),
    payee_partner_id uuid,
    payee_name text,
    FOREIGN KEY (company_id, payee_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_purchase_debit_note_payee CHECK ((payee_partner_id IS NULL) = (payee_name IS NULL)),
    note text CONSTRAINT ck_purchase_debit_note_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE purchase_debit_note_line (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    purchase_debit_note_id   uuid NOT NULL,
    line_number              integer NOT NULL CONSTRAINT ck_purchase_debit_note_line_line_number CHECK (line_number > 0),
    correction_of_line_id    uuid NOT NULL,                  -- the purchase invoice line; price-only (rule 15)
    line_amount              types.amount NOT NULL CONSTRAINT ck_purchase_debit_note_line_line_amount CHECK (line_amount > 0),
    description              text,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (purchase_debit_note_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, purchase_debit_note_id) REFERENCES purchase_debit_note (company_id, id),
    FOREIGN KEY (company_id, correction_of_line_id) REFERENCES purchase_invoice_line (company_id, id)
);
-- gr_ir_write_off: internal posting, human_only; moves I up to R at the positions' value on a line closed short (rule 13).
CREATE TABLE gr_ir_write_off (
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL,
    document_date    date NOT NULL,
    posting_date     date NOT NULL,
    reason           text NOT NULL CONSTRAINT ck_gr_ir_write_off_reason CHECK (length(btrim(reason)) > 0),   -- interim: not stated in ADR-0047
    recorded_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id)
);
CREATE TABLE gr_ir_write_off_line (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    gr_ir_write_off_id      uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_gr_ir_write_off_line_line_number CHECK (line_number > 0),
    purchase_order_line_id  uuid NOT NULL,
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_gr_ir_write_off_line_inventory_quantity CHECK (inventory_quantity > 0),
    line_amount             types.amount NOT NULL CONSTRAINT ck_gr_ir_write_off_line_line_amount CHECK (line_amount >= 0),
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (gr_ir_write_off_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, gr_ir_write_off_id) REFERENCES gr_ir_write_off (company_id, id),
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id)
);

-- ===== Line content shared by every document type [sales, purchasing] =====
-- The pricing trace (ADR-0047 rule 16): one row per step, in the line's content, reproducing the stored net unit price
-- and line amount (INV-93). Copied prices carry their source (holistic review S2): a line copied from a quotation within
-- validity, or to an invoice or correction, keeps its steps with source_kind copied and the source line, and the line's
-- is_price_copied exempts it from re-pricing when its item, unit, quantity or date changes; repricing (quotation_expired
-- with reprice) clears the flag and writes new steps with source_kind procedure.
CREATE TABLE document_line_price_step (                    -- [documents] ADR-0047 rule 16; written by sales and purchasing pricing
    company_id                uuid NOT NULL,
    document_id               uuid NOT NULL,
    line_number               integer NOT NULL,
    step_number               integer NOT NULL CONSTRAINT ck_document_line_price_step_step_number CHECK (step_number > 0),
    step                      text NOT NULL CONSTRAINT ck_document_line_price_step_step CHECK (step IN ('list_price', 'base_price', 'promotion', 'manual_discount', 'net_unit_price', 'line_amount', 'document_discount')),
    source_table              text,                          -- e.g. price_list_entry, price_list_option_extra, promotion
    source_id                 uuid,
    value                     numeric NOT NULL,              -- a price, a percentage or an amount, as the step defines
    source_kind               text NOT NULL DEFAULT 'procedure' CONSTRAINT ck_document_line_price_step_source_kind CHECK (source_kind IN ('procedure', 'manual', 'copied')),
    copied_from_document_id   uuid,
    copied_from_line_number   integer,
    recorded_at               timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, line_number, step_number),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, copied_from_document_id) REFERENCES document (company_id, id),
    CONSTRAINT ck_document_line_price_step_copied CHECK ((source_kind = 'copied') = (copied_from_document_id IS NOT NULL AND copied_from_line_number IS NOT NULL)),
    CONSTRAINT ck_document_line_price_step_source CHECK ((source_table IS NULL) = (source_id IS NULL))
);
-- Free text for is_custom values (ADR-0046 rule 9; ADR-0045 rule 15): personal and untrusted.
CREATE TABLE document_line_custom_text (                   -- [documents] ADR-0046 rule 9; ADR-0045 rule 15
    company_id            uuid NOT NULL,
    document_id           uuid NOT NULL,
    line_number           integer NOT NULL,
    variant_attribute_id  uuid NOT NULL,
    text                  text NOT NULL,
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, line_number, variant_attribute_id),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, variant_attribute_id) REFERENCES variant_attribute (company_id, id)
);
-- The installment schedule of an invoice, part of its content (ADR-0047 rule 6; ADR-0026 rule 5); open items are
-- derived from it at posting. interim: table not named in ADR-0047.
CREATE TABLE document_installment (                        -- [documents] ADR-0047 rule 6; ADR-0026 rule 5
    company_id            uuid NOT NULL,
    document_id           uuid NOT NULL,
    installment_number    integer NOT NULL CONSTRAINT ck_document_installment_installment_number CHECK (installment_number > 0),
    due_date              date NOT NULL,
    transaction_amount    types.amount NOT NULL CONSTRAINT ck_document_installment_transaction_amount CHECK (transaction_amount > 0),
    discount_due_date     date,
    discount_percent      types.percent,
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, installment_number),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id),
    CONSTRAINT ck_document_installment_discount CHECK ((discount_due_date IS NULL) = (discount_percent IS NULL))
);

-- ===== Material documents [inventory] (ADR-0020 rule 3; ADR-0023 rule 7; ADR-0030 rule 8; ADR-0031 rules 8, 12) =====
CREATE TABLE material_document (
    id             uuid PRIMARY KEY,
    company_id     uuid NOT NULL,
    document_id    uuid NOT NULL,                            -- one per posting document (ADR-0014 rule 2)
    posting_date   date NOT NULL,
    recorded_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_material_document_document_id UNIQUE (document_id),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id)
);
CREATE TABLE material_document_line (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    material_document_id    uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_material_document_line_line_number CHECK (line_number > 0),
    source_line_number      integer,                         -- interim: not stated in ADR-0020 (the posting document's line that caused it)
    item_id                 uuid NOT NULL,
    warehouse_id            uuid NOT NULL,
    movement_type_id        uuid NOT NULL REFERENCES movement_type (id),
    direction               text NOT NULL CONSTRAINT ck_material_document_line_direction CHECK (direction IN ('in', 'out')),   -- the type's, flipped when is_reversal
    is_reversal             boolean NOT NULL DEFAULT false,
    quantity                types.quantity NOT NULL CONSTRAINT ck_material_document_line_quantity CHECK (quantity > 0),   -- inventory unit (ADR-0018 rule 11)
    lot_id                  uuid REFERENCES lot (id),
    serial_number_id        uuid REFERENCES serial_number (id),
    company_amount          types.amount NOT NULL CONSTRAINT ck_material_document_line_company_amount CHECK (company_amount >= 0),   -- the value moved; zero for non-owned stock
    valuation_warehouse_id  uuid,                            -- the area at level warehouse; null at levels company and site (ADR-0020 rule 2; ADR-0068 rule 8)
    valuation_site_id       uuid,                            -- the area at level site; null at levels company and warehouse; set by the stock lock helper (ADR-0068 rule 8; INV-810)
    derivation_trace_id     uuid REFERENCES derivation_trace (id),
    bin_id                  uuid NOT NULL,                   -- the default bin outside bin-managed warehouses (ADR-0031 rule 8)
    stock_status            text NOT NULL DEFAULT 'available' CONSTRAINT ck_material_document_line_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),
    handling_unit_id        uuid,
    catch_weight_quantity   types.quantity,                  -- reserved, empty until after Phase 1
    cost_object_id          uuid REFERENCES cost_object (id),
    owner_partner_id        uuid,                            -- reserved; null for own stock (ADR-0030 rule 8)
    valuation_type          text,                            -- reserved valuation axis, never set in Phase 1 (ADR-0020 rule 17 note of 2026-11-21)
    posting_date            date NOT NULL,                   -- copied from the posting document (ADR-0031 rule 12; INV-48)
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (material_document_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, material_document_id) REFERENCES material_document (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, valuation_warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_material_document_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, owner_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_material_document_line_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_material_document_line_serial_quantity CHECK (serial_number_id IS NULL OR quantity = 1),
    CONSTRAINT ck_material_document_line_catch_weight CHECK (catch_weight_quantity IS NULL),
    CONSTRAINT ck_material_document_line_valuation_type CHECK (valuation_type IS NULL),   -- reserved until split valuation (ADR-0020 rule 17)
    FOREIGN KEY (company_id, valuation_site_id) REFERENCES site (company_id, id),
    CONSTRAINT ck_material_document_line_valuation_area CHECK (valuation_site_id IS NULL OR valuation_warehouse_id IS NULL)
);
-- The dated negative-stock check reads posting_date per key (ADR-0020 rule 10; ADR-0031 rule 14).
CREATE INDEX ix_material_document_line_company_id_item_id_warehouse_id_posting_date
    ON material_document_line (company_id, item_id, warehouse_id, posting_date);

-- ===== Stock balances [inventory] (ADR-0020 rules 8-10; ADR-0023 rules 4-5; ADR-0030 rule 8) =====
-- Written only through the stock lock helper in the posting transaction; never by other SQL or triggers.
CREATE TABLE stock_value (                                 -- the lock row per (item, warehouse), created on first use
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL,
    item_id          uuid NOT NULL,
    warehouse_id     uuid NOT NULL,
    valuation_type   text,                                   -- reserved valuation axis, never set in Phase 1 (ADR-0020 rules 8, 17 notes of 2026-11-21)
    company_amount   types.amount NOT NULL DEFAULT 0 CONSTRAINT ck_stock_value_company_amount CHECK (company_amount >= 0),   -- negative_stock_value (ADR-0021 rule 9)
    recorded_at      timestamptz NOT NULL DEFAULT now(),     -- the last change
    CONSTRAINT uq_stock_value_key UNIQUE NULLS NOT DISTINCT (company_id, item_id, warehouse_id, valuation_type),   -- a null type counts as one value
    CONSTRAINT ck_stock_value_valuation_type CHECK (valuation_type IS NULL),   -- reserved until split valuation (ADR-0020 rule 17)
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id)
);
CREATE TABLE stock_quantity (
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    item_id            uuid NOT NULL,
    warehouse_id       uuid NOT NULL,
    bin_id             uuid NOT NULL,
    lot_id             uuid REFERENCES lot (id),
    serial_number_id   uuid REFERENCES serial_number (id),
    stock_status       text NOT NULL DEFAULT 'available' CONSTRAINT ck_stock_quantity_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),
    handling_unit_id   uuid,
    owner_partner_id   uuid,
    quantity           types.quantity NOT NULL CONSTRAINT ck_stock_quantity_quantity CHECK (quantity >= 0),   -- no key below zero now (ADR-0023 rule 5)
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    -- The full key; null lot, serial, handling unit and owner each count as one value (ADR-0030 rule 8).
    CONSTRAINT uq_stock_quantity_key UNIQUE NULLS NOT DISTINCT (company_id, item_id, warehouse_id, bin_id, lot_id, serial_number_id, stock_status, handling_unit_id, owner_partner_id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_stock_quantity_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, owner_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_stock_quantity_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_stock_quantity_serial CHECK (serial_number_id IS NULL OR quantity <= 1)
);
CREATE INDEX ix_stock_quantity_company_id_item_id_warehouse_id ON stock_quantity (company_id, item_id, warehouse_id);
-- A serial has at most one unit on hand, whatever its bin, status or owner (ADR-0020 rule 10; INV-22).
CREATE UNIQUE INDEX ux_stock_quantity_serial_on_hand ON stock_quantity (serial_number_id) WHERE serial_number_id IS NOT NULL AND quantity > 0;

-- ===== Preliminary price [inventory] (ADR-0020 rule 11; ADR-0035 rule 4; ADR-0044 rule 9) =====
CREATE TABLE preliminary_price (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    item_id                 uuid NOT NULL,
    valuation_warehouse_id  uuid,                            -- the area at level warehouse; null at levels company and site (ADR-0068 rule 8)
    valuation_site_id       uuid,                            -- the area at level site; null at levels company and warehouse
    posting_period_id       uuid NOT NULL REFERENCES posting_period (id),
    unit_price              types.unit_price NOT NULL CONSTRAINT ck_preliminary_price_unit_price CHECK (unit_price >= 0),   -- company currency per inventory unit
    price_source            text NOT NULL CONSTRAINT ck_preliminary_price_price_source CHECK (price_source IN ('prior_actual', 'area_receipt', 'company_receipt', 'cost_estimate', 'purchase_list', 'last_purchase_invoice', 'opening', 'manual')),   -- interim: not stated in ADR-0020 (which branch of rule 11 gave the price; purchase_list and last_purchase_invoice: its rule 11 note of the UoM simulation review)
    derivation_trace_id     uuid REFERENCES derivation_trace (id),
    set_by_user_id          uuid REFERENCES user_account (id),   -- UpdatePreliminaryPrice is human_only, audited
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_preliminary_price_key UNIQUE NULLS NOT DISTINCT (company_id, item_id, valuation_site_id, valuation_warehouse_id, posting_period_id),   -- the area's pair (ADR-0068 rule 8)
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, valuation_warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT ck_preliminary_price_manual CHECK ((price_source = 'manual') = (set_by_user_id IS NOT NULL)),
    FOREIGN KEY (company_id, valuation_site_id) REFERENCES site (company_id, id),
    CONSTRAINT ck_preliminary_price_valuation_area CHECK (valuation_site_id IS NULL OR valuation_warehouse_id IS NULL)
);

-- ===== Reservations and warehouse tasks [inventory] (ADR-0023 rules 13-15, 20; ADR-0028 rule 2; ADR-0031 rule 6) =====
-- Both refer to demand and supply lines only through demand_supply_line (ADR-0028 rule 2). Writes take the stock_value
-- lock of the item and warehouse (ADR-0023 rule 10).
CREATE TABLE stock_reservation (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    demand_supply_line_id   uuid NOT NULL,
    item_id                 uuid NOT NULL,
    warehouse_id            uuid NOT NULL,
    lot_id                  uuid REFERENCES lot (id),        -- optional, by agreement; never a serial
    quantity                types.quantity NOT NULL CONSTRAINT ck_stock_reservation_quantity CHECK (quantity > 0),
    picked_quantity         types.quantity NOT NULL DEFAULT 0,
    fulfilled_quantity      types.quantity NOT NULL DEFAULT 0,
    state                   text NOT NULL DEFAULT 'open' CONSTRAINT ck_stock_reservation_state CHECK (state IN ('open', 'picked', 'fulfilled', 'canceled')),
    destination_bin_id      uuid,                            -- production component staging (ADR-0034 rule 9)
    release_sequence        integer,
    owner_partner_id        uuid,
    transferred_from_reservation_id uuid,                    -- TransferStockReservation from an approved change proposal (ADR-0064 rule 24)
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, demand_supply_line_id) REFERENCES demand_supply_line (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_stock_reservation_destination_bin FOREIGN KEY (destination_bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, owner_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_stock_reservation_progress CHECK (picked_quantity BETWEEN 0 AND quantity AND fulfilled_quantity BETWEEN 0 AND quantity),
    -- fulfilled when fulfilled equals quantity (rule 13); a plain warehouse fulfils without picks (ADR-0023 rule 16).
    CONSTRAINT ck_stock_reservation_fulfilled CHECK ((state = 'fulfilled') = (fulfilled_quantity = quantity) OR state = 'canceled'),
    CONSTRAINT ck_stock_reservation_picked CHECK (state <> 'picked' OR picked_quantity > fulfilled_quantity),
    CONSTRAINT ck_stock_reservation_transferred_from CHECK (transferred_from_reservation_id IS NULL OR transferred_from_reservation_id <> id)
);
CREATE INDEX ix_stock_reservation_company_id_item_id_warehouse_id ON stock_reservation (company_id, item_id, warehouse_id) WHERE state IN ('open', 'picked');
CREATE INDEX ix_stock_reservation_demand_supply_line_id ON stock_reservation (demand_supply_line_id);
-- The transfer's source, a reservation of the same company (ADR-0064 rule 24); added after the table, as it refers to itself.
ALTER TABLE stock_reservation ADD CONSTRAINT fk_stock_reservation_transferred_from FOREIGN KEY (company_id, transferred_from_reservation_id) REFERENCES stock_reservation (company_id, id);
-- reservation_transfer_invalid: a transferred row has its source's company, item, warehouse and lot; the link never changes after
-- insert, so a transfer chain has no cycle; item, warehouse and lot never change on a row that has or is a source (ADR-0064 rule 24).
CREATE FUNCTION stock_reservation_transfer_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE src stock_reservation%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.transferred_from_reservation_id IS DISTINCT FROM OLD.transferred_from_reservation_id THEN
            RAISE EXCEPTION 'reservation_transfer_link_immutable' USING ERRCODE = 'check_violation';
        END IF;
        IF (NEW.item_id, NEW.warehouse_id, NEW.lot_id) IS DISTINCT FROM (OLD.item_id, OLD.warehouse_id, OLD.lot_id)
           AND (NEW.transferred_from_reservation_id IS NOT NULL
                OR EXISTS (SELECT 1 FROM stock_reservation s WHERE s.transferred_from_reservation_id = NEW.id)) THEN
            RAISE EXCEPTION 'reservation_transfer_invalid' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.transferred_from_reservation_id IS NOT NULL THEN
        SELECT * INTO src FROM stock_reservation WHERE id = NEW.transferred_from_reservation_id;
        IF FOUND AND ((src.company_id, src.item_id, src.warehouse_id) IS DISTINCT FROM (NEW.company_id, NEW.item_id, NEW.warehouse_id)
                      OR src.lot_id IS DISTINCT FROM NEW.lot_id) THEN
            RAISE EXCEPTION 'reservation_transfer_invalid' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_stock_reservation_transfer_guard BEFORE INSERT OR UPDATE OF transferred_from_reservation_id, item_id, warehouse_id, lot_id ON stock_reservation
    FOR EACH ROW EXECUTE FUNCTION stock_reservation_transfer_guard();
CREATE TABLE warehouse_task (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    warehouse_id            uuid NOT NULL,
    task_kind               text NOT NULL CONSTRAINT ck_warehouse_task_task_kind CHECK (task_kind IN ('putaway', 'pick', 'move', 'replenishment', 'status_change', 'count')),
    state                   text NOT NULL DEFAULT 'open' CONSTRAINT ck_warehouse_task_state CHECK (state IN ('open', 'in_progress', 'confirmed', 'canceled')),   -- interim: state names not listed in ADR-0023 (verbs Start, Confirm, Cancel)
    item_id                 uuid,                            -- empty on a count task over bins
    lot_id                  uuid REFERENCES lot (id),
    quantity                types.quantity CONSTRAINT ck_warehouse_task_quantity CHECK (quantity > 0),   -- inventory unit
    uom_id                  uuid REFERENCES uom (id),        -- the demand line's unit, for display (rule 14)
    from_bin_id             uuid,
    to_bin_id               uuid,                            -- empty when putaway found no target (an exception, rule 12)
    handling_unit_id        uuid,
    stock_status            text CONSTRAINT ck_warehouse_task_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),
    to_stock_status         text CONSTRAINT ck_warehouse_task_to_stock_status CHECK (to_stock_status IN ('available', 'quality_inspection', 'blocked')),
    demand_supply_line_id   uuid,                            -- pick and production staging tasks
    source_document_id      uuid,                            -- the posting that created a putaway task (rule 11)
    assigned_user_id        uuid REFERENCES user_account (id),
    confirmed_quantity      types.quantity CONSTRAINT ck_warehouse_task_confirmed_quantity CHECK (confirmed_quantity >= 0),
    shortage_reason         text,
    owner_partner_id        uuid,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT fk_warehouse_task_from_bin FOREIGN KEY (from_bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT fk_warehouse_task_to_bin FOREIGN KEY (to_bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, demand_supply_line_id) REFERENCES demand_supply_line (company_id, id),
    FOREIGN KEY (company_id, source_document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, owner_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_warehouse_task_pick_demand CHECK (task_kind <> 'pick' OR (demand_supply_line_id IS NOT NULL AND item_id IS NOT NULL AND quantity IS NOT NULL)),
    CONSTRAINT ck_warehouse_task_status_change CHECK ((task_kind = 'status_change') = (to_stock_status IS NOT NULL)),
    -- confirmed: the actual quantity, never above the task's (task_quantity_exceeded); a short one needs a reason (rule 15).
    CONSTRAINT ck_warehouse_task_confirmed CHECK ((state = 'confirmed') = (confirmed_quantity IS NOT NULL)
        AND (confirmed_quantity IS NULL OR quantity IS NULL OR confirmed_quantity <= quantity)
        AND (confirmed_quantity IS NULL OR quantity IS NULL OR confirmed_quantity = quantity OR coalesce(length(btrim(shortage_reason)), 0) > 0))
);
CREATE INDEX ix_warehouse_task_company_id_warehouse_id_state ON warehouse_task (company_id, warehouse_id, state) WHERE state IN ('open', 'in_progress');
CREATE INDEX ix_warehouse_task_demand_supply_line_id ON warehouse_task (demand_supply_line_id) WHERE demand_supply_line_id IS NOT NULL;
-- Moves inside one warehouse: no value, no journal; per (item, warehouse, lot or serial) they net to zero (ADR-0023 rule 8).
CREATE TABLE warehouse_movement (
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    warehouse_id            uuid NOT NULL,
    item_id                 uuid NOT NULL,
    lot_id                  uuid REFERENCES lot (id),
    serial_number_id        uuid REFERENCES serial_number (id),
    quantity                types.quantity NOT NULL CONSTRAINT ck_warehouse_movement_quantity CHECK (quantity > 0),
    from_bin_id             uuid NOT NULL,
    to_bin_id               uuid NOT NULL,
    from_stock_status       text NOT NULL CONSTRAINT ck_warehouse_movement_from_stock_status CHECK (from_stock_status IN ('available', 'quality_inspection', 'blocked')),
    to_stock_status         text NOT NULL CONSTRAINT ck_warehouse_movement_to_stock_status CHECK (to_stock_status IN ('available', 'quality_inspection', 'blocked')),
    from_handling_unit_id   uuid,
    to_handling_unit_id     uuid,
    business_date           date NOT NULL,                   -- clock.today, history only
    warehouse_task_id       uuid,
    source_command          text CONSTRAINT ck_warehouse_movement_source_command CHECK (source_command IN ('pack', 'unpack', 'count_correction')),
    owner_partner_id        uuid,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT fk_warehouse_movement_from_bin FOREIGN KEY (from_bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT fk_warehouse_movement_to_bin FOREIGN KEY (to_bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, from_handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, to_handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, warehouse_task_id) REFERENCES warehouse_task (company_id, id),
    FOREIGN KEY (company_id, owner_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_warehouse_movement_source CHECK ((warehouse_task_id IS NULL) <> (source_command IS NULL)),
    CONSTRAINT ck_warehouse_movement_changes CHECK ((from_bin_id, from_stock_status, from_handling_unit_id) IS DISTINCT FROM (to_bin_id, to_stock_status, to_handling_unit_id)),
    CONSTRAINT ck_warehouse_movement_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL)
);
CREATE INDEX ix_warehouse_movement_company_id_item_id_warehouse_id ON warehouse_movement (company_id, item_id, warehouse_id);

-- ===== GR/IR by unit positions [inventory] (ADR-0030 rules 3-5; ADR-0047 rule 13) =====
-- Layers (from, to, price): each position is priced once, when a receipt or an invoice first reaches it, at the line's
-- GR/IR price then in force, an exact rational in the order's currency (set_order_line_gr_ir_price). Positions keep
-- their first price for the life of the line.
CREATE TABLE purchase_order_line_gr_ir_layer (
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    purchase_order_line_id   uuid NOT NULL,
    from_position            types.quantity NOT NULL CONSTRAINT ck_purchase_order_line_gr_ir_layer_from_position CHECK (from_position >= 0),
    to_position              types.quantity NOT NULL,
    price_numerator          numeric NOT NULL,
    price_denominator        numeric NOT NULL,
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id),
    CONSTRAINT ck_purchase_order_line_gr_ir_layer_positions CHECK (to_position > from_position),
    CONSTRAINT ck_purchase_order_line_gr_ir_layer_price CHECK (price_numerator >= 0 AND price_denominator > 0
        AND price_numerator = trunc(price_numerator) AND price_denominator = trunc(price_denominator)),
    CONSTRAINT ex_purchase_order_line_gr_ir_layer_overlap EXCLUDE USING gist (
        purchase_order_line_id WITH =, numrange(from_position, to_position, '[)') WITH &&)
);
-- One row per GR/IR posting on a line: postings are differences of rounded cumulative values (rule 13), so the line's
-- balance, the sum of gr_ir_amount (debit positive), is round(V(I)) - round(V(R)) (INV-92). A reversal mirrors one
-- posting exactly and is allowed only for the latest unreversed posting of its side (reversal_not_latest).
-- interim: table not named in ADR-0047, which names the interface post_gr_ir_positions (side, quantity, sign).
-- A posting of kind rounding_clearing is the whole of a gr_ir_rounding_clearing document: its own document row (DS-05 document),
-- no header or line table; it never counts as latest and a later posting on the line reverses it first (ADR-0056 rule 10).
CREATE TABLE purchase_order_line_gr_ir_posting (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL,
    purchase_order_line_id     uuid NOT NULL,
    document_id                uuid NOT NULL,
    line_number                integer NOT NULL,             -- the posting document's line
    posting_kind               text NOT NULL CONSTRAINT ck_purchase_order_line_gr_ir_posting_posting_kind CHECK (posting_kind IN ('receipt', 'return', 'invoice', 'quantity_credit', 'write_off', 'rounding_clearing')),
    from_position              types.quantity NOT NULL CONSTRAINT ck_purchase_order_line_gr_ir_posting_from_position CHECK (from_position >= 0),
    to_position                types.quantity NOT NULL,
    gr_ir_amount               types.amount NOT NULL,        -- order currency; receipt and quantity credit negative, invoice, return and write-off positive
    reversal_of_posting_id     uuid,
    recorded_at                timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, reversal_of_posting_id) REFERENCES purchase_order_line_gr_ir_posting (company_id, id),
    CONSTRAINT uq_purchase_order_line_gr_ir_posting_reversal_of_posting_id UNIQUE (reversal_of_posting_id),
    CONSTRAINT ck_purchase_order_line_gr_ir_posting_positions CHECK (to_position > from_position),
    CONSTRAINT ck_purchase_order_line_gr_ir_posting_sign CHECK (reversal_of_posting_id IS NOT NULL
        OR (posting_kind IN ('receipt', 'quantity_credit') AND gr_ir_amount <= 0)
        OR (posting_kind IN ('invoice', 'return', 'write_off') AND gr_ir_amount >= 0)
        -- gr_ir_rounding_clearing moves the lagging side within the unit rounding tolerance, either way (ADR-0056 rule 10)
        OR posting_kind = 'rounding_clearing')
);
CREATE INDEX ix_purchase_order_line_gr_ir_posting_purchase_order_line_id ON purchase_order_line_gr_ir_posting (purchase_order_line_id);
-- Invoice first: the stock-bound difference for quantities not yet received waits here until the receipt (ADR-0030 rule 4).
CREATE TABLE pending_receipt_adjustment (
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL,
    purchase_order_line_id      uuid NOT NULL,
    purchase_invoice_line_id    uuid NOT NULL,
    clearing_journal_line_id    uuid NOT NULL REFERENCES journal_line (id),   -- the invoice's purchase_cost_clearing line, the source of the landed cost
    total_company_amount        types.amount NOT NULL,        -- the total difference in company currency (may be negative)
    quantity_to_receive         types.quantity NOT NULL CONSTRAINT ck_pending_receipt_adjustment_quantity_to_receive CHECK (quantity_to_receive >= 0),
    amount_to_apply             types.amount NOT NULL,
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_pending_receipt_adjustment_purchase_invoice_line_id UNIQUE (purchase_invoice_line_id),   -- one row per invoice line
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id),
    FOREIGN KEY (company_id, purchase_invoice_line_id) REFERENCES purchase_invoice_line (company_id, id),
    CONSTRAINT ck_pending_receipt_adjustment_amount CHECK (sign(amount_to_apply) * sign(total_company_amount) >= 0 AND abs(amount_to_apply) <= abs(total_company_amount)
        AND (quantity_to_receive > 0 OR amount_to_apply = 0))
);
CREATE INDEX ix_pending_receipt_adjustment_purchase_order_line_id ON pending_receipt_adjustment (purchase_order_line_id) WHERE quantity_to_receive > 0;

-- ===== Keys added to tables of other design items (ADR-0028 rule 2; ADR-0030 rule 3) =====
-- GR/IR lines name their purchase order line; the column exists in DS-06 from step 1, the key comes with the table.
ALTER TABLE journal_line ADD CONSTRAINT fk_journal_line_purchase_order_line
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id);
-- demand_supply_line has the step 5 line columns from step 3; their keys are added with the line tables.
ALTER TABLE demand_supply_line ADD CONSTRAINT fk_demand_supply_line_sales_order_line
    FOREIGN KEY (company_id, sales_order_line_id) REFERENCES sales_order_line (company_id, id);
ALTER TABLE demand_supply_line ADD CONSTRAINT fk_demand_supply_line_purchase_order_line
    FOREIGN KEY (company_id, purchase_order_line_id) REFERENCES purchase_order_line (company_id, id);
ALTER TABLE demand_supply_line ADD CONSTRAINT fk_demand_supply_line_purchase_request_line
    FOREIGN KEY (company_id, purchase_request_line_id) REFERENCES purchase_request_line (company_id, id);

-- ===== Append-only rows (ADR-0020 rule 3; ADR-0023 rule 8; ADR-0047 rule 13) =====
CREATE FUNCTION inventory_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% rows are append-only (ADR-0020 rule 3; ADR-0023 rule 8; ADR-0047 rule 13)', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END $$;
CREATE TRIGGER trg_material_document_append_only
    BEFORE UPDATE OR DELETE ON material_document FOR EACH ROW EXECUTE FUNCTION inventory_reject_change();
CREATE TRIGGER trg_material_document_line_append_only
    BEFORE UPDATE OR DELETE ON material_document_line FOR EACH ROW EXECUTE FUNCTION inventory_reject_change();
CREATE TRIGGER trg_warehouse_movement_append_only
    BEFORE UPDATE OR DELETE ON warehouse_movement FOR EACH ROW EXECUTE FUNCTION inventory_reject_change();
CREATE TRIGGER trg_purchase_order_line_gr_ir_posting_append_only
    BEFORE UPDATE OR DELETE ON purchase_order_line_gr_ir_posting FOR EACH ROW EXECUTE FUNCTION inventory_reject_change();
CREATE TRIGGER trg_material_document_line_no_truncate
    BEFORE TRUNCATE ON material_document_line FOR EACH STATEMENT EXECUTE FUNCTION inventory_reject_change();
-- Layers never change once written: a position keeps its first price (ADR-0047 rule 13).
CREATE TRIGGER trg_purchase_order_line_gr_ir_layer_append_only
    BEFORE UPDATE OR DELETE ON purchase_order_line_gr_ir_layer FOR EACH ROW EXECUTE FUNCTION inventory_reject_change();
-- The company's barcode registry (DS-20, ADR-0061 rule 7): a handling unit's barcode is unique across every barcode type,
-- and stays reserved when the unit goes; a supplier's SSCC may be released only after the GS1 reuse period.
CREATE TRIGGER trg_handling_unit_register AFTER INSERT OR UPDATE OF barcode, is_legacy_barcode OR DELETE ON handling_unit
    FOR EACH ROW EXECUTE FUNCTION barcode_register('handling_unit', 'barcode', 'id');

-- ===== Stock documents [inventory] (ADR-0075; ADR-0020 rules 4-7, 18; ADR-0023 rules 7, 9, 13, 18; ADR-0027 rule 7) =====
-- The posting document types that ADR-0027 rule 7 left to a DS-09 deliverable: the stock transfer, the stock count, scrap and
-- internal consumption. Each is a typed header with lines (ADR-0009 rule 1), reversible (ADR-0020 rule 7), and posts one
-- material document through the stock lock helper and the journal through the posting interfaces, like goods_receipt. The
-- material document line names its source line by source_line_number; no back-link column is kept. The remaining step 3 types
-- (other_receipt, other_issue, opening_balance and the non-posting transfer_order) follow below (ADR-0075 rules 11 to 15).
CREATE TABLE stock_transfer (                              -- [inventory] ADR-0075 rule 1; reversible (ADR-0020 rule 7)
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL,
    step                  text NOT NULL CONSTRAINT ck_stock_transfer_step CHECK (step IN ('direct', 'dispatch', 'receive')),   -- one document, or two through a transit warehouse (ADR-0023 rule 7)
    from_warehouse_id     uuid NOT NULL,
    to_warehouse_id       uuid NOT NULL,
    dispatch_transfer_id  uuid,                              -- a receive names the dispatch it receives
    reference             text,                              -- the sender's or the carrier's reference
    document_date         date NOT NULL,
    posting_date          date NOT NULL,
    note                  text CONSTRAINT ck_stock_transfer_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, from_warehouse_id, to_warehouse_id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, from_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, to_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, dispatch_transfer_id) REFERENCES stock_transfer (company_id, id),
    CONSTRAINT ck_stock_transfer_warehouses CHECK (from_warehouse_id <> to_warehouse_id),
    CONSTRAINT ck_stock_transfer_dispatch CHECK ((step = 'receive') = (dispatch_transfer_id IS NOT NULL))
);
-- At most one live receive per dispatch (not canceled, not reversed) is enforced by the command under the dispatch's lock and checked by INV-867 (ADR-0075 rule 2); the document state is on another table, so the index is not unique.
CREATE INDEX ix_stock_transfer_dispatch_transfer_id ON stock_transfer (dispatch_transfer_id) WHERE dispatch_transfer_id IS NOT NULL;
CREATE TABLE stock_transfer_line (                         -- [inventory] ADR-0075 rule 1
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    stock_transfer_id       uuid NOT NULL,
    from_warehouse_id       uuid NOT NULL,                   -- carried for the bin keys below
    to_warehouse_id         uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_stock_transfer_line_line_number CHECK (line_number > 0),
    item_id                 uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_stock_transfer_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot, as on every document line (ADR-0056 rule 9)
    uom_denominator         bigint NOT NULL,
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_stock_transfer_line_inventory_quantity CHECK (inventory_quantity > 0),
    from_bin_id             uuid,                            -- the line's bin, else the default bin (ADR-0023 rule 7)
    to_bin_id               uuid,                            -- the receiving bin, else the default receiving bin
    lot_id                  uuid REFERENCES lot (id),
    serial_number_id        uuid REFERENCES serial_number (id),
    handling_unit_id        uuid,                            -- keeps its identity through transit (ADR-0023 rule 7); transfers move available stock only
    dispatch_line_id        uuid,                            -- a receive line names the dispatch line it receives
    transfer_order_line_id  uuid,                            -- the transfer order line it fulfils: a direct transfer between its two warehouses, a dispatch from its source, a receive into its destination (ADR-0075 rule 14; INV-871)
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (stock_transfer_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, stock_transfer_id, from_warehouse_id, to_warehouse_id) REFERENCES stock_transfer (company_id, id, from_warehouse_id, to_warehouse_id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT fk_stock_transfer_line_from_bin FOREIGN KEY (from_bin_id, from_warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT fk_stock_transfer_line_to_bin FOREIGN KEY (to_bin_id, to_warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, dispatch_line_id) REFERENCES stock_transfer_line (company_id, id),
    FOREIGN KEY (company_id, transfer_order_line_id) REFERENCES transfer_order_line (company_id, id),
    CONSTRAINT ck_stock_transfer_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_stock_transfer_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_stock_transfer_line_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_stock_transfer_line_serial_quantity CHECK (serial_number_id IS NULL OR inventory_quantity = 1)
);
CREATE INDEX ix_stock_transfer_line_dispatch_line_id ON stock_transfer_line (dispatch_line_id) WHERE dispatch_line_id IS NOT NULL;
CREATE INDEX ix_stock_transfer_line_company_id_item_id ON stock_transfer_line (company_id, item_id);

CREATE TABLE stock_count (                                 -- [inventory] ADR-0075 rule 3; reversible (ADR-0020 rule 7)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    warehouse_id        uuid NOT NULL,                       -- one count document counts one warehouse
    document_date       date NOT NULL,
    posting_date        date NOT NULL,
    note                text CONSTRAINT ck_stock_count_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    business_unit_id    uuid,                                -- set by a person or an agent (ADR-0069 rule 8)
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, warehouse_id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE stock_count_line (                            -- [inventory] ADR-0075 rule 3; one counted entry; several entries of one key are summed (ADR-0056 rule 15)
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    stock_count_id          uuid NOT NULL,
    warehouse_id            uuid NOT NULL,                   -- carried for the bin key below
    line_number             integer NOT NULL CONSTRAINT ck_stock_count_line_line_number CHECK (line_number > 0),
    item_id                 uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_stock_count_line_quantity CHECK (quantity >= 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot, as on every document line (ADR-0056 rule 9)
    uom_denominator         bigint NOT NULL,
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_stock_count_line_inventory_quantity CHECK (inventory_quantity >= 0),
    bin_id                  uuid NOT NULL,                   -- the counted bin; the default bin outside bin-managed warehouses
    lot_id                  uuid REFERENCES lot (id),
    serial_number_id        uuid REFERENCES serial_number (id),
    stock_status            text NOT NULL DEFAULT 'available' CONSTRAINT ck_stock_count_line_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),   -- the counted status
    book_quantity           types.quantity NOT NULL CONSTRAINT ck_stock_count_line_book_quantity CHECK (book_quantity >= 0),   -- inventory unit; the book quantity of the key, frozen at book_taken_at; equal on every line of one key (INV-865)
    book_taken_at           timestamptz NOT NULL,            -- the confirmation of the count task, else the creation of the draft (ADR-0023 rule 18)
    count_task_id           uuid,                            -- the confirmed count task that created the line
    difference_reason_id    uuid,                            -- reason, kind count_difference, the same on every line of one key; required on a key with a difference while documents.reason_required.count_difference is true (ADR-0074 rule 22)
    difference_reason_kind  text NOT NULL DEFAULT 'count_difference' CONSTRAINT ck_stock_count_line_difference_reason_kind CHECK (difference_reason_kind = 'count_difference'),
    difference_note         text CONSTRAINT ck_stock_count_line_difference_note CHECK (difference_note IS NULL OR char_length(difference_note) <= 4000),
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (stock_count_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, stock_count_id, warehouse_id) REFERENCES stock_count (company_id, id, warehouse_id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT fk_stock_count_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, count_task_id) REFERENCES warehouse_task (company_id, id),
    FOREIGN KEY (company_id, difference_reason_id, difference_reason_kind) REFERENCES reason (company_id, id, kind),
    CONSTRAINT ck_stock_count_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_stock_count_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_stock_count_line_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_stock_count_line_serial_quantity CHECK (serial_number_id IS NULL OR (inventory_quantity <= 1 AND book_quantity <= 1))
);
CREATE INDEX ix_stock_count_line_company_id_item_id ON stock_count_line (company_id, item_id);
CREATE INDEX ix_stock_count_line_count_task_id ON stock_count_line (count_task_id) WHERE count_task_id IS NOT NULL;

CREATE TABLE scrap (                                       -- [inventory] ADR-0075 rule 4; reversible (ADR-0020 rule 7)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    document_date       date NOT NULL,
    posting_date        date NOT NULL,
    note                text CONSTRAINT ck_scrap_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    business_unit_id    uuid,                                -- set by a person or an agent (ADR-0069 rule 8)
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE scrap_line (                                  -- [inventory] ADR-0075 rule 4
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    scrap_id            uuid NOT NULL,
    line_number         integer NOT NULL CONSTRAINT ck_scrap_line_line_number CHECK (line_number > 0),
    item_id             uuid NOT NULL,
    warehouse_id        uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_scrap_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot, as on every document line (ADR-0056 rule 9)
    uom_denominator         bigint NOT NULL,
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_scrap_line_inventory_quantity CHECK (inventory_quantity > 0),
    bin_id              uuid NOT NULL,                       -- the line's bin; the default bin outside bin-managed warehouses (ADR-0023 rule 7)
    lot_id              uuid REFERENCES lot (id),
    serial_number_id    uuid REFERENCES serial_number (id),
    stock_status        text NOT NULL DEFAULT 'available' CONSTRAINT ck_scrap_line_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),   -- the held status the goods are scrapped from (ADR-0070 rule 15)
    handling_unit_id    uuid,
    scrap_reason_id     uuid,                                -- reason, kind scrap; required while documents.reason_required.scrap is true (ADR-0074 rule 22)
    scrap_reason_kind   text NOT NULL DEFAULT 'scrap' CONSTRAINT ck_scrap_line_scrap_reason_kind CHECK (scrap_reason_kind = 'scrap'),
    reason_note         text CONSTRAINT ck_scrap_line_reason_note CHECK (reason_note IS NULL OR char_length(reason_note) <= 4000),
    cost_center_id      uuid,                                -- the cost center that bears the loss, when the account determination reads it
    project_id          uuid,
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scrap_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, scrap_id) REFERENCES scrap (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_scrap_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, scrap_reason_id, scrap_reason_kind) REFERENCES reason (company_id, id, kind),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, project_id) REFERENCES project (company_id, id),
    CONSTRAINT ck_scrap_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_scrap_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_scrap_line_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_scrap_line_serial_quantity CHECK (serial_number_id IS NULL OR inventory_quantity = 1),
    CONSTRAINT ck_scrap_line_dimension CHECK (num_nonnulls(cost_center_id, project_id) <= 1)
);
CREATE INDEX ix_scrap_line_company_id_item_id ON scrap_line (company_id, item_id);

CREATE TABLE internal_consumption (                        -- [inventory] ADR-0075 rule 5; reversible (ADR-0020 rule 7)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    document_date       date NOT NULL,
    posting_date        date NOT NULL,
    note                text CONSTRAINT ck_internal_consumption_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    business_unit_id    uuid,                                -- set by a person or an agent (ADR-0069 rule 8)
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE internal_consumption_line (                   -- [inventory] ADR-0075 rule 5
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    internal_consumption_id uuid NOT NULL,
    line_number         integer NOT NULL CONSTRAINT ck_internal_consumption_line_line_number CHECK (line_number > 0),
    item_id             uuid NOT NULL,
    warehouse_id        uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_internal_consumption_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot, as on every document line (ADR-0056 rule 9)
    uom_denominator         bigint NOT NULL,
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_internal_consumption_line_inventory_quantity CHECK (inventory_quantity > 0),
    bin_id              uuid NOT NULL,
    lot_id              uuid REFERENCES lot (id),
    serial_number_id    uuid REFERENCES serial_number (id),
    stock_status        text NOT NULL DEFAULT 'available' CONSTRAINT ck_internal_consumption_line_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),   -- the held status of a sample (ADR-0070 rule 15)
    handling_unit_id    uuid,
    consumption_kind    text NOT NULL DEFAULT 'internal' CONSTRAINT ck_internal_consumption_line_consumption_kind CHECK (consumption_kind IN ('internal', 'quality_sample')),   -- movement type internal_consumption or quality_sample
    cost_center_id      uuid,
    project_id          uuid,
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (internal_consumption_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, internal_consumption_id) REFERENCES internal_consumption (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_internal_consumption_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, project_id) REFERENCES project (company_id, id),
    CONSTRAINT ck_internal_consumption_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_internal_consumption_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_internal_consumption_line_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_internal_consumption_line_serial_quantity CHECK (serial_number_id IS NULL OR inventory_quantity = 1),
    -- exactly one cost center or project bears an internal consumption; a quality sample may name none (ADR-0075 rule 5)
    CONSTRAINT ck_internal_consumption_line_dimension CHECK (num_nonnulls(cost_center_id, project_id) = 1
        OR (consumption_kind = 'quality_sample' AND num_nonnulls(cost_center_id, project_id) = 0))
);
CREATE INDEX ix_internal_consumption_line_company_id_item_id ON internal_consumption_line (company_id, item_id);

CREATE TABLE other_receipt (                                 -- [inventory] ADR-0075 rule 11; reversible (ADR-0020 rule 7)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    document_date       date NOT NULL,
    posting_date        date NOT NULL,
    note                text CONSTRAINT ck_other_receipt_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    business_unit_id    uuid,                                -- set by a person or an agent (ADR-0069 rule 8)
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE other_receipt_line (                                  -- [inventory] ADR-0075 rule 11
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    other_receipt_id    uuid NOT NULL,
    line_number         integer NOT NULL CONSTRAINT ck_other_receipt_line_line_number CHECK (line_number > 0),
    item_id             uuid NOT NULL,
    warehouse_id        uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_other_receipt_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot, as on every document line (ADR-0056 rule 9)
    uom_denominator         bigint NOT NULL,
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_other_receipt_line_inventory_quantity CHECK (inventory_quantity > 0),
    bin_id              uuid,                                -- the line's bin, else the default receiving bin (ADR-0023 rule 7)
    lot_id              uuid REFERENCES lot (id),
    serial_number_id    uuid REFERENCES serial_number (id),
    stock_status        text NOT NULL DEFAULT 'available' CONSTRAINT ck_other_receipt_line_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),   -- quality_inspection when the product requires inspection at receipt (ADR-0070 rule 2)
    handling_unit_id    uuid,
    company_amount      types.amount NOT NULL CONSTRAINT ck_other_receipt_line_company_amount CHECK (company_amount >= 0),   -- the line's value in company currency (value source document)
    reason_id           uuid,                                -- reason, kind other_receipt; required while documents.reason_required.other_receipt is true (ADR-0074 rule 22)
    reason_kind         text NOT NULL DEFAULT 'other_receipt' CONSTRAINT ck_other_receipt_line_reason_kind CHECK (reason_kind = 'other_receipt'),
    reason_note         text CONSTRAINT ck_other_receipt_line_reason_note CHECK (reason_note IS NULL OR char_length(reason_note) <= 4000),
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (other_receipt_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, other_receipt_id) REFERENCES other_receipt (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_other_receipt_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, reason_id, reason_kind) REFERENCES reason (company_id, id, kind),
    CONSTRAINT ck_other_receipt_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_other_receipt_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_other_receipt_line_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_other_receipt_line_serial_quantity CHECK (serial_number_id IS NULL OR inventory_quantity = 1)
);
CREATE INDEX ix_other_receipt_line_company_id_item_id ON other_receipt_line (company_id, item_id);

CREATE TABLE other_issue (                                 -- [inventory] ADR-0075 rule 12; reversible (ADR-0020 rule 7)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    document_date       date NOT NULL,
    posting_date        date NOT NULL,
    note                text CONSTRAINT ck_other_issue_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    business_unit_id    uuid,                                -- set by a person or an agent (ADR-0069 rule 8)
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id)
);
CREATE TABLE other_issue_line (                                  -- [inventory] ADR-0075 rule 12
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    other_issue_id      uuid NOT NULL,
    line_number         integer NOT NULL CONSTRAINT ck_other_issue_line_line_number CHECK (line_number > 0),
    item_id             uuid NOT NULL,
    warehouse_id        uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_other_issue_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot, as on every document line (ADR-0056 rule 9)
    uom_denominator         bigint NOT NULL,
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_other_issue_line_inventory_quantity CHECK (inventory_quantity > 0),
    bin_id              uuid NOT NULL,                       -- the line's bin; the default bin outside bin-managed warehouses (ADR-0023 rule 7; ADR-0031 rule 8)
    lot_id              uuid REFERENCES lot (id),
    serial_number_id    uuid REFERENCES serial_number (id),
    stock_status        text NOT NULL DEFAULT 'available' CONSTRAINT ck_other_issue_line_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),   -- the status the goods leave
    handling_unit_id    uuid,
    reason_id           uuid,                                -- reason, kind other_issue; required while documents.reason_required.other_issue is true (ADR-0074 rule 22)
    reason_kind         text NOT NULL DEFAULT 'other_issue' CONSTRAINT ck_other_issue_line_reason_kind CHECK (reason_kind = 'other_issue'),
    reason_note         text CONSTRAINT ck_other_issue_line_reason_note CHECK (reason_note IS NULL OR char_length(reason_note) <= 4000),
    cost_center_id      uuid,
    project_id          uuid,
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (other_issue_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, other_issue_id) REFERENCES other_issue (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_other_issue_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    FOREIGN KEY (company_id, reason_id, reason_kind) REFERENCES reason (company_id, id, kind),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, project_id) REFERENCES project (company_id, id),
    CONSTRAINT ck_other_issue_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_other_issue_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_other_issue_line_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_other_issue_line_serial_quantity CHECK (serial_number_id IS NULL OR inventory_quantity = 1),
    CONSTRAINT ck_other_issue_line_dimension CHECK (num_nonnulls(cost_center_id, project_id) <= 1)
);
CREATE INDEX ix_other_issue_line_company_id_item_id ON other_issue_line (company_id, item_id);

CREATE TABLE opening_balance (                                 -- [inventory] ADR-0075 rule 13; reversible (ADR-0020 rule 7)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    document_date       date NOT NULL,
    posting_date        date NOT NULL,
    note                text CONSTRAINT ck_opening_balance_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id)
);
CREATE TABLE opening_balance_line (                                  -- [inventory] ADR-0075 rule 13; value spread from the item's total per valuation area (ADR-0044 rule 9)
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    opening_balance_id  uuid NOT NULL,
    line_number         integer NOT NULL CONSTRAINT ck_opening_balance_line_line_number CHECK (line_number > 0),
    item_id             uuid NOT NULL,
    warehouse_id        uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_opening_balance_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot, as on every document line (ADR-0056 rule 9)
    uom_denominator         bigint NOT NULL,
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_opening_balance_line_inventory_quantity CHECK (inventory_quantity > 0),
    bin_id              uuid NOT NULL,                       -- the line's bin; the default bin outside bin-managed warehouses (ADR-0023 rule 7; ADR-0031 rule 8)
    lot_id              uuid REFERENCES lot (id),
    serial_number_id    uuid REFERENCES serial_number (id),
    stock_status        text NOT NULL DEFAULT 'available' CONSTRAINT ck_opening_balance_line_stock_status CHECK (stock_status IN ('available', 'quality_inspection', 'blocked')),   -- any status, as in the old books (ADR-0023 rule 7)
    handling_unit_id    uuid,
    company_amount      types.amount NOT NULL CONSTRAINT ck_opening_balance_line_company_amount CHECK (company_amount >= 0),   -- the line's value in company currency (value source document)
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (opening_balance_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, opening_balance_id) REFERENCES opening_balance (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_opening_balance_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    FOREIGN KEY (company_id, handling_unit_id) REFERENCES handling_unit (company_id, id),
    CONSTRAINT ck_opening_balance_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_opening_balance_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    CONSTRAINT ck_opening_balance_line_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_opening_balance_line_serial_quantity CHECK (serial_number_id IS NULL OR inventory_quantity = 1)
);
CREATE INDEX ix_opening_balance_line_company_id_item_id ON opening_balance_line (company_id, item_id);

-- The non-posting demand document of a planned move between two warehouses (ADR-0027 rule 7; ADR-0024 rule 8): each line is a
-- demand row at the source and a supply row at the destination; stock transfers fulfil it in one step or two (ADR-0075 rule 14).
CREATE TABLE transfer_order (                              -- [inventory] ADR-0075 rule 14; non-posting, change orders from step 5 (ADR-0028 rule 4)
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    from_warehouse_id       uuid NOT NULL,
    to_warehouse_id         uuid NOT NULL,
    transfer_route_id       uuid,                            -- the route planning converted it from; its lead time dates the supply (ADR-0024 rule 3)
    document_date           date NOT NULL,
    requested_date          date NOT NULL,                   -- the date the goods are needed at the destination
    note                    text CONSTRAINT ck_transfer_order_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- ADR-0074 rule 16
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, from_warehouse_id, to_warehouse_id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, from_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, to_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, transfer_route_id) REFERENCES transfer_route (company_id, id),
    CONSTRAINT ck_transfer_order_warehouses CHECK (from_warehouse_id <> to_warehouse_id)
);
CREATE TABLE transfer_order_line (                         -- [inventory] ADR-0075 rule 14
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    transfer_order_id       uuid NOT NULL,
    from_warehouse_id       uuid NOT NULL,                   -- carried from the header, for its key
    to_warehouse_id         uuid NOT NULL,
    line_number             integer NOT NULL CONSTRAINT ck_transfer_order_line_line_number CHECK (line_number > 0),
    item_id                 uuid NOT NULL,
    quantity                types.quantity NOT NULL CONSTRAINT ck_transfer_order_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                  uuid NOT NULL REFERENCES uom (id),
    uom_numerator           bigint NOT NULL,                    -- the conversion snapshot, as on every document line (ADR-0056 rule 9)
    uom_denominator         bigint NOT NULL,
    uom_factor_source       text NOT NULL,                      -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity      types.quantity NOT NULL CONSTRAINT ck_transfer_order_line_inventory_quantity CHECK (inventory_quantity > 0),
    lot_id                  uuid REFERENCES lot (id),        -- optional, by agreement; never a serial (as a reservation, ADR-0023 rule 13)
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (transfer_order_id, line_number),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, transfer_order_id, from_warehouse_id, to_warehouse_id) REFERENCES transfer_order (company_id, id, from_warehouse_id, to_warehouse_id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT ck_transfer_order_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_transfer_order_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE INDEX ix_transfer_order_line_company_id_item_id ON transfer_order_line (company_id, item_id);
-- demand_supply_line gets the key its step 3 column was waiting for (ADR-0028 rule 2).
ALTER TABLE demand_supply_line ADD CONSTRAINT fk_demand_supply_line_transfer_order_line
    FOREIGN KEY (company_id, transfer_order_line_id) REFERENCES transfer_order_line (company_id, id);
