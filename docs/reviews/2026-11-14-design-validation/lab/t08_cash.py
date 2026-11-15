"""Scenario: DS-25 cash, bank, receivables and payables (ADR-0048), pure functions (lab finding L-16).

B: the matching cascade `match_bank_line` (rule 9): already-posted documents first; then whole-token references
   within one partner, side and currency (a partial or excess amount settles the referenced items, never another
   item); then the counterparty's bank account (bank code and number) with an exact amount; then a bounded subset;
   shared accounts and ambiguous references go unmatched. Inputs are put in canonical order first, so shuffled
   inputs give the same proposal. Reference scores depend on who owns the paying account: the item's partner
   100 / 80, nobody (counterparty_unverified) at most 85 / 65, another partner (third party) at most 60; neither of
   the last two is auto-posted. Installments: a due-ordered prefix summing exactly scores 100, a single item 90,
   and <reference>-<installment> names one installment (holistic review notes on rule 9).
A: allocation proposals (rule 6).
D: early-payment discounts by the gross-up of rule 7.
P: bad-debt provision by aging bucket (rule 14).
F: the moving-average book rate of a money account (rule 12): the rate of the cumulative recorded balance; an
   outflow that empties the balance takes all of its company amount; the cash floor checked at the posting date and
   every later date for every account without overdraft; a zero foreign balance after any posting (outflow,
   inflow or reversal) sweeps the rest to realized difference; overdraft only on company-currency bank accounts.
K: cash count differences (rule 4).
Not covered: tables, locks, consumers, statement readers, tax evidence.
"""
import random, re
from decimal import Decimal as D, ROUND_HALF_UP
from fractions import Fraction as F
from itertools import combinations
import datetime as dt

RESULTS = []
def check(name, got, want):
    ok = got == want; RESULTS.append((ok, name, str(got))); print(("PASS " if ok else "FAIL ") + f"{name} -- {got}")
def rnd(x, minor=0):
    x = D(x.numerator) / D(x.denominator) if isinstance(x, F) else D(x)
    return x.quantize(D(1).scaleb(-minor), rounding=ROUND_HALF_UP)
d = dt.date.fromisoformat

# ---------------- B: matching cascade ----------------
# open items: id, partner, side the item sits on (debit = receivable, settled by inflows), reference, currency, open amount, due
ITEMS = [
    ("oi1", "P1", "debit", "INV-0101", "VND", 1500000, d("2026-05-10")),
    ("oi2", "P1", "debit", "INV-0102", "VND", 2500000, d("2026-05-20")),
    ("oi3", "P1", "debit", "INV-0103", "VND", 1000000, d("2026-05-25")),
    ("oi4", "P2", "debit", "INV-0201", "VND", 4000000, d("2026-05-15")),
    ("oi5", "P2", "debit", "INV-0202", "VND", 4000000, d("2026-05-18")),
    ("oi6", "P3", "debit", "INV-01", "VND", 1000000, d("2026-05-01")),
    ("oi7", "P1", "credit", "BILL-77", "VND", 2500000, d("2026-05-12")),          # a payable to P1
    ("oi8", "P1", "debit", "INV-0104", "USD", 100, d("2026-05-12")),
]
ACCOUNTS = {("BANK-A", "0123456789"): ["P1"], ("BANK-B", "9988776655"): ["P2"], ("BANK-C", "5555"): ["P1", "P3"]}
POSTED = [  # unmatched posted payment documents of this money account: id, direction, amount, date, reference, partner
    ("pay1", "in", 4000000, d("2026-05-16"), "", "P2"),
]
MAX_SUBSET = 6
TOKEN = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
def ref_tokens(text):
    """Reference-shaped tokens only: at least four characters with a digit (a package may set a stricter pattern)."""
    return {t for t in TOKEN.findall(text.upper()) if len(t) >= 4 and any(ch.isdigit() for ch in t)}
RULES = [("PHI DICH VU", "account:bank_charge"), ("LAI TIEN GUI", "account:interest_income"), ("CONG TY P2", "partner:P2")]   # company rules
def match_bank_line(line, items, posted, accounts, currency="VND", rules=()):
    items = sorted(items, key=lambda i: (i[6], i[0]))           # canonical order: shuffled inputs give the same answer
    posted = sorted(posted, key=lambda p: (p[3], p[0]))
    side = "debit" if line["direction"] == "in" else "credit"
    mine = [i for i in items if i[2] == side and i[4] == currency]
    partners = accounts.get(line.get("counterparty"), [])
    # 1. already posted
    cand = [p for p in posted if p[1] == line["direction"] and p[2] == line["amount"] and abs((p[3] - line["date"]).days) <= 5
            and (p[4] and p[4] in ref_tokens(line["description"]) or p[5] in partners)]
    if cand:
        best = min(cand, key=lambda p: (abs((p[3] - line["date"]).days), p[3], p[0]))
        return ("posted", best[0], [], 95)
    # 2. whole-token references within one partner; <reference>-<installment_number> names one installment
    tokens = ref_tokens(line["description"])
    ref = [i for i in mine if i[3] in tokens or f"{i[3]}-{i[7] if len(i) > 7 else 1}" in tokens]
    if ref:
        if len({i[1] for i in ref}) > 1: return ("unmatched", "ambiguous_reference", [], 0)
        owner = ref[0][1]                                        # untrusted reference: who owns the paying account?
        trust = "" if owner in partners else ("_third_party" if partners else "_unverified")
        cap_exact, cap_partial = {"": (100, 80), "_unverified": (85, 65), "_third_party": (60, 60)}[trust]
        run, prefix = 0, []
        for i in ref:                                            # due-date order: a prefix summing exactly
            run += i[5]; prefix.append(i)
            if run >= line["amount"]: break
        if run == line["amount"]: return ("reference" + trust, owner, [(i[0], i[5]) for i in prefix], min(100, cap_exact))
        single = [i for i in ref if i[5] == line["amount"]]
        if single: return ("reference_single" + trust, owner, [(single[0][0], single[0][5])], min(90, cap_exact))
        out, left = [], line["amount"]
        for i in ref:                                            # oldest due first
            take = min(left, i[5]); out.append((i[0], take)); left -= take
            if left == 0: break
        if left: out.append(("on_account", left))
        return ("reference_partial" + trust, owner, out, cap_partial)
    # company rules, only after steps 1 and 2
    up = line["description"].upper()
    for pattern, target in rules:
        if pattern in up:
            kind, val = target.split(":")
            if kind == "account": return ("rule_account", val, [("account", line["amount"])], 75)
            partners = [val]; break
    # 3. account and exact amount
    if len(partners) > 1: return ("unmatched", "shared_account", [], 0)
    if partners:
        pm = [i for i in mine if i[1] == partners[0]]
        exact = [i for i in pm if i[5] == line["amount"]]
        if exact: return ("account_amount", partners[0], [(exact[0][0], exact[0][5])], 90 if len(exact) == 1 else 60)
        # 4. bounded subset: fewest items, then oldest, then id
        best = None
        for k in range(2, min(len(pm), MAX_SUBSET) + 1):
            for combo in combinations(pm[:MAX_SUBSET], k):
                if sum(i[5] for i in combo) == line["amount"]:
                    key = (k, [i[6] for i in combo], [i[0] for i in combo])
                    if best is None or key < best[0]: best = (key, combo)
            if best: break
        if best: return ("account_subset", partners[0], [(i[0], i[5]) for i in best[1]], 70)
    return ("unmatched", "no_rule", [], 0)
L = lambda desc, amt, cp=None, direction="in", date="2026-05-16": {"description": desc, "amount": amt, "counterparty": cp, "direction": direction, "date": d(date)}
check("B01 an already-posted receipt of the same amount and partner is found first, before any open item",
      match_bank_line(L("ck", 4000000, ("BANK-B", "9988776655")), ITEMS, POSTED, ACCOUNTS)[:2], ("posted", "pay1"))
check("B02 a whole-token reference with the exact amount, paid from the partner's own account", match_bank_line(L("TT INV-0102 thanh toan", 2500000, ("BANK-A", "0123456789")), ITEMS, [], ACCOUNTS), ("reference", "P1", [("oi2", 2500000)], 100))
check("B03 INV-01 does not match inside INV-0102: whole tokens only", match_bank_line(L("pay INV-0102", 1000000, ("BANK-A", "0123456789")), ITEMS, [], ACCOUNTS)[0], "reference_partial")
check("B04 a reference whose amount differs settles that item partly, never another item",
      match_bank_line(L("INV-0101", 1000000, ("BANK-A", "0123456789")), ITEMS, [], ACCOUNTS), ("reference_partial", "P1", [("oi1", 1000000)], 80))
check("B05 more than the referenced item: the rest goes on account", match_bank_line(L("INV-0103", 1200000), ITEMS, [], ACCOUNTS)[2], [("oi3", 1000000), ("on_account", 200000)])
check("B06 references of two partners are ambiguous: unmatched", match_bank_line(L("INV-01 INV-0103", 2000000), ITEMS, [], ACCOUNTS)[:2], ("unmatched", "ambiguous_reference"))
check("B07 an inflow never matches a payable (side), nor an item in another currency",
      (match_bank_line(L("BILL-77", 2500000), ITEMS, [], ACCOUNTS)[0], match_bank_line(L("INV-0104", 100), ITEMS, [], ACCOUNTS)[0]), ("unmatched", "unmatched"))
check("B08 no reference: the counterparty's account and an exact amount", match_bank_line(L("ck", 1000000, ("BANK-A", "0123456789")), ITEMS, [], ACCOUNTS), ("account_amount", "P1", [("oi3", 1000000)], 90))
check("B09 an account shared by two partners: unmatched", match_bank_line(L("ck", 1000000, ("BANK-C", "5555")), ITEMS, [], ACCOUNTS)[:2], ("unmatched", "shared_account"))
check("B10 a sum of items: the fewest, then the oldest", match_bank_line(L("ck", 4000000, ("BANK-A", "0123456789")), ITEMS, [], ACCOUNTS), ("account_subset", "P1", [("oi1", 1500000), ("oi2", 2500000)], 70))
rng = random.Random(25)
lines = [L("ck", 4000000, ("BANK-A", "0123456789")), L("INV-0101 INV-0103", 2500000), L("ck", 4000000, ("BANK-B", "9988776655"), date="2026-06-30"), L("INV-0102", 1000000)]
same = all(len({str(match_bank_line(ln, rng.sample(ITEMS, len(ITEMS)), rng.sample(POSTED, len(POSTED)), ACCOUNTS)) for _ in range(40)}) == 1 for ln in lines)
check("B11 shuffled items and posted documents always give the same proposal", same, True)
check("B12 a short token (thang 5) is not a reference: the exact account match stands", match_bank_line(L("thanh toan thang 5", 1000000, ("BANK-A", "0123456789")), ITEMS + [("oi9", "P1", "debit", "5", "VND", 700000, d("2026-04-01"))], [], ACCOUNTS)[:3], ("account_amount", "P1", [("oi3", 1000000)]))
check("B13 a P1 invoice paid from P2's account: matched with a third-party flag, at most 60", match_bank_line(L("INV-0102", 2500000, ("BANK-B", "9988776655")), ITEMS, [], ACCOUNTS), ("reference_third_party", "P1", [("oi2", 2500000)], 60))
check("B14 a company rule maps a bank fee to an account", match_bank_line(L("Phi dich vu thang 5", 22000), ITEMS, [], ACCOUNTS, rules=RULES)[:2], ("rule_account", "bank_charge"))
check("B15 a company rule names the partner when the account is unknown", match_bank_line(L("CONG TY P2 chuyen tien", 4000000, ("XXX", "1")), ITEMS, [], ACCOUNTS, rules=RULES)[:3], ("account_amount", "P2", [("oi4", 4000000)]))
# untrusted references (holistic review note on rule 9)
check("B16 a reference from an account no partner owns: flagged counterparty_unverified, at most 85",
      match_bank_line(L("TT INV-0102", 2500000), ITEMS, [], ACCOUNTS), ("reference_unverified", "P1", [("oi2", 2500000)], 85))
check("B17 the same for a partial amount: at most 65",
      match_bank_line(L("INV-0101", 1000000), ITEMS, [], ACCOUNTS), ("reference_partial_unverified", "P1", [("oi1", 1000000)], 65))
check("B18 an account registered to no partner counts as unknown",
      match_bank_line(L("INV-0102", 2500000, ("BANK-Z", "000")), ITEMS, [], ACCOUNTS)[0::3], ("reference_unverified", 85))
check("B19 another partner's account in the partial branch: third party, at most 60",
      match_bank_line(L("INV-0101", 1000000, ("BANK-B", "9988776655")), ITEMS, [], ACCOUNTS), ("reference_partial_third_party", "P1", [("oi1", 1000000)], 60))
def auto_post_eligible(res):
    """An enabled auto-post rule may consider only matches whose paying account belongs to the item's partner."""
    return res[0] != "unmatched" and not res[0].endswith(("_unverified", "_third_party"))
check("B20 unverified and third-party drafts are never auto-posted; a verified one may be",
      [auto_post_eligible(match_bank_line(ln, ITEMS, [], ACCOUNTS)) for ln in (L("TT INV-0102", 2500000), L("INV-0102", 2500000, ("BANK-B", "9988776655")), L("INV-0102", 2500000, ("BANK-A", "0123456789")))],
      [False, False, True])
# installments share their invoice's reference (holistic review note on rule 9)
INST = [("oi21", "P4", "debit", "INV-0301", "VND", 3000000, d("2026-05-10"), 1), ("oi22", "P4", "debit", "INV-0301", "VND", 3000000, d("2026-06-10"), 2),
        ("oi23", "P4", "debit", "INV-0301", "VND", 4000000, d("2026-07-10"), 3)]
P4ACC = ("BANK-D", "4444"); ACC4 = dict(ACCOUNTS); ACC4[P4ACC] = ["P4"]
check("B21 the first installment's amount settles it at 100", match_bank_line(L("INV-0301", 3000000, P4ACC), ITEMS + INST, [], ACC4), ("reference", "P4", [("oi21", 3000000)], 100))
check("B22 a due-ordered prefix summing exactly settles both installments at 100", match_bank_line(L("INV-0301", 6000000, P4ACC), ITEMS + INST, [], ACC4), ("reference", "P4", [("oi21", 3000000), ("oi22", 3000000)], 100))
check("B23 a later installment alone equals the amount: settled at 90", match_bank_line(L("INV-0301", 4000000, P4ACC), ITEMS + INST, [], ACC4), ("reference_single", "P4", [("oi23", 4000000)], 90))
check("B24 INV-0301-2 names the second installment only", match_bank_line(L("TT INV-0301-2", 3000000, P4ACC), ITEMS + INST, [], ACC4), ("reference", "P4", [("oi22", 3000000)], 100))
check("B25 an installment token with a short amount settles that installment partly", match_bank_line(L("INV-0301-3", 1000000, P4ACC), ITEMS + INST, [], ACC4), ("reference_partial", "P4", [("oi23", 1000000)], 80))
same4 = all(len({str(match_bank_line(ln, rng.sample(ITEMS + INST, len(ITEMS) + len(INST)), [], ACC4)) for _ in range(40)}) == 1
            for ln in (L("INV-0301", 4000000, P4ACC), L("INV-0301", 6000000, P4ACC), L("INV-0301-2", 3000000, P4ACC)))
check("B26 shuffled installments always give the same proposal", same4, True)

# ---------------- A: allocation proposals ----------------
def propose_allocation(amount, items):
    items = sorted(items, key=lambda i: (i[6], i[0]))
    exact = [i for i in items if i[5] == amount]
    if exact: return [(exact[0][0], amount)]
    out, left = [], amount
    for i in items:
        if left <= 0: break
        take = min(left, i[5]); out.append((i[0], take)); left -= take
    if left > 0: out.append(("on_account", left))
    return out
P1 = [i for i in ITEMS if i[1] == "P1" and i[2] == "debit" and i[4] == "VND"]
check("A01 an exact amount settles that item", propose_allocation(2500000, P1), [("oi2", 2500000)])
check("A02 otherwise oldest due first, the last partly", propose_allocation(3000000, P1), [("oi1", 1500000), ("oi2", 1500000)])
check("A03 an overpayment ends on account (ADR-0026 rule 8)", propose_allocation(6000000, P1), [("oi1", 1500000), ("oi2", 2500000), ("oi3", 1000000), ("on_account", 1000000)])

# ---------------- D: early-payment discounts (rule 7) ----------------
def settle_with_discount(open_amount, cash, percent, discount_due, value_date, minor=0):
    """Cash c settles round(c / (1 - p/100)), capped at the open amount; the discount is the rest of that share."""
    if value_date > discount_due: return D(cash), D(0)
    settled = min(rnd(F(cash) / (1 - F(percent) / 100), minor), D(open_amount))
    return settled, settled - D(cash)
check("D01 9,800,000 in time at 2% settles 10,000,000 with a 200,000 discount", settle_with_discount(10000000, 9800000, 2, d("2026-05-10"), d("2026-05-10")), (D(10000000), D(200000)))
check("D02 late: no discount, the cash settles itself", settle_with_discount(10000000, 9800000, 2, d("2026-05-10"), d("2026-05-11")), (D(9800000), D(0)))
check("D03 a partial payment of 3,333,333 at 1.5% settles 3,384,094 with a 50,761 discount", settle_with_discount(10000000, 3333333, F(3, 2), d("2026-05-10"), d("2026-05-10")), (D(3384094), D(50761)))
check("D04 the cap: paying more than needed settles at most the open amount", settle_with_discount(10000000, 9900000, 2, d("2026-05-10"), d("2026-05-01")), (D(10000000), D(100000)))

# ---------------- P: bad-debt provision ----------------
BUCKETS = [(180, 365, 30), (365, 730, 50), (730, 1095, 70), (1095, 10 ** 6, 100)]    # regime, unverified
def required_allowance(items, on):
    total = F(0); per = []
    for iid, open_company_amount, due in items:
        days = (on - due).days
        pct = next((p for lo, hi, p in BUCKETS if lo <= days < hi), 0)
        per.append((iid, days, pct)); total += F(open_company_amount) * pct / 100
    return rnd(total), per
req, per = required_allowance([("a", 100000000, d("2025-10-01")), ("b", 50000000, d("2024-12-31")), ("c", 20000000, d("2026-05-01"))], d("2026-06-30"))
check("P01 per-item buckets: 272 days 30%, 546 days 50%, 60 days 0%", [p[2] for p in per], [30, 50, 0])
check("P02 required allowance 55,000,000; the entry posts the difference from 40,000,000", (req, req - D(40000000)), (D(55000000), D(15000000)))

# ---------------- F: moving-average book rate ----------------
class MoneyAccount:
    def __init__(self, is_cash, overdraft=False, foreign=True):
        if overdraft and (is_cash or foreign): raise ValueError("overdraft_not_allowed")     # banks in company currency only
        self.lines, self.is_cash, self.overdraft, self.realized = [], is_cash, overdraft, F(0)   # (date, seq, fc, lc)
    def sweep(self, on):
        """Whenever the foreign balance is zero, the remaining company amount goes to realized exchange difference."""
        fc, lc = self.cumulative()
        if fc == 0 and lc != 0:
            self.lines.append((on, len(self.lines), F(0), -lc)); self.realized += -lc
    def cumulative(self): return sum((l[2] for l in self.lines), F(0)), sum((l[3] for l in self.lines), F(0))
    def floor_ok(self, extra):
        ls = sorted(self.lines + [extra], key=lambda l: (l[0], l[1])); run = F(0)
        for l in ls:
            run += l[2]
            if run < 0: return False
        return True
    def inflow(self, on, fc, rate):
        self.lines.append((on, len(self.lines), F(fc), F(rnd(F(fc) * F(rate))))); self.sweep(on)
    def reverse(self, seq, on=None):
        """A reversal mirrors the line on the original's date; its sweep, if any, is dated on the reversal's posting date."""
        l = self.lines[seq]
        if not self.overdraft and not self.floor_ok((l[0], len(self.lines), -l[2], F(0))): return "money_account_negative"
        self.lines.append((l[0], len(self.lines), -l[2], -l[3])); self.sweep(on or l[0])
    def outflow(self, on, fc, actual_rate):
        fc = F(fc)
        if not self.overdraft and not self.floor_ok((on, len(self.lines), -fc, F(0))): return "money_account_negative"
        bfc, blc = self.cumulative()
        covered = min(fc, max(bfc, F(0)))
        if covered == bfc and covered > 0: lc_cov = blc                                  # empties the balance: all of it
        else: lc_cov = F(rnd(covered * blc / bfc)) if covered > 0 else F(0)
        lc_out = lc_cov + F(rnd((fc - covered) * F(actual_rate)))                        # beyond the balance: settlement rate
        self.lines.append((on, len(self.lines), -fc, -lc_out)); self.sweep(on)
        return lc_out, F(rnd(fc * F(actual_rate))) - lc_out
m = MoneyAccount(False); m.inflow(d("2026-05-02"), 1000, 25000); m.inflow(d("2026-05-05"), 1000, 25400)
check("F01 1,000 @25,000 + 1,000 @25,400; paying 500 at 25,600: book 12,600,000, realized 200,000", m.outflow(d("2026-05-10"), 500, 25600), (F(12600000), F(200000)))
c = MoneyAccount(True); c.inflow(d("2026-05-02"), 100, 1); c.inflow(d("2026-05-10"), 100, 1); c.outflow(d("2026-05-11"), 150, 1)
check("F02 a backdated cash outflow that would make an earlier date negative is refused (in 100 May 2, in 100 May 10, out 150 May 11, then out 100 May 5)",
      c.outflow(d("2026-05-05"), 100, 1), "money_account_negative")
r = MoneyAccount(False); r.inflow(d("2026-05-01"), 100, 25000); r.inflow(d("2026-05-10"), 100, 26000); r.outflow(d("2026-05-11"), 100, 25500); r.outflow(d("2026-05-05"), 100, 25000)
check("F03 a backdated outflow emptying the balance takes all of its company amount: no residual", r.cumulative(), (F(0), F(0)))
try:
    MoneyAccount(False, overdraft=True); refused = False
except ValueError: refused = True
check("F04 overdraft is not allowed on a foreign-currency money account in Phase 1", refused, True)
v = MoneyAccount(False, overdraft=True, foreign=False); v.inflow(d("2026-05-01"), 100, 1); v.outflow(d("2026-05-02"), 300, 1)
check("F06 a company-currency bank account with overdraft may go below zero", v.cumulative(), (F(-200), F(-200)))
g = MoneyAccount(False); g.inflow(d("2026-05-01"), 100, 25000); g.inflow(d("2026-05-10"), 100, 26000); g.outflow(d("2026-05-11"), 100, 25500); g.reverse(1, d("2026-05-20"))
check("F07 a reversed inflow that leaves the foreign balance at zero sweeps the residual to realized difference", (g.cumulative(), g.realized), ((F(0), F(0)), F(50000)))
b = MoneyAccount(False); b.inflow(d("2026-05-02"), 100, 25000); b.outflow(d("2026-05-10"), 100, 25000)
check("F08 a bank account without overdraft has the same all-date floor as cash", b.outflow(d("2026-05-05"), 50, 25000), "money_account_negative")
check("F05 cash may not go negative", MoneyAccount(True).outflow(d("2026-05-03"), 1, 1), "money_account_negative")

# ---------------- K: cash count ----------------
def cash_count(book, counted):
    diff = D(counted) - D(book)
    return ("cash_surplus", diff) if diff > 0 else (("cash_shortage", -diff) if diff < 0 else (None, D(0)))
check("K01 counted above book: cash surplus", cash_count(15200000, 15250000), ("cash_surplus", D(50000)))
check("K02 counted below book: cash shortage", cash_count(15200000, 15180000), ("cash_shortage", D(20000)))
check("K03 equal: no adjustment document", cash_count(1000, 1000), (None, D(0)))

print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
