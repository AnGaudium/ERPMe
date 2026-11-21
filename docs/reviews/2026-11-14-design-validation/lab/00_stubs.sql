-- Lab only: minimal stubs for tables DS-06 references but other design items define.
-- load_all.py skips every stub a design file defines, so only the labs that load DS-06 without DS-05, DS-15 or DS-22 use
-- them. The five DS-05 stubs at the end mirror the design columns of DS-05-platform.sql (names, types, NOT NULL and
-- defaults; no checks, no foreign keys to tables loaded after the stubs); t15_platform_ddl.py check A02b compares them.
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
-- document keeps UNIQUE (company_id, id), the target of the company keys of DS-06 (S2 schema review S4).
CREATE TABLE document (id uuid PRIMARY KEY, company_id uuid NOT NULL, document_type text NOT NULL, state text NOT NULL DEFAULT 'draft',
  UNIQUE (company_id, id));
CREATE TABLE material_document (id uuid PRIMARY KEY, document_id uuid NOT NULL UNIQUE REFERENCES document(id));
CREATE TABLE material_document_line (id uuid PRIMARY KEY, material_document_id uuid NOT NULL REFERENCES material_document(id));
CREATE TABLE fiscal_year (id uuid PRIMARY KEY, company_id uuid NOT NULL, code text NOT NULL, start_date date NOT NULL, end_date date NOT NULL,
  is_migration boolean NOT NULL DEFAULT false, recorded_at timestamptz NOT NULL DEFAULT now(), UNIQUE (company_id, code), UNIQUE (company_id, id));
CREATE TABLE posting_period (id uuid PRIMARY KEY, company_id uuid NOT NULL, fiscal_year_id uuid NOT NULL, number integer NOT NULL, kind text NOT NULL,
  start_date date NOT NULL, end_date date NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(), UNIQUE (company_id, id), UNIQUE (fiscal_year_id, number),
  UNIQUE (company_id, fiscal_year_id, id), FOREIGN KEY (company_id, fiscal_year_id) REFERENCES fiscal_year (company_id, id));
CREATE TABLE posting_period_area_state (id uuid PRIMARY KEY, company_id uuid NOT NULL, posting_period_id uuid NOT NULL, area text NOT NULL, state text NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(), UNIQUE (posting_period_id, area), FOREIGN KEY (company_id, posting_period_id) REFERENCES posting_period (company_id, id));
CREATE TABLE close_task (id uuid PRIMARY KEY, company_id uuid NOT NULL, posting_period_id uuid NOT NULL, code text NOT NULL, area text NOT NULL, kind text NOT NULL,
  is_required boolean NOT NULL, is_sequential boolean NOT NULL, depends_on text[] NOT NULL DEFAULT '{}', parameters jsonb NOT NULL DEFAULT '{}',
  state text NOT NULL DEFAULT 'pending', entry_count_at_done bigint, actor_kind text, actor_id uuid, on_behalf_of_id uuid, completed_at timestamptz,
  evidence jsonb, recorded_at timestamptz NOT NULL DEFAULT now(), UNIQUE (company_id, id), UNIQUE (posting_period_id, code));
CREATE TABLE tax_code (id uuid PRIMARY KEY, localization_package text NOT NULL, code text NOT NULL, name text NOT NULL, tax_kind text NOT NULL, package_kind text,
  direction text NOT NULL, calculation text NOT NULL, sequence integer NOT NULL, base_includes text[] NOT NULL DEFAULT '{}', transaction_key_id uuid NOT NULL,
  deductibility text, fixed_asset_code text, import_treatment text, basis jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (localization_package, code));
