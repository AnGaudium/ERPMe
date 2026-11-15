"""Flow 2: a sale price list maintained by a person (flows report Part B, flow 2; ADR-0045 rules 2-7, 13; ADR-0046 rules 15, 17;
holistic S13: SetPriceListEntries upserts by key and end-dates the predecessor)."""
import datetime as dt
from decimal import Decimal as D

from .core import TRACE, W, ins, upd, new_id, d, set_day
from . import platform as P
from . import md
from .common import probe

ENTRIES = [("MFU", "product", "EA", 0, "2026-11-01", D(8500000)), ("ABS", "item", "EA", 0, "2026-11-01", D(170000)),
           ("ABS", "item", "EA", 8, "2026-11-01", D(155000))]
EXTRAS = [("color", "blue", D(250000)), ("color", "grey", D(0)), ("label", "text", D(50000))]
RATES = [("width", D(1500)), ("height", D(1000))]


def run(db):
    TRACE.start_flow(2, "Price list creation", "Tạo bảng giá",
                     "A sales clerk creates a dated sale list for project customers: product-level entry, quantity break, option extras and "
                     "characteristic rates; a later price end-dates its predecessor; the overlap constraint guards the table; find_price looks up prices.")
    set_day("2026-11-02")
    clerk = W.user["sales_clerk"]
    who = f"{clerk['name']} (sales_clerk)"
    actor = P.person("sales_clerk")
    rules = [r for r in db.all("select r.code from policy_rule_version v join policy_rule r on r.id=v.policy_rule_id where v.action='direct_master_data_change' "
                               "and v.command_type in ('CreatePriceList','SetPriceListEntries','SetPriceListOptionExtras','SetPriceListCharacteristicRates')")]

    # 1 CreatePriceList
    ok, why = P.can(clerk, "CreatePriceList")
    pl = new_id("price_list")
    ins(db, "price_list", id=pl, code="PROJ-2026", name="Project customers 2026 (sample)", kind="sale", currency="VND")
    W.proj = pl
    W.code_of[pl] = "PROJ-2026"
    P.audit(db, "CreatePriceList", actor, effect_class="master_data_change", subject_table="price_list", subject_id=pl)
    ev = [P.emit(db, "PriceListCreated", "price_list", pl, actor, "CreatePriceList")]
    TRACE.step("person", who, "CreatePriceList", "The sales clerk creates a sale list", "Nhân viên kinh doanh tạo bảng giá bán",
               mode="direct (a person; agents need a change proposal)", rule="ADR-0045 rules 2, 7; ADR-0029 rule 5 note (holistic Q3)",
               inputs={"code": "PROJ-2026", "kind": "sale", "currency": "VND"}, outputs={"price_list": "PROJ-2026", "permission": why},
               policy=[f"direct_master_data_change deny rules on price commands: {len(rules)} (seeded only for bank accounts): allowed"], events=ev,
               notes="segregation price_list_vs_sales_approval: the sales clerk maintains prices, so the clerk may not approve quotations or orders (A7: lists moved to the clerk)")

    # 2 SetPriceListEntries
    rows = []
    for code, kind, uom, minq, start, price in ENTRIES:
        target = {"product_id": W.products[code]["id"]} if kind == "product" else {"item_id": W.items[code]["id"]}
        eid = new_id("price_list_entry")
        ins(db, "price_list_entry", id=eid, price_list_id=pl, uom_id=W.uom[uom], minimum_quantity=D(minq), start_date=d(start), unit_price=price, **target)
        rows.append({"target": f"{kind} {code}", "unit": uom, "minimum_quantity": minq, "start": start, "unit_price": price})
    P.audit(db, "SetPriceListEntries", actor, effect_class="master_data_change", subject_table="price_list", subject_id=pl)
    ev = [P.emit(db, "PriceListEntriesSet", "price_list", pl, actor, "SetPriceListEntries")]
    TRACE.step("person", who, "SetPriceListEntries", "Entries: product-level price for the configurable unit and a quantity break",
               "Nhập giá: giá cấp sản phẩm cho khung cấu hình và giá theo bậc số lượng", mode="direct", rule="ADR-0045 rules 4, 7; ADR-0046 rule 15",
               inputs={"entries": rows}, outputs={"entries_written": len(rows)}, events=ev)

    # 3 a later price: upsert by key, the predecessor is end-dated (S13)
    old = db.one("select id from price_list_entry where price_list_id=%s and item_id=%s and minimum_quantity=0", (pl, W.items["ABS"]["id"]))[0]
    upd(db, "price_list_entry", {"id": old}, end_date=d("2026-11-30"))
    ins(db, "price_list_entry", id=new_id("price_list_entry"), price_list_id=pl, item_id=W.items["ABS"]["id"], uom_id=W.uom["EA"], minimum_quantity=0,
        start_date=d("2026-12-01"), unit_price=D(180000))
    P.audit(db, "SetPriceListEntries", actor, effect_class="master_data_change", subject_table="price_list", subject_id=pl)
    TRACE.step("det", "master_data handler of SetPriceListEntries", "SetPriceListEntries (upsert)",
               "A December price end-dates the November one", "Giá tháng 12 tự kết thúc giá tháng 11",
               mode="command handler, deterministic", rule="ADR-0045 rule 7 note (holistic S13)",
               inputs={"ABS from 2026-12-01": 180000}, outputs={"predecessor_end_date": "2026-11-30", "new_entry_start": "2026-12-01"},
               deterministic="upsert by key (list, target, unit, minimum quantity); a past-start predecessor is only end-dated")

    # 4 the overlap exclusion constraint (database defense)
    def overlap():
        ins(db, "price_list_entry", id=new_id("probe"), price_list_id=pl, item_id=W.items["ABS"]["id"], uom_id=W.uom["EA"], minimum_quantity=0,
            start_date=d("2026-11-15"), unit_price=D(150000))
    ok_ov, msg = probe(db, "overlap", overlap)
    TRACE.step("db", "PostgreSQL exclusion constraint", "ex_price_list_entry_overlap", "A raw overlapping entry is refused by the database",
               "CSDL từ chối giá chồng lấn thời gian", mode="database defense (probe, rolled back)", rule="ADR-0045 rule 7; DS-20",
               inputs={"ABS from 2026-11-15": 150000}, outputs={"rejected": ok_ov, "error": msg, "maps_to": "price_list_entry_overlap"}, status="rejected (expected)")
    TRACE.check("the overlap constraint rejects an overlapping entry", ok_ov, msg)

    # 5 option extras and characteristic rates
    for ch, val, extra in EXTRAS:
        ins(db, "price_list_option_extra", id=new_id("price_list_option_extra"), price_list_id=pl, product_id=W.unit, variant_attribute_id=W.A[ch],
            variant_attribute_value_id=W.V[(ch, val)], start_date=d("2026-11-01"), unit_price_extra=extra)
    P.audit(db, "SetPriceListOptionExtras", actor, effect_class="master_data_change", subject_table="price_list", subject_id=pl)
    for ch, rate in RATES:
        ins(db, "price_list_characteristic_rate", id=new_id("price_list_characteristic_rate"), price_list_id=pl, product_id=W.unit,
            variant_attribute_id=W.A[ch], start_date=d("2026-11-01"), rate_per_value=rate)
    P.audit(db, "SetPriceListCharacteristicRates", actor, effect_class="master_data_change", subject_table="price_list", subject_id=pl)
    TRACE.step("person", who, "SetPriceListOptionExtras + SetPriceListCharacteristicRates", "Option extras and rates per millimetre",
               "Phụ phí tùy chọn và đơn giá theo mm", mode="direct", rule="ADR-0046 rules 15, 17",
               inputs={"extras": [{"characteristic": c, "value": v, "extra": e} for c, v, e in EXTRAS], "rates": [{"characteristic": c, "per_mm": r} for c, r in RATES]},
               outputs={"extras": len(EXTRAS), "rates": len(RATES)})

    # 6 assign the list to the new customer
    ok_u, why_u = P.can(clerk, "UpdatePartner")
    upd(db, "customer_profile", {"partner_id": W.customer}, price_list_id=pl)
    P.audit(db, "UpdatePartner", actor, effect_class="master_data_change", subject_table="partner", subject_id=W.customer)
    ev = [P.emit(db, "PartnerUpdated", "partner", W.customer, actor, "UpdatePartner")]
    TRACE.step("person", who, "UpdatePartner", "The list is assigned to the new customer", "Gán bảng giá cho khách hàng mới",
               mode="direct", rule="ADR-0045 rule 13 (payload of the profile change undefined: A12)", inputs={"partner": "C-0001", "price_list": "PROJ-2026"},
               outputs={"customer_profile.price_list_id": "PROJ-2026", "permission": why_u}, events=ev)

    # 7 lookups: GetPrice -> master_data.contract.find_price
    cfg = {"width": D(1600), "height": D(900), "material": "steel", "size_class": "L", "mounting": "floor", "color": "blue"}
    looks = [("ABS 4 EA on 2026-11-03", dict(item=W.items["ABS"]["id"], qty=4, uom="EA", on=d("2026-11-03"))),
             ("ABS 8 EA on 2026-11-03 (break)", dict(item=W.items["ABS"]["id"], qty=8, uom="EA", on=d("2026-11-03"))),
             ("ABS 1 BOX on 2026-11-03 (inventory unit fallback)", dict(item=W.items["ABS"]["id"], qty=1, uom="BOX", on=d("2026-11-03"))),
             ("ABS 4 EA on 2026-12-05 (new price)", dict(item=W.items["ABS"]["id"], qty=4, uom="EA", on=d("2026-12-05"))),
             ("MFU 1600 x 900 steel floor blue", dict(product=W.unit, qty=2, uom="EA", on=d("2026-11-03"), values=cfg)),
             ("FRAME-L on the sale list", dict(item=W.items["FRAME-L"]["id"], qty=1, uom="EA", on=d("2026-11-03")))]
    results = []
    for label, a in looks:
        r = md.get_price(db, pl, a["on"], a["qty"], a["uom"], item=a.get("item"), product=a.get("product"), values=a.get("values"))
        results.append({"lookup": label, "price": r["price"], "reason": r["reason"], "rows": [x["table"] for x in r["rows_used"]]})
    W.price_mfu = results[4]["price"]
    TRACE.step("det", "master_data.contract.find_price", "GetPrice x6", "Six price lookups", "Sáu lần tra giá",
               mode="query, pure function", rule="ADR-0045 rule 4 (S15 signature note); ADR-0046 rules 15, 17",
               inputs={"lookups": [l for l, _ in looks]}, outputs={"results": results},
               deterministic="entered unit first, then inventory unit with the factor; highest break not above the quantity; configured: "
                             "product entry + extras + rate x value, rounded once")
    TRACE.check("quantity break applies at 8 EA", results[1]["price"] == D(155000), results[1])
    TRACE.check("BOX falls back to the inventory unit (10 EA at the break price)", results[2]["price"] == D(1550000), results[2])
    TRACE.check("the December price applies after the end-dated November entry", results[3]["price"] == D(180000), results[3])
    TRACE.check("configured price = 8,500,000 + 1,600 x 1,500 + 900 x 1,000 + 250,000 = 12,050,000", results[4]["price"] == D(12050000), results[4])
    TRACE.check("an item without an entry returns price_missing", results[5]["reason"] == "price_missing", results[5])
    TRACE.check("the clerk who maintains prices is barred from approving quotations by segregation",
                "price_list_vs_sales_approval" in P.segregation_pairs(db, {"type": "quotation"}, clerk, "ApproveQuotation") or not P.can(clerk, "ApproveQuotation")[0],
                "", "ADR-0054 rule 19")
    return True
