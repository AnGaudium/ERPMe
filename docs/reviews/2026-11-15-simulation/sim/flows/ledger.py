"""Posting path (ADR-0014, ADR-0026 rule 3) through the DS-06 triggers, account determination from the l10n_vn TT99
package rows (overlay, ADR-0053), and the stock ledger of DS-09 (material documents, quantities, values).
Simulation code, not product code."""
from decimal import Decimal as D

from .core import EFF, W, fmt, ins, upd, money, new_id


def period_of(day):
    return W.periods[(day.year, day.month)]


def determine(key, valuation_class=None, item_group=None, partner_group=None, tax_code=None, warehouse=None):
    """Most specific row of account_determination whose filled determinants all match (ADR-0015)."""
    best, best_n = None, -1
    given = {"valuation_class": valuation_class, "item_group": item_group, "partner_group": partner_group, "tax_code": tax_code,
             "warehouse": warehouse}
    for r in W.det_rows:
        if r["transaction_key"] != key:
            continue
        ok, n = True, 0
        for k, v in given.items():
            if r[k]:
                if r[k] != v:
                    ok = False
                    break
                n += 1
        if ok and n > best_n:
            best, best_n = r, n
    if not best:
        raise KeyError(f"account_determination_missing: {key} {valuation_class} {item_group} {tax_code}")
    return best["account_code"]


def post_entry(db, doc_id, posting_date, lines, description=None, document_date=None):
    """One journal entry per document (uq_journal_entry_document_id). Each line: acct, side, amount (positive),
    optional partner, item, warehouse, mdl, pol, tax_code, evidence, cost_object, key, desc, and an open-item effect:
    oi_create {kind, due_date, installment, reference, partner_reference, payment_term_id} or oi_settle (item id)."""
    period, fy = period_of(posting_date)
    eid = new_id("journal_entry")
    summary = []
    with db.tx():
        ins(db, "journal_entry", id=eid, document_id=doc_id, posting_date=posting_date, document_date=document_date or posting_date,
            posting_period_id=period, fiscal_year_id=fy, line_count=len(lines), database_transaction_number="0")
        for n, ln in enumerate(lines, 1):
            a = W.acc[ln["acct"]]
            amt = money(ln["amount"])
            signed = amt if ln["side"] == "debit" else -amt
            lid, oi = new_id("journal_line"), None
            if "oi_create" in ln:
                c = ln["oi_create"]
                oi = new_id("open_item")
                ins(db, "open_item", id=oi, partner_id=ln["partner"], account_id=a["id"], open_item_kind=c["kind"], natural_side=ln["side"],
                    transaction_currency="VND", origin_document_id=doc_id, origin_journal_line_id=lid, installment_number=c.get("installment", 1),
                    payment_term_id=c.get("payment_term_id"), document_date=document_date or posting_date, posting_date=posting_date,
                    original_posting_date=posting_date, due_date=c.get("due_date"), reference=c.get("reference"),
                    partner_reference=c.get("partner_reference"), original_transaction_amount=signed, original_company_amount=signed,
                    open_transaction_amount=signed, open_company_amount=signed)
                W.code_of[oi] = f"{c.get('reference')} #{c.get('installment', 1)}"
                ln["_oi"] = oi
            if "oi_settle" in ln:
                oi = ln["oi_settle"]
                cur = db.one("select open_transaction_amount, natural_side from open_item where id=%s for update", (oi,))
                if cur[1] == ln["side"] or abs(signed) > abs(cur[0]):
                    raise RuntimeError("open_item_oversettled or wrong side (ADR-0026 rule 6)")
            ins(db, "journal_line", id=lid, journal_entry_id=eid, line_number=n, posting_period_id=period, account_id=a["id"],
                system_account_id=a["sa"], transaction_key_id=W.tk.get(ln.get("key")), side=ln["side"], transaction_currency="VND",
                transaction_amount=signed, company_currency="VND", company_amount=signed, partner_id=ln.get("partner"), item_id=ln.get("item"),
                warehouse_id=ln.get("warehouse"), material_document_line_id=ln.get("mdl"), open_item_id=oi, purchase_order_line_id=ln.get("pol"),
                tax_code_id=ln.get("tax_code"), evidence_method=ln.get("evidence"), cost_object_id=ln.get("cost_object"),
                salesperson_id=ln.get("salesperson"), description=ln.get("desc"))
            if "oi_settle" in ln:
                db.x("""update open_item set open_transaction_amount = open_transaction_amount + %s, open_company_amount = open_company_amount + %s,
                        is_settled = (open_transaction_amount + %s = 0), last_settlement_date = %s where id=%s""", (signed, signed, signed, posting_date, oi))
                EFF.add("open_item (settlement)")
            row = {"line": n, "account": ln["acct"], "account_name": a["name"], "account_name_vi": a["name_vi"], "system_account": a["sa_code"],
                   "side": ln["side"], "amount": fmt(amt)}
            if ln.get("key"):
                row["transaction_key"] = ln["key"]
            for k in ("partner", "item"):
                if ln.get(k):
                    row[k] = W.code_of.get(ln[k], str(ln[k]))
            if "oi_create" in ln:
                c = ln["oi_create"]
                row["open_item"] = f"creates {c['kind']} #{c.get('installment', 1)} due {c.get('due_date')}"
            elif "oi_settle" in ln:
                row["open_item"] = f"settles {W.code_of.get(ln['oi_settle'], 'item')}"
            if ln.get("evidence"):
                row["evidence_method"] = ln["evidence"]
            if ln.get("cost_object"):
                row["cost_object"] = W.code_of.get(ln["cost_object"])
            if ln.get("desc"):
                row["desc"] = ln["desc"]
            summary.append(row)
        db.x("set constraints all immediate")      # balance trigger and deferred keys fire here
        db.x("set constraints all deferred")       # back to the default for later statements of an enclosing transaction
    entry = {"journal_entry_id": str(eid), "document": W.code_of.get(doc_id, str(doc_id)), "posting_date": posting_date.isoformat(),
             "description": description, "lines": summary,
             "balanced": sum(D(s["amount"]) * (1 if s["side"] == "debit" else -1) for s in summary) == 0}
    EFF.journal.append(entry)
    return eid, entry


# ------------------------------------------------------------------ stock (DS-09 tables)
def material_document(db, doc_id, posting_date):
    mid = new_id("material_document")
    ins(db, "material_document", id=mid, document_id=doc_id, posting_date=posting_date)
    return {"id": mid, "n": 0, "posting_date": posting_date}


def stock_move(db, md, item, wh, movement, qty, amount, source_line=None, cost_object=None):
    """One material document line plus the stock quantity and value caches (ADR-0020 rule 3; ADR-0023 rule 8)."""
    md["n"] += 1
    mt = W.movement[movement]
    lid = new_id("material_document_line")
    bin_id = W.bins[wh]
    ins(db, "material_document_line", id=lid, material_document_id=md["id"], line_number=md["n"], source_line_number=source_line,
        item_id=item, warehouse_id=wh, movement_type_id=mt["id"], direction=mt["direction"], quantity=qty, company_amount=money(amount),
        bin_id=bin_id, cost_object_id=cost_object, posting_date=md["posting_date"])
    sign = 1 if mt["direction"] == "in" else -1
    row = db.one("select id, quantity from stock_quantity where item_id=%s and warehouse_id=%s and bin_id=%s", (item, wh, bin_id))
    if row:
        if row[1] + sign * D(qty) < 0:
            raise RuntimeError("stock_insufficient (ADR-0023 rule 9)")
        upd(db, "stock_quantity", {"id": row[0]}, quantity=row[1] + sign * D(qty))
    else:
        if sign < 0:
            raise RuntimeError("stock_insufficient (ADR-0023 rule 9)")
        ins(db, "stock_quantity", id=new_id("stock_quantity"), item_id=item, warehouse_id=wh, bin_id=bin_id, quantity=qty)
    row = db.one("select id, company_amount from stock_value where item_id=%s and warehouse_id=%s", (item, wh))
    if row:
        upd(db, "stock_value", {"id": row[0]}, company_amount=row[1] + sign * money(amount))
    else:
        ins(db, "stock_value", id=new_id("stock_value"), item_id=item, warehouse_id=wh, company_amount=money(amount))
    return lid


def add_value(db, item, wh, amount):
    """A value-only change of stock (landed cost to stock): stock_value only."""
    row = db.one("select id, company_amount from stock_value where item_id=%s and warehouse_id=%s", (item, wh))
    upd(db, "stock_value", {"id": row[0]}, company_amount=row[1] + money(amount))


def on_hand(db, item, wh=None):
    wh = wh or W.wh
    q = db.val("select coalesce(sum(quantity),0) from stock_quantity where item_id=%s and warehouse_id=%s", (item, wh))
    v = db.val("select coalesce(sum(company_amount),0) from stock_value where item_id=%s and warehouse_id=%s", (item, wh))
    return D(q), D(v)


def preliminary_price(db, item, day):
    p, _ = period_of(day)
    r = db.val("select unit_price from preliminary_price where item_id=%s and posting_period_id=%s", (item, p))
    if r is None:
        r = db.val("select unit_price from preliminary_price where item_id=%s order by recorded_at desc limit 1", (item,))
    return D(r) if r is not None else None
