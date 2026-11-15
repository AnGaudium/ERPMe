"""Scenario: DS-20 master data DDL (ADR-0018, ADR-0019, ADR-0023, ADR-0045) loaded with DS-06 (lab finding L-13).

Part M checks constraints the database holds (it does not cover the rules commands enforce, ADR-0045 rule 13).
Part P checks the price lookup of ADR-0045 rules 4 and 17 on real rows, with exact fractions: the entered unit
first; else the quantity converted exactly to the inventory unit (product unit, else unit conversion) and the price
converted back and rounded half up to ten decimals; the highest quantity break not above the quantity; the entry
valid on the date; option extras per inventory unit, a product-specific extra winning over an all-products one.
"""
import os, re
from decimal import Decimal as D, ROUND_HALF_UP
from fractions import Fraction as F
from lab import *

c = conn(); c.autocommit = True
X = c.execute
B = '{"kind": "company_decision"}'
I = {k: new() for k in ["user", "co", "co2", "ig", "vc", "itg", "ig2", "vc2", "itg2", "ea", "ctn", "kg", "g", "bag", "cm", "prod", "prod2", "prod_kg",
                        "item1", "item_kg", "item_co2", "attr_color", "attr_size", "v_red", "v_blue", "v_s", "attr_finish", "v_matte", "v_gloss",
                        "attr_engr", "v_engr", "pl", "pl_buy", "pg", "ptg", "partner", "partner2", "sa", "acct"]}
t = str(I["co"])[-8:]
X("insert into currency (code, minor_unit) values ('VND',0),('USD',2) on conflict do nothing")
X("insert into user_account values (%s)", (I["user"],))
for k, code in (("co", "C5-"), ("co2", "C5B-")):
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,legal_form,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','joint_stock','warehouse',%s,'vi')", (I[k], code + t, I["user"]))
for k, code, kind, dec in (("ea", "EA" + t, "count", 0), ("ctn", "CT" + t, "count", 0), ("kg", "KG" + t, "mass", 3), ("g", "G" + t, "mass", 0),
                           ("bag", "BAG" + t, "count", 0), ("cm", "CM" + t, "length", 2)):
    X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,%s,%s)", (I[k], code, code, kind, dec))
X("insert into uom_conversion (id, from_uom_id, to_uom_id, numerator, denominator) values (%s,%s,%s,1000,1)", (new(), I["kg"], I["g"]))   # 1 kg = 1000 g; grams take the inverse (ADR-0056 rule 3)
for co, ig, vc, itg in (("co", "ig", "vc", "itg"), ("co2", "ig2", "vc2", "itg2")):
    X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,'goods','Goods',%s)", (I[ig], I[co], B))
    X("insert into valuation_class (id, company_id, code, name, basis) values (%s,%s,'merchandise','Merchandise',%s)", (I[vc], I[co], B))
    X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,'standard','Standard',%s)", (I[itg], I[co], B))
X("insert into partner_group (id, company_id, code, name, basis) values (%s,%s,'domestic','Domestic',%s)", (I["pg"], I["co"], B))
X("insert into partner_tax_group (id, company_id, code, name, directions, basis) values (%s,%s,'domestic','Domestic','{sale,purchase}',%s)", (I["ptg"], I["co"], B))
X("insert into system_account (id, code) values (%s,%s)", (I["sa"], "receivable_trade_" + t))
X("insert into account (id, company_id, code, system_account_id) values (%s,%s,'131',%s)", (I["acct"], I["co"], I["sa"]))
for k in ("partner", "partner2"):
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,'P','organization','VN')", (I[k], I["co"], k + t))
def product(cx, pid, ptype="stock", vc=True, company="co", tracking="none", inv="ea", pur="ctn"):
    s = "" if company == "co" else "2"
    cx.execute("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id,
                  sales_uom_id, item_tax_group_id, tracking) values (%s,%s,%s,'P',%s,%s,%s,%s,%s,%s,%s,%s)""",
               (pid, I[company], 'P-' + str(pid)[-8:], ptype, I["ig" + s], I["vc" + s] if vc else None, I[inv], I[pur], I[inv], I["itg" + s], tracking))
product(c, I["prod"])
product(c, I["prod_kg"], inv="kg", pur="kg")
product(c, I["prod2"], company="co2")
PU = "insert into product_uom (id, company_id, product_id, inventory_uom_id, uom_id, numerator, denominator, is_exact) values (%s,%s,%s,%s,%s,%s,%s,%s)"
X(PU, (new(), I["co"], I["prod"], I["ea"], I["ctn"], 24, 1, True))        # 1 carton = 24 each
X(PU, (new(), I["co"], I["prod_kg"], I["kg"], I["bag"], 7, 3, False))    # 1 bag = 7/3 kg: a ratio with no finite decimal (inexact, ADR-0056 rule 7)
X("insert into variant_attribute (id, company_id, code, name) values (%s,%s,'color','Color'),(%s,%s,'size','Size')", (I["attr_color"], I["co"], I["attr_size"], I["co"]))
X("insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, code, name) values (%s,%s,%s,'variant','red','Red'),(%s,%s,%s,'variant','blue','Blue'),(%s,%s,%s,'variant','s','S')",
  (I["v_red"], I["co"], I["attr_color"], I["v_blue"], I["co"], I["attr_color"], I["v_s"], I["co"], I["attr_size"]))
# Line options (ADR-0045 rule 15): attributes that do not create items
X("insert into variant_attribute (id, company_id, code, name, variant_mode) values (%s,%s,'finish','Finish','line_option'),(%s,%s,'engraving','Engraving','line_option')",
  (I["attr_finish"], I["co"], I["attr_engr"], I["co"]))
X("insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, code, name) values (%s,%s,%s,'line_option','matte','Matte'),(%s,%s,%s,'line_option','gloss','Gloss')",
  (I["v_matte"], I["co"], I["attr_finish"], I["v_gloss"], I["co"], I["attr_finish"]))
X("insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, code, name, is_custom) values (%s,%s,%s,'line_option','text','Text',true)", (I["v_engr"], I["co"], I["attr_engr"]))
X("insert into product_variant_attribute (company_id, product_id, variant_attribute_id, position) values (%s,%s,%s,1),(%s,%s,%s,2)", (I["co"], I["prod"], I["attr_color"], I["co"], I["prod"], I["attr_finish"]))
X("insert into product_variant_attribute (company_id, product_id, variant_attribute_id, position, is_required) values (%s,%s,%s,3,false)", (I["co"], I["prod"], I["attr_engr"]))
X("insert into product_attribute_value values (%s,%s,%s,%s),(%s,%s,%s,%s)", (I["co"], I["prod"], I["attr_finish"], I["v_matte"], I["co"], I["prod"], I["attr_finish"], I["v_gloss"]))
X("insert into item (id, company_id, product_id, code, variant_key, length, width, height, dimension_uom_id, net_weight, gross_weight, weight_uom_id)"
  " values (%s,%s,%s,'SKU-RED',%s,40,30,20,%s,1.2,1.5,%s)", (I["item1"], I["co"], I["prod"], sorted([I["v_red"]]), I["cm"], I["kg"]))
X("insert into item_variant_value (company_id, item_id, product_id, variant_attribute_id, variant_attribute_value_id) values (%s,%s,%s,%s,%s)",
  (I["co"], I["item1"], I["prod"], I["attr_color"], I["v_red"]))                       # a valid variant value row
X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'SKU-KG')", (I["item_kg"], I["co"], I["prod_kg"]))
X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'SKU-CO2')", (I["item_co2"], I["co2"], I["prod2"]))
X("insert into price_list (id, company_id, code, name, kind, currency, is_default) values (%s,%s,'RETAIL','Retail','sale','VND',true)", (I["pl"], I["co"]))
X("insert into price_list (id, company_id, code, name, kind, currency) values (%s,%s,'BUY','Buy','purchase','VND')", (I["pl_buy"], I["co"]))
def entry(item, uom, minq, start, end, price, cx=None):
    (cx or c).execute("insert into price_list_entry (id, company_id, price_list_id, item_id, uom_id, minimum_quantity, start_date, end_date, unit_price) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      (new(), I["co"], I["pl"], I[item], I[uom], minq, start, end, price))
entry("item1", "ea", 0, "2026-01-01", "2026-12-31", "10000")
entry("item1", "ea", 100, "2026-01-01", "2026-12-31", "9000")
entry("item1", "ea", 0, "2027-01-01", None, "11000")
entry("item_kg", "kg", 0, "2026-01-01", None, "10000")
entry("item_kg", "kg", 5, "2026-01-01", None, "9500")
c.close()

def trial(name, fn, should_fail, match=None):
    class Rollback(Exception): pass
    cx = conn()
    try:
        with cx.transaction():
            fn(cx); cx.execute("set constraints all immediate"); raise Rollback()
    except Rollback:
        ok, detail = not should_fail, "succeeded (rolled back)"
    except Exception as e:
        msg = str(e).splitlines()[0]; ok, detail = should_fail and (match is None or match in msg), "failed: " + msg
    finally:
        cx.close()
    RESULTS.append((ok, name, detail)); print(("PASS " if ok else "FAIL ") + name + " -- " + detail)
def check(name, got, want):
    ok = got == want; RESULTS.append((ok, name, str(got))); print(("PASS " if ok else "FAIL ") + f"{name} -- {got}")

# ---- M: constraints ----
trial("M01 a declaring branch needs a tax ID", lambda cx: cx.execute("insert into branch (id, company_id, code, name, is_declaring_unit) values (%s,%s,'B1','B1',true)", (new(), I["co"])), True, "ck_branch_declaring_unit_tax_id")
trial("M02 a stock product needs a valuation class", lambda cx: product(cx, new(), vc=False), True, "ck_product_valuation_class")
trial("M03 a service has no valuation class", lambda cx: product(cx, new(), ptype="service"), True, "ck_product_valuation_class")
trial("M04 a non-stock product cannot be lot-tracked", lambda cx: product(cx, new(), ptype="non_stock", vc=False, tracking="lot"), True, "ck_product_tracking_stock")
trial("M05 item dimensions need a unit", lambda cx: cx.execute("insert into item (id, company_id, product_id, code, variant_key, length) values (%s,%s,%s,'X1',%s,5)", (new(), I["co"], I["prod"], [I["v_blue"]])), True, "ck_item_dimension_uom")
trial("M06 gross weight below net weight is rejected", lambda cx: cx.execute("insert into item (id, company_id, product_id, code, variant_key, net_weight, gross_weight, weight_uom_id) values (%s,%s,%s,'X2',%s,2,1,%s)", (new(), I["co"], I["prod"], [I["v_blue"]], I["kg"])), True, "ck_item_gross_weight")
trial("M07 an item cannot belong to another company's product", lambda cx: cx.execute("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'X3')", (new(), I["co2"], I["prod"])), True, "fk_item_product")
trial("M08 two items of a product cannot share a variant combination", lambda cx: cx.execute("insert into item (id, company_id, product_id, code, variant_key) values (%s,%s,%s,'X4',%s)", (new(), I["co"], I["prod"], [I["v_red"]])), True, "item_product_id_variant_key_key")
def blue_item(cx, attr, value):
    i = new()
    cx.execute("insert into item (id, company_id, product_id, code, variant_key) values (%s,%s,%s,%s,%s)", (i, I["co"], I["prod"], 'X-' + str(i)[-8:], [I[value]]))
    cx.execute("insert into item_variant_value (company_id, item_id, product_id, variant_attribute_id, variant_attribute_value_id) values (%s,%s,%s,%s,%s)", (I["co"], i, I["prod"], I[attr], I[value]))
trial("M09 a valid variant value row is accepted", lambda cx: blue_item(cx, "attr_color", "v_blue"), False)
trial("M10 a variant value must belong to its attribute", lambda cx: blue_item(cx, "attr_color", "v_s"), True, "fk_item_variant_value_value")
trial("M11 a variant value's attribute must be on the item's product", lambda cx: blue_item(cx, "attr_size", "v_s"), True, "fk_item_variant_value_product_attribute")
trial("M12 a line-option value can never be an item's variant value", lambda cx: blue_item(cx, "attr_finish", "v_gloss"), True, "fk_item_variant_value_value")
trial("M13 an allowed value needs its attribute on the product", lambda cx: cx.execute("insert into product_attribute_value values (%s,%s,%s,%s)", (I["co"], I["prod"], I["attr_size"], I["v_s"])), True, "fk_product_attribute_value_attribute")
trial("M14 an allowed value must belong to its attribute", lambda cx: cx.execute("insert into product_attribute_value values (%s,%s,%s,%s)", (I["co"], I["prod"], I["attr_finish"], I["v_red"])), True, "fk_product_attribute_value_value")
trial("M15 only a line-option value may ask for custom text", lambda cx: cx.execute("insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, code, name, is_custom) values (%s,%s,%s,'variant','c','C',true)", (new(), I["co"], I["attr_color"])), True, "ck_variant_attribute_value_custom")
trial("M16 a value must carry its attribute's mode", lambda cx: cx.execute("insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, code, name) values (%s,%s,%s,'line_option','c','C')", (new(), I["co"], I["attr_color"])), True, "fk_variant_attribute_value_attribute")
trial("M17 an attribute's mode cannot change once it has values", lambda cx: cx.execute("update variant_attribute set variant_mode='line_option' where id=%s", (I["attr_color"],)), True, "fk_variant_attribute_value_attribute")
trial("M18 a transit warehouse needs its valuation warehouse", lambda cx: cx.execute("insert into warehouse (id, company_id, code, name, kind, default_bin_id) values (%s,%s,'T1','T','transit',%s)", (new(), I["co"], new())), True, "ck_warehouse_valuation_warehouse")
trial("M19 every warehouse has a default bin", lambda cx: cx.execute("insert into warehouse (id, company_id, code, name, kind) values (%s,%s,'W0','W','physical')", (new(), I["co"])), True, "default_bin_id")
def wh_bins(cx, foreign_default=False, foreign_zone=False, same_barcode=False, bin_managed=False, processor=None, n=2):
    ws, zs, bs = [new() for _ in range(n)], [new() for _ in range(n)], [new() for _ in range(n)]
    for k in range(n):
        cx.execute("insert into warehouse (id, company_id, code, name, kind, default_bin_id, is_bin_managed, processor_partner_id) values (%s,%s,%s,'W','physical',%s,%s,%s)",
                   (ws[k], I["co"], 'W%d-' % k + str(ws[k])[-8:], bs[(k + 1) % n] if (foreign_default and k == 0) else bs[k], bin_managed and k == 0, processor))
        cx.execute("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'DEFAULT','Default')", (zs[k], I["co"], ws[k]))
    for k in range(n):
        z = zs[(k + 1) % n] if (foreign_zone and k == 0) else zs[k]
        cx.execute("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEFAULT',%s,'storage')",
                   (bs[k], I["co"], ws[k], z, ('BC-' + t if same_barcode else 'BC-' + str(bs[k])[-12:]).upper()))   # normalized form (ADR-0061 rule 7)
trial("M20 a warehouse with its own default bin is accepted (deferred link)", lambda cx: wh_bins(cx), False)
trial("M21 a warehouse's default bin cannot be another warehouse's bin", lambda cx: wh_bins(cx, foreign_default=True), True, "fk_warehouse_default_bin")
trial("M22 a bin's zone must be in the bin's warehouse", lambda cx: wh_bins(cx, foreign_zone=True), True, "fk_bin_zone")
trial("M23 bin barcodes are unique in a company", lambda cx: wh_bins(cx, same_barcode=True), True, "bin_company_id_barcode_key")
trial("M24 a bin-managed warehouse needs receiving and shipping bins", lambda cx: wh_bins(cx, bin_managed=True), True, "ck_warehouse_bin_managed")
trial("M25 one active processor warehouse per processor", lambda cx: wh_bins(cx, processor=I["partner"]), True, "ux_warehouse_processor")
trial("M26 only sale lists may include tax", lambda cx: cx.execute("insert into price_list (id, company_id, code, name, kind, currency, is_tax_included) values (%s,%s,'P','P','purchase','VND',true)", (new(), I["co"])), True, "ck_price_list_tax")
trial("M27 one default list per kind", lambda cx: cx.execute("insert into price_list (id, company_id, code, name, kind, currency, is_default) values (%s,%s,'R2','R2','sale','VND',true)", (new(), I["co"])), True, "ux_price_list_default")
trial("M28 one active by-product list per company", lambda cx: [cx.execute("insert into price_list (id, company_id, code, name, kind, currency) values (%s,%s,%s,'BP','by_product','VND')", (new(), I["co"], code)) for code in ("BP1", "BP2")], True, "ux_price_list_by_product")
trial("M29 a price entry of another company's list is rejected", lambda cx: cx.execute("insert into price_list_entry (id, company_id, price_list_id, item_id, uom_id, start_date, unit_price) values (%s,%s,%s,%s,%s,'2030-01-01',1)", (new(), I["co2"], I["pl"], I["item_co2"], I["ea"])), True, "fk_price_list_entry_list")
trial("M30 a price entry for another company's item is rejected", lambda cx: cx.execute("insert into price_list_entry (id, company_id, price_list_id, item_id, uom_id, start_date, unit_price) values (%s,%s,%s,%s,%s,'2030-01-01',1)", (new(), I["co"], I["pl"], I["item_co2"], I["ea"])), True, "fk_price_list_entry_item")
trial("M31 price entries of one list, item, unit and break never overlap", lambda cx: entry("item1", "ea", 0, "2026-06-01", "2027-03-31", "1", cx), True, "ex_price_list_entry_overlap")
trial("M32 an entry with another break may share the dates", lambda cx: entry("item1", "ea", 50, "2026-06-01", "2026-12-31", "9500", cx), False)
def extra(cx, value, attr="attr_finish", product="prod", start="2026-01-01", end=None, amount=500, mode="line_option"):
    cx.execute("insert into price_list_option_extra (id, company_id, price_list_id, product_id, variant_attribute_id, variant_attribute_value_id, variant_mode, start_date, end_date, unit_price_extra)"
               " values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (new(), I["co"], I["pl"], I[product] if product else None, I[attr], I[value], mode, start, end, amount))
trial("M33 an option extra's mode must match its value's mode (variant mode only for configurable products, by command)", lambda cx: extra(cx, "v_red", attr="attr_color", mode="line_option"), True, "fk_price_list_option_extra_value")
trial("M34 an option extra's value must belong to its attribute", lambda cx: extra(cx, "v_engr"), True, "fk_price_list_option_extra_value")
trial("M35 option extras for one value never overlap", lambda cx: [extra(cx, "v_matte"), extra(cx, "v_matte", start="2026-06-01")], True, "ex_price_list_option_extra_overlap")
trial("M36 a customer profile names a sale list, never a purchase list", lambda cx: cx.execute("insert into customer_profile (company_id, partner_id, receivable_account_id, price_list_id) values (%s,%s,%s,%s)", (I["co"], I["partner"], I["acct"], I["pl_buy"])), True, "fk_customer_profile_price_list")
def bank(cx):
    for _ in range(2):
        cx.execute("insert into partner_bank_account (id, company_id, partner_id, bank_name, account_number, holder_name) values (%s,%s,%s,'Bank','123','H')", (new(), I["co"], I["partner"]))
trial("M37 a bank account without a bank code cannot be entered twice", bank, True, "partner_bank_account_partner_id_bank_code_account_number_key")
trial("M38 a core unit code may not start with x-", lambda cx: cx.execute("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,'X','count',0)", (new(), 'x-' + t)), True, "ck_uom_company_code")
trial("M39 a company unit code must start with x-", lambda cx: cx.execute("insert into uom (id, company_id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,'Pack','count',0)", (new(), I["co"], 'PK' + t)), True, "ck_uom_company_code")
trial("M40 a conversion factor is positive", lambda cx: cx.execute(PU, (new(), I["co"], I["prod"], I["ea"], I["kg"], 0, 1, True)), True, "ck_product_uom_numerator")
trial("M41 a group row needs its basis", lambda cx: cx.execute("insert into item_group (id, company_id, code, name) values (%s,%s,'g2','G2')", (new(), I["co"])), True, "basis")
# M42: every DS-20 table carries company_id except the global catalogs (ADR-0045 rule 1; ADR-0022 rule 8).
ddl = open(os.environ.get("ERPME_DS20", os.path.join(os.path.expanduser(os.environ.get("ERPME_DOCS", "~/Projects/ERPMe/docs")), "design", "DS-20-master-data.sql"))).read()
tables = re.findall(r"^CREATE TABLE (\w+)", ddl, re.M)
cx = conn()
missing = [tb for tb in tables if tb not in ("currency", "uom", "uom_conversion", "company") and not cx.execute(
    "select 1 from information_schema.columns where table_schema='erpme' and table_name=%s and column_name='company_id'", (tb,)).fetchone()]
cx.close()
check(f"M42 all {len(tables) - 4} company tables of DS-20 carry company_id (missing: {missing or 'none'})", missing, [])

# ---- P: price lookup (ADR-0045 rules 4, 17) ----
def q10(fr):
    return (D(fr.numerator) / D(fr.denominator)).quantize(D("0.0000000001"), rounding=ROUND_HALF_UP) if isinstance(fr, F) else fr
def best(cx, pl, item, uom, qty, on):
    rows = cx.execute("select minimum_quantity, unit_price from price_list_entry where price_list_id=%s and item_id=%s and uom_id=%s"
                      " and start_date <= %s and (end_date is null or end_date >= %s)", (pl, item, uom, on, on)).fetchall()
    ok = [(F(m), F(p)) for m, p in rows if F(m) <= qty]
    return max(ok)[1] if ok else None
def factor(cx, item, uom):
    """Inventory units per one unit: 1 for the inventory unit, else the product unit, else the unit conversion."""
    prod, inv = cx.execute("select p.id, p.inventory_uom_id from item i join product p on p.id=i.product_id where i.id=%s", (item,)).fetchone()
    if uom == inv: return prod, inv, F(1)
    r = cx.execute("select numerator, denominator from product_uom where product_id=%s and item_id is null and uom_id=%s", (prod, uom)).fetchone() or \
        cx.execute("select numerator, denominator from uom_conversion where from_uom_id=%s and to_uom_id=%s", (uom, inv)).fetchone() or \
        cx.execute("select denominator, numerator from uom_conversion where from_uom_id=%s and to_uom_id=%s", (inv, uom)).fetchone()   # the inverse (ADR-0056 rule 3)
    return prod, inv, (F(r[0], r[1]) if r else None)
def find_price(cx, pl, item, uom, qty, on, values=()):
    qty = F(str(qty))
    prod, inv, f = factor(cx, item, uom)
    if f is None: return "uom_not_allowed"
    base = best(cx, pl, item, uom, qty, on)
    if base is None and uom != inv:
        b = best(cx, pl, item, inv, qty * f, on)
        base = None if b is None else F(q10(b * f))
    if base is None: return None
    extra = F(0)
    for v in values:
        rows = cx.execute("select product_id, unit_price_extra from price_list_option_extra where price_list_id=%s and variant_attribute_value_id=%s"
                          " and (product_id=%s or product_id is null) and start_date <= %s and (end_date is null or end_date >= %s)", (pl, v, prod, on, on)).fetchall()
        pick = [r for r in rows if r[0] is not None] or rows          # product-specific wins
        extra += sum((F(r[1]) for r in pick), F(0))
    total = base + F(q10(extra * f))
    return None if total < 0 else q10(total)

cx = conn()
cases = [
    ("P01 base price for 5 each in 2026", ("item1", "ea", 5, "2026-06-01", ()), D("10000")),
    ("P02 the 100-each break applies at 100", ("item1", "ea", 100, "2026-06-01", ()), D("9000")),
    ("P03 the 2027 entry applies after the old one ends", ("item1", "ea", 5, "2027-02-01", ()), D("11000")),
    ("P04 a carton with no carton entry is priced from the each price x 24", ("item1", "ctn", 1, "2026-06-01", ()), D("240000")),
    ("P05 5 cartons = 120 each reach the each break", ("item1", "ctn", 5, "2026-06-01", ()), D("216000")),
    ("P06 no entry before the first start date", ("item1", "ea", 1, "2025-12-31", ()), None),
    ("P07 a bag of 7/3 kg: 10000 x 7/3 rounded half up to ten decimals", ("item_kg", "bag", 1, "2026-06-01", ()), D("23333.3333333333")),
    ("P08 3 bags = exactly 7 kg reach the 5 kg break: 9500 x 7/3", ("item_kg", "bag", 3, "2026-06-01", ()), D("22166.6666666667")),
    ("P09 2 bags = 4 2/3 kg stay below the 5 kg break", ("item_kg", "bag", 2, "2026-06-01", ()), D("23333.3333333333")),
    ("P10 grams through the unit conversion: 10000 / 1000", ("item_kg", "g", 500, "2026-06-01", ()), D("10.0000000000")),
    ("P11 a unit with no product unit and no conversion is not allowed", ("item1", "kg", 1, "2026-06-01", ()), "uom_not_allowed"),
]
for name, (it, u, qty, on, vals), want in cases:
    check(name, find_price(cx, I["pl"], I[it], I[u], qty, on, vals), want)
cx.close()
c = conn(); c.autocommit = True
c.execute("insert into price_list_entry (id, company_id, price_list_id, item_id, uom_id, minimum_quantity, start_date, unit_price) values (%s,%s,%s,%s,%s,0,'2026-01-01',230000)",
          (new(), I["co"], I["pl"], I["item1"], I["ctn"]))
c.execute("insert into price_list_entry (id, company_id, price_list_id, item_id, uom_id, minimum_quantity, start_date, unit_price) values (%s,%s,%s,%s,%s,10,'2026-01-01',4500000)",
          (new(), I["co"], I["pl"], I["item_kg"], I["bag"]))       # a bag entry only from 10 bags
extra(c, "v_gloss", amount=500)                                    # product-specific
extra(c, "v_gloss", product=None, amount=300)                      # all products: loses to the product-specific one
extra(c, "v_matte", product=None, amount=-20000)                   # a cheaper option
extra(c, "v_engr", attr="attr_engr", amount=1000, end="2026-03-31")  # expired before June
extra(c, "v_engr", attr="attr_engr", product="prod_kg", amount=300)
opt = [
    ("P12 the entered unit's entry always wins: a carton entry over the converted each price", ("item1", "ctn", 1, "2026-06-01", ()), D("230000")),
    ("P13 the entered unit's entry wins even above the each break (5 cartons = 120 each)", ("item1", "ctn", 5, "2026-06-01", ()), D("230000")),
    ("P14 no qualifying bag break (5 < 10) falls back to the kg price", ("item_kg", "bag", 5, "2026-06-01", ()), D("22166.6666666667")),
    ("P15 the bag entry applies from 10 bags", ("item_kg", "bag", 10, "2026-06-01", ()), D("4500000")),
    ("P16 gloss: the product-specific extra 500 wins over the all-products 300", ("item1", "ea", 5, "2026-06-01", ("v_gloss",)), D("10500")),
    ("P17 a gloss carton adds 500 x 24 to the carton entry", ("item1", "ctn", 1, "2026-06-01", ("v_gloss",)), D("242000")),
    ("P18 an expired extra adds nothing", ("item1", "ea", 5, "2026-06-01", ("v_engr",)), D("10000")),
    ("P19 an extra on a 7/3 unit: 300 x 7/3 rounded once", ("item_kg", "bag", 1, "2026-06-01", ("v_engr",)), D("24033.3333333333")),
    ("P20 a negative total gives no price", ("item1", "ea", 5, "2026-06-01", ("v_matte",)), None),
]
for name, (it, u, qty, on, vals), want in opt:
    check(name, find_price(c, I["pl"], I[it], I[u], qty, on, tuple(I[v] for v in vals)), want)
c.close()
print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
