"""Lab helpers (not product code)."""
import os, uuid, psycopg
DSN = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab") + " options=-csearch_path=nativeflows"
def new(): return uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.UUID(bytes=uuid.uuid4().bytes)
def conn(): return psycopg.connect(DSN)
RESULTS = []
def expect(name, fn, should_fail, match=None):
    c = conn()
    try:
        with c.transaction():
            fn(c)
        ok = not should_fail
        detail = "succeeded"
    except Exception as e:
        msg = str(e).splitlines()[0]
        ok = should_fail and (match is None or match in msg)
        detail = "failed: " + msg
    finally:
        c.close()
    RESULTS.append((ok, name, detail)); print(("PASS " if ok else "FAIL ") + name + " -- " + detail)


# Ledger and period fixtures: full rows of the design tables (DS-06 system_account and account; DS-05 fiscal_year,
# posting_period and posting_period_area_state, or the lab stubs that mirror them). X is a connection's or cursor's execute.
def ins_system_account(X, id_, code, control_kind="none", account_type="asset"):
    """A postable catalog leaf; normal balance follows the type (ADR-0010 rule 4)."""
    normal = "debit" if account_type in ("asset", "expense") else "credit"
    X("insert into system_account (id, code, account_type, normal_balance, is_contra, is_bilateral, control_kind, is_postable, added_in, name, meaning)"
      " values (%s,%s,%s,%s,false,false,%s,true,'0.1.0',%s,'lab fixture')", (id_, code, account_type, normal, control_kind, code))


def ins_account(X, id_, company_id, code, system_account_id, currency=None):
    """A postable operational account mapped to a system account (ADR-0010 rule 11)."""
    X("insert into account (id, company_id, code, name, is_postable, system_account_id, currency) values (%s,%s,%s,%s,true,%s,%s)",
      (id_, company_id, code, "Account " + code, system_account_id, currency))


def ins_fiscal_year(X, id_, company_id, code, start_date, end_date, is_migration=False):
    X("insert into fiscal_year (id, company_id, code, start_date, end_date, is_migration) values (%s,%s,%s,%s,%s,%s)",
      (id_, company_id, code, start_date, end_date, is_migration))


def ins_posting_period(X, id_, company_id, fiscal_year_id, number, start_date, end_date, kind="regular"):
    X("insert into posting_period (id, company_id, fiscal_year_id, number, kind, start_date, end_date) values (%s,%s,%s,%s,%s,%s,%s)",
      (id_, company_id, fiscal_year_id, number, kind, start_date, end_date))


def ins_area_state(X, company_id, posting_period_id, area, state):
    X("insert into posting_period_area_state (id, company_id, posting_period_id, area, state) values (%s,%s,%s,%s,%s)",
      (new(), company_id, posting_period_id, area, state))


def entry_dates(cx, journal_entry_id):
    """posting_date and fiscal_year_id a journal line copies from its entry (ADR-0014 rule 5 note; INV-99)."""
    return cx.execute("select posting_date, fiscal_year_id from journal_entry where id = %s", (journal_entry_id,)).fetchone()


# Lab-only stand-in for the command layer (S2 schema phase B). The 87 tables below gained the primary key id in phase B,
# with no default, because the command layer supplies UUIDv7 IDs (ADR-0006 rule 2). Their lab fixtures predate the key and
# insert without an id, so after loading, load_all.py and load_ds06.py give id the default uuidv7() on these tables (the
# ones the load defines). The design DDL never has this default (barcode's, for rows database code writes, is in the DDL).
# Lab only, also for the E2 registries among them (setting_definition, setting_preset, setting_preset_item, extension_point,
# event_consumer, public_mail_domain): the design gives those a uuid5 id computed by the loader (ADR-0006 rule 1 note), and
# the lab's uuidv7() default stands in for it (S2 schema review note N5).
PHASE_B_ID_TABLES = (
    "change_proposal_execution_item", "event_subject", "event_consumer", "open_item_collection",
    "installation_role_assignment", "team_member", "role_level", "role_permission", "role_assignment_scope",
    "company_segregation_rule", "segregation_review", "approval_pool_document_type", "approval_stage_member",
    "company_currency_activation", "working_calendar_holiday", "data_translation", "partner_role", "customer_profile",
    "supplier_profile", "employee_profile", "product_variant_attribute", "product_attribute_value", "item_variant_value",
    "product_classification", "external_id_map", "document_line_price_step", "document_line_custom_text",
    "document_installment", "automation_scope_skip", "configuration_state", "decision_table_row", "parameter_set_value",
    "setting_definition", "setting_preset", "setting_preset_item", "extension_point", "public_mail_domain",
    "interaction_content", "interaction_match_candidate", "complaint_document", "data_subject_request_content",
    "outbound_message_content", "outbound_message_recipient", "outbound_message_delivery_recipient", "partner_search_key",
    "extraction_word", "extraction_rule_run", "extraction_confirmation", "extraction_result_link", "planning_setting",
    "planning_state", "production_structure", "supplier_purchasing_term", "supplier_item_lead_time", "sales_history",
    "demand_event_window", "forecast_line", "work_center_activity", "routing_operation_activity", "item_production_setting",
    "item_low_level_code", "planned_order_operation", "replenishment_request_line", "production_order_operation_activity",
    "operation_execution", "production_order_output_serial", "operation_confirmation_activity",
    "operation_confirmation_time_log", "costing_sheet_row", "costing_sheet_base_member", "site_costing_sheet",
    "cost_estimate_line", "cost_estimate_sheet_row", "cost_estimate_gap", "activity_rate", "pool_allocation_rule",
    "normal_capacity", "production_cost_settlement_line", "production_order_period_cost",
    "production_order_period_cost_detail", "configuration_table_column", "configuration_table_row", "configuration_default",
    "product_configuration_value", "conversation_member", "message_mention", "notification_preference",
)


def id_default_shim_sql():
    """SQL that sets DEFAULT uuidv7() on the id of each loaded table of PHASE_B_ID_TABLES; runs with search_path nativeflows."""
    names = ", ".join(f"'{t}'" for t in PHASE_B_ID_TABLES)
    return ("DO $$\nDECLARE v_table text;\nBEGIN\n"
            f"    FOREACH v_table IN ARRAY ARRAY[{names}] LOOP\n"
            "        CONTINUE WHEN to_regclass('nativeflows.' || v_table) IS NULL;\n"
            "        EXECUTE format('ALTER TABLE nativeflows.%I ALTER COLUMN id SET DEFAULT uuidv7()', v_table);\n"
            "    END LOOP;\nEND $$;\n")


def erasure_marker(X, scope="EraseDataSubject", company_id=None):
    """Writes the idempotency record of an erasure command in the current transaction and sets nativeflows.erasure_command_id
    to its id, as the dispatcher does (ADR-0038 rule 4; ADR-0079 rule 7; erasure_marker_valid in DS-05), with
    nativeflows.company_id set to the record's company ('installation' for none). Returns the id.
    X is a connection's or cursor's execute; call it inside the transaction that erases."""
    rid = new()
    X("insert into idempotency_record (id, company_id, actor_kind, actor_id, scope, idempotency_key, request_hash)"
      " values (%s, %s, 'human', %s, %s, %s, %s)", (rid, company_id, new(), scope, "lab-" + str(rid), "0" * 64))
    X("select set_config('nativeflows.erasure_command_id', %s, true)", (str(rid),))
    # the record must belong to the current company (S2 schema review round 2, R2-N1), as the dispatcher sets it
    X("select set_config('nativeflows.company_id', %s, true)", (str(company_id) if company_id else "installation",))
    return rid


def insert_aged(X, table, sql, params=()):
    """Lab only: runs one INSERT into `table` that keeps the recorded_at the fixture gives, for the few labs that need a row
    written in the past (t15 E04: a version written before its run was tainted). The design sets recorded_at on every
    INSERT and UPDATE (trg_<table>_set_recorded_at; ADR-0007 rule 9; S2 adversarial review S2), so this helper disables
    that one named trigger for the statement (ALTER TABLE ... DISABLE TRIGGER; the lab role owns the tables) and enables it
    again, also when the INSERT fails. Every other trigger of the table still fires. Never a pattern for product code."""
    trg = f"trg_{table}_set_recorded_at"
    X(f"ALTER TABLE {table} DISABLE TRIGGER {trg}")
    try:
        return X(sql, params)
    finally:
        X(f"ALTER TABLE {table} ENABLE TRIGGER {trg}")


COMPANY_KEY_SQL = """
with fk as (
  select r.relname src, f.relname tgt,
    (select array_agg(a.attname::text order by u.o) from unnest(k.conkey) with ordinality u(x, o)
       join pg_attribute a on a.attrelid = k.conrelid and a.attnum = u.x) cols,
    (select array_agg(a.attname::text order by u.o) from unnest(k.confkey) with ordinality u(x, o)
       join pg_attribute a on a.attrelid = k.confrelid and a.attnum = u.x) tcols,
    (select a.attnotnull from pg_attribute a where a.attrelid = k.conrelid and a.attname = 'company_id' and not a.attisdropped) src_nn,
    (select a.attnotnull from pg_attribute a where a.attrelid = k.confrelid and a.attname = 'company_id' and not a.attisdropped) tgt_nn
  from pg_constraint k join pg_class r on r.oid = k.conrelid join pg_class f on f.oid = k.confrelid
    join pg_namespace n on n.oid = r.relnamespace
  where n.nspname = 'nativeflows' and k.contype = 'f' and k.conparentid = 0)
select src, cols, tgt, tcols, src_nn, tgt_nn from fk where src_nn is not null and tgt_nn is not null"""


def company_key_findings(X, allowlist):
    """The company-key rule of the ADR-0017 rule 19 note (2026-11-21), read from the catalog of the loaded schema: every
    foreign key between two tables with company_id NOT NULL that lacks company_id (single- or multi-column), or that pairs
    company_id with another column, and every key without company_id to or from a table with a nullable company_id that
    `allowlist` (gen_overview's COMPANY_KEY_ALLOWLIST) does not name. Returns (number of keys between company_id tables, findings)."""
    rows = X(COMPANY_KEY_SQL).fetchall()
    bad = []
    for src, cols, tgt, tcols, src_nn, tgt_nn in rows:
        if "company_id" in cols:
            if tcols[cols.index("company_id")] != "company_id":
                bad.append(("mispaired", src, tuple(cols), tgt))
        elif src_nn and tgt_nn:
            bad.append(("no company_id", src, tuple(cols), tgt))
        elif any(t not in allowlist for t, nn in ((src, src_nn), (tgt, tgt_nn)) if not nn):
            bad.append(("not allowlisted", src, tuple(cols), tgt))
    return len(rows), bad
