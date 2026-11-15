"""Scenario: DS-26 statutory reporting (ADR-0049), pure functions (lab finding L-17).

G: the line grammar (rules 5, 9): terms summed with ';', a '-' prefix subtracts, formulas over [line] with +, -
   (ASCII only), unary minus, parentheses, pos() and neg(); cycles rejected; carry over the header's comparative range,
   empty (with report_comparative_missing) without a filing or stored value; definition checks (rules 3, 5, 7).
M: measures (rules 6, 13): turnover by side with storno lines lowering it, migration entries in balances only,
   closing entries excluded on request, special periods of the year ending on `to` excluded from turnover, change
   and closing but never from opening or earlier years; selectors with '|' and '!' on the tree.
Y: one year earlier (rule 13): month ends to month ends, across leap years, for both comparative kinds.
S: the bilateral split (rule 7): by account, partner, or partner and open-item kind; kind, term and undated filters.
P: counterpart attribution (rule 8) on random entries: every line's pairs sum to its amount, every pair is its exact
   share rounded down or up (largest remainder, then the alternating-path step), reversals mirror, pairs between two
   cash accounts cancel, and one line on one side equals a largest-remainder split.
C: the direct cash flow (rule 12): the parts on non-cash counterparts sum exactly to the change in cash.
R: ranges before the cut-over (rule 14): opening turnover (before closing entries), stored comparative values,
   counterpart terms incomplete across the cut-over, the errors.
E: a small balance sheet and income statement end to end, with check lines (rule 9).
B: book row order and cursor (rule 10), also over stock rows ending on their natural key; the idempotent balance carry-forward, reversals netted (rule 22).
F: filing from a render job (rule 19): mismatches refused, staleness a stored check result.
H: render keys with the subject's state, and the marker (rule 28).
Not covered: tables, templates, WeasyPrint, XML schemas, locks, consumers.
"""
import datetime as dt
import hashlib
import json
import random
import re
from fractions import Fraction as F

RESULTS = []
def check(name, got, want):
    ok = got == want; RESULTS.append((ok, name, str(got))); print(("PASS " if ok else "FAIL ") + f"{name} -- {got}")
d = dt.date.fromisoformat

# ---------------- G: grammar ----------------
TOKEN = re.compile(r"\s*(?:(\[[0-9a-z_]+\])|(pos|neg)|([()+\-]))")
class GrammarError(Exception): pass

def parse_formula(text):
    if "−" in text: raise GrammarError("U+2212 minus: use ASCII '-'")
    toks, i = [], 0
    while i < len(text):
        if text[i].isspace(): i += 1; continue
        m = TOKEN.match(text, i)
        if not m or m.end() == i: raise GrammarError(f"bad token at {text[i:]!r}")
        toks.append(m.group(1) or m.group(2) or m.group(3)); i = m.end()
    pos = [0]
    def peek(): return toks[pos[0]] if pos[0] < len(toks) else None
    def take(t=None):
        tok = peek()
        if tok is None or (t and tok != t): raise GrammarError(f"expected {t}, got {tok}")
        pos[0] += 1; return tok
    def expr():
        node = term()
        while peek() in ("+", "-"):
            op = take(); node = (op, node, term())
        return node
    def term():
        tok = peek()
        if tok == "-": take(); return ("neg1", term())
        if tok in ("pos", "neg"): take(); take("("); e = expr(); take(")"); return (tok, e)
        if tok == "(": take(); e = expr(); take(")"); return e
        if tok and tok.startswith("["): take(); return ("ref", tok[1:-1])
        raise GrammarError(f"unexpected {tok}")
    node = expr()
    if peek() is not None: raise GrammarError(f"trailing {peek()}")
    return node

def refs(node):
    if node[0] == "ref": return {node[1]}
    return set().union(*(refs(n) for n in node[1:] if isinstance(n, tuple)))

def eval_node(node, val):
    k = node[0]
    if k == "ref": return val(node[1])
    subs = [eval_node(n, val) for n in node[1:] if isinstance(n, tuple)]
    if None in subs: return None                                  # an empty value empties every formula above it
    if k == "+": return eval_node(node[1], val) + eval_node(node[2], val)
    if k == "-": return eval_node(node[1], val) - eval_node(node[2], val)
    if k == "neg1": return -eval_node(node[1], val)
    if k == "pos": return max(eval_node(node[1], val), 0)
    if k == "neg": return max(-eval_node(node[1], val), 0)
    raise GrammarError(k)

def evaluate(lines, term_value):
    """lines: {code: source}; term_value(kind, arg) gives non-formula terms. Returns values or raises on a cycle."""
    parsed = {}
    for code, src in lines.items():
        terms = []
        for raw in [t for t in src.split(";") if t]:
            sign = -1 if raw.startswith("-") else 1
            raw = raw[1:] if sign < 0 else raw
            kind, _, arg = raw.partition(":")
            terms.append((sign, kind, parse_formula(arg) if kind == "formula" else arg))
        parsed[code] = terms
    done, active = {}, set()
    def value(code):
        if code in done: return done[code]
        if code in active: raise GrammarError(f"cycle through {code}")
        if code not in parsed: raise GrammarError(f"unknown line {code}")
        active.add(code)
        total = 0
        for sign, kind, arg in parsed[code]:
            x = eval_node(arg, value) if kind == "formula" else term_value(kind, arg)
            total = None if (total is None or x is None) else total + sign * x
        active.discard(code); done[code] = total
        return total
    return {c: value(c) for c in parsed}

boxes = {"36": "formula:[35]-[25]", "22": "carry:43", "35": "account:x", "25": "account:y",
         "37": "account:p", "38": "account:q",
         "40a": "formula:pos([36]-[22]+[37]-[38])", "41": "formula:neg([36]-[22]+[37]-[38])", "43": "formula:[41]"}
def tv(kind, arg):
    return {"account:x": 100, "account:y": 180, "account:p": 0, "account:q": 0, "carry:43": 30}[f"{kind}:{arg}"]
v = evaluate(boxes, tv)
check("G01 01/GTGT-style: 36 = 35 - 25 = -80; with 22 carried 30: 40a = pos(-110) = 0, 41 = neg(-110) = 110, 43 = 41",
      (v["36"], v["40a"], v["41"], v["43"]), (-80, 0, 110, 110))
v2 = evaluate({"a": "account:x;-account:y", "b": "formula:-[a]+(-[a])"}, tv)
check("G02 a '-' term subtracts; unary minus and parentheses", (v2["a"], v2["b"]), (-80, 160))
try: evaluate({"a": "formula:[b]", "b": "formula:[a]+[c]", "c": "account:x"}, tv); r = "accepted"
except GrammarError as e: r = "rejected" if "cycle" in str(e) else str(e)
check("G03 a cycle through formulas is rejected", r, "rejected")
try: parse_formula("[35]−[25]"); r = "accepted"
except GrammarError: r = "rejected"
check("G04 U+2212 minus is rejected; ASCII '-' is the only minus", r, "rejected")
try: parse_formula("[35]*2"); r = "accepted"
except GrammarError: r = "rejected"
check("G05 no other operators or constants", r, "rejected")
check("G06 pos and neg are magnitudes: pos(-5)=0, neg(-5)=5, neg(5)=0",
      (eval_node(parse_formula("pos([a])"), lambda c: -5), eval_node(parse_formula("neg([a])"), lambda c: -5),
       eval_node(parse_formula("neg([a])"), lambda c: 5)), (0, 5, 0))

# carry: the prior range is the header's comparative range; filing first, then a stored value, else empty
FILINGS = {("b02", ("2025-01-01", "2025-12-31")): {"60": 900}}
STORED = {("b02", "60", ("2024-01-01", "2024-12-31")): 700}
def carry_value(report, line, prior, checks):
    filing = FILINGS.get((report, prior))
    if filing is not None and line in filing: return filing[line]
    if (report, line, prior) in STORED: return STORED[(report, line, prior)]
    checks.append("report_comparative_missing"); return None
def carry_run(prior):
    checks = []
    v = evaluate({"60": "account:x", "61": "carry:60", "62": "formula:[60]+[61]"},
                 lambda k, a: 100 if k == "account" else carry_value("b02", a, prior, checks))
    return (v["61"], v["62"]), checks
check("G07 carry reads the filing over the comparative range, else the stored value, else it is empty with report_comparative_missing and empties the formula above it",
      (carry_run(("2025-01-01", "2025-12-31")), carry_run(("2024-01-01", "2024-12-31")), carry_run(("2023-01-01", "2023-12-31"))),
      (((900, 1000), []), ((700, 800), []), ((None, None), ["report_comparative_missing"])))

SPLIT_MEASURES = {"opening_debit", "opening_credit", "closing_debit", "closing_credit"}
def definition_errors(header, lines):
    """The rule 3, 5 and 7 checks that keep regime choices in the definition: report_definition_invalid reasons."""
    errs = []
    for code, src in lines.items():
        for raw in [t for t in src.split(";") if t]:
            kind, _, arg = raw.lstrip("-").partition(":")
            if kind == "carry" and header.get("comparative", "none") == "none": errs.append(f"{code}: carry with comparative none")
            if kind != "account": continue
            sel, m, *opts = arg.split(":")
            o = dict(x.split("=") for x in opts)
            if m in SPLIT_MEASURES and "by" not in o: errs.append(f"{code}: {m} without by")
            if "term" in o and "undated" not in o: errs.append(f"{code}: term without undated")
            if "term" in o and "term_months" not in header: errs.append(f"{code}: term without term_months")
    return errs
check("G08 a split measure needs by, term needs undated and the header's term_months, carry needs a comparative",
      definition_errors({"comparative": "none"}, {"a": "account:131:closing_debit", "b": "account:131:closing_debit:by=partner_kind:term=short",
                                                   "c": "carry:a", "d": "account:131:closing_debit:by=partner_kind:term=short:undated=short"}),
      ["a: closing_debit without by", "b: term without undated", "b: term without term_months", "c: carry with comparative none",
       "d: term without term_months"])
check("G09 a definition that states every choice passes",
      definition_errors({"comparative": "day_before_from", "term_months": 12},
                        {"a": "account:131:closing_debit:by=partner_kind:term=short:undated=short", "c": "carry:a", "e": "account:511:credit_turnover"}), [])

# ---------------- M: measures ----------------
TREE = {"111": None, "1111": "111", "1121": "112", "112": None, "131": None, "331": None, "338": None, "3388": "338",
        "33881": "3388", "33882": "3388", "511": None, "5111": "511", "632": None, "911": None, "421": None, "4212": "421",
        "642": None, "515": None, "635": None, "3331": None, "1381": None}
def descendants(code):
    out = {code}
    changed = True
    while changed:
        changed = False
        for c, p in TREE.items():
            if p in out and c not in out: out.add(c); changed = True
    return out
def resolve(selector):
    inc, *exc = selector.split("!")
    accs = set().union(*(descendants(c) for c in inc.split("|") if c in TREE)) if inc else set()
    for e in exc: accs -= descendants(e) if e in TREE else set()
    return accs

# journal line: entry, date, line_no, account, side, storno, amount (company, minor units), partner, kind, due, closing, migration
def L(entry, date, n, acc, amt, side=None, storno=False, partner=None, kind=None, due=None, closing=False, migration=False):
    side = side or ("debit" if (amt > 0) != storno else "credit")
    return dict(entry=entry, date=d(date), n=n, acc=acc, amt=amt, side=side, storno=storno, partner=partner,
                kind=kind, due=d(due) if due else None, closing=closing, migration=migration)

def measure(lines, selector, m, frm, to, closing_entries="include", special_periods="include"):
    accs = resolve(selector)
    # exclude: only the special-period entries of the fiscal year whose last day is `to` (they carry that date);
    # earlier years' special entries stay, and opening (the day before `from`) never holds the excluded ones
    sel = [l for l in lines if l["acc"] in accs
           and not (special_periods == "exclude" and l.get("special") and l["date"] == to)]
    bal = lambda day: sum(l["amt"] for l in sel if l["date"] <= day)
    rng = [l for l in sel if frm <= l["date"] <= to and not l["migration"]
           and not (closing_entries == "exclude" and l["closing"])]
    if m == "opening": return bal(frm - dt.timedelta(days=1))
    if m == "closing": return bal(to)
    if m == "debit_turnover": return sum(l["amt"] for l in rng if l["side"] == "debit")
    if m == "credit_turnover": return -sum(l["amt"] for l in rng if l["side"] == "credit")
    if m == "change": return (measure(lines, selector, "debit_turnover", frm, to, closing_entries, special_periods)
                              - measure(lines, selector, "credit_turnover", frm, to, closing_entries, special_periods))
    raise ValueError(m)

J = [
    L("M1", "2026-06-30", 1, "1111", 5_000_000, migration=True), L("M1", "2026-06-30", 2, "421", -5_000_000, migration=True),
    L("E1", "2026-07-05", 1, "131", 1_100_000, partner="C1", kind="invoice", due="2026-08-04"),
    L("E1", "2026-07-05", 2, "5111", -1_000_000), L("E1", "2026-07-05", 3, "3331", -100_000),
    L("E2", "2026-07-20", 1, "1111", 1_100_000), L("E2", "2026-07-20", 2, "131", -1_100_000, partner="C1", kind="invoice"),
    # E3 reverses E2 by storno: same sides, negated amounts
    L("E3", "2026-07-25", 1, "1111", -1_100_000, side="debit", storno=True),
    L("E3", "2026-07-25", 2, "131", 1_100_000, side="credit", storno=True, partner="C1", kind="invoice"),
    L("CL", "2026-07-31", 1, "5111", 1_000_000, closing=True), L("CL", "2026-07-31", 2, "911", -1_000_000, closing=True),
    L("CL", "2026-07-31", 3, "911", 1_000_000, closing=True), L("CL", "2026-07-31", 4, "4212", -1_000_000, closing=True),
]
JUL = (d("2026-07-01"), d("2026-07-31"))
check("M01 storno lowers debit turnover of 1111: 1,100,000 - 1,100,000 = 0, migration entry left out",
      measure(J, "111", "debit_turnover", *JUL), 0)
check("M02 the migration entry counts in the balance: opening of 111 on 1 July is 5,000,000", measure(J, "111", "opening", *JUL), 5_000_000)
check("M03 revenue credit turnover with closing entries excluded is 1,000,000; included, 511's change is 0",
      (measure(J, "511", "credit_turnover", *JUL, closing_entries="exclude"), measure(J, "511", "change", *JUL)), (1_000_000, 0))
check("M04 selectors: '338!33881' reaches 3388 and 33882 but not 33881", sorted(resolve("338!33881")), ["338", "3388", "33882"])
check("M05 '111|112' reaches both trees", sorted(resolve("111|112")), ["111", "1111", "112", "1121"])
SP = [L("S0", "2025-12-31", 1, "642", 50), L("S0", "2025-12-31", 2, "331", -50),
      L("R1", "2026-12-15", 1, "642", 1000), L("R1", "2026-12-15", 2, "331", -1000),
      L("S1", "2026-12-31", 1, "642", 300), L("S1", "2026-12-31", 2, "331", -300)]
for l in SP: l["special"] = l["entry"].startswith("S")
DEC = (d("2026-12-01"), d("2026-12-31"))
check("M06 special-period entries on the year's last day: included by default, left out with special_periods=exclude",
      (measure(SP, "642", "debit_turnover", *DEC), measure(SP, "642", "debit_turnover", *DEC, special_periods="exclude")), (1300, 1000))
ex = {m: measure(SP, "642", m, *DEC, special_periods="exclude") for m in ("opening", "change", "closing")}
check("M07 exclude removes this year's special entries from change and closing alike, keeps last year's in opening and closing, and opening + change = closing",
      (ex["opening"], ex["change"], ex["closing"], ex["opening"] + ex["change"] == ex["closing"]), (50, 1000, 1050, True))
check("M08 a range over two year ends keeps the earlier year's special entries in turnover; a `to` that is no year end changes nothing",
      (measure(SP, "642", "debit_turnover", d("2025-12-01"), d("2026-12-31"), special_periods="exclude"),
       measure(SP, "642", "closing", d("2026-01-01"), d("2026-12-30"), special_periods="exclude")
       == measure(SP, "642", "closing", d("2026-01-01"), d("2026-12-30"))), (1050, True))

# ---------------- Y: one year earlier ----------------
def month_end(day):
    return (dt.date(day.year + day.month // 12, day.month % 12 + 1, 1) - dt.timedelta(days=1))
def add_months(day, n):
    """Rule 13: a month's last day moves to the last day of the target month; any other day keeps its number."""
    y, m = divmod(day.month - 1 + n, 12); first = dt.date(day.year + y, m + 1, 1)
    end = month_end(first)
    return end if day == month_end(day) else first.replace(day=min(day.day, end.day))
def one_year_earlier(day): return add_months(day, -12)
def comparative_range(kind, frm, to):
    if kind == "prior_year_range": return one_year_earlier(frm), one_year_earlier(to)
    if kind == "day_before_from": return one_year_earlier(frm), frm - dt.timedelta(days=1)
    raise ValueError(kind)
check("Y01 month ends map to month ends across leap years; other days keep their number",
      [one_year_earlier(d(x)).isoformat() for x in ("2025-02-28", "2024-02-29", "2025-03-15", "2025-04-30", "2024-03-31")],
      ["2024-02-29", "2023-02-28", "2024-03-15", "2024-04-30", "2023-03-31"])
check("Y02 prior_year_range of February 2025 is 1 to 29 February 2024; of February 2024, 1 to 28 February 2023",
      (comparative_range("prior_year_range", d("2025-02-01"), d("2025-02-28")), comparative_range("prior_year_range", d("2024-02-01"), d("2024-02-29"))),
      ((d("2024-02-01"), d("2024-02-29")), (d("2023-02-01"), d("2023-02-28"))))
check("Y03 day_before_from moves `from` by the same rule: from 1 March 2025 gives 1 March 2024 to 28 February 2025; from 29 February 2024 (a month end) starts 28 February 2023",
      (comparative_range("day_before_from", d("2025-03-01"), d("2025-12-31")), comparative_range("day_before_from", d("2024-02-29"), d("2024-12-31"))[0]),
      ((d("2024-03-01"), d("2025-02-28")), d("2023-02-28")))

# ---------------- S: bilateral split ----------------
def split(lines, selector, to, by, kind=None, term=None, term_months=None, undated=None):
    accs = resolve(selector)
    sel = [l for l in lines if l["acc"] in accs and l["date"] <= to]
    if kind: sel = [l for l in sel if l["kind"] in kind]
    if term:
        assert term_months and undated in ("short", "long"), "term needs term_months and undated (rule 7)"
        horizon = add_months(to, term_months)
        long_ = lambda l: (undated == "long") if l["due"] is None else l["due"] > horizon
        sel = [l for l in sel if long_(l) == (term == "long")]
    key = {"account": lambda l: (l["acc"],), "partner": lambda l: (l["acc"], l["partner"]),
           "partner_kind": lambda l: (l["acc"], l["partner"], l["kind"])}[by]
    groups = {}
    for l in sel: groups[key(l)] = groups.get(key(l), 0) + l["amt"]
    return (sum(v for v in groups.values() if v > 0), sum(-v for v in groups.values() if v < 0))

B = [
    L("I1", "2026-12-01", 1, "131", 5000, partner="C1", kind="invoice", due="2027-01-01"),
    L("A1", "2026-12-10", 1, "131", -2000, partner="C1", kind="advance"),
    L("I2", "2026-12-12", 1, "131", 700, partner="C2", kind="invoice", due="2028-06-30"),
    L("A2", "2026-12-15", 1, "131", -900, partner="C3", kind="payment_on_account"),
]
B_OFFSETS = [L("I1", "2026-12-01", 2, "3388", -5000), L("A1", "2026-12-10", 2, "1111", 2000),
             L("I2", "2026-12-12", 2, "3388", -700), L("A2", "2026-12-15", 2, "1111", 900)]
YE = d("2026-12-31")
check("S01 by partner and kind: receivables 5,700, advances 2,900 (C1's advance not netted)", split(B, "131", YE, "partner_kind"), (5700, 2900))
check("S02 by partner: C1 nets to 3,000; receivables 3,700, advances 900", split(B, "131", YE, "partner"), (3700, 900))
check("S03 by account: one net balance 2,800", split(B, "131", YE, "account"), (2800, 0))
check("S04 kind=advance|payment_on_account: credit part 2,900", split(B, "131", YE, "partner_kind", kind=("advance", "payment_on_account")), (0, 2900))
check("S05 term with undated=short: C2's invoice due mid-2028 is long-term; short-term debit 5,000 plus items without due date on the credit side",
      (split(B, "131", YE, "partner_kind", term="long", term_months=12, undated="short"),
       split(B, "131", YE, "partner_kind", term="short", term_months=12, undated="short")), ((700, 0), (5000, 2900)))
check("S07 undated=long moves the items without a due date to the long-term part; the horizon from 31 December is 31 December next year",
      (split(B, "131", YE, "partner_kind", term="long", term_months=12, undated="long"), add_months(YE, 12)), ((700, 2900), d("2027-12-31")))
check("S06 the two parts always sum to the balance", all(a - b == 2800 for a, b in
      [split(B, "131", YE, by) for by in ("account", "partner", "partner_kind")]), True)

# ---------------- P: counterpart attribution ----------------
AUGMENTED = [0]
def pairs(entry):
    """entry: list of (line_no, amount). Returns {(i, j): m} for positive line i and negative line j.
    Each pair is its exact share |a_i| x |a_j| / S rounded down or up, and every line's pairs sum to its amount.
    The computation uses only line numbers and absolute amounts, with the side holding the entry's lowest line number
    as the 'first' side, so a reversal (negated amounts, same line numbers) gets exactly the same pair amounts."""
    lines = sorted((n, a) for n, a in entry if a != 0)
    first_sign = 1 if lines[0][1] > 0 else -1
    A = [(n, abs(a)) for n, a in lines if (a > 0) == (first_sign > 0)]
    B = [(n, abs(a)) for n, a in lines if (a > 0) != (first_sign > 0)]
    S = sum(a for _, a in A)
    assert S == sum(a for _, a in B), "entry must balance"
    exact = {(i, j): F(ai * bj, S) for i, ai in A for j, bj in B}
    m = {k: v.numerator // v.denominator for k, v in exact.items()}
    up = {k: 0 for k in exact}                                    # 1 when the pair is rounded up
    need_a = {i: ai - sum(m[(i, j)] for j, _ in B) for i, ai in A}
    need_b = {j: bj - sum(m[(i, j)] for i, _ in A) for j, bj in B}
    frac = {k: exact[k] - m[k] for k in exact}
    # pass 1: largest remainder first, ties by the first side's line number, then the other side's
    for k in sorted(exact, key=lambda k: (-frac[k], k[0], k[1])):
        if frac[k] and need_a[k[0]] > 0 and need_b[k[1]] > 0:
            up[k] = 1; need_a[k[0]] -= 1; need_b[k[1]] -= 1
    # pass 2: a unit still missing moves earlier units along the shortest alternating path (breadth-first, line order)
    rows, cols = [i for i, _ in A], [j for j, _ in B]
    while any(need_a[i] > 0 for i in rows):
        start = next(i for i in rows if need_a[i] > 0)
        prev, frontier, found = {("r", start): None}, [("r", start)], None
        while frontier and not found:
            nxt = []
            for kind, x in frontier:
                if kind == "r":
                    for j in cols:
                        if frac[(x, j)] and not up[(x, j)] and ("c", j) not in prev:
                            prev[("c", j)] = (kind, x); nxt.append(("c", j))
                            if need_b[j] > 0: found = ("c", j); break
                else:
                    for i in rows:
                        if up[(i, x)] and ("r", i) not in prev:
                            prev[("r", i)] = (kind, x); nxt.append(("r", i))
                if found: break
            frontier = nxt
        assert found, "an integral rounding always exists"
        node = found
        while prev[node] is not None:
            p_ = prev[node]
            if node[0] == "c": up[(p_[1], node[1])] = 1          # row -> column: round this pair up
            else: up[(node[1], p_[1])] = 0                        # column -> row: round that pair down again
            node = p_
        need_a[start] -= 1; need_b[found[1]] -= 1; AUGMENTED[0] += 1
    out = {}
    for (i, j), v in exact.items():
        key = (i, j) if first_sign > 0 else (j, i)                # keyed (positive line, negative line)
        out[key] = m[(i, j)] + up[(i, j)]
    return out

def attribution(entry):
    """{line_no: {other_line_no: signed part}}"""
    out = {n: {} for n, a in entry if a != 0}
    for (i, j), v in pairs([(n, a) for n, a in entry if a != 0]).items():
        out[i][j] = out[i].get(j, 0) + v; out[j][i] = out[j].get(i, 0) - v
    return out

def largest_remainder(total, weights):
    W = sum(weights.values()); sign = 1 if total >= 0 else -1; t = abs(total)
    ex = {k: F(t * w, W) for k, w in weights.items()}; fl = {k: v.numerator // v.denominator for k, v in ex.items()}
    left = t - sum(fl.values())
    for k in sorted(ex, key=lambda k: (-(ex[k] - fl[k]), k))[:left]: fl[k] += 1
    return {k: sign * v for k, v in fl.items()}

def random_entry(rng, max_side=5, top=10**7):
    p = [rng.randint(1, top) for _ in range(rng.randint(1, max_side))]
    nvals = [rng.randint(1, top) for _ in range(rng.randint(1, max_side))]
    # make the sides equal by scaling the last negative line
    diff = sum(p) - sum(nvals)
    if diff > 0: nvals[-1] += diff
    else: p[-1] += -diff
    amounts = p + [-x for x in nvals]
    rng.shuffle(amounts)
    return [(k + 1, a) for k, a in enumerate(amounts)]

rng = random.Random(49)
ok_sum = ok_mirror = ok_lr = True; single_side = 0; floor_ceil = True
for _ in range(5000):
    e = random_entry(rng)
    att = attribution(e)
    ok_sum &= all(sum(att[n].values()) == a for n, a in e)           # a line's parts sum to its own amount
    m = pairs(e)
    exact = {(i, j): F(ai * -aj, sum(x for _, x in e if x > 0)) for i, ai in e if ai > 0 for j, aj in e if aj < 0}
    floor_ceil &= all(abs(F(m[k]) - exact[k]) < 1 for k in m)
    rev = attribution([(n, -a) for n, a in e])
    ok_mirror &= all(rev[n][o] == -att[n][o] for n in att for o in att[n])
    pos_ = [n for n, a in e if a > 0]; neg_ = [n for n, a in e if a < 0]
    if len(pos_) == 1:
        single_side += 1
        lr = largest_remainder(dict(e)[pos_[0]], {j: -a for j, a in e if a < 0})
        ok_lr &= {j: -v for j, v in att[pos_[0]].items()} == {j: -v for j, v in lr.items()}
check("P01 every line's pairs sum exactly to its own amount (rows and columns), 5,000 random entries", ok_sum, True)
check("P02 a reversal (negated amounts, same line numbers) has exactly the negated pairs", ok_mirror, True)
check(f"P03 with one positive line ({single_side} entries) the pairs equal a largest-remainder split of it", ok_lr, True)
check("P04 every pair is its exact share rounded down or up", floor_ceil, True)
print(f"NOTE units placed by the alternating-path pass: {AUGMENTED[0]}")
e = [(1, 110_000), (2, -100_000), (3, -10_000)]
check("P05 a cash receipt 110,000 against 131 100,000 and 3331 10,000", attribution(e)[1], {2: 100_000, 3: 10_000})
e = [(1, -10_010), (2, 10_000), (3, 10)]
check("P06 a transfer 1111 -> 1121 with a fee: 10,000 to the other cash account, 10 to the fee", attribution(e)[1], {2: -10_000, 3: -10})
e = [(1, 1), (2, 1), (3, 1), (4, -3)]
check("P07 one line on one side: each counterpart gets its share", attribution(e)[4], {1: -1, 2: -1, 3: -1})
check("P09 equal remainders go to the lowest line numbers: three lines of 1 against 2 and 1",
      attribution([(1, 1), (2, 1), (3, 1), (4, -2), (5, -1)])[4], {1: -1, 2: -1, 3: 0})
e = [(1, 1), (2, 1), (3, -1), (4, -1)]
check("P08 two by two of 1: pairs (1,3) and (2,4) by remainder order, then line numbers", pairs(e), {(1, 3): 1, (1, 4): 0, (2, 3): 0, (2, 4): 1})
check("P10 its reversal gets the same pairs", pairs([(n, -a) for n, a in e]), {(3, 1): 1, (4, 1): 0, (3, 2): 0, (4, 2): 1})

# ---------------- C: direct cash flow ----------------
CASH = {"1111", "1121"}
NONCASH = ["131", "331", "5111", "3331", "642", "515", "635", "33882"]
def cash_flow(entries, selector_accounts, side):
    """Sum, over cash lines of the given side, of parts attributed to lines on the selected non-cash accounts."""
    total = 0
    for e in entries:
        att = attribution([(n, a) for n, acc, a, s in e])
        accs = {n: acc for n, acc, a, s in e}; sides = {n: s for n, acc, a, s in e}
        for n in att:
            if accs[n] in CASH and sides[n] == side:
                total += sum(v for o, v in att[n].items() if accs[o] in selector_accounts)
    return total
ok_cash = ok_cancel = True
for _ in range(1000):
    entries = []
    for _k in range(rng.randint(1, 8)):
        e = random_entry(rng, 4, 10**6)
        lines = []
        for n, a in e:
            acc = rng.choice(sorted(CASH)) if rng.random() < 0.4 else rng.choice(NONCASH)
            storno = rng.random() < 0.1
            side = ("debit" if a > 0 else "credit") if not storno else ("credit" if a > 0 else "debit")
            lines.append((n, acc, a, side))
        entries.append(lines)
    change = sum(a for e in entries for n, acc, a, s in e if acc in CASH)
    flows = cash_flow(entries, set(NONCASH), "debit") + cash_flow(entries, set(NONCASH), "credit")
    ok_cash &= flows == change
    internal = cash_flow(entries, CASH, "debit") + cash_flow(entries, CASH, "credit")
    ok_cancel &= internal == 0
check("C01 the parts on non-cash counterparts sum exactly to the change in cash (1,000 random periods, storno lines included)", ok_cash, True)
check("C02 parts between two cash accounts cancel exactly", ok_cancel, True)
pay = [[(1, "1121", -25_020_000, "credit"), (2, "331", 25_000_000, "debit"), (3, "642", 11_000, "debit"), (4, "635", 9_000, "debit")]]
check("C03 a bank payment with a fee and a realized exchange loss: outflow split 25,000,000 / 11,000 / 9,000",
      (cash_flow(pay, {"331"}, "credit"), cash_flow(pay, {"642"}, "credit"), cash_flow(pay, {"635"}, "credit")),
      (-25_000_000, -11_000, -9_000))

# ---------------- R: before the cut-over ----------------
OPENING_DATE = d("2026-06-30")
OPENING_TURNOVER = {("5111", d("2026-01-01")): (0, 4_000_000)}          # account, start_date -> (debit, credit); end_date = opening date
COMPARATIVE = {("b02", "10", d("2025-01-01"), d("2025-12-31")): 7_500_000}
def turnover_with_opening(lines, acc, m, frm, to, closing_entries="exclude"):
    if frm > OPENING_DATE: return measure(lines, acc, m, frm, to, closing_entries), []
    if to <= OPENING_DATE: raise LookupError("report_range_before_opening")
    row = OPENING_TURNOVER.get((acc, frm))
    base = measure(lines, acc, m, frm, to, closing_entries)
    # opening_turnover is turnover before closing entries: it adds only to terms with closing_entries=exclude
    if row is None or closing_entries != "exclude": return base, ["report_turnover_incomplete"]
    return base + (row[0] if m == "debit_turnover" else row[1]), []
def straddles(frm, to): return frm <= OPENING_DATE < to
def counterpart_with_opening(entries, acc, other, frm, to):
    """A counterpart= (or cash_in / cash_out) term: opening_turnover has no pairs, so a straddling range is incomplete."""
    total = 0
    for e in entries:
        if not (frm <= e[0] <= to): continue
        att = attribution([(n, a) for n, ac, a in e[1]]); accs = {n: ac for n, ac, a in e[1]}
        total += sum(v for n in att if accs[n] == acc for o, v in att[n].items() if accs[o] == other)
    return total, (["report_turnover_incomplete"] if straddles(frm, to) else [])
def comparative(report, line, frm, to, compute):
    try: return compute(frm, to), []
    except LookupError:
        if (report, line, frm, to) in COMPARATIVE: return COMPARATIVE[(report, line, frm, to)], []
        return None, ["report_comparative_missing"]
YEAR = (d("2026-01-01"), d("2026-12-31"))
J2 = [l for l in J if l["acc"] != "5111" or not l["closing"]]
check("R01 revenue of the cut-over year adds the year-to-date opening turnover: 4,000,000 + 1,000,000",
      turnover_with_opening(J, "5111", "credit_turnover", *YEAR), (5_000_000, []))
check("R07 opening turnover is before closing entries: a revenue term that keeps closing entries is incomplete across the cut-over",
      turnover_with_opening(J, "5111", "credit_turnover", *YEAR, closing_entries="include")[1], ["report_turnover_incomplete"])
CP = [(d("2026-07-05"), [(1, "131", 1_100_000), (2, "5111", -1_000_000), (3, "3331", -100_000)])]
check("R08 a counterpart term over a range straddling the cut-over gives report_turnover_incomplete; after the cut-over it is complete",
      (counterpart_with_opening(CP, "5111", "131", *YEAR), counterpart_with_opening(CP, "5111", "131", d("2026-07-01"), d("2026-12-31"))),
      ((-1_000_000, ["report_turnover_incomplete"]), (-1_000_000, [])))
check("R02 an account without an opening turnover row in a straddling range gives report_turnover_incomplete",
      turnover_with_opening(J2, "3331", "credit_turnover", *YEAR)[1], ["report_turnover_incomplete"])
check("R03 the prior-year comparative comes from report_comparative_value",
      comparative("b02", "10", d("2025-01-01"), d("2025-12-31"), lambda f, t: turnover_with_opening(J2, "5111", "credit_turnover", f, t)[0]),
      (7_500_000, []))
check("R04 without a stored value the cell is empty with report_comparative_missing",
      comparative("b02", "20", d("2025-01-01"), d("2025-12-31"), lambda f, t: turnover_with_opening(J2, "632", "debit_turnover", f, t)[0]),
      (None, ["report_comparative_missing"]))
check("R05 a straddling range that starts after the opening turnover's start date is incomplete for that account too",
      turnover_with_opening(J2, "5111", "credit_turnover", d("2026-03-01"), d("2026-12-31"))[1], ["report_turnover_incomplete"])
try: turnover_with_opening(J2, "5111", "credit_turnover", d("2026-01-01"), d("2026-05-31")); r = "computed"
except LookupError as e: r = str(e)
check("R06 a current range ending before the opening date fails", r, "report_range_before_opening")

# ---------------- E: end to end ----------------
def term_value_for(lines, frm, to):
    def tv(kind, arg):
        if kind == "account":
            sel, m, *opts = arg.split(":")
            o = dict(x.split("=") for x in opts)
            if m in ("closing_debit", "closing_credit"):
                deb, cre = split(lines, sel, to, o["by"])           # by is required on split measures (rule 7)
                return deb if m == "closing_debit" else cre
            return measure(lines, sel, m, frm, to, o.get("closing_entries", "include"))
        raise GrammarError(kind)
    return tv
YEAR_J = J + B + B_OFFSETS
b01 = {"110": "account:111|112:closing", "131": "account:131:closing_debit:by=partner_kind", "100": "formula:[110]+[131]",
       "312": "account:131:closing_credit:by=partner_kind", "331": "account:331:closing_credit:by=partner_kind",
       "3331": "account:3331:closing_credit:by=account", "338": "account:338:closing_credit:by=account", "421": "-account:421:closing",
       "300": "formula:[312]+[331]+[3331]+[338]+[421]", "check": "formula:[100]-[300]"}
v = evaluate(b01, term_value_for(YEAR_J, *YEAR))
check("E01 a small balance sheet balances: the check line is zero", v["check"], 0)
b02 = {"01": "account:511:credit_turnover:closing_entries=exclude", "10": "formula:[01]",
       "50": "formula:[10]", "check": "formula:[50]-[sum]", "sum": "account:4212:credit_turnover"}
v = evaluate(b02, term_value_for(YEAR_J, *YEAR))
check("E02 revenue excludes the closing entry; profit equals what closing carried to 4212", (v["01"], v["check"]), (1_000_000, 0))

# ---------------- B: book order, cursor, carry-forward ----------------
def row_key(r): return (r["date"], r["number"], r["type"], r["entry_id"], r["line"])
HEADS = [(d("2026-03-0%d" % rng.randint(1, 3)), f"{rng.randint(1, 4):04d}", rng.choice(["payment", "receipt"]), f"e{e:03d}") for e in range(60)]
BOOK = [dict(date=dd, number=no, type=ty, entry_id=eid, line=n) for dd, no, ty, eid in HEADS for n in (3, 1, 2)]
seen = {}                                                         # numbers are unique per type: drop later duplicates
BOOK = [r for r in BOOK if seen.setdefault((r["type"], r["number"]), r["entry_id"]) == r["entry_id"]]
ordered = sorted(BOOK, key=row_key)
def page(after, size):
    rows = [r for r in ordered if after is None or row_key(r) > after][:size]
    return rows, (row_key(rows[-1]) if rows else None)
got, cur = [], None
while True:
    rows, cur = page(cur, 3)
    if not rows: break
    got += rows
check("B01 the five keys order rows totally: no two rows share a key, and a cursor over them neither repeats nor skips",
      (len({row_key(r) for r in BOOK}) == len(BOOK), got == ordered), (True, True))
heads = sorted({(r["date"], r["number"], r["entry_id"]) for r in BOOK})
shared = [(x, y) for x in heads for y in heads if x[2] < y[2] and x[:2] == y[:2]]
def contiguous(eid):
    idx = [i for i, r in enumerate(ordered) if r["entry_id"] == eid]
    return idx == list(range(idx[0], idx[0] + len(idx)))
check(f"B02 lines of one entry stay together, also for the {len(shared)} pairs of entries of two types sharing date and number",
      (len(shared) > 0, all(contiguous(r["entry_id"]) for r in ordered)), (True, True))

# stock rows are aggregates without an ID: they end on their natural key (item, warehouse, owner, lot)
def stock_key(r): return (r["warehouse_group"], r["item_id"], r["warehouse_id"], r["owner_partner_id"] or "", r["lot_id"] or "")
STOCK = {}
for _ in range(80):
    k = dict(warehouse_group=rng.choice(["north", "south"]), item_id=f"i{rng.randint(1, 5)}", warehouse_id=f"w{rng.randint(1, 3)}",
             owner_partner_id=rng.choice([None, "p1"]), lot_id=rng.choice([None, "l1", "l2"]))
    STOCK[stock_key(k)] = dict(k, quantity=STOCK.get(stock_key(k), {}).get("quantity", 0) + rng.randint(1, 9))   # one row per key
stock_rows = sorted(STOCK.values(), key=stock_key)
got, cur = [], None
while True:
    rows = [r for r in stock_rows if cur is None or stock_key(r) > cur][:4]
    if not rows: break
    got += rows; cur = stock_key(rows[-1])
check(f"B05 a cursor over {len(stock_rows)} stock rows by group, item, warehouse, owner and lot neither repeats nor skips",
      (got == stock_rows, len({stock_key(r) for r in got}) == len(got)), (True, True))

def carry_forward(year_end_balance, moved_before):
    """RunBalanceCarryForward: moves the year-end balance minus what earlier runs for that year moved (their close_task_id)."""
    amount = year_end_balance - sum(moved_before)
    return amount if amount else None                             # nothing to post
runs = []
for bal in (-5_000_000, -5_000_000, -5_200_000):                  # second run unchanged; then a special-period adjustment of -200,000
    a = carry_forward(bal, runs)
    if a is not None: runs.append(a)
check("B03 the carry-forward is idempotent: a second run posts nothing, a run after a special-period adjustment moves only the difference",
      (runs, sum(runs)), ([-5_000_000, -200_000], -5_200_000))
runs.append(-runs[-1])                                            # the -200,000 transfer is reversed: negated amounts, same task
a = carry_forward(-5_200_000, runs)
check("B04 a reversed transfer is netted out of what earlier runs moved, so the next run moves it again",
      (a, sum(runs) + a), (-200_000, -5_200_000))

# ---------------- F: filing from a render job ----------------
class Refused(Exception): pass
def file_report(job, code, frm, to, definition_hash_now, entry_count_now, comparative_hash_now):
    """Rule 19: refuse only a job that is not done or has another code, range or definition hash; staleness is a
    best-effort check result; the snapshot is the job's lines, never recomputed."""
    if job["state"] != "done" or (job["code"], job["from"], job["to"], job["definition_hash"]) != (code, frm, to, definition_hash_now):
        raise Refused("report_render_job_mismatch")
    checks = list(job["checks"])
    if (job["entry_count"], job["comparative_hash"]) != (entry_count_now, comparative_hash_now):
        checks.append("report_snapshot_stale")
    return {"lines": job["lines"], "lines_hash": job["lines_hash"], "checks": checks}
LINES = {"10": 1_000_000, "20": 400_000}
JOB = {"state": "done", "code": "b02", "from": d("2026-01-01"), "to": d("2026-12-31"), "definition_hash": "h1", "lines": LINES,
       "lines_hash": hashlib.sha256(json.dumps(LINES, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
       "checks": ["report_periods_open"], "entry_count": 120, "comparative_hash": "c1"}
f = file_report(JOB, "b02", d("2026-01-01"), d("2026-12-31"), "h1", 121, "c1")
check("F01 a posting after the render: filing succeeds with report_snapshot_stale beside report_periods_open and stores the job's lines unchanged",
      (f["checks"], f["lines"] is LINES), (["report_periods_open", "report_snapshot_stale"], True))
outcomes = []
for job, rng_to, h in ((dict(JOB, state="pending"), d("2026-12-31"), "h1"), (JOB, d("2026-11-30"), "h1"), (JOB, d("2026-12-31"), "h2")):
    try: file_report(job, "b02", d("2026-01-01"), rng_to, h, 120, "c1"); outcomes.append("filed")
    except Refused as e: outcomes.append(str(e))
check("F02 a job not done, over another range, or of another definition hash is refused with report_render_job_mismatch",
      outcomes, ["report_render_job_mismatch"] * 3)

# ---------------- H: render keys ----------------
def render_key(subject, state, template_version, contract_version, language, marker, fmt):
    body = json.dumps({"subject": subject, "state": state, "template_version": template_version, "contract_version": contract_version,
                       "language": language, "marker": marker, "format": fmt}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()
def marker(state, number):
    if state == "reversed": return "REVERSED"
    if state == "canceled": return "CANCELED"
    return "DRAFT" if number is None else None
V = {"document_version_id": "v-1"}
POSTED = {"document": "posted", "e_invoice": "accepted"}
k1 = render_key(V, POSTED, "t-3", "1.2", "vi", None, "pdf")
check("H01 the same inputs give the same key", k1 == render_key(V, dict(POSTED), "t-3", "1.2", "vi", None, "pdf"), True)
check("H02 language, marker or contract version change the key",
      len({k1, render_key(V, POSTED, "t-3", "1.2", "en", None, "pdf"), render_key(V, POSTED, "t-3", "1.2", "vi", "DRAFT", "pdf"),
           render_key(V, POSTED, "t-3", "1.3", "vi", None, "pdf")}), 4)
check("H03 the same version reversed, or in another e-invoice state, gets a new key; the marker reads REVERSED, CANCELED, DRAFT",
      (len({k1, render_key(V, {"document": "reversed", "e_invoice": "accepted"}, "t-3", "1.2", "vi", marker("reversed", "0001"), "pdf"),
            render_key(V, {"document": "posted", "e_invoice": "replaced"}, "t-3", "1.2", "vi", None, "pdf")}),
       marker("reversed", "0001"), marker("canceled", None), marker("draft", None), marker("posted", "0001")),
      (3, "REVERSED", "CANCELED", "DRAFT", None))

print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
