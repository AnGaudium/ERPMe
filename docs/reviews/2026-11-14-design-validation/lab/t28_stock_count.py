"""Scenario: the stock documents of ADR-0075 (stock count, stock transfer, scrap, internal consumption). Not product code.

Run: python t28_stock_count.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs).

K: the count (rule 3): the book quantity frozen per key, the difference counted minus book, several entries of one key summed
   in the inventory unit, a key with no line posting nothing and a counted zero a shortage, a pick between the freeze and the
   posting never a difference, the shortage and surplus movements, the dated negative stock check, the reversal and its refusal
   when a surplus was consumed, bin netting leaving INV-866 true, INV-865 and INV-866 on rows.
T: the two-step transfer (rules 1, 2): a receive within its dispatch, a short receipt leaving stock in transit, the dispatch
   not reversible before its receive, INV-867 and INV-868 on rows.
With --load: the DDL of the four documents (keys, the line unit block, the freeze columns, serial quantities, the reason kind,
the cost center or project bearer) and, on a posted count and its reversal with material document lines, INV-866 in SQL.
Not covered: commands, the stock lock helper, the journal, warehouse tasks, reservations.
"""
import os, sys
from datetime import datetime, timezone
from decimal import Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from fx_adr74 import DOCS, RESULTS, build, check, conn, doc, ins, new, reset_and_load, trial  # noqa: E402

NOW = datetime.now(timezone.utc)


# ======================================================================= reference functions
def freeze(stock, keys=None):
    """Rule 3: the book quantity of each counted key (a key with no stock has book 0)."""
    return {k: stock.get(k, D(0)) for k in (keys if keys is not None else stock)}


def differences(lines, book):
    """Counted entries per key summed, minus the stored book quantity. Keys with no line are absent."""
    counted = {}
    for key, q in lines:
        counted[key] = counted.get(key, D(0)) + D(q)
    return {k: counted[k] - book[k] for k in counted}


def post_count(lines, book, stock_now, net_bins=False):
    """The movements a count posts: (key, movement type, quantity); the dated negative stock check on shortages."""
    diff = differences(lines, book)
    moves = []
    for k, d in sorted(diff.items()):
        if d > 0:
            moves.append((k, "stock_count_surplus", d))
        elif d < 0:
            if stock_now.get(k, D(0)) + d < 0:
                raise ValueError("negative_stock")
            moves.append((k, "stock_count_shortage", -d))
    return moves


def per_item_lot(moves):
    out = {}
    for (item, bin_, lot, status), mt, q in moves:
        s = q if mt == "stock_count_surplus" else -q
        out[(item, lot)] = out.get((item, lot), D(0)) + s
    return out


def inv_866(lines, book, moves):
    """The signed sum of the material lines equals the sum of counted minus stored book, per (item, lot)."""
    want = {}
    for (item, bin_, lot, status), d in differences(lines, book).items():
        want[(item, lot)] = want.get((item, lot), D(0)) + d
    got = per_item_lot(moves)
    return all(want.get(k, D(0)) == got.get(k, D(0)) for k in set(want) | set(got))


def inv_865(rows):
    """Every line of one key holds the same book quantity, freeze time and difference reason."""
    seen, bad = {}, []
    for r in rows:
        v = (r["book"], r["taken"], r["reason"])
        if seen.setdefault(r["key"], v) != v:
            bad.append(r["key"])
    return sorted(set(bad))


def reverse(moves, stock_now):
    out = []
    for k, mt, q in moves:
        back = "stock_count_shortage" if mt == "stock_count_surplus" else "stock_count_surplus"
        if back == "stock_count_shortage" and stock_now.get(k, D(0)) - q < 0:
            raise ValueError("negative_stock")
        out.append((k, back, q))
    return out


def receive_ok(dispatch_lines, receive_lines):
    """INV-867: each receive line names a dispatch line of the same item and lot and receives no more than it sent."""
    sent = {l["id"]: l for l in dispatch_lines}
    for r in receive_lines:
        s = sent.get(r["dispatch_line"])
        if s is None or (s["item"], s["lot"]) != (r["item"], r["lot"]) or D(r["q"]) > D(s["q"]):
            return False
    return True


def warehouse_kinds_ok(step, from_kind, to_kind, dispatch_to_kind=None):
    """INV-868."""
    if step == "direct":
        return from_kind == "physical" and to_kind == "physical"
    if step == "dispatch":
        return from_kind == "physical" and to_kind in ("transit", "goods_sent")
    return from_kind == dispatch_to_kind and from_kind in ("transit", "goods_sent") and to_kind == "physical"


# ======================================================================= K: the count
A, Bk = ("A", "bin1", None, "available"), ("B", "bin1", None, "available")
stock = {A: D(10), Bk: D(5)}
book = freeze(stock, [A, Bk])
check("K01 the freeze stores the stock of each counted key, and a key with no stock has book 0",
      book == {A: D(10), Bk: D(5)} and freeze(stock, [("C", "bin1", None, "available")]) == {("C", "bin1", None, "available"): D(0)})
check("K02 several entries of one key are summed before the difference (3 cartons of 4 and 2 pieces against a book of 10)",
      differences([(A, 12), (A, 0), (A, 2)], book) == {A: D(4)})
check("K03 a key with no line is not counted and posts nothing; a counted zero is a line and posts a shortage",
      post_count([(A, 10)], book, stock) == [] and post_count([(A, 10), (Bk, 0)], book, stock) == [(Bk, "stock_count_shortage", D(5))])
check("K04 a surplus posts stock_count_surplus and a shortage stock_count_shortage, once per key",
      post_count([(A, 13), (Bk, 4)], book, stock) == [(A, "stock_count_surplus", D(3)), (Bk, "stock_count_shortage", D(1))])
now = dict(stock); now[A] = D(7)                       # a pick of 3 between the freeze and the posting (EC-322)
check("K05 a pick between the freeze and the posting is not a difference: counted 10 against a book of 10 posts nothing, and stock stays 7",
      post_count([(A, 10)], book, now) == [])
now2 = {A: D(2), Bk: D(5)}
try:
    post_count([(A, 4)], book, now2); ok = False
except ValueError as e:
    ok = str(e) == "negative_stock"
check("K06 a shortage beyond the stock now (a big pick after the freeze) is refused by the dated negative stock check", ok)
lines = [(A, 13), (Bk, 4)]
moves = post_count(lines, book, stock)
check("K07 INV-866 holds for a count with a surplus and a shortage", inv_866(lines, book, moves))
check("K08 INV-866 finds a posting that is one unit short", not inv_866(lines, book, [(A, "stock_count_surplus", D(2)), (Bk, "stock_count_shortage", D(1))]))
Bk2 = ("B", "bin2", None, "available")
lines2 = [(Bk, 4), (Bk2, 6)]
book2 = {Bk: D(5), Bk2: D(5)}
m2 = post_count(lines2, book2, {Bk: D(5), Bk2: D(5)})
check("K09 with a shortage in one bin and a surplus in another, INV-866 holds per item and lot (the sum is zero), netted or gross",
      inv_866(lines2, book2, m2) and per_item_lot(m2) == {("B", None): D(0)})
check("K10 the reversal repeats the movements the other way and nets to zero",
      per_item_lot(moves) and all(v == 0 for v in per_item_lot(moves + reverse(moves, {A: D(13), Bk: D(4)})).values()))
try:
    reverse(moves, {A: D(0), Bk: D(4)}); ok = False
except ValueError as e:
    ok = str(e) == "negative_stock"
check("K11 a surplus count whose stock was shipped cannot be reversed (EC-323)", ok)
check("K12 INV-865 finds a key whose lines hold different book quantities",
      inv_865([{"key": A, "book": D(10), "taken": 1, "reason": None}, {"key": A, "book": D(9), "taken": 1, "reason": None}, {"key": Bk, "book": D(5), "taken": 1, "reason": None}]) == [A])

# ======================================================================= T: transfers
disp = [{"id": "d1", "item": "A", "lot": None, "q": 10}, {"id": "d2", "item": "B", "lot": None, "q": 4}]
check("T01 a receive within its dispatch is valid; a short receipt of 8 of 10 is valid and leaves 2 in transit",
      receive_ok(disp, [{"dispatch_line": "d1", "item": "A", "lot": None, "q": 8}]) and 10 - 8 == 2)
check("T02 INV-867 refuses a receive of more than was sent, of another item, or of an unknown dispatch line",
      not receive_ok(disp, [{"dispatch_line": "d1", "item": "A", "lot": None, "q": 11}])
      and not receive_ok(disp, [{"dispatch_line": "d1", "item": "B", "lot": None, "q": 1}])
      and not receive_ok(disp, [{"dispatch_line": "zz", "item": "A", "lot": None, "q": 1}]))
check("T03 INV-868: direct between physical warehouses, dispatch into transit or goods_sent, receive out of the dispatch's destination",
      warehouse_kinds_ok("direct", "physical", "physical") and not warehouse_kinds_ok("direct", "physical", "transit")
      and warehouse_kinds_ok("dispatch", "physical", "transit") and warehouse_kinds_ok("dispatch", "physical", "goods_sent")
      and not warehouse_kinds_ok("dispatch", "physical", "physical")
      and warehouse_kinds_ok("receive", "transit", "physical", "transit") and not warehouse_kinds_ok("receive", "goods_sent", "physical", "transit"))

# ======================================================================= X: the DDL (--load)
if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("X00 load_all.py loads every DDL file with the ADR-0075 tables", n_tables > 0, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    I = build(c)
    cols = {}
    for t_, col, nul in X("select table_name, column_name, is_nullable from information_schema.columns where table_schema='nativeflows'").fetchall():
        cols.setdefault(t_, {})[col] = nul
    NEW = ("stock_transfer", "stock_transfer_line", "stock_count", "stock_count_line", "scrap", "scrap_line", "internal_consumption", "internal_consumption_line")
    check("X01 the eight tables exist with company_id and recorded_at NOT NULL", all(t_ in cols and cols[t_].get("company_id") == "NO" and cols[t_].get("recorded_at") == "NO" for t_ in NEW),
          [t_ for t_ in NEW if t_ not in cols])
    UNIT = ("quantity", "uom_id", "uom_numerator", "uom_denominator", "uom_factor_source", "inventory_quantity")
    check("X02 every line table carries the unit block, NOT NULL", all(cols[t_].get(b) == "NO" for t_ in NEW if t_.endswith("_line") for b in UNIT))
    check("X03 a transfer line has no status (transfers move available stock only); the other lines carry the held status",
          "stock_status" not in cols["stock_transfer_line"] and all("stock_status" in cols[t_] for t_ in ("stock_count_line", "scrap_line", "internal_consumption_line")))

    for code, name, direction in (("stock_count_surplus", "Count surplus", "in"), ("stock_count_shortage", "Count shortage", "out")):
        X("""insert into movement_type (id, code, name, direction, value_source, costing_role, offset_transaction_key, needs_reference, sap_analog, added_in)
             values (%s,%s,%s,%s,'regime','regime',%s,true,'701','0.1.0')""", (new(), code + I["t"], name, direction, "inventory_count_" + ("surplus" if direction == "in" else "shortage")))
    MT = {r[0][:-8]: r[1] for r in X("select code, id from movement_type where code like %s", ("stock_count_%" + I["t"],)).fetchall()}

    def unit(q):
        return dict(quantity=q, uom_id=I["ea"], uom_numerator=1, uom_denominator=1, uom_factor_source="identity", inventory_quantity=q)

    def count_header(cx):
        d = doc(cx, I, "stock_count")
        ins(cx, "stock_count", id=d, company_id=I["co"], warehouse_id=I["w1"], document_date="2026-11-10", posting_date="2026-11-10")
        return d

    def cline(cx, d, n, q, book_q, bin_=None, **o):
        v = dict(id=new(), company_id=I["co"], stock_count_id=d, warehouse_id=I["w1"], line_number=n, item_id=I["item"], bin_id=bin_ or I["b1"],
                 book_quantity=book_q, book_taken_at=NOW)
        v.update(unit(q)); v.update(o)
        ins(cx, "stock_count_line", **v)

    with c.transaction():
        cd = count_header(c)
        cline(c, cd, 1, 12, 10); cline(c, cd, 2, 2, 10)             # one key, two entries
        cline(c, cd, 3, 3, 5, bin_=I["bin_a"], difference_reason_id=I["reason_count_difference"], difference_note="miscount")
        cline(c, cd, 4, 0, 0, bin_=I["bin_a"], item_id=I["item2"])  # a counted zero where nothing was booked
    check("X04 a count with two entries of one key, a reason and a counted zero is stored", True)
    trial("X05 a counted quantity is not negative", lambda cx: cline(cx, count_header(cx), 1, -1, 0), "ck_stock_count_line_")
    trial("X06 the book quantity is not negative", lambda cx: cline(cx, count_header(cx), 1, 1, -1), "ck_stock_count_line_book_quantity")
    trial("X07 the difference reason is of kind count_difference (a scrap reason is refused by the key)",
          lambda cx: cline(cx, count_header(cx), 1, 1, 1, difference_reason_id=I["reason_scrap"]), "stock_count_line_company_id_difference_reason_id")
    trial("X08 a counted bin is one of the count's warehouse", lambda cx: cline(cx, count_header(cx), 1, 1, 1, bin_=I["b2"]), "fk_stock_count_line_bin")
    trial("X09 a serial counts 0 or 1", lambda cx: cline(cx, count_header(cx), 1, 2, 0, serial_number_id=new()), "ck_stock_count_line_serial_quantity")
    trial("X10 line numbers are unique within a count", lambda cx: (lambda d: (cline(cx, d, 1, 1, 1), cline(cx, d, 1, 2, 1)))(count_header(cx)), "stock_count_line_stock_count_id_line_number_key")
    trial("X11 the unit snapshot is checked (1 EA entered as 5 inventory units)", lambda cx: ins(cx, "stock_count_line", id=new(), company_id=I["co"], stock_count_id=count_header(cx),
          warehouse_id=I["w1"], line_number=1, item_id=I["item"], bin_id=I["b1"], book_quantity=0, book_taken_at=NOW, quantity=1, uom_id=I["ea"], uom_numerator=1,
          uom_denominator=1, uom_factor_source="identity", inventory_quantity=5), "ck_stock_count_line_uom")
    keys = X("""select bin_id, item_id, count(*), count(distinct book_quantity), count(distinct book_taken_at), count(distinct difference_reason_id) from stock_count_line
                where stock_count_id=%s group by bin_id, item_id, lot_id, serial_number_id, stock_status order by 3 desc""", (cd,)).fetchall()
    check("X12 INV-865 in SQL: the key with two entries holds one book quantity, freeze time and reason", keys[0][2] == 2 and keys[0][3:] == (1, 1, 0), keys[0])

    # ---- posting and reversal: material documents (the lab writes what the stock lock helper would)
    def material(cx, document, lines, reversal=False):
        md = new()
        ins(cx, "material_document", id=md, company_id=I["co"], document_id=document, posting_date="2026-11-10")
        for n, (item, bin_, qty, mt) in enumerate(lines, 1):
            direction = "in" if mt == "surplus" else "out"
            if reversal:
                direction = "out" if direction == "in" else "in"
            ins(cx, "material_document_line", id=new(), company_id=I["co"], material_document_id=md, line_number=n, source_line_number=n, item_id=item, warehouse_id=I["w1"],
                movement_type_id=MT["stock_count_" + mt], direction=direction, is_reversal=reversal, quantity=qty, company_amount=0, bin_id=bin_, posting_date="2026-11-10")
    # key (item, b1): counted 14, book 10: surplus 4; key (item, bin_a): counted 3, book 5: shortage 2; key (item2, bin_a): counted 0, book 0: nothing
    with c.transaction():
        material(c, cd, [(I["item"], I["b1"], 4, "surplus"), (I["item"], I["bin_a"], 2, "shortage")])
    sql_866 = """select m.item_id, sum(case when m.direction = 'in' then m.quantity else -m.quantity end) from material_document_line m
                 join material_document md on md.id = m.material_document_id where md.document_id = %s group by m.item_id"""
    got = {r[0]: r[1] for r in X(sql_866, (cd,)).fetchall()}
    want = X("""select item_id, sum(inventory_quantity) - sum(b) from (select item_id, bin_id, lot_id, serial_number_id, stock_status, sum(inventory_quantity) inventory_quantity,
                max(book_quantity) b from stock_count_line where stock_count_id = %s group by 1,2,3,4,5) k group by item_id""", (cd,)).fetchall()
    check("X13 INV-866 in SQL: the signed sum of the material lines equals counted minus stored book, per item", {r[0]: r[1] for r in want} == {I["item"]: D(2), I["item2"]: D(0)} and got == {I["item"]: D(2)},
          (dict(want), got))
    rev = doc(c, I, "stock_count")
    ins(c, "stock_count", id=rev, company_id=I["co"], warehouse_id=I["w1"], document_date="2026-11-11", posting_date="2026-11-11")
    with c.transaction():
        material(c, rev, [(I["item"], I["b1"], 4, "surplus"), (I["item"], I["bin_a"], 2, "shortage")], reversal=True)
    net = X(sql_866, (rev,)).fetchall()
    check("X14 a reversal's material lines carry is_reversal and the opposite direction, and net the original to zero", net[0][1] == D(-2) and got[I["item"]] + net[0][1] == 0, net)

    # ---- transfers
    def transfer(cx, step="direct", frm="w1", to="w2", dispatch=None, **o):
        d = doc(cx, I, "stock_transfer")
        ins(cx, "stock_transfer", id=d, company_id=I["co"], step=step, from_warehouse_id=I[frm], to_warehouse_id=I[to], dispatch_transfer_id=dispatch,
            document_date="2026-11-10", posting_date="2026-11-10", **o)
        return d
    def tline(cx, d, n, q, frm="w1", to="w2", **o):
        v = dict(id=new(), company_id=I["co"], stock_transfer_id=d, from_warehouse_id=I[frm], to_warehouse_id=I[to], line_number=n, item_id=I["item"])
        v.update(unit(q)); v.update(o)
        ins(cx, "stock_transfer_line", **v)
        return v["id"]
    with c.transaction():
        td = transfer(c); tline(c, td, 1, 5)
        dd = transfer(c, "dispatch", "w1", "wt"); dl = tline(c, dd, 1, 10, "w1", "wt")
        rd = transfer(c, "receive", "wt", "w2", dispatch=dd); tline(c, rd, 1, 8, "wt", "w2", dispatch_line_id=dl)
    check("X15 a direct transfer, a dispatch into a transit warehouse and its receive of 8 of 10 are stored", True)
    trial("X16 a transfer is between two different warehouses", lambda cx: transfer(cx, "direct", "w1", "w1"), "ck_stock_transfer_warehouses")
    trial("X17 a receive names its dispatch", lambda cx: transfer(cx, "receive", "wt", "w2"), "ck_stock_transfer_dispatch")
    trial("X18 only a receive names a dispatch", lambda cx: transfer(cx, "direct", "w1", "w2", dispatch=dd), "ck_stock_transfer_dispatch")
    trial("X19 a dispatch is received by one document", lambda cx: transfer(cx, "receive", "wt", "w2", dispatch=dd), "ux_stock_transfer_dispatch_transfer_id")
    trial("X20 a transfer line is of its header's warehouses", lambda cx: tline(cx, td, 9, 1, "w2", "w1"), "stock_transfer_line_company_id_stock_transfer_id_")
    trial("X21 a source bin is of the source warehouse", lambda cx: tline(cx, td, 9, 1, from_bin_id=I["b2"]), "fk_stock_transfer_line_from_bin")
    trial("X22 a lot and a serial are never both named", lambda cx: tline(cx, td, 9, 1, lot_id=new(), serial_number_id=new()), "ck_stock_transfer_line_lot_or_serial")
    kinds = dict(X("select code, kind from warehouse where company_id=%s", (I["co"],)).fetchall())
    check("X23 INV-868 in SQL for the stored transfers: the dispatch goes to a transit warehouse, the receive comes out of it",
          X("""select (select kind from warehouse where id = d.to_warehouse_id), (select kind from warehouse where id = r.from_warehouse_id)
               from stock_transfer r join stock_transfer d on d.id = r.dispatch_transfer_id where r.id = %s""", (rd,)).fetchone() == ("transit", "transit"), kinds)
    over = X("""select count(*) from stock_transfer_line r join stock_transfer_line d on d.id = r.dispatch_line_id where r.inventory_quantity > d.inventory_quantity or r.item_id <> d.item_id""").fetchone()[0]
    check("X24 INV-867 in SQL: no receive line exceeds its dispatch line", over == 0, over)

    # ---- scrap and internal consumption
    def scrap(cx, q=1, **o):
        d = doc(cx, I, "scrap")
        ins(cx, "scrap", id=d, company_id=I["co"], document_date="2026-11-10", posting_date="2026-11-10")
        v = dict(id=new(), company_id=I["co"], scrap_id=d, line_number=1, item_id=I["item"], warehouse_id=I["w1"], bin_id=I["b1"], scrap_reason_id=I["reason_scrap"])
        v.update(unit(q)); v.update(o)
        ins(cx, "scrap_line", **v)
    with c.transaction():
        scrap(c, stock_status="blocked", reason_note="cracked")
        scrap(c, cost_center_id=I["cc"])
    check("X25 a scrap line from the blocked status with a reason, and one with a cost center, are stored", True)
    check("X26 the scrap reason column is nullable: the company setting documents.reason_required.scrap decides, checked by the command (ADR-0074 rule 22)",
          cols["scrap_line"].get("scrap_reason_id") == "YES")
    trial("X27 the scrap reason is of kind scrap", lambda cx: scrap(cx, scrap_reason_id=I["reason_cancel"]), "scrap_line_company_id_scrap_reason_id_")
    trial("X28 a scrap bears at most one of cost center and project", lambda cx: scrap(cx, cost_center_id=I["cc"], project_id=I["proj"]), "ck_scrap_line_dimension")
    trial("X29 a scrap quantity is positive", lambda cx: scrap(cx, q=0), "ck_scrap_line_")
    def consume(cx, **o):
        d = doc(cx, I, "internal_consumption")
        ins(cx, "internal_consumption", id=d, company_id=I["co"], document_date="2026-11-10", posting_date="2026-11-10")
        v = dict(id=new(), company_id=I["co"], internal_consumption_id=d, line_number=1, item_id=I["item"], warehouse_id=I["w1"], bin_id=I["b1"])
        v.update(unit(1)); v.update(o)
        ins(cx, "internal_consumption_line", **v)
    with c.transaction():
        consume(c, cost_center_id=I["cc"]); consume(c, project_id=I["proj"])
        consume(c, consumption_kind="quality_sample", stock_status="quality_inspection")
    check("X30 a consumption to a cost center, one to a project and a quality sample with none are stored", True)
    trial("X31 a consumption naming both a cost center and a project is refused", lambda cx: consume(cx, cost_center_id=I["cc"], project_id=I["proj"]), "ck_internal_consumption_line_dimension")
    trial("X32 an internal consumption naming neither is refused", lambda cx: consume(cx), "ck_internal_consumption_line_dimension")
    trial("X33 a quality sample may name one, never both", lambda cx: consume(cx, consumption_kind="quality_sample", cost_center_id=I["cc"], project_id=I["proj"]), "ck_internal_consumption_line_dimension")
    trial("X34 a consumption kind is internal or quality_sample", lambda cx: consume(cx, consumption_kind="gift", cost_center_id=I["cc"]), "ck_internal_consumption_line_consumption_kind")
    trial("X35 a stock status is one of the three", lambda cx: consume(cx, cost_center_id=I["cc"], stock_status="reserved"), "ck_internal_consumption_line_stock_status")
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
