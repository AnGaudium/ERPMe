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
