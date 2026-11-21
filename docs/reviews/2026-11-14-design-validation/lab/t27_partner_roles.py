"""Scenario: document parties, external IDs, custom fields, reasons and header notes (ADR-0074). Not product code.

Run: python t27_partner_roles.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs).

P: the party reference functions (rules 1 to 5): defaults from partner_relationship, a party not stated is the next one up,
   and what each consequence reads (open item and credit exposure: the payer; tax identity: the bill-to party; delivery:
   the ship-to party; document partner: the sold-to partner; purchases: the invoicing party and the payee), the exposure of
   one payer over several buyers, a relationship change leaving an existing order alone, INV-863 on a list of invoices.
C: the custom value validation (rule 10): unknown key, wrong value, missing required value, retired field, decimal strings.
With --load: partner_relationship keys and defaults; the party columns on sales_order, delivery and purchase_order (a name
exactly when named, an address of the party's own, a partner of the company); external_id_map keys (the source system group refused), the lookup functions and
INV-860; custom_values as an object and the definition CHECKs; the reason kind in the key (document.canceled_reason_id,
only in state canceled); the header notes and journal_entry.note.
Not covered: commands, the snapshot copy itself (a command), the generated schemas, the posting of invoices and payments.
"""
import os, re, sys
from decimal import Decimal as D, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from fx_adr74 import DOCS, RESULTS, build, check, conn, doc, ins, new, reset_and_load, trial  # noqa: E402

# ======================================================================= reference functions
CUSTOMER_ROLES = ("ship_to", "bill_to", "payer")
SUPPLIER_ROLES = ("invoicing_party", "payee")


def default_parties(partner, relationships, side):
    """Rule 3: for each role the default active relationship of the partner, else not stated (None)."""
    roles = CUSTOMER_ROLES if side == "sales" else SUPPLIER_ROLES
    out = {}
    for role in roles:
        hit = [r for r in relationships if r["partner"] == partner and r["role"] == role and r["is_default"] and r["is_active"]]
        out[role] = (hit[0]["related"], hit[0].get("address")) if hit else None
    return out


def effective(doc_, side):
    """Rule 1: a party not stated is the next one up."""
    p = doc_["partner"]
    if side == "sales":
        ship = doc_.get("ship_to") or p
        bill = doc_.get("bill_to") or p
        payer = doc_.get("payer") or bill
        return {"ship_to": ship, "bill_to": bill, "payer": payer}
    inv = doc_.get("invoicing_party") or p
    payee = doc_.get("payee") or inv
    return {"invoicing_party": inv, "payee": payee}


def consequences(doc_, side):
    """Rule 4."""
    e = effective(doc_, side)
    if side == "sales":
        return {"open_item": e["payer"], "credit": e["payer"], "tax_identity": e["bill_to"], "delivery": e["ship_to"], "document_partner": doc_["partner"]}
    return {"open_item": e["invoicing_party"], "tax_identity": e["invoicing_party"], "payment": e["payee"], "document_partner": doc_["partner"]}


def exposure_by_payer(docs):
    out = {}
    for d in docs:
        pay = effective(d, "sales")["payer"]
        out[pay] = out.get(pay, 0) + d["amount"]
    return out


def inv_863(invoices):
    """Invoices whose open item belongs to another partner than the rule's party."""
    bad = []
    for d in invoices:
        side = d.get("side", "sales")
        want = consequences(d, side)["open_item"]
        if d["open_item_partner"] != want:
            bad.append(d["id"])
    return bad


def validate_custom(values, definitions):
    """Rule 10: returns the list of (code, error)."""
    errs = []
    by = {d["code"]: d for d in definitions}
    for k, v in values.items():
        d = by.get(k)
        if d is None:
            errs.append((k, "custom_field_unknown")); continue
        if not d["is_active"]:
            errs.append((k, "custom_field_invalid")); continue
        t, val = d["data_type"], d.get("validation", {})
        ok = True
        if t == "text":
            ok = isinstance(v, str) and len(v) <= val.get("max_length", 10 ** 6) and (not val.get("pattern") or re.fullmatch(val["pattern"], v) is not None)
        elif t == "integer":
            ok = isinstance(v, int) and not isinstance(v, bool) and val.get("min", v) <= v <= val.get("max", v)
        elif t == "decimal":
            try:
                x = D(v) if isinstance(v, str) else None
                ok = x is not None and D(val.get("min", x)) <= x <= D(val.get("max", x)) and -x.as_tuple().exponent <= val.get("scale", 99)
            except InvalidOperation:
                ok = False
        elif t == "boolean":
            ok = isinstance(v, bool)
        elif t == "date":
            ok = isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) is not None
        elif t == "choice":
            ok = v in val.get("choices", [])
        if not ok:
            errs.append((k, "custom_field_invalid"))
    for d in definitions:
        if d["is_active"] and d["is_required"] and d["code"] not in values:
            errs.append((d["code"], "custom_field_required"))
    return sorted(errs)


# ======================================================================= P: parties
rels = [{"partner": "S", "role": "ship_to", "related": "T", "address": "adr_t", "is_default": True, "is_active": True},
        {"partner": "S", "role": "bill_to", "related": "H", "address": "adr_h", "is_default": True, "is_active": True},
        {"partner": "S", "role": "payer", "related": "G", "is_default": True, "is_active": True},
        {"partner": "S", "role": "payer", "related": "G2", "is_default": False, "is_active": True},
        {"partner": "U", "role": "bill_to", "related": "H2", "is_default": True, "is_active": False},
        {"partner": "SUP", "role": "invoicing_party", "related": "I", "is_default": True, "is_active": True},
        {"partner": "SUP", "role": "payee", "related": "P", "is_default": True, "is_active": True}]
d0 = default_parties("U", rels, "sales")
check("P01 a partner with no active default relationship leaves every party unstated", d0 == {"ship_to": None, "bill_to": None, "payer": None}, d0)
order0 = {"partner": "U"}
check("P02 with no party named, every consequence reads the sold-to partner (a simple customer carries nothing new)",
      set(consequences(order0, "sales").values()) == {"U"}, consequences(order0, "sales"))
d1 = default_parties("S", rels, "sales")
check("P03 the defaults are the active default relationships, with the address of the related party",
      d1 == {"ship_to": ("T", "adr_t"), "bill_to": ("H", "adr_h"), "payer": ("G", None)}, d1)
order1 = {"partner": "S", "ship_to": "T", "bill_to": "H", "payer": "G"}
c1 = consequences(order1, "sales")
check("P04 the open item and the credit exposure follow the payer, the tax identity the bill-to party, the delivery the ship-to party, the document the sold-to partner",
      c1 == {"open_item": "G", "credit": "G", "tax_identity": "H", "delivery": "T", "document_partner": "S"}, c1)
check("P05 a payer not stated is the bill-to party, and a bill-to party not stated is the sold-to partner",
      effective({"partner": "S", "bill_to": "H"}, "sales")["payer"] == "H" and effective({"partner": "S"}, "sales")["payer"] == "S")
p1 = consequences({"partner": "SUP", "invoicing_party": "I", "payee": "P"}, "purchases")
check("P06 on purchases the payable and the input tax identity follow the invoicing party and the payment its payee",
      p1 == {"open_item": "I", "tax_identity": "I", "payment": "P", "document_partner": "SUP"}, p1)
check("P07 a payee not stated is the invoicing party; an invoicing party not stated is the ordered-from partner",
      effective({"partner": "SUP"}, "purchases") == {"invoicing_party": "SUP", "payee": "SUP"})
exp = exposure_by_payer([{"partner": "S", "payer": "G", "amount": 100}, {"partner": "S2", "payer": "G", "amount": 50}, {"partner": "S3", "amount": 7}])
check("P08 two buyers paid by one group are one credit exposure (the group's), and a buyer that pays for itself its own", exp == {"G": 150, "S3": 7}, exp)
snapshot = dict(order1)
rels[0]["related"] = "T2"
check("P09 changing a default relationship does not touch an order that already carries its parties",
      snapshot["ship_to"] == "T" and default_parties("S", rels, "sales")["ship_to"][0] == "T2")
bad = inv_863([{"id": "i1", "partner": "S", "payer": "G", "open_item_partner": "G"}, {"id": "i2", "partner": "S", "payer": "G", "open_item_partner": "S"},
               {"id": "i3", "partner": "SUP", "invoicing_party": "I", "payee": "P", "side": "purchases", "open_item_partner": "I"},
               {"id": "i4", "partner": "SUP", "invoicing_party": "I", "payee": "P", "side": "purchases", "open_item_partner": "P"}])
check("P10 INV-863 finds the invoice whose open item is not its payer's and the bill whose payable is its payee's", bad == ["i2", "i4"], bad)

# ======================================================================= C: custom fields
defs = [{"code": "region", "data_type": "choice", "validation": {"choices": ["north", "south"]}, "is_required": True, "is_active": True},
        {"code": "note_code", "data_type": "text", "validation": {"max_length": 5, "pattern": "[A-Z]+"}, "is_required": False, "is_active": True},
        {"code": "weight", "data_type": "decimal", "validation": {"min": "0", "max": "100", "scale": 2}, "is_required": False, "is_active": True},
        {"code": "seats", "data_type": "integer", "validation": {"min": 1}, "is_required": False, "is_active": True},
        {"code": "vip", "data_type": "boolean", "validation": {}, "is_required": False, "is_active": True},
        {"code": "since", "data_type": "date", "validation": {}, "is_required": False, "is_active": True},
        {"code": "old", "data_type": "text", "validation": {}, "is_required": False, "is_active": False}]
check("C01 a valid set of values passes", validate_custom({"region": "north", "note_code": "AB", "weight": "12.50", "seats": 3, "vip": True, "since": "2026-11-19"}, defs) == [])
check("C02 an unknown key is custom_field_unknown", validate_custom({"region": "north", "zzz": 1}, defs) == [("zzz", "custom_field_unknown")])
check("C03 a missing value of a required field is custom_field_required", validate_custom({}, defs) == [("region", "custom_field_required")])
errs = validate_custom({"region": "east", "note_code": "abcdef", "weight": 12.5, "seats": 0, "vip": "yes", "since": "19/11/2026"}, defs)
check("C04 every wrong value is custom_field_invalid, and a decimal must be a string, never a float",
      errs == sorted((k, "custom_field_invalid") for k in ("region", "note_code", "weight", "seats", "vip", "since")), errs)
check("C05 a decimal beyond its scale is invalid", validate_custom({"region": "south", "weight": "1.234"}, defs) == [("weight", "custom_field_invalid")])
check("C06 a retired field refuses a value; its absence is never required", validate_custom({"region": "south", "old": "x"}, defs) == [("old", "custom_field_invalid")])

# ======================================================================= X: the DDL (--load)
if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("X00 load_all.py loads every DDL file with the ADR-0074 tables", n_tables > 0, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    I = build(c)
    cols = {}
    for t_, col, nul in X("select table_name, column_name, is_nullable from information_schema.columns where table_schema='nativeflows'").fetchall():
        cols.setdefault(t_, {})[col] = nul
    PARTIES = {"quotation": ("ship_to", "bill_to", "payer"), "sales_order": ("ship_to", "bill_to", "payer"), "delivery": ("ship_to",),
               "sales_invoice": ("bill_to", "payer"), "sales_return": ("bill_to", "payer"), "credit_note": ("bill_to", "payer"),
               "debit_note": ("bill_to", "payer"), "purchase_order": ("invoicing_party", "payee"), "purchase_invoice": ("invoicing_party", "payee"),
               "purchase_return": ("invoicing_party", "payee"), "purchase_credit_note": ("invoicing_party", "payee"), "purchase_debit_note": ("invoicing_party", "payee")}
    missing = [(t_, p) for t_, ps in PARTIES.items() for p in ps for col in (p + "_partner_id", p + "_name") if col not in cols.get(t_, {})]
    check("X01 the party columns sit on the 12 headers of ADR-0074 rule 2, and the interim delivery_address and quotation.cancel_reason are gone",
          not missing and "delivery_address" not in cols["delivery"] and "cancel_reason" not in cols["quotation"], missing[:4])
    NOTES = ["quotation", "sales_order", "purchase_request", "purchase_order", "goods_receipt", "return_to_supplier", "delivery", "return_from_customer",
             "service_receipt", "sales_invoice", "sales_return", "credit_note", "debit_note", "purchase_invoice", "purchase_return", "purchase_credit_note", "purchase_debit_note",
             "stock_transfer", "stock_count", "scrap", "internal_consumption"]
    check("X02 note is on the 17 commercial headers and the four stock headers, and on journal_entry", all("note" in cols[t_] for t_ in NOTES) and "note" in cols["journal_entry"],
          [t_ for t_ in NOTES if "note" not in cols[t_]])
    CUSTOM = ["partner", "product", "item", "quotation", "sales_order", "delivery", "sales_invoice", "purchase_order", "goods_receipt", "purchase_invoice", "production_order"]
    check("X03 custom_values (NOT NULL) is on the 11 tables of ADR-0074 rule 9 and on no other table",
          all(cols[t_].get("custom_values") == "NO" for t_ in CUSTOM) and sorted(t_ for t_, cc in cols.items() if "custom_values" in cc) == sorted(CUSTOM),
          sorted(t_ for t_, cc in cols.items() if "custom_values" in cc))
    # ---- partner_relationship
    def rel(cx, role="ship_to", partner="sold", related="ship", **o):
        ins(cx, "partner_relationship", id=new(), company_id=I["co"], partner_id=I[partner], related_partner_id=I[related], role=role, **o)
    ins(c, "partner_relationship", id=new(), company_id=I["co"], partner_id=I["sold"], related_partner_id=I["ship"], role="ship_to", address_id=I["adr_ship"], is_default=True)
    ins(c, "partner_relationship", id=new(), company_id=I["co"], partner_id=I["sold"], related_partner_id=I["bill"], role="bill_to", address_id=I["adr_bill"], is_default=True)
    ins(c, "partner_relationship", id=new(), company_id=I["co"], partner_id=I["sold"], related_partner_id=I["payer"], role="payer", is_default=True)
    trial("X04 a second default of one role for a partner is refused", lambda cx: rel(cx, "ship_to", "sold", "bill", is_default=True), "ux_partner_relationship_default")
    trial("X05 one relationship per partner, related partner and role", lambda cx: rel(cx, "ship_to", "sold", "ship"), "partner_relationship_company_id_partner_id_related")
    trial("X06 a partner is not its own related party", lambda cx: rel(cx, "payer", "sold", "sold"), "ck_partner_relationship_not_self")
    trial("X07 an inactive relationship cannot be the default", lambda cx: rel(cx, "payee", "sup", "payee", is_default=True, is_active=False), "ck_partner_relationship_default")
    trial("X08 a payer relationship names no address", lambda cx: rel(cx, "payer", "sup", "inv", address_id=I["adr_bill"]), "ck_partner_relationship_address")
    trial("X09 the address is one of the related partner's own", lambda cx: rel(cx, "ship_to", "sup", "ship", address_id=I["adr_bill"]), "partner_relationship_company_id_related_partner_id_")
    trial("X10 the related partner belongs to the company", lambda cx: rel(cx, "ship_to", "sup", "other"), "partner_relationship_company_id_related_partner_id_")
    # ---- party columns
    def order(cx, **o):
        d = doc(cx, I, "sales_order", partner="sold")
        ins(cx, "sales_order", id=d, company_id=I["co"], partner_id=I["sold"], partner_name="SOLD", currency="VND", document_date="2026-11-10", **o)
        return d
    good = new()
    with c.transaction():
        order(c, ship_to_partner_id=I["ship"], ship_to_name="SHIP", ship_to_address_id=I["adr_ship"], ship_to_address='{"lines": ["1 Example Street"]}',
              bill_to_partner_id=I["bill"], bill_to_name="BILL", bill_to_tax_id="0100000001", bill_to_address_id=I["adr_bill"], bill_to_address='{"lines": ["1 Example Street"]}',
              payer_partner_id=I["payer"], payer_name="PAYER")
    check("X11 an order with ship-to, bill-to and payer parties and their snapshots is stored", True)
    with c.transaction():
        order(c)
    check("X12 an order with no party named is stored (the simple customer carries nothing new)", True)
    trial("X13 a named party needs its name", lambda cx: order(cx, payer_partner_id=I["payer"]), "ck_sales_order_payer")
    trial("X14 a name without a party is refused", lambda cx: order(cx, payer_name="PAYER"), "ck_sales_order_payer")
    trial("X15 a tax ID or an address without its bill-to party is refused", lambda cx: order(cx, bill_to_tax_id="1"), "ck_sales_order_bill_to")
    trial("X16 the address of a party is its own: the head office's address under the ship-to party is refused",
          lambda cx: order(cx, ship_to_partner_id=I["ship"], ship_to_name="SHIP", ship_to_address_id=I["adr_bill"]), "sales_order_company_id_ship_to_partner_id_")
    trial("X17 a party of another company is refused", lambda cx: order(cx, payer_partner_id=I["other"], payer_name="X"), "sales_order_company_id_payer_partner_id_")
    def delivery(cx, **o):
        d = doc(cx, I, "delivery", partner="sold")
        ins(cx, "delivery", id=d, company_id=I["co"], partner_id=I["sold"], partner_name="SOLD", document_date="2026-11-10", posting_date="2026-11-10", **o)
    with c.transaction():
        delivery(c, ship_to_partner_id=I["ship"], ship_to_name="SHIP", ship_to_address_id=I["adr_ship"], ship_to_address='{"lines": ["1 Example Street"]}')
    check("X18 a delivery carries its ship-to party and address snapshot", True)
    def po(cx, **o):
        d = doc(cx, I, "purchase_order", partner="sup")
        ins(cx, "purchase_order", id=d, company_id=I["co"], partner_id=I["sup"], partner_name="SUP", currency="VND", document_date="2026-11-10", **o)
    with c.transaction():
        po(c, invoicing_party_partner_id=I["inv"], invoicing_party_name="INV", invoicing_party_tax_id="0200000002", payee_partner_id=I["payee"], payee_name="PAYEE")
    check("X19 a purchase order carries its invoicing party and payee", True)
    trial("X20 a payee has no address or tax ID columns, and its name goes with its partner", lambda cx: po(cx, payee_name="PAYEE"), "ck_purchase_order_payee")
    # ---- note and custom values
    trial("X21 a note is at most 4,000 characters", lambda cx: order(cx, note="x" * 4001), "ck_sales_order_note")
    with c.transaction():
        order(c, note="x" * 4000)
    check("X22 a note of 4,000 characters is stored", True)
    trial("X23 custom_values is a JSON object", lambda cx: order(cx, custom_values="[1]"), "ck_sales_order_custom_values")
    with c.transaction():
        order(c, custom_values='{"region": "north"}')
    check("X24 an object of custom values is stored on a header", True)
    # ---- custom field definitions
    def cfd(cx, **o):
        v = dict(id=new(), company_id=I["co"], target_table="partner", code="region", label="Region", data_type="choice", is_personal_data=False); v.update(o)   # no default since ADR-0079 rule 2
        ins(cx, "custom_field_definition", **v)
    cfd(c)
    trial("X25 one definition per company, table and code", lambda cx: cfd(cx), "custom_field_definition_company_id_target_table_")
    trial("X26 the target table is one that has custom_values", lambda cx: cfd(cx, target_table="journal_line"), "ck_custom_field_definition_target_table")
    trial("X27 the code is a lower-case key", lambda cx: cfd(cx, code="Region-1"), "ck_custom_field_definition_code")
    trial("X28 the data type is one of the six", lambda cx: cfd(cx, code="r2", data_type="reference"), "ck_custom_field_definition_data_type")
    trial("X29 a field class is cost or margin", lambda cx: cfd(cx, code="r3", field_class="secret"), "ck_custom_field_definition_field_class")
    trial("X30 validation is a JSON object", lambda cx: cfd(cx, code="r4", validation="[]"), "ck_custom_field_definition_validation")
    # ---- external ids
    def ext(cx, source="shop", table="partner", key="C-1", entity=None):
        ins(cx, "external_id_map", company_id=I["co"], source_system=source, table_name=table, external_key=key, entity_id=entity or I["sold"])
    ext(c)
    trial("X31 a key names one entity in a source system", lambda cx: ext(cx, entity=I["ship"]), "uq_external_id_map_key")
    trial("X32 an entity has one key in a source system", lambda cx: ext(cx, key="C-2"), "uq_external_id_map_entity")
    ext(c, source="edi", key="C-1", entity=I["ship"])
    check("X33 the same key may name another entity in another source system", True)
    check("X34 external_id_resolve and external_key_of read the map in both directions",
          X("select external_id_resolve(%s,'shop','partner','C-1') = %s and external_key_of(%s,'edi','partner',%s) = 'C-1' and external_id_resolve(%s,'shop','partner','nope') is null",
            (I["co"], I["sold"], I["co"], I["ship"], I["co"])).fetchone()[0])
    trial("X35 a source system code is a lower-case code", lambda cx: ext(cx, source="Web Shop", key="Z"), "ck_external_id_map_source_system")
    trial("X35a the source system group is reserved for the group key until the distribution command exists (rule 7 note; external_id_source_reserved)",
          lambda cx: ext(cx, source="group", key="G-1"), "ck_external_id_map_source_system_reserved")
    ext(c, key="DANGLING", source="shop2", entity=new())
    dang = X("""select count(*) from external_id_map m where m.table_name = 'partner' and not exists (select 1 from partner p where p.company_id = m.company_id and p.id = m.entity_id)""").fetchone()[0]
    check("X36 INV-860's check finds the mapping whose entity does not exist", dang == 1, dang)
    # ---- reasons
    d_cancel = doc(c, I, "quotation", state="draft", partner="sold")
    c_sql = "update document set state='canceled', canceled_reason_id=%s, canceled_note='lost' where id=%s"
    X(c_sql, (I["reason_cancel"], d_cancel))
    check("X37 a document canceled with a reason of kind cancel stores it", X("select canceled_reason_id from document where id=%s", (d_cancel,)).fetchone()[0] == I["reason_cancel"])
    d2 = doc(c, I, "quotation", state="draft", partner="sold")
    trial("X38 a reason of another kind is refused by the key", lambda cx: cx.execute(c_sql, (I["reason_scrap"], d2)), "document_company_id_canceled_reason_id_")
    trial("X39 a canceled reason is allowed only in state canceled", lambda cx: cx.execute("update document set canceled_reason_id=%s where id=%s", (I["reason_cancel"], d2)), "ck_document_canceled")
    trial("X40 a reason kind is one of the eight", lambda cx: cx.execute("insert into reason (id, company_id, kind, code, name) values (%s,%s,'other','x','X')", (new(), I["co"])), "ck_reason_kind")
    trial("X41 one reason code per company and kind", lambda cx: cx.execute("insert into reason (id, company_id, kind, code, name) values (%s,%s,'cancel','cancel_1','Dup')", (new(), I["co"])), "reason_company_id_kind_code_key")
    X("insert into reason (id, company_id, kind, code, name) values (%s,%s,'scrap','cancel_1','Same code, other kind')", (new(), I["co"]))
    check("X42 the same code may exist under another kind", True)
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
