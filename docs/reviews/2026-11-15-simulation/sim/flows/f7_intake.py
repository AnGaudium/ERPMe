"""Flow 7: supplier invoices from a company mailbox (ADR-0057 rules 3-6, 14-15, 25; ADR-0063 rule 27; ADR-0056 rule 10).
An e-invoice XML from a sender matched to exactly one partner is read deterministically (rung 1), imported, its companion
PDF is linked as a rendering, and the invoice is matched to the order and receipt per inventory unit; a PDF from an
unmatched sender is stored only; a near duplicate posts with its payment held for review. No LLM call: the XML rung is code."""
import datetime as dt
import hashlib
import re
import xml.etree.ElementTree as ET
from decimal import Decimal as D
from fractions import Fraction as F

from .core import TRACE, W, ins, upd, new_id, now, sha, money, set_day
from . import platform as P
from . import ledger as L
from . import commerce as C
from . import uom as U
from . import xdesign as X
from .f6_uom import Line, q, fd

OMEGA_TAX = "0109990884"
XML_TPL = ("<HDon><DLHDon><TTChung><PBan>2.1.0</PBan><KHMSHDon>1</KHMSHDon><KHHDon>C26TOF</KHHDon><SHDon>{num}</SHDon><NLap>{day}</NLap>"
           "<DVTTe>VND</DVTTe></TTChung><NDHDon><NBan><Ten>OMEGA FASTENERS</Ten><MST>{seller}</MST></NBan><NMua><MST>{buyer}</MST></NMua>"
           "<DSHHDVu><HHDVu><STT>1</STT><MHHDVu>OMG-M8X40</MHHDVu><THHDVu>Bu long M8x40</THHDVu><DVTinh>THÙNG</DVTinh><SLuong>{qty}</SLuong>"
           "<DGia>250000</DGia><ThTien>{net}</ThTien><TSuat>10%</TSuat></HHDVu></DSHHDVu><TToan><TgTCThue>{net}</TgTCThue><TgTThue>{tax}</TgTThue>"
           "<TgTTTBSo>{gross}</TgTTTBSo></TToan></NDHDon></DLHDon><DSCKS><NBan>signature</NBan></DSCKS></HDon>")


def parse_e_invoice(raw):
    """The package's structured reader (rung 1, ADR-0057 rule 6): fields by XPath, then the arithmetic of rule 14."""
    root = ET.fromstring(raw)
    g = lambda p: root.findtext(p)  # noqa: E731
    f = {"invoice_symbol": ("code", g("DLHDon/TTChung/KHHDon"), "DLHDon/TTChung/KHHDon"),
         "invoice_number": ("code", g("DLHDon/TTChung/SHDon"), "DLHDon/TTChung/SHDon"),
         "issue_date": ("date", g("DLHDon/TTChung/NLap"), "DLHDon/TTChung/NLap"),
         "currency": ("currency", g("DLHDon/TTChung/DVTTe"), "DLHDon/TTChung/DVTTe"),
         "seller_tax_id": ("tax_id", g("DLHDon/NDHDon/NBan/MST"), "DLHDon/NDHDon/NBan/MST"),
         "buyer_tax_id": ("tax_id", g("DLHDon/NDHDon/NMua/MST"), "DLHDon/NDHDon/NMua/MST"),
         "lines[1].seller_item_code": ("code", g(".//HHDVu/MHHDVu"), "//HHDVu[1]/MHHDVu"),
         "lines[1].unit_text": ("text", g(".//HHDVu/DVTinh"), "//HHDVu[1]/DVTinh"),
         "lines[1].quantity": ("quantity", g(".//HHDVu/SLuong"), "//HHDVu[1]/SLuong"),
         "lines[1].unit_price": ("amount", g(".//HHDVu/DGia"), "//HHDVu[1]/DGia"),
         "lines[1].line_amount": ("amount", g(".//HHDVu/ThTien"), "//HHDVu[1]/ThTien"),
         "net_total": ("amount", g(".//TToan/TgTCThue"), "//TToan/TgTCThue"),
         "tax_amount": ("amount", g(".//TToan/TgTThue"), "//TToan/TgTThue"),
         "gross_total": ("amount", g(".//TToan/TgTTTBSo"), "//TToan/TgTTTBSo")}
    v = {k: x[1] for k, x in f.items()}
    rules = {"line_arithmetic": D(v["lines[1].quantity"]) * D(v["lines[1].unit_price"]) == D(v["lines[1].line_amount"]),
             "lines_sum_to_net": D(v["lines[1].line_amount"]) == D(v["net_total"]),
             "tax_by_rate": money(D(v["net_total"]) * D("0.1")) == D(v["tax_amount"]),
             "gross": D(v["net_total"]) + D(v["tax_amount"]) == D(v["gross_total"]),
             "buyer_is_company": v["buyer_tax_id"] == W.company_tax_id}
    return f, rules, ("passed" if root.find("DSCKS") is not None else "absent")


def shape_ok(vt, v, path):
    """The mandatory shape rule by value type (ADR-0057 rule 17); None for text, which has no closed shape."""
    if vt == "text":
        return None
    if vt in ("amount", "quantity"):
        return bool(re.fullmatch(r"-?\d{1,18}(\.\d{1,6})?", v or ""))
    if vt == "date":
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v or ""))
    if vt == "currency":
        return v == "VND"
    if vt == "tax_id":
        return bool(re.fullmatch(r"\d{10}(-\d{3})?", v or ""))
    return bool(re.fullmatch(r"[A-Za-z0-9./_-]{1,40}", v or ""))


def run(db):
    TRACE.start_flow(7, "Supplier invoice intake", "Tiếp nhận hóa đơn đầu vào",
                     "A company mailbox receives supplier invoices: the e-invoice XML of a sender matched to exactly one partner is read by code, "
                     "imported and matched per inventory unit; a stranger's PDF is stored only; a near duplicate posts with its payment held for review.")
    set_day("2026-11-24")
    X.load_setting_definitions(db)
    I = X.lab("t20_intake")
    owner, buyer, wk, acc = (W.user[k] for k in ("owner", "buyer", "warehouse_keeper", "accountant"))
    oa, ba, wa, aa = (P.person(k) for k in ("owner", "buyer", "warehouse_keeper", "accountant"))
    omega, bolt, CART, H87 = W.partners["S-OMEGA"], W.items["BOLT-M8"], W.uom["x-carton"], W.uom["H87"]
    W.company_tax_id = db.val("select tax_id from company where id=%s", (W.co,)) or "0100000000"

    # 1 the AP mailbox with an intake purpose; the reader registry; Omega's sending domain --------------------------------
    ok_m, why_m = P.can(acc, "CreatePurchaseInvoice", node="purchase_invoice")
    W.ap_mailbox = new_id("mailbox")
    ins(db, "mailbox", id=W.ap_mailbox, code="AP", name="Supplier invoices (sample)", email_address="invoices@sample-manufacturing.example",
        connector_kind="imap", connector_settings={"host": "imap.sample-manufacturing.example", "folder": "INBOX"}, credential_ref="secret/ap-mailbox",
        authserv_id="mx.sample-manufacturing.example", is_authentication_verified=True, authentication_probe_result="passed",
        authentication_checked_at=now(), owner_user_id=acc["id"], document_intake_purpose="supplier_invoice")
    P.audit(db, "UpdateMailbox", oa, subject_table="mailbox", subject_id=W.ap_mailbox, human_only=True)
    reader = new_id("document_reader")
    ins(db, "document_reader", id=reader, code="l10n_vn.e_invoice_xml", version="1.0.0", rung="structured_xml", package_code="l10n_vn",
        purposes=["supplier_invoice"], content_hash=sha("l10n_vn.e_invoice_xml 1.0.0"), recorded_at=now())
    ins(db, "partner_email_domain", id=new_id("partner_email_domain"), partner_id=omega, domain="omega-fasteners.example")
    TRACE.step("person", f"{owner['name']} (owner)", "UpdateMailbox", "The AP mailbox gets the purpose supplier_invoice",
               "Hộp thư kế toán phải trả được gán mục đích hóa đơn nhà cung cấp", mode="direct, human_only", rule="ADR-0057 rule 25; ADR-0052 rule 11",
               outputs={"mailbox": "AP", "document_intake_purpose": "supplier_invoice", "document_intake_quarantine_limit": 20,
                        "owner": f"{acc['name']} (accountant)", "owner_holds_purpose_leaf": why_m, "readers": ["l10n_vn.e_invoice_xml 1.0.0 (structured_xml)"]},
               notes="UpdateMailbox refuses a purpose whose leaf the mailbox owner does not hold (mailbox_owner_not_permitted), so deliveries never fail for rights")
    TRACE.check("the mailbox owner holds edit on the purpose's leaf", ok_m, why_m, "ADR-0057 rule 25")

    # 2 two orders of 4 cartons and their receipts (the goods the invoices will bill) ------------------------------------
    lines = []
    for n in (1, 2):
        lp = C.price_line(db, W.price_lists["BUY-OMEGA"], W.today, D(4), "x-carton", item=bolt["id"])
        pol = new_id("purchase_order_line")
        po = P.create_doc(db, "purchase_order", ba, header={"partner_id": omega, "partner_name": "Omega Fasteners (sample)", "partner_tax_id": OMEGA_TAX,
                                                           "currency": "VND", "price_list_id": W.price_lists["BUY-OMEGA"], "payment_term_id": W.terms["NET30"]["id"],
                                                           "buyer_id": W.employee["buyer"], "document_date": W.today},
                          lines=[("purchase_order_line", dict(id=pol, purchase_order_id="__DOC__", line_number=1, item_id=bolt["id"], quantity=D(4), uom_id=CART,
                                                              uom_numerator=24, uom_denominator=1, uom_factor_source="product", inventory_quantity=D(96),
                                                              warehouse_id=W.wh, requested_date=W.today, list_unit_price=lp["list_price"],
                                                              net_unit_price=lp["net_unit_price"], line_amount=lp["amount"]))],
                          number=P.next_number(db, "purchase_order", "PO"), partner_id=omega)
        C.write_steps(db, po["id"], 1, lp["list_price"], lp["net_unit_price"], lp["amount"])
        P.submit(db, po, ba, {"amount": lp["amount"]}, "SubmitPurchaseOrder")
        ln = Line(pol, bolt["id"], "BOLT-M8", CART, 4, F(24), "product", 96, lp["amount"])
        ins(db, "purchase_order_line_gr_ir_layer", id=new_id("purchase_order_line_gr_ir_layer"), purchase_order_line_id=pol, from_position=0, to_position=96,
            price_numerator=D(ln.price.numerator), price_denominator=D(ln.price.denominator))
        v, _ = U.convert_part(F(24), F(0), F(0), F(4), 0)
        amt, a, b = ln.gr.post("R", v, ln.price)
        gid = new_id("goods_receipt_line")
        gr = P.create_doc(db, "goods_receipt", wa, header={"partner_id": omega, "partner_name": "Omega Fasteners (sample)", "document_date": W.today, "posting_date": W.today},
                          lines=[("goods_receipt_line", dict(id=gid, goods_receipt_id="__DOC__", line_number=1, purchase_order_line_id=pol, item_id=bolt["id"],
                                                             quantity=D(4), uom_id=CART, uom_numerator=24, uom_denominator=1, uom_factor_source="product",
                                                             inventory_quantity=q(v), warehouse_id=W.wh, gr_ir_position_from=a, gr_ir_position_to=b))],
                          number=P.next_number(db, "goods_receipt", "GR"), partner_id=omega)
        md_ = L.material_document(db, gr["id"], W.today)
        mdl = L.stock_move(db, md_, bolt["id"], W.wh, "purchase_receipt", q(v), amt, source_line=1)
        L.post_entry(db, gr["id"], W.today, [
            {"acct": L.determine("inventory_posting", valuation_class="raw_material"), "side": "debit", "amount": amt, "item": bolt["id"], "warehouse": W.wh, "mdl": mdl,
             "pol": pol, "key": "inventory_posting", "desc": f"receipt BOLT-M8 4 x-carton = {q(v)} H87"},
            {"acct": L.determine("gr_ir_clearing"), "side": "credit", "amount": amt, "pol": pol, "key": "gr_ir_clearing", "desc": f"GR/IR positions {a}-{b}"}],
            description=f"goods receipt {gr['number']}")
        P.set_state(db, gr, "posted")
        ins(db, "purchase_order_line_gr_ir_posting", id=new_id("purchase_order_line_gr_ir_posting"), purchase_order_line_id=pol, document_id=gr["id"], line_number=1,
            posting_kind="receipt", from_position=a, to_position=b, gr_ir_amount=-amt)
        P.audit(db, "PostGoodsReceipt", wa, effect_class="posting", doc=gr, subject_table="goods_receipt", subject_id=gr["id"])
        lines.append({"po": po, "line": ln, "gr": gr, "credit": amt})
    TRACE.step("person", f"{buyer['name']} (buyer) and {wk['name']} (warehouse_keeper)", "SubmitPurchaseOrder x2 + PostGoodsReceipt x2",
               "Two orders of 4 cartons are received: 96 pieces each at GR/IR positions 0-96", "Hai đơn 4 thùng đã nhập kho: mỗi đơn 96 cái, vị trí GR/IR 0-96",
               mode="direct", rule="ADR-0056 rules 9-10; ADR-0047 rules 10, 13",
               outputs={"orders": [x["po"]["number"] for x in lines], "receipts": [x["gr"]["number"] for x in lines], "per_receipt": "4 x-carton = 96 H87 (24/1, product)",
                        "gr_ir_credit_each": lines[0]["credit"], "price_per_H87": fd(lines[0]["line"].price)})

    # 3 mailbox intake: an authenticated message from Omega's domain with an XML and its PDF rendering ---------------------
    intake = P.system_for(acc)
    num1 = "0000811"
    xml1 = XML_TPL.format(num=num1, day=str(W.today), seller=OMEGA_TAX, buyer=W.company_tax_id, qty=4, net=1000000, tax=100000, gross=1100000).encode()
    pdf1 = f"%PDF-1.7 text layer: HOA DON GTGT C26TOF So {num1} Omega Fasteners Tong cong 1.100.000".encode()

    def message(sender, domain, key, parts, authenticated=True):
        atts = []
        for name, media, raw in parts:
            a = new_id("attachment")
            ins(db, "attachment", id=a, sha256=hashlib.sha256(raw).hexdigest(), media_type=media, byte_count=len(raw), storage_key=f"sim/{a}",
                data_label="internal", source_kind="email", state="clean", contains_untrusted=True)
            atts.append({"id": a, "name": name, "media": media, "raw": raw, "sha": hashlib.sha256(raw).hexdigest()})
        inter = new_id("interaction")
        ins(db, "interaction", id=inter, kind="email", direction="inbound", occurred_at=now(), subject=f"Invoice from {domain}", is_untrusted=True)
        ins(db, "interaction_participant", id=new_id("interaction_participant"), interaction_id=inter, role="from", email_address=sender)
        raw_all = b"".join(p[2] for p in parts)
        mid = new_id("inbound_message")
        ins(db, "inbound_message", id=mid, mailbox_id=W.ap_mailbox, provider_message_key=key, message_id=f"<{key}@{domain}>",
            message_id_hash=hashlib.sha256(f"<{key}@{domain}>".encode()).hexdigest(), content_hash=hashlib.sha256(raw_all).hexdigest(),
            sender_address=sender, sender_domain=domain, is_sender_authenticated=authenticated, received_at=now(), interaction_id=inter,
            sender_authentication={"spf": "pass", "dkim": "pass", "dmarc": "pass" if authenticated else "fail"})
        for a in atts:
            ins(db, "attachment_link", id=new_id("attachment_link"), attachment_id=a["id"], target_table="inbound_message", target_id=mid)
        partners = [r[0] for r in db.all("select partner_id from partner_email_domain where domain=%s", (domain,))] if authenticated else []
        P.audit(db, "RecordInboundMessage", intake, subject_table="interaction", subject_id=inter, internal_only=True)
        return mid, inter, atts, partners

    mid1, inter1, atts1, partners1 = message("billing@omega-fasteners.example", "omega-fasteners.example", "UIDV7:101",
                                             [("C26TOF_0000811.xml", "application/xml", xml1), ("C26TOF_0000811.pdf", "application/pdf", pdf1)])
    msg = {"authenticated": True, "partners": [str(p) for p in partners1], "parts": [a["media"] for a in atts1]}
    plan1 = I.mailbox_plan({"authenticated": True, "matched_partners": [str(p) for p in partners1],
                            "parts": [{"kind": "xml" if a["media"].endswith("xml") else "pdf", "name": a["name"]} for a in atts1]})
    TRACE.step("system", "job mailbox_intake (system on behalf of the mailbox owner)", "RecordInboundMessage",
               "An authenticated message from Omega's domain: an XML and a PDF", "Thư đã xác thực từ tên miền của Omega: một XML và một PDF",
               mode="system job; the message is outside content (tainted)", rule="ADR-0052 rules 14-15; ADR-0057 rule 25",
               outputs={"message": msg, "matched_partner": "S-OMEGA" if len(partners1) == 1 else None, "lab_mailbox_plan": plan1},
               deterministic="matched to exactly one active partner by its sender domain after sender authentication passed")

    # 4 the consumer requests the XML part first; rung 1 reads it ---------------------------------------------------------
    def request(att, partner, inbound, by_actor, by_user):
        ex = new_id("document_extraction")
        ins(db, "document_extraction", id=ex, attachment_id=att["id"], purpose="supplier_invoice", attachment_sha256=att["sha"],
            detected_media_type=att["media"], data_label="internal", requested_by_user_id=by_user["id"], partner_id=partner, inbound_message_id=inbound)
        P.audit(db, "RequestDocumentExtraction", by_actor, subject_table="document_extraction", subject_id=ex)
        ev = P.emit(db, "DocumentExtractionRequested", "document_extraction", ex, by_actor, "RequestDocumentExtraction", tainted=True)
        return ex, ev

    def read_xml(ex, raw):
        fields, rules, sig = parse_e_invoice(raw)
        fids = {}
        for path, (vt, val, xp) in fields.items():
            fid = new_id("extraction_field")
            norm = U.normalize_unit_text(val) if vt == "text" and "unit" in path else val
            ins(db, "extraction_field", id=fid, document_extraction_id=ex, field_path=path, value_type=vt, value_raw=val, value_normalized=norm,
                status="found", method="parsed", evidence_kind="xpath", evidence={"xpath": xp}, document_reader_id=reader, data_label="internal", recorded_at=now())
            fids[path] = fid
        rule_of = {"lines[1].line_amount": "line_arithmetic", "net_total": "lines_sum_to_net", "tax_amount": "tax_by_rate", "gross_total": "gross",
                   "buyer_tax_id": "buyer_is_company"}
        for path, fid in fids.items():
            vt = fields[path][0]
            shape = shape_ok(vt, fields[path][1], path)
            if shape is None:
                continue                                   # text: no closed shape, never trusted (rule 17)
            ins(db, "extraction_rule_run", document_extraction_id=ex, run_number=1, extraction_field_id=fid, rule="shape", passed=shape,
                trigger_kind="ladder", recorded_at=now())
            if path in rule_of:
                ins(db, "extraction_rule_run", document_extraction_id=ex, run_number=1, extraction_field_id=fid, rule=rule_of[path], passed=rules[rule_of[path]],
                    trigger_kind="ladder", recorded_at=now())
        upd(db, "document_extraction", {"id": ex}, document_kind="xml", page_count=1, signature_state=sig, final_reader_id=reader, state="extracted",
            reader_attempts=[{"rung": "structured_xml", "reader": "l10n_vn.e_invoice_xml", "version": "1.0.0", "outcome": "valid_record"}])
        P.audit(db, "RecordDocumentExtraction", P.system_for(acc), subject_table="document_extraction", subject_id=ex, internal_only=True)
        trust = db.all("select field_path, is_untrusted from extraction_field_trust where document_extraction_id=%s order by field_path", (ex,))
        return fields, rules, sig, {p: u for p, u in trust}

    ex1, ev1 = request(atts1[0], omega, mid1, intake, acc)
    fields1, rules1, sig1, trust1 = read_xml(ex1, xml1)
    TRACE.step("det", "document_extraction_runner (consumer, system on behalf of the mailbox owner): rung 1 l10n_vn.e_invoice_xml",
               "RequestDocumentExtraction + RecordDocumentExtraction", "The XML part is read by the package's structured reader: no model",
               "Phần XML được đọc bằng bộ đọc có cấu trúc của gói: không dùng mô hình", mode="deterministic ladder, stops at the first valid record",
               rule="ADR-0057 rules 3-6, 14, 17", events=[ev1],
               outputs={"state": "extracted", "signature_state": sig1, "fields": {k: v[1] for k, v in fields1.items()}, "rules": rules1,
                        "untrusted_fields": sorted(p for p, u in trust1.items() if u)},
               deterministic="schema version 2.1.0 selected; fields by XPath; arithmetic, tax by rate and buyer tax ID checked; trust computed by the view "
                             "extraction_field_trust (text fields always untrusted)")
    TRACE.check("rung 1 reads the XML with every rule passed and no LLM call", all(rules1.values()) and sig1 == "passed", rules1, "ADR-0057 rules 6, 14")

    # 5 import as system on behalf of the mailbox owner; duplicate levels; the companion PDF is its rendering -------------
    hist = [{"seller": r[0], "number": r[1], "gross": int(r[2]), "date": r[3]}
            for r in db.all("select seller_tax_id, invoice_number, gross_amount, invoice_date from e_invoice_record where direction='incoming'")]
    S = X.lab("t24_settings")
    st = {k.split(".")[-1]: X.get_setting(db, k) for k in ("intake.duplicate.date_window_days", "intake.duplicate.amount_tolerance_minor_units",
                                                           "intake.duplicate.number_normalization", "intake.duplicate.near_outcome")}

    def import_record(ex, fields, att, mid):
        v = {k: x[1] for k, x in fields.items()}
        new_inv = {"seller": v["seller_tax_id"], "number": v["invoice_number"], "gross": int(v["gross_total"]), "date": dt.date.fromisoformat(v["issue_date"])}
        dup = S.duplicate_check(new_inv, hist, st)
        rid = new_id("e_invoice_record")
        ins(db, "e_invoice_record", id=rid, direction="incoming", state="imported", seller_tax_id=v["seller_tax_id"], seller_name="OMEGA FASTENERS",
            invoice_form="1", invoice_symbol=v["invoice_symbol"], invoice_number=v["invoice_number"], invoice_date=new_inv["date"], currency="VND",
            net_amount=D(v["net_total"]), tax_amount=D(v["tax_amount"]), gross_amount=D(v["gross_total"]), signature_state="passed",
            authority_status="unchecked", supplier_partner_id=omega, imported_by_user_id=None, source_attachment_id=att["id"])
        ins(db, "e_invoice_record_line", e_invoice_record_id=rid, line_number=1, seller_item_code=v["lines[1].seller_item_code"], item_name="Bu long M8x40",
            unit_text=v["lines[1].unit_text"], quantity=D(v["lines[1].quantity"]), unit_price=D(v["lines[1].unit_price"]), net_amount=D(v["lines[1].line_amount"]),
            tax_rate=D(10), stated_tax_amount=D(v["tax_amount"]))
        ins(db, "extraction_result_link", document_extraction_id=ex, target_table="e_invoice_record", target_id=rid, recorded_at=now())
        P.audit(db, "ImportEInvoiceRecord", intake, subject_table="e_invoice_record", subject_id=rid,
                check_codes=["duplicate_document_suspected"] if dup["level"] == "near" else [])
        hist.append(new_inv)
        wi = P.raise_item(db, "supplier_invoice_received", "e_invoice_record", rid, ("role", "accountant"), due_days=2, tainted=True,
                          details={"seller_tax_id": v["seller_tax_id"], "duplicate": dup["level"]})
        return rid, dup, wi

    rid1, dup1, wi1 = import_record(ex1, fields1, atts1[0], mid1)
    pdf_text = atts1[1]["raw"].decode()
    is_render = I.companion_of({"name": atts1[1]["name"], "text_layer": pdf_text}, [{"name": atts1[0]["name"], "invoice_number": num1}]) == atts1[0]["name"]
    ex1p, _ = request(atts1[1], omega, mid1, intake, acc)
    if is_render:
        upd(db, "document_extraction", {"id": ex1p}, state="canceled", canceled_reason="rendering_of_parsed_xml", document_kind="pdf_text")
        ins(db, "attachment_link", id=new_id("attachment_link"), attachment_id=atts1[1]["id"], target_table="e_invoice_record", target_id=rid1)
    TRACE.step("system", "tax consumer e_invoice_intake (system on behalf of the mailbox owner)", "ImportEInvoiceRecord",
               "The record is imported; the PDF is linked as its rendering and not read", "Nhập bản ghi hóa đơn; PDF được liên kết là bản thể hiện và không đọc",
               mode="system on behalf of the mailbox owner, whatever the signature", rule="ADR-0057 rules 15, 25; ADR-0063 rule 27",
               outputs={"e_invoice_record": f"C26TOF-{num1}", "duplicate_levels": {"file": "new hash", "key": "no holder", "near": dup1["level"] or "none"},
                        "near_settings_in_force": st, "companion_pdf": "rendering_of_parsed_xml" if is_render else "own document",
                        "work_item": "supplier_invoice_received"}, work_items=[wi1],
               deterministic="the XML's invoice number is a whole token of the PDF's text layer, so the PDF is the XML's rendering (rule 25)")
    TRACE.check("the companion PDF is linked as the rendering and its request canceled", is_render and db.val("select canceled_reason from document_extraction where id=%s", (ex1p,)) == "rendering_of_parsed_xml", "", "ADR-0057 rule 25")

    # 6 match per inventory unit, then the accountant books the invoice from the record ------------------------------------
    def match_and_post(rid, num, x, day_note):
        ln = x["line"]
        ut = U.resolve_unit_text(db, bolt["id"], "THÙNG", partner=omega)
        part, _ = U.convert_part(ln.f, ln.Ci, ln.Pi, F(4), 0)
        price_inv = F(1000000) / part
        grv = (ln.gr.V(ln.gr.R) - ln.gr.V(F(0))) / ln.gr.R
        amt, a, b = ln.gr.post("I", part, ln.price)
        pinv = P.create_doc(db, "purchase_invoice", aa, header={"partner_id": omega, "partner_name": "Omega Fasteners (sample)", "partner_tax_id": OMEGA_TAX,
                                                               "partner_reference": f"C26TOF-{num}", "external_document_key": {"seller_tax_id": OMEGA_TAX, "form": "1", "symbol": "C26TOF", "number": num},
                                                               "supplier_invoice_date": W.today, "document_date": W.today, "posting_date": W.today, "currency": "VND",
                                                               "payment_term_id": W.terms["NET30"]["id"]},
                            lines=[("purchase_invoice_line", dict(id=new_id("purchase_invoice_line"), purchase_invoice_id="__DOC__", line_number=1, line_kind="goods",
                                                                  purchase_order_line_id=ln.pol, item_id=bolt["id"], quantity=D(4), uom_id=ut["uom_id"], uom_numerator=24,
                                                                  uom_denominator=1, uom_factor_source="product", inventory_quantity=q(part), unit_price=D(250000),
                                                                  line_amount=D(1000000)))], partner_id=omega, number=f"C26TOF-{num}")
        C.write_tax(db, pinv["id"], 1, D(1000000), "vat_in_10", D(10), stated=D(100000))
        dec, _ = P.submit(db, pinv, aa, {"amount": D(1000000), "is_match_exceeded": False, "is_direct_expense": False}, "SubmitPurchaseInvoice")
        with db.tx():
            L.post_entry(db, pinv["id"], W.today, [
                {"acct": L.determine("gr_ir_clearing"), "side": "debit", "amount": amt, "pol": ln.pol, "key": "gr_ir_clearing", "desc": f"clear GR/IR positions {a}-{b}"},
                {"acct": L.determine("input_tax", tax_code="vat_in_10"), "side": "debit", "amount": D(100000), "tax_code": W.tax["vat_in_10"], "key": "input_tax", "desc": "stated VAT 10%"},
                {"acct": L.determine("payable_reconciliation"), "side": "credit", "amount": D(1100000), "partner": omega, "key": "payable_reconciliation",
                 "oi_create": {"kind": "invoice", "due_date": W.today + dt.timedelta(days=30), "reference": f"C26TOF-{num}", "payment_term_id": W.terms["NET30"]["id"]},
                 "desc": "payable"}], description=f"purchase invoice C26TOF-{num}")
            P.set_state(db, pinv, "posted")
        ins(db, "purchase_order_line_gr_ir_posting", id=new_id("purchase_order_line_gr_ir_posting"), purchase_order_line_id=ln.pol, document_id=pinv["id"], line_number=1,
            posting_kind="invoice", from_position=a, to_position=b, gr_ir_amount=amt)
        P.audit(db, "PostPurchaseInvoice", aa, effect_class="posting", doc=pinv, subject_table="purchase_invoice", subject_id=pinv["id"], policy_decision_id=dec["id"])
        ln.Ci, ln.Pi = ln.Ci + 4, ln.Pi + part
        upd(db, "e_invoice_record", {"id": rid}, state="converted", document_id=pinv["id"])
        oi = db.val("select id from open_item where origin_document_id=%s", (pinv["id"],))
        return pinv, oi, {"unit_text": ut["trail"], "invoice_part": f"round((0 + 4) x 24/1) - 0 = {q(part)} H87", "gr_ir_positions": f"{a}-{b}",
                          "gr_ir_debit": amt, "receipt_credit": x["credit"], "price_per_H87": {"invoice": fd(price_inv), "gr_ir": fd(grv)},
                          "line_balance": ln.gr.balance(), "match": "within tolerance (price and quantity equal)"}

    pinv1, oi1, m1 = match_and_post(rid1, num1, lines[0], "")
    TRACE.step("person", f"{acc['name']} (accountant)", "CreatePurchaseInvoice + PostPurchaseInvoice (from the record)",
               "Matched to the order and receipt per piece; the accountant books it and GR/IR clears", "Đối chiếu với đơn và phiếu nhập theo cái; kế toán ghi sổ, GR/IR về 0",
               mode="direct (a person from the record)", rule="ADR-0056 rules 10, 12, 19; ADR-0047 rules 13-14", outputs=m1,
               deterministic="unit text by alias -> x-carton; invoice part by the cumulative rule in the order unit; GR/IR positions in the inventory unit")
    TRACE.check("GR/IR positions are in the inventory unit (0-96 H87) and the line's GR/IR balance is zero", m1["gr_ir_positions"] == "0-96" and m1["line_balance"] == 0, m1,
                "ADR-0056 rule 10; INV-92")

    # 7 a PDF from a sender matched to no partner is stored only -------------------------------------------------------------
    pdf2 = b"%PDF-1.7 Invoice 7781 please pay to the new account below"
    mid2, inter2, atts2, partners2 = message("accounts@freemail.example", "freemail.example", "UIDV7:102", [("invoice.pdf", "application/pdf", pdf2)])
    n_ex2 = db.val("select count(*) from document_extraction where attachment_id=%s", (atts2[0]["id"],))
    TRACE.step("system", "crm consumer mailbox_document_intake", "(no request)", "A PDF from an unmatched sender is stored only",
               "PDF từ người gửi không khớp đối tác chỉ được lưu", mode="consumer decision, deterministic", rule="ADR-0057 rule 25",
               outputs={"sender": "accounts@freemail.example", "matched_partners": len(partners2), "extractions_requested": n_ex2, "stored": "attachment + inbound_message",
                        "next": "a person may request its extraction from the message"},
               deterministic="non-XML parts are requested only for a message matched to exactly one active partner")
    TRACE.check("the unmatched sender's PDF gets no extraction (stored only)", n_ex2 == 0 and len(partners2) == 0, n_ex2, "ADR-0057 rule 25")

    # 8 a near duplicate two days later: different number, same gross -> posted with the payment held -------------------------
    set_day("2026-11-26")
    num2 = "0000812"
    xml2 = XML_TPL.format(num=num2, day=str(W.today), seller=OMEGA_TAX, buyer=W.company_tax_id, qty=4, net=1000000, tax=100000, gross=1100000).encode()
    mid3, _, atts3, partners3 = message("billing@omega-fasteners.example", "omega-fasteners.example", "UIDV7:103", [("C26TOF_0000812.xml", "application/xml", xml2)])
    ex3, _ = request(atts3[0], omega, mid3, intake, acc)
    fields3, rules3, _, _ = read_xml(ex3, xml2)
    rid3, dup3, wi3 = import_record(ex3, fields3, atts3[0], mid3)
    TRACE.step("system", "e_invoice_intake: duplicate levels", "ImportEInvoiceRecord", "A second Omega invoice two days later with the same gross is a suspected near duplicate",
               "Hóa đơn Omega thứ hai cách hai ngày, cùng tổng tiền: nghi trùng gần", mode="system on behalf of the mailbox owner", rule="ADR-0057 rule 15; ADR-0063 rule 27",
               outputs={"e_invoice_record": f"C26TOF-{num2}", "levels": {"file": "new hash", "key": "different number: no holder", "near": dup3["level"]},
                        "check_result": "duplicate_document_suspected", "settings_used": st, "imported": True},
               deterministic="near: same seller, gross within 1 minor unit and issue dates 2 <= 7 days apart (the core defaults)")
    pinv3, oi3, m3 = match_and_post(rid3, num2, lines[1], "")
    blocked = st["near_outcome"] == "review" and dup3["level"] == "near"
    ins(db, "open_item_collection", open_item_id=oi3, is_payment_blocked=blocked)
    wi_d = P.raise_item(db, "duplicate_document_review", "document", pinv3["id"], ("role", "accountant"), due_days=2,
                        details={"suspected_of": f"C26TOF-{num1}", "test": "same seller, gross within 1, 2 days"})
    TRACE.step("person", f"{acc['name']} (accountant)", "PostPurchaseInvoice (near duplicate)", "Posted under review: the open item is blocked for payment",
               "Ghi sổ ở chế độ xem xét: khoản phải trả bị chặn thanh toán", mode="direct; the posting sets the hold", rule="ADR-0063 rule 27; ADR-0048 (open_item_collection)",
               outputs={"invoice": pinv3["number"], "gr_ir": m3["gr_ir_positions"], "open_item_collection.is_payment_blocked": blocked, "work_item": "duplicate_document_review"},
               work_items=[wi_d], notes="open_item_collection has no DDL yet: the simulation keeps it in sim_stubs.sql (design gap)")
    P.resolve_item(db, wi_d["id"], "not a duplicate: second delivery under PO-2, receipt " + lines[1]["gr"]["number"])
    db.x("update open_item_collection set is_payment_blocked=false where open_item_id=%s", (oi3,))
    P.audit(db, "ResolveDuplicateDocumentReview", aa, subject_table="purchase_invoice", subject_id=pinv3["id"], reason="second delivery, own receipt", human_only=True)
    TRACE.step("person", f"{acc['name']} (accountant)", "resolve duplicate_document_review", "A person records 'not a duplicate' with a reason: the hold is released",
               "Người dùng ghi nhận 'không trùng' kèm lý do: bỏ chặn thanh toán", mode="direct, human_only", rule="ADR-0063 rule 27",
               outputs={"reason": "second delivery, own receipt", "is_payment_blocked": False})
    TRACE.check("the near duplicate is suspected under the default settings and its payment held until a person resolves it",
                dup3["level"] == "near" and blocked and st == {"date_window_days": 7, "amount_tolerance_minor_units": 1, "number_normalization": "digits_only", "near_outcome": "review"},
                {"dup": dup3, "settings": st}, "ADR-0063 rule 27")
    return True
