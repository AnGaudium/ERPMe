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
        closing_stock = sum(qty[n] * p[n] for n in qty)
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
