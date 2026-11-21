"""Scenario: valuation by site (ADR-0068 rules 2, 7-9, 11; ADR-0020 rules 8, 17 notes of 2026-11-21). Not product code.

Run: python t32_site_valuation.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs).

Rules that live in command code or the stock lock helper are written here as small reference functions, tested, and then run
against rows of the DDL, as the other labs do.
V: the valuation area (rule 7; rule 8; INV-810): both columns null at level company; at level site only valuation_site_id, the
   site of the line's warehouse (a transit warehouse through its valuation warehouse); at level warehouse only
   valuation_warehouse_id (the warehouse, or a transit warehouse's valuation warehouse).
N: the period-end adjustment of a transfer (rule 9): inside one area it changes the issue and the receipt by the same amount,
   so the area's value does not change; between areas it moves value.
B: the command checks of rule 2 and rule 11: site_branch_mismatch, site_required, warehouse_site_fixed, and the transfer route
   whose lead time may be omitted (and becomes 0) only inside one site.
C: the DDL text: the level CHECK lists company, site and warehouse.
With --load: the level CHECK; physical warehouses carry a site and transit ones none (ck_warehouse_site), a site of the same
company; material_document_line keeps at most one area column, a site of its company, and no valuation type (reserved,
ADR-0020 rule 17 note); INV-810 in SQL on lines written at level site; preliminary_price keyed by the area pair with NULLS NOT
DISTINCT; stock_value per (item, warehouse, valuation type), a null type counting as one value, and a set type refused
(reserved); value neutrality of a site-internal transfer and the value moved by a transfer between sites, summed per site over
stock_value; the DDL does not hold the branch rule (a command check), and the reference function finds the mismatching
warehouse among the DDL's rows.
Not covered: the stock lock helper, the costing solve, account determination, the posting commands.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from fx_adr74 import DOCS, RESULTS, build, check, conn, doc, ins, new, reset_and_load, trial  # noqa: E402


# ======================================================================= reference functions
def site_of_warehouse(wh, warehouses):
    """master_data.contract.site_of_warehouse (rule 2): a physical warehouse's site; a transit or goods-sent warehouse takes
    the site of its valuation warehouse."""
    w = warehouses[wh]
    return w["site_id"] if w["kind"] == "physical" else warehouses[w["valuation_warehouse_id"]]["site_id"]


def valuation_area(level, wh, warehouses):
    """(valuation_site_id, valuation_warehouse_id) that the stock lock helper writes (rule 8; INV-810)."""
    if level == "company":
        return (None, None)
    if level == "site":
        return (site_of_warehouse(wh, warehouses), None)
    w = warehouses[wh]
    return (None, wh if w["kind"] == "physical" else w["valuation_warehouse_id"])


def adjust_transfer(values, area_of, issue_wh, receipt_wh, delta):
    """Period-end adjustment of a transfer valued at a preliminary price: the issue and the receipt both change by delta
    (rule 9). Returns the new values per warehouse and the change of value per area."""
    new_values = dict(values)
    new_values[issue_wh] -= delta
    new_values[receipt_wh] += delta
    change = {}
    for wh in values:
        change[area_of(wh)] = change.get(area_of(wh), 0) + new_values[wh] - values[wh]
    return new_values, {a: v for a, v in change.items() if v != 0}


def check_warehouse(site_branch, warehouse_branch, kind="physical"):
    """site_branch_mismatch (rule 2): a site with a branch gives each physical warehouse that branch."""
    return "site_branch_mismatch" if kind == "physical" and site_branch is not None and warehouse_branch != site_branch else None


def choose_site(site_id, active_sites):
    """CreateWarehouse (rule 2): the only active site by default; with several, site_required."""
    if site_id is not None:
        return site_id, None
    return (active_sites[0], None) if len(active_sites) == 1 else (None, "site_required")


def change_site(has_material_lines):
    return "warehouse_site_fixed" if has_material_lines else None


def route_lead_time(lead_time_days, source_site, destination_site):
    """CreateTransferRoute (rule 11): lead time may be omitted only inside one site, and is then 0."""
    if lead_time_days is not None:
        return lead_time_days, None
    return (0, None) if source_site == destination_site else (None, "validation_failed")


# ======================================================================= V: the valuation area
W = {"w1": {"kind": "physical", "site_id": "S1", "valuation_warehouse_id": None}, "w2": {"kind": "physical", "site_id": "S1", "valuation_warehouse_id": None},
     "w3": {"kind": "physical", "site_id": "S2", "valuation_warehouse_id": None}, "wt": {"kind": "transit", "site_id": None, "valuation_warehouse_id": "w1"}}
check("V01 at level company both columns are null; at level site only the site; at level warehouse only the warehouse (rule 8)",
      [valuation_area("company", "w1", W), valuation_area("site", "w2", W), valuation_area("warehouse", "w2", W)] == [(None, None), ("S1", None), (None, "w2")])
check("V02 a transit warehouse is valued in its valuation warehouse's area: its site at level site, the warehouse at level warehouse (rule 2)",
      valuation_area("site", "wt", W) == ("S1", None) and valuation_area("warehouse", "wt", W) == (None, "w1"))
check("V03 at level site, two warehouses of one site share an area and a warehouse of another site does not (rule 7)",
      valuation_area("site", "w1", W) == valuation_area("site", "w2", W) != valuation_area("site", "w3", W))

# ======================================================================= N: value neutrality
vals = {"w1": 1000, "w2": 500, "w3": 200, "wt": 0}
site_area = lambda wh: valuation_area("site", wh, W)
wh_area = lambda wh: valuation_area("warehouse", wh, W)
_, ch_in = adjust_transfer(vals, site_area, "w1", "w2", 7)
_, ch_out = adjust_transfer(vals, site_area, "w1", "w3", 7)
_, ch_wh = adjust_transfer(vals, wh_area, "w1", "w2", 7)
check("N01 at level site, the adjustment of a transfer inside the site leaves the area's value unchanged (rule 9)", ch_in == {}, ch_in)
check("N02 a transfer between sites moves the adjustment from the issuing site to the receiving site", ch_out == {("S1", None): -7, ("S2", None): 7}, ch_out)
check("N03 at level warehouse the same internal transfer moves value between two areas: the reason site is the standard (rule 7)",
      ch_wh == {(None, "w1"): -7, (None, "w2"): 7}, ch_wh)
_, ch_t = adjust_transfer(vals, site_area, "w1", "wt", 7)
check("N04 a dispatch into the site's own transit warehouse stays inside the area", ch_t == {}, ch_t)

# ======================================================================= B: command checks
check("B01 site_branch_mismatch: a physical warehouse of a site with a branch must carry that branch; a site without a branch leaves it free; a transit warehouse is not checked",
      [check_warehouse("BR1", "BR2"), check_warehouse("BR1", "BR1"), check_warehouse(None, "BR2"), check_warehouse("BR1", None, kind="transit")]
      == ["site_branch_mismatch", None, None, None])
check("B02 site_required: without a site, the only active site is taken; with two active sites the warehouse is refused",
      choose_site(None, ["S1"]) == ("S1", None) and choose_site(None, ["S1", "S2"]) == (None, "site_required") and choose_site("S2", ["S1", "S2"]) == ("S2", None))
check("B03 warehouse_site_fixed: the site changes only while the warehouse has no material document line", change_site(True) == "warehouse_site_fixed" and change_site(False) is None)
check("B04 a transfer route inside one site may omit its lead time and gets 0; between sites the lead time is required (rule 11)",
      route_lead_time(None, "S1", "S1") == (0, None) and route_lead_time(None, "S1", "S2")[1] == "validation_failed" and route_lead_time(3, "S1", "S2") == (3, None))

# ======================================================================= C: DDL text
ds20 = re.sub(r"\s+", " ", open(os.path.join(DOCS, "design", "DS-20-master-data.sql"), encoding="utf-8").read())
m = re.search(r"ck_company_valuation_area_level CHECK \(valuation_area_level IN \(([^)]*)\)\)", ds20)
check("C01 the level CHECK lists company, site and warehouse (rule 7)", m and set(re.findall(r"'(\w+)'", m.group(1))) == {"company", "site", "warehouse"}, m and m.group(1))

# ======================================================================= X: the DDL (--load)
if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("X00 load_all.py loads every DDL file", n_tables > 0, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    I = build(c)                                    # one site MAIN with w1, w2 and the transit warehouse wt valued in w1
    trial("X01 the valuation level is company, site or warehouse", lambda cx: cx.execute("update company set valuation_area_level='plant' where id=%s", (I["co"],)),
          "ck_company_valuation_area_level")
    X("update company set valuation_area_level='site' where id=%s", (I["co"],))     # the lab plays setup: level site (rule 7, standard preset)
    I["site2"], I["w3"], I["z3"], I["b3"] = new(), new(), new(), new()
    X("insert into site (id, company_id, code, name, kind) values (%s,%s,'S2','Second site','distribution')", (I["site2"], I["co"]))
    with c.transaction():
        X("insert into warehouse (id, company_id, site_id, code, name, kind, default_bin_id) values (%s,%s,%s,'W3','W3','physical',%s)", (I["w3"], I["co"], I["site2"], I["b3"]))
        X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'DEFAULT','Default')", (I["z3"], I["co"], I["w3"]))
        X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEFAULT',%s,'storage')",
          (I["b3"], I["co"], I["w3"], I["z3"], "W3-DEFAULT" + I["t"].upper()))

    def warehouse(cx, kind="physical", site=None, valuation=None, co="co", branch=None):
        w, z, b = new(), new(), new()
        cx.execute("insert into warehouse (id, company_id, site_id, valuation_warehouse_id, code, name, kind, default_bin_id, branch_id) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                   (w, I[co], site, valuation, "WX" + w.hex[:6], "WX", kind, b, branch))
        cx.execute("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'DEFAULT','Default')", (z, I[co], w))
        cx.execute("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEFAULT',%s,'storage')", (b, I[co], w, z, "BX" + b.hex[:10].upper()))
        return w
    trial("X02 a physical warehouse carries a site (ck_warehouse_site)", lambda cx: warehouse(cx), "ck_warehouse_site")
    trial("X03 a transit warehouse carries none: its site is its valuation warehouse's", lambda cx: warehouse(cx, kind="transit", site=I["site"], valuation=I["w1"]), "ck_warehouse_site")
    trial("X04 a warehouse's site is of its company", lambda cx: warehouse(cx, site=I["site"], co="co2"), "warehouse_company_id_site_id_fkey")

    WH = {r[0]: {"kind": r[1], "site_id": r[2], "valuation_warehouse_id": r[3]}
          for r in X("select id, kind, site_id, valuation_warehouse_id from warehouse where company_id=%s", (I["co"],)).fetchall()}
    LEVEL = X("select valuation_area_level from company where id=%s", (I["co"],)).fetchone()[0]
    mt = new()
    X("""insert into movement_type (id, code, name, direction, value_source, costing_role, offset_transaction_key, needs_reference, sap_analog, added_in)
         values (%s,%s,'Transfer issue','out','preliminary_price','revalued_issue','inventory_transfer',false,'311','0.1.0')""", (mt, "lab_transfer" + I["t"]))
    md = new()
    X("insert into material_document (id, company_id, document_id, posting_date) values (%s,%s,%s,'2026-11-10')", (md, I["co"], doc(c, I, "stock_transfer", state="posted")))
    LN = iter(range(1, 1000))

    def mline(cx, wh, bin_, area=None, **o):
        vs, vw = area if area is not None else valuation_area(LEVEL, wh, WH)
        v = dict(id=new(), company_id=I["co"], material_document_id=md, line_number=next(LN), item_id=I["item"], warehouse_id=wh, movement_type_id=mt,
                 direction="out", quantity=1, company_amount=100, bin_id=bin_, posting_date="2026-11-10", valuation_site_id=vs, valuation_warehouse_id=vw)
        v.update(o)
        ins(cx, "material_document_line", **v)
    with c.transaction():
        for wh, b in ((I["w1"], I["b1"]), (I["w2"], I["b2"]), (I["wt"], I["bt"]), (I["w3"], I["b3"])):
            mline(c, wh, b)
    check("X05 lines of w1, w2, the transit warehouse and w3, with the area the helper writes at level site, are stored", True)
    rows = X("select warehouse_id, valuation_site_id, valuation_warehouse_id from material_document_line where material_document_id=%s", (md,)).fetchall()
    bad = [r for r in rows if (r[1], r[2]) != valuation_area(LEVEL, r[0], WH)]
    sites = {r[1] for r in rows}
    check("X06 INV-810 in SQL: every line's area pair equals the reference for level site; w1, w2 and the transit warehouse share the site, w3 has its own",
          not bad and len(rows) == 4 and sites == {I["site"], I["site2"]}, bad)
    trial("X07 a line keeps at most one area column (ck_material_document_line_valuation_area)",
          lambda cx: mline(cx, I["w1"], I["b1"], area=(I["site"], I["w1"])), "ck_material_document_line_valuation_area")
    I["site_x"] = new()
    X("insert into site (id, company_id, code, name, kind) values (%s,%s,'SX','Other company site','factory')", (I["site_x"], I["co2"]))
    trial("X08 the area's site is of the line's company", lambda cx: mline(cx, I["w1"], I["b1"], area=(I["site_x"], None)), "material_document_line_company_id_valuation_site_id_fkey")
    trial("X09 the valuation type is reserved and never set in Phase 1 (ADR-0020 rule 17 note)",
          lambda cx: mline(cx, I["w1"], I["b1"], valuation_type="new"), "ck_material_document_line_valuation_type")

    fy, pp = new(), new()
    X("insert into fiscal_year (id, company_id) values (%s,%s)", (fy, I["co"]))
    X("insert into posting_period (id, company_id, fiscal_year_id, start_date, end_date) values (%s,%s,%s,'2026-11-01','2026-11-30')", (pp, I["co"], fy))

    def price(cx, site=None, wh=None):
        ins(cx, "preliminary_price", id=new(), company_id=I["co"], item_id=I["item"], valuation_site_id=site, valuation_warehouse_id=wh, posting_period_id=pp,
            unit_price=100, price_source="prior_actual")
    price(c, site=I["site"]); price(c, site=I["site2"])
    check("X10 one preliminary price per site area and period", True)
    trial("X11 a second price for the same site area and period is refused (uq_preliminary_price_key)", lambda cx: price(cx, site=I["site"]), "uq_preliminary_price_key")
    price(c)
    trial("X12 the company-level area (both null) is one value under NULLS NOT DISTINCT: a second one is refused", lambda cx: price(cx), "uq_preliminary_price_key")
    trial("X13 a price names at most one area column", lambda cx: price(cx, site=I["site"], wh=I["w1"]), "ck_preliminary_price_valuation_area")

    def sv(cx, wh, amount, **o):
        ins(cx, "stock_value", id=new(), company_id=I["co"], item_id=I["item"], warehouse_id=wh, company_amount=amount, **o)
    for wh, amount in (("w1", 1000), ("w2", 500), ("wt", 0), ("w3", 200)):
        sv(c, I[wh], amount)
    trial("X14 one stock_value row per (item, warehouse, valuation type): a second row with a null type is refused (NULLS NOT DISTINCT)",
          lambda cx: sv(cx, I["w1"], 1), "uq_stock_value_key")
    trial("X15 the valuation type of stock_value is reserved and never set in Phase 1", lambda cx: sv(cx, I["w2"], 1, valuation_type="new"), "ck_stock_value_valuation_type")
    PER_SITE = """select coalesce(w.site_id, v.site_id), sum(s.company_amount) from stock_value s join warehouse w on w.company_id = s.company_id and w.id = s.warehouse_id
                  left join warehouse v on v.company_id = w.company_id and v.id = w.valuation_warehouse_id where s.company_id = %s and s.item_id = %s group by 1"""

    def per_site():
        return dict(X(PER_SITE, (I["co"], I["item"])).fetchall())

    def adjust(issue, receipt, delta):     # what the period-end adjustment writes through the stock lock helper (rule 9)
        with c.transaction():
            X("update stock_value set company_amount = company_amount - %s where company_id=%s and item_id=%s and warehouse_id=%s", (delta, I["co"], I["item"], I[issue]))
            X("update stock_value set company_amount = company_amount + %s where company_id=%s and item_id=%s and warehouse_id=%s", (delta, I["co"], I["item"], I[receipt]))
    before = per_site()
    adjust("w1", "w2", 7)
    after_in = per_site()
    per_wh = dict(X("select warehouse_id, company_amount from stock_value where company_id=%s and item_id=%s", (I["co"], I["item"])).fetchall())
    check("X16 a transfer adjustment inside the site moves stock_value per warehouse (w1 993, w2 507) and leaves the site's sum unchanged (rule 9; ADR-0020 rule 6)",
          after_in == before and per_wh[I["w1"]] == 993 and per_wh[I["w2"]] == 507, (before, after_in))
    adjust("w1", "w3", 7)
    after_out = per_site()
    check("X17 a transfer adjustment between sites moves 7 from the first site to the second, as the reference function says",
          after_out[I["site"]] == before[I["site"]] - 7 and after_out[I["site2"]] == before[I["site2"]] + 7, after_out)

    br1, br2 = new(), new()
    for b, code in ((br1, "BR1"), (br2, "BR2")):
        X("insert into branch (id, company_id, code, name) values (%s,%s,%s,%s)", (b, I["co"], code, code))
    I["site_b"] = new()
    X("insert into site (id, company_id, code, name, kind, branch_id) values (%s,%s,'SB','Branch site','store',%s)", (I["site_b"], I["co"], br1))
    with c.transaction():
        w_ok = warehouse(c, site=I["site_b"], branch=br1)
        w_bad = warehouse(c, site=I["site_b"], branch=br2)
    rows = X("""select w.id, s.branch_id, w.branch_id, w.kind from warehouse w join site s on s.company_id = w.company_id and s.id = w.site_id
                where w.company_id = %s""", (I["co"],)).fetchall()
    found = sorted(r[0] for r in rows if check_warehouse(r[1], r[2], r[3]))
    check("X18 the DDL stores a warehouse whose branch differs from its site's (the rule is a command check, site_branch_mismatch); the reference function finds exactly that warehouse",
          found == [w_bad] and w_ok not in found, found)
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
