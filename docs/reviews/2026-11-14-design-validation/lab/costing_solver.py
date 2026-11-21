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
            for key in ("issues", "returns", "reversals", "transfers", "transfer_reversals", "receipt_reversals"):
                for ln in X.get(key, ()):
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


def rounding_bound(n_rounded, n_share):
    """ADR-0020 rule 13 note (S2 adversarial review S4): the rounding bound of an item and area in a period, in minor units:
    one half for each line whose value the costing sets as round(quantity x price) (its issues), plus one for each
    issue_return line revalued with an original of the same period and area (its cumulative share is the difference of two
    rounded amounts). A reversal revalued with its original takes exactly the original's value and adds nothing."""
    return F(n_rounded, 2) + n_share


def _order(Q):
    """The areas of a period in an order where every transfer's source comes before its destination (ADR-0020 rule 12: the
    components in topological order). A cycle of transfers within one period is the exact solve's case, not this prototype's."""
    edges = {ar: {t["to"] for t in Q[ar].get("transfers", ())} for ar in Q}
    order, seen, busy = [], set(), set()

    def visit(ar):
        if ar in busy:
            raise ValueError("a cycle of transfers within a period: solved as one linear system (rule 12), not by cost_period")
        if ar in seen:
            return
        busy.add(ar)
        for to in sorted(edges[ar]):
            visit(to)
        busy.discard(ar); seen.add(ar); order.append(ar)
    for ar in sorted(Q):
        visit(ar)
    return order[::-1]


def cost_period(k, op, Q, final, prelim, offs):
    """One period over all areas (ADR-0020 rules 12, 13 and the rule 12 note as decided in the S2 schema review, S7 and S8;
    the rule 7, 12 and 13 notes of the S2 adversarial review, S4 and S5, and of its second pass, N4 and N5).
    Line kinds of an area: receipts (q, v), a receipt (0, v) being a value-only receipt addition such as a late landed cost
    (S6); issues (revalued); returns of issues (issue_return); reversals of issues; receipt_reversals (the whole original
    receipt, its document value v); transfers out (revalued at the area's price, received by area `to` at that value); and
    transfer_reversals, listed in the transfer's source area (back into it, out of the destination, at the transfer's value).
    Pass 1, areas in transfer order: each area's actual average A from its opening and receipts only; a same-period receipt
    reversal nets out of the receipts, a same-period transfer enters its destination's receipts at its value, and its
    same-period reversal nets out of them. Returns and reversals never enter A. Rule 13 replaces A by the preliminary price
    when the area has no quantity base (no opening quantity, no receipts) or the average would be negative. Every issue and
    transfer out is valued at A. Pass 2: every return takes its cumulative share of its original's value, and every reversal
    its original's whole value: this period's value when the original is in this period and area (case a: the pair is
    revalued together and nets), else the final value (case b, or another area): a fixed-value line, inward (returns,
    reversals of issues and of transfers into their source) or outward (reversals of earlier receipts, and of earlier transfers
    out of their destination). Pass 3: closing values. Fixed-value lines leave their difference in the closing value:
    target = round(A x (closing q - signed fixed q)) + signed fixed values. Value-only additions in an area with no quantity
    base stay in the closing value when the closing quantity is not zero (they enter the next period through the opening
    value; ADR-0020 rule 12/13 notes, second pass N4). When the closing quantity is zero, the target is 0 and the remainder is
    posted as the rule 13 residual. With no fixed-value line and a remainder beyond the rounding bound, rule 13 as written
    moves the area's issues to the preliminary price (in the exact solve this cannot occur; the random check counts it);
    with fixed-value lines the issues stay at A (the exception note). A negative target, which only fixed-value lines or a
    negative value-only addition can cause, is treated like a closing quantity of zero (R2-S1): the area closes at
    round(A x closing q). Returns ({area: (price, (closing q, target), posted residual)}, line targets);
    cost_period.prelim_switches counts the areas moved to the preliminary price by the bound."""
    order = _order(Q)
    switched = set()
    get = lambda X, key: list(X.get(key, ()))
    while True:
        tg, price, base = {}, {}, {}
        for ar in order:                                   # pass 1
            X = Q[ar]; q0, v0 = op.get(ar, (F(0), F(0)))
            rq = sum(F(q) for q, _ in X["receipts"]); rv = sum(F(v) for _, v in X["receipts"])
            for ln in get(X, "receipt_reversals"):
                if ln["orig"]["period"] == k:
                    rq -= ln["q"]; rv -= ln["v"]
            for src in Q:
                for t in get(Q[src], "transfers"):
                    if t["to"] == ar:
                        rq += t["q"]; rv += tg[t["id"]]
                for r in get(Q[src], "transfer_reversals"):
                    if r["orig"]["to"] == ar and r["orig"]["period"] == k:
                        rq -= r["q"]; rv -= tg[r["orig"]["id"]]
            bq, bv = q0 + rq, v0 + rv
            actual = bv / bq if bq > 0 and bv >= 0 else None       # rule 13: no quantity base, or a negative average
            price[ar] = prelim[ar] if (actual is None or ar in switched) else actual
            for ln in X["issues"] + get(X, "transfers"):
                tg[ln["id"]] = round_amount(ln["q"] * price[ar])
            base[ar] = (actual, bq, bv)
        fin = dict(final); fin.update(tg)
        for ar in order:                                   # pass 2
            for ln in Q[ar]["returns"]:
                o = ln["orig"]
                tg[ln["id"]] = share(fin[o["id"]], o["q"], offs[ln["id"]], ln["q"])
            for ln in get(Q[ar], "reversals") + get(Q[ar], "transfer_reversals"):
                tg[ln["id"]] = fin[ln["orig"]["id"]]
        fin.update(tg)
        res, beyond = {}, []
        for ar in sorted(Q):                               # pass 3
            X = Q[ar]; p = price[ar]; actual, bq, bv = base[ar]
            same = lambda l: l["orig"]["period"] == k and l["orig"]["area"] == ar
            inward = X["returns"] + get(X, "reversals") + get(X, "transfer_reversals")
            outward = [(l["q"], F(l["v"])) for l in get(X, "receipt_reversals") if l["orig"]["period"] != k]
            for src in Q:
                outward += [(r["q"], fin[r["orig"]["id"]]) for r in get(Q[src], "transfer_reversals") if r["orig"]["to"] == ar and r["orig"]["period"] != k]
            fixed_in = [l for l in inward if not same(l)]
            cq = (bq - sum(l["q"] for l in X["issues"] + get(X, "transfers")) + sum(l["q"] for l in inward) - sum(q for q, _ in outward))
            if cq < 0:
                raise ValueError(f"negative closing quantity in area {ar}")
            value = (bv - sum(tg[l["id"]] for l in X["issues"] + get(X, "transfers")) + sum(tg[l["id"]] for l in inward)
                     - sum(v for _, v in outward))
            fixed_q = sum(l["q"] for l in fixed_in) - sum(q for q, _ in outward)
            fixed_v = sum(tg[l["id"]] for l in fixed_in) - sum(v for _, v in outward)
            if cq == 0:
                target = 0
                bound = rounding_bound(len(X["issues"]) + len(get(X, "transfers")), sum(1 for l in X["returns"] if same(l)))
                if not fixed_in and not outward and abs(value) > bound and actual is not None and ar not in switched:
                    beyond.append(ar)
            else:
                target = round_amount(p * (cq - fixed_q)) + fixed_v
                if bq == 0:                  # second pass N4: no quantity base, units on hand: the additions stay in the closing value
                    target += bv
                if target < 0:               # only fixed-value lines or a negative addition make it negative (R2-S1)
                    target = round_amount(p * cq)
            res[ar] = (p, (cq, target), value - target)
        if not beyond:
            return res, tg
        for ar in beyond:                    # rule 13 as written: value beyond rounding left at zero quantity
            switched.add(ar)
            cost_period.prelim_switches += 1


cost_period.prelim_switches = 0


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
            for ln in Q[ar]["issues"] + list(Q[ar].get("transfers", ())):
                cur.setdefault(ln["id"], round_amount(ln["q"] * prelim[k]))
        for ar in sorted(Q):
            for ln in Q[ar]["returns"]:
                o = ln["orig"]
                cur.setdefault(ln["id"], share(cur[o["id"]], o["q"], offs[ln["id"]], ln["q"]))
            for ln in list(Q[ar].get("reversals", ())) + list(Q[ar].get("transfer_reversals", ())):   # at the value its original carries now
                cur.setdefault(ln["id"], cur[ln["orig"]["id"]])
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
    rules 7, 12, 13 and their notes), sharing nothing with cost_period, share, return_offsets, _norm, _order, _prelim or
    rounding_bound but round_amount. It walks the periods in order, keeps a ledger of every line's value and of each
    original's returned quantity, and values each line from its definition: a reversal takes the whole value its original
    has (S5), whether it reverses an issue, a receipt (its document value) or a transfer (both sides); a receipt (0, v) is a
    value-only addition (S6), which stays in the closing value of an area without a quantity base while units remain and is
    the residual only at a zero closing quantity (second pass N4); a transfer is valued at its source area's price and is a
    receipt of its destination at that value; at a zero closing quantity a remainder within half a minor unit per rounded
    issue or transfer plus one per same-period return is rounding (S4). Returns (line values,
    [{area: (price, (closing q, v), residual)}])."""
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
        rows_of = lambda area, key: areas[area].get(key, [])
        made_here = {}                                    # id of an issue or transfer of this period -> its area
        for area in areas:
            for line in rows_of(area, "issues") + rows_of(area, "transfers"):
                made_here[line["id"]] = area
        prelim = {a_: last_avg.get(a_, first_unit.get(a_, F(0))) for a_ in areas}
        # areas whose price feeds another's receipts come first; repeat until all are priced (no cycles in these cases)
        pending = sorted(areas)
        moved = set()
        while True:
            values, avg, has_base, q_base, v_base = {}, {}, {}, {}, {}
            todo = list(pending)
            while todo:
                if all(any(line["to"] == area for src in todo if src != area for line in rows_of(src, "transfers")) for area in todo):
                    raise ValueError("a cycle of transfers within a period")
                for area in list(todo):
                    feeds = [line for src in areas for line in rows_of(src, "transfers") if line["to"] == area]
                    if any(line["id"] not in values for line in feeds):
                        continue
                    q_open, v_open = stock.get(area, (F(0), F(0)))
                    q_in = q_open + sum(F(q) for q, _ in rows_of(area, "receipts"))
                    v_in = v_open + sum(F(v) for _, v in rows_of(area, "receipts"))
                    for line in rows_of(area, "receipt_reversals"):
                        if line["orig"]["period"] == k:   # case (a): the reversed receipt nets out of the receipts
                            q_in -= F(line["q"]); v_in -= F(line["v"])
                    for line in feeds:
                        q_in += F(line["q"]); v_in += values[line["id"]]
                    for src in areas:
                        for line in rows_of(src, "transfer_reversals"):
                            if line["orig"]["to"] == area and line["orig"]["period"] == k:
                                q_in -= F(line["q"]); v_in -= values[line["orig"]["id"]]
                    q_base[area], v_base[area] = q_in, v_in
                    has_base[area] = q_in > 0 and v_in >= 0
                    avg[area] = v_in / q_in if has_base[area] and area not in moved else prelim[area]
                    for line in rows_of(area, "issues") + rows_of(area, "transfers"):
                        values[line["id"]] = round_amount(F(line["q"]) * avg[area])
                    todo.remove(area)
            done = dict(returned)
            for area in sorted(areas):
                for line in areas[area]["returns"]:
                    orig = line["orig"]
                    worth = values[orig["id"]] if orig["id"] in values else ledger[orig["id"]]
                    before = done.get(orig["id"], F(0))
                    after = before + F(line["q"])
                    values[line["id"]] = round_amount(worth * after / F(orig["q"])) - round_amount(worth * before / F(orig["q"]))
                    done[orig["id"]] = after
                for line in rows_of(area, "reversals") + rows_of(area, "transfer_reversals"):
                    oid = line["orig"]["id"]
                    values[line["id"]] = values[oid] if oid in values else ledger[oid]
            result, redo = {}, []
            for area in sorted(areas):
                unit = avg[area]
                rows = areas[area]
                out_lines = rows["issues"] + rows_of(area, "transfers")
                inward = rows["returns"] + rows_of(area, "reversals") + rows_of(area, "transfer_reversals")
                local = lambda l: l["orig"]["id"] in made_here and made_here[l["orig"]["id"]] == area
                kept_in = [l for l in inward if not local(l)]
                kept_out = [(F(l["q"]), F(l["v"])) for l in rows_of(area, "receipt_reversals") if l["orig"]["period"] != k]
                for src in areas:
                    for l in rows_of(src, "transfer_reversals"):
                        if l["orig"]["to"] == area and l["orig"]["period"] != k:
                            kept_out.append((F(l["q"]), ledger[l["orig"]["id"]]))
                left = q_base[area] - sum(F(l["q"]) for l in out_lines) + sum(F(l["q"]) for l in inward) - sum(q for q, _ in kept_out)
                book = v_base[area] - sum(values[l["id"]] for l in out_lines) + sum(values[l["id"]] for l in inward) - sum(v for _, v in kept_out)
                if left == 0:
                    target = 0                            # nothing left: everything remaining is the posted residual
                    limit = F(len(out_lines), 2) + sum(1 for l in rows["returns"] if local(l))
                    if not kept_in and not kept_out and abs(book) > limit and has_base[area] and area not in moved:
                        redo.append(area)
                else:
                    kept_q = sum(F(l["q"]) for l in kept_in) - sum(q for q, _ in kept_out)
                    kept_v = sum(values[l["id"]] for l in kept_in) - sum(v for _, v in kept_out)
                    target = round_amount(unit * (left - kept_q)) + kept_v
                    if q_base[area] == 0:
                        target += v_base[area]            # value-only additions without a quantity base stay with the units on hand
                    if target < 0:
                        target = round_amount(unit * left)   # a negative target closes at the average
                result[area] = (unit, (left, target), book - target)
            if not redo:
                break
            moved |= set(redo)
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


def random_scenario(rng, n_periods=4, areas=("A", "B")):
    """A random multi-period, two-area scenario: receipts (some value-only), issues, partial and cross-area returns of
    issues, reversals of issues that have no return, transfers between the two areas (one direction per period, so no
    cycle within a period), reversals of transfers and of receipts, in the same period or a later one (S2 adversarial
    review, third pass: N5 in the random comparison), never a negative closing quantity."""
    op = {a_: (F(rng.randint(0, 20)), F(rng.randint(0, 400))) for a_ in areas}
    op = {a_: (q, v if q else F(0)) for a_, (q, v) in op.items()}
    lines, ps, qty, n = [], [], {a_: op[a_][0] for a_ in areas}, 0
    left, reversed_, has_ret = {}, set(), set()
    receipts, transfers = [], []                     # reversible receipts and transfers not yet reversed
    for k in range(n_periods):
        P = {a_: dict(receipts=[], issues=[], returns=[], reversals=[], transfers=[], transfer_reversals=[], receipt_reversals=[])
             for a_ in areas}
        for a_ in areas:
            for _ in range(rng.randint(0, 2)):
                q = rng.randint(0, 15); v = rng.randint(0, 40 * max(q, 1))
                P[a_]["receipts"].append((q, v)); qty[a_] += q
                if q > 0:
                    n += 1; receipts.append(dict(id=f"G{n}", period=k, area=a_, q=F(q), v=F(v)))
            avail = qty[a_]
            for _ in range(rng.randint(0, 3)):
                if avail <= 0:
                    break
                q = rng.randint(1, int(avail)); avail -= q; qty[a_] -= q; n += 1
                ln = dict(id=f"I{n}", period=k, area=a_, q=F(q), kind="issue"); P[a_]["issues"].append(ln)
                lines.append(ln); left[ln["id"]] = F(q)
        src, dst = rng.sample(list(areas), 2)            # this period's transfer direction
        for _ in range(rng.randint(0, 2)):
            if qty[src] <= 0:
                break
            q = F(rng.randint(1, int(qty[src]))); qty[src] -= q; qty[dst] += q; n += 1
            tr = dict(id=f"T{n}", period=k, area=src, q=q, to=dst, kind="transfer")
            P[src]["transfers"].append(tr); transfers.append(tr)
        if transfers and rng.random() < 0.3:             # a whole transfer goes back, from its destination into its source
            tr = rng.choice(transfers)
            if qty[tr["to"]] >= tr["q"]:
                transfers.remove(tr); qty[tr["to"]] -= tr["q"]; qty[tr["area"]] += tr["q"]; n += 1
                P[tr["area"]]["transfer_reversals"].append(dict(id=f"TV{n}", q=tr["q"], kind="transfer_reversal", orig=tr))
        if receipts and rng.random() < 0.3:              # a whole receipt is reversed at its document value
            rc = rng.choice(receipts)
            if qty[rc["area"]] >= rc["q"]:
                receipts.remove(rc); qty[rc["area"]] -= rc["q"]; n += 1
                P[rc["area"]]["receipt_reversals"].append(dict(id=f"GV{n}", q=rc["q"], v=rc["v"], kind="receipt_reversal", orig=rc))
        for _ in range(rng.randint(0, 3)):
            cand = [l for l in lines if left[l["id"]] > 0 and l["id"] not in reversed_]
            if not cand:
                break
            o = rng.choice(cand); n += 1
            if rng.random() < 0.3 and o["id"] not in has_ret:      # a reversal of the whole issue, in its own area
                reversed_.add(o["id"]); left[o["id"]] = F(0); qty[o["area"]] += o["q"]
                P[o["area"]]["reversals"].append(dict(id=f"V{n}", q=o["q"], kind="reversal", orig=o))
            else:
                q = F(rng.randint(1, int(left[o["id"]]))); left[o["id"]] -= q; has_ret.add(o["id"])
                to = rng.choice(areas); qty[to] += q
                P[to]["returns"].append(dict(id=f"R{n}", q=q, kind="return", orig=o))
        ps.append(P)
    return ps, op


def check_adversarial_cases():
    """The costing checks of the S2 adversarial review (2026-11-21): the rounding bound at a zero closing quantity (S4),
    reversals (S5), a late landed cost as a value-only receipt addition (S6) and the consequence of sales returns kept at
    their original cost (note N7). Each case is hand-computed and compared with independent_values, its own code path.
    Returns [(ok, name, detail)]."""
    R = []
    same = lambda ps_, op_: naive_periods(ps_, op_) == independent_values(ps_, op_)
    iss = lambda i, k, q, **kw: dict(id=i, period=k, q=F(q), kind="issue", **kw)
    # S4, within the bound: opening 3 for 100, three issues of 1 at 33.33 -> 33 each, remainder 1 <= 3 x 1/2
    s4 = [dict(receipts=[], issues=[iss("A1", 0, 1), iss("A2", 0, 1), iss("A3", 0, 1)], returns=[])]
    f4, n4 = naive_periods(s4, (F(3), F(100)))
    R.append((n4[0][0] == F(100, 3) and [f4[x] for x in ("A1", "A2", "A3")] == [33, 33, 33] and n4[0][1] == (0, 0)
              and n4[0][2] == 1 and rounding_bound(3, 0) == F(3, 2) and same(s4, (F(3), F(100))),
              "S4 within the bound: opening 3 for 100 and three issues of 1 close at quantity 0 with 1 left; 1 is within the bound "
              "3 x 1/2, so it is a rounding residual: the issues stay at the actual average (33 each) and 1 is posted", n4[0]))
    # S4, on the bound: opening 2 for 1, two issues of 1 at 0.5 -> 1 each, remainder -1 = -(2 x 1/2): still rounding
    e4 = [dict(receipts=[], issues=[iss("B1", 0, 1), iss("B2", 0, 1)], returns=[])]
    fe4, ne4 = naive_periods(e4, (F(2), F(1)))
    R.append((fe4["B1"] == fe4["B2"] == 1 and ne4[0][0] == F(1, 2) and ne4[0][2] == -1 and same(e4, (F(2), F(1))),
              "S4 on the bound: opening 2 for 1 and two issues of 1 at 0.5 take 1 each; the remainder -1 equals the bound 2 x 1/2, "
              "so it is still rounding: the issues stay at the actual average and -1 is posted", ne4[0]))
    # S4, beyond the bound: only a fixed-value line can leave it (the kept return of the zero-closing example): issues stay at A
    z = [dict(receipts=[], issues=[iss("X", 0, 10)], returns=[]),
         dict(receipts=[(10, 150)], issues=[iss("Y", 1, 14)], returns=[])]
    z[1]["returns"] = [dict(id="RX", q=F(4), kind="return", orig=z[0]["issues"][0])]
    before = cost_period.prelim_switches
    fz, nz = naive_periods(z, (F(10), F(100)))
    R.append((nz[1][2] == -20 and abs(nz[1][2]) > rounding_bound(1, 0) and fz["Y"] == 210 and nz[1][0] == 15
              and cost_period.prelim_switches == before and same(z, (F(10), F(100))),
              "S4 beyond the bound: a kept return leaves -20 at quantity 0, beyond the bound 1/2; the exception note applies, the "
              "issue of 14 stays at the actual average 15 (210) and -20 is posted; the preliminary price is not used", nz[1]))
    # S5, same period: an internal consumption of 10 and its reversal in P1 net and are revalued together
    c = iss("C", 0, 10)
    r5 = [dict(receipts=[(100, 1400)], issues=[c], returns=[], reversals=[dict(id="CV", q=F(10), kind="reversal", orig=c)])]
    fr5, nr5 = naive_periods(r5, (F(100), F(1000)))
    R.append((nr5[0][0] == 12 and fr5["C"] == fr5["CV"] == 120 and nr5[0][1] == (200, 2400) and nr5[0][2] == 0 and same(r5, (F(100), F(1000))),
              "S5 same period: an issue of 10 and its reversal both take the period's average 12 (120); the pair nets to zero and "
              "the area closes 200 for 2,400 = 200 x 12 as if neither existed", nr5[0]))
    # S5, later period: the reversal in P2 keeps C's final value, outside P2's average; at zero closing quantity -> residual
    c2 = iss("C2", 0, 10)
    l5 = [dict(receipts=[(100, 1400)], issues=[c2], returns=[]),
          dict(receipts=[(10, 300)], issues=[iss("I2", 1, 50)], returns=[], reversals=[dict(id="C2V", q=F(10), kind="reversal", orig=c2)])]
    fl5, nl5 = naive_periods(l5, (F(100), F(1000)))
    a2 = F(2280 + 300, 200)
    l5z = [dict(l5[0]), dict(l5[1], issues=[iss("I2z", 1, 210)])]
    flz, nlz = naive_periods(l5z, (F(100), F(1000)))
    R.append((fl5["C2V"] == fl5["C2"] == 120 and nl5[1][0] == a2 and nl5[1][1] == (160, round_amount(a2 * 150) + 120)
              and nl5[1][2] == 0 and nlz[1][1] == (0, 0) and flz["I2z"] == round_amount(210 * a2)
              and nlz[1][2] == 2580 - round_amount(210 * a2) + 120 and same(l5, (F(100), F(1000))) and same(l5z, (F(100), F(1000))),
              "S5 later period: an issue of 10 in P1 (120 at 12) reversed in P2 keeps 120; P2's average (2,280 + 300)/200 = 12.9 "
              "ignores it, the area closes 160 for 150 x 12.9 + 120 with the difference kept; issuing everything instead closes at "
              "quantity 0, the issue stays at 12.9 and the kept difference 10 x (12 - 12.9) = -9 is the posted residual",
              (nl5[1], nlz[1])))
    # S5, rerun: a backdated receipt in P1 revalues C2; the reversal follows by one value-only line in P2
    cur, _, _, _ = incremental(l5, (F(100), F(1000)), prelim=[F(10), F(10)])
    late = [dict(l5[0], receipts=[(100, 1400), (50, 900)]), l5[1]]
    fll, nll = naive_periods(late, (F(100), F(1000)))
    cur2, out2, adj2, _ = incremental(late, (F(100), F(1000)), prelim=[F(10), F(10)], posted=cur)
    rv = [x for x in adj2 if x[1] == "C2V"]
    R.append((cur == fl5 and cur2 == fll and fll["C2"] == 132 and rv == [(1, "C2V", 12)] and same(late, (F(100), F(1000))),
              "S5 rerun: a backdated receipt of 50 for 900 in P1 moves P1's average to 13.2 and the issue to 132; the reversal in P2 "
              "follows by one value-only line of 12 dated in P2, and every value equals costing from scratch", rv))
    # S6: a late landed cost of 50 as a value-only receipt addition (0, 50)
    base6 = [dict(receipts=[(10, 100)], issues=[iss("G1", 0, 5)], returns=[]),
             dict(receipts=[(10, 120)], issues=[iss("G2", 1, 5)], returns=[])]
    fb, nb = naive_periods(base6, (F(0), F(0)))
    lc = [base6[0], dict(base6[1], receipts=[(10, 120), (0, 50)])]
    fl6, nl6 = naive_periods(lc, (F(0), F(0)))
    R.append((nl6[0] == nb[0] and fl6["G1"] == fb["G1"] == 50 and nb[1][0] == F(34, 3) and nl6[1][0] == F(220, 15)
              and fl6["G2"] == round_amount(5 * F(220, 15)) and same(lc, (F(0), F(0))),
              "S6 later period: a landed cost of 50 for a receipt of P1, posted in P2, enters P2's average ((50 + 120 + 50)/15 = "
              "14.67 instead of 170/15 = 11.33) and leaves P1 untouched (its average 10 and its issue 50 unchanged)", (nb[1][0], nl6[1][0])))
    cur6, _, _, _ = incremental(base6, (F(0), F(0)), prelim=[F(10), F(10)])
    back = [dict(base6[0], receipts=[(10, 100), (0, 50)]), base6[1]]
    fk, nk = naive_periods(back, (F(0), F(0)))
    curk, outk, adjk, _ = incremental(back, (F(0), F(0)), prelim=[F(10), F(10)], posted=cur6)
    R.append((nk[0][0] == 15 and fk["G1"] == 75 and curk == fk and [o[:2] for o in outk] == [o[:2] for o in nk]
              and (0, "G1", 25) in adjk and same(back, (F(0), F(0))),
              "S6 dated in an earlier unlocked period: the same 50 dated in P1 after P1 was costed makes P1 stale; the rerun moves "
              "P1's average to 15 and its issue from 50 to 75 by a value-only line, and P2 follows (rule 14)", nk[0][0]))
    zq = [dict(receipts=[(10, 100)], issues=[iss("H1", 0, 10)], returns=[]), dict(receipts=[(0, 50)], issues=[], returns=[])]
    fq, nq = naive_periods(zq, (F(0), F(0)))
    R.append((nq[1][1] == (0, 0) and nq[1][2] == 50 and nq[1][0] == 10 and same(zq, (F(0), F(0))),
              "S6 zero quantity: a landed cost of 50 posted in P2 when the area holds nothing has no quantity base; rule 13 posts "
              "the 50 as the residual and the area closes 0 for 0", nq[1]))
    # N7: the consequence of sales returns at the original issue cost (the author's decision)
    d = iss("D", 0, 10)
    n7 = [dict(receipts=[], issues=[d], returns=[]),
          dict(receipts=[(10, 100)], issues=[], returns=[dict(id="RD", q=F(5), kind="return", orig=d)]),
          dict(receipts=[(10, 100)], issues=[], returns=[])]
    f7, h7 = naive_periods(n7, (F(10), F(1000)))
    R.append((f7["D"] == 1000 and f7["RD"] == 500 and h7[1][0] == 10 and h7[1][1] == (15, 600) and h7[1][2] == 0
              and h7[2][0] == 28 and same(n7, (F(10), F(1000))),
              "N7 (returns at the original cost): a delivery of 10 at 100 (1,000) in P1; in P2 a receipt of 10 for 100 (average 10) "
              "and a return of 5 of that delivery at 100 each (500): the area closes 15 units for 600, 40 per unit against the "
              "period's average 10, with nothing posted; P3's receipt of 10 for 100 gives the average (600 + 100)/25 = 28",
              (h7[1], h7[2][0])))
    # Random scenarios: cost_period = independent_values; the bound never moves issues to the preliminary price
    import random
    rng = random.Random(20261121); before = cost_period.prelim_switches; bad = []; zero_areas = 0
    kinds = defaultdict(int)                       # line kinds generated, reversals split by same or later period
    for i in range(600):
        ps_, op_ = random_scenario(rng)
        for k_, P_ in enumerate(ps_):
            for X_ in P_.values():
                kinds["transfers"] += len(X_["transfers"])
                for key in ("transfer_reversals", "receipt_reversals"):
                    for l_ in X_[key]:
                        kinds[key + (" same" if l_["orig"]["period"] == k_ else " later")] += 1
        try:
            fa, ha = naive_periods(ps_, op_); fb_, hb = independent_values(ps_, op_)
        except ValueError as e:
            bad.append((i, str(e))); continue
        if fa != fb_ or ha != hb:
            bad.append(i)
        zero_areas += sum(1 for h in ha for a_ in h if h[a_][1][0] == 0)
    R.append((not bad and cost_period.prelim_switches == before and zero_areas > 100 and len(kinds) == 5 and min(kinds.values()) >= 50,
              "random: on 600 random four-period, two-area scenarios with value-only receipts, partial and cross-area returns, "
              "reversals of issues, transfers, and reversals of transfers and of receipts in the same and a later period (third pass), "
              "cost_period and independent_values agree on every line value, price, closing and residual; in "
              f"{zero_areas} area-periods closing at quantity 0 the remainder never exceeds the rounding bound without a fixed-value "
              "line, so the bound never moves issues to the preliminary price", bad[:3] or (zero_areas, dict(kinds))))
    return R


def check_second_pass_cases():
    """The costing checks of the second pass of the S2 adversarial review (2026-11-21): N4, a value-only receipt addition in an
    area whose only quantity came back by returns (the chief architect's decision: it stays in the closing value while units
    remain, and is the rule 13 residual only at a zero closing quantity), and N5, reversals of receipts and of transfers
    (the ADR-0020 rule 7 note: case a, same period, the pair nets; case b, later period, a fixed-value line). Each case is
    hand-computed and compared with independent_values, its own code path. Returns [(ok, name, detail)]."""
    R = []
    same = lambda ps_, op_: naive_periods(ps_, op_) == independent_values(ps_, op_)
    iss = lambda i, k, q, **kw: dict(id=i, period=k, q=F(q), kind="issue", **kw)
    # N4: no quantity base, units on hand from a return: the late landed cost stays in the closing value
    d = iss("D", 0, 10)
    n4 = [dict(receipts=[(10, 100)], issues=[d], returns=[]),
          dict(receipts=[(0, 50)], issues=[], returns=[dict(id="RD", q=F(4), kind="return", orig=d)]),
          dict(receipts=[(6, 60)], issues=[], returns=[])]
    f4, h4 = naive_periods(n4, (F(0), F(0)))
    n4z = [n4[0], dict(n4[1], issues=[iss("D2", 1, 4)]), n4[2]]
    f4z, h4z = naive_periods(n4z, (F(0), F(0)))
    R.append((f4["RD"] == 40 and h4[1][1] == (4, 90) and h4[1][2] == 0 and h4[2][0] == 15 and h4z[1][1] == (0, 0) and h4z[1][2] == 50
              and same(n4, (F(0), F(0))) and same(n4z, (F(0), F(0))),
              "N4 (second pass): P1 receives 10 for 100 and delivers them; in P2 a return of 4 (40, its original cost) is the area's only "
              "quantity and a landed cost of 50 arrives: the area closes 4 units for 90 with no residual, and P3's receipt of 6 for 60 "
              "averages (90 + 60)/10 = 15; issuing the 4 in P2 instead closes at quantity 0 and the 50 is the rule 13 residual",
              (h4[1], h4z[1])))
    # N5, receipt reversal in the same period: it nets out of the receipts
    r1 = dict(id="R1", period=0, area="A", q=F(10), v=F(300))
    s5 = [dict(receipts=[(10, 300)], issues=[iss("E", 0, 5)], returns=[],
               receipt_reversals=[dict(id="R1V", q=F(10), v=F(300), kind="receipt_reversal", orig=r1)])]
    fs5, hs5 = naive_periods(s5, (F(10), F(100)))
    R.append((hs5[0][0] == 10 and fs5["E"] == 50 and hs5[0][1] == (5, 50) and hs5[0][2] == 0 and same(s5, (F(10), F(100))),
              "N5 receipt reversed in its own period: opening 10 for 100, a receipt of 10 for 300 and its reversal net out of the receipts; "
              "the average stays 10, the issue of 5 takes 50, and the area closes 5 for 50", hs5[0]))
    # N5, receipt reversal in a later period: a fixed-value outward line, its difference stays in the closing value
    l5 = [dict(receipts=[(10, 300)], issues=[iss("E1", 0, 5)], returns=[]),
          dict(receipts=[(10, 150)], issues=[], returns=[], receipt_reversals=[dict(id="R1V", q=F(10), v=F(300), kind="receipt_reversal", orig=r1)])]
    fl5, hl5 = naive_periods(l5, (F(10), F(100)))
    l5z = [l5[0], dict(l5[1], issues=[iss("E2", 1, 15)])]
    flz, hlz = naive_periods(l5z, (F(10), F(100)))
    R.append((hl5[0][0] == 20 and hl5[1][0] == 18 and hl5[1][1] == (15, 150) and hl5[1][2] == 0 and flz["E2"] == 270
              and hlz[1][1] == (0, 0) and hlz[1][2] == -120 and same(l5, (F(10), F(100))) and same(l5z, (F(10), F(100))),
              "N5 receipt reversed in a later period: P1 averages (100 + 300)/20 = 20; in P2 a receipt of 10 for 150 gives the average "
              "(300 + 150)/25 = 18, which the reversal (10 units at their document value 300) does not enter; the area closes 15 for "
              "18 x 25 - 300 = 150 with nothing posted; issuing all 15 at 18 instead closes at quantity 0 and -120 is the residual",
              (hl5[1], hlz[1])))
    # N5, transfer and its reversal in the same period: both sides net
    t1 = dict(id="T1", period=0, area="A", q=F(4), to="B", kind="transfer")
    op2 = {"A": (F(10), F(100)), "B": (F(10), F(300))}
    t5 = [{"A": dict(receipts=[], issues=[], returns=[], transfers=[t1], transfer_reversals=[dict(id="T1V", q=F(4), kind="transfer_reversal", orig=t1)]),
           "B": dict(receipts=[], issues=[], returns=[])}]
    ft5, ht5 = naive_periods(t5, op2)
    c5 = [{"A": dict(receipts=[], issues=[], returns=[], transfers=[t1]), "B": dict(receipts=[], issues=[], returns=[])}]
    fc5, hc5 = naive_periods(c5, op2)
    R.append((ft5["T1"] == ft5["T1V"] == 40 and ht5[0]["A"][1] == (10, 100) and ht5[0]["B"] == (30, (10, 300), 0)
              and fc5["T1"] == 40 and hc5[0]["A"][1] == (6, 60) and hc5[0]["B"] == (F(340, 14), (14, 340), 0) and same(t5, op2) and same(c5, op2),
              "N5 transfer reversed in its own period: A (10 for 100) transfers 4 to B (10 for 300) at A's average, 40, and reverses it; "
              "the pair nets in both areas, which close as if neither existed (A 10 for 100, B 10 for 300 at 30); without the reversal "
              "A closes 6 for 60 and B 14 for 340", (ht5[0], hc5[0])))
    # N5, transfer reversed in a later period: inward fixed line in the source, outward fixed line in the destination
    tl = [{"A": dict(receipts=[], issues=[], returns=[], transfers=[t1]), "B": dict(receipts=[], issues=[], returns=[])},
          {"A": dict(receipts=[(10, 200)], issues=[], returns=[], transfer_reversals=[dict(id="T1V", q=F(4), kind="transfer_reversal", orig=t1)]),
           "B": dict(receipts=[], issues=[], returns=[])}]
    ftl, htl = naive_periods(tl, op2)
    R.append((ftl["T1V"] == ftl["T1"] == 40 and htl[1]["A"] == (F(65, 4), (20, 300), 0) and htl[1]["B"] == (F(340, 14), (10, 300), 0) and same(tl, op2),
              "N5 transfer reversed in a later period: P1 transfers 4 from A to B at 40; in P2 A receives 10 for 200, its average "
              "(60 + 200)/16 = 16.25 ignores the reversal, which comes back at 40 and closes A at 16 x 16.25 + 40 = 300 for 20 units; "
              "B sends the 4 back at 40 and closes 10 units for 340 - 40 = 300; nothing is posted in either area", (htl[1]["A"], htl[1]["B"])))
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
    rs = check_issue_returns() + [check_group_currency()] + check_adversarial_cases()
    for ok, name, detail in rs:
        print(("PASS " if ok else "FAIL ") + name + " -- " + str(detail))
    raise SystemExit(0 if all(ok for ok, *_ in rs) else 1)
