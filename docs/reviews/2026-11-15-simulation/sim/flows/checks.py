"""Invariant checks over the whole database after the run (catalogs/invariants.csv codes)."""
from decimal import Decimal as D

from .core import W, jsonable


def global_checks(db):
    out = []

    def rec(code, name, ok, detail=""):
        out.append({"code": code, "name": name, "ok": bool(ok), "detail": jsonable(detail)})

    r = db.one("""select count(*), coalesce(sum(n),0), count(*) filter (where s <> 0 or n <> lc) from (
                    select e.id, e.line_count lc, count(l.id) n, sum(l.company_amount) s from journal_entry e join journal_line l on l.journal_entry_id=e.id group by e.id) x""")
    rec("INV-01", "every journal entry balances and has its declared line count", r[2] == 0, f"{r[0]} entries, {r[1]} lines, unbalanced {r[2]}")
    tb = db.val("select coalesce(sum(company_amount),0) from journal_line")
    rec("INV-02", "trial balance sums to zero", tb == 0, f"sum {tb}")
    bad = db.val("""select count(*) from journal_line l join account a on a.id=l.account_id where l.system_account_id <> a.system_account_id""")
    rec("INV-05", "every line's system account equals its account's mapping", bad == 0, bad)
    bad = db.all("""select o.reference, o.original_transaction_amount, coalesce(sum(l.transaction_amount),0), o.open_transaction_amount
                      from open_item o left join journal_line l on l.open_item_id=o.id group by o.id
                     having o.open_transaction_amount <> coalesce(sum(l.transaction_amount),0)""")
    rec("INV-oi", "each open item's open amount equals the sum of its journal lines (ADR-0026 rule 1)", not bad, bad)
    ctl = db.all("""select a.code, sum(l.company_amount), (select coalesce(sum(o.open_company_amount),0) from open_item o where o.account_id=a.id)
                      from journal_line l join account a on a.id=l.account_id join system_account s on s.id=a.system_account_id
                     where s.control_kind in ('receivable','payable') group by a.id, a.code""")
    rec("INV-ctl", "receivable and payable control accounts equal their open items (ADR-0026)", all(x[1] == x[2] for x in ctl),
        [{"account": c, "balance": b, "open_items": o} for c, b, o in ctl])
    inv = db.all("""select a.code, coalesce(sum(l.company_amount),0) from journal_line l join account a on a.id=l.account_id
                     join system_account s on s.id=a.system_account_id where s.control_kind='inventory' group by a.code order by a.code""")
    sv = {}
    for code, amt in db.all("""select p.valuation_class_id, sum(v.company_amount) from stock_value v join item i on i.id=v.item_id
                                join product p on p.id=i.product_id group by p.valuation_class_id"""):
        sv[code] = amt
    vc_code = {v: k for k, v in W.vc.items()}
    by_acct = {}
    from .ledger import determine
    for vc, amt in sv.items():
        a = determine("inventory_posting", valuation_class=vc_code[vc])
        by_acct[a] = by_acct.get(a, D(0)) + amt
    gl = {c: a for c, a in inv}
    rec("INV-20", "inventory accounts equal the stock valuation (stock_value by valuation class)",
        all(gl.get(a, 0) == v for a, v in by_acct.items()) and all(by_acct.get(a, 0) == v for a, v in gl.items() if a != "154"),
        {"gl": gl, "stock_value": by_acct, "note": "154 (work in process) is a cost-object balance, not stock"})
    neg = db.val("select count(*) from stock_quantity where quantity < 0")
    rec("INV-21", "no negative stock", neg == 0, neg)
    bad = db.all("""select m.id, m.company_amount, coalesce(sum(abs(l.company_amount)),0) from material_document_line m
                     left join journal_line l on l.material_document_line_id=m.id group by m.id having m.company_amount <> coalesce(sum(abs(l.company_amount)),0)""")
    rec("INV-23", "every material line's amount equals the journal lines that refer to it", not bad, len(bad))
    bad = db.all("""select pol.id, coalesce(sum(l.company_amount),0) from purchase_order_line pol
                      join journal_line l on l.purchase_order_line_id=pol.id join account a on a.id=l.account_id and a.code='33881'
                     group by pol.id having coalesce(sum(l.company_amount),0) <> 0
                        and (select coalesce(sum(inventory_quantity),0) from goods_receipt_line g where g.purchase_order_line_id=pol.id)
                          = (select coalesce(sum(inventory_quantity),0) from purchase_invoice_line p where p.purchase_order_line_id=pol.id)""")
    rec("INV-92", "GR/IR is zero on every order line where received equals invoiced", not bad, bad)
    bad = db.val("""select count(*) from policy_decision d join document_version v on v.id=d.document_version_id
                     where v.is_tainted and d.actor_kind <> 'human' and d.outcome='allowed'""")
    rec("INV-84", "no allowed decision for a non-human actor on a tainted version", bad == 0, bad)
    bad = db.all("""select d.number, d.document_type from document d join document_version v on v.document_id=d.id and v.version=d.version
                     where d.state='posted' and v.is_tainted and not exists (select 1 from taint_clearance c where c.document_version_id=v.id)
                       and not exists (select 1 from audit_record a where a.document_id=d.id and a.command_type like 'Post%%' and a.actor_kind='human')""")
    rec("INV-82/84", "every posted, effectively tainted document was posted by a person", not bad, bad)
    bad = db.val("""select count(*) from audit_record where actor_kind='system' and origin_agent_run_id is not null and effect_class in ('posting','master_data_change')""")
    rec("INV-85", "no consumer of an agent chain posts or changes master data", bad == 0, bad)
    bad = db.val("""select count(*) from audit_record where (actor_kind='agent' or origin_agent_run_id is not null) and (effect_class='master_data_change' or is_proposal_bound)""")
    rec("INV-86", "no proposal-bound or master-data command by an agent or its chain", bad == 0, bad)
    bad = db.val("""select count(*) from approval a where a.actor_kind <> 'human'""")
    bad2 = db.val("""select count(*) from approval a where exists (select 1 from document_actor(a.document_id) w where w.actor_role='writer' and w.user_account_id=a.actor_id)""")
    rec("INV-17/225", "every approval is human and no approver wrote a version of the document", bad == 0 and bad2 == 0, {"non_human": bad, "approver_writer": bad2})
    bad = db.val("""select count(*) from (select policy_decision_id, actor_id from approval where decision='approved' group by 1,2 having count(*)>1) x""")
    rec("INV-224", "no person counted twice in one round", bad == 0, bad)
    bad = db.val("""select count(*) from policy_decision where required_rank is not null and (approval_plan is null or jsonb_array_length(approval_plan)=0)""")
    rec("INV-230", "every ranked decision has a plan", bad == 0, bad)
    bad = db.val("""select count(*) from bank_statement_line l where match_state='matched'
                     and not exists (select 1 from document d where d.id=l.matched_document_id and d.state='posted')""")
    rec("INV-95", "every matched bank line refers to a posted document", bad == 0, bad)
    bad = db.val("""select count(*) from document_version v where not v.is_tainted and exists (select 1 from agent_run r where r.id in (v.agent_run_id, v.origin_agent_run_id) and r.tainted_at is not null)""")
    rec("INV-88", "every version written by a tainted run is tainted", bad == 0, bad)
    bad = db.val("""select count(*) from audit_record a join agent_run r on r.id = coalesce(a.agent_run_id, a.origin_agent_run_id)
                     where r.tainted_at is not null and not a.is_draft_only and a.command_type not in ('StartAgentRun','CompleteAgentRun')""")
    rec("INV-216", "every command of a tainted run or its chain is draft-only", bad == 0, bad)
    bad = db.all("""select r.agent_type_code, r.llm_call_count, r.budget->>'max_llm_calls' from agent_run r where r.llm_call_count > (r.budget->>'max_llm_calls')::int""")
    rec("INV-212", "every agent run stayed within its LLM-call budget", not bad, bad)
    bad = db.val("""select count(*) from document_line_price_step s where s.step='line_amount' and exists (
                      select 1 from quotation_line q where q.quotation_id=s.document_id and q.line_number=s.line_number and q.line_amount <> s.value
                      union all select 1 from sales_order_line q where q.sales_order_id=s.document_id and q.line_number=s.line_number and q.line_amount <> s.value
                      union all select 1 from sales_invoice_line q where q.sales_invoice_id=s.document_id and q.line_number=s.line_number and q.line_amount <> s.value
                      union all select 1 from purchase_order_line q where q.purchase_order_id=s.document_id and q.line_number=s.line_number and q.line_amount <> s.value)""")
    rec("INV-93", "price steps reproduce every line amount", bad == 0, bad)
    out += uom_checks(db)
    return out


def uom_checks(db):
    """INV-600 to INV-605 (ADR-0056 rule 25)."""
    from fractions import Fraction as F
    from . import uom as U
    out = []

    def rec(code, name, ok, detail=""):
        out.append({"code": code, "name": name, "ok": bool(ok), "detail": jsonable(detail)})
    part_tables = {"goods_receipt_line", "purchase_invoice_line", "return_to_supplier_line", "delivery_line", "sales_invoice_line"}
    bad, n_lines, missing = [], 0, []
    for t in sorted(U.BLOCK_TABLES):
        cols = db.cols[t]
        itemcol = next((c for c in ("item_id", "component_item_id", "output_item_id") if c in cols), None)
        sel = ", ".join([itemcol or "null", "product_id" if "product_id" in cols else "null", "order_quantity" if t == "planned_order" else "quantity",
                         "uom_id" if "uom_id" in cols else "order_uom_id", "uom_numerator", "uom_denominator", "uom_factor_source",
                         "inventory_quantity" if "inventory_quantity" in cols else ("quantity" if t == "planned_order" else "null")])
        for item, prod, qty, uom_id, n, d, src, inv in db.all(f"select {sel} from {t}"):
            if qty is None and uom_id is None:
                continue
            n_lines += 1
            if None in (n, d, src):
                missing.append(t)
                continue
            r = U.to_inventory(db, uom_id, item=item, product=None if item else prod)
            if "error" in r or r["factor"] != F(n, d) or r["source"] != src:
                bad.append({"table": t, "uom": U.code_of(uom_id), "snapshot": f"{n}/{d} {src}", "resolved": r.get("error") or f"{r['factor']} {r['source']}"})
                continue
            if inv is not None:
                exact = F(str(qty)) * F(n, d)
                dec = U.dec_of(r["inventory_uom_id"])
                if t == "planned_order":
                    ok = F(str(inv)) == U.round_quantity(exact, dec, "half_up")
                elif t in part_tables:
                    ok = abs(F(str(inv)) - exact) <= 1
                else:
                    ok = F(str(inv)) in (U.round_quantity(exact, dec, "half_up"), U.round_quantity(exact, dec, "up"))
                if not ok:
                    bad.append({"table": t, "quantity": qty, "inventory_quantity": inv, "exact": str(exact)})
    rec("INV-600", f"every line's unit block is present and equals convert_quantity ({n_lines} lines in {len(U.BLOCK_TABLES)} tables)", not bad and not missing, bad[:5] or missing[:5])
    # INV-601: replay the cumulative rule per purchase order line (receipts and returns; invoices)
    bad = []
    for pol, oq, ou, n, d, oinv in db.all("select id, quantity, uom_id, uom_numerator, uom_denominator, inventory_quantity from purchase_order_line"):
        f = F(n, d)
        dec = U.dec_of(db.val("select p.inventory_uom_id from purchase_order_line l join item i on i.id=l.item_id join product p on p.id=i.product_id where l.id=%s", (pol,)))
        C_, P_ = F(0), F(0)
        evs = db.all("""select g.recorded_at, 'r', g.id, g.quantity, g.uom_id, g.inventory_quantity, null from goods_receipt_line g where g.purchase_order_line_id=%s
                        union all select r.recorded_at, 'x', r.id, r.quantity, r.uom_id, r.inventory_quantity, r.goods_receipt_line_id from return_to_supplier_line r
                          join goods_receipt_line g on g.id=r.goods_receipt_line_id where g.purchase_order_line_id=%s order by 1""", (pol, pol))
        stored = {}
        for _, kind, lid, qty, uom_id, inv, src in evs:
            if kind == "r":
                stored[lid] = (F(str(qty)), F(str(inv)), uom_id)
                if uom_id == ou:
                    exp = U.round_quantity((C_ + F(str(qty))) * f, dec) - P_
                    if exp != F(str(inv)):
                        bad.append({"line": str(pol), "receipt": float(inv), "expected": float(exp)})
                    C_, P_ = C_ + F(str(qty)), P_ + F(str(inv))
            else:
                pq, pv, pu = stored[src]
                if F(str(inv)) > pv:
                    bad.append({"return_exceeds_part": float(inv), "part": float(pv)})
                if pu == ou:
                    C_, P_ = C_ - F(str(qty)), P_ - F(str(inv))
        Ci, Pi = F(0), F(0)
        for qty, uom_id, inv in db.all("select quantity, uom_id, inventory_quantity from purchase_invoice_line where purchase_order_line_id=%s order by recorded_at", (pol,)):
            if uom_id == ou:
                exp = U.round_quantity((Ci + F(str(qty))) * f, dec) - Pi
                if exp != F(str(inv)):
                    bad.append({"line": str(pol), "invoice": float(inv), "expected": float(exp)})
                Ci, Pi = Ci + F(str(qty)), Pi + F(str(inv))
        if Ci == F(str(oq)) and Pi != F(str(oinv)):
            bad.append({"line": str(pol), "invoiced_parts": float(Pi), "order_inventory_quantity": float(oinv)})
    rec("INV-601", "forward parts follow round((C + q) x f) - P, returns never exceed their part, completed invoices sum to the line", not bad, bad[:5])
    # INV-602: material lines equal their document lines' inventory quantities; stock at the unit's decimals
    bad = []
    for t, hdr in (("goods_receipt_line", "goods_receipt_id"), ("return_to_supplier_line", "return_to_supplier_id"), ("delivery_line", "delivery_id"),
                   ("production_issue_line", "production_issue_id"), ("production_receipt_line", "production_receipt_id")):
        for doc, s in db.all(f"select {hdr}, sum(inventory_quantity) from {t} group by 1"):
            m = db.val("select sum(l.quantity) from material_document_line l join material_document d on d.id=l.material_document_id where d.document_id=%s", (doc,))
            if m != s:
                bad.append({"table": t, "lines": s, "material": m})
    for item, qty in db.all("select item_id, quantity from stock_quantity"):
        dec = U.dec_of(U.item_product(db, item)[1])
        if F(str(qty)) * 10 ** dec != int(F(str(qty)) * 10 ** dec):
            bad.append({"stock_decimals": float(qty)})
    rec("INV-602", "stock only in the inventory unit: material lines equal their lines' inventory quantities, stock at the unit's decimals", not bad, bad[:5])
    bad = []
    for t in sorted(U.BLOCK_TABLES):
        cols = db.cols[t]
        itemcol = next((c for c in ("item_id", "component_item_id", "output_item_id") if c in cols), None)
        if not itemcol:
            continue
        ucol = "uom_id" if "uom_id" in cols else "order_uom_id"
        for item, uom_id, n, d, src in db.all(f"select {itemcol}, {ucol}, uom_numerator, uom_denominator, uom_factor_source from {t} where uom_factor_source in ('item','product')"):
            prod = U.item_product(db, item)[0]
            row = db.one("select numerator, denominator from product_uom where product_id=%s and uom_id=%s and is_active and " +
                         ("item_id=%s" if src == "item" else "item_id is null and %s is not null"), (prod, uom_id, item))
            if not row or F(row[0], row[1]) != F(n, d):
                bad.append({"table": t, "snapshot": f"{n}/{d}", "row": row})
    rec("INV-603", "every item- or product-sourced snapshot carries the factor of the row in force", not bad, bad[:5])
    ser = db.val("select count(*) from product where tracking='serial'")
    rec("INV-604", "serial-tracked products resolve only exact units", True, f"{ser} serial-tracked product(s): nothing to check")
    bad = []
    for pid, uom_id, inv, n, d, ex, fs in db.all("select product_id, uom_id, inventory_uom_id, numerator, denominator, is_exact, factor_source from product_uom where is_active"):
        if U.is_exact(n, d, U.dec_of(inv), U.dec_of(uom_id)) != ex:
            bad.append({"product_uom": U.code_of(uom_id), "is_exact": ex})
        g = U.to_inventory(db, uom_id, product=pid) if fs == "catalog" else None
        if g and g.get("source") == "global" and g["factor"] != F(n, d):
            bad.append({"catalog_factor": U.code_of(uom_id)})
    dup = db.val("select count(*) from (select product_id, item_id, uom_id from product_uom where is_active group by 1,2,3 having count(*)>1) x")
    rec("INV-605", "product units: is_exact by rule 7, catalog rows at the catalog factor, one active row per unit", not bad and dup == 0, bad[:5])
    return out
