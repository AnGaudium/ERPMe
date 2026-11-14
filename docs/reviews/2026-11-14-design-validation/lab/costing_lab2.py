"""Lab prototype 2 (not product code): the DS-53 production costing model, period by period.

Validates that, with the restrictions below, one period's solve is a linear system in the
stock-node prices, solved per strongly connected component (SCC) in exact rationals, that
value is conserved, that WIP carries across periods by cost component, and that rounding to
the minor unit ties out.

Model of one period (all quantities known; unknowns are stock-node prices p_n):
  pool value per (pool, group) = constant postings + sum(indirect issue qty * p_n)   [linear]
  pool split: variable part, fixed part (by account cost behaviour, here given per posting)
  driver: activity quantity per order (or a constant basis such as output quantity)
  variable -> orders by driver share; fixed -> orders at fixed/max(D, N); rest unabsorbed
  idle pool (D = 0) -> unabsorbed entirely
  order component pools (material, labor, overhead, external):
      opening WIP_c + incurred_c in the period
  WIP methods for orders not complete, with R_p = main output received in the period,
  U = units in process (constant, from issued-vs-required quantities, floored at 0):
      no receipt in the period: everything stays WIP
      direct_material: material WIP = pool_m * U / (R_p + U); conversion all to output
      equivalent_units: WIP_c = pool_c * U*pct_c / (R_p + U*pct_c)
      planned_cost: WIP = constant (U * planned unit cost), capped at the pool after the solve
  complete orders: no WIP; abnormal material excess (cumulative, at completion) to COGS;
      cost with no output this period -> residual to COGS
  outputs: (sum pools - WIP - abnormal - by-product value) split by coefficient * quantity
  stock node price: (V0 + receipts + output shares + transfers in) / (Q0 + Qin)
"""
from fractions import Fraction as F
from collections import defaultdict
import itertools

COMP = ("material", "labor", "overhead", "external")


class Period:
    def __init__(self, name, opening_stock, opening_wip):
        self.name = name
        self.q0 = {n: F(q) for n, (q, v) in opening_stock.items()}
        self.v0 = {n: F(v) for n, (q, v) in opening_stock.items()}
        self.wip0 = {o: {c: F(x) for c, x in d.items()} for o, d in opening_wip.items()}
        self.purchases = defaultdict(list)     # n -> [(q, value)]
        self.transfers = []                    # (src, dst, q)
        self.sales = defaultdict(F)            # n -> q
        self.pools = {}                        # k -> dict
        self.orders = {}                       # o -> dict

    def pool(self, k, variable=0, fixed=0, indirect=(), normal=None, driver="activity", fixed_indirect=()):
        self.pools[k] = dict(variable=F(variable), fixed=F(fixed), indirect=[(n, F(q)) for n, q in indirect],
                             fixed_indirect=[(n, F(q)) for n, q in fixed_indirect],
                             normal=None if normal is None else F(normal), driver=driver)

    def order(self, o, issues, outputs, activity=None, external=0, complete=False, method="direct_material",
              units_in_process=0, pct=None, planned_wip=0, byproducts=(), required=None, tol=F(0), basis_qty=0, G=None, received_prior=0, issued_prior=None):
        self.orders[o] = dict(issues=[(n, F(q)) for n, q in issues],
                              outputs=[(n, F(q), F(c)) for n, q, c in outputs],
                              activity={k: F(v) for k, v in (activity or {}).items()},
                              external=F(external), complete=complete, method=method,
                              U=F(units_in_process), pct={c: F(v) for c, v in (pct or {}).items()},
                              planned_wip=F(planned_wip),
                              byproducts=[(n, F(q), F(v)) for n, q, v in byproducts],
                              required={n: F(q) for n, q in (required or {}).items()}, tol=F(tol),
                              basis_qty=F(basis_qty), G=None if G is None else F(G), received_prior=F(received_prior),
                              issued_prior={n: F(q) for n, q in (issued_prior or {}).items()})


class Lin:
    """A linear form: const + sum coef[n] * p_n."""
    def __init__(self, const=F(0), coef=None):
        self.const = F(const); self.coef = defaultdict(F, coef or {})
    def __add__(self, o):
        r = Lin(self.const, dict(self.coef))
        if isinstance(o, Lin):
            r.const += o.const
            for k, v in o.coef.items(): r.coef[k] += v
        else:
            r.const += F(o)
        return r
    __radd__ = __add__
    def __mul__(self, f):
        return Lin(self.const * f, {k: v * f for k, v in self.coef.items()})
    __rmul__ = __mul__
    def __sub__(self, o): return self + (o * F(-1) if isinstance(o, Lin) else -F(o))
    def ev(self, p): return self.const + sum(v * p[k] for k, v in self.coef.items())


def pool_allocations(per):
    """Return per (order, component) linear allocations and per pool unabsorbed forms."""
    alloc = defaultdict(lambda: Lin()); unabsorbed = {}
    for k, pd in per.pools.items():
        var = Lin(pd["variable"]) + sum((Lin(0, {n: q}) for n, q in pd["indirect"]), Lin())
        fix = Lin(pd["fixed"]) + sum((Lin(0, {n: q}) for n, q in pd["fixed_indirect"]), Lin())
        comp = "labor" if k.startswith("L") else "overhead"
        if pd["driver"] == "activity":
            d = {o: od["activity"].get(k, F(0)) for o, od in per.orders.items()}
        else:  # constant basis: output quantity of orders in the period
            d = {o: od["basis_qty"] for o, od in per.orders.items()}
        D = sum(d.values())
        if D == 0:
            unabsorbed[k] = var + fix          # idle pool: everything to COGS
            continue
        denom_fixed = max(D, pd["normal"]) if pd["normal"] is not None else D
        for o, x in d.items():
            if x:
                alloc[(o, comp)] = alloc[(o, comp)] + var * (x / D) + fix * (x / denom_fixed)
        unabsorbed[k] = fix * (1 - D / denom_fixed)
    return alloc, unabsorbed


def build(per, planned_cap=frozenset(), neg_cap=frozenset()):
    """Build equations. Returns (rows, order forms)."""
    alloc, unabsorbed = pool_allocations(per)
    nodes = sorted(per.q0)
    inflow_q = defaultdict(F); inflow_v = defaultdict(lambda: Lin())
    for n, lst in per.purchases.items():
        for q, v in lst: inflow_q[n] += F(q); inflow_v[n] = inflow_v[n] + F(v)
    for s, d, q in per.transfers:
        inflow_q[d] += F(q); inflow_v[d] = inflow_v[d] + Lin(0, {s: F(q)})
    forms = {}
    for o, od in per.orders.items():
        pool = {c: Lin(per.wip0.get(o, {}).get(c, F(0))) for c in COMP}
        for n, q in od["issues"]:
            pool["material"] = pool["material"] + Lin(0, {n: q})
        for c in ("labor", "overhead"):
            pool[c] = pool[c] + alloc[(o, c)]
        pool["external"] = pool["external"] + od["external"]
        total = sum((pool[c] for c in COMP), Lin())
        byp = sum((q * v for _, q, v in od["byproducts"]), F(0))
        for n, q, v in od["byproducts"]:
            inflow_q[n] += q; inflow_v[n] = inflow_v[n] + q * v
        R = sum(q for _, q, _ in od["outputs"][:1])     # main output received in the period
        abnormal = Lin()
        if od["complete"]:
            # cumulative excess at completion: issued - required * (1 + tol), valued at actual
            # ADR-0035 rule 10: cumulative issues against required x (cumulative received / G) x (1 + tol)
            G = od["G"] if od["G"] is not None else (od["received_prior"] + R)
            cum_recv = od["received_prior"] + R
            for n, q in od["issues"]:
                req = od["required"].get(n)
                if req is not None and G:
                    cum_issued = od["issued_prior"].get(n, F(0)) + q
                    excess = max(F(0), cum_issued - req * (cum_recv / G) * (1 + od["tol"]))
                    abnormal = abnormal + Lin(0, {n: excess})
            wip = {c: Lin() for c in COMP}
        elif R == 0:
            wip = dict(pool)                              # no output this period: all stays WIP
        elif od["method"] == "direct_material":
            wip = {c: Lin() for c in COMP}
            wip["material"] = pool["material"] * (od["U"] / (R + od["U"]))
        elif od["method"] == "equivalent_units":
            wip = {}
            for c in COMP:
                eq = od["U"] * od["pct"].get(c, F(1) if c == "material" else F(0))
                wip[c] = pool[c] * (eq / (R + eq)) if R + eq else Lin()
        elif od["method"] == "planned_cost":
            if o in planned_cap:
                wip = dict(pool); wip = {c: pool[c] for c in COMP}   # cap: WIP = pool, outputs get 0
                wip["material"] = wip["material"] - byp                # keep by-product credit in output side
            else:
                wip = {c: Lin() for c in COMP}; wip["material"] = Lin(od["planned_wip"])
        to_output = total - sum((wip[c] for c in COMP), Lin()) - abnormal - byp
        residual = Lin()
        if (od["complete"] and R == 0) or o in neg_cap:
            residual = to_output; to_output = Lin()      # rule 10, and rule 11 clamp (may be negative)
        tw = sum(q * c for _, q, c in od["outputs"])
        for n, q, c in od["outputs"]:
            if tw:
                inflow_q[n] += q; inflow_v[n] = inflow_v[n] + to_output * (q * c / tw)
        forms[o] = dict(pool=pool, wip=wip, abnormal=abnormal, to_output=to_output, residual=residual, byp=byp)
    rows = {}
    for n in nodes:
        rows[n] = (per.q0[n] + inflow_q[n], Lin(per.v0[n]) + inflow_v[n])
    return rows, forms, unabsorbed


def solve_scc(rows):
    """Price per node: p_n * Qtot = value form; solve per SCC in topological order."""
    nodes = list(rows)
    deps = {n: {k for k, v in rows[n][1].coef.items() if v != 0} for n in nodes}
    # Tarjan SCC
    index = {}; low = {}; stack = []; on = set(); sccs = []; counter = itertools.count()
    def strong(v):
        index[v] = low[v] = next(counter); stack.append(v); on.add(v)
        for w in deps[v]:
            if w not in index: strong(w); low[v] = min(low[v], low[w])
            elif w in on: low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop(); on.discard(w); comp.append(w)
                if w == v: break
            sccs.append(comp)
    for v in nodes:
        if v not in index: strong(v)
    p = {}; singular = []
    for comp in sccs:   # Tarjan emits SCCs in reverse topological order of dependencies = deps first
        idx = {n: i for i, n in enumerate(comp)}; m = len(comp)
        A = [[F(0)] * m for _ in range(m)]; b = [F(0)] * m
        for n in comp:
            qtot, val = rows[n]; i = idx[n]
            A[i][i] += qtot; b[i] += val.const
            for k, v in val.coef.items():
                if k in idx: A[i][idx[k]] -= v
                else: b[i] += v * p[k]
        try:
            sol = gauss(A, b)
            for n in comp: p[n] = sol[idx[n]]
        except ValueError:
            singular.append(comp)
            for n in comp: p[n] = None
    return p, singular


def gauss(A, b):
    n = len(b); M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = next((r for r in range(c, n) if M[r][c] != 0), None)
        if piv is None: raise ValueError("singular")
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c and M[r][c] != 0:
                f = M[r][c] / M[c][c]; M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def run_period(per, preliminary):
    cap = set(); neg = set()
    for _ in range(2 * len(per.orders) + 1):
        rows, forms, unabs = build(per, frozenset(cap), frozenset(neg))
        p, singular = solve_scc(rows)
        for comp in singular:                       # degenerate: keep preliminary prices
            for n in comp: p[n] = preliminary[n]
        new = {o for o, od in per.orders.items() if od["method"] == "planned_cost" and not od["complete"]
               and o not in cap and forms[o]["to_output"].ev(p) < 0}
        new_neg = {o for o, od in per.orders.items() if o not in neg and od["outputs"] and forms[o]["to_output"].ev(p) < 0
                   and not (od["method"] == "planned_cost" and not od["complete"])}
        if not new and not new_neg: break
        cap |= new; neg |= new_neg
    per.neg_cap = neg
    return p, forms, unabs, singular, cap


def conservation(per, p, forms, unabs):
    vin = sum(per.v0.values()) + sum(F(v) for l in per.purchases.values() for _, v in l)
    vin += sum(sum(d.values()) for d in per.wip0.values())
    vin += sum(pd["variable"] + pd["fixed"] for pd in per.pools.values())
    vin += sum(od["external"] for od in per.orders.values())
    qty = dict(per.q0)
    for n, l in per.purchases.items():
        for q, _ in l: qty[n] += F(q)
    for s, d, q in per.transfers: qty[s] -= F(q); qty[d] += F(q)
    for k, pd in per.pools.items():
        for n, q in pd["indirect"] + pd["fixed_indirect"]: qty[n] -= q
    for o, od in per.orders.items():
        for n, q in od["issues"]: qty[n] -= q
        for n, q, _ in od["byproducts"]: qty[n] += q
        for n, q, _ in od["outputs"]: qty[n] += q
    for n, q in per.sales.items(): qty[n] -= q
    closing_stock = sum(qty[n] * p[n] for n in qty)
    cogs = sum(q * p[n] for n, q in per.sales.items())
    cogs += sum(f.ev(p) for f in unabs.values())
    cogs += sum(forms[o]["abnormal"].ev(p) + forms[o]["residual"].ev(p) for o in forms)
    closing_wip = sum(sum(w.ev(p) for w in forms[o]["wip"].values()) for o in forms)
    return vin, closing_stock + cogs + closing_wip, qty, closing_wip


def largest_remainder(values, total):
    """Round exact values to integers (minor unit VND) summing exactly to round(total)."""
    floors = {k: int(v // 1) for k, v in values.items()}
    target = int(round(total)); rest = target - sum(floors.values())
    order = sorted(values, key=lambda k: (-(values[k] - floors[k]), str(k)))
    for k in order[:rest]: floors[k] += 1
    return floors


if __name__ == "__main__":
    ok = True
    # ---------- period 1
    P1 = Period("2027-01", {"A": (100, 1000), "B": (50, 2500), "S": (0, 0), "F": (0, 0), "G": (0, 0),
                            "BY": (0, 0), "GLUE": (40, 400), "R": (0, 0)}, {})
    P1.purchases["A"].append((300, 3900)); P1.purchases["B"].append((40, 2080)); P1.purchases["GLUE"].append((60, 660))
    # pools: labor pool L1 (activity driver, normal capacity 100h), overhead pool O1 with indirect glue
    P1.pool("L1", variable=0, fixed=5000, normal=100)                     # fixed labour, 80h used -> 20% unabsorbed
    P1.pool("O1", variable=1200, fixed=800, indirect=[("GLUE", 30)], normal=None)
    P1.pool("O2", variable=300, fixed=0, driver="basis")                  # no activity: constant basis (output qty)
    P1.pool("IDLE", variable=0, fixed=700, normal=50)                     # idle cost center -> COGS
    # order 1: subassembly S, complete, with by-product, abnormal excess on A
    P1.order("PO1", issues=[("A", 130)], outputs=[("S", 60, 1)], activity={"L1": 50, "O1": 50},
             complete=True, byproducts=[("BY", 10, 1)], required={"A": 120}, tol=F(5, 100), basis_qty=60)
    # order 2: finished F + co-product G (3:1), complete, consumes S and B
    P1.order("PO2", issues=[("S", 50), ("B", 40)], outputs=[("F", 40, 3), ("G", 20, 1)],
             activity={"L1": 30, "O1": 30}, external=900, complete=True, required={"S": 50, "B": 40}, basis_qty=60)
    # order 3: open, partial receipt, direct material WIP
    P1.order("PO3", issues=[("A", 50), ("B", 10)], outputs=[("S", 5, 1)], activity={"O1": 20},
             method="direct_material", units_in_process=5, basis_qty=5)
    # order 4: open, no receipt this period -> all WIP
    P1.order("PO4", issues=[("A", 20)], outputs=[], activity={"O1": 10}, method="equivalent_units", units_in_process=4)
    # order 5: open, equivalent units with partial receipt
    P1.order("PO5", issues=[("A", 40)], outputs=[("S", 6, 1)], activity={"O1": 10}, method="equivalent_units",
             units_in_process=4, pct={"material": 1, "labor": F(1, 2), "overhead": F(1, 2)}, basis_qty=6)
    # order 6: rework cycle F -> F
    P1.order("PO6", issues=[("F", 4)], outputs=[("F", 4, 1)], activity={"O1": 5}, complete=True, required={"F": 4})
    P1.sales.update({"F": F(30), "G": F(15), "S": F(5)})
    prelim = {n: F(10) for n in P1.q0}
    p1, f1, u1, s1, cap1 = run_period(P1, prelim)
    vin, vout, qty, wip1 = conservation(P1, p1, f1, u1)
    print("P1 prices:", {n: float(v) for n, v in sorted(p1.items())})
    print("P1 conservation:", vin == vout, float(vin), float(vout), "closing WIP", float(wip1))
    ok &= vin == vout and all(q >= 0 for q in qty.values())
    # carry WIP by component
    wip_carry = {o: {c: f1[o]["wip"][c].ev(p1) for c in COMP} for o in f1 if not P1.orders[o]["complete"]}
    print("P1 WIP by component:", {o: {c: float(v) for c, v in d.items() if v} for o, d in wip_carry.items()})
    # ---------- period 2: PO3 completes with more receipts, PO4 gets first receipt (planned_cost), late cost on PO1
    stock2 = {n: (qty[n], qty[n] * p1[n]) for n in qty}
    P2 = Period("2027-02", stock2, wip_carry)
    P2.purchases["A"].append((100, 1250))
    P2.pool("L1", fixed=5000, normal=100)
    P2.pool("O1", variable=900, fixed=800, normal=None)
    P2.order("PO3", issues=[("A", 8)], outputs=[("S", 5, 1)], activity={"O1": 10}, complete=True, required={"A": 55},
             G=10, received_prior=5, issued_prior={"A": 50})          # cumulative 58 vs 55 -> 3 abnormal
    P2.order("PO7", issues=[("A", 1)], outputs=[("S", 1, 1)], complete=True, byproducts=[("BY", 100, 1)],
             required={"A": 1}, G=1)                                   # by-product worth more than the order
    P2.order("PO4", issues=[("A", 10)], outputs=[("R", 3, 1)], activity={"L1": 60, "O1": 10}, method="planned_cost",
             units_in_process=2, planned_wip=10 ** 6)       # absurd planned WIP -> capped
    P2.order("PO5", issues=[], outputs=[("S", 4, 1)], activity={"O1": 5}, complete=True)
    P2.order("PO1L", issues=[], outputs=[], activity={"L1": 10}, complete=True)   # late cost, no output -> residual
    P2.sales.update({"S": F(10), "F": F(10)})
    p2, f2, u2, s2, cap2 = run_period(P2, {n: p1.get(n) or F(10) for n in P2.q0})
    vin2, vout2, qty2, wip2 = conservation(P2, p2, f2, u2)
    print("P2 prices:", {n: float(v) for n, v in sorted(p2.items())})
    print("P2 conservation:", vin2 == vout2, float(vin2), float(vout2), "closing WIP", float(wip2), "planned cap:", sorted(cap2))
    print("P2 residual to COGS:", {o: float(f2[o]["residual"].ev(p2)) for o in f2 if f2[o]["residual"].ev(p2)})
    print("P2 negative-output clamp:", sorted(P2.neg_cap), "PO3 abnormal:", float(f2["PO3"]["abnormal"].ev(p2)))
    ok &= "PO7" in P2.neg_cap and f2["PO3"]["abnormal"].ev(p2) == 3 * p2["A"]
    ok &= vin2 == vout2 and all(q >= 0 for q in qty2.values())
    # singular component: two nodes transferring to each other with no other inflow and zero opening
    P3 = Period("2027-03", {"X": (0, 0), "Y": (0, 0)}, {})
    P3.transfers += [("X", "Y", 5), ("Y", "X", 5)]
    p3, f3, u3, s3, _ = run_period(P3, {"X": F(7), "Y": F(7)})
    print("P3 singular components:", s3, "-> preliminary kept:", {n: float(v) for n, v in p3.items()})
    ok &= bool(s3)
    # rounding: receipts of PO2 outputs to VND, ties out exactly to the order's to-output value
    vals = {}
    t = f1["PO2"]["to_output"].ev(p1); tw = sum(q * c for _, q, c in P1.orders["PO2"]["outputs"])
    for n, q, c in P1.orders["PO2"]["outputs"]: vals[n] = t * q * c / tw
    r = largest_remainder(vals, t)
    print("rounding PO2 outputs:", r, "sum", sum(r.values()), "target", round(t))
    ok &= sum(r.values()) == round(t)
    print("ALL CHECKS:", "PASS" if ok else "FAIL")
