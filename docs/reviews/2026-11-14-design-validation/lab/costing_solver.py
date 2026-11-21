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


def line_target(line, period, p, final):
    """The final value of a line by definition. Issues and same-period returns (case a) at the period's actual average;
    a return of an earlier period's issue (case b) at the original's final unit cost (lab assumption for a partial return:
    round(q x final value / original q))."""
    if line["kind"] == "issue":
        return round_amount(line["q"] * p)
    o = line["orig"]
    if o["period"] == period:
        return round_amount(line["q"] * p)
    return round_amount(line["q"] * final[o["id"]] / o["q"])


def cost_period(period, opening, P, final, prelim):
    """One area, one period: the actual average from the opening and the receipts only; the targets of the issue and
    return lines; the closing value with the case (b) residual kept and the rounding residual posted (rule 13). When the
    closing quantity is zero but value remains (rule 13), issues and same-period returns keep the preliminary price and the
    residual is posted. Returns (p, targets, closing (q, v), posted residual)."""
    q0, v0 = opening
    rq = sum(F(q) for q, _ in P["receipts"]); rv = sum(F(v) for _, v in P["receipts"])
    p = (v0 + rv) / (q0 + rq)
    cq = q0 + rq - sum(l["q"] for l in P["issues"]) + sum(l["q"] for l in P["returns"])
    kept_lines = [l for l in P["returns"] if l["orig"]["period"] != period]
    kept_q = sum(l["q"] for l in kept_lines)

    def run(price):
        tg = {ln["id"]: line_target(ln, period, price, final) for ln in P["issues"] + P["returns"]}
        value = v0 + rv - sum(tg[l["id"]] for l in P["issues"]) + sum(tg[l["id"]] for l in P["returns"])
        return tg, value
    tg, value = run(p)
    if cq == 0 and value != 0:                                    # rule 13: the area keeps the preliminary price
        tg, value = run(prelim)
        return p, tg, (cq, 0), value
    kept = sum(tg[l["id"]] for l in kept_lines)
    target = 0 if cq == 0 else round_amount(p * (cq - kept_q)) + kept
    return p, tg, (cq, target), value - target


def rule11_prelim(k, out, opening):
    """The deterministic preliminary price of period k: the actual average of k-1, else the opening unit value."""
    return out[k - 1][0] if k else opening[1] / opening[0]


def naive_periods(periods, opening):
    """From scratch: every period by definition, in order."""
    final, out, op = {}, [], opening
    for k, P in enumerate(periods):
        p, tg, close, resid = cost_period(k, op, P, final, rule11_prelim(k, out, opening))
        final.update(tg); out.append((p, close, resid)); op = close
    return final, out


def incremental(periods, opening, prelim, posted=None, done=None):
    """The posting path: lines post at a preliminary price (returns at the original's current value), then the
    sequential close task costs each period and posts only differences (ADR-0012 rules 15, 16); a rerun posts the
    difference again. `posted` carries the values already in the books (for a rerun). The posting prices are free: the
    result must not depend on them, except where rule 13 keeps the rule 11 price."""
    cur = dict(posted or {})
    for k, P in enumerate(periods):
        for ln in P["issues"]:
            cur.setdefault(ln["id"], round_amount(ln["q"] * prelim[k]))
        for ln in P["returns"]:
            o = ln["orig"]
            cur.setdefault(ln["id"], round_amount(ln["q"] * cur[o["id"]] / o["q"]))
    adjustments, resid_posted, op, out = [], dict(done or {}), opening, []
    for k, P in enumerate(periods):
        p, tg, close, resid = cost_period(k, op, P, cur, rule11_prelim(k, out, opening))
        for lid, t in tg.items():
            if t != cur[lid]:
                adjustments.append((k, lid, t - cur[lid])); cur[lid] = t
        prev = resid_posted.get(k, 0)
        if resid != prev:
            adjustments.append((k, "residual", resid - prev)); resid_posted[k] = resid
        out.append((p, close, resid)); op = close
    return cur, out, adjustments, resid_posted


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
    """The checks of the issue_return role against a naive recomputation. Returns [(ok, name, detail)]."""
    R = []
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
    R.append((cur1 == fin == acc and [o[:2] for o in out1] == [o[:2] for o in nv] == [o[:2] for o in out2],
              "both posting paths end at the naive recomputation: line values and closing (quantity, value) per period",
              (p1, p2, p3)))
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
    # rule 13: a closing quantity of zero posts the residual
    z = [dict(receipts=[], issues=[dict(id="X", period=0, q=F(10), kind="issue")], returns=[]),
         dict(receipts=[(10, 150)], issues=[dict(id="Y", period=1, q=F(10), kind="issue")], returns=[])]
    z[1]["returns"] = [dict(id="RX", q=F(4), kind="return", orig=z[0]["issues"][0])]
    z[1]["issues"][0]["q"] = F(14)
    fz, nz = naive_periods(z, (F(10), F(100)))
    cz, oz, _, _ = incremental(z, (F(10), F(100)), prelim=[F(10), F(10)])
    R.append((nz[1][1] == (0, 0) and fz["Y"] == 140 and nz[1][2] == 150 - 140 + 40 and fz == cz
              and [o[:2] for o in oz] == [o[:2] for o in nz],
              "case (b) with closing quantity zero: rule 13 keeps the preliminary price 10 for the issue of 14 (140), the return "
              "keeps 40, and the residual 150 - 140 + 40 = 50 is posted, closing value 0", nz[1]))
    # case (c): a backdated receipt in P1 reruns P1 to P3; R2 follows D1 by a value-only adjustment in P2's rerun
    late = [dict(P) for P in periods]; late[0] = dict(late[0], receipts=late[0]["receipts"] + [(50, 900)])
    fin_l, nv_l = naive_periods(late, opening)
    cur_r, out_r, adj_r, _ = incremental(late, opening, prelim=[F(10)] * 3, posted=cur1)
    r2_adj = [a for a in adj_r if a[1] == "R2"]
    R.append((cur_r == fin_l and [o[:2] for o in out_r] == [o[:2] for o in nv_l] and r2_adj == [(1, "R2", fin_l["R2"] - fin["R2"])]
              and fin_l["R2"] == round_amount(5 * fin_l["D1"] / 50),
              "case (c): a backdated receipt of 50 for 900 in P1 moves P1's average to 13.2; the rerun posts only differences, "
              "R2 follows D1 by one value-only line in P2 (60 -> 66), and every value equals the naive recomputation",
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
    return R

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
    rs = check_issue_returns()
    for ok, name, detail in rs:
        print(("PASS " if ok else "FAIL ") + name + " -- " + str(detail))
    raise SystemExit(0 if all(ok for ok, *_ in rs) else 1)
