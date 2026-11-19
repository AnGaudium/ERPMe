-- DS-15 access: DDL draft for ADR-0054 (users, roles and authorizations) and ADR-0055 (approval pools and stages).
-- PostgreSQL 18. Tested in the design lab (docs/reviews/2026-11-14-design-validation, t12_access.py). The ADRs win if
-- this file disagrees.
-- Loading: DS-20 references user_account, which this file defines, so the lab loader orders DS-20, DS-06 and this file
-- together, after 00_stubs.sql without its one-column user_account stub (the older scenarios keep the stub).
-- Conventions of DS-20: tables in schema `nativeflows`, domains in `types`; keys inline, named by the MetaData convention in
-- migrations (ADR-0004 rule 15); IDs are UUIDv7 from context.new_id (ADR-0006 rule 3), no defaults; references between
-- company tables are composite on (company_id, id); every table with company_id gets FORCE ROW LEVEL SECURITY and the
-- generated company policy (ADR-0017 rule 19; ADR-0022 rule 8).
-- Installation tables, without company_id and without a company policy, reached only through permissions.contract and
-- the authentication endpoints (ADR-0054 rule 1): user_account, user_session, credential_reset, integration_client,
-- integration_token, installation_role_assignment. The lab checks this list.
-- Core catalogs that are files, not tables (ADR-0054 rule 25): authorization-areas.csv, authorization-verb-levels.csv,
-- role-templates.csv, role-template-levels.csv, segregation-rules.csv. Tables keep their codes as text, validated by
-- commands against the catalog of the running registry.
-- Owner module per section in brackets (ADR-0022 rule 2).

-- ===== Users and credentials [permissions] (ADR-0054 rules 3-4; ADR-0017 rules 1-3, 7) =====
CREATE TABLE user_account (                                -- personal data (spec 17); installation data
    id                    uuid PRIMARY KEY,
    login                 text NOT NULL UNIQUE,
    display_name          text NOT NULL,
    email                 text,
    language              text NOT NULL,                       -- BCP 47
    time_zone             text,                                -- IANA name; null means the company's
    password_hash         text,                                -- argon2; null for a user who signs in only through OIDC
    totp_secret           bytea,                               -- encrypted at rest (DS-18)
    is_totp_enabled       boolean NOT NULL DEFAULT false,
    oidc_issuer           text,
    oidc_subject          text,
    is_active             boolean NOT NULL DEFAULT true,
    failed_sign_in_count  integer NOT NULL DEFAULT 0 CONSTRAINT ck_user_account_failed_sign_in_count CHECK (failed_sign_in_count >= 0),
    locked_until          timestamptz,
    password_changed_at   timestamptz,
    created_at            timestamptz NOT NULL,
    disabled_at           timestamptz,
    erased_at             timestamptz,                         -- personal fields replaced by a token (ADR-0019 rule 10)
    UNIQUE (oidc_issuer, oidc_subject),
    CONSTRAINT ck_user_account_login CHECK (login = lower(login) AND length(login) BETWEEN 3 AND 254),
    CONSTRAINT ck_user_account_oidc CHECK ((oidc_issuer IS NULL) = (oidc_subject IS NULL)),
    CONSTRAINT ck_user_account_credential CHECK (NOT is_active OR password_hash IS NOT NULL OR oidc_subject IS NOT NULL),
    CONSTRAINT ck_user_account_totp CHECK (NOT is_totp_enabled OR totp_secret IS NOT NULL),
    CONSTRAINT ck_user_account_disabled CHECK (is_active = (disabled_at IS NULL)),
    CONSTRAINT ck_user_account_erased CHECK (erased_at IS NULL OR NOT is_active)
);
CREATE TABLE user_session (                                -- server-side sessions (ADR-0017 rule 2; ADR-0040 rule 12)
    id                   uuid PRIMARY KEY,
    user_account_id      uuid NOT NULL REFERENCES user_account (id),
    token_hash           bytea NOT NULL UNIQUE,
    csrf_token_hash      bytea NOT NULL,
    created_at           timestamptz NOT NULL,
    last_seen_at         timestamptz NOT NULL,
    absolute_expires_at  timestamptz NOT NULL,
    revoked_at           timestamptz,
    CONSTRAINT ck_user_session_expiry CHECK (absolute_expires_at > created_at)
);
CREATE INDEX ix_user_session_user_account_id ON user_session (user_account_id);
CREATE TABLE credential_reset (                            -- one-time password reset token (ADR-0054 rule 4)
    id                  uuid PRIMARY KEY,
    user_account_id     uuid NOT NULL REFERENCES user_account (id),
    token_hash          bytea NOT NULL UNIQUE,
    created_by_user_id  uuid NOT NULL REFERENCES user_account (id),
    issued_in_company_id uuid REFERENCES company (id),       -- the issuing company; null for an operator (ADR-0054 rule 4)
    created_at          timestamptz NOT NULL,
    expires_at          timestamptz NOT NULL,
    used_at             timestamptz,
    voided_at           timestamptz,                         -- a newer reset was consumed, or the user became shared (rule 3)
    CONSTRAINT ck_credential_reset_expiry CHECK (expires_at > created_at AND expires_at <= created_at + interval '24 hours'),
    CONSTRAINT ck_credential_reset_once CHECK (used_at IS NULL OR voided_at IS NULL)
);
CREATE TABLE integration_client (                          -- ADR-0017 rules 1, 3, 13
    id                   uuid PRIMARY KEY,
    code                 text NOT NULL UNIQUE,
    name                 text NOT NULL,
    accountable_user_id  uuid NOT NULL REFERENCES user_account (id),
    is_active            boolean NOT NULL DEFAULT true
);
CREATE TABLE integration_token (                           -- stored only as a hash, at most one year (ADR-0017 rule 3)
    id                     uuid PRIMARY KEY,
    integration_client_id  uuid NOT NULL REFERENCES integration_client (id),
    token_hash             bytea NOT NULL UNIQUE,
    created_at             timestamptz NOT NULL,
    expires_at             timestamptz NOT NULL,
    revoked_at             timestamptz,
    CONSTRAINT ck_integration_token_expiry CHECK (expires_at > created_at AND expires_at <= created_at + interval '1 year')
);
CREATE TABLE installation_role_assignment (                -- ADR-0017 rule 7
    user_account_id     uuid NOT NULL REFERENCES user_account (id),
    role                text NOT NULL CONSTRAINT ck_installation_role_assignment_role CHECK (role IN ('operator')),
    granted_by_user_id  uuid REFERENCES user_account (id),     -- null only for the bootstrap operator
    granted_at          timestamptz NOT NULL,
    PRIMARY KEY (user_account_id, role)
);

-- ===== Organization for access [master_data] (ADR-0054 rule 6) =====
CREATE TABLE department (
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL REFERENCES company (id),
    code                text NOT NULL,
    name                text NOT NULL,
    parent_id           uuid,                                -- a tree; cycles refused by the command (department_cycle)
    manager_partner_id  uuid,                                -- an active employee (command check)
    is_active           boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, parent_id) REFERENCES department (company_id, id),
    FOREIGN KEY (company_id, manager_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_department_parent CHECK (parent_id IS DISTINCT FROM id)
);
CREATE TABLE team (
    id             uuid PRIMARY KEY,
    company_id     uuid NOT NULL REFERENCES company (id),
    code           text NOT NULL,
    name           text NOT NULL,
    department_id  uuid,
    is_active      boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, department_id) REFERENCES department (company_id, id)
);
CREATE TABLE team_member (                                 -- employee partners (command check: active employee role)
    company_id  uuid NOT NULL,
    team_id     uuid NOT NULL,
    partner_id  uuid NOT NULL,
    PRIMARY KEY (team_id, partner_id),
    FOREIGN KEY (company_id, team_id) REFERENCES team (company_id, id),
    FOREIGN KEY (company_id, partner_id) REFERENCES partner (company_id, id)
);
CREATE INDEX ix_team_member_partner_id ON team_member (partner_id);

-- ===== Roles and levels [permissions] (ADR-0054 rules 7-11) =====
CREATE TABLE role (
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL REFERENCES company (id),
    code                        text NOT NULL,
    name                        text NOT NULL,
    template_code               text,                          -- role-templates.csv; null for a role the company made
    basis                       jsonb NOT NULL,                -- template entry basis, or company_decision (ADR-0016 rule 12)
    is_totp_required            boolean NOT NULL DEFAULT false,
    suggested_owner_scope_read  text NOT NULL DEFAULT 'company',
    suggested_owner_scope_edit  text NOT NULL DEFAULT 'company',
    registry_version            text NOT NULL,                 -- the registry the stored expansion was computed from
    expansion_hash              text NOT NULL,                 -- SHA-256 of the stored sorted permission list (INV-220)
    is_active                   boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    CONSTRAINT ck_role_suggested_owner_scope CHECK ((suggested_owner_scope_read, suggested_owner_scope_edit) IN (
        ('own', 'own'), ('team', 'own'), ('team', 'team'), ('department', 'own'), ('department', 'department'),
        ('branch', 'own'), ('branch', 'team'), ('branch', 'department'), ('branch', 'branch'),
        ('company', 'own'), ('company', 'team'), ('company', 'department'), ('company', 'branch'), ('company', 'company')))
);
CREATE TABLE role_level (                                  -- one level per node of the area tree; inherited downward
    company_id          uuid NOT NULL,
    role_id             uuid NOT NULL,
    authorization_area  text NOT NULL,                       -- a node code of authorization-areas.csv
    level               text NOT NULL CONSTRAINT ck_role_level_level CHECK (level IN ('none', 'read', 'edit', 'post', 'full')),
    can_approve         boolean NOT NULL DEFAULT false,
    PRIMARY KEY (role_id, authorization_area),
    FOREIGN KEY (company_id, role_id) REFERENCES role (company_id, id),
    CONSTRAINT ck_role_level_approve CHECK (NOT can_approve OR level <> 'none')
);
CREATE TABLE role_permission (                             -- the expansion minus holds in force, read by the dispatcher (ADR-0054 rule 9)
    company_id  uuid NOT NULL,
    role_id     uuid NOT NULL,
    permission  text NOT NULL,                               -- a command type, query or capability name
    PRIMARY KEY (role_id, permission),
    FOREIGN KEY (company_id, role_id) REFERENCES role (company_id, id)
);
-- A permission an upgrade would have added but that would break segregation mode block or the small-company bound
-- (ADR-0054 rule 9). Holds in force (held, ignored) are left out of role_permission; an UpdateRole that changes levels
-- ends them (state ended).
CREATE TABLE role_permission_hold (
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL REFERENCES company (id),
    role_id             uuid NOT NULL,
    permission          text NOT NULL,
    reason              text NOT NULL CONSTRAINT ck_role_permission_hold_reason CHECK (reason IN ('segregation_conflict', 'small_company_mode_active')),
    registry_version    text NOT NULL,                       -- the upgrade that created it
    state               text NOT NULL DEFAULT 'held' CONSTRAINT ck_role_permission_hold_state CHECK (state IN ('held', 'granted', 'ignored', 'ended')),
    created_at          timestamptz NOT NULL,
    decided_by_user_id  uuid REFERENCES user_account (id),   -- null for held, and for ended by the system
    decided_at          timestamptz,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, role_id) REFERENCES role (company_id, id),
    CONSTRAINT ck_role_permission_hold_decided CHECK ((state = 'held') = (decided_at IS NULL)),
    CONSTRAINT ck_role_permission_hold_person CHECK (state NOT IN ('granted', 'ignored') OR decided_by_user_id IS NOT NULL)
);
CREATE UNIQUE INDEX ux_role_permission_hold_in_force ON role_permission_hold (role_id, permission) WHERE state IN ('held', 'ignored');

-- ===== Invitations [permissions] (ADR-0054 rule 3) =====
-- CreateUserAccount writes one per call. A new login is confirmed at once (is_new_account); an existing login stays
-- pending until its own user runs ConfirmUserInvitation. Display name and e-mail are what the company typed; the
-- company's queries show these, never the account's own data, while pending. ConfirmUserInvitation and the user's
-- CancelUserInvitation are company-scoped commands whose permission check is that the caller is user_account_id.
-- The invited user's pending list is a registered cross-company query; its nativeflows.company_ids come from a
-- security-definer function owned by a no-login role nativeflows_invitation, whose only policy here sees pending rows:
--   pending_invitation_companies(user_account_id uuid) RETURNS SETOF uuid  -- company IDs only; no role has BYPASSRLS
-- (the pattern of nativeflows_claim, ADR-0017 rule 19; role and function are created with the database roles, not here).
-- Pending invitations expire after the installation setting invitation_expiry_days (default 30).
CREATE TABLE user_invitation (
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL REFERENCES company (id),
    user_account_id     uuid NOT NULL REFERENCES user_account (id),
    login               text NOT NULL,
    display_name        text NOT NULL,                       -- as typed by the company
    email               text,                                -- as typed by the company
    is_new_account      boolean NOT NULL,
    state               text NOT NULL CONSTRAINT ck_user_invitation_state CHECK (state IN ('pending', 'confirmed', 'canceled', 'expired')),
    created_by_user_id  uuid NOT NULL REFERENCES user_account (id),
    created_at          timestamptz NOT NULL,
    expires_at          timestamptz,                         -- pending invitations only: created_at + invitation_expiry_days
    decided_by_user_id  uuid REFERENCES user_account (id),
    decided_at          timestamptz,
    UNIQUE (company_id, id),
    CONSTRAINT ck_user_invitation_expiry CHECK (is_new_account OR (expires_at IS NOT NULL AND expires_at > created_at)),
    CONSTRAINT ck_user_invitation_new CHECK (NOT is_new_account OR state = 'confirmed'),
    CONSTRAINT ck_user_invitation_decided CHECK ((state = 'pending') = (decided_at IS NULL)),
    -- an existing account's invitation is confirmed only by that account's own user (INV-231)
    CONSTRAINT ck_user_invitation_confirmed_by_user CHECK (state <> 'confirmed' OR is_new_account OR decided_by_user_id IS NOT DISTINCT FROM user_account_id)
);
CREATE UNIQUE INDEX ux_user_invitation_pending ON user_invitation (company_id, user_account_id) WHERE state = 'pending';

-- ===== Assignments and scopes [permissions] (ADR-0054 rules 12-16; ADR-0017 rules 6, 9-10, 13) =====
CREATE TABLE role_assignment (
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL REFERENCES company (id),
    role_id                uuid NOT NULL,
    principal_kind         text NOT NULL CONSTRAINT ck_role_assignment_principal_kind CHECK (principal_kind IN ('user', 'integration_client')),  -- agent types get no assignments (ADR-0054 rule 16)
    user_account_id        uuid REFERENCES user_account (id),
    integration_client_id  uuid REFERENCES integration_client (id),
    owner_scope_read       text,                               -- users only
    owner_scope_edit       text,
    field_classes          text[] NOT NULL DEFAULT '{}' CONSTRAINT ck_role_assignment_field_classes CHECK (field_classes <@ ARRAY['cost', 'margin']::text[]),
    valid_from             date NOT NULL,
    valid_to               date,                               -- inclusive; null is open (ADR-0027 rule 12)
    granted_by_user_id     uuid REFERENCES user_account (id),  -- null only for the bootstrap owner (ADR-0017 rule 7)
    user_invitation_id     uuid,                               -- in force only when null or confirmed (ADR-0054 rules 3, 12)
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, role_id) REFERENCES role (company_id, id),
    FOREIGN KEY (company_id, user_invitation_id) REFERENCES user_invitation (company_id, id),
    CONSTRAINT ck_role_assignment_invitation CHECK (user_invitation_id IS NULL OR principal_kind = 'user'),
    CONSTRAINT ck_role_assignment_principal CHECK (
        (principal_kind = 'user') = (user_account_id IS NOT NULL)
        AND (principal_kind = 'integration_client') = (integration_client_id IS NOT NULL)),
    CONSTRAINT ck_role_assignment_owner_scope CHECK (
        (principal_kind = 'user') = (owner_scope_read IS NOT NULL) AND (owner_scope_read IS NULL) = (owner_scope_edit IS NULL)),
    -- The edit scope is never wider than the read scope (ADR-0054 rule 13).
    CONSTRAINT ck_role_assignment_owner_scope_pair CHECK (owner_scope_read IS NULL OR (owner_scope_read, owner_scope_edit) IN (
        ('own', 'own'), ('team', 'own'), ('team', 'team'), ('department', 'own'), ('department', 'department'),
        ('branch', 'own'), ('branch', 'team'), ('branch', 'department'), ('branch', 'branch'),
        ('company', 'own'), ('company', 'team'), ('company', 'department'), ('company', 'branch'), ('company', 'company'))),
    CONSTRAINT ck_role_assignment_dates CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CONSTRAINT ck_role_assignment_not_self CHECK (user_account_id IS NULL OR granted_by_user_id IS NULL OR user_account_id <> granted_by_user_id)
);
CREATE INDEX ix_role_assignment_user_account_id ON role_assignment (user_account_id) WHERE user_account_id IS NOT NULL;
CREATE INDEX ix_role_assignment_role_id ON role_assignment (role_id);
-- Record scope: a branch or a warehouse per row; none means the whole company (ADR-0017 rule 9). Owner scope branch
-- needs at least one row and company none: a command rule and INV-221, since it spans rows.
CREATE TABLE role_assignment_scope (
    company_id          uuid NOT NULL,
    role_assignment_id  uuid NOT NULL,
    branch_id           uuid,
    warehouse_id        uuid,
    FOREIGN KEY (company_id, role_assignment_id) REFERENCES role_assignment (company_id, id),
    FOREIGN KEY (company_id, branch_id) REFERENCES branch (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT ck_role_assignment_scope_one CHECK ((branch_id IS NULL) <> (warehouse_id IS NULL))
);
CREATE UNIQUE INDEX ux_role_assignment_scope ON role_assignment_scope (role_assignment_id, branch_id, warehouse_id) NULLS NOT DISTINCT;

-- ===== Delegation [permissions] (ADR-0054 rule 21) =====
CREATE TABLE delegation (
    id                  uuid PRIMARY KEY,
    company_id          uuid NOT NULL REFERENCES company (id),
    delegator_user_id   uuid NOT NULL REFERENCES user_account (id),
    substitute_user_id  uuid NOT NULL REFERENCES user_account (id),   -- a user account, so never an agent
    kind                text NOT NULL CONSTRAINT ck_delegation_kind CHECK (kind IN ('approval')),   -- role_assignments dropped (ADR-0054 rule 21 note, 2026-11-19)
    start_date          date NOT NULL,
    end_date            date NOT NULL,                                -- inclusive; always time-bound
    reason              text NOT NULL,
    state               text NOT NULL DEFAULT 'active' CONSTRAINT ck_delegation_state CHECK (state IN ('active', 'canceled')),
    created_by_user_id  uuid NOT NULL REFERENCES user_account (id),
    UNIQUE (company_id, id),
    CONSTRAINT ck_delegation_not_self CHECK (delegator_user_id <> substitute_user_id),
    CONSTRAINT ck_delegation_dates CHECK (end_date >= start_date AND end_date - start_date <= 365)
);
CREATE INDEX ix_delegation_substitute_user_id ON delegation (substitute_user_id);

-- ===== Segregation of duties [permissions] (ADR-0054 rules 17-20) =====
CREATE TABLE company_segregation_rule (                    -- enablement of segregation-rules.csv rows
    company_id  uuid NOT NULL REFERENCES company (id),
    rule_code   text NOT NULL,
    is_enabled  boolean NOT NULL DEFAULT true,
    basis       jsonb NOT NULL,
    PRIMARY KEY (company_id, rule_code)
);
CREATE TABLE segregation_exception (                       -- small-company mode only; immutable (ADR-0054 rule 20)
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL REFERENCES company (id),
    kind                 text NOT NULL CONSTRAINT ck_segregation_exception_kind CHECK (kind IN ('pair', 'own_document_approval', 'own_agent_draft_approval', 'own_run_taint_clearance')),   -- ADR-0067 rules 16, 17 (proposed); command_type ClearTaint for own_run_taint_clearance
    rule_code            text,                                -- the pair's rule; null for the other kinds
    user_account_id      uuid NOT NULL REFERENCES user_account (id),
    command_type         text NOT NULL,
    document_id          uuid NOT NULL,
    related_document_id  uuid,
    audit_record_id      uuid NOT NULL,
    recorded_at          timestamptz NOT NULL,
    CONSTRAINT ck_segregation_exception_rule CHECK ((kind = 'pair') = (rule_code IS NOT NULL))
);
CREATE INDEX ix_segregation_exception_company_recorded ON segregation_exception (company_id, recorded_at);
CREATE TABLE segregation_review (                          -- one per posting period with exceptions, by ConfirmSegregationReview
    company_id            uuid NOT NULL REFERENCES company (id),
    posting_period_id     uuid NOT NULL REFERENCES posting_period (id),
    exception_count       integer NOT NULL CONSTRAINT ck_segregation_review_count CHECK (exception_count >= 0),
    confirmed_by_user_id  uuid NOT NULL REFERENCES user_account (id),
    confirmed_at          timestamptz NOT NULL,
    PRIMARY KEY (company_id, posting_period_id)
);

-- ===== Approval pools and stages [policy] (ADR-0055 rules 1-4) =====
-- Keys to role and user_account are references to tables of permissions only; policy's code never reads assignments
-- (ADR-0055 rule 1). Pool general cannot be deactivated, and no selector row names an inactive pool (command checks).
CREATE TABLE approval_pool (
    id          uuid PRIMARY KEY,
    company_id  uuid NOT NULL REFERENCES company (id),
    code        text NOT NULL,
    name        text NOT NULL,
    basis       jsonb NOT NULL,
    is_active   boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
-- Selector: position 0 is the one default row per document type; conditional rows (position >= 1) name a boolean
-- policy input of that type and are tried in position order (ADR-0055 rule 3).
CREATE TABLE approval_pool_document_type (
    company_id        uuid NOT NULL,
    document_type     text NOT NULL,
    position          smallint NOT NULL CONSTRAINT ck_approval_pool_document_type_position CHECK (position >= 0),
    condition_input   text,
    approval_pool_id  uuid NOT NULL,
    PRIMARY KEY (company_id, document_type, position),
    FOREIGN KEY (company_id, approval_pool_id) REFERENCES approval_pool (company_id, id),
    CONSTRAINT ck_approval_pool_document_type_default CHECK ((position = 0) = (condition_input IS NULL))
);
CREATE TABLE approval_stage (
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    approval_pool_id     uuid NOT NULL,
    sequence             smallint NOT NULL CONSTRAINT ck_approval_stage_sequence CHECK (sequence >= 1),
    code                 text NOT NULL,
    name                 text NOT NULL,
    min_rank             integer NOT NULL,                       -- non-decreasing along sequence (command check, approval_pool_invalid)
    required_approvals   smallint NOT NULL CONSTRAINT ck_approval_stage_required_approvals CHECK (required_approvals >= 1),
    scope_binding        text NOT NULL DEFAULT 'document_scope' CONSTRAINT ck_approval_stage_scope_binding CHECK (scope_binding IN ('document_scope', 'company')),
    escalation_role_id   uuid,
    due_days             smallint NOT NULL DEFAULT 2 CONSTRAINT ck_approval_stage_due_days CHECK (due_days BETWEEN 1 AND 90),
    is_active            boolean NOT NULL DEFAULT true,
    UNIQUE (company_id, id),
    UNIQUE (approval_pool_id, sequence),
    UNIQUE (approval_pool_id, code),
    FOREIGN KEY (company_id, approval_pool_id) REFERENCES approval_pool (company_id, id),
    FOREIGN KEY (company_id, escalation_role_id) REFERENCES role (company_id, id)
);
CREATE TABLE approval_stage_member (
    company_id         uuid NOT NULL,
    approval_stage_id  uuid NOT NULL,
    member_kind        text NOT NULL CONSTRAINT ck_approval_stage_member_kind CHECK (member_kind IN ('user', 'role')),
    user_account_id    uuid REFERENCES user_account (id),
    role_id            uuid,
    position           smallint CONSTRAINT ck_approval_stage_member_position CHECK (position IS NULL OR position >= 1),   -- the stage's order top to bottom; null sorts last (ADR-0076 rule 6)
    FOREIGN KEY (company_id, approval_stage_id) REFERENCES approval_stage (company_id, id),
    FOREIGN KEY (company_id, role_id) REFERENCES role (company_id, id),
    CONSTRAINT ck_approval_stage_member_target CHECK ((member_kind = 'user') = (user_account_id IS NOT NULL) AND (member_kind = 'role') = (role_id IS NOT NULL))
);
CREATE UNIQUE INDEX ux_approval_stage_member ON approval_stage_member (approval_stage_id, user_account_id, role_id) NULLS NOT DISTINCT;

-- ===== Changes to tables of other design items =====
-- employee_profile (DS-20) gains department_id and manager_partner_id in DS-20-master-data.sql; the department key is
-- added here because department is defined in this file (ADR-0054 rule 6).
ALTER TABLE employee_profile ADD CONSTRAINT fk_employee_profile_department FOREIGN KEY (company_id, department_id) REFERENCES department (company_id, id);
-- Columns on tables that have no DDL draft yet, listed for their owners:
--   document (DS-05, ADR-0009 rule 1): owner_employee_id uuid (an employee partner, composite key to partner),
--     created_by_user_id uuid NOT NULL REFERENCES user_account (ADR-0054 rule 14).
--   approval_procedure (DS-28): approver_role and scope_binding removed; code, name, rank, is_active kept (ADR-0055 rule 5).
--   policy_decision (DS-28): approval_pool_id, approval_plan jsonb, continues_policy_decision_id (ADR-0055 rule 6).
--   approval (DS-05): approval_stage_id, approval_pool_id, delegated_from_user_id, is_escalated (ADR-0055 rule 9).
--   work_item (DS-29, ADR-0042 rule 2): owner_kind gains 'approval_stage'; owner_approval_stage_id uuid, a composite key
--     to approval_stage, set exactly when owner_kind is approval_stage (ADR-0055 rule 12).
--   audit_record (DS-36, ADR-0038 rule 2): delegated_from_user_id (ADR-0054 rule 21).
