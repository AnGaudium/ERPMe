"""Scenario: the remaining stock documents and the reason settings (ADR-0075 rules 11 to 15; ADR-0074 rule 22). Not product code.

Run: python t29_other_stock_documents.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs).

R: the reason requirement (ADR-0074 rule 22): the core defaults per kind from settings.csv, reason_required when a required
   reason is missing, a company that sets a kind false, and an other issue with and without its reason.
O: the opening balance (rule 13): posting only in the migration period (migration_not_open elsewhere), the value spread by
   largest remainder summing exactly to the area's total, the first preliminary price as total over quantity (INV-870, INV-872).
F: transfer order fulfilment (rule 14): the warehouse fit per step (INV-871), the open quantity after a dispatch and a short receive.
C: the catalog rows: eight reason settings and five count settings in settings.csv, in the shape rules 22 and 15 state.
With --load: the DDL of other_receipt, other_issue, opening_balance and transfer_order (keys, the unit block, the reason kind,
the value, the bearer), the transfer order key on stock_transfer_line and demand_supply_line, and nullable reason columns.
Not covered: commands, the migration batch (DS-21), the journal, reservations.
"""
import csv, os, sys
from datetime import date
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from fx_adr74 import DOCS, RESULTS, build, check, conn, doc, ins, new, reset_and_load, trial  # noqa: E402

SETTINGS = {r["key"]: r for r in csv.DictReader(open(os.path.join(DOCS, "catalogs", "settings.csv"), encoding="utf-8"))}
KINDS = ("cancel", "reject", "return", "scrap", "count_difference", "block", "other_receipt", "other_issue")


# ======================================================================= reference functions
def required(kind, company_settings):
    key = f"documents.reason_required.{kind}"
    return company_settings.get(key, SETTINGS[key]["core_default"]) == "true"


def check_reason(kind, reason_id, company_settings):
    """None when acceptable, else the error code."""
    return "reason_required" if reason_id is None and required(kind, company_settings) else None


def opening_ok(posting_date, migration_period, migration_open=True):
    start, end = migration_period
    return None if migration_open and start <= posting_date <= end else "migration_not_open"


def spread(total, quantities):
    """Largest remainder by quantity, in the currency's minor unit (whole units here); ties by line order."""
    q = sum(quantities)
    exact = [F(total) * x / q for x in quantities]
    base = [int(e) for e in exact]
    rest = total - sum(base)
    order = sorted(range(len(exact)), key=lambda i: (-(exact[i] - base[i]), i))
    for i in order[:rest]:
        base[i] += 1
    return base, F(total, q)


def fits(step, line_from, line_to, order_from, order_to):
    if step == "direct":
        return (line_from, line_to) == (order_from, order_to)
    if step == "dispatch":
        return line_from == order_from
    return line_to == order_to


def open_quantity(ordered, postings):
    """Delivered = posted receives and direct transfers; a dispatch delivers nothing yet."""
    return ordered - sum(q for step, q in postings if step in ("receive", "direct"))


# ======================================================================= R: reasons
d = {k: SETTINGS[f"documents.reason_required.{k}"]["core_default"] for k in KINDS}
check("R01 core defaults: true for count differences, scrap, returns, rejections, other receipts and issues; false for cancel and block",
      d == {"cancel": "false", "reject": "true", "return": "true", "scrap": "true", "count_difference": "true", "block": "false",
            "other_receipt": "true", "other_issue": "true"}, d)
check("R02 an other issue line without a reason is refused with reason_required; with one it passes",
      check_reason("other_issue", None, {}) == "reason_required" and check_reason("other_issue", "r1", {}) is None)
check("R03 a cancel without a reason passes by default; a company that sets documents.reason_required.cancel true refuses it",
      check_reason("cancel", None, {}) is None and check_reason("cancel", None, {"documents.reason_required.cancel": "true"}) == "reason_required")
check("R04 a company that sets documents.reason_required.scrap false lets a scrap line post without a reason",
      check_reason("scrap", None, {"documents.reason_required.scrap": "false"}) is None)

# ======================================================================= O: opening balance
mig = (date(2026, 12, 31), date(2026, 12, 31))
check("O01 an opening balance posts in the migration period only (INV-870); an ordinary date is migration_not_open, and so is a closed migration",
      opening_ok(date(2026, 12, 31), mig) is None and opening_ok(date(2027, 1, 5), mig) == "migration_not_open"
      and opening_ok(date(2026, 12, 31), mig, migration_open=False) == "migration_not_open")
lines, price = spread(1000, [1, 1, 1])
check("O02 a total of 1,000 over three lines of one unit spreads as 333, 333, 334 and sums exactly (INV-872, EC-334)",
      sorted(lines) == [333, 333, 334] and sum(lines) == 1000, lines)
check("O03 the first preliminary price is the total over the quantity, exactly 1000/3", price == F(1000, 3), price)
lines2, price2 = spread(1001, [5, 2, 3])
check("O04 an uneven split by quantity still sums to the total, each line within one unit of its exact share",
      sum(lines2) == 1001 and all(abs(l - F(1001) * q / 10) < 1 for l, q in zip(lines2, [5, 2, 3])) and price2 == F(1001, 10), lines2)

# ======================================================================= F: transfer orders
check("F01 a direct transfer fulfils an order line only between its two warehouses; a dispatch from its source; a receive into its destination (INV-871)",
      fits("direct", "W1", "W2", "W1", "W2") and not fits("direct", "W1", "W3", "W1", "W2")
      and fits("dispatch", "W1", "WT", "W1", "W2") and not fits("dispatch", "W3", "WT", "W1", "W2")
      and fits("receive", "WT", "W2", "W1", "W2") and not fits("receive", "WT", "W3", "W1", "W2"))
check("F02 an order of 10 with a dispatch of 10 and a receive of 8 stays open for 2 (EC-335)", open_quantity(10, [("dispatch", 10), ("receive", 8)]) == 2)

# ======================================================================= C: catalog rows
cnt = [k for k in ("movement_type.stock_count_shortage.value_source", "movement_type.stock_count_shortage.costing_role",
                   "movement_type.stock_count_surplus.value_source", "movement_type.stock_count_surplus.costing_role", "stock_count.bin_difference_method")]
check("C01 the five count settings are required regime settings with no core default, leaf package (ADR-0075 rule 15)",
      all(k in SETTINGS and SETTINGS[k]["core_default"] == "fail_closed" and SETTINGS[k]["scope"] == "regime" and SETTINGS[k]["leaf"] == "package" for k in cnt),
      [k for k in cnt if k not in SETTINGS])
check("C02 the eight reason settings are company booleans on the leaf reason, tightened by true (ADR-0074 rule 22)",
      all(SETTINGS[f"documents.reason_required.{k}"]["scope"] == "company" and SETTINGS[f"documents.reason_required.{k}"]["leaf"] == "reason"
          and SETTINGS[f"documents.reason_required.{k}"]["direction"] == "true_tighter" for k in KINDS))

# ======================================================================= X: the DDL (--load)
if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("X00 load_all.py loads every DDL file with the tables of ADR-0075 rules 11 to 14", n_tables > 0, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    I = build(c)
    cols = {}
    for t_, col, nul in X("select table_name, column_name, is_nullable from information_schema.columns where table_schema='nativeflows'").fetchall():
        cols.setdefault(t_, {})[col] = nul
    NEW = ("other_receipt", "other_receipt_line", "other_issue", "other_issue_line", "opening_balance", "opening_balance_line", "transfer_order", "transfer_order_line")
    check("X01 the eight tables exist with company_id and recorded_at NOT NULL", all(t_ in cols and cols[t_].get("company_id") == "NO" and cols[t_].get("recorded_at") == "NO" for t_ in NEW))
    REASONS = {"other_receipt_line": "reason_id", "other_issue_line": "reason_id", "scrap_line": "scrap_reason_id", "stock_count_line": "difference_reason_id",
               "return_to_supplier_line": "return_reason_id", "production_receipt": "scrap_reason_id", "approval": "reject_reason_id", "document": "canceled_reason_id"}
    check("X02 every reason column is nullable, so the company setting alone decides (ADR-0074 rule 22)", all(cols[t_].get(cn) == "YES" for t_, cn in REASONS.items()),
          [t_ for t_, cn in REASONS.items() if cols[t_].get(cn) != "YES"])
    fks = {r[0] for r in X("select conname from pg_constraint where contype='f' and conname in ('fk_demand_supply_line_transfer_order_line')").fetchall()}
    check("X03 demand_supply_line.transfer_order_line_id has its foreign key, and stock_transfer_line names the order line",
          "fk_demand_supply_line_transfer_order_line" in fks and "transfer_order_line_id" in cols["stock_transfer_line"])

    def unit(q):
        return dict(quantity=q, uom_id=I["ea"], uom_numerator=1, uom_denominator=1, uom_factor_source="identity", inventory_quantity=q)

    def header(cx, t):
        dd = doc(cx, I, t)
        ins(cx, t, id=dd, company_id=I["co"], document_date="2026-11-10", posting_date="2026-11-10")
        return dd

    def issue(cx, **o):
        v = dict(id=new(), company_id=I["co"], other_issue_id=header(cx, "other_issue"), line_number=1, item_id=I["item"], warehouse_id=I["w1"], bin_id=I["b1"])
        v.update(unit(1)); v.update(o); ins(cx, "other_issue_line", **v)
    with c.transaction():
        issue(c, reason_id=I["reason_other_issue"], reason_note="sample for a trade fair", cost_center_id=I["cc"])
        issue(c)
    check("X04 an other issue line with its reason and a cost center, and one without (the setting decides), are stored", True)
    trial("X05 the reason of an other issue is of kind other_issue", lambda cx: issue(cx, reason_id=I["reason_scrap"]), "other_issue_line_company_id_reason_id_")
    trial("X06 an other issue bears at most one of cost center and project", lambda cx: issue(cx, cost_center_id=I["cc"], project_id=I["proj"]), "ck_other_issue_line_dimension")

    def receipt(cx, **o):
        v = dict(id=new(), company_id=I["co"], other_receipt_id=header(cx, "other_receipt"), line_number=1, item_id=I["item"], warehouse_id=I["w1"],
                 company_amount=1000, reason_id=I["reason_other_receipt"])
        v.update(unit(10)); v.update(o); ins(cx, "other_receipt_line", **v)
    with c.transaction():
        receipt(c)
    check("X07 an other receipt line valued 1,000 without a bin (the default receiving bin applies) is stored", True)
    trial("X08 an other receipt line carries its value", lambda cx: receipt(cx, company_amount=None), "null value in column \"company_amount\"")
    trial("X09 the value is not negative", lambda cx: receipt(cx, company_amount=-1), "ck_other_receipt_line_company_amount")
    trial("X10 the reason of an other receipt is of kind other_receipt", lambda cx: receipt(cx, reason_id=I["reason_other_issue"]), "other_receipt_line_company_id_reason_id_")

    def opening(cx, **o):
        v = dict(id=new(), company_id=I["co"], opening_balance_id=header(cx, "opening_balance"), line_number=1, item_id=I["item"], warehouse_id=I["w1"], bin_id=I["b1"],
                 company_amount=333, stock_status="blocked")
        v.update(unit(1)); v.update(o); ins(cx, "opening_balance_line", **v)
    with c.transaction():
        opening(c)
    check("X11 an opening balance line in the blocked status with its spread value is stored", True)
    check("X12 an opening balance has no reason, business unit or custom values (ADR-0075 rule 13)",
          not any(cn in cols["opening_balance_line"] for cn in ("reason_id",)) and "business_unit_id" not in cols["opening_balance"] and "custom_values" not in cols["opening_balance"])
    trial("X13 an opening line's bin is of its warehouse", lambda cx: opening(cx, bin_id=I["b2"]), "fk_opening_balance_line_bin")

    def order(cx, frm="w1", to="w2"):
        dd = doc(cx, I, "transfer_order")
        ins(cx, "transfer_order", id=dd, company_id=I["co"], from_warehouse_id=I[frm], to_warehouse_id=I[to], document_date="2026-11-10", requested_date="2026-11-20")
        return dd

    def oline(cx, o, frm="w1", to="w2", **kw):
        v = dict(id=new(), company_id=I["co"], transfer_order_id=o, from_warehouse_id=I[frm], to_warehouse_id=I[to], line_number=1, item_id=I["item"])
        v.update(unit(10)); v.update(kw); ins(cx, "transfer_order_line", **v)
        return v["id"]
    with c.transaction():
        to_ = order(c); tol = oline(c, to_)
        st = doc(c, I, "stock_transfer")
        ins(c, "stock_transfer", id=st, company_id=I["co"], step="dispatch", from_warehouse_id=I["w1"], to_warehouse_id=I["wt"], document_date="2026-11-10", posting_date="2026-11-10")
        v = dict(id=new(), company_id=I["co"], stock_transfer_id=st, from_warehouse_id=I["w1"], to_warehouse_id=I["wt"], line_number=1, item_id=I["item"], transfer_order_line_id=tol)
        v.update(unit(10)); ins(c, "stock_transfer_line", **v)
    check("X14 a transfer order with a line, and a dispatch into the transit warehouse that names the order line, are stored", True)
    trial("X15 a transfer order is between two different warehouses", lambda cx: order(cx, "w1", "w1"), "ck_transfer_order_warehouses")
    trial("X16 an order line is of its order's warehouses", lambda cx: oline(cx, to_, "w2", "w1", line_number=2), "transfer_order_line_company_id_transfer_order_id_")
    trial("X17 an order line names a lot or nothing, never a serial (no serial column)", lambda cx: oline(cx, to_, line_number=3, serial_number_id=new()), "column \"serial_number_id\"")
    trial("X18 the unit snapshot is checked", lambda cx: oline(cx, to_, line_number=4, inventory_quantity=50), "ck_transfer_order_line_uom")
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
