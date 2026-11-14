"""Scenario: ADR-0025 rule 4 gated control kinds in the DS-06 trigger (lab finding L-03)."""
from lab import *

c = conn(); c.autocommit = True
X = c.execute
I = {k: new() for k in ["user", "co", "sa_wip", "sa_cash", "a_wip", "a_cash", "fy", "jan", "feb", "co1", "pool"]}
X("insert into currency values ('VND',0) on conflict do nothing")
X("insert into user_account values (%s)", (I["user"],))
X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id)"
  " values (%s,'C2','Co2','VND','Asia/Ho_Chi_Minh','vn','tt99','warehouse',%s)", (I["co"], I["user"]))
X("insert into system_account values (%s,'inventory_work_in_process_t2','cost_object'),(%s,'cash_t2','none')", (I["sa_wip"], I["sa_cash"]))
X("insert into account (id,company_id,code,system_account_id) values (%s,%s,'154',%s),(%s,%s,'111',%s)",
  (I["a_wip"], I["co"], I["sa_wip"], I["a_cash"], I["co"], I["sa_cash"]))
X("insert into fiscal_year values (%s,%s)", (I["fy"], I["co"]))
X("insert into posting_period (id,company_id,fiscal_year_id,start_date,end_date) values (%s,%s,%s,'2027-01-01','2027-01-31'),(%s,%s,%s,'2027-02-01','2027-02-28')",
  (I["jan"], I["co"], I["fy"], I["feb"], I["co"], I["fy"]))
for p in ["jan", "feb"]:
    for area in ["general", "inventory", "receivable", "payable"]:
        X("insert into posting_period_area_state values (%s,%s,'open')", (I[p], area))
X("insert into cost_object (id,company_id,code,name,kind,production_order_id) values (%s,%s,'PO-1','PO 1','production_order',%s)", (I["co1"], I["co"], new()))
c.close()

def post(cx, date, period, wip_amount, cost_object=None, doc_type="journal", doc_id=None):
    d = doc_id or new()
    if doc_id is None:
        cx.execute("insert into document (id,company_id,document_type) values (%s,%s,%s)", (d, I["co"], doc_type))
    e = new()
    cx.execute("insert into journal_entry (id,company_id,document_id,posting_date,document_date,posting_period_id,fiscal_year_id,line_count)"
               " values (%s,%s,%s,%s,%s,%s,%s,2)", (e, I["co"], d, date, date, I[period], I["fy"]))
    for n, acct, sa, side, amt, co in [(1, "a_wip", "sa_wip", "debit", wip_amount, cost_object), (2, "a_cash", "sa_cash", "credit", -wip_amount, None)]:
        cx.execute("insert into journal_line (id,journal_entry_id,company_id,line_number,posting_period_id,account_id,system_account_id,side,"
                   "transaction_currency,transaction_amount,company_currency,company_amount,cost_object_id) values (%s,%s,%s,%s,%s,%s,%s,%s,'VND',%s,'VND',%s,%s)",
                   (new(), e, I["co"], n, I[period], I[acct], I[sa], side, amt, amt, co))

expect("S01 before activation, WIP line without cost object posts", lambda cx: post(cx, "2027-01-10", "jan", 100), False)
c = conn(); c.autocommit = True
reclass = new()
c.execute("insert into document (id,company_id,document_type) values (%s,%s,'subledger_reclassification')", (reclass, I["co"]))
c.execute("insert into subledger_activation (id,company_id,control_kind,effective_from,reclassification_document_id) values (%s,%s,'cost_object','2027-02-01',%s)",
          (new(), I["co"], reclass))
c.close()
expect("S02 after activation, a line dated before effective_from is rejected", lambda cx: post(cx, "2027-01-20", "jan", 5, I["co1"]), True, "subledger_activation_date_not_reached")
expect("S03 after activation, a WIP line without cost object is rejected", lambda cx: post(cx, "2027-02-10", "feb", 5), True, "control_dimension_missing")
expect("S04 after activation, a WIP line with cost object posts", lambda cx: post(cx, "2027-02-10", "feb", 5, I["co1"]), False)
expect("S05 the reclassification document's undimensioned lines post", lambda cx: post(cx, "2027-02-01", "feb", 100, doc_id=reclass), False)
def wrong_kind(cx):
    cx.execute("insert into cost_object (id,company_id,code,name,kind) values (%s,%s,'BAD','bad','cost_pool')", (new(), I["co"]))
expect("S06 a cost pool without its cost center is rejected", wrong_kind, True, "ck_cost_object_kind_reference")
print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
