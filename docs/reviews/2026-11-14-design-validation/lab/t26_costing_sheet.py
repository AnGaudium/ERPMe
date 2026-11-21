"""Scenario: the costing sheet and cost component structure (ADR-0072). Not product code.

Run: python t26_costing_sheet.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs);
  NATIVEFLOWS_LAB_DIR points at lab.py and load_all.py (default: this file's directory).

M: the detail mapping (rule 3): activity type, then item group, then valuation class, then account, then the posting
   component's default; it never leaves the line's posting component.
E: the sheet's evaluation (rules 6, 8): base rows over the estimate's own priced lines, percent of a base and of a subtotal,
   amounts per activity unit and per output unit, subtotals that skip nested subtotals, surcharge lines in their details
   and credited cost centers, lines summing to the total, lower levels only when the base row includes them, selling
   rows only in selling costing.
R: rate selection (rule 7): effective dates, then the most specific condition set (site, item group, valuation class);
   a missing rate is a gap left out of the total, never zero; a stored zero rate is no gap.
U: roll-up (rules 3, 4): on random estimates, details sum exactly to the four posting components.
J: the job's split into production_order_period_cost_detail (rule 4) on random two-period orders: every column sums
   exactly to its parent, each row balances, the second period opens with the first's closing split, unmapped cost lands
   in the default detail, and a zero available amount sends closing and residual to the default detail.
P: the projected final cost's flags (rule 14): provisional until complete and settled; a completed order's unsettled
   period without receipts is projected residual.
With --load (the schema of load_all.py): overhead_surcharge gone and cost_estimate_line.cost_center_id settled; one
default detail per posting component; mappings as a function within one posting component; the row shapes, the base
members, rates by kind with no overlap; estimate lines held to their detail's posting component; a costing_rate_missing
gap blocks release, a released snapshot is frozen; the period cost detail table's keys and balance.
Not covered: commands and their checks (costing_sheet_row_invalid, cost_component_detail_limit), the costing job itself
(costing_lab2.py), the queries' reading of other modules.
"""
import os, random, sys
from datetime import date
from decimal import Decimal as D, ROUND_HALF_UP, ROUND_FLOOR
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import RESULTS, conn, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
UNIT = D("0.01")
COMPONENTS = ("material", "labor", "overhead", "other")


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def round_amount(x):
    return D(x).quantize(UNIT, rounding=ROUND_HALF_UP)


# ======================================================================= reference functions
# Detailed components: code -> (posting component, sequence, is_default)
DETAILS = {
    "material": ("material", 10, True), "raw_material": ("material", 11, False), "packaging": ("material", 12, False),
    "labor": ("labor", 20, True), "direct_labor": ("labor", 21, False),
    "overhead": ("overhead", 30, True), "machine": ("overhead", 31, False), "energy": ("overhead", 32, False),
    "depreciation": ("overhead", 33, False), "material_handling": ("overhead", 34, False),
    "other": ("other", 40, True), "subcontracting": ("other", 41, False),
}
DEFAULT = {c: d for d, (c, _, is_def) in DETAILS.items() if is_def}
# Mapping rows: (posting component, source kind, source value) -> detail
MAPPING = {
    ("material", "item_group", "RAW"): "raw_material", ("material", "item_group", "PACK"): "packaging",
    ("material", "valuation_class", "VC_PACK"): "packaging",
    ("labor", "activity_type", "LABOR_HR"): "direct_labor", ("labor", "account", "WAGES"): "direct_labor",
    ("overhead", "activity_type", "MACHINE_HR"): "machine", ("overhead", "account", "ENERGY"): "energy",
    ("overhead", "account", "DEPRECIATION"): "depreciation",
    ("other", "account", "SUBCON"): "subcontracting",
}


def map_detail(component, activity_type=None, item_group=None, valuation_class=None, account=None):
    """production.map_cost_component_detail (rule 3): first hit in a fixed order, only among the component's details."""
    for kind, value in (("activity_type", activity_type), ("item_group", item_group), ("valuation_class", valuation_class), ("account", account)):
        if value is not None and (component, kind, value) in MAPPING:
            return MAPPING[(component, kind, value)]
    return DEFAULT[component]


def select_rate(rates, row_number, ctx):
    """Rule 7: valid on the date, every stated condition matching, the most specific set by fixed precedence."""
    cands = [r for r in rates if r["row"] == row_number and r["from"] <= ctx["date"] and (r["to"] is None or ctx["date"] <= r["to"])
             and all(r.get(k) is None or r.get(k) == ctx.get(k) for k in ("site", "item_group", "valuation_class"))]
    if not cands:
        return None
    spec = lambda r: (r.get("site") is not None) * 4 + (r.get("item_group") is not None) * 2 + (r.get("valuation_class") is not None)
    cands.sort(key=spec, reverse=True)
    assert len(cands) == 1 or spec(cands[0]) != spec(cands[1]), "an overlap the exclusion constraint forbids"
    return cands[0]["value"]


def evaluate(rows, lines, rates, purpose, ctx, lot_quantity):
    """production.evaluate_costing_sheet (rule 8). lines: priced lines (component, detail, amount, level, activity, quantity).
    Returns (surcharge lines, snapshot rows, gaps, values by row)."""
    kinds = {r["n"]: r["kind"] for r in rows}
    values, out, snap, gaps = {}, [], [], []
    for r in sorted(rows, key=lambda r: r["n"]):
        if purpose == "production" and r.get("usage", "production") == "selling":
            continue
        if r["kind"] == "base":
            members = r["members"]
            v = sum((l["amount"] for l in lines if (l["level"] == 0 or r.get("lower")) and (l["component"] in members or l["detail"] in members)), D(0))
            values[r["n"]] = v
            snap.append({"n": r["n"], "kind": "base", "amount": v})
        elif r["kind"] == "subtotal":
            v = sum((values[n] for n in values if r["from"] <= n <= r["to"] and kinds[n] != "subtotal"), D(0))
            values[r["n"]] = v
            snap.append({"n": r["n"], "kind": "subtotal", "amount": v})
        else:
            rate = select_rate(rates, r["n"], ctx)
            if rate is None:
                gaps.append(("costing_rate_missing", r["n"]))
                continue
            if r["skind"] == "percent":
                base = values.get(r["base_row"], D(0))
                v = round_amount(base * rate / 100)
            elif r["skind"] == "per_output_unit":
                base = lot_quantity
                v = round_amount(base * rate)
            else:
                base = sum((l["quantity"] for l in lines if l["level"] == 0 and l.get("activity") == r["activity"]), D(0))
                v = round_amount(base * rate)
            values[r["n"]] = v
            if r.get("usage", "production") == "production":
                snap.append({"n": r["n"], "kind": "surcharge", "rate": rate, "amount": v, "detail": r["detail"], "cc": r["cc"]})
                if v != 0:
                    out.append({"component": DETAILS[r["detail"]][0], "detail": r["detail"], "amount": v, "cc": r["cc"], "row": r["n"], "level": 0})
    return out, snap, gaps, values


def lr_split(total, weights, order):
    """Largest remainder in minor units: shares proportional to weights (any sign, sum not 0), ties by order."""
    a = sum(weights.values())
    raw = {k: F(total) * F(w) / F(a) / F(UNIT) for k, w in weights.items()}
    base = {k: (v.numerator // v.denominator) for k, v in raw.items()}
    rest = int(F(total) / F(UNIT)) - sum(base.values())
    for k in sorted(raw, key=lambda k: (-(raw[k] - base[k]), order(k)))[:rest]:
        base[k] += 1
    return {k: D(v) * UNIT for k, v in base.items()}


def split_detail(parent, prev_closing, incurred, abnormal):
    """Rule 4: the job's split of one order, period and posting component into details."""
    comp = parent["component"]
    opening = dict(prev_closing) if prev_closing else ({DEFAULT[comp]: parent["opening"]} if parent["opening"] else {})
    keys = set(opening) | set(incurred) | set(abnormal) | {DEFAULT[comp]}
    avail = {k: opening.get(k, D(0)) + incurred.get(k, D(0)) - abnormal.get(k, D(0)) for k in keys}
    order = lambda k: (DETAILS[k][1], k)
    if sum(avail.values()) == 0:
        closing = {k: (parent["closing"] if k == DEFAULT[comp] else D(0)) for k in keys}
        residual = {k: (parent["residual"] if k == DEFAULT[comp] else D(0)) for k in keys}
    else:
        closing = lr_split(parent["closing"], avail, order)
        residual = lr_split(parent["residual"], avail, order)
    rows = {}
    for k in keys:
        rows[k] = {"opening": opening.get(k, D(0)), "incurred": incurred.get(k, D(0)), "abnormal": abnormal.get(k, D(0)),
                   "residual": residual[k], "closing": closing[k], "to_output": avail[k] - closing[k] - residual[k]}
    return rows


def projected_flags(complete, periods):
    """Rule 14: provisional unless complete and every period with postings settled; a completed order's unsettled period without receipts is residual."""
    provisional = not (complete and all(p["settled"] for p in periods))
    residual = sum((p["cost"] for p in periods if complete and not p["settled"] and p["receipts"] == 0), D(0))
    return provisional, residual


# ======================================================================= M: mapping
check("M01 an activity type mapped in the component wins over the account (plan and actual land in one detail)",
      map_detail("overhead", activity_type="MACHINE_HR", account="ENERGY") == "machine")
check("M02 item group before valuation class, valuation class before account",
      map_detail("material", item_group="RAW", valuation_class="VC_PACK") == "raw_material"
      and map_detail("material", item_group="OTHER", valuation_class="VC_PACK", account="X") == "packaging")
check("M03 an unmapped value falls into the posting component's default detail",
      map_detail("overhead", account="RENT") == "overhead" and map_detail("other") == "other")
check("M04 the function looks only among the line's component: a labor activity on an overhead line does not leave overhead",
      map_detail("overhead", activity_type="LABOR_HR") == "overhead" and DETAILS[map_detail("labor", activity_type="LABOR_HR")][0] == "labor")
check("M05 the example structure stays within the limit of 12 details, with one default per posting component",
      len(DETAILS) <= 12 and sorted(DEFAULT) == sorted(COMPONENTS))

# ======================================================================= E: evaluation
LINES = [  # an estimate for a lot of 100: own lines at level 0, a made component's rolled-up lines at level 1
    {"component": "material", "detail": map_detail("material", item_group="RAW"), "amount": D("5000.00"), "level": 0},
    {"component": "material", "detail": map_detail("material", item_group="PACK"), "amount": D("800.00"), "level": 0},
    {"component": "labor", "detail": map_detail("labor", activity_type="LABOR_HR"), "amount": D("1200.00"), "level": 0, "activity": "LABOR_HR", "quantity": D("40")},
    {"component": "overhead", "detail": map_detail("overhead", activity_type="MACHINE_HR"), "amount": D("900.00"), "level": 0, "activity": "MACHINE_HR", "quantity": D("12.5")},
    {"component": "other", "detail": map_detail("other", account="SUBCON"), "amount": D("300.00"), "level": 0},
    {"component": "material", "detail": "raw_material", "amount": D("2000.00"), "level": 1},
    {"component": "overhead", "detail": "material_handling", "amount": D("150.00"), "level": 1},
]
ROWS = [
    {"n": 10, "kind": "base", "label": "Material", "members": {"material"}},
    {"n": 20, "kind": "surcharge", "label": "Material overhead", "skind": "percent", "base_row": 10, "cc": "CC_STORES", "detail": "material_handling"},
    {"n": 30, "kind": "base", "label": "Conversion", "members": {"direct_labor", "machine"}},
    {"n": 40, "kind": "surcharge", "label": "Machine energy", "skind": "per_activity_unit", "activity": "MACHINE_HR", "cc": "CC_UTIL", "detail": "energy"},
    {"n": 50, "kind": "surcharge", "label": "Production overhead", "skind": "percent", "base_row": 30, "cc": "CC_PROD", "detail": "overhead"},
    {"n": 60, "kind": "subtotal", "label": "Cost of goods manufactured", "from": 10, "to": 59},
    {"n": 70, "kind": "surcharge", "label": "Quality per unit", "skind": "per_output_unit", "cc": "CC_QA", "detail": "overhead"},
    {"n": 80, "kind": "subtotal", "label": "Production cost", "from": 10, "to": 79},
    {"n": 90, "kind": "surcharge", "label": "Administration", "usage": "selling", "skind": "percent", "base_row": 80, "cc": "CC_ADMIN"},
    {"n": 100, "kind": "surcharge", "label": "Selling", "usage": "selling", "skind": "percent", "base_row": 80, "cc": "CC_SALES"},
    {"n": 110, "kind": "subtotal", "label": "Total cost", "usage": "selling", "from": 10, "to": 109},
]
D1, D2 = date(2026, 12, 1), date(2027, 1, 15)
RATES = [
    {"row": 20, "from": date(2026, 1, 1), "to": None, "value": D("10")},
    {"row": 40, "from": date(2026, 1, 1), "to": None, "value": D("8.40")},
    {"row": 50, "from": date(2026, 1, 1), "to": date(2026, 12, 31), "value": D("50")},
    {"row": 50, "from": date(2027, 1, 1), "to": None, "value": D("55")},
    {"row": 50, "from": date(2026, 1, 1), "to": None, "value": D("60"), "item_group": "FG_HEAVY"},
    {"row": 50, "from": date(2026, 1, 1), "to": None, "value": D("65"), "site": "S2", "item_group": "FG_HEAVY"},
    {"row": 50, "from": date(2026, 1, 1), "to": None, "value": D("40"), "valuation_class": "VC_FG"},
    {"row": 70, "from": date(2026, 1, 1), "to": None, "value": D("1.25")},
    {"row": 90, "from": date(2026, 1, 1), "to": None, "value": D("6")},
    {"row": 100, "from": date(2026, 1, 1), "to": None, "value": D("4")},
]
CTX = {"date": D1, "site": "S1", "item_group": "FG_LIGHT", "valuation_class": None}
out, snap, gaps, vals = evaluate(ROWS, LINES, RATES, "production", CTX, D(100))
by_row = {l["row"]: l for l in out}
check("E01 a base row sums the version's own lines of its members: material 5,800 (raw and packaging), conversion 2,100 (labor and machine)",
      vals[10] == D("5800.00") and vals[30] == D("2100.00"), (vals[10], vals[30]))
check("E02 a percent of a base: 10% of material is 580.00 in material_handling, crediting the stores cost center",
      by_row[20]["amount"] == D("580.00") and by_row[20]["detail"] == "material_handling" and by_row[20]["cc"] == "CC_STORES", by_row[20])
check("E03 an amount per activity unit: 12.5 machine hours at 8.40 is 105.00 in energy", by_row[40]["amount"] == D("105.00") and by_row[40]["detail"] == "energy")
check("E04 an amount per output unit: a lot of 100 at 1.25 is 125.00", by_row[70]["amount"] == D("125.00"))
check("E05 a subtotal sums base and surcharge rows in its range and skips nested subtotals: 5,800 + 580 + 2,100 + 105 + 1,050 = 9,635; then + 125 = 9,760",
      vals[60] == D("9635.00") and vals[80] == D("9760.00"), (vals[60], vals[80]))
check("E06 every surcharge line lands in labor, overhead or other, never material, and rolls up to its detail's component",
      all(l["component"] in ("labor", "overhead", "other") and DETAILS[l["detail"]][0] == l["component"] for l in out))
prod_total = sum(l["amount"] for l in LINES) + sum(l["amount"] for l in out)
check("E07 the estimate's lines (priced and surcharge) sum to its total; a line no base row covers (subcontracting) stays in the total and bears no surcharge",
      prod_total == D("12210.00") and vals[10] + vals[30] == D("7900.00"), prod_total)
check("E08 selling rows are skipped in production costing: no line, no snapshot row, no value", 90 not in vals and 100 not in vals and 110 not in vals and not any(s["n"] >= 90 for s in snap))
out_s, snap_s, gaps_s, vals_s = evaluate(ROWS, LINES, RATES, "selling", CTX, D(100))
check("E09 selling costing evaluates every row: administration 6% and selling 4% of the production cost 9,760, total 10,736; its production rows equal the estimate's",
      vals_s[90] == D("585.60") and vals_s[100] == D("390.40") and vals_s[110] == D("10736.00") and out_s == out, (vals_s[90], vals_s[100], vals_s[110]))
check("E10 selling surcharges never become estimate lines (INV-852)", all(l["row"] < 90 for l in out_s))
rows_lower = [dict(r, lower=True) if r["n"] == 10 else r for r in ROWS]
out_l, _, _, vals_l = evaluate(rows_lower, LINES, RATES, "production", CTX, D(100))
check("E11 a base row with is_lower_level_included also takes the made component's rolled-up material (7,800), so material overhead is 780.00",
      vals_l[10] == D("7800.00") and {l["row"]: l for l in out_l}[20]["amount"] == D("780.00"))
check("E12 the rolled-up lines keep their own detail and are never surcharged twice by default (base 10 without lower levels is 5,800)", vals[10] == D("5800.00"))

# ======================================================================= R: rates
check("R01 by date: the 2026 rate of row 50 is 50%, the 2027 rate 55%",
      select_rate(RATES, 50, CTX) == D("50") and select_rate(RATES, 50, dict(CTX, date=D2)) == D("55"))
check("R02 an item-group rate beats the rate without conditions", select_rate(RATES, 50, dict(CTX, item_group="FG_HEAVY")) == D("60"))
check("R03 a site and item-group rate beats the item-group rate at that site only",
      select_rate(RATES, 50, dict(CTX, site="S2", item_group="FG_HEAVY")) == D("65") and select_rate(RATES, 50, dict(CTX, site="S3", item_group="FG_HEAVY")) == D("60"))
check("R04 a valuation-class rate ranks below an item-group rate and above none",
      select_rate(RATES, 50, dict(CTX, valuation_class="VC_FG")) == D("40") and select_rate(RATES, 50, dict(CTX, item_group="FG_HEAVY", valuation_class="VC_FG")) == D("60"))
no50 = [r for r in RATES if r["row"] != 50]
out_g, snap_g, gaps_g, vals_g = evaluate(ROWS, LINES, no50, "production", CTX, D(100))
check("R05 a missing rate is a gap (costing_rate_missing), writes no line and no snapshot row, and the total leaves it out, never as zero",
      gaps_g == [("costing_rate_missing", 50)] and 50 not in {l["row"] for l in out_g} and 50 not in {s["n"] for s in snap_g}
      and vals_g[60] == D("8585.00"), (gaps_g, vals_g.get(60)))
zero50 = no50 + [{"row": 50, "from": date(2026, 1, 1), "to": None, "value": D("0")}]
out_z, snap_z, gaps_z, _ = evaluate(ROWS, LINES, zero50, "production", CTX, D(100))
check("R06 a stored zero rate is a real zero: no gap and no line, but the snapshot shows the row at 0",
      gaps_z == [] and 50 not in {l["row"] for l in out_z} and any(s["n"] == 50 and s["amount"] == 0 for s in snap_z))
check("R07 a rate valid only before the costing date is no rate", select_rate([{"row": 1, "from": date(2025, 1, 1), "to": date(2025, 12, 31), "value": D(1)}], 1, CTX) is None)

# ======================================================================= U: roll-up on random estimates
rnd = random.Random(72)
SOURCES = [("material", dict(item_group="RAW")), ("material", dict(item_group="PACK")), ("material", dict(valuation_class="VC_PACK")),
           ("material", dict(item_group="NEW")), ("labor", dict(activity_type="LABOR_HR")), ("labor", dict(account="WAGES")),
           ("labor", dict(account="BONUS")), ("overhead", dict(activity_type="MACHINE_HR")), ("overhead", dict(account="ENERGY")),
           ("overhead", dict(account="DEPRECIATION")), ("overhead", dict(account="RENT")), ("other", dict(account="SUBCON")), ("other", dict(account="FREIGHT"))]
bad = []
for trial_ in range(500):
    lines = []
    for _ in range(rnd.randint(1, 25)):
        comp, facts = rnd.choice(SOURCES)
        lines.append({"component": comp, "detail": map_detail(comp, **facts), "amount": D(rnd.randint(-50000, 900000)) / 100,
                      "level": rnd.choice((0, 0, 1)), "activity": facts.get("activity_type"), "quantity": D(rnd.randint(1, 400)) / 10})
    s_out, *_ = evaluate(ROWS, lines, RATES, "production", dict(CTX, date=rnd.choice((D1, D2))), D(rnd.randint(1, 500)))
    alll = lines + s_out
    by_comp = {c: sum((l["amount"] for l in alll if l["component"] == c), D(0)) for c in COMPONENTS}
    by_det = {}
    for l in alll:
        by_det[l["detail"]] = by_det.get(l["detail"], D(0)) + l["amount"]
    rolled = {c: sum((v for k, v in by_det.items() if DETAILS[k][0] == c), D(0)) for c in COMPONENTS}
    if rolled != by_comp or any(DETAILS[l["detail"]][0] != l["component"] for l in alll):
        bad.append(trial_)
check("U01 on 500 random estimates, the detailed components sum exactly to the four posting components, and no line's detail leaves its component", not bad, bad[:3])

# ======================================================================= J: the job's split on random two-period orders
bad, bad_default = [], []
for trial_ in range(400):
    comp = rnd.choice(COMPONENTS)
    choices = [d for d, (c, _, _) in DETAILS.items() if c == comp]
    prev = None
    for period in (1, 2):
        incurred = {}
        for _ in range(rnd.randint(0, 6)):
            d_ = rnd.choice(choices)
            incurred[d_] = incurred.get(d_, D(0)) + D(rnd.randint(-20000, 500000)) / 100
        abnormal = {d_: D(rnd.randint(0, 3000)) / 100 for d_ in rnd.sample(choices, rnd.randint(0, min(2, len(choices))))}
        opening = sum(prev.values(), D(0)) if prev else D(0)
        avail = opening + sum(incurred.values(), D(0)) - sum(abnormal.values(), D(0))
        closing = (avail * D(rnd.randint(0, 100)) / 100).quantize(UNIT) if period == 1 else D(0)
        residual = (D(rnd.randint(-10, 10)) / 100) if rnd.random() < 0.3 else D(0)
        parent = {"component": comp, "opening": opening, "incurred": sum(incurred.values(), D(0)), "abnormal": sum(abnormal.values(), D(0)),
                  "residual": residual, "closing": closing}
        parent["to_output"] = parent["opening"] + parent["incurred"] - parent["abnormal"] - parent["residual"] - parent["closing"]
        rows = split_detail(parent, prev, incurred, abnormal)
        sums_ok = all(sum((r[col] for r in rows.values()), D(0)) == parent[col] for col in ("opening", "incurred", "abnormal", "residual", "closing", "to_output"))
        bal_ok = all(r["closing"] == r["opening"] + r["incurred"] - r["abnormal"] - r["residual"] - r["to_output"] for r in rows.values())
        carry_ok = prev is None or all(rows[k]["opening"] == v for k, v in prev.items())
        if not (sums_ok and bal_ok and carry_ok):
            bad.append((trial_, period))
        prev = {k: r["closing"] for k, r in rows.items() if r["closing"] != 0}
check("J01 on 400 random two-period orders, every column of the detail rows sums exactly to the parent row, each row balances, and period 2 opens with period 1's closing split (INV-851)", not bad, bad[:3])
rows0 = split_detail({"component": "overhead", "opening": D(0), "incurred": D(0), "abnormal": D(0), "residual": D("0.00"), "closing": D("0.00")},
                     None, {"energy": D("500.00"), "machine": D("-500.00")}, {})
check("J02 a component whose available amount is 0 (+500 energy, -500 machine) sends closing and residual to the default detail; to-output carries the rest per detail",
      rows0["overhead"]["closing"] == 0 and rows0["energy"]["to_output"] == D("500.00") and rows0["machine"]["to_output"] == D("-500.00"))
rows1 = split_detail({"component": "overhead", "opening": D(0), "incurred": D("1000.00"), "abnormal": D(0), "residual": D(0), "closing": D("100.00")},
                     None, {map_detail("overhead", account="RENT"): D("400.00"), "energy": D("600.00")}, {})
check("J03 unmapped overhead (rent) lands in the default overhead detail and takes its share of WIP: closing 40 and 60",
      rows1["overhead"]["incurred"] == D("400.00") and rows1["overhead"]["closing"] == D("40.00") and rows1["energy"]["closing"] == D("60.00"))
rows2 = split_detail({"component": "labor", "opening": D(0), "incurred": D("1.00"), "abnormal": D(0), "residual": D(0), "closing": D("0.01")},
                     None, {"labor": D("0.50"), "direct_labor": D("0.50")}, {})
check("J04 a tie in the largest remainder goes by sequence: the default labor detail (20) before direct_labor (21)",
      rows2["labor"]["closing"] == D("0.01") and rows2["direct_labor"]["closing"] == 0)

# ======================================================================= P: projected final cost flags
check("P01 an order in progress is provisional; a completed order with an unsettled period is provisional; complete and settled is final",
      projected_flags(False, [{"settled": True, "cost": D(1), "receipts": 1}])[0]
      and projected_flags(True, [{"settled": True, "cost": D(1), "receipts": 1}, {"settled": False, "cost": D(5), "receipts": 1}])[0]
      and not projected_flags(True, [{"settled": True, "cost": D(1), "receipts": 1}])[0])
check("P02 a completed order's unsettled period without receipts is projected residual; with a receipt, or while in progress, it is not",
      projected_flags(True, [{"settled": True, "cost": D(900), "receipts": 10}, {"settled": False, "cost": D(40), "receipts": 0}])[1] == D(40)
      and projected_flags(True, [{"settled": False, "cost": D(40), "receipts": 2}])[1] == 0
      and projected_flags(False, [{"settled": False, "cost": D(40), "receipts": 0}])[1] == 0)


# ======================================================================= X: the DDL (--load)
def reset_and_load(raw_dsn, docs):
    import psycopg
    from load_all import load_all
    with psycopg.connect(raw_dsn, autocommit=True) as cx:
        tables = [r[0] for r in cx.execute("select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
                                           " where n.nspname = 'nativeflows' and c.relkind in ('r', 'p') and not c.relispartition").fetchall()]
        for i in range(0, len(tables), 20):
            cx.execute("DROP TABLE IF EXISTS " + ", ".join(f'nativeflows."{t}"' for t in tables[i:i + 20]) + " CASCADE")
    return load_all(raw_dsn, docs)


if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("X00 load_all.py loads every DDL file with the ADR-0072 tables", n_tables > 0, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    cols = {}
    for t_, col, nul in X("select table_name, column_name, is_nullable from information_schema.columns where table_schema='nativeflows'").fetchall():
        cols.setdefault(t_, {})[col] = nul
    NEWT = ("cost_component_detail", "cost_component_detail_mapping", "costing_sheet", "costing_sheet_row", "costing_sheet_base_member",
            "costing_sheet_rate", "site_costing_sheet", "cost_estimate_sheet_row", "production_order_period_cost_detail")
    check("X01 the nine tables exist with company_id and recorded_at NOT NULL; overhead_surcharge is gone; cost_estimate_line has credited_cost_center_id and its detail, and no cost_center_id",
          all(t_ in cols and cols[t_].get("company_id") == "NO" and cols[t_].get("recorded_at") == "NO" for t_ in NEWT)
          and "overhead_surcharge" not in cols and "cost_center_id" not in cols["cost_estimate_line"]
          and cols["cost_estimate_line"].get("cost_component_detail_id") == "NO" and "credited_cost_center_id" in cols["cost_estimate_line"]
          and "costing_sheet_id" in cols["production_version"] and "costing_sheet_id" in cols["cost_estimate"],
          [t_ for t_ in NEWT if t_ not in cols])
    cons = {r[0] for r in X("select conname from pg_constraint k join pg_namespace n on n.oid = k.connamespace where n.nspname='nativeflows'").fetchall()}
    check("X02 the detail read model keeps its parent's key and balance, and holds each row to its detail's posting component",
          {"fk_production_order_period_cost_detail_parent", "ck_production_order_period_cost_detail_balance", "fk_production_order_period_cost_detail_detail"} <= cons)

    def trial(name, fn, should_fail, match=None):
        cx = conn()
        cx.autocommit = True
        try:
            cx.execute("BEGIN")
            fn(cx)
            cx.execute("SET CONSTRAINTS ALL IMMEDIATE")
            ok, detail = not should_fail, "succeeded"
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0]
            ok, detail = should_fail and (match is None or match in msg), "failed: " + msg
        finally:
            try:
                cx.execute("ROLLBACK")
            finally:
                cx.close()
        check(name, ok, detail)

    def step(name, fn):
        try:
            with c.transaction():
                fn(c)
            check(name, True)
        except Exception as e:  # noqa: BLE001
            check(name, False, str(e).splitlines()[0])

    I = {k: new() for k in """u1 co co2 ea hr ig igH vc itg pFG iFG pRM iRM cal cc ccA S1 S2 WP zP bP mach WC1 B R PV CS CS2 CE""".split()}
    t = str(I["co"])[-8:]
    B_ = '{"kind": "company_decision"}'
    H = lambda s: (s * 64)[:64]
    X("insert into currency (code, minor_unit) values ('USD',2) on conflict do nothing")
    X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'u1','en','x',now())", (I["u1"], "u1" + t))
    for k, code in (("co", "C26-"), ("co2", "C26B-")):
        X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
          " values (%s,%s,'Sample Co','USD','UTC','l10n_xx','xx_test','site',%s,'en')", (I[k], code + t, I["u1"]))
    for k, code, kind in (("ea", "EA26", "count"), ("hr", "HR26", "time")):
        if "name" in cols["uom"]:
            X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,%s,3)", (I[k], code + t, code, kind))
        else:
            X("insert into uom (id, code, quantity_kind, decimal_places) values (%s,%s,%s,3)", (I[k], code + t, kind))
    for tbl, k, code in (("item_group", "ig", "std"), ("item_group", "igH", "heavy"), ("valuation_class", "vc", "std"), ("item_tax_group", "itg", "std")):
        X(f"insert into {tbl} (id, company_id, code, name, basis) values (%s,%s,%s,%s,%s)", (I[k], I["co"], code, code, B_))
    for pk, ik, code, grp in (("pFG", "iFG", "FG-1", "igH"), ("pRM", "iRM", "RM-1", "ig")):
        X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
             item_tax_group_id, tracking) values (%s,%s,%s,%s,'stock',%s,%s,%s,%s,%s,%s,'none')""",
          (I[pk], I["co"], code, code, I[grp], I["vc"], I["ea"], I["ea"], I["ea"], I["itg"]))
        X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,%s)", (I[ik], I["co"], I[pk], code))
    X("insert into working_calendar (id, company_id, code, name, working_weekdays) values (%s,%s,'STD','Std','{1,2,3,4,5}')", (I["cal"], I["co"]))
    X("insert into cost_center (id, company_id, code, name, kind) values (%s,%s,'PROD','Production','production')", (I["cc"], I["co"]))
    X("insert into cost_center (id, company_id, code, name, kind) values (%s,%s,'ADM','Administration','administration')", (I["ccA"], I["co"]))
    with c.transaction():
        for k, code in (("S1", "MAIN"), ("S2", "EAST")):
            X("insert into site (id, company_id, code, name, kind) values (%s,%s,%s,%s,'factory')", (I[k], I["co"], code, code))
        X("insert into warehouse (id, company_id, site_id, code, name, kind, working_calendar_id, default_bin_id) values (%s,%s,%s,'WP','WP','physical',%s,%s)",
          (I["WP"], I["co"], I["S1"], I["cal"], I["bP"]))
        X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'Z','Zone')", (I["zP"], I["co"], I["WP"]))
        X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEF','WP-DEF26','storage')", (I["bP"], I["co"], I["WP"], I["zP"]))
    X("insert into activity_type (id, company_id, code, name, time_uom_id, recorded_at) values (%s,%s,'machine','Machine',%s,now())", (I["mach"], I["co"], I["hr"]))
    X("""insert into work_center (id, company_id, code, name, production_warehouse_id, working_calendar_id, hours_per_day, cost_center_id, recorded_at)
         values (%s,%s,'MILL1','Mill',%s,%s,8,%s,now())""", (I["WC1"], I["co"], I["WP"], I["cal"], I["cc"]))

    DET = {}

    def seed_details(cx):
        for code, (comp, seq, is_def) in DETAILS.items():
            DET[code] = new()
            cx.execute("insert into cost_component_detail (id, company_id, code, name, cost_component, sequence, is_default, recorded_at) values (%s,%s,%s,%s,%s,%s,%s,now())",
                       (DET[code], I["co"], code, code, comp, seq, is_def))
    step("X03 the four defaults CreateCompany seeds and eight more details, 12 in all", seed_details)
    trial("X04 a second default for a posting component is refused (INV-850)", lambda cx: cx.execute(
        "insert into cost_component_detail (id, company_id, code, name, cost_component, is_default, recorded_at) values (%s,%s,'mat2','m','material',true,now())", (new(), I["co"])),
          True, "ux_cost_component_detail_default")
    trial("X05 a default detail cannot be inactive", lambda cx: cx.execute("update cost_component_detail set is_active=false where id=%s", (DET["labor"],)),
          True, "ck_cost_component_detail_default_active")

    def mapping(cx, detail, comp, kind, **src):
        cx.execute("""insert into cost_component_detail_mapping (id, company_id, cost_component_detail_id, cost_component, source_kind, activity_type_id, item_group_id, valuation_class_id, recorded_at)
                      values (%s,%s,%s,%s,%s,%s,%s,%s,now())""", (new(), I["co"], DET[detail], comp, kind, src.get("at"), src.get("ig"), src.get("vc")))
    step("X06 mappings: the machine activity to machine, the standard item group to raw material", lambda cx: (
        mapping(cx, "machine", "overhead", "activity_type", at=I["mach"]), mapping(cx, "raw_material", "material", "item_group", ig=I["ig"])))
    trial("X07 one source maps to at most one detail per posting component", lambda cx: mapping(cx, "packaging", "material", "item_group", ig=I["ig"]),
          True, "uq_cost_component_detail_mapping_source")
    trial("X08 the same source may map in another posting component", lambda cx: mapping(cx, "subcontracting", "other", "item_group", ig=I["ig"]), False)
    trial("X09 a mapping row cannot claim a component its detail does not roll up to", lambda cx: mapping(cx, "machine", "labor", "activity_type", at=I["mach"]),
          True, "fk_cost_component_detail_mapping_detail")
    trial("X10 a mapping's source must match its kind", lambda cx: mapping(cx, "energy", "overhead", "account", at=I["mach"]), True, "ck_cost_component_detail_mapping_source")

    def row(cx, sheet, n, kind, **kw):
        names = ["company_id", "costing_sheet_id", "row_number", "row_kind", "label"] + list(kw)
        vals = [I["co"], I[sheet], n, kind, f"row {n}"] + list(kw.values())
        cx.execute(f"insert into costing_sheet_row ({', '.join(names)}, recorded_at) values ({', '.join(['%s'] * len(names))}, now())", vals)

    def member(cx, sheet, n, comp=None, detail=None):
        cx.execute("insert into costing_sheet_base_member (company_id, costing_sheet_id, row_number, cost_component, cost_component_detail_id, recorded_at) values (%s,%s,%s,%s,%s,now())",
                   (I["co"], I[sheet], n, comp, DET[detail] if detail else None))

    def sheet(cx):
        cx.execute("insert into costing_sheet (id, company_id, code, name, recorded_at) values (%s,%s,'STD','Standard',now())", (I["CS"], I["co"]))
        row(cx, "CS", 10, "base"); member(cx, "CS", 10, comp="material")
        row(cx, "CS", 20, "surcharge", surcharge_kind="percent", base_row_number=10, credited_cost_center_id=I["cc"],
            cost_component_detail_id=DET["material_handling"], cost_component="overhead")
        row(cx, "CS", 30, "base"); member(cx, "CS", 30, detail="direct_labor"); member(cx, "CS", 30, detail="machine")
        row(cx, "CS", 40, "surcharge", surcharge_kind="per_activity_unit", activity_type_id=I["mach"], credited_cost_center_id=I["cc"],
            cost_component_detail_id=DET["energy"], cost_component="overhead")
        row(cx, "CS", 50, "surcharge", surcharge_kind="percent", base_row_number=30, credited_cost_center_id=I["cc"],
            cost_component_detail_id=DET["overhead"], cost_component="overhead")
        row(cx, "CS", 60, "subtotal", from_row_number=10, to_row_number=59)
        row(cx, "CS", 70, "surcharge", surcharge_kind="per_output_unit", credited_cost_center_id=I["cc"], cost_component_detail_id=DET["overhead"], cost_component="overhead")
        row(cx, "CS", 80, "subtotal", from_row_number=10, to_row_number=79)
        row(cx, "CS", 90, "surcharge", usage="selling", surcharge_kind="percent", base_row_number=80, credited_cost_center_id=I["ccA"])
        row(cx, "CS", 110, "subtotal", usage="selling", from_row_number=10, to_row_number=109)
    step("X11 a sheet with base, percent, per-activity-unit, per-output-unit, subtotal and selling rows is written", sheet)
    trial("X12 a surcharge cannot land in material", lambda cx: row(cx, "CS", 120, "surcharge", surcharge_kind="per_output_unit", credited_cost_center_id=I["cc"],
          cost_component_detail_id=DET["raw_material"], cost_component="material"), True, "ck_costing_sheet_row_component")
    trial("X13 a surcharge row's detail must roll up to the component it states", lambda cx: row(cx, "CS", 120, "surcharge", surcharge_kind="per_output_unit",
          credited_cost_center_id=I["cc"], cost_component_detail_id=DET["energy"], cost_component="labor"), True, "fk_costing_sheet_row_detail")
    trial("X14 a percent row refers only to an earlier row", lambda cx: row(cx, "CS", 120, "surcharge", surcharge_kind="percent", base_row_number=130,
          credited_cost_center_id=I["cc"], cost_component_detail_id=DET["overhead"], cost_component="overhead"), True, "ck_costing_sheet_row_shape")
    trial("X15 a production surcharge names a detail and a credited cost center", lambda cx: row(cx, "CS", 120, "surcharge", surcharge_kind="per_output_unit",
          credited_cost_center_id=I["cc"]), True, "ck_costing_sheet_row_shape")
    trial("X16 a selling surcharge names no detail", lambda cx: row(cx, "CS", 120, "surcharge", usage="selling", surcharge_kind="per_output_unit",
          credited_cost_center_id=I["ccA"], cost_component_detail_id=DET["overhead"], cost_component="overhead"), True, "ck_costing_sheet_row_shape")
    trial("X17 a base row is never a selling row", lambda cx: row(cx, "CS", 120, "base", usage="selling"), True, "ck_costing_sheet_row_shape")
    trial("X18 a subtotal sums earlier rows only", lambda cx: row(cx, "CS", 120, "subtotal", from_row_number=10, to_row_number=130), True, "ck_costing_sheet_row_shape")
    trial("X19 a base member belongs to a base row", lambda cx: member(cx, "CS", 20, comp="labor"), True, "fk_costing_sheet_base_member_row")
    trial("X20 a member appears once per sheet", lambda cx: member(cx, "CS", 30, comp="material"), True, "uq_costing_sheet_base_member")

    def rate(cx, n, skind, frm, to=None, pct=None, amt=None, site=None, ig=None):
        cx.execute("""insert into costing_sheet_rate (id, company_id, costing_sheet_id, row_number, surcharge_kind, site_id, item_group_id, valid_from, valid_to, rate_percent, rate_amount, recorded_at)
                      values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())""", (new(), I["co"], I["CS"], n, skind, I[site] if site else None, I[ig] if ig else None, frm, to, pct, amt))
    step("X21 rates: 10% material overhead, 8.40 per machine hour, 50% then 55% production overhead, 1.25 per unit, 65% for heavy items at the east site, 6% administration",
         lambda cx: (rate(cx, 20, "percent", "2026-01-01", pct=10), rate(cx, 40, "per_activity_unit", "2026-01-01", amt="8.40"),
                     rate(cx, 50, "percent", "2026-01-01", "2026-12-31", pct=50), rate(cx, 50, "percent", "2027-01-01", pct=55),
                     rate(cx, 50, "percent", "2026-01-01", pct=65, site="S2", ig="igH"), rate(cx, 70, "per_output_unit", "2026-01-01", amt="1.25"),
                     rate(cx, 90, "percent", "2026-01-01", pct=6)))
    trial("X22 rates of one row and condition set never overlap in dates (costing_rate_overlap)", lambda cx: rate(cx, 50, "percent", "2026-06-01", "2027-02-01", pct=52),
          True, "ex_costing_sheet_rate_overlap")
    trial("X23 another condition set may overlap: a site rate beside the general one", lambda cx: rate(cx, 50, "percent", "2026-01-01", pct=58, site="S2"), False)
    trial("X24 a percent row takes a percent, not an amount", lambda cx: rate(cx, 20, "percent", "2028-01-01", amt="3", site="S2"), True, "ck_costing_sheet_rate_value")
    trial("X25 a rate's kind must be its row's kind", lambda cx: rate(cx, 40, "percent", "2028-01-01", pct=3, site="S2"), True, "fk_costing_sheet_rate_row")
    trial("X26 a base or subtotal row takes no rate", lambda cx: rate(cx, 10, "percent", "2028-01-01", pct=3), True, "fk_costing_sheet_rate_row")
    step("X27 the main site gets the sheet; a production version may override it", lambda cx: (
        cx.execute("insert into costing_sheet (id, company_id, code, name, recorded_at) values (%s,%s,'HEAVY','Heavy line',now())", (I["CS2"], I["co"])),
        cx.execute("insert into site_costing_sheet (company_id, site_id, costing_sheet_id, recorded_at) values (%s,%s,%s,now())", (I["co"], I["S1"], I["CS"]))))
    trial("X28 one sheet per site", lambda cx: cx.execute("insert into site_costing_sheet (company_id, site_id, costing_sheet_id, recorded_at) values (%s,%s,%s,now())",
                                                       (I["co"], I["S1"], I["CS2"])), True, "uq_site_costing_sheet_site_id")
    trial("X29 a site of one company cannot take another company's sheet", lambda cx: cx.execute(
        "insert into site_costing_sheet (company_id, site_id, costing_sheet_id, recorded_at) values (%s,%s,%s,now())", (I["co2"], I["S2"], I["CS"])), True, "foreign key")

    def structure(cx):
        cx.execute("insert into bill_of_materials (id, company_id, item_id, alternative, name, recorded_at) values (%s,%s,%s,'1','FG-1',now())", (I["B"], I["co"], I["iFG"]))
        cx.execute("insert into bill_of_materials_revision (id, company_id, bill_of_materials_id, revision, start_date, base_quantity, recorded_at) values (%s,%s,%s,1,'2026-12-01',1,now())",
                   (I["R"], I["co"], I["B"]))
        cx.execute("""insert into production_version (id, company_id, item_id, production_warehouse_id, code, bill_of_materials_id, start_date, costing_sheet_id, recorded_at)
                      values (%s,%s,%s,%s,'V1',%s,'2026-12-01',%s,now())""", (I["PV"], I["co"], I["iFG"], I["WP"], I["B"], I["CS2"]))
        cx.execute("""insert into cost_estimate (id, company_id, production_version_id, costing_date, costing_lot_quantity, bill_of_materials_revision_id, costing_sheet_id, recorded_at)
                      values (%s,%s,%s,'2026-12-01',100,%s,%s,now())""", (I["CE"], I["co"], I["PV"], I["R"], I["CS"]))
    step("X30 a version overriding its site's sheet, and a draft estimate naming the sheet it used", structure)

    def line(cx, n, comp, detail, amount, item=None, act=None, row_n=None, cc=None, est="CE"):
        cx.execute("""insert into cost_estimate_line (company_id, cost_estimate_id, line_number, cost_component, component_item_id, activity_type_id, cost_component_detail_id,
                      costing_sheet_row_number, credited_cost_center_id, quantity, price, company_amount, recorded_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,now())""",
                   (I["co"], I[est], n, comp, I[item] if item else None, I[act] if act else None, DET[detail], row_n, I[cc] if cc else None, amount, amount))

    def snaprow(cx, n, kind, amount, **kw):
        names = ["company_id", "cost_estimate_id", "row_number", "row_kind", "label", "company_amount"] + list(kw)
        cx.execute(f"insert into cost_estimate_sheet_row ({', '.join(names)}, recorded_at) values ({', '.join(['%s'] * len(names))}, now())",
                   [I["co"], I["CE"], n, kind, f"row {n}", amount] + list(kw.values()))

    def estimate_lines(cx):
        line(cx, 1, "material", "raw_material", "5800.00", item="iRM")
        line(cx, 2, "overhead", "machine", "900.00", act="mach")
        line(cx, 3, "overhead", "material_handling", "580.00", row_n=20, cc="cc")
        line(cx, 4, "overhead", "energy", "105.00", row_n=40, cc="cc")
        snaprow(cx, 10, "base", "5800.00")
        snaprow(cx, 20, "surcharge", "580.00", surcharge_kind="percent", base_amount="5800.00", rate=10, credited_cost_center_id=I["cc"], cost_component_detail_id=DET["material_handling"])
        snaprow(cx, 40, "surcharge", "105.00", surcharge_kind="per_activity_unit", base_quantity="12.5", rate="8.40", credited_cost_center_id=I["cc"], cost_component_detail_id=DET["energy"])
        cx.execute("""insert into cost_estimate_gap (company_id, cost_estimate_id, gap_number, gap_kind, costing_sheet_id, costing_sheet_row_number, recorded_at)
                      values (%s,%s,1,'costing_rate_missing',%s,50,now())""", (I["co"], I["CE"], I["CS"]))
    step("X31 the estimate's priced and surcharge lines, its sheet-row snapshot, and a costing_rate_missing gap are written", estimate_lines)
    trial("X32 an estimate line's detail must roll up to the line's posting component", lambda cx: line(cx, 9, "labor", "machine", "1.00", act="mach"),
          True, "fk_cost_estimate_line_detail")
    trial("X33 a surcharge line never lands in material", lambda cx: line(cx, 9, "material", "raw_material", "1.00", row_n=20, cc="cc"), True, "ck_cost_estimate_line_source")
    trial("X34 a surcharge line names its credited cost center, and only a surcharge line does", lambda cx: line(cx, 9, "overhead", "energy", "1.00", row_n=40),
          True, "ck_cost_estimate_line_source")
    trial("X35 a costing_rate_missing gap names the sheet and the row", lambda cx: cx.execute(
        "insert into cost_estimate_gap (company_id, cost_estimate_id, gap_number, gap_kind, recorded_at) values (%s,%s,2,'costing_rate_missing',now())", (I["co"], I["CE"])),
          True, "ck_cost_estimate_gap_subject")
    trial("X36 a surcharge snapshot row carries its rate, credited cost center and detail", lambda cx: snaprow(cx, 50, "surcharge", "1.00", surcharge_kind="percent", base_amount="1.00"),
          True, "ck_cost_estimate_sheet_row_shape")
    trial("X37 an estimate with a missing rate is never released, as a gap (cost_estimate_incomplete)", lambda cx: cx.execute(
        "update cost_estimate set state='released', released_at=now(), company_amount=7385, unit_cost=73.85 where id=%s", (I["CE"],)), True, "cost_estimate_incomplete")
    step("X38 the rate is set, the gap resolved with its surcharge line and snapshot row, and the estimate is released", lambda cx: (
        cx.execute("delete from cost_estimate_gap where cost_estimate_id=%s", (I["CE"],)),
        line(cx, 5, "overhead", "overhead", "450.00", row_n=50, cc="cc"),
        snaprow(cx, 50, "surcharge", "450.00", surcharge_kind="percent", base_amount="900.00", rate=50, credited_cost_center_id=I["cc"], cost_component_detail_id=DET["overhead"]),
        cx.execute("update cost_estimate set state='released', released_at=now(), company_amount=7835, unit_cost=78.35 where id=%s", (I["CE"],))))
    s_ = X("select sum(company_amount) from cost_estimate_line where cost_estimate_id=%s", (I["CE"],)).fetchone()[0]
    check("X39 the released estimate's lines sum to its company_amount (INV-852)", s_ == D("7835.00"), s_)
    trial("X40 a released estimate's sheet-row snapshot is frozen", lambda cx: cx.execute("update cost_estimate_sheet_row set rate=11 where cost_estimate_id=%s and row_number=20", (I["CE"],)),
          True, "revision_released")
    rolled = dict(X("""select d.cost_component, sum(l.company_amount) from cost_estimate_line l join cost_component_detail d on d.id = l.cost_component_detail_id
                       where l.cost_estimate_id=%s group by 1""", (I["CE"],)).fetchall())
    direct = dict(X("select cost_component, sum(company_amount) from cost_estimate_line where cost_estimate_id=%s group by 1", (I["CE"],)).fetchall())
    check("X41 in the database, the estimate's details roll up exactly to its posting components", rolled == direct and rolled, (rolled, direct))
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
