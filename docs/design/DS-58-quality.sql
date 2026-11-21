-- DS-58 quality management: DDL draft for ADR-0070 (quality management core, D24). PostgreSQL 18.
-- Kept in a file of its own, like DS-36: load_all.py loads it after the files of its FILE_ORDER, and it refers only to
-- tables they define (DS-20, DS-22-09-42, DS-43-54, DS-05-platform, DS-15) and DS-36-document-intake.sql.
-- The ADRs win if this file disagrees.
-- Conventions of DS-20 and DS-05: tables in schema nativeflows, domains in types; keys inline, named by the MetaData naming
-- convention in migrations (ADR-0004 rule 15); UUIDv7 IDs from context.new_id or the client, no ID defaults; references
-- between company tables are composite on (company_id, id); recorded_at on every row (ADR-0007 rule 9). Every table gets
-- FORCE ROW LEVEL SECURITY and the company policy (ADR-0017 rule 19), written at the end as rls_v1 would.
-- Lifecycle columns are named state; enumerations are text with CHECK ck_<table>_<col> (ADR-0004 rules 14, 15).
-- Referenced tables defined elsewhere: company, item, item_group, product, uom, warehouse, lot, serial_number, partner,
-- site, reason (DS-20); document, agent_run (DS-05-platform); user_account (DS-15); production_order (DS-43-54);
-- document_extraction (DS-36). platform_check_append_only() is DS-05-platform's guard.
-- The stock key is unchanged: a lot claims stock by (item, warehouse, lot or serial, held_stock_status) (ADR-0070 rule 9).
-- Owner module: quality (ADR-0070 rule 1); every table below says so.
-- Columns ADR-0070 adds to tables of other files, placed there: product.inspection_points, replacing is_inspection_required
-- (DS-20; rule 2); return_to_supplier_line.stock_status (DS-22-09-42; rule 15); the purpose certificate_of_analysis in
-- ck_document_extraction_purpose, ck_document_reader_purposes and ck_extraction_mapping_rule_purpose (the partner's
-- mapping rules resolve characteristic codes, rule 11), and the target inspection_result in
-- ck_extraction_result_link_target (DS-36; rule 11). The scrap and internal_consumption line tables are defined in
-- DS-22-09-42 (ADR-0075 rules 4, 5); their lines carry stock_status like material_document_line, and
-- internal_consumption lines take movement type internal_consumption or quality_sample (rule 15). inspection_lot_line.reason_id
-- (rule 12) follows scrap_line.scrap_reason_id and return_to_supplier_line.return_reason_id (ADR-0074 rule 22).

-- ===== Master data [quality] (ADR-0070 rules 3-6) =====
CREATE TABLE sampling_procedure (                          -- [quality] ADR-0070 rule 3; company data, change-tracked, master_data_change
    id              uuid PRIMARY KEY,
    company_id      uuid NOT NULL REFERENCES company (id),
    code            text NOT NULL,
    name            text NOT NULL,
    kind            text NOT NULL CONSTRAINT ck_sampling_procedure_kind CHECK (kind IN ('fixed_quantity', 'percent', 'full')),   -- later: iso_2859, skip_lot (rule 21)
    sample_quantity types.quantity CONSTRAINT ck_sampling_procedure_sample_quantity CHECK (sample_quantity > 0),   -- inventory units, fixed_quantity only
    sample_percent  types.percent CONSTRAINT ck_sampling_procedure_sample_percent CHECK (sample_percent > 0 AND sample_percent <= 100),
    is_active       boolean NOT NULL DEFAULT true,
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    CONSTRAINT ck_sampling_procedure_parameters CHECK ((kind = 'fixed_quantity') = (sample_quantity IS NOT NULL)
        AND (kind = 'percent') = (sample_percent IS NOT NULL))
);
CREATE TABLE inspection_plan (                             -- [quality] ADR-0070 rule 4; the header has no effect without a released revision
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    code              text NOT NULL,
    name              text NOT NULL,
    item_id           uuid,
    item_group_id     uuid,
    inspection_point  text NOT NULL CONSTRAINT ck_inspection_plan_inspection_point CHECK (inspection_point IN ('goods_receipt', 'in_process', 'production_output', 'customer_return', 'stock_recheck')),
    site_id           uuid,                                    -- optional; selection prefers a plan of the lot's site (rule 4)
    operation_number  integer CONSTRAINT ck_inspection_plan_operation_number CHECK (operation_number > 0),   -- in_process plans of an item only
    is_active         boolean NOT NULL DEFAULT true,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    UNIQUE NULLS NOT DISTINCT (company_id, item_id, item_group_id, inspection_point, site_id, operation_number),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, item_group_id) REFERENCES item_group (company_id, id),
    FOREIGN KEY (company_id, site_id) REFERENCES site (company_id, id),
    CONSTRAINT ck_inspection_plan_subject CHECK (num_nonnulls(item_id, item_group_id) = 1),
    CONSTRAINT ck_inspection_plan_operation CHECK (operation_number IS NULL OR (inspection_point = 'in_process' AND item_id IS NOT NULL))
);
CREATE TABLE inspection_plan_revision (                    -- [quality] ADR-0070 rule 4; immutable once released, like bill_of_materials_revision
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    inspection_plan_id      uuid NOT NULL,
    revision                integer NOT NULL CONSTRAINT ck_inspection_plan_revision_revision CHECK (revision > 0),
    state                   text NOT NULL DEFAULT 'draft' CONSTRAINT ck_inspection_plan_revision_state CHECK (state IN ('draft', 'released')),
    start_date              date NOT NULL,
    sampling_procedure_id   uuid NOT NULL,
    is_auto_accept_allowed  boolean NOT NULL DEFAULT false,   -- rule 14: one of three choices
    is_sample_destroyed     boolean NOT NULL DEFAULT false,   -- the auto decision adds sample_consumption (rule 14)
    content_hash            text CONSTRAINT ck_inspection_plan_revision_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    released_at             timestamptz,
    copy_from_revision_id   uuid,
    recorded_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (inspection_plan_id, revision),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, inspection_plan_id) REFERENCES inspection_plan (company_id, id),
    FOREIGN KEY (company_id, sampling_procedure_id) REFERENCES sampling_procedure (company_id, id),
    FOREIGN KEY (company_id, copy_from_revision_id) REFERENCES inspection_plan_revision (company_id, id),
    CONSTRAINT ck_inspection_plan_revision_released CHECK ((state = 'released') = (content_hash IS NOT NULL AND released_at IS NOT NULL))
);
-- At most one draft per plan (draft_revision_exists, as ADR-0033 rule 3).
CREATE UNIQUE INDEX ux_inspection_plan_revision_draft ON inspection_plan_revision (inspection_plan_id) WHERE state = 'draft';
CREATE TABLE inspection_characteristic (                   -- [quality] ADR-0070 rule 5; lines of a revision, immutable with it
    id                            uuid PRIMARY KEY,
    company_id                    uuid NOT NULL,
    inspection_plan_revision_id   uuid NOT NULL,
    position                      integer NOT NULL CONSTRAINT ck_inspection_characteristic_position CHECK (position > 0),
    code                          text NOT NULL,
    name                          text NOT NULL,
    kind                          text NOT NULL CONSTRAINT ck_inspection_characteristic_kind CHECK (kind IN ('quantitative', 'qualitative')),
    uom_id                        uuid REFERENCES uom (id),
    target_value                  types.quantity,
    lower_limit                   types.quantity,             -- inclusive
    upper_limit                   types.quantity,             -- inclusive
    allowed_result_codes          text[],
    passing_result_codes          text[],
    is_required                   boolean NOT NULL DEFAULT true,
    is_recorded_per_unit          boolean NOT NULL DEFAULT false,   -- one result per sample unit, else one summary result
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (inspection_plan_revision_id, position),
    UNIQUE (inspection_plan_revision_id, code),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, inspection_plan_revision_id),
    FOREIGN KEY (company_id, inspection_plan_revision_id) REFERENCES inspection_plan_revision (company_id, id),
    CONSTRAINT ck_inspection_characteristic_quantitative CHECK (kind <> 'quantitative' OR (uom_id IS NOT NULL
        AND num_nonnulls(lower_limit, upper_limit) > 0 AND allowed_result_codes IS NULL AND passing_result_codes IS NULL
        AND (lower_limit IS NULL OR upper_limit IS NULL OR lower_limit <= upper_limit)
        AND (target_value IS NULL OR ((lower_limit IS NULL OR lower_limit <= target_value) AND (upper_limit IS NULL OR target_value <= upper_limit))))),
    CONSTRAINT ck_inspection_characteristic_qualitative CHECK (kind <> 'qualitative' OR (uom_id IS NULL AND target_value IS NULL
        AND lower_limit IS NULL AND upper_limit IS NULL AND cardinality(allowed_result_codes) > 0
        AND cardinality(passing_result_codes) > 0 AND passing_result_codes <@ allowed_result_codes))
);
CREATE TABLE defect_code (                                 -- [quality] ADR-0070 rule 6; company data, change-tracked, master_data_change
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    code         text NOT NULL,
    name         text NOT NULL,
    severity     text NOT NULL CONSTRAINT ck_defect_code_severity CHECK (severity IN ('critical', 'major', 'minor')),
    is_active    boolean NOT NULL DEFAULT true,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);

-- ===== Inspection lots [quality] (ADR-0070 rules 7-9, 12, 15) =====
-- A non-posting document type: the shared document row holds state, version and number (ADR-0009 rules 1, 6).
CREATE TABLE inspection_lot (                              -- [quality] ADR-0070 rule 7
    id                            uuid PRIMARY KEY,
    company_id                    uuid NOT NULL,
    inspection_point              text NOT NULL CONSTRAINT ck_inspection_lot_inspection_point CHECK (inspection_point IN ('goods_receipt', 'in_process', 'production_output', 'customer_return', 'stock_recheck')),
    item_id                       uuid NOT NULL,
    warehouse_id                  uuid NOT NULL,             -- record scope (ADR-0017 rule 9); for in_process the production warehouse
    lot_id                        uuid,
    serial_number_id              uuid,   -- a single-serial lot; a lot of several serials names them on its lines
    held_stock_status             text CONSTRAINT ck_inspection_lot_held_stock_status CHECK (held_stock_status IN ('quality_inspection', 'blocked')),
    quantity                      types.quantity NOT NULL CONSTRAINT ck_inspection_lot_quantity CHECK (quantity > 0),   -- inventory unit
    sample_quantity               types.quantity NOT NULL CONSTRAINT ck_inspection_lot_sample_quantity CHECK (sample_quantity >= 0),
    inspection_plan_revision_id   uuid,                      -- null: no plan matched; a person decides (rule 8)
    source_document_id            uuid,                      -- the posting document that created the stock or progress
    source_line_number            integer CONSTRAINT ck_inspection_lot_source_line_number CHECK (source_line_number > 0),
    partner_id                    uuid,                      -- supplier at goods_receipt, customer at customer_return
    production_order_id           uuid,
    operation_number              integer CONSTRAINT ck_inspection_lot_operation_number CHECK (operation_number > 0),
    outcome                       text CONSTRAINT ck_inspection_lot_outcome CHECK (outcome IN ('accepted', 'accepted_with_deviation', 'rejected')),
    deviation_reason              text,
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, inspection_plan_revision_id),   -- results carry the lot's revision through it
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, inspection_plan_revision_id) REFERENCES inspection_plan_revision (company_id, id),
    FOREIGN KEY (company_id, source_document_id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id),
    CONSTRAINT ck_inspection_lot_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_inspection_lot_sample CHECK (sample_quantity <= quantity),
    CONSTRAINT ck_inspection_lot_source CHECK ((source_document_id IS NULL) = (source_line_number IS NULL)
        AND (inspection_point = 'stock_recheck' OR source_document_id IS NOT NULL)),
    -- in_process lots hold no stock and name the order and operation; every other point holds stock (rules 7, 9)
    CONSTRAINT ck_inspection_lot_point CHECK (CASE inspection_point
        WHEN 'in_process' THEN held_stock_status IS NULL AND production_order_id IS NOT NULL AND operation_number IS NOT NULL
        WHEN 'customer_return' THEN held_stock_status = 'blocked' AND operation_number IS NULL
        WHEN 'stock_recheck' THEN held_stock_status IS NOT NULL AND operation_number IS NULL
        ELSE held_stock_status = 'quality_inspection' AND operation_number IS NULL END),
    CONSTRAINT ck_inspection_lot_deviation CHECK ((outcome = 'accepted_with_deviation') = (coalesce(length(btrim(deviation_reason)), 0) > 0)),
    FOREIGN KEY (company_id, lot_id) REFERENCES lot (company_id, id),   -- company key (ADR-0017 rule 19 note, 2026-11-21)
    FOREIGN KEY (company_id, serial_number_id) REFERENCES serial_number (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE INDEX ix_inspection_lot_stock_key ON inspection_lot (company_id, item_id, warehouse_id, lot_id);
CREATE INDEX ix_inspection_lot_source_document_id ON inspection_lot (source_document_id) WHERE source_document_id IS NOT NULL;
-- The usage decision's split (rule 12): document lines, versioned with the lot. Sum = lot quantity is checked at Submit (INV-831).
CREATE TABLE inspection_lot_line (                         -- [quality] ADR-0070 rule 12
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL,
    inspection_lot_id   uuid NOT NULL,
    line_number         integer NOT NULL CONSTRAINT ck_inspection_lot_line_line_number CHECK (line_number > 0),
    disposition         text NOT NULL CONSTRAINT ck_inspection_lot_line_disposition CHECK (disposition IN ('release', 'block', 'return_to_supplier', 'scrap', 'rework', 'sample_consumption')),
    quantity            types.quantity NOT NULL CONSTRAINT ck_inspection_lot_line_quantity CHECK (quantity > 0),   -- inventory unit
    serial_number_id    uuid,
    reason_id           uuid,                                -- only for scrap (kind scrap) and return_to_supplier (kind return); required while documents.reason_required.scrap or .return is true (ADR-0074 rule 22); the executor copies it to the draft it creates (rule 15)
    reason_kind         text CONSTRAINT ck_inspection_lot_line_reason_kind CHECK (reason_kind IN ('scrap', 'return')),
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (inspection_lot_id, line_number),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, disposition),
    FOREIGN KEY (company_id, inspection_lot_id) REFERENCES inspection_lot (company_id, id),
    FOREIGN KEY (company_id, reason_id, reason_kind) REFERENCES reason (company_id, id, kind),
    CONSTRAINT ck_inspection_lot_line_serial_quantity CHECK (serial_number_id IS NULL OR quantity = 1),
    CONSTRAINT ck_inspection_lot_line_reason CHECK ((reason_id IS NULL) = (reason_kind IS NULL)
        AND (reason_id IS NULL OR (disposition = 'scrap' AND reason_kind = 'scrap') OR (disposition = 'return_to_supplier' AND reason_kind = 'return'))),
    FOREIGN KEY (company_id, serial_number_id) REFERENCES serial_number (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
-- What the executor created for a line, and how it ended (rule 15). Written only by RecordInspectionLotExecution;
-- state moves created -> done | canceled once, by trigger; identity and target never change.
CREATE TABLE inspection_lot_execution (                    -- [quality] ADR-0070 rule 15
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    inspection_lot_line_id   uuid NOT NULL,
    disposition              text NOT NULL,              -- the line's, held by the key below
    target_table             text NOT NULL CONSTRAINT ck_inspection_lot_execution_target_table CHECK (target_table IN ('warehouse_task', 'return_to_supplier', 'scrap', 'internal_consumption', 'production_order')),
    target_id                uuid NOT NULL,              -- polymorphic; created with this client ID in the same batch
    state                    text NOT NULL DEFAULT 'created' CONSTRAINT ck_inspection_lot_execution_state CHECK (state IN ('created', 'done', 'canceled')),
    done_quantity            types.quantity CONSTRAINT ck_inspection_lot_execution_done_quantity CHECK (done_quantity >= 0),
    recorded_at              timestamptz NOT NULL DEFAULT now(),       -- the last write
    UNIQUE (company_id, id),
    UNIQUE (target_table, target_id),
    CONSTRAINT fk_inspection_lot_execution_line FOREIGN KEY (company_id, inspection_lot_line_id, disposition) REFERENCES inspection_lot_line (company_id, id, disposition),
    CONSTRAINT ck_inspection_lot_execution_done CHECK ((state = 'done') = (done_quantity IS NOT NULL)),
    -- the target fits the disposition (INV-834); a rework from blocked also has a status-change task
    CONSTRAINT ck_inspection_lot_execution_target CHECK (CASE disposition
        WHEN 'release' THEN target_table = 'warehouse_task'
        WHEN 'block' THEN target_table = 'warehouse_task'
        WHEN 'return_to_supplier' THEN target_table = 'return_to_supplier'
        WHEN 'scrap' THEN target_table = 'scrap'
        WHEN 'sample_consumption' THEN target_table = 'internal_consumption'
        WHEN 'rework' THEN target_table IN ('production_order', 'warehouse_task') END)
);
CREATE INDEX ix_inspection_lot_execution_line ON inspection_lot_execution (inspection_lot_line_id);

-- ===== Results [quality] (ADR-0070 rules 10-11) =====
-- Append-only; a correction is a new row superseding an earlier one; confirmation sets two columns once (trigger).
CREATE TABLE inspection_result (                           -- [quality] ADR-0070 rule 10
    id                            uuid PRIMARY KEY,
    company_id                    uuid NOT NULL,
    inspection_lot_id             uuid NOT NULL,
    inspection_plan_revision_id   uuid NOT NULL,            -- the lot's revision (fk_inspection_result_lot); a lot without a plan has no results
    inspection_characteristic_id  uuid NOT NULL,
    sample_number                 integer CONSTRAINT ck_inspection_result_sample_number CHECK (sample_number > 0),   -- null: a summary result
    serial_number_id              uuid,
    value                         types.quantity,           -- quantitative, in the characteristic's unit; typed for SPC later
    result_code                   text,                     -- qualitative, one of allowed_result_codes
    is_passed                     boolean NOT NULL,         -- computed by the handler from the immutable revision
    defect_code_id                uuid,
    note                          text,
    entry_source                  text NOT NULL CONSTRAINT ck_inspection_result_entry_source CHECK (entry_source IN ('person', 'integration', 'certificate', 'agent')),
    recorded_by_user_id           uuid REFERENCES user_account (id),   -- person rows
    agent_run_id                  uuid,                     -- agent rows
    document_extraction_id        uuid,                     -- certificate rows
    extraction_field_id           uuid,                     -- the value's field
    attachment_id                 uuid,                     -- optional photo or certificate (ADR-0038 rule 14)
    test_equipment_id             uuid,                     -- reserved for calibration (rule 21); null in Phase 1
    supersedes_result_id          uuid,
    confirmed_by_user_id          uuid REFERENCES user_account (id),
    confirmed_at                  timestamptz,
    recorded_at                   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, inspection_lot_id, inspection_characteristic_id),
    CONSTRAINT fk_inspection_result_lot FOREIGN KEY (company_id, inspection_lot_id, inspection_plan_revision_id) REFERENCES inspection_lot (company_id, id, inspection_plan_revision_id),
    FOREIGN KEY (company_id, inspection_characteristic_id, inspection_plan_revision_id) REFERENCES inspection_characteristic (company_id, id, inspection_plan_revision_id),
    FOREIGN KEY (company_id, defect_code_id) REFERENCES defect_code (company_id, id),
    FOREIGN KEY (company_id, agent_run_id) REFERENCES agent_run (company_id, id),
    FOREIGN KEY (company_id, document_extraction_id) REFERENCES document_extraction (company_id, id),
    -- a correction stays on its lot and characteristic
    CONSTRAINT fk_inspection_result_supersedes FOREIGN KEY (company_id, supersedes_result_id, inspection_lot_id, inspection_characteristic_id)
        REFERENCES inspection_result (company_id, id, inspection_lot_id, inspection_characteristic_id),
    CONSTRAINT ck_inspection_result_value CHECK (num_nonnulls(value, result_code) = 1),
    CONSTRAINT ck_inspection_result_test_equipment CHECK (test_equipment_id IS NULL),
    CONSTRAINT ck_inspection_result_source CHECK (CASE entry_source
        WHEN 'person' THEN recorded_by_user_id IS NOT NULL AND agent_run_id IS NULL AND document_extraction_id IS NULL
        WHEN 'integration' THEN agent_run_id IS NULL AND document_extraction_id IS NULL
        WHEN 'certificate' THEN document_extraction_id IS NOT NULL
        WHEN 'agent' THEN agent_run_id IS NOT NULL END),
    -- person and integration rows are confirmed when written; certificate and agent rows only by a person later (rule 10)
    CONSTRAINT ck_inspection_result_confirmed CHECK ((confirmed_by_user_id IS NULL) = (confirmed_at IS NULL)
        AND (entry_source IN ('certificate', 'agent') OR confirmed_at IS NULL)),
    CONSTRAINT ck_inspection_result_extraction_field CHECK (extraction_field_id IS NULL OR document_extraction_id IS NOT NULL),
    FOREIGN KEY (company_id, serial_number_id) REFERENCES serial_number (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
-- A row is superseded at most once, so the result in force per (lot, characteristic, unit) is unique (rule 10).
CREATE UNIQUE INDEX ux_inspection_result_supersedes ON inspection_result (supersedes_result_id) WHERE supersedes_result_id IS NOT NULL;
CREATE UNIQUE INDEX ux_inspection_result_root ON inspection_result (inspection_lot_id, inspection_characteristic_id, coalesce(sample_number, 0)) WHERE supersedes_result_id IS NULL;
-- "Confirmed" for a decision: entry_source in (person, integration) or confirmed_at is not null (INV-832).

-- ===== Nonconformance [quality] (ADR-0070 rule 16) =====
-- Not a document type, like complaint (ADR-0052 rule 20); history in audit; actions are work items in a work case.
CREATE TABLE nonconformance (                              -- [quality] ADR-0070 rule 16
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL REFERENCES company (id),
    kind                        text NOT NULL CONSTRAINT ck_nonconformance_kind CHECK (kind IN ('supplier', 'internal', 'customer')),
    state                       text NOT NULL DEFAULT 'open' CONSTRAINT ck_nonconformance_state CHECK (state IN ('open', 'closed', 'canceled')),
    defect_code_id              uuid,
    item_id                     uuid,
    lot_id                      uuid,
    serial_number_id            uuid,
    quantity                    types.quantity CONSTRAINT ck_nonconformance_quantity CHECK (quantity > 0),   -- inventory unit
    partner_id                  uuid,                      -- the supplier or customer
    inspection_lot_id           uuid,
    source_table                text CONSTRAINT ck_nonconformance_source_table CHECK (source_table IN ('document', 'complaint')),
    source_id                   uuid,                      -- polymorphic, checked by the command; a complaint by ID only (rule 1)
    description                 text NOT NULL,
    root_cause                  text,
    containment_action          text,
    containment_user_id         uuid REFERENCES user_account (id),
    containment_due_date        date,
    corrective_action           text,
    corrective_user_id          uuid REFERENCES user_account (id),
    corrective_due_date         date,
    opened_at                   timestamptz NOT NULL,
    closed_at                   timestamptz,
    close_note                  text,
    cancel_reason               text,
    version                     integer NOT NULL DEFAULT 1,
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, defect_code_id) REFERENCES defect_code (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, inspection_lot_id) REFERENCES inspection_lot (company_id, id),
    CONSTRAINT ck_nonconformance_lot_or_serial CHECK (lot_id IS NULL OR serial_number_id IS NULL),
    CONSTRAINT ck_nonconformance_partner CHECK (kind = 'internal' OR partner_id IS NOT NULL),
    CONSTRAINT ck_nonconformance_source CHECK ((source_table IS NULL) = (source_id IS NULL)),
    CONSTRAINT ck_nonconformance_closed CHECK ((state = 'closed') = (closed_at IS NOT NULL)
        AND (state <> 'closed' OR coalesce(length(btrim(close_note)), 0) > 0)
        AND (state <> 'canceled' OR coalesce(length(btrim(cancel_reason)), 0) > 0)),
    CONSTRAINT ck_nonconformance_closed_after_opened CHECK (closed_at IS NULL OR closed_at >= opened_at),
    CONSTRAINT ck_nonconformance_containment CHECK ((containment_user_id IS NULL) = (containment_due_date IS NULL)),
    CONSTRAINT ck_nonconformance_corrective CHECK ((corrective_user_id IS NULL) = (corrective_due_date IS NULL)),
    FOREIGN KEY (company_id, lot_id) REFERENCES lot (company_id, id),   -- company key (ADR-0017 rule 19 note, 2026-11-21)
    FOREIGN KEY (company_id, serial_number_id) REFERENCES serial_number (company_id, id)   -- company key (ADR-0017 rule 19 note, 2026-11-21)
);
CREATE INDEX ix_nonconformance_company_id_partner_id ON nonconformance (company_id, partner_id) WHERE state = 'open';

-- ===== Guards (ADR-0070 rules 4, 10, 15) =====
-- Released revisions and their characteristics are immutable (as ADR-0033 rules 3-4; INV-830): the trigger refuses any change
-- to a released inspection_plan_revision row except none, and any insert, update or delete of a characteristic whose revision
-- is released. inspection_result is append-only except the once-only confirmation columns. inspection_lot_execution
-- changes only state (created -> done | canceled, once), done_quantity and recorded_at. The trigger bodies follow
-- DS-43-54's bill_of_materials_revision guard and DS-05-platform's platform_check_append_only().

-- ===== recorded_at on insert and update; TRUNCATE refused (ADR-0007 rules 9, 16 and their notes) =====
-- Every table of this file has recorded_at timestamptz NOT NULL DEFAULT now(). The DO block attaches the trigger
-- trg_<table>_set_recorded_at (function set_recorded_at) to every table of v_tables: BEFORE INSERT OR UPDATE on tables
-- updated in place, BEFORE INSERT on the append-only tables of v_append_only. recorded_at is so the instant of the last
-- write, set by the system and never taken from a client (ADR-0007 rule 9 and its notes; S2 adversarial review S2).
-- Append-only tables are those whose guard trigger refuses every update outside an erasure, and pure logs.
-- Row guards without UPDATE OF on in-place tables sort before set_recorded_at, so they compare rows before it runs; a
-- BEFORE INSERT trigger whose function reads NEW.recorded_at sorts after it, so it sees the system's value.
-- TRUNCATE skips row triggers and row-level security, so every table with company_id, every append-only table and every
-- table with a BEFORE DELETE guard, unless it has a TRUNCATE trigger of its own, is listed in v_refuse_truncate (default
-- partitions with their parent) and gets trg_<table>_refuse_truncate (BEFORE TRUNCATE, function refuse_truncate; S2
-- adversarial review N4; S2 schema review R6-N2). Retention drops partitions and never truncates (ADR-0017 rule 19 note).
-- Lab gen_overview.py --check compares this section with what schema_phase_b.py writes from the table definitions and
-- triggers of the design files. The functions are defined in every file because the labs load subsets.
CREATE OR REPLACE FUNCTION set_recorded_at() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    NEW.recorded_at := now();
    RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION refuse_truncate() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$
BEGIN
    RAISE EXCEPTION '% is never truncated (company, append-only or guarded rows)', TG_TABLE_NAME USING ERRCODE = 'restrict_violation';
END $$;
DO $$
DECLARE
    v_tables            text[] := ARRAY['sampling_procedure', 'inspection_plan', 'inspection_plan_revision', 'inspection_characteristic', 'defect_code',
        'inspection_lot', 'inspection_lot_line', 'inspection_lot_execution', 'inspection_result', 'nonconformance'];
    v_append_only       text[] := ARRAY[]::text[];
    v_refuse_truncate   text[] := ARRAY['sampling_procedure', 'inspection_plan', 'inspection_plan_revision', 'inspection_characteristic', 'defect_code',
        'inspection_lot', 'inspection_lot_line', 'inspection_lot_execution', 'inspection_result', 'nonconformance']::text[];
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
-- Lab gen_overview.py --check compares this section with what schema_phase_b.py writes.
DO $$
DECLARE
    v_tables    text[] := ARRAY['sampling_procedure', 'inspection_plan', 'inspection_plan_revision', 'inspection_characteristic', 'defect_code',
        'inspection_lot', 'inspection_lot_line', 'inspection_lot_execution', 'inspection_result', 'nonconformance'];
    v_nullable  text[] := ARRAY[]::text[];
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
    END LOOP;
END $$;
-- ===== end of row-level security =====
