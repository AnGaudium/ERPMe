-- DS-63: internal messaging and notifications (ADR-0076). Design draft, PostgreSQL 18. The ADR wins if this file disagrees.
-- Owner module: work (layer 2, beside the work queue of ADR-0042; a note on ADR-0027 rule 1). Every table has company_id,
-- FORCE ROW LEVEL SECURITY and the generated company policy (ADR-0017 rule 19).
-- user_account (DS-15) is installation data: a user takes part in a company's conversations while an active role assignment
-- in that company exists, checked through a registered function (ADR-0076 rule 12). Messages are personal data (spec 17) and
-- untrusted text; no agent run reads or writes these tables (rule 9). Link tables keep composite primary keys, as in DS-15 and DS-20.

-- ===== Conversations [work] (ADR-0076 rules 1-3) =====
CREATE TABLE conversation (                                -- [work] ADR-0076 rule 1
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL REFERENCES company (id),
    kind                     text NOT NULL CONSTRAINT ck_conversation_kind CHECK (kind IN ('channel', 'direct', 'record')),
    name                     text CONSTRAINT ck_conversation_name CHECK (name ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),   -- channels only, a slug
    topic                    text CONSTRAINT ck_conversation_topic CHECK (topic IS NULL OR char_length(topic) <= 500),
    is_private               boolean NOT NULL DEFAULT false,      -- channels only: current members alone read it
    subject_table            text CONSTRAINT ck_conversation_subject_table CHECK (subject_table IN ('document', 'partner', 'product', 'item', 'project')),   -- record threads only (rule 3)
    subject_id               uuid,
    direct_key               text CONSTRAINT ck_conversation_direct_key CHECK (direct_key ~ '^[0-9a-f-]{36}(,[0-9a-f-]{36}){1,7}$'),   -- direct only: 2 to 8 sorted member IDs (rule 2)
    last_sequence            bigint NOT NULL DEFAULT 0 CONSTRAINT ck_conversation_last_sequence CHECK (last_sequence >= 0),   -- the counter of message.sequence, moved under the row lock (rule 4)
    created_by_user_account_id uuid NOT NULL REFERENCES user_account (id),
    closed_at                timestamptz,                         -- channels only (CloseConversation): read-only afterwards
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    CONSTRAINT ck_conversation_shape CHECK (
        (kind = 'channel' AND name IS NOT NULL AND subject_table IS NULL AND subject_id IS NULL AND direct_key IS NULL)
     OR (kind = 'direct'  AND name IS NULL AND NOT is_private AND topic IS NULL AND subject_table IS NULL AND subject_id IS NULL AND direct_key IS NOT NULL AND closed_at IS NULL)
     OR (kind = 'record'  AND name IS NULL AND NOT is_private AND topic IS NULL AND subject_table IS NOT NULL AND subject_id IS NOT NULL AND direct_key IS NULL AND closed_at IS NULL))
);
CREATE UNIQUE INDEX ux_conversation_channel_name ON conversation (company_id, name) WHERE kind = 'channel';
CREATE UNIQUE INDEX ux_conversation_record_subject ON conversation (company_id, subject_table, subject_id) WHERE kind = 'record';
CREATE UNIQUE INDEX ux_conversation_direct_key ON conversation (company_id, direct_key) WHERE kind = 'direct';

CREATE TABLE conversation_member (                         -- [work] ADR-0076 rules 2, 3; a member is a row with left_at null; for a record thread, a follower
    company_id               uuid NOT NULL,
    conversation_id          uuid NOT NULL,
    user_account_id          uuid NOT NULL REFERENCES user_account (id),
    is_owner                 boolean NOT NULL DEFAULT false,      -- channels only, checked by the commands
    notify_level             text NOT NULL DEFAULT 'all' CONSTRAINT ck_conversation_member_notify_level CHECK (notify_level IN ('all', 'mentions', 'none')),
    last_read_sequence       bigint NOT NULL DEFAULT 0 CONSTRAINT ck_conversation_member_last_read_sequence CHECK (last_read_sequence >= 0),
    joined_at                timestamptz NOT NULL,
    left_at                  timestamptz,                         -- EndConversationMember; only a channel member may join again
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (conversation_id, user_account_id),
    FOREIGN KEY (company_id, conversation_id) REFERENCES conversation (company_id, id),
    CONSTRAINT ck_conversation_member_left CHECK (left_at IS NULL OR left_at >= joined_at)
);
CREATE INDEX ix_conversation_member_user_account_id ON conversation_member (company_id, user_account_id) WHERE left_at IS NULL;

-- ===== Messages [work] (ADR-0076 rules 4, 5) =====
CREATE TABLE message (                                     -- [work] ADR-0076 rule 4; people only write messages
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    conversation_id          uuid NOT NULL,
    sequence                 bigint NOT NULL CONSTRAINT ck_message_sequence CHECK (sequence > 0),   -- the conversation's order and unread marker (rule 4; INV-881)
    parent_message_id        uuid,                                -- a reply: one level, to a message of the same conversation
    author_user_account_id   uuid NOT NULL REFERENCES user_account (id),
    body                     text NOT NULL CONSTRAINT ck_message_body CHECK (char_length(body) <= 8000),   -- plain text; <@n> stands for the n-th mention (rule 5); empty once withdrawn or removed
    edited_at                timestamptz,
    withdrawn_at             timestamptz,                         -- the author's withdrawal by UpdateMessage: the body is cleared, the row stays
    body_removed_at          timestamptz,                         -- retention or erasure cleared the body (rule 10)
    recorded_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    UNIQUE (company_id, conversation_id, id),
    UNIQUE (conversation_id, sequence),
    FOREIGN KEY (company_id, conversation_id) REFERENCES conversation (company_id, id),
    FOREIGN KEY (company_id, conversation_id, parent_message_id) REFERENCES message (company_id, conversation_id, id),
    CONSTRAINT ck_message_not_own_parent CHECK (parent_message_id IS DISTINCT FROM id),
    CONSTRAINT ck_message_body_cleared CHECK ((withdrawn_at IS NULL AND body_removed_at IS NULL) OR body = ''),
    CONSTRAINT ck_message_body_present CHECK (body <> '' OR withdrawn_at IS NOT NULL OR body_removed_at IS NOT NULL)
);
CREATE INDEX ix_message_parent_message_id ON message (parent_message_id) WHERE parent_message_id IS NOT NULL;
CREATE INDEX ix_message_company_id_recorded_at ON message (company_id, recorded_at) WHERE body <> '';

CREATE TABLE message_mention (                             -- [work] ADR-0076 rule 5; at most 20 per message, picked in the composer
    company_id       uuid NOT NULL,
    message_id       uuid NOT NULL,
    position         integer NOT NULL CONSTRAINT ck_message_mention_position CHECK (position BETWEEN 1 AND 20),   -- the n of <@n> in the body
    user_account_id  uuid NOT NULL REFERENCES user_account (id),
    recorded_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, position),
    UNIQUE (message_id, user_account_id),
    FOREIGN KEY (company_id, message_id) REFERENCES message (company_id, id)
);
CREATE INDEX ix_message_mention_user_account_id ON message_mention (company_id, user_account_id);

-- ===== Notifications [work] (ADR-0076 rules 6, 7) =====
CREATE TABLE notification_email (                          -- [work] ADR-0076 rule 7; one e-mail to one person, the intent of ADR-0013 rule 10
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL,
    recipient_user_account_id   uuid NOT NULL REFERENCES user_account (id),
    email_kind                  text NOT NULL CONSTRAINT ck_notification_email_email_kind CHECK (email_kind IN ('immediate', 'digest')),
    outcome                     text CONSTRAINT ck_notification_email_outcome CHECK (outcome IN ('sent', 'failed', 'unknown')),   -- set once by RecordNotificationEmailOutcome; unknown is never resent
    attempt_count               integer NOT NULL DEFAULT 0 CONSTRAINT ck_notification_email_attempt_count CHECK (attempt_count BETWEEN 0 AND 3),
    failure_reason              text,
    outcome_at                  timestamptz,
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    CONSTRAINT ck_notification_email_outcome_at CHECK ((outcome IS NULL) = (outcome_at IS NULL) AND (failure_reason IS NULL OR outcome = 'failed'))
);
CREATE INDEX ix_notification_email_open ON notification_email (company_id, recorded_at) WHERE outcome IS NULL;

CREATE TABLE notification (                                -- [work] ADR-0076 rule 6; written only by CreateNotification, from the fan-out consumer
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL,
    recipient_user_account_id   uuid NOT NULL REFERENCES user_account (id),
    kind                        text NOT NULL CONSTRAINT ck_notification_kind CHECK (kind IN ('mention', 'direct_message', 'reply', 'followed', 'work_item')),
    actor_user_account_id       uuid REFERENCES user_account (id),   -- who caused it; null for a work item raised by the system
    conversation_id             uuid,
    message_id                  uuid,
    work_item_id                uuid,
    read_at                     timestamptz,
    email_pending               boolean NOT NULL DEFAULT false,      -- waiting for RunNotificationMail; cleared when grouped into an e-mail or dropped
    notification_email_id       uuid,                                -- the e-mail that carried it
    recorded_at                 timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, conversation_id) REFERENCES conversation (company_id, id),
    FOREIGN KEY (company_id, conversation_id, message_id) REFERENCES message (company_id, conversation_id, id),
    FOREIGN KEY (company_id, work_item_id) REFERENCES work_item (company_id, id),
    FOREIGN KEY (company_id, notification_email_id) REFERENCES notification_email (company_id, id),
    CONSTRAINT ck_notification_source CHECK ((kind = 'work_item') = (work_item_id IS NOT NULL)
        AND (kind = 'work_item' OR (conversation_id IS NOT NULL AND message_id IS NOT NULL))),
    CONSTRAINT ck_notification_email CHECK (NOT (email_pending AND notification_email_id IS NOT NULL))
);
-- One notification per recipient and message, the strongest kind; one unread notification per recipient and work item (rule 6).
CREATE UNIQUE INDEX ux_notification_recipient_message ON notification (recipient_user_account_id, message_id) WHERE message_id IS NOT NULL;
CREATE UNIQUE INDEX ux_notification_recipient_work_item ON notification (recipient_user_account_id, work_item_id) WHERE work_item_id IS NOT NULL AND read_at IS NULL;
CREATE INDEX ix_notification_recipient_unread ON notification (company_id, recipient_user_account_id, id) WHERE read_at IS NULL;
CREATE INDEX ix_notification_email_pending ON notification (company_id, recorded_at) WHERE email_pending;


CREATE TABLE notification_preference (                     -- [work] ADR-0076 rule 7; a missing row takes the kind's default; SetNotificationPreferences replaces a person's list
    company_id       uuid NOT NULL REFERENCES company (id),
    user_account_id  uuid NOT NULL REFERENCES user_account (id),
    kind             text NOT NULL CONSTRAINT ck_notification_preference_kind CHECK (kind IN ('mention', 'direct_message', 'reply', 'followed', 'work_item')),
    email_mode       text NOT NULL CONSTRAINT ck_notification_preference_email_mode CHECK (email_mode IN ('immediate', 'digest', 'off')),
    recorded_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, user_account_id, kind)
);

-- The direct key is 2 to 8 IDs in strictly ascending order, so the same people always give the same key (ADR-0076 rule 2).
CREATE FUNCTION direct_key_valid(k text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT k ~ '^[0-9a-f-]{36}(,[0-9a-f-]{36}){1,7}$' AND coalesce((SELECT bool_and(x < y) FROM (SELECT x, lead(x) OVER (ORDER BY o) AS y FROM unnest(string_to_array(k, ',')) WITH ORDINALITY AS t(x, o)) p WHERE y IS NOT NULL), false)
$$;
ALTER TABLE conversation ADD CONSTRAINT ck_conversation_direct_key_sorted CHECK (direct_key IS NULL OR direct_key_valid(direct_key));
