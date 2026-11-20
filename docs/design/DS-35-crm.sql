-- DS-35 minimal CRM: DDL draft for ADR-0052 (on the foundation of ADR-0019). PostgreSQL 18.
-- Loaded after DS-20-master-data.sql and together with DS-06 in the design lab
-- (docs/reviews/2026-11-14-design-validation, t11_crm.py). The ADRs win if this file disagrees.
-- Conventions as DS-20: tables in schema nativeflows, keys inline (migrations name them by the MetaData naming convention,
-- ADR-0004 rule 15), UUIDv7 IDs from context.new_id or the client, no ID defaults, recorded_at on every row (ADR-0007 rule 9).
-- Every table carries company_id, FORCE ROW LEVEL SECURITY and the generated company policy (ADR-0017 rule 19),
-- except the global catalog public_mail_domain. The lab checks this list (ADR-0052 rule 3).
-- References inside a company are composite on (company_id, id). DS-20's contact has UNIQUE (company_id, id) and
-- UNIQUE (company_id, partner_id, id), so a row naming a partner and a contact keeps the contact inside that partner.
-- Tables are in dependency order: each follows the tables it references, so the file loads top to bottom (rule 3).
-- Owner module: crm, except personal_data_processing_log [audit] (ADR-0052 rule 26).
-- Referenced tables defined elsewhere: document (documents, ADR-0009 rule 1, with partner_id, document_date and
-- UNIQUE (company_id, id) by ADR-0052 rule 18), user_account (DS-15), company, partner and contact (DS-20).
-- attachment (DS-36) and agent_run (DS-32) are referenced by ID without a foreign key until their DDL exists.
-- pg_trgm is installed (ADR-0022 rule 8). Data labels and untrusted fields: ADR-0052 rule 29.
-- Rules that need other rows (public domains, one purpose per message type, partner of a linked document, consent
-- at send) are enforced by commands and named in ADR-0052; the append-only rule of rule 7 is held by a trigger.
-- The final-state immutability of the two document types (outbound_message, data_subject_request; ADR-0009 rule 14,
-- with the non-final but frozen state sending of ADR-0052 rule 27) is the documents module's generic trigger; their
-- headers and versions hold no personal text, which lives in the *_content tables that erasure blanks (rules 24, 27).

-- ===== E-mail domains [crm] (ADR-0052 rule 5) =====
CREATE TABLE public_mail_domain (                          -- global catalog: core rows plus the active package's rows
    domain        text PRIMARY KEY CONSTRAINT ck_public_mail_domain_domain CHECK (domain ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$'),
    source        text NOT NULL CONSTRAINT ck_public_mail_domain_source CHECK (source IN ('core', 'package')),
    package_code  text,
    recorded_at   timestamptz NOT NULL,
    CONSTRAINT ck_public_mail_domain_package CHECK ((source = 'package') = (package_code IS NOT NULL))
);
CREATE TABLE partner_email_domain (                        -- a public mail domain is refused by the command (public_mail_domain)
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL,
    partner_id   uuid NOT NULL,
    domain       text CONSTRAINT ck_partner_email_domain_domain CHECK (domain ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$'),
    is_active    boolean NOT NULL DEFAULT true,
    erased_at    timestamptz,                                -- an individual partner's domain is personal (rules 25, 29)
    recorded_at  timestamptz NOT NULL,
    UNIQUE (partner_id, domain),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_partner_email_domain_erased CHECK ((domain IS NOT NULL OR erased_at IS NOT NULL) AND (erased_at IS NULL OR NOT is_active))
);
-- Not unique on the domain alone: a domain shared by two partners is accepted with email_domain_shared and never matches.
CREATE INDEX ix_partner_email_domain_company_id_domain ON partner_email_domain (company_id, domain) WHERE is_active;

-- ===== Mailboxes [crm] (ADR-0052 rules 11-12) =====
CREATE TABLE mailbox (
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL REFERENCES company (id),
    code                        text NOT NULL,
    name                        text NOT NULL,
    email_address               text NOT NULL,
    connector_kind              text NOT NULL CONSTRAINT ck_mailbox_connector_kind CHECK (connector_kind IN ('imap')),
    connector_settings          jsonb NOT NULL,                -- host, port, folder, submission server: never a secret
    credential_ref              text NOT NULL,                 -- key in the installation secret store (DS-37)
    authserv_id                 text NOT NULL,                 -- whose Authentication-Results are trusted (rule 14)
    is_authentication_verified  boolean NOT NULL DEFAULT false, -- the probe of rule 11 passed; until then nothing authenticates
    authentication_probe_result text CONSTRAINT ck_mailbox_authentication_probe_result
                                    CHECK (authentication_probe_result IN ('passed', 'probe_no_field', 'forged_field_kept', 'field_not_topmost', 'transport_error')),
    authentication_checked_at   timestamptz,
    owner_user_id               uuid NOT NULL REFERENCES user_account (id),   -- owner of mailbox_unreachable (subject_owner)
    is_intake_enabled           boolean NOT NULL DEFAULT true,
    is_sending_enabled          boolean NOT NULL DEFAULT false,
    document_intake_purpose     text CONSTRAINT ck_mailbox_document_intake_purpose CHECK (document_intake_purpose IN ('supplier_invoice', 'inquiry_lines', 'shop_floor_report')),   -- attachments go to the reader ladder (ADR-0057 rule 25)
    document_intake_quarantine_limit integer NOT NULL DEFAULT 20 CONSTRAINT ck_mailbox_document_intake_quarantine_limit CHECK (document_intake_quarantine_limit > 0),   -- quarantined records of messages not matched to a partner, per receipt date; past it, extracted but not imported (ADR-0057 rule 25)
    intake_cursor               jsonb,                         -- provider position, e.g. IMAP UIDVALIDITY and last UID
    last_intake_at              timestamptz,
    consecutive_failure_count   integer NOT NULL DEFAULT 0 CONSTRAINT ck_mailbox_consecutive_failure_count CHECK (consecutive_failure_count >= 0),
    is_active                   boolean NOT NULL DEFAULT true,
    version                     integer NOT NULL DEFAULT 1,
    recorded_at                 timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, email_address),
    UNIQUE (company_id, id),
    -- only a completed negative probe clears the flag; a transport error keeps the last state (rule 11)
    CONSTRAINT ck_mailbox_verified CHECK (NOT is_authentication_verified OR (authentication_checked_at IS NOT NULL AND coalesce(authentication_probe_result IN ('passed', 'transport_error'), false)))
);

-- ===== Interactions [crm] (ADR-0052 rules 6-10) =====
CREATE TABLE interaction (                                 -- append-only except matching and erasure (rule 7)
    id                uuid PRIMARY KEY,
    company_id        uuid NOT NULL REFERENCES company (id),
    partner_id        uuid,
    contact_id        uuid,
    kind              text NOT NULL CONSTRAINT ck_interaction_kind CHECK (kind IN ('email', 'call', 'meeting', 'chat', 'note', 'task')),
    direction         text NOT NULL CONSTRAINT ck_interaction_direction_value CHECK (direction IN ('inbound', 'outbound', 'internal')),
    occurred_at       timestamptz NOT NULL,
    subject           text,
    is_untrusted      boolean NOT NULL,
    match_method      text CONSTRAINT ck_interaction_match_method CHECK (match_method IN ('reply', 'contact_email', 'domain', 'entered', 'confirmed')),
    matched_at        timestamptz,
    correction_of_id  uuid,
    due_date          date,                                  -- tasks only (rule 19)
    assignee_user_id  uuid REFERENCES user_account (id),     -- tasks only
    erased_at         timestamptz,
    version           integer NOT NULL DEFAULT 1,
    recorded_at       timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, partner_id),                     -- links carry the interaction's partner (rule 9)
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT fk_interaction_contact FOREIGN KEY (company_id, partner_id, contact_id) REFERENCES contact (company_id, partner_id, id),
    FOREIGN KEY (company_id, correction_of_id) REFERENCES interaction (company_id, id),
    CONSTRAINT ck_interaction_direction CHECK ((kind IN ('note', 'task')) = (direction = 'internal')),
    CONSTRAINT ck_interaction_contact_partner CHECK (contact_id IS NULL OR partner_id IS NOT NULL),
    CONSTRAINT ck_interaction_matched CHECK ((partner_id IS NULL) = (match_method IS NULL) AND (partner_id IS NULL) = (matched_at IS NULL)),
    CONSTRAINT ck_interaction_automatic_match CHECK (match_method NOT IN ('reply', 'contact_email', 'domain') OR (kind = 'email' AND direction = 'inbound')),
    CONSTRAINT ck_interaction_task CHECK ((kind = 'task') = (due_date IS NOT NULL) AND (kind = 'task') = (assignee_user_id IS NOT NULL)),
    CONSTRAINT ck_interaction_inbound_email_untrusted CHECK (is_untrusted OR NOT (kind = 'email' AND direction = 'inbound')),
    CONSTRAINT ck_interaction_not_own_correction CHECK (correction_of_id IS NULL OR correction_of_id <> id)
);
CREATE INDEX ix_interaction_company_id_partner_id_occurred_at ON interaction (company_id, partner_id, occurred_at DESC) WHERE partner_id IS NOT NULL;
CREATE INDEX ix_interaction_company_id_occurred_at ON interaction (company_id, occurred_at) WHERE partner_id IS NULL;
CREATE TABLE interaction_content (                         -- personal; untrusted when the interaction is
    interaction_id  uuid PRIMARY KEY,
    company_id      uuid NOT NULL,
    body_text       text,                                    -- plain text; HTML is converted by a sanitizer, never stored
    erased_at       timestamptz,
    recorded_at     timestamptz NOT NULL,
    FOREIGN KEY (company_id, interaction_id) REFERENCES interaction (company_id, id)
);
CREATE TABLE interaction_participant (
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL,
    interaction_id   uuid NOT NULL,
    role             text NOT NULL CONSTRAINT ck_interaction_participant_role CHECK (role IN ('from', 'to', 'cc', 'bcc', 'reply_to', 'attendee')),
    email_address    text,
    display_name     text,
    contact_id       uuid,
    user_account_id  uuid REFERENCES user_account (id),
    erased_at        timestamptz,
    recorded_at      timestamptz NOT NULL,
    FOREIGN KEY (company_id, interaction_id) REFERENCES interaction (company_id, id),
    FOREIGN KEY (company_id, contact_id) REFERENCES contact (company_id, id),
    CONSTRAINT ck_interaction_participant_identity CHECK (erased_at IS NOT NULL OR num_nonnulls(email_address, contact_id, user_account_id) > 0)
);
CREATE INDEX ix_interaction_participant_interaction_id ON interaction_participant (interaction_id);
CREATE INDEX ix_interaction_participant_company_id_email_address ON interaction_participant (company_id, email_address) WHERE email_address IS NOT NULL;

-- ===== Inbound messages [crm] (ADR-0052 rules 13-14) =====
CREATE TABLE inbound_message (                             -- append-only except erasure (rule 7)
    id                               uuid PRIMARY KEY,
    company_id                       uuid NOT NULL,
    mailbox_id                       uuid NOT NULL,
    provider_message_key             text NOT NULL,          -- IMAP: UIDVALIDITY and UID
    message_id                       text,                   -- raw Message-ID: personal, untrusted, blanked by erasure
    message_id_hash                  text CONSTRAINT ck_inbound_message_message_id_hash CHECK (message_id_hash ~ '^[0-9a-f]{64}$'),
    content_hash                     text NOT NULL CONSTRAINT ck_inbound_message_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    referenced_message_id_hashes     text[] NOT NULL DEFAULT '{}',   -- In-Reply-To and References, hashed only
    sender_address                   text,                   -- the single RFC 5322 From mailbox, normalized (rule 14)
    sender_display_name              text,
    sender_domain                    text,
    sender_authentication            jsonb NOT NULL,         -- parsed results of the trusted field and the reason; personal
    is_sender_authenticated          boolean NOT NULL,
    received_at                      timestamptz NOT NULL,   -- the provider's receive time
    raw_attachment_id                uuid,                   -- the raw message as an attachment (DS-36)
    parse_notes                      jsonb NOT NULL DEFAULT '[]',
    interaction_id                   uuid NOT NULL,
    duplicate_of_inbound_message_id  uuid,
    is_own_message                   boolean NOT NULL DEFAULT false,
    -- canonical: neither a copy nor an own message; a copy may only point to a canonical row (rule 13)
    is_canonical                     boolean GENERATED ALWAYS AS (duplicate_of_inbound_message_id IS NULL AND NOT is_own_message) STORED,
    duplicate_target_canonical       boolean GENERATED ALWAYS AS (CASE WHEN duplicate_of_inbound_message_id IS NOT NULL THEN true END) STORED,
    erased_at                        timestamptz,
    recorded_at                      timestamptz NOT NULL,
    UNIQUE (company_id, mailbox_id, provider_message_key),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, interaction_id, message_id_hash, content_hash, is_canonical),
    FOREIGN KEY (company_id, mailbox_id) REFERENCES mailbox (company_id, id),
    FOREIGN KEY (company_id, interaction_id) REFERENCES interaction (company_id, id),
    -- a copy has the same hashes and the same interaction as the canonical row it points to (ADR-0052 rule 13)
    CONSTRAINT fk_inbound_message_duplicate FOREIGN KEY (company_id, duplicate_of_inbound_message_id, interaction_id, message_id_hash, content_hash, duplicate_target_canonical)
        REFERENCES inbound_message (company_id, id, interaction_id, message_id_hash, content_hash, is_canonical),
    CONSTRAINT ck_inbound_message_not_own_duplicate CHECK (duplicate_of_inbound_message_id IS NULL OR duplicate_of_inbound_message_id <> id),
    CONSTRAINT ck_inbound_message_duplicate_has_message_id CHECK (duplicate_of_inbound_message_id IS NULL OR message_id_hash IS NOT NULL),
    CONSTRAINT ck_inbound_message_own_not_duplicate CHECK (NOT (is_own_message AND duplicate_of_inbound_message_id IS NOT NULL))
);
-- The natural key of ADR-0030 rule 10: one canonical row per Message-ID and content; copies and own messages point elsewhere.
CREATE UNIQUE INDEX ux_inbound_message_natural_key ON inbound_message (company_id, message_id_hash, content_hash)
    WHERE is_canonical AND message_id_hash IS NOT NULL;
CREATE INDEX ix_inbound_message_interaction_id ON inbound_message (interaction_id);
CREATE INDEX ix_inbound_message_company_id_sender_address ON inbound_message (company_id, sender_address) WHERE sender_address IS NOT NULL;
CREATE TABLE interaction_match_candidate (                 -- evidence for a person, never a match; replaced on UnmatchInteraction (rule 15)
    company_id      uuid NOT NULL,
    interaction_id  uuid NOT NULL,
    partner_id      uuid NOT NULL,
    reason          text NOT NULL CONSTRAINT ck_interaction_match_candidate_reason CHECK (reason IN ('several_partners', 'contact_email_unauthenticated', 'domain_unauthenticated', 'tax_id_in_content', 'name_similarity')),
    score           numeric(5,4) CONSTRAINT ck_interaction_match_candidate_score CHECK (score IS NULL OR score BETWEEN 0 AND 1),
    rank            smallint NOT NULL CONSTRAINT ck_interaction_match_candidate_rank CHECK (rank BETWEEN 1 AND 10),
    recorded_at     timestamptz NOT NULL,
    PRIMARY KEY (interaction_id, partner_id),                -- one row per partner, with its best reason
    UNIQUE (interaction_id, rank),                           -- order: reason as listed, score descending, partner code
    FOREIGN KEY (company_id, interaction_id) REFERENCES interaction (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id)
);

-- ===== Complaints and links [crm] (ADR-0052 rules 9, 20-21) =====
CREATE TABLE complaint (
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL REFERENCES company (id),
    partner_id             uuid NOT NULL,
    contact_id             uuid,
    origin_interaction_id  uuid,
    category               text NOT NULL CONSTRAINT ck_complaint_category CHECK (category IN ('delivery', 'quality', 'billing', 'service', 'other')),
    title                  text,
    is_title_untrusted     boolean NOT NULL DEFAULT false,
    state                  text NOT NULL DEFAULT 'open' CONSTRAINT ck_complaint_state CHECK (state IN ('open', 'closed')),
    opened_at              timestamptz NOT NULL,
    closed_at              timestamptz,
    resolution_note        text,
    erased_at              timestamptz,
    version                integer NOT NULL DEFAULT 1,
    recorded_at            timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, partner_id),                     -- links carry the complaint's partner (rule 9)
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT fk_complaint_contact FOREIGN KEY (company_id, partner_id, contact_id) REFERENCES contact (company_id, partner_id, id),
    FOREIGN KEY (company_id, origin_interaction_id) REFERENCES interaction (company_id, id),
    CONSTRAINT ck_complaint_closed CHECK ((state = 'closed') = (closed_at IS NOT NULL)),
    CONSTRAINT ck_complaint_closed_after_opened CHECK (closed_at IS NULL OR closed_at >= opened_at),
    CONSTRAINT ck_complaint_title CHECK (title IS NOT NULL OR erased_at IS NOT NULL)
);
CREATE INDEX ix_complaint_company_id_partner_id ON complaint (company_id, partner_id) WHERE state = 'open';
CREATE TABLE complaint_document (                          -- links, never copies (rule 9); the document's partner is the command's check
    company_id    uuid NOT NULL,
    complaint_id  uuid NOT NULL,
    partner_id    uuid NOT NULL,                             -- the complaint's partner
    document_id   uuid NOT NULL,
    recorded_at   timestamptz NOT NULL,
    PRIMARY KEY (complaint_id, document_id),
    CONSTRAINT fk_complaint_document_complaint FOREIGN KEY (company_id, complaint_id, partner_id) REFERENCES complaint (company_id, id, partner_id),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id)
);
CREATE INDEX ix_complaint_document_document_id ON complaint_document (document_id);
CREATE TABLE interaction_link (                            -- links, never copies (rule 9); only from a matched interaction
    id              uuid PRIMARY KEY,
    company_id      uuid NOT NULL,
    interaction_id  uuid NOT NULL,
    partner_id      uuid NOT NULL,                           -- the interaction's partner; a complaint target must have it too
    document_id     uuid,
    complaint_id    uuid,
    recorded_at     timestamptz NOT NULL,
    UNIQUE NULLS NOT DISTINCT (interaction_id, document_id, complaint_id),
    -- the interaction is matched to this partner; UnmatchInteraction and MatchInteraction cannot move it under a link
    CONSTRAINT fk_interaction_link_interaction FOREIGN KEY (company_id, interaction_id, partner_id) REFERENCES interaction (company_id, id, partner_id),
    FOREIGN KEY (company_id, document_id) REFERENCES document (company_id, id),
    CONSTRAINT fk_interaction_link_complaint FOREIGN KEY (company_id, complaint_id, partner_id) REFERENCES complaint (company_id, id, partner_id),
    CONSTRAINT ck_interaction_link_target CHECK (num_nonnulls(document_id, complaint_id) = 1)
);
CREATE INDEX ix_interaction_link_document_id ON interaction_link (document_id) WHERE document_id IS NOT NULL;

-- ===== Consent and data subjects [crm] (ADR-0052 rules 22-25) =====
CREATE TABLE processing_purpose (                          -- company data seeded from the package; basis as in DS-20
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    code                 text NOT NULL,
    name                 text NOT NULL,
    is_consent_required  boolean NOT NULL,
    message_types        text[] NOT NULL DEFAULT '{}' CONSTRAINT ck_processing_purpose_message_types
                             CHECK (message_types <@ ARRAY['reply', 'document', 'payment_reminder', 'follow_up', 'marketing', 'general']::text[]),
    basis                jsonb NOT NULL,                     -- set by the command; {"source": "core_template"} for the core template (rule 22)
    is_active            boolean NOT NULL DEFAULT true,
    recorded_at          timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
CREATE TABLE processing_basis (                            -- append-only; ended_at and end_reason set once (rule 7)
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    contact_id               uuid,
    partner_id               uuid,                           -- an individual, sole proprietorship or employee partner (command check)
    processing_purpose_id    uuid NOT NULL,
    lawful_basis             text NOT NULL CONSTRAINT ck_processing_basis_lawful_basis CHECK (lawful_basis IN ('contract', 'legal_obligation', 'consent')),
    started_at               timestamptz NOT NULL,
    ended_at                 timestamptz,
    end_reason               text CONSTRAINT ck_processing_basis_end_reason CHECK (end_reason IN ('withdrawn', 'purpose_ended', 'erased')),
    evidence_interaction_id  uuid,
    recorded_at              timestamptz NOT NULL,
    FOREIGN KEY (company_id, contact_id) REFERENCES contact (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, processing_purpose_id) REFERENCES processing_purpose (company_id, id),
    FOREIGN KEY (company_id, evidence_interaction_id) REFERENCES interaction (company_id, id),
    CONSTRAINT ck_processing_basis_subject CHECK (num_nonnulls(contact_id, partner_id) = 1),
    CONSTRAINT ck_processing_basis_consent_evidence CHECK (lawful_basis <> 'consent' OR evidence_interaction_id IS NOT NULL),
    CONSTRAINT ck_processing_basis_end CHECK ((ended_at IS NULL) = (end_reason IS NULL) AND (ended_at IS NULL OR ended_at >= started_at))
);
-- One current basis per subject, purpose and lawful basis.
CREATE UNIQUE INDEX ux_processing_basis_current ON processing_basis (company_id, processing_purpose_id, lawful_basis, contact_id, partner_id) NULLS NOT DISTINCT
    WHERE ended_at IS NULL;
CREATE TABLE data_subject_request_content (                -- personal text of a request, outside the header and the version (rule 24)
    company_id               uuid NOT NULL,
    data_subject_request_id  uuid NOT NULL,
    content_hash             text NOT NULL CONSTRAINT ck_data_subject_request_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    content_salt             text CONSTRAINT ck_data_subject_request_content_salt CHECK (content_salt ~ '^[0-9a-f]{32}$'),   -- random; in the hash; blanked by erasure
    requester_name           text,
    requester_email          text,
    requester_phone          text,
    outcome_note             text,
    identity_proof_hash      text CONSTRAINT ck_data_subject_request_content_proof CHECK (identity_proof_hash ~ '^[0-9a-f]{64}$'),   -- kept after erasure
    erased_at                timestamptz,
    recorded_at              timestamptz NOT NULL,
    PRIMARY KEY (company_id, data_subject_request_id, content_hash),
    CONSTRAINT ck_data_subject_request_content_salt_kept CHECK (content_salt IS NOT NULL OR erased_at IS NOT NULL),
    FOREIGN KEY (company_id, data_subject_request_id) REFERENCES document (company_id, id)
);
CREATE TABLE data_subject_request (                        -- typed header of a non-posting document type (ADR-0009 rule 1); no personal text
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    request_kind           text NOT NULL CONSTRAINT ck_data_subject_request_kind CHECK (request_kind IN ('access', 'correction', 'deletion')),
    contact_id             uuid,
    partner_id             uuid,
    origin_interaction_id  uuid,
    due_date               date NOT NULL,                    -- package rule, flagged; core default 30 calendar days (rule 24)
    content_hash           text NOT NULL,
    recorded_at            timestamptz NOT NULL,
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    CONSTRAINT fk_data_subject_request_content FOREIGN KEY (company_id, id, content_hash)
        REFERENCES data_subject_request_content (company_id, data_subject_request_id, content_hash),
    FOREIGN KEY (company_id, contact_id) REFERENCES contact (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, origin_interaction_id) REFERENCES interaction (company_id, id),
    CONSTRAINT ck_data_subject_request_subject CHECK (num_nonnulls(contact_id, partner_id) <= 1)
);

-- ===== Outgoing messages [crm] (ADR-0052 rules 27-28) =====
CREATE TABLE outbound_message_content (                    -- subject and body, outside the header and the version (rule 27)
    company_id           uuid NOT NULL,
    outbound_message_id  uuid NOT NULL,
    content_hash         text NOT NULL CONSTRAINT ck_outbound_message_content_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    content_salt         text CONSTRAINT ck_outbound_message_content_salt CHECK (content_salt ~ '^[0-9a-f]{32}$'),   -- random; in the hash; blanked by erasure
    subject              text,
    body_text            text,
    erased_at            timestamptz,
    recorded_at          timestamptz NOT NULL,
    PRIMARY KEY (company_id, outbound_message_id, content_hash),
    CONSTRAINT ck_outbound_message_content_salt_kept CHECK (content_salt IS NOT NULL OR erased_at IS NOT NULL),
    FOREIGN KEY (company_id, outbound_message_id) REFERENCES document (company_id, id)
);
CREATE TABLE outbound_message (                            -- typed header of a non-posting document type (ADR-0009 rule 1); no personal text
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL,
    mailbox_id                  uuid NOT NULL,
    partner_id                  uuid NOT NULL,
    message_type                text NOT NULL CONSTRAINT ck_outbound_message_message_type
                                    CHECK (message_type IN ('reply', 'document', 'payment_reminder', 'follow_up', 'marketing', 'general')),
    content_hash                text NOT NULL,
    in_reply_to_interaction_id  uuid,
    message_id                  text NOT NULL,               -- <UUIDv7@mailbox domain>, made at Create and kept on every attempt
    message_id_hash             text NOT NULL CONSTRAINT ck_outbound_message_message_id_hash CHECK (message_id_hash ~ '^[0-9a-f]{64}$'),
    recorded_at                 timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, partner_id),
    UNIQUE (company_id, message_id_hash),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    CONSTRAINT fk_outbound_message_content FOREIGN KEY (company_id, id, content_hash)
        REFERENCES outbound_message_content (company_id, outbound_message_id, content_hash),
    FOREIGN KEY (company_id, mailbox_id) REFERENCES mailbox (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, in_reply_to_interaction_id) REFERENCES interaction (company_id, id)
);
CREATE TABLE outbound_message_recipient (                  -- only contacts of the message's partner, held by the two composite keys
    company_id           uuid NOT NULL,
    outbound_message_id  uuid NOT NULL,
    partner_id           uuid NOT NULL,
    contact_id           uuid NOT NULL,
    role                 text NOT NULL CONSTRAINT ck_outbound_message_recipient_role CHECK (role IN ('to', 'cc', 'bcc')),
    recorded_at          timestamptz NOT NULL,
    PRIMARY KEY (outbound_message_id, contact_id),
    CONSTRAINT fk_outbound_message_recipient_message FOREIGN KEY (company_id, outbound_message_id, partner_id)
        REFERENCES outbound_message (company_id, id, partner_id),
    CONSTRAINT fk_outbound_message_recipient_contact FOREIGN KEY (company_id, partner_id, contact_id)
        REFERENCES contact (company_id, partner_id, id)
);
CREATE TABLE outbound_message_delivery (                   -- late data of ADR-0009 rule 14: one row per attempt (rule 28)
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    outbound_message_id  uuid NOT NULL,
    attempt_number       smallint NOT NULL CONSTRAINT ck_outbound_message_delivery_attempt CHECK (attempt_number >= 1),
    requested_at         timestamptz NOT NULL,
    outcome              text CONSTRAINT ck_outbound_message_delivery_outcome CHECK (outcome IN ('sent', 'failed', 'unknown')),   -- null while in flight
    outcome_at           timestamptz,
    sent_at              timestamptz,
    sent_content_hash    text CONSTRAINT ck_outbound_message_delivery_sent_hash CHECK (sent_content_hash ~ '^[0-9a-f]{64}$'),   -- rule 13's own messages
    interaction_id       uuid,                                -- the outbound interaction recorded when sent
    failure_reason       text,                                -- personal: server replies may name addresses; blanked by erasure
    erased_at            timestamptz,
    recorded_at          timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (outbound_message_id, attempt_number),
    FOREIGN KEY (company_id, outbound_message_id) REFERENCES outbound_message (company_id, id),
    FOREIGN KEY (company_id, interaction_id) REFERENCES interaction (company_id, id),
    CONSTRAINT ck_outbound_message_delivery_outcome_at CHECK ((outcome IS NULL) = (outcome_at IS NULL)),
    CONSTRAINT ck_outbound_message_delivery_sent CHECK (
        (outcome IS NOT DISTINCT FROM 'sent') = (sent_at IS NOT NULL)
        AND (outcome IS NOT DISTINCT FROM 'sent') = (interaction_id IS NOT NULL)
        AND (outcome IS NOT DISTINCT FROM 'sent') = (sent_content_hash IS NOT NULL)),
    CONSTRAINT ck_outbound_message_delivery_failed CHECK (outcome IS DISTINCT FROM 'failed' OR failure_reason IS NOT NULL OR erased_at IS NOT NULL),
    CONSTRAINT ck_outbound_message_delivery_reason CHECK (failure_reason IS NULL OR coalesce(outcome IN ('failed', 'unknown'), false))
);
-- At most one attempt in flight and at most one sent attempt per message.
CREATE UNIQUE INDEX ux_outbound_message_delivery_open ON outbound_message_delivery (outbound_message_id) WHERE outcome IS NULL;
CREATE UNIQUE INDEX ux_outbound_message_delivery_sent ON outbound_message_delivery (outbound_message_id) WHERE outcome = 'sent';
CREATE TABLE outbound_message_delivery_recipient (         -- the addresses used by one attempt, copied at send; personal
    company_id                    uuid NOT NULL,
    outbound_message_delivery_id  uuid NOT NULL,
    contact_id                    uuid NOT NULL,
    role                          text NOT NULL CONSTRAINT ck_outbound_message_delivery_recipient_role CHECK (role IN ('to', 'cc', 'bcc')),
    email_address                 text,
    erased_at                     timestamptz,
    recorded_at                   timestamptz NOT NULL,
    PRIMARY KEY (outbound_message_delivery_id, contact_id),
    FOREIGN KEY (company_id, outbound_message_delivery_id) REFERENCES outbound_message_delivery (company_id, id),
    FOREIGN KEY (company_id, contact_id) REFERENCES contact (company_id, id),
    CONSTRAINT ck_outbound_message_delivery_recipient_address CHECK (email_address IS NOT NULL OR erased_at IS NOT NULL)
);
CREATE INDEX ix_outbound_message_delivery_recipient_contact_id ON outbound_message_delivery_recipient (contact_id);

-- ===== What the system learned, and search keys [crm] (ADR-0019 rules 18-20; ADR-0052 rules 17, 31) =====
CREATE TABLE interaction_summary (                         -- an agent's summary arrives by an approved change proposal (rule 31)
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    interaction_id     uuid,
    summary_text       text,
    agent_run_id       uuid,                                 -- the run that wrote it (DS-32)
    model              text,
    prompt_version     text,
    is_untrusted       boolean NOT NULL,
    edited_by_user_id  uuid REFERENCES user_account (id),
    erased_at          timestamptz,
    recorded_at        timestamptz NOT NULL,
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, interaction_id) REFERENCES interaction (company_id, id)
);
CREATE INDEX ix_interaction_summary_partner_id ON interaction_summary (partner_id);
CREATE TABLE partner_insight (                             -- computed by RunPartnerInsightComputation, with its method; deleted by erasure
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    partner_id         uuid NOT NULL,
    name               text NOT NULL,
    value              jsonb NOT NULL,
    method             text NOT NULL,
    computed_date      date NOT NULL,
    edited_by_user_id  uuid REFERENCES user_account (id),    -- set by UpdatePartnerInsight; the job keeps an edited value
    recorded_at        timestamptz NOT NULL,
    UNIQUE (partner_id, name),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id)
);
CREATE TABLE partner_tax_lookup (                          -- dated snapshot of a tax ID lookup; result is untrusted
    id            uuid PRIMARY KEY,
    company_id    uuid NOT NULL REFERENCES company (id),
    partner_id    uuid,
    tax_id        text,
    provider      text NOT NULL,
    looked_up_at  timestamptz NOT NULL,
    result        jsonb,
    erased_at     timestamptz,
    recorded_at   timestamptz NOT NULL,
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_partner_tax_lookup_tax_id CHECK (tax_id IS NOT NULL OR erased_at IS NOT NULL)
);
CREATE TABLE partner_search_key (                          -- kept by crm's consumer of partner and contact events; deleted by erasure
    partner_id         uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    normalized_name    text NOT NULL,
    normalized_tax_id  text,
    recorded_at        timestamptz NOT NULL,
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id)
);
CREATE INDEX ix_partner_search_key_normalized_name ON partner_search_key USING gin (normalized_name gin_trgm_ops);
CREATE INDEX ix_partner_search_key_company_id_normalized_tax_id ON partner_search_key (company_id, normalized_tax_id) WHERE normalized_tax_id IS NOT NULL;

-- ===== Processing log [audit] (ADR-0019 rule 11; ADR-0052 rule 26) =====
CREATE TABLE personal_data_processing_log (                -- IDs and field names only, never values; append-only (trigger below)
    id               uuid PRIMARY KEY,
    company_id       uuid NOT NULL REFERENCES company (id),
    processing_kind  text NOT NULL CONSTRAINT ck_personal_data_processing_log_kind CHECK (processing_kind IN ('llm_send', 'tax_id_lookup', 'export', 'erasure', 'retention')),   -- retention: ADR-0079 rule 9
    subject_table    text,
    subject_id       uuid,
    field_names      text[] NOT NULL DEFAULT '{}',
    recipient        text,                                   -- provider and model, or lookup provider
    agent_run_id     uuid,
    audit_record_id  uuid,
    recorded_at      timestamptz NOT NULL,
    CONSTRAINT ck_personal_data_processing_log_subject CHECK ((subject_table IS NULL) = (subject_id IS NULL))
);
CREATE INDEX ix_personal_data_processing_log_subject_id ON personal_data_processing_log (subject_id) WHERE subject_id IS NOT NULL;

-- ===== Append-only guard (ADR-0052 rule 7) =====
-- Arguments: columns that may change; columns that may be set once from null; columns only the erasure command may
-- change; optionally the column naming the row's document, for the content tables whose rows the generated Delete of a
-- draft removes (rule 7): the dispatcher sets nativeflows.document_delete_id to that document's ID for Delete alone, and the
-- delete is allowed only while the document is a draft. Generated columns follow their sources and are skipped. The dispatcher sets nativeflows.erasure_command_id only for
-- EraseDataSubject (ADR-0038 rule 4); DS-36 adds the check that it names an idempotency record of that command in the
-- same transaction.
CREATE FUNCTION crm_check_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_mutable       text[];
    v_set_once      text[];
    v_erasure_only  text[];
    v_generated     text[];
    v_is_erasing    boolean;
    v_old           jsonb;
    v_new           jsonb;
    v_key           text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF TG_NARGS > 3
           AND coalesce(current_setting('nativeflows.document_delete_id', true), '') = to_jsonb(OLD) ->> TG_ARGV[3]
           AND EXISTS (SELECT 1 FROM document d WHERE d.id = (to_jsonb(OLD) ->> TG_ARGV[3])::uuid AND d.state = 'draft') THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION '% rows are never deleted (ADR-0052 rule 7)', TG_TABLE_NAME USING ERRCODE = 'check_violation';
    END IF;
    v_mutable := TG_ARGV[0]::text[];
    v_set_once := TG_ARGV[1]::text[];
    v_erasure_only := TG_ARGV[2]::text[];
    SELECT coalesce(array_agg(attname::text), '{}') INTO v_generated
        FROM pg_attribute WHERE attrelid = TG_RELID AND attgenerated <> '' AND NOT attisdropped;
    v_is_erasing := coalesce(current_setting('nativeflows.erasure_command_id', true), '') <> '';
    v_old := to_jsonb(OLD);
    v_new := to_jsonb(NEW);
    FOR v_key IN SELECT jsonb_object_keys(v_new) LOOP
        CONTINUE WHEN (v_old -> v_key) IS NOT DISTINCT FROM (v_new -> v_key);
        CONTINUE WHEN v_key = ANY (v_generated);
        CONTINUE WHEN v_key = ANY (v_mutable);
        CONTINUE WHEN v_key = ANY (v_set_once) AND jsonb_typeof(v_old -> v_key) = 'null';
        CONTINUE WHEN v_key = ANY (v_erasure_only) AND v_is_erasing;
        RAISE EXCEPTION '%.% is append-only (ADR-0052 rule 7)', TG_TABLE_NAME, v_key USING ERRCODE = 'check_violation';
    END LOOP;
    RETURN NEW;
END
$$;
CREATE TRIGGER trg_interaction_append_only BEFORE UPDATE OR DELETE ON interaction FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{partner_id,contact_id,match_method,matched_at,version,recorded_at}', '{}', '{subject,erased_at}');
CREATE TRIGGER trg_interaction_content_append_only BEFORE UPDATE OR DELETE ON interaction_content FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{recorded_at}', '{}', '{body_text,erased_at}');
CREATE TRIGGER trg_interaction_participant_append_only BEFORE UPDATE OR DELETE ON interaction_participant FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{recorded_at}', '{contact_id}', '{email_address,display_name,erased_at}');
CREATE TRIGGER trg_inbound_message_append_only BEFORE UPDATE OR DELETE ON inbound_message FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{recorded_at}', '{}', '{message_id,sender_address,sender_display_name,sender_domain,sender_authentication,parse_notes,erased_at}');
CREATE TRIGGER trg_processing_basis_append_only BEFORE UPDATE OR DELETE ON processing_basis FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{recorded_at}', '{ended_at,end_reason}', '{}');
CREATE TRIGGER trg_data_subject_request_content_append_only BEFORE UPDATE OR DELETE ON data_subject_request_content FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{recorded_at}', '{}', '{requester_name,requester_email,requester_phone,outcome_note,content_salt,erased_at}', 'data_subject_request_id');
CREATE TRIGGER trg_outbound_message_content_append_only BEFORE UPDATE OR DELETE ON outbound_message_content FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{recorded_at}', '{}', '{subject,body_text,content_salt,erased_at}', 'outbound_message_id');
CREATE TRIGGER trg_outbound_message_delivery_append_only BEFORE UPDATE OR DELETE ON outbound_message_delivery FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{recorded_at}', '{outcome,outcome_at,sent_at,sent_content_hash,interaction_id,failure_reason}', '{failure_reason,erased_at}');
CREATE TRIGGER trg_outbound_message_delivery_recipient_append_only BEFORE UPDATE OR DELETE ON outbound_message_delivery_recipient FOR EACH ROW
    EXECUTE FUNCTION crm_check_append_only('{recorded_at}', '{}', '{email_address,erased_at}');

-- ===== Processing log guard [audit] (ADR-0052 rule 26) =====
CREATE FUNCTION audit_refuse_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% rows are never updated or deleted (ADR-0052 rule 26)', TG_TABLE_NAME USING ERRCODE = 'check_violation';
END
$$;
CREATE TRIGGER trg_personal_data_processing_log_append_only BEFORE UPDATE OR DELETE ON personal_data_processing_log FOR EACH ROW
    EXECUTE FUNCTION audit_refuse_change();
