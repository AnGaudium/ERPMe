"""Scenario: multiple units of measure (ADR-0056), as pure functions and on the DDL drafts.

Run: python t17_uom.py [--load]
  The pure checks (part U) always run. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there and loads every DDL file of design/, and the database checks (part D) run.
  NATIVEFLOWS_DOCS points at the docs/ tree (default ~/Projects/NativeFlows/docs); NATIVEFLOWS_LAB_DIR at lab.py and load_all.py
  (default: this file's directory).

U: the rules of ADR-0056 as lab functions, with exact fractions: the core unit catalogs; convert_quantity resolution
   (identity, item, product, global in both directions, no chaining, retired rows, company units); exactness against
   brute force; the cumulative rule on the 7/3 bag and on random part sequences with returns, reversals out of order and
   parts in other units; the carton 24/1 and g<->kg examples; round_quantity modes, rounding to zero and scrap; the
   serial whole factor; the proposed-unit order; supplier minimum and multiple in the order unit; the receipt tolerance
   on the ordered quantity; three-way match per inventory unit; the price-break example; returns priced in another
   unit; packaging consistency; the issue multiple; alias normalization and unit text resolution; GetItemUnits; the
   l10n_vn unit names against the core catalog.
D: with --load, on all DDL: the core catalogs load into uom and uom_conversion; a purchase order in cartons, receipts
   in pieces and an invoice in cartons leave GR/IR at zero; a bag order with three cumulative receipts does too; the
   line unit block exists on every quantity line table; the database refuses bad factors, snapshots, packaging shapes,
   duplicate units and aliases, and a retired default pick unit; a line naming a retired unit is accepted by the
   database (no check can hold it) and found by the INV-603 query; a kg row retired and replaced on the same unit leaves old
   lines at their snapshot, gives new lines the new factor, and keeps one active row; catalog rows, the clearing posting kind
   and unique item barcodes.
Not covered: commands, the dispatcher, consumers, RLS policies of the company tables, prints and the e-invoice add-on.
"""
import csv, os, random, sys, unicodedata, uuid
from decimal import Decimal as D_
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import RESULTS, conn, expect, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
CAT = os.path.join(DOCS, "catalogs")
NS = uuid.UUID("f244ce09-3c6c-4c82-af14-918bdeca6be3")           # ADR-0006 rule 4


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ======================================================================= the rules as lab functions
def round_quantity(x, dec, mode="half_up"):
    """ADR-0006 rules 15, 17: half_up is half away from zero; up is away from zero."""
    y = F(x) * 10 ** dec
    sign, a = (-1 if y < 0 else 1), abs(y)
    if mode == "up":
        n = -(-a.numerator // a.denominator)
    elif mode == "half_up":
        h = a + F(1, 2)
        n = h.numerator // h.denominator
    else:
        raise ValueError(mode)
    return F(sign * n, 10 ** dec)


def round_unit_price(x):                                         # unit-price scale, 10 decimals, half up
    return round_quantity(x, 10)


def round_amount(x):                                              # VND: 0 decimals, half up
    return round_quantity(x, 0)


def is_exact(n, d, d_inv, d_entered):
    """ADR-0056 rule 7: n x 10^dI divisible by d x 10^dE."""
    return (n * 10 ** d_inv) % (d * 10 ** d_entered) == 0


UNITS = {r["code"]: (r["quantity_kind"], int(r["decimal_places"])) for r in read_csv(os.path.join(CAT, "units.csv"))}
CORE = set(UNITS)
CONV_ROWS = read_csv(os.path.join(CAT, "unit-conversions.csv"))
GLOBAL = {(r["from_code"], r["to_code"]): (int(r["numerator"]), int(r["denominator"]), True) for r in CONV_ROWS}
for code, kind, dec in (("x-carton", "count", 0), ("x-pallet", "count", 0), ("x-pack", "count", 0), ("x-bag", "count", 0),
                        ("x-can", "count", 0), ("x-carton-20", "count", 0)):
    UNITS[code] = (kind, dec)

# products: inventory unit and tracking; items: their product
PROD = {"P_PCS": ("H87", "none"), "P_KG": ("KGM", "none"), "P_G": ("GRM", "none"), "P_T": ("TNE", "none"), "P_L": ("LTR", "none"),
        "P_DAY": ("DAY", "none"), "P_H": ("HUR", "none"),
        "P_SER": ("H87", "serial"), "P_M": ("MTR", "none")}
ITEM = {"I_DAY": "P_DAY", "I_H": "P_H", "I_STD": "P_PCS", "I_BIG": "P_PCS", "I_KG": "P_KG", "I_G": "P_G", "I_T": "P_T", "I_L": "P_L", "I_SER": "P_SER", "I_FRAME": "P_M"}
# product_uom rows: (product, item or None, unit) -> dict
ROWS = {}


def product_uom(prod, unit, n, d, item=None, active=True, source="stated", contains=None, flags=()):
    ROWS[(prod, item, unit)] = dict(id=f"pu:{prod}:{item}:{unit}", n=n, d=d, active=active, source=source, contains=contains, flags=set(flags))


product_uom("P_PCS", "x-carton", 24, 1, flags={"purchase_default", "counting"})
product_uom("P_PCS", "x-pack", 6, 1, flags={"default_pick"})
product_uom("P_PCS", "x-pallet", 960, 1, source="packaging", contains=("x-carton", 40))
product_uom("P_PCS", "x-carton", 12, 1, item="I_BIG")                     # the big variant's carton holds 12
product_uom("P_KG", "x-bag", 7, 3)                                       # 1 bag = 7/3 kg: inexact at 3 decimals
product_uom("P_L", "x-can", 5, 1)
product_uom("P_M", "H87", 12, 5, item="I_FRAME")                         # the configured frame: 1 piece = 2.4 m


def convert_to_inventory(item, unit, rows=None, glob=None):
    """ADR-0056 rule 6: identity, item row, product row, global pair or its inverse; a retired row stops the search."""
    rows = ROWS if rows is None else rows
    glob = GLOBAL if glob is None else glob
    prod = ITEM[item]
    inv = PROD[prod][0]
    if unit == inv:
        return F(1), "identity", None
    for key, src in (((prod, item, unit), "item"), ((prod, None, unit), "product")):
        r = rows.get(key)
        if r:
            return ("uom_retired", None, r["id"]) if not r["active"] else (F(r["n"], r["d"]), src, r["id"])
    if unit in CORE and inv in CORE and UNITS[unit][0] == UNITS[inv][0]:
        if (unit, inv) in glob and glob[(unit, inv)][2]:
            n, d, _ = glob[(unit, inv)]
            return F(n, d), "global", f"uom_conversion:{unit}:{inv}"
        if (inv, unit) in glob and glob[(inv, unit)][2]:
            n, d, _ = glob[(inv, unit)]
            return F(d, n), "global", f"uom_conversion:{inv}:{unit}"
    return "uom_not_allowed", None, None


def convert_quantity(item, from_unit, to_unit):
    fa, sa, _ = convert_to_inventory(item, from_unit)
    fb, sb, _ = convert_to_inventory(item, to_unit)
    if not isinstance(fa, F):
        return fa
    if not isinstance(fb, F):
        return fb
    return fa / fb, (sa, sb)


def convert_part(f, cum, posted, q, dec, mode="half_up"):
    """ADR-0056 rule 10: round((C + q) x f) - P, signed (a return is a negative q)."""
    return round_quantity((cum + q) * f, dec, mode) - posted


def item_units(item):
    """GetItemUnits (ADR-0056 rule 20): every allowed unit with factor, source, exactness and flags."""
    prod = ITEM[item]
    inv = PROD[prod][0]
    out = {inv: dict(factor=F(1), source="identity", is_exact=True, is_active=True)}
    for (p, it, u), r in ROWS.items():
        if p == prod and it in (None, item) and (u not in out or it == item):
            f = F(r["n"], r["d"])
            out[u] = dict(factor=f, source="item" if it else "product", is_active=r["active"], flags=r["flags"],
                          is_exact=is_exact(f.numerator, f.denominator, UNITS[inv][1], UNITS[u][1]), factor_source=r["source"])
    for u in CORE:
        if u not in out and UNITS[u][0] == UNITS[inv][0]:
            f, src, _ = convert_to_inventory(item, u)
            if isinstance(f, F):
                out[u] = dict(factor=f, source=src, is_active=True, is_exact=is_exact(f.numerator, f.denominator, UNITS[inv][1], UNITS[u][1]))
    return out


def propose_unit(typed=None, source_line=None, barcode=None, partner_item=None, supplier_item=None, product_default=None, inventory=None,
                 purchasing=True):
    """ADR-0056 rule 13."""
    if typed:
        return typed, None
    for unit, source in ((source_line, "source_line"), (barcode, "barcode"), (partner_item, "partner_item"),
                         (supplier_item if purchasing else None, "supplier_item"), (product_default, "product_default"), (inventory, "inventory_unit")):
        if unit:
            return unit, source


def plan_order(shortfall, f, minimum, multiple, d_order, d_inv):
    """ADR-0056 rule 14; ADR-0024 rule 15: the shortfall in the order unit, the minimum, then the multiple (up)."""
    x = round_quantity(F(shortfall) / f, d_order, "up")
    q = max(x, F(minimum))
    if multiple:
        m = F(multiple)
        q = -(-q // m) * m
    inv = round_quantity(q * f, d_inv, "half_up")
    return q, inv, inv - shortfall


def gr_ir_value(price, x):
    return price * x


def match_price(invoice_net, inv_qty, price, invoiced_before, tolerance_percent, tolerance_amount):
    """ADR-0056 rule 12: per inventory unit; True when within the larger tolerance."""
    mine = F(invoice_net) / inv_qty
    ref = (gr_ir_value(price, invoiced_before + inv_qty) - gr_ir_value(price, invoiced_before)) / inv_qty
    return abs(mine - ref) <= max(ref * F(tolerance_percent) / 100, F(tolerance_amount)), mine - ref


def find_price(entries, item, unit, qty):
    """ADR-0045 rule 4 with convert_quantity: entered unit first, else the inventory unit x factor (10 decimals, half up)."""
    qty = F(qty)
    f, _, _ = convert_to_inventory(item, unit)
    if not isinstance(f, F):
        return f
    inv = PROD[ITEM[item]][0]
    def best(u, q):
        ok = [(F(m), F(p)) for (uu, m, p) in entries if uu == u and F(m) <= q]
        return max(ok)[1] if ok else None
    p = best(unit, qty)
    if p is None and unit != inv:
        b = best(inv, qty * f)
        p = None if b is None else round_unit_price(b * f)
    return p


def packaging_consistent(prod, unit):
    r = ROWS[(prod, None, unit)]
    cu, cq = r["contains"]
    cf = F(1) if cu == PROD[prod][0] else F(ROWS[(prod, None, cu)]["n"], ROWS[(prod, None, cu)]["d"])
    return F(r["n"], r["d"]) == cq * cf


def requirement(qty_per_base, q_out, base, scrap_percent, f, issue_multiple, d_inv):
    """ADR-0033 rule 6 with ADR-0056 rule 17: exact with scrap, up to whole issue multiples, up to the decimals."""
    exact = F(qty_per_base) * F(q_out) / F(base) * (1 + F(scrap_percent) / 100) * f
    if issue_multiple:
        m = F(issue_multiple) * f
        exact = -(-exact // m) * m
    return round_quantity(exact, d_inv, "up")


FOLD = {"đ": "d", "ð": "d", "ł": "l", "ø": "o", "ß": "ss", "æ": "ae", "œ": "oe", "þ": "th", "ı": "i", "ħ": "h"}   # ADR-0052 rule 17


def normalize_unit_text(text):
    """ADR-0056 rule 19: lower case, NFKD without combining marks, the core fold table, then spaces and . - _ / removed."""
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(FOLD.get(ch, ch) for ch in t if not unicodedata.combining(ch))
    return "".join(ch for ch in t if not ch.isspace() and ch not in ".-_/")


ALIASES = {normalize_unit_text(a): u for a, u in (("Thùng", "x-carton"), ("Cái", "H87"), ("Kg", "KGM"))}


def resolve_unit_text(item, text, partner_texts=None):
    """ADR-0056 rule 19: partner item text, alias, unit code; never guessed."""
    n = normalize_unit_text(text)
    for pt, u in (partner_texts or {}).items():
        if normalize_unit_text(pt) == n:
            return u
    u = ALIASES.get(n) or next((c for c in UNITS if normalize_unit_text(c) == n), None)
    if u is None:
        return "unit_text_unresolved"
    f, _, _ = convert_to_inventory(item, u)
    return u if isinstance(f, F) else f


# ======================================================================= U: pure checks
kinds = {"count", "mass", "length", "area", "volume", "time"}
check("U01 units.csv: 15 core units, unique UN/ECE Rec 20 codes, known kinds, 0 to 6 decimals, no x- code",
      len(CORE) == 15 and all(UNITS[c][0] in kinds and 0 <= UNITS[c][1] <= 6 and not c.startswith("x-") for c in CORE)
      and {"H87", "SET", "KGM", "GRM", "TNE", "MTR", "CMT", "MMT", "MTK", "MTQ", "LTR", "MLT", "HUR", "MIN", "DAY"} == CORE, sorted(CORE))
pairs = [frozenset((r["from_code"], r["to_code"])) for r in CONV_ROWS]
check("U02 unit-conversions.csv: 12 direct pairs of core units of one kind, each stored once from the larger unit (factor >= 1)",
      len(CONV_ROWS) == 12 and len(set(pairs)) == 12
      and all(r["from_code"] in CORE and r["to_code"] in CORE and UNITS[r["from_code"]][0] == UNITS[r["to_code"]][0]
              and int(r["numerator"]) >= int(r["denominator"]) > 0 for r in CONV_ROWS), len(CONV_ROWS))
check("U03 the inventory unit converts by identity, factor 1, no row", convert_to_inventory("I_STD", "H87") == (F(1), "identity", None))
check("U04 an item's own row wins over its product's (the big variant's carton holds 12)", convert_to_inventory("I_BIG", "x-carton")[:2] == (F(12), "item"))
check("U05 without an item row the product's row applies (the standard carton holds 24)", convert_to_inventory("I_STD", "x-carton")[:2] == (F(24), "product"))
check("U06 a stored global pair applies directly: a product kept in grams takes kilograms at 1000/1", convert_to_inventory("I_G", "KGM")[:2] == (F(1000), "global"))
check("U07 the inverse of a stored pair is derived: a product kept in kilograms takes grams at 1/1000", convert_to_inventory("I_KG", "GRM")[:2] == (F(1, 1000), "global"))
no_tg = {k: v for k, v in GLOBAL.items() if set(k) != {"TNE", "GRM"}}
check("U08 no chaining: without the tonne-gram row, grams of a product kept in tonnes are not allowed, although g-kg and kg-t exist",
      convert_to_inventory("I_T", "GRM", glob=no_tg)[0] == "uom_not_allowed" and convert_to_inventory("I_T", "GRM")[0] == F(1, 1000000))
check("U09 a company unit converts only through a product unit: a can of a product kept in pieces is not allowed",
      convert_to_inventory("I_STD", "x-can")[0] == "uom_not_allowed")
check("U10 a unit of another kind with no product unit is not allowed (kilograms of a product kept in pieces)", convert_to_inventory("I_STD", "KGM")[0] == "uom_not_allowed")
rows_ret = dict(ROWS); rows_ret[("P_PCS", "I_BIG", "x-carton")] = dict(ROWS[("P_PCS", "I_BIG", "x-carton")], active=False)
check("U11 a retired item row stops the search with uom_retired; it does not uncover the product's carton of 24",
      convert_to_inventory("I_BIG", "x-carton", rows=rows_ret)[0] == "uom_retired")
rows_ret2 = dict(ROWS); rows_ret2[("P_PCS", None, "x-carton")] = dict(ROWS[("P_PCS", None, "x-carton")], active=False)
check("U12 a retired product row gives uom_retired, never a fall-through", convert_to_inventory("I_STD", "x-carton", rows=rows_ret2)[0] == "uom_retired")
check("U13 between two units the factor is the quotient of their factors to the inventory unit: a carton is 4 packs, a pallet 40 cartons",
      convert_quantity("I_STD", "x-carton", "x-pack")[0] == 4 and convert_quantity("I_STD", "x-pallet", "x-carton")[0] == 40)
check("U14 exactness: carton 24/1 pieces (0, 0 decimals) is exact", is_exact(24, 1, 0, 0))
check("U15 exactness: bag 7/3 kg (kg 3, bag 0 decimals) is inexact: 7000 is not divisible by 3", not is_exact(7, 3, 3, 0))
check("U16 exactness: g to kg (1/1000; kg 3, g 0) and kg to g (1000/1; g 0, kg 3) are both exact", is_exact(1, 1000, 3, 0) and is_exact(1000, 1, 0, 3))
check("U17 exactness: with tonnes at 6 decimals, t to kg and kg to t are both exact; hour and minute are inexact both ways (0.01 h is 0.6 min); day to hour is exact",
      is_exact(1000, 1, UNITS["KGM"][1], UNITS["TNE"][1]) and is_exact(1, 1000, UNITS["TNE"][1], UNITS["KGM"][1]) and not is_exact(1, 60, UNITS["HUR"][1], UNITS["MIN"][1])
      and not is_exact(60, 1, UNITS["MIN"][1], UNITS["HUR"][1]) and is_exact(24, 1, UNITS["HUR"][1], UNITS["DAY"][1]))
rng = random.Random(56)
mism = []
for _ in range(3000):
    n, d, di, de = rng.randint(1, 60), rng.randint(1, 60), rng.randint(0, 3), rng.randint(0, 3)
    brute = all((F(k, 10 ** de) * F(n, d) * 10 ** di).denominator == 1 for k in range(1, 61))
    if brute != is_exact(n, d, di, de):
        mism.append((n, d, di, de))
check("U18 the exactness formula equals brute force (every quantity the entered unit holds converts exactly) on 3000 random factors and decimals", not mism, mism[:3])
f_bag, dkg = F(7, 3), UNITS["KGM"][1]
q_order = round_quantity(3 * f_bag, dkg)
parts, cum, posted = [], F(0), F(0)
for _ in range(3):
    p = convert_part(f_bag, cum, posted, 1, dkg); parts.append(p); cum += 1; posted += p
check("U19 the cumulative rule: three receipts of 1 bag (7/3 kg) against an order of 3 bags are 2.333, 2.334, 2.333 and sum to 7.000",
      parts == [F("2.333"), F("2.334"), F("2.333")] and sum(parts) == q_order == 7, [str(float(x)) for x in parts])
check("U20 rounding each receipt on its own would leave 6.999 kg against 7.000 ordered (the drift the rule removes)",
      3 * round_quantity(f_bag, dkg) == F("6.999"))
price_kg = F(210000, 7)                                          # 70,000 per bag = 30,000 per kg
credits, pos = [], F(0)
for p in parts:
    credits.append(round_amount(gr_ir_value(price_kg, pos + p)) - round_amount(gr_ir_value(price_kg, pos))); pos += p
per_line = 3 * round_amount(gr_ir_value(price_kg, round_quantity(f_bag, dkg)))
check("U21 GR/IR on the bag line: cumulative receipts credit 69,990, 70,020 and 69,990, the invoice of 3 bags debits 210,000, the balance is 0; per-line rounding leaves 30",
      credits == [69990, 70020, 69990] and round_amount(gr_ir_value(price_kg, q_order)) - sum(credits) == 0 and 210000 - per_line == 30, credits)
def grid_ceil(x, dec):
    y = F(x) * 10 ** dec
    return F(-((-y.numerator) // y.denominator), 10 ** dec)


def grid_floor(x, dec):
    y = F(x) * 10 ** dec
    return F(y.numerator // y.denominator, 10 ** dec)


def clamp_part(raw, q, f, dec):
    """ADR-0056 rule 10: a positive forward part lies between q x f - 1 and q x f + 1 inventory units, bounds rounded inward;
    a computed value of zero or less is rejected (quantity_rounds_to_zero) and returns None."""
    if raw <= 0:
        return None
    lo, hi = grid_ceil(q * f - 1, dec), grid_floor(q * f + 1, dec)
    return min(max(raw, lo), hi)


st = dict(seq=0, fwd_max=F(0), ret_max=F(0), ret_over_one=0, clamped=0, exact_seq=0, rejected=0, step_max=F(0))
bad_seq = []
rng22 = random.Random(5622)
FS22 = [F(7, 3), F(5, 7), F(11, 6), F(13, 9), F(8, 3), F(8, 147), F(3, 7), F(25, 72), F(1, 4), F(24, 1), F(12, 1), F(1, 1000), F(1000, 1)]
while st["seq"] < 20000:
    f = rng22.choice(FS22)
    dE, dI = rng22.choice([0, 1, 2]), rng22.choice([0, 0, 1, 2, 3])
    sE, sI = F(1, 10 ** dE), F(1, 10 ** dI)
    exact_unit = is_exact(f.numerator, f.denominator, dI, dE)
    q_s = rng22.randint(2, 300) * sE
    Q_s = round_quantity(q_s * f, dI)
    if Q_s <= 0:
        continue
    st["seq"] += 1; st["exact_seq"] += exact_unit
    C = P = T = F(0); parts_ = []
    dev = lambda: P - round_quantity(C * f, dI)
    def grow(d0):                                               # T grows by the change of the deviation (rule 10); it never shrinks
        global T
        ch = abs(dev() - d0); T += ch; st["step_max"] = max(st["step_max"], ch)
        if ch >= 3:
            bad_seq.append(("growth_per_posting", st["seq"], str(ch)))
    def forward(q):
        global C, P
        raw = round_quantity((C + q) * f, dI) - P
        inv = clamp_part(raw, q, f, dI)
        if inv is None:                                          # zero or less: rejected, nothing posts
            st["rejected"] += 1
            return
        d0 = dev(); C += q; P += inv
        if inv != raw:
            st["clamped"] += 1; grow(d0)
        if inv <= 0 or abs(inv - q * f) > 1:
            bad_seq.append(("forward_bound", st["seq"]))
        st["fwd_max"] = max(st["fwd_max"], abs(inv - q * f))
        parts_.append(dict(q=q, v=inv, rq=F(0), rv=F(0)))
        if P > Q_s + T:
            bad_seq.append(("upper_limit", st["seq"]))
    def give_back(x, r, s_):
        global C, P
        d0 = dev(); x["rq"] += r; x["rv"] += s_; C -= r; P -= s_; grow(d0)
        e = abs(s_ - r * f)
        st["ret_max"] = max(st["ret_max"], e); st["ret_over_one"] += e > 1
        if e > 2 or s_ <= 0 or x["rv"] > x["v"]:
            bad_seq.append(("return_bound", st["seq"], str(e)))
        if x["rq"] == x["q"] and x["rv"] != x["v"]:
            bad_seq.append(("return_sum", st["seq"]))
    for _ in range(rng22.randint(3, 40)):
        op = rng22.random()
        live = [x for x in parts_ if x["q"] > x["rq"]]
        if op < 0.45 and C < q_s:
            forward(rng22.randint(1, int((q_s - C) / sE)) * sE)
        elif op < 0.6 and live:                                  # the whole rest of a part
            x = rng22.choice(live)
            if x["v"] - x["rv"] > 0:
                give_back(x, x["q"] - x["rq"], x["v"] - x["rv"])
        elif op < 0.75 and [x for x in live if x["q"] - x["rq"] > sE]:   # a partial return: its cumulative share of the part
            x = rng22.choice([x for x in live if x["q"] - x["rq"] > sE])
            r = rng22.randint(1, int((x["q"] - x["rq"]) / sE) - 1) * sE
            s_ = round_quantity(x["v"] * (x["rq"] + r) / x["q"], dI) - x["rv"]
            if s_ > 0:                                           # a share that rounds to zero is rejected (quantity_rounds_to_zero)
                give_back(x, r, s_)
        elif op < 0.9 and [x for x in parts_ if x["rq"] == 0]:  # a reversal of an unreturned part, in any order, mirrors it
            x = rng22.choice([x for x in parts_ if x["rq"] == 0]); parts_.remove(x)
            d0 = dev(); C -= x["q"]; P -= x["v"]; grow(d0)
        if abs(dev()) > T:
            bad_seq.append(("deviation_above_T", st["seq"]))
    if C < q_s:
        forward(q_s - C)
    if abs(P - Q_s) > T or (T == 0 and P != Q_s):
        bad_seq.append(("completion", st["seq"]))
    if exact_unit and T != 0:
        bad_seq.append(("exact_T", st["seq"]))
check(f"U22 on {st['seq']} random sequences (inventory units of 0 to 3 decimals, entered units of 0 to 2, {st['exact_seq']} with an exact unit) of forward parts, whole and partial returns and reversals in any order: a forward part computing to zero or less is rejected ({st['rejected']} times), every posted one is positive and within one inventory unit of its exact conversion ({st['clamped']} clamped), every return strictly within two (largest {float(st['ret_max']):.3f}) and never above its part, each deviation-changing posting grows T by less than three units (largest {float(st['step_max']):.3f}), a part's returns sum exactly to it, the deviation never exceeds T, no limit is passed beyond T, completion lands within T (exactly when T is 0), and T stays 0 for every exact unit",
      not bad_seq and st["fwd_max"] <= 1 and st["ret_max"] < 2, bad_seq[:3])
part_v, share = F(2), round_quantity(F(2) * 3 / 4, 0)            # a part of 4 quarters (exact 1 piece) posted 2 after a clamp
check(f"U64 why the database bound is two inventory units, not one: a share of a part can lie more than one unit from its exact conversion ({st['ret_over_one']} returns in U22). A part of 4 at 1/4 piece posted at 2 pieces, partially returned for 3, takes round(2 x 3/4) = 2 against an exact 0.75; clamping the share instead pushes the error into the return that takes the rest, and exact sums need that rest",
      st["ret_over_one"] > 0 and share == 2 and abs(share - F(3, 4)) > 1)
f35, posted35, c35 = F(3, 5), [], F(0)
for _ in range(10):                                               # ten receipts of 1 unit (3/5 piece) on an order of 10 units = 6 pieces
    v_ = clamp_part(round_quantity((c35 + 1) * f35, 0) - sum(posted35), 1, f35, 0)
    if v_ is not None:
        posted35.append(v_); c35 += 1
two35 = clamp_part(round_quantity((c35 + 2) * f35, 0) - sum(posted35), 2, f35, 0)
floor35 = sum(max(round_quantity((k + 1) * f35, 0) - round_quantity(k * f35, 0), F(1)) for k in range(10))   # the removed floor
check("U66 a unit of 3/5 piece on pieces (0 decimals): of ten receipts of 1 unit only the first posts (1 piece); the others compute round(2 x 3/5) - 1 = 0 and are refused (quantity_rounds_to_zero), so nothing inflates; a receipt of 2 units then posts 1; a one-step floor would have posted 10 pieces against an order of 6",
      posted35 == [1] and c35 == 1 and two35 == 1 and floor35 == 10)
f_bar = F(1, 6)
bars2 = [clamp_part(round_quantity(2 * f_bar, 0), 2, f_bar, 0) for _ in range(6)]
check("U67 bars kept in pieces, received in metres at 1 m = 1/6 bar: a receipt of 2 m computes round(2/6) = 0 and is refused, every time; 12 m post 2 bars; a floor would have posted 6 bars for 12 m",
      bars2 == [None] * 6 and clamp_part(round_quantity(12 * f_bar, 0), 12, f_bar, 0) == 2)
def smallest_postable(f, C, P, dE, dI, limit=10000):
    """The details field of quantity_rounds_to_zero: the smallest entered quantity whose cumulative value posts (rule 10)."""
    for k in range(1, limit):
        q = F(k, 10 ** dE)
        if round_quantity((C + q) * f, dI) - P > 0:
            return q
check("U68 quantity_rounds_to_zero names the smallest entered quantity that would post: 2 units after the first 3/5-piece receipt, 3 m for bars at 1 m = 1/6 bar",
      smallest_postable(f35, F(1), F(1), 0, 0) == 2 and smallest_postable(f_bar, F(0), F(0), 0, 0) == 3)
def step_below(n, d, d_entered, d_inv):
    """ADR-0056 rule 7: unit_step_below_inventory_step when one entered step converts to less than half an inventory step."""
    return F(n, d) / 10 ** d_entered < F(1, 2 * 10 ** d_inv)
check("U69 unit_step_below_inventory_step warns at product unit creation for metres on bars (1/6 < 1/2) and minutes on days kept at 2 decimals (1/1440 < 0.005), not for cartons of 24, the 3/5-piece unit, grams on kilograms or bags of 7/3 kg",
      step_below(1, 6, 0, 0) and step_below(1, 1440, 0, 2) and not any(step_below(*a_) for a_ in ((24, 1, 0, 0), (3, 5, 0, 0), (1, 1000, 0, 3), (7, 3, 0, 3))))
ct = F(24)
T_ct = F(0); R_ct = round_quantity(10 * ct, 0); C_ct, P_ct = F(10), R_ct
d0 = P_ct - round_quantity(C_ct * ct, 0); C_ct -= 1; P_ct -= 24; T_ct += abs((P_ct - round_quantity(C_ct * ct, 0)) - d0)   # return 1 carton
R_after = P_ct + 23                                               # 23 pieces in another unit, exact (identity): no rounding, T unchanged
check("U65 exact units keep T at 0: 10 cartons of 24 pieces received, 1 carton returned, then 23 pieces received: T = 0, so 239 of 240 does not fulfil the line, and a receipt of 25 pieces (241) is refused by receipt_exceeds_order",
      T_ct == 0 and R_after == 239 and not abs(R_after - 240) <= T_ct and P_ct + 25 > 240 + T_ct)
tol_parts = [round_quantity(f_bag, dkg) for _ in range(3)]       # an order of 7 kg received as three bags, each converting on its own
tolerance = 3 * F(1, 10 ** dkg)
check("U23 parts in another unit convert on their own and close within the unit rounding tolerance: 3 bags on a 7 kg order give 6.999, fulfilled with a tolerance of 0.003; with no such part the tolerance is 0",
      sum(tol_parts) == F("6.999") and sum(tol_parts) >= 7 - tolerance and 0 * F(1, 10 ** dkg) == 0)
price_pcs = F(2300000, 240)                                      # 10 cartons at 230,000 = 240 pieces
r1 = round_amount(gr_ir_value(price_pcs, 100)) - round_amount(gr_ir_value(price_pcs, 0))
r2 = round_amount(gr_ir_value(price_pcs, 240)) - round_amount(gr_ir_value(price_pcs, 100))
inv_ct = round_quantity(10 * convert_to_inventory("I_STD", "x-carton")[0], 0)
invoice = round_amount(gr_ir_value(price_pcs, inv_ct))
check("U24 the carton example: 10 cartons = 240 pieces; receipts of 100 and 140 pieces credit 958,333 and 1,341,667; the invoice of 10 cartons debits 2,300,000; GR/IR is 0",
      (inv_ct, r1, r2, invoice, invoice - r1 - r2) == (240, 958333, 1341667, 2300000, 0), (inv_ct, r1, r2, invoice))
check("U25 the g<->kg example: 500 g on a product kept in kg is 0.500 kg; 1.250 kg on a product kept in g is 1250 g",
      round_quantity(500 * convert_to_inventory("I_KG", "GRM")[0], dkg) == F("0.5")
      and round_quantity(F("1.25") * convert_to_inventory("I_G", "KGM")[0], UNITS["GRM"][1]) == 1250)
check("U26 round_quantity modes: half_up 2.3335 -> 2.334 and -2.3335 -> -2.334 (half away from zero); up 2.3331 -> 2.334",
      round_quantity(F("2.3335"), 3) == F("2.334") and round_quantity(F("-2.3335"), 3) == F("-2.334") and round_quantity(F("2.3331"), 3, "up") == F("2.334"))
check("U27 1 minute of a product kept in days (2 decimals) rounds to zero: the line is rejected with quantity_rounds_to_zero",
      round_quantity(1 * convert_to_inventory("I_DAY", "MIN")[0], UNITS["DAY"][1]) == 0)
G, scrap = 10, 3
Q = round_quantity(F(G) / (1 - F(scrap, 100)), 0, "up")
req = requirement(2, Q, 1, 5, F(1), None, 0)
check("U28 scrap: Q = 10 / (1 - 3%) = 10.309... is stored rounded up to 11; a component of 2 per unit with 5% scrap needs 2 x 11 x 1.05 = 23.1, rounded up once to 24",
      (Q, req) == (11, 24), (Q, req))
check("U29 serial-tracked products: every unit must be exact: cartons of 24 and pallets of 960 pieces are, a 7/3 unit and kilograms at 4 pieces each (kg 3 decimals) are not (serial_unit_not_exact)",
      [is_exact(n, d, 0, de) for n, d, de in ((24, 1, 0), (960, 1, 0), (7, 3, 0), (4, 1, 3))] == [True, True, False, False])
ctx = dict(partner_item="x-pack", supplier_item="x-carton", product_default="x-carton", inventory="H87")
check("U30 proposed unit: a copied line takes its source line's unit first, then a scanned barcode's",
      propose_unit(source_line="x-pallet", barcode="x-pack", **ctx) == ("x-pallet", "source_line") and propose_unit(barcode="x-pallet", **ctx) == ("x-pallet", "barcode"))
check("U31 proposed unit: then the partner's unit, then the supplier's order unit (purchasing only)",
      propose_unit(**ctx) == ("x-pack", "partner_item")
      and propose_unit(supplier_item="x-carton", product_default="x-pack", inventory="H87") == ("x-carton", "supplier_item")
      and propose_unit(supplier_item="x-carton", product_default="x-pack", inventory="H87", purchasing=False) == ("x-pack", "product_default"))
check("U32 proposed unit: then the inventory unit; a typed unit always wins and is not reported as proposed",
      propose_unit(inventory="H87") == ("H87", "inventory_unit") and propose_unit(typed="x-pack", **ctx) == ("x-pack", None))
check("U33 supplier order unit: a need of 100 pieces, cartons of 24, minimum 2, multiple 1 gives 5 cartons, 120 pieces, excess 20",
      plan_order(100, F(24), 2, 1, 0, 0) == (5, 120, 20))
check("U34 ... a need of 10 pieces is raised to the minimum of 2 cartons: 48 pieces, excess 38", plan_order(10, F(24), 2, 1, 0, 0) == (2, 48, 38))
check("U35 ... in an inexact order unit: a need of 10 kg in bags of 7/3 kg with multiple 2 gives 6 bags, 14.000 kg, excess 4.000",
      plan_order(10, f_bag, 0, 2, 0, 3) == (6, 14, 4))
limit = 240 * (1 + F(5, 100))
old_second = (240 - 240) * (1 + F(5, 100))                       # the open quantity after a full receipt, times the tolerance
check("U36 receipt tolerance on the ordered quantity: 240 ordered at 5% allows 252 in total, so 240 then 12 pass and a further 1 is refused; on the open quantity the 12 would be refused after a full receipt while one receipt of 252 passes",
      240 + 12 <= limit < 240 + 12 + 1 and 12 > old_second and 252 <= 240 * (1 + F(5, 100)), float(limit))
ok1, diff1 = match_price(2300000, 240, price_pcs, 0, 0, 0)
ok2, diff2 = match_price(2310000, 240, price_pcs, 0, 0, 40)
ok3, _ = match_price(2310000, 240, price_pcs, 0, 0, 50)
check("U37 three-way match per inventory unit: an invoice of 10 cartons at 230,000 matches exactly; at 231,000 it is 41.67 per piece above, beyond a tolerance amount of 40 per inventory unit and within 50",
      ok1 and diff1 == 0 and not ok2 and ok3 and round(float(diff2), 2) == 41.67, float(diff2))
inv_mixed = 9 * 24 + 30
check("U38 the match quantity compares inventory quantities: 9 cartons and 30 pieces (246) exceed 240 x 1.02 = 244.8",
      inv_mixed > 240 * F(102, 100))
LIST = [("H87", 0, 10000), ("H87", 100, 9000), ("x-carton", 0, 230000)]
LIST2 = [("H87", 0, 10000), ("H87", 100, 9000), ("x-carton", 10, 220000)]
LIST_KG = [("KGM", 0, 10000), ("KGM", 5, 9500)]
got = (find_price(LIST, "I_STD", "x-carton", 5), find_price(LIST2, "I_STD", "x-carton", 5), find_price(LIST2, "I_STD", "x-carton", 2),
       find_price(LIST_KG, "I_KG", "x-bag", 3), find_price(LIST_KG, "I_KG", "x-bag", 2))
check("U39 the price-break example: 5 cartons 230,000 (the carton entry wins over 9,000 x 24); with a carton break only from 10: 5 cartons 216,000, 2 cartons 240,000; 3 bags 22,166.6666666667, 2 bags 23,333.3333333333",
      got == (230000, 216000, 240000, F("22166.6666666667"), F("23333.3333333333")), [str(x) for x in got])
p_bag = F(100000)
p_kg = round_unit_price(p_bag / f_bag * 1)
amount_kg = round_amount(7 * p_kg)
check("U40 a credit in kg of an invoice line of 3 bags at 100,000: the price per kg is 42,857.1428571429 and 7 kg credit 300,000, the line's whole net amount",
      p_kg == F("42857.1428571429") and amount_kg == 300000, str(p_kg))
check("U41 packaging: a pallet that contains 40 cartons of 24 has factor 960, consistent; 950 would be uom_packaging_inconsistent",
      packaging_consistent("P_PCS", "x-pallet") and F(950) != 40 * F(24))
check("U42 issue multiple: 0.25 can per unit, 1 can = 5 litres, for Q = 10 is 2.5 cans = 12.500 l, raised to 3 whole cans = 15.000 l",
      requirement(F("0.25"), 10, 1, 0, F(5), None, 3) == F("12.5") and requirement(F("0.25"), 10, 1, 0, F(5), 1, 3) == 15)
check("U43 alias normalization: Thùng, THUNG and ' thung ' are one text; m² becomes m2; Đôi becomes doi",
      len({normalize_unit_text(x) for x in ("Thùng", "THUNG", " thung ")}) == 1 and normalize_unit_text("m²") == "m2" and normalize_unit_text("Đôi") == "doi")
check("U44 unit text resolution: the partner's own text first, then an alias, then a code; unknown text is unit_text_unresolved, never guessed",
      resolve_unit_text("I_STD", "CTN", {"ctn": "x-carton"}) == "x-carton" and resolve_unit_text("I_STD", "thung") == "x-carton"
      and resolve_unit_text("I_KG", "kgm") == "KGM" and resolve_unit_text("I_STD", "hộp") == "unit_text_unresolved"
      and resolve_unit_text("I_STD", "kg") == "uom_not_allowed")
units_std, units_big = item_units("I_STD"), item_units("I_BIG")
check("U45 GetItemUnits: the standard item lists pieces, carton 24, pack 6, pallet 960 and no kilograms; the big variant lists its own carton of 12",
      set(units_std) == {"H87", "x-carton", "x-pack", "x-pallet"} and units_std["x-carton"]["factor"] == 24 and units_big["x-carton"]["factor"] == 12
      and units_big["x-carton"]["source"] == "item", sorted(units_std))
units_kg = item_units("I_KG")
check("U46 GetItemUnits for a product kept in kg: its bag (7/3, inexact) and the catalog's grams and tonnes, both exact into kg; for a product kept in hours, days convert exactly and minutes do not",
      {"KGM", "x-bag", "GRM", "TNE"} == set(units_kg) and not units_kg["x-bag"]["is_exact"] and units_kg["GRM"]["is_exact"] and units_kg["TNE"]["is_exact"]
      and item_units("I_H")["DAY"]["is_exact"] and not item_units("I_H")["MIN"]["is_exact"],
      sorted(units_kg))
check("U47 the configured frame bought by the metre has its own item-level factor: 1 piece = 12/5 m, exact at m 3 decimals",
      convert_to_inventory("I_FRAME", "H87")[:2] == (F(12, 5), "item") and is_exact(12, 5, UNITS["MTR"][1], 0))
rows_rep = dict(ROWS)
rows_rep[("P_PCS", None, "KGM")] = dict(id="pu:kg4", n=4, d=1, active=True, source="stated", contains=None, flags=set())
old_line = dict(qty=2, n=4, d=1, inv=round_quantity(2 * convert_to_inventory("I_STD", "KGM", rows=rows_rep)[0], 0))
retired = [dict(rows_rep[("P_PCS", None, "KGM")], active=False)]          # retire the row of 4 and add a row of 5 on the same unit
rows_rep[("P_PCS", None, "KGM")] = dict(id="pu:kg5", n=5, d=1, active=True, source="stated", contains=None, flags=set())
f_new = convert_to_inventory("I_STD", "KGM", rows=rows_rep)
def inv603(line, follow_on=False):
    """A line after the retirement violates INV-603 when it carries a retired row's factor that no active row has, unless it follows its source."""
    f = F(line["n"], line["d"])
    act = rows_rep[("P_PCS", None, "KGM")]
    return any(F(r["n"], r["d"]) == f for r in retired) and F(act["n"], act["d"]) != f and not follow_on
check("U59 retire and replace on the same unit: an old line keeps 2 kg = 8 pieces at its snapshot 4/1, new lines resolve to the active 5/1 (10 pieces); a new line at 4/1 violates INV-603, a follow-on at 4/1 does not",
      old_line["inv"] == 8 and f_new[:2] == (F(5), "product") and round_quantity(2 * f_new[0], 0) == 10
      and inv603(dict(n=4, d=1)) and not inv603(dict(n=5, d=1)) and not inv603(dict(n=4, d=1), follow_on=True))
# --- first review (B1, S1-S8, N2, N8)
r_bag, c_, p_ = [], F(0), F(0)
for _ in range(3):
    x = convert_part(f_bag, c_, p_, 1, dkg); r_bag.append(x); c_ += 1; p_ += x
ret1 = r_bag[0]                                                   # returning receipt 1 mirrors its own 2.333
c1, p1 = c_ - 1, p_ - ret1
again1 = convert_part(f_bag, c1, p1, 1, dkg)
ret2 = r_bag[1]                                                   # returning receipt 2 mirrors its own 2.334
c2, p2 = c_ - 1, p_ - ret2
again2 = convert_part(f_bag, c2, p2, 1, dkg)
part3 = convert_part(f_bag, F(0), F(0), 3, dkg)                   # one part of 3 bags, returned bag by bag
rets, rq, rinv = [], 0, F(0)
for k in range(3):
    ri = round_quantity(part3 * (rq + 1) / 3, dkg) - rinv          # the cumulative share of the part
    rets.append(ri); rq += 1; rinv += ri
check("U49 returns take their part as source: returning receipt 1 posts 2.333 (not 2.334) and the replacement receipt 2.333; returning receipt 2 posts 2.334 and its replacement 2.334; each line sums to 7.000; a 3-bag part returned bag by bag posts 2.333, 2.334, 2.333",
      (ret1, again1, ret2, again2) == (F("2.333"), F("2.333"), F("2.334"), F("2.334")) and p1 + again1 == 7 and p2 + again2 == 7
      and rets == [F("2.333"), F("2.334"), F("2.333")] and sum(rets) == part3 == 7, [str(float(x)) for x in (ret1, again1, ret2, again2)])
f83 = F(8, 3)
dels = [round_quantity(f83, 3) for _ in range(3)]                 # three bags of 8/3 kg, each converting on its own
T3 = 3 * F(1, 1000)
check("U50 the unit rounding tolerance applies both ways: 8.000 kg ordered and three bags of 8/3 kg delivered (2.667 each, 8.001) pass quantity_exceeds_open with T = 0.003 and fulfil the line; without the tolerance the third delivery would be refused",
      sum(dels) == F("8.001") and sum(dels) <= 8 + T3 and abs(sum(dels) - 8) <= T3 and not sum(dels) <= 8)
own = [round_quantity(f_bag, dkg) for _ in range(3)]              # a 7 kg order received as three bags converting on their own
R_, I_ = F(0), F(7)
gr = []
for x in own:
    gr.append(-(round_amount(price_kg * (R_ + x)) - round_amount(price_kg * R_))); R_ += x
inv_debit = round_amount(price_kg * I_)
balance = sum(gr) + inv_debit
clearing = -(round_amount(price_kg * I_) - round_amount(price_kg * R_)) if abs(I_ - R_) <= T3 and I_ > R_ else 0
check("U51 GR/IR rounding clearing: receipts of 6.999 kg against an invoice of 7.000 kg leave 30 on GR/IR; the consequence posting credits round(V(I)) - round(V(R)) = 30 against price_difference and GR/IR is 0; a difference above the tolerance is not cleared",
      (R_, balance, clearing, balance + clearing) == (F("6.999"), 30, -30, 0) and not abs(F("6.996") - 7) <= T3, (str(R_), balance, clearing))
def replace_price_entries(entries, today, product_items, own_item_rows, item=None):
    """ADR-0056 rule 5: entries of the unit valid on or after today at the replaced level: earlier start end-dated, later removed, today refused."""
    out = {}
    for name, key, start, end in entries:
        in_scope = (key == item) if item else (key == "product" or (key in product_items and key not in own_item_rows))
        if not in_scope or (end is not None and end < today):
            continue
        if start == today:
            return "price_entry_starts_today"
        out[name] = ("end", "2026-11-14") if start < today else ("remove", None)
    return out
E = [("E1", "I_STD", "2026-01-01", None), ("E2", "I_STD", "2026-12-01", None), ("E3", "I_BIG", "2026-01-01", None),
     ("E4", "product", "2026-03-01", "2026-12-31"), ("E5", "I_STD", "2026-01-01", "2026-06-30")]
got_p = replace_price_entries(E, "2026-11-15", {"I_STD", "I_BIG"}, {"I_BIG"})
got_i = replace_price_entries(E, "2026-11-15", {"I_STD", "I_BIG"}, set(), item="I_BIG")
got_t = replace_price_entries(E + [("E6", "I_STD", "2026-11-15", None)], "2026-11-15", {"I_STD", "I_BIG"}, {"I_BIG"})
check("U52 price entries at a product-level replacement: E1 (started earlier) end-dated to 2026-11-14, E2 (starts later) removed, the product-keyed E4 end-dated, E3 of an item with its own row and the ended E5 untouched; an item-level replacement touches only that item's entries; an entry starting today refuses it (price_entry_starts_today)",
      got_p == {"E1": ("end", "2026-11-14"), "E2": ("remove", None), "E4": ("end", "2026-11-14")} and got_i == {"E3": ("end", "2026-11-14")}
      and got_t == "price_entry_starts_today", (got_p, got_i, got_t))
def replace_unit(rows, unit, factor, also=None):
    """ADR-0056 rule 5: packaging rows that contain the replaced unit must be replaced in the same command."""
    new = dict(rows); new[("P_PCS", None, unit)] = dict(rows[("P_PCS", None, unit)], n=factor, d=1)
    for (p_, it, u), r in rows.items():
        if r.get("contains") and r["contains"][0] == unit and u not in (also or {}):
            return "uom_packaging_inconsistent"
        if u in (also or {}):
            new[(p_, it, u)] = dict(r, n=also[u], d=1)
    global ROWS
    saved, ROWS = ROWS, new
    ok = packaging_consistent("P_PCS", "x-pallet")
    ROWS = saved
    return ok
check("U53 replacing the carton of 24 by 20 while a pallet contains 40 cartons is refused (uom_packaging_inconsistent) unless the pallet is replaced in the same command, at 800",
      replace_unit(ROWS, "x-carton", 20) == "uom_packaging_inconsistent" and replace_unit(ROWS, "x-carton", 20, {"x-pallet": 800}) is True
      and replace_unit(ROWS, "x-carton", 20, {"x-pallet": 960}) is False)
rows_s6 = dict(ROWS); rows_s6[("P_PCS", "I_STD", "x-carton")] = dict(id="pu:std:ct12", n=12, d=1, active=True, source="stated", contains=None, flags=set())
check("U54 an item's own row for a unit its product already has is a replacement for that item only: the standard item now resolves 12 (item), the product's 24 stays for other items",
      convert_to_inventory("I_STD", "x-carton", rows=rows_s6)[:2] == (F(12), "item") and ROWS[("P_PCS", None, "x-carton")]["n"] == 24)
def catalog_row(item, unit, n, d):
    g = convert_to_inventory(item, unit, rows={})[0]
    return "uom_conversion_conflict" if g != F(n, d) else "catalog"
check("U55 a product unit for a catalog-convertible unit takes the catalog's factor (grams of a product kept in kg: 1/1000, factor_source catalog); another factor is uom_conversion_conflict; a price entry in grams is allowed and found",
      catalog_row("I_KG", "GRM", 1, 1000) == "catalog" and catalog_row("I_KG", "GRM", 1, 999) == "uom_conversion_conflict"
      and find_price([("GRM", 0, 12)], "I_KG", "GRM", 500) == 12)
check("U56 the fold table of ADR-0052: Łódź becomes lodz, Straße strasse, Đôi doi, and ł, ø, æ fold too",
      normalize_unit_text("Łódź") == "lodz" and normalize_unit_text("Straße") == "strasse" and normalize_unit_text("Đôi") == "doi" and normalize_unit_text("łøæ") == "loae")
def post_draft(snapshot, current, follow_on):
    """ADR-0056 rule 9: a draft snapshotted before a retirement keeps it only as a follow-on line; others are resolved again."""
    return (snapshot, None) if follow_on or snapshot == current else (current, "uom_factor_changed")
check("U57 drafts across a retirement: a draft at 4/1 posts at 5/1 with uom_factor_changed; a follow-on draft keeping its source's 4/1 posts at 4/1",
      post_draft(F(4), F(5), False) == (F(5), "uom_factor_changed") and post_draft(F(4), F(5), True) == (F(4), None))
d1 = convert_part(f_bag, F(0), F(0), 1, dkg); d2 = convert_part(f_bag, F(0), F(0), 1, dkg)   # two drafts, both provisional at C = 0
post1 = convert_part(f_bag, F(0), F(0), 1, dkg); post2 = convert_part(f_bag, F(1), post1, 1, dkg)
check("U58 parts are provisional on drafts: two drafts of one bag both show 2.333; the first posts 2.333, the second is recomputed at Post to 2.334 and its pick task changes by 0.001 (part_quantity_recomputed)",
      (d1, d2, post1, post2, post2 - d2) == (F("2.333"), F("2.333"), F("2.333"), F("2.334"), F("0.001")))
# --- second review (S1-S3, N2)
r3 = []; c_, p_ = F(0), F(0)
for _ in range(3):
    x = convert_part(f_bag, c_, p_, 1, dkg); r3.append(x); c_ += 1; p_ += x
inv_part = convert_part(f_bag, F(0), F(0), 3, dkg)                # one invoice line of 3 bags, sourced by the order line
R_ret = p_ - r3[1]                                                # return of receipt 2 mirrors its 2.334
I_follow = inv_part - r3[1]                                       # the supplier credit names that return line: the same 2.334
I_part = inv_part - round_quantity(1 * f_bag, dkg)                # had it applied the part rule on the invoice part: 2.333
gl = lambda I_, R__: round_amount(price_kg * I_) - round_amount(price_kg * R__)
delivered_net, invoiced_net = p_ - r3[1], inv_part - r3[1]        # sales side: customer return of delivery 2 and its sales return
check("U60 a money return follows its stock return: receipt 2 (2.334) returned and its bag credited naming that return line give R = I = 4.666 and GR/IR 0 (the part rule on the invoice would give I = 4.667 and a residual of 30); on the sales side invoiced net equals delivered net and sales_return_due closes",
      (R_ret, I_follow, gl(I_follow, R_ret), I_part, gl(I_part, R_ret), invoiced_net - delivered_net) == (F("4.666"), F("4.666"), 0, F("4.667"), 30, 0))
dl = r3[:]                                                        # deliveries of one bag each: 2.333, 2.334, 2.333
inv_by_order, ci, pi = [], F(0), F(0)
for _ in dl:                                                      # each invoice line sourced by the order line, not the delivery line
    x = convert_part(f_bag, ci, pi, 1, dkg); inv_by_order.append(x); ci += 1; pi += x
check("U61 the source of an invoice is the order line: three delivery lines of 2.333, 2.334 and 2.333 invoiced one by one post 2.333, 2.334, 2.333 and complete at 7.000 = delivered; the delivery lines as sources would stop at 6.999",
      inv_by_order == dl and sum(inv_by_order) == sum(dl) == 7 and 3 * round_quantity(f_bag, dkg) == F("6.999"))
class GrIrLine:
    """A purchase order line in kg (Q = 7.000) with GR/IR postings and the rounding clearing of rule 10."""
    def __init__(s_, q, price, step):
        s_.Q, s_.price, s_.step, s_.R, s_.I, s_.tsteps, s_.clearing, s_.amounts, s_.events = q, price, step, F(0), F(0), 0, None, [], []
    def _v(s_, x):
        return round_amount(s_.price * x)
    def post(s_, side, q, rounded_or_return=False):
        if s_.clearing is not None:                               # every later posting first reverses an active clearing
            s_.amounts.append(-s_.clearing); s_.events.append("reversed"); s_.clearing = None
        before = s_.R if side == "R" else s_.I
        after = before + q
        amt = (s_._v(after) - s_._v(before)) * (-1 if side == "R" else 1)
        s_.amounts.append(amt)
        if side == "R": s_.R = after
        else: s_.I = after
        s_.tsteps += 1 if rounded_or_return else 0
        T = s_.tsteps * s_.step
        if s_.R != s_.I and abs(s_.R - s_.Q) <= T and abs(s_.I - s_.Q) <= T:
            s_.clearing = -(s_._v(s_.I) - s_._v(s_.R)) if s_.I > s_.R else (s_._v(s_.R) - s_._v(s_.I))
            s_.amounts.append(s_.clearing); s_.events.append("fired")
        return sum(s_.amounts)
ln = GrIrLine(F(7), price_kg, F(1, 1000))
for x in own:                                                     # three bags converting on their own: rounded parts in another unit
    ln.post("R", x, True)
b1 = ln.post("I", F(7))                                           # invoice of 7.000 kg: within tolerance, the clearing fires on R
b2 = ln.post("I", F("-0.010"), True)                              # a quantity credit of 0.010 kg: the clearing is reversed, out of tolerance
b3 = ln.post("I", F("0.010"))                                     # a further invoice of 0.010 kg: back within tolerance, it fires again
check("U62 the GR/IR rounding clearing fires on the lagging side (balance 0), a later credit of 0.010 kg reverses it as a consequence and leaves the line out of tolerance (balance -270 = round(V(I)) - round(V(R))), and a later invoice brings the line back and fires it again (balance 0)",
      (b1, b2, b3) == (0, -270, 0) and ln.events == ["fired", "reversed", "fired"] and b2 == round_amount(price_kg * F("6.990")) - round_amount(price_kg * F("6.999")),
      (b1, b2, b3, ln.events))
HIER = {"pack": (6, None), "carton": (24, ("pack", 4)), "pallet": (960, ("carton", 40))}
def check_replacement(repl):
    """ADR-0056 rule 5: packaging rows that contain a replaced unit, transitively, are replaced in the same command and stay consistent."""
    affected, grew = set(repl), True
    while grew:
        grew = False
        for u, (_, cont) in HIER.items():
            if cont and cont[0] in affected and u not in affected:
                affected.add(u); grew = True
    if not affected <= set(repl):
        return "uom_packaging_inconsistent"
    fac = {u: repl.get(u, HIER[u][0]) for u in HIER}
    return all(cont is None or fac[u] == cont[1] * fac[cont[0]] for u, (_, cont) in HIER.items()) or "uom_packaging_inconsistent"
check("U63 packaging replacement is transitive: a pack of 6 becoming 5 needs the carton (4 packs) at 20 and the pallet (40 cartons) at 800 in the same command; leaving out either, or a wrong factor, is uom_packaging_inconsistent",
      check_replacement({"pack": 5}) == check_replacement({"pack": 5, "carton": 20}) == check_replacement({"pack": 5, "carton": 20, "pallet": 960}) == "uom_packaging_inconsistent"
      and check_replacement({"pack": 5, "carton": 20, "pallet": 800}) is True)
vn_path = os.path.join(DOCS, "design", "DS-19-vietnam-tt99", "i18n", "vi", "unit_names.csv")
vn = read_csv(vn_path) if os.path.exists(vn_path) else []
check("U48 l10n_vn unit names: one Vietnamese name for every core unit and only for core units, each unverified with an open question",
      vn and sorted(r["code"] for r in vn) == sorted(CORE) and all(r["name_vi"].strip() and r["basis"] == "unverified" and r["basis_document"].startswith("(DS-") for r in vn),
      len(vn))
# --- UoM simulation review, 2026-11-15: the positions and value of a return, the preliminary price before the first receipt
def layer_value(layers, x):
    """V(x): the exact value of positions 0 to x over GR/IR price layers (from, to, price) (ADR-0047 rule 13)."""
    return sum(p * max(F(0), min(F(x), b) - a) for a, b, p in layers)
rc, c_, p_ = [], F(0), F(0)
for _ in range(3):                                                # receipts of one bag each: 2.333, 2.334, 2.333
    x = convert_part(f_bag, c_, p_, 1, dkg); rc.append(x); c_ += 1; p_ += x
own_pos = [(sum(rc[:k]), sum(rc[:k + 1])) for k in range(3)]     # each receipt line's stored range
q_ret = rc[1]                                                    # the return of receipt 2 mirrors its part (ADR-0056 rule 10)
ret_pos = (p_ - q_ret, p_)                                       # and debits the latest received positions (ADR-0047 rule 13 note)
one = [(F(0), F(10), price_kg)]                                  # one GR/IR price on the line
co = [(F(0), F("4.667"), price_kg), (F("4.667"), F(10), F(33000))]   # a change order before receipt 3: 33,000 per kg
debit = lambda L, a, b: round_amount(layer_value(L, b)) - round_amount(layer_value(L, a))
check("U70 a return debits GR/IR at the line's latest positions and stores them: receipts 2.333, 2.334 and 2.333 hold 0-2.333, "
      "2.333-4.667 and 4.667-7.000; the return of receipt 2 mirrors that receipt's 2.334 kg (its part reference) and stores positions "
      "4.666-7.000 (to - from = its inventory quantity); with one price both ranges are worth 70,020, after a change order to 33,000 "
      "the debit is 77,019 against 70,020 for the named receipt's own range (ADR-0047 rule 13 note)",
      rc == [F("2.333"), F("2.334"), F("2.333")] and own_pos[1] == (F("2.333"), F("4.667")) and ret_pos == (F("4.666"), F(7))
      and ret_pos[1] - ret_pos[0] == q_ret and ret_pos != own_pos[1]
      and debit(one, *ret_pos) == debit(one, *own_pos[1]) == 70020 and (debit(co, *ret_pos), debit(co, *own_pos[1])) == (77019, 70020),
      (debit(co, *ret_pos), debit(co, *own_pos[1])))
gr_in = [debit(co, a, b) for a, b in own_pos]                     # receipts credit GR/IR and add stock: 69,990, 70,020, 76,989
stock_out = debit(co, *ret_pos)                                  # interim seed: document value = the GR/IR debit (ADR-0020 rule 5 note)
price_diff = stock_out - debit(co, *ret_pos)
stock_left = sum(gr_in) - stock_out
inv_debit = debit(co, F(0), F(7))                                # the invoice of 3 bags reaches positions 0-7.000
credit_q = debit(co, F(7) - q_ret, F(7))                         # the supplier's credit follows its stock return: 2.334 at the latest invoiced positions
balance = (inv_debit - credit_q) - (sum(gr_in) - stock_out)      # round(V(I)) - round(V(R)) with R = I = 4.666
alt_diff = stock_out - debit(co, *own_pos[1])                    # valuing at the named receipt's own range would leave a price difference
mt = {r["code"]: r for r in read_csv(os.path.join(CAT, "movement-types.csv"))}
check("U71 under the interim seed the value leaving stock on a purchase return is the GR/IR debit of the positions debited: 77,019 "
      "leaves with no price difference, 139,980 stays for 4.666 kg (the value of the positions still held), and after the supplier's "
      "credit GR/IR is 0; the named receipt's value would leave a price difference of 6,999; movement type purchase_return keeps value "
      "source regime and states the seed (ADR-0020 rule 5 note)",
      gr_in == [69990, 70020, 76989] and (stock_out, price_diff, stock_left) == (77019, 0, 139980)
      and stock_left == round_amount(layer_value(co, F("4.666"))) and balance == 0 and alt_diff == 6999
      and mt["purchase_return"]["value_source"] == "regime" and "GR/IR debit of the positions" in mt["purchase_return"]["meaning"],
      (stock_out, stock_left, balance, alt_diff))
def preliminary_price(item, prior_actual=None, area_receipt=None, company_receipt=None, produced=False, estimate=None,
                      list_entries=None, last_invoice=None, manual=None):
    """ADR-0020 rule 11 and its notes: the actual average of N-1, then receipts (area, company); then a produced item takes its
    released estimate, a purchased item its purchase list price (find_price for one inventory unit, in the inventory unit),
    else its last purchase invoice price (net after the document discount / inventory quantity); then a manual price."""
    for p, src in ((prior_actual, "prior_actual"), (area_receipt, "area_receipt"), (company_receipt, "company_receipt")):
        if p is not None:
            return F(p), src
    if produced:
        chain = ((estimate, "cost_estimate"), (manual, "manual"))
    else:
        lp = find_price(list_entries, item, PROD[ITEM[item]][0], 1) if list_entries else None
        li = F(last_invoice[0]) / F(last_invoice[1]) if last_invoice else None
        chain = ((lp, "purchase_list"), (li, "last_purchase_invoice"), (manual, "manual"))
    for p, src in chain:
        if p is not None:
            return F(p), src
    return "preliminary_price_missing", None
both = [("H87", 0, 11000), ("x-carton", 0, 250000)]
ctn_only = [("x-carton", 0, 250000)]
last_inv = (500000, 48)                                          # 2 cartons invoiced at 500,000 net: 48 pieces
ds22 = open(os.path.join(DOCS, "design", "DS-22-09-42-commercial-inventory.sql"), encoding="utf-8").read()
ck_src = ds22.split("CONSTRAINT ck_preliminary_price_price_source CHECK", 1)[1].split("\n", 1)[0]
check("U72 preliminary price of a purchased item before its first receipt: the supplier list price for one piece in the inventory "
      "unit (11,000, not 250,000 / 24); a list priced only per carton gives none, so the last purchase invoice price per inventory "
      "unit applies (500,000 / 48); else a manual price; else preliminary_price_missing; a receipt still comes first; a produced item "
      "keeps its released estimate and never takes a list or invoice price; DS-22 stores both new price sources (ADR-0020 rule 11 note; "
      "ADR-0035 rule 14 note)",
      preliminary_price("I_STD", list_entries=both, last_invoice=last_inv, manual=9000) == (11000, "purchase_list")
      and preliminary_price("I_STD", list_entries=ctn_only, last_invoice=last_inv, manual=9000) == (F(31250, 3), "last_purchase_invoice")
      and preliminary_price("I_STD", list_entries=ctn_only, manual=9000) == (9000, "manual")
      and preliminary_price("I_STD", list_entries=ctn_only)[0] == "preliminary_price_missing"
      and preliminary_price("I_STD", area_receipt=10500, list_entries=both) == (10500, "area_receipt")
      and preliminary_price("I_STD", produced=True, estimate=8000, list_entries=both) == (8000, "cost_estimate")
      and preliminary_price("I_STD", produced=True, list_entries=both, last_invoice=last_inv)[0] == "preliminary_price_missing"
      and "'purchase_list'" in ck_src and "'last_purchase_invoice'" in ck_src)

# ======================================================================= D: database checks (--load)
if "--load" in sys.argv:
    import psycopg  # noqa: E402
    from load_all import load_all  # noqa: E402

    class FractionDumper(psycopg.adapt.Dumper):                  # exact quantities and amounts of the lab model, as numeric
        oid = psycopg.adapters.types["numeric"].oid
        def dump(self, obj):
            return str(D_(obj.numerator) / D_(obj.denominator)).encode()
    psycopg.adapters.register_dumper(F, FractionDumper)
    dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = load_all(dsn, DOCS)
    check("D01 load_all.py loads every DDL file of design/ into one schema", n_tables > 200, n_tables)
    c = conn(); c.autocommit = True
    X = c.execute
    cols = {}
    for t_, col, nullable in X("select table_name, column_name, is_nullable from information_schema.columns where table_schema='nativeflows'").fetchall():
        cols.setdefault(t_, {})[col] = nullable
    BLOCK = ("quantity", "uom_id", "uom_numerator", "uom_denominator", "uom_factor_source", "inventory_quantity")
    REQUIRED = ["quotation_line", "sales_order_line", "delivery_line", "return_from_customer_line", "sales_invoice_line", "sales_return_line",
                "purchase_request_line", "purchase_order_line", "goods_receipt_line", "return_to_supplier_line", "service_receipt_line",
                "purchase_return_line", "production_issue_line", "production_receipt_line", "operation_progress_component", "replenishment_request_line"]
    OPTIONAL = ["purchase_invoice_line", "credit_note_line", "purchase_credit_note_line"]
    miss = [(t_, b) for t_ in REQUIRED + OPTIONAL for b in BLOCK if b not in cols.get(t_, {})]
    nulls = [(t_, b) for t_ in REQUIRED for b in BLOCK if cols.get(t_, {}).get(b) != "NO"]
    check(f"D02 the line unit block exists on all {len(REQUIRED) + len(OPTIONAL)} quantity line tables, NOT NULL on the {len(REQUIRED)} whose quantity is required",
          not miss and not nulls, (miss + nulls)[:5])
    found = [t_ for t_, cc in cols.items() if "uom_id" in cc and "inventory_quantity" in cc]
    check("D03 every table with uom_id and inventory_quantity carries the snapshot (discovery over the whole schema)",
          sorted(found) == sorted(REQUIRED + OPTIONAL) and all("uom_factor_source" in cols[t_] for t_ in found), sorted(set(found) ^ set(REQUIRED + OPTIONAL)))
    pu = {"id", "item_id", "inventory_uom_id", "factor_source", "is_exact", "contains_uom_id", "contains_quantity", "is_counting_unit",
          "is_default_pick_unit", "is_active", "retired_at", "recorded_at"}
    defaults = X("""select table_name, column_name from information_schema.columns where table_schema='nativeflows' and column_default is not null
                    and table_name in ('bill_of_materials_component', 'bill_of_materials_output') and column_name like 'uom_%%'""").fetchall()
    check("D04 the master data and planning columns: product_uom rebuilt, uom.name, uom_conversion.id and is_active, uom_alias, supplier_item.order_uom_id NOT NULL, the planned order's order unit, bill of materials snapshots without defaults and issue_multiple",
          pu <= set(cols["product_uom"]) and cols["uom"].get("name") == "NO" and {"id", "is_active"} <= set(cols["uom_conversion"]) and "uom_alias" in cols
          and cols["supplier_item"].get("order_uom_id") == "NO" and {"order_quantity", "order_uom_id", "uom_numerator"} <= set(cols["planned_order"])
          and "issue_multiple" in cols["bill_of_materials_component"] and "numerator" not in cols["bill_of_materials_component"] and not defaults
          and "id" in cols["item_barcode"],
          sorted(pu - set(cols["product_uom"])) or defaults)

    # ---- the core catalogs into uom and uom_conversion
    U = {}
    with c.transaction():
        for code, (kind, dec) in UNITS.items():
            if code in CORE:
                U[code] = uuid.uuid5(NS, f"uom:{code}")
                name = next(r["name"] for r in read_csv(os.path.join(CAT, "units.csv")) if r["code"] == code)
                X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,%s,%s)", (U[code], code, name, kind, dec))
        for r in CONV_ROWS:
            X("insert into uom_conversion (id, from_uom_id, to_uom_id, numerator, denominator) values (%s,%s,%s,%s,%s)",
              (uuid.uuid5(NS, f"uom_conversion:{r['from_code']}:{r['to_code']}"), U[r["from_code"]], U[r["to_code"]], r["numerator"], r["denominator"]))
    check("D05 the core catalogs load: 15 units and 12 conversions with uuid5 ids (ADR-0006 rule 4)",
          X("select (select count(*) from uom), (select count(*) from uom_conversion)").fetchone() == (15, 12))

    I = {k: new() for k in ["user", "co", "ig", "vc", "itg", "w", "z", "b", "supp", "p_pcs", "i_pcs", "p_kg", "i_kg", "i_big", "p_ser", "i_ser",
                            "pu_ct", "pu_bag", "pu_pack", "pu_big", "pu_kg4", "pu_kg5"]}
    t = str(I["co"])[-8:]
    B = '{"kind": "company_decision"}'
    X("insert into currency (code, minor_unit) values ('VND', 0) on conflict do nothing")
    X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I["user"], "u17" + t))
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','warehouse',%s,'vi')", (I["co"], "C17-" + t, I["user"]))
    X("select set_config('nativeflows.company_id', %s, false)", (str(I["co"]),))
    for code, name in (("x-carton", "Carton"), ("x-bag", "Bag"), ("x-pack", "Pack"), ("x-pallet", "Pallet")):
        U[code] = new()
        X("insert into uom (id, company_id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,%s,'count',0)", (U[code], I["co"], code, name))
    X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,'g','G',%s)", (I["ig"], I["co"], B))
    X("insert into valuation_class (id, company_id, code, name, basis) values (%s,%s,'v','V',%s)", (I["vc"], I["co"], B))
    X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,'s','S',%s)", (I["itg"], I["co"], B))
    def product(pk, ik, code, inv, pur, tracking="none"):
        X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
             item_tax_group_id, tracking) values (%s,%s,%s,%s,'stock',%s,%s,%s,%s,%s,%s,%s)""",
          (I[pk], I["co"], code, code, I["ig"], I["vc"], U[inv], U[pur], U[inv], I["itg"], tracking))
        X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,%s)", (I[ik], I["co"], I[pk], code))
    product("p_pcs", "i_pcs", "PCS", "H87", "x-carton")
    product("p_kg", "i_kg", "BAGGED", "KGM", "KGM")
    product("p_ser", "i_ser", "SER", "H87", "H87", "serial")
    X("insert into item (id, company_id, product_id, code, variant_key) values (%s,%s,%s,'PCS-BIG',%s)", (I["i_big"], I["co"], I["p_pcs"], [new()]))   # a second variant
    def pu_row(cx, pid, prod, inv, unit, n, d, exact, **o):
        v = dict(id=pid, company_id=I["co"], product_id=I[prod], inventory_uom_id=U[inv], uom_id=U[unit], numerator=n, denominator=d, is_exact=exact)
        v.update(o)
        cx.execute(f"insert into product_uom ({', '.join(v)}) values ({', '.join(['%s'] * len(v))})", list(v.values()))
    pu_row(c, I["pu_ct"], "p_pcs", "H87", "x-carton", 24, 1, True, is_counting_unit=True)
    pu_row(c, I["pu_pack"], "p_pcs", "H87", "x-pack", 6, 1, True, is_default_pick_unit=True)
    pu_row(c, new(), "p_pcs", "H87", "x-pallet", 960, 1, True, factor_source="packaging", contains_uom_id=U["x-carton"], contains_quantity=40)
    pu_row(c, I["pu_bag"], "p_kg", "KGM", "x-bag", 7, 3, False)
    with c.transaction():                                         # a warehouse with its default zone and bin (deferred keys)
        X("insert into warehouse (id, company_id, code, name, kind, default_bin_id) values (%s,%s,'W1','W1','physical',%s)", (I["w"], I["co"], I["b"]))
        X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'DEFAULT','Default')", (I["z"], I["co"], I["w"]))
        X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEFAULT','W1-DEFAULT','storage')", (I["b"], I["co"], I["w"], I["z"]))
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,'SUPP','Supplier (sample)','organization','VN')", (I["supp"], I["co"]))
    X("insert into partner_role (company_id, partner_id, role) values (%s,%s,'supplier')", (I["co"], I["supp"]))

    def ins(cx, table, **v):
        cx.execute(f"insert into {table} ({', '.join(v)}) values ({', '.join(['%s'] * len(v))})", list(v.values()))
        return v.get("id")
    def doc(cx, dtype, state="posted"):
        d = new()
        ins(cx, "document", id=d, company_id=I["co"], document_type=dtype, state=state, version=1, created_by_user_id=I["user"], partner_id=I["supp"],
            document_date="2026-11-15", recorded_at="2026-11-15T08:00:00Z", posted_at="2026-11-15T08:00:00Z" if state == "posted" else None)
        return d
    SNAP = dict(partner_name="Supplier (sample)")
    def snap(n, d, src):
        return dict(uom_numerator=n, uom_denominator=d, uom_factor_source=src)

    def p2p(unit, src, n, d, order_qty, order_inv, unit_price, line_amount, receipts, invoice_qty, invoice_inv, item="i_pcs"):
        """A purchase order line, receipts (entered quantity, unit, snapshot, inventory quantity), an invoice; GR/IR postings."""
        price = F(line_amount) / F(order_inv)
        with c.transaction():
            d_po = doc(c, "purchase_order", "approved")
            ins(c, "purchase_order", id=d_po, company_id=I["co"], partner_id=I["supp"], currency="VND", document_date="2026-11-15", **SNAP)
            pol = ins(c, "purchase_order_line", id=new(), company_id=I["co"], purchase_order_id=d_po, line_number=1, item_id=I[item], quantity=order_qty,
                      uom_id=U[unit], inventory_quantity=order_inv, warehouse_id=I["w"], requested_date="2026-11-20", net_unit_price=unit_price,
                      line_amount=line_amount, **snap(n, d, src))
            ins(c, "purchase_order_line_gr_ir_layer", id=new(), company_id=I["co"], purchase_order_line_id=pol, from_position=0, to_position=order_inv,
                price_numerator=price.numerator, price_denominator=price.denominator)
        R = F(0)
        for rq, ru, (rn, rd, rs), rinv in receipts:
            amount = round_amount(price * (R + F(rinv))) - round_amount(price * R)
            with c.transaction():
                d_gr = doc(c, "goods_receipt")
                ins(c, "goods_receipt", id=d_gr, company_id=I["co"], partner_id=I["supp"], document_date="2026-11-15", posting_date="2026-11-15", **SNAP)
                ins(c, "goods_receipt_line", id=new(), company_id=I["co"], goods_receipt_id=d_gr, line_number=1, purchase_order_line_id=pol, item_id=I[item],
                    quantity=rq, uom_id=U[ru], inventory_quantity=rinv, warehouse_id=I["w"], gr_ir_position_from=R, gr_ir_position_to=R + F(rinv), **snap(rn, rd, rs))
                ins(c, "purchase_order_line_gr_ir_posting", id=new(), company_id=I["co"], purchase_order_line_id=pol, document_id=d_gr, line_number=1,
                    posting_kind="receipt", from_position=R, to_position=R + F(rinv), gr_ir_amount=-amount)
            R += F(rinv)
        with c.transaction():
            d_pi = doc(c, "purchase_invoice")
            ins(c, "purchase_invoice", id=d_pi, company_id=I["co"], partner_id=I["supp"], partner_reference="INV-" + str(d_pi)[-6:], supplier_invoice_date="2026-11-15",
                document_date="2026-11-15", posting_date="2026-11-15", currency="VND", **SNAP)
            ins(c, "purchase_invoice_line", id=new(), company_id=I["co"], purchase_invoice_id=d_pi, line_number=1, line_kind="goods", purchase_order_line_id=pol,
                item_id=I[item], quantity=invoice_qty, uom_id=U[unit], inventory_quantity=invoice_inv, unit_price=unit_price, line_amount=line_amount,
                is_price_copied=True, **snap(n, d, src))
            ins(c, "purchase_order_line_gr_ir_posting", id=new(), company_id=I["co"], purchase_order_line_id=pol, document_id=d_pi, line_number=1,
                posting_kind="invoice", from_position=0, to_position=invoice_inv, gr_ir_amount=round_amount(price * F(invoice_inv)))
        return pol, d_po

    POL_CT, D_PO_CT = p2p("x-carton", "product", 24, 1, 10, 240, 230000, 2300000,
                          [(100, "H87", (1, 1, "identity"), 100), (140, "H87", (1, 1, "identity"), 140)], 10, 240)
    sums = X("""select sum(gr_ir_amount) filter (where posting_kind = 'receipt'), sum(gr_ir_amount) filter (where posting_kind = 'invoice'), sum(gr_ir_amount)
                from purchase_order_line_gr_ir_posting where purchase_order_line_id=%s""", (POL_CT,)).fetchone()
    check("D06 a purchase order of 10 cartons, receipts of 100 and 140 pieces and an invoice of 10 cartons: GR/IR credits 2,300,000, debits 2,300,000 and is 0",
          tuple(int(x) for x in sums) == (-2300000, 2300000, 0), sums)
    rec = X("select sum(inventory_quantity), array_agg(uom_factor_source order by gr_ir_position_from) from goods_receipt_line where purchase_order_line_id=%s", (POL_CT,)).fetchone()
    snap_ct = X("select quantity, uom_numerator, uom_denominator, uom_factor_source, inventory_quantity from purchase_order_line where id=%s", (POL_CT,)).fetchone()
    check("D07 the order line stores its snapshot (10 cartons, 24/1, product, 240) and the receipts in pieces sum to 240 by identity",
          (int(snap_ct[0]), snap_ct[1], snap_ct[2], snap_ct[3], int(snap_ct[4])) == (10, 24, 1, "product", 240) and int(rec[0]) == 240 and rec[1] == ["identity", "identity"],
          (snap_ct, rec))
    bag_receipts, cum_, post_ = [], F(0), F(0)
    for _ in range(3):
        pinv = convert_part(f_bag, cum_, post_, 1, 3); bag_receipts.append((1, "x-bag", (7, 3, "product"), pinv)); cum_ += 1; post_ += pinv
    POL_BAG, _ = p2p("x-bag", "product", 7, 3, 3, F(7), 70000, 210000, bag_receipts, 3, F(7), item="i_kg")
    bag = X("""select array_agg(g.inventory_quantity order by g.gr_ir_position_from)::text, sum(g.inventory_quantity),
                      (select sum(gr_ir_amount) from purchase_order_line_gr_ir_posting where purchase_order_line_id=%s)
               from goods_receipt_line g where g.purchase_order_line_id=%s""", (POL_BAG, POL_BAG)).fetchone()
    check("D08 a bag order (3 bags = 7.000 kg) with three cumulative receipts of 1 bag: 2.333, 2.334, 2.333 are accepted, sum to 7.000, and GR/IR is 0",
          bag[0] == "{2.333000,2.334000,2.333000}" and F(str(bag[1])) == 7 and int(bag[2]) == 0, bag)

    def X_bad(name, match, fn):
        def run(cx):
            cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, True, match)
    def X_good(name, fn):
        def run(cx):
            cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, False)
    X_bad("D09 a product unit's factor is positive", "ck_product_uom_numerator",
          lambda cx: pu_row(cx, new(), "p_pcs", "H87", "x-bag", 0, 1, True))
    X_bad("D10 a product unit is never the product's inventory unit (held through the key to the product)", "ck_product_uom_not_inventory",
          lambda cx: pu_row(cx, new(), "p_pcs", "H87", "H87", 1, 1, True))
    X_bad("D11 ... and its inventory unit is the product's own (the key refuses another)", "fk_product_uom_inventory_unit",
          lambda cx: pu_row(cx, new(), "p_pcs", "KGM", "x-bag", 1, 1, True))
    X_bad("D12 an item-level row names an item of the same product", "fk_product_uom_item_product",
          lambda cx: pu_row(cx, new(), "p_pcs", "H87", "x-bag", 2, 1, True, item_id=I["i_kg"]))
    X_bad("D13 one active row per product, item and unit: a second active product-level carton is refused", "ux_product_uom_active_unit",
          lambda cx: pu_row(cx, new(), "p_pcs", "H87", "x-carton", 20, 1, True))
    X_good("D14 an item-level carton of 12 beside the product's carton of 24",
           lambda cx: pu_row(cx, new(), "p_pcs", "H87", "x-carton", 12, 1, True, item_id=I["i_big"]))
    X_bad("D15 the packaging shape: contains_quantity is a whole number above 1", "ck_product_uom_packaging",
          lambda cx: pu_row(cx, new(), "p_pcs", "H87", "x-bag", 36, 1, True, contains_uom_id=U["x-carton"], contains_quantity=1.5))
    X_bad("D16 ... a factor set from packaging names its contained unit", "ck_product_uom_packaging",
          lambda cx: pu_row(cx, new(), "p_pcs", "H87", "x-bag", 48, 1, True, factor_source="packaging"))
    X_bad("D17 a retired row carries retired_at, and only a retired row does", "ck_product_uom_retired",
          lambda cx: cx.execute("update product_uom set is_active=false where id=%s", (I["pu_ct"],)))
    X_bad("D18 a retired unit cannot be the default pick unit (the one retirement rule a check can hold)", "ck_product_uom_retired",
          lambda cx: cx.execute("update product_uom set is_active=false, retired_at=now() where id=%s", (I["pu_pack"],)))
    X_bad("D19 at most one default pick unit per product", "ux_product_uom_default_pick_unit",
          lambda cx: cx.execute("update product_uom set is_default_pick_unit=true where id=%s", (I["pu_ct"],)))
    X_bad("D20 a global pair is stored once, from the larger unit: grams to kilograms at 1/1000 is refused", "ck_uom_conversion_direction",
          lambda cx: cx.execute("insert into uom_conversion (id, from_uom_id, to_uom_id, numerator, denominator) values (%s,%s,%s,1,1000)", (new(), U["GRM"], U["KGM"])))
    X_bad("D21 ... and a pair already stored cannot be stored again in either direction", "ux_uom_conversion_pair",
          lambda cx: cx.execute("insert into uom_conversion (id, from_uom_id, to_uom_id, numerator, denominator) values (%s,%s,%s,1,1)", (new(), U["GRM"], U["KGM"])))
    pol_line = lambda **o: (lambda cx: ins(cx, "purchase_order_line", **dict(dict(id=new(), company_id=I["co"], purchase_order_id=D_PO_CT, line_number=9, item_id=I["i_pcs"],
                                             quantity=1, uom_id=U["x-carton"], inventory_quantity=24, warehouse_id=I["w"], requested_date="2026-11-20",
                                             uom_numerator=24, uom_denominator=1, uom_factor_source="product"), **o)))
    X_good("D22 a carton line with its snapshot 24/1 and 24 pieces is accepted", pol_line())
    X_good("D44 the gross-error bound is two inventory units: 1 carton (24 pieces) stored as 26 is accepted",
           pol_line(line_number=11, inventory_quantity=26))
    X_bad("D45 ... and stored as 27 is refused", "ck_purchase_order_line_uom_quantity", pol_line(line_number=12, inventory_quantity=27))
    X_bad("D23 a carton line stored as one piece (inventory quantity = quantity under factor 24) is refused", "ck_purchase_order_line_uom_quantity",
          pol_line(inventory_quantity=1))
    X_bad("D24 the identity snapshot is 1/1 only", "ck_purchase_order_line_uom_factor", pol_line(uom_factor_source="identity"))
    X_bad("D25 a snapshot factor is positive", "ck_purchase_order_line_uom_factor", pol_line(uom_numerator=0))
    X_bad("D26 a snapshot source is identity, item, product or global", "ck_purchase_order_line_uom_factor", pol_line(uom_factor_source="supplier"))
    X_bad("D27 the snapshot is required on a line (no default factor)", "uom_numerator", pol_line(uom_numerator=None))
    X_good("D28 the cumulative part 2.334 of a bag (7/3 kg) lies within the gross-error bound and is accepted",
           pol_line(line_number=7, item_id=I["i_kg"], uom_id=U["x-bag"], quantity=1, inventory_quantity=D_("2.334"), uom_numerator=7, uom_denominator=3))
    X_bad("D29 a purchase invoice quantity line carries its snapshot (all six fields or none)", "ck_purchase_invoice_line_uom_snapshot",
          lambda cx: ins(cx, "purchase_invoice_line", id=new(), company_id=I["co"],
                         purchase_invoice_id=X("select id from purchase_invoice limit 1").fetchone()[0], line_number=9, line_kind="goods",
                         purchase_order_line_id=POL_CT, item_id=I["i_pcs"], quantity=1, uom_id=U["x-carton"], inventory_quantity=24, line_amount=1))
    X_bad("D30 a unit alias is unique per company by its normalized text", "uq_uom_alias_normalized",
          lambda cx: [ins(cx, "uom_alias", id=new(), company_id=I["co"], alias=a, normalized_alias="thung", uom_id=U["x-carton"]) for a in ("Thùng", "THUNG")])
    X_bad("D31 the normalized text is stored normalized (lower case, no spaces)", "ck_uom_alias_normalized",
          lambda cx: ins(cx, "uom_alias", id=new(), company_id=I["co"], alias="Thùng", normalized_alias="Thùng X", uom_id=U["x-carton"]))
    X_bad("D32 a supplier item names its order unit", "order_uom_id",
          lambda cx: ins(cx, "supplier_item", id=new(), company_id=I["co"], supplier_partner_id=I["supp"], item_id=I["i_pcs"], supplier_processing_days=1,
                         transit_days=0, start_date="2026-01-01", recorded_at="2026-11-15T00:00:00Z"))
    X_good("D33 a supplier item with order unit carton, minimum 2 and multiple 1 (in cartons)",
           lambda cx: ins(cx, "supplier_item", id=new(), company_id=I["co"], supplier_partner_id=I["supp"], item_id=I["i_pcs"], order_uom_id=U["x-carton"],
                          minimum_order_quantity=2, order_multiple=1, supplier_processing_days=1, transit_days=0, start_date="2026-01-01", recorded_at="2026-11-15T00:00:00Z"))
    # INV-603: retire the carton, then a follow-on receipt in cartons (allowed) and a new order line in cartons (a violation)
    X("update product_uom set is_active=false, retired_at=now() where id=%s", (I["pu_ct"],))
    with c.transaction():
        d_gr = doc(c, "goods_receipt")
        ins(c, "goods_receipt", id=d_gr, company_id=I["co"], partner_id=I["supp"], document_date="2026-11-15", posting_date="2026-11-15", **SNAP)
        ins(c, "goods_receipt_line", id=new(), company_id=I["co"], goods_receipt_id=d_gr, line_number=1, purchase_order_line_id=POL_CT, item_id=I["i_pcs"],
            quantity=1, uom_id=U["x-carton"], inventory_quantity=24, warehouse_id=I["w"], gr_ir_position_from=240, gr_ir_position_to=264, **snap(24, 1, "product"))
    late = ins(c, "purchase_order_line", id=new(), company_id=I["co"], purchase_order_id=D_PO_CT, line_number=8, item_id=I["i_pcs"], quantity=2,
               uom_id=U["x-carton"], inventory_quantity=48, warehouse_id=I["w"], requested_date="2026-11-20", **snap(24, 1, "product"))
    SOURCE = {"sales_order_line": ("quotation_line_id", "quotation_line"), "delivery_line": ("sales_order_line_id", "sales_order_line"),
              "return_from_customer_line": ("delivery_line_id", "delivery_line"), "sales_invoice_line": ("delivery_line_id", "delivery_line"),
              "sales_return_line": ("return_from_customer_line_id", "return_from_customer_line"), "credit_note_line": ("correction_of_line_id", "sales_invoice_line"),
              "purchase_order_line": ("purchase_request_line_id", "purchase_request_line"), "goods_receipt_line": ("purchase_order_line_id", "purchase_order_line"),
              "return_to_supplier_line": ("goods_receipt_line_id", "goods_receipt_line"), "service_receipt_line": ("purchase_order_line_id", "purchase_order_line"),
              "purchase_invoice_line": ("purchase_order_line_id", "purchase_order_line"), "purchase_return_line": ("return_to_supplier_line_id", "return_to_supplier_line"),
              "purchase_credit_note_line": ("correction_of_line_id", "purchase_invoice_line")}
    parts_sql, covered = [], []
    for t_ in REQUIRED + OPTIONAL:
        col, src = SOURCE.get(t_, (None, None))
        item_expr = "l.item_id" if "item_id" in cols[t_] else "s.item_id"   # a service receipt line takes its item from its order line
        if "recorded_at" not in cols[t_] or (item_expr == "s.item_id" and not (col and col in cols[t_])):
            continue
        if col and col in cols[t_]:
            join, sel = f"left join {src} s on s.id = l.{col}", "s.uom_id, s.uom_numerator, s.uom_denominator"
        else:
            join, sel = "", "null::uuid, null::bigint, null::bigint"
        idcol = "id" if "id" in cols[t_] else "replenishment_request_id"   # replenishment request lines are keyed by request and line number
        parts_sql.append(f"select '{t_}' as kind, l.{idcol}, {item_expr}, l.uom_id, l.uom_factor_source as src, l.recorded_at, l.uom_numerator as n, "
                         f"l.uom_denominator as d, {sel} from {t_} l {join}")
        covered.append(t_)
    # INV-603 (ADR-0056 rules 5, 6): the row in force at the line's time, at the level the line names; an item level with rows hides the product level.
    INV603 = "with lines (kind, id, item_id, uom_id, src, recorded_at, n, d, s_uom, s_n, s_d) as (" + " union all ".join(parts_sql) + """)
      select l.kind, l.id from lines l join item i on i.id = l.item_id
        left join lateral (
          select u.numerator, u.denominator, case when u.item_id is null then 'product' else 'item' end as lvl
            from product_uom u
           where u.product_id = i.product_id and u.uom_id = l.uom_id and u.recorded_at <= l.recorded_at
             and (u.retired_at is null or u.retired_at > l.recorded_at)
             and (u.item_id = l.item_id or (u.item_id is null and not exists (
                   select 1 from product_uom x where x.product_id = i.product_id and x.uom_id = l.uom_id and x.item_id = l.item_id and x.recorded_at <= l.recorded_at)))
           order by (u.item_id is null) limit 1) r on true
       where l.src in ('item', 'product') and l.quantity_placeholder
         and not coalesce(l.s_uom = l.uom_id and l.s_n = l.n and l.s_d = l.d, false)
         and (r.lvl is null or r.lvl <> l.src or r.numerator * l.d <> r.denominator * l.n)
       order by l.recorded_at""".replace(" and l.quantity_placeholder", "")
    hits = X(INV603).fetchall()
    check(f"D34 a line naming a retired unit is accepted by the database (no check can hold it) and INV-603, over all {len(covered)} line tables, finds exactly the new order line; the follow-on receipt in the order's unit and snapshot is not a new use",
          [h[1] for h in hits] == [late] and len(covered) == len(REQUIRED + OPTIONAL), (hits, len(covered)))
    # Retire and replace on the same unit (ADR-0056 rule 5): 1 kg of a product kept in pieces was 4 pieces and becomes 5.
    pu_row(c, I["pu_kg4"], "p_pcs", "H87", "KGM", 4, 1, True)
    pol_kg = ins(c, "purchase_order_line", id=new(), company_id=I["co"], purchase_order_id=D_PO_CT, line_number=6, item_id=I["i_pcs"], quantity=2,
                 uom_id=U["KGM"], inventory_quantity=8, warehouse_id=I["w"], requested_date="2026-11-20", **snap(4, 1, "product"))
    with c.transaction():                                         # one command: retire the row of 4 and add the row of 5 for the same unit
        X("update product_uom set is_active=false, retired_at=now() where id=%s", (I["pu_kg4"],))
        pu_row(c, I["pu_kg5"], "p_pcs", "H87", "KGM", 5, 1, True)
    rows_kg = X("select numerator, denominator, is_active from product_uom where product_id=%s and item_id is null and uom_id=%s order by is_active",
                (I["p_pcs"], U["KGM"])).fetchall()
    check("D37 retire and replace keeps the unit code: the kg row of 4 is retired and a kg row of 5 is active beside it (uniqueness among active rows only)",
          rows_kg == [(4, 1, False), (5, 1, True)], rows_kg)
    X_bad("D38 ... and a second active kg row is refused", "ux_product_uom_active_unit",
          lambda cx: pu_row(cx, new(), "p_pcs", "H87", "KGM", 6, 1, True))
    active = X("select numerator, denominator from product_uom where product_id=%s and item_id is null and uom_id=%s and is_active", (I["p_pcs"], U["KGM"])).fetchone()
    new_kg = ins(c, "purchase_order_line", id=new(), company_id=I["co"], purchase_order_id=D_PO_CT, line_number=5, item_id=I["i_pcs"], quantity=2,
                 uom_id=U["KGM"], inventory_quantity=2 * F(active[0], active[1]), warehouse_id=I["w"], requested_date="2026-11-20",
                 **snap(active[0], active[1], "product"))
    with c.transaction():                                         # a follow-on receipt of the old order line keeps the old snapshot
        d_gr2 = doc(c, "goods_receipt")
        ins(c, "goods_receipt", id=d_gr2, company_id=I["co"], partner_id=I["supp"], document_date="2026-11-15", posting_date="2026-11-15", **SNAP)
        ins(c, "goods_receipt_line", id=new(), company_id=I["co"], goods_receipt_id=d_gr2, line_number=1, purchase_order_line_id=pol_kg, item_id=I["i_pcs"],
            quantity=2, uom_id=U["KGM"], inventory_quantity=8, warehouse_id=I["w"], gr_ir_position_from=0, gr_ir_position_to=8, **snap(4, 1, "product"))
    stale = ins(c, "purchase_order_line", id=new(), company_id=I["co"], purchase_order_id=D_PO_CT, line_number=4, item_id=I["i_pcs"], quantity=2,
                uom_id=U["KGM"], inventory_quantity=8, warehouse_id=I["w"], requested_date="2026-11-20", **snap(4, 1, "product"))
    snaps = dict(X("select id, array[quantity, inventory_quantity, uom_numerator, uom_denominator]::text from purchase_order_line where id = any(%s)",
                   ([pol_kg, new_kg],)).fetchall())
    check("D39 the old line keeps its snapshot (2 kg = 8 pieces at 4/1) and a new line resolves to the active row (2 kg = 10 pieces at 5/1)",
          (snaps[pol_kg], snaps[new_kg]) == ("{2.000000,8.000000,4,1}", "{2.000000,10.000000,5,1}"), snaps)
    big_wrong = ins(c, "purchase_order_line", id=new(), company_id=I["co"], purchase_order_id=D_PO_CT, line_number=3, item_id=I["i_big"], quantity=1,
                    uom_id=U["x-carton"], inventory_quantity=24, warehouse_id=I["w"], requested_date="2026-11-20", **snap(24, 1, "product"))
    ins(c, "purchase_order_line", id=new(), company_id=I["co"], purchase_order_id=D_PO_CT, line_number=2, item_id=I["i_big"], quantity=1,
        uom_id=U["x-carton"], inventory_quantity=12, warehouse_id=I["w"], requested_date="2026-11-20", **snap(12, 1, "item"))
    hits2 = [h[1] for h in X(INV603).fetchall()]
    check("D40 after the replacement INV-603 finds the carton line, the new kg line at the retired factor 4/1, and a big-variant line at the product's 24 although its own row of 12 is in force; the new kg line at 5/1, the big-variant line at 12 (item) and the follow-on receipt at the old order line's 4/1 are not violations",
          sorted(map(str, hits2)) == sorted(map(str, [late, stale, big_wrong])), hits2)
    X_good("D41 a product unit of a catalog-convertible unit at the catalog's factor: grams of a product kept in kg, 1/1000, factor_source catalog",
           lambda cx: pu_row(cx, new(), "p_kg", "KGM", "GRM", 1, 1000, True, factor_source="catalog"))
    X_good("D42 the GR/IR posting kind rounding_clearing is accepted in both directions (ADR-0056 rule 10)",
           lambda cx: [ins(cx, "purchase_order_line_gr_ir_posting", id=new(), company_id=I["co"], purchase_order_line_id=POL_BAG, document_id=D_PO_CT, line_number=1,
                           posting_kind="rounding_clearing", from_position=F("6.999"), to_position=F(7), gr_ir_amount=a_) for a_ in (-30, 30)])
    X_bad("D43 an item barcode is unique per company, beside its surrogate id", "uq_item_barcode_barcode",
          lambda cx: [ins(cx, "item_barcode", id=new(), company_id=I["co"], item_id=I["i_pcs"], uom_id=U["x-carton"], barcode="08930000000019") for _ in range(2)])
    X_bad("D35 a credit note quantity line carries its unit and snapshot", "ck_credit_note_line_uom_snapshot",
          lambda cx: ins(cx, "credit_note_line", id=new(), company_id=I["co"], credit_note_id=new(), line_number=1, item_id=I["i_pcs"], quantity=1,
                         inventory_quantity=1, net_unit_price=1, line_amount=1))
    X_bad("D36 a purchase return line carries its entered quantity, unit and snapshot", "null value in column",
          lambda cx: ins(cx, "purchase_return_line", id=new(), company_id=I["co"], purchase_return_id=new(), line_number=1, return_to_supplier_line_id=new(),
                         item_id=I["i_pcs"], inventory_quantity=1, line_amount=1))
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
