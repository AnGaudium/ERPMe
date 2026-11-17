-- DS-36 document intake: DDL draft for ADR-0057 (document intake and extraction) and the keys ADR-0062 (product
-- engineering) closes between DS-43-54 and DS-05-platform. Named after DS-36, the item that owns the attachments module
-- (ADR-0027 rule 2; ADR-0038 rules 13-15); its other tables (attachment, attachment_link) are in DS-05-platform.sql.
-- Kept in a file of its own so that the platform lab's closed lists (installation tables, nullable company columns,
-- policy counts) stay as they are; load_all.py loads it after the files of its FILE_ORDER (ADR-0057 rule 1).
-- PostgreSQL 18. The ADRs win if this file disagrees.
-- Conventions of DS-20 and DS-05: tables in schema nativeflows, domains in types; keys inline, named by the MetaData naming
-- convention in migrations (ADR-0004 rule 15); UUIDv7 IDs from context.new_id, no ID defaults; references between company
-- tables are composite on (company_id, id); recorded_at on every row (ADR-0007 rule 9). Every table with company_id gets
-- FORCE ROW LEVEL SECURITY and the company policy (ADR-0017 rule 19), written at the end as rls_v1 would.
-- Installation table without company_id: document_reader.
-- Referenced tables defined elsewhere: company, partner (DS-20); user_account (DS-15); inbound_message (DS-35);
-- attachment, agent_run, change_proposal_item (DS-05-platform); bill_of_materials, bill_of_materials_component (DS-43-54).
-- platform_check_append_only() is DS-05-platform's guard function.
-- Trust is not stored: the view extraction_field_trust computes it from the field, its extraction, its latest rule run
-- and its confirmation (ADR-0057 rule 17).
-- Owner module per section in brackets (ADR-0022 rule 2).

-- ===== Readers [attachments] (ADR-0057 rules 4-6) =====
-- Written by the registry at startup from the readers registered on the document_reader hook; nobody edits them.
CREATE TABLE document_reader (                             -- installation data; immutable (trigger below)
    id             uuid PRIMARY KEY,
    code           text NOT NULL CONSTRAINT ck_document_reader_code CHECK (code ~ '^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$'),   -- <owner>.<name>, e.g. core.spreadsheet_cells
    version        text NOT NULL CONSTRAINT ck_document_reader_version CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
    rung           text NOT NULL CONSTRAINT ck_document_reader_rung CHECK (rung IN ('structured_xml', 'embedded_xml', 'qr_vcard', 'spreadsheet', 'pdf_text', 'ocr_words', 'vision')),
    package_code   text,                                   -- the localization package that registered it; null for core and module readers
    purposes       text[] NOT NULL,                        -- the purposes it reads (rule 2)
    content_hash   text NOT NULL CONSTRAINT ck_document_reader_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    recorded_at    timestamptz NOT NULL,
    UNIQUE (code, version),
    CONSTRAINT ck_document_reader_purposes CHECK (cardinality(purposes) > 0
        AND purposes <@ ARRAY['supplier_invoice', 'contact_card', 'inquiry_lines', 'product_source', 'shop_floor_report', 'delivery_note', 'certificate_of_analysis']::text[])
);

-- ===== Extractions [attachments] (ADR-0057 rules 3, 7-10, 14, 17-19, 23) =====
CREATE TABLE document_extraction (                         -- one per attachment and purpose (rule 3)
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    attachment_id            uuid NOT NULL,
    purpose                  text NOT NULL CONSTRAINT ck_document_extraction_purpose CHECK (purpose IN ('supplier_invoice', 'contact_card', 'inquiry_lines', 'product_source', 'shop_floor_report', 'delivery_note', 'certificate_of_analysis')),   -- certificate_of_analysis: ADR-0070 rule 11
    attachment_sha256        text NOT NULL CONSTRAINT ck_document_extraction_sha256 CHECK (attachment_sha256 ~ '^[0-9a-f]{64}$'),
    detected_media_type      text NOT NULL,                -- from the bytes, never the file name (rule 4)
    document_kind            text CONSTRAINT ck_document_extraction_document_kind CHECK (document_kind IN ('xml', 'pdf_embedded_xml', 'pdf_text', 'pdf_image', 'image', 'spreadsheet', 'email')),
    page_count               integer CONSTRAINT ck_document_extraction_page_count CHECK (page_count > 0),
    data_label               text NOT NULL CONSTRAINT ck_document_extraction_data_label CHECK (data_label IN ('internal', 'personal', 'sensitive_personal')),   -- the attachment's or higher (rule 19)
    state                    text NOT NULL DEFAULT 'pending' CONSTRAINT ck_document_extraction_state CHECK (state IN ('pending', 'extracted', 'needs_review', 'verified', 'canceled')),
    reader_attempts          jsonb NOT NULL DEFAULT '[]' CONSTRAINT ck_document_extraction_attempts CHECK (jsonb_typeof(reader_attempts) = 'array'),   -- per rung: reader, version, outcome (rule 4)
    final_reader_id          uuid REFERENCES document_reader (id),   -- the rung whose record was valid; null when none was
    -- the flags and the signature state are set only by RecordDocumentExtraction while the record is pending (rules 4, 7)
    hidden_text_suspected    boolean NOT NULL DEFAULT false,         -- text-layer words without OCR counterpart at their position (rule 18)
    injection_signal         boolean NOT NULL DEFAULT false,         -- a classifier's signal, never a gate (rule 18)
    is_full_review_required  boolean NOT NULL DEFAULT false,
    signature_state          text CONSTRAINT ck_document_extraction_signature_state CHECK (signature_state IN ('passed', 'signer_mismatch', 'failed', 'absent', 'not_applicable')),   -- rule 6
    partner_id               uuid,                         -- whose document (rule 25); selects the mapping rules
    inbound_message_id       uuid,                         -- the message it arrived with (rule 25)
    requested_by_user_id     uuid NOT NULL REFERENCES user_account (id),   -- the human the request acts for
    verified_by_user_id      uuid REFERENCES user_account (id),
    verified_at              timestamptz,
    -- failed cross-field rules verified past (rule 14): a list of {"rule": <code>, "reason": <text with a non-blank character>}, never the shape rule
    rule_overrides           jsonb NOT NULL DEFAULT '[]' CONSTRAINT ck_document_extraction_rule_overrides CHECK (jsonb_typeof(rule_overrides) = 'array'
                                 AND NOT jsonb_path_exists(rule_overrides, '$[*] ? (@.type() != "object" || !(exists(@.rule)) || !(exists(@.reason))
                                     || @.rule.type() != "string" || @.reason.type() != "string" || @.rule == "shape" || @.reason like_regex "^\\s*$")')),
    canceled_reason          text,                         -- a person's reason, or rendering_of_parsed_xml from the system (rule 25)
    recorded_at              timestamptz NOT NULL,
    CONSTRAINT uq_document_extraction_attachment_purpose UNIQUE (company_id, attachment_id, purpose),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, attachment_id) REFERENCES attachment (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, inbound_message_id) REFERENCES inbound_message (company_id, id),
    CONSTRAINT ck_document_extraction_verified CHECK ((state = 'verified') = (verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL)),
    CONSTRAINT ck_document_extraction_canceled CHECK ((state = 'canceled') = (canceled_reason IS NOT NULL)),
    -- suspected hidden text forces a full review, and such a record is never 'extracted'; authenticity is the e-invoice record's quarantine, not a review (rules 7, 25)
    CONSTRAINT ck_document_extraction_full_review CHECK (NOT hidden_text_suspected OR is_full_review_required),
    CONSTRAINT ck_document_extraction_overrides CHECK (state = 'verified' OR rule_overrides = '[]'::jsonb),
    CONSTRAINT ck_document_extraction_extracted CHECK (state <> 'extracted' OR (final_reader_id IS NOT NULL AND NOT is_full_review_required))
);
-- OCR and text-layer words with normalized boxes and reading-order lines (rule 9); personal and untrusted with their extraction.
CREATE TABLE extraction_word (
    company_id               uuid NOT NULL,
    document_extraction_id   uuid NOT NULL,
    layer                    text NOT NULL CONSTRAINT ck_extraction_word_layer CHECK (layer IN ('ocr', 'text_layer')),
    page_number              integer NOT NULL CONSTRAINT ck_extraction_word_page CHECK (page_number > 0),
    word_number              integer NOT NULL CONSTRAINT ck_extraction_word_number CHECK (word_number > 0),   -- reading order on the page
    line_number              integer NOT NULL CONSTRAINT ck_extraction_word_line CHECK (line_number > 0),     -- reading-order line on the page (rule 12)
    cell_ref                 text,                         -- the cell of a detected table the word lies in; words of different cells never align together (rule 12)
    text                     text NOT NULL,
    x0                       numeric(7,6) NOT NULL,
    y0                       numeric(7,6) NOT NULL,
    x1                       numeric(7,6) NOT NULL,
    y1                       numeric(7,6) NOT NULL,
    confidence_raw           numeric(5,4) CONSTRAINT ck_extraction_word_confidence CHECK (confidence_raw BETWEEN 0 AND 1),   -- the engine's score
    is_on_render             boolean,                      -- text layer only: an OCR word of equal text overlaps it (rule 18)
    recorded_at              timestamptz NOT NULL,
    PRIMARY KEY (document_extraction_id, layer, page_number, word_number),
    FOREIGN KEY (company_id, document_extraction_id) REFERENCES document_extraction (company_id, id),
    -- boxes in 0..1 from the page's top left, so they survive any rendering
    CONSTRAINT ck_extraction_word_box CHECK (0 <= x0 AND x0 < x1 AND x1 <= 1 AND 0 <= y0 AND y0 < y1 AND y1 <= 1),
    CONSTRAINT ck_extraction_word_on_render CHECK ((layer = 'text_layer') = (is_on_render IS NOT NULL))
);
CREATE TABLE extraction_field (                            -- append-only; a correction is a new row superseding an earlier one (rule 8)
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    document_extraction_id   uuid NOT NULL,
    field_path               text NOT NULL CONSTRAINT ck_extraction_field_path CHECK (field_path ~ '^[a-z][a-z0-9_]*(\[[0-9]+\])?(\.[a-z][a-z0-9_]*(\[[0-9]+\])?)*$'),   -- e.g. lines[3].unit_price
    value_type               text NOT NULL CONSTRAINT ck_extraction_field_value_type CHECK (value_type IN ('text', 'code', 'amount', 'quantity', 'percent', 'date', 'tax_id', 'email', 'phone', 'currency', 'unit', 'bank_account', 'url')),
    value_raw                text,                         -- as printed or stored in the source; for aligned vision values, the page's text
    value_normalized         text,                         -- canonical form (ADR-0006 rule 13 decimals, ISO dates, resolved unit codes)
    status                   text NOT NULL CONSTRAINT ck_extraction_field_status CHECK (status IN ('found', 'not_found', 'illegible')),
    method                   text NOT NULL CONSTRAINT ck_extraction_field_method CHECK (method IN ('parsed', 'ocr', 'vision_aligned', 'vision_unaligned', 'computed', 'human')),
    evidence_kind            text CONSTRAINT ck_extraction_field_evidence_kind CHECK (evidence_kind IN ('xpath', 'cell', 'char_span', 'page_region', 'qr_payload')),
    evidence                 jsonb CONSTRAINT ck_extraction_field_evidence_object CHECK (jsonb_typeof(evidence) = 'object'),   -- rule 10
    document_reader_id       uuid REFERENCES document_reader (id),
    agent_run_id             uuid,                         -- vision rows: the document_reader run (rule 11)
    entered_by_user_id       uuid REFERENCES user_account (id),   -- human rows: the person who entered the correction
    confidence_raw           numeric(5,4) CONSTRAINT ck_extraction_field_confidence_raw CHECK (confidence_raw BETWEEN 0 AND 1),   -- the engine's own score, never a model's self-report
    confidence_calibrated    numeric(5,4) CONSTRAINT ck_extraction_field_confidence_calibrated CHECK (confidence_calibrated BETWEEN 0 AND 1),   -- from the company's golden set (rule 13)
    data_label               text NOT NULL CONSTRAINT ck_extraction_field_data_label CHECK (data_label IN ('internal', 'personal', 'sensitive_personal')),
    supersedes_field_id      uuid,                         -- the row this one replaces
    recorded_at              timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, document_extraction_id),
    UNIQUE (company_id, id, document_extraction_id, field_path, value_type),
    FOREIGN KEY (company_id, document_extraction_id) REFERENCES document_extraction (company_id, id),
    FOREIGN KEY (company_id, agent_run_id) REFERENCES agent_run (company_id, id),
    -- a correction stays in its extraction and field and keeps the value type (rule 8)
    CONSTRAINT fk_extraction_field_supersedes FOREIGN KEY (company_id, supersedes_field_id, document_extraction_id, field_path, value_type)
        REFERENCES extraction_field (company_id, id, document_extraction_id, field_path, value_type),
    CONSTRAINT ck_extraction_field_value CHECK ((status = 'found') = (value_raw IS NOT NULL)),
    CONSTRAINT ck_extraction_field_evidence CHECK ((evidence_kind IS NULL) = (evidence IS NULL)
        AND (method NOT IN ('parsed', 'ocr', 'vision_aligned') OR status <> 'found' OR evidence IS NOT NULL)
        AND (method <> 'computed' OR evidence IS NULL)),
    CONSTRAINT ck_extraction_field_vision_run CHECK ((method IN ('vision_aligned', 'vision_unaligned')) = (agent_run_id IS NOT NULL)),
    CONSTRAINT ck_extraction_field_reader CHECK (method IN ('computed', 'human') OR document_reader_id IS NOT NULL),
    -- a person's row names its person; only a person's row or a vision row supersedes (the trigger checks which rows a vision row may replace)
    CONSTRAINT ck_extraction_field_human CHECK ((method = 'human') = (entered_by_user_id IS NOT NULL)
        AND (supersedes_field_id IS NULL OR method IN ('human', 'vision_aligned', 'vision_unaligned')))
);
-- One root row per path, and a row is superseded at most once, so the current value of a field is unique (rule 8).
CREATE UNIQUE INDEX ux_extraction_field_root ON extraction_field (document_extraction_id, field_path) WHERE supersedes_field_id IS NULL;
CREATE UNIQUE INDEX ux_extraction_field_supersedes ON extraction_field (supersedes_field_id) WHERE supersedes_field_id IS NOT NULL;
-- Rule runs (rule 14): one row per run, field and rule; append-only; every run evaluates every current field, and trust reads only the
-- extraction's highest run number. Confirmations start no run.
CREATE TABLE extraction_rule_run (
    company_id               uuid NOT NULL,
    document_extraction_id   uuid NOT NULL,
    run_number               integer NOT NULL CONSTRAINT ck_extraction_rule_run_number CHECK (run_number > 0),   -- increasing per extraction
    extraction_field_id      uuid NOT NULL,
    rule                     text NOT NULL CONSTRAINT ck_extraction_rule_run_rule CHECK (rule ~ '^[a-z][a-z0-9_]*(:[a-z0-9_]+)?$'),   -- 'shape' is mandatory for every field
    passed                   boolean NOT NULL,             -- strictly true or false
    detail                   jsonb NOT NULL DEFAULT '{}',
    trigger_kind             text NOT NULL CONSTRAINT ck_extraction_rule_run_trigger CHECK (trigger_kind IN ('ladder', 'vision', 'correction')),   -- written in the same transaction as that write (rule 14)
    recorded_at              timestamptz NOT NULL,
    PRIMARY KEY (document_extraction_id, run_number, extraction_field_id, rule),
    FOREIGN KEY (company_id, extraction_field_id, document_extraction_id) REFERENCES extraction_field (company_id, id, document_extraction_id)
);
CREATE INDEX ix_extraction_rule_run_field ON extraction_rule_run (extraction_field_id, run_number);
-- A person's confirmation of a field row (rule 23); one per row; append-only.
CREATE TABLE extraction_confirmation (
    company_id               uuid NOT NULL,
    document_extraction_id   uuid NOT NULL,
    extraction_field_id      uuid PRIMARY KEY,
    confirmed_by_user_id     uuid NOT NULL REFERENCES user_account (id),
    confirmed_at             timestamptz NOT NULL,
    recorded_at              timestamptz NOT NULL,
    FOREIGN KEY (company_id, extraction_field_id, document_extraction_id) REFERENCES extraction_field (company_id, id, document_extraction_id)
);
-- The subjects an extraction led to (rule 19): the e-invoice record, proposals, the created contact and partner, documents.
CREATE TABLE extraction_result_link (
    company_id               uuid NOT NULL,
    document_extraction_id   uuid NOT NULL,
    target_table             text NOT NULL CONSTRAINT ck_extraction_result_link_target CHECK (target_table IN ('e_invoice_record', 'change_proposal', 'contact', 'partner',
                                 'quotation', 'purchase_invoice', 'bill_of_materials_revision', 'inspection_result')),   -- inspection_result: ADR-0070 rule 11
    target_id                uuid NOT NULL,                -- polymorphic, checked by the command that links it
    recorded_at              timestamptz NOT NULL,
    PRIMARY KEY (document_extraction_id, target_table, target_id),
    FOREIGN KEY (company_id, document_extraction_id) REFERENCES document_extraction (company_id, id)
);
CREATE INDEX ix_extraction_result_link_target ON extraction_result_link (company_id, target_table, target_id);

-- ===== Trust, computed when read (ADR-0057 rule 17) =====
-- is_untrusted for a field row's normalized value: the extraction's flags, the type, the status, the person's confirmation and
-- the row's results in the extraction's highest rule run. value_raw and evidence are always served as untrusted. The query
-- layer serves this attribute for extraction fields (ADR-0050 rule 28), and the dispatcher stores what it served with the
-- run number (latest_run_number) in the step's context_refs (INV-642).
CREATE VIEW extraction_field_trust WITH (security_invoker = true) AS
WITH latest AS (
    SELECT document_extraction_id, max(run_number) AS run_number FROM extraction_rule_run GROUP BY document_extraction_id
), results AS (
    SELECT r.extraction_field_id, count(*) AS rule_count, bool_and(r.passed) AS all_passed, bool_or(r.rule = 'shape' AND r.passed) AS shape_passed
      FROM extraction_rule_run r JOIN latest l ON l.document_extraction_id = r.document_extraction_id AND l.run_number = r.run_number
     GROUP BY r.extraction_field_id
)
SELECT f.id AS extraction_field_id, f.company_id, f.document_extraction_id, f.field_path, f.value_type, f.method,
       (SELECT l.run_number FROM latest l WHERE l.document_extraction_id = f.document_extraction_id) AS latest_run_number,
       NOT EXISTS (SELECT 1 FROM extraction_field g WHERE g.supersedes_field_id = f.id) AS is_current,
       c.extraction_field_id IS NOT NULL AS is_confirmed,
       CASE WHEN e.hidden_text_suspected OR coalesce(e.signature_state, '') IN ('failed', 'signer_mismatch') THEN true
            WHEN f.value_type IN ('text', 'url', 'email', 'phone') OR f.status <> 'found' THEN true
            WHEN c.extraction_field_id IS NOT NULL THEN NOT coalesce(res.shape_passed, false)
            WHEN f.method IN ('parsed', 'ocr', 'computed') THEN NOT (coalesce(res.rule_count, 0) > 0 AND res.all_passed AND res.shape_passed)
            ELSE true END AS is_untrusted
  FROM extraction_field f
  JOIN document_extraction e ON e.id = f.document_extraction_id
  LEFT JOIN extraction_confirmation c ON c.extraction_field_id = f.id
  LEFT JOIN results res ON res.extraction_field_id = f.id;

-- ===== Mapping rules [master_data] (ADR-0057 rule 24) =====
CREATE TABLE extraction_mapping_rule (                     -- company data, change-tracked; master_data_change, proposals for agents
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    partner_id               uuid NOT NULL,
    purpose                  text NOT NULL CONSTRAINT ck_extraction_mapping_rule_purpose CHECK (purpose IN ('supplier_invoice', 'contact_card', 'inquiry_lines', 'product_source', 'shop_floor_report', 'delivery_note', 'certificate_of_analysis')),   -- certificate_of_analysis: ADR-0070 rule 11
    rule_kind                text NOT NULL CONSTRAINT ck_extraction_mapping_rule_kind CHECK (rule_kind IN ('label_anchor', 'column_header', 'unit_text')),
    source_text              text NOT NULL,                -- as first seen
    normalized_source_text   text NOT NULL,                -- NFKC, case folded, whitespace collapsed
    target                   text NOT NULL,                -- a field path, or a unit code for unit_text
    is_active                boolean NOT NULL DEFAULT true,
    recorded_at              timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_extraction_mapping_rule_normalized CHECK (length(normalized_source_text) > 0 AND normalized_source_text = lower(normalized_source_text))
);
-- One active rule per partner, purpose, kind and source text.
CREATE UNIQUE INDEX ux_extraction_mapping_rule_active ON extraction_mapping_rule (company_id, partner_id, purpose, rule_kind, normalized_source_text) WHERE is_active;

-- ===== Data-processing permissions [agent_runs] (ADR-0057 rules 20-21) =====
CREATE TABLE data_processing_permission (                  -- company data, change-tracked; SetDataProcessingPermission only from an approved proposal
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    data_class               text NOT NULL CONSTRAINT ck_data_processing_permission_data_class CHECK (data_class IN ('internal', 'personal')),   -- sensitive personal: never in Phase 1
    seat_class               text NOT NULL CONSTRAINT ck_data_processing_permission_seat_class CHECK (seat_class ~ '^[a-z][a-z0-9_]*$'),   -- e.g. extraction_vision_personal
    provider                 text NOT NULL CONSTRAINT ck_data_processing_permission_provider CHECK (provider ~ '^[a-z][a-z0-9_]*$'),     -- adapter code (ADR-0050 rule 3)
    processing_region        text NOT NULL,                -- a region of the installation's provider registry (DS-37)
    processing_country       text NOT NULL CONSTRAINT ck_data_processing_permission_country CHECK (processing_country ~ '^[A-Z]{2}$'),   -- copied from the registry by the handler
    is_cross_border          boolean NOT NULL,             -- computed by the handler: processing_country differs from the company's country
    assessment_attachment_id uuid,                         -- the recorded assessment, where the regime policy requires one
    assessed_on              date,
    approved_by_user_id      uuid NOT NULL REFERENCES user_account (id),
    -- ADR-0063 rule 14: optional purposes; the provider's terms and retention the permission was approved under, copied from
    -- the registry by the handler (null only where the registry declares no terms reference); suspended when the registry
    -- changes the endpoint's region or terms (RunDataProcessingProviderCheck).
    purposes                 text[] CONSTRAINT ck_data_processing_permission_purposes CHECK (purposes IS NULL OR (cardinality(purposes) >= 1
                                 AND purposes <@ ARRAY['supplier_invoice', 'contact_card', 'inquiry_lines', 'product_source'])),
    provider_terms_ref       text,
    provider_retention_days  integer CONSTRAINT ck_data_processing_permission_retention CHECK (provider_retention_days IS NULL OR provider_retention_days >= 0),
    suspended_at             timestamptz,
    suspension_reason        text CONSTRAINT ck_data_processing_permission_suspension_reason CHECK (suspension_reason IN ('provider_region_changed', 'provider_terms_changed')),
    effective_from           date NOT NULL,
    effective_to             date,                         -- inclusive; null = open
    recorded_at              timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, assessment_attachment_id) REFERENCES attachment (company_id, id),
    CONSTRAINT ck_data_processing_permission_assessment CHECK ((assessment_attachment_id IS NULL) = (assessed_on IS NULL)),
    CONSTRAINT ck_data_processing_permission_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_data_processing_permission_suspended CHECK ((suspended_at IS NULL) = (suspension_reason IS NULL)),
    -- one permission per class, seat class, provider and region on any date
    CONSTRAINT ex_data_processing_permission_overlap EXCLUDE USING gist (
        company_id WITH =, data_class WITH =, seat_class WITH =, provider WITH =, processing_region WITH =,
        daterange(effective_from, effective_to, '[]') WITH &&)
);

-- ===== Keys to tables of other files (ADR-0062 rules 14, 19) =====
-- A draft bill of materials or component may name the change proposal item that will create its item, by the item's
-- stable ID and inside the company. change_proposal_item (DS-05-platform) gains the company key for it.
ALTER TABLE change_proposal_item ADD CONSTRAINT uq_change_proposal_item_company_id_id UNIQUE (company_id, id);
ALTER TABLE bill_of_materials ADD CONSTRAINT fk_bill_of_materials_proposed_item FOREIGN KEY (company_id, proposed_change_proposal_item_id) REFERENCES change_proposal_item (company_id, id);
ALTER TABLE bill_of_materials_component ADD CONSTRAINT fk_bill_of_materials_component_proposed_item FOREIGN KEY (company_id, proposed_change_proposal_item_id) REFERENCES change_proposal_item (company_id, id);

-- ===== Guards =====
CREATE FUNCTION document_reader_reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'document_reader rows are never updated or deleted' USING ERRCODE = 'restrict_violation';
END
$$;
CREATE TRIGGER trg_document_reader_immutable BEFORE UPDATE OR DELETE ON document_reader
    FOR EACH ROW EXECUTE FUNCTION document_reader_reject_change();
-- Fields, rule runs, confirmations, words and links never change; erasure blanks field values and evidence and word text
-- (ADR-0057 rules 8, 19).
CREATE TRIGGER trg_extraction_field_append_only BEFORE UPDATE OR DELETE ON extraction_field FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{value_raw,value_normalized,evidence}');
CREATE TRIGGER trg_extraction_word_append_only BEFORE UPDATE OR DELETE ON extraction_word FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{text}');
CREATE TRIGGER trg_extraction_rule_run_append_only BEFORE UPDATE OR DELETE ON extraction_rule_run FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{}');
CREATE TRIGGER trg_extraction_confirmation_append_only BEFORE UPDATE OR DELETE ON extraction_confirmation FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{}');
CREATE TRIGGER trg_extraction_result_link_append_only BEFORE UPDATE OR DELETE ON extraction_result_link FOR EACH ROW
    EXECUTE FUNCTION platform_check_append_only('{}', '{}', '{}');
-- Appends to an extraction (rules 7, 8, 12, 23): nothing is appended to a verified or canceled extraction; a vision row
-- supersedes only a row not found or illegible; a confirmation names a current row that is not an unaligned vision value.
CREATE FUNCTION extraction_check_append() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_state   text;
    v_status  text;
    v_method  text;
BEGIN
    SELECT state INTO v_state FROM document_extraction WHERE id = NEW.document_extraction_id;
    IF v_state IN ('verified', 'canceled') THEN
        RAISE EXCEPTION 'extraction_not_reviewable' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_TABLE_NAME = 'extraction_field' THEN
        IF NEW.supersedes_field_id IS NOT NULL AND NEW.method <> 'human' THEN
            SELECT status INTO v_status FROM extraction_field WHERE id = NEW.supersedes_field_id;
            IF v_status = 'found' THEN
                RAISE EXCEPTION 'extraction_field_superseded: a machine row replaces only a row not found or illegible' USING ERRCODE = 'check_violation';
            END IF;
        END IF;
    ELSIF TG_TABLE_NAME = 'extraction_confirmation' THEN
        SELECT method INTO v_method FROM extraction_field WHERE id = NEW.extraction_field_id;
        IF v_method = 'vision_unaligned' OR EXISTS (SELECT 1 FROM extraction_field g WHERE g.supersedes_field_id = NEW.extraction_field_id) THEN
            RAISE EXCEPTION 'extraction_field_superseded: only a current row that is not an unaligned vision value is confirmed' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_extraction_field_append BEFORE INSERT ON extraction_field FOR EACH ROW EXECUTE FUNCTION extraction_check_append();
CREATE TRIGGER trg_extraction_rule_run_append BEFORE INSERT ON extraction_rule_run FOR EACH ROW EXECUTE FUNCTION extraction_check_append();
CREATE TRIGGER trg_extraction_confirmation_append BEFORE INSERT ON extraction_confirmation FOR EACH ROW EXECUTE FUNCTION extraction_check_append();
-- Extraction states (rule 7): pending -> extracted | needs_review | canceled (the system, rule 25); extracted -> needs_review
-- | verified | canceled; needs_review -> verified | canceled; verified and canceled are final. Identity columns never change;
-- the flags and the signature state change only while the record is pending (the recording command, rule 4); an extracted
-- record never rests on a vision reader.
CREATE FUNCTION document_extraction_check_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'document_extraction rows are never deleted' USING ERRCODE = 'restrict_violation';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.company_id, NEW.attachment_id, NEW.purpose, NEW.attachment_sha256, NEW.requested_by_user_id, NEW.data_label)
           IS DISTINCT FROM (OLD.company_id, OLD.attachment_id, OLD.purpose, OLD.attachment_sha256, OLD.requested_by_user_id, OLD.data_label) THEN
            RAISE EXCEPTION 'document_extraction identity and label never change' USING ERRCODE = 'restrict_violation';
        END IF;
        IF OLD.state IN ('verified', 'canceled') THEN
            RAISE EXCEPTION 'extraction_not_reviewable' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.state <> OLD.state AND NOT (
               (OLD.state = 'pending' AND NEW.state IN ('extracted', 'needs_review', 'canceled'))
            OR (OLD.state = 'extracted' AND NEW.state IN ('needs_review', 'verified', 'canceled'))
            OR (OLD.state = 'needs_review' AND NEW.state IN ('verified', 'canceled'))) THEN
            RAISE EXCEPTION 'document_extraction state % cannot become %', OLD.state, NEW.state USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.state <> 'pending' AND (NEW.hidden_text_suspected, NEW.injection_signal, NEW.is_full_review_required, NEW.signature_state)
           IS DISTINCT FROM (OLD.hidden_text_suspected, OLD.injection_signal, OLD.is_full_review_required, OLD.signature_state) THEN
            RAISE EXCEPTION 'extraction flags and signature state are set only while pending' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF NEW.state = 'extracted' AND EXISTS (SELECT 1 FROM document_reader r WHERE r.id = NEW.final_reader_id AND r.rung = 'vision') THEN
        RAISE EXCEPTION 'an extracted record never rests on a vision reader' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_document_extraction_change BEFORE INSERT OR UPDATE OR DELETE ON document_extraction
    FOR EACH ROW EXECUTE FUNCTION document_extraction_check_change();

-- ===== Row-level security (ADR-0017 rule 19; ADR-0022 rule 8) =====
DO $$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY['document_extraction', 'extraction_word', 'extraction_field', 'extraction_rule_run', 'extraction_confirmation',
                                   'extraction_result_link', 'extraction_mapping_rule', 'data_processing_permission'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', v_table);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', v_table);
        EXECUTE format('CREATE POLICY company_policy ON %I USING (company_id::text = current_setting(''nativeflows.company_id'', true))', v_table);
        EXECUTE format('CREATE POLICY company_ids_policy ON %I FOR SELECT USING (company_id::text = ANY (string_to_array(current_setting(''nativeflows.company_ids'', true), '','')))', v_table);
    END LOOP;
END
$$;
