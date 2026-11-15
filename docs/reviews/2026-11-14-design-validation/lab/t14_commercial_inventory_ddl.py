"""Scenario: the DS-22, DS-09 and DS-42 DDL draft (DS-22-09-42-commercial-inventory.sql; ADR-0047, ADR-0020, ADR-0023,
ADR-0030) loaded with DS-20, DS-56, DS-06, DS-15 and the planning and production draft, on a small real P2P and O2C dataset.

Run: python t14_commercial_inventory_ddl.py
  ERPME_LAB_DSN must name a throwaway database (and PGPASSWORD its password): the script drops and rebuilds schemas
  erpme and types there. ERPME_DOCS points at the docs/ tree to load (default ~/Projects/ERPMe/docs); its lab folder
  gives lab.py, load_ds06.py and 00_stubs.sql. ERPME_DS22 may point at another copy of the draft.

A: the loader orders DS-20, DS-56, DS-06, DS-15, the planning and production draft (DS-43-54, which owns
   demand_supply_line) and this draft together, and they load.
M: company_id and recorded_at on every table of the draft (movement_type is the one global catalog), line numbers.
P: P2P: request, order, supply rows released at approval, two receipts with GR/IR position ranges, material documents,
   stock balances and journal entries through the DS-06 triggers, the invoice's GR/IR posting, INV-92 at zero.
O: O2C: a quotation line without an item (product plus configuration), a sales order with copied prices, demand rows
   released at approval, a credit release by approval, reservation, pick task, delivery at the preliminary price,
   invoice with installments, receivable open items, and a bank receipt's journal entry settling one item.
T: constraint and trigger scenarios, each matched to the constraint that must refuse it.
Not covered: commands, the stock lock helper, consumers, RLS policies, the documents module's final-state trigger, and
the tables of DS-05-platform.sql (document, line taxes, money accounts, payments, bank statements; t15_platform_ddl.py).
demand_supply_line belongs to the planning DDL (DS-43-54-planning-production.sql in design/, or ERPME_DS43); this draft
relies on its hold_reasons set and adds the keys of its sales order, purchase order and purchase request line columns.
"""
import os, re, subprocess, sys, tempfile
from decimal import Decimal as D, ROUND_HALF_UP
from datetime import datetime, timezone
from fractions import Fraction as F

DOCS = os.path.expanduser(os.environ.get("ERPME_DOCS", "~/Projects/ERPMe/docs"))
DESIGN = os.path.join(DOCS, "design")
LAB = os.path.join(DOCS, "reviews/2026-11-14-design-validation/lab")
DS22 = os.environ.get("ERPME_DS22", os.path.join(DESIGN, "DS-22-09-42-commercial-inventory.sql"))
DS43 = os.environ.get("ERPME_DS43", os.path.join(DESIGN, "DS-43-54-planning-production.sql"))   # owns demand_supply_line
sys.path.insert(0, LAB)
from lab import conn, new, RESULTS  # noqa: E402


def check(name, got, want):
    ok = got == want
    RESULTS.append((ok, name, str(got)))
    print(("PASS " if ok else "FAIL ") + f"{name} -- {got}")


def trial(name, fn, match):
    """fn must fail with an error whose first line contains match; everything is rolled back."""
    class Rollback(Exception):
        pass
    cx = conn()
    try:
        with cx.transaction():
            fn(cx); cx.execute("set constraints all immediate"); raise Rollback()
    except Rollback:
        ok, detail = False, "succeeded (rolled back)"
    except Exception as e:
        msg = str(e).splitlines()[0]
        ok, detail = match in msg, "failed: " + msg
    finally:
        cx.close()
    RESULTS.append((ok, name, detail)); print(("PASS " if ok else "FAIL ") + name + " -- " + detail)


# ======================================================================= A: load
# Lab-only: the shared document row's columns (ADR-0009 rule 1; ADR-0052 rule 18), document_version (documents) and
# work_item, which DS-05-platform.sql defines and the credit hold keys to (this lab does not load DS-05).
EXTRA_STUBS = """SET search_path = erpme;
ALTER TABLE document ADD COLUMN partner_id uuid, ADD COLUMN document_date date, ADD COLUMN number text, ADD COLUMN version integer NOT NULL DEFAULT 1,
  ADD COLUMN reversal_of_id uuid REFERENCES document (id), ADD COLUMN correction_of_id uuid REFERENCES document (id),
  ADD CONSTRAINT uq_document_company_id_id UNIQUE (company_id, id);
CREATE TABLE work_item (id uuid PRIMARY KEY, company_id uuid NOT NULL, UNIQUE (company_id, id));
CREATE TABLE document_version (id uuid PRIMARY KEY, company_id uuid NOT NULL, document_id uuid NOT NULL REFERENCES document (id),
  version integer NOT NULL, content jsonb NOT NULL, derived_from_version_id uuid, recorded_at timestamptz NOT NULL, UNIQUE (document_id, version));
"""
stubs = open(os.path.join(LAB, "00_stubs.sql"), encoding="utf-8").read()
for stub_line in ("CREATE TABLE user_account (id uuid PRIMARY KEY);\n",                 # DS-15 defines it in full (as t12, t16)
                  "CREATE TABLE material_document (id uuid PRIMARY KEY, document_id uuid NOT NULL UNIQUE REFERENCES document(id));\n",
                  "CREATE TABLE material_document_line (id uuid PRIMARY KEY, material_document_id uuid NOT NULL REFERENCES material_document(id));\n"):
    assert stubs.count(stub_line) == 1, stub_line
    stubs = stubs.replace(stub_line, "")                   # the draft defines material_document and its lines in full
ddl22 = open(DS22, encoding="utf-8").read()
src = "".join(open(os.path.join(DESIGN, f), encoding="utf-8").read() + "\n"
              for f in ("DS-20-master-data.sql", "DS-56-product-configuration.sql", "DS-06-universal-journal.sql", "DS-15-access.sql")) \
    + open(DS43, encoding="utf-8").read() + "\n" + ddl22
with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as tf:
    tf.write(src)
p = subprocess.run([sys.executable, os.path.join(LAB, "load_ds06.py"), tf.name], capture_output=True, text=True)
os.unlink(tf.name)
order = next((l for l in p.stderr.splitlines() if l.startswith("-- order:")), "")
check("A1 the loader orders DS-20, DS-56, DS-06, DS-15, DS-43-54 and the draft together without a cycle", p.returncode, 0)
c = conn(); c.autocommit = True
X = c.execute
try:
    X(stubs); X(EXTRA_STUBS); X("SET search_path = erpme;\n" + p.stdout)
    loaded = "loaded"
except Exception as e:
    loaded = str(e).splitlines()[0]
check("A2 the ordered DDL executes on PostgreSQL 18", loaded, "loaded")
check("A3 DS-06's journal_line follows the draft's material_document_line and purchase_order_line in the order",
      order.index(" material_document_line,") < order.index(" journal_line,") and "purchase_order_line" in order, True)

# ======================================================================= M: coverage
tables = re.findall(r"^CREATE TABLE (\w+)", ddl22, re.M)
GLOBAL = {"movement_type"}
def has_col(t, col):
    return X("select 1 from information_schema.columns where table_schema='erpme' and table_name=%s and column_name=%s", (t, col)).fetchone() is not None
missing = [t for t in tables if t not in GLOBAL and not has_col(t, "company_id")]
check(f"M1 all {len(tables) - len(GLOBAL)} company tables of the draft carry company_id (missing: {missing or 'none'})", missing, [])
check("M2 the global catalog movement_type has no company_id", [t for t in GLOBAL if has_col(t, "company_id")], [])
no_rec = [t for t in tables if not has_col(t, "recorded_at")]
check(f"M3 all {len(tables)} tables carry recorded_at (missing: {no_rec or 'none'})", no_rec, [])
lines_ = [t for t in tables if t.endswith("_line") and t != "demand_supply_line"]
no_ln = [t for t in lines_ if not has_col(t, "line_number")]
check(f"M4 all {len(lines_)} line tables carry line_number (ADR-0028 rule 1)", no_ln, [])
hdr_doc = [t for t in tables if X("""select 1 from pg_constraint k join pg_class r on r.oid = k.conrelid join pg_class f on f.oid = k.confrelid
    where r.relname=%s and f.relname='document' and k.contype='f'""", (t,)).fetchone()]
check("M5 every header of the 18 document types refers to the shared document row", len([t for t in hdr_doc if not t.startswith("document_") and t not in (
      "material_document", "warehouse_task", "purchase_order_line_gr_ir_posting")]), 18)

# ======================================================================= fixture
I = {k: new() for k in ["user", "co", "co2", "ea", "ig", "vc", "itg", "pstd", "istd", "pcfg", "icfg", "cfg", "cfg2", "va", "pc2", "ic2",
                        "w1", "z1", "b1", "w2", "z2", "b2", "cust", "contact", "supp", "x2", "sl", "pl", "pt", "fy", "pp",
                        "sa_inv", "sa_grir", "sa_rec", "sa_rev", "sa_cogs", "sa_bank", "sa_tax", "a_inv", "a_grir", "a_rec", "a_rev",
                        "a_cogs", "a_bank", "a_tax", "mt_pr", "mt_si", "ma", "ser"]}
t = str(I["co"])[-8:]
B = '{"kind": "company_decision"}'
X("insert into currency (code, minor_unit) values ('VND', 0) on conflict do nothing")
X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I["user"], "u14" + t))
for k, code in (("co", "C14-"), ("co2", "C14B-")):
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','warehouse',%s,'vi')", (I[k], code + t, I["user"]))
X("insert into uom (id, code, quantity_kind, decimal_places) values (%s,%s,'count',0)", (I["ea"], "EA14" + t))
for co in ("co", "co2"):
    X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,'g','G',%s)", (I["ig"] if co == "co" else new(), I[co], B))
X("insert into valuation_class (id, company_id, code, name, basis) values (%s,%s,'v','V',%s)", (I["vc"], I["co"], B))
X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,'s','S',%s)", (I["itg"], I["co"], B))
def product(pid, co, code, configurable=False, ig=None):
    X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
         item_tax_group_id, is_item_created_on_order, is_configurable) values (%s,%s,%s,%s,'stock',%s,%s,%s,%s,%s,%s,%s,%s)""",
      (pid, I[co], code, code, ig or I["ig"], I["vc"], I["ea"], I["ea"], I["ea"], I["itg"], configurable, configurable))
product(I["pstd"], "co", "STD"); product(I["pcfg"], "co", "UNIT", True)
X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'STD')", (I["istd"], I["co"], I["pstd"]))
X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'UNIT-1')", (I["icfg"], I["co"], I["pcfg"]))
X("insert into serial_number (id, company_id, item_id, code) values (%s,%s,%s,'SN1')", (I["ser"], I["co"], I["istd"]))
for k in ("cfg", "cfg2"):
    X("insert into product_configuration (id, company_id, product_id, content_hash, created_at) values (%s,%s,%s,%s,now())",
      (I[k], I["co"], I["pcfg"] if k == "cfg" else I["pstd"], ("a" if k == "cfg" else "b") * 64))
X("insert into variant_attribute (id, company_id, code, name, variant_mode) values (%s,%s,'engr','Engraving','line_option')", (I["va"], I["co"]))
with c.transaction():                                     # warehouses with their default zone and bin (deferred keys)
    for w, z, b, code in (("w1", "z1", "b1", "W1"), ("w2", "z2", "b2", "W2")):
        X("insert into warehouse (id, company_id, code, name, kind, default_bin_id) values (%s,%s,%s,%s,'physical',%s)", (I[w], I["co"], code, code, I[b]))
        X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'DEFAULT','Default')", (I[z], I["co"], I[w]))
        X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEFAULT',%s,'storage')",
          (I[b], I["co"], I[w], I[z], code + "-DEFAULT"))
for k, co, code in (("cust", "co", "CUST"), ("supp", "co", "SUPP"), ("x2", "co2", "X2")):
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,%s,'organization','VN')", (I[k], I[co], code, code + " (sample)"))
X("insert into partner_role (company_id, partner_id, role) values (%s,%s,'customer'),(%s,%s,'supplier')", (I["co"], I["cust"], I["co"], I["supp"]))
X("insert into contact (id, company_id, partner_id, name, email) values (%s,%s,%s,'Lan','lan@cust.example')", (I["contact"], I["co"], I["cust"]))
X("insert into price_list (id, company_id, code, name, kind, currency, is_default) values (%s,%s,'S','S','sale','VND',true),(%s,%s,'P','P','purchase','VND',true)",
  (I["sl"], I["co"], I["pl"], I["co"]))
X("insert into payment_term (id, company_id, code, name) values (%s,%s,'2x15','Two installments')", (I["pt"], I["co"]))
X("insert into fiscal_year (id, company_id) values (%s,%s)", (I["fy"], I["co"]))
X("insert into posting_period (id, company_id, fiscal_year_id, start_date, end_date) values (%s,%s,%s,'2026-11-01','2026-11-30')", (I["pp"], I["co"], I["fy"]))
for area in ("general", "inventory", "receivable", "payable"):
    X("insert into posting_period_area_state values (%s,%s,'open')", (I["pp"], area))
for code, ck in (("inv", "inventory"), ("grir", "none"), ("rec", "receivable"), ("rev", "none"), ("cogs", "none"), ("bank", "none"), ("tax", "none")):
    X("insert into system_account (id, code, control_kind) values (%s,%s,%s)", (I["sa_" + code], code + t, ck))
    X("insert into account (id, company_id, code, system_account_id) values (%s,%s,%s,%s)", (I["a_" + code], I["co"], code, I["sa_" + code]))
X("""insert into movement_type (id, code, name, direction, value_source, costing_role, offset_transaction_key, needs_reference, sap_analog, added_in)
     values (%s,%s,'Purchase receipt','in','document','receipt','gr_ir_clearing',true,'101','0.1.0'),
            (%s,%s,'Sales issue','out','preliminary_price','revalued_issue','cost_of_goods_sold',true,'601','0.1.0')""",
  (I["mt_pr"], "purchase_receipt" + t, I["mt_si"], "sales_issue" + t))

def ins(cx, table, **v):
    cx.execute(f"insert into {table} ({', '.join(v)}) values ({', '.join(['%s'] * len(v))})", list(v.values()))
    return v.get("id")
def doc(cx, dtype, state="posted", partner=None, date="2026-11-10", co="co", correction_of=None):
    d = new()
    ins(cx, "document", id=d, company_id=I[co], document_type=dtype, state=state, partner_id=I[partner] if partner else None,
        document_date=date, correction_of_id=correction_of)
    return d
NOW = datetime.now(timezone.utc)
SNAP = dict(partner_name="(sample)", partner_tax_id="0100000000")
def rnd(x):
    """Round an exact fraction half up to the currency's minor unit (VND: 0 decimals)."""
    return int((D(x.numerator) / D(x.denominator)).quantize(D(1), ROUND_HALF_UP))
def journal(cx, document_id, lines, ids_in=None):
    """Post one journal entry through the DS-06 triggers: lines are (account, side, amount, extra columns)."""
    je = new()
    ins(cx, "journal_entry", id=je, company_id=I["co"], document_id=document_id, posting_date="2026-11-10", document_date="2026-11-10",
        posting_period_id=I["pp"], fiscal_year_id=I["fy"], line_count=len(lines))
    ids = []
    for n, (acc, side, amount, extra) in enumerate(lines, 1):
        signed = amount if side == "debit" else -amount
        jl = ids_in[n - 1] if ids_in else new(); ids.append(jl)
        ins(cx, "journal_line", id=jl, journal_entry_id=je, company_id=I["co"], line_number=n, posting_period_id=I["pp"], account_id=I["a_" + acc],
            system_account_id=I["sa_" + acc], side=side, transaction_currency="VND", transaction_amount=signed, company_currency="VND", company_amount=signed, **extra)
    return ids
def stock_in(cx, item, wh, bin_, qty, value):
    """The stock lock helper's effect, as the lab writes it: balances per key and per (item, warehouse)."""
    if cx.execute("""update stock_quantity set quantity = quantity + %s where company_id=%s and item_id=%s and warehouse_id=%s and bin_id=%s
                     and lot_id is null and serial_number_id is null and stock_status='available' and handling_unit_id is null and owner_partner_id is null""",
                  (qty, I["co"], item, wh, bin_)).rowcount == 0:
        cx.execute("insert into stock_quantity (id, company_id, item_id, warehouse_id, bin_id, quantity) values (%s,%s,%s,%s,%s,%s)", (new(), I["co"], item, wh, bin_, qty))
    if cx.execute("update stock_value set company_amount = company_amount + %s where company_id=%s and item_id=%s and warehouse_id=%s",
                  (value, I["co"], item, wh)).rowcount == 0:
        cx.execute("insert into stock_value (id, company_id, item_id, warehouse_id, company_amount) values (%s,%s,%s,%s,%s)", (new(), I["co"], item, wh, value))

# ======================================================================= P: purchase to pay
PRICE = F(1000000, 30)                                  # the order line's GR/IR price, an exact rational (ADR-0047 rule 10)
V = lambda x: PRICE * x
L = {}
with c.transaction():
    d_pr = doc(c, "purchase_request", "approved")
    ins(c, "purchase_request", id=d_pr, company_id=I["co"], document_date="2026-11-05")
    L["prl"] = ins(c, "purchase_request_line", id=new(), company_id=I["co"], purchase_request_id=d_pr, line_number=1, item_id=I["istd"], quantity=30, uom_id=I["ea"],
                   inventory_quantity=30, warehouse_id=I["w1"], requested_date="2026-11-09")
    d_po = doc(c, "purchase_order", "draft", "supp")
    ins(c, "purchase_order", id=d_po, company_id=I["co"], partner_id=I["supp"], currency="VND", price_list_id=I["pl"], payment_term_id=I["pt"], document_date="2026-11-06", **SNAP)
    L["pol"] = ins(c, "purchase_order_line", id=new(), company_id=I["co"], purchase_order_id=d_po, line_number=1, purchase_request_line_id=L["prl"], item_id=I["istd"],
                   quantity=30, uom_id=I["ea"], inventory_quantity=30, warehouse_id=I["w1"], requested_date="2026-11-09", list_unit_price=D("33333.3333333333"),
                   net_unit_price=D("33333.3333333333"), line_amount=1000000)
    L["dsl_po"] = ins(c, "demand_supply_line", id=new(), recorded_at=NOW, company_id=I["co"], item_id=I["istd"], warehouse_id=I["w1"], direction="supply", open_quantity=30,
                      requested_date="2026-11-09", source_kind="purchase_order_line", purchase_order_line_id=L["pol"], hold_reasons=["not_approved"])
held = X("select count(*) from demand_supply_line where purchase_order_line_id=%s and hold_reasons <> '{}'", (L["pol"],)).fetchone()[0]
with c.transaction():                                   # approval: release the supply row and price the line (ADR-0047 rules 10, 13)
    X("update document set state='approved' where id=%s", (d_po,))
    X("update demand_supply_line set hold_reasons='{}', ordered_date='2026-11-06' where id=%s", (L["dsl_po"],))
    ins(c, "purchase_order_line_gr_ir_layer", id=new(), company_id=I["co"], purchase_order_line_id=L["pol"], from_position=0, to_position=30,
        price_numerator=PRICE.numerator, price_denominator=PRICE.denominator)
check("P01 the draft order's supply row is created held (not_approved) and released by approval",
      (held, X("select hold_reasons from demand_supply_line where id=%s", (L["dsl_po"],)).fetchone()[0]), (1, []))
R = 0
GR = []
for q in (10, 20):                                      # two receipts: positions [0, 10) and [10, 30)
    amount = rnd(V(R + q)) - rnd(V(R))
    with c.transaction():
        d = doc(c, "goods_receipt", "posted", "supp")
        ins(c, "goods_receipt", id=d, company_id=I["co"], partner_id=I["supp"], document_date="2026-11-10", posting_date="2026-11-10", **SNAP)
        grl = ins(c, "goods_receipt_line", id=new(), company_id=I["co"], goods_receipt_id=d, line_number=1, purchase_order_line_id=L["pol"], item_id=I["istd"],
                  quantity=q, uom_id=I["ea"], inventory_quantity=q, warehouse_id=I["w1"], gr_ir_position_from=R, gr_ir_position_to=R + q)
        md = ins(c, "material_document", id=new(), company_id=I["co"], document_id=d, posting_date="2026-11-10")
        mdl = ins(c, "material_document_line", id=new(), company_id=I["co"], material_document_id=md, line_number=1, source_line_number=1, item_id=I["istd"],
                  warehouse_id=I["w1"], movement_type_id=I["mt_pr"], direction="in", quantity=q, company_amount=amount, valuation_warehouse_id=I["w1"],
                  bin_id=I["b1"], posting_date="2026-11-10")
        stock_in(c, I["istd"], I["w1"], I["b1"], q, amount)
        ins(c, "purchase_order_line_gr_ir_posting", id=new(), company_id=I["co"], purchase_order_line_id=L["pol"], document_id=d, line_number=1,
            posting_kind="receipt", from_position=R, to_position=R + q, gr_ir_amount=-amount)
        jl = journal(c, d, [("inv", "debit", amount, dict(item_id=I["istd"], warehouse_id=I["w1"], material_document_line_id=mdl)),
                            ("grir", "credit", amount, dict(purchase_order_line_id=L["pol"]))])
        X("update demand_supply_line set open_quantity = open_quantity - %s where id=%s", (q, L["dsl_po"]))
    GR.append((d, grl, mdl, amount, jl)); R += q
check("P02 receipts of 10 and 20 at the rational price post 333,333 and 666,667 (differences of rounded cumulative values)",
      [g[3] for g in GR], [333333, 666667])
check("P03 the supply row's open quantity is stored once and falls to zero (ADR-0031 rule 5)",
      X("select open_quantity from demand_supply_line where id=%s", (L["dsl_po"],)).fetchone()[0], D("0.000000"))
with c.transaction():
    d_pi = doc(c, "purchase_invoice", "posted", "supp")
    ins(c, "purchase_invoice", id=d_pi, company_id=I["co"], partner_id=I["supp"], partner_reference="INV-0001", supplier_invoice_date="2026-11-11",
        document_date="2026-11-11", posting_date="2026-11-11", currency="VND", payment_term_id=I["pt"], **SNAP)
    L["pil"] = ins(c, "purchase_invoice_line", id=new(), company_id=I["co"], purchase_invoice_id=d_pi, line_number=1, line_kind="goods",
                   purchase_order_line_id=L["pol"], item_id=I["istd"], quantity=30, uom_id=I["ea"], inventory_quantity=30, unit_price=D("33333.3333333333"),
                   line_amount=1000000, is_price_copied=True)
    ins(c, "purchase_order_line_gr_ir_posting", id=new(), company_id=I["co"], purchase_order_line_id=L["pol"], document_id=d_pi, line_number=1,
        posting_kind="invoice", from_position=0, to_position=30, gr_ir_amount=rnd(V(30)) - rnd(V(0)))
check("P04 INV-92: with received = invoiced = 30 the line's GR/IR postings sum to zero",
      X("select sum(gr_ir_amount) from purchase_order_line_gr_ir_posting where purchase_order_line_id=%s", (L["pol"],)).fetchone()[0], D("0.0000"))
check("P05 stock_quantity per key equals the material lines (30 in the default bin)",
      X("select quantity from stock_quantity where item_id=%s and bin_id=%s", (I["istd"], I["b1"])).fetchone()[0],
      X("select sum(quantity) from material_document_line where item_id=%s and direction='in'", (I["istd"],)).fetchone()[0])
check("P06 stock_value equals the material line values and the inventory journal lines (ADR-0020 rule 6)",
      X("select (select company_amount from stock_value where item_id=%(i)s), (select sum(company_amount) from journal_line where item_id=%(i)s)", {"i": I["istd"]}).fetchone(),
      (D("1000000.0000"), D("1000000.0000")))

# ======================================================================= O: order to cash
with c.transaction():
    d_q = doc(c, "quotation", "approved", "cust")
    ins(c, "quotation", id=d_q, company_id=I["co"], partner_id=I["cust"], contact_id=I["contact"], currency="VND", price_list_id=I["sl"],
        payment_term_id=I["pt"], document_date="2026-11-01", valid_until="2026-11-30", **SNAP)
    L["ql1"] = ins(c, "quotation_line", id=new(), company_id=I["co"], quotation_id=d_q, line_number=1, product_id=I["pcfg"], product_configuration_id=I["cfg"],
                   configuration_values='{"width": 600}', quantity=1, uom_id=I["ea"], inventory_quantity=1, net_unit_price=8000000, line_amount=8000000)
    L["ql2"] = ins(c, "quotation_line", id=new(), company_id=I["co"], quotation_id=d_q, line_number=2, product_id=I["pstd"], item_id=I["istd"], quantity=10,
                   uom_id=I["ea"], inventory_quantity=10, list_unit_price=100000, net_unit_price=100000, line_amount=1000000)
    for n, (step, val) in enumerate((("list_price", 100000), ("base_price", 100000), ("net_unit_price", 100000), ("line_amount", 1000000)), 1):
        ins(c, "document_line_price_step", company_id=I["co"], document_id=d_q, line_number=2, step_number=n, step=step, value=val)
check("O01 an approved quotation keeps a line with product and configuration and no item (holistic review B1)",
      X("select item_id is null and product_configuration_id is not null from quotation_line where id=%s", (L["ql1"],)).fetchone()[0], True)
with c.transaction():
    d_so = doc(c, "sales_order", "pending_approval", "cust")
    ins(c, "sales_order", id=d_so, company_id=I["co"], partner_id=I["cust"], currency="VND", price_list_id=I["sl"], payment_term_id=I["pt"], document_date="2026-11-02", **SNAP)
    L["sol1"] = ins(c, "sales_order_line", id=new(), company_id=I["co"], sales_order_id=d_so, line_number=1, quotation_line_id=L["ql1"], product_id=I["pcfg"],
                    item_id=I["icfg"], product_configuration_id=I["cfg"], quantity=1, uom_id=I["ea"], inventory_quantity=1, warehouse_id=I["w1"],
                    net_unit_price=8000000, line_amount=8000000, is_price_copied=True)
    L["sol2"] = ins(c, "sales_order_line", id=new(), company_id=I["co"], sales_order_id=d_so, line_number=2, quotation_line_id=L["ql2"], product_id=I["pstd"],
                    item_id=I["istd"], quantity=10, uom_id=I["ea"], inventory_quantity=10, warehouse_id=I["w1"], planned_delivery_date="2026-11-12",
                    list_unit_price=100000, net_unit_price=100000, line_amount=1000000, is_price_copied=True)
    for n, (step, val) in enumerate((("list_price", 100000), ("base_price", 100000), ("net_unit_price", 100000), ("line_amount", 1000000)), 1):
        ins(c, "document_line_price_step", company_id=I["co"], document_id=d_so, line_number=2, step_number=n, step=step, value=val,
            source_kind="copied", copied_from_document_id=d_q, copied_from_line_number=2)
    for sol, item, q in ((L["sol1"], I["icfg"], 1), (L["sol2"], I["istd"], 10)):
        L["dsl_" + str(sol)] = ins(c, "demand_supply_line", id=new(), recorded_at=NOW, company_id=I["co"], item_id=item, warehouse_id=I["w1"], direction="demand",
                                   open_quantity=q, requested_date="2026-11-12", source_kind="sales_order_line", sales_order_line_id=sol, hold_reasons=["not_approved"])
unreleased = X("select count(*) from demand_supply_line where direction='demand' and 'not_approved' = any(hold_reasons)").fetchone()[0]
with c.transaction():                                   # approval with is_credit_exceeded: the approval is the credit release (ADR-0047 rule 18)
    X("update document set state='approved' where id=%s", (d_so,))
    X("update demand_supply_line set hold_reasons = array_remove(hold_reasons, 'not_approved') where sales_order_line_id in (%s, %s)", (L["sol1"], L["sol2"]))
    ins(c, "credit_hold", id=new(), company_id=I["co"], sales_order_id=d_so, partner_id=I["cust"], state="released", currency="VND",
        credit_limit_amount=5000000, credit_exposure_amount=9000000, release_kind="approval", released_at="2026-11-02T03:00:00Z", released_order_amount=9000000)
check("O02 submit creates both demand rows unreleased; approval releases them (holistic review B2, S5)",
      (unreleased, X("select count(*) from demand_supply_line where direction='demand' and hold_reasons = '{}'").fetchone()[0]), (2, 2))
check("O03 copied price steps reproduce the stored line amount and name their source (INV-93; holistic review S2)",
      X("""select l.net_unit_price * l.quantity = s.value and s.copied_from_line_number = 2 and l.is_price_copied
           from sales_order_line l join document_line_price_step s on s.document_id = l.sales_order_id and s.line_number = l.line_number and s.step = 'line_amount'
           where l.id=%s""", (L["sol2"],)).fetchone()[0], True)
dsl2 = L["dsl_" + str(L["sol2"])]
with c.transaction():                                   # reservation and pick (ADR-0023 rules 13-15)
    L["res"] = ins(c, "stock_reservation", id=new(), company_id=I["co"], demand_supply_line_id=dsl2, item_id=I["istd"], warehouse_id=I["w1"], quantity=10)
    L["task"] = ins(c, "warehouse_task", id=new(), company_id=I["co"], warehouse_id=I["w1"], task_kind="pick", item_id=I["istd"], quantity=10, uom_id=I["ea"],
                    from_bin_id=I["b1"], to_bin_id=I["b1"], demand_supply_line_id=dsl2)
    X("update warehouse_task set state='confirmed', confirmed_quantity=10 where id=%s", (L["task"],))
    X("update stock_reservation set picked_quantity=10, state='picked' where id=%s", (L["res"],))
    ins(c, "preliminary_price", id=new(), company_id=I["co"], item_id=I["istd"], valuation_warehouse_id=I["w1"], posting_period_id=I["pp"],
        unit_price=D("33333.3333333333"), price_source="area_receipt")
pp_price = X("select unit_price from preliminary_price where item_id=%s", (I["istd"],)).fetchone()[0]
cogs = int((pp_price * 10).quantize(D(1), ROUND_HALF_UP))
with c.transaction():
    d_dl = doc(c, "delivery", "posted", "cust")
    ins(c, "delivery", id=d_dl, company_id=I["co"], partner_id=I["cust"], document_date="2026-11-12", posting_date="2026-11-12", **SNAP)
    L["dl"] = ins(c, "delivery_line", id=new(), company_id=I["co"], delivery_id=d_dl, line_number=1, sales_order_line_id=L["sol2"], item_id=I["istd"],
                  quantity=10, uom_id=I["ea"], inventory_quantity=10, warehouse_id=I["w1"])
    md = ins(c, "material_document", id=new(), company_id=I["co"], document_id=d_dl, posting_date="2026-11-12")
    mdl = ins(c, "material_document_line", id=new(), company_id=I["co"], material_document_id=md, line_number=1, source_line_number=1, item_id=I["istd"],
              warehouse_id=I["w1"], movement_type_id=I["mt_si"], direction="out", quantity=10, company_amount=cogs, valuation_warehouse_id=I["w1"],
              bin_id=I["b1"], posting_date="2026-11-12")
    stock_in(c, I["istd"], I["w1"], I["b1"], -10, -cogs)
    journal(c, d_dl, [("cogs", "debit", cogs, {}), ("inv", "credit", cogs, dict(item_id=I["istd"], warehouse_id=I["w1"], material_document_line_id=mdl))])
    X("update stock_reservation set fulfilled_quantity=10, state='fulfilled' where id=%s", (L["res"],))
    X("update demand_supply_line set open_quantity=0, closed_reason='fulfilled' where id=%s", (dsl2,))
check("O04 delivery at the preliminary price: 333,333 leaves stock; 20 units and 666,667 remain",
      X("select (select quantity from stock_quantity where item_id=%(i)s), (select company_amount from stock_value where item_id=%(i)s)", {"i": I["istd"]}).fetchone(),
      (D("20.000000"), D("666667.0000")))
check("O05 the reservation is fulfilled and the demand row closed; the pick task is confirmed (INV-58 shape)",
      X("""select r.state, d.closed_reason, w.state from stock_reservation r join demand_supply_line d on d.id = r.demand_supply_line_id
           join warehouse_task w on w.demand_supply_line_id = d.id where r.id=%s""", (L["res"],)).fetchone(), ("fulfilled", "fulfilled", "confirmed"))
OI, JL = [new(), new()], [new(), new(), new(), new()]
with c.transaction():
    d_si = doc(c, "sales_invoice", "posted", "cust")
    ins(c, "sales_invoice", id=d_si, company_id=I["co"], partner_id=I["cust"], currency="VND", payment_term_id=I["pt"], document_date="2026-11-13",
        posting_date="2026-11-13", **SNAP)
    L["sil"] = ins(c, "sales_invoice_line", id=new(), company_id=I["co"], sales_invoice_id=d_si, line_number=1, sales_order_line_id=L["sol2"], delivery_line_id=L["dl"],
                   product_id=I["pstd"], item_id=I["istd"], quantity=10, uom_id=I["ea"], inventory_quantity=10, net_unit_price=100000, line_amount=1000000, is_price_copied=True)
    for n, due in ((1, "2026-11-28"), (2, "2026-12-13")):
        ins(c, "document_installment", company_id=I["co"], document_id=d_si, installment_number=n, due_date=due, transaction_amount=550000)
    for n, due in ((0, "2026-11-28"), (1, "2026-12-13")):
        X("""insert into open_item (id, company_id, partner_id, account_id, open_item_kind, natural_side, transaction_currency, origin_document_id, origin_journal_line_id,
             installment_number, payment_term_id, document_date, posting_date, original_posting_date, due_date, original_transaction_amount, original_company_amount,
             open_transaction_amount, open_company_amount) values (%s,%s,%s,%s,'invoice','debit','VND',%s,%s,%s,%s,'2026-11-13','2026-11-13','2026-11-13',%s,550000,550000,550000,550000)""",
          (OI[n], I["co"], I["cust"], I["a_rec"], d_si, JL[n], n + 1, I["pt"], due))     # the origin line follows (deferred key)
    je_ids = journal(c, d_si, [("rec", "debit", 550000, dict(partner_id=I["cust"], open_item_id=OI[0])), ("rec", "debit", 550000, dict(partner_id=I["cust"], open_item_id=OI[1])),
                              ("rev", "credit", 1000000, {}), ("tax", "credit", 100000, {})], JL)
check("O06 the installment schedule sums to the invoice total with 10% tax and equals its receivable open items (ADR-0047 rule 6)",
      X("""select (select sum(transaction_amount) from document_installment where document_id=%(d)s),
                  (select sum(line_amount) * 1.1 from sales_invoice_line where sales_invoice_id=%(d)s),
                  (select sum(original_transaction_amount) from open_item where origin_document_id=%(d)s)""", {"d": d_si}).fetchone(),
      (D("1100000.0000"), D("1100000.00000"), D("1100000.0000")))
with c.transaction():                                   # the bank receipt's typed rows are DS-05-platform's; its entry settles the item
    d_pay = doc(c, "bank_receipt", "posted", "cust", "2026-11-28")
    journal(c, d_pay, [("bank", "debit", 550000, {}), ("rec", "credit", 550000, dict(partner_id=I["cust"], open_item_id=OI[0], evidence_method="bank_transfer"))])
    X("update open_item set open_transaction_amount=0, open_company_amount=0, is_settled=true, last_settlement_date='2026-11-28' where id=%s", (OI[0],))
check("O07 a bank receipt settles the first installment through DS-06; the second stays open",
      X("select count(*) filter (where is_settled), count(*) filter (where not is_settled) from open_item where origin_document_id=%s", (d_si,)).fetchone(), (1, 1))

# ======================================================================= T: constraints that must refuse
co, ea = I["co"], I["ea"]
def qline(**o):
    v = dict(id=new(), company_id=co, quotation_id=d_q, line_number=9, product_id=I["pstd"], quantity=1, uom_id=ea, inventory_quantity=1)
    v.update(o); return lambda cx: ins(cx, "quotation_line", **v)
def soline(**o):
    v = dict(id=new(), company_id=co, sales_order_id=d_so, line_number=9, product_id=I["pstd"], item_id=I["istd"], quantity=1, uom_id=ea, inventory_quantity=1)
    v.update(o); return lambda cx: ins(cx, "sales_order_line", **v)
trial("T01 a quotation line names a product", qline(product_id=None), "null value in column \"product_id\"")
trial("T02 a quotation line's item belongs to its product", qline(item_id=I["icfg"]), "fk_quotation_line_item_product")
trial("T03 a quotation line's configuration belongs to its product", qline(product_id=I["pcfg"], product_configuration_id=I["cfg2"]), "fk_quotation_line_configuration")
def bad_quotation(cx):
    d = doc(cx, "quotation", "draft", "cust")
    ins(cx, "quotation", id=d, company_id=co, partner_id=I["cust"], currency="VND", document_date="2026-11-10", valid_until="2026-11-01", **SNAP)
trial("T04 a quotation is valid until a date on or after its document date", bad_quotation, "ck_quotation_valid_until")
trial("T05 a line number is unique in its document", qline(line_number=2), "duplicate key value")
trial("T06 line numbers are positive", qline(line_number=0), "ck_quotation_line_line_number")
def so_header(**o):
    def f(cx):
        d = doc(cx, "sales_order", "draft", "cust")
        v = dict(id=d, company_id=co, partner_id=I["cust"], currency="VND", document_date="2026-11-10"); v.update(SNAP); v.update(o)
        ins(cx, "sales_order", **v)
    return f
trial("T07 a sales order cannot name another company's partner", so_header(partner_id=I["x2"]), "violates foreign key constraint")
trial("T08 a sales order cannot use a purchase list (kind key)", so_header(price_list_id=I["pl"]), "violates foreign key constraint")
trial("T09 a contact belongs to the document's partner", so_header(partner_id=I["supp"], contact_id=I["contact"]), "violates foreign key constraint")
trial("T10 a manual price flag needs the manual price", soline(is_price_manual=True), "ck_sales_order_line_manual_price")
trial("T11 a free-of-charge line has price and amount zero", soline(is_free_of_charge=True, net_unit_price=5, line_amount=5), "ck_sales_order_line_free_of_charge")
trial("T12 a manual discount is at most 100 percent", soline(manual_discount_percent=120), "ck_sales_order_line_manual_discount_percent")
trial("T13 a copied price step names its source line", lambda cx: ins(cx, "document_line_price_step", company_id=co, document_id=d_so, line_number=1, step_number=1,
      step="net_unit_price", value=1, source_kind="copied"), "ck_document_line_price_step_copied")
trial("T14 a promotion has exactly one scope", lambda cx: ins(cx, "promotion", id=new(), company_id=co, code="P1", name="P", priority=1, start_date="2026-11-01",
      item_id=I["istd"], product_id=I["pstd"], kind="percent", discount_percent=5), "ck_promotion_scope")
trial("T15 a free goods promotion names the free item and quantities", lambda cx: ins(cx, "promotion", id=new(), company_id=co, code="P2", name="P", priority=1,
      start_date="2026-11-01", item_id=I["istd"], kind="free_goods"), "ck_promotion_kind_fields")
def note(table, reason):
    def f(cx):
        d = doc(cx, table, "draft", "cust", correction_of=d_si)
        ins(cx, table, id=d, company_id=co, partner_id=I["cust"], currency="VND", reason=reason, document_date="2026-11-20", posting_date="2026-11-20", **SNAP)
    return f
trial("T16 a credit note never credits returned goods or charges (reasons of rule 8)", note("credit_note", "additional_charge"), "ck_credit_note_reason")
trial("T17 a debit note has no allowance reason", note("debit_note", "allowance"), "ck_debit_note_reason")
def piline(**o):
    v = dict(id=new(), company_id=co, purchase_invoice_id=d_pi, line_number=9, line_kind="goods", item_id=I["istd"], quantity=1, uom_id=ea, inventory_quantity=1, line_amount=1)
    v.update(o); return lambda cx: ins(cx, "purchase_invoice_line", **v)
trial("T18 a goods line of a purchase invoice refers to an order line (purchase_order_required)", piline(), "ck_purchase_invoice_line_kind_reference")
trial("T19 an expense line has no order line", piline(line_kind="expense", purchase_order_line_id=L["pol"]), "ck_purchase_invoice_line_kind_reference")
def pi_blank(cx):
    d = doc(cx, "purchase_invoice", "draft", "supp")
    ins(cx, "purchase_invoice", id=d, company_id=co, partner_id=I["supp"], partner_reference="  ", supplier_invoice_date="2026-11-11", document_date="2026-11-11",
        posting_date="2026-11-11", currency="VND", **SNAP)
trial("T20 a purchase invoice carries the supplier's number", pi_blank, "ck_purchase_invoice_partner_reference")
trial("T21 a receipt line's position range equals its inventory quantity", lambda cx: ins(cx, "goods_receipt_line", id=new(), company_id=co, goods_receipt_id=GR[0][0],
      line_number=2, purchase_order_line_id=L["pol"], item_id=I["istd"], quantity=5, uom_id=ea, inventory_quantity=5, warehouse_id=I["w1"],
      gr_ir_position_from=30, gr_ir_position_to=36), "ck_goods_receipt_line_positions")
trial("T21b a receipt line of an order line stores its position range (null-safe check)", lambda cx: ins(cx, "goods_receipt_line", id=new(), company_id=co,
      goods_receipt_id=GR[0][0], line_number=2, purchase_order_line_id=L["pol"], item_id=I["istd"], quantity=5, uom_id=ea, inventory_quantity=5, warehouse_id=I["w1"]),
      "ck_goods_receipt_line_positions")
trial("T15b a percent promotion states its percentage (null-safe check)", lambda cx: ins(cx, "promotion", id=new(), company_id=co, code="P3", name="P", priority=1,
      start_date="2026-11-01", item_id=I["istd"], kind="percent"), "ck_promotion_kind_fields")
trial("T22 GR/IR layers of one line never overlap", lambda cx: ins(cx, "purchase_order_line_gr_ir_layer", id=new(), company_id=co, purchase_order_line_id=L["pol"],
      from_position=29, to_position=40, price_numerator=1, price_denominator=1), "ex_purchase_order_line_gr_ir_layer_overlap")
trial("T23 a layer's price is an exact rational of integers", lambda cx: ins(cx, "purchase_order_line_gr_ir_layer", id=new(), company_id=co, purchase_order_line_id=L["pol"],
      from_position=30, to_position=40, price_numerator=D("1.5"), price_denominator=1), "ck_purchase_order_line_gr_ir_layer_price")
trial("T24 a receipt credits GR/IR (negative amount)", lambda cx: ins(cx, "purchase_order_line_gr_ir_posting", id=new(), company_id=co, purchase_order_line_id=L["pol"],
      document_id=GR[0][0], line_number=1, posting_kind="receipt", from_position=0, to_position=1, gr_ir_amount=10), "ck_purchase_order_line_gr_ir_posting_sign")
first_post = X("select id from purchase_order_line_gr_ir_posting where document_id=%s", (GR[1][0],)).fetchone()[0]
def reverse_twice(cx):
    for _ in range(2):
        ins(cx, "purchase_order_line_gr_ir_posting", id=new(), company_id=co, purchase_order_line_id=L["pol"], document_id=GR[1][0], line_number=1,
            posting_kind="receipt", from_position=10, to_position=30, gr_ir_amount=666667, reversal_of_posting_id=first_post)
trial("T25 a GR/IR posting is reversed at most once", reverse_twice, "uq_purchase_order_line_gr_ir_posting_reversal_of_posting_id")
trial("T26 GR/IR postings are append-only", lambda cx: cx.execute("update purchase_order_line_gr_ir_posting set gr_ir_amount=0 where id=%s", (first_post,)), "append-only")
trial("T27 GR/IR layers never change (a position keeps its first price)", lambda cx: cx.execute("update purchase_order_line_gr_ir_layer set price_numerator=1"), "append-only")
def sq(**o):
    v = dict(id=new(), company_id=co, item_id=I["istd"], warehouse_id=I["w1"], bin_id=I["b1"], quantity=1); v.update(o)
    return lambda cx: ins(cx, "stock_quantity", **v)
trial("T28 no stock key goes below zero", lambda cx: cx.execute("update stock_quantity set quantity = quantity - 21 where item_id=%s", (I["istd"],)), "ck_stock_quantity_quantity")
trial("T29 the stock key treats null lot, serial, handling unit and owner as one value", sq(), "uq_stock_quantity_key")
trial("T30 a stock row's bin belongs to its warehouse", sq(bin_id=I["b2"]), "fk_stock_quantity_bin")
trial("T31 a serial has at most one unit in a row", sq(serial_number_id=I["ser"], quantity=2), "ck_stock_quantity_serial")
def serial_twice(cx):
    sq(serial_number_id=I["ser"])(cx); sq(serial_number_id=I["ser"], stock_status="blocked")(cx)
trial("T32 a serial is on hand at most once across statuses (INV-22)", serial_twice, "ux_stock_quantity_serial_on_hand")
trial("T33 material document lines are append-only (update)", lambda cx: cx.execute("update material_document_line set quantity=1 where id=%s", (GR[0][2],)), "append-only")
trial("T34 material document lines are append-only (delete)", lambda cx: cx.execute("delete from material_document_line where id=%s", (GR[0][2],)), "append-only")
def mdl_serial(cx):
    md = X("select id from material_document where document_id=%s", (GR[0][0],)).fetchone()[0]
    ins(cx, "material_document_line", id=new(), company_id=co, material_document_id=md, line_number=2, item_id=I["istd"], warehouse_id=I["w1"], movement_type_id=I["mt_pr"],
        direction="in", quantity=2, serial_number_id=I["ser"], company_amount=0, bin_id=I["b1"], posting_date="2026-11-10")
trial("T35 a serial-tracked material line has quantity 1", mdl_serial, "ck_material_document_line_serial_quantity")
trial("T36 one material document per posting document", lambda cx: ins(cx, "material_document", id=new(), company_id=co, document_id=GR[0][0], posting_date="2026-11-10"),
      "uq_material_document_document_id")
def jl_no_mdl(cx):
    d = doc(cx, "goods_receipt", "posted", "supp")
    ins(cx, "material_document", id=new(), company_id=co, document_id=d, posting_date="2026-11-10")
    journal(cx, d, [("inv", "debit", 1, dict(item_id=I["istd"], warehouse_id=I["w1"])), ("grir", "credit", 1, dict(purchase_order_line_id=L["pol"]))])
trial("T37 DS-06: an inventory line of a document with a material document needs its material line", jl_no_mdl, "needs its material document line")
trial("T38 a GR/IR journal line names an existing purchase order line (ADR-0030 rule 3 key)", lambda cx: journal(cx, doc(cx, "purchase_invoice", "posted", "supp"),
      [("cogs", "debit", 1, {}), ("grir", "credit", 1, dict(purchase_order_line_id=new()))]), "fk_journal_line_purchase_order_line")
def res(**o):
    v = dict(id=new(), company_id=co, demand_supply_line_id=dsl2, item_id=I["istd"], warehouse_id=I["w1"], quantity=5); v.update(o)
    return lambda cx: ins(cx, "stock_reservation", **v)
trial("T39 a reservation never fulfils more than its quantity", res(fulfilled_quantity=6), "ck_stock_reservation_progress")
trial("T40 a reservation is fulfilled exactly when fulfilled equals quantity", res(state="fulfilled", fulfilled_quantity=4), "ck_stock_reservation_fulfilled")
trial("T42 a reservation refers to a demand row of its own company", res(company_id=I["co2"]), "violates foreign key constraint")
def foreign_sol(cx):
    v = new(); ins(cx, "sales_order_line", id=v, company_id=co, sales_order_id=d_so, line_number=3, product_id=I["pstd"], item_id=I["istd"], quantity=1, uom_id=ea, inventory_quantity=1)
    ins(cx, "demand_supply_line", id=new(), recorded_at=NOW, company_id=I["co2"], item_id=I["istd"], warehouse_id=I["w1"], direction="demand", open_quantity=1,
        requested_date="2026-11-12", source_kind="sales_order_line", sales_order_line_id=v)
trial("T43 a demand row cannot name another company's sales order line (the draft's step 5 key)", foreign_sol, "violates foreign key constraint")
def task(**o):
    v = dict(id=new(), company_id=co, warehouse_id=I["w1"], task_kind="pick", item_id=I["istd"], quantity=5, from_bin_id=I["b1"], demand_supply_line_id=dsl2); v.update(o)
    return lambda cx: ins(cx, "warehouse_task", **v)
trial("T44 a pick task serves a demand row (ADR-0028 rule 2)", task(demand_supply_line_id=None), "ck_warehouse_task_pick_demand")
trial("T45 a confirmation never exceeds the task's quantity (task_quantity_exceeded)", task(state="confirmed", confirmed_quantity=6), "ck_warehouse_task_confirmed")
trial("T46 a short confirmation needs a shortage reason", task(state="confirmed", confirmed_quantity=3), "ck_warehouse_task_confirmed")
trial("T47 a task's bins belong to its warehouse", task(to_bin_id=I["b2"]), "fk_warehouse_task_to_bin")
trial("T48 a warehouse movement has one source and changes something", lambda cx: ins(cx, "warehouse_movement", id=new(), company_id=co, warehouse_id=I["w1"],
      item_id=I["istd"], quantity=1, from_bin_id=I["b1"], to_bin_id=I["b1"], from_stock_status="available", to_stock_status="available", business_date="2026-11-12",
      source_command="pack"), "ck_warehouse_movement_changes")
trial("T49 one preliminary price per item, area and period (null area counts once)", lambda cx: [ins(cx, "preliminary_price", id=new(), company_id=co, item_id=I["icfg"],
      posting_period_id=I["pp"], unit_price=1, price_source="cost_estimate") for _ in range(2)], "uq_preliminary_price_key")
trial("T50 a manual preliminary price names the human who set it", lambda cx: ins(cx, "preliminary_price", id=new(), company_id=co, item_id=I["icfg"],
      posting_period_id=I["pp"], unit_price=1, price_source="manual"), "ck_preliminary_price_manual")
def hold(**o):
    v = dict(id=new(), company_id=co, sales_order_id=d_so, partner_id=I["cust"], state="held", currency="VND", credit_limit_amount=1, credit_exposure_amount=2,
             held_at="2026-11-20T03:00:00Z"); v.update(o)
    return lambda cx: ins(cx, "credit_hold", **v)
trial("T51 one hold or standing release per order", hold(), "ux_credit_hold_current")
trial("T52 ReleaseCreditHold needs the releasing human and a reason", hold(state="lapsed", release_kind="manual", released_at="2026-11-21T03:00:00Z",
      released_by_user_id=I["user"], release_reason=" "), "ck_credit_hold_manual_release")
trial("T52b a manual release without any reason is refused too (null-safe check)", hold(state="lapsed", release_kind="manual", released_at="2026-11-21T03:00:00Z",
      released_by_user_id=I["user"]), "ck_credit_hold_manual_release")
trial("T53 a release by approval was never held", hold(state="lapsed", release_kind="approval", released_at="2026-11-21T03:00:00Z"), "ck_credit_hold_approval_release")
trial("T60 a handling unit's barcode is unique in the company", lambda cx: [ins(cx, "handling_unit", id=new(), company_id=co, code="HU" + str(n), barcode="HU-1",
      handling_unit_type_id=(X("insert into handling_unit_type (id, company_id, code, name) values (%s,%s,%s,'P') returning id", (new(), co, "PAL" + str(n))).fetchone()[0]),
      warehouse_id=I["w1"], bin_id=I["b1"]) for n in (1, 2)], "duplicate key value")
trial("T61 a pending receipt adjustment never applies more than its total", lambda cx: ins(cx, "pending_receipt_adjustment", id=new(), company_id=co,
      purchase_order_line_id=L["pol"], purchase_invoice_line_id=L["pil"], clearing_journal_line_id=GR[0][4][1], total_company_amount=100,
      quantity_to_receive=5, amount_to_apply=150), "ck_pending_receipt_adjustment_amount")
def pcn_line(cx):
    d = doc(cx, "purchase_credit_note", "draft", "supp", correction_of=d_pi)
    ins(cx, "purchase_credit_note", id=d, company_id=co, partner_id=I["supp"], currency="VND", document_date="2026-11-20", posting_date="2026-11-20", **SNAP)
    ins(cx, "purchase_credit_note_line", id=new(), company_id=co, purchase_credit_note_id=d, line_number=1, credit_kind="quantity", correction_of_line_id=L["pil"], line_amount=10)
trial("T62 a quantity credit of a supplier credit note carries its quantity", pcn_line, "ck_purchase_credit_note_line_kind_quantity")
def foreign_delivery(cx):
    d = doc(cx, "delivery", "draft", "x2", co="co2")
    ins(cx, "delivery", id=d, company_id=I["co2"], partner_id=I["x2"], document_date="2026-11-12", posting_date="2026-11-12", **SNAP)
    ins(cx, "delivery_line", id=new(), company_id=I["co2"], delivery_id=d, line_number=1, sales_order_line_id=L["sol2"], item_id=I["istd"], quantity=1, uom_id=ea,
        inventory_quantity=1, warehouse_id=I["w1"])
trial("T63 a delivery line cannot name another company's order line or item", foreign_delivery, "violates foreign key constraint")
def ret_line(cx):
    d = doc(cx, "return_from_customer", "draft", "cust", correction_of=d_dl)
    ins(cx, "return_from_customer", id=d, company_id=co, partner_id=I["cust"], document_date="2026-11-20", posting_date="2026-11-20", **SNAP)
    ins(cx, "return_from_customer_line", id=new(), company_id=co, return_from_customer_id=d, line_number=1, delivery_line_id=L["dl"], item_id=I["istd"], quantity=1,
        uom_id=ea, inventory_quantity=1, warehouse_id=I["w1"], bin_id=I["b2"])
trial("T64 a customer return's bin belongs to its warehouse", ret_line, "fk_return_from_customer_line_bin")
trial("T65 a sales invoice line with a delivery names its item", lambda cx: ins(cx, "sales_invoice_line", id=new(), company_id=co, sales_invoice_id=d_si, line_number=9,
      delivery_line_id=L["dl"], product_id=I["pstd"], quantity=1, uom_id=ea, inventory_quantity=1, net_unit_price=1, line_amount=1), "ck_sales_invoice_line_delivery_item")
trial("T66 installments with a discount date carry the discount percent", lambda cx: ins(cx, "document_installment", company_id=co, document_id=d_si, installment_number=3,
      due_date="2026-12-31", transaction_amount=1, discount_due_date="2026-12-10"), "ck_document_installment_discount")
c.close()
print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
sys.exit(0 if all(r[0] for r in RESULTS) else 1)
