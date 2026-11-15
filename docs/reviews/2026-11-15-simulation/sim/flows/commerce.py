"""Pricing procedure (ADR-0047 rule 16), tax engine (ADR-0041 via the DS-19 matrix), price steps and line taxes."""
from decimal import Decimal as D
from fractions import Fraction as F

from .core import W, ins, money, new_id
from . import md, pure

STEP_NO = {"list_price": 1, "base_price": 2, "promotion": 3, "manual_discount": 4, "net_unit_price": 5, "line_amount": 6, "document_discount": 7}


def tax_for(db, direction, day, partner_tax_group="domestic", item_tax_group="standard"):
    """tax.contract.compute_taxes, reduced: the matrix row in force gives the code; the rate in force on the tax date."""
    codes = db.val("""select tax_codes from tax_matrix where direction=%s and partner_tax_group=%s and item_tax_group=%s and effective_from<=%s
                      order by effective_from desc limit 1""", (direction, partner_tax_group, item_tax_group, day))
    code = codes[0]
    rate = db.val("""select r.rate_percent from tax_rate r join tax_code c on c.id=r.tax_code_id where c.code=%s and r.effective_from<=%s
                     order by r.effective_from desc limit 1""", (code, day))
    return code, D(rate)


def price_line(db, pl, day, qty, uom, item=None, product=None, values=None, manual_price=None, manual_discount=D(0)):
    gp = md.get_price(db, pl, day, qty, uom, item=item, product=product, values=values)
    r = pure.price_line(gp["price"], qty, manual_price=manual_price, manual_discount=manual_discount)
    r["list_price"] = gp["price"]
    r["find_price"] = gp
    return r


def write_steps(db, doc_id, line_number, list_price, net_unit, amount, doc_discount=D(0), manual_discount=D(0), source_kind="procedure",
                copied_from=None, list_source=None):
    rows = [("list_price", list_price), ("base_price", list_price)]
    if manual_discount:
        rows.append(("manual_discount", manual_discount))
    rows += [("net_unit_price", net_unit), ("line_amount", amount)]
    if doc_discount:
        rows.append(("document_discount", doc_discount))
    for step, value in rows:
        if value is None:
            continue
        extra = {}
        if source_kind == "copied":
            extra = {"copied_from_document_id": copied_from[0], "copied_from_line_number": copied_from[1]}
        if step == "list_price" and list_source and source_kind != "copied":
            extra.update(source_table=list_source[0], source_id=list_source[1])
        ins(db, "document_line_price_step", document_id=doc_id, line_number=line_number, step_number=STEP_NO[step], step=step, value=D(value),
            source_kind=source_kind, **extra)


def write_tax(db, doc_id, line_number, base, code, rate, stated=None):
    computed = money(F(str(base)) * F(str(rate)) / 100)
    tax = money(stated) if stated is not None else computed
    ins(db, "document_line_tax", id=new_id("document_line_tax"), document_id=doc_id, line_number=line_number, tax_code_id=W.tax[code],
        rate_percent=rate, base_transaction_amount=money(base), tax_transaction_amount=tax, computed_tax_transaction_amount=computed)
    return tax, computed


def credit_exposure(db, partner):
    """sales.contract.get_credit_exposure, reduced: open receivable items plus open approved orders (gross)."""
    oi = db.val("select coalesce(sum(open_company_amount),0) from open_item where partner_id=%s and natural_side='debit'", (partner,))
    orders = W.open_orders.get(partner, D(0)) if hasattr(W, "open_orders") else D(0)
    limit = db.val("select credit_limit from customer_profile where partner_id=%s", (partner,))
    return {"open_items": D(oi), "open_orders": orders, "exposure": D(oi) + orders, "credit_limit": limit}
