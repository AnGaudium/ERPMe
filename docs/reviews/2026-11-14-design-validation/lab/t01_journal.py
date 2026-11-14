"""Scenario: DS-06 journal triggers (ADR-0014, ADR-0026)."""
from lab import *
import datetime as dt
c = conn(); c.autocommit = True
X = c.execute
ids = {k: new() for k in ["user","co","sa_rec","sa_rev","sa_inv","sa_cash","a_rec","a_rev","a_inv","a_cash","fy","p1","p0","partner","partner2","item","wh"]}
X("insert into currency values ('VND',0),('USD',2)")
X("insert into user_account values (%s)", (ids["user"],))
X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language) values (%s,'C1','Co','VND','Asia/Ho_Chi_Minh','vn','tt99','warehouse',%s,'vi')", (ids["co"], ids["user"]))
for k, code, kind in [("sa_rec","receivable_trade","receivable"),("sa_rev","revenue_goods","none"),("sa_inv","inventory_goods","inventory"),("sa_cash","cash","none")]:
    X("insert into system_account values (%s,%s,%s)", (ids[k], code, kind))
for a, s, code in [("a_rec","sa_rec","131"),("a_rev","sa_rev","511"),("a_inv","sa_inv","156"),("a_cash","sa_cash","111")]:
    X("insert into account (id,company_id,code,system_account_id) values (%s,%s,%s,%s)", (ids[a], ids["co"], code, ids[s]))
X("insert into fiscal_year values (%s,%s)", (ids["fy"], ids["co"]))
X("insert into posting_period (id,company_id,fiscal_year_id,start_date,end_date) values (%s,%s,%s,'2027-01-01','2027-01-31'),(%s,%s,%s,'2026-12-01','2026-12-31')", (ids["p1"],ids["co"],ids["fy"],ids["p0"],ids["co"],ids["fy"]))
for p, st in [("p1","open"),("p0","locked")]:
    for area in ["general","inventory","receivable","payable"]:
        X("insert into posting_period_area_state values (%s,%s,%s)", (ids[p], area, st))
for k, code in [("partner","CUS1"),("partner2","CUS2")]:
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,%s,'organization','VN')", (ids[k], ids["co"], code, code))
# DS-20 master data for the item and warehouse the journal lines refer to (ADR-0045)
u, ig, vc, tg, pr = new(), new(), new(), new(), new()
X("insert into uom (id, code, quantity_kind, decimal_places) values (%s,%s,'count',0)", (u, "EA-" + str(u)[-8:]))
X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,'goods','Goods','{}')", (ig, ids["co"]))
X("insert into valuation_class (id, company_id, code, name, basis) values (%s,%s,'merchandise','Merchandise','{}')", (vc, ids["co"]))
X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,'standard','Standard','{}')", (tg, ids["co"]))
X("insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id, item_tax_group_id) values (%s,%s,'P1','P1','stock',%s,%s,%s,%s,%s,%s)", (pr, ids["co"], ig, vc, u, u, u, tg))
X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'ITEM1')", (ids["item"], ids["co"], pr))
zn, bn = new(), new()
with c.transaction():                                   # warehouse, default zone and bin in one command (ADR-0031 rule 8)
    X("insert into warehouse (id, company_id, code, name, kind, default_bin_id) values (%s,%s,'WH1','WH1','physical',%s)", (ids["wh"], ids["co"], bn))
    X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'DEFAULT','Default')", (zn, ids["co"], ids["wh"]))
    X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEFAULT',%s,'storage')", (bn, ids["co"], ids["wh"], zn, 'WH1-' + str(bn)[-12:]))
c.close()

def doc(cx, t="sales_invoice"):
    d = new(); cx.execute("insert into document (id,company_id,document_type) values (%s,%s,%s)", (d, ids["co"], t)); return d
def entry(cx, d, n, period="p1", date="2027-01-15"):
    e = new()
    cx.execute("insert into journal_entry (id,company_id,document_id,posting_date,document_date,posting_period_id,fiscal_year_id,line_count) values (%s,%s,%s,%s,%s,%s,%s,%s) returning id",
               (e, ids["co"], d, date, date, ids[period], ids["fy"], n)); return e
def line(cx, e, n, acct, side, amt, period="p1", **kw):
    sa = {"a_rec":"sa_rec","a_rev":"sa_rev","a_inv":"sa_inv","a_cash":"sa_cash"}[acct]
    lid = kw.pop("id", None) or new()
    cols = dict(id=lid, journal_entry_id=e, company_id=ids["co"], line_number=n, posting_period_id=ids[period], account_id=ids[acct], system_account_id=ids[sa],
                side=side, transaction_currency="VND", transaction_amount=amt, company_currency="VND", company_amount=amt)
    cols.update(kw)
    cx.execute("insert into journal_line (%s) values (%s)" % (",".join(cols), ",".join(["%s"]*len(cols))), list(cols.values())); return lid
def open_item(cx, d, line_id, partner="partner", amt=1000):
    oi = new()
    cx.execute("""insert into open_item (id,company_id,partner_id,account_id,open_item_kind,natural_side,transaction_currency,origin_document_id,origin_journal_line_id,
      document_date,posting_date,due_date,original_transaction_amount,original_company_amount,open_transaction_amount,open_company_amount)
      values (%s,%s,%s,%s,'invoice','debit','VND',%s,%s,'2027-01-15','2027-01-15','2027-02-15',%s,%s,%s,%s)""",
      (oi, ids["co"], ids[partner], ids["a_rec"], d, line_id, amt, amt, amt, amt)); return oi

def invoice_ok(cx):
    d = doc(cx); e = entry(cx, d, 2); l1 = new(); oi = open_item(cx, d, l1)
    line(cx, e, 1, "a_rec", "debit", 1000, id=l1, partner_id=ids["partner"], open_item_id=oi)
    line(cx, e, 2, "a_rev", "credit", -1000)
expect("T01 balanced invoice with open item posts", invoice_ok, False)
def unbalanced(cx):
    d = doc(cx); e = entry(cx, d, 2); line(cx, e, 1, "a_cash", "debit", 1000); line(cx, e, 2, "a_rev", "credit", -900)
expect("T02 unbalanced entry rejected at commit", unbalanced, True, "does not balance")
def rec_no_oi(cx):
    d = doc(cx); e = entry(cx, d, 2); line(cx, e, 1, "a_rec", "debit", 1000, partner_id=ids["partner"]); line(cx, e, 2, "a_rev", "credit", -1000)
expect("T03 receivable line without open item rejected", rec_no_oi, True, "need partner and open item")
def locked(cx):
    d = doc(cx); e = entry(cx, d, 2, period="p0", date="2026-12-15"); line(cx, e, 1, "a_cash", "debit", 5, period="p0"); line(cx, e, 2, "a_rev", "credit", -5, period="p0")
expect("T04 posting into a locked period rejected", locked, True, "locked")
def wrong_sign(cx):
    d = doc(cx); e = entry(cx, d, 2); line(cx, e, 1, "a_cash", "debit", -5); line(cx, e, 2, "a_rev", "credit", 5)
expect("T05 amount sign must match side", wrong_sign, True, "signs")
def storno(cx):
    d = doc(cx); e = entry(cx, d, 2); line(cx, e, 1, "a_cash", "debit", -5, is_storno=True); line(cx, e, 2, "a_rev", "credit", 5, is_storno=True)
expect("T06 storno lines with flipped signs post", storno, False)
def oi_mismatch(cx):
    d = doc(cx); e = entry(cx, d, 2); l1 = new(); oi = open_item(cx, d, l1, partner="partner2")
    line(cx, e, 1, "a_rec", "debit", 1000, id=l1, partner_id=ids["partner"], open_item_id=oi); line(cx, e, 2, "a_rev", "credit", -1000)
expect("T07 line partner differing from its open item rejected", oi_mismatch, True, "does not match its open item")
def inv_no_item(cx):
    d = doc(cx); e = entry(cx, d, 2); line(cx, e, 1, "a_inv", "debit", 7); line(cx, e, 2, "a_cash", "credit", -7)
expect("T08 inventory line without item and warehouse rejected", inv_no_item, True, "item and warehouse")
def inv_no_mdl(cx):
    d = doc(cx, "goods_receipt"); cx.execute("insert into material_document values (%s,%s)", (new(), d)); e = entry(cx, d, 2)
    line(cx, e, 1, "a_inv", "debit", 7, item_id=ids["item"], warehouse_id=ids["wh"]); line(cx, e, 2, "a_cash", "credit", -7)
expect("T09 inventory line needs its material line when a material document exists", inv_no_mdl, True, "material document line")
# T10/T11 need a committed entry
c = conn(); c.autocommit = True
d0 = new(); c.execute("insert into document (id,company_id,document_type) values (%s,%s,'cash_receipt')", (d0, ids["co"]))
with c.transaction():
    e0 = entry(c, d0, 2); l0 = line(c, e0, 1, "a_cash", "debit", 3); line(c, e0, 2, "a_rev", "credit", -3)
c.close()
expect("T10 journal line update rejected (append-only)", lambda cx: cx.execute("update journal_line set description='x' where id=%s", (l0,)), True, "append-only")
expect("T11 posted entry cannot gain lines later", lambda cx: line(cx, e0, 3, "a_cash", "debit", 1), True, "cannot gain lines")
def oi_update_identity(cx):
    cx.execute("update open_item set partner_id=%s", (ids["partner2"],))
expect("T12 open item identity immutable", oi_update_identity, True, "immutable")
def oi_update_amount(cx):
    cx.execute("update open_item set open_transaction_amount=0, is_settled=true")
expect("T13 open item cache columns may change", oi_update_amount, False)
print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
