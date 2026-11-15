"""Master data functions over the DS-20/DS-56 tables: GetPrice, configurations, configured items, estimates."""
import hashlib
import json
from decimal import Decimal as D
from fractions import Fraction as F

from .core import W, ins, new_id, fmt, now
from . import pure


def norm(v):
    return format(v.normalize(), "f") if isinstance(v, D) else str(v)


def factor_of(db, product_id, uom_id, item=None):
    """ADR-0045 rule 4 with ADR-0056 rule 6: the factor of master_data.contract.convert_quantity."""
    from . import uom as U
    r = U.to_inventory(db, uom_id, item=item, product=None if item else product_id)
    inv = db.one("select inventory_uom_id from product where id=%s", (product_id,))[0]
    return (r["factor"] if "factor" in r else None), inv


def get_price(db, pl, on, qty, uom_code, item=None, product=None, values=None):
    """find_price (ADR-0045 rule 4; ADR-0046 rule 15 for configurable products)."""
    uom = W.uom[uom_code]
    if product is None:
        product = db.one("select product_id from erpme.item where id=%s", (item,))[0]
    f, inv = factor_of(db, product, uom, item=item)

    def rows(col, target, u):
        return db.all(f"select id, minimum_quantity, unit_price from erpme.price_list_entry where price_list_id=%s and {col}=%s and uom_id=%s"
                      " and start_date<=%s and (end_date is null or end_date>=%s)", (pl, target, u, on, on))

    def extras(vid):
        return db.all("select id, product_id, unit_price_extra from erpme.price_list_option_extra where price_list_id=%s and variant_attribute_value_id=%s"
                      " and (product_id=%s or product_id is null) and start_date<=%s and (end_date is null or end_date>=%s)", (pl, vid, product, on, on))

    def rates(attr):
        return db.one("select id, rate_per_value from erpme.price_list_characteristic_rate where price_list_id=%s and product_id=%s and variant_attribute_id=%s"
                      " and start_date<=%s and (end_date is null or end_date>=%s)", (pl, product, attr, on, on))
    vl, vn = [], []
    for code, v in (values or {}).items():
        mode, vt, _ = W.MODEL.ch[code]
        if vt == "list":
            vl.append((W.V[(code, v)], mode == "variant"))
        else:
            vn.append((W.A[code], v, mode == "variant"))
    if item is not None:
        price, reason, used = pure.find_price(lambda k: rows("item_id", item, uom if k == "entered" else inv), extras, rates, f, qty, vl, vn, item_entry_replaces=True)
        if price is not None or values is None:
            return {"price": price, "reason": reason, "rows_used": used, "factor": f, "target": "item"}
    price, reason, used = pure.find_price(lambda k: rows("product_id", product, uom if k == "entered" else inv), extras, rates, f, qty, vl, vn)
    return {"price": price, "reason": reason, "rows_used": used, "factor": f, "target": "product"}


def canon(values):
    pairs = sorted((str(W.A[k]), str(W.V[(k, v)]) if W.MODEL.ch[k][1] == "list" else norm(v)) for k, v in values.items())
    return json.dumps({"product": str(W.unit), "values": pairs}, separators=(",", ":"))


def save_configuration(db, values):
    """Content-addressed find-or-create (ADR-0046 rule 9): only complete configurations; numbers stored as numbers."""
    h = hashlib.sha256(canon(values).encode()).hexdigest()
    row = db.one("select id from erpme.product_configuration where company_id=%s and product_id=%s and content_hash=%s", (W.co, W.unit, h))
    if row:
        return row[0], False, h
    cid = new_id("md")
    with db.tx():
        ins(db, "product_configuration", id=cid, company_id=W.co, product_id=W.unit, content_hash=h, created_at=now())
        for k, v in values.items():
            lst = W.MODEL.ch[k][1] == "list"
            ins(db, "product_configuration_value", company_id=W.co, product_configuration_id=cid, product_id=W.unit, variant_attribute_id=W.A[k],
                value_type=W.MODEL.ch[k][1], variant_attribute_value_id=W.V[(k, v)] if lst else None, numeric_value=None if lst else v)
    return cid, True, h


def configured_item(db, cfg_id):
    """ADR-0046 rule 11: the item whose variant_key equals the item-defining values; number value rows appear only now."""
    rows = db.all("""select pcv.variant_attribute_id, pcv.variant_attribute_value_id, pcv.numeric_value from erpme.product_configuration_value pcv
                     join erpme.variant_attribute a on a.id = pcv.variant_attribute_id join erpme.product_variant_attribute pva
                       on pva.product_id = pcv.product_id and pva.variant_attribute_id = a.id
                     where pcv.product_configuration_id=%s and a.variant_mode='variant' order by pva.position""", (cfg_id,))
    pairs, names = [], []
    for a, vid, nv in rows:
        if vid is None:
            code = norm(D(nv))
            r = db.one("select id from erpme.variant_attribute_value where variant_attribute_id=%s and numeric_value=%s", (a, nv))
            if r:
                vid = r[0]
            else:
                vid = new_id("md")
                ins(db, "variant_attribute_value", id=vid, company_id=W.co, variant_attribute_id=a, variant_mode="variant", value_type="number",
                    code=code, name=code, numeric_value=nv)
            names.append(code)
        else:
            names.append(db.one("select code from erpme.variant_attribute_value where id=%s", (vid,))[0])
        pairs.append((a, vid))
    key = sorted(p[1] for p in pairs)
    r = db.one("select id, code from erpme.item where product_id=%s and variant_key=%s::uuid[]", (W.unit, key))
    if r:
        return r[0], False, r[1], None
    n = db.one("update erpme.product set last_item_number = last_item_number + 1 where id=%s returning code, last_item_number", (W.unit,))
    iid = new_id("md")
    code = f"{n[0]}-{n[1]:04d}"
    # name: product name and item-defining values in position order (width x height / material / size / mounting)
    vals = dict(zip([W.A_code[a] for a, _ in pairs], names))
    name = f"MFU {vals['width']} x {vals['height']} / {vals['material']} / {vals['size_class']} / {vals['mounting']} (sample)"
    ins(db, "item", id=iid, company_id=W.co, product_id=W.unit, code=code, variant_key=key)
    for a, vid in pairs:
        ins(db, "item_variant_value", company_id=W.co, item_id=iid, product_id=W.unit, variant_attribute_id=a, variant_attribute_value_id=vid)
    W.code_of[iid] = code
    return iid, True, code, name


def item_defining(values):
    return {k: v for k, v in values.items() if W.MODEL.ch[k][0] == "variant"}


def estimate(values):
    """production.contract.estimate_configuration (ADR-0046 rule 14): explosion of the product-level structure priced at preliminary prices."""
    total, lines = pure.estimate_configuration(W.MODEL, W.COMP, values, W.prelim)
    return total, [{"component": W.code_of[i], "quantity": q, "unit_price": p, "amount": a} for i, q, p, a in lines]
