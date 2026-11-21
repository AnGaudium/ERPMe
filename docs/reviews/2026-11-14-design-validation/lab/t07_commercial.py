"""Scenario: DS-22 commercial documents (ADR-0047), pure functions (lab finding L-15).

G: GR/IR per purchase order line by unit positions (ADR-0047 rule 13), with postings as differences of rounded
   cumulative values: random sequences of receipts, invoices, returns, credit notes, reversals and order price
   changes, in a currency without decimals and one with two. The balance always equals
   round(V(0, I)) - round(V(0, R)), so it is zero whenever received equals invoiced (INV-37, INV-92). Reversals are
   allowed only for the latest posting of a side. A position keeps its first price for the life of the line.
P: the pricing procedure (rules 16-17): list price, manual price, promotion, manual discount, the net unit price
   stored at the unit-price scale and the amount computed from it, the document discount percentage allocated by
   largest remainder, free goods, and the policy inputs (discount, margin, below cost after the document discount).
R: correction limits and EC-20 (rule 20).
M: three-way match tolerances (rule 14).
C: credit exposure, holds and the release recorded by an approval (rule 18).
Not covered here: the database side (tables, locks, consumers), foreign-currency residuals, and tax.
"""
import random
from decimal import Decimal as D, ROUND_HALF_UP
from fractions import Fraction as F

RESULTS = []
def check(name, got, want):
    ok = got == want; RESULTS.append((ok, name, str(got))); print(("PASS " if ok else "FAIL ") + f"{name} -- {got}")
def rnd(x, minor):
    return F((D(x.numerator) / D(x.denominator)).quantize(D(1).scaleb(-minor), rounding=ROUND_HALF_UP))

# ---------------- G: GR/IR by unit positions ----------------
class GrIrLine:
    """One purchase order line; positions in the inventory unit, priced once when first posted."""
    def __init__(self, price, minor=0):
        self.price, self.minor, self.layers, self.R, self.I, self.balance = F(price), minor, [], F(0), F(0), F(0)
        self.side = {"R": [], "I": []}        # postings per side: [doc, from, to, amount, reversed, sign]
        self.n = 0
    def frontier(self): return self.layers[-1][1] if self.layers else F(0)
    def _extend(self, upto):
        if upto > self.frontier(): self.layers.append((self.frontier(), upto, self.price))
    def V(self, b):
        return sum(((min(b, hi) - lo) * p for lo, hi, p in self.layers if b > lo), F(0))
    def cum(self, b): return rnd(self.V(b), self.minor)
    def _post(self, side, q, sign):
        a = self.R if side == "R" else self.I
        b = a + sign * q
        if sign > 0: self._extend(b)
        amt = self.cum(max(a, b)) - self.cum(min(a, b))
        self.n += 1; self.side[side].append([self.n, min(a, b), max(a, b), amt, False, sign])
        if side == "R": self.R = b
        else: self.I = b
        self.balance += (-amt if side == "R" else amt) * sign     # receipts credit GR/IR, invoices debit; returns and credits the opposite
        return amt
    def receipt(self, q): return self._post("R", q, +1)
    def invoice(self, q, unit):
        amt = self._post("I", q, +1); return amt, rnd(q * F(unit), self.minor) - amt
    def return_(self, q): return self._post("R", q, -1)
    def credit(self, q): return self._post("I", q, -1)
    def reverse(self, side, doc):
        live = [p for p in self.side[side] if not p[4]]
        if not live or live[-1][0] != doc: return "reversal_not_latest"
        p = live[-1]; p[4] = True
        q, sign, amt = p[2] - p[1], p[5], p[3]
        if side == "R": self.R -= sign * q
        else: self.I -= sign * q
        self.balance -= (-amt if side == "R" else amt) * sign       # the exact mirror
        return amt
    def expected(self): return self.cum(self.I) - self.cum(self.R)

rng = random.Random(22)
ident = steps = zero_ok = zero_n = rev_ok = rev_rejected = 0
N = 600
for n in range(N):
    minor = rng.choice([0, 2])
    line = GrIrLine(rng.choice([100, 120, F(1001, 10), F(100, 3)]), minor)
    for _ in range(rng.randint(3, 16)):
        op = rng.random(); q = F(rng.randint(1, 12), rng.choice([1, 1, 2, 3, 7]))
        if op < 0.26: line.receipt(q)
        elif op < 0.52: line.invoice(q, line.price + rng.choice([0, 0, 5, -3]))
        elif op < 0.62 and line.R > 0: line.return_(min(q, line.R))
        elif op < 0.72 and line.I > 0: line.credit(min(q, line.I))
        elif op < 0.84:
            side = rng.choice("RI"); live = [p for p in line.side[side] if not p[4]]
            if live:
                target = rng.choice(live)[0]
                before = (line.R, line.I)
                r = line.reverse(side, target)
                if r == "reversal_not_latest": rev_rejected += 1; rev_ok += (line.R, line.I) == before
                else: rev_ok += 1
        else: line.price = F(rng.choice([100, 110, 125, F(997, 10), F(200, 7)]))
        steps += 1; ident += line.balance == line.expected()
        if line.R == line.I: zero_n += 1; zero_ok += line.balance == 0
check(f"G01 {N} random sequences ({steps} steps), rounded postings in 0 or 2 decimals: the balance always equals round(V(I)) - round(V(R))", ident, steps)
check(f"G02 GR/IR is zero at every step where received equals invoiced ({zero_n} steps), INV-37", zero_ok, zero_n)
check(f"G03 reversals of the latest posting mirror it; others are refused and change nothing ({rev_rejected} refused)", rev_ok > 0 and rev_rejected > 0, True)
l = GrIrLine(100); l.receipt(F(1, 3)); l.receipt(F(1, 3)); l.receipt(F(1, 3)); a, d = l.invoice(F(1), 100)
check("G04 three receipts of 1/3 at 100 VND post 33, 34, 33 (rounded cumulative values); the invoice of 1 clears 100 and GR/IR is 0",
      (l.side["R"][0][3], l.side["R"][1][3], l.side["R"][2][3], a, l.balance), (F(33), F(34), F(33), F(100), F(0)))
l = GrIrLine(100); l.receipt(10); l.receipt(10)
check("G05 a single-price line: returning 5 debits GR/IR at the receipt price", l.return_(5), F(500))
l = GrIrLine(100); l.receipt(10); l.price = F(120); l.receipt(10)
a, d = l.invoice(15, 130)
check("G06 receipt 10 @100, change order to 120, receipt 10 @120; invoice 15 @130 clears 10x100 + 5x120, difference 350", (a, d, l.balance), (F(1600), F(350), F(-600)))
l = GrIrLine(100); a, d = l.invoice(8, 100); l.price = F(110); r = l.receipt(8)
check("G07 invoice first at 100, then a change order to 110: the receipt still credits at 100", (a, r, l.balance), (F(800), F(800), F(0)))
l = GrIrLine(100); l.receipt(10); l.price = F(120); l.receipt(10); l.invoice(10, 120); l.return_(5); l.invoice(5, 120)
alt = F(-(10 * 100 + 10 * 120) + 10 * 100 + 5 * 100 + 5 * 120)   # the same steps with the return priced at its own receipt (100)
check("G08 receipts 10 @100 and 10 @120, invoice 10, return 5, invoice 5: positions leave 0; the receipt-price rule would leave -100",
      (l.R == l.I, l.balance, alt), (True, F(0), F(-100)))
l = GrIrLine(100); l.receipt(10); l.price = F(120); l.receipt(10)
first = l.side["R"][0][0]
check("G09 reversing the first of two receipts is refused (not the latest); reversing the second mirrors 1,200",
      (l.reverse("R", first), l.reverse("R", l.side["R"][1][0]), l.balance), ("reversal_not_latest", F(1200), F(-1000)))
l = GrIrLine(100); l.receipt(10); l.invoice(10, 100); l.return_(10); l.credit(10); l.price = F(90); r = l.receipt(10)
check("G10 positions keep their first price: after a full return and credit, a replacement receipt posts at 100 although the order now says 90", (r, l.balance), (F(1000), F(-1000)))

# ---------------- P: pricing procedure ----------------
SCALE = D("0.0000000001")
def round_amount(x, minor=0):
    x = D(x.numerator) / D(x.denominator) if isinstance(x, F) else D(x)
    return x.quantize(D(1).scaleb(-minor), rounding=ROUND_HALF_UP)
def round_price(x):
    return (D(x.numerator) / D(x.denominator)).quantize(SCALE, rounding=ROUND_HALF_UP)
PROMOS = [  # code, priority, kind, scope item, min qty, value, free item, (per, give)
    ("P10OFF", 10, "percent", "A", 10, F(10), None, None),
    ("P5K", 20, "amount_per_unit", "A", 1, F(5000), None, None),
    ("B10G1", 5, "free_goods", "B", 10, None, "B", (10, 1)),
]
def best_promotion(item, qty):
    elig = [p for p in PROMOS if p[3] == item and qty >= p[4]]
    return min(elig, key=lambda p: (-p[1], p[0])) if elig else None
def price_line(item, qty, list_price, manual_price=None, manual_discount=F(0)):
    steps = [("list_price", list_price)]
    base = F(manual_price) if manual_price is not None else list_price
    if manual_price is not None: steps.append(("manual_price", base))
    promo = best_promotion(item, qty); free = None; net = base
    if promo and promo[2] == "percent": net = net * (1 - promo[5] / 100); steps.append(("promotion", promo[0]))
    elif promo and promo[2] == "amount_per_unit": net = net - promo[5]; steps.append(("promotion", promo[0]))
    elif promo and promo[2] == "free_goods":
        per, give = promo[7]; free = (promo[6], (qty // per) * give, promo[0]); steps.append(("promotion", promo[0]))
    if manual_discount: net = net * (1 - manual_discount / 100); steps.append(("manual_discount", manual_discount))
    stored = round_price(net)                                  # stored at the unit-price scale
    return {"item": item, "qty": qty, "list": list_price, "net_unit_price": stored, "amount": round_amount(stored * qty), "steps": steps, "free": free,
            "outside_list": list_price is None or (manual_price is not None and F(manual_price) != list_price), "is_free": False}
def free_line(item, qty, list_price):
    return {"item": item, "qty": qty, "list": list_price, "net_unit_price": D(0), "amount": D(0), "steps": [("free_of_charge", None)],
            "free": None, "outside_list": False, "is_free": True}
def allocate_percent(pct, lines, minor=0):
    """Header discount percentage: total rounded once, allocated by largest remainder in minor units; ties to the earlier line."""
    amts = [F(str(l["amount"])) for l in lines]; tot = sum(amts)
    if tot == 0: return [0] * len(lines)
    unit = F(1, 10 ** minor)
    total = F(str(round_amount(tot * F(pct) / 100, minor)))
    raw = [total * a / tot / unit for a in amts]
    floors = [int(r) for r in raw]; rest = int(total / unit) - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:rest]: floors[i] += 1
    return [F(f) * unit for f in floors]
a = price_line("A", 5, F(100000))
check("P01 5 of A at list 100,000: the 5,000 amount promotion (priority 20) applies", (a["net_unit_price"], a["amount"], a["steps"][-1]), (D("95000.0000000000"), D(475000), ("promotion", "P5K")))
check("P02 12 of A: both promotions eligible; the higher priority P5K wins", price_line("A", 12, F(100000))["steps"][-1], ("promotion", "P5K"))
a = price_line("A", 3, F(100000), manual_discount=F(3))
check("P03 promotion then manual discount: (100,000 - 5,000) x 0.97 = 92,150", (a["net_unit_price"], a["amount"]), (D("92150.0000000000"), D(276450)))
a = price_line("C", 3, F(1, 3) * 100000)
check("P04 a price of 100,000/3 is stored at ten decimals and the amount is computed from the stored price (INV-93)",
      (a["net_unit_price"], a["amount"], round_amount(a["net_unit_price"] * 3)), (D("33333.3333333333"), D(100000), D(100000)))
a = price_line("C", 1, F(50000), manual_price=48000)
check("P05 a manual price below the list is outside the list", (a["outside_list"], a["net_unit_price"]), (True, D("48000.0000000000")))
check("P06 no list price is outside the list", price_line("C", 1, None, manual_price=1000)["outside_list"], True)
b = price_line("B", 25, F(20000))
check("P07 buy 10 get 1: 25 of B give 2 free B on a generated line", b["free"], ("B", 2, "B10G1"))
L3 = [price_line("A", 5, F(100000)), price_line("A", 3, F(100000), manual_discount=F(3)), price_line("C", 7, F(33333), manual_discount=F(1))]
alloc = allocate_percent(1, L3)
check("P08 a 1% document discount: the total is rounded once and allocated by largest remainder", ([int(x) for x in alloc], sum(alloc)), ([4750, 2764, 2310], F(9824)))
check("P09 ties go to the earlier line; a zero total allocates nothing", (allocate_percent(F(1, 3), [{"amount": D(100)}] * 3), allocate_percent(5, [{"amount": D(0)}])), ([F(1), F(0), F(0)], [0]))
def policy_inputs(lines, pct, cost):
    paid = [l for l in lines if not l["is_free"]]
    alloc = dict(zip([id(l) for l in paid], allocate_percent(pct, paid)))
    net_of = lambda l: F(str(l["amount"])) - alloc.get(id(l), 0)
    gross = sum(F(l["qty"]) * (l["list"] if l["list"] is not None else F(str(l["net_unit_price"]))) for l in lines)
    net = sum(net_of(l) for l in lines)
    known = all(cost.get(l["item"]) is not None for l in lines)
    c = sum(F(l["qty"]) * cost[l["item"]] for l in lines) if known else None
    below = any(not l["is_free"] and cost.get(l["item"]) is not None and net_of(l) / l["qty"] < cost[l["item"]] for l in lines)
    return {"discount_percent": round_price((gross - net) / gross * 100), "margin_percent": None if c is None else round_price((net - c) / net * 100),
            "is_price_below_cost": below, "is_price_outside_list": any(l["outside_list"] for l in lines), "cost_known": known}
L1 = [price_line("A", 5, F(100000)), price_line("D", 2, F(60000))]
check("P10 D at 60,000 against a cost of 59,500 is not below cost before a document discount",
      policy_inputs(L1, 0, {"A": F(80000), "D": F(59500)})["is_price_below_cost"], False)
check("P11 ... but a 2% document discount takes it below cost after allocation (the policy uses the amount after it)",
      policy_inputs(L1, 2, {"A": F(80000), "D": F(59500)})["is_price_below_cost"], True)
L2 = [price_line("B", 25, F(20000)), free_line("B", 2, F(20000))]
pi = policy_inputs(L2, 0, {"B": F(15000)})
check("P12 free goods: not below cost, counted in the discount at their list price, their cost in the margin",
      (pi["is_price_below_cost"], pi["discount_percent"], pi["margin_percent"]), (False, D("7.4074074074"), D("19.0000000000")))
check("P13 an unknown cost leaves margin unknown (the decision needs a human)", policy_inputs(L1, 0, {"A": F(80000), "D": None})["margin_percent"], None)

# ---------------- R: corrections and EC-20 ----------------
class OrderLine:
    def __init__(self, ordered): self.ordered, self.delivered, self.returned, self.invoiced, self.credited, self.return_credited = F(ordered), F(0), F(0), F(0), F(0), F(0)
    def delivered_net(self): return self.delivered - self.returned
    def invoiced_net(self): return self.invoiced - self.credited
    def deliver(self, q):
        if self.delivered_net() + q > self.ordered: return "quantity_exceeds_open"
        self.delivered += q
    def invoice(self, q):
        if self.invoiced_net() + q > self.delivered_net(): return "invoice_exceeds_delivered"
        self.invoiced += q
    def return_(self, q):
        if q > self.delivered_net(): return "correction_exceeds_original"
        self.returned += q
    def sales_return_due(self): return max(F(0), self.invoiced_net() - self.delivered_net())      # the work item's quantity
    def sales_return(self, q):
        """A sales_return credits returned goods: within returned not yet credited, and within invoiced net."""
        if q > self.returned - self.return_credited or q > self.invoiced_net(): return "correction_exceeds_original"
        self.credited += q; self.return_credited += q
ol = OrderLine(10); ol.deliver(10); ol.invoice(6); ol.return_(5)
check("R01 EC-20: 10 delivered, 6 invoiced, 5 returned: a sales return for 1 is due (work item)", ol.sales_return_due(), F(1))
check("R02 after it, delivered net 5 equals invoiced net 5 and nothing is due", (ol.sales_return(1), ol.delivered_net() - ol.invoiced_net(), ol.sales_return_due()), (None, F(0), F(0)))
ol = OrderLine(10); ol.deliver(10); ol.invoice(6); ol.return_(3)
check("R03 3 returned of 4 uninvoiced: nothing due, 1 remains to invoice", (ol.sales_return_due(), ol.delivered_net() - ol.invoiced_net()), (F(0), F(1)))
check("R04 a return above the delivered net is refused", ol.return_(8), "correction_exceeds_original")
check("R05 an invoice above the delivered net is refused (stock lines)", ol.invoice(2), "invoice_exceeds_delivered")
check("R06 a sales return above the returned quantity is refused", ol.sales_return(4), "correction_exceeds_original")
check("R07 a delivery above the open quantity is refused", OrderLine(5).deliver(6), "quantity_exceeds_open")

# ---------------- M: three-way match ----------------
def match(ordered, received_net, invoiced_net, order_price, invoice_price, qty_tol=F(0), price_tol_pct=F(0), price_tol_amt=F(0), require_receipt=False):
    out = []
    if invoiced_net > ordered * (1 + qty_tol / 100): out.append("match_quantity_exceeded")
    if require_receipt and invoiced_net > received_net: out.append("match_quantity_exceeded")
    if abs(F(invoice_price) - F(order_price)) > max(F(order_price) * price_tol_pct / 100, price_tol_amt): out.append("match_price_difference")
    return sorted(set(out))
check("M01 within zero tolerance: no difference", match(F(10), F(10), F(10), 100, 100), [])
check("M02 price 101 vs 100 with zero tolerance", match(F(10), F(10), F(10), 100, 101), ["match_price_difference"])
check("M03 within 2% tolerance", match(F(10), F(10), F(10), 100, 101, price_tol_pct=F(2)), [])
check("M04 an amount tolerance covers a small absolute difference", match(F(10), F(10), F(10), 1000, 1300, price_tol_pct=F(1), price_tol_amt=F(500)), [])
check("M05 invoicing 11 of 10 ordered is beyond tolerance; invoicing before receipt is not, unless receipts are required",
      (match(F(10), F(10), F(11), 100, 100), match(F(10), F(0), F(5), 100, 100), match(F(10), F(0), F(5), 100, 100, require_receipt=True)),
      (["match_quantity_exceeded"], [], ["match_quantity_exceeded"]))

# ---------------- C: credit exposure and holds ----------------
def exposure(parts, rates, limit_currency):
    per_cur = {}
    for part in parts:
        for cur, amt in part.items(): per_cur[cur] = per_cur.get(cur, F(0)) + F(amt)
    total = sum(a * F(rates[(c, limit_currency)]) if c != limit_currency else a for c, a in per_cur.items())
    return per_cur, round_amount(total)
pc, tot = exposure([{"VND": 300000000, "USD": 2000}, {"VND": 50000000}, {"VND": 20000000}, {"USD": 1000}], {("USD", "VND"): 25400}, "VND")
check("C01 exposure per currency, converted to the limit currency at the transaction rate", (pc["USD"], tot), (F(3000), D(446200000)))
def holds(orders, exposure_total, limit):
    return sorted(o["id"] for o in orders if exposure_total > limit and not o.get("released"))
orders = [{"id": 1}, {"id": 2, "released": True}, {"id": 3, "released": True, "note": "approved at Submit over the limit"}]
check("C02 over the limit: an unreleased order is held; one released, or approved over the limit, is not", holds(orders, D(446200000), D(400000000)), [1])
check("C03 under the limit: nothing is held", holds([{"id": 1}], D(300000000), D(400000000)), [])

print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
raise SystemExit(0 if all(r[0] for r in RESULTS) else 1)   # a failing check fails the lab
