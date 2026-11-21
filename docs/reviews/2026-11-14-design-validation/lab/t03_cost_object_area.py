"""Scenario: cost-object lines are in area inventory (ADR-0035 rule 3), company check, activation append-only (lab L-07)."""
from lab import *

c = conn(); c.autocommit = True
X = c.execute
I = {k: new() for k in ["user", "co", "co_other", "sa_wip", "sa_cash", "a_wip", "a_cash", "fy", "apr", "po", "po_other"]}
X("insert into currency values ('VND',0) on conflict do nothing")
X("insert into user_account values (%s)", (I["user"],))
for k, code in [("co", "C3"), ("co_other", "C4")]:
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','vn','tt99','warehouse',%s,'vi')", (I[k], code, I["user"]))
ins_system_account(X, I["sa_wip"], "wip_t3", "cost_object")
ins_system_account(X, I["sa_cash"], "cash_t3")
ins_account(X, I["a_wip"], I["co"], "154", I["sa_wip"])
ins_account(X, I["a_cash"], I["co"], "111", I["sa_cash"])
ins_fiscal_year(X, I["fy"], I["co"], "2027", "2027-01-01", "2027-12-31")
ins_posting_period(X, I["apr"], I["co"], I["fy"], 4, "2027-04-01", "2027-04-30")
for area, st in [("general", "open"), ("inventory", "locked"), ("receivable", "open"), ("payable", "open")]:
    ins_area_state(X, I["co"], I["apr"], area, st)
X("insert into cost_object (id,company_id,code,name,kind,production_order_id) values (%s,%s,'PO','PO','production_order',%s)", (I["po"], I["co"], new()))
X("insert into cost_object (id,company_id,code,name,kind,production_order_id) values (%s,%s,'PO','PO','production_order',%s)", (I["po_other"], I["co_other"], new()))
c.close()

def post(cx, cost_object, wip=True):
    d = new(); cx.execute("insert into document (id,company_id,document_type) values (%s,%s,'journal')", (d, I["co"]))
    e = new()
    cx.execute("insert into journal_entry (id,company_id,document_id,posting_date,document_date,posting_period_id,fiscal_year_id,line_count)"
               " values (%s,%s,%s,'2027-04-10','2027-04-10',%s,%s,2)", (e, I["co"], d, I["apr"], I["fy"]))
    a1, s1 = (I["a_wip"], I["sa_wip"]) if wip else (I["a_cash"], I["sa_cash"])
    for n, a, sa, side, amt, co in [(1, a1, s1, "debit", 5, cost_object), (2, I["a_cash"], I["sa_cash"], "credit", -5, None)]:
        cx.execute("insert into journal_line (id,journal_entry_id,company_id,line_number,posting_period_id,posting_date,fiscal_year_id,account_id,system_account_id,side,"
                   "transaction_currency,transaction_amount,company_currency,company_amount,cost_object_id) values (%s,%s,%s,%s,%s,'2027-04-10',%s,%s,%s,%s,'VND',%s,'VND',%s,%s)",
                   (new(), e, I["co"], n, I["apr"], I["fy"], a, sa, side, amt, amt, co))

expect("A01 a WIP line is rejected when the inventory area is locked (general open)", lambda cx: post(cx, I["po"]), True, "area inventory")
expect("A02 a cash-only entry still posts in general", lambda cx: post(cx, None, wip=False), False)
def other_company(cx):
    cx.execute("update posting_period_area_state set state='open' where posting_period_id=%s and area='inventory'", (I["apr"],))
    post(cx, I["po_other"])
expect("A03 a cost object of another company is rejected", other_company, True, "another company")
def activation_update(cx):
    d = new(); cx.execute("insert into document (id,company_id,document_type) values (%s,%s,'subledger_reclassification')", (d, I["co"]))
    a = new(); cx.execute("insert into subledger_activation (id,company_id,control_kind,effective_from,reclassification_document_id) values (%s,%s,'fixed_asset','2027-05-01',%s)", (a, I["co"], d))
    cx.execute("update subledger_activation set effective_from='2027-06-01' where id=%s", (a,))
expect("A04 subledger activation rows are append-only", activation_update, True, "append-only")
print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
