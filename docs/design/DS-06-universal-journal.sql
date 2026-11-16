-- DS-06 universal journal: DDL draft for ADR-0014.
-- PostgreSQL 18. Loaded and trigger-tested in the design lab (docs/reviews/2026-11-14-design-validation). The ADRs win if this file disagrees.
-- Tables live in schema `nativeflows` (ADR-0022 rule 7); domains live in schema `types` (ADR-0006 rule 8).
-- Primary and foreign keys are shown inline; in migrations they get names from the
-- MetaData naming convention (ADR-0004 rule 15).
-- Referenced tables (document, account, system_account, posting_period, fiscal_year,
-- applied_rate, transaction_key, partner, item, warehouse (DS-20-master-data.sql),
-- tax_code, open_item, payment_term and payment_term_line (below, ADR-0026), cost_object and fixed_asset (stubs below, ADR-0025), material_document, material_document_line,
-- close_task, posting_period_area_state, currency) are defined by their own design items.
-- IDs of journal rows come from context.new_id (ADR-0014 rule 14), so there are no ID defaults.

-- ADR-0027 rules 3 and 5: company, branch, cost_center and project are owned by master_data and defined in
-- DS-20-master-data.sql (ADR-0045); the lab loads both files together. derivation_trace is owned by ledger.
CREATE TABLE derivation_trace (
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

-- ADR-0025 rule 2. cost_object is owned by production (ADR-0032; ADR-0034 rule 15) with kinds per ADR-0035 rule 1;
-- fixed_asset stays a stub owned by ledger until the assets module (Phase 3). Placed after company and cost_center (lab finding L-01).
CREATE TABLE cost_object (
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
CREATE TABLE fixed_asset (
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    code        text NOT NULL,
    name        text NOT NULL,
    UNIQUE (company_id, code)
);
-- Both get FORCE ROW LEVEL SECURITY and the generated company policy (ADR-0022 rule 8).

-- ADR-0025 rule 4: activation of a gated control kind, read by journal_line_check_insert (lab finding L-03).
CREATE TABLE subledger_activation (
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL REFERENCES company (id),
    control_kind                   text NOT NULL CONSTRAINT ck_subledger_activation_control_kind CHECK (control_kind IN ('cost_object', 'fixed_asset', 'loan')),
    effective_from                 date NOT NULL,
    reclassification_document_id   uuid NOT NULL REFERENCES document (id),
    recorded_at                    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_subledger_activation_company_id_control_kind UNIQUE (company_id, control_kind)
);
-- FORCE ROW LEVEL SECURITY and the generated company policy; append-only (trigger below, after journal_reject_change).

CREATE TABLE journal_entry (
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
    recorded_at                  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_journal_entry_document_id UNIQUE (document_id)
);

CREATE INDEX ix_journal_entry_company_id_posting_date
    ON journal_entry (company_id, posting_date);
CREATE INDEX ix_journal_entry_posting_period_id_close_task_id
    ON journal_entry (posting_period_id, close_task_id);


-- ADR-0026: open-item core, owned by ledger. RLS: FORCE ROW LEVEL SECURITY and the generated company policy.
CREATE TABLE payment_term (
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    code        text NOT NULL,
    name        text NOT NULL,
    is_active   boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code)
);
CREATE TABLE payment_term_line (
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
CREATE TABLE open_item (
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

CREATE TABLE journal_line (
    id                         uuid          PRIMARY KEY,
    journal_entry_id           uuid          NOT NULL REFERENCES journal_entry (id),
    company_id                 uuid          NOT NULL REFERENCES company (id),
    line_number                integer       NOT NULL,
    posting_period_id          uuid          NOT NULL REFERENCES posting_period (id),
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
    description                text,
    recorded_at                timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT uq_journal_line_journal_entry_id_line_number UNIQUE (journal_entry_id, line_number),
    CONSTRAINT ck_journal_line_line_number_positive CHECK (line_number > 0),
    CONSTRAINT ck_journal_line_side CHECK (side IN ('debit', 'credit')),
    CONSTRAINT ck_journal_line_group_pair CHECK ((group_currency IS NULL) = (group_amount IS NULL)),
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
    -- ADR-0010 rule 12: mark the account first; this locks its row and freezes its mapping.
    UPDATE account SET has_posting = true WHERE id = NEW.account_id AND NOT has_posting;

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
CREATE TABLE account_period_balance (
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
-- FORCE ROW LEVEL SECURITY and the generated company policy.
CREATE TABLE opening_turnover (
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
