"""Scenario: the production agent (ADR-0064), as pure functions, on the applied docs and on the DDL drafts.

Run: python t25_production_agent.py [--load]
  The pure checks (part P) and the document checks (part C) always run. With --load, ERPME_LAB_DSN must name a throwaway
  database: load_all.py drops and rebuilds schemas erpme and types there and loads every DDL file of design/, and the
  database checks (part D) run. ERPME_DOCS points at the docs/ tree (default ~/Projects/ERPMe/docs); ERPME_LAB_DIR at
  lab.py and load_all.py (default: this file's directory).

P: the rules of ADR-0064 as lab functions: the settings rows of rule 23 parsed from the ADR (defaults inside bounds,
   today's behavior, the asymmetric change path, out-of-bounds values refused, a random property test); the shortage list
   with its short and uncovered views (rule 5); the release verdict and the shortage policy input (rule 6); the
   reservation priority (rule 7); the sweep against others' reservations, with racing receipts under the stock lock
   (a naive unlocked race must over-reserve), the scheduled window and the global halt (rules 3, 15, 23); upward pegging
   sums (rule 8); exceptions and action messages with grace days, tolerances and the horizon, and the bottom-up order
   (rule 17); alternative versions on recomputed dates (rule 16); completion candidates for standard and disassembly
   orders and stalled orders (rule 12); the yield, activity and duplicate checks (rule 22); capture scope resolution
   without a leak, stated quantities, draft-only commands and floor 3 (rules 4, 19); the import's auto-post gate (rule
   25); reservation transfers only by proposal (rule 24); variance drivers summing to the category, the ranking and the
   negative residual (rules 10, 11, 20); the hard locks on tool lists (rule 4).
C: the applied docs: status line, rule and code ranges free of ADR-0063's, catalog rows with field counts, DS-04 codes,
   work item kinds, leaves, the backlog row, no country content in the ADR.
D: with --load, on all DDL: the production exception kinds bound to production_order_id, the entry source and import
   reference with its unique index, the reservation transfer key, and the purpose value in four checks.
Not covered: commands, the planning run, the dispatcher, the gateway.
"""
import collections, csv, datetime as dt, json, os, random, re, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("ERPME_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import RESULTS, conn, expect, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("ERPME_DOCS", "~/Projects/ERPMe/docs"))
ADR = os.path.join(DOCS, "adr", "0064-production-agent.md")
random.seed(64)
D = dt.date


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


ADR_TEXT = open(ADR, encoding="utf-8").read()

# ======================================================================= P1 settings rows (rule 23)
print("== P: rules as lab functions")


def parse_settings(text):
    """Rule 23's rows in ADR-0063's vocabulary: scope, value type, core default, bounds (a..b, a.., or values a|b), direction, leaf, outdates."""
    rows = {}
    for line in text.splitlines():
        m = re.match(r"^\s+\| `((?:production|planning)\.[a-z_.]+)` \|(.*)\|\s*$", line)
        if not m:
            continue
        cells = [c.strip().strip("`").replace("\\|", "|") for c in re.split(r"(?<!\\)\|", m.group(2))]
        if len(cells) != 7:
            continue
        scope, typ, default, bounds, tighter, leaf, outdates = cells
        lo = hi = None
        if re.match(r"^\d+\.\.\d*$", bounds):
            lo_s, hi_s = bounds.split("..")
            lo, hi = int(lo_s), (int(hi_s) if hi_s else None)
        rows[m.group(1)] = dict(scope=scope, type=typ, default=default, bounds=bounds, lo=lo, hi=hi, tighter=tighter, leaf=leaf, outdates=outdates)
    return rows


SET = parse_settings(ADR_TEXT)
VOCAB = dict(scope={"company", "company;product_category"}, type={"enum", "integer", "percent", "boolean", "code_list", "decimal"},
             outdates={"auto_post", "promotion", "none"})
check("P01 rule 23 lists 26 settings in ADR-0063's vocabulary: scope, value type, default, bounds, direction, leaf and outdates",
      len(SET) == 26 and all(v["scope"] in VOCAB["scope"] and v["type"] in VOCAB["type"] and v["outdates"] in VOCAB["outdates"]
                             and re.match(r"^(higher|lower|true|false|subset)_tighter$|^neutral$|^order:[a-z_]+(<[a-z_]+)+$", v["tighter"]) for v in SET.values()), len(SET))
num = {k: v for k, v in SET.items() if v["lo"] is not None}
bad = [k for k, v in num.items() if not (v["lo"] <= int(v["default"]) <= (v["hi"] if v["hi"] is not None else 10 ** 9))]
CODES = {"production.agent.shortage_candidate_kinds": ["expedite_supply", "stock_transfer", "alternative_version", "reschedule", "partial_staging", "transfer_reservation", "split_order"],
         "production.capture.enabled_sources": ["spreadsheet", "photo", "message_text"]}


def allowed(v, key):
    return CODES[key] if v["type"] == "code_list" else v["bounds"].split("|")


def default_value(v):
    return json.loads(v["default"]) if v["type"] == "code_list" else v["default"]


bad += [k for k, v in SET.items() if v["lo"] is None and not set(default_value(v) if v["type"] == "code_list" else [v["default"]]) <= set(allowed(v, k))]
bad += [k for k, v in SET.items() if v["type"] == "code_list" and v["bounds"] != "codes"]
check("P02 every default lies inside its hard bounds (numeric ranges, allowed values, code lists)", bad == [] and len(num) >= 15, bad or len(num))
LEAVES = {r["code"] for r in csv.DictReader(open(os.path.join(DOCS, "catalogs/authorization-areas.csv"), encoding="utf-8"))}
check("P03 every setting's leaf is a node of the authorization tree", all(v["leaf"] in LEAVES for v in SET.values()),
      [v["leaf"] for v in SET.values() if v["leaf"] not in LEAVES])


def S(key):
    v = SET[key]
    d = v["default"]
    return int(d) if v["lo"] is not None else d


check("P04 the defaults reproduce ADR-0034: reservation at release, yield deviations as warnings, no automatic import posting, duplicate check on",
      S("production.reservation.mode") == "on_release" and S("production.confirmation.over_tolerance_action") == "warn"
      and S("production.mes_import.auto_post") == "false" and S("production.confirmation.duplicate_window_minutes") >= 10)


def change_path(key, old, new):
    """ADR-0063's asymmetric path: out of bounds refused; tightening immediate; loosening by change proposal; neutral by one person."""
    v = SET[key]
    t = v["tighter"]
    if v["lo"] is not None:
        if new < v["lo"] or (v["hi"] is not None and new > v["hi"]):
            return "setting_out_of_bounds"
    elif not set(new if isinstance(new, list) else [new]) <= set(allowed(v, key)):
        return "setting_out_of_bounds"
    if t == "neutral" or new == old:
        return "immediate"
    if t in ("higher_tighter", "lower_tighter"):
        tighter = (new > old) if t == "higher_tighter" else (new < old)
    elif t == "subset_tighter":
        tighter = set(new) <= set(old)
    elif t in ("true_tighter", "false_tighter"):
        tighter = new == t.split("_")[0]
    else:
        order = t.split(":", 1)[1].split("<")
        tighter = order.index(new) > order.index(old)
    return "immediate" if tighter else "proposal"


check("P05 tightening is immediate, loosening is a proposal, out of bounds is refused, a neutral row needs one person",
      change_path("production.confirmation.yield_tolerance_percent", 0, 5) == "proposal"
      and change_path("production.confirmation.yield_tolerance_percent", 5, 2) == "immediate"
      and change_path("production.confirmation.yield_tolerance_percent", 0, 101) == "setting_out_of_bounds"
      and change_path("production.confirmation.duplicate_window_minutes", 120, 5) == "setting_out_of_bounds"
      and change_path("production.confirmation.duplicate_window_minutes", 120, 60) == "proposal"
      and change_path("production.mes_import.auto_post", "false", "true") == "proposal"
      and change_path("production.mes_import.auto_post", "true", "false") == "immediate"
      and change_path("production.confirmation.over_tolerance_action", "warn", "reject") == "immediate"
      and change_path("production.capture.enabled_sources", ["spreadsheet"], ["spreadsheet", "photo"]) == "proposal"
      and change_path("production.reservation.window_days", 14, 30) == "immediate"
      and change_path("production.order.start_grace_days", 1, 10) == "immediate" and change_path("planning.production_rescheduling_horizon_days", 60, 5) == "immediate"
      and change_path("production.mes_import.min_evidence_drafts", 300, 200) == "proposal"
      and change_path("production.capture.enabled_sources", ["spreadsheet"], ["voice"]) == "setting_out_of_bounds"
      and change_path("production.reservation.mode", "on_release", "never") == "setting_out_of_bounds")
oob = 0
for _ in range(400):
    k = random.choice(sorted(num))
    v = num[k]
    x = v["lo"] - random.randint(1, 50) if v["hi"] is None or random.random() < 0.5 else v["hi"] + random.randint(1, 50)
    oob += change_path(k, int(v["default"]), x) == "setting_out_of_bounds"
check("P06 property: 400 random values outside the bounds are all refused", oob == 400, oob)
check("P07b the import evidence is sized by the rule of three on ADR-0063's 1% ceiling: 300 drafts, 99% unchanged, inside their bounds",
      S("production.mes_import.min_evidence_drafts") == -(-3 * 100 // 1) and S("production.mes_import.min_unchanged_percent") >= 100 - 1
      and SET["production.mes_import.min_evidence_drafts"]["lo"] == 150 and SET["production.mes_import.min_evidence_drafts"]["hi"] == 3000)
check("P07 the duplicate window cannot switch the check off and the horizon cannot switch messages off (lower bounds 10 and 1)",
      SET["production.confirmation.duplicate_window_minutes"]["lo"] == 10 and SET["planning.production_rescheduling_horizon_days"]["lo"] == 1)

# ======================================================================= P2 shortage list, priority, verdict (rules 5-7)


def priority_key(line):
    return (line["requested"], line.get("mto_due") or D(9999, 12, 31), line["order_no"], line["line"])


def shortage_list(lines, atp, keep=lambda ln: True):
    """Rule 5. lines: every component line of the company's open orders; atp: (item, warehouse) -> free stock. Uncovered is
    allocated before any filter: approved orders first in priority, then draft and pending orders from what is left."""
    out, free = [], dict(atp)
    groups = [x for x in lines if x["state"] == "approved"], [x for x in lines if x["state"] in ("draft", "pending_approval")]
    for grp in groups:
        for ln in sorted(grp, key=priority_key):
            k = (ln["item"], ln["wh"])
            open_req = max(0, ln["required"] - ln["issued"] - ln["backflushed"])
            unreserved = max(0, open_req - ln["reserved"])
            short = max(0, open_req - ln["reserved"] - atp.get(k, 0))
            take = min(unreserved, free.get(k, 0))
            free[k] = free.get(k, 0) - take
            out.append(dict(ln, open_requirement=open_req, short=short, uncovered=unreserved - take))
    return [r for r in out if keep(r)]


def L(order_no, item, required, requested, reserved=0, issued=0, backflushed=0, line=1, mto_due=None, state="approved", wh="WP"):
    return dict(order_no=order_no, item=item, required=required, requested=requested, reserved=reserved, issued=issued,
                backflushed=backflushed, line=line, mto_due=mto_due, state=state, wh=wh)


lines = [L("MO-2", "C1", 10, D(2026, 12, 3)), L("MO-1", "C1", 10, D(2026, 12, 3), mto_due=D(2026, 12, 20)), L("MO-3", "C1", 10, D(2026, 12, 1))]
sl = shortage_list(lines, {("C1", "WP"): 15})
order = [r["order_no"] for r in sl]
check("P08 priority: requested date, then the make-to-order due date (none last), then document number", order == ["MO-3", "MO-1", "MO-2"], order)
check("P09 the order's own view counts all free stock (short 0 for each), the cross-order view allocates it in priority (uncovered 0, 5, 10)",
      [r["short"] for r in sl] == [0, 0, 0] and [r["uncovered"] for r in sl] == [0, 5, 10], [(r["short"], r["uncovered"]) for r in sl])
mixed = [L("MO-1", "C1", 10, D(2026, 12, 1)), L("MO-D", "C1", 10, D(2026, 11, 25), state="draft"), L("MO-2", "C1", 10, D(2026, 12, 5)),
         L("MO-W2", "C1", 10, D(2026, 12, 1), wh="W2"), L("MO-P", "C2", 5, D(2026, 12, 1), state="pending_approval")]
full = {r["order_no"]: r["uncovered"] for r in shortage_list(mixed, {("C1", "WP"): 15, ("C1", "W2"): 10, ("C2", "WP"): 5})}
filt = {r["order_no"]: r["uncovered"] for r in shortage_list(mixed, {("C1", "WP"): 15, ("C1", "W2"): 10, ("C2", "WP"): 5}, keep=lambda r: r["order_no"] in ("MO-2", "MO-D"))}
check("P11b uncovered: approved orders first (the earlier draft gets what is left), per item and warehouse, and a filtered call returns the same values",
      full == {"MO-1": 0, "MO-2": 5, "MO-W2": 0, "MO-D": 10, "MO-P": 0} and filt == {"MO-2": 5, "MO-D": 10}, (full, filt))
sl2 = shortage_list([L("MO-4", "C2", 10, D(2026, 12, 1), reserved=4, issued=3, backflushed=1)], {("C2", "WP"): 0})
check("P10 open requirement = required − issued − backflushed; short = open − reserved − ATP", sl2[0]["open_requirement"] == 6 and sl2[0]["short"] == 2, sl2[0])
over = shortage_list([L("MO-5", "C2", 10, D(2026, 12, 1), issued=12)], {("C2", "WP"): 3})
check("P11 over-issue never makes the open requirement negative", over[0]["open_requirement"] == 0 and over[0]["short"] == 0)

BLOCKING = {"production_version_invalid": "master_data", "revision_invalid": "master_data", "subledger_not_active": "accounting_gate",
            "output_serial_missing": "master_data", "external_supplier_missing": "master_data", "processor_route_missing": "master_data"}
SOFT = {"component_short": "material", "work_center_overloaded": "capacity"}


def release_verdict(reasons):
    if any(r in BLOCKING for r in reasons):
        return "blocked"
    if any(r in SOFT for r in reasons):
        return "ready_with_shortage"
    assert all(r in BLOCKING or r in SOFT for r in reasons)
    return "ready"


def order_reasons(order_lines, atp, overloaded=False, subledger=True, version_ok=True):
    r = []
    if any(x["short"] > 0 for x in shortage_list(order_lines, atp)):
        r.append("component_short")
    if overloaded:
        r.append("work_center_overloaded")
    if not subledger:
        r.append("subledger_not_active")
    if not version_ok:
        r.append("production_version_invalid")
    return r


check("P12 verdicts: blocked by a master-data or accounting reason, ready_with_shortage by material or capacity only, else ready",
      release_verdict(order_reasons([L("A", "C1", 5, D(2026, 12, 1))], {("C1", "WP"): 1}, subledger=False)) == "blocked"
      and release_verdict(order_reasons([L("A", "C1", 5, D(2026, 12, 1))], {("C1", "WP"): 1}, overloaded=True)) == "ready_with_shortage"
      and release_verdict(order_reasons([L("A", "C1", 5, D(2026, 12, 1))], {("C1", "WP"): 5})) == "ready")


def has_component_shortage(order_lines, atp):          # ADR-0034 rule 5 note: ATP below a component's open requirement at Submit
    return any(max(0, x["required"] - x["issued"] - x["backflushed"]) > x["reserved"] + atp.get((x["item"], x["wh"]), 0) for x in order_lines)


agree = True
for _ in range(300):
    ls = [L("R", random.choice(["C1", "C2"]), random.randint(0, 20), D(2026, 12, random.randint(1, 28)), reserved=random.randint(0, 5),
            issued=random.randint(0, 8), line=i) for i in range(random.randint(1, 4))]
    atp = {("C1", "WP"): random.randint(0, 15), ("C2", "WP"): random.randint(0, 15)}
    agree &= has_component_shortage(ls, atp) == ("component_short" in order_reasons(ls, atp))
check("P13 INV-736: the shortage policy input equals the verdict's component_short on 300 random orders", agree)


def llm_verdict_output_ok(out, offered):
    """L1 may name a root cause among offered reason handles; any verdict field is refused."""
    return set(out) <= {"explanation", "root_cause"} and out.get("root_cause") in offered | {"none"}


def raises_shortage_item(order_rows, business_date, horizon=S("production.agent.readiness_horizon_days")):
    """Rule 12: short or uncovered above 0 within the horizon, in every reservation mode."""
    return any((r["short"] > 0 or r["uncovered"] > 0) and r["requested"] <= business_date + dt.timedelta(days=horizon) for r in order_rows)


three = shortage_list([L(f"MO-{i}", "C1", 10, D(2026, 11, 25), line=1) for i in range(3)], {("C1", "WP"): 15})
check("P13b S3: three orders needing 30 against 15 free each look covered on their own view, yet two raise shortage items from the cross-order view",
      all(r["short"] == 0 for r in three) and sum(raises_shortage_item([r], D(2026, 11, 20)) for r in three) == 2)
check("P14 the model cannot set a verdict: an output with a verdict field, or an unoffered handle, is refused",
      not llm_verdict_output_ok({"explanation": "x", "verdict": "ready"}, {"r1"}) and not llm_verdict_output_ok({"explanation": "x", "root_cause": "r9"}, {"r1"})
      and llm_verdict_output_ok({"explanation": "x", "root_cause": "r1"}, {"r1"}))

# ======================================================================= P3 the sweep (rule 15), modes and the halt


class Stock:
    def __init__(self, on_hand):
        self.on_hand = dict(on_hand)
        self.reserved = {}          # (demand, item) -> qty
        self.lock = threading.Lock()

    def atp(self, item):
        return self.on_hand.get((item, "WP"), self.on_hand.get(item, 0)) - sum(q for (d, i), q in self.reserved.items() if i == item)

    def reserve_line(self, demand, item, open_req, locked=True):
        """ReserveProductionOrderComponent: under the order and stock locks, reserve the line's unreserved requirement up to
        available to promise; never others' reservations. Unlocked, the read and the write are apart (the naive race)."""
        def read():
            return max(0, open_req - self.reserved.get((demand, item), 0)), self.atp(item)

        def write(need, atp):
            take = max(0, min(need, atp))
            self.reserved[(demand, item)] = self.reserved.get((demand, item), 0) + take
            return take
        if locked:
            with self.lock:
                return write(*read())
        need, atp = read()
        time.sleep(0.002)
        return write(need, atp)


def sweep(stock, lines, mode, business_date, window_days, mode_check=lambda: "assisted", locked=True):
    if mode == "off":
        return [], "off"
    done = []
    for ln in sorted((x for x in lines if x["state"] == "approved"), key=priority_key):
        if mode_check() == "off":
            return done, "halted"
        if mode == "scheduled" and ln["requested"] > business_date + dt.timedelta(days=window_days):
            continue
        open_req = max(0, ln["required"] - ln["issued"] - ln["backflushed"])
        if open_req > stock.reserved.get((ln["order_no"], ln["item"]), 0):
            done.append((ln["order_no"], stock.reserve_line(ln["order_no"], ln["item"], open_req, locked)))
    return done, "done"


st = Stock({("C1", "WP"): 12})
st.reserved[("SO-9", "C1")] = 8                     # a sales order holds 8
res, _ = sweep(st, [L("MO-1", "C1", 10, D(2026, 12, 1))], "on_release", D(2026, 11, 20), 14)
check("P15 EC-202: stock reserved for a sales order is never taken; the sweep reserves only the 4 free", res == [("MO-1", 4)] and st.reserved[("SO-9", "C1")] == 8, res)


def race(locked, on_hand=10):
    st_ = Stock({("C1", "WP"): on_hand})
    ls = [L("MO-1", "C1", 10, D(2026, 12, 1)), L("MO-2", "C1", 10, D(2026, 12, 2))]
    ts = [threading.Thread(target=sweep, args=(st_, ls, "on_release", D(2026, 11, 20), 14), kwargs={"locked": locked}) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return sum(st_.reserved.values()), max(st_.reserved.values())


tot_locked, max_locked = race(True)
tot_big, max_big = race(True, on_hand=30)
naive = max(race(False)[0] for _ in range(5))
check("P16 EC-201: two sweeps racing under the locks never reserve more than the 10 on hand, nor more than a line's 10 with 30 on hand; the naive race over-reserves",
      tot_locked <= 10 and max_big <= 10 and tot_big == 20 and naive > 10, (tot_locked, tot_big, max_big, naive))
st = Stock({("C1", "WP"): 50})
far = [L("MO-1", "C1", 5, D(2026, 11, 25)), L("MO-2", "C1", 5, D(2027, 3, 1))]
res, _ = sweep(st, far, "scheduled", D(2026, 11, 20), 14)
check("P17 INV-741: in mode scheduled only lines inside the 14-day window are reserved; mode off reserves nothing",
      res == [("MO-1", 5)] and sweep(Stock({("C1", "WP"): 50}), far, "off", D(2026, 11, 20), 14)[1] == "off", res)
calls = {"n": 0}


def mode_after_two():
    calls["n"] += 1
    return "assisted" if calls["n"] <= 2 else "off"


st = Stock({("C1", "WP"): 100})
res, outcome = sweep(st, [L(f"MO-{i}", "C1", 1, D(2026, 12, 1), line=i) for i in range(6)], "on_release", D(2026, 11, 20), 14, mode_check=mode_after_two)
check("P18 EC-217: setting the agent types off mid-sweep stops it at the next call boundary", outcome == "halted" and len(res) == 2, (outcome, len(res)))
st = Stock({("C1", "WP"): 30})
res, _ = sweep(st, [L("MO-1", "C1", 10, D(2026, 12, 1), state="pending_approval"), L("MO-2", "C1", 10, D(2026, 12, 1))], "on_release", D(2026, 11, 20), 14)
check("P19 the sweep reserves only for approved orders; INV-735: reservations never exceed the open requirement",
      res == [("MO-2", 10)] and sweep(st, [L("MO-2", "C1", 10, D(2026, 12, 1))], "on_release", D(2026, 11, 20), 14)[0] == [])

# ======================================================================= P4 upward pegging (rule 8)


def peg(supplies, demands, mto=None):
    """Allocate supply (id, date, qty) to demand (id, date, qty): make-to-order links first, then by date."""
    mto = mto or {}
    left_s = {s[0]: s[2] for s in supplies}
    left_d = {d[0]: d[2] for d in demands}
    out = []
    for s_id, d_id in mto.items():
        q = min(left_s[s_id], left_d[d_id])
        out.append((s_id, d_id, q)); left_s[s_id] -= q; left_d[d_id] -= q
    for s in sorted(supplies, key=lambda x: (x[1], x[0])):
        for d in sorted(demands, key=lambda x: (x[1], x[0])):
            q = min(left_s[s[0]], left_d[d[0]])
            if q > 0:
                out.append((s[0], d[0], q)); left_s[s[0]] -= q; left_d[d[0]] -= q
    return out


ok = True
for _ in range(200):
    sup = [(f"MO-{i}", D(2026, 12, random.randint(1, 28)), random.randint(1, 20)) for i in range(random.randint(1, 4))]
    dem = [(f"SO-{i}", D(2026, 12, random.randint(1, 28)), random.randint(1, 20)) for i in range(random.randint(1, 4))]
    p = peg(sup, dem, {sup[0][0]: dem[0][0]})
    for s in sup:
        ok &= sum(q for a, _, q in p if a == s[0]) <= s[2]
    for d_ in dem:
        ok &= sum(q for _, b, q in p if b == d_[0]) <= d_[2]
    ok &= sum(q for *_, q in p) == min(sum(s[2] for s in sup), sum(d_[2] for d_ in dem))
check("P20 pegging: make-to-order first, then by date; no supply or demand over-pegged and the pegged total is the smaller side (200 random)", ok)

# ======================================================================= P5 exceptions and action messages (rule 17)
TOL = dict(start_grace=S("production.order.start_grace_days"), overdue_grace=S("production.order.overdue_grace_days"),
           in_tol=S("planning.production_reschedule_in_tolerance_days"), out_tol=S("planning.production_reschedule_out_tolerance_days"),
           horizon=S("planning.production_rescheduling_horizon_days"))


def order_exceptions(o, planning_date, tol=TOL):
    out = []
    if o["state"] == "approved" and o["exec"] == "not_started" and o["start"] + dt.timedelta(days=tol["start_grace"]) < planning_date:
        out.append("production_order_start_overdue")
    if o["state"] == "approved" and o["exec"] != "technically_complete" and o["end"] + dt.timedelta(days=tol["overdue_grace"]) < planning_date:
        out.append("production_order_overdue")
    return out


def action_message(o, need_date, needed_qty, planning_date, tol=TOL):
    """need_date: first need the order's supply serves (None: never needed within the horizon)."""
    supply = o["end"]
    if need_date is None:
        return ("cancel", None) if o["exec"] == "not_started" else None
    if (supply - need_date).days > tol["in_tol"]:
        return ("expedite", need_date)
    if (need_date - supply).days > tol["out_tol"] and (supply - planning_date).days <= tol["horizon"]:
        return ("postpone", need_date)
    if o["exec"] == "not_started" and needed_qty < o["G"]:
        return ("reduce", max(needed_qty, o.get("posted", 0)))
    return None


O = lambda **k: dict(dict(state="approved", exec="not_started", start=D(2026, 12, 1), end=D(2026, 12, 10), G=10), **k)
check("P21 start overdue only after the grace day; overdue on the day after the end with grace 0; never for a complete or draft order",
      order_exceptions(O(), D(2026, 12, 2)) == [] and order_exceptions(O(), D(2026, 12, 3)) == ["production_order_start_overdue"]
      and order_exceptions(O(exec="in_progress"), D(2026, 12, 11)) == ["production_order_overdue"]
      and order_exceptions(O(exec="technically_complete"), D(2026, 12, 20)) == [] and order_exceptions(O(state="draft"), D(2026, 12, 20)) == [])
check("P22 EC-205: an out-tolerance of 3 hides a 2-day postponement, while a 1-day lateness is raised with the in-tolerance at 0",
      action_message(O(), D(2026, 12, 12), 10, D(2026, 11, 20)) is None and action_message(O(), D(2026, 12, 9), 10, D(2026, 11, 20)) == ("expedite", D(2026, 12, 9))
      and action_message(O(), D(2026, 12, 14), 10, D(2026, 11, 20)) == ("postpone", D(2026, 12, 14)))
check("P23 postpone only within the horizon; cancel only for a not-started order (EC-215); reduce never below what is posted",
      action_message(O(end=D(2027, 6, 1), start=D(2027, 5, 20)), D(2027, 6, 10), 10, D(2026, 11, 20)) is None
      and action_message(O(), None, 0, D(2026, 11, 20)) == ("cancel", None) and action_message(O(exec="in_progress"), None, 0, D(2026, 11, 20)) is None
      and action_message(O(posted=7), D(2026, 12, 10), 4, D(2026, 11, 20)) == ("reduce", 7))


def bottom_up(proposals, low_level):
    return sorted(proposals, key=lambda p: (-low_level[p["item"]], p["order"]))


props = [{"order": "MO-PARENT", "item": "FG"}, {"order": "MO-SUB", "item": "SUB"}, {"order": "MO-PART", "item": "PART"}]
seq = [p["order"] for p in bottom_up(props, {"FG": 0, "SUB": 1, "PART": 2})]
check("P24 EC-203: rescheduling is proposed bottom-up by low-level code, components before parents", seq == ["MO-PART", "MO-SUB", "MO-PARENT"], seq)


def alt_versions(versions, start, end, short_item):
    """Only versions valid on both the recomputed start and the end, whose structure does not use the short component."""
    return [v["code"] for v in versions if v["from"] <= start and (v["to"] is None or v["to"] >= end) and short_item not in v["items"]]


vs = [{"code": "V2", "from": D(2026, 12, 5), "to": None, "items": {"C9"}}, {"code": "V3", "from": D(2026, 1, 1), "to": None, "items": {"C9"}},
      {"code": "V4", "from": D(2026, 1, 1), "to": None, "items": {"C1"}}]
check("P25 EC-204: a version valid on the end date but not on the recomputed start is not offered; one using the short component neither",
      alt_versions(vs, D(2026, 12, 1), D(2026, 12, 10), "C1") == ["V3"])

# ======================================================================= P6 completion and stalled orders (rule 12)


def completion_candidate(o, pct=S("production.completion.propose_at_percent")):
    ops_done = all(op["final"] or op["cum"] >= op["expected"] for op in o["ops"] if op["internal"])
    if o["type"] == "disassembly":
        recv = all(c["received"] * 100 >= pct * c["planned"] for c in o["co_products"])
    else:
        recv = o["received"] * 100 >= pct * o["G"]
    return o["state"] == "approved" and o["exec"] != "technically_complete" and recv and ops_done


def stalled(o, business_date, days=S("production.order.stalled_days"), calendar=lambda d: d.weekday() < 5):
    if o["exec"] != "in_progress":
        return False
    n, d = 0, o["last_posting"]
    while d < business_date:
        d += dt.timedelta(days=1)
        n += calendar(d)
    return n >= days


ops = [{"internal": True, "final": True, "cum": 97, "expected": 100}, {"internal": False, "final": False, "cum": 0, "expected": 100}]
o97 = dict(type="standard", state="approved", exec="in_progress", G=100, received=97, ops=ops)
check("P26 EC-212: 97% received is a candidate under 95% and not under the default 100%; external operations do not block",
      completion_candidate(o97, 95) and not completion_candidate(o97))
dis = dict(type="disassembly", state="approved", exec="in_progress", co_products=[{"received": 4, "planned": 4}, {"received": 1, "planned": 2}], ops=[])
check("P27 EC-214: a disassembly order qualifies only when every co-product line reaches the share", not completion_candidate(dis)
      and completion_candidate(dict(dis, co_products=[{"received": 4, "planned": 4}, {"received": 2, "planned": 2}])))
check("P28 stalled after 5 working days without a posting, counting the warehouse calendar (a weekend does not count)",
      not stalled({"exec": "in_progress", "last_posting": D(2026, 11, 13)}, D(2026, 11, 19))
      and stalled({"exec": "in_progress", "last_posting": D(2026, 11, 13)}, D(2026, 11, 20)))

# ======================================================================= P7 confirmation checks (rule 22)


def confirmation_checks(c, prev_cum_yield, Q, history, now_min, tol=None):
    tol = tol or dict(yield_pct=S("production.confirmation.yield_tolerance_percent"), action=S("production.confirmation.over_tolerance_action"),
                      act_pct=S("production.confirmation.activity_tolerance_percent"), window=S("production.confirmation.duplicate_window_minutes"))
    results, error = [], None
    base = Q if prev_cum_yield is None else prev_cum_yield
    cum = c["cum_before"] + c["yield"] + c["scrap"]
    if prev_cum_yield is not None and cum > prev_cum_yield:
        results.append("yield_above_previous_operation")
    if cum * 100 > base * (100 + tol["yield_pct"]):
        if tol["action"] == "reject":
            error = "yield_tolerance_exceeded"
        elif prev_cum_yield is None or tol["yield_pct"] > 0:
            results.append("yield_above_tolerance")
    for act, actual in c["activities"].items():
        if actual * 100 > c["standards"][act] * (100 + tol["act_pct"]):
            results.append("activity_above_standard")
    if any(h["order"] == c["order"] and h["op"] == c["op"] and (h["yield"], h["scrap"], h["reason"]) == (c["yield"], c["scrap"], c["reason"])
           and not h["reversed"] and now_min - h["at"] <= tol["window"] for h in history):
        results.append("operation_confirmation_duplicate_suspected")
    return error, results


c1 = dict(order="MO-1", op=20, cum_before=0, scrap=0, reason=None, activities={"machine": 5}, standards={"machine": 5})
tolw = dict(yield_pct=5, action="warn", act_pct=25, window=120)
tolr = dict(tolw, action="reject")
e1, r1 = confirmation_checks(dict(c1, **{"yield": 52}), 50, 100, [], 0, tolw)
e2, r2 = confirmation_checks(dict(c1, **{"yield": 53}), 50, 100, [], 0, tolw)
e3, _ = confirmation_checks(dict(c1, **{"yield": 53}), 50, 100, [], 0, tolr)
check("P29 EC-207: yield 52 over a previous 50 inside 5% gives only yield_above_previous_operation; 53 warns; under reject it is refused",
      e1 is None and r1 == ["yield_above_previous_operation"] and e2 is None and "yield_above_tolerance" in r2 and e3 == "yield_tolerance_exceeded", (r1, r2, e3))
e4, r4 = confirmation_checks(dict(c1, **{"yield": 10}), None, 100, [], 0)
check("P30 the default tolerance 0 with warn reproduces ADR-0034: the first operation against Q, deviations only as check results",
      e4 is None and r4 == [] and confirmation_checks(dict(c1, **{"yield": 101}), None, 100, [], 0)[1] == ["yield_above_tolerance"])
check("P30b N1: with tolerance 0 and warn, a later operation above the previous one gets yield_above_previous_operation only, never twice",
      confirmation_checks(dict(c1, **{"yield": 51}), 50, 100, [], 0, dict(tolw, yield_pct=0))[1] == ["yield_above_previous_operation"])
check("P31 activity above standard by more than 25% gives activity_above_standard; at 25% it does not",
      "activity_above_standard" in confirmation_checks(dict(c1, **{"yield": 10, "activities": {"machine": 6.5}}), None, 100, [], 0)[1]
      and "activity_above_standard" not in confirmation_checks(dict(c1, **{"yield": 10, "activities": {"machine": 6.25}}), None, 100, [], 0)[1])
hist = [dict(order="MO-1", op=20, scrap=0, reason=None, reversed=False, at=0, **{"yield": 10})]
check("P32 EC-208: the same numbers re-typed within 120 minutes are a suspected duplicate; after the window, or when reversed, not",
      "operation_confirmation_duplicate_suspected" in confirmation_checks(dict(c1, **{"yield": 10}), None, 100, hist, 90)[1]
      and "operation_confirmation_duplicate_suspected" not in confirmation_checks(dict(c1, **{"yield": 10}), None, 100, hist, 200)[1]
      and "operation_confirmation_duplicate_suspected" not in confirmation_checks(dict(c1, **{"yield": 10}), None, 100, [dict(hist[0], reversed=True)], 90)[1])

# ======================================================================= P8 capture (rules 4, 19)
ORDERS = {"MO-0001": {"branch": "B1", "state": "approved", "exec": "in_progress"}, "MO-0002": {"branch": "B2", "state": "approved", "exec": "not_started"}}


def resolve_scope(field, human_branches):
    """The scope resolver: a trusted order number resolved to exactly one order in the human's record scope."""
    if not field["trusted"]:
        return ("agent_scope_unresolved", {"redacted": True})
    hits = [n for n, o in ORDERS.items() if n == field["value"] and o["branch"] in human_branches]
    if len(hits) != 1:
        return ("agent_scope_unresolved", {"redacted": True})
    return ("subject", hits[0])


out_scope = resolve_scope({"value": "MO-0002", "trusted": True}, {"B1"})
missing = resolve_scope({"value": "MO-9999", "trusted": True}, {"B1"})
check("P33 EC-206: an order outside the human's branch is unresolved with the same response as a missing order (no leak)",
      out_scope == missing == ("agent_scope_unresolved", {"redacted": True}) and resolve_scope({"value": "MO-0001", "trusted": True}, {"B1"}) == ("subject", "MO-0001"))
check("P34 an untrusted order number (a vision value not confirmed) never sets the scope", resolve_scope({"value": "MO-0001", "trusted": False}, {"B1"})[0] == "agent_scope_unresolved")

COMMANDS = {  # name: (effect class, is_draft_only, proposal_bound)
    "CreateOperationConfirmation": ("other", True, False), "CreateProductionIssue": ("other", True, False), "CreateProductionReceipt": ("other", True, False),
    "PostOperationConfirmation": ("posting", False, False), "UpdateProductionOrder": ("other", True, False), "CreateChangeProposal": ("other", True, False),
    "ReserveProductionOrderComponent": ("other", False, False), "CompleteProductionOrder": ("other", False, True), "ReopenProductionOrder": ("other", False, True),
    "TransferStockReservation": ("other", False, True), "SubmitProductionOrder": ("other", False, False), "ApproveProductionOrder": ("other", False, False),
    "StartAgentRun": ("other", False, False), "ImportOperationConfirmation": ("other", False, False), "CancelProductionOrder": ("other", False, False),
    "FirmPlannedOrder": ("other", False, True), "CreateStockTransfer": ("other", True, False), "RunProductionOrderCheck": ("other", False, False)}


def dispatch(cmd, tainted, tool_list, payload_orders=(), subject=None):
    if cmd not in tool_list:
        return "tool_not_allowed"
    if tainted and not COMMANDS[cmd][1]:
        return "tainted_run_not_allowed"
    if tainted and any(o != subject for o in payload_orders):
        return "tainted_read_out_of_scope"
    return "ok"


TOOLS = {"production": {"ReserveProductionOrderComponent", "UpdateProductionOrder", "CreateChangeProposal", "CreateStockTransfer"},
         "production_capture": {"CreateOperationConfirmation", "CreateProductionIssue", "CreateProductionReceipt"},
         "production_variance": set()}
FORBIDDEN = {c for c, (eff, _, pb) in COMMANDS.items() if eff == "posting" or pb or re.match(r"^(Submit|Post|Approve|Issue|Send)", c)} | {
    "StartAgentRun", "ImportOperationConfirmation", "FirmPlannedOrder", "RunProductionOrderCheck"}
check("P35 INV-730: no production tool list holds a forbidden command (posting, Submit/Post/Approve, proposal-bound, StartAgentRun, the import, planned orders)",
      all(not (t & FORBIDDEN) for t in TOOLS.values()) and {"TransferStockReservation", "CompleteProductionOrder"} <= FORBIDDEN)
check("P36 EC-209: a capture run told to post, or to draft for another order, is refused; its own order's draft passes",
      dispatch("PostOperationConfirmation", True, TOOLS["production_capture"] | {"PostOperationConfirmation"}) == "tainted_run_not_allowed"
      and dispatch("CreateOperationConfirmation", True, TOOLS["production_capture"], ["MO-0002"], "MO-0001") == "tainted_read_out_of_scope"
      and dispatch("CreateOperationConfirmation", True, TOOLS["production_capture"], ["MO-0001"], "MO-0001") == "ok"
      and dispatch("ReserveProductionOrderComponent", True, TOOLS["production"]) == "tainted_run_not_allowed")


def capture_draft(fields, llm_out):
    """Quantities, lot and date come from extraction fields as stated; the model's output may hold only handles and codes."""
    if any(isinstance(v, (int, float)) for k, v in llm_out.items() if k != "operation_handle_index"):
        raise ValueError("llm_output_invalid")
    if set(llm_out) - {"operation_handle", "operation_handle_index", "reason_code", "note"}:
        raise ValueError("llm_output_invalid")
    return {"yield": fields["yield_quantity"]["value"], "scrap": fields.get("scrap_quantity", {"value": 0})["value"],
            "posting_date": fields["posting_date"]["value"], "evidence": sorted(f["id"] for f in fields.values()),
            "reason_code": llm_out.get("reason_code"), "entry_source": "capture_agent"}


F = {"production_order_number": {"id": "f1", "value": "MO-0001"}, "yield_quantity": {"id": "f2", "value": "48"},
     "scrap_quantity": {"id": "f3", "value": "2"}, "posting_date": {"id": "f4", "value": "2026-11-16"}}
dr = capture_draft(F, {"operation_handle": "op20", "reason_code": "surface_defect", "note": "two scratched"})
try:
    capture_draft(F, {"operation_handle": "op20", "yield": 50})
    model_num = False
except ValueError:
    model_num = True
check("P37 INV-733: draft quantities equal the extraction's stated values with field IDs as evidence; a model-written quantity is refused",
      dr["yield"] == "48" and dr["scrap"] == "2" and dr["evidence"] == ["f1", "f2", "f3", "f4"] and model_num)


def milestone_plan(ops, milestone_no, cum):
    """ADR-0034 rule 12: earlier internal non-milestone operations back to the previous milestone are raised to the milestone's cumulative quantity."""
    out = []
    for op in sorted(ops, key=lambda o: -o["no"]):
        if op["no"] >= milestone_no:
            continue
        if op["milestone"]:
            break
        if op["internal"] and op["cum"] < cum:
            out.append((op["no"], cum - op["cum"]))
    return sorted(out)


check("P38 EC-210: the milestone's generated confirmations come from code: operations 10 and 20 raised, external 25 skipped, stop at milestone 5",
      milestone_plan([{"no": 5, "milestone": True, "internal": True, "cum": 50}, {"no": 10, "milestone": False, "internal": True, "cum": 20},
                      {"no": 20, "milestone": False, "internal": True, "cum": 0}, {"no": 25, "milestone": False, "internal": False, "cum": 0}], 30, 50) == [(10, 30), (20, 50)])


def post_rank(policy_rank, actor, tainted, hold_allowed=False):
    """ADR-0043 rule 9 floor 3 and rule 10: a non-human post of a tainted version is human_post; a type that may not wait cannot hold."""
    if tainted and actor != "human":
        return "human_post"
    if policy_rank not in ("allow",) and not hold_allowed:
        return "human_post"
    return policy_rank


check("P39 EC-216: a policy that would allow a tainted capture draft without a person still gives human_post (floor 3)",
      post_rank("allow", "system", True) == "human_post" and post_rank("allow", "human", True) == "allow")

# ======================================================================= P9 the production import gate (rule 25)


def evidence_ok(drafts, months, min_drafts=S("production.mes_import.min_evidence_drafts"), min_pct=S("production.mes_import.min_unchanged_percent"),
                min_months=S("production.mes_import.min_evidence_months")):
    """GetProductionImportShadowEvaluation: enough import drafts over enough months, enough posted unchanged, none to another order or operation."""
    unchanged = sum(1 for d_ in drafts if d_ == "unchanged")
    return (len(drafts) >= min_drafts and months >= min_months and unchanged * 100 >= min_pct * len(drafts) and "other_target" not in drafts)


def import_row(row, settings, policy_enabled_with_evidence, seen_refs, check_results, state_ok=True, credential_post=True):
    if row["external_reference"] in seen_refs:
        return "duplicate_external_document"
    seen_refs.add(row["external_reference"])
    if settings["auto_post"] and policy_enabled_with_evidence and credential_post and not check_results and state_ok:
        return "posted_by_integration"
    return "draft_for_person"


check("P39b the import's evidence: 300 drafts over 2 months at 99% unchanged suffice; 299 drafts, 1 month, 98% or one draft posted to another operation do not",
      evidence_ok(["unchanged"] * 297 + ["edited"] * 3, 2) and not evidence_ok(["unchanged"] * 299, 2) and not evidence_ok(["unchanged"] * 300, 1)
      and not evidence_ok(["unchanged"] * 294 + ["edited"] * 6, 2) and not evidence_ok(["unchanged"] * 299 + ["other_target"], 2))
refs = set()
check("P40 EC-218: auto-post off keeps drafts; on without evidence too; on with evidence posts a clean row; a check result or a failed state keeps a draft; a repeated reference is refused",
      import_row({"external_reference": "r1"}, {"auto_post": False}, True, refs, []) == "draft_for_person"
      and import_row({"external_reference": "r2"}, {"auto_post": True}, False, refs, []) == "draft_for_person"
      and import_row({"external_reference": "r3"}, {"auto_post": True}, True, refs, []) == "posted_by_integration"
      and import_row({"external_reference": "r4"}, {"auto_post": True}, True, refs, ["yield_above_tolerance"]) == "draft_for_person"
      and import_row({"external_reference": "r5"}, {"auto_post": True}, True, refs, [], state_ok=False) == "draft_for_person"
      and import_row({"external_reference": "r3"}, {"auto_post": True}, True, refs, []) == "duplicate_external_document"
      and import_row({"external_reference": "r6"}, {"auto_post": True}, True, refs, ["yield_above_previous_operation"]) == "draft_for_person"
      and import_row({"external_reference": "r7"}, {"auto_post": True}, True, refs, [], credential_post=False) == "draft_for_person")

# ======================================================================= P10 reservation transfer (rule 24)


def transfer(reservations, src, target_line, qty, from_proposal, lines_kind, target_unreserved=10 ** 9, target_atp=0):
    r = reservations[src]
    target_short = max(0, target_unreserved - target_atp)          # rule 24: computed at execution under the target order's lock
    if not from_proposal:
        return "proposal_required"
    if lines_kind.get(r["line"]) != "production_order_component" or lines_kind.get(target_line) != "production_order_component":
        return "reservation_transfer_invalid"
    if qty > r["qty"] - r["picked"] or qty <= 0 or qty > target_short:
        return "reservation_transfer_invalid"
    r["qty"] -= qty
    if r["qty"] == 0:
        r["state"] = "canceled"
    nid = f"R{len(reservations) + 1}"
    reservations[nid] = {"line": target_line, "qty": qty, "picked": 0, "state": "open", "transferred_from": src}
    return nid


RS = {"R1": {"line": "MO-2/1", "qty": 8, "picked": 3, "state": "open"}, "R2": {"line": "SO-1/1", "qty": 5, "picked": 0, "state": "open"}}
KIND = {"MO-2/1": "production_order_component", "MO-1/1": "production_order_component", "SO-1/1": "sales_order_line"}
before = sum(r["qty"] for r in RS.values() if r["state"] != "canceled")
a = transfer(RS, "R1", "MO-1/1", 5, False, KIND)
b = transfer(RS, "R1", "MO-1/1", 6, True, KIND)
c = transfer(RS, "R2", "MO-1/1", 1, True, KIND)
d_ = transfer(RS, "R1", "MO-1/1", 5, True, KIND)
after = sum(r["qty"] for r in RS.values() if r["state"] != "canceled")
check("P41 EC-219: outside a proposal proposal_required; above the unpicked quantity or from a sales order invalid; through one the total is conserved",
      a == "proposal_required" and b == c == "reservation_transfer_invalid" and d_ == "R3" and RS["R1"]["qty"] == 3
      and RS["R3"]["transferred_from"] == "R1" and before == after, (a, b, c, d_))

RS2 = {"R1": {"line": "MO-2/1", "qty": 8, "picked": 0, "state": "open"}}
stock_t = Stock({("C1", "WP"): 0})
open_req_t, reserved_t = 5, 0
unres = lambda: max(0, open_req_t - reserved_t)
first = transfer(RS2, "R1", "MO-1/1", 6, True, KIND, unres(), stock_t.atp("C1"))
stock_t.on_hand[("C1", "WP")] = 5                     # EC-200: a goods receipt arrives; nothing reserves it (mode off)
stale = transfer(RS2, "R1", "MO-1/1", 3, True, KIND, unres(), stock_t.atp("C1"))
stock_t.on_hand[("C1", "WP")] = 2                     # partly covered: short 3
partial = transfer(RS2, "R1", "MO-1/1", 3, True, KIND, unres(), stock_t.atp("C1"))
check("P41b S2 r2: the cap is the target's short quantity from stock: above 5 refused; after a receipt of 5 that nothing reserved, refused (EC-200); with 2 free, 3 allowed",
      first == "reservation_transfer_invalid" and stale == "reservation_transfer_invalid" and partial == "R2" and RS2["R1"]["qty"] == 5, (first, stale, partial))

# ======================================================================= P11 variance drivers, ranking, residual (rules 9-11, 20)


def usage_variance(required, Q, progress, issued, backflushed):
    target = required * progress / Q
    return dict(target=target, actual=issued + backflushed, variance=issued + backflushed - target, category="input_quantity")


uv = usage_variance(20, 10, 5, 12, 0)
check("P42 usage variance at progress: 20 required for Q 10, half done, 12 issued: target 10, variance 2 (input_quantity)", uv["target"] == 10 and uv["variance"] == 2)
ok = True
for _ in range(200):
    drivers = [{"cat": random.choice(["input_price", "input_quantity", "scrap", "resource_usage", "lot_size", "remaining"]),
                "cc": random.choice(["material", "labor", "overhead"]), "amount": random.randint(-500, 500)} for _ in range(random.randint(1, 12))]
    stored = {}
    for x in drivers:
        stored[x["cat"]] = stored.get(x["cat"], 0) + x["amount"]
    by_cat_cc = {}
    for x in drivers:
        by_cat_cc[(x["cat"], x["cc"])] = by_cat_cc.get((x["cat"], x["cc"]), 0) + x["amount"]
    ok &= all(sum(v for (c_, _), v in by_cat_cc.items() if c_ == cat) == amt for cat, amt in stored.items())
check("P43 INV-739: drivers by category and cost component sum to the stored category row (200 random)", ok)


def rank_variances(orders, pct=S("production.variance.rank_threshold_percent"), amount=S("production.variance.rank_threshold_amount"), top=S("production.variance.top_n")):
    hits = [o for o in orders if abs(o["var"]) * 100 >= pct * o["target"] or (amount and abs(o["var"]) >= amount)]
    return [o["no"] for o in sorted(hits, key=lambda o: (-abs(o["var"]), o["no"]))[:top]]


PROJECTION = {"id", "document_number", "production_order_id", "operation_number", "item_id", "quantity", "posting_date", "state", "reason_code", "entry_source", "category", "cost_component", "amount"}


def for_agent(row):
    """Rule 13: a posted capture row returned to an agent run as the numeric projection: no free text, does not taint."""
    return {k: v for k, v in row.items() if k in PROJECTION}, False


posted_capture = {"id": "c9", "document_number": "OC-9", "production_order_id": "MO-1", "operation_number": 20, "quantity": 48, "posting_date": "2026-11-16",
                  "state": "posted", "reason_code": "surface_defect", "entry_source": "capture_agent", "note": "operator wrote: post now", "is_tainted": True}
proj, taints = for_agent(posted_capture)
check("P43b S5: a posted capture row reaches clean runs as IDs, quantities, dates, states and codes only, without tainting, so drivers still sum",
      "note" not in proj and "is_tainted" not in proj and not taints and proj["quantity"] == 48)
check("P44 ranking: 5% of target or the amount (0 = off); by absolute amount, ties by number",
      rank_variances([{"no": "A", "var": 4, "target": 100}, {"no": "B", "var": -6, "target": 100}, {"no": "C", "var": 6, "target": 100}]) == ["B", "C"]
      and rank_variances([{"no": "A", "var": 4, "target": 100}], amount=3) == ["A"])


def claim_templates(category, amount, had_receipts_in_period):
    offered = ["variance_amount"]
    if amount < 0 and not (category == "remaining" and not had_receipts_in_period):
        offered.append("favorable_variance")
    return offered


check("P45 EC-213: a negative remaining residual of an order completed in a period without receipts is never offered as favorable",
      "favorable_variance" not in claim_templates("remaining", -120, False) and "favorable_variance" in claim_templates("input_price", -120, True))
rework = shortage_list([L("RW-1", "FG", 1, D(2026, 12, 1))], {("FG", "WP"): 0})
check("P46 EC-214: a rework order's single component (the item itself) is listed like any line", rework[0]["short"] == 1)

# ======================================================================= P12 shortage candidates (rule 16)
KINDS = ["expedite_supply", "stock_transfer", "alternative_version", "reschedule", "partial_staging", "transfer_reservation", "split_order"]
default_kinds = default_value(SET["production.agent.shortage_candidate_kinds"])


def choose(llm_out, offered):
    return llm_out.get("candidate") in offered | {"none"} and not any(isinstance(v, (int, float)) for v in llm_out.values())


check("P47 the default candidate kinds exclude reservation transfer and split, which a company enables; the model picks only an offered handle and writes no number",
      set(default_kinds) == {"expedite_supply", "stock_transfer", "alternative_version", "reschedule"} and set(default_kinds) < set(KINDS)
      and choose({"candidate": "c2"}, {"c1", "c2"}) and not choose({"candidate": "c9"}, {"c1"}) and not choose({"candidate": "c1", "new_start": 3}, {"c1"}))


def cand_key(x):
    """Rule 16's total order: kind, then (transfer_reservation only) donor priority latest first, start, larger cover, document, line."""
    return (KINDS.index(x[0]), -x[5], x[1], -x[2], x[3], x[4])


def candidate_set(c):
    S_, out = c["uncovered"], []                       # tuples: kind, start, cover, document, line, donor priority (0 elsewhere)
    for m in c["messages"]:
        if m["run"] == c["latest_run"] and m["proposed"] <= c["start"]:
            out.append(("expedite_supply", m["proposed"], min(S_, m["open"]), m["doc"], m["line"], 0))
    for wh, (atp, lead) in c["warehouses"].items():
        if atp > 0:
            out.append(("stock_transfer", c["today"] + dt.timedelta(days=lead), min(S_, atp), wh, 0, 0))
    for v in c["versions"]:
        if c["state"] in ("draft", "pending_approval") and c["item"] not in v["items"]:
            out.append(("alternative_version", v["start"], S_, v["code"], 0, 0))
    if c["cover_date"]:
        out.append(("reschedule", c["cover_date"], S_, c["order"], 0, 0))
    if c.get("ops_covered"):
        out.append(("partial_staging", c["start"], 0, c["order"], 0, 0))
    for d_ in c["donors"]:
        q = min(S_, d_["unpicked"], c["target_short"])
        if q > 0:
            out.append(("transfer_reservation", c["start"], q, d_["doc"], 0, d_["priority"]))
    if 0 < c["covered_g"] < c["G"]:
        out.append(("split_order", c["start"], c["covered_g"], c["order"], 0, 0))
    return [x for x in out if x[0] in c["kinds"]]


def candidates(c, cap=7):
    """Rule 16: the best candidate of each enabled kind first, in kind order, then the rest in the total order, at most 7."""
    allc = sorted(candidate_set(c), key=cand_key)
    firsts, seen = [], set()
    for x in allc:
        if x[0] not in seen:
            seen.add(x[0]); firsts.append(x)
    rest = [x for x in allc if x not in firsts]
    return (firsts + rest)[:cap]


def brute_select(cands, cap=7):
    """An independent selection by repeated minimum, without sorting: per kind its minimum, then the minimum of what is left."""
    pool, out = list(cands), []
    for k in KINDS:
        of_k = [x for x in pool if x[0] == k]
        if of_k:
            m = min(of_k, key=cand_key); out.append(m); pool.remove(m)
    while pool and len(out) < cap:
        m = min(pool, key=cand_key); out.append(m); pool.remove(m)
    return out[:cap]


def covered_g(lines_, G):
    """Rule 16 split: lines with required 0 skipped; a fixed-quantity line allows a split only when fully covered."""
    if any(ln.get("fixed") and ln["uncovered"] > 0 for ln in lines_):
        return 0
    vals = [int((ln["required"] - ln["uncovered"]) * G / ln["required"]) for ln in lines_ if ln["required"] > 0 and not ln.get("fixed")]
    return min(vals) if vals else G      # no scaling line: G, which the caller's 0 < covered G < G test reads as "no split", as intended


ok, ok_b = True, True
for _ in range(150):
    case = dict(uncovered=random.randint(1, 20), start=D(2026, 12, 10), today=D(2026, 11, 20), latest_run="r2", item="C1", order="MO-1",
                state=random.choice(["draft", "approved"]), G=10, target_short=random.randint(0, 20), kinds=KINDS, ops_covered=random.random() < 0.5,
                messages=[dict(run=random.choice(["r1", "r2"]), proposed=D(2026, 12, random.randint(1, 20)), open=random.randint(1, 15), doc=f"PO-{i}", line=1) for i in range(3)],
                warehouses={f"W{i}": (random.randint(0, 9), random.randint(1, 4)) for i in range(3)},
                versions=[dict(code=f"V{i}", start=D(2026, 12, random.randint(1, 9)), items={random.choice(["C1", "C9"])}) for i in range(2)],
                cover_date=random.choice([None, D(2026, 12, 18)]), donors=[dict(doc=f"MO-{9 - i}", priority=i, unpicked=random.randint(0, 6)) for i in range(3)],
                covered_g=random.randint(0, 10))
    base_ = candidates(case)
    shuffled = dict(case, messages=random.sample(case["messages"], 3), donors=random.sample(case["donors"], 3),
                    warehouses=dict(random.sample(sorted(case["warehouses"].items()), 3)), versions=random.sample(case["versions"], 2))
    ok &= candidates(shuffled) == base_ and len(base_) <= 7
    ok &= all(not (m["run"] == "r1" and ("expedite_supply", m["proposed"], min(case["uncovered"], m["open"]), m["doc"], 1, 0) in base_) for m in case["messages"])
    kinds_present = {x[0] for x in candidate_set(case)}
    ok &= kinds_present <= {x[0] for x in base_}
    ok_b &= base_ == brute_select(candidate_set(case))
check("P47b S4: candidates are the same for shuffled input, at most 7, never from a stale planning run's message", ok)
check("P47c S4: the selection equals an independent repeated-minimum selection over the same candidate set (150 random cases; this proves the selection, not the candidate rules)", ok_b)
crowd = dict(uncovered=10, start=D(2026, 12, 10), today=D(2026, 11, 20), latest_run="r2", item="C1", order="MO-1", state="approved", G=10, target_short=10,
             kinds=KINDS, ops_covered=False, cover_date=D(2026, 12, 18), covered_g=6, versions=[],
             messages=[dict(run="r2", proposed=D(2026, 12, i + 1), open=3, doc=f"PO-{i}", line=1) for i in range(4)],
             warehouses={f"W{i}": (5, i + 1) for i in range(3)},
             donors=[dict(doc="MO-7", priority=1, unpicked=4), dict(doc="MO-9", priority=3, unpicked=2), dict(doc="MO-8", priority=2, unpicked=4)])
got = candidates(crowd)
kinds_got = [x[0] for x in got]
check("P47e S1 r2: 4 expedite lines and 3 warehouses still leave room for reschedule, transfer_reservation and split_order, within 7",
      len(got) == 7 and {"reschedule", "transfer_reservation", "split_order", "expedite_supply", "stock_transfer"} <= set(kinds_got), kinds_got)
donor_order = [x[3] for x in sorted([x for x in candidate_set(crowd) if x[0] == "transfer_reservation"], key=cand_key)]
check("P47f S1 r2: reservation transfer donors come latest in the priority first, ahead of cover", donor_order == ["MO-9", "MO-8", "MO-7"], donor_order)
check("P47g N4: partial staging is offered when an operation is fully covered, with cover 0 and the order's start",
      ("partial_staging", D(2026, 12, 10), 0, "MO-1", 0, 0) in candidate_set(dict(crowd, ops_covered=True)))
check("P47d S4, N3: split covers the largest G the covered lines support, rounded down (5); a line with required 0 is skipped; an uncovered fixed-quantity line allows no split",
      covered_g([{"required": 20, "uncovered": 10}, {"required": 10, "uncovered": 3}], 10) == 5
      and covered_g([{"required": 20, "uncovered": 10}, {"required": 0, "uncovered": 0}], 10) == 5
      and covered_g([{"required": 20, "uncovered": 10}, {"required": 1, "uncovered": 1, "fixed": True}], 10) == 0
      and covered_g([{"required": 20, "uncovered": 10}, {"required": 1, "uncovered": 0, "fixed": True}], 10) == 5)


# ======================================================================= C: the applied docs
print("== C: the applied docs")
check("C01 the status line is exact", "\nStatus: proposed (2026-11-15) under ADR-0005 (builder Claude Opus 5.5).\n" in ADR_TEXT
      or "\nStatus: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5) after three review rounds.\n" in ADR_TEXT)
invs = [int(x) for x in re.findall(r"^- \*\*INV-(\d+):\*\*", ADR_TEXT, re.M)]
ecs = [int(x) for x in re.findall(r"^- \*\*EC-(\d+):\*\*", ADR_TEXT, re.M)]
clash = [x for x in re.findall(r"(?:INV-7[0-2]\d|EC-1[89]\d)\b", ADR_TEXT)]
check("C02 the ADR's invariants are INV-730 to INV-741 and its edge cases EC-200 to EC-219, clear of ADR-0063's INV-700 to INV-729 and EC-180 to EC-199",
      invs == list(range(730, 742)) and ecs == list(range(200, 220)) and clash == [], (invs[:2], ecs[:2], clash))
sections = re.findall(r"^## (.+)$", ADR_TEXT, re.M)
check("C03 sections: Decision with numbered rules, then Options considered, Consequences, Documents updated, Edge cases and invariants",
      sections == ["Decision", "Options considered", "Consequences", "Documents updated", "Edge cases and invariants"] and "### Rules" in ADR_TEXT, sections)
rules = [int(x) for x in re.findall(r"^(\d+)\. ", ADR_TEXT.split("### Rules")[1].split("\n## ")[0], re.M)]
check("C04 the rules are numbered 1 to 31 without gaps", rules == list(range(1, 32)), rules[-3:])
check("C05 no country-specific content in the ADR", not re.search(r"Vietnam|VND|TT99|tt99|l10n_vn|VAS\b|Asia/Ho_Chi_Minh", ADR_TEXT))


def rows(name):
    with open(os.path.join(DOCS, "catalogs", name), encoding="utf-8") as f:
        return list(csv.reader(f))


bad = {}
for name in ("invariants.csv", "edge-cases.csv", "work-item-kinds.csv", "authorization-areas.csv", "role-template-levels.csv"):
    r = rows(name)
    bad[name] = [x[0] for x in r[1:] if x and len(x) != len(r[0])]
check("C06 every catalog row has its header's field count", all(v == [] for v in bad.values()), {k: v[:3] for k, v in bad.items() if v})
inv = {x[0]: x for x in rows("invariants.csv")[1:]}
ec = {x[0]: x for x in rows("edge-cases.csv")[1:]}
check("C07 INV-730 to INV-741 and EC-200 to EC-219 are in the catalogs, without a first step (production core step pending)",
      all(f"INV-{n}" in inv and inv[f"INV-{n}"][4] == "" for n in range(730, 742)) and all(f"EC-{n}" in ec and ec[f"EC-{n}"][3] == "" for n in range(200, 220)))
dup = [k for k, n in collections.Counter(x[0] for x in rows("invariants.csv")[1:] + rows("edge-cases.csv")[1:]).items() if n > 1]
check("C08 no duplicate invariant or edge case codes", dup == [], dup)
wik = {x[0]: x for x in rows("work-item-kinds.csv")[1:]}
need = {"production_order_exception", "production_component_shortage", "production_completion_candidate", "production_order_stalled",
        "production_standard_review", "shop_floor_report_extracted", "production_import_review"}
check("C09 the seven work item kinds exist; exception items resolve only by the system (hard lock 6)",
      need <= set(wik) and all(wik[k][5] == "system" for k in ("production_order_exception", "production_component_shortage", "production_completion_candidate", "production_order_stalled", "production_standard_review")))
d04 = open(os.path.join(DOCS, "design/DS-04-command-envelope.md"), encoding="utf-8").read()
codes = ["yield_tolerance_exceeded", "reservation_transfer_invalid", "yield_above_tolerance", "activity_above_standard",
         "operation_confirmation_duplicate_suspected", "reservation_deferred"]
check("C10 DS-04 has each new code exactly once", all(d04.count(f"| `{c}` |") == 1 for c in codes), [c for c in codes if d04.count(f"| `{c}` |") != 1])
outcome_codes = {o.split(":", 1)[1] for x in ec.values() if x[0] in {f"EC-{n}" for n in range(200, 220)} for o in x[8].split("|") if ":" in o}
check("C11 every must_reject code of EC-200 to EC-219 is in DS-04", all(f"| `{c}` |" in d04 for c in outcome_codes), sorted(c for c in outcome_codes if f"| `{c}` |" not in d04))
tl = {(x[0], x[1]): x for x in rows("role-template-levels.csv")[1:]}
check("C12 leaves under agent and the seeded template levels exist",
      {"agent_production", "agent_production_capture", "agent_production_variance"} <= LEAVES
      and ("production_planner", "agent_production") in tl and ("shop_floor_lead", "agent_production_capture") in tl and ("chief_accountant", "agent_production_variance") in tl)
SC = os.path.join(DOCS, "catalogs", "settings.csv")
srows = {r["key"]: r for r in csv.DictReader(open(SC, encoding="utf-8"))} if os.path.exists(SC) else {}
if any(k in srows for k in SET):
    mism = [k for k, v in SET.items() if k not in srows or (srows[k]["scope"], srows[k]["value_type"], srows[k]["core_default"], srows[k]["bounds"],
            srows[k]["direction"], srows[k]["leaf"], srows[k]["outdates"]) != (v["scope"], v["type"], v["default"], v["bounds"], v["tighter"], v["leaf"], v["outdates"])]
    check("C14 the settings catalog holds rule 23's rows: all 23, equal to the ADR, with storage setting_value and change effect immediate",
          mism == [] and all(srows[k]["storage"] == "setting_value" and srows[k]["change_effect"] == "immediate" for k in SET), mism[:3])
else:
    check("C14 the settings catalog does not hold rule 23's rows yet, so rule 23 holds them and names the dependency on ADR-0063", "Dependency on ADR-0063" in ADR_TEXT)
oq = open(os.path.join(DOCS, "open-questions.md"), encoding="utf-8").read()
oql = {k: [l for l in oq.splitlines() if l.startswith(k)] for k in ("- [ ] (DS-32, DS-34, DS-47) Readings", "- [ ] (DS-32, DS-34) Agent values", "- [ ] (DS-42, DS-22) Reservations", "- [ ] (DS-52) Production execution")}
check("C15 B1: four existing open questions name ADR-0064 (readings p-r, budgets and import evidence, reservation priority, a partial note on DS-52 that stays open); none is added",
      all(len(v) == 1 and "ADR-0064" in v[0] for v in oql.values()) and "(p)" in oql["- [ ] (DS-32, DS-34, DS-47) Readings"][0]
      and oql["- [ ] (DS-52) Production execution"][0].startswith("- [ ] ") and oq.count("ADR-0064") == 4)
ds17 = open(os.path.join(DOCS, "design/DS-17-synthetic-dataset.md"), encoding="utf-8").read()
n_ec = sum(1 for x in rows("edge-cases.csv")[1:] if x and x[0].startswith("EC-"))
check("C16 N11: DS-17 states the catalog's true edge case count", f"Version 0.1.0 has {n_ec} edge cases." in ds17, n_ec)
bl = open(os.path.join(DOCS, "design/backlog.md"), encoding="utf-8").read()
check("C13 the DS-57 backlog row names ADR-0064", bool(re.search(r"^\| DS-57 \|.*ADR-0064", bl, re.M)))

# ======================================================================= D: database checks
if "--load" in sys.argv:
    print("== D: database checks")
    import psycopg  # noqa: F401
    from load_all import load_all  # noqa: E402
    dsn = os.environ.get("ERPME_LAB_DSN", "host=127.0.0.1 port=5561 dbname=erpme_lab user=lab")
    n_tables = load_all(dsn, DOCS)
    check("D01 load_all.py loads every DDL file of design/", n_tables > 200, n_tables)
    c = conn(); c.autocommit = True
    X = c.execute
    I = {k: new() for k in "u co co2 ea ig vc itg p1 i1 p2 i2 cal cc WP zP bP WC PR doc doc2 docX OP OPX comp comp2 out i3 p3 lot dsl dsl2 dslX R1 R2 RX c1 c2 c3".split()}
    t = str(I["co"])[-8:]
    B_ = '{"kind": "company_decision"}'
    X("insert into currency (code, minor_unit) values ('USD', 2) on conflict do nothing")
    X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I["u"], "u25" + t))
    for k, code in (("co", "C25-"), ("co2", "C25B-")):
        X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
          " values (%s,%s,'Co','USD','UTC','l10n_test','test','warehouse',%s,'en')", (I[k], code + t, I["u"]))
    X("select set_config('erpme.company_id', %s, false)", (str(I["co"]),))
    X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,'EA','count',2)", (I["ea"], "EA25" + t))
    for tbl, k in (("item_group", "ig"), ("valuation_class", "vc"), ("item_tax_group", "itg")):
        X(f"insert into {tbl} (id, company_id, code, name, basis) values (%s,%s,'std','Std',%s)", (I[k], I["co"], B_))
    for pk, ik, code in (("p1", "i1", "FG25"), ("p2", "i2", "C25")):
        X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
             item_tax_group_id, tracking) values (%s,%s,%s,%s,'stock',%s,%s,%s,%s,%s,%s,'none')""", (I[pk], I["co"], code, code, I["ig"], I["vc"], I["ea"], I["ea"], I["ea"], I["itg"]))
        X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,%s)", (I[ik], I["co"], I[pk], code))
    X("insert into working_calendar (id, company_id, code, name, working_weekdays) values (%s,%s,'STD','Std','{1,2,3,4,5}')", (I["cal"], I["co"]))
    X("insert into cost_center (id, company_id, code, name, kind) values (%s,%s,'ASM','Assembly','production')", (I["cc"], I["co"]))
    with c.transaction():
        X("insert into warehouse (id, company_id, code, name, kind, working_calendar_id, default_bin_id) values (%s,%s,'WP','WP','physical',%s,%s)", (I["WP"], I["co"], I["cal"], I["bP"]))
        X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'Z','Zone')", (I["zP"], I["co"], I["WP"]))
        X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEF','WP25-DEF','storage')", (I["bP"], I["co"], I["WP"], I["zP"]))
    X("""insert into work_center (id, company_id, code, name, production_warehouse_id, working_calendar_id, hours_per_day, cost_center_id, recorded_at)
         values (%s,%s,'WC1','Line',%s,%s,8,%s,now())""", (I["WC"], I["co"], I["WP"], I["cal"], I["cc"]))
    X("""insert into planning_run (id, company_id, planning_date, requested_by_user_id, state, started_at, recorded_at) values (%s,%s,'2026-11-16',%s,'running',now(),now())""",
      (I["PR"], I["co"], I["u"]))

    def document(cx, dk, dtype, state="approved", co="co"):
        cx.execute("insert into document (id, company_id, document_type, state, version, created_by_user_id, change_state, recorded_at) values (%s,%s,%s,%s,1,%s,'none',now())",
                   (I[dk], I[co], dtype, state, I["u"]))

    def order(cx, dk, co="co"):
        document(cx, dk, "production_order", co=co)
        cx.execute("""insert into production_order (id, company_id, order_type, item_id, production_warehouse_id, good_quantity, planned_output_quantity, planned_start_date,
                      planned_end_date, recorded_at) values (%s,%s,'rework',%s,%s,10,10,'2026-12-01','2026-12-10',now())""", (I[dk], I[co], I["i1"], I["WP"]))
    with c.transaction():
        order(c, "doc")
        X("""insert into production_order_operation (id, company_id, production_order_id, line_number, operation_number, work_center_id, control, expected_quantity,
             scheduled_start_date, scheduled_end_date, recorded_at) values (%s,%s,%s,1,10,%s,'internal',10,'2026-12-01','2026-12-02',now())""", (I["OP"], I["co"], I["doc"], I["WC"]))
        X("""insert into production_order_component (id, company_id, production_order_id, line_number, component_item_id, required_quantity, issue_warehouse_id, operation_number,
             consumption_method, requested_date, recorded_at) values (%s,%s,%s,%s,%s,10,%s,10,'manual','2026-12-01',now())""", (I["comp"], I["co"], I["doc"], 1, I["i2"], I["WP"]))
        X("""insert into production_order_component (id, company_id, production_order_id, line_number, component_item_id, required_quantity, issue_warehouse_id, operation_number,
             consumption_method, requested_date, recorded_at) values (%s,%s,%s,%s,%s,10,%s,10,'manual','2026-12-01',now())""", (I["comp2"], I["co"], I["doc"], 2, I["i2"], I["WP"]))
        for dk, ck in (("dsl", "comp"), ("dsl2", "comp2")):
            X("""insert into demand_supply_line (id, company_id, item_id, warehouse_id, direction, open_quantity, requested_date, source_kind, production_order_component_id, recorded_at)
                 values (%s,%s,%s,%s,'demand',10,'2026-12-01','production_order_component',%s,now())""", (I[dk], I["co"], I["i2"], I["WP"], I[ck]))
        X("insert into stock_reservation (id, company_id, demand_supply_line_id, item_id, warehouse_id, quantity) values (%s,%s,%s,%s,%s,8)", (I["R1"], I["co"], I["dsl"], I["i2"], I["WP"]))
    check("D02 fixture: a released rework order with an internal operation, a component line, demand lines and a reservation", True)

    def exc(cx, kind, po=None, co="co"):
        cx.execute("""insert into planning_exception (id, company_id, planning_run_id, kind, exception_key, item_id, warehouse_id, production_order_id, recorded_at)
                      values (%s,%s,%s,%s,%s,%s,%s,%s,now())""", (new(), I[co], I["PR"], kind, f"{kind}:{new()}", I["i1"], I["WP"], I[po] if po else None))
    expect("D03 a production_order_start_overdue exception naming its order is accepted", lambda cx: exc(cx, "production_order_start_overdue", "doc"), False)
    expect("D04 a production order exception without production_order_id is refused", lambda cx: exc(cx, "production_order_overdue"), True, "ck_planning_exception_production_order")
    expect("D05 another kind with production_order_id is refused", lambda cx: exc(cx, "below_safety_stock", "doc"), True, "ck_planning_exception_production_order")
    expect("D06 an unknown kind is still refused", lambda cx: exc(cx, "production_order_late", "doc"), True, "ck_planning_exception_kind")

    fk = [d for (d,) in X("""select pg_get_constraintdef(k.oid) from pg_constraint k join pg_class r on r.oid=k.conrelid join pg_class f on f.oid=k.confrelid
                             where r.relname='planning_exception' and f.relname='production_order' and k.contype='f'""").fetchall()]
    check("D07 the exception's order key carries company_id, so it cannot name another company's order", fk == ["FOREIGN KEY (company_id, production_order_id) REFERENCES production_order(company_id, id)"], fk)
    expect("D07b an exception naming an order that does not exist is refused", lambda cx: cx.execute(
        """insert into planning_exception (id, company_id, planning_run_id, kind, exception_key, item_id, warehouse_id, production_order_id, recorded_at)
           values (%s,%s,%s,'production_order_overdue','x',%s,%s,%s,now())""", (new(), I["co"], I["PR"], I["i1"], I["WP"], new())), True, "foreign key")

    def conf(cx, dk, source=None, ref=None):
        document(cx, dk, "operation_confirmation", state="draft")
        cols, vals = "", ""
        args = [I[dk], I["co"], I["doc"], I["OP"]]
        if source:
            cols += ", entry_source"; vals += ",%s"; args.append(source)
        if ref is not None:
            cols += ", external_reference"; vals += ",%s"; args.append(ref)
        cx.execute(f"""insert into operation_confirmation (id, company_id, production_order_id, production_order_operation_id, yield_quantity, scrap_quantity, posting_date{cols}, recorded_at)
                       values (%s,%s,%s,%s,5,0,'2026-12-02'{vals},now())""", args)
    expect("D08 a confirmation without an entry source defaults to person", lambda cx: conf(cx, "c1"), False)
    src = X("select entry_source from operation_confirmation where id=%s", (I["c1"],)).fetchone()
    check("D09 the stored entry source is person", src and src[0] == "person", src)
    expect("D10 a production import row without its external reference is refused", lambda cx: conf(cx, "c2", "production_import"), True, "ck_operation_confirmation_external_reference")
    expect("D11 a capture draft with an external reference is refused", lambda cx: conf(cx, "c2", "capture_agent", "R-1"), True, "ck_operation_confirmation_external_reference")
    expect("D12 an unknown entry source is refused", lambda cx: conf(cx, "c2", "sensor"), True, "ck_operation_confirmation_entry_source")
    expect("D13 a production import row with its reference is accepted", lambda cx: conf(cx, "c2", "production_import", "MES-0001"), False)
    expect("D13b a blank import reference is refused", lambda cx: conf(cx, "c3", "production_import", "  "), True, "ck_operation_confirmation_external_reference")
    expect("D14 the same reference again is refused (duplicate_external_document)", lambda cx: conf(cx, "c3", "production_import", "MES-0001"), True, "ux_operation_confirmation_external_reference")

    def resv(cx, rk, src_k, co="co", dsl="dsl2"):
        cx.execute("insert into stock_reservation (id, company_id, demand_supply_line_id, item_id, warehouse_id, quantity, transferred_from_reservation_id) values (%s,%s,%s,%s,%s,3,%s)",
                   (I[rk], I[co], I[dsl], I["i2"], I["WP"], I[src_k]))
    expect("D15 a transferred reservation names its source", lambda cx: resv(cx, "R2", "R1"), False)
    expect("D16 a reservation is never its own source", lambda cx: resv(cx, "RX", "RX"), True, "ck_stock_reservation_transferred_from")
    expect("D17 the source must be a reservation of the same company (company key)", lambda cx: cx.execute(
        "insert into stock_reservation (id, company_id, demand_supply_line_id, item_id, warehouse_id, quantity, transferred_from_reservation_id) values (%s,%s,%s,%s,%s,1,%s)",
        (new(), I["co"], I["dsl2"], I["i2"], I["WP"], new())), True, "fk_stock_reservation_transferred_from")
    defs = dict(X("""select conname, pg_get_constraintdef(oid) from pg_constraint where conname in
                    ('ck_document_reader_purposes','ck_document_extraction_purpose','ck_extraction_mapping_rule_purpose','ck_mailbox_document_intake_purpose')""").fetchall())
    check("D18 the purpose value shop_floor_report is in the four purpose checks", len(defs) == 4 and all("shop_floor_report" in v for v in defs.values()), sorted(defs))
    idx = X("select indexdef from pg_indexes where schemaname='erpme' and indexname='ux_operation_confirmation_external_reference'").fetchone()
    check("D19 the import reference index is unique per company and partial", idx and "UNIQUE" in idx[0] and "company_id" in idx[0] and "WHERE" in idx[0], idx)
    X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
         item_tax_group_id, tracking) values (%s,%s,'C25B','C25B','stock',%s,%s,%s,%s,%s,%s,'none')""", (I["p3"], I["co"], I["ig"], I["vc"], I["ea"], I["ea"], I["ea"], I["itg"]))
    X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,'C25B')", (I["i3"], I["co"], I["p3"]))

    def resv_item(cx):
        cx.execute("insert into stock_reservation (id, company_id, demand_supply_line_id, item_id, warehouse_id, quantity, transferred_from_reservation_id) values (%s,%s,%s,%s,%s,1,%s)",
                   (new(), I["co"], I["dsl2"], I["i3"], I["WP"], I["R1"]))
    expect("D20 S1: a transferred row with another item than its source is refused by the trigger", resv_item, True, "reservation_transfer_invalid")
    expect("D21 the transfer link never changes after insert, so no cycle can form", lambda cx: cx.execute(
        "update stock_reservation set transferred_from_reservation_id=%s where id=%s", (I["R2"], I["R1"])), True, "reservation_transfer_link_immutable")
    X("insert into lot (id, company_id, item_id, code) values (%s,%s,%s,'L25')", (I["lot"], I["co"], I["i2"]))

    def resv_lot(cx):
        cx.execute("""insert into stock_reservation (id, company_id, demand_supply_line_id, item_id, warehouse_id, lot_id, quantity, transferred_from_reservation_id)
                      values (%s,%s,%s,%s,%s,%s,1,%s)""", (new(), I["co"], I["dsl2"], I["i2"], I["WP"], I["lot"], I["R1"]))
    expect("D22 N2: a transferred row with another lot than its source is refused", resv_lot, True, "reservation_transfer_invalid")
    expect("D23 N1: the item of a transferred row cannot change", lambda cx: cx.execute(
        "update stock_reservation set item_id=%s where id=%s", (I["i3"], I["R2"])), True, "reservation_transfer_invalid")
    expect("D24 N1: the lot of a transfer source cannot change", lambda cx: cx.execute(
        "update stock_reservation set lot_id=%s where id=%s", (I["lot"], I["R1"])), True, "reservation_transfer_invalid")
    expect("D25 the quantity of a linked row may still change (not a transfer field)", lambda cx: cx.execute(
        "update stock_reservation set quantity=2 where id=%s", (I["R2"],)), False)
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
