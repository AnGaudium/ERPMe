"""Flow 6, second part: purchases in units other than the stock unit (ADR-0056, with its notes on ADR-0018, 0020, 0024,
0045 and 0047). Case A: bolts kept in pieces (H87), bought in cartons of 24 (exact), planned in cartons, received first in
pieces then in cartons, invoiced in cartons through an e-invoice whose unit text resolves by alias. Case B: sealant kept in
kg (3 decimals), bought in bags of 7/3 kg (inexact), three receipts of one bag by the cumulative rule, the return of one
receipt as its own source, a replacement receipt, and an e-invoice whose unit text is unknown and stays unresolved until a
person approves an alias."""
import datetime as dt
import hashlib
from decimal import Decimal as D
from fractions import Fraction as F

from .core import TRACE, W, ins, upd, new_id, now, sha, money, set_day, fmt, jsonable
from . import platform as P
from . import ledger as L
from . import pure, commerce as C
from . import uom as U
from .common import approval_walk


def q(x):
    return U.to_dec(x)


def fd(x, places=4):
    """A rational for reading: exact decimal when it terminates, else rounded with its fraction."""
    x = F(x)
    dd = U.to_dec(x)
    if x == F(str(dd)) and len(str(dd)) < 24:
        return format(dd.normalize(), "f")
    return f"{float(x):.{places}f} ({x.numerator}/{x.denominator})"


class Line:
    """A purchase order line with its GR/IR positions and its parts (ADR-0047 rule 13; ADR-0056 rule 10)."""
    def __init__(self, pol, item, code, uom_id, qty, f, src, inv_q, net):
        self.pol, self.item, self.code, self.uom, self.qty, self.f, self.src, self.Q = pol, item, code, uom_id, F(str(qty)), f, src, F(str(inv_q))
        self.price = F(str(net)) / self.Q                     # GR/IR price per inventory unit, exact (ADR-0047 rule 10)
        self.gr = pure.GrIrLine(layers=[(F(0), self.Q, self.price)])
        self.C, self.P = F(0), F(0)                           # receipts in the order unit: net entered, net inventory
        self.Ci, self.Pi = F(0), F(0)                         # invoices in the order unit
        self.R_other = F(0)
        self.T = F(0)
        self.parts = []                                       # receipt lines: (gr_line_id, unit, entered, inventory, returned_entered, returned_inv)

    def received(self):
        return self.gr.R


def item_units_view(db, item):
    """GetItemUnits (ADR-0056 rule 20), reduced: inventory unit, product rows, catalog units of the kind."""
    prod, inv = U.item_product(db, item)
    out = [{"unit": U.code_of(inv), "factor": "1/1", "source": "identity", "decimals": U.dec_of(inv)}]
    for uid, n, d, fs, ex, rid in db.all("select uom_id, numerator, denominator, factor_source, is_exact, id from product_uom where product_id=%s and is_active", (prod,)):
        out.append({"unit": U.code_of(uid), "factor": f"{n}/{d}", "source": "product", "factor_source": fs, "is_exact": ex, "row": str(rid), "decimals": U.dec_of(uid)})
    kind = db.val("select quantity_kind from uom where id=%s", (inv,))
    for uid, code in db.all("select id, code from uom where company_id is null and quantity_kind=%s and id<>%s order by code", (kind, inv)):
        r = U.to_inventory(db, uid, item=item)
        if "factor" in r:
            out.append({"unit": code, "factor": f"{r['factor'].numerator}/{r['factor'].denominator}", "source": "global", "decimals": U.dec_of(uid)})
    return out


def run(db):
    TRACE.start_flow(6, "Procure to pay (P2P)", "Mua hàng đến thanh toán (P2P)", "")
    set_day("2026-11-17")
    owner, buyer, pm, wk, acc, planner = (W.user[k] for k in ("owner", "buyer", "purchasing_manager", "warehouse_keeper", "accountant", "production_planner"))
    oa, ba, wa, aa = P.person("owner"), P.person("buyer"), P.person("warehouse_keeper"), P.person("accountant")
    omega, delta = W.partners["S-OMEGA"], W.partners["S-DELTA"]
    H87, KGM, CART, BAG = W.uom["H87"], W.uom["KGM"], W.uom["x-carton"], W.uom["x-bag"]

    # ------------------------------------------------ U1 item master: units on the product (ADR-0056 rules 4, 7)
    items = {}
    for code, name, inv, pu, n, d, vc in (("BOLT-M8", "Bolt M8 x 40 (sample)", H87, CART, 24, 1, "raw_material"),
                                         ("SEALANT", "Sealant powder (sample)", KGM, BAG, 7, 3, "raw_material")):
        pid = new_id("product")
        ins(db, "product", id=pid, code=code, name=name, product_type="stock", item_group_id=W.ig["other"], valuation_class_id=W.vc[vc],
            inventory_uom_id=inv, purchase_uom_id=pu, sales_uom_id=inv, item_tax_group_id=W.itg)
        iid = new_id("item")
        ins(db, "item", id=iid, product_id=pid, code=code)
        ex = U.is_exact(n, d, U.dec_of(inv), U.dec_of(pu))
        rid = new_id("product_uom")
        ins(db, "product_uom", id=rid, product_id=pid, uom_id=pu, inventory_uom_id=inv, numerator=n, denominator=d, factor_source="stated", is_exact=ex)
        P.audit(db, "CreateProductUom", oa, effect_class="master_data_change", subject_table="product_uom", subject_id=rid)
        step_warn = F(1, 10 ** U.dec_of(pu)) * F(n, d) < F(1, 10 ** U.dec_of(inv)) / 2
        W.items[code] = {"id": iid, "product": pid, "name": name, "uom": U.code_of(inv), "vc": vc, "ig": "other", "code": code}
        W.code_of[iid], W.code_of[pid] = code, code
        items[code] = {"id": iid, "product": pid, "inv": inv, "pu": pu, "f": F(n, d), "row": rid, "exact": ex,
                       "checks": ([] if ex else [{"code": "unit_inexact", "details": {"factor": f"{n}/{d}", "decimals": {U.code_of(pu): U.dec_of(pu), U.code_of(inv): U.dec_of(inv)}, "reason": "decimals"}}])
                                 + ([{"code": "unit_step_below_inventory_step"}] if step_warn else [])}
        ins(db, "item_low_level_code", item_id=iid, low_level_code=0)
        ins(db, "preliminary_price", id=new_id("preliminary_price"), item_id=iid, valuation_warehouse_id=W.wh, posting_period_id=L.period_of(W.today)[0],
            unit_price=D("10416.67") if code == "BOLT-M8" else D(30000), price_source="manual", set_by_user_id=owner["id"])
    ok_p, why_p = P.can(owner, "CreateProductUom", node="product")
    TRACE.step("person", f"{owner['name']} (owner)", "CreateProduct + CreateProductUom", "Item master: stock unit, purchase unit and the factor on the product",
               "Danh mục hàng: đơn vị tồn kho, đơn vị mua và hệ số quy đổi trên mặt hàng", mode="direct; leaf product (master_data_change)",
               rule="ADR-0056 rules 4, 7, 20; ADR-0018 rules 9-10",
               outputs={"items": [{"item": c, "inventory_unit": U.code_of(v["inv"]), "decimals": U.dec_of(v["inv"]), "purchase_uom_id": U.code_of(v["pu"]),
                                   "product_uom": {"unit": U.code_of(v["pu"]), "numerator": v["f"].numerator, "denominator": v["f"].denominator,
                                                   "factor_source": "stated", "is_exact": v["exact"], "row": str(v["row"])}, "check_results": v["checks"]}
                                  for c, v in items.items()],
                        "units": {c: item_units_view(db, v["id"]) for c, v in items.items()}, "permission": why_p},
               deterministic="is_exact by rule 7: n x 10^dI divisible by d x 10^dE (24 x 1 by 1 x 1: exact; 7 x 1000 by 3 x 1: inexact)",
               notes="only the owner template holds product edit, so product units are maintained by the owner (role-template-levels)")

    # ------------------------------------------------ U2 supplier items with an order unit, partner items, purchase list entries
    for sup, code, ou, mn, mult, proc, pcode in ((omega, "BOLT-M8", CART, 2, 1, 2, "OMG-M8X40"), (delta, "SEALANT", BAG, 1, 1, 2, "DMS-SEAL")):
        ins(db, "supplier_item", id=new_id("supplier_item"), supplier_partner_id=sup, item_id=items[code]["id"], order_uom_id=ou, supplier_processing_days=proc,
            transit_days=1, minimum_order_quantity=D(mn), order_multiple=D(mult), is_preferred=True, start_date=dt.date(2026, 11, 1))
        ins(db, "partner_item", id=new_id("partner_item"), partner_id=sup, item_id=items[code]["id"], partner_item_code=pcode,
            partner_item_name=W.items[code]["name"].replace(" (sample)", ""), uom_id=None)
        P.audit(db, "CreateSupplierItem", ba, effect_class="master_data_change", subject_table="supplier_item")
    for pl, code, uom_id, price in (("BUY-OMEGA", "BOLT-M8", CART, 250000), ("BUY-OMEGA", "BOLT-M8", H87, 11000), ("BUY-DELTA", "SEALANT", BAG, 70000)):
        ins(db, "price_list_entry", id=new_id("price_list_entry"), price_list_id=W.price_lists[pl], item_id=items[code]["id"], uom_id=uom_id,
            minimum_quantity=0, start_date=dt.date(2026, 11, 1), unit_price=D(price))
    P.audit(db, "SetPriceListEntries", P.person("purchasing_manager"), effect_class="master_data_change", subject_table="price_list")
    ins(db, "item_warehouse_planning", id=new_id("item_warehouse_planning"), item_id=items["BOLT-M8"]["id"], warehouse_id=W.wh, planning_method="net_requirements",
        replenishment_source="purchase", safety_stock_quantity=D(100), lot_size_method="exact", receiving_days=1)
    TRACE.step("person", f"{buyer['name']} (buyer) and {pm['name']} (purchasing_manager)", "CreateSupplierItem + SetPriceListEntries",
               "Supplier order units with minimum and multiple; prices per unit", "Đơn vị đặt hàng của nhà cung cấp, tối thiểu và bội số; giá theo đơn vị",
               mode="direct; leaf supplier_item at edit (buyer), price_list at edit (purchasing manager)", rule="ADR-0056 rules 14, 16; ADR-0024 rule 2",
               outputs={"supplier_items": [{"supplier": "S-OMEGA", "item": "BOLT-M8", "order_uom_id": "x-carton", "minimum": 2, "multiple": 1},
                                           {"supplier": "S-DELTA", "item": "SEALANT", "order_uom_id": "x-bag", "minimum": 1, "multiple": 1}],
                        "partner_items": [{"code": "OMG-M8X40", "uom_id": None}, {"code": "DMS-SEAL", "uom_id": None}],
                        "prices": [{"list": "BUY-OMEGA", "item": "BOLT-M8", "per": "x-carton", "price": 250000}, {"list": "BUY-OMEGA", "item": "BOLT-M8", "per": "H87", "price": 11000},
                                   {"list": "BUY-DELTA", "item": "SEALANT", "per": "x-bag", "price": 70000}],
                        "safety_stock_BOLT-M8": "100 H87"})

    # ------------------------------------------------ U3 planning: shortfall in pieces -> order unit, rounded up (rule 14)
    bolt = items["BOLT-M8"]
    prun = new_id("planning_run")
    ins(db, "planning_run", id=prun, planning_date=W.today, requested_by_user_id=planner["id"], scope_item_ids=[bolt["id"]], started_at=now())
    stock = L.on_hand(db, bolt["id"])[0]
    short = D(100) - stock
    q_order, inv_q, steps = U.order_unit_lot(short, bolt["f"], U.dec_of(CART), U.dec_of(H87), D(2), D(1))
    rel = W.today
    plo = new_id("planned_order")
    ins(db, "planned_order", id=plo, item_id=bolt["id"], warehouse_id=W.wh, order_type="purchase", supplier_partner_id=omega, need_date=W.today + dt.timedelta(days=5),
        quantity=q(inv_q), order_quantity=q(q_order), order_uom_id=CART, uom_numerator=24, uom_denominator=1, uom_factor_source="product",
        rounding_excess_quantity=q(inv_q) - short, release_date=rel, planning_run_id=prun)
    ins(db, "planned_order_pegging", id=new_id("planned_order_pegging"), planned_order_id=plo, pegging_target_kind="safety_stock", quantity=short)
    ins(db, "planned_order_pegging", id=new_id("planned_order_pegging"), planned_order_id=plo, pegging_target_kind="lot_size_excess", quantity=q(inv_q) - short)
    upd(db, "planning_run", {"id": prun}, state="completed", completed_at=now(), output_counts={"planned_orders": 1}, input_hash=sha([str(short)]), output_hash=sha([str(plo)]))
    TRACE.step("det", "planning: lot sizing in the supplier's order unit (RunPlanning scoped to BOLT-M8)", "RunPlanning (order unit)",
               "Planning converts the shortfall into cartons and rounds up", "Hoạch định quy nhu cầu thiếu ra thùng và làm tròn lên",
               mode="system job on behalf of the planner; netting in the inventory unit", rule="ADR-0056 rules 8 (up), 14; ADR-0024 rules 6, 15",
               inputs={"stock": stock, "safety_stock": 100, "shortfall": f"{fmt(short)} H87", "order_unit": "x-carton = 24/1 H87 (product_uom)", "minimum": "2 x-carton", "multiple": "1 x-carton"},
               outputs={"steps": [{"step": s_, "value": fd(v)} for s_, v in steps], "order_quantity": f"{q(q_order)} x-carton", "quantity": f"{q(inv_q)} H87",
                        "rounding_excess": f"{q(inv_q) - short} H87"},
               deterministic="100 / 24 = 25/6 cartons, rounded up to 5 (above the minimum of 2, a multiple of 1); 5 x 24 = 120 pieces half up; excess 20")

    # ------------------------------------------------ U4 conversion -> replenishment -> purchase request in cartons
    sysb = P.system_for(buyer)
    upd(db, "planned_order", {"id": plo}, state="converted")
    rr = new_id("replenishment_request")
    ins(db, "replenishment_request", id=rr, requested_by_user_id=buyer["id"])
    ins(db, "replenishment_request_line", replenishment_request_id=rr, line_number=1, origin_planned_order_id=plo, item_id=bolt["id"], warehouse_id=W.wh,
        order_type="purchase", supplier_partner_id=omega, quantity=q(q_order), uom_id=CART, uom_numerator=24, uom_denominator=1, uom_factor_source="product",
        inventory_quantity=q(inv_q), need_date=W.today + dt.timedelta(days=5), release_date=rel)
    prq = P.create_doc(db, "purchase_request", sysb, header={"buyer_id": W.employee["buyer"], "document_date": W.today}, number=P.next_number(db, "purchase_request", "PRQ"),
                       lines=[("purchase_request_line", dict(id=new_id("purchase_request_line"), purchase_request_id="__DOC__", line_number=1, item_id=bolt["id"],
                                                             quantity=q(q_order), uom_id=CART, uom_numerator=24, uom_denominator=1, uom_factor_source="product",
                                                             inventory_quantity=q(inv_q), warehouse_id=W.wh, requested_date=W.today + dt.timedelta(days=5),
                                                             suggested_supplier_id=omega, origin_planned_order_id=plo))])
    P.audit(db, "ConvertPlannedOrder", ba, subject_table="planned_order", subject_id=plo)
    lp = C.price_line(db, W.price_lists["BUY-OMEGA"], W.today, q(q_order), "x-carton", item=bolt["id"])
    dec, res = P.submit(db, prq, ba, {"amount": lp["amount"], "is_cost_unknown": False}, "SubmitPurchaseRequest")
    TRACE.step("person", f"{buyer['name']} (buyer)", "ConvertPlannedOrder + SubmitPurchaseRequest", "The buyer converts; the request carries the order unit and its snapshot",
               "NV mua chuyển đơn kế hoạch; đề nghị mua mang đơn vị đặt hàng và hệ số", mode="direct; request drafted by system on behalf of the buyer",
               rule="ADR-0056 rule 14 (hand-over); ADR-0043 rule 4 note (amount from the purchase list)",
               outputs={"replenishment_request_line": "5 x-carton, 24/1 product, 120 H87", "purchase_request": prq["number"], "amount": lp["amount"],
                        "state": P.doc_state(db, prq["id"])}, decision=P.decision_summary(dec), events=res["events"])

    # ------------------------------------------------ U5 purchase order copied from the request: unit and snapshot kept, uneven price
    unit_p, src_p, trail_p = U.propose_unit(db, bolt["id"], partner=omega, source_line=CART)
    _, src_up, trail_up = U.propose_unit(db, bolt["id"], partner=omega)
    pol_id = new_id("purchase_order_line")
    po = P.create_doc(db, "purchase_order", ba, header={"partner_id": omega, "partner_name": "Omega Fasteners (sample)", "partner_tax_id": "0109990884", "currency": "VND",
                                                       "price_list_id": W.price_lists["BUY-OMEGA"], "payment_term_id": W.terms["NET30"]["id"], "buyer_id": W.employee["buyer"],
                                                       "document_date": W.today},
                      lines=[("purchase_order_line", dict(id=pol_id, purchase_order_id="__DOC__", line_number=1,
                                                          purchase_request_line_id=db.val("select id from purchase_request_line where purchase_request_id=%s", (prq["id"],)),
                                                          item_id=bolt["id"], quantity=q(q_order), uom_id=CART, uom_numerator=24, uom_denominator=1, uom_factor_source="product",
                                                          inventory_quantity=q(inv_q), warehouse_id=W.wh, requested_date=W.today + dt.timedelta(days=5),
                                                          list_unit_price=lp["list_price"], net_unit_price=lp["net_unit_price"], line_amount=lp["amount"]))],
                      number=P.next_number(db, "purchase_order", "PO"), partner_id=omega, derived_from=P.latest_version(db, prq["id"])[0])
    C.write_steps(db, po["id"], 1, lp["list_price"], lp["net_unit_price"], lp["amount"])
    dec, res = P.submit(db, po, ba, {"amount": lp["amount"]}, "SubmitPurchaseOrder")
    A = Line(pol_id, bolt["id"], "BOLT-M8", CART, q_order, bolt["f"], "product", inv_q, lp["amount"])
    ins(db, "purchase_order_line_gr_ir_layer", id=new_id("purchase_order_line_gr_ir_layer"), purchase_order_line_id=pol_id, from_position=0, to_position=q(inv_q),
        price_numerator=D(A.price.numerator), price_denominator=D(A.price.denominator))
    ins(db, "demand_supply_line", id=new_id("demand_supply_line"), item_id=bolt["id"], warehouse_id=W.wh, direction="supply", open_quantity=q(inv_q),
        requested_date=W.today + dt.timedelta(days=5), ordered_date=W.today, source_kind="purchase_order_line", purchase_order_line_id=pol_id)
    P.set_state(db, prq, "closed", closed_reason="fulfilled")
    TRACE.step("person", f"{buyer['name']} (buyer)", "CreatePurchaseOrder + SubmitPurchaseOrder", "Order in cartons with the unit snapshot",
               "Đơn mua theo thùng, kèm ảnh chụp đơn vị", mode="direct; copied from the request (rule 11)", rule="ADR-0056 rules 9, 11, 13; ADR-0047 rule 10",
               outputs={"purchase_order": po["number"], "line": {"quantity": q(q_order), "uom": "x-carton", "uom_numerator": 24, "uom_denominator": 1,
                                                                 "uom_factor_source": "product", "inventory_quantity": f"{q(inv_q)} H87", "unit_price": lp["net_unit_price"],
                                                                 "line_amount": lp["amount"]},
                        "proposed_uom_source": src_p, "proposal_without_a_source_line": {"source": src_up, "trail": trail_up},
                        "state": P.doc_state(db, po["id"])}, decision=P.decision_summary(dec), events=res["events"])
    TRACE.step("det", "master_data.contract.convert_quantity + inventory.contract.set_order_line_gr_ir_price", "convert_quantity (BOLT-M8, x-carton)",
               "Deterministic conversion: where the factor comes from and the GR/IR price per piece", "Quy đổi tất định: nguồn hệ số và giá GR/IR mỗi cái",
               mode="pure functions", rule="ADR-0056 rules 6, 7, 9; ADR-0047 rules 10, 13",
               inputs={"item": "BOLT-M8", "unit": "x-carton", "quantity": q(q_order)},
               outputs={"resolution": ["identity: no (x-carton is not the inventory unit H87)", "item row: none", f"product row: product_uom {bolt['row']} x-carton = 24/1 H87",
                                       "global: not reached"],
                        "factor": "24/1", "source": "product", "is_exact": True, "inventory_quantity": f"round(5 x 24) = {q(inv_q)} H87",
                        "gr_ir_price": f"{lp['amount']} / {q(inv_q)} = {A.price.numerator}/{A.price.denominator} per H87 (= {float(A.price):.4f}, stored as an exact rational)",
                        "naive_rounded_price_drift": f"a price rounded to {money(A.price)} per piece would post {money(A.price) * 120} for 120 pieces, {money(A.price) * 120 - lp['amount']} off"},
               deterministic="item -> product -> global, first hit wins; the factor is a reduced fraction; the layer price is exact and rounding happens once per posting")

    # ------------------------------------------------ U6-U8 receipts: pieces (other unit), cartons (cumulative part), pieces
    tol = D(0)
    def receive(line, uom_id, entered, label, title_vi):
        if uom_id == line.uom:
            v, checks = U.convert_part(line.f, line.C, line.P, F(str(entered)), U.dec_of(U.item_product(db, line.item)[1]))
            snap = (line.f.numerator, line.f.denominator, line.src)
            how = f"cumulative part in the order unit: round(({fd(line.C)} + {entered}) x {line.f.numerator}/{line.f.denominator}) - {fd(line.P)} = {fd(v)}"
        else:
            r = U.to_inventory(db, uom_id, item=line.item)
            v = U.round_quantity(F(str(entered)) * r["factor"], U.dec_of(r["inventory_uom_id"]))
            snap = (r["factor"].numerator, r["factor"].denominator, r["source"])
            checks = [] if v == F(str(entered)) * r["factor"] else ["quantity_rounded"]
            how = f"another unit converts on its own: round({entered} x {r['factor'].numerator}/{r['factor'].denominator}) = {fd(v)} (takes no part in C or P)"
            if "quantity_rounded" in checks:
                line.T += F(1, 10 ** U.dec_of(r["inventory_uom_id"]))
        limit = line.Q * (1 + F(str(tol)) / 100) + line.T
        if line.received() + v > limit:
            raise RuntimeError("receipt_exceeds_order")
        gid = new_id("goods_receipt_line")
        a0 = line.received()
        amt, a, b = line.gr.post("R", v, line.price)
        gr = P.create_doc(db, "goods_receipt", wa, header={"partner_id": omega if line.code == "BOLT-M8" else delta, "partner_name": "Omega Fasteners (sample)" if line.code == "BOLT-M8" else "Delta Metal Supply (sample)",
                                                          "document_date": W.today, "posting_date": W.today},
                          lines=[("goods_receipt_line", dict(id=gid, goods_receipt_id="__DOC__", line_number=1, purchase_order_line_id=line.pol, item_id=line.item,
                                                             quantity=D(str(entered)), uom_id=uom_id, uom_numerator=snap[0], uom_denominator=snap[1], uom_factor_source=snap[2],
                                                             inventory_quantity=q(v), warehouse_id=W.wh, gr_ir_position_from=a, gr_ir_position_to=b))],
                          number=P.next_number(db, "goods_receipt", "GR"), partner_id=omega if line.code == "BOLT-M8" else delta)
        md_ = L.material_document(db, gr["id"], W.today)
        mdl = L.stock_move(db, md_, line.item, W.wh, "purchase_receipt", q(v), amt, source_line=1)
        L.post_entry(db, gr["id"], W.today, [
            {"acct": L.determine("inventory_posting", valuation_class="raw_material"), "side": "debit", "amount": amt, "item": line.item, "warehouse": W.wh, "mdl": mdl,
             "pol": line.pol, "key": "inventory_posting", "desc": f"receipt {line.code} {entered} {U.code_of(uom_id)} = {q(v)} {U.code_of(U.item_product(db, line.item)[1])}"},
            {"acct": L.determine("gr_ir_clearing"), "side": "credit", "amount": amt, "pol": line.pol, "key": "gr_ir_clearing", "desc": f"GR/IR positions {a}-{b}"}],
            description=f"goods receipt {gr['number']}")
        P.set_state(db, gr, "posted")
        ins(db, "purchase_order_line_gr_ir_posting", id=new_id("purchase_order_line_gr_ir_posting"), purchase_order_line_id=line.pol, document_id=gr["id"], line_number=1,
            posting_kind="receipt", from_position=a, to_position=b, gr_ir_amount=-amt)
        P.audit(db, "PostGoodsReceipt", wa, effect_class="posting", doc=gr, subject_table="goods_receipt", subject_id=gr["id"])
        if uom_id == line.uom:
            line.C += F(str(entered))
            line.P += v
        line.parts.append({"gr_line": gid, "doc": gr, "uom": uom_id, "q": F(str(entered)), "v": v, "r": F(0), "rv": F(0), "from": a, "to": b})
        db.x("update demand_supply_line set open_quantity=%s where purchase_order_line_id=%s", (q(max(line.Q - line.received(), F(0))), line.pol))
        if line.received() >= line.Q - line.T:
            db.x("update demand_supply_line set closed_reason='fulfilled' where purchase_order_line_id=%s", (line.pol,))
        TRACE.step("person", f"{wk['name']} (warehouse_keeper)", "CreateGoodsReceipt + PostGoodsReceipt", label, title_vi, mode="direct",
                   rule="ADR-0056 rules 10, 11; ADR-0047 rules 11, 13",
                   inputs={"entered": f"{entered} {U.code_of(uom_id)}", "snapshot": f"{snap[0]}/{snap[1]} {snap[2]}"},
                   outputs={"inventory_quantity": q(v), "conversion": how, "check_results": checks, "gr_ir_positions": f"{a}-{b}", "gr_ir_credit": amt,
                            "received_net": q(line.received()), "ordered": q(line.Q), "receipt_limit": q(limit), "C": str(line.C), "P": q(line.P)},
                   deterministic=f"GR/IR credit = round(V({b})) - round(V({a})) at {line.price.numerator}/{line.price.denominator} per inventory unit")
        return gr, v, amt

    receive(A, H87, 70, "Receipt 1: 70 pieces against the carton order", "Nhập lần 1: 70 cái cho đơn theo thùng")
    receive(A, CART, 2, "Receipt 2: 2 cartons in the order unit (cumulative part)", "Nhập lần 2: 2 thùng theo đơn vị đặt (phần lũy kế)")
    receive(A, H87, 2, "Receipt 3: the last 2 pieces", "Nhập lần 3: 2 cái còn lại")

    # ------------------------------------------------ U9 e-invoice in cartons; unit text by alias; agent (no LLM) drafts; person posts
    rid = import_record(db, aa, "0109990884", "OMEGA FASTENERS", "C26TOF", "0000789", po["number"], [(1, "OMG-M8X40", "Bu lông M8x40", "THÙNG", D(5), D(250000))])
    wi = P.raise_item(db, "supplier_invoice_received", "e_invoice_record", rid, ("role", "accountant"), due_days=2, details={"seller_tax_id": "0109990884"})
    run_ = P.start_run(db, "purchase_invoice", "work_item", wi["id"], acc, scope_kind="partner", scope_partner=omega, subject=("e_invoice_record", rid),
                       taint_source=("outside_subject", "e_invoice_record", rid))
    ut = U.resolve_unit_text(db, bolt["id"], "THÙNG", partner=omega)
    agent = P.Actor("agent", run=run_, on_behalf_of=acc)
    inv_q_part, checks = U.convert_part(A.f, A.Ci, A.Pi, F(5), 0)
    i_amt, ia, ib = A.gr.post("I", inv_q_part, A.price)
    net = money(D(5) * D(250000))
    unit_inv_price = F(str(net)) / inv_q_part
    gr_value_per_unit = (A.gr.V(F(str(ib))) - A.gr.V(F(str(ia)))) / (F(str(ib)) - F(str(ia)))
    lim = max(A.price * F(str(W.settings["purchasing.match_price_tolerance_percent"])) / 100, F(str(W.settings["purchasing.match_price_tolerance_amount"])))
    match = {"quantity": f"invoiced {fd(inv_q_part)} <= received {fd(A.received())} H87 (ordered {fd(A.Q)})", "price_invoice_per_H87": fd(unit_inv_price),
             "price_gr_ir_per_H87": fd(gr_value_per_unit), "difference": fd(abs(unit_inv_price - gr_value_per_unit)), "tolerance_per_H87": fd(lim),
             "results": [] if abs(unit_inv_price - gr_value_per_unit) <= lim and inv_q_part <= A.received() else ["match_price_difference"]}
    pinv = P.create_doc(db, "purchase_invoice", agent, header={"partner_id": omega, "partner_name": "Omega Fasteners (sample)", "partner_tax_id": "0109990884",
                                                              "partner_reference": "C26TOF-0000789", "external_document_key": {"seller_tax_id": "0109990884", "form": "1", "symbol": "C26TOF", "number": "0000789"},
                                                              "supplier_invoice_date": W.today, "document_date": W.today, "posting_date": W.today, "currency": "VND",
                                                              "payment_term_id": W.terms["NET30"]["id"]},
                        lines=[("purchase_invoice_line", dict(id=new_id("purchase_invoice_line"), purchase_invoice_id="__DOC__", line_number=1, line_kind="goods",
                                                              purchase_order_line_id=A.pol, item_id=bolt["id"], quantity=D(5), uom_id=ut["uom_id"], uom_numerator=24,
                                                              uom_denominator=1, uom_factor_source="product", inventory_quantity=q(inv_q_part), unit_price=D(250000), line_amount=net))],
                        partner_id=omega, work_item=wi["id"], workflow_step="purchase_invoice.draft", number="C26TOF-0000789")
    C.write_tax(db, pinv["id"], 1, net, "vat_in_10", D(10), stated=money(net * D("0.1")))
    P.audit(db, "CreatePurchaseInvoice", agent, doc=pinv, subject_table="purchase_invoice", subject_id=pinv["id"], draft_only=True)
    P.end_run(db, run_, "drafted")
    TRACE.step("llm", "purchase_invoice agent (deterministic steps only, no LLM call)", "ImportEInvoiceRecord + D2 map_lines + D3 + CreatePurchaseInvoice",
               "The e-invoice in cartons: code by partner item, unit text by alias, drafted", "Hóa đơn điện tử theo thùng: mã theo hàng của NCC, đơn vị theo bí danh",
               mode="agent run, tainted, draft only; every line resolved without the LLM", rule="ADR-0056 rules 12, 19; ADR-0051 rule 21 (D2, D3 in units)",
               outputs={"unit_text": "THÙNG", "normalized": ut["normalized"], "resolution": ut["trail"], "unit": ut.get("unit"),
                        "order_line_selected": f"{po['number']}/1 by inventory quantity: uninvoiced received {fd(A.received())} H87 = line {fd(inv_q_part)} H87",
                        "invoice_line": {"quantity": 5, "uom": "x-carton", "snapshot": "24/1 product", "inventory_quantity": q(inv_q_part), "amount": net},
                        "three_way_match_per_inventory_unit": match})
    dec, res = P.submit(db, pinv, aa, {"amount": net, "is_match_exceeded": bool(match["results"]), "is_direct_expense": False}, "SubmitPurchaseInvoice")
    tax = money(net * D("0.1"))
    with db.tx():
        eid, _ = L.post_entry(db, pinv["id"], W.today, [
            {"acct": L.determine("gr_ir_clearing"), "side": "debit", "amount": i_amt, "pol": A.pol, "key": "gr_ir_clearing", "desc": f"clear GR/IR positions {ia}-{ib}"},
            {"acct": L.determine("input_tax", tax_code="vat_in_10"), "side": "debit", "amount": tax, "tax_code": W.tax["vat_in_10"], "key": "input_tax", "desc": "stated VAT 10%"},
            {"acct": L.determine("payable_reconciliation"), "side": "credit", "amount": net + tax, "partner": omega, "key": "payable_reconciliation",
             "oi_create": {"kind": "invoice", "due_date": W.today + dt.timedelta(days=30), "reference": "C26TOF-0000789", "payment_term_id": W.terms["NET30"]["id"]}, "desc": "payable"}],
            description="purchase invoice C26TOF-0000789 (cartons)")
        P.set_state(db, pinv, "posted")
    ins(db, "purchase_order_line_gr_ir_posting", id=new_id("purchase_order_line_gr_ir_posting"), purchase_order_line_id=A.pol, document_id=pinv["id"], line_number=1,
        posting_kind="invoice", from_position=ia, to_position=ib, gr_ir_amount=i_amt)
    P.audit(db, "PostPurchaseInvoice", aa, effect_class="posting", doc=pinv, subject_table="purchase_invoice", subject_id=pinv["id"], policy_decision_id=dec["id"])
    A.Ci, A.Pi = A.Ci + 5, A.Pi + inv_q_part
    P.set_state(db, po, "closed", closed_reason="fulfilled")
    bal_A = A.gr.balance()
    TRACE.step("person", f"{acc['name']} (accountant)", "SubmitPurchaseInvoice + PostPurchaseInvoice", "The accountant posts the carton invoice: GR/IR is zero",
               "Kế toán ghi sổ hóa đơn theo thùng: GR/IR bằng không", mode="direct; tainted draft, a person posts", rule="ADR-0047 rules 13-14; ADR-0056 rules 10, 12",
               outputs={"invoice_part": f"round((0 + 5) x 24) - 0 = {inv_q_part} H87", "gr_ir_debit": i_amt, "gr_ir_balance_line": bal_A, "rounding_clearing": "not needed (exact unit, T = 0)"},
               decision=P.decision_summary(dec), events=[P.emit(db, "PurchaseInvoicePosted", "purchase_invoice", pinv["id"], aa, "PostPurchaseInvoice")])
    TRACE.check("BOLT-M8: stock 120 H87 at 1,250,000 and GR/IR zero after the invoice", L.on_hand(db, bolt["id"]) == (D(120), D(1250000)) and bal_A == 0,
                L.on_hand(db, bolt["id"]), "INV-92; ADR-0056 rule 1")

    # ================================================ Case B: inexact bag of 7/3 kg
    seal = items["SEALANT"]
    unit_b, src_b, trail_b = U.propose_unit(db, seal["id"], partner=delta)
    lpB = C.price_line(db, W.price_lists["BUY-DELTA"], W.today, 3, "x-bag", item=seal["id"])
    blk = U.block(db, unit_b, 3, item=seal["id"])
    polB = new_id("purchase_order_line")
    poB = P.create_doc(db, "purchase_order", ba, header={"partner_id": delta, "partner_name": "Delta Metal Supply (sample)", "partner_tax_id": "0109990651", "currency": "VND",
                                                        "price_list_id": W.price_lists["BUY-DELTA"], "payment_term_id": W.terms["NET30"]["id"], "buyer_id": W.employee["buyer"],
                                                        "document_date": W.today},
                       lines=[("purchase_order_line", dict(id=polB, purchase_order_id="__DOC__", line_number=1, item_id=seal["id"], warehouse_id=W.wh,
                                                           requested_date=W.today + dt.timedelta(days=3), list_unit_price=lpB["list_price"], net_unit_price=lpB["net_unit_price"],
                                                           line_amount=lpB["amount"], **blk))],
                       number=P.next_number(db, "purchase_order", "PO"), partner_id=delta)
    C.write_steps(db, poB["id"], 1, lpB["list_price"], lpB["net_unit_price"], lpB["amount"])
    decB, resB = P.submit(db, poB, ba, {"amount": lpB["amount"]}, "SubmitPurchaseOrder")
    B = Line(polB, seal["id"], "SEALANT", BAG, 3, seal["f"], blk["uom_factor_source"], blk["inventory_quantity"], lpB["amount"])
    ins(db, "purchase_order_line_gr_ir_layer", id=new_id("purchase_order_line_gr_ir_layer"), purchase_order_line_id=polB, from_position=0, to_position=blk["inventory_quantity"],
        price_numerator=D(B.price.numerator), price_denominator=D(B.price.denominator))
    ins(db, "demand_supply_line", id=new_id("demand_supply_line"), item_id=seal["id"], warehouse_id=W.wh, direction="supply", open_quantity=blk["inventory_quantity"],
        requested_date=W.today + dt.timedelta(days=3), ordered_date=W.today, source_kind="purchase_order_line", purchase_order_line_id=polB)
    TRACE.step("person", f"{buyer['name']} (buyer)", "CreatePurchaseOrder + SubmitPurchaseOrder (bags)", "Order of 3 bags of 7/3 kg: the proposed unit and an inexact factor",
               "Đơn 3 bao 7/3 kg: đơn vị đề xuất và hệ số không chẵn", mode="direct; no source line", rule="ADR-0056 rules 7, 9, 13, 14",
               outputs={"proposed_uom_source": src_b, "proposal_trail": trail_b, "line": {"quantity": 3, "uom": "x-bag", "uom_numerator": 7, "uom_denominator": 3,
                                                                                        "uom_factor_source": blk["uom_factor_source"], "inventory_quantity": f"{blk['inventory_quantity']} KGM",
                                                                                        "unit_price": lpB["net_unit_price"], "amount": lpB["amount"]},
                        "check_results": [{"code": "unit_inexact", "reason": "decimals"}], "gr_ir_price": f"{lpB['amount']} / 7 = {fd(B.price)} per KGM"},
               decision=P.decision_summary(decB), events=resB["events"])
    for k in (1, 2, 3):
        receive(B, BAG, 1, f"Bag receipt {k}: one bag by the cumulative rule", f"Nhập bao lần {k}: một bao theo quy tắc lũy kế")
    # return of receipt 2 as its own source (part-as-source): the whole part mirrors its stored inventory quantity
    part = B.parts[1]
    share = U.return_share(part["q"], part["v"], part["r"], part["rv"], F(1), 3)
    R_before = B.received()
    amt_ret = B.gr.cum(R_before) - B.gr.cum(R_before - share)
    amt_ret = U.to_dec(amt_ret)
    B.gr.R = R_before - share
    rt = P.create_doc(db, "return_to_supplier", wa, header={"partner_id": delta, "partner_name": "Delta Metal Supply (sample)", "document_date": W.today, "posting_date": W.today},
                      lines=[("return_to_supplier_line", dict(id=new_id("return_to_supplier_line"), return_to_supplier_id="__DOC__", line_number=1, goods_receipt_line_id=part["gr_line"],
                                                              item_id=seal["id"], quantity=D(1), uom_id=BAG, uom_numerator=7, uom_denominator=3, uom_factor_source=B.src,
                                                              inventory_quantity=q(share), warehouse_id=W.wh, gr_ir_position_from=q(B.gr.R), gr_ir_position_to=q(R_before)))],
                      number=P.next_number(db, "return_to_supplier", "RT"), partner_id=delta, derived_from=P.latest_version(db, part["doc"]["id"])[0])
    md_ = L.material_document(db, rt["id"], W.today)
    mdl = L.stock_move(db, md_, seal["id"], W.wh, "purchase_return", q(share), amt_ret, source_line=1)
    L.post_entry(db, rt["id"], W.today, [
        {"acct": L.determine("gr_ir_clearing"), "side": "debit", "amount": amt_ret, "pol": B.pol, "key": "gr_ir_clearing", "desc": f"GR/IR latest positions {q(B.gr.R)}-{q(R_before)}"},
        {"acct": L.determine("inventory_posting", valuation_class="raw_material"), "side": "credit", "amount": amt_ret, "item": seal["id"], "warehouse": W.wh, "mdl": mdl,
         "key": "inventory_posting", "desc": f"return 1 x-bag = {q(share)} KGM (receipt 2 as source)"}], description=f"return to supplier {rt['number']}")
    P.set_state(db, rt, "posted")
    ins(db, "purchase_order_line_gr_ir_posting", id=new_id("purchase_order_line_gr_ir_posting"), purchase_order_line_id=B.pol, document_id=rt["id"], line_number=1,
        posting_kind="return", from_position=q(B.gr.R), to_position=q(R_before), gr_ir_amount=amt_ret)
    P.audit(db, "PostReturnToSupplier", wa, effect_class="posting", doc=rt, subject_table="return_to_supplier", subject_id=rt["id"])
    dev_before = B.P - U.round_quantity(B.C * B.f, 3)
    B.C -= 1
    B.P -= share
    part["r"], part["rv"] = F(1), share
    dev_after = B.P - U.round_quantity(B.C * B.f, 3)
    B.T += abs(dev_after - dev_before)
    db.x("update demand_supply_line set open_quantity=%s, closed_reason=null where purchase_order_line_id=%s", (q(B.Q - B.received()), B.pol))
    TRACE.step("person", f"{wk['name']} (warehouse_keeper)", "CreateReturnToSupplier + PostReturnToSupplier", "Return of receipt 2: the part is its own source",
               "Trả lại lần nhập 2: phần nhập là nguồn của chính nó", mode="direct", rule="ADR-0056 rule 10 (returns take the part they name); ADR-0047 rule 13 (latest positions)",
               outputs={"part": f"receipt 2: 1 x-bag stored as {q(part['v'])} KGM", "return_quantity": f"{q(share)} KGM (mirrors the whole part)",
                        "gr_ir_debit": amt_ret, "gr_ir_positions": f"{q(B.gr.R)}-{q(R_before)} (latest)", "C": str(B.C), "P": q(B.P),
                        "deviation": f"P - round(C x f) = {q(dev_after)}", "tolerance_T": q(B.T)},
               deterministic="a return never posts more than its part: 2.334, not round(1 x 7/3) = 2.333")
    receive(B, BAG, 1, "Replacement receipt of one bag: the cumulative rule corrects itself", "Nhập bù một bao: quy tắc lũy kế tự điều chỉnh")

    # ------------------------------------------------ e-invoice for the bags: unknown unit text stays unresolved; alias proposal; person
    ridB = import_record(db, aa, "0109990651", "DELTA METAL SUPPLY", "C26TDM", "0000501", poB["number"], [(1, "DMS-SEAL", "Bột trám", "bịch", D(3), D(70000))])
    wiB = P.raise_item(db, "supplier_invoice_received", "e_invoice_record", ridB, ("role", "accountant"), due_days=2, details={"seller_tax_id": "0109990651"})
    runB = P.start_run(db, "purchase_invoice", "work_item", wiB["id"], acc, scope_kind="partner", scope_partner=delta, subject=("e_invoice_record", ridB),
                       taint_source=("outside_subject", "e_invoice_record", ridB))
    utB = U.resolve_unit_text(db, seal["id"], "bịch", partner=delta)
    agB = P.Actor("agent", run=runB, on_behalf_of=acc)
    plan = {"items": [{"command_type": "CreateUomAlias", "payload": {"alias": "bịch", "normalized_alias": U.normalize_unit_text("bịch"), "uom": "x-bag"}}],
            "evidence": {"e_invoice_record": str(ridB), "line": 1}}
    cp = P.create_doc(db, "change_proposal", agB, header={"plan": plan, "plan_hash": sha(plan), "evidence": [{"table": "e_invoice_record", "id": str(ridB)}],
                                                          "reason": "Unit text 'bịch' on the supplier's invoice is not known", "document_date": W.today},
                      work_item=wiB["id"], workflow_step="purchase_invoice.mapping", header_table="change_proposal", number="CP unit alias")
    ins(db, "change_proposal_item", id=new_id("change_proposal_item"), change_proposal_id=cp["id"], item_index=0, command_type="CreateUomAlias", schema_version=1,
        payload=plan["items"][0]["payload"], target_table="uom_alias", field_changes=[{"field": "alias", "new": "bịch"}, {"field": "uom", "new": "x-bag"}])
    P.audit(db, "CreateChangeProposal", agB, doc=cp, subject_table="change_proposal", subject_id=cp["id"], draft_only=True)
    P.note_item(db, wiB["id"], "agent_run", runB["id"], "Line 1 not drafted: unit text 'bịch' unresolved (unit_text_unresolved); alias proposed.", untrusted=True)
    P.end_run(db, runB, "drafted")
    TRACE.step("llm", "purchase_invoice agent (deterministic steps only, no LLM call)", "D2 map_lines (unit text) + CreateChangeProposal (CreateUomAlias)",
               "Unknown unit text 'bịch' is never guessed: the line stays unresolved, an alias is proposed", "Đơn vị 'bịch' không đoán: dòng chưa giải quyết, đề xuất bí danh",
               mode="agent run, tainted, draft only", rule="ADR-0056 rule 19; ADR-0029",
               outputs={"unit_text": "bịch", "normalized": utB["normalized"], "result": utB["result"], "trail": utB["trail"], "line_drafted": False,
                        "change_proposal": "CP unit alias", "is_tainted": cp["tainted"]})
    TRACE.check("an unknown unit text stays unit_text_unresolved", utB["result"] == "unit_text_unresolved", utB, "ADR-0056 rule 19")
    decA, resA = P.submit(db, cp, aa, {"amount": 0}, "SubmitChangeProposal")
    TRACE.step("person", f"{acc['name']} (accountant)", "SubmitChangeProposal", "The accountant submits the alias proposal", "Kế toán gửi duyệt đề xuất bí danh",
               mode="direct", rule="ADR-0029 rule 3", decision=P.decision_summary(decA), events=resA["events"], work_items=resA["items"])
    approval_walk(db, cp, ["owner"], "'bịch' is this supplier's word for the 7/3 kg bag", "ApproveChangeProposal", "The owner approves the alias",
                  "Giám đốc duyệt bí danh đơn vị", "ADR-0055 rule 7 (target permission CreateUomAlias: leaf product)")
    ins(db, "uom_alias", id=new_id("uom_alias"), alias="bịch", normalized_alias=U.normalize_unit_text("bịch"), uom_id=BAG)
    P.audit(db, "CreateUomAlias", P.system_for(owner), effect_class="master_data_change", subject_table="uom_alias", proposal_bound=True)
    P.set_state(db, cp, "closed", closed_reason="fulfilled")
    utB2 = U.resolve_unit_text(db, seal["id"], "bịch", partner=delta)
    inv_part, chk = U.convert_part(B.f, B.Ci, B.Pi, F(3), 3)
    ib_amt, iba, ibb = B.gr.post("I", inv_part, B.price)
    netB = money(D(3) * D(70000))
    priceB = F(str(netB)) / inv_part
    grvB = (B.gr.V(F(str(ibb))) - B.gr.V(F(str(iba)))) / (F(str(ibb)) - F(str(iba)))
    pinvB = P.create_doc(db, "purchase_invoice", aa, header={"partner_id": delta, "partner_name": "Delta Metal Supply (sample)", "partner_tax_id": "0109990651",
                                                            "partner_reference": "C26TDM-0000501", "external_document_key": {"seller_tax_id": "0109990651", "form": "1", "symbol": "C26TDM", "number": "0000501"},
                                                            "supplier_invoice_date": W.today, "document_date": W.today, "posting_date": W.today, "currency": "VND",
                                                            "payment_term_id": W.terms["NET30"]["id"]},
                         lines=[("purchase_invoice_line", dict(id=new_id("purchase_invoice_line"), purchase_invoice_id="__DOC__", line_number=1, line_kind="goods",
                                                               purchase_order_line_id=B.pol, item_id=seal["id"], quantity=D(3), uom_id=utB2["uom_id"], uom_numerator=7, uom_denominator=3,
                                                               uom_factor_source=B.src, inventory_quantity=q(inv_part), unit_price=D(70000), line_amount=netB))],
                         partner_id=delta, number="C26TDM-0000501")
    C.write_tax(db, pinvB["id"], 1, netB, "vat_in_10", D(10), stated=money(netB * D("0.1")))
    decI, resI = P.submit(db, pinvB, aa, {"amount": netB, "is_match_exceeded": abs(priceB - grvB) > lim, "is_direct_expense": False}, "SubmitPurchaseInvoice")
    taxB = money(netB * D("0.1"))
    with db.tx():
        L.post_entry(db, pinvB["id"], W.today, [
            {"acct": L.determine("gr_ir_clearing"), "side": "debit", "amount": ib_amt, "pol": B.pol, "key": "gr_ir_clearing", "desc": f"clear GR/IR positions {iba}-{ibb}"},
            {"acct": L.determine("input_tax", tax_code="vat_in_10"), "side": "debit", "amount": taxB, "tax_code": W.tax["vat_in_10"], "key": "input_tax", "desc": "stated VAT 10%"},
            {"acct": L.determine("payable_reconciliation"), "side": "credit", "amount": netB + taxB, "partner": delta, "key": "payable_reconciliation",
             "oi_create": {"kind": "invoice", "due_date": W.today + dt.timedelta(days=30), "reference": "C26TDM-0000501", "payment_term_id": W.terms["NET30"]["id"]}, "desc": "payable"}],
            description="purchase invoice C26TDM-0000501 (bags)")
        P.set_state(db, pinvB, "posted")
    ins(db, "purchase_order_line_gr_ir_posting", id=new_id("purchase_order_line_gr_ir_posting"), purchase_order_line_id=B.pol, document_id=pinvB["id"], line_number=1,
        posting_kind="invoice", from_position=iba, to_position=ibb, gr_ir_amount=ib_amt)
    P.audit(db, "PostPurchaseInvoice", aa, effect_class="posting", doc=pinvB, subject_table="purchase_invoice", subject_id=pinvB["id"], policy_decision_id=decI["id"])
    B.Ci, B.Pi = B.Ci + 3, B.Pi + inv_part
    bal_B = B.gr.balance()
    clearing = "not needed: R = I = 7.000 KGM" if B.gr.R == B.gr.I else f"R {B.gr.R} vs I {B.gr.I}: gr_ir_rounding_clearing within T = {B.T}"
    P.set_state(db, poB, "closed", closed_reason="fulfilled")
    TRACE.step("person", f"{acc['name']} (accountant)", "CreatePurchaseInvoice + PostPurchaseInvoice (bags)", "After the alias, the accountant books the bag invoice: GR/IR is zero",
               "Sau khi có bí danh, kế toán ghi sổ hóa đơn bao: GR/IR bằng không", mode="direct (a person from the record)", rule="ADR-0056 rules 10, 12, 19; ADR-0047 rules 13-14",
               outputs={"unit_text_now": utB2["trail"], "invoice_part": f"round((0 + 3) x 7/3) - 0 = {inv_part} KGM", "gr_ir_debit": ib_amt,
                        "match_per_KGM": {"invoice": fd(priceB), "gr_ir": fd(grvB)}, "gr_ir_balance_line": bal_B, "rounding_clearing": clearing},
               decision=P.decision_summary(decI), events=[P.emit(db, "PurchaseInvoicePosted", "purchase_invoice", pinvB["id"], aa, "PostPurchaseInvoice")])

    # ------------------------------------------------ checks of the scenario
    parts_B = [q(p["v"]) for p in B.parts]
    TRACE.check("SEALANT: bag receipts 2.333, 2.334, 2.333, return 2.334, replacement 2.334; stock 7.000 KGM at 210,000",
                parts_B == [D("2.333"), D("2.334"), D("2.333"), D("2.334")] and L.on_hand(db, seal["id"]) == (D("7.000"), D(210000)), {"parts": parts_B, "stock": L.on_hand(db, seal["id"])},
                "ADR-0056 rule 10 worked example")
    TRACE.check("SEALANT: GR/IR zero after the invoice, no residual", bal_B == 0, bal_B, "INV-92")
    TRACE.check("the returned part posted no more than the part", q(share) == q(part["v"]), {"share": q(share), "part": q(part["v"])}, "ADR-0056 rule 10; INV-601")
    TRACE.check("BOLT-M8 receipts sum to the order line's 120 pieces and the invoice part equals it", A.received() == A.Q and inv_q_part == A.Q, "", "ADR-0056 rule 10")
    TRACE.check("an alias resolves 'THÙNG' to x-carton", ut["result"] == "resolved" and ut["unit"] == "x-carton", ut, "ADR-0056 rule 19")
    TRACE.step("det", "ledger and inventory queries", "UoM scenario totals", "Totals: stock in the inventory unit, GR/IR per line, no drift",
               "Tổng kết: tồn kho theo đơn vị tồn, GR/IR theo dòng, không lệch làm tròn", mode="queries", rule="ADR-0056 rules 1, 10; INV-92, INV-602",
               outputs={"BOLT-M8": {"stock": f"{L.on_hand(db, bolt['id'])[0]} H87", "value": L.on_hand(db, bolt["id"])[1], "gr_ir": bal_A},
                        "SEALANT": {"stock": f"{L.on_hand(db, seal['id'])[0]} KGM", "value": L.on_hand(db, seal["id"])[1], "gr_ir": bal_B, "tolerance_T": q(B.T)},
                        "naive_per_part_rounding": "3 x round(7/3) = 6.999 KGM would leave 0.001 KGM and 30 VND open forever"})
    return True


def import_record(db, actor, tax_id, seller, symbol, number, order_ref, lines):
    """ImportEInvoiceRecord (ADR-0051 rule 20 note): the structured record through the package reader; duplicate key refused."""
    if db.val("select count(*) from e_invoice_record where direction='incoming' and seller_tax_id=%s and invoice_symbol=%s and invoice_number=%s", (tax_id, symbol, number)):
        raise RuntimeError("duplicate_external_document")
    xml = f"<HDon><MST>{tax_id}</MST><KHHDon>{symbol}</KHHDon><SHDon>{number}</SHDon></HDon>".encode()
    att = new_id("attachment")
    ins(db, "attachment", id=att, sha256=hashlib.sha256(xml).hexdigest(), media_type="application/xml", byte_count=len(xml), storage_key=f"sim/{att}.xml",
        data_label="internal", source_kind="upload", state="clean", is_accounting_evidence=True, contains_untrusted=True)
    rid = new_id("e_invoice_record")
    net = sum(q_ * p for *_, q_, p in lines)
    ins(db, "e_invoice_record", id=rid, direction="incoming", state="imported", seller_tax_id=tax_id, seller_name=seller, invoice_form="1", invoice_symbol=symbol,
        invoice_number=number, invoice_date=W.today, currency="VND", order_reference=order_ref, net_amount=net, tax_amount=money(net * D("0.1")),
        gross_amount=net + money(net * D("0.1")), signature_state="passed", authority_status="unchecked", imported_by_user_id=actor.user["id"], source_attachment_id=att)
    for n, code, name, unit, q_, p in lines:
        ins(db, "e_invoice_record_line", e_invoice_record_id=rid, line_number=n, seller_item_code=code, item_name=name, unit_text=unit, quantity=q_, unit_price=p,
            net_amount=q_ * p, tax_rate=D(10), stated_tax_amount=money(q_ * p * D("0.1")))
    P.audit(db, "ImportEInvoiceRecord", actor, subject_table="e_invoice_record", subject_id=rid)
    return rid
