"""Flow 8: scanning goods in (ADR-0061 rules 1-5, 7, 12-18; ADR-0063 rule 26; ADR-0056 rules 9-10). A GS1-128 scan with
GTIN, count, lot and expiry fills a receipt line in the purchase unit, which converts to the inventory unit; an unknown code
is refused, never guessed; a best-before date is kept apart from expiry by default. No LLM: the scan path is code only."""
import datetime as dt
from decimal import Decimal as D
from fractions import Fraction as F

from .core import TRACE, W, ins, upd, new_id, now, sha, set_day
from . import platform as P
from . import ledger as L
from . import commerce as C
from . import uom as U
from . import xdesign as X
from .common import probe
from .f6_uom import Line, q, fd

GS = "\x1d"


def run(db):
    TRACE.start_flow(8, "Barcode receipt", "Nhập kho bằng mã vạch",
                     "A GS1-128 label is scanned at the dock: the parser and EvaluateBarcode resolve GTIN, count, lot and expiry, fill the receipt "
                     "line in the purchase unit and convert it; an unknown code is refused; a best-before date never becomes an expiry date by default.")
    set_day("2026-11-27")
    T = X.lab("t19_barcode")
    S = X.lab("t24_settings")
    owner, buyer, wk = W.user["owner"], W.user["buyer"], W.user["warehouse_keeper"]
    oa, ba, wa = P.person("owner"), P.person("buyer"), P.person("warehouse_keeper")
    delta, KGM, BAG = W.partners["S-DELTA"], W.uom["KGM"], W.uom["x-bag"]

    # 1 item master: a lot-tracked adhesive in kg, bought in bags of 5/2 kg; the bag's GTIN-14 in the registry ------------------
    pid, iid = new_id("product"), new_id("item")
    ins(db, "product", id=pid, code="ADHESIVE", name="Two-part adhesive (sample)", product_type="stock", item_group_id=W.ig["other"],
        valuation_class_id=W.vc["raw_material"], inventory_uom_id=KGM, purchase_uom_id=BAG, sales_uom_id=KGM, item_tax_group_id=W.itg, tracking="lot")
    ins(db, "item", id=iid, product_id=pid, code="ADHESIVE")
    ins(db, "product_uom", id=new_id("product_uom"), product_id=pid, uom_id=BAG, inventory_uom_id=KGM, numerator=5, denominator=2, factor_source="stated",
        is_exact=U.is_exact(5, 2, 3, 0))
    ins(db, "item_low_level_code", item_id=iid, low_level_code=0)
    ins(db, "preliminary_price", id=new_id("preliminary_price"), item_id=iid, valuation_warehouse_id=W.wh, posting_period_id=L.period_of(W.today)[0],
        unit_price=D(32000), price_source="manual", set_by_user_id=owner["id"])
    W.items["ADHESIVE"] = {"id": iid, "product": pid, "name": "Two-part adhesive (sample)", "uom": "KGM", "vc": "raw_material", "ig": "other", "code": "ADHESIVE"}
    W.code_of[iid] = W.code_of[pid] = "ADHESIVE"
    data13 = "1893123400012"
    gtin = data13 + str(T.check_digit(data13))
    ib = new_id("item_barcode")
    ins(db, "item_barcode", id=ib, item_id=iid, uom_id=BAG, barcode=gtin)
    P.audit(db, "CreateItemBarcode", oa, effect_class="master_data_change", subject_table="item_barcode", subject_id=ib)
    ins(db, "price_list_entry", id=new_id("price_list_entry"), price_list_id=W.price_lists["BUY-DELTA"], item_id=iid, uom_id=BAG, minimum_quantity=0,
        start_date=dt.date(2026, 11, 1), unit_price=D(80000))
    reg_row = db.one("select barcode_type, encoding, is_legacy from barcode where barcode=%s", (gtin,))
    def_bb = X.get_setting(db, "barcode.gs1.best_before_fills_expiry")
    TRACE.step("person", f"{owner['name']} (owner)", "CreateProduct + CreateProductUom + CreateItemBarcode",
               "A lot-tracked adhesive in kg, bought in bags of 2.5 kg; the bag's GTIN-14 is registered", "Keo theo lô, tồn theo kg, mua theo bao 2,5 kg; đăng ký GTIN-14 của bao",
               mode="direct; leaf product (master_data_change)", rule="ADR-0061 rules 4, 7, 10; ADR-0056 rules 4, 7",
               outputs={"gtin": gtin, "check_digit": f"weights 3,1,... from the right of {data13} -> {gtin[-1]}", "registry_row": dict(zip(("barcode_type", "encoding", "is_legacy"), reg_row)),
                        "unit": "x-bag = 5/2 KGM (stated, exact)", "barcode.gs1.best_before_fills_expiry": def_bb},
               deterministic="trg_item_barcode_register writes the company-wide barcode registry after checking normalization and the check digit")
    TRACE.check("the trigger registered the GTIN-14 as an item_unit gtin", reg_row == ("item_unit", "gtin", False), reg_row, "ADR-0061 rule 7")

    # 2 order 3 bags --------------------------------------------------------------------------------------------------------------
    lp = C.price_line(db, W.price_lists["BUY-DELTA"], W.today, D(3), "x-bag", item=iid)
    pol = new_id("purchase_order_line")
    po = P.create_doc(db, "purchase_order", ba, header={"partner_id": delta, "partner_name": "Delta Metal Supply (sample)", "partner_tax_id": "0109990651",
                                                       "currency": "VND", "price_list_id": W.price_lists["BUY-DELTA"], "payment_term_id": W.terms["NET30"]["id"],
                                                       "buyer_id": W.employee["buyer"], "document_date": W.today},
                      lines=[("purchase_order_line", dict(id=pol, purchase_order_id="__DOC__", line_number=1, item_id=iid, quantity=D(3), uom_id=BAG,
                                                          uom_numerator=5, uom_denominator=2, uom_factor_source="product", inventory_quantity=D("7.500"),
                                                          warehouse_id=W.wh, requested_date=W.today, list_unit_price=lp["list_price"],
                                                          net_unit_price=lp["net_unit_price"], line_amount=lp["amount"]))],
                      number=P.next_number(db, "purchase_order", "PO"), partner_id=delta)
    C.write_steps(db, po["id"], 1, lp["list_price"], lp["net_unit_price"], lp["amount"])
    P.submit(db, po, ba, {"amount": lp["amount"]}, "SubmitPurchaseOrder")
    ln = Line(pol, iid, "ADHESIVE", BAG, 3, F(5, 2), "product", F(15, 2), lp["amount"])
    ins(db, "purchase_order_line_gr_ir_layer", id=new_id("purchase_order_line_gr_ir_layer"), purchase_order_line_id=pol, from_position=0, to_position=D("7.5"),
        price_numerator=D(ln.price.numerator), price_denominator=D(ln.price.denominator))
    TRACE.step("person", f"{buyer['name']} (buyer)", "CreatePurchaseOrder + SubmitPurchaseOrder", "Order 3 bags = 7.500 kg at 80,000 per bag",
               "Đặt 3 bao = 7,500 kg, 80.000 mỗi bao", mode="direct", rule="ADR-0056 rules 9, 11", outputs={"order": po["number"], "line_amount": lp["amount"],
                                                                                                         "gr_ir_price_per_KGM": fd(ln.price)})

    # registry and typed rows as EvaluateBarcode reads them through the contracts
    def registry():
        reg = T.Registry()
        for b, bt, enc, leg in db.all("select barcode, barcode_type, encoding, is_legacy from barcode"):
            reg.rows[b] = dict(type=bt, owner=None, retired_type=None, retired_owner=None, legacy=leg, enc=enc, retired_months=None)
        data = {"item_barcode": {b: (str(i), str(u)) for b, i, u in db.all("select barcode, item_id, uom_id from item_barcode")},
                "lots": {(str(i), c): str(l) for l, i, c in db.all("select id, item_id, code from lot")}, "serials": {}}
        return reg, data

    def receive(scan_raw, label, label_vi, expect_lot):
        reg, data = registry()
        r = T.resolve({"raw": scan_raw, "symbology_identifier": "]C1"}, reg, data, {"capture": ("lot",)}, today=W.today)
        el = {k: v["raw"] for k, v in r["elements"].items()}
        cand = r["candidates"][0]
        fills = bool(X.get_setting(db, "barcode.gs1.best_before_fills_expiry"))
        lot_dates = S.receive_lot(el, fills)
        qty = F(cand["quantity"])
        v, checks = U.convert_part(ln.f, ln.C, ln.P, qty, 3)
        lot = new_id("lot")
        ins(db, "lot", id=lot, item_id=iid, code=cand["lot_code"], expiry_date=lot_dates["expiry_date"], best_before_date=lot_dates["best_before_date"])
        amt, a, b = ln.gr.post("R", v, ln.price)
        gid = new_id("goods_receipt_line")
        scan = {"raw": scan_raw.replace(GS, "<GS>"), "symbology_identifier": "]C1", "source": "pwa_camera", "decoder": "wasm", "confirmed_as_read": False}
        gr = P.create_doc(db, "goods_receipt", wa, header={"partner_id": delta, "partner_name": "Delta Metal Supply (sample)", "document_date": W.today, "posting_date": W.today},
                          lines=[("goods_receipt_line", dict(id=gid, goods_receipt_id="__DOC__", line_number=1, purchase_order_line_id=pol, item_id=iid,
                                                             quantity=D(str(qty)), uom_id=BAG, uom_numerator=5, uom_denominator=2, uom_factor_source="product",
                                                             inventory_quantity=q(v), warehouse_id=W.wh, lot_id=lot, gr_ir_position_from=a, gr_ir_position_to=b))],
                          number=P.next_number(db, "goods_receipt", "GR"), partner_id=delta)
        md_ = L.material_document(db, gr["id"], W.today)
        mdl = L.stock_move(db, md_, iid, W.wh, "purchase_receipt", q(v), amt, source_line=1)
        L.post_entry(db, gr["id"], W.today, [
            {"acct": L.determine("inventory_posting", valuation_class="raw_material"), "side": "debit", "amount": amt, "item": iid, "warehouse": W.wh, "mdl": mdl,
             "pol": pol, "key": "inventory_posting", "desc": f"receipt ADHESIVE {qty} x-bag = {q(v)} KGM, lot {cand['lot_code']}"},
            {"acct": L.determine("gr_ir_clearing"), "side": "credit", "amount": amt, "pol": pol, "key": "gr_ir_clearing", "desc": f"GR/IR positions {a}-{b}"}],
            description=f"goods receipt {gr['number']}")
        P.set_state(db, gr, "posted")
        ins(db, "purchase_order_line_gr_ir_posting", id=new_id("purchase_order_line_gr_ir_posting"), purchase_order_line_id=pol, document_id=gr["id"], line_number=1,
            posting_kind="receipt", from_position=a, to_position=b, gr_ir_amount=-amt)
        P.audit(db, "PostGoodsReceipt", wa, effect_class="posting", doc=gr, subject_table="goods_receipt", subject_id=gr["id"])
        ln.C += qty
        ln.P += v
        TRACE.step("det", "inventory query EvaluateBarcode (erpme.gs1 parser, registry, typed rows)", "EvaluateBarcode",
                   label, label_vi, mode="query, pure function of the scan, the registry and the business date", rule="ADR-0061 rules 1-5, 12-14, 17",
                   inputs={"scan": scan}, outputs={"encoding": r["encoding"], "elements": el, "issues": r["issues"], "checks": r["checks"],
                                                    "candidate": {k: (str(v_) if isinstance(v_, F) else v_) for k, v_ in cand.items() if k not in ("item_id", "uom_id")}},
                   deterministic="AIs split by the predefined-length table and GS; check digit, dates (century window from the business date), required pairs")
        TRACE.step("person", f"{wk['name']} (warehouse_keeper)", "CreateGoodsReceipt (scan) + PostGoodsReceipt",
                   f"The scan fills the line: {qty} x-bag, lot {cand['lot_code']}; it converts to {q(v)} KGM", f"Quét điền dòng: {qty} bao, lô {cand['lot_code']}; quy đổi {q(v)} kg",
                   mode="direct; the scan object is kept next to each field it filled", rule="ADR-0061 rules 16-17; ADR-0063 rule 26; ADR-0056 rules 9-10",
                   outputs={"line": {"quantity": str(qty), "uom_id": "x-bag", "snapshot": "5/2 product", "inventory_quantity": q(v),
                                     "conversion": f"round(({fd(ln.C - qty)} + {qty}) x 5/2) - {fd(ln.P - v)} = {fd(v)}"},
                            "lot": {"code": cand["lot_code"], **{k: (str(x) if x else None) for k, x in lot_dates.items()}},
                            "barcode.gs1.best_before_fills_expiry": fills, "gr_ir_positions": f"{a}-{b}", "gr_ir_credit": amt,
                            "lab_resolve_interim_expiry": str(cand.get("expiry_date")) if cand.get("expiry_date") else None})
        return r, cand, lot_dates, v

    # 3 scan with (01) GTIN, (17) expiry, (10) lot and (30) count: 2 bags ------------------------------------------------------------
    raw1 = f"01{gtin}17270531" + "10LOT-2611A" + GS + "302"
    r1, c1, l1, v1 = receive(raw1, "The GS1-128 scan resolves to the bag's item, 2 bags, lot LOT-2611A, expiry 2027-05-31",
                             "Mã GS1-128 xác định mặt hàng, 2 bao, lô LOT-2611A, hạn dùng 2027-05-31", True)
    TRACE.check("the scan fills the line in the purchase unit (2 x-bag) and converts it to 5.000 KGM", F(c1["quantity"]) == 2 and c1["quantity_uom_id"] == str(BAG)
                and v1 == F(5) and l1["expiry_date"] == dt.date(2027, 5, 31), {"cand": str(c1.get("quantity")), "v": str(v1)}, "ADR-0061 rule 17; ADR-0056 rule 10")

    # 4 an unknown code is refused ----------------------------------------------------------------------------------------------------
    reg, data = registry()
    r_unk = T.resolve({"raw": "4006381333931", "symbology_identifier": "]E0"}, reg, data, {}, today=W.today)
    try:
        T.confirm({"raw": "4006381333931", "symbology_identifier": "]E0"}, reg, data, [{"type": "lot", "item_id": iid}], today=W.today)
        conf = "accepted"
    except T.LabError as e:
        conf = e.code
    TRACE.step("det", "inventory query EvaluateBarcode + scan-to-confirm", "EvaluateBarcode (unknown) -> scan_unresolved",
               "An unregistered EAN-13 is refused with a typed issue, never guessed", "Mã EAN-13 chưa đăng ký bị từ chối bằng lỗi có kiểu, không đoán",
               mode="query; the receipt step accepts only what it expects", rule="ADR-0061 rules 13-15", status="rejected (expected)",
               inputs={"scan": {"raw": "4006381333931", "symbology_identifier": "]E0"}},
               outputs={"encoding": r_unk["encoding"], "issues": r_unk["issues"], "candidates": r_unk["candidates"], "confirm": conf})
    TRACE.check("an unknown code is refused (barcode_unknown, scan_unresolved) with no candidate", r_unk["issues"] == ["barcode_unknown"]
                and not r_unk["candidates"] and conf == "scan_unresolved", {"issues": r_unk["issues"], "confirm": conf}, "ADR-0061 rule 14")

    # 5 the last bag's label carries only (15) best before -------------------------------------------------------------------------
    raw2 = f"01{gtin}15270430" + "10LOT-2611B" + GS + "301"
    r2, c2, l2, v2 = receive(raw2, "A label with (15) best before only: 1 bag, lot LOT-2611B", "Nhãn chỉ có (15) sử dụng tốt nhất trước: 1 bao, lô LOT-2611B", False)
    TRACE.check("best before is stored as best_before_date and does not fill expiry under the default setting",
                l2["expiry_date"] is None and l2["best_before_date"] == dt.date(2027, 4, 30) and def_bb is False
                and db.val("select expiry_date from lot where code='LOT-2611B'") is None, {k: str(v) for k, v in l2.items()}, "ADR-0063 rule 26")
    TRACE.check("the two receipts sum to the order line (7.500 KGM, GR/IR positions 0-7.5)", ln.gr.R == F(15, 2), str(ln.gr.R), "ADR-0056 rule 10")
    TRACE.step("det", "ledger and inventory queries", "barcode scenario totals", "Stock 7.500 KGM in two lots; GR/IR open until the invoice",
               "Tồn 7,500 kg ở hai lô; GR/IR mở đến khi có hóa đơn", mode="queries", rule="ADR-0056 rule 1; INV-602",
               outputs={"stock": f"{L.on_hand(db, iid)[0]} KGM", "value": L.on_hand(db, iid)[1], "lots": [r[0] for r in db.all("select code from lot where item_id=%s order by code", (iid,))],
                        "gr_ir_line_balance": -ln.gr.balance() if ln.gr.balance() else 0},
               notes="the lab's resolve() still reads (15) as the expiry when (17) is absent (ADR-0061 rule 17 interim); the simulation applies ADR-0063 rule 26's setting")
    return True
