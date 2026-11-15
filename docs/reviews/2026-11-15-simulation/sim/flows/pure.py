"""Deterministic functions of the design, as pure Python over loaded rows.

The configuration evaluation, configured price, explosion and estimate follow the design lab's t06 (ADR-0046);
the price lookup follows t05 (ADR-0045 rules 4, 17); pricing, GR/IR positions, three-way match and credit follow
t07 (ADR-0047); the matching cascade follows t08 (ADR-0048 rule 9). Forecast and netting follow ADR-0024 rules
10-15 and ADR-0036 rules 3-5 in the reduced form the trace labels.
"""
import datetime as dt
import re
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from fractions import Fraction as F
from itertools import combinations

SCALE = D("0.0000000001")


def q10(x):
    x = D(x.numerator) / D(x.denominator) if isinstance(x, F) else D(x)
    return x.quantize(SCALE, rounding=ROUND_HALF_UP)


def round_amount(x, minor=0):
    x = D(x.numerator) / D(x.denominator) if isinstance(x, F) else D(x)
    return x.quantize(D(1).scaleb(-minor), rounding=ROUND_HALF_UP)


def num(x):
    return D(str(x))


# ============================================================ ADR-0046 rule 8: evaluate_configuration
class Model:
    def __init__(self, ch, rules, tables, defaults, required):
        self.ch, self.rules, self.tables, self.defaults, self.required = ch, rules, tables, defaults, required


def cond(m, cd, val):
    if not cd:
        return True
    if "all" in cd:
        r = [cond(m, x, val) for x in cd["all"]]
        return False if False in r else (None if None in r else True)
    if "any" in cd:
        r = [cond(m, x, val) for x in cd["any"]]
        return True if True in r else (None if None in r else False)
    if "not" in cd:
        r = cond(m, cd["not"], val)
        return None if r is None else not r
    cv, op, v = val.get(cd["c"]), cd["op"], cd.get("v")
    if op == "set":
        return cv is not None
    if op == "unset":
        return cv is None
    if cv is None:
        return None
    if m.ch[cd["c"]][1] == "number":
        v = [num(x) for x in v] if op in ("in", "not_in", "between") else num(v)
    return {"eq": lambda: cv == v, "ne": lambda: cv != v, "in": lambda: cv in v, "not_in": lambda: cv not in v,
            "lt": lambda: cv < v, "le": lambda: cv <= v, "gt": lambda: cv > v, "ge": lambda: cv >= v,
            "between": lambda: v[0] <= cv <= v[1]}[op]()


def initial(m, k):
    mode, vt, spec = m.ch[k]
    return frozenset(spec) if vt == "list" else (spec[0], spec[1])


def step_values(m, k, lo, hi, limit=2):
    base, st = m.ch[k][2][0], m.ch[k][2][2]
    n = ((lo - base) / st).to_integral_value(rounding=ROUND_CEILING) if lo > base else D(0)
    out, v = [], base + n * st
    while v <= hi and len(out) < limit:
        out.append(v)
        v += st
    return out


def has_step(m, k, lo, hi):
    return bool(step_values(m, k, lo, hi, 1))


def allowed(m, k, v, dom):
    if m.ch[k][1] == "list":
        return v in dom
    base, st = m.ch[k][2][0], m.ch[k][2][2]
    return dom[0] <= v <= dom[1] and (v - base) % st == 0


def single(m, k, dom):
    if m.ch[k][1] == "list":
        return next(iter(dom)) if len(dom) == 1 else None
    vs = step_values(m, k, dom[0], dom[1])
    return vs[0] if len(vs) == 1 else None


def cell_ok(m, col, cell, v):
    if cell == "*" or v is None:
        return True
    if isinstance(cell, dict):
        return num(cell["min"]) <= v <= num(cell["max"])
    return v == num(cell) if m.ch[col][1] == "number" else v == cell


def domains(m, val):
    dom = {k: initial(m, k) for k in m.ch}
    for kind, cd, tg, ef, ms in m.rules:
        if kind == "restrict" and cond(m, cd, val) is True:
            if m.ch[tg][1] == "list":
                dom[tg] = dom[tg] & frozenset(ef["values"])
            else:
                dom[tg] = (max(dom[tg][0], num(ef["min"])), min(dom[tg][1], num(ef["max"])))
    for code, cols, rows in m.tables:
        match = [r for r in rows if all(cell_ok(m, col, cell, val.get(col)) for col, cell in zip(cols, r))]
        for i, col in enumerate(cols):
            if val.get(col) is not None or m.ch[col][1] != "list":
                continue
            cells = {r[i] for r in match}
            if "*" not in cells:
                dom[col] = dom[col] & frozenset(cells)
    return dom


def rounds(m, val, src, log):
    for rnd in range(len(m.ch) + 1):
        snap = dict(val)
        dom = domains(m, snap)
        proposals = {}
        for kind, cd, tg, ef, ms in m.rules:
            if kind == "set" and cond(m, cd, snap) is True:
                proposals.setdefault(tg, set()).add(num(ef["value"]) if m.ch[tg][1] == "number" else ef["value"])
        new_vals = {}
        for k in m.ch:
            if k in snap:
                continue
            if k in proposals:
                if len(proposals[k]) == 1:
                    (v,) = proposals[k]
                    if allowed(m, k, v, dom[k]):
                        new_vals[k] = (v, "rule")
            elif k in m.required:
                s = single(m, k, dom[k])
                if s is not None:
                    new_vals[k] = (s, "rule")
        if not new_vals:
            return dom
        log.append({"round": len(log) + 1, "gave": {k: v for k, (v, _) in new_vals.items()}})
        for k, (v, s) in new_vals.items():
            val[k] = v
            src[k] = s
    raise RuntimeError("evaluation bound exceeded")


def evaluate(m, chosen, lookahead=True):
    val = {k: (num(v) if m.ch[k][1] == "number" else v) for k, v in chosen.items() if k in m.ch}
    src = {k: "user" for k in val}
    log = []
    dom = rounds(m, val, src, log)
    shown, unset = dict(dom), [k for k in m.ch if k not in val]
    applied = True
    while applied:
        applied = False
        for tg, v, cd in m.defaults:
            v = num(v) if m.ch[tg][1] == "number" else v
            if tg not in val and cond(m, cd, val) is True and allowed(m, tg, v, dom[tg]):
                val[tg] = v
                src[tg] = "default"
                dom = rounds(m, val, src, log)
                applied = True
                break
    viol = []
    true_rules = [r for r in m.rules if cond(m, r[1], val) is True]
    for k, v in val.items():
        if not allowed(m, k, v, dom[k]):
            msgs = sorted(ms for kind, cd, tg, ef, ms in true_rules if kind == "restrict" and tg == k
                          and not allowed(m, k, v, domains(Model(m.ch, [(kind, cd, tg, ef, ms)], [], [], set()), val)[k]))
            viol.append(("configuration_value_out_of_range", k, tuple(msgs)))
    for k in m.ch:
        sets = [r for r in true_rules if r[0] == "set" and r[2] == k]
        vals = {num(r[3]["value"]) if m.ch[k][1] == "number" else r[3]["value"] for r in sets}
        if sets and (len(vals) > 1 or val.get(k) not in vals or not allowed(m, k, val[k], dom[k])):
            viol.append(("configuration_set_conflict", k, tuple(sorted(r[4] for r in sets))))
        dd = dom[k]
        if (m.ch[k][1] == "list" and not dd) or (m.ch[k][1] == "number" and (dd[0] > dd[1] or not has_step(m, k, dd[0], dd[1]))):
            viol.append(("configuration_domain_empty", k, tuple(sorted(r[4] for r in true_rules if r[0] == "restrict" and r[2] == k))))
    for kind, cd, tg, ef, ms in true_rules:
        if kind == "forbid":
            viol.append((ms, None, ()))
    for code, cols, rows in m.tables:
        if not [r for r in rows if all(cell_ok(m, col, cell, val.get(col)) for col, cell in zip(cols, r))]:
            viol.append(("configuration_table_no_match", code, ()))
    req = set(m.required) | {r[2] for r in true_rules if r[0] == "require"}
    missing = sorted(k for k in req if k not in val)
    look = {}
    if lookahead:
        # holistic Q1 (ADR-0046 rule 8 note): leads_to_violation is true only when the value adds a violation absent from
        # the baseline; lookahead covers characteristics with no user or rule value, defaulted ones included.
        base_v = {(v[0], v[1]) for v in viol}
        for k in [k for k in m.ch if src.get(k) not in ("user", "rule")]:
            if m.ch[k][1] == "list":
                look[k] = {v: bool({(x[0], x[1]) for x in evaluate(m, {**chosen, k: v}, lookahead=False)["violations"]} - base_v)
                           for v in sorted(shown[k])}
    return {"values": val, "source": src, "domain": shown, "violations": sorted(viol, key=str), "missing": missing,
            "complete": not viol and not missing, "lookahead": look, "rounds": log}


def describe_domain(m, k, dom):
    if m.ch[k][1] == "list":
        return sorted(dom)
    lo, hi = dom
    return {"min": lo, "max": hi, "step": m.ch[k][2][2]}


# ============================================================ ADR-0046 rules 12-14: explosion and estimate
def explode(m, components, values, good_qty):
    """Selection by condition, linear sizing, exact rationals rounded once up per line to the unit's decimals."""
    out = []
    for comp in components:
        if cond(m, comp["condition"], values) is not True:
            continue
        q = F(str(comp["quantity"]))
        if comp["sizing"] == "linear":
            q += F(str(comp["quantity_per_value"])) * F(str(values[comp["characteristic"]]))
        req = q * F(str(good_qty))
        if req:
            out.append((comp["item"], (D(req.numerator) / D(req.denominator)).quantize(D(1).scaleb(-comp["decimals"]), rounding=ROUND_CEILING)))
    return out


def estimate_configuration(m, components, values, prices):
    rows = explode(m, components, values, 1)
    lines = [(it, qty, prices[it], round_amount(qty * prices[it])) for it, qty in rows]
    return sum((l[3] for l in lines), D(0)), lines


# ============================================================ ADR-0045 rule 4 / ADR-0046 rule 15: find_price
def best_entry(rows, qty):
    """rows: (id, minimum_quantity, unit_price) valid on the date; highest break not above the quantity."""
    ok = [(F(str(m)), F(str(p)), i) for i, m, p in rows if F(str(m)) <= qty]
    return max(ok, key=lambda r: r[0]) if ok else None


def find_price(entries_for, extras_for, rates_for, factor, qty, values_list=(), values_num=(), item_entry_replaces=False):
    """Generic lookup. entries_for(uom_kind) -> rows for the entered unit ('entered') or inventory unit ('inventory');
    extras_for(value_id) -> [(id, product_id, extra)]; rates_for(attr) -> (id, rate) or None.
    Returns (price or None, reason, rows used)."""
    qty = F(str(qty))
    used = []
    if factor is None:
        return None, "uom_not_allowed", used
    base = None
    e = best_entry(entries_for("entered"), qty)
    if e:
        base = e[1]
        used.append({"table": "price_list_entry", "id": e[2], "minimum_quantity": e[0], "unit_price": e[1], "unit": "entered"})
    else:
        e = best_entry(entries_for("inventory"), qty * factor)
        if e:
            base = F(q10(e[1] * factor))
            used.append({"table": "price_list_entry", "id": e[2], "minimum_quantity": e[0], "unit_price": e[1], "unit": "inventory", "factor": factor})
    if base is None:
        return None, "price_missing", used
    extra = F(0)
    for vid, is_item_defining in values_list:
        if item_entry_replaces and is_item_defining:
            continue
        rows = extras_for(vid)
        pick = [r for r in rows if r[1] is not None] or rows
        for r in pick:
            extra += F(str(r[2]))
            used.append({"table": "price_list_option_extra", "id": r[0], "unit_price_extra": r[2]})
    for attr, v, is_item_defining in values_num:
        if item_entry_replaces and is_item_defining:
            continue
        r = rates_for(attr)
        if r:
            extra += F(str(r[1])) * F(str(v))
            used.append({"table": "price_list_characteristic_rate", "id": r[0], "rate_per_value": r[1], "value": v})
    total = base + F(q10(extra * factor))
    if total < 0:
        return None, "negative_price", used
    return q10(total), "ok", used


# ============================================================ ADR-0047 rule 16: pricing procedure
def price_line(list_price, qty, manual_price=None, manual_discount=D(0), promotion=None):
    steps = [("list_price", list_price)]
    base = F(str(manual_price)) if manual_price is not None else (F(str(list_price)) if list_price is not None else None)
    if manual_price is not None:
        steps.append(("manual_price", manual_price))
    if base is None:
        return {"error": "price_required", "steps": steps}
    net = base
    if promotion:
        steps.append(("promotion", promotion))
    if manual_discount:
        net = net * (1 - F(str(manual_discount)) / 100)
        steps.append(("manual_discount_percent", manual_discount))
    stored = q10(net)
    steps.append(("net_unit_price", stored))
    amount = round_amount(F(str(stored)) * F(str(qty)))
    steps.append(("line_amount", amount))
    return {"net_unit_price": stored, "amount": amount, "steps": steps,
            "outside_list": list_price is None or (manual_price is not None and D(str(manual_price)) != list_price)}


def allocate_percent(pct, amounts, minor=0):
    amts = [F(str(a)) for a in amounts]
    tot = sum(amts)
    if tot == 0 or not pct:
        return [D(0)] * len(amounts)
    unit = F(1, 10 ** minor)
    total = F(str(round_amount(tot * F(str(pct)) / 100, minor)))
    raw = [total * a / tot / unit for a in amts]
    floors = [int(r) for r in raw]
    rest = int(total / unit) - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:rest]:
        floors[i] += 1
    return [D(f) * D(unit.numerator) / D(unit.denominator) for f in floors]


def policy_inputs(lines, doc_pct):
    """lines: dicts with qty, list_price, net_unit_price, amount, cost_per_unit (or None), is_free. ADR-0047 rule 22."""
    paid = [l for l in lines if not l.get("is_free")]
    alloc = allocate_percent(doc_pct, [l["amount"] for l in paid])
    a_of = {id(l): a for l, a in zip(paid, alloc)}
    net_of = lambda l: F(str(l["amount"])) - F(str(a_of.get(id(l), 0)))
    gross = sum(F(str(l["qty"])) * F(str(l["list_price"] if l["list_price"] is not None else l["net_unit_price"])) for l in lines)
    net = sum(net_of(l) for l in lines)
    known = all(l.get("cost_per_unit") is not None for l in lines)
    cost = sum(F(str(l["qty"])) * F(str(l["cost_per_unit"])) for l in lines) if known else None
    below = any(not l.get("is_free") and l.get("cost_per_unit") is not None and net_of(l) / F(str(l["qty"])) < F(str(l["cost_per_unit"])) for l in lines)
    return {"amount": round_amount(net), "discount_percent": q10((gross - net) / gross * 100) if gross else D(0),
            "margin_percent": None if cost is None else q10((net - cost) / net * 100), "is_price_below_cost": below,
            "is_price_outside_list": any(l.get("outside_list") for l in lines), "cost_known": known}


def tax_amount(net, rate):
    return round_amount(F(str(net)) * F(str(rate)) / 100)


def installments(total, term_lines, doc_date):
    """Largest remainder split of the total by the term's percents (ADR-0026 rule 5)."""
    raw = [F(str(total)) * F(str(p)) / 100 for p, _ in term_lines]
    fl = [int(r) for r in raw]
    rest = int(total) - sum(fl)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - fl[i]), i))
    for i in order[:rest]:
        fl[i] += 1
    return [{"installment": n + 1, "amount": D(a), "due_date": doc_date + dt.timedelta(days=days), "percent": p}
            for n, (a, (p, days)) in enumerate(zip(fl, term_lines))]


# ============================================================ ADR-0047 rule 13: GR/IR by unit positions
class GrIrLine:
    def __init__(self, layers=None, R=F(0), I=F(0)):
        self.layers = layers or []             # (from, to, price) exact rationals
        self.R, self.I = R, I

    def frontier(self):
        return self.layers[-1][1] if self.layers else F(0)

    def extend(self, upto, price):
        if upto > self.frontier():
            self.layers.append((self.frontier(), upto, F(price)))

    def V(self, b):
        return sum(((min(b, hi) - lo) * p for lo, hi, p in self.layers if b > lo), F(0))

    def cum(self, b):
        return F(round_amount(self.V(b)))

    def post(self, side, q, price):
        a = self.R if side == "R" else self.I
        b = a + q
        self.extend(b, price)
        amt = self.cum(b) - self.cum(a)
        if side == "R":
            self.R = b
        else:
            self.I = b
        return D(amt.numerator) / D(amt.denominator), D(a.numerator) / D(a.denominator), D(b.numerator) / D(b.denominator)

    def balance(self):
        """Credit-positive GR/IR balance in the trace sense: round(V(I)) - round(V(R))."""
        x = self.cum(self.I) - self.cum(self.R)
        return D(x.numerator) / D(x.denominator)


def three_way_match(ordered, received, invoiced, order_price, invoice_price, qty_tol, price_tol_pct, price_tol_amt, require_receipt):
    out = []
    if F(str(invoiced)) > F(str(ordered)) * (1 + F(str(qty_tol)) / 100):
        out.append("match_quantity_exceeded")
    if require_receipt and invoiced > received:
        out.append("match_quantity_exceeded")
    limit = max(F(str(order_price)) * F(str(price_tol_pct)) / 100, F(str(price_tol_amt)))
    diff = abs(F(str(invoice_price)) - F(str(order_price)))
    if diff > limit:
        out.append("match_price_difference")
    info = ["invoice_before_receipt"] if invoiced > received else []
    return sorted(set(out)), info, {"difference_per_unit": q10(diff), "tolerance_per_unit": q10(limit)}


# ============================================================ ADR-0048 rule 9: match_bank_line
TOKEN = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")


def ref_tokens(text):
    return {t for t in TOKEN.findall(text.upper()) if len(t) >= 4 and any(ch.isdigit() for ch in t)}


def match_bank_line(line, items, posted, accounts, rules=(), currency="VND", max_subset=6):
    """items: (id, partner, side, reference, currency, open_amount, due_date, partner_reference);
    posted: (id, direction, amount, date, reference, partner); accounts: {(bank_code, number): [partners]}."""
    items = sorted(items, key=lambda i: (i[6], str(i[0])))
    posted = sorted(posted, key=lambda p: (p[3], str(p[0])))
    side = "debit" if line["direction"] == "in" else "credit"
    mine = [i for i in items if i[2] == side and i[4] == currency]
    partners = accounts.get(line.get("counterparty"), [])
    trail = []
    cand = [p for p in posted if p[1] == line["direction"] and p[2] == line["amount"] and abs((p[3] - line["date"]).days) <= 5
            and ((p[4] and p[4] in ref_tokens(line["description"])) or p[5] in partners)]
    trail.append(f"step 1 already posted: {len(cand)} candidate(s)")
    if cand:
        best = min(cand, key=lambda p: (abs((p[3] - line["date"]).days), p[3], str(p[0])))
        return {"kind": "posted", "document": best[0], "allocations": [], "score": 95, "trail": trail}
    tokens = ref_tokens(line["description"]) | set(line.get("extra_tokens") or ())
    # a token <reference>-<n> names installment n alone (holistic F8)
    def refd(i):
        if i[3] in tokens or (i[7] and i[7] in tokens):
            return True
        return f"{i[3]}-{i[8]}" in tokens if len(i) > 8 else False
    ref = [i for i in mine if refd(i)]
    single_inst = [i for i in mine if len(i) > 8 and f"{i[3]}-{i[8]}" in tokens]
    if single_inst:
        ref = single_inst
    trail.append(f"step 2 reference: tokens {sorted(tokens)}; {len(ref)} item(s) referenced")
    if ref:
        if len({i[1] for i in ref}) > 1:
            return {"kind": "unmatched", "reason": "ambiguous_reference", "allocations": [], "score": 0, "trail": trail}
        partner = ref[0][1]
        # whose account paid (holistic F7): own -> 100/80; unknown -> counterparty_unverified, caps 85/65; others' -> third party, cap 60
        if partner in partners:
            cap_exact, cap_part, flag = 100, 80, None
        elif not partners:
            cap_exact, cap_part, flag = 85, 65, "counterparty_unverified"
        else:
            cap_exact, cap_part, flag = 60, 60, "paid_by_third_party"
        # due-ordered prefix summing exactly scores 100; else one referenced item equal to the amount scores 90 (holistic F8)
        acc, prefix = D(0), []
        for i in ref:
            acc += i[5]
            prefix.append(i)
            if acc >= line["amount"]:
                break
        if acc == line["amount"]:
            trail.append(f"prefix of {len(prefix)} referenced item(s) in due order sums exactly; cap {cap_exact} ({flag or 'own account'})")
            return {"kind": "reference", "partner": partner, "allocations": [(i[0], i[5]) for i in prefix], "score": min(100, cap_exact),
                    "flag": flag, "trail": trail}
        eq = [i for i in ref if i[5] == line["amount"]]
        if eq:
            trail.append(f"single referenced item equal to the amount; cap {cap_exact} ({flag or 'own account'})")
            return {"kind": "reference", "partner": partner, "allocations": [(eq[0][0], eq[0][5])], "score": min(90, cap_exact),
                    "flag": flag, "trail": trail}
        out, left = [], line["amount"]
        for i in ref:
            take = min(left, i[5])
            out.append((i[0], take))
            left -= take
            if left == 0:
                break
        if left:
            out.append(("on_account", left))
        return {"kind": "reference_partial", "partner": partner, "allocations": out, "score": min(80, cap_part), "flag": flag, "trail": trail}
    if line.get("step2_only"):
        trail.append("re-run at step 2 only (ADR-0051 rule 18): nothing found")
        return {"kind": "unmatched", "reason": "no_reference", "allocations": [], "score": 0, "trail": trail}
    up = line["description"].upper()
    for pattern, kind, target in rules:
        if pattern in up:
            trail.append(f"company rule '{pattern}' -> {kind}:{target}")
            if kind == "account":
                return {"kind": "rule_account", "account": target, "allocations": [("account", line["amount"])], "score": 75, "trail": trail}
            partners = [target]
            break
    if len(partners) > 1:
        return {"kind": "unmatched", "reason": "shared_account", "allocations": [], "score": 0, "trail": trail}
    trail.append(f"step 3 account and amount: counterparty partners {partners}")
    if partners:
        pm = [i for i in mine if i[1] == partners[0]]
        exact = [i for i in pm if i[5] == line["amount"]]
        if exact:
            return {"kind": "account_amount", "partner": partners[0], "allocations": [(exact[0][0], exact[0][5])], "score": 90 if len(exact) == 1 else 60, "trail": trail}
        best = None
        for k in range(2, min(len(pm), max_subset) + 1):
            for combo in combinations(pm[:max_subset], k):
                if sum(i[5] for i in combo) == line["amount"]:
                    key = (k, [i[6] for i in combo], [str(i[0]) for i in combo])
                    if best is None or key < best[0]:
                        best = (key, combo)
            if best:
                break
        trail.append("step 4 subset: " + ("found" if best else "none"))
        if best:
            return {"kind": "account_subset", "partner": partners[0], "allocations": [(i[0], i[5]) for i in best[1]], "score": 70, "trail": trail}
    trail.append("step 5 unmatched")
    return {"kind": "unmatched", "reason": "no_rule", "allocations": [], "score": 0, "trail": trail}


# ============================================================ calendars (ADR-0024 rules 4-5)
def is_working(day, weekdays=(1, 2, 3, 4, 5)):
    return day.isoweekday() in weekdays


def add_working_days(day, n):
    while n > 0:
        day += dt.timedelta(days=1)
        if is_working(day):
            n -= 1
    return day


def sub_working_days(day, n):
    while n > 0:
        day -= dt.timedelta(days=1)
        if is_working(day):
            n -= 1
    return day


def purchase_arrival(release, processing, transit, receiving):
    """Lead time of a purchase: processing on the supplier's working days, transit in calendar days, receiving on the warehouse's working days."""
    a = add_working_days(release, processing)
    a = a + dt.timedelta(days=transit)
    while not is_working(a):
        a += dt.timedelta(days=1)
    return add_working_days(a, receiving)


def release_for(need, processing, transit, receiving, planning_date):
    """The latest working day from which the order still arrives by need; never before the planning date."""
    day = need
    while day >= planning_date:
        if is_working(day) and purchase_arrival(day, processing, transit, receiving) <= need:
            return day, purchase_arrival(day, processing, transit, receiving), False
        day -= dt.timedelta(days=1)
    rel = planning_date
    while not is_working(rel):
        rel += dt.timedelta(days=1)
    return rel, purchase_arrival(rel, processing, transit, receiving), True


# ============================================================ ADR-0024 rules 10-11: forecast
def moving_average_forecast(history_weeks, weeks_ahead, window=8):
    """ADR-0024 rule 11 with the holistic F0 tiers per (item, warehouse), n = non-event weeks since the first history week:
    n = 0 no forecast; 1 <= n < 8 mean of n weeks, unindexed; 8 <= n < 52 the 8-week average, unindexed; n >= 52 indexed.
    Below 52 weeks the run carries the check result forecast_history_insufficient."""
    n = len(history_weeks)
    if n == 0:
        return [], None, ["forecast_history_insufficient"], "none"
    last = [q for _, q in history_weeks[-window:]]
    avg = sum(F(str(q)) for q in last) / len(last)
    tier = "short_mean" if n < 8 else ("unindexed" if n < 52 else "indexed")
    checks = [] if n >= 52 else ["forecast_history_insufficient"]
    start = history_weeks[-1][0]
    out = [(start + dt.timedelta(days=7 * (i + 1)), avg) for i in range(weeks_ahead)]
    return out, avg, checks, tier


def spread_week(week_start, qty, decimals=0):
    """Uniform daily spread over the five working days (the fallback of ADR-0024 rule 10 without daily history),
    carrying the rounding remainder forward so nothing is lost."""
    days = [week_start + dt.timedelta(days=i) for i in range(5)]
    out, carried, unit = [], F(0), F(1, 10 ** decimals)
    share = F(qty) / 5
    for i, day in enumerate(days):
        want = share + carried
        q = (want // unit) * unit if i < 4 else want
        carried = want - q
        out.append((day, q))
    return out


# ============================================================ ADR-0051 rule 1: rank_candidates (token-set ratio, folded text)
def _indel_ratio(a, b):
    """Normalized Indel similarity in percent (the rapidfuzz ratio): 2 * LCS / (len a + len b)."""
    if not a and not b:
        return 100.0
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if ca == cb else max(prev[j], cur[j - 1]))
        prev = cur
    return 200.0 * prev[-1] / (len(a) + len(b))


def token_set_ratio(a, b):
    from .core import fold
    ta, tb = set(re.findall(r"[a-z0-9]+", fold(a))), set(re.findall(r"[a-z0-9]+", fold(b)))
    inter = " ".join(sorted(ta & tb))
    da, db_ = " ".join(sorted(ta - tb)), " ".join(sorted(tb - ta))
    s1, s2 = (inter + " " + da).strip(), (inter + " " + db_).strip()
    if inter and (not da or not db_):
        return 100.0
    return max(_indel_ratio(inter, s1), _indel_ratio(inter, s2), _indel_ratio(s1, s2))


def rank_candidates(text, candidates, accept=92, lead=8, top=5):
    """candidates: [(handle, label)]. Accepted without an LLM when the best scores >= accept and leads the next by >= lead."""
    scored = sorted(((round(token_set_ratio(text, label), 1), h, label) for h, label in candidates), key=lambda r: (-r[0], str(r[1])))
    best = scored[0] if scored else None
    nxt = scored[1][0] if len(scored) > 1 else 0
    accepted = best is not None and best[0] >= accept and best[0] - nxt >= lead
    return {"accepted": best[1] if accepted else None, "scores": scored[:top], "rule": f">= {accept} and lead >= {lead}"}


# ============================================================ l10n_vn package rule stubs (ADR-0019 rule 4; DS-19)
def vn_tax_id_valid(tax_id):
    """Format and check digit of a 10-digit enterprise code (13 with a branch suffix): weights 31,29,23,19,17,13,7,5,3,
    check = 10 - (sum mod 11). Package rule stub (the package's validator is not drafted)."""
    t = re.sub(r"[\s.]", "", str(tax_id or ""))
    m = re.fullmatch(r"(\d{10})(-\d{3})?", t)
    if not m:
        return False, t
    ds = [int(c) for c in m.group(1)]
    chk = 10 - (sum(x * w for x, w in zip(ds[:9], (31, 29, 23, 19, 17, 13, 7, 5, 3))) % 11)
    return chk == ds[9], t


def vn_phone_normalize(text):
    digits = re.sub(r"\D", "", str(text or ""))
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return ("+84" + digits[1:]) if re.fullmatch(r"0\d{9}", digits) else None
