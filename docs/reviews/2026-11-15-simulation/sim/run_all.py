"""Run the six NativeFlows flows end to end on nativeflows_sim, from scratch, and write trace/trace.json and trace/trace.md.

Simulation for design validation, not product code. Usage: see README.md.
"""
import datetime as dt
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_schema  # noqa: E402
from flows import core, seed, checks, render  # noqa: E402
from flows import f1_customer, f2_price_list, f3_cpq, f4_o2c, f5_planning, f6_p2p, f6_uom  # noqa: E402
import importlib  # noqa: E402
NEW_FLOWS = [(7, "f7_intake"), (8, "f8_barcode"), (9, "f9_workflow_settings"), (10, "f10_analysis"), (11, "f11_production")]
from flows.core import TRACE, W, LLM_STATS, jsonable  # noqa: E402

# Execution follows the business timeline: flow 4 places the order, flows 5 and 6 plan and buy the components,
# then flow 4 continues with production, delivery, invoice and cash.
PLAN = [(1, f1_customer.run), (2, f2_price_list.run), (3, f3_cpq.run), (4, f4_o2c.run_order), (5, f5_planning.run),
        (6, f6_p2p.run), (6, f6_uom.run), (4, f4_o2c.run_fulfil)]
# flows 7-11 (ADR-0057 to ADR-0064) run after the timeline of flows 1-6, from 2026-11-24
for _n, _m in NEW_FLOWS:
    if os.path.exists(os.path.join(HERE, "flows", _m + ".py")):
        PLAN.append((_n, importlib.import_module("flows." + _m).run))
ONLY = os.environ.get("SIM_ONLY")   # e.g. "1,2" for development; the full run is the default


def main():
    db = core.DB()
    print("load schema ...")
    db.x("set client_min_messages = warning")
    db.x("DROP SCHEMA IF EXISTS nativeflows CASCADE; DROP SCHEMA IF EXISTS types CASCADE")
    schema_info = build_schema.load(db.cx, core.DSN)
    db.load_columns()
    from flows import uom
    uom.BLOCK_TABLES.clear()
    uom.BLOCK_TABLES.update(t for t, c in db.cols.items() if "uom_factor_source" in c)
    n_tables = db.val("select count(*) from information_schema.tables where table_schema='nativeflows' and table_type='BASE TABLE'")
    print(f"  {n_tables} tables")
    TRACE.flow = 0
    setup = seed.seed(db)
    results, failed = {}, None
    for flow, fn in PLAN:
        if ONLY and str(flow) not in ONLY.split(","):
            continue
        if failed:
            results.setdefault(flow, False)
            continue
        print(f"flow {flow}: {fn.__name__}")
        try:
            ok = fn(db)
            results[flow] = results.get(flow, True) and bool(ok)
        except Exception:
            tb = traceback.format_exc()
            print(tb)
            results[flow] = False
            failed = flow
            f = next((x for x in TRACE.flows if x["flow"] == flow), None)
            if f:
                f["error"] = tb.strip().splitlines()[-1]
    print("checks ...")
    inv = checks.global_checks(db)
    for i in inv:
        print(("PASS " if i["ok"] else "FAIL ") + i["code"] + " " + i["name"] + ("" if i["ok"] else f" -- {i['detail']}"))
    for f in TRACE.flows:
        f["status"] = "pass" if results.get(f["flow"]) and all(c["ok"] for c in f["checks"]) else "fail"
        f["steps"] = sum(1 for s in TRACE.steps if s["flow"] == f["flow"])
        f["llm_calls"] = sum(1 for s in TRACE.steps if s["flow"] == f["flow"] and s.get("llm"))
    trace = {"meta": {"run_at": dt.datetime.now(core.TZ).isoformat(timespec="seconds"), "database": "nativeflows_sim", "format_version": "2.0",
                      "schema": schema_info, "tables": n_tables,
                      "simulation_stubs": "sim_stubs.sql (not design DDL)",
                      "llm": {"model": core.LLM_MODEL, "mode": core.LLM_MODE, "live": LLM_STATS["live"], "fallback": LLM_STATS["fallback"],
                              "calls": LLM_STATS["calls"]},
                      "lanes": {"person": "human", "llm": "agent_llm", "det": "deterministic", "system": "system", "db": "deterministic (database)"}},
             "setup": jsonable(setup), "cast": [{"name": u["name"], "template": u["template"], "login": u["login"]} for u in W.users_list],
             "flows": sorted(TRACE.flows, key=lambda f: f["flow"]), "steps": TRACE.steps, "invariants": jsonable(inv)}
    os.makedirs(os.path.join(HERE, "trace"), exist_ok=True)
    with open(os.path.join(HERE, "trace", "trace.json"), "w", encoding="utf-8") as fh:
        json.dump(jsonable(trace), fh, ensure_ascii=False, indent=1)
    render.render(jsonable(trace), os.path.join(HERE, "trace", "trace.md"))
    print(f"steps: {len(TRACE.steps)}; LLM live {LLM_STATS['live']}, fallback {LLM_STATS['fallback']}")
    print("flows: " + ", ".join(f"{f['flow']}={f['status']}" for f in trace["flows"]))
    return 0 if all(f["status"] == "pass" for f in trace["flows"]) and all(i["ok"] for i in inv) else 1


if __name__ == "__main__":
    sys.exit(main())
