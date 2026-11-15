"""Units of measure (ADR-0056) as pure Python over the DS-20 rows: convert_quantity (item -> product -> global),
exactness (rule 7), round_quantity by use (rule 8), the line unit block (rule 9), convert_part and part-as-source
returns (rule 10), the unit rounding tolerance and the GR/IR rounding clearing test (rule 10), the proposed unit
(rule 13), order-unit lot sizing (rule 14), normalize_unit_text and unit-text resolution (rule 19).
Simulation code, not product code; the lab's t17_uom.py checks the same functions."""
import unicodedata
import uuid
from decimal import Decimal as D
from fractions import Fraction as F

from .core import W

NS = uuid.UUID("f244ce09-3c6c-4c82-af14-918bdeca6be3")       # ADR-0006 rule 4
FOLD = {"đ": "d", "ð": "d", "ł": "l", "ø": "o", "ß": "ss", "æ": "ae", "œ": "oe", "þ": "th", "ı": "i", "ħ": "h"}
BLOCK_TABLES = set()     # tables carrying the line unit block, read from the schema at start


def core_id(code):
    return uuid.uuid5(NS, f"uom:{code}")


def dec_of(uom_id):
    return W.uom_dec[uom_id]


def code_of(uom_id):
    return W.uom_code[uom_id]


def fr(x):
    return x if isinstance(x, F) else F(str(x))


def to_dec(x):
    x = fr(x)
    return D(x.numerator) / D(x.denominator)


def round_quantity(x, dec, mode="half_up"):
    """ADR-0006 rules 15, 17 and ADR-0056 rule 8: half_up is half away from zero; up is away from zero."""
    y = fr(x) * 10 ** dec
    sign, a = (-1 if y < 0 else 1), abs(y)
    if mode == "up":
        n = -(-a.numerator // a.denominator)
    else:
        h = a + F(1, 2)
        n = h.numerator // h.denominator
    return F(sign * n, 10 ** dec)


def is_exact(n, d, d_inv, d_entered):
    """ADR-0056 rule 7: n x 10^dI divisible by d x 10^dE."""
    return (n * 10 ** d_inv) % (d * 10 ** d_entered) == 0


def item_product(db, item):
    return db.one("select i.product_id, p.inventory_uom_id from item i join product p on p.id=i.product_id where i.id=%s", (item,))


def product_inventory(db, product):
    return db.val("select inventory_uom_id from product where id=%s", (product,))


def to_inventory(db, uom_id, item=None, product=None):
    """ADR-0056 rule 6, to the inventory unit: identity, item row, product row, global pair (either direction), else
    uom_not_allowed; a level with rows but none active stops with uom_retired. Returns a dict."""
    if item is not None:
        product, inv = item_product(db, item)
    else:
        inv = product_inventory(db, product)
    if uom_id == inv:
        return {"factor": F(1), "source": "identity", "row": None, "inventory_uom_id": inv}
    levels = []
    if item is not None:
        levels.append(("item", db.all("select id, numerator, denominator, is_active from product_uom where product_id=%s and item_id=%s and uom_id=%s",
                                      (product, item, uom_id))))
    levels.append(("product", db.all("select id, numerator, denominator, is_active from product_uom where product_id=%s and item_id is null and uom_id=%s",
                                     (product, uom_id))))
    for src, rows in levels:
        if rows:
            act = [r for r in rows if r[3]]
            if not act:
                return {"error": "uom_retired", "level": src}
            r = act[0]
            return {"factor": F(r[1], r[2]), "source": src, "row": str(r[0]), "inventory_uom_id": inv}
    r = db.one("select id, numerator, denominator, is_active from uom_conversion where from_uom_id=%s and to_uom_id=%s", (uom_id, inv))
    if r:
        return {"factor": F(r[1], r[2]), "source": "global", "row": str(r[0]), "inventory_uom_id": inv} if r[3] else {"error": "uom_retired", "level": "global"}
    r = db.one("select id, numerator, denominator, is_active from uom_conversion where from_uom_id=%s and to_uom_id=%s", (inv, uom_id))
    if r:
        return {"factor": F(r[2], r[1]), "source": "global", "row": str(r[0]), "inventory_uom_id": inv} if r[3] else {"error": "uom_retired", "level": "global"}
    return {"error": "uom_not_allowed"}


def convert_quantity(db, from_uom, to_uom=None, item=None, product=None):
    """master_data.contract.convert_quantity: the factor as a reduced fraction, its source, is_exact, the row."""
    a = to_inventory(db, from_uom, item=item, product=product)
    if "error" in a:
        return a
    inv = a["inventory_uom_id"]
    to_uom = to_uom or inv
    b = to_inventory(db, to_uom, item=item, product=product)
    if "error" in b:
        return b
    f = a["factor"] / b["factor"]
    return {"factor": f, "source": a["source"] if to_uom == inv else (a["source"], b["source"]), "row": a["row"],
            "is_exact": is_exact(f.numerator, f.denominator, dec_of(to_uom), dec_of(from_uom)), "inventory_uom_id": inv}


def block(db, uom_id, quantity, item=None, product=None, mode="half_up", inventory_quantity=None, snapshot=None):
    """The line unit block (rule 9): quantity, uom_id, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity.
    snapshot (n, d, source) keeps a source line's snapshot for a follow-on line in its unit (rule 11)."""
    if snapshot:
        n, d, src = snapshot
        f = F(n, d)
        inv = item_product(db, item)[1] if item else product_inventory(db, product)
    else:
        r = to_inventory(db, uom_id, item=item, product=product)
        if "error" in r:
            raise RuntimeError(r["error"])
        f, src, inv = r["factor"], r["source"], r["inventory_uom_id"]
    if inventory_quantity is None:
        iq = round_quantity(fr(quantity) * f, dec_of(inv), mode)
        if iq == 0:
            raise RuntimeError("quantity_rounds_to_zero")
        inventory_quantity = to_dec(iq)
    return {"quantity": D(str(quantity)), "uom_id": uom_id, "uom_numerator": f.numerator, "uom_denominator": f.denominator,
            "uom_factor_source": src, "inventory_quantity": inventory_quantity}


def fill_block(db, table, cols):
    """Used by core.ins for lines written without an explicit block: resolves the snapshot as the command would."""
    if table not in BLOCK_TABLES or cols.get("uom_factor_source") is not None or cols.get("uom_id") is None:
        return cols
    item = cols.get("item_id") or cols.get("component_item_id") or cols.get("output_item_id")
    product = cols.get("product_id")
    r = to_inventory(db, cols["uom_id"], item=item, product=None if item else product)
    if "error" in r:
        raise RuntimeError(f"{table}: {r['error']}")
    cols.update(uom_numerator=r["factor"].numerator, uom_denominator=r["factor"].denominator, uom_factor_source=r["source"])
    meta = db.cols[table]
    if "inventory_quantity" in meta and cols.get("inventory_quantity") is None and cols.get("quantity") is not None:
        cols["inventory_quantity"] = to_dec(round_quantity(fr(cols["quantity"]) * r["factor"], dec_of(r["inventory_uom_id"])))
    return cols


def convert_part(f, cum, posted, q, dec, mode="half_up"):
    """master_data.contract.convert_part (rule 10): round((C + q) x f) - P, rejected at zero or less, clamped to
    q x f +- 1 inventory unit (bounds rounded inward). Returns (value, check results)."""
    f, cum, posted, q = fr(f), fr(cum), fr(posted), fr(q)
    v = round_quantity((cum + q) * f, dec, mode) - posted
    if v <= 0:
        raise RuntimeError("quantity_rounds_to_zero")
    lo, hi = q * f - 1, q * f + 1
    step = F(1, 10 ** dec)
    lo_r = -((-lo) // step) * step if lo > 0 else lo
    hi_r = (hi // step) * step
    checks = []
    if v < lo_r:
        v, checks = lo_r, ["part_quantity_clamped"]
    elif v > hi_r:
        v, checks = hi_r, ["part_quantity_clamped"]
    if v != q * f:
        checks.append("quantity_rounded")
    return v, checks


def return_share(part_q, part_v, r0, v0, r, dec):
    """A return of r from a part (entered q, stored v), with earlier returns r0 taking v0: round(v x (r0 + r) / q) - v0."""
    if fr(r0) + fr(r) == fr(part_q):
        return fr(part_v) - fr(v0)
    v = round_quantity(fr(part_v) * (fr(r0) + fr(r)) / fr(part_q), dec) - fr(v0)
    if v <= 0:
        raise RuntimeError("quantity_rounds_to_zero")
    return v


def order_unit_lot(shortfall_inv, f, dec_order, dec_inv, minimum, multiple):
    """Rule 14: the shortfall converted exactly into the order unit, rounded up to the minimum and the multiple there,
    converted back with half_up as the order line will."""
    exact = fr(shortfall_inv) / fr(f)
    q = round_quantity(exact, dec_order, "up")
    steps = [("exact in the order unit", exact), ("rounded up to the unit's decimals", q)]
    if minimum and q < fr(minimum):
        q = fr(minimum)
        steps.append(("raised to the minimum", q))
    if multiple:
        m = fr(multiple)
        k = -(-q.numerator * m.denominator // (m.numerator * q.denominator))
        if k * m != q:
            q = k * m
            steps.append(("rounded up to the multiple", q))
    inv = round_quantity(q * fr(f), dec_inv, "half_up")
    return q, inv, steps


def normalize_unit_text(text):
    t = unicodedata.normalize("NFKD", str(text).lower())
    t = "".join(FOLD.get(ch, ch) for ch in t if not unicodedata.combining(ch))
    return "".join(ch for ch in t if not ch.isspace() and ch not in ".-_/")


def resolve_unit_text(db, item, text, partner=None):
    """Rule 19: partner_item.partner_uom_text, else an active alias, else a unit code; then allowed for the item."""
    n = normalize_unit_text(text)
    trail = []
    u = None
    if partner:
        for pt, pu in db.all("select partner_uom_text, uom_id from partner_item where partner_id=%s and item_id=%s and partner_uom_text is not null", (partner, item)):
            if normalize_unit_text(pt) == n:
                u = pu
                trail.append(f"partner_item text '{pt}'")
                break
    if u is None:
        r = db.one("select uom_id, alias from uom_alias where normalized_alias=%s and is_active", (n,))
        if r:
            u = r[0]
            trail.append(f"alias '{r[1]}' -> {code_of(r[0])}")
    if u is None:
        for uid, code in db.all("select id, code from uom where company_id is null or company_id=%s", (W.co,)):
            if normalize_unit_text(code) == n:
                u = uid
                trail.append(f"unit code {code}")
                break
    if u is None:
        return {"text": text, "normalized": n, "result": "unit_text_unresolved", "trail": trail or ["no partner text, alias or unit code"]}
    conv = to_inventory(db, u, item=item)
    if "error" in conv:
        return {"text": text, "normalized": n, "result": conv["error"], "trail": trail}
    return {"text": text, "normalized": n, "result": "resolved", "uom_id": u, "unit": code_of(u), "factor": conv["factor"], "source": conv["source"], "trail": trail}


def propose_unit(db, item, partner=None, typed=None, source_line=None):
    """Rule 13 for purchasing: source line, (barcode), partner_item.uom_id, supplier_item.order_uom_id, product
    purchase_uom_id, inventory unit. Returns (uom_id, proposed_uom_source, trail)."""
    trail = []
    if typed:
        return typed, None, ["typed by the person: wins, not reported as proposed"]
    if source_line:
        return source_line, "source_line", ["the source line's unit"]
    trail.append("barcode: none scanned")
    if partner:
        r = db.val("select uom_id from partner_item where partner_id=%s and item_id=%s and is_active", (partner, item))
        trail.append(f"partner_item.uom_id: {code_of(r) if r else 'not set'}")
        if r:
            return r, "partner_item", trail
        r = db.val("select order_uom_id from supplier_item where supplier_partner_id=%s and item_id=%s", (partner, item))
        trail.append(f"supplier_item.order_uom_id: {code_of(r) if r else 'no supplier item'}")
        if r:
            return r, "supplier_item", trail
    r = db.val("select p.purchase_uom_id from item i join product p on p.id=i.product_id where i.id=%s", (item,))
    trail.append(f"product.purchase_uom_id: {code_of(r)}")
    if r:
        return r, "product_default", trail
    inv = item_product(db, item)[1]
    return inv, "inventory_unit", trail
