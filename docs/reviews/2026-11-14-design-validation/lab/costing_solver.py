"""Lab prototype (not product code): exact periodic actual costing over a graph of
stock nodes and production cost objects (ADR-0020 rule 12, ADR-0025 rule 6), to
validate the DS-53 approach before it is designed.

Unknowns: one periodic average price per stock node (item, valuation area).
Equations, all linear in the unknowns:
  stock node n:  p_n * (Q0_n + Qin_n) = V0_n + fixed_in_n + sum(inflow value terms)
  inflow value terms from a production order o into n: share_{o,n} * C_o
  order cost C_o = WIP0_o + sum_i q_i * p_src(i) + activities_o + overhead_o
                   - byproduct_value_o - closingWIP_o
  closing WIP: 'actual' rule -> order not complete keeps everything (no outflow);
               'equivalent' rule -> closingWIP = alpha * (WIP0 + inputs).
Co-products split by coefficients (coef_j * qty_j / sum coef*qty).
Solved per strongly connected component, exactly, with Fractions.
"""
from fractions import Fraction as F
from collections import defaultdict


class Model:
    def __init__(self):
        self.nodes = {}          # n -> dict(q0, v0)
        self.purch = defaultdict(list)   # n -> [(qty, value)]
        self.transfers = []      # (src, dst, qty)
        self.issues_out = defaultdict(F)  # n -> qty issued to sales/consumption (valued at p_n)
        # issue returns (costing role issue_return, ADR-0020 rule 12 note): never in the receipts or the revalued issues
        self.returns_same = defaultdict(F)   # n -> qty returned of an issue of this period: revalued with it at p_n
        self.returns_fixed = defaultdict(list)   # n -> [(qty, value)]: original in an earlier period, value kept
        self.orders = {}         # o -> dict

    def node(self, n, q0=0, v0=0):
        self.nodes[n] = dict(q0=F(q0), v0=F(v0))

    def order(self, o, inputs, outputs, activities=0, wip0=0, complete=True,
              byproducts=(), wip_rule="actual", alpha=F(0)):
        # inputs: [(src_node, qty)], outputs: [(dst_node, qty, coefficient)]
        self.orders[o] = dict(inputs=[(n, F(q)) for n, q in inputs],
                              outputs=[(n, F(q), F(c)) for n, q, c in outputs],
                              activities=F(activities), wip0=F(wip0), complete=complete,
                              byproducts=[(n, F(q), F(v)) for n, q, v in byproducts],
                              wip_rule=wip_rule, alpha=F(alpha))

    # ----- build the linear system A p = b over node prices
    def solve(self):
        names = sorted(self.nodes)
        idx = {n: i for i, n in enumerate(names)}
        N = len(names)
        A = [[F(0)] * N for _ in range(N)]
        b = [F(0)] * N
        qin = defaultdict(F)
        for n, lst in self.purch.items():
            for q, v in lst:
                qin[n] += F(q); b[idx[n]] += F(v)
        for s, d, q in self.transfers:
            qin[d] += F(q)
            A[idx[d]][idx[s]] -= F(q)          # value q*p_s flows into d
        # production orders: order cost as linear form over p
        self.order_cost = {}
        for o, od in self.orders.items():
            coef = defaultdict(F); const = od["wip0"] + od["activities"]
            for n, q in od["inputs"]:
                coef[n] += q
            for n, q, v in od["byproducts"]:
                const -= q * v; qin[n] += q; b[idx[n]] += q * v
            if not od["complete"]:
                if od["wip_rule"] == "actual":
                    self.order_cost[o] = (dict(coef), const, F(1))   # all stays in WIP
                    continue
                keep = od["alpha"]
                coef = {k: v * (1 - keep) for k, v in coef.items()}; const *= (1 - keep)
            self.order_cost[o] = (dict(coef), const, F(0))
            total_w = sum(q * c for _, q, c in od["outputs"])
            for n, q, c in od["outputs"]:
                share = q * c / total_w
                qin[n] += q
                for k, v in coef.items():
                    A[idx[n]][idx[k]] -= share * v
                b[idx[n]] += share * const
        for n in names:
            A[idx[n]][idx[n]] += self.nodes[n]["q0"] + qin[n]
            b[idx[n]] += self.nodes[n]["v0"]
        p = gauss(A, b)
        self.price = {n: p[idx[n]] for n in names}
        return self.price

    def check_conservation(self):
        """Value in = value out + closing stock + closing WIP, exactly."""
        p = self.price
        value_in = sum(nd["v0"] for nd in self.nodes.values()) + sum(F(v) for l in self.purch.values() for _, v in l)
        value_in += sum(od["activities"] + od["wip0"] for od in self.orders.values())
        out_sales = sum(q * p[n] for n, q in self.issues_out.items())
        out_sales -= sum(q * p[n] for n, q in self.returns_same.items())
        value_in += sum(F(v) for l in self.returns_fixed.values() for _, v in l)
        byp_external = 0  # by-products stay in stock nodes
        # closing stock quantities
        qty = {n: nd["q0"] for n, nd in self.nodes.items()}
        for n, l in self.purch.items():
            for q, _ in l: qty[n] += F(q)
        for s, d, q in self.transfers:
            qty[s] -= F(q); qty[d] += F(q)
        for od in self.orders.values():
            for n, q in od["inputs"]: qty[n] -= q
            for n, q, _ in od["byproducts"]: qty[n] += q
            if od["complete"] or od["wip_rule"] != "actual":
                for n, q, _ in od["outputs"]: qty[n] += q
        for n, q in self.issues_out.items(): qty[n] -= F(q)
        for n, q in self.returns_same.items(): qty[n] += F(q)
        fixed_q = defaultdict(F)
        for n, l in self.returns_fixed.items():
            for q, _ in l: qty[n] += F(q); fixed_q[n] += F(q)
        # a fixed-value return sits in the closing value at its own value; its difference from p_n stays there
        closing_stock = sum((qty[n] - fixed_q[n]) * p[n] for n in qty) + sum(F(v) for l in self.returns_fixed.values() for _, v in l)
        closing_wip = F(0)
        for o, od in self.orders.items():
            coef, const, keep_all = self.order_cost[o]
            gross = od["wip0"] + od["activities"] + sum(q * p[n] for n, q in od["inputs"]) - sum(q * v for _, q, v in od["byproducts"])
            if not od["complete"]:
                closing_wip += gross if od["wip_rule"] == "actual" else od["alpha"] * (od["wip0"] + od["activities"] + sum(q * p[n] for n, q in od["inputs"]))
        return value_in, out_sales + closing_stock + closing_wip, qty


def gauss(A, b):
    n = len(b); M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = next((r for r in range(c, n) if M[r][c] != 0), None)
        if piv is None: raise ValueError("singular")
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c and M[r][c] != 0:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def naive_iteration(m, rounds=200):
    """Independent check: fixed-point iteration in floats-free Fractions."""
    p = {n: F(0) for n in m.nodes}
    for _ in range(rounds):
        newp = {}
        for n in m.nodes:
            q = m.nodes[n]["q0"]; v = m.nodes[n]["v0"]
            for qq, vv in m.purch.get(n, []): q += F(qq); v += F(vv)
            for s, d, qq in m.transfers:
                if d == n: q += F(qq); v += F(qq) * p[s]
            for o, od in m.orders.items():
                for bn, bq, bv in od["byproducts"]:
                    if bn == n: q += bq; v += bq * bv
                if not od["complete"] and od["wip_rule"] == "actual":
                    continue
                keep = od["alpha"] if not od["complete"] else F(0)
                cost = (od["wip0"] + od["activities"] + sum(qq * p[s] for s, qq in od["inputs"])) * (1 - keep) - sum(bq * bv for _, bq, bv in od["byproducts"]) * (1 - keep)
                tw = sum(qq * c for _, qq, c in od["outputs"])
                for on, oq, oc in od["outputs"]:
                    if on == n: q += oq; v += cost * oq * oc / tw
            newp[n] = v / q if q else F(0)
        p = newp
    return p



# ----- sales returns at the original issue cost: costing role issue_return (ADR-0020 rules 4, 5, 12 notes; OQ-150)
def round_amount(x):
    """Minor unit, half away from zero (ADR-0006 rule 18)."""
    x = F(x); s = -1 if x < 0 else 1; h = abs(x) + F(1, 2)
    return s * (h.numerator // h.denominator)


def _norm(periods, opening):
    """A period is one area's dict (receipts, issues, returns), or {area: dict}; a line takes its area from where it is."""
    ps = []
    for P in periods:
        Q = {"A": P} if "receipts" in P else P
        for ar, X in Q.items():
            for ln in X["issues"] + X["returns"]:
                ln.setdefault("area", ar)
        ps.append(Q)
    op = {"A": opening} if isinstance(opening, tuple) else dict(opening)
    return ps, op


def return_offsets(ps):
    """r per return line: the quantity of its original already returned before it (period, area, line order)."""
    r, done = {}, defaultdict(F)
    for Q in ps:
        for ar in sorted(Q):
            for ln in Q[ar]["returns"]:
                o = ln["orig"]["id"]; r[ln["id"]] = done[o]; done[o] += ln["q"]
    return r


def share(V, Q, r, q):
    """The cumulative rule: a return of q after r already returned of Q takes round(V(r+q)/Q) - round(Vr/Q), so the returns
    of a whole line total exactly its value V."""
    return round_amount(V * (r + q) / Q) - round_amount(V * r / Q)


def cost_period(k, op, Q, final, prelim, offs):
    """One period over all areas (ADR-0020 rules 12, 13 and the rule 12 note as decided in the S2 schema review, S7 and S8).
    Pass 1: each area's actual average A from its opening and receipts only (returns never enter it). Rule 13 replaces A by
    the preliminary price when the area has no quantity base (no opening quantity, no receipts) or the average would be
    negative. Every issue, returned units issued again included, is valued at A. Pass 2: every return takes its cumulative
    share of its original's value: this period's value when the original is in this period and area (case a), else the
    final value (case b, or another area). Pass 3: closing values. A return kept outside the average leaves its difference in
    the closing value: target = round(A x (closing q - kept q)) + kept values. When the closing quantity is zero, the target
    is 0 and whatever value remains (rounding and the set-aside difference) is the posted rule 13 residual, with the issues
    still at A. When the target would be negative, which only kept returns can cause (A is never negative here), it is
    treated like a closing quantity of zero (S2 schema review round 2, R2-S1): the issues stay at A, the kept differences are
    posted as the rule 13 residual and the area closes at round(A x closing q). The posted residual is the book value minus
    the target.
    Returns ({area: (A, (closing q, target), posted residual)}, line targets)."""
    base = {}
    for ar in sorted(Q):
        X = Q[ar]; q0, v0 = op.get(ar, (F(0), F(0)))
        rq = sum(F(q) for q, _ in X["receipts"]); rv = sum(F(v) for _, v in X["receipts"])
        bq, bv = q0 + rq, v0 + rv
        p = bv / bq if bq > 0 and bv >= 0 else prelim[ar]        # rule 13: no quantity base, or a negative average
        cq = bq - sum(l["q"] for l in X["issues"]) + sum(l["q"] for l in X["returns"])
        if cq < 0:
            raise ValueError(f"negative closing quantity in area {ar}")
        base[ar] = (p, cq, bv)
    tg = {}
    for ar in sorted(Q):
        for ln in Q[ar]["issues"]:
            tg[ln["id"]] = round_amount(ln["q"] * base[ar][0])
    fin = dict(final); fin.update(tg)
    for ar in sorted(Q):
        for ln in Q[ar]["returns"]:
            o = ln["orig"]
            tg[ln["id"]] = share(fin[o["id"]], o["q"], offs[ln["id"]], ln["q"])
    res = {}
    for ar in sorted(Q):
        X = Q[ar]; p, cq, vin = base[ar]
        kept = [l for l in X["returns"] if l["orig"]["period"] != k or l["orig"]["area"] != ar]
        if cq == 0:
            target = 0
        else:
            target = round_amount(p * (cq - sum(l["q"] for l in kept))) + sum(tg[l["id"]] for l in kept)
            if target < 0:               # only kept returns make it negative: like a zero closing quantity (R2-S1)
                target = round_amount(p * cq)
        value = vin - sum(tg[l["id"]] for l in X["issues"]) + sum(tg[l["id"]] for l in X["returns"])
        res[ar] = (p, (cq, target), value - target)
    return res, tg


def _prelim(k, out, op0, Q):
    """The deterministic preliminary price per area: the actual average of k-1, else the opening unit value."""
    pr = {}
    for ar in Q:
        if k and ar in out[k - 1]:
            pr[ar] = out[k - 1][ar][0]
        else:
            q, v = op0.get(ar, (F(0), F(0))); pr[ar] = v / q if q else F(0)
    return pr


def _flat(out):
    return [o["A"] for o in out] if all(set(o) == {"A"} for o in out) else out


def naive_periods(periods, opening):
    """From scratch: every period by definition, in order."""
    ps, op = _norm(periods, opening); op0 = dict(op); offs = return_offsets(ps)
    final, out = {}, []
    for k, Q in enumerate(ps):
        r, tg = cost_period(k, op, Q, final, _prelim(k, out, op0, Q), offs)
        final.update(tg); out.append(r); op.update({ar: r[ar][1] for ar in r})
    return final, _flat(out)


def incremental(periods, opening, prelim, posted=None, done=None):
    """The posting path: issues post at a preliminary price, returns at their share of the original's current value; then
    the sequential close task costs each period and posts only differences (ADR-0012 rules 15, 16); a rerun posts the
    difference again. `posted` carries the values already in the books (for a rerun). The posting prices are free: the
    result must not depend on them, except where rule 13 keeps the rule 11 price."""
    ps, op = _norm(periods, opening); op0 = dict(op); offs = return_offsets(ps)
    cur = dict(posted or {})
    for k, Q in enumerate(ps):
        for ar in sorted(Q):
            for ln in Q[ar]["issues"]:
                cur.setdefault(ln["id"], round_amount(ln["q"] * prelim[k]))
        for ar in sorted(Q):
            for ln in Q[ar]["returns"]:
                o = ln["orig"]
                cur.setdefault(ln["id"], share(cur[o["id"]], o["q"], offs[ln["id"]], ln["q"]))
    adjustments, resid_posted, out = [], dict(done or {}), []
    for k, Q in enumerate(ps):
        r, tg = cost_period(k, op, Q, cur, _prelim(k, out, op0, Q), offs)
        for lid, t in tg.items():
            if t != cur[lid]:
                adjustments.append((k, lid, t - cur[lid])); cur[lid] = t
        for ar in sorted(r):
            prev = resid_posted.get((k, ar), 0)
            if r[ar][2] != prev:
                adjustments.append((k, "residual", r[ar][2] - prev)); resid_posted[(k, ar)] = r[ar][2]
        out.append(r); op.update({x: r[x][1] for x in r})
    return cur, _flat(out), adjustments, resid_posted


def independent_values(periods, opening):
    """An independent naive recomputation (S2 schema review finding S6): its own code path from the rules' text (ADR-0020
    rules 12, 13 and the rule 12 note), sharing nothing with cost_period, share, return_offsets, _norm or _prelim but
    round_amount. It walks the periods in order, keeps a ledger of every line's value and of each original's returned
    quantity, and values each line from its definition. Returns (line values, [{area: (price, (closing q, v), residual)}])."""
    ledger, returned, history = {}, {}, []
    stock = {}                                            # area -> (quantity, value) carried into the next period
    first_unit = {}                                       # area -> opening unit value, the preliminary price of period 0
    if isinstance(opening, tuple):
        opening = {"A": opening}
    for area, (q, v) in opening.items():
        stock[area] = (F(q), F(v))
        first_unit[area] = F(v) / F(q) if q else F(0)
    last_avg = {}
    for k, period in enumerate(periods):
        areas = {"A": period} if "receipts" in period else period
        where = {}                                        # line id -> area, for this period's issues
        for area, rows in areas.items():
            for line in rows["issues"]:
                where[line["id"]] = area
        prelim = {a_: last_avg.get(a_, first_unit.get(a_, F(0))) for a_ in areas}
        avg, qty_base, val_base, closing_q = {}, {}, {}, {}
        for area, rows in areas.items():
            q_open, v_open = stock.get(area, (F(0), F(0)))
            q_in = q_open + sum(F(q) for q, _ in rows["receipts"])
            v_in = v_open + sum(F(v) for _, v in rows["receipts"])
            qty_base[area], val_base[area] = q_in, v_in
            avg[area] = v_in / q_in if q_in > 0 and v_in >= 0 else prelim[area]
            closing_q[area] = q_in - sum(F(l["q"]) for l in rows["issues"]) + sum(F(l["q"]) for l in rows["returns"])
        values = {}
        for area, rows in areas.items():
            for line in rows["issues"]:
                values[line["id"]] = round_amount(F(line["q"]) * avg[area])
        done = dict(returned)
        for area in sorted(areas):
            for line in areas[area]["returns"]:
                orig = line["orig"]
                worth = values[orig["id"]] if orig["id"] in values else ledger[orig["id"]]
                before = done.get(orig["id"], F(0))
                after = before + F(line["q"])
                values[line["id"]] = round_amount(worth * after / F(orig["q"])) - round_amount(worth * before / F(orig["q"]))
                done[orig["id"]] = after
        result = {}
        for area, rows in areas.items():
            unit = avg[area]
            book = val_base[area] - sum(values[l["id"]] for l in rows["issues"]) + sum(values[l["id"]] for l in rows["returns"])
            outside = [l for l in rows["returns"] if where.get(l["orig"]["id"]) != area]
            rest_q = closing_q[area] - sum(F(l["q"]) for l in outside)
            target = round_amount(unit * rest_q) + sum(values[l["id"]] for l in outside)
            if closing_q[area] == 0:
                target = 0                                # nothing left: everything remaining is the posted residual
            elif target < 0:
                target = round_amount(unit * closing_q[area])   # a negative target from kept returns closes at the average
            result[area] = (unit, (closing_q[area], target), book - target)
        ledger.update(values)
        returned = done
        last_avg = {}                                     # the preliminary price is the previous period's price
        for area, (unit, closing, _) in result.items():
            stock[area] = closing
            last_avg[area] = unit
        history.append(result)
    if all(set(h) == {"A"} for h in history):
        history = [h["A"] for h in history]
    return ledger, history


def issue_return_example():
    """Three periods in one area. P1: opening 100 @ 1,000; receipt 100 for 1,400; delivery D1 of 50; a return of 10 of D1
    in P1 (case a). P2: receipt 40 for 600; delivery D2 of 30; a return of 5 of D1 (case b). P3: receipt 25 for 400;
    delivery D3 of 20 (absorption of P2's residual through the opening value)."""
    mk = lambda i, k, q: dict(id=i, period=k, q=F(q), kind="issue")
    d1, d2, d3 = mk("D1", 0, 50), mk("D2", 1, 30), mk("D3", 2, 20)
    periods = [dict(receipts=[(100, 1400)], issues=[d1], returns=[dict(id="R1", q=F(10), kind="return", orig=d1)]),
               dict(receipts=[(40, 600)], issues=[d2], returns=[dict(id="R2", q=F(5), kind="return", orig=d1)]),
               dict(receipts=[(25, 400)], issues=[d3], returns=[])]
    return periods, (F(100), F(1000))


def check_issue_returns():
    """The checks of the issue_return role. Hand-computed values are the independent evidence, with independent_values (its
    own code path, S2 schema review S6); the comparisons of the two posting paths with naive_periods share cost_period and
    prove path independence only. Returns [(ok, name, detail)]."""
    R = []
    examples = []                                         # (name, periods, opening) for the independent recomputation
    periods, opening = issue_return_example()
    fin, nv = naive_periods(periods, opening)
    p1, p2, p3 = (x[0] for x in nv)
    # path 1: everything posted first at stale prices, then costed in order; path 2: each period costed before the next
    cur1, out1, adj1, _ = incremental(periods, opening, prelim=[F(10), F(10), F(10)])
    cur2, out2, adj2 = None, None, None
    acc, done = {}, {}
    for k in range(3):
        pre = [F(10)] + [nv[j][0] for j in range(k)]
        acc, out2, adj2, done = incremental(periods[:k + 1], opening, prelim=pre + [pre[-1]] * 3, posted=acc, done=done)
    examples.append(("three periods", periods, opening))
    R.append((cur1 == fin == acc and [o[:2] for o in out1] == [o[:2] for o in nv] == [o[:2] for o in out2],
              "path independence (same cost_period, not an independent check): posting everything first at stale prices and costing "
              "each period before the next both end at the values of costing every period from scratch", (p1, p2, p3)))
    # case (a): D1 and R1 revalued together at P1's average, the pair nets to an issue of 40, no residual
    R.append((p1 == 12 and fin["D1"] == 600 and fin["R1"] == 120 and fin["D1"] - fin["R1"] == round_amount(40 * p1)
              and nv[0][1] == (160, 1920) and nv[0][2] == 0,
              "case (a): opening 100 @ 1,000 plus 100 for 1,400 gives 12; delivery 50 = 600, its return of 10 = 120, net 480 = 40 x 12; "
              "closing 160 for 1,920 = 160 x 12, no residual", (fin["D1"], fin["R1"], nv[0][1])))
    # the average ignores returns: adding R1 as a receipt would change it
    as_receipt = (1000 + 1400 + 100) / F(210)
    R.append((p1 != as_receipt, "case (a): the return stays out of the average (as a receipt at its preliminary value 100 the average "
              "would be 2,500/210, not 12)", as_receipt))
    # case (b): R2 keeps D1's final unit cost 12 (60), P2's average is (1,920 + 600)/200 = 12.6, residual 60 - 63 = -3 stays
    R.append((p2 == F(63, 5) and fin["R2"] == 60 and nv[1][1] == (175, 2202) and round_amount(p2 * 170) + 60 == 2202
              and nv[1][2] == 0,
              "case (b): the return of 5 of D1 keeps 12 (value 60); P2's average (1,920 + 600)/200 = 12.6 ignores it; closing 175 "
              "for 2,202 = 170 x 12.6 + 60: the residual -3 stays in the closing value, nothing posted", (p2, nv[1])))
    # absorption: P3's opening value carries the residual
    R.append((p3 == F(2602, 200) and nv[2][1][1] == round_amount(p3 * 180),
              "next period: P3's average (2,202 + 400)/200 = 13.01 absorbs the residual through the opening value", p3))
    # rule 13 as decided in the S2 schema review (S8): a closing quantity of zero posts what remains, the issues stay at A
    z = [dict(receipts=[], issues=[dict(id="X", period=0, q=F(10), kind="issue")], returns=[]),
         dict(receipts=[(10, 150)], issues=[dict(id="Y", period=1, q=F(10), kind="issue")], returns=[])]
    z[1]["returns"] = [dict(id="RX", q=F(4), kind="return", orig=z[0]["issues"][0])]
    z[1]["issues"][0]["q"] = F(14)
    fz, nz = naive_periods(z, (F(10), F(100)))
    cz, oz, _, _ = incremental(z, (F(10), F(100)), prelim=[F(10), F(10)])
    examples.append(("closing quantity zero after a return", z, (F(10), F(100))))
    R.append((nz[1][0] == 15 and nz[1][1] == (0, 0) and fz["Y"] == 210 and fz["RX"] == 40 and nz[1][2] == 150 - 210 + 40 == -20
              and fz == cz and [o[:2] for o in oz] == [o[:2] for o in nz],
              "case (b) with closing quantity zero (S2 review S8): the issue of 14, the 4 returned units included, stays at the actual "
              "average 15 (210), the return keeps 40, and the set-aside difference 4 x (10 - 15) = -20 is the posted rule 13 residual, "
              "closing value 0", nz[1]))
    # case (c): a backdated receipt in P1 reruns P1 to P3; R2 follows D1 by a value-only adjustment in P2's rerun
    late = [dict(P) for P in periods]; late[0] = dict(late[0], receipts=late[0]["receipts"] + [(50, 900)])
    fin_l, nv_l = naive_periods(late, opening)
    examples.append(("backdated receipt", late, opening))
    cur_r, out_r, adj_r, _ = incremental(late, opening, prelim=[F(10)] * 3, posted=cur1)
    r2_adj = [a for a in adj_r if a[1] == "R2"]
    R.append((cur_r == fin_l and [o[:2] for o in out_r] == [o[:2] for o in nv_l] and r2_adj == [(1, "R2", fin_l["R2"] - fin["R2"])]
              and fin_l["R2"] == round_amount(5 * fin_l["D1"] / 50),
              "case (c): a backdated receipt of 50 for 900 in P1 moves P1's average to 13.2; the rerun posts only differences, "
              "R2 follows D1 by one value-only line in P2 (60 -> 66), and every value equals costing from scratch (path independence)",
              (nv_l[0][0], r2_adj)))
    # multi-area: the exact solve over areas linked by transfers is unchanged by issue returns
    m = Model()
    m.node("A@W1", 100, 1000); m.node("A@W2", 0, 0)
    m.purch["A@W1"].append((100, 1400)); m.transfers.append(("A@W1", "A@W2", 30))
    m.issues_out.update({"A@W1": F(50), "A@W2": F(10)})
    before = dict(m.solve())
    m.returns_same["A@W1"] += 10; m.returns_fixed["A@W2"].append((F(5), F(55)))
    after = m.solve(); vin, vout, _ = m.check_conservation(); it = naive_iteration(m)
    R.append((before == after and vin == vout and all(after[n] == it[n] or abs(after[n] - it[n]) < F(1, 10**30) for n in after),
              "areas linked by a transfer: issue returns change no average of the exact solve, value is conserved with the case (b) "
              "value kept, and the solve equals the naive iteration", (after, vin, vout)))
    # case 1: a return into another valuation area (same period) is valued at the original's cost, outside that area's average
    dA = dict(id="DA", period=0, area="A", q=F(30), kind="issue")
    two = [{"A": dict(receipts=[(100, 1400)], issues=[dA], returns=[]),
            "B": dict(receipts=[(50, 850)], issues=[], returns=[dict(id="RB", q=F(10), kind="return", orig=dA)])}]
    op2 = {"A": (F(100), F(1000)), "B": (F(50), F(750))}
    f2, n2 = naive_periods(two, op2)
    c2, o2, _, _ = incremental(two, op2, prelim=[F(10)])
    two_l = [{"A": dict(two[0]["A"], receipts=[(100, 1400), (50, 900)]), "B": two[0]["B"]}]
    f2l, n2l = naive_periods(two_l, op2)
    examples += [("return into another area", two, op2), ("return into another area, backdated receipt", two_l, op2)]
    c2l, o2l, adj2l, _ = incremental(two_l, op2, prelim=[F(10)], posted=c2)
    R.append((n2[0]["A"][0] == 12 and n2[0]["B"][0] == 16 and f2["DA"] == 360 and f2["RB"] == 120 and n2[0]["B"][1] == (110, 1720)
              and n2[0]["B"][2] == 0 and f2 == c2 and o2 == n2
              and f2l["RB"] == share(f2l["DA"], 30, 0, 10) == 132 and c2l == f2l and o2l == n2l
              and [a_ for a_ in adj2l if a_[1] == "RB"] == [(0, "RB", 12)],
              "case 1: a delivery of 30 from area A (average 12, value 360) returned 10 into area B in the same period takes 120, "
              "B's average stays 16 = 1,600/100, B closes 110 for 1,720 = 100 x 16 + 120 with the -40 kept; a backdated receipt in A "
              "(average 13.2) moves the return to 132 by one value-only line; both paths agree (path independence)", (n2[0], adj2l)))
    # case 2: partial returns take cumulative shares, so the returns of a whole line total exactly its value
    d3 = dict(id="D3", period=0, q=F(3), kind="issue")
    cum = [dict(receipts=[], issues=[d3], returns=[]),
           dict(receipts=[(30, 1000)], issues=[], returns=[dict(id="Q1", q=F(1), kind="return", orig=d3)]),
           dict(receipts=[(30, 1000)], issues=[], returns=[dict(id="Q2", q=F(1), kind="return", orig=d3),
                                                           dict(id="Q3", q=F(1), kind="return", orig=d3)])]
    fc, nc = naive_periods(cum, (F(30), F(1000)))
    cc, oc, _, _ = incremental(cum, (F(30), F(1000)), prelim=[F(30)] * 3)
    examples.append(("cumulative partial returns", cum, (F(30), F(1000))))
    per_line = 3 * round_amount(F(1) * fc["D3"] / 3)
    R.append((fc["D3"] == 100 and [fc[x] for x in ("Q1", "Q2", "Q3")] == [33, 34, 33] and fc["Q1"] + fc["Q2"] + fc["Q3"] == fc["D3"]
              and per_line == 99 and fc == cc and oc == nc,
              "case 2: a delivery of 3 valued 100 returned 1, 1 and 1 over two periods takes 33, 34 and 33 (cumulative shares), "
              "exactly 100; rounding each return alone would give 99; both paths agree (path independence)", [fc[x] for x in ("Q1", "Q2", "Q3")]))
    # ---- S2 schema review S7: rule 13 as written, in the three reproduced cases
    sold = [dict(receipts=[(10, 300)], issues=[dict(id="S1", period=0, q=F(20), kind="issue")], returns=[])]
    fs, ns = naive_periods(sold, (F(10), F(100)))
    examples.append(("sold out, no value left", sold, (F(10), F(100))))
    R.append((ns[0][0] == 20 and fs["S1"] == 400 and ns[0][1] == (0, 0) and ns[0][2] == 0,
              "S7 (i): opening 10 for 100, a receipt of 10 for 300 and an issue of 20 close at quantity 0 with no value left after the "
              "actual average: the issue takes 20 (400), nothing is posted (before the fix: 200 at the preliminary 10, residual 200)", ns[0]))
    dE = dict(id="DE", period=0, area="A", q=F(10), kind="issue")
    empty = [{"A": dict(receipts=[], issues=[dE], returns=[]),
              "B": dict(receipts=[], issues=[], returns=[dict(id="RE", q=F(4), kind="return", orig=dE)])}]
    ope = {"A": (F(20), F(240))}
    try:
        fe, ne = naive_periods(empty, ope); err = None
    except ZeroDivisionError as e:
        fe, ne, err = {}, [{}], e
    examples.append(("return into an empty area", empty, ope))
    R.append((err is None and fe["DE"] == 120 and fe["RE"] == 48 and ne[0]["B"][1] == (4, 48) and ne[0]["B"][2] == 0,
              "S7 (ii): a return of 4 into area B, which has no opening and no receipts, takes 48 of the issue of 10 for 120 from A; B "
              "has no quantity base, so rule 13 gives it the preliminary price, and it closes 4 for 48 with nothing posted (before "
              "the fix: ZeroDivisionError)", err or ne[0].get("B")))
    dN = dict(id="DN", period=0, q=F(10), kind="issue")
    neg = [dict(receipts=[], issues=[dN], returns=[]),
           dict(receipts=[(10, 500)], issues=[dict(id="N2", period=1, q=F(12), kind="issue")], returns=[dict(id="RN", q=F(5), kind="return", orig=dN)])]
    fn_, nn = naive_periods(neg, (F(10), F(100)))
    examples.append(("negative closing value", neg, (F(10), F(100))))
    R.append((fn_["RN"] == 50 and nn[1][0] == 50 and fn_["N2"] == 600 and nn[1][1] == (3, 150) and nn[1][2] == 500 - 600 + 50 - 150 == -200,
              "S7 (iii) as decided in round 2 (R2-S1): a return of 5 at 10 (50) into an area averaging 50, then an issue of 12 that "
              "takes 2 returned units, would close 3 units at 50 x (3 - 5) + 50 = -50; only the kept return makes it negative, so it "
              "is treated like a zero closing quantity: the issue stays at the actual average 50 (600), the area closes 3 x 50 = 150 "
              "and the kept difference 5 x (10 - 50) = -200 is the posted rule 13 residual (before: the issue at the preliminary "
              "10 and 400 posted)", nn[1]))
    # ---- S8: returned units issued again are issues at A; the return's difference stays in the closing value
    dR = dict(id="DR", period=0, q=F(10), kind="issue")
    reiss = [dict(receipts=[], issues=[dR], returns=[]),
             dict(receipts=[(20, 300)], issues=[dict(id="I2", period=1, q=F(22), kind="issue")], returns=[dict(id="RR", q=F(5), kind="return", orig=dR)])]
    fr, nr = naive_periods(reiss, (F(10), F(100)))
    examples.append(("returned units issued again", reiss, (F(10), F(100))))
    R.append((fr["I2"] == 330 and fr["RR"] == 50 and nr[1][0] == 15 and nr[1][1] == (3, 20) and nr[1][2] == 0,
              "S8: a return of 5 at 10 into an area averaging 15, then an issue of 22 that takes 2 returned units: the issue is "
              "22 x 15 = 330, the area closes 3 for 15 x (3 - 5) + 50 = 20 with the -25 difference kept, nothing posted", nr[1]))
    # ---- S6: the independent recomputation agrees with cost_period on every example
    bad = []
    for name, ps_, op_ in examples:
        f_a, h_a = naive_periods(ps_, op_)
        f_b, h_b = independent_values(ps_, op_)
        if f_a != f_b or h_a != h_b:
            bad.append(name)
    R.append((not bad and len(examples) == 10,
              "S6: an independent recomputation (independent_values, its own code path from the rules) gives the same line values, "
              "prices, closing (quantity, value) and residuals as cost_period on all 10 examples", bad or len(examples)))
    return R

def check_group_currency():
    """The group-currency amount of costing lines (ADR-0020 rule 12 note of the chief architect, 2026-11-21; SAP's Material
    Ledger computes prices in each currency from that currency's own amounts). Two areas linked by a transfer; amounts in
    minor units. Company currency C; group currency G, translated per line at the rate of its own posting date: the opening
    at 1/20, W1's receipt at 1/25, W2's receipt at 1/24, the issue from W1 at 1/25; the period-end rate is 1/26. The group
    solve uses the same flows with group amounts; the independent recomputation is naive_iteration, its own code path.
    Returns one (ok, name, detail)."""
    def model(v0, r1, r2):
        m = Model()
        m.node("W1", 100, v0); m.node("W2", 0, 0)
        m.purch["W1"].append((100, r1)); m.purch["W2"].append((50, r2))
        m.transfers.append(("W1", "W2", 30))
        m.issues_out.update({"W1": F(50), "W2": F(10)})
        return m
    mc = model(100000, 140000, 90000)                                    # company amounts
    mg = model(F(100000, 20), F(140000, 25), F(90000, 24))               # each line translated at its own date's rate
    pc, pg = mc.solve(), mg.solve()
    ig = naive_iteration(mg)
    vin, vout, _ = mg.check_conservation()
    issue_c = 50 * 1000                                                   # the issue from W1 at the preliminary price 1,000
    issue_g = F(issue_c, 25)                                              # its group amount at its posting date's rate
    reval_g = 50 * pg["W1"] - issue_g                                     # group adjustment from the group solve
    reval_c_retranslated = (50 * pc["W1"] - issue_c) / 26                 # the company adjustment retranslated (rejected)
    ok = (pc == {"W1": 1200, "W2": 1575} and pg == {"W1": 53, "W2": F(267, 4)}
          and all(pg[n] == ig[n] for n in pg) and vin == vout == 14350
          and all(pg[n] != pc[n] / 26 for n in pg) and pg["W1"] / pc["W1"] != pg["W2"] / pc["W2"]
          and reval_g == 650 and reval_c_retranslated != reval_g)
    return (ok, "group currency: two areas linked by a transfer, rates moving in the period; the group solve gives W1 53 and "
            "W2 66.75 per unit, equal to the naive iteration on group amounts, group value conserved (14,350 in = out); "
            "retranslating the company averages 1,200 and 1,575 at the period-end rate 1/26 gives other values, and no single "
            "rate maps both areas (53/1,200 vs 66.75/1,575); the issue's group revaluation is 650, not the retranslated company adjustment 10,000/26 (about 385)",
            (pc, pg, reval_g, reval_c_retranslated))


if __name__ == "__main__":
    m = Model()
    # stock nodes: (item, area)
    for n, q0, v0 in [("A@W1", 100, 1000), ("B@W1", 50, 2500), ("S@W1", 10, 400), ("F@W1", 0, 0),
                      ("G@W1", 0, 0), ("BY@W1", 0, 0), ("A@W2", 0, 0)]:
        m.node(n, q0, v0)
    m.purch["A@W1"].append((200, 2600))          # receipt with value
    m.purch["B@W1"].append((50, 2600))
    m.transfers.append(("A@W1", "A@W2", 30))     # transfer between areas
    # order 1: subassembly S from 2 A + labor, by-product BY at fixed value 1
    m.order("PO1", inputs=[("A@W1", 120)], outputs=[("S@W1", 60, 1)], activities=600, byproducts=[("BY@W1", 10, 1)])
    # order 2: finished F with co-product G (coefficients 3:1) from S + B + overhead
    m.order("PO2", inputs=[("S@W1", 50), ("B@W1", 40)], outputs=[("F@W1", 40, 3), ("G@W1", 20, 1)], activities=800)
    # order 3: rework: F back into F (cycle F -> PO3 -> F)
    m.order("PO3", inputs=[("F@W1", 5)], outputs=[("F@W1", 5, 1)], activities=50)
    # order 4: not complete, WIP at actual
    m.order("PO4", inputs=[("A@W1", 20), ("B@W1", 5)], outputs=[("S@W1", 10, 1)], activities=100, complete=False)
    # order 5: not complete, equivalent units alpha=0.4 of cost stays in WIP, rest flows... (partial output)
    m.order("PO5", inputs=[("A@W2", 20)], outputs=[("S@W1", 6, 1)], activities=60, complete=False, wip_rule="equivalent", alpha=F(2, 5))
    m.issues_out.update({"F@W1": F(30), "G@W1": F(15), "S@W1": F(5)})
    price = m.solve()
    for n in sorted(price):
        print(f"{n:7} price = {price[n]}  ~ {float(price[n]):.6f}")
    vin, vout, qty = m.check_conservation()
    print("conservation:", "OK" if vin == vout else "MISMATCH", float(vin), float(vout))
    neg = {n: q for n, q in qty.items() if q < 0}
    print("negative closing quantities:", neg or "none")
    naive = naive_iteration(m)
    diff = max(abs(float(price[n] - naive[n])) for n in price)
    print("max |exact - iterated| =", diff)
    rs = check_issue_returns() + [check_group_currency()]
    for ok, name, detail in rs:
        print(("PASS " if ok else "FAIL ") + name + " -- " + str(detail))
    raise SystemExit(0 if all(ok for ok, *_ in rs) else 1)
