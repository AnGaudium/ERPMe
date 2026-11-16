-- Simulation stubs: tables the six flows write that have no design DDL yet. NOT design DDL.
-- Each stub carries only the columns the simulation reads; the README lists them as stubs.
SET search_path = nativeflows;

-- lab stub tax_code (00_stubs.sql has only id): the DS-19 tax_codes.csv columns the simulation reads (DS-23 pending)
ALTER TABLE tax_code ADD COLUMN code text UNIQUE, ADD COLUMN tax_kind text, ADD COLUMN direction text,
    ADD COLUMN transaction_key text, ADD COLUMN deductibility text;
-- tax rates by date (DS-19 tax_rates.csv; DS-23 pending)
CREATE TABLE tax_rate (id uuid PRIMARY KEY, tax_code_id uuid NOT NULL REFERENCES tax_code (id), effective_from date NOT NULL,
    rate_percent numeric(9,6) NOT NULL, UNIQUE (tax_code_id, effective_from));
-- tax matrix (DS-19 tax_matrix.csv)
CREATE TABLE tax_matrix (direction text NOT NULL, partner_tax_group text NOT NULL, item_tax_group text NOT NULL,
    effective_from date NOT NULL, tax_codes text[] NOT NULL);
-- lab stub account (00_stubs.sql): names for reading the trace
ALTER TABLE account ADD COLUMN name_en text, ADD COLUMN name_vi text;
-- account determination rows (DS-19 regimes/tt99/account_determination.csv; ADR-0015, DS-10 DDL pending)
CREATE TABLE account_determination (company_id uuid NOT NULL, transaction_key text NOT NULL, valuation_class text, warehouse text,
    item_group text, partner_group text, tax_code text, currency text, account_code text NOT NULL, basis text);
-- company and regime settings read by the flows (DS-14 settings storage pending)
CREATE TABLE company_setting (company_id uuid NOT NULL, key text NOT NULL, value jsonb NOT NULL, source text NOT NULL,
    PRIMARY KEY (company_id, key));
-- e-invoice records, incoming and outgoing (ADR-0051 rule 20 note names the columns; DS-24 DDL pending)
CREATE TABLE e_invoice_record (id uuid PRIMARY KEY, company_id uuid NOT NULL, direction text NOT NULL CHECK (direction IN ('incoming','outgoing')),
    document_id uuid REFERENCES document (id), state text NOT NULL, seller_tax_id text, seller_name text, invoice_form text, invoice_symbol text,
    invoice_number text, invoice_date date, currency text, stated_rate numeric, order_reference text, net_amount numeric, tax_amount numeric,
    gross_amount numeric, signature_state text CHECK (signature_state IN ('passed','failed','absent')), authority_status text,
    supplier_partner_id uuid, supplier_confirmed_by_user_id uuid, imported_by_user_id uuid, source_attachment_id uuid,
    provider_reference text, recorded_at timestamptz NOT NULL);
CREATE TABLE e_invoice_record_line (e_invoice_record_id uuid NOT NULL REFERENCES e_invoice_record (id), line_number integer NOT NULL,
    seller_item_code text, item_name text, unit_text text, quantity numeric, unit_price numeric, net_amount numeric, tax_rate numeric,
    stated_tax_amount numeric, PRIMARY KEY (e_invoice_record_id, line_number));
-- landed cost document (ADR-0021; DS-21/DS-22 landed cost DDL pending): header keyed by document, lines to stock
CREATE TABLE landed_cost (id uuid PRIMARY KEY REFERENCES document (id), company_id uuid NOT NULL, cost_type text NOT NULL,
    source_document_id uuid NOT NULL REFERENCES document (id), posting_date date NOT NULL, recorded_at timestamptz NOT NULL);
CREATE TABLE landed_cost_line (landed_cost_id uuid NOT NULL REFERENCES landed_cost (id), line_number integer NOT NULL,
    item_id uuid NOT NULL, warehouse_id uuid NOT NULL, purchase_order_line_id uuid, company_amount numeric NOT NULL,
    PRIMARY KEY (landed_cost_id, line_number));

-- ADR-0048's side table open_item_collection (named in ADR-0048 and ADR-0063 rule 27, no DDL yet): the payment hold of a
-- near-duplicate purchase invoice (flow 7)
CREATE TABLE IF NOT EXISTS open_item_collection (open_item_id uuid PRIMARY KEY REFERENCES open_item (id), company_id uuid NOT NULL,
    dunning_level integer NOT NULL DEFAULT 0, last_reminder_date date, is_payment_blocked boolean NOT NULL DEFAULT false,
    is_disputed boolean NOT NULL DEFAULT false, dispute_reason text, recorded_at timestamptz NOT NULL);
