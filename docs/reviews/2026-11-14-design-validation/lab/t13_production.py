"""Design lab for the holistic production review (ADR-0024 rule 11, ADR-0033 rule 5, ADR-0035 rule 9 notes).

Pure functions in exact rationals, no database:
  E1-E9  units in process of an open order when no manual line qualifies (item P17): first-operation progress under
         operation backflush, zero under receipt backflush or without a routing, never units for an order not started
  D1-D3  disassembly progress by input issued (item P16)
  F1-F7  forecast tiers by history length, and the event index fallback (item F0)
  V1-V5  version selection for backward scheduling: selected on the end date, valid at the resulting start, else the next
         version, else production_version_missing (item P3)
Usage: python3 -I t13_production.py
"""
import sys
from fractions import Fraction as F

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail else ""))


# ---------------------------------------------------------------- units in process (ADR-0035 rule 9 and its notes)
def effective_method(c, has_operations):
    """ADR-0034 rule 2: operation backflush without an operation, or on an order without operations, is receipt backflush."""
    if c["method"] == "backflush_at_operation" and (not has_operations or c.get("operation") is None):
        return "backflush_at_receipt"
    return c["method"]


def units_in_process(o):
    G, Q, received = F(o["G"]), F(o["Q"]), F(o["received"])
    ops = bool(o.get("operations"))
    manual = [c for c in o["components"] if effective_method(c, ops) == "manual" and not c.get("fixed")]
    if manual:
        E = min(F(c["net_issued"]) * G / F(c["required"]) for c in manual)
    elif ops and any(effective_method(c, ops) == "backflush_at_operation" for c in o["components"]):
        E = F(o["first_op_yield_scrap"]) * G / Q
    else:
        E = received
    return max(F(0), E - received)


def old_units_in_process(o):
    """The superseded rule: no qualifying line gives E = G."""
    G, received = F(o["G"]), F(o["received"])
    manual = [c for c in o["components"] if c["method"] == "manual" and not c.get("fixed")]
    E = min(F(c["net_issued"]) * G / F(c["required"]) for c in manual) if manual else G
    return max(F(0), E - received)


def wip_direct_material(pool, R, U):
    """direct_material: WIP = pool x U / (R + U); with no receipt in the period everything stays WIP."""
    if R == 0:
        return pool
    return pool * U / (R + U)


def disassembly_uip(o):
    G = F(o["G"])
    E = F(o["input_issued"])
    D = min(F(x["received"]) * G / F(x["planned"]) for x in o["outputs"])
    return max(F(0), E - D), D


def lab_units():
    op = [10, 20]
    man = {"method": "manual", "required": 200, "net_issued": 120}
    bfo = {"method": "backflush_at_operation", "operation": 10, "required": 50}
    bfr = {"method": "backflush_at_receipt", "required": 30}
    fixed = {"method": "manual", "fixed": True, "required": 5, "net_issued": 5}
    o1 = dict(G=100, Q=100, received=40, operations=op, components=[man, bfo], first_op_yield_scrap=90)
    check("E1 a qualifying manual line decides: E = 120 x 100 / 200 = 60, U = 60 - 40 = 20", units_in_process(o1) == 20,
          units_in_process(o1))
    o2 = dict(G=100, Q=125, received=10, operations=op, components=[bfo, bfr], first_op_yield_scrap=50)
    check("E2 operation backflush only: E = first operation's yield + scrap 50 x G / Q = 40, U = 30",
          units_in_process(o2) == 30, units_in_process(o2))
    o3 = dict(G=100, Q=100, received=10, operations=op, components=[bfr], first_op_yield_scrap=70)
    check("E3 every component backflushed at receipt: U = 0 (old rule: 90)",
          units_in_process(o3) == 0 and old_units_in_process(o3) == 90)
    o4 = dict(G=100, Q=100, received=10, operations=[], components=[bfo], first_op_yield_scrap=0)
    check("E4 no routing: operation backflush counts as receipt backflush, U = 0", units_in_process(o4) == 0)
    o5 = dict(G=100, Q=100, received=0, operations=op, components=[fixed, bfo], first_op_yield_scrap=25)
    check("E5 fixed manual lines never qualify: the first-operation rule applies, U = 25", units_in_process(o5) == 25)
    o6 = dict(G=100, Q=100, received=0, operations=op, components=[], first_op_yield_scrap=0)
    check("E6 no component at all: U = 0", units_in_process(o6) == 0)
    o7 = dict(G=100, Q=100, received=0, operations=op, components=[bfo], first_op_yield_scrap=0)
    check("E7 an order not started has no units in process (old rule: G = 100)",
          units_in_process(o7) == 0 and old_units_in_process(o7) == 100)
    o8 = dict(G=100, Q=100, received=0, operations=op, components=[dict(bfo, operation=None)], first_op_yield_scrap=60)
    check("E8 operation backflush without an operation number counts as receipt backflush, U = 0", units_in_process(o8) == 0)
    # E9: the split that the old rule distorted. Pool 1,000 of material on an order with receipt backflush only.
    pool, R = F(1000), F(10)
    new_w, old_w = wip_direct_material(pool, R, units_in_process(o3)), wip_direct_material(pool, R, old_units_in_process(o3))
    check("E9 direct_material WIP: all cost to the 10 received units under the new rule (old rule kept 900 in WIP)",
          new_w == 0 and old_w == 900, (new_w, old_w))


def lab_disassembly():
    d1 = dict(G=10, input_issued=10, outputs=[dict(planned=20, received=12), dict(planned=10, received=8)])
    u, d = disassembly_uip(d1)
    check("D1 disassembly: D = min(12 x 10 / 20, 8 x 10 / 10) = 6, U = 10 - 6 = 4", (u, d) == (4, 6), (u, d))
    d2 = dict(G=10, input_issued=6, outputs=[dict(planned=20, received=12), dict(planned=10, received=6)])
    check("D2 outputs received for all input issued: U = 0", disassembly_uip(d2)[0] == 0)
    d3 = dict(G=10, input_issued=0, outputs=[dict(planned=20, received=0), dict(planned=10, received=0)])
    check("D3 nothing issued: U = 0", disassembly_uip(d3)[0] == 0)


# ---------------------------------------------------------------- forecast tiers (ADR-0024 rule 11 note)
def forecast(weeks, seasonal=None, event_index=None, next_week=None):
    """weeks: list of (iso_week, quantity, event_code or None), oldest first. Returns (tier, weekly quantity)."""
    plain = [F(q) for _, q, e in weeks if e is None]
    n = len(plain)
    if n == 0:
        return "none", None
    if n < 8:
        return "short_mean", sum(plain) / n
    base = sum(plain[-8:]) / 8
    if n < 52:
        return "unindexed", base
    wk, ev = next_week
    if ev is not None and event_index and ev in event_index:
        return "indexed", base * event_index[ev]
    return "indexed", base * (seasonal.get(wk, F(1)) if seasonal else F(1))


def lab_forecast():
    check("F1 no history: tier none, no forecast", forecast([]) == ("none", None))
    w = [(i, q, None) for i, q in enumerate([4, 0, 8], 1)]
    check("F2 three weeks: their mean, zero weeks counted", forecast(w) == ("short_mean", F(4)))
    w = [(i, 10, None) for i in range(1, 8)] + [(8, 100, "promo")]
    check("F3 seven plain weeks and an event week: n = 7, event weeks left out", forecast(w) == ("short_mean", F(10)))
    w = [(i, i, None) for i in range(1, 21)]
    check("F4 twenty weeks: the last 8 weeks' average, unindexed", forecast(w) == ("unindexed", F(sum(range(13, 21)), 8)))
    w = [(i % 52 + 1, 10, None) for i in range(60)]
    check("F5 sixty weeks: indexed by the seasonal index", forecast(w, {5: F(3, 2)}, {}, (5, None)) == ("indexed", F(15)))
    check("F6 an event with no past occurrence uses the week's seasonal index",
          forecast(w, {5: F(3, 2)}, {"tet": F(2)}, (5, "new_event")) == ("indexed", F(15)))
    check("F7 an event with past occurrences uses its event index",
          forecast(w, {5: F(3, 2)}, {"tet": F(2)}, (5, "tet")) == ("indexed", F(20)))


# ---------------------------------------------------------------- version selection (ADR-0033 rule 5 note)
def valid(v, day, qty):
    return v["active"] and v["start"] <= day <= v["end"] and v["min"] <= qty <= v["max"] and \
        all(r <= day for r in v["revision_starts"])


def select_backward(versions, end_day, qty, lead_days):
    order = sorted(versions, key=lambda v: (v["priority"], v["code"]))
    for v in order:
        if not valid(v, end_day, qty):
            continue
        start = end_day - lead_days(v)
        if valid(v, start, qty):
            return v["code"], start
    return "production_version_missing", None


def lab_versions():
    base = dict(active=True, min=0, max=1000, revision_starts=[0])
    v1 = dict(base, code="V1", priority=1, start=50, end=200)
    v2 = dict(base, code="V2", priority=2, start=0, end=200)
    lt = lambda v: 20
    check("V1 the first version valid at end and start is chosen", select_backward([v1, v2], 100, 10, lt) == ("V1", 80))
    check("V2 V1 starts after the resulting start: the next version V2 is chosen",
          select_backward([v1, v2], 60, 10, lt) == ("V2", 40))
    check("V3 no version valid on both dates: production_version_missing",
          select_backward([v1], 60, 10, lt) == ("production_version_missing", None))
    v3 = dict(base, code="V3", priority=1, start=0, end=200, revision_starts=[45])
    check("V4 a revision released after the resulting start makes the version invalid there",
          select_backward([v3, v2], 60, 10, lt) == ("V2", 40))
    check("V5 selection never depends on input order", select_backward([v2, v1], 60, 10, lt) == select_backward([v1, v2], 60, 10, lt))


def main():
    lab_units()
    lab_disassembly()
    lab_forecast()
    lab_versions()
    fails = RESULTS.count(False)
    print(f"t13 production: {len(RESULTS) - fails}/{len(RESULTS)} PASS")
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
