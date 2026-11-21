-- DS-06 universal journal: DDL draft for ADR-0014.
-- PostgreSQL 18. Loaded and trigger-tested in the design lab (docs/reviews/2026-11-14-design-validation). The ADRs win if this file disagrees.
-- Tables live in schema `nativeflows` (ADR-0022 rule 7); domains live in schema `types` (ADR-0006 rule 8).
-- Primary and foreign keys are shown inline; in migrations they get names from the
-- MetaData naming convention (ADR-0004 rule 15).
-- Defined here: the system chart, transaction keys, accounts and applied rates (ADR-0010, ADR-0015, ADR-0011), the journal,
-- open_item, payment_term and payment_term_line (ADR-0026), cost_object and fixed_asset (ADR-0025).
-- Referenced tables defined elsewhere: company, branch, partner, item, warehouse, cost_center, project, business_unit, currency
-- (DS-20-master-data.sql); document (DS-05-platform.sql); fiscal_year, posting_period, posting_period_area_state, close_task
-- and tax_code (DS-05-platform.sql, owners periods and tax); material_document and material_document_line
-- (DS-22-09-42-commercial-inventory.sql). The labs that load this file without DS-05 keep lab stubs for the five DS-05 tables.
-- IDs of journal rows come from context.new_id (ADR-0014 rule 14), so there are no ID defaults.
-- Owner module of each table in brackets on its CREATE TABLE line (ADR-0022 rules 2, 7).
-- recorded_at convention (D13, ADR-0007 rules 9, 16): every table has recorded_at timestamptz NOT NULL DEFAULT now(); a table
-- whose rows are updated in place also gets the trigger trg_<table>_set_recorded_at, BEFORE UPDATE, which runs the shared
-- function set_recorded_at(), so recorded_at is the instant of the last write. Append-only tables need no trigger. The labs
-- load subsets of the design files, so every file that attaches the trigger defines the function itself, with
-- CREATE OR REPLACE, before its first use.
CREATE OR REPLACE FUNCTION set_recorded_at() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    NEW.recorded_at := now();
    RETURN NEW;
END $$;

-- ADR-0027 rules 3 and 5: company, branch, cost_center and project are owned by master_data and defined in
-- DS-20-master-data.sql (ADR-0045); the lab loads both files together. derivation_trace is owned by ledger.
CREATE TABLE derivation_trace (                            -- [ledger] ADR-0027 rule 3
    id            uuid PRIMARY KEY,
    company_id    uuid NOT NULL REFERENCES company (id),
    rule_code     text NOT NULL,
    rule_version  text NOT NULL,
    inputs        jsonb NOT NULL,   -- typed references: {kind, table, id or key, effective_from}
    steps         jsonb NOT NULL,   -- ordered intermediate values as exact decimal or rational strings
    result        jsonb NOT NULL,
    recorded_at   timestamptz NOT NULL,
    command_id    uuid NOT NULL     -- the command request id (ADR-0008)
);
CREATE INDEX ix_derivation_trace_company_id_rule_code ON derivation_trace (company_id, rule_code);

-- ===== System chart of accounts [ledger] (ADR-0010 rules 1-9, 16; catalog docs/catalogs/system-accounts.csv) =====
-- Global catalog, loaded from the catalog file by nativeflows admin migrate (ADR-0022 rule 8): no company_id and no row-level
-- security; application roles get SELECT only. id = uuid5(f244ce09-3c6c-4c82-af14-918bdeca6be3, 'system_account:<code>')
-- (ADR-0006 rule 4; ADR-0010 rule 1); the loader computes it, so there is no ID default. One column per catalog column
-- (ADR-0010 rule 1); the catalog's parent_code becomes parent_id, the parent's uuid5 (ADR-0004 rule 12; ADR-0010 rule 1
-- note). The catalog CI holds the rules that need other rows (rule 16): every parent exists, no cycles, five roots, a child
-- has its parent's type and contra flag, exactly the leaves are postable. From 1.0.0, released rows change only in the
-- wording of name and meaning (rule 9).
CREATE TABLE system_account (                              -- [ledger] ADR-0010 rule 1; global catalog, uuid5 IDs
    id              uuid PRIMARY KEY,
    code            text NOT NULL UNIQUE CONSTRAINT ck_system_account_code CHECK (code ~ '^[a-z][a-z0-9_]*$'),   -- snake_case, never an account number (rule 2)
    parent_id       uuid REFERENCES system_account (id),   -- null for the five roots (rule 3)
    account_type    text NOT NULL CONSTRAINT ck_system_account_account_type CHECK (account_type IN ('asset', 'liability', 'equity', 'income', 'expense')),   -- rule 3
    normal_balance  text NOT NULL CONSTRAINT ck_system_account_normal_balance CHECK (normal_balance IN ('debit', 'credit')),
    is_contra       boolean NOT NULL,
    is_bilateral    boolean NOT NULL,
    control_kind    text NOT NULL CONSTRAINT ck_system_account_control_kind CHECK (control_kind IN (
                        'inventory', 'receivable', 'payable', 'gr_ir', 'cost_object', 'fixed_asset', 'loan', 'none')),   -- rule 5; gated kinds ADR-0025 rules 3-5
    is_postable     boolean NOT NULL,                      -- exactly the leaves (rules 7, 16)
    added_in        text NOT NULL CONSTRAINT ck_system_account_added_in CHECK (added_in ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),   -- catalog version (rule 9)
    name            text NOT NULL,                         -- English source, translated through i18n (rule 1)
    meaning         text NOT NULL,
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    -- Debit for assets and expenses, credit for the others, opposite for contra accounts (rule 4); all 117 rows of 0.1.0 pass.
    CONSTRAINT ck_system_account_normal_balance_rule CHECK (normal_balance = CASE WHEN (account_type IN ('asset', 'expense')) <> is_contra THEN 'debit' ELSE 'credit' END),
    CONSTRAINT ck_system_account_bilateral CHECK (NOT is_bilateral OR control_kind IN ('receivable', 'payable')),   -- rule 6
    CONSTRAINT ck_system_account_control_kind_leaf CHECK (control_kind = 'none' OR is_postable)   -- control kinds only on leaves (rule 16)
);
CREATE TRIGGER trg_system_account_set_recorded_at BEFORE UPDATE ON system_account
    FOR EACH ROW EXECUTE FUNCTION set_recorded_at();

-- ===== Transaction keys [ledger] (ADR-0015 rules 1-4; ADR-0027 rule 11; catalog docs/catalogs/transaction-keys.csv) =====
-- Global catalog loaded like system_account; id = uuid5(..., 'transaction_key:<code>') (ADR-0006 rule 4; ADR-0015 rule 1).
-- One column per catalog column (ADR-0015 rule 1). The catalog CI holds the rules that need other rows (rule 2): every
-- required system account exists, and a key that shares a system account's code requires only that account or its
-- descendants. Codes in required_system_accounts are catalog codes, as movement_type.offset_transaction_key is (DS-22).
CREATE TABLE transaction_key (                             -- [ledger] ADR-0015 rule 1; global catalog, uuid5 IDs
    id                        uuid PRIMARY KEY,
    code                      text NOT NULL UNIQUE CONSTRAINT ck_transaction_key_code CHECK (code ~ '^[a-z][a-z0-9_]*$'),
    name                      text NOT NULL,
    determinants              text[] NOT NULL CONSTRAINT ck_transaction_key_determinants CHECK (
                                  determinants <@ ARRAY['valuation_class', 'warehouse', 'item_group', 'partner_group', 'tax_code', 'currency']::text[]),   -- ordered, most significant first; empty: one account per company (rule 3)
    required_system_accounts  text[] NOT NULL CONSTRAINT ck_transaction_key_required_system_accounts CHECK (cardinality(required_system_accounts) >= 1),   -- leaves or nodes (rule 4)
    required_control_kind     text CONSTRAINT ck_transaction_key_required_control_kind CHECK (required_control_kind IN (
                                  'inventory', 'receivable', 'payable', 'gr_ir', 'cost_object', 'fixed_asset', 'loan', 'none')),   -- null: not checked (rule 4; ADR-0010 rule 13)
    has_regime_alternatives   boolean NOT NULL,            -- ADR-0027 rule 11; ADR-0015 rule 2
    added_in                  text NOT NULL CONSTRAINT ck_transaction_key_added_in CHECK (added_in ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),   -- versioned like the system chart (rule 1)
    meaning                   text NOT NULL,
    recorded_at               timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_transaction_key_set_recorded_at BEFORE UPDATE ON transaction_key
    FOR EACH ROW EXECUTE FUNCTION set_recorded_at();

-- ===== Operational accounts [ledger] (ADR-0010 rules 5, 10-12; ADR-0035 rule 7) =====
-- Company data; row-level security in the last section (ADR-0017 rule 19; ADR-0022 rule 8).
-- Command rules, not held here: CreateAccount and the package CI reject a postable account mapped to an inner node
-- (rule 11), and moving a balance to another account is a document (rule 12). The mapping gives the account its type,
-- normal balance, control kind and flags, so they are not stored here (rule 11).
CREATE TABLE account (                                     -- [ledger] ADR-0010 rule 10
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL REFERENCES company (id),
    code               text NOT NULL,                      -- the company's number, e.g. 1561 (rule 10); data, never an identifier (ADR-0004 rule 5)
    name               text NOT NULL,
    parent_id          uuid,                               -- the operational tree used by statutory reports (rule 10)
    is_postable        boolean NOT NULL,
    system_account_id  uuid REFERENCES system_account (id),   -- exactly for postable accounts (rule 11)
    currency           text REFERENCES currency (code),    -- restricts the account to one transaction currency (rule 10)
    cost_behavior      text CONSTRAINT ck_account_cost_behavior CHECK (cost_behavior IN ('variable', 'fixed')),   -- production cost accounts (rule 5; ADR-0035 rule 7)
    has_posting        boolean NOT NULL DEFAULT false,     -- set by the first journal line, which locks the row (rule 12; journal_line_check_insert)
    is_active          boolean NOT NULL DEFAULT true,
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_id) REFERENCES account (company_id, id),
    CONSTRAINT ck_account_mapping CHECK (is_postable = (system_account_id IS NOT NULL))   -- rule 11
);
-- ADR-0010 rule 12: once has_posting is true, code, system_account_id, is_postable and currency never change. has_posting
-- stays true, since "from then on" the freeze holds. ADR-0017 rule 18 note and ADR-0063 rule 1: the function pins
-- search_path and names its table with the schema. It reads no table.
CREATE FUNCTION nativeflows.account_check_posted_immutable() RETURNS trigger
    LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    IF OLD.has_posting AND (
        NOT NEW.has_posting
        OR NEW.code IS DISTINCT FROM OLD.code
        OR NEW.system_account_id IS DISTINCT FROM OLD.system_account_id
        OR NEW.is_postable IS DISTINCT FROM OLD.is_postable
        OR NEW.currency IS DISTINCT FROM OLD.currency
    ) THEN
        RAISE EXCEPTION 'an account with postings keeps its code, mapping, postable flag and currency (ADR-0010 rule 12)'
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_account_posted_immutable
    BEFORE UPDATE ON nativeflows.account
    FOR EACH ROW EXECUTE FUNCTION nativeflows.account_check_posted_immutable();
CREATE TRIGGER trg_account_set_recorded_at BEFORE UPDATE ON account
    FOR EACH ROW EXECUTE FUNCTION set_recorded_at();

-- ===== Applied rates [ledger] (ADR-0011 rules 3, 9-10, 12; ADR-0048 rule 12) =====
-- One conversion that journal lines used; the lines of one document share it (rule 3). Written at posting (rule 1) and
-- never updated, so it has no recorded_at trigger. Company data; row-level security in the last section.
CREATE TABLE applied_rate (                                -- [ledger] ADR-0011 rule 3
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    from_currency            text NOT NULL REFERENCES currency (code),
    to_currency              text NOT NULL REFERENCES currency (code),
    rate                     types.exchange_rate NOT NULL CONSTRAINT ck_applied_rate_rate CHECK (rate > 0),   -- per unit of from_currency, rounded once by round_exchange_rate (rule 10)
    origin                   text NOT NULL CONSTRAINT ck_applied_rate_origin CHECK (origin IN ('lookup', 'document', 'invoice', 'customs', 'settlement', 'book')),   -- rule 3
    selection_date           date NOT NULL,                -- rule 3
    first_exchange_rate_id   uuid,                         -- the quote used; key to exchange_rate added with DS-10's DDL (rule 9)
    second_exchange_rate_id  uuid,                         -- the second quote of a cross rate (rule 10)
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    CONSTRAINT ck_applied_rate_lookup CHECK (origin <> 'lookup' OR first_exchange_rate_id IS NOT NULL),   -- a lookup records its quotes (rule 10)
    CONSTRAINT ck_applied_rate_cross CHECK (second_exchange_rate_id IS NULL OR first_exchange_rate_id IS NOT NULL)   -- rule 10
);

-- ===== Subledgers, journal and open items (ADR-0014, ADR-0025, ADR-0026) =====

-- ADR-0025 rule 2. cost_object is owned by production (ADR-0032; ADR-0034 rule 15) with kinds per ADR-0035 rule 1;
-- fixed_asset stays a stub owned by ledger until the assets module (Phase 3). Placed after company and cost_center (lab finding L-01).
CREATE TABLE cost_object (                                 -- [production] ADR-0025 rule 2; ADR-0035 rule 1
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    code                 text NOT NULL,
    name                 text NOT NULL,
    kind                 text NOT NULL CONSTRAINT ck_cost_object_kind CHECK (kind IN ('production_order', 'cost_pool')),
    production_order_id  uuid,   -- FK to production_order (ADR-0034), added by DS-43-54-planning-production.sql
    cost_center_id       uuid REFERENCES cost_center (id),
    state                text NOT NULL DEFAULT 'open' CONSTRAINT ck_cost_object_state CHECK (state IN ('open', 'closed')),
    UNIQUE (company_id, code),
    CONSTRAINT uq_cost_object_company_id_id_production_order_id UNIQUE (company_id, id, production_order_id),   -- an order's cost_object_id names the cost object that names it (DS-43-54)
    CONSTRAINT ck_cost_object_kind_reference CHECK ((kind = 'production_order') = (production_order_id IS NOT NULL)
        AND (kind = 'cost_pool') = (cost_center_id IS NOT NULL))
);
CREATE UNIQUE INDEX uq_cost_object_cost_center_id ON cost_object (cost_center_id) WHERE cost_center_id IS NOT NULL;
CREATE UNIQUE INDEX uq_cost_object_production_order_id ON cost_object (production_order_id) WHERE production_order_id IS NOT NULL;
CREATE TABLE fixed_asset (                                 -- [ledger] ADR-0025 rule 2; a stub until the assets module
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    code        text NOT NULL,
    name        text NOT NULL,
    UNIQUE (company_id, code)
);
-- Both are under row-level security (last section; ADR-0022 rule 8).

-- ADR-0025 rule 4: activation of a gated control kind, read by journal_line_check_insert (lab finding L-03).
CREATE TABLE subledger_activation (                        -- [ledger] ADR-0025 rule 4
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL REFERENCES company (id),
    control_kind                   text NOT NULL CONSTRAINT ck_subledger_activation_control_kind CHECK (control_kind IN ('cost_object', 'fixed_asset', 'loan')),
    effective_from                 date NOT NULL,
    reclassification_document_id   uuid NOT NULL REFERENCES document (id),
    recorded_at                    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_subledger_activation_company_id_control_kind UNIQUE (company_id, control_kind)
);
-- Row-level security in the last section; append-only (trigger below, after journal_reject_change).

CREATE TABLE journal_entry (                               -- [ledger] ADR-0014 rule 1
    id                           uuid        PRIMARY KEY,
    company_id                   uuid        NOT NULL REFERENCES company (id),
    document_id                  uuid        NOT NULL REFERENCES document (id),
    posting_date                 date        NOT NULL,
    document_date                date        NOT NULL,
    posting_period_id            uuid        NOT NULL REFERENCES posting_period (id),
    fiscal_year_id               uuid        NOT NULL REFERENCES fiscal_year (id),
    is_closing_entry             boolean     NOT NULL DEFAULT false,
    close_task_id                uuid        REFERENCES close_task (id),
    database_transaction_number  xid8        NOT NULL,
    line_count                   integer     NOT NULL CHECK (line_count >= 2),
    business_unit_trace_id       uuid        REFERENCES derivation_trace (id),   -- ADR-0069 rule 12: the entry's business unit derivation (rule_code business_unit_derivation); journal_line.derivation_trace_id stays costing's
    note                         text CONSTRAINT ck_journal_entry_note CHECK (note IS NULL OR char_length(note) <= 4000),   -- copied from the document's header note at posting (ADR-0074 rule 17)
    recorded_at                  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_journal_entry_document_id UNIQUE (document_id)
);

CREATE INDEX ix_journal_entry_company_id_posting_date
    ON journal_entry (company_id, posting_date);
CREATE INDEX ix_journal_entry_posting_period_id_close_task_id
    ON journal_entry (posting_period_id, close_task_id);


-- ADR-0026: open-item core, owned by ledger. Row-level security in the last section.
CREATE TABLE payment_term (                                -- [ledger] ADR-0026 rule 5
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    code        text NOT NULL,
    name        text NOT NULL,
    is_active   boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code)
);
CREATE TABLE payment_term_line (                           -- [ledger] ADR-0026 rule 5
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL REFERENCES company (id),
    payment_term_id  uuid NOT NULL REFERENCES payment_term (id),
    line_number      integer NOT NULL,
    amount_percent   types.percent NOT NULL,
    due_days         integer NOT NULL,
    due_date_base    text NOT NULL CONSTRAINT ck_payment_term_line_due_date_base CHECK (due_date_base IN ('document_date', 'end_of_month')),
    discount_percent types.percent,
    discount_days    integer,
    UNIQUE (payment_term_id, line_number)
);
CREATE TABLE open_item (                                   -- [ledger] ADR-0026 rule 1
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL REFERENCES company (id),
    partner_id                  uuid NOT NULL REFERENCES partner (id),
    account_id                  uuid NOT NULL REFERENCES account (id),
    open_item_kind              text NOT NULL CONSTRAINT ck_open_item_open_item_kind CHECK (open_item_kind IN ('invoice', 'credit', 'advance', 'payment_on_account', 'loan', 'other')),
    natural_side                text NOT NULL CONSTRAINT ck_open_item_natural_side CHECK (natural_side IN ('debit', 'credit')),
    transaction_currency        text NOT NULL REFERENCES currency (code),
    origin_document_id          uuid NOT NULL REFERENCES document (id),
    origin_journal_line_id      uuid NOT NULL UNIQUE,   -- FK below, deferred: the item is inserted before its line
    installment_number          integer NOT NULL DEFAULT 1,
    payment_term_id             uuid REFERENCES payment_term (id),
    document_date               date NOT NULL,
    posting_date                date NOT NULL,
    original_posting_date       date NOT NULL,          -- the posting date, or the old system's date for opening items (ADR-0026 rule 1; ADR-0044 rule 8; ADR-0048 rule 18)
    due_date                    date,
    discount_due_date           date,
    discount_percent            types.percent,
    reference                   text,
    partner_reference           text,
    original_transaction_amount types.amount NOT NULL,
    original_company_amount     types.amount NOT NULL,
    original_group_amount       types.amount,
    open_transaction_amount     types.amount NOT NULL,
    open_company_amount         types.amount NOT NULL,
    open_group_amount           types.amount,
    revaluation_company_amount  types.amount NOT NULL DEFAULT 0,
    revaluation_group_amount    types.amount,
    is_settled                  boolean NOT NULL DEFAULT false,
    is_reversed                 boolean NOT NULL DEFAULT false,
    last_settlement_date        date,
    predecessor_open_item_id    uuid REFERENCES open_item (id),
    CONSTRAINT ck_open_item_due_date CHECK ((open_item_kind IN ('invoice', 'credit') AND due_date IS NOT NULL)
                                           OR (open_item_kind IN ('advance', 'payment_on_account', 'loan') AND due_date IS NULL)
                                           OR open_item_kind = 'other'),
    -- Amounts are signed like journal amounts (debit positive); comparisons use magnitudes (ADR-0026 rule 1 note).
    CONSTRAINT ck_open_item_original_transaction_amount CHECK (sign(original_transaction_amount) = CASE natural_side WHEN 'debit' THEN 1 ELSE -1 END),
    CONSTRAINT ck_open_item_is_settled CHECK (NOT is_settled OR (open_transaction_amount = 0 AND open_company_amount = 0 AND coalesce(open_group_amount, 0) = 0))
);
CREATE INDEX ix_open_item_company_id_partner_id ON open_item (company_id, partner_id) WHERE NOT is_settled AND NOT is_reversed;
CREATE INDEX ix_open_item_company_id_account_id ON open_item (company_id, account_id) WHERE NOT is_settled AND NOT is_reversed;
CREATE INDEX ix_open_item_company_id_due_date ON open_item (company_id, due_date) WHERE NOT is_settled AND NOT is_reversed;
CREATE INDEX ix_open_item_origin_document_id ON open_item (origin_document_id);

CREATE TABLE journal_line (                                -- [ledger] ADR-0014 rule 5
    id                         uuid          PRIMARY KEY,
    journal_entry_id           uuid          NOT NULL REFERENCES journal_entry (id),
    company_id                 uuid          NOT NULL REFERENCES company (id),
    line_number                integer       NOT NULL,
    posting_period_id          uuid          NOT NULL REFERENCES posting_period (id),
    posting_date               date          NOT NULL,     -- copied from the entry at insert (ADR-0014 rule 5 note, 2026-11-21; INV-99)
    fiscal_year_id             uuid          NOT NULL REFERENCES fiscal_year (id),   -- copied from the entry at insert (as posting_date)
    account_id                 uuid          NOT NULL REFERENCES account (id),
    system_account_id          uuid          NOT NULL REFERENCES system_account (id),
    transaction_key_id         uuid          REFERENCES transaction_key (id),
    side                       text          NOT NULL,
    is_storno                  boolean       NOT NULL DEFAULT false,
    transaction_currency       text          NOT NULL REFERENCES currency (code),
    transaction_amount         types.amount  NOT NULL,
    company_currency           text          NOT NULL REFERENCES currency (code),
    company_amount             types.amount  NOT NULL,
    group_currency             text          REFERENCES currency (code),
    group_amount               types.amount,
    company_applied_rate_id    uuid          REFERENCES applied_rate (id),
    group_applied_rate_id      uuid          REFERENCES applied_rate (id),
    branch_id                  uuid          REFERENCES branch (id),
    partner_id                 uuid          REFERENCES partner (id),
    item_id                    uuid          REFERENCES item (id),
    warehouse_id               uuid          REFERENCES warehouse (id),
    cost_center_id             uuid          REFERENCES cost_center (id),
    project_id                 uuid          REFERENCES project (id),
    cost_object_id             uuid          REFERENCES cost_object (id),   -- ADR-0025; production orders and pools (ADR-0035), Phase 1
    fixed_asset_id             uuid          REFERENCES fixed_asset (id),   -- ADR-0025, empty until Phase 3
    salesperson_id             uuid          REFERENCES partner (id),   -- partner with the employee role (ADR-0027 rule 6)
    tax_code_id                uuid          REFERENCES tax_code (id),
    material_document_line_id  uuid          REFERENCES material_document_line (id),
    open_item_id               uuid          REFERENCES open_item (id),
    purchase_order_line_id     uuid,         -- ADR-0030 rule 3: GR/IR per order line; FK to purchase_order_line added at step 5
    evidence_method            text          CONSTRAINT ck_journal_line_evidence_method CHECK (evidence_method IS NULL OR (open_item_id IS NOT NULL AND evidence_method IN ('cash', 'bank_transfer', 'card', 'offset', 'third_party', 'none'))),   -- lines of ADR-0048 rule 18; how a settlement was paid, in any regime (ADR-0053 rule 11)
    derivation_trace_id        uuid          REFERENCES derivation_trace (id),
    business_unit_id           uuid,         -- ADR-0069 rule 4; composite key to business_unit below (the unit is of the line's company); profit-and-loss lines only in Phase 1 (rule 5, posting logic)
    business_unit_source       text          CONSTRAINT ck_journal_line_business_unit_source CHECK (business_unit_source IN ('line', 'item', 'cost_center', 'project', 'document', 'site', 'company_default', 'reversal', 'closing')),   -- the derivation step that set it (ADR-0069 rules 9, 11)
    description                text,
    recorded_at                timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT uq_journal_line_journal_entry_id_line_number UNIQUE (journal_entry_id, line_number),
    CONSTRAINT ck_journal_line_line_number_positive CHECK (line_number > 0),
    CONSTRAINT ck_journal_line_side CHECK (side IN ('debit', 'credit')),
    CONSTRAINT ck_journal_line_group_pair CHECK ((group_currency IS NULL) = (group_amount IS NULL)),
    CONSTRAINT ck_journal_line_business_unit_pair CHECK ((business_unit_id IS NULL) = (business_unit_source IS NULL)),
    FOREIGN KEY (company_id, business_unit_id) REFERENCES business_unit (company_id, id),
    CONSTRAINT ck_journal_line_not_all_zero
        CHECK (transaction_amount <> 0 OR company_amount <> 0 OR COALESCE(group_amount, 0) <> 0),
    -- Rule 6: transaction and company amounts never have opposite signs.
    CONSTRAINT ck_journal_line_same_sign
        CHECK (transaction_amount = 0 OR company_amount = 0
               OR sign(transaction_amount) = sign(company_amount))
);

CREATE INDEX ix_journal_line_company_id_account_id_posting_period_id
    ON journal_line (company_id, account_id, posting_period_id);
CREATE INDEX ix_journal_line_company_id_system_account_id_posting_period_id
    ON journal_line (company_id, system_account_id, posting_period_id);
CREATE INDEX ix_journal_line_company_id_partner_id
    ON journal_line (company_id, partner_id) WHERE partner_id IS NOT NULL;
CREATE INDEX ix_journal_line_open_item_id
    ON journal_line (open_item_id) WHERE open_item_id IS NOT NULL;
CREATE INDEX ix_journal_line_material_document_line_id
    ON journal_line (material_document_line_id) WHERE material_document_line_id IS NOT NULL;
CREATE INDEX ix_journal_line_purchase_order_line_id
    ON journal_line (purchase_order_line_id) WHERE purchase_order_line_id IS NOT NULL;
-- ADR-0069 rule 4: profit and loss per business unit.
CREATE INDEX ix_journal_line_company_id_business_unit_id_posting_period_id
    ON journal_line (company_id, business_unit_id, posting_period_id) WHERE business_unit_id IS NOT NULL;

-- Rule 13: append-only.
CREATE FUNCTION journal_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'journal rows are append-only (ADR-0014 rule 13)'
        USING ERRCODE = 'restrict_violation';
END $$;

CREATE TRIGGER trg_journal_entry_append_only
    BEFORE UPDATE OR DELETE ON journal_entry
    FOR EACH ROW EXECUTE FUNCTION journal_reject_change();
CREATE TRIGGER trg_journal_entry_no_truncate
    BEFORE TRUNCATE ON journal_entry
    FOR EACH STATEMENT EXECUTE FUNCTION journal_reject_change();
CREATE TRIGGER trg_journal_line_append_only
    BEFORE UPDATE OR DELETE ON journal_line
    FOR EACH ROW EXECUTE FUNCTION journal_reject_change();
CREATE TRIGGER trg_subledger_activation_append_only
    BEFORE UPDATE OR DELETE ON subledger_activation
    FOR EACH ROW EXECUTE FUNCTION journal_reject_change();
CREATE TRIGGER trg_journal_line_no_truncate
    BEFORE TRUNCATE ON journal_line
    FOR EACH STATEMENT EXECUTE FUNCTION journal_reject_change();

-- Rule 1: the creating transaction is set by the database, never by a client.
CREATE FUNCTION journal_entry_set_transaction() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.database_transaction_number := pg_current_xact_id();
    RETURN NEW;
END $$;

CREATE TRIGGER trg_journal_entry_set_transaction
    BEFORE INSERT ON journal_entry
    FOR EACH ROW EXECUTE FUNCTION journal_entry_set_transaction();

-- Rule 12: checks on every line insert.
-- ADR-0069 rules 5 and 14 (a business unit on profit-and-loss lines only; ledger.business_unit.required_on_profit_and_loss)
-- are posting logic, not this trigger, like the control-account setting.
CREATE FUNCTION journal_line_check_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_entry          journal_entry%ROWTYPE;
    v_account        account%ROWTYPE;
    v_control_kind   text;
    v_period_kind    text;
    v_area           text;
    v_state          text;
    v_company_ccy    text;
    v_has_material   boolean;
    v_sign           int;
    v_activation     subledger_activation%ROWTYPE;
BEGIN
    -- ADR-0010 rule 12: mark the account first; this locks its row and freezes its mapping. recorded_at is the last write (D8).
    UPDATE account SET has_posting = true, recorded_at = now() WHERE id = NEW.account_id AND NOT has_posting;

    SELECT * INTO v_entry FROM journal_entry WHERE id = NEW.journal_entry_id;
    IF v_entry.database_transaction_number IS DISTINCT FROM pg_current_xact_id() THEN
        RAISE EXCEPTION 'a posted journal entry cannot gain lines (ADR-0014 rule 12)'
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.company_id IS DISTINCT FROM v_entry.company_id
       OR NEW.posting_period_id IS DISTINCT FROM v_entry.posting_period_id THEN
        RAISE EXCEPTION 'line company or period differs from its entry (ADR-0014 rule 12)'
            USING ERRCODE = 'check_violation';
    END IF;
    -- ADR-0014 rule 5 note (2026-11-21); INV-99: the line's posting date and fiscal year are its entry's.
    IF NEW.posting_date IS DISTINCT FROM v_entry.posting_date
       OR NEW.fiscal_year_id IS DISTINCT FROM v_entry.fiscal_year_id THEN
        RAISE EXCEPTION 'line posting date or fiscal year differs from its entry (ADR-0014 rule 5; INV-99)'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.line_number > v_entry.line_count THEN
        RAISE EXCEPTION 'line number above the entry''s line count (ADR-0014 rule 12)'
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT * INTO v_account FROM account WHERE id = NEW.account_id;
    IF NOT v_account.is_postable OR v_account.company_id <> NEW.company_id
       OR NEW.system_account_id IS DISTINCT FROM v_account.system_account_id THEN
        RAISE EXCEPTION 'account is not postable here or system account differs (ADR-0014 rule 12)'
            USING ERRCODE = 'check_violation';
    END IF;
    IF v_account.currency IS NOT NULL AND v_account.currency <> NEW.transaction_currency THEN
        RAISE EXCEPTION 'account accepts only %, not % (ADR-0014 rule 10)',
            v_account.currency, NEW.transaction_currency USING ERRCODE = 'check_violation';
    END IF;
    SELECT company_currency INTO v_company_ccy FROM company WHERE id = NEW.company_id;
    IF NEW.company_currency <> v_company_ccy THEN
        RAISE EXCEPTION 'company currency must be % (ADR-0014 rule 10)', v_company_ccy
            USING ERRCODE = 'check_violation';
    END IF;

    -- Rule 6: sign follows side, opposite for storno lines; rule 7 lets the group
    -- amount of an adjustment line (transaction amount 0) differ.
    v_sign := CASE WHEN NEW.side = 'debit' THEN 1 ELSE -1 END;
    IF NEW.is_storno THEN v_sign := -v_sign; END IF;
    IF (NEW.transaction_amount <> 0 AND sign(NEW.transaction_amount) <> v_sign)
       OR (NEW.company_amount <> 0 AND sign(NEW.company_amount) <> v_sign)
       OR (NEW.transaction_amount <> 0 AND COALESCE(NEW.group_amount, 0) <> 0
           AND sign(NEW.group_amount) <> v_sign)
       OR (NEW.transaction_amount = 0 AND NEW.company_amount = 0
           AND sign(NEW.group_amount) <> v_sign) THEN
        RAISE EXCEPTION 'amount signs do not match side and storno flag (ADR-0014 rules 6-7)'
            USING ERRCODE = 'check_violation';
    END IF;

    -- Rule 10: required columns by control kind.
    SELECT control_kind INTO v_control_kind FROM system_account WHERE id = NEW.system_account_id;
    IF v_control_kind IN ('receivable', 'payable')
       AND (NEW.partner_id IS NULL OR NEW.open_item_id IS NULL) THEN
        RAISE EXCEPTION '% lines need partner and open item (ADR-0014 rule 10)', v_control_kind
            USING ERRCODE = 'check_violation';
    END IF;
    IF v_control_kind = 'inventory' THEN
        IF NEW.item_id IS NULL OR NEW.warehouse_id IS NULL THEN
            RAISE EXCEPTION 'inventory lines need item and warehouse (ADR-0014 rule 10)'
                USING ERRCODE = 'check_violation';
        END IF;
        SELECT EXISTS (SELECT 1 FROM material_document md WHERE md.document_id = v_entry.document_id)
          INTO v_has_material;
        IF v_has_material AND NEW.material_document_line_id IS NULL THEN
            RAISE EXCEPTION 'inventory line needs its material document line (ADR-0014 rule 10)'
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    -- The flagged rule on manual entries to control accounts is enforced by the posting logic.

    -- Rule 12: the area state of the period, read under a share lock.
    SELECT kind INTO v_period_kind FROM posting_period WHERE id = NEW.posting_period_id;
    v_area := CASE
        WHEN v_period_kind = 'special' THEN 'general'
        WHEN v_control_kind IN ('inventory', 'receivable', 'payable') THEN v_control_kind
        WHEN v_control_kind = 'cost_object' THEN 'inventory'   -- ADR-0035 rule 3: production cost is inventory valuation
        ELSE 'general' END;
    SELECT state INTO v_state
      FROM posting_period_area_state
     WHERE posting_period_id = NEW.posting_period_id AND area = v_area
       FOR SHARE;
    IF v_state IS NULL OR v_state = 'locked' THEN
        RAISE EXCEPTION 'posting period is locked or has no state in area % (ADR-0012 rule 5)', v_area
            USING ERRCODE = 'restrict_violation';
    END IF;

    -- ADR-0025 rule 4: read after the FOR SHARE area-state lock, which ActivateSubledger takes exclusively
    -- for periods from effective_from (lab finding L-07). Gated kinds are enforced only from their activation; the reclassification document's
    -- undimensioned lines are the single exception (lab finding L-03).
    IF v_control_kind IN ('cost_object', 'fixed_asset', 'loan') THEN
        SELECT * INTO v_activation FROM subledger_activation
         WHERE company_id = NEW.company_id AND control_kind = v_control_kind;
        IF FOUND AND v_entry.document_id IS DISTINCT FROM v_activation.reclassification_document_id THEN
            IF v_entry.posting_date < v_activation.effective_from THEN
                RAISE EXCEPTION 'subledger_activation_date_not_reached: % is active from % (ADR-0025 rule 4)',
                    v_control_kind, v_activation.effective_from USING ERRCODE = 'check_violation';
            END IF;
            IF (v_control_kind = 'cost_object' AND NEW.cost_object_id IS NULL)
               OR (v_control_kind = 'fixed_asset' AND NEW.fixed_asset_id IS NULL)
               OR (v_control_kind = 'loan' AND (NEW.partner_id IS NULL OR NEW.open_item_id IS NULL)) THEN
                RAISE EXCEPTION 'control_dimension_missing: % lines need their dimension (ADR-0025 rule 4)', v_control_kind
                    USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    END IF;
    IF NEW.cost_object_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM cost_object WHERE id = NEW.cost_object_id AND company_id = NEW.company_id) THEN
        RAISE EXCEPTION 'cost object of another company (ADR-0025 rule 1)' USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END $$;

CREATE TRIGGER trg_journal_line_check_insert
    BEFORE INSERT ON journal_line
    FOR EACH ROW EXECUTE FUNCTION journal_line_check_insert();

-- Rule 11: once per entry, at commit or at SET CONSTRAINTS ALL IMMEDIATE.
CREATE FUNCTION journal_entry_check_balance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_lines         int;
    v_group_nulls   int;
BEGIN
    SELECT count(*), count(*) FILTER (WHERE group_amount IS NULL)
      INTO v_lines, v_group_nulls
      FROM journal_line WHERE journal_entry_id = NEW.id;
    IF v_lines < 2 OR v_lines <> NEW.line_count THEN
        RAISE EXCEPTION 'journal entry % has % lines, expected % (ADR-0014 rule 11)', NEW.id, v_lines, NEW.line_count
            USING ERRCODE = 'check_violation';
    END IF;
    IF v_group_nulls NOT IN (0, v_lines) THEN
        RAISE EXCEPTION 'journal entry % mixes lines with and without group amounts', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (
        SELECT 1 FROM journal_line WHERE journal_entry_id = NEW.id
         GROUP BY transaction_currency HAVING SUM(transaction_amount) <> 0
    ) OR EXISTS (
        SELECT 1 FROM journal_line WHERE journal_entry_id = NEW.id
        HAVING SUM(company_amount) <> 0 OR COALESCE(SUM(group_amount), 0) <> 0
    ) THEN
        RAISE EXCEPTION 'journal entry % does not balance (ADR-0014 rule 11)', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_journal_entry_balance
    AFTER INSERT ON journal_entry
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION journal_entry_check_balance();

-- Rule 18: period balance cache, written when a period's general area is locked.
CREATE TABLE account_period_balance (                      -- [ledger] ADR-0014 rule 18
    id                           uuid          PRIMARY KEY,
    company_id                   uuid          NOT NULL REFERENCES company (id),
    account_id                   uuid          NOT NULL REFERENCES account (id),
    posting_period_id            uuid          NOT NULL REFERENCES posting_period (id),
    transaction_currency         text          NOT NULL REFERENCES currency (code),
    is_closing_entry             boolean       NOT NULL,
    transaction_debit_turnover   types.amount  NOT NULL,
    transaction_credit_turnover  types.amount  NOT NULL,
    transaction_closing_balance  types.amount  NOT NULL,
    company_debit_turnover       types.amount  NOT NULL,
    company_credit_turnover      types.amount  NOT NULL,
    company_closing_balance      types.amount  NOT NULL,
    group_debit_turnover         types.amount,
    group_credit_turnover        types.amount,
    group_closing_balance        types.amount,
    recorded_at                  timestamptz   NOT NULL DEFAULT now(),
    -- Named by hand: the convention name would exceed 63 bytes (ADR-0004 rule 6).
    CONSTRAINT uq_account_period_balance_key
        UNIQUE (company_id, account_id, posting_period_id, transaction_currency, is_closing_entry)
);

-- ADR-0044 rule 10; ADR-0049 rule 14: year-to-date turnover before a mid-year cut-over, non-posting, read by statutory
-- reports. Owned by ledger, written by CreateOpeningTurnover in the migration's batches, unchanged after
-- CompleteMigration. Dates instead of a fiscal year: the first fiscal year after a mid-year cut-over is short.
-- Row-level security in the last section.
CREATE TABLE opening_turnover (                            -- [ledger] ADR-0044 rule 10
    id                       uuid          PRIMARY KEY,
    company_id               uuid          NOT NULL REFERENCES company (id),
    account_id               uuid          NOT NULL REFERENCES account (id),
    start_date               date          NOT NULL,
    end_date                 date          NOT NULL,      -- the migration's opening_date
    company_debit_turnover   types.amount  NOT NULL,
    company_credit_turnover  types.amount  NOT NULL,
    recorded_at              timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT uq_opening_turnover_company_id_account_id_start_date UNIQUE (company_id, account_id, start_date),
    CONSTRAINT ck_opening_turnover_dates CHECK (start_date <= end_date)
);

-- ADR-0026 rule 3: the cycle open_item <-> journal_line is closed by a deferred foreign key.
ALTER TABLE open_item ADD CONSTRAINT fk_open_item_origin_journal_line_id_journal_line
    FOREIGN KEY (origin_journal_line_id) REFERENCES journal_line (id) DEFERRABLE INITIALLY DEFERRED;

-- ADR-0026 rules 1 and 4: identity of an open item is immutable; a referring line matches its item.
CREATE FUNCTION open_item_identity_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.company_id, NEW.partner_id, NEW.account_id, NEW.open_item_kind, NEW.natural_side,
        NEW.transaction_currency, NEW.origin_document_id, NEW.origin_journal_line_id)
       IS DISTINCT FROM
       (OLD.company_id, OLD.partner_id, OLD.account_id, OLD.open_item_kind, OLD.natural_side,
        OLD.transaction_currency, OLD.origin_document_id, OLD.origin_journal_line_id) THEN
        RAISE EXCEPTION 'open item identity is immutable (ADR-0026 rule 1)' USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_open_item_identity_immutable
    BEFORE UPDATE ON open_item FOR EACH ROW EXECUTE FUNCTION open_item_identity_immutable();

CREATE FUNCTION journal_line_check_open_item() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v open_item%ROWTYPE;
BEGIN
    IF NEW.open_item_id IS NOT NULL THEN
        SELECT * INTO v FROM open_item WHERE id = NEW.open_item_id;
        IF v.company_id <> NEW.company_id OR v.partner_id IS DISTINCT FROM NEW.partner_id
           OR v.account_id <> NEW.account_id OR v.transaction_currency <> NEW.transaction_currency THEN
            RAISE EXCEPTION 'line does not match its open item (ADR-0026 rule 4)' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_journal_line_check_open_item
    BEFORE INSERT ON journal_line FOR EACH ROW EXECUTE FUNCTION journal_line_check_open_item();

-- ===== Row-level security (ADR-0017 rule 19; ADR-0022 rule 8; D9) =====
-- rls_v1 as in DS-05-platform.sql: the company policy, compared as text and failing closed, and the read-only company_ids
-- policy for registered cross-company queries. Every company table of this file is listed; system_account and
-- transaction_key are global catalogs without company_id.
DO $$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'derivation_trace', 'account', 'applied_rate', 'cost_object', 'fixed_asset', 'subledger_activation', 'journal_entry',
        'payment_term', 'payment_term_line', 'open_item', 'journal_line', 'account_period_balance', 'opening_turnover'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', v_table);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', v_table);
        EXECUTE format('CREATE POLICY company_policy ON %I USING (company_id::text = current_setting(''nativeflows.company_id'', true))', v_table);
        EXECUTE format('CREATE POLICY company_ids_policy ON %I FOR SELECT USING (company_id::text = ANY (string_to_array(current_setting(''nativeflows.company_ids'', true), '','')))', v_table);
    END LOOP;
END
$$;
