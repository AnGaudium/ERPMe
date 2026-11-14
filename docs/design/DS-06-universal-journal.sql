-- DS-06 universal journal: DDL draft for ADR-0014.
-- PostgreSQL 18. Draft for review; not yet executed. The ADR's rules win if this file disagrees.
-- Tables live in schema `erpme` (ADR-0022 rule 7); domains live in schema `types` (ADR-0006 rule 8).
-- Primary and foreign keys are shown inline; in migrations they get names from the
-- MetaData naming convention (ADR-0004 rule 15).
-- Referenced tables (company, document, account, system_account, posting_period, fiscal_year,
-- applied_rate, transaction_key, branch, partner, item, warehouse, cost_center, project,
-- employee, tax_code, open_item, material_document, material_document_line, derivation_trace,
-- close_task, posting_period_area_state, currency) are defined by their own design items.
-- IDs of journal rows come from context.new_id (ADR-0014 rule 14), so there are no ID defaults.

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
    salesperson_id             uuid          REFERENCES employee (id),
    tax_code_id                uuid          REFERENCES tax_code (id),
    material_document_line_id  uuid          REFERENCES material_document_line (id),
    open_item_id               uuid          REFERENCES open_item (id),
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
        ELSE 'general' END;
    SELECT state INTO v_state
      FROM posting_period_area_state
     WHERE posting_period_id = NEW.posting_period_id AND area = v_area
       FOR SHARE;
    IF v_state IS NULL OR v_state = 'locked' THEN
        RAISE EXCEPTION 'posting period is locked or has no state in area % (ADR-0012 rule 5)', v_area
            USING ERRCODE = 'restrict_violation';
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
