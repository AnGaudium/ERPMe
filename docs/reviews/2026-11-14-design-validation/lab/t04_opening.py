"""Scenario: ADR-0044 opening documents on the DS-06 triggers (lab finding L-12).

Shows that the DS-06 triggers accept the shape of ADR-0044 rules 7 and 8 and the lock of rule 2:
opening documents per currency in a one-day migration fiscal year, offsets per currency to the clearing
account, and a full opening (assets, receivable, equity) leaving the clearing account at zero in company
currency with the expected per-currency residuals (rule 12).
Not covered: the group-only completion lines of rule 12 (the lab schema has no group columns). O05 sets the area
state to locked by direct UPDATE, standing in for CompleteMigration's lock.
"""
from lab import *
c = conn(); c.autocommit = True
X = c.execute
I = {k: new() for k in ["user", "co", "sa_cash", "sa_bank", "sa_rec", "sa_clr", "sa_eq", "a_cash", "a_bank", "a_rec", "a_clr", "a_eq",
                        "fym", "fy27", "mig", "jan", "partner"]}
tag = str(I["co"])[-8:]
X("insert into currency values ('VND',0),('USD',2) on conflict do nothing")
X("insert into user_account values (%s)", (I["user"],))
X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
  " values (%s,%s,'Co4','VND','Asia/Ho_Chi_Minh','vn','tt99','warehouse',%s,'vi')", (I["co"], 'C4-' + tag, I["user"]))
for k, code, kind in [("sa_cash", "cash_on_hand", "none"), ("sa_bank", "cash_in_bank", "none"), ("sa_rec", "receivable_trade", "receivable"),
                      ("sa_clr", "opening_balance_clearing", "none"), ("sa_eq", "owner_capital", "none")]:
    X("insert into system_account values (%s,%s,%s)", (I[k], code + '_' + tag, kind))
for a, s, code in [("a_cash", "sa_cash", "111"), ("a_bank", "sa_bank", "1122"), ("a_rec", "sa_rec", "131"), ("a_clr", "sa_clr", "999"), ("a_eq", "sa_eq", "4111")]:
    X("insert into account (id,company_id,code,system_account_id) values (%s,%s,%s,%s)", (I[a], I["co"], code, I[s]))
# ADR-0044 rule 2: a one-day migration fiscal year before the first operating fiscal year
X("insert into fiscal_year values (%s,%s),(%s,%s)", (I["fym"], I["co"], I["fy27"], I["co"]))
X("insert into posting_period (id,company_id,fiscal_year_id,start_date,end_date) values (%s,%s,%s,'2026-12-31','2026-12-31'),(%s,%s,%s,'2027-01-01','2027-01-31')",
  (I["mig"], I["co"], I["fym"], I["jan"], I["co"], I["fy27"]))
for p in ["mig", "jan"]:
    for area in ["general", "inventory", "receivable", "payable"]:
        X("insert into posting_period_area_state values (%s,%s,'open')", (I[p], area))
X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,'Old customer','organization','VN')", (I["partner"], I["co"], 'CUS-OLD-' + tag))
c.close()
SA = {"a_cash": "sa_cash", "a_bank": "sa_bank", "a_rec": "sa_rec", "a_clr": "sa_clr", "a_eq": "sa_eq"}

def doc(cx, t):
    d = new(); cx.execute("insert into document (id,company_id,document_type) values (%s,%s,%s)", (d, I["co"], t)); return d
def entry(cx, d, n):
    e = new()
    cx.execute("insert into journal_entry (id,company_id,document_id,posting_date,document_date,posting_period_id,fiscal_year_id,line_count)"
               " values (%s,%s,%s,'2026-12-31','2026-12-31',%s,%s,%s)", (e, I["co"], d, I["mig"], I["fym"], n)); return e
def line(cx, e, n, acct, side, cur, tamt, camt, **kw):
    cols = dict(id=kw.pop("id", None) or new(), journal_entry_id=e, company_id=I["co"], line_number=n, posting_period_id=I["mig"],
                account_id=I[acct], system_account_id=I[SA[acct]], side=side, transaction_currency=cur, transaction_amount=tamt,
                company_currency="VND", company_amount=camt)
    cols.update(kw)
    cx.execute("insert into journal_line (%s) values (%s)" % (",".join(cols), ",".join(["%s"] * len(cols))), list(cols.values()))
    return cols["id"]

def opening(cx, cur, lines):
    """One opening_balance_entry per currency (rule 7): balance lines plus one offset to clearing."""
    d = doc(cx, "opening_balance_entry"); e = entry(cx, d, len(lines) + 1)
    tt = tc = 0
    for n, (acct, side, t, cm) in enumerate(lines, 1):
        line(cx, e, n, acct, side, cur, t, cm); tt += t; tc += cm
    line(cx, e, len(lines) + 1, "a_clr", "credit" if tt > 0 else "debit", cur, -tt, -tc)
def opening_item(cx):
    d = doc(cx, "opening_open_item_entry"); e = entry(cx, d, 2); l1 = new(); oi = new()
    cx.execute("""insert into open_item (id,company_id,partner_id,account_id,open_item_kind,natural_side,transaction_currency,origin_document_id,origin_journal_line_id,
      document_date,posting_date,due_date,original_transaction_amount,original_company_amount,open_transaction_amount,open_company_amount,reference)
      values (%s,%s,%s,%s,'invoice','debit','USD',%s,%s,'2026-11-20','2026-12-31','2027-01-20',500,12600000,500,12600000,'HD-0001234')""",
      (oi, I["co"], I["partner"], I["a_rec"], d, l1))
    line(cx, e, 1, "a_rec", "debit", "USD", 500, 12600000, id=l1, partner_id=I["partner"], open_item_id=oi)
    line(cx, e, 2, "a_clr", "credit", "USD", -500, -12600000)

class Rollback(Exception): pass
def trial(name, fn, should_fail, match=None):
    """Run a scenario and always roll it back, so scenarios do not accumulate."""
    def run(cx):
        fn(cx)
        cx.execute('set constraints all immediate')   # fire the deferred balance checks before rolling back
        raise Rollback()
    cx = conn()
    try:
        with cx.transaction(): run(cx)
    except Rollback:
        ok, detail = not should_fail, "succeeded (rolled back)"
    except Exception as e:
        msg = str(e).splitlines()[0]; ok, detail = should_fail and (match is None or match in msg), "failed: " + msg
    finally:
        cx.close()
    RESULTS.append((ok, name, detail)); print(("PASS " if ok else "FAIL ") + name + " -- " + detail)

trial("O01 an opening entry in USD with its offset in USD posts", lambda cx: opening(cx, "USD", [("a_bank", "debit", 1000, 25000000)]), False)
def mixed(cx):
    d = doc(cx, "opening_balance_entry"); e = entry(cx, d, 2)
    line(cx, e, 1, "a_bank", "debit", "USD", 1000, 25000000); line(cx, e, 2, "a_clr", "credit", "VND", -25000000, -25000000)
trial("O02 a USD line offset in VND is rejected though company amounts balance (per-currency balance, ADR-0011 rule 4)", mixed, True, "balance")
trial("O03 an opening open item dated on the opening date, with the old date kept as document date, posts", opening_item, False)

cx = conn(); cx.autocommit = True
with cx.transaction():
    opening(cx, "USD", [("a_bank", "debit", 1000, 25000000)])
    opening(cx, "VND", [("a_cash", "debit", 10000000, 10000000), ("a_eq", "credit", -47600000, -47600000)])
    opening_item(cx)
rows = cx.execute("select transaction_currency, sum(transaction_amount), sum(company_amount) from journal_line where account_id=%s group by 1 order by 1", (I["a_clr"],)).fetchall()
total = sum(r[2] for r in rows)
cx.close()
ok = total == 0 and rows == [("USD", -1500, -37600000), ("VND", 37600000, 37600000)]
RESULTS.append((ok, "O04 full opening: clearing zero in company currency, residuals per currency", str(rows)))
print(("PASS " if ok else "FAIL ") + f"O04 full opening: clearing zero in company currency ({total}), residuals per currency {rows}")

c = conn(); c.autocommit = True
c.execute("update posting_period_area_state set state='locked' where posting_period_id=%s", (I["mig"],))
c.close()
trial("O05 once CompleteMigration has locked the migration period, opening entries are rejected", lambda cx: opening(cx, "VND", [("a_cash", "debit", 1, 1)]), True, "locked")
print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
