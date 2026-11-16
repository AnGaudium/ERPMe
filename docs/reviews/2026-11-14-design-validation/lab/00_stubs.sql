-- Lab only: minimal stubs for tables DS-06 references but other design items define.
DROP SCHEMA IF EXISTS nativeflows CASCADE; DROP SCHEMA IF EXISTS types CASCADE;
CREATE SCHEMA types; CREATE SCHEMA nativeflows;
SET search_path = nativeflows;
CREATE EXTENSION IF NOT EXISTS btree_gist;             -- installed in production (ADR-0022 rule 8)
CREATE DOMAIN types.amount AS numeric(24,4);
CREATE DOMAIN types.quantity AS numeric(24,6);
CREATE DOMAIN types.unit_price AS numeric(28,10);
CREATE DOMAIN types.exchange_rate AS numeric(30,15);
CREATE DOMAIN types.percent AS numeric(9,6);
CREATE TABLE user_account (id uuid PRIMARY KEY);
CREATE TABLE system_account (id uuid PRIMARY KEY, code text UNIQUE NOT NULL, control_kind text NOT NULL DEFAULT 'none');
CREATE TABLE account (id uuid PRIMARY KEY, company_id uuid NOT NULL, code text NOT NULL, system_account_id uuid NOT NULL REFERENCES system_account(id),
  is_postable boolean NOT NULL DEFAULT true, currency text, has_posting boolean NOT NULL DEFAULT false);
CREATE TABLE fiscal_year (id uuid PRIMARY KEY, company_id uuid NOT NULL);
CREATE TABLE posting_period (id uuid PRIMARY KEY, company_id uuid NOT NULL, fiscal_year_id uuid, kind text NOT NULL DEFAULT 'regular', start_date date, end_date date);
CREATE TABLE posting_period_area_state (posting_period_id uuid NOT NULL REFERENCES posting_period(id), area text NOT NULL, state text NOT NULL, PRIMARY KEY (posting_period_id, area));
CREATE TABLE document (id uuid PRIMARY KEY, company_id uuid NOT NULL, document_type text NOT NULL, state text NOT NULL DEFAULT 'draft');
CREATE TABLE material_document (id uuid PRIMARY KEY, document_id uuid NOT NULL UNIQUE REFERENCES document(id));
CREATE TABLE material_document_line (id uuid PRIMARY KEY, material_document_id uuid NOT NULL REFERENCES material_document(id));
CREATE TABLE applied_rate (id uuid PRIMARY KEY);
CREATE TABLE close_task (id uuid PRIMARY KEY);
CREATE TABLE tax_code (id uuid PRIMARY KEY);
CREATE TABLE transaction_key (id uuid PRIMARY KEY, code text);
