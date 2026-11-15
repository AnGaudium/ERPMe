"""Scenario: agent-assisted reporting and analysis (ADR-0060), as pure functions and on the DDL drafts.

Run: python t18_analysis.py [--load]
  The pure checks (parts C to G) always run. With --load, ERPME_LAB_DSN must name a throwaway database: load_all.py drops
  and rebuilds schemas erpme and types there and loads every DDL file of design/, this script rebuilds a lab schema
  query with three fact views and their label views, and the database checks (part D) run. Recreate the database before
  each --load: reloading an existing schema can exceed the container's lock limit.
  ERPME_DOCS points at the docs/ tree (default ~/Projects/ERPMe/docs); ERPME_LAB_DIR at lab.py and load_all.py
  (default: this file's directory).

C: the core catalogs analysis-measures.csv and analysis-dimensions.csv: field counts, unique codes, fewer than 40
   measures, selectors naming only core system accounts (the neutral core), ADR-0049's turnover options on journal
   measures (closing entries out of profit and loss, migration entries out of every turnover), field classes on ledger
   cost and margin, facts offering the dimensions a basis or a requirement needs, unique synonyms, derived measures.
V: plan validation (ADR-0060 rule 10): good plans pass, and a bad plan is refused with each of the 14 codes, in order;
   pinned bases, contributions in transaction currency, field classes always, past as-of on a snapshot.
S: the compiler (rule 12): one SELECT over declared query views, bound values only (no plan string in the SQL), an
   is_in_scope filter per fact, subtotals per pinned basis and no grand total, ranked other rows, truncation, per-bucket
   carry-forward for balances, two facts joined on dimension keys, drill-row statements by cell kind.
H, T: hashes with definition hashes (rule 9); relative dates, ISO weeks, months and comparisons (rule 8).
K: exact additive contributions on random data with ties and none members: the reconciliation row is zero (rule 18).
N: the numeral check by word class, fail-closed languages, directions and superlatives against cell facts, the
   co-reference check and rendering (rule 23).
A: the abstention mapping and repair limit, exact-only verified matching, the stated-value check (rules 22, 24).
B, G: the verified badge with open filters and definition hashes, KPI status, caches keyed by company, user and scope,
   and per-view grants (rules 13, 26, 27, 30).
D: with --load, on all DDL: the four tables of DS-33-analysis.sql and their guards; agent runs completing with each
   analysis outcome under ck_agent_run_outcome; then a company with posted sales invoices, a deduction, an expense, cost
   of goods sold, a special-period adjustment, a closing entry and a migration-year entry with their journal lines (the closing case is EC-170); lab
   views journal_line_overview, sales_line_overview and system_account_turnover whose is_in_scope reads a per-view grant
   map; and plans run on them: every cell equals its drill rows by kind (sums, differences, distinct counts,
   contributions, balances); management totals equal ADR-0049's turnover over operational accounts with closing entries
   excluded and the special-period option; per-currency subtotals without a grand total; two facts under two owner
   scopes; a scoped member lookup; a per-bucket closing balance carried forward; truncation; a read-only, single-statement
   compilation; the cost guard over scan nodes.
Not covered: the model, the gateway, the dispatcher, RLS of the views, the production read model, opening_turnover
rows, several assignments per view (one grant per view here).
"""
import csv, hashlib, json, os, random, re, sys, unicodedata
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal as D

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("ERPME_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import RESULTS, conn, expect, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("ERPME_DOCS", "~/Projects/ERPMe/docs"))
CAT = os.path.join(DOCS, "catalogs")


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def read_csv(name):
    with open(os.path.join(CAT, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def split(v, sep=";"):
    return [x for x in (v or "").split(sep) if x]


def jdump(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


# ======================================================================= the catalog
MEAS = {r["code"]: r for r in read_csv("analysis-measures.csv")}
DIMS = {r["code"]: r for r in read_csv("analysis-dimensions.csv")}
SA_PARENT = {r["code"]: r["parent_code"] for r in read_csv("system-accounts.csv")}
with open(os.path.join(CAT, "analysis-measures.csv"), "rb") as f1, open(os.path.join(CAT, "analysis-dimensions.csv"), "rb") as f2:
    CATALOG_HASH = hashlib.sha256(f1.read() + b"\0" + f2.read()).hexdigest()
FACTS = sorted({m["fact"] for m in MEAS.values()})
NOT_OWNER_SCOPED = {"system_account_turnover", "stock_overview", "production_variance_overview"}   # ADR-0060 rule 3
CURRENT_SNAPSHOT = {"open_item_overview", "stock_overview"}
LABEL_VIEWS = {d: f"{d}_dimension" for d, r in DIMS.items() if r["kind"] in ("entity", "catalog")}   # query.<dimension>_dimension
LABELLED = ("partner", "item_group", "system_account")    # the dimensions whose label views the lab builds
DERIVED = {"ratio", "difference"}
PNL_ROOTS = ("income", "expense")


def sa_path(code):
    out = []
    while code:
        out.append(code)
        code = SA_PARENT[code]
    return "/".join(reversed(out))


def dim_facts(d):
    return set(split(DIMS[d]["facts"]))


def dim_fan_out(d):
    return set(split(DIMS[d]["fan_out_facts"]))


def base_measures(code):
    m = MEAS[code]
    if m["aggregation"] in DERIVED:
        return [b for op in split(m["column"]) for b in base_measures(op)]
    return [code]


def selectors(m):
    """'system_account:revenue;closing_entries:exclude' -> [('system_account', ['revenue']), ('closing_entries', ['exclude'])]."""
    return [(s.split(":", 1)[0], s.split(":", 1)[1].split("|")) for s in split(m["selector"])]


VIEW_HASH = {f: sha(f"{f}:lab-view-declaration-1") for f in FACTS}   # the view declaration hashes (columns and SQL, ADR-0050 rule 45)


def subtree(code, parents):
    return sorted(c for c in parents if code in path_of(c, parents).split("/"))


def path_of(code, parents):
    out = []
    while code:
        out.append(code)
        code = parents[code]
    return "/".join(reversed(out))


def definition_hash(code, catalog=None, views=None, accounts=None):
    """Rule 2: the canonical declaration without label texts, its fact's view declaration hash, and its selectors' expansion."""
    cat = catalog or {**{("m", k): v for k, v in MEAS.items()}, **{("d", k): v for k, v in DIMS.items()}}
    views, accounts = views or VIEW_HASH, accounts or SA_PARENT
    key = ("m", code) if ("m", code) in cat else ("d", code)
    row = {k: v for k, v in cat[key].items() if k not in ("meaning", "synonyms", "added_in")}
    reads = {}
    if key[0] == "m":
        reads["view"] = views.get(row["fact"])
        reads["subtrees"] = {v: subtree(v, accounts) for col, vals in selectors(row) if col == "system_account" for v in vals}
    return sha(jdump({"declaration": row, "reads": reads}))


# ======================================================================= plans: canonical form and hashes (rule 9)
PLAN_KEYS = {"plan_version", "measures", "dimensions", "filters", "time", "derived", "contributions", "sort", "limit",
             "with_other_row", "with_total_row"}
DEFAULTS = {"dimensions": [], "filters": [], "time": None, "derived": [], "contributions": None, "sort": [], "limit": None,
            "with_other_row": False, "with_total_row": False}


def canonical(plan):
    p = {k: json.loads(json.dumps(plan.get(k, v))) for k, v in DEFAULTS.items()}
    p["plan_version"] = plan.get("plan_version")
    p["measures"] = sorted(plan.get("measures", []))
    p["filters"] = sorted(({"dimension": f["dimension"], "op": f["op"], "values": sorted(map(str, f["values"]))} for f in p["filters"]),
                          key=lambda f: (f["dimension"], f["op"], f["values"]))
    p["derived"] = sorted(p["derived"], key=lambda d: (d["op"], d["of"]))
    if p["time"] is not None:
        p["time"].setdefault("special_periods", "include")
    return p


def named_objects(plan):
    ms = set(plan.get("measures", [])) | ({plan["contributions"]["measure"]} if plan.get("contributions") else set())
    objs = {b for m in ms if m in MEAS for b in [m] + base_measures(m)}
    ds = {d["dimension"] for d in plan.get("dimensions") or []} | {f["dimension"] for f in plan.get("filters") or []}
    ds |= {plan["time"]["dimension"]} if (plan.get("time") or {}).get("dimension") else set()
    ds |= {plan["contributions"]["dimension"]} if plan.get("contributions") else set()
    return sorted(objs | {d for d in ds if d in DIMS})


def analysis_plan_hash(plan, catalog=None, views=None, accounts=None):
    defs = {o: definition_hash(o, catalog, views, accounts) for o in named_objects(plan)}
    return sha(jdump({"plan": canonical(plan), "definitions": defs}))


def analysis_resolved_hash(plan, ctx):
    p = canonical(plan)
    if p["time"] and p["time"].get("range"):
        r = resolve_plan_time(plan, ctx)
        p["time"] = dict(p["time"], range={"from": r[0][0], "to": r[0][1]}, compare=({"from": r[1][0], "to": r[1][1]} if r[1] else None))
    return sha(jdump(p) + CATALOG_HASH)


# ======================================================================= time (rule 8)
def month_end(d):
    return date(d.year + d.month // 12, d.month % 12 + 1, 1) - timedelta(days=1)


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, month_end(date(y, m, 1)).day))


def fiscal_year_start(bd, fy_month):
    return date(bd.year if bd.month >= fy_month else bd.year - 1, fy_month, 1)


RELATIVE = {"today", "yesterday", "this_week", "last_week", "month_to_date", "this_month", "last_month", "this_calendar_quarter",
            "last_calendar_quarter", "this_calendar_year", "last_calendar_year", "this_fiscal_quarter", "last_fiscal_quarter",
            "fiscal_year_to_date", "this_fiscal_year", "last_fiscal_year", "last_n_days", "last_n_weeks", "last_n_months"}


NAMED = ("month", "calendar_quarter", "calendar_year", "fiscal_quarter", "fiscal_year")


def resolve_named(rng, fy_month):
    """Rule 8: named periods, resolved by code."""
    if "month" in rng:
        y, m = re.fullmatch(r"(\d{4})-(\d{2})", str(rng["month"])).groups()
        s = date(int(y), int(m), 1)
        return (s, month_end(s))
    if "calendar_quarter" in rng:
        y, qn = re.fullmatch(r"(\d{4})-Q([1-4])", str(rng["calendar_quarter"])).groups()
        s = date(int(y), 3 * (int(qn) - 1) + 1, 1)
        return (s, month_end(add_months(s, 2)))
    if "calendar_year" in rng:
        y = int(rng["calendar_year"])
        return (date(y, 1, 1), date(y, 12, 31))
    if "fiscal_year" in rng:
        s = date(int(rng["fiscal_year"]), fy_month, 1)
        return (s, month_end(add_months(s, 11)))
    y, qn = re.fullmatch(r"(\d{4})-Q([1-4])", str(rng["fiscal_quarter"])).groups()
    s = add_months(date(int(y), fy_month, 1), 3 * (int(qn) - 1))
    return (s, month_end(add_months(s, 2)))


def resolve_range(rng, bd, fy_month):
    if "from" in rng:
        return (date.fromisoformat(str(rng["from"])), date.fromisoformat(str(rng["to"])))
    if any(k in rng for k in NAMED):
        try:
            return resolve_named(rng, fy_month)
        except (AttributeError, ValueError) as e:
            raise ValueError("named period") from e
    rel = rng["relative"]
    if rel not in RELATIVE:
        raise ValueError(rel)
    m0 = bd.replace(day=1)
    w0 = bd - timedelta(days=bd.weekday())                       # ISO week: Monday
    if rel == "today":
        return (bd, bd)
    if rel == "yesterday":
        return (bd - timedelta(days=1),) * 2
    if rel == "this_week":
        return (w0, w0 + timedelta(days=6))
    if rel == "last_week":
        return (w0 - timedelta(days=7), w0 - timedelta(days=1))
    if rel == "month_to_date":
        return (m0, bd)
    if rel == "this_month":
        return (m0, month_end(m0))
    if rel == "last_month":
        s = add_months(m0, -1)
        return (s, month_end(s))
    if rel in ("this_calendar_quarter", "last_calendar_quarter"):
        s = date(bd.year, 3 * ((bd.month - 1) // 3) + 1, 1)
        if rel == "last_calendar_quarter":
            s = add_months(s, -3)
        return (s, month_end(add_months(s, 2)))
    if rel == "this_calendar_year":
        return (date(bd.year, 1, 1), date(bd.year, 12, 31))
    if rel == "last_calendar_year":
        return (date(bd.year - 1, 1, 1), date(bd.year - 1, 12, 31))
    if rel in ("last_n_days", "last_n_weeks", "last_n_months"):
        n = int(rng["n"])
        if n < 1:
            raise ValueError("n")
        if rel == "last_n_days":
            return (bd - timedelta(days=n - 1), bd)
        if rel == "last_n_weeks":
            return (w0 - timedelta(days=7 * n), w0 - timedelta(days=1))
        return (add_months(m0, -n), m0 - timedelta(days=1))
    fy = fiscal_year_start(bd, fy_month)
    if rel in ("this_fiscal_quarter", "last_fiscal_quarter"):
        k = ((bd.year - fy.year) * 12 + bd.month - fy.month) // 3
        s = add_months(fy, 3 * k - (3 if rel == "last_fiscal_quarter" else 0))
        return (s, month_end(add_months(s, 2)))
    if rel == "fiscal_year_to_date":
        return (fy, bd)
    if rel == "this_fiscal_year":
        return (fy, month_end(add_months(fy, 11)))
    s = add_months(fy, -12)                                      # last_fiscal_year
    return (s, month_end(add_months(s, 11)))


def shift_year(d, n):
    if d.month == 2 and d.day == 29:
        d = d.replace(day=28)
    return d.replace(year=d.year + n)


def compare_range(r, cmp, bd, fy_month):
    if cmp is None:
        return None
    if "from" in cmp or any(k in cmp for k in NAMED):
        return resolve_range(cmp, bd, fy_month)
    a, b = r
    if cmp["relative"] == "same_period_last_year":
        return (shift_year(a, -1), shift_year(b, -1))
    if cmp["relative"] == "previous_month_same_days":           # day for day, clamped to the month's end
        return (add_months(a, -1), add_months(b, -1))
    if cmp["relative"] != "previous_period":
        return resolve_range(cmp, bd, fy_month)
    if a.day == 1 and b == month_end(b):                          # whole months: the previous block of months
        k = (b.year - a.year) * 12 + b.month - a.month + 1
        s = add_months(a, -k)
        return (s, month_end(add_months(s, k - 1)))
    n = (b - a).days + 1
    return (a - timedelta(days=n), a - timedelta(days=1))


def resolve_plan_time(plan, ctx):
    t = plan.get("time") or {}
    if not t.get("range"):
        return (None, None)
    r = resolve_range(t["range"], ctx["business_date"], ctx["fy_month"])
    return (r, compare_range(r, t.get("compare"), ctx["business_date"], ctx["fy_month"]))


def months_spanned(a, b):
    return (b.year - a.year) * 12 + b.month - a.month + 1


# ======================================================================= validation (rule 10)
ORDER = ["analysis_plan_invalid", "unknown_measure", "unknown_dimension", "analysis_not_permitted", "dimension_not_shared",
         "fan_out_refused", "currency_mixed", "unit_mixed", "dimension_required", "measure_not_additive", "time_range_invalid",
         "filter_value_unknown", "analysis_too_broad", "analysis_data_not_ready"]
SETTINGS = {"analysis_max_cells": 5000, "analysis_agent_max_cells": 500, "analysis_max_range_months": 60,
            "analysis_max_estimated_rows": 5_000_000}
OPS = {"eq", "in", "not_in", "in_subtree"}
PIN = {"transaction_currency": ("currency",), "inventory_unit": ("item", "product")}


def pinned_by_group(plan):
    """The grouped dimensions that pin a measure's basis (rule 10): totals stay within their members."""
    group = [d.get("dimension") for d in plan.get("dimensions") or []]
    out = []
    for m in plan.get("measures") or []:
        for b in base_measures(m) if m in MEAS else []:
            out += [d for d in PIN.get(MEAS[b]["basis"], ()) if d in group and d not in out]
    return out


def validate(plan, actor, ctx):
    v = []
    add = lambda code, path, msg="": v.append((code, path, msg))
    # V1 the model
    if set(plan) - PLAN_KEYS:
        add("analysis_plan_invalid", sorted(set(plan) - PLAN_KEYS)[0], "unknown field")
    if plan.get("plan_version") != 1:
        add("analysis_plan_invalid", "plan_version")
    ms = plan.get("measures") or []
    if not 1 <= len(ms) <= 5:
        add("analysis_plan_invalid", "measures")
    dims = plan.get("dimensions") or []
    if len(dims) > 3:
        add("analysis_plan_invalid", "dimensions")
    for i, f in enumerate(plan.get("filters") or []):
        vals = f.get("values") or []
        if f.get("op") not in OPS or not 1 <= len(vals) <= 100 or (f.get("op") == "eq" and len(vals) != 1):
            add("analysis_plan_invalid", f"filters[{i}]")
        elif f["op"] == "in_subtree" and f.get("dimension") in DIMS and DIMS[f["dimension"]]["is_tree"] != "true":
            add("analysis_plan_invalid", f"filters[{i}].op", "in_subtree needs a tree dimension")
    lim = plan.get("limit")
    if lim is not None and (not isinstance(lim, int) or not 1 <= lim <= (50 if actor["agent"] else 1000)):
        add("analysis_plan_invalid", "limit")
    names = set(ms) | {d.get("dimension") for d in dims}
    for i, s in enumerate(plan.get("sort") or []):
        if s.get("by") not in names or s.get("dir") not in ("asc", "desc"):
            add("analysis_plan_invalid", f"sort[{i}]")
    for i, d in enumerate(plan.get("derived") or []):
        if d.get("op") not in ("difference", "growth", "share_of_total") or d.get("of") not in ms:
            add("analysis_plan_invalid", f"derived[{i}]")
    c = plan.get("contributions")
    if c is not None and (set(c) != {"measure", "dimension", "top"} or not isinstance(c["top"], int) or not 1 <= c["top"] <= 25):
        add("analysis_plan_invalid", "contributions")
    t = plan.get("time") or {}
    if t.get("special_periods", "include") not in ("include", "exclude"):
        add("analysis_plan_invalid", "time.special_periods")
    # V2 measures
    named_m = list(ms) + ([c["measure"]] if c and "measure" in c else [])
    for i, m in enumerate(named_m):
        if m not in MEAS:
            add("unknown_measure", f"measures[{i}]", m)
    known_m = [m for m in named_m if m in MEAS]
    # V3 dimensions and grains
    group = [d.get("dimension") for d in dims]
    filt = [f.get("dimension") for f in plan.get("filters") or []]
    contrib_dim = [c["dimension"]] if c and "dimension" in c else []
    for path, d in [(f"dimensions[{i}]", x) for i, x in enumerate(group)] + [(f"filters[{i}]", x) for i, x in enumerate(filt)] \
            + ([("time.dimension", t["dimension"])] if t.get("dimension") else []) + [("contributions.dimension", x) for x in contrib_dim]:
        if d not in DIMS:
            add("unknown_dimension", path, d)
    for i, d in enumerate(dims):
        if d.get("dimension") in DIMS:
            r = DIMS[d["dimension"]]
            if (r["kind"] == "time") != ("grain" in d) or ("grain" in d and d["grain"] not in split(r["grains"], "|")):
                add("unknown_dimension", f"dimensions[{i}].grain", d.get("grain"))
    if t.get("dimension") in DIMS and DIMS[t["dimension"]]["kind"] != "time":
        add("unknown_dimension", "time.dimension", "not a time dimension")
    bases = sorted({b for m in known_m for b in base_measures(m)})
    facts = sorted({MEAS[b]["fact"] for b in bases})
    # V4 rights: facts, owner scope, the field class of every measure named or computed from
    for f in facts:
        if f not in actor["facts"]:
            add("analysis_not_permitted", "measures", f"fact {f}")
        if f in NOT_OWNER_SCOPED and not actor["wide"]:
            add("analysis_not_permitted", "measures", f"owner scope branch or company for {f}")
    for m in sorted(set(known_m) | set(bases)):
        if MEAS[m]["field_class"] and MEAS[m]["field_class"] not in actor["classes"]:
            add("analysis_not_permitted", "measures", f"field class {MEAS[m]['field_class']} for {m}")
    # V5 common dimensions, V6 fan-out
    kd = lambda xs: [x for x in xs if x in DIMS]
    for f in facts:
        for d in kd(group + contrib_dim + filt):
            if f not in dim_facts(d) | dim_fan_out(d):
                add("dimension_not_shared", d, f)
        if t.get("dimension") in DIMS and f not in dim_facts(t["dimension"]):
            add("dimension_not_shared", "time.dimension", f)
        for d in kd(group + contrib_dim):
            if f in dim_fan_out(d):
                add("fan_out_refused", d, f)
    # V7 currency, V8 unit, V9 required
    def pinned(dset, single, by_group=True):
        if by_group and any(d in group for d in dset):
            return True
        if not single:                                            # a required dimension: any filter on it
            return any(f.get("dimension") in dset for f in plan.get("filters") or [])
        return any(f.get("dimension") in dset and f.get("op") in ("eq", "in") and len(f.get("values") or []) == 1
                   for f in plan.get("filters") or [])
    for b in bases:
        by_group = not (c and c.get("measure") in MEAS and b in base_measures(c["measure"]))   # contributions need a filter
        if MEAS[b]["basis"] == "transaction_currency" and not pinned({"currency"}, True, by_group):
            add("currency_mixed", b)
        if MEAS[b]["basis"] == "inventory_unit" and not pinned({"item", "product"}, True, by_group):
            add("unit_mixed", b)
        for r in split(MEAS[b]["requires"]):
            if not pinned({r}, False):
                add("dimension_required", b, r)
    for m in known_m:
        if MEAS[m]["aggregation"] == "difference" and len({MEAS[o]["basis"] for o in split(MEAS[m]["column"])}) > 1:
            add("currency_mixed", m, "operands of different bases")
    # V10 additivity
    if c and c.get("measure") in MEAS and MEAS[c["measure"]]["additivity"] != "additive":
        add("measure_not_additive", "contributions.measure")
    for i, d in enumerate(plan.get("derived") or []):
        if d.get("op") == "share_of_total" and d.get("of") in MEAS and MEAS[d["of"]]["additivity"] == "non_additive":
            add("measure_not_additive", f"derived[{i}]")
    # V11 time
    timed = [f for f in facts if f not in CURRENT_SNAPSHOT]
    rng = None
    try:
        rng, _ = resolve_plan_time(plan, ctx)
    except (ValueError, KeyError, TypeError):
        add("time_range_invalid", "time.range")
    if timed and not t.get("range"):
        add("time_range_invalid", "time.range", "a range is needed")
    if rng and rng[0] > rng[1]:
        add("time_range_invalid", "time.range", "unordered")
    if t.get("compare") and not t.get("range"):
        add("time_range_invalid", "time.compare")
    if c and not t.get("compare"):
        add("time_range_invalid", "contributions", "a comparison is needed")
    # V12 members
    for i, f in enumerate(plan.get("filters") or []):
        d = f.get("dimension")
        if d not in DIMS:
            continue
        r = DIMS[d]
        for val in f.get("values") or []:
            if d == "system_account":
                ok = val in SA_PARENT
            elif r["kind"] == "enum":
                ok = val in split(r["values"], "|")
            else:
                ok = val in ctx["members"].get(d, set())
            if not ok:
                add("filter_value_unknown", f"filters[{i}]", val)
    # V13 span, cardinality and cost
    if rng and rng[0] <= rng[1] and months_spanned(*rng) > SETTINGS["analysis_max_range_months"]:
        add("analysis_too_broad", "time.range", "analysis_max_range_months")
    high = [d for d in kd(group) if DIMS[d]["cardinality"] in ("high", "identifier")]
    if len(high) > 1:
        add("analysis_too_broad", "dimensions", "two high-cardinality dimensions")
    elif high and plan.get("limit") is None:
        add("analysis_too_broad", "limit", "a limit is needed")
    cells = max(1, len(ms) + len(plan.get("derived") or []))
    for d in dims:
        x = d.get("dimension")
        if x in DIMS and DIMS[x]["kind"] == "time" and rng and rng[0] <= rng[1]:
            cells *= {"day": (rng[1] - rng[0]).days + 1, "week": (rng[1] - rng[0]).days // 7 + 1, "month": months_spanned(*rng),
                      "quarter": months_spanned(*rng) // 3 + 1, "year": rng[1].year - rng[0].year + 1}.get(d.get("grain"), months_spanned(*rng))
        elif x in high:
            cells *= (plan.get("limit") or 1) + 1
        elif x in DIMS:
            cells *= ctx["member_count"].get(x, 10)
    if cells > SETTINGS["analysis_agent_max_cells" if actor["agent"] else "analysis_max_cells"]:
        add("analysis_too_broad", "plan", "analysis_max_cells")
    if ctx.get("estimated_rows", 0) > SETTINGS["analysis_max_estimated_rows"]:
        add("analysis_too_broad", "plan", "analysis_max_estimated_rows")
    # V14 readiness
    opening_ok = rng and all(MEAS[b]["fact"] == "journal_line_overview" and "closing_entries:exclude" in MEAS[b]["selector"] for b in bases) \
        and any(s_ == rng[0] and e_ == ctx["cutover"] - timedelta(days=1) for s_, e_ in ctx.get("opening_turnover", []))
    if (rng and rng[0] < ctx["cutover"] and not opening_ok) or ctx.get("migration_loading"):
        add("analysis_data_not_ready", "time.range")
    if t.get("as_of") and any(f in CURRENT_SNAPSHOT for f in facts) and date.fromisoformat(t["as_of"]) < ctx["business_date"]:
        add("analysis_data_not_ready", "time.as_of", "current snapshot only")
    v.sort(key=lambda x: ORDER.index(x[0]))
    return v


# ======================================================================= the compiler (rule 12)
TIME_GRAINS = {"day": "day", "week": "week", "month": "month", "quarter": "quarter", "year": "year"}   # whitelist
BAL_KEYS = "f.system_account_code, f.branch_id, f.cost_center_id, f.project_id, f.transaction_currency"


class Sql:
    """Collects bound parameters; values never enter the text. Parameters are added in text order."""
    def __init__(self):
        self.params = []

    def p(self, value):
        self.params.append(value)
        return "%s"


def selector_sql(q, m, alias="f"):
    parts, closing_excluded = [], False
    for col, vals in selectors(m):
        if col == "system_account":
            parts.append("(" + " OR ".join(f"('/' || {alias}.system_account_path || '/') LIKE {q.p('%/' + v + '/%')}" for v in vals) + ")")
        elif col == "closing_entries":
            parts.append(f"NOT {alias}.is_closing_entry")
            closing_excluded = True
        elif col == "migration_entries":
            parts.append(f"NOT {alias}.is_migration_entry")
        elif vals in (["true"], ["false"]):
            parts.append(f"{alias}.{col} = {q.p(vals == ['true'])}")
        else:
            parts.append(f"{alias}.{col} = ANY({q.p(vals)})")
    if m["fact"] == "journal_line_overview" and not closing_excluded:
        parts.append(f"{alias}.row_source = 'journal_line'")      # opening_turnover rows count only where closing entries are excluded (rule 3)
    return " AND ".join(parts)


def filter_sql(q, fact, f, alias="f"):
    d = DIMS[f["dimension"]]
    col = d["column"]
    if fact in dim_fan_out(f["dimension"]):                      # one-to-many: filter only, as EXISTS (rule 5)
        stem = fact.replace("_overview", "")
        return (f"EXISTS (SELECT 1 FROM query.{stem}_line_dimension x WHERE x.{stem}_id = {alias}.id"
                f" AND x.{col}::text = ANY({q.p([str(x) for x in f['values']])}))")
    if f["op"] == "in_subtree":
        return "(" + " OR ".join(f"('/' || {alias}.system_account_path || '/') LIKE {q.p('%/' + v + '/%')}" for v in f["values"]) + ")"
    neg = "NOT " if f["op"] == "not_in" else ""
    return f"{neg}({alias}.{col}::text = ANY({q.p([str(x) for x in f['values']])}))"


FY_OF = "(SELECT p.fiscal_year_id FROM query.posting_period_dimension p WHERE {to} BETWEEN p.start_date AND p.end_date AND p.kind = 'regular')"


def row_filters(q, plan, fact, rng, cmp_, alias="f", with_time=True, to=None):
    w = [f"{alias}.is_in_scope"]
    for f in plan.get("filters") or []:
        w.append(filter_sql(q, fact, f, alias))
    t = plan.get("time") or {}
    if t.get("special_periods") == "exclude" and fact == "journal_line_overview":
        w.append(f"NOT {alias}.is_special_period")
    to = to or (rng[1] if rng else None)
    if t.get("special_periods") == "exclude" and fact == "system_account_turnover" and to:
        # rule 12: only the special periods of the fiscal year that ends on `to`
        w.append(f"NOT ({alias}.is_special_period AND {alias}.fiscal_year_id = {FY_OF.format(to=q.p(to))})")
    if with_time and rng and fact not in CURRENT_SNAPSHOT and t.get("dimension"):
        col = DIMS[t["dimension"]]["column"]
        if fact == "system_account_turnover":
            w.append(f"{alias}.period_end <= {q.p(rng[1])}")
        elif col == "posting_period_id":
            w.append(f"{alias}.posting_date BETWEEN {q.p(rng[0])} AND {q.p(rng[1])}")
        elif cmp_:
            w.append(f"(({alias}.{col} BETWEEN {q.p(rng[0])} AND {q.p(rng[1])}) OR ({alias}.{col} BETWEEN {q.p(cmp_[0])} AND {q.p(cmp_[1])}))")
        else:
            w.append(f"{alias}.{col} BETWEEN {q.p(rng[0])} AND {q.p(rng[1])}")
    return w


def dim_expr(d, grain=None, alias="f", fact=None):
    col = DIMS[d]["column"]
    if DIMS[d]["kind"] == "time" and col != "posting_period_id":
        e = f"date_trunc('{TIME_GRAINS[grain]}', {alias}.{col})::date::text"
        if fact == "journal_line_overview":                     # opening turnover rows: their own bucket (rule 3)
            e = f"CASE WHEN {alias}.row_source = 'opening_turnover' THEN '~opening' ELSE {e} END"
        return e
    return f"coalesce({alias}.{col}::text, '~none')"


def measure_row_expr(q, b, alias="f"):
    m = MEAS[b]
    sel = selector_sql(q, m, alias)
    col = f"{alias}.{m['column']}"
    if m["aggregation"] == "count":
        return (f"CASE WHEN {sel} THEN 1 ELSE 0 END" if sel else "1"), "sum"
    if m["aggregation"] == "count_distinct":
        return (f"CASE WHEN {sel} THEN {col} END" if sel else col), "count_distinct"
    signed = col if m["sign"] == "1" else f"(-{col})"
    return (f"CASE WHEN {sel} THEN {signed} END" if sel else signed), "sum"


def restriction(q, bases):
    """Rows that no measure of the fact selects are left out, so they form no empty member."""
    sels = [selector_sql(q, MEAS[b]) for b in bases]
    return ["(" + " OR ".join(sels) + ")"] if all(sels) else []


def agg(kind, expr):
    return f"count(DISTINCT {expr})" if kind == "count_distinct" else f"coalesce(sum({expr}), 0)"


def derived_expr(code, cols):
    m = MEAS[code]
    if m["aggregation"] == "difference":
        a, b = split(m["column"])
        return f"({derived_expr(a, cols)} - {derived_expr(b, cols)})"
    if m["aggregation"] == "ratio":
        a, b = split(m["column"])
        return f"round(100 * ({derived_expr(a, cols)})::numeric / nullif({derived_expr(b, cols)}, 0), 2)"
    return cols[code]


def compile_plan(plan, ctx):
    """One SELECT for a validated plan. Returns (sql, params, meta)."""
    q = Sql()
    rng, cmp_ = resolve_plan_time(plan, ctx)
    if plan.get("contributions"):
        return compile_contributions(plan, q, rng, cmp_)
    dims = plan.get("dimensions") or []
    ms = list(plan["measures"])
    facts = sorted({MEAS[b]["fact"] for m in ms for b in base_measures(m)})
    if facts == ["system_account_turnover"] and "posting_period" in [d["dimension"] for d in dims]:
        return compile_balance_buckets(plan, q, rng)
    gnames = [f"g{i + 1}" for i in range(len(dims))]
    pins = [gnames[i] for i, d in enumerate(dims) if d["dimension"] in pinned_by_group(plan)]
    lim = plan.get("limit")
    high = next((i for i, d in enumerate(dims) if DIMS[d["dimension"]]["cardinality"] in ("high", "identifier")), None)
    ranked = high if high is not None else (next((i for i, d in enumerate(dims) if DIMS[d["dimension"]]["kind"] != "time"), None) if lim else None)
    ctes, per_fact, trunc = [], {}, []
    for k, fact in enumerate(facts):
        bases = sorted({b for m in ms for b in base_measures(m) if MEAS[b]["fact"] == fact})
        sel = [f"{dim_expr(d['dimension'], d.get('grain'), fact=fact)} AS {g}" for d, g in zip(dims, gnames)]
        kinds = {}
        for j, b in enumerate(bases):
            e, kinds[b] = measure_row_expr(q, b)
            sel.append(f"{e} AS v{j}")
        if fact == "system_account_turnover" and MEAS[bases[0]]["additivity"] == "semi_additive" and "posting_period" in [d["dimension"] for d in dims]:
            # rule 12: the per-bucket carry-forward runs inside this fact's own aggregation; the facts join on the bucket keys
            ti = [d["dimension"] for d in dims].index("posting_period")
            excl = (plan.get("time") or {}).get("special_periods") == "exclude"
            bf, bt = q.p(rng[0]), q.p(rng[1])
            skip = f" AND NOT (p.kind = 'special' AND p.fiscal_year_id = {FY_OF.format(to=q.p(rng[1]))})" if excl else ""
            ctes.append(f"b{k} AS (SELECT p.key AS bkey, p.seq AS bseq FROM query.posting_period_dimension p WHERE p.end_date BETWEEN {bf} AND {bt}{skip})")
            wb = row_filters(q, plan, fact, None, None, to=rng[1])
            selb = [(f"b{k}.bkey AS {g}" if i == ti else f"{dim_expr(d['dimension'], alias='x')} AS {g}") for i, (d, g) in enumerate(zip(dims, gnames))]
            ctes.append(f"r{k} AS (SELECT {', '.join(selb)}, b{k}.bseq, x.{MEAS[bases[0]]['column']} AS v0 FROM b{k} CROSS JOIN LATERAL"
                        f" (SELECT DISTINCT ON ({BAL_KEYS}) f.* FROM query.{fact} f WHERE {' AND '.join(wb)} AND f.period_seq <= b{k}.bseq"
                        f" ORDER BY {BAL_KEYS}, f.period_seq DESC) x)")
            agg_b = f"SELECT {', '.join(gnames)}, 0 AS gr, coalesce(sum(v0), 0) AS a_{bases[0]} FROM r{k} GROUP BY {', '.join(gnames)}"
            if plan.get("with_total_row"):
                agg_b += (f" UNION ALL SELECT {', '.join('NULL' for _ in gnames)}, {(1 << len(gnames)) - 1}, coalesce(sum(v0), 0) FROM r{k}"
                          f" WHERE bseq = (SELECT max(bseq) FROM b{k})")
            ctes.append(f"a{k} AS ({agg_b})")
            per_fact[fact] = (k, bases)
            continue
        w = row_filters(q, plan, fact, rng, cmp_) + restriction(q, bases)
        src = f"query.{fact} f"
        if MEAS[bases[0]]["additivity"] == "semi_additive" and fact == "system_account_turnover":
            src = f"(SELECT DISTINCT ON ({BAL_KEYS}) f.* FROM query.{fact} f WHERE {' AND '.join(w)} ORDER BY {BAL_KEYS}, f.period_seq DESC) f"
            w = ["true"]
        ctes.append(f"r{k} AS (SELECT {', '.join(sel)} FROM {src} WHERE {' AND '.join(w)})")
        rows = f"r{k}"
        if ranked is not None and lim:
            g = gnames[ranked]
            others = [x for x in gnames if x != g]               # rank within the other grouped members (one currency, one month)
            part = f"PARTITION BY {', '.join(others)} " if others else ""
            first = bases.index(base_measures(ms[0])[0]) if base_measures(ms[0])[0] in bases else 0
            tail = "~other" if plan.get("with_other_row") else "~cut"
            ctes.append(f"k{k} AS (SELECT {', '.join(others + [g])}, row_number() OVER ({part}ORDER BY {agg(kinds[bases[first]], f'v{first}')} DESC, {g}) AS rn"
                        f" FROM r{k} GROUP BY {', '.join(others + [g])})")
            ctes.append(f"t{k} AS (SELECT CASE WHEN k{k}.rn <= {q.p(lim)} THEN r{k}.{g} ELSE '{tail}' END AS {g}"
                        + "".join(f", r{k}.{x}" for x in others)
                        + f", {', '.join(f'r{k}.v{j}' for j in range(len(bases)))} FROM r{k} JOIN k{k} USING ({', '.join(others + [g])}))")
            rows = f"t{k}"
            if tail == "~cut":
                trunc.append(k)
        sets = [f"({', '.join(gnames)})"] if gnames else []
        if plan.get("with_total_row") and gnames and set(pins) != set(gnames):
            sets.append(f"({', '.join(pins)})" if pins else "()")   # a pinned basis: subtotals per member, no grand total; none if it is all
        gs = f"GROUPING SETS ({', '.join(sets)})" if gnames else ""
        grp = list(gnames) + [f"grouping({', '.join(gnames)}) AS gr" if gnames else "0 AS gr"]
        aggs = [f"{agg(kinds[b], f'v{j}')} AS a_{b}" for j, b in enumerate(bases)]
        ctes.append(f"a{k} AS (SELECT {', '.join(grp + aggs)} FROM {rows}" + (f" GROUP BY {gs}" if gs else "") + ")")
        per_fact[fact] = (k, bases)
    first = per_fact[facts[0]][0]
    frm = f"a{first}"
    for fact in facts[1:]:
        k = per_fact[fact][0]
        on = " AND ".join([f"a{first}.{g} IS NOT DISTINCT FROM a{k}.{g}" for g in gnames] + [f"a{first}.gr = a{k}.gr"])
        frm += f" FULL JOIN a{k} ON {on}"
    akeys = {b: f"a{per_fact[MEAS[b]['fact']][0]}.a_{b}" for f_ in facts for b in per_fact[f_][1]}
    cols = {b: f"coalesce({akeys[b]}, 0)" for b in akeys}
    gcol = lambda g: f"coalesce({', '.join(f'a{per_fact[f][0]}.{g}' for f in facts)})"
    gr = f"coalesce({', '.join(f'a{per_fact[f][0]}.gr' for f in facts)})"
    out = [f"{gcol(g)} AS {g}" for g in gnames]
    sub_mask = sum(1 << (len(gnames) - 1 - i) for i, g in enumerate(gnames) if g not in pins) if pins else None
    kind = f"CASE WHEN {gr} = 0 THEN 'member'" + (f" WHEN {gr} = {sub_mask} THEN 'subtotal'" if pins else "") + " ELSE 'total' END"
    out.insert(0, f"{kind} AS row_kind")
    for i, m in enumerate(ms):
        out.append(f"{derived_expr(m, cols)} AS m{i + 1}")
    for i, d in enumerate(dims):
        if d["dimension"] in LABELLED:
            out.append(f"(SELECT l.label FROM query.{LABEL_VIEWS[d['dimension']]} l WHERE l.key = {gcol(f'g{i + 1}')}) AS l{i + 1}")
    flag = " OR ".join(f"EXISTS (SELECT 1 FROM query.{fact} f WHERE "
                       f"{' AND '.join(['NOT f.is_in_scope'] + row_filters(q, plan, fact, rng, cmp_)[1:] + restriction(q, per_fact[fact][1]))})" for fact in facts)
    out.append(f"({flag}) AS is_scope_filtered")
    out.append("(" + (" OR ".join(f"EXISTS (SELECT 1 FROM k{k} WHERE rn > {q.p(lim)})" for k in trunc) if trunc else "false") + ") AS is_truncated")
    where = (" WHERE " + " AND ".join(f"{gcol(g)} IS DISTINCT FROM '~cut'" for g in gnames)) if trunc else ""
    order = ", ".join([gr] + gnames)
    sql = "WITH " + ",\n".join(ctes) + f"\nSELECT {', '.join(out)} FROM {frm}{where} ORDER BY {order}"
    return sql, q.params, {"dims": [d["dimension"] for d in dims], "measures": ms, "facts": facts, "pins": pins}


def compile_balance_buckets(plan, q, rng):
    """Rule 12: a semi-additive balance per bucket (posting period, or fiscal year ending after its special periods), carried
    forward per key; other grouped dimensions are part of the key; the total is the last bucket's value."""
    m = plan["measures"][0]
    fact = MEAS[m]["fact"]
    col = MEAS[m]["column"]
    dims = plan["dimensions"]
    tdim = next(d for d in dims if d["dimension"] == "posting_period")
    others = [d for d in dims if d["dimension"] != "posting_period"]
    excl = (plan.get("time") or {}).get("special_periods") == "exclude"
    b_from, b_to = q.p(rng[0]), q.p(rng[1])
    skip = f" AND NOT (p.kind = 'special' AND p.fiscal_year_id = {FY_OF.format(to=q.p(rng[1]))})" if excl else ""
    if tdim.get("grain") == "fiscal_year":
        b = (f"b AS (SELECT p.fiscal_year_id::text AS bkey, max(p.seq) AS bseq FROM query.posting_period_dimension p"
             f" WHERE p.fiscal_year_id IN (SELECT fiscal_year_id FROM query.posting_period_dimension WHERE end_date BETWEEN {b_from} AND {b_to}){skip}"
             " GROUP BY p.fiscal_year_id)")
    else:
        b = f"b AS (SELECT p.key AS bkey, p.seq AS bseq FROM query.posting_period_dimension p WHERE p.end_date BETWEEN {b_from} AND {b_to}{skip})"
    w = row_filters(q, plan, fact, None, None, to=rng[1])
    oth = [f"{dim_expr(d['dimension'], alias='x')} AS o{i}" for i, d in enumerate(others)]
    sel_out, grp = [], ["bkey", "bseq"] + [f"o{i}" for i in range(len(others))]
    oi = 0
    for d in dims:
        if d is tdim:
            sel_out.append("bkey")
        else:
            sel_out.append(f"o{oi}")
            oi += 1
    sql = (f"WITH {b},\n"
           f"r AS (SELECT b.bkey, b.bseq{''.join(', ' + o for o in oth)}, x.{col} AS v FROM b CROSS JOIN LATERAL (SELECT DISTINCT ON ({BAL_KEYS}) f.* FROM query.{fact} f"
           f" WHERE {' AND '.join(w)} AND f.period_seq <= b.bseq ORDER BY {BAL_KEYS}, f.period_seq DESC) x)\n"
           f"SELECT 'member' AS row_kind, {', '.join(sel_out)}, coalesce(sum(v), 0) AS m1, bseq FROM r GROUP BY {', '.join(grp)}\n"
           + (f"UNION ALL SELECT 'total', {', '.join('NULL' for _ in dims)}, coalesce(sum(v), 0), NULL FROM r WHERE bseq = (SELECT max(bseq) FROM b)\n"
              if plan.get("with_total_row") else "")
           + f"ORDER BY {len(dims) + 3} NULLS LAST, 1, 2" + (", 3" if others else ""))
    return sql, q.params, {"balance_buckets": True, "fact": fact}


def compile_contributions(plan, q, rng, cmp_):
    c = plan["contributions"]
    fact = MEAS[c["measure"]]["fact"]
    col = DIMS[plan["time"]["dimension"]]["column"]
    period = f"CASE WHEN f.{col} BETWEEN {q.p(rng[0])} AND {q.p(rng[1])} THEN 1 ELSE 0 END"   # parameters in text order
    e, kind = measure_row_expr(q, c["measure"])
    w = row_filters(q, plan, fact, rng, cmp_) + restriction(q, [c["measure"]])
    top, top2 = q.p(c["top"]), q.p(c["top"])
    sql = (f"WITH r AS (SELECT {dim_expr(c['dimension'])} AS g, {period} AS p, {e} AS v FROM query.{fact} f WHERE {' AND '.join(w)}),\n"
           "m AS (SELECT g, coalesce(sum(v) FILTER (WHERE p = 1), 0) - coalesce(sum(v) FILTER (WHERE p = 0), 0) AS d FROM r GROUP BY g),\n"
           "k AS (SELECT g, d, row_number() OVER (ORDER BY abs(d) DESC, g) AS rn FROM m),\n"
           "t AS (SELECT coalesce(sum(v) FILTER (WHERE p = 1), 0) - coalesce(sum(v) FILTER (WHERE p = 0), 0) AS d FROM r)\n"
           f"SELECT 'member' AS row_kind, g, d, rn FROM k WHERE rn <= {top}\n"
           f"UNION ALL SELECT 'other', NULL, coalesce(sum(d), 0), NULL FROM k WHERE rn > {top2}\n"
           "UNION ALL SELECT 'total', NULL, d, NULL FROM t\n"
           "UNION ALL SELECT 'reconciliation', NULL, t.d - coalesce((SELECT sum(d) FROM k), 0), NULL FROM t\n"
           "ORDER BY 4 NULLS LAST, 1")
    return sql, q.params, {"contributions": True, "fact": fact}


def compile_cell_rows(plan, ctx, cell, measure, top_keys=None):
    """ListAnalysisCellRow (rule 16): the fact rows behind one cell, each with its contribution, by the cell's kind."""
    q = Sql()
    rng, cmp_ = resolve_plan_time(plan, ctx)
    m = MEAS[measure]
    grains = {d["dimension"]: d.get("grain") for d in plan.get("dimensions") or []}
    c = plan.get("contributions")
    if c:
        grains[c["dimension"]] = None
    parts = []
    operands = [(measure, 1)] if m["aggregation"] != "difference" else [(o, s) for o, s in zip(split(m["column"]), (1, -1))]
    kind = "count_distinct" if m["aggregation"] == "count_distinct" else "sum"
    for op, sign in operands:
        om = MEAS[op]

        def expr():                                               # called once per occurrence, so parameters follow the text
            if om["aggregation"] == "count_distinct":
                return f"f.{om['column']}"
            e = measure_row_expr(q, op)[0]
            return f"{sign} * ({e})" if sign != 1 else e
        if c:                                                     # contribution rows: P1 with their sign, P0 negated
            col = DIMS[plan["time"]["dimension"]]["column"]
            per = f"f.{col} BETWEEN {q.p(rng[0])} AND {q.p(rng[1])}"
            contrib = f"CASE WHEN {per} THEN {expr()} ELSE -({expr()}) END"
        else:
            contrib = expr()
        w = row_filters(q, plan, om["fact"], rng, cmp_)
        sel = selector_sql(q, om)
        if sel:
            w.append(sel)
        for d, key in cell.items():
            x = dim_expr(d, grains.get(d), fact=om["fact"])
            if key == "~other":
                w.append(f"NOT ({x} = ANY({q.p(list(top_keys))}))")
            else:
                w.append(f"{x} = {q.p(key)}")
        parts.append(f"SELECT f.document_id, f.id, {contrib} AS contribution FROM query.{om['fact']} f WHERE {' AND '.join(w)}")
    sql = " UNION ALL ".join(parts) + " ORDER BY 1, 2"
    return sql, q.params, kind


def compile_balance_rows(plan, ctx, bucket_seq, first_seq):
    """Rule 16: a balance drills to an opening row (the turnover rows before the range) plus the journal lines of the range."""
    q = Sql()
    w_bal = row_filters(q, plan, "system_account_turnover", None, None)
    p1 = q.p(first_seq)
    w_lines = row_filters(q, plan, "journal_line_overview", None, None)
    p2, p3 = q.p(first_seq), q.p(bucket_seq)
    sql = (f"SELECT NULL::uuid AS document_id, NULL::uuid AS id, coalesce(sum(x.company_closing_balance), 0) AS contribution FROM "
           f"(SELECT DISTINCT ON ({BAL_KEYS}) f.* FROM query.system_account_turnover f WHERE {' AND '.join(w_bal)} AND f.period_seq < {p1}"
           f" ORDER BY {BAL_KEYS}, f.period_seq DESC) x\n"
           f"UNION ALL SELECT f.document_id, f.id, f.company_amount FROM query.journal_line_overview f WHERE {' AND '.join(w_lines)}"
           f" AND f.row_source = 'journal_line' AND f.period_seq BETWEEN {p2} AND {p3}")
    return sql, q.params


FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO|SET|LOCK|VACUUM|NOTIFY)\b", re.I)


def one_select(sql):
    s = sql.strip()
    allowed = set(FACTS) | set(LABEL_VIEWS.values()) | {f"{f.replace('_overview', '')}_line_dimension" for f in FACTS} | {"posting_period_dimension"}
    return (s.upper().startswith(("WITH", "SELECT")) and ";" not in s and not FORBIDDEN.search(s)
            and set(re.findall(r"\bquery\.(\w+)", s)) <= allowed and "erpme." not in s)


def scan_rows(node):
    """Rule 10, V13: the rows the planner estimates its scan nodes read, summed over the plan tree."""
    own = node.get("Plan Rows", 0) if node.get("Node Type", "").endswith("Scan") and "Relation Name" in node else 0
    return own + sum(scan_rows(ch) for ch in node.get("Plans", []))


def cost_guard(estimate, debug=False):
    """GetAnalysisPlanExplanation returns the raw estimate only to holders of read_analysis_debug (rule 14)."""
    status = "within_limit" if estimate <= SETTINGS["analysis_max_estimated_rows"] else "analysis_max_estimated_rows"
    return {"cost_guard": status, **({"estimated_rows": estimate} if debug else {})}


# ======================================================================= contributions, pure (rule 18)
def contributions(rows, top):
    """rows: (member or None, period 0/1, value). Returns the result rows; the total is computed from rows directly."""
    m = {}
    for g, p, val in rows:
        g = "~none" if g is None else g
        m.setdefault(g, [D(0), D(0)])[p] += val
    deltas = sorted(((g, v[1] - v[0]) for g, v in m.items()), key=lambda x: (-abs(x[1]), x[0]))
    out = [("member", g, d) for g, d in deltas[:top]]
    out.append(("other", None, sum((d for _, d in deltas[top:]), D(0))))
    total = sum((val if p == 1 else -val for _, p, val in rows), D(0))
    out.append(("total", None, total))
    out.append(("reconciliation", None, total - sum(d for k, _, d in out if k in ("member", "other"))))
    return out


# ======================================================================= explanation (rule 23): key facts and a narrative plan, both rendered by code
IDENT = re.compile(r"^[A-Za-z0-9_:~.-]{1,64}$")
TEMPLATES = {"en": {
    "value": "{measure} for {member}: {value} ({period})",
    "total": "{measure}, total: {value} ({period})",
    "change": "{measure} for {member} changed from {a} to {b} ({signed}, {direction})",
    "share": "{member}: {value} of {measure} ({period})",
    "contribution": "{member} contributed {signed} to the change in {measure} ({period} against {compare_period})",
    "direction": {1: "rose", -1: "fell", 0: "was unchanged"}}}
# The claim catalog (rule 23): template and fact roles. The model names no member; code renders members from each fact's row.
CLAIMS = {"en": {
    "largest_value": ("{member} has the largest {measure}.", ["fact"]),
    "smallest_value": ("{member} has the smallest {measure}.", ["fact"]),
    "largest_contributor": ("{member} is the largest contributor to the change in {measure}.", ["fact"]),
    "largest_offset": ("{member} is the largest offset to the change in {measure}.", ["fact"]),
    "most_of_change": ("{member} explains most of the change in {measure}.", ["fact"]),
    "rose": ("{measure} rose for {member}.", ["fact"]),
    "fell": ("{measure} fell for {member}.", ["fact"]),
    "flat": ("{measure} was almost unchanged for {member}.", ["fact"]),
    "same_direction": ("{measure} moved in the same direction for {member_a} and {member_b}.", ["fact_a", "fact_b"]),
    "opposite_direction": ("{measure} moved in opposite directions for {member_a} and {member_b}.", ["fact_a", "fact_b"]),
    "scope_note": ("These figures cover only the records you may see.", []),
    "also": ("Also,", []),
    "meanwhile": ("Meanwhile,", []),
}}
CONNECTORS = {"also", "meanwhile"}
FLAT_RATIO = D("0.01")                                          # the flat band: 1% of the absolute base value, an agent type constant
MEMBER_ROWS = ("member", "contribution")


def flat_band(c):
    return abs(D(c.get("base", "0"))) * FLAT_RATIO


def sgn(x):
    return (x > 0) - (x < 0)


def mark_extremes(cells_):
    """D5: is_max and is_min on member rows of each measure, only when the extreme is unique (rule 23)."""
    for kind, key in (("value", lambda v: v), ("contribution", abs)):
        by_measure = {}
        for cid, c in cells_.items():
            if c.get("row_kind") in MEMBER_ROWS and (c["kind"] == "value" if kind == "value" else c.get("row_kind") == "contribution"):
                by_measure.setdefault(c["measure"], []).append(cid)
        for m, ids in by_measure.items():
            vals = [key(D(cells_[i]["value"])) for i in ids]
            for flag, ext in (("is_max", max(vals)), ("is_min", min(vals))) if kind == "value" else (("is_max", max(vals)),):
                hits = [i for i, v in zip(ids, vals) if v == ext]
                for i in ids:
                    cells_[i][flag] = len(hits) == 1 and i == hits[0]
    return cells_


def precondition(claim, f, ctx):
    """Rule 23: each claim's deterministic precondition on the served cells. f: role -> (cell id, cell). Returns (holds, reason)."""
    c = f["fact"][1] if "fact" in f else None
    if claim in ("largest_value", "smallest_value"):
        flag = "is_max" if claim == "largest_value" else "is_min"
        return (c.get("row_kind") == "member" and c["kind"] == "value" and bool(c.get(flag)) and not ctx.get("truncated")
                and ctx.get("member_rows", 0) >= 2, f"not the unique {flag[3:]} member row of a complete result with two or more rows")
    if claim in ("largest_contributor", "largest_offset", "most_of_change"):
        t = D(ctx.get("total_change", "0"))
        if c.get("row_kind") != "contribution" or t == 0:
            return (False, "not a member contribution, or a zero total change")
        v = D(c["value"])
        want = sgn(t) if claim != "largest_offset" else -sgn(t)
        if sgn(v) != want:
            return (False, "contribution of the wrong sign")
        same = [D(x) for x in ctx.get("contrib", {}).values() if sgn(D(x)) == want]
        if claim == "most_of_change":
            pool = same + ([D(ctx["other"])] if "other" in ctx and sgn(D(ctx["other"])) == want else [])
            return (abs(v) > sum(abs(x) for x in pool) / 2, "not more than half of the contributions of its sign")
        return (abs(v) == max(abs(x) for x in same) and [abs(x) for x in same].count(abs(v)) == 1, "not the unique largest of its sign")
    if claim in ("rose", "fell", "flat"):
        if c["kind"] != "change" or c.get("row_kind") not in MEMBER_ROWS or not c.get("members"):
            return (False, "not a member row's change")
        v, band = D(c["value"]), flat_band(c)
        return ({"rose": v > band, "fell": v < -band, "flat": abs(v) <= band}[claim], f"change outside the {claim} condition")
    if claim in ("same_direction", "opposite_direction"):
        (ia, a), (ib, b) = f["fact_a"], f["fact_b"]
        if ia == ib or a["kind"] != "change" or b["kind"] != "change" or a.get("row_kind") not in MEMBER_ROWS or b.get("row_kind") not in MEMBER_ROWS:
            return (False, "not two distinct member changes")
        if a["measure"] != b["measure"] or a.get("comparison") != b.get("comparison"):
            return (False, "different measures or comparisons")
        va, vb = D(a["value"]), D(b["value"])
        outside = abs(va) > flat_band(a) and abs(vb) > flat_band(b)
        same = sgn(va) == sgn(vb)
        return (outside and (same if claim == "same_direction" else not same), "signs do not match the claim")
    if claim == "scope_note":
        return (bool(ctx.get("is_scope_filtered")), "result not scope-filtered")
    return (True, "")                                             # connectors


def validate_narrative(plan, offered, cells, lang="en"):
    """Rule 23: the narrative plan's shape. offered: handle -> cell id. Steps are {claim, facts}; no member, no free text."""
    errs = []
    if not isinstance(plan, list) or len(plan) > 8:
        return ["narrative_shape"]
    for i, st in enumerate(plan):
        if not isinstance(st, dict) or not set(st) <= {"claim", "facts"} or "claim" not in st or not isinstance(st.get("facts", {}), dict):
            errs.append(f"step{i}:shape")
            continue
        strings = [st["claim"]] + list((st.get("facts") or {}).keys()) + list((st.get("facts") or {}).values())
        if not all(isinstance(x, str) and IDENT.match(x) for x in strings):
            errs.append(f"step{i}:not_an_identifier")
            continue
        if st["claim"] not in CLAIMS[lang]:
            errs.append(f"step{i}:unknown_claim")
            continue
        f_ = st.get("facts") or {}
        if sorted(f_) != sorted(CLAIMS[lang][st["claim"]][1]):
            errs.append(f"step{i}:roles")
            continue
        if not all(h in offered for h in f_.values()):
            errs.append(f"step{i}:fact_not_offered")
    return errs


def validate_pick(pick, offered):
    """L3's key-fact pick: at most 5 offered handles, none twice (ADR-0050 rule 36)."""
    return isinstance(pick, list) and len(pick) <= 5 and len(set(pick)) == len(pick) and all(isinstance(h, str) and h in offered for h in pick)


def chip(label):
    return f"\u27e6{label}\u27e7"                                 # a member marker; the UI shows a chip or link, the label is data


def member_phrase(c, members):
    """Rule 23: the fact's whole row: every grouped member, and the pinned member of a pinned basis."""
    p = " in ".join(chip(members[m]) for m in c["members"])
    return p + (f" within {chip(members[c['pinned']])}" if c.get("pinned") else "")


def render_narrative(plan, offered, cells, members, mnames, ctx, lang="en"):
    """Rule 23: a pure function of (plan, cells, member labels, catalog). Returns (sentences, dropped)."""
    out, dropped, pending = [], [], ""
    cite = {h: i + 1 for i, h in enumerate(offered)}
    for i, st in enumerate(plan):
        tpl, froles = CLAIMS[lang][st["claim"]]
        f = {r: (offered[h], cells[offered[h]]) for r, h in (st.get("facts") or {}).items()}
        ok, reason = precondition(st["claim"], f, ctx)
        if not ok:
            dropped.append({"step": i, "claim": st["claim"], "reason": reason})
            pending = ""
            continue
        if st["claim"] in CONNECTORS:
            pending = tpl + " " if out else ""                      # only between two rendered sentences
            continue
        measure = next((mnames.get(c.get("measure"), c.get("measure")) for _, c in f.values()), "")
        args = {"member": member_phrase(f["fact"][1], members)} if "fact" in f else {}
        if "fact_a" in f:
            args = {"member_a": member_phrase(f["fact_a"][1], members), "member_b": member_phrase(f["fact_b"][1], members)}
        text = tpl.format(measure=measure, **args)
        refs = "".join(f" [{cite[h]}]" for h in (st.get("facts") or {}).values())
        out.append(pending + (text[:-1] + refs + "." if refs else text))
        pending = ""
    return out, dropped


def skeletons(mnames, lang="en"):
    """Every sentence shape the catalog can produce, with member phrases and citation markers taken out."""
    shapes = set()
    for code, (tpl, fr) in CLAIMS[lang].items():
        if code in CONNECTORS:
            continue
        for mn in list(mnames.values()) + [""]:
            base = tpl.format(measure=mn, member="\u27e6\u27e7", member_a="\u27e6\u27e7", member_b="\u27e6\u27e7")
            for pre in ("", "Also, ", "Meanwhile, "):
                shapes.add(pre + base)
    return shapes


def skeleton_of(sentence):
    s_ = re.sub(r"\u27e6[^\u27e7]*\u27e7(?: in \u27e6[^\u27e7]*\u27e7)*(?: within \u27e6[^\u27e7]*\u27e7)?", "\u27e6\u27e7", sentence)
    return re.sub(r" \[\d+\]", "", s_)


SAVED_ROLES = ("total", "total_change", "max", "min", "largest_contribution")


def resolve_saved(ref, result):
    """Rule 26: a saved fact is {role, measure} or {members: {dimension: key}, measure, kind}, never a cell position.
    Returns the one cell it names, or None (no cell, or several), which drops the step."""
    if not isinstance(ref, dict) or not ref.get("measure"):
        return None
    cs = [(cid, c) for cid, c in result.items() if c.get("measure") == ref["measure"]]
    if set(ref) == {"role", "measure"} and ref["role"] in SAVED_ROLES:
        r = ref["role"]
        if r == "total":
            cs = [x for x in cs if x[1].get("row_kind") == "total" and x[1]["kind"] == "value"]
        elif r == "total_change":
            cs = [x for x in cs if x[1].get("row_kind") == "total" and x[1]["kind"] in ("change", "contribution")]
        elif r in ("max", "min"):
            cs = [x for x in cs if x[1].get("row_kind") == "member" and x[1]["kind"] == "value" and x[1].get("is_" + r)]
        else:
            tot = [D(c["value"]) for _, c in cs if c.get("row_kind") == "total" and c["kind"] == "contribution"]
            t = tot[0] if len(tot) == 1 else D(0)
            same = [(cid, c) for cid, c in cs if c.get("row_kind") == "contribution" and t != 0 and sgn(D(c["value"])) == sgn(t)]
            top = max((abs(D(c["value"])) for _, c in same), default=None)
            cs = [x for x in same if abs(D(x[1]["value"])) == top]
    elif set(ref) == {"members", "measure", "kind"} and isinstance(ref["members"], dict):
        cs = [x for x in cs if x[1].get("member_keys") == ref["members"] and x[1]["kind"] == ref["kind"]]
    else:
        return None
    return cs[0][0] if len(cs) == 1 else None


def render_saved(plan, result, members, mnames, ctx, lang="en"):
    """Rule 26: resolve a saved plan's references on the new result, drop unresolved steps, then render as any plan."""
    offered, steps, unresolved = {}, [], []
    for i, st in enumerate(plan):
        facts = {}
        for role, ref in (st.get("facts") or {}).items():
            cid = resolve_saved(ref, result)
            if cid is None:
                facts = None
                break
            facts[role] = cid
        if facts is None:
            unresolved.append({"step": i, "claim": st["claim"], "reason": "reference resolves to no cell or to several"})
            continue
        for cid in facts.values():
            offered.setdefault(cid, cid)
        steps.append({"claim": st["claim"], "facts": {r: cid for r, cid in facts.items()}} if facts else {"claim": st["claim"]})
    out, dropped = render_narrative(steps, offered, result, members, mnames, ctx, lang)
    return out, unresolved + dropped


def fmt(value, basis, scale, signed=False):
    qv = D(value).quantize(D(1).scaleb(-scale), rounding=ROUND_HALF_UP)
    s_ = f"{qv:+,.{scale}f}" if signed else f"{qv:,.{scale}f}"
    return s_ + ("%" if basis == "percent" else f" {basis}" if basis not in ("count",) else "")


def key_fact(template, cells, members, measures, lang="en", period="", compare_period="", a=None, as_of=None):
    """Rule 23: a key fact rendered by code from the language's template; the direction word is computed from the sign.
    A balance or current-snapshot measure shows its as-of date instead of the period."""
    T = TEMPLATES[lang]
    c = cells[template[1]]
    mem = ", ".join(members[mm] for mm in c["members"]) or ""
    name = measures.get(c.get("measure", ""), c.get("measure", ""))
    if c.get("measure") in MEAS and MEAS[c["measure"]]["additivity"] == "semi_additive" and as_of:
        period = f"as of {as_of}"
    kind = template[0]
    if kind == "change":
        b = D(a) + D(c["value"])
        sign = (D(c["value"]) > 0) - (D(c["value"]) < 0)
        return T["change"].format(measure=name, member=mem, a=fmt(a, c["basis"], c["scale"]), b=fmt(b, c["basis"], c["scale"]),
                                  signed=fmt(c["value"], c["basis"], c["scale"], True), direction=T["direction"][sign])
    if kind == "contribution":
        return T["contribution"].format(member=mem, signed=fmt(c["value"], c["basis"], c["scale"], True), measure=name, period=period,
                                        compare_period=compare_period)
    return T[kind].format(measure=name, member=mem, value=fmt(c["value"], c["basis"], c["scale"]), period=period)


def default_facts(cells, truncated=False, k=5):
    """D5: the total, the largest member (complete results only) and the changes."""
    out = [("total", c) for c, v in cells.items() if v.get("row") == "total" and v["kind"] == "value"]
    out += [("value", c) for c, v in cells.items() if v.get("is_max") and v["kind"] == "value" and not truncated]
    out += [("change", c) for c, v in cells.items() if v["kind"] == "change" and v.get("row_kind") != "contribution"]
    return out[:k]


def explanation_language(lang, company_lang):
    """Rule 23: a language without a claim catalog and templates gets key facts only, in the company's language, else English."""
    if lang in TEMPLATES and lang in CLAIMS:
        return lang, True
    return (company_lang if company_lang in TEMPLATES else "en"), False


# ======================================================================= the agent's decisions (rules 22, 24)
OUTCOME = {"analysis_plan_invalid": "ambiguous_term", "unknown_measure": "ambiguous_term", "unknown_dimension": "ambiguous_term",
           "currency_mixed": "ambiguous_term", "unit_mixed": "ambiguous_term", "dimension_required": "ambiguous_term",
           "time_range_invalid": "ambiguous_term", "filter_value_unknown": "ambiguous_term",
           "dimension_not_shared": "out_of_coverage", "fan_out_refused": "out_of_coverage", "measure_not_additive": "out_of_coverage",
           "analysis_not_permitted": "not_permitted", "permission_denied": "not_permitted", "analysis_data_not_ready": "data_not_ready",
           "analysis_too_broad": "too_broad", "timeout": "too_broad", "period_unstated": "ambiguous_term"}   # the last: L2's stated-value check
NO_REPAIR = {"analysis_not_permitted", "permission_denied", "analysis_data_not_ready"}
MODEL_KIND = {"clarify": "ambiguous_term", "out_of_coverage": "out_of_coverage", "not_permitted": "not_permitted",
              "ambiguous_member": "ambiguous_member", "clarify_member": "ambiguous_member"}


def plan_loop(attempts, max_attempts=3):
    """attempts: the planner's successive outputs, each ('plan', [violation codes]) or (kind,). Returns (outcome, calls)."""
    calls, last = 0, None
    for out in attempts[:max_attempts]:
        calls += 1
        if out[0] != "plan":
            return MODEL_KIND[out[0]], calls
        codes = out[1]
        if not codes:
            return "answered", calls
        if codes[0] in NO_REPAIR:
            return OUTCOME[codes[0]], calls
        last = codes[0]
    return OUTCOME[last], calls


def member_outcome(matches):
    """A lookup with several members for one name abstains ambiguous_member with their handles (rule 24)."""
    if len(matches) == 1:
        return ("member", matches[0])
    if not matches:
        return ("filter_value_unknown", None)
    return ("ambiguous_member", [f"m{i + 1}" for i in range(len(matches))])


def code_member_decision(lookups, plan_members):
    """Rule 22: code, not the model, ends the run ambiguous_member when one search text matched several members and the plan uses one."""
    for text, found in lookups.items():
        if len(found) > 1 and set(found) & set(plan_members):
            return ("ambiguous_member", text, [f"m{i + 1}" for i in range(len(found))])
    return None


def normalize_question(text):
    t = unicodedata.normalize("NFC", text).casefold()
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"[\s?.!。？！]+$", "", t)


def token_set_ratio(a, b):
    """A stand-in for rapidfuzz's token-set ratio: 100 when one question's tokens are a subset of the other's."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0
    return 100 if ta <= tb or tb <= ta else int(200 * len(ta & tb) / (len(ta) + len(tb)))


def match_verified(question, verified, asker=None):
    """D2 (rule 22): exact equality of normalized questions only; similar questions become L1 hints, never answers. Only analyses
    and examples visible to the asker count: visibility company, or the asker's own private ones (rule 22, D1)."""
    nq = normalize_question(question)
    verified = [(e[0], e[1]) for e in verified if len(e) == 2 or e[2] == "company" or e[3] == asker]
    for vq, plan in verified:
        if normalize_question(vq) == nq:
            return plan, []
    hints = sorted(((token_set_ratio(nq, normalize_question(vq)), vq) for vq, _ in verified), reverse=True)
    return None, [vq for score, vq in hints[:5] if score > 0]


EN_NUMBERS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
EN_NUMBERS.update({"twenty": 20, "thirty": 30, "first": 1, "second": 2, "third": 3, "fourth": 4})
EN_MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}


def normalize_numbers(question, lang="en"):
    """Number words to digits and month names to month numbers, through the language's lists (rule 22)."""
    toks = re.findall(r"\w+|\S", question.casefold())
    out = []
    for t in toks:
        out.append(str(EN_NUMBERS[t]) if t in EN_NUMBERS else (f"month{EN_MONTHS[t]}" if t in EN_MONTHS else t))
    return " ".join(out)


def question_numbers(question):
    return {int(x) for x in re.findall(r"(?<![\d/.-])\d+(?![\d/.-])", question)}


def question_dates(question):
    out = set(re.findall(r"\d{4}-\d{2}-\d{2}", question))
    for d_, m_, y_ in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", question):   # the company's locale: day/month/year here
        out.add(f"{int(y_):04d}-{int(m_):02d}-{int(d_):02d}")
    return out


def stated_values_ok(plan, question):
    """L2's stated-value check (rule 22): absolute dates, named periods, n, limit and top must stand in the normalized question."""
    norm = normalize_numbers(question)
    nums, dates = question_numbers(norm), question_dates(question)
    months = {int(x) for x in re.findall(r"month(\d+)", norm)} | {int(m_) for m_, y_ in re.findall(r"\b(\d{1,2})/(\d{4})\b", question)}
    quarters = {int(x) for x in re.findall(r"\bq([1-4])\b", norm)} | ({n for n in nums if 1 <= n <= 4} if "quarter" in norm else set())
    t = plan.get("time") or {}
    for r in (t.get("range"), t.get("compare")):
        if not r:
            continue
        if "from" in r and not {str(r["from"]), str(r["to"])} <= dates:
            return False
        if "n" in r and int(r["n"]) not in nums:
            return False
        if "month" in r and not (int(str(r["month"])[:4]) in nums and int(str(r["month"])[5:7]) in months):
            return False
        for k in ("calendar_quarter", "fiscal_quarter"):
            if k in r and not (int(str(r[k])[:4]) in nums and int(str(r[k])[-1]) in quarters):
                return False
        for k in ("calendar_year", "fiscal_year"):
            if k in r and int(r[k]) not in nums:
                return False
    if plan.get("limit") is not None and plan["limit"] not in nums:
        return False
    if plan.get("contributions") and plan["contributions"].get("top") is not None and plan["contributions"]["top"] not in nums:
        return False
    return True


# ======================================================================= badge, KPI, caches, grants (rules 13, 26, 27, 30)
def badge(plan, verified, catalog=None):
    """verified: list of (analysis_plan_hash, open_filters) of verified versions and examples."""
    h = analysis_plan_hash(plan, catalog)
    for vh, open_f in verified:
        stripped = dict(plan, filters=[f for f in plan.get("filters") or [] if f["dimension"] not in open_f])
        if h == vh or analysis_plan_hash(stripped, catalog) == vh:
            return "verified"
    return "generated"


def kpi_status(value, target, direction, warning=None, critical=None):
    good = (lambda a, b: a >= b) if direction == "up" else (lambda a, b: a <= b)
    if critical is not None and not good(value, critical):
        return "critical"
    return "on_track" if good(value, warning if warning is not None else target) else "warning"


def scope_fingerprint(actor):
    return sha(jdump({"grants": actor.get("grants", {}), "classes": sorted(actor["classes"]), "wide": actor["wide"]}))


def cache_key(kind, company, user, actor, payload, version):
    return sha(jdump([kind, company, user, scope_fingerprint(actor), payload, CATALOG_HASH, version]))


def in_scope(row, grants, view):
    """Rule 13: a view reads its own grant entry only; no entry, no rows."""
    g = grants.get(view)
    if g is None:
        return False
    if g.get("branches") is not None and row["branch"] not in g["branches"]:
        return False
    return g["owner"] == "company" or row["created_by"] == g["user"]


def lookup_allowed(actor, dimension, fact):
    """ListAnalysisDimensionMember needs the List permission of a fact that offers the dimension (rule 14)."""
    return fact in actor["facts"] and fact in dim_facts(dimension)


# ======================================================================= C: catalogs
with open(os.path.join(CAT, "analysis-measures.csv"), encoding="utf-8", newline="") as f1, \
     open(os.path.join(CAT, "analysis-dimensions.csv"), encoding="utf-8", newline="") as f2:
    rows_m, rows_d = list(csv.reader(f1)), list(csv.reader(f2))
check("C01 both catalogs keep their header's field count on every row",
      all(len(r) == len(rows_m[0]) for r in rows_m) and all(len(r) == len(rows_d[0]) for r in rows_d))
check("C02 codes are unique snake_case and the catalog holds fewer than 40 measures (35) and 22 dimensions",
      len(MEAS) == len(rows_m) - 1 == 35 and len(DIMS) == len(rows_d) - 1 == 22
      and all(re.fullmatch(r"[a-z][a-z0-9_]*", c) for c in list(MEAS) + list(DIMS)), (len(MEAS), len(DIMS)))
sa_sel = [(c, v) for c, m in MEAS.items() for col, vals in selectors(m) if col == "system_account" for v in vals]
check("C03 the neutral core: every system account a selector names is a code of system-accounts.csv; no selector looks like an operational account number",
      sa_sel and all(v in SA_PARENT for _, v in sa_sel) and not any(re.search(r"\d", m["selector"]) for m in MEAS.values()), sa_sel[:3])
bad = []
for c, m in MEAS.items():
    for d in split(m["requires"]) + ({"transaction_currency": ["currency"], "inventory_unit": ["item"]}.get(m["basis"], [])):
        if m["fact"] not in dim_facts(d):
            bad.append((c, d))
    if m["default_time"] and m["fact"] not in dim_facts(m["default_time"]):
        bad.append((c, m["default_time"]))
check("C04 every fact offers the dimensions its measures' bases, requirements and default times need", not bad, bad[:3])
syn = [s.strip().casefold() for m in MEAS.values() for s in split(m["synonyms"])]
check("C05 synonyms are unique across measures (one certified measure per business term)", len(syn) == len(set(syn)),
      sorted({s for s in syn if syn.count(s) > 1}))
check("C06 derived measures name measures of their own fact; ratios are non-additive percent, differences keep their operands' basis",
      all(all(o in MEAS and MEAS[o]["fact"] == m["fact"] for o in split(m["column"])) for m in MEAS.values() if m["aggregation"] in DERIVED)
      and all(m["additivity"] == "non_additive" and m["basis"] == "percent" for m in MEAS.values() if m["aggregation"] == "ratio")
      and all(len({MEAS[o]["basis"] for o in split(m["column"])} | {m["basis"]}) == 1 for m in MEAS.values() if m["aggregation"] == "difference"))
check("C07 hierarchies close: every parent dimension exists and shares its child's facts; only system_account is a tree; kinds are time, entity, catalog or enum",
      all(not r["parent_code"] or (r["parent_code"] in DIMS and dim_facts(r["parent_code"]) >= dim_facts(c)) for c, r in DIMS.items())
      and [c for c, r in DIMS.items() if r["is_tree"] == "true"] == ["system_account"]
      and {r["kind"] for r in DIMS.values()} == {"time", "entity", "catalog", "enum"} and all(bool(r["values"]) == (r["kind"] == "enum") for r in DIMS.values()))
check("C08 every semi-additive measure names the one dimension it is not additive over: posting_period for balances, as_of for current snapshots",
      all((m["non_additive_over"] == "posting_period") == (m["fact"] == "system_account_turnover") and m["non_additive_over"] in ("posting_period", "as_of")
          for m in MEAS.values() if m["additivity"] == "semi_additive") and not any(m["non_additive_over"] for m in MEAS.values() if m["additivity"] != "semi_additive"))
jsum = [m for m in MEAS.values() if m["fact"] == "journal_line_overview" and m["aggregation"] == "sum"]
pnl = [m for m in jsum if any(col == "system_account" and sa_path(v).split("/")[0] in PNL_ROOTS for col, vals in selectors(m) for v in vals)]
check("C09 ADR-0049's turnover options: every journal turnover measure excludes migration entries, and every profit-and-loss one closing entries too; balances keep both",
      len(pnl) == 4 and all("migration_entries:exclude" in m["selector"] for m in jsum) and all("closing_entries:exclude" in m["selector"] for m in pnl)
      and not any("closing_entries" in m["selector"] for m in jsum if m not in pnl) and "entries" not in MEAS["ledger_closing_balance"]["selector"],
      [m["code"] for m in pnl])
check("C10 field classes always on ledger cost and margin: cost_of_goods_sold cost, gross_profit and gross_margin_percent margin",
      (MEAS["cost_of_goods_sold"]["field_class"], MEAS["gross_profit"]["field_class"], MEAS["gross_margin_percent"]["field_class"]) == ("cost", "margin", "margin"))

# ======================================================================= V: validation
BD = date(2026, 11, 20)
CTX = {"business_date": BD, "fy_month": 4, "cutover": date(2025, 4, 1), "members": {
    "branch": {"B1", "B2"}, "partner": {"P1", "P2", "P3"}, "item": {"I1", "I2"}, "product": {"PR1"}, "item_group": {"IG1", "IG2"},
    "partner_group": {"G1"}, "warehouse": {"W1"}, "account": {"A1"}, "cost_center": {"CC1"}, "currency": {"USD", "VND"}},
    "member_count": {"branch": 2, "item_group": 5, "currency": 3, "system_account": 20, "partner_group": 4, "overdue_bucket": 5, "document_type": 8}}
ALL = {"facts": set(FACTS), "classes": {"cost", "margin"}, "wide": True, "agent": False}
AGENT = dict(ALL, agent=True)
CLERK = {"facts": set(FACTS) - NOT_OWNER_SCOPED, "classes": set(), "wide": False, "agent": True}
LAST_Q = {"dimension": "posting_date", "range": {"relative": "last_fiscal_quarter"}}
P_GOOD1 = {"plan_version": 1, "measures": ["net_revenue"], "dimensions": [{"dimension": "item_group"}, {"dimension": "posting_date", "grain": "month"}],
           "time": LAST_Q, "with_total_row": True}
P_GOOD2 = {"plan_version": 1, "measures": ["sales_line_amount"], "dimensions": [{"dimension": "currency"}, {"dimension": "partner"}],
           "time": {"dimension": "posting_date", "range": {"from": "2026-10-01", "to": "2026-11-30"}}, "limit": 2, "with_other_row": True, "with_total_row": True}
P_GOOD3 = {"plan_version": 1, "measures": ["net_revenue"], "time": {"dimension": "posting_date", "range": {"relative": "this_month"}, "compare": {"relative": "previous_period"}},
           "contributions": {"measure": "net_revenue", "dimension": "partner", "top": 10}}
P_GOOD4 = {"plan_version": 1, "measures": ["receivable_open_amount"], "dimensions": [{"dimension": "overdue_bucket"}], "with_total_row": True}
P_GOOD5 = {"plan_version": 1, "measures": ["ledger_closing_balance"], "filters": [{"dimension": "system_account", "op": "in_subtree", "values": ["inventory"]}],
           "time": {"dimension": "posting_period", "range": {"relative": "last_month"}}}
for name, p, a in (("V01 net revenue by item group and month, last fiscal quarter, with totals", P_GOOD1, AGENT),
                   ("V02 transaction-currency amounts by currency and top-2 customers with the other row", P_GOOD2, AGENT),
                   ("V03 a contribution plan of net revenue by customer, this month against the previous one", P_GOOD3, AGENT),
                   ("V04 open receivables by overdue bucket at the current snapshot, no range needed", P_GOOD4, AGENT),
                   ("V05 a closing balance of the inventory subtree, for an actor with company owner scope", P_GOOD5, ALL)):
    vv = validate(p, a, CTX)
    check(name + ": accepted", vv == [], vv)


def bad_plan(**over):
    p = json.loads(json.dumps(P_GOOD1))
    for k, v in over.items():
        if v is None:
            p.pop(k, None)
        else:
            p[k] = v
    return p


BAD = [
    ("analysis_plan_invalid", bad_plan(plan_version=2, colour="red"), AGENT, "a wrong version and an unknown field"),
    ("unknown_measure", bad_plan(measures=["website_visits"]), AGENT, "a measure outside the catalog"),
    ("unknown_dimension", bad_plan(dimensions=[{"dimension": "region"}]), AGENT, "a dimension outside the catalog"),
    ("analysis_not_permitted", bad_plan(measures=["gross_profit"], dimensions=[{"dimension": "item_group"}]), dict(CLERK, facts=set(FACTS)), "gross profit without the margin class (field classes always)"),
    ("dimension_not_shared", bad_plan(dimensions=[{"dimension": "overdue_bucket"}]), AGENT, "an open-item dimension on journal lines"),
    ("fan_out_refused", {"plan_version": 1, "measures": ["receivable_open_amount"], "dimensions": [{"dimension": "item"}], "limit": 10, "with_other_row": True}, AGENT,
     "open receivables grouped by item, reached only through invoice lines"),
    ("currency_mixed", bad_plan(measures=["sales_line_amount"], dimensions=[{"dimension": "item_group"}]), AGENT, "document amounts summed across currencies"),
    ("unit_mixed", bad_plan(measures=["sales_quantity"], dimensions=[{"dimension": "item_group"}]), AGENT, "quantities summed across products"),
    ("dimension_required", bad_plan(measures=["ledger_net_turnover"], dimensions=[{"dimension": "branch"}]), AGENT, "ledger turnover without a system account"),
    ("measure_not_additive", dict(P_GOOD3, measures=["gross_margin_percent"], contributions={"measure": "gross_margin_percent", "dimension": "partner", "top": 5}), AGENT,
     "contributions of a ratio"),
    ("time_range_invalid", bad_plan(time={"dimension": "posting_date", "range": {"from": "2026-11-30", "to": "2026-10-01"}}), AGENT, "an unordered range"),
    ("filter_value_unknown", bad_plan(filters=[{"dimension": "branch", "op": "eq", "values": ["B9"]}]), AGENT, "a branch outside the scope"),
    ("analysis_too_broad", bad_plan(time={"dimension": "posting_date", "range": {"from": "2020-01-01", "to": "2026-11-30"}}), AGENT, "a range of 83 months"),
    ("analysis_data_not_ready", bad_plan(time={"dimension": "posting_date", "range": {"from": "2025-01-01", "to": "2025-06-30"}}), AGENT, "a range before the cut-over"),
]
for i, (code, p, a, why) in enumerate(BAD):
    vv = validate(p, a, CTX)
    check(f"V{6 + i:02d} refused with {code}: {why}", vv and vv[0][0] == code, vv[:2])
check("V20 all 14 codes of rule 10 are exercised, in the rule's order", [b[0] for b in BAD] == ORDER)
vv = validate(bad_plan(measures=["sales_line_amount", "sales_quantity"], dimensions=[{"dimension": "item_group"}], colour="x"), AGENT, CTX)
check("V21 every violation is returned with its path, the first code answers (so one repair round can fix all)",
      [x[0] for x in vv] == ["analysis_plan_invalid", "currency_mixed", "unit_mixed"] and all(x[1] for x in vv), vv)
check("V22 owner scope: a clerk without branch or company owner scope may not read the closing balance fact; the agent limit is 50",
      validate(P_GOOD5, CLERK, CTX)[0][0] == "analysis_not_permitted"
      and validate(dict(P_GOOD2, limit=60), AGENT, CTX)[0][0] == "analysis_plan_invalid" and validate(dict(P_GOOD2, limit=60), ALL, CTX) == [])
check("V23 a high-cardinality dimension needs a limit; a filter on one currency pins the basis; grouping by currency pins it too, with subtotals",
      validate(dict(P_GOOD2, limit=None), AGENT, CTX)[0][0] == "analysis_too_broad"
      and validate(dict(P_GOOD2, dimensions=[{"dimension": "item_group"}], filters=[{"dimension": "currency", "op": "eq", "values": ["USD"]}], limit=None), AGENT, CTX) == []
      and pinned_by_group(P_GOOD2) == ["currency"] and pinned_by_group(P_GOOD1) == [])
check("V24 items filter open items through EXISTS (allowed) but never group them; a past as-of on a current snapshot is data_not_ready",
      validate(dict(P_GOOD4, filters=[{"dimension": "item", "op": "eq", "values": ["I1"]}]), AGENT, CTX) == []
      and validate(dict(P_GOOD4, time={"dimension": "due_date", "as_of": "2026-10-31"}), AGENT, CTX)[0][0] == "analysis_data_not_ready")
check("V25 the agent's cell ceiling (500) trips before the people's (5,000): 31 days by 20 system accounts",
      validate({"plan_version": 1, "measures": ["ledger_net_turnover"], "dimensions": [{"dimension": "system_account"}, {"dimension": "posting_date", "grain": "day"}],
                "time": {"dimension": "posting_date", "range": {"relative": "last_month"}}}, AGENT, CTX)[0][0] == "analysis_too_broad"
      and validate({"plan_version": 1, "measures": ["ledger_net_turnover"], "dimensions": [{"dimension": "system_account"}, {"dimension": "posting_date", "grain": "day"}],
                    "time": {"dimension": "posting_date", "range": {"relative": "last_month"}}}, ALL, CTX) == [])
PC_TC = {"plan_version": 1, "measures": ["sales_line_amount"], "time": {"dimension": "posting_date", "range": {"relative": "this_month"}, "compare": {"relative": "previous_period"}},
         "contributions": {"measure": "sales_line_amount", "dimension": "partner", "top": 5}}
check("V26 contributions of a transaction-currency measure need a filter on one currency (a total change across currencies would mix them)",
      validate(PC_TC, AGENT, CTX)[0][0] == "currency_mixed"
      and validate(dict(PC_TC, filters=[{"dimension": "currency", "op": "eq", "values": ["VND"]}]), AGENT, CTX) == [])
check("V27 field classes always: cost of goods sold by item group needs cost even for a branch-wide question; with the class it passes",
      validate(bad_plan(measures=["cost_of_goods_sold"]), dict(ALL, classes={"margin"}), CTX)[0][0] == "analysis_not_permitted"
      and validate(bad_plan(measures=["cost_of_goods_sold"]), ALL, CTX) == [])
check("V28 an unknown relative range and an unknown special-period option are refused; last_n_months and previous_month_same_days pass",
      validate(bad_plan(time={"dimension": "posting_date", "range": {"relative": "last_fortnight"}}), AGENT, CTX)[0][0] == "time_range_invalid"
      and validate(bad_plan(time=dict(LAST_Q, special_periods="maybe")), AGENT, CTX)[0][0] == "analysis_plan_invalid"
      and validate(bad_plan(time={"dimension": "posting_date", "range": {"relative": "last_n_months", "n": 6}, "compare": {"relative": "previous_month_same_days"}}), AGENT, CTX) == [])

# ======================================================================= S: compiler
COMP = [compile_plan(p, CTX) for p in (P_GOOD1, P_GOOD2, P_GOOD3, P_GOOD4, P_GOOD5)]
check("S01 every compiled plan is one SELECT over declared query views, with no DML, no ';' and no erpme table",
      all(one_select(s) for s, _, _ in COMP), [s[:80] for s, _, _ in COMP if not one_select(s)])
SECRET = "Robert'); DROP TABLE x;--"
pp = dict(P_GOOD1, filters=[{"dimension": "branch", "op": "in", "values": [SECRET, "B1"]}])
s_, prm, _ = compile_plan(pp, CTX)
check("S02 filter values are bound parameters: a hostile value never appears in the SQL text and travels in the parameters",
      SECRET not in s_ and "B1" not in s_ and [SECRET, "B1"] in prm and one_select(s_))
check("S03 every fact aggregation filters on is_in_scope, and the scope flag is one EXISTS over NOT is_in_scope",
      all("f.is_in_scope" in s and "NOT f.is_in_scope" in s for s, _, m in COMP if not m.get("contributions")) and "f.is_in_scope" in COMP[2][0])
check("S04 the grand total comes from GROUPING SETS; a basis pinned by currency gets subtotals per currency and no grand total",
      "GROUPING SETS ((g1, g2), ())" in COMP[0][0] and "GROUPING SETS ((g1, g2), (g1))" in COMP[1][0] and "'subtotal'" in COMP[1][0]
      and "'~other'" in COMP[1][0] and "PARTITION BY g1" in COMP[1][0])
s2, _, m2 = compile_plan({"plan_version": 1, "measures": ["net_revenue", "sales_customer_count"], "dimensions": [{"dimension": "item_group"}],
                          "time": LAST_Q, "with_total_row": True}, CTX)
check("S05 two facts aggregate apart and join on dimension keys and the grouping flag (no fact rows joined, no fan-out)",
      m2["facts"] == ["journal_line_overview", "sales_line_overview"] and "FULL JOIN a1 ON" in s2 and "count(DISTINCT" in s2 and one_select(s2))
check("S06 the contribution statement carries member, other, total and reconciliation rows and computes the total from rows",
      all(k in COMP[2][0] for k in ("'other'", "'total'", "'reconciliation'", "FILTER (WHERE p = 1)")))
s7, p7, k7 = compile_cell_rows(P_GOOD1, CTX, {"item_group": "IG1", "posting_date": "2026-08-01"}, "net_revenue")
check("S07 a drill-row statement is one SELECT with the cell's members, the closing and migration exclusions and the subtree bound",
      one_select(s7) and "IG1" not in s7 and "IG1" in p7 and "%/revenue/%" in p7 and "NOT f.is_closing_entry" in s7 and "NOT f.is_migration_entry" in s7 and k7 == "sum")
check("S08 the semi-additive closing balance reads the latest period per key (DISTINCT ON period order), never a sum over periods",
      "DISTINCT ON" in COMP[4][0] and "period_seq DESC" in COMP[4][0])
check("S09 the open-item item filter compiles to EXISTS over its line dimension view",
      "EXISTS (SELECT 1 FROM query.open_item_line_dimension" in compile_plan(dict(P_GOOD4, filters=[{"dimension": "item", "op": "eq", "values": ["I1"]}]), CTX)[0])
sb, _, mb = compile_plan({"plan_version": 1, "measures": ["ledger_closing_balance"], "dimensions": [{"dimension": "posting_period", "grain": "posting_period"}],
                          "filters": [{"dimension": "system_account", "op": "in_subtree", "values": ["revenue"]}],
                          "time": {"dimension": "posting_period", "range": {"from": "2026-10-01", "to": "2026-11-30"}}, "with_total_row": True}, CTX)
check("S10 a balance by posting period carries each key forward per bucket (LATERAL, latest row at or before the bucket) and totals the last bucket",
      mb.get("balance_buckets") and "CROSS JOIN LATERAL" in sb and "f.period_seq <= b.bseq" in sb and "max(bseq)" in sb and one_select(sb))
st, _, _ = compile_plan(dict(P_GOOD1, dimensions=[{"dimension": "item_group"}], limit=1), CTX)
check("S11 a limit without the other row truncates: tail members become ~cut, excluded from the rows, kept in the total, and is_truncated is computed",
      "'~cut'" in st and "IS DISTINCT FROM '~cut'" in st and "AS is_truncated" in st and one_select(st))
sd, pd, _ = compile_cell_rows(P_GOOD1, CTX, {"item_group": "IG1", "posting_date": "2026-08-01"}, "gross_profit")
check("S12 a difference cell drills to the signed union of its operands' rows (net revenue +, cost of goods sold -)",
      sd.count("SELECT f.document_id") == 2 and "-1 * (" in sd and "%/cost_of_goods_sold/%" in pd and one_select(sd))
check("S13 special_periods exclude adds the flag filter on journal lines", "NOT f.is_special_period" in compile_plan(bad_plan(time=dict(LAST_Q, special_periods="exclude")), CTX)[0])
check("S14 the cost guard sums the rows of scan nodes, not output rows, and shows the estimate only with the debug capability",
      scan_rows({"Node Type": "Aggregate", "Plan Rows": 2, "Plans": [{"Node Type": "Seq Scan", "Relation Name": "journal_line", "Plan Rows": 900},
                 {"Node Type": "Hash Join", "Plan Rows": 5, "Plans": [{"Node Type": "Index Scan", "Relation Name": "document", "Plan Rows": 100}]}]}) == 1000
      and cost_guard(10) == {"cost_guard": "within_limit"} and cost_guard(10, True)["estimated_rows"] == 10
      and cost_guard(6_000_000) == {"cost_guard": "analysis_max_estimated_rows"})

# ======================================================================= H, T: hashes and time
pa = {"plan_version": 1, "measures": ["sales_cost", "net_revenue"], "filters": [{"dimension": "branch", "op": "in", "values": ["B2", "B1"]},
      {"dimension": "currency", "op": "eq", "values": ["USD"]}], "time": LAST_Q}
pb = {"time": dict(LAST_Q, special_periods="include"), "filters": [{"values": ["USD"], "op": "eq", "dimension": "currency"}, {"dimension": "branch", "values": ["B1", "B2"], "op": "in"}],
      "measures": ["net_revenue", "sales_cost"], "plan_version": 1, "derived": [], "with_total_row": False}
check("H01 analysis_plan_hash ignores key order, list order of measures, filters and values, and stated defaults", analysis_plan_hash(pa) == analysis_plan_hash(pb))
check("H02 relative dates keep the plan hash across months; the resolved hash changes with the business date",
      analysis_resolved_hash(P_GOOD1, CTX) != analysis_resolved_hash(P_GOOD1, dict(CTX, business_date=date(2027, 3, 5)))
      and analysis_resolved_hash(P_GOOD1, CTX) == analysis_resolved_hash(P_GOOD1, dict(CTX)))
CAT2 = {**{("m", k): dict(v) for k, v in MEAS.items()}, **{("d", k): dict(v) for k, v in DIMS.items()}}
CAT2[("m", "net_revenue")]["selector"] = "system_account:revenue_goods;closing_entries:exclude;migration_entries:exclude"
CAT3 = {**{("m", k): dict(v) for k, v in MEAS.items()}, **{("d", k): dict(v) for k, v in DIMS.items()}}
CAT3[("m", "stock_value")]["column"] = "other_value"
check("H03 the plan hash covers the definitions it names: a changed net_revenue changes P1's hash, a changed stock_value does not; label texts do not count",
      analysis_plan_hash(P_GOOD1, CAT2) != analysis_plan_hash(P_GOOD1) and analysis_plan_hash(P_GOOD1, CAT3) == analysis_plan_hash(P_GOOD1)
      and definition_hash("net_revenue", {**CAT3, ("m", "net_revenue"): dict(MEAS["net_revenue"], meaning="x")}) == definition_hash("net_revenue"))
CTX_O = dict(CTX, cutover=date(2026, 10, 1), opening_turnover=[(date(2026, 4, 1), date(2026, 9, 30))])
PO = {"plan_version": 1, "measures": ["net_revenue"], "dimensions": [{"dimension": "posting_date", "grain": "month"}],
      "time": {"dimension": "posting_date", "range": {"from": "2026-04-01", "to": "2026-11-30"}}, "with_total_row": True}
check("V29 a range before the cut-over passes only where opening_turnover rows cover it whole for measures that exclude closing entries; a malformed named period is refused",
      validate(PO, ALL, CTX_O) == [] and validate(dict(PO, time={"dimension": "posting_date", "range": {"from": "2026-05-01", "to": "2026-11-30"}}), ALL, CTX_O)[0][0] == "analysis_data_not_ready"
      and validate(dict(PO, measures=["ledger_net_turnover"], filters=[{"dimension": "system_account", "op": "in_subtree", "values": ["revenue"]}]), ALL, CTX_O)[0][0] == "analysis_data_not_ready"
      and validate(bad_plan(time={"dimension": "posting_date", "range": {"month": "2026-13"}}), AGENT, CTX)[0][0] == "time_range_invalid")
ss, _, _ = compile_plan({"plan_version": 1, "measures": ["sales_line_amount"], "dimensions": [{"dimension": "currency"}], "time": LAST_Q, "with_total_row": True}, CTX)
check("S15 a basis pinned by the only grouped dimension adds no subtotal rows (each member row is its subtotal) and no grand total",
      "GROUPING SETS ((g1))" in ss and "GROUPING SETS ((g1), (g1))" not in ss and "()" not in ss.split("GROUPING SETS")[1][:20])
BAL = {"plan_version": 1, "measures": ["ledger_closing_balance"], "filters": [{"dimension": "system_account", "op": "in_subtree", "values": ["revenue"]}],
       "time": {"dimension": "posting_period", "range": {"from": "2026-10-01", "to": "2026-11-30"}}, "with_total_row": True}
s16a = compile_plan(dict(BAL, dimensions=[{"dimension": "posting_period", "grain": "posting_period"}, {"dimension": "branch"}]), CTX)[0]
s16b = compile_plan(dict(BAL, dimensions=[{"dimension": "posting_period", "grain": "fiscal_year"}]), CTX)[0]
s16c = compile_plan(dict(BAL, dimensions=[{"dimension": "posting_period", "grain": "posting_period"}], time=dict(BAL["time"], special_periods="exclude")), CTX)[0]
check("S16 carry-forward with another grouped dimension carries per group; the fiscal-year bucket ends at the year's last period; special_periods exclude skips only that year's special periods",
      "CROSS JOIN LATERAL" in s16a and "x.branch_id" in s16a and "GROUP BY bkey, bseq, o0" in s16a and "max(p.seq)" in s16b and "GROUP BY p.fiscal_year_id" in s16b
      and "p.kind = 'special' AND p.fiscal_year_id =" in s16c and "f.is_special_period AND f.fiscal_year_id =" in s16c and all(one_select(x) for x in (s16a, s16b, s16c)))
check("S17 a month breakdown of journal measures puts opening_turnover rows into their own member ~opening", "THEN '~opening'" in compile_plan(PO, CTX_O)[0])
s18 = compile_plan(dict(BAL, measures=["ledger_closing_balance", "ledger_net_turnover"], dimensions=[{"dimension": "posting_period", "grain": "posting_period"}]), CTX)[0]
check("S18 a balance beside a second fact keeps the per-bucket carry-forward inside its own aggregation and joins the other fact on the bucket keys",
      "CROSS JOIN LATERAL" in s18 and "FULL JOIN" in s18 and "WHERE bseq = (SELECT max(bseq) FROM b1)" in s18 and one_select(s18))
R_ = lambda rel, bd=BD, **k: resolve_range(dict(relative=rel, **k), bd, 4)
check("T01 fiscal year from April: business date 2026-11-20 is in fiscal quarter Oct-Dec; the last fiscal quarter is Jul-Sep; the fiscal year Apr 2026 to Mar 2027",
      R_("this_fiscal_quarter") == (date(2026, 10, 1), date(2026, 12, 31)) and R_("last_fiscal_quarter") == (date(2026, 7, 1), date(2026, 9, 30))
      and R_("this_fiscal_year") == (date(2026, 4, 1), date(2027, 3, 31)) and R_("fiscal_year_to_date") == (date(2026, 4, 1), BD))
check("T02 a business date in February belongs to the fiscal year that started the April before; calendar quarters and years ignore the fiscal year",
      R_("this_fiscal_year", date(2027, 2, 10)) == (date(2026, 4, 1), date(2027, 3, 31)) and R_("last_fiscal_quarter", date(2027, 2, 10)) == (date(2026, 10, 1), date(2026, 12, 31))
      and R_("last_calendar_quarter") == (date(2026, 7, 1), date(2026, 9, 30)) and R_("last_calendar_year") == (date(2025, 1, 1), date(2025, 12, 31)))
check("T03 comparisons: the previous whole month, the same length before a partial range, the same days of the previous month, and 29 February a year back",
      compare_range((date(2026, 11, 1), date(2026, 11, 30)), {"relative": "previous_period"}, BD, 4) == (date(2026, 10, 1), date(2026, 10, 31))
      and compare_range((date(2026, 11, 1), date(2026, 11, 20)), {"relative": "previous_period"}, BD, 4) == (date(2026, 10, 12), date(2026, 10, 31))
      and compare_range((date(2026, 11, 1), date(2026, 11, 20)), {"relative": "previous_month_same_days"}, BD, 4) == (date(2026, 10, 1), date(2026, 10, 20))
      and compare_range((date(2027, 3, 1), date(2027, 3, 31)), {"relative": "previous_month_same_days"}, BD, 4) == (date(2027, 2, 1), date(2027, 2, 28))
      and compare_range((date(2028, 2, 29), date(2028, 2, 29)), {"relative": "same_period_last_year"}, BD, 4) == (date(2027, 2, 28), date(2027, 2, 28)))
check("T04 ISO weeks start on Monday (2026-11-20 is a Friday); last_n_weeks and last_n_months are whole weeks and months before the current one",
      R_("this_week") == (date(2026, 11, 16), date(2026, 11, 22)) and R_("last_week") == (date(2026, 11, 9), date(2026, 11, 15))
      and R_("last_n_weeks", n=2) == (date(2026, 11, 2), date(2026, 11, 15)) and R_("last_n_months", n=6) == (date(2026, 5, 1), date(2026, 10, 31))
      and R_("last_n_days", n=30) == (date(2026, 10, 22), BD))

VH2 = dict(VIEW_HASH, journal_line_overview=sha("journal_line_overview:changed-sign"))
SA2 = dict(SA_PARENT, revenue_new_child="revenue")
check("H04 the definition hash covers what a measure reads: a changed journal view or a new child account under revenue changes P1's hash; a changed stock view does not",
      analysis_plan_hash(P_GOOD1, views=VH2) != analysis_plan_hash(P_GOOD1) and analysis_plan_hash(P_GOOD1, accounts=SA2) != analysis_plan_hash(P_GOOD1)
      and analysis_plan_hash(P_GOOD1, views=dict(VIEW_HASH, stock_overview="x")) == analysis_plan_hash(P_GOOD1)
      and badge(P_GOOD1, [(analysis_plan_hash(P_GOOD1), [])]) == "verified")
NP = lambda **k: resolve_range(k, BD, 4)
check("T05 named periods resolve by code: March 2026, Q1 2026, calendar year 2025, fiscal year 2026 (Apr-Mar), fiscal Q2 2026 (Jul-Sep)",
      NP(month="2026-03") == (date(2026, 3, 1), date(2026, 3, 31)) and NP(calendar_quarter="2026-Q1") == (date(2026, 1, 1), date(2026, 3, 31))
      and NP(calendar_year=2025) == (date(2025, 1, 1), date(2025, 12, 31)) and NP(fiscal_year=2026) == (date(2026, 4, 1), date(2027, 3, 31))
      and NP(fiscal_quarter="2026-Q2") == (date(2026, 7, 1), date(2026, 9, 30)))

# ======================================================================= K: contributions
rnd = random.Random(60)
ok, ties_seen, none_seen = True, False, False
for _ in range(300):
    rows_ = [(rnd.choice(["A", "B", "C", "D", "E", "F", None]), rnd.randint(0, 1),
              (D(rnd.randint(-500, 5000)) / 100 if rnd.random() < 0.5 else D(rnd.randint(-3, 9)))) for _ in range(rnd.randint(1, 60))]
    out = contributions(rows_, rnd.randint(1, 4))
    recon = [d for k, _, d in out if k == "reconciliation"][0]
    total = [d for k, _, d in out if k == "total"][0]
    ok &= recon == 0 and total == sum(v for _, p, v in rows_ if p == 1) - sum(v for _, p, v in rows_ if p == 0)
    deltas = [d for k, _, d in out if k == "member"]
    ties_seen |= len(set(map(abs, deltas))) < len(deltas)
    none_seen |= any(g == "~none" for k, g, _ in out if k == "member")
check("K01 over 300 random data sets the reconciliation row is exactly zero and the total equals the change computed from rows", ok)
check("K02 the data sets exercised ties in |change| (broken by member key) and rows without a member (the none member)", ties_seen and none_seen)
out = contributions([("A", 0, D(100)), ("A", 1, D(100)), ("B", 1, D(30)), ("C", 0, D(40))], 1)
check("K03 a member in one period only counts the other as zero; ranking by |change| puts C (-40) before B (+30); A unchanged",
      out[0] == ("member", "C", D(-40)) and out[1] == ("other", None, D(30)) and out[2] == ("total", None, D(-10)) and out[3][2] == 0, out)

# ======================================================================= N: the explanation
cells = mark_extremes({
    "c1": {"kind": "value", "value": "1250000", "basis": "VND", "scale": 0, "members": [], "row_kind": "total", "row": "total", "measure": "net_revenue"},
    "c2": {"kind": "value", "value": "900000", "basis": "VND", "scale": 0, "members": ["m1", "m6"], "row_kind": "member", "row": "r1", "measure": "net_revenue"},
    "c3": {"kind": "change", "value": "-40000", "base": "940000", "basis": "VND", "scale": 0, "members": ["m1", "m6"], "row_kind": "member", "row": "r1", "measure": "net_revenue", "comparison": "P0"},
    "c4": {"kind": "value", "value": "350000", "basis": "VND", "scale": 0, "members": ["m2", "m6"], "row_kind": "member", "row": "r2", "measure": "net_revenue"},
    "c5": {"kind": "change", "value": "125000", "base": "225000", "basis": "VND", "scale": 0, "members": ["m2", "m6"], "row_kind": "member", "row": "r2", "measure": "net_revenue", "comparison": "P0"},
    "c6": {"kind": "change", "value": "-3000", "base": "900000", "basis": "VND", "scale": 0, "members": ["m3", "m6"], "row_kind": "member", "row": "r3", "measure": "net_revenue", "comparison": "P0"},
    "c7": {"kind": "change", "value": "-60000", "base": "300000", "basis": "VND", "scale": 0, "members": ["m2", "m6"], "row_kind": "member", "row": "r2", "measure": "cost_of_goods_sold", "comparison": "P0"},
    "c8": {"kind": "value", "value": "500000", "basis": "VND", "scale": 0, "members": ["m3", "m6"], "row_kind": "member", "row": "r3", "measure": "net_revenue"}})
members = {"m1": "Item group A", "m2": "Item group B", "m3": "Line 2", "m4": "Customer P3", "m5": "Customer P1", "m6": "November 2026", "m7": "USD", "m8": "Tripled to 500"}
MNAMES = {"net_revenue": "Net revenue", "cost_of_goods_sold": "Cost of goods sold"}
OFF = {f"f{i}": f"c{i}" for i in range(1, 9)}                    # the offered facts: handle -> cell
CTXN = {"truncated": False, "member_rows": 3, "is_scope_filtered": True}
PLAN = [{"claim": "largest_value", "facts": {"fact": "f2"}}, {"claim": "also"}, {"claim": "fell", "facts": {"fact": "f3"}},
        {"claim": "opposite_direction", "facts": {"fact_a": "f3", "fact_b": "f5"}}, {"claim": "scope_note"}]
check("N01 a narrative plan of claims and offered fact handles validates; the model names no member", validate_narrative(PLAN, OFF, cells) == [], validate_narrative(PLAN, OFF, cells))
sent, drop = render_narrative(PLAN, OFF, cells, members, MNAMES, CTXN)
check("N02 code renders every sentence from the catalog with the fact's whole row as the member (both grouped members), measure labels and citation markers; no value",
      sent == ["\u27e6Item group A\u27e7 in \u27e6November 2026\u27e7 has the largest Net revenue [2].",
               "Also, Net revenue fell for \u27e6Item group A\u27e7 in \u27e6November 2026\u27e7 [3].",
               "Net revenue moved in opposite directions for \u27e6Item group A\u27e7 in \u27e6November 2026\u27e7 and \u27e6Item group B\u27e7 in \u27e6November 2026\u27e7 [3] [5].",
               "These figures cover only the records you may see."] and drop == [], sent)
R2 = ["{{m1}} had {{c6}}{{c7}} customers.", "Customers of {{m1}}: {{c6}}.{{c7}}", "Customers of {{m1}}: {{c6}}/{{c7}}", "{{m1}} had {{c6}}k customers.",
      "{{m1}} had {{c6}} mn customers.", "{{m1}} had {{c6}} K customers.", "{{m1}} had minus {{c6}} customers.", "{{m1}} had {{c6}} times {{c6}} customers.",
      "Revenue in {{period}} was {{c1}}.", "{{m1}} ranked {{rank:c2}}.", "{{m1}} {{dir:c3}} by {{abs:c3}}."]
R3 = ["{{m3}} had {{c6}} {{c7}} customers.", "{{m3}} had {{c6}} {{c7}} customers.", "{{m3}} had {{c6}} {{c7}} customers.",
      "{{c6}} point {{c7}}", "{{c6}} to {{c7}}", "{{c6}} – {{c7}}", "{{c6}} E {{c7}}", "{{c6}} grand", "{{c6}} squared", "{{m3}} {{c6}} customers.",
      "more than {{c6}}", "under {{c6}}", "nearly {{c6}}", "{{c6}} customers each day", "{{c6}} customers on average", "{{c6}} dollars", "{{c6}} USD", "{{c6}} nil"]
R3W = ["{{m3}} had 12 500 customers {{ref:c6}}.", "{{m3}} had 12 500 customers {{ref:c6}}.", "Customers {{ref:c6}}: 12 point 500.", "From 12 – 500 {{ref:c6}}.",
       "{{m3}} grew 12 {{ref:c6}}.", "Line 2 12 customers {{ref:c6}}.", "Customers reached twelve {{ref:c6}}.", "A grand total {{ref:c6}}.", "Customers squared {{ref:c6}}.",
       "More than a dozen {{ref:c6}}.", "Nearly all {{ref:c6}}.", "Customers each day {{ref:c6}}.", "On average {{ref:c6}}.", "Several dollars {{ref:c6}}.",
       "In USD {{ref:c6}}.", "Customers were nil {{ref:c6}}.", "Orders in XII {{ref:c6}}.", "Up 12% {{ref:c6}}.", "٣ customers {{ref:c6}}.", "Quarter Ⅲ {{ref:c6}}."]
R4 = ["had 三百 customers [1]", "hai trăm", "deux cents", "had no customers [1]", "a single customer", "{{m1}} dominates sales.", "{{m1}} trails every other group",
      "sales were flat", "tw​o", "twо", "ｔｗｏ"]
PROBES = R2 + R3 + R3W + R4
placements = lambda p: [[{"claim": p}], [{"claim": "largest_value", "facts": {"fact": p}}], [{"claim": "largest_value", "facts": {p: "f2"}}],
                        [{"claim": "largest_value", "facts": {"fact": "f2"}, "members": {"member": p}}], [{"claim": "largest_value", "text": p}], [p]]
check(f"N03 every probe of review rounds 2 to 4 ({len(PROBES)}) is not representable: in any field, as a role or as a member it fails the shape check",
      all(validate_narrative(pl, OFF, cells) for p in PROBES for pl in placements(p)),
      [p for p in PROBES if not all(validate_narrative(pl, OFF, cells) for pl in placements(p))][:3])
rnd_p = random.Random(4)
JUNK = ["had 12 500", "\u4e09\u767e", "two", "tw\u200bo", "IGNORE PREVIOUS", "f2 f3", "{{c1}}", "<b>x</b>", "f99", "m9", "largest value", "x" * 70, "", "\u0663", "Line 2 12"]
VALID = list(CLAIMS["en"]) + list(OFF) + ["fact", "fact_a", "fact_b"]
SHAPES = skeletons(MNAMES)
leaks, accepted, impure = 0, 0, 0
for _ in range(2000):
    def pick():
        return rnd_p.choice(JUNK) if rnd_p.random() < 0.3 else rnd_p.choice(VALID)

    def valid_step():
        cl = rnd_p.choice(list(CLAIMS["en"]))
        st = {"claim": cl}
        if CLAIMS["en"][cl][1]:
            st["facts"] = {r: rnd_p.choice(list(OFF)) for r in CLAIMS["en"][cl][1]}
        return st
    plan = []
    for _ in range(rnd_p.randint(1, 4)):
        st = valid_step()
        r_ = rnd_p.random()
        if r_ < 0.15:
            st["claim"] = pick()
        elif r_ < 0.3 and "facts" in st:
            st["facts"][rnd_p.choice(list(st["facts"]))] = pick()
        elif r_ < 0.4 and "facts" in st:
            st["facts"][pick()] = pick()
        elif r_ < 0.5:
            st[pick()] = pick()
        plan.append(st)
    if validate_narrative(plan, OFF, cells):
        continue
    accepted += 1
    out1, _ = render_narrative(plan, OFF, cells, members, MNAMES, CTXN)
    out2, _ = render_narrative(json.loads(json.dumps(plan)), OFF, cells, members, MNAMES, CTXN)
    impure += out1 != out2
    for sent_ in out1:
        chips = re.findall(r"\u27e6([^\u27e7]*)\u27e7", sent_)
        leaks += skeleton_of(sent_) not in SHAPES or not set(chips) <= set(members.values()) or any(j and j in sent_ for j in JUNK if j not in members.values())
check(f"N04 property test: 2,000 random plans with arbitrary strings in every field; the {accepted} accepted ones render as a pure function, every sentence a catalog shape, and no model string reaches the output except resolved member labels",
      accepted > 50 and leaks == 0 and impure == 0, (accepted, leaks, impure))
CON = {"c": "contrib", "o": "other"}
def contrib_ctx(vals, total, other=None):
    """Contribution member rows A, B, C (and an other row) with a total change."""
    cs = {k: {"kind": "change", "value": str(v), "members": [k], "row_kind": "contribution", "measure": "net_revenue"} for k, v in vals.items()}
    ctx = {"total_change": str(total), "contrib": {k: str(v) for k, v in vals.items()}}
    if other is not None:
        ctx["other"] = str(other)
    return cs, ctx
CA, XA = contrib_ctx({"A": 80, "B": 70, "C": -100}, 50)
pc = lambda cl, k, cs, cx: precondition(cl, {"fact": (k, cs[k])}, cx)[0]
check("N05 contributions with mixed signs (A +80, B +70, C -100, total +50): only A explains most of the change; A, not C, is the largest contributor; C is the largest offset",
      pc("most_of_change", "A", CA, XA) and not pc("most_of_change", "B", CA, XA) and not pc("most_of_change", "C", CA, XA)
      and pc("largest_contributor", "A", CA, XA) and not pc("largest_contributor", "C", CA, XA) and pc("largest_offset", "C", CA, XA) and not pc("largest_offset", "A", CA, XA))
CZ, XZ = contrib_ctx({"A": 80, "B": -80}, 0)
CT, XT = contrib_ctx({"A": 60, "B": 60, "C": -70}, 50)
CO, XO = contrib_ctx({"A": 60, "B": 10}, 120, other=50)
check("N06 a zero total change supports no contribution claim; a tie supports no largest contributor; the other row counts in the half of most_of_change, but never qualifies itself",
      not any(pc(cl, "A", CZ, XZ) for cl in ("largest_contributor", "most_of_change", "largest_offset"))
      and not pc("largest_contributor", "A", CT, XT) and not pc("largest_contributor", "B", CT, XT)
      and not pc("most_of_change", "A", CO, XO) and pc("most_of_change", "A", CO, dict(XO, other="5"))
      and not precondition("largest_contributor", {"fact": ("o", {"kind": "change", "value": "50", "members": [], "row_kind": "other", "measure": "net_revenue"})}, XO)[0])
TIE = mark_extremes({"a": {"kind": "value", "value": "5", "row_kind": "member", "measure": "m", "members": ["m1"]},
                     "b": {"kind": "value", "value": "5", "row_kind": "member", "measure": "m", "members": ["m2"]},
                     "c": {"kind": "value", "value": "2", "row_kind": "member", "measure": "m", "members": ["m3"]},
                     "t": {"kind": "value", "value": "12", "row_kind": "total", "measure": "m", "members": []}})
check("N07 is_max and is_min are set only for a unique extreme of member rows: two equal maxima mark none, the unique minimum is marked, the total row never",
      not TIE["a"]["is_max"] and not TIE["b"]["is_max"] and TIE["c"]["is_min"] and "is_max" not in TIE["t"]
      and cells["c2"]["is_max"] and cells["c4"]["is_min"] and not cells["c8"]["is_max"])
s9, d9 = render_narrative([{"claim": "same_direction", "facts": {"fact_a": "f3", "fact_b": "f7"}}, {"claim": "opposite_direction", "facts": {"fact_a": "f3", "fact_b": "f3"}},
                           {"claim": "same_direction", "facts": {"fact_a": "f3", "fact_b": "f6"}}], OFF, cells, members, MNAMES, CTXN)
check("N08 direction pairs need two distinct facts of the same measure and comparison: net revenue against cost of goods sold is dropped, one fact twice is dropped, a change inside the flat band is dropped",
      s9 == [] and [d["reason"] for d in d9] == ["different measures or comparisons", "not two distinct member changes", "signs do not match the claim"], d9)
s10, d10 = render_narrative([{"claim": "fell", "facts": {"fact": "f5"}}, {"claim": "also"}, {"claim": "rose", "facts": {"fact": "f5"}}, {"claim": "meanwhile"}],
                            OFF, cells, members, MNAMES, CTXN)
s10b, _ = render_narrative([{"claim": "also"}, {"claim": "rose", "facts": {"fact": "f5"}}], OFF, cells, members, MNAMES, CTXN)
check("N09 a connector renders only between two rendered sentences: not after a dropped step, not at the start, not at the end",
      s10 == ["Net revenue rose for \u27e6Item group B\u27e7 in \u27e6November 2026\u27e7 [5]."] and s10b == s10, (s10, s10b))
check("N10 largest and smallest need a complete result with at least two member rows; a total row never qualifies",
      not precondition("largest_value", {"fact": ("c2", cells["c2"])}, dict(CTXN, member_rows=1))[0]
      and not precondition("smallest_value", {"fact": ("c4", cells["c4"])}, dict(CTXN, truncated=True))[0]
      and not precondition("largest_value", {"fact": ("c1", dict(cells["c1"], is_max=True))}, CTXN)[0]
      and precondition("smallest_value", {"fact": ("c4", cells["c4"])}, CTXN)[0])
PINC = {"p1": {"kind": "value", "value": "100.00", "basis": "USD", "scale": 2, "members": ["m5"], "pinned": "m7", "row_kind": "member", "measure": "net_revenue", "is_max": True}}
s11, _ = render_narrative([{"claim": "largest_value", "facts": {"fact": "h"}}], {"h": "p1"}, PINC, members, MNAMES, CTXN)
s12, _ = render_narrative([{"claim": "rose", "facts": {"fact": "h"}}], {"h": "q"}, {"q": {"kind": "change", "value": "5", "base": "1", "members": ["m8"], "row_kind": "member", "measure": "net_revenue"}},
                          members, MNAMES, CTXN)
check("N11 a pinned basis adds the pinned member to the phrase; a label that reads like a claim stays inside its chip as data",
      s11 == ["\u27e6Customer P1\u27e7 within \u27e6USD\u27e7 has the largest Net revenue [1]."] and s12 == ["Net revenue rose for \u27e6Tripled to 500\u27e7 [1]."], (s11, s12))
check("N12 the plan's checks: a non-offered handle, wrong roles, an unknown claim, more than eight steps, a member field, a free-text field",
      validate_narrative([{"claim": "largest_value", "facts": {"fact": "f12"}}], OFF, cells) == ["step0:fact_not_offered"]
      and validate_narrative([{"claim": "largest_value", "facts": {"x": "f2"}}], OFF, cells) == ["step0:roles"]
      and validate_narrative([{"claim": "biggest_ever"}], OFF, cells) == ["step0:unknown_claim"]
      and validate_narrative([{"claim": "also"}] * 9, OFF, cells) == ["narrative_shape"]
      and validate_narrative([{"claim": "largest_value", "facts": {"fact": "f2"}, "members": {"member": "m1"}}], OFF, cells) == ["step0:shape"]
      and validate_narrative([{"claim": "also", "note": "x"}], OFF, cells) == ["step0:shape"])
RES1 = mark_extremes({
    "t": {"kind": "value", "value": "1250000", "members": [], "row_kind": "total", "measure": "net_revenue", "member_keys": {}},
    "tc": {"kind": "contribution", "value": "700000", "members": [], "row_kind": "total", "measure": "net_revenue", "member_keys": {}},
    "a": {"kind": "value", "value": "900000", "members": ["m1", "m6"], "row_kind": "member", "measure": "net_revenue", "member_keys": {"item_group": "IG1", "posting_date": "2026-11-01"}},
    "b": {"kind": "value", "value": "350000", "members": ["m2", "m6"], "row_kind": "member", "measure": "net_revenue", "member_keys": {"item_group": "IG2", "posting_date": "2026-11-01"}},
    "ac": {"kind": "change", "value": "-40000", "base": "940000", "members": ["m1", "m6"], "row_kind": "member", "measure": "net_revenue", "comparison": "P0",
           "member_keys": {"item_group": "IG1", "posting_date": "2026-11-01"}},
    "x": {"kind": "change", "value": "900000", "members": ["m4"], "row_kind": "contribution", "measure": "net_revenue", "member_keys": {"partner": "P3"}},
    "y": {"kind": "change", "value": "-200000", "members": ["m5"], "row_kind": "contribution", "measure": "net_revenue", "member_keys": {"partner": "P1"}}})
RES2 = {k: dict(v) for k, v in RES1.items()}
RES2["a"], RES2["b"] = dict(RES1["b"], value="1200000"), dict(RES1["a"])          # next month: the rows reorder and the largest member changes
RES2 = mark_extremes(RES2)
R = lambda ref, res: resolve_saved(ref, res)
check("N13 saved references resolve by every role (total, total_change, max, min, largest_contribution) and by full coordinate, for a value and for a change",
      R({"role": "total", "measure": "net_revenue"}, RES1) == "t" and R({"role": "total_change", "measure": "net_revenue"}, RES1) == "tc"
      and R({"role": "max", "measure": "net_revenue"}, RES1) == "a" and R({"role": "min", "measure": "net_revenue"}, RES1) == "b"
      and R({"role": "largest_contribution", "measure": "net_revenue"}, RES1) == "x"
      and R({"members": {"item_group": "IG1", "posting_date": "2026-11-01"}, "measure": "net_revenue", "kind": "change"}, RES1) == "ac"
      and R({"members": {"item_group": "IG1", "posting_date": "2026-11-01"}, "measure": "net_revenue", "kind": "value"}, RES1) == "a")
check("N14 saved references refuse what drifts or is ambiguous: first_change and cell positions are not references; a single key of a two-dimension row, or a missing member, resolves to nothing",
      R({"role": "first_change", "measure": "net_revenue"}, RES1) is None and R({"cell": "c2"}, RES1) is None
      and R({"members": {"item_group": "IG1"}, "measure": "net_revenue", "kind": "value"}, RES1) is None
      and R({"members": {"item_group": "IG9", "posting_date": "2026-11-01"}, "measure": "net_revenue", "kind": "value"}, RES1) is None)
SAVED = [{"claim": "largest_value", "facts": {"fact": {"role": "max", "measure": "net_revenue"}}},
         {"claim": "largest_value", "facts": {"fact": {"members": {"item_group": "IG1", "posting_date": "2026-11-01"}, "measure": "net_revenue", "kind": "value"}}},
         {"claim": "fell", "facts": {"fact": {"members": {"item_group": "IG9", "posting_date": "2026-11-01"}, "measure": "net_revenue", "kind": "change"}}}]
o1, d1 = render_saved(SAVED, RES1, members, MNAMES, dict(CTXN, member_rows=2))
o2, d2 = render_saved(SAVED, RES2, members, MNAMES, dict(CTXN, member_rows=2))
check("N15 position drift: a saved plan by role names next month's largest member; by coordinate, its claim is re-checked and dropped once false; an unresolved reference drops its step",
      o1[0].startswith("\u27e6Item group A\u27e7") and o2[0].startswith("\u27e6Item group B\u27e7") and len(o1) == 2 and len(o2) == 1
      and [d["claim"] for d in d2] == ["fell", "largest_value"] and d2[0]["reason"].startswith("reference"), (o1, o2, d2))
check("N16 the key-fact pick: at most five offered handles, none twice",
      validate_pick(["f1", "f2"], OFF) and not validate_pick(["f1", "f1"], OFF) and not validate_pick(["f13"], OFF) and not validate_pick(["f1", "f2", "f3", "f4", "f5", "f6"], OFF))
check("N17 key facts are rendered by code from the templates, with the direction computed from the sign, and the as-of date for a balance",
      key_fact(("change", "c3"), cells, members, MNAMES, a="940000") == "Net revenue for Item group A, November 2026 changed from 940,000 VND to 900,000 VND (-40,000 VND, fell)"
      and key_fact(("total", "c1"), cells, members, MNAMES, period="November 2026") == "Net revenue, total: 1,250,000 VND (November 2026)"
      and key_fact(("value", "cb"), {"cb": {"kind": "value", "value": "7400000", "basis": "VND", "scale": 0, "members": ["m1"], "measure": "ledger_closing_balance"}},
                   members, {"ledger_closing_balance": "Closing balance"}, period="October-November 2026", as_of="2026-11-30") == "Closing balance for Item group A: 7,400,000 VND (as of 2026-11-30)")
check("N18 code's default facts: the total, the largest member on complete results only, and the changes; at most five",
      default_facts(cells) == [("total", "c1"), ("value", "c2"), ("change", "c3"), ("change", "c5"), ("change", "c6")] and ("value", "c2") not in default_facts(cells, truncated=True))
check("N19 a language without a claim catalog and templates gets key facts only, in the company's language or English",
      explanation_language("fr", "fr") == ("en", False) and explanation_language("en", "fr") == ("en", True))
check("N20 the catalog's own texts and measure labels hold no digit, number word or unit word (the CI check)",
      not any(re.search(r"\d", t) for t, *_ in CLAIMS["en"].values()) and not any(re.search(r"\d", v) for v in MNAMES.values()))

# ======================================================================= A: abstention, matching, stated values
check("A01 a valid first plan answers with one call; a repaired plan answers on the second call",
      plan_loop([("plan", [])]) == ("answered", 1) and plan_loop([("plan", ["currency_mixed"]), ("plan", [])]) == ("answered", 2))
check("A02 after three attempts the last code maps to its abstention: currency mixing and time ask for a choice, fan-out is out of coverage",
      plan_loop([("plan", ["currency_mixed"])] * 4) == ("ambiguous_term", 3) and plan_loop([("plan", ["fan_out_refused"])] * 3) == ("out_of_coverage", 3)
      and plan_loop([("plan", ["time_range_invalid"])] * 3) == ("ambiguous_term", 3))
check("A03 not permitted and data not ready are never repaired; timeouts and broad plans ask to narrow",
      plan_loop([("plan", ["analysis_not_permitted"]), ("plan", [])]) == ("not_permitted", 1)
      and plan_loop([("plan", ["analysis_data_not_ready"])]) == ("data_not_ready", 1) and OUTCOME["timeout"] == OUTCOME["analysis_too_broad"] == "too_broad")
check("A04 the planner's own abstentions (clarify, out of coverage, not permitted, ambiguous member) end the loop at once",
      plan_loop([("clarify",)]) == ("ambiguous_term", 1) and plan_loop([("out_of_coverage",)]) == ("out_of_coverage", 1)
      and plan_loop([("not_permitted",)]) == ("not_permitted", 1) and plan_loop([("ambiguous_member",)]) == ("ambiguous_member", 1))
check("A05 every code of rule 10 maps to one of the abstentions; two customers matching one name abstain with their handles",
      set(ORDER) <= set(OUTCOME) and set(OUTCOME.values()) == {"ambiguous_term", "out_of_coverage", "not_permitted", "data_not_ready", "too_broad"}
      and member_outcome(["P1", "P7"]) == ("ambiguous_member", ["m1", "m2"]) and member_outcome(["P1"]) == ("member", "P1"))
VERIFIED = [("Net revenue last month", "PLAN_A"), ("Open receivables by overdue bucket", "PLAN_B")]
check("A06 D2 accepts exact normalized equality only; a superset question (token-set 100) is a hint for L1, never a verified answer",
      match_verified("  net revenue LAST month?? ", VERIFIED) == ("PLAN_A", [])
      and match_verified("Net revenue last month by customer", VERIFIED)[0] is None
      and match_verified("Net revenue last month by customer", VERIFIED)[1][0] == "Net revenue last month"
      and token_set_ratio("net revenue last month by customer", "net revenue last month") == 100)
VIS = [("Margin by customer", "PLAN_P", "private", "u7"), ("Margin by customer", "PLAN_C", "company", "u1"), ("Stock by bin", "PLAN_S", "private", "u7")]
check("A13 D2 and the hints read only the asker's set: company analyses and the asker's own private ones; another user's private analysis is never matched or hinted",
      match_verified("Margin by customer", VIS, asker="u2") == ("PLAN_C", []) and match_verified("Margin by customer", VIS[:1], asker="u7") == ("PLAN_P", [])
      and match_verified("Stock by bin", VIS, asker="u2")[0] is None and "Stock by bin" not in match_verified("Stock by bin", VIS, asker="u2")[1] and "Stock by bin" not in match_verified("Stock by bin please", VIS, asker="u2")[1])
check("A07 normalized questions fold case and whitespace and drop trailing punctuation, keeping letters with diacritics distinct",
      normalize_question("  Net   Revenue LAST month?? ") == "net revenue last month" and normalize_question("Doanh thu?") != normalize_question("Doanh thú?"))
Q = "Net revenue for the last 6 months, top 5 customers"
check("A08 stated values: n and limit must stand in the question; a model-made n, limit or date is invalid output",
      stated_values_ok({"time": {"range": {"relative": "last_n_months", "n": 6}}, "limit": 5}, Q)
      and not stated_values_ok({"time": {"range": {"relative": "last_n_months", "n": 7}}, "limit": 5}, Q)
      and not stated_values_ok({"time": {"range": {"relative": "last_n_months", "n": 6}}, "limit": 10}, Q)
      and not stated_values_ok({"time": {"range": {"from": "2026-01-01", "to": "2026-06-30"}}}, Q))
check("A09 stated dates in ISO form or the company's day/month/year form pass; contributions' top follows the same rule",
      stated_values_ok({"time": {"range": {"from": "2026-07-01", "to": "2026-09-30"}}}, "Revenue from 01/07/2026 to 30/09/2026")
      and stated_values_ok({"time": {"range": {"from": "2026-07-01", "to": "2026-09-30"}}}, "Revenue 2026-07-01 to 2026-09-30")
      and not stated_values_ok({"contributions": {"top": 3}}, "What drove the change?") and stated_values_ok({"contributions": {"top": None}}, "What drove the change?"))

check("A10 named periods and number words pass the stated-value check: 'in March 2026', 'Q1 2026', 'the last three months'; a wrong month or year fails",
      stated_values_ok({"time": {"range": {"month": "2026-03"}}}, "Net revenue in March 2026")
      and stated_values_ok({"time": {"range": {"calendar_quarter": "2026-Q1"}}}, "Net revenue Q1 2026")
      and stated_values_ok({"time": {"range": {"relative": "last_n_months", "n": 3}}}, "Net revenue for the last three months")
      and stated_values_ok({"time": {"range": {"calendar_year": 2025}}}, "Sales in 2025")
      and not stated_values_ok({"time": {"range": {"month": "2026-04"}}}, "Net revenue in March 2026")
      and not stated_values_ok({"time": {"range": {"calendar_quarter": "2025-Q1"}}}, "Net revenue Q1 2026"))
check("A11 an unstated period after the repairs abstains ambiguous_term (period options), never output_invalid",
      plan_loop([("plan", ["period_unstated"])] * 3) == ("ambiguous_term", 3))
check("A12 code decides ambiguous_member: a search text that matched two customers and a plan using one of them ends the run so, whatever the model chose; clarify_member is the model's way",
      code_member_decision({"anh": ["P1", "P7"]}, ["P1"]) == ("ambiguous_member", "anh", ["m1", "m2"]) and code_member_decision({"anh": ["P1"]}, ["P1"]) is None
      and plan_loop([("clarify_member",)]) == ("ambiguous_member", 1))

# ======================================================================= B, G: badge, KPI, caches, grants
v_hash = analysis_plan_hash(P_GOOD1)
check("B01 the badge is verified for the verified plan, and for it with a filter on an open dimension; generated otherwise",
      badge(P_GOOD1, [(v_hash, ["branch"])]) == "verified"
      and badge(dict(P_GOOD1, filters=[{"dimension": "branch", "op": "eq", "values": ["B1"]}]), [(v_hash, ["branch"])]) == "verified"
      and badge(dict(P_GOOD1, filters=[{"dimension": "partner", "op": "eq", "values": ["P1"]}]), [(v_hash, ["branch"])]) == "generated"
      and badge(dict(P_GOOD1, measures=["revenue_deduction"]), [(v_hash, [])]) == "generated")
check("B02 a changed measure definition ends the badge of a verified plan naming it (the hash covers definitions)",
      badge(P_GOOD1, [(v_hash, [])], CAT2) == "generated" and badge(P_GOOD1, [(v_hash, [])], CAT3) == "verified")
check("B03 KPI status by direction: up with target 100, warning 90, critical 80; down mirrored; without thresholds the target splits on track and warning",
      [kpi_status(v, 100, "up", 90, 80) for v in (120, 95, 85, 80, 70)] == ["on_track", "on_track", "warning", "warning", "critical"]
      and [kpi_status(v, 10, "down", 12, 15) for v in (8, 11, 13, 20)] == ["on_track", "on_track", "warning", "critical"]
      and [kpi_status(v, 100, "up") for v in (100, 99)] == ["on_track", "warning"])
u1 = dict(ALL, grants={"journal_line_overview": {"owner": "company"}})
u2 = dict(ALL, grants={"journal_line_overview": {"owner": "own"}})
rh = analysis_resolved_hash(P_GOOD1, CTX)
check("B04 cache keys hold company, user and scope: two companies, two users with equal grants, or one user with another scope never share an entry",
      cache_key("result", "co1", "u1", u1, rh, "1.0.0") != cache_key("result", "co2", "u1", u1, rh, "1.0.0")
      and cache_key("result", "co1", "u1", u1, rh, "1.0.0") != cache_key("result", "co1", "u9", u1, rh, "1.0.0")
      and cache_key("result", "co1", "u1", u1, rh, "1.0.0") != cache_key("result", "co1", "u1", u2, rh, "1.0.0")
      and cache_key("plan", "co1", "u1", u1, "q", "1.0.0") == cache_key("plan", "co1", "u1", dict(u1), "q", "1.0.0"))
GR = {"journal_line_overview": {"owner": "company"}, "sales_line_overview": {"owner": "own", "user": "U2"}}
row_u1 = {"branch": "B1", "created_by": "U1"}
check("G01 per-view grants: the sales view's own scope hides U1's line there, the journal view's company scope shows it, and a view without an entry shows nothing",
      in_scope(row_u1, GR, "journal_line_overview") and not in_scope(row_u1, GR, "sales_line_overview")
      and in_scope({"branch": "B2", "created_by": "U2"}, GR, "sales_line_overview") and not in_scope(row_u1, GR, "stock_overview")
      and not in_scope({"branch": "B2", "created_by": "U1"}, {"journal_line_overview": {"owner": "company", "branches": ["B1"]}}, "journal_line_overview"))
check("G02 member lookup needs the List permission of a fact that offers the dimension",
      lookup_allowed(ALL, "partner", "sales_line_overview") and not lookup_allowed(dict(ALL, facts={"stock_overview"}), "partner", "sales_line_overview")
      and not lookup_allowed(ALL, "partner", "stock_overview"))

# ======================================================================= D: database checks (--load)
if "--load" in sys.argv:
    import psycopg  # noqa: E402
    from psycopg.types.json import Jsonb  # noqa: E402
    from load_all import load_all  # noqa: E402
    dsn = os.environ.get("ERPME_LAB_DSN", "host=127.0.0.1 port=5561 dbname=erpme_lab user=lab")
    n_tables = load_all(dsn, DOCS)
    check("D01 load_all.py loads every DDL file of design/ into one schema, DS-33-analysis.sql included", n_tables > 200, n_tables)
    c = conn(); c.autocommit = True
    X = c.execute
    cols = {}
    for t_, col in X("select table_name, column_name from information_schema.columns where table_schema='erpme'").fetchall():
        cols.setdefault(t_, set()).add(col)
    T4 = ("analysis_question", "saved_analysis", "saved_analysis_version", "analysis_example")
    forced = {r[0] for r in X("select relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='erpme' and relforcerowsecurity")}
    check("D02 the four tables exist with company_id and forced row-level security", all(t_ in cols and "company_id" in cols[t_] and t_ in forced for t_ in T4))

    I = {k: new() for k in ["user", "user2", "co", "b1", "b2", "g1", "p1", "p2", "p3", "ig1", "ig2", "itg", "pr1", "pr2", "i1", "i2", "u",
                            "fy", "fym", "oct", "nov", "spc", "mig"]}
    t = str(I["co"])[-8:]
    X("insert into currency (code, minor_unit) values ('VND', 0), ('USD', 2) on conflict do nothing")
    for k in ("user", "user2"):
        X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I[k], k + "18" + t))
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','lab','lab','company',%s,'en')", (I["co"], "C18-" + t, I["user"]))
    X("select set_config('erpme.company_id', %s, false)", (str(I["co"]),))
    for k, code in (("b1", "B1"), ("b2", "B2")):
        X("insert into branch (id, company_id, code, name) values (%s,%s,%s,%s)", (I[k], I["co"], code, code))
    X("insert into partner_group (id, company_id, code, name, basis) values (%s,%s,'G1','Group 1','{}')", (I["g1"], I["co"]))
    for k, code, grp in (("p1", "P1", "g1"), ("p2", "P2", "g1"), ("p3", "P3", None)):
        X("insert into partner (id, company_id, code, name, partner_kind, country, partner_group_id) values (%s,%s,%s,%s,'organization','US',%s)",
          (I[k], I["co"], code, "Customer " + code, I[grp] if grp else None))
    uom_name = "name" in cols["uom"]
    X(f"insert into uom (id, code, {'name, ' if uom_name else ''}quantity_kind, decimal_places) values (%s,%s,{'%s, ' if uom_name else ''}'count',0)",
      (I["u"], "EA18" + t) + (("Each",) if uom_name else ()))
    X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,'s','S','{}')", (I["itg"], I["co"]))
    for ig, pr, it, code in (("ig1", "pr1", "i1", "A"), ("ig2", "pr2", "i2", "B")):
        X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,%s,%s,'{}')", (I[ig], I["co"], "IG" + code, "Item group " + code))
        X("""insert into product (id, company_id, code, name, product_type, item_group_id, inventory_uom_id, purchase_uom_id, sales_uom_id, item_tax_group_id)
             values (%s,%s,%s,%s,'non_stock',%s,%s,%s,%s,%s)""", (I[pr], I["co"], "PR" + code, "Product " + code, I[ig], I["u"], I["u"], I["u"], I["itg"]))
        X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,%s)", (I[it], I["co"], I[pr], "IT" + code))
    SAX = {}
    for code in ("cash_on_hand", "revenue_goods", "revenue_services", "revenue_deduction_return", "selling_expense", "cost_of_goods_sold",
                 "income_summary", "opening_balance_clearing"):
        SAX[code] = new()
        X("insert into system_account (id, code, control_kind) values (%s,%s,'none')", (SAX[code], code + ":" + t))
    ACC = {}
    for acode, sa in (("CASH", "cash_on_hand"), ("REV-G1", "revenue_goods"), ("REV-G2", "revenue_goods"), ("REV-S", "revenue_services"),
                      ("DED-R", "revenue_deduction_return"), ("SELL", "selling_expense"), ("COGS", "cost_of_goods_sold"), ("ISUM", "income_summary"),
                      ("OBC", "opening_balance_clearing")):
        ACC[acode] = (new(), sa)
        X("insert into account (id, company_id, code, system_account_id) values (%s,%s,%s,%s)", (ACC[acode][0], I["co"], acode, SAX[sa]))
    X("insert into fiscal_year (id, company_id) values (%s,%s), (%s,%s)", (I["fy"], I["co"], I["fym"], I["co"]))
    for k, fy, kind, a, b in (("mig", "fym", "regular", "2026-09-30", "2026-09-30"), ("oct", "fy", "regular", "2026-10-01", "2026-10-31"),
                              ("nov", "fy", "regular", "2026-11-01", "2026-11-30"), ("spc", "fy", "special", "2026-11-30", "2026-11-30")):
        X("insert into posting_period (id, company_id, fiscal_year_id, kind, start_date, end_date) values (%s,%s,%s,%s,%s,%s)", (I[k], I["co"], I[fy], kind, a, b))
        for area in ("general", "inventory", "receivable", "payable"):
            X("insert into posting_period_area_state (posting_period_id, area, state) values (%s,%s,'open')", (I[k], area))
    has_snap = "uom_numerator" in cols["sales_invoice_line"]

    def post(dtype, day, branch, partner, lines, currency="VND", invoice=None, period=None, closing=False, creator="user"):
        """A posted document with its journal entry: lines (account code, side, transaction amount, company amount, item key)."""
        period = I[period] if period else (I["oct"] if day < "2026-11-01" else I["nov"])
        fy = I["fym"] if period == I["mig"] else I["fy"]
        with c.transaction():
            d = new()
            X("""insert into document (id, company_id, document_type, state, version, number, branch_id, partner_id, document_date, created_by_user_id, posted_at, recorded_at)
                 values (%s,%s,%s,'posted',1,%s,%s,%s,%s,%s,%s,%s)""", (d, I["co"], dtype, dtype[:2].upper() + "-" + str(d)[-6:], I[branch], I[partner] if partner else None,
                                                                          day, I[creator], day + "T08:00:00Z", day + "T08:00:00Z"))
            if invoice:
                X("insert into sales_invoice (id, company_id, partner_id, partner_name, currency, document_date, posting_date) values (%s,%s,%s,%s,%s,%s,%s)",
                  (d, I["co"], I[partner], "Customer", currency, day, day))
                for n, (item, qty, amount) in enumerate(invoice, 1):
                    X("""insert into sales_invoice_line (id, company_id, sales_invoice_id, line_number, product_id, item_id, quantity, uom_id, inventory_quantity,
                         net_unit_price, line_amount""" + (", uom_numerator, uom_denominator, uom_factor_source" if has_snap else "") + ")"
                      " values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s" + (",1,1,'identity'" if has_snap else "") + ")",
                      (new(), I["co"], d, n, I["pr1" if item == "i1" else "pr2"], I[item], qty, I["u"], qty, D(amount) / qty, amount))
            e = new()
            X("insert into journal_entry (id, company_id, document_id, posting_date, document_date, posting_period_id, fiscal_year_id, line_count, is_closing_entry)"
              " values (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (e, I["co"], d, day, day, period, fy, len(lines), closing))
            for n, (acode, side, tamt, camt, item) in enumerate(lines, 1):
                aid, sa = ACC[acode]
                X("""insert into journal_line (id, journal_entry_id, company_id, line_number, posting_period_id, account_id, system_account_id, side, transaction_currency,
                     transaction_amount, company_currency, company_amount, branch_id, partner_id, item_id) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'VND',%s,%s,%s,%s)""",
                  (new(), e, I["co"], n, period, aid, SAX[sa], side, currency if acode in ("CASH", "REV-S") else "VND", tamt, camt, I[branch],
                   I[partner] if partner else None, I[item] if item else None))
        return d

    post("general_journal", "2026-09-30", "b1", None, [("CASH", "debit", 1000000, 1000000, None), ("OBC", "credit", -1000000, -1000000, None)], period="mig")
    post("sales_invoice", "2026-10-05", "b1", "p1", [("CASH", "debit", 3000000, 3000000, None), ("REV-G1", "credit", -1000000, -1000000, "i1"), ("REV-G2", "credit", -2000000, -2000000, "i2")],
         invoice=[("i1", 10, 1000000), ("i2", 4, 2000000)])
    post("sales_invoice", "2026-10-20", "b2", "p2", [("CASH", "debit", 500000, 500000, None), ("REV-G1", "credit", -500000, -500000, "i1")], invoice=[("i1", 5, 500000)], creator="user2")
    post("sales_invoice", "2026-11-03", "b1", "p1", [("CASH", "debit", 1200000, 1200000, None), ("REV-G1", "credit", -1200000, -1200000, "i1")], invoice=[("i1", 12, 1200000)])
    post("sales_invoice", "2026-11-10", "b2", "p3", [("CASH", "debit", D("100.00"), 2500000, None), ("REV-S", "credit", D("-100.00"), -2500000, "i2")], currency="USD",
         invoice=[("i2", 1, D("100.00"))])
    post("sales_invoice", "2026-11-15", "b2", "p1", [("CASH", "debit", 700000, 700000, None), ("REV-G2", "credit", -700000, -700000, "i2")], invoice=[("i2", 2, 700000)], creator="user2")
    post("general_journal", "2026-11-18", "b1", "p2", [("DED-R", "debit", 300000, 300000, "i1"), ("CASH", "credit", -300000, -300000, None)])
    post("general_journal", "2026-11-19", "b1", None, [("SELL", "debit", 400000, 400000, None), ("CASH", "credit", -400000, -400000, None)])
    post("general_journal", "2026-11-20", "b1", "p1", [("COGS", "debit", 900000, 900000, "i1"), ("CASH", "credit", -900000, -900000, None)])
    post("general_journal", "2026-11-30", "b1", "p3", [("CASH", "debit", 100000, 100000, None), ("REV-S", "credit", -100000, -100000, "i2")], period="spc")
    # the year's closing entry, in the special period: revenue accounts to the income summary (ADR-0012 rule 18)
    post("general_journal", "2026-11-30", "b1", None, [("REV-G1", "debit", 2700000, 2700000, None), ("REV-G2", "debit", 2700000, 2700000, None),
                                                      ("REV-S", "debit", 2600000, 2600000, None), ("DED-R", "credit", -300000, -300000, None),
                                                      ("ISUM", "credit", -7700000, -7700000, None)], period="spc", closing=True)

    # ---- lab views in schema query (the product declares them in query/views.py; ADR-0060 rule 3)
    def grant_sql(view, branch, owner):
        """is_in_scope from the view's own entry of the per-view grant map (rule 13); one grant per view in the lab."""
        return (f"coalesce((SELECT (NOT (g ? 'branches') OR {branch}::text IN (SELECT jsonb_array_elements_text(g -> 'branches')))"
                f" AND (g ->> 'owner' = 'company' OR {owner}::text = g ->> 'user')"
                f" FROM (SELECT nullif(current_setting('erpme.read_grants', true), '')::jsonb -> '{view}' AS g) s WHERE g IS NOT NULL), false)")
    with c.transaction():
        X("DROP SCHEMA IF EXISTS query CASCADE")
        X("CREATE SCHEMA query")
        X("CREATE TABLE query.lab_system_account (code text PRIMARY KEY, path text NOT NULL, label text NOT NULL)")
        for r in read_csv("system-accounts.csv"):
            X("insert into query.lab_system_account values (%s,%s,%s)", (r["code"], sa_path(r["code"]), r["name"]))
        X("CREATE TABLE query.lab_migration_fiscal_year (id uuid PRIMARY KEY)")   # the migration fiscal years of ADR-0044 rule 2
        X("insert into query.lab_migration_fiscal_year values (%s)", (I["fym"],))
        X("""CREATE VIEW query.posting_period_dimension AS
             SELECT p.id::text AS key, p.kind || ' ' || p.start_date AS label, p.start_date, p.end_date, p.kind, p.fiscal_year_id,
                    row_number() OVER (ORDER BY p.start_date, p.kind) AS seq
             FROM erpme.posting_period p WHERE p.company_id::text = current_setting('erpme.company_id', true)""")
        X(f"""CREATE VIEW query.journal_line_overview WITH (security_barrier) AS
              SELECT jl.id, jl.company_id, je.document_id, d.document_type, d.number AS document_number, je.posting_date, jl.posting_period_id, pd.seq AS period_seq,
                     split_part(sa.code, ':', 1) AS system_account_code, lsa.path AS system_account_path, jl.account_id, jl.partner_id, p.partner_group_id,
                     jl.salesperson_id, jl.item_id, it.product_id, pr.item_group_id, jl.warehouse_id, jl.branch_id, jl.cost_center_id, jl.project_id,
                     jl.transaction_currency, jl.side, jl.company_amount, jl.transaction_amount, 'journal_line'::text AS row_source,
                     je.is_closing_entry, (je.fiscal_year_id IN (SELECT id FROM query.lab_migration_fiscal_year)) AS is_migration_entry,
                     (pd.kind = 'special') AS is_special_period, d.created_by_user_id,
                     {grant_sql('journal_line_overview', 'jl.branch_id', 'd.created_by_user_id')} AS is_in_scope
              FROM erpme.journal_line jl JOIN erpme.journal_entry je ON je.id = jl.journal_entry_id JOIN erpme.document d ON d.id = je.document_id
              JOIN query.posting_period_dimension pd ON pd.key = jl.posting_period_id::text
              JOIN erpme.system_account sa ON sa.id = jl.system_account_id JOIN query.lab_system_account lsa ON lsa.code = split_part(sa.code, ':', 1)
              LEFT JOIN erpme.partner p ON p.id = jl.partner_id LEFT JOIN erpme.item it ON it.id = jl.item_id LEFT JOIN erpme.product pr ON pr.id = it.product_id
              WHERE d.state IN ('posted', 'reversed') AND jl.company_id::text = current_setting('erpme.company_id', true)
              UNION ALL   -- opening_turnover rows (ADR-0049 rule 14; ADR-0060 rule 3): no document, owner or branch
              SELECT ot.id, ot.company_id, NULL::uuid, NULL::text, NULL::text, ot.end_date, NULL::uuid, NULL::bigint,
                     split_part(sa.code, ':', 1), lsa.path, ot.account_id, NULL::uuid, NULL::uuid, NULL::uuid, NULL::uuid, NULL::uuid, NULL::uuid, NULL::uuid,
                     NULL::uuid, NULL::uuid, NULL::uuid, NULL::text, NULL::text, ot.company_debit_turnover - ot.company_credit_turnover,
                     ot.company_debit_turnover - ot.company_credit_turnover, 'opening_turnover'::text, false, false, false, NULL::uuid,
                     coalesce((SELECT g ->> 'owner' = 'company' AND NOT (g ? 'branches')
                               FROM (SELECT nullif(current_setting('erpme.read_grants', true), '')::jsonb -> 'journal_line_overview' AS g) s WHERE g IS NOT NULL), false)
              FROM erpme.opening_turnover ot JOIN erpme.account a ON a.id = ot.account_id JOIN erpme.system_account sa ON sa.id = a.system_account_id
              JOIN query.lab_system_account lsa ON lsa.code = split_part(sa.code, ':', 1)
              WHERE ot.company_id::text = current_setting('erpme.company_id', true)""")
        X(f"""CREATE VIEW query.sales_line_overview WITH (security_barrier) AS
              SELECT l.id, l.company_id, d.id AS document_id, d.document_type, si.posting_date, si.document_date, si.partner_id, p.partner_group_id,
                     si.salesperson_id, l.item_id, l.product_id, pr.item_group_id, d.branch_id, si.currency AS transaction_currency,
                     l.line_amount AS signed_line_amount, l.inventory_quantity AS signed_inventory_quantity,
                     {grant_sql('sales_line_overview', 'd.branch_id', 'd.created_by_user_id')} AS is_in_scope
              FROM erpme.sales_invoice_line l JOIN erpme.sales_invoice si ON si.id = l.sales_invoice_id JOIN erpme.document d ON d.id = si.id
              JOIN erpme.partner p ON p.id = si.partner_id JOIN erpme.product pr ON pr.id = l.product_id
              WHERE d.state IN ('posted', 'reversed') AND l.company_id::text = current_setting('erpme.company_id', true)""")
        X(f"""CREATE VIEW query.system_account_turnover WITH (security_barrier) AS
              WITH t AS (SELECT jl.company_id, jl.posting_period_id, pd.end_date AS period_end, pd.seq AS period_seq, pd.fiscal_year_id,
                                (pd.kind = 'special') AS is_special_period, split_part(sa.code, ':', 1) AS system_account_code,
                                lsa.path AS system_account_path, jl.branch_id, jl.cost_center_id, jl.project_id, jl.transaction_currency,
                                sum(jl.company_amount) AS company_net_turnover
                         FROM erpme.journal_line jl JOIN erpme.journal_entry je ON je.id = jl.journal_entry_id JOIN erpme.document d ON d.id = je.document_id
                         JOIN query.posting_period_dimension pd ON pd.key = jl.posting_period_id::text
                         JOIN erpme.system_account sa ON sa.id = jl.system_account_id JOIN query.lab_system_account lsa ON lsa.code = split_part(sa.code, ':', 1)
                         WHERE d.state IN ('posted', 'reversed') AND jl.company_id::text = current_setting('erpme.company_id', true)
                         GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
              SELECT t.*, sum(company_net_turnover) OVER (PARTITION BY system_account_code, branch_id, cost_center_id, project_id, transaction_currency
                                                         ORDER BY period_seq) AS company_closing_balance,
                     {grant_sql('system_account_turnover', 't.branch_id', 'NULL')} AS is_in_scope FROM t""")
        X("CREATE VIEW query.partner_dimension AS SELECT id::text AS key, name AS label FROM erpme.partner")
        X("CREATE VIEW query.item_group_dimension AS SELECT id::text AS key, name AS label FROM erpme.item_group")
        X("CREATE VIEW query.system_account_dimension AS SELECT code AS key, label, path FROM query.lab_system_account")

    X("insert into opening_turnover (id, company_id, account_id, start_date, end_date, company_debit_turnover, company_credit_turnover) values (%s,%s,%s,'2026-04-01','2026-09-30',0,5000000)",
      (new(), I["co"], ACC["REV-G1"][0]))
    LCTX = dict(CTX, business_date=date(2026, 11, 30), cutover=date(2026, 10, 1), opening_turnover=[(date(2026, 4, 1), date(2026, 9, 30))], members={"branch": {str(I["b1"]), str(I["b2"])}, "partner": {str(I[k]) for k in ("p1", "p2", "p3")}},
                member_count=dict(CTX["member_count"]))
    RNG = {"dimension": "posting_date", "range": {"from": "2026-10-01", "to": "2026-11-30"}}
    VIEWS = ("journal_line_overview", "sales_line_overview", "system_account_turnover")
    FULL = {v: {"owner": "company"} for v in VIEWS}

    def tx(grants):
        X("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        X("select set_config('erpme.read_grants', %s, true)", (jdump(grants),))

    def run(plan, grants=None):
        sql, params, meta = compile_plan(plan, LCTX)
        with c.transaction():
            tx(grants or FULL)
            rows = X(sql, params).fetchall()
        return rows, meta

    def drill(plan, cell, measure, top_keys=None, grants=None):
        sql, params, kind = compile_cell_rows(plan, LCTX, cell, measure, top_keys)
        with c.transaction():
            tx(grants or FULL)
            rows = X(sql, params).fetchall()
        return (sum((r[2] for r in rows), D(0)) if kind == "sum" else len({r[2] for r in rows})), rows

    def report_change(subtree, frm, to, closing_exclude, special=True, accounts_only=False):
        """ADR-0049 rule 6's change measure, computed apart from the analysis layer: operational accounts mapped to the subtree, migration
        entries out, closing entries out when asked, special periods per the option; grouped by operational account when asked."""
        rows = X("""select a.code, sum(jl.company_amount) from journal_line jl join journal_entry je on je.id = jl.journal_entry_id
                    join account a on a.id = jl.account_id join system_account sa on sa.id = a.system_account_id join posting_period pp on pp.id = jl.posting_period_id
                    where jl.company_id = %s and je.posting_date between %s and %s and je.fiscal_year_id <> %s
                      and (not %s or not je.is_closing_entry) and (%s or pp.kind <> 'special')
                      and ('/' || (select path from query.lab_system_account where code = split_part(sa.code, ':', 1)) || '/') like %s
                    group by a.code""", (I["co"], frm, to, I["fym"], closing_exclude, special, f"%/{subtree}/%")).fetchall()
        return rows if accounts_only else sum((r[1] for r in rows), D(0))

    # ---- P1: net revenue by item group and month, with totals; drills; management total = ADR-0049 turnover
    P1 = {"plan_version": 1, "measures": ["net_revenue"], "dimensions": [{"dimension": "item_group"}, {"dimension": "posting_date", "grain": "month"}],
          "time": RNG, "with_total_row": True}
    check("D03 plan 1 (net revenue by item group and month) validates on the loaded catalog", validate(P1, ALL, LCTX) == [], validate(P1, ALL, LCTX))
    r1, _ = run(P1)
    members1 = [r for r in r1 if r[0] == "member"]
    total1 = [r for r in r1 if r[0] == "total"][0]
    drills = [(r, drill(P1, {"item_group": r[1], "posting_date": r[2]}, "net_revenue")[0]) for r in members1]
    check(f"D04 plan 1: each of its {len(members1)} cells equals the sum of its drill rows (INV-410)", members1 and all(r[3] == s for r, s in drills),
          [(r[1][-4:], r[2], r[3], s) for r, s in drills])
    by_acc = report_change("revenue", "2026-10-01", "2026-11-30", True, accounts_only=True)
    check("D05 management total: net revenue (7,700,000) equals ADR-0049's change with closing_entries=exclude over the operational accounts of the revenue subtree, the closing entry left out (INV-411)",
          total1[3] == -report_change("revenue", "2026-10-01", "2026-11-30", True) == -sum(v for _, v in by_acc) == D(7700000), (total1[3], by_acc))
    r1s, _ = run(dict(P1, time=dict(RNG, special_periods="exclude")))
    check("D06 special_periods exclude leaves the special-period adjustment out on both sides (7,600,000)",
          [r[3] for r in r1s if r[0] == "total"][0] == -report_change("revenue", "2026-10-01", "2026-11-30", True, special=False) == D(7600000))
    P1T = {"plan_version": 1, "measures": ["ledger_net_turnover"], "filters": [{"dimension": "system_account", "op": "in_subtree", "values": ["revenue"]}], "time": RNG}
    r1t, _ = run(P1T)
    check("D07 the ledger turnover measure keeps the closing entry, as ADR-0049's change without the option: the revenue subtree nets to zero over the closed year",
          validate(P1T, ALL, LCTX) == [] and r1t[0][1] == report_change("revenue", "2026-10-01", "2026-11-30", False) == 0, r1t)
    P1C = {"plan_version": 1, "measures": ["ledger_net_turnover"], "filters": [{"dimension": "system_account", "op": "in_subtree", "values": ["cash"]}], "time": RNG}
    check("D08 migration entries never count in turnover: cash turnover over the range is 6,400,000 without the opening of 1,000,000 (posted in the migration year)",
          run(P1C)[0][0][1] == report_change("cash", "2026-09-30", "2026-11-30", False) == D(6400000))
    check("D09 the November deduction reduces item group A's November cell (1,200,000 less 300,000); the special-period adjustment falls in November for item group B; labels come from the label view",
          any(r[2] == "2026-11-01" and r[3] == D(900000) and r[4] == "Item group A" for r in members1)
          and any(r[2] == "2026-11-01" and r[3] == D(3300000) and r[4] == "Item group B" for r in members1), [(r[2], r[3], r[4]) for r in members1])
    GB1 = {**FULL, "journal_line_overview": {"owner": "company", "branches": [str(I["b1"])]}}
    tb = [r for r in run(P1, GB1)[0] if r[0] == "total"][0]
    check("D10 a branch scope on the journal view: totals of in-scope rows only (4,000,000 for B1) and the scope flag set; full scope leaves it unset",
          tb[3] == D(4000000) and tb[-2] is True and total1[-2] is False, (tb[3], tb[-2], total1[-2]))
    _, rows_scoped = drill(P1, {"item_group": str(I["ig1"]), "posting_date": "2026-10-01"}, "net_revenue",
                           grants={**FULL, "journal_line_overview": {"owner": "company", "branches": [str(I["b2"])]}})
    check("D11 drill rows follow the scope too: item group A in October under branch B2 lists only B2's journal line", len(rows_scoped) == 1 and rows_scoped[0][2] == D(500000), rows_scoped)
    # ---- P2: transaction-currency amounts by currency and top customer with the other row: per-currency subtotals, no grand total
    P2 = {"plan_version": 1, "measures": ["sales_line_amount"], "dimensions": [{"dimension": "currency"}, {"dimension": "partner"}], "time": RNG,
          "limit": 1, "with_other_row": True, "with_total_row": True}
    check("D12 plan 2 validates; without the currency dimension it is refused with currency_mixed",
          validate(P2, ALL, LCTX) == [] and validate(dict(P2, dimensions=[{"dimension": "partner"}]), ALL, LCTX)[0][0] == "currency_mixed")
    r2, _ = run(P2)
    m2_ = [r for r in r2 if r[0] == "member"]
    subs = {r[1]: r[3] for r in r2 if r[0] == "subtotal"}
    check("D13 plan 2: one subtotal per currency (VND 5,400,000; USD 100.00) and no grand total: VND and USD never add up (INV-412)",
          subs == {"VND": D(5400000), "USD": D("100.00")} and not [r for r in r2 if r[0] == "total"], (subs, [r[0] for r in r2]))
    ok2 = []
    for r in m2_:
        keys = [x[2] for x in m2_ if x[1] == r[1] and x[2] != "~other"]
        s, _ = drill(P2, {"currency": r[1], "partner": r[2]}, "sales_line_amount", top_keys=keys)
        ok2.append((r[1], r[2][-4:], r[3], s, r[3] == s))
    check("D14 plan 2: every cell, the other row included, equals the sum of its drill rows; ranks are per currency (P1 tops VND, P2 in the VND other row, P3 alone in USD)",
          ok2 and all(x[-1] for x in ok2) and (D(500000) in [r[3] for r in m2_ if r[1] == "VND" and r[2] == "~other"])
          and [(r[2], r[3]) for r in m2_ if r[1] == "USD"] == [(str(I["p3"]), D("100.00"))], ok2)
    # ---- P3: distinct customers by branch
    P3 = {"plan_version": 1, "measures": ["sales_customer_count"], "dimensions": [{"dimension": "branch"}], "time": RNG, "with_total_row": True}
    r3, _ = run(P3)
    cells3 = {r[1]: r[2] for r in r3 if r[0] == "member"}
    tot3 = [r[2] for r in r3 if r[0] == "total"][0]
    check("D15 plan 3: customers per branch (B1: 1, B2: 3) total 3, not 4: P1 bought in both, and the total is recomputed from rows (INV-412)",
          cells3 == {str(I["b1"]): 1, str(I["b2"]): 3} and tot3 == 3, (cells3, tot3))
    check("D16 plan 3: a distinct-count cell equals the number of distinct keys among its drill rows", drill(P3, {"branch": str(I["b2"])}, "sales_customer_count")[0] == 3)
    # ---- contributions, with drills
    PC = {"plan_version": 1, "measures": ["net_revenue"], "time": {"dimension": "posting_date", "range": {"from": "2026-11-01", "to": "2026-11-30"}, "compare": {"relative": "previous_period"}},
          "contributions": {"measure": "net_revenue", "dimension": "partner", "top": 1}}
    check("D17 the contribution plan validates", validate(PC, ALL, LCTX) == [], validate(PC, ALL, LCTX))
    sql, params, _ = compile_plan(PC, LCTX)
    with c.transaction():
        tx(FULL)
        rc = X(sql, params).fetchall()
    jd = -report_change("revenue", "2026-11-01", "2026-11-30", True) + report_change("revenue", "2026-10-01", "2026-10-31", True)
    kinds = {r[0]: r for r in rc}
    check("D18 contributions: the total change equals ADR-0049's change between the months (+700,000), member plus other equals it, and the reconciliation row is zero",
          kinds["total"][2] == jd == D(700000) and kinds["reconciliation"][2] == 0 and kinds["member"][2] + kinds["other"][2] == jd, rc)
    s_m, _ = drill(PC, {"partner": kinds["member"][1]}, "net_revenue")
    s_o, _ = drill(PC, {"partner": "~other"}, "net_revenue", top_keys=[kinds["member"][1]])
    check("D19 contribution rows drill to their rows, November signed and October negated: P3's +2,600,000 and the other row's -1,900,000 (INV-410)",
          kinds["member"][1] == str(I["p3"]) and s_m == kinds["member"][2] == D(2600000) and s_o == kinds["other"][2] == D(-1900000), (s_m, s_o))
    # ---- difference drill and field classes
    PG = {"plan_version": 1, "measures": ["gross_profit"], "dimensions": [{"dimension": "item_group"}], "time": RNG, "with_total_row": True}
    rg, _ = run(PG)
    ga = [r for r in rg if r[0] == "member" and r[1] == str(I["ig1"])][0]
    check("D20 gross profit of item group A (2,400,000 net revenue less 900,000 cost of goods sold) equals its drill rows, the signed union of both measures' rows",
          ga[2] == D(1500000) == drill(PG, {"item_group": str(I["ig1"])}, "gross_profit")[0] and validate(PG, dict(ALL, classes={"cost"}), LCTX)[0][0] == "analysis_not_permitted", ga)
    # ---- two facts, two owner scopes; member lookup
    P5 = {"plan_version": 1, "measures": ["net_revenue", "sales_customer_count"], "dimensions": [{"dimension": "item_group"}], "time": RNG, "with_total_row": True}
    GOWN = {"journal_line_overview": {"owner": "company"}, "sales_line_overview": {"owner": "own", "user": str(I["user2"])}}
    r5f, _ = run(P5)
    r5o, _ = run(P5, GOWN)
    check("D21 two facts under one company scope: totals 7,700,000 and 3 customers",
          [r[2:4] for r in r5f if r[0] == "total"] == [(D(7700000), 3)], r5f)
    check("D22 two facts under two owner scopes: the journal view keeps company scope (7,700,000) while the sales view's own scope counts only the clerk's two customers, and the flag is set",
          [r[2:4] for r in r5o if r[0] == "total"] == [(D(7700000), 2)] and all(r[-2] is True for r in r5o), r5o)

    def lookup(dim, fact, text, grants):
        col = DIMS[dim]["column"]
        with c.transaction():
            tx(grants)
            return {r[1] for r in X(f"SELECT DISTINCT l.key, l.label FROM query.{fact} f JOIN query.{LABEL_VIEWS[dim]} l ON l.key = f.{col}::text"
                                   " WHERE f.is_in_scope AND l.label ILIKE %s", (f"%{text}%",)).fetchall()}
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,'P4','Customer P4','organization','US')", (new(), I["co"]))

    def lookup_master(dim, fact, text, grants, master_permission=True):
        """Rule 14: a caller with a company-wide grant on the fact and the List permission of the dimension's master data also finds members without rows."""
        g = grants.get(fact) or {}
        if g.get("owner") == "company" and "branches" not in g and master_permission:
            with c.transaction():
                tx(grants)
                return {r[0] for r in X(f"SELECT l.label FROM query.{LABEL_VIEWS[dim]} l WHERE l.label ILIKE %s", (f"%{text}%",)).fetchall()}
        return lookup(dim, fact, text, grants)
    check("D23b a new customer without rows: found by a company-wide caller holding the partner master data permission; not without that permission, not by the clerk, not with record scope",
          "Customer P4" in lookup_master("partner", "sales_line_overview", "customer", FULL)
          and "Customer P4" not in lookup_master("partner", "sales_line_overview", "customer", GOWN)
          and "Customer P4" not in lookup_master("partner", "sales_line_overview", "customer", FULL, master_permission=False)
          and "Customer P4" not in lookup_master("partner", "sales_line_overview", "customer", {"sales_line_overview": {"owner": "company", "branches": [str(I["b1"]), str(I["b2"])]}}))
    check("D23 member lookup returns only members of the fact's rows within its scope: the clerk finds two customers, the full scope three, a view without a grant none",
          lookup("partner", "sales_line_overview", "customer", GOWN) == {"Customer P1", "Customer P2"}
          and lookup("partner", "sales_line_overview", "customer", FULL) == {"Customer P1", "Customer P2", "Customer P3"}
          and lookup("partner", "sales_line_overview", "customer", {"journal_line_overview": {"owner": "company"}}) == set())
    # ---- balances: one as-of value, and per bucket carried forward
    P6 = {"plan_version": 1, "measures": ["ledger_closing_balance"], "filters": [{"dimension": "system_account", "op": "in_subtree", "values": ["cash"]}],
          "time": {"dimension": "posting_period", "range": {"from": "2026-10-01", "to": "2026-11-30"}}}
    r6, _ = run(P6)
    check("D24 the cash closing balance at the end of the range holds the migration opening (1,000,000 plus 6,400,000 of movements): balances keep migration entries",
          validate(P6, ALL, LCTX) == [] and r6[0][1] == D(7400000), r6)
    P7 = {"plan_version": 1, "measures": ["ledger_closing_balance"], "dimensions": [{"dimension": "posting_period", "grain": "posting_period"}],
          "filters": [{"dimension": "system_account", "op": "in_subtree", "values": ["revenue"]}],
          "time": {"dimension": "posting_period", "range": {"from": "2026-10-01", "to": "2026-11-30"}}, "with_total_row": True}
    r7, _ = run(P7)
    b7 = [(r[3], r[2]) for r in r7 if r[0] == "member"]
    check("D25 the revenue closing balance per period, carried forward: October -3,500,000, November -7,600,000, the special period 0 after closing (the USD key with no row there carried); total = last bucket",
          validate(P7, ALL, LCTX) == [] and b7 == [(2, D(-3500000)), (3, D(-7600000)), (4, D(0))] and [r[2] for r in r7 if r[0] == "total"] == [D(0)], r7)
    ok7 = []
    for seq, val in b7:
        sql, params = compile_balance_rows(P7, LCTX, seq, 2)
        with c.transaction():
            tx(FULL)
            ok7.append(sum((r[2] for r in X(sql, params).fetchall()), D(0)) == val)
    check("D26 each balance cell equals its opening row plus the journal lines of the range up to its bucket (INV-410, as ADR-0049's books)", all(ok7) and len(ok7) == 3, ok7)
    P7X = dict(P7, time=dict(P7["time"], special_periods="exclude"))
    r7x, _ = run(P7X)
    check("D30a special_periods exclude on the balance: the special-period bucket disappears and the year-end balance is taken before it (-7,600,000), as ADR-0049 rule 13",
          [(r[3], r[2]) for r in r7x if r[0] == "member"] == [(2, D(-3500000)), (3, D(-7600000))] and [r[2] for r in r7x if r[0] == "total"] == [D(-7600000)], r7x)
    P7B = dict(P7, dimensions=[{"dimension": "posting_period", "grain": "posting_period"}, {"dimension": "branch"}])
    r7b, _ = run(P7B)
    cell = {(r[4], r[2]): r[3] for r in r7b if r[0] == "member"}
    check("D30b a balance by period and branch carries per group: branch B2 has no row in the special period and keeps -3,700,000 there; each bucket's groups sum to the bucket of D25",
          validate(P7B, ALL, LCTX) == [] and cell.get((4, str(I["b2"]))) == D(-3700000) and cell.get((4, str(I["b1"]))) == D(3700000)
          and all(sum(v for (sq, _), v in cell.items() if sq == seq) == val for seq, val in b7), r7b)
    r7f, _ = run(dict(P7, dimensions=[{"dimension": "posting_period", "grain": "fiscal_year"}]))
    r7fx, _ = run(dict(P7X, dimensions=[{"dimension": "posting_period", "grain": "fiscal_year"}]))
    check("D30c the fiscal-year bucket ends after its special period (0 after closing); with special periods excluded it ends at November (-7,600,000)",
          [r[2] for r in r7f if r[0] == "member"] == [D(0)] and [r[2] for r in r7fx if r[0] == "member"] == [D(-7600000)], (r7f, r7fx))
    P7M = dict(P7, measures=["ledger_closing_balance", "ledger_net_turnover"])
    r7m, _ = run(P7M)
    by_p = {r[1]: (r[2], r[3]) for r in r7m if r[0] == "member"}
    check("D30g closing balance and movement by period, two facts: the balance carries per bucket (-3,500,000; -7,600,000; 0) beside the turnover (-3,500,000; -4,100,000; +7,600,000); totals: last bucket 0 and sum 0",
          validate(P7M, ALL, LCTX) == [] and by_p == {str(I["oct"]): (D(-3500000), D(-3500000)), str(I["nov"]): (D(-7600000), D(-4100000)), str(I["spc"]): (D(0), D(7600000))}
          and [(r[2], r[3]) for r in r7m if r[0] == "total"] == [(D(0), D(0))], r7m)
    PO = {"plan_version": 1, "measures": ["net_revenue"], "dimensions": [{"dimension": "posting_date", "grain": "month"}],
          "time": {"dimension": "posting_date", "range": {"from": "2026-04-01", "to": "2026-11-30"}}, "with_total_row": True}
    ro, _ = run(PO)
    rob, _ = run(PO, {**FULL, "journal_line_overview": {"owner": "company", "branches": [str(I["b1"]), str(I["b2"])]}})
    check("D30d opening turnover: a fiscal year to date across the cut-over shows the 5,000,000 before the cut-over as its own member ~opening, never in October, inside the total of 12,700,000",
          validate(PO, ALL, LCTX) == [] and [(r[1], r[2]) for r in ro if r[0] == "member"] == [("2026-10-01", D(3500000)), ("2026-11-01", D(4200000)), ("~opening", D(5000000))]
          and [r[2] for r in ro if r[0] == "total"] == [D(12700000)], ro)
    check("D30e opening turnover rows have no owner or branch: a grant with record scope leaves them out (total 7,700,000, no ~opening) and sets the scope flag",
          [r[1] for r in rob if r[0] == "member"] == ["2026-10-01", "2026-11-01"] and [r[2] for r in rob if r[0] == "total"] == [D(7700000)] and rob[0][-2] is True, rob)
    rs, _ = run({"plan_version": 1, "measures": ["sales_line_amount"], "dimensions": [{"dimension": "currency"}], "time": RNG, "with_total_row": True})
    check("D30f a basis pinned by the only grouped dimension: one row per currency, no subtotal duplicates and no grand total",
          [(r[0], r[1]) for r in rs] == [("member", "USD"), ("member", "VND")], rs)
    # ---- truncation
    PT = {"plan_version": 1, "measures": ["net_revenue"], "dimensions": [{"dimension": "item_group"}], "time": RNG, "limit": 1, "with_total_row": True}
    rt, _ = run(PT)
    check("D27 a limit without the other row: one member row (item group B, 5,300,000), the total still 7,700,000, and is_truncated set",
          [(r[1], r[2]) for r in rt if r[0] == "member"] == [(str(I["ig2"]), D(5300000))] and [r[2] for r in rt if r[0] == "total"] == [D(7700000)]
          and all(r[-1] is True for r in rt), rt)
    # ---- statements
    stmts = [compile_plan(p, LCTX)[0] for p in (P1, P2, P3, PC, P5, P6, P7, PT)]
    okp = []
    for i, s in enumerate(stmts):
        try:
            with c.transaction():
                X(f"PREPARE lab_an_{i} AS {re.sub('%s', lambda m, n=iter(range(1, 999)): '$' + str(next(n)), s)}")
                X(f"DEALLOCATE lab_an_{i}")
            okp.append(True)
        except psycopg.Error as e:
            okp.append(str(e).splitlines()[0])
    check("D28 each compiled statement prepares as a single statement (PREPARE refuses more than one)", all(x is True for x in okp), okp)
    with c.transaction():
        tx(FULL)
        plan_json = X("EXPLAIN (FORMAT JSON) " + compile_plan(P1, LCTX)[0], compile_plan(P1, LCTX)[1]).fetchone()[0][0]["Plan"]
    est, out_rows = scan_rows(plan_json), plan_json["Plan Rows"]
    check("D29 the cost guard reads the planner's scan-node rows (EXPLAIN, no ANALYZE), more than the plan's output rows", est >= 1 and est >= out_rows, (est, out_rows))

    # ---- agent runs complete with each analysis outcome (ck_agent_run_outcome, DS-05-platform.sql)
    def run_row(cx, outcome, state="completed"):
        cx.execute("select set_config('erpme.company_id', %s, true)", (str(I["co"]),))
        cx.execute("""insert into agent_run (id, company_id, agent_type_code, agent_type_version, seatmap_hash, mode, trigger_kind, started_by_kind, on_behalf_of_id,
                      scope_kind, subject_table, subject_id, budget, state, outcome, started_at, ended_at, recorded_at)
                      values (%s,%s,'analysis','1.0.0',%s,'evaluation','person','human',%s,'subject','analysis_question',%s,'{}',%s,%s,now(),now(),now())""",
                   (new(), I["co"], "0" * 64, I["user"], new(), state, outcome))
    X("insert into agent_type (id, code, name, recorded_at) values (%s,'analysis','Analysis',now())", (new(),))
    X("""insert into agent_type_version (id, agent_type_code, version, content_hash, behavior_hash, declaration, field_classes, recorded_at)
         values (%s,'analysis','1.0.0',%s,%s,%s,'{cost,margin}',now())""",
      (new(), "1" * 64, "2" * 64, Jsonb({"scope_kind": "subject", "subject_tables": ["analysis_question", "analysis_example"], "may_read_untrusted": False})))
    for oc in ("answered", "ambiguous_term", "ambiguous_member", "out_of_coverage", "not_permitted", "data_not_ready", "too_broad"):
        expect(f"D30 an analysis run completes with outcome {oc}", lambda cx, oc=oc: run_row(cx, oc), False)
    expect("D31 an outcome outside the table is still refused", lambda cx: run_row(cx, "answered_badly"), True, "ck_agent_run_outcome")
    expect("D32 the analysis outcomes belong to state completed only, not stopped", lambda cx: run_row(cx, "answered", "stopped"), True, "ck_agent_run_outcome")

    # ---- the tables' checks and guards
    def ins(cx, table, **v):
        cx.execute("select set_config('erpme.company_id', %s, true)", (str(I["co"]),))
        cx.execute(f"insert into {table} ({', '.join(v)}) values ({', '.join(['%s'] * len(v))})", [Jsonb(x) if isinstance(x, (dict, list)) else x for x in v.values()])
        return v.get("id")
    H = "a" * 64
    Q_ = dict(company_id=I["co"], asked_by_user_id=I["user"], question_text="Net revenue by item group last month", language="en", asked_at="2026-11-30T08:00:00Z",
              recorded_at="2026-11-30T08:00:00Z")
    ANS = dict(state="answered", outcome="answered", plan={"plan_version": 1}, analysis_plan_hash=H, analysis_resolved_hash=H, catalog_version="0.1.0", badge="generated",
               result={"rows": []}, key_facts={"facts": [{"template": "total", "cell": "c1"}]}, narrative_plan=[{"claim": "largest_value", "facts": {"fact": "f2"}}], as_of="2026-11-30T08:00:01Z", answered_at="2026-11-30T08:00:02Z")
    QA = new()
    expect("D33 an answered question with plan, badge, result and a placeholder-only narration is accepted",
           lambda cx: ins(cx, "analysis_question", id=QA, **Q_, **ANS), False)
    expect("D34 a narrative plan holding free text is refused: every string is a short identifier (INV-413 in the row)",
           lambda cx: ins(cx, "analysis_question", id=new(), **Q_, **dict(ANS, narrative_plan=[{"claim": "largest_value", "facts": {"fact": "had 12 500 customers"}}])),
           True, "ck_analysis_question_narrative_plan")
    expect("D34b a narrative step with a field beyond claim, facts and members is refused",
           lambda cx: ins(cx, "analysis_question", id=new(), **Q_, **dict(ANS, narrative_plan=[{"claim": "also", "text": "Sales doubled"}])), True, "ck_analysis_question_narrative_plan")
    for nm, bad_plan_ in (("a role key holding free text", [{"claim": "largest_value", "facts": {"Revenue tripled to 500!": "f1"}}]),
                          ("a numeric claim with an array of numbers", [{"claim": 12500, "facts": [500, 3.5]}]),
                          ("free-text keys nested under members", [{"claim": "rose", "facts": {"fact": {"members": {"Item group tripled!": "k"}, "measure": "net_revenue", "kind": "change"}}}]),
                          ("a member handle at step level", [{"claim": "largest_value", "facts": {"fact": "f2"}, "members": {"member": "m1"}}])):
        expect(f"D34x the round-5 bypass refused on the question row: {nm}",
               lambda cx, bp=bad_plan_: ins(cx, "analysis_question", id=new(), **Q_, **dict(ANS, narrative_plan=bp)), True, "ck_analysis_question_narrative_plan")
    expect("D34c an answer carries its key facts", lambda cx: ins(cx, "analysis_question", id=new(), **Q_, **dict(ANS, key_facts=None)), True, "ck_analysis_question_answer")
    expect("D35 an abstention carries no badge, result or narration",
           lambda cx: ins(cx, "analysis_question", id=new(), **Q_, state="abstained", outcome="too_broad", answered_at="2026-11-30T08:00:02Z", badge="generated"),
           True, "ck_analysis_question_answer")
    expect("D36 an open question has no outcome, and an open row with a badge and result is refused too (the null-safe answer check)",
           lambda cx: ins(cx, "analysis_question", id=new(), **Q_, badge="generated", result={"rows": []}), True, "ck_analysis_question_answer")
    expect("D37 a failed question has no outcome but its stop reason",
           lambda cx: ins(cx, "analysis_question", id=new(), **Q_, state="failed", failure_reason="budget_exceeded", answered_at="2026-11-30T08:00:02Z"), False)
    expect("D38 a failed question with an outcome is refused",
           lambda cx: ins(cx, "analysis_question", id=new(), **Q_, state="failed", outcome="too_broad", failure_reason="budget_exceeded", answered_at="2026-11-30T08:00:02Z"),
           True, "ck_analysis_question_closed")
    expect("D39 an ambiguous member carries its options; abstained with routing_blocked is a closed state",
           lambda cx: (ins(cx, "analysis_question", id=new(), **Q_, state="abstained", outcome="ambiguous_member", clarification_options={"members": ["k1", "k2"]},
                           answered_at="2026-11-30T08:00:02Z"),
                       ins(cx, "analysis_question", id=new(), **Q_, state="abstained", outcome="routing_blocked", answered_at="2026-11-30T08:00:02Z")), False)
    expect("D40 a verified badge names exactly one verified source", lambda cx: ins(cx, "analysis_question", id=new(), **Q_, **dict(ANS, badge="verified")),
           True, "ck_analysis_question_verified_source")
    expect("D41 a closed question is frozen: its plan hash cannot change", lambda cx: cx.execute("update analysis_question set analysis_plan_hash=%s where id=%s", ("b" * 64, QA)),
           True, "only feedback and erasure")
    expect("D42 the asker's feedback and the erasure of the text are allowed on a closed question",
           lambda cx: (cx.execute("update analysis_question set feedback='wrong', feedback_at=now() where id=%s", (QA,)),
                       cx.execute("update analysis_question set question_text=NULL, erased_at=now() where id=%s", (QA,))), False)
    expect("D42b feedback is given once: changing it is refused", lambda cx: cx.execute("update analysis_question set feedback='helpful' where id=%s", (QA,)),
           True, "only feedback and erasure")
    expect("D42c feedback is given once: clearing it is refused", lambda cx: cx.execute("update analysis_question set feedback=NULL, feedback_at=NULL where id=%s", (QA,)),
           True, "only feedback and erasure")
    SA_ID, KPI_ID, V1, V2 = new(), new(), new(), new()
    ins(c, "saved_analysis", id=SA_ID, company_id=I["co"], code="revenue_by_group", name="Revenue by group", kind="analysis", latest_version=2, owner_user_id=I["user"],
        recorded_at="2026-11-30T08:00:00Z")
    ins(c, "saved_analysis", id=KPI_ID, company_id=I["co"], code="monthly_revenue", name="Monthly revenue", kind="kpi", latest_version=1, owner_user_id=I["user"],
        recorded_at="2026-11-30T08:00:00Z")
    VER = dict(company_id=I["co"], plan={"plan_version": 1}, analysis_plan_hash=H, definition_hashes={"net_revenue": H}, catalog_version="0.1.0",
               created_by_user_id=I["user"], recorded_at="2026-11-30T08:00:00Z")
    ins(c, "saved_analysis_version", id=V1, saved_analysis_id=SA_ID, kind="analysis", version=1, **VER)
    expect("D43 a saved analysis cannot be verified without a released version in force",
           lambda cx: cx.execute("update saved_analysis set state='verified' where id=%s", (SA_ID,)), True, "ck_saved_analysis_verified")
    expect("D44 the verified version must exist: version 2 has no row, so the deferred key refuses it at commit",
           lambda cx: cx.execute("update saved_analysis set state='verified', verified_version=2 where id=%s", (SA_ID,)), True, "fk_saved_analysis_verified_version")
    SAVEDP = [{"claim": "rose", "facts": {"fact": {"members": {"item_group": "k1", "posting_date": "2026-11-01"}, "measure": "net_revenue", "kind": "change"}}},
              {"claim": "largest_value", "facts": {"fact": {"role": "max", "measure": "net_revenue"}}}]
    expect("D44b a saved narrative plan by full coordinate and by role is accepted on a draft version",
           lambda cx: ins(cx, "saved_analysis_version", id=new(), saved_analysis_id=SA_ID, kind="analysis", version=2, narrative_plan=SAVEDP, **VER), False)
    expect("D44c the saved-version check refuses the round-5 bypass too (free-text keys under members)",
           lambda cx: ins(cx, "saved_analysis_version", id=new(), saved_analysis_id=SA_ID, kind="analysis", version=3,
                          narrative_plan=[{"claim": "rose", "facts": {"fact": {"members": {"Item group tripled!": "k"}, "measure": "net_revenue", "kind": "change"}}}], **VER),
           True, "ck_saved_analysis_version_narrative_plan")
    expect("D45 a version's kind must equal its saved analysis's (an analysis version under a KPI is refused)",
           lambda cx: ins(cx, "saved_analysis_version", id=new(), saved_analysis_id=KPI_ID, kind="analysis", version=1, **VER), True, "foreign key")
    expect("D46 a KPI version needs its measure, grain, direction and target",
           lambda cx: ins(cx, "saved_analysis_version", id=new(), saved_analysis_id=KPI_ID, kind="kpi", version=1, kpi_measure="net_revenue", **VER), True, "ck_saved_analysis_version_kpi")
    expect("D47 KPI thresholds lie on the unfavourable side: for direction up a warning above the target is refused",
           lambda cx: ins(cx, "saved_analysis_version", id=new(), saved_analysis_id=KPI_ID, kind="kpi", version=1, kpi_measure="net_revenue", kpi_time_grain="month",
                          favorable_direction="up", target_value=100, warning_threshold=110, **VER), True, "ck_saved_analysis_version_thresholds")
    expect("D48 no agent drafts a KPI: a KPI version with an origin agent run is refused",
           lambda cx: ins(cx, "saved_analysis_version", id=new(), saved_analysis_id=KPI_ID, kind="kpi", version=1, kpi_measure="net_revenue", kpi_time_grain="month",
                          favorable_direction="up", target_value=100, origin_agent_run_id=X("select id from agent_run limit 1").fetchone()[0], **VER),
           True, "ck_saved_analysis_version_kpi_by_people")
    expect("D49 a self-release must say so: released by its author without is_self_released is refused",
           lambda cx: cx.execute("update saved_analysis_version set released_by_user_id=%s, released_at=now() where id=%s", (I["user"], V1)), True, "ck_saved_analysis_version_released")
    X("update saved_analysis_version set released_by_user_id=%s, released_at=now() where id=%s", (I["user2"], V1))
    X("update saved_analysis set state='verified', verified_version=1 where id=%s", (SA_ID,))
    expect("D50 a released version is immutable and cannot be deleted",
           lambda cx: cx.execute("update saved_analysis_version set analysis_plan_hash=%s where id=%s", ("b" * 64, V1)), True, "immutable")
    EX = dict(company_id=I["co"], question_text="Net revenue last month?", normalized_question="net revenue last month", language="en", flow="ledger",
              source="person", created_by_user_id=I["user"], recorded_at="2026-11-30T08:00:00Z")
    E1, E2 = new(), new()
    ins(c, "analysis_example", id=E1, expected_outcome="answered", plan={"plan_version": 1}, analysis_plan_hash=H, catalog_version="0.1.0", state="verified",
        released_by_user_id=I["user2"], released_at="2026-11-30T09:00:00Z", **EX)
    expect("D51 a released example is immutable: its plan cannot change", lambda cx: cx.execute("update analysis_example set analysis_plan_hash=%s where id=%s", ("b" * 64, E1)),
           True, "immutable")
    expect("D52 a new version (2, superseding the verified one) may be drafted beside it",
           lambda cx: ins(cx, "analysis_example", id=E2, expected_outcome="answered", plan={"plan_version": 1}, analysis_plan_hash="c" * 64, catalog_version="0.1.0",
                          version=2, supersedes_example_id=E1, **EX), False)
    expect("D53 one verified example per question: releasing version 2 while version 1 is verified is refused",
           lambda cx: cx.execute("update analysis_example set state='verified', released_by_user_id=%s, released_at=now() where id=%s", (I["user2"], E2)), True, "ux_analysis_example_verified")
    expect("D54 retiring version 1 and releasing version 2 in one command succeeds",
           lambda cx: (cx.execute("update analysis_example set state='retired' where id=%s", (E1,)),
                       cx.execute("update analysis_example set state='verified', released_by_user_id=%s, released_at=now() where id=%s", (I["user2"], E2))), False)
    expect("D55 an answerable example carries its plan; an abstention example carries none",
           lambda cx: ins(cx, "analysis_example", id=new(), expected_outcome="answered", **dict(EX, normalized_question="x")), True, "ck_analysis_example_plan")
    X("DROP SCHEMA query CASCADE")                                # leave the lab database as load_all.py made it
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
