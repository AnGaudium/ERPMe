"""Flow 5: demand planning (flows report Part B flow 5; ADR-0024 rules 10-23 with holistic F0 tiers; ADR-0036 rules 1-12;
ADR-0051 rules 23-25 with the flow-review correction; ADR-0055 rule 16 note A13)."""
import datetime as dt
from decimal import Decimal as D, ROUND_CEILING
from fractions import Fraction as F

from .core import TRACE, W, ins, upd, new_id, now, sha, numbers_in, stray_numbers, set_day, fmt, jsonable
from . import platform as P
from . import ledger as L
from . import md, pure
from . import uom as U
from .common import llm_step, llm_view, approval_walk

HORIZON = 28
EXPLAIN_SCHEMA = {"type": "object", "required": ["explanation", "recommended", "reason_codes"], "properties": {
    "explanation": {"type": "string", "maxlen": 1200}, "recommended": {"type": "string"}, "reason_codes": {"type": "array", "items": {"type": "string"}}}}
SYS_EXPLAIN = ("You are step L1 explain of ERPMe's planning workflow (ADR-0051 rule 24), seat analysis. Explain the planning exception to a planner "
               "in Vietnamese in at most 1200 characters, using only the facts and numbers given, and recommend one of the offered candidate "
               "handles or none. You compute nothing new and change nothing. Return only JSON PlanningExplainOutput 1.0.0: {\"explanation\", "
               "\"recommended\": a candidate handle or \"none\", \"reason_codes\": [short codes]}.")


def lot_size(short, iwp, si):
    """Lot size in the inventory unit, then the supplier's minimum and multiple in its order unit (ADR-0056 rule 14):
    converted exactly, rounded up there, converted back half_up. Returns (inventory quantity, order quantity, steps)."""
    qty = short
    if iwp["lot"] == "fixed":
        qty = (short / iwp["fixed"]).to_integral_value(rounding=ROUND_CEILING) * iwp["fixed"]
    q_order, inv, steps = U.order_unit_lot(qty, si["f"], si["dec_order"], si["dec_inv"], si["min"], si["mult"])
    return U.to_dec(inv), U.to_dec(q_order), steps


def net_node(code, demands, stock, iwp, si, pdate, end):
    """net_requirements per (item, warehouse), day by day, safety stock as a floor, pegging to what caused each shortfall."""
    projected, orders, exceptions, day = stock, [], [], pdate
    while day <= end:
        todays = [x for x in demands if x["day"] == day]
        for x in todays:
            projected -= x["qty"]
        if projected < iwp["safety"]:
            short = iwp["safety"] - projected
            peg, rem = [], short
            for x in todays:
                take = min(rem, x["qty"])
                if take > 0:
                    peg.append({**x["peg"], "quantity": take})
                    rem -= take
            if rem > 0:
                peg.append({"pegging_target_kind": "safety_stock", "quantity": rem})
                if day == pdate:
                    exceptions.append({"kind": "below_safety_stock", "item": code, "evidence": {"stock": stock, "safety_stock": iwp["safety"]}})
            qty, q_order, steps = lot_size(short, iwp, si)
            if qty > short:
                peg.append({"pegging_target_kind": "lot_size_excess", "quantity": qty - short})
                if any(s[0] == "raised to the minimum" for s in steps):
                    exceptions.append({"kind": "supplier_minimum_excess", "item": code, "evidence": {"needed": short, "supplier_minimum": si["min"],
                                                                                                     "order_unit": U.code_of(si["order_uom"])}})
            rel, arr, late = pure.release_for(day, si["proc"], si["transit"], iwp["receiving"], pdate)
            o = {"item": code, "need_date": day, "quantity": qty, "shortfall": short, "release_date": rel, "availability_date": arr, "pegging": peg,
                 "supplier": si["supplier"], "rounding_excess": qty - short, "late_days": (arr - day).days if late else 0,
                 "order_quantity": q_order, "order_uom": si["order_uom"], "f": si["f"], "source": si["source"], "lot_steps": steps}
            if late:
                exceptions.append({"kind": "shortage_inside_lead_time", "item": code, "lateness_days": (arr - day).days,
                                   "evidence": {"need_date": day, "earliest_arrival": arr, "lead_time": f"{si['proc']} working + {si['transit']} transit + {iwp['receiving']} receiving"}})
            orders.append(o)
            projected += qty
        day += dt.timedelta(days=1)
    return orders, exceptions


def run(db):
    TRACE.start_flow(5, "Demand planning", "Hoạch định nhu cầu",
                     "Forecast from sales history (short-history tier), a regenerative planning run: make-to-order production planned order pegged "
                     "to the sales line, component explosion, net requirements with safety stock, lot sizes and lead times, exceptions as work items; "
                     "the planning agent (never tainted) explains and drafts a change proposal; the planner submits, another eligible person approves; "
                     "the executor converts and purchasing drafts the purchase request; the planner converts the production planned order.")
    set_day("2026-11-05")
    pdate = W.today
    end = pdate + dt.timedelta(days=HORIZON)
    planner, pm, owner = W.user["production_planner"], W.user["purchasing_manager"], W.user["owner"]
    pa = P.person("production_planner")
    sysp = P.system_for(planner)
    abs_ = W.items["ABS"]["id"]
    # 1 forecast
    fc, avg, checks, tier = pure.moving_average_forecast(W.abs_history, 5)
    fr = new_id("forecast_run")
    daily, carry = [], F(0)
    for ws, qy in fc:
        for i in range(5):
            day = ws + dt.timedelta(days=i)
            want = qy / 5 + carry
            take = F(int(want))
            carry = want - take
            daily.append([day, take])
    daily = [x for x in daily if pdate <= x[0] <= end]
    ins(db, "forecast_run", id=fr, planning_date=pdate, method="moving_average", requested_by_user_id=planner["id"], check_results=[{"code": c, "item": "ABS"} for c in checks],
        input_hash=sha([(w, q) for w, q in W.abs_history]), output_hash=sha(daily))
    for day, q in daily:
        ins(db, "forecast_line", forecast_run_id=fr, item_id=abs_, warehouse_id=W.wh, forecast_date=day, quantity=D(q.numerator) / D(q.denominator), forecast_tier=tier)
    so_abs = W.dsl[2]
    rd = db.val("select requested_date from demand_supply_line where id=%s", (so_abs["id"],))
    left, consumed = F(so_abs["qty"]), []
    order = [x for x in sorted(daily, key=lambda x: x[0], reverse=True) if rd - dt.timedelta(days=7) <= x[0] <= rd] + \
            [x for x in sorted(daily, key=lambda x: x[0]) if rd < x[0] <= rd + dt.timedelta(days=7)]
    for x in order:
        take = min(left, x[1])
        if take:
            x[1] -= take
            left -= take
            consumed.append({"day": x[0], "consumed": take})
        if not left:
            break
    TRACE.step("system", "job RunForecast (on behalf of the planner)", "RunForecast", "Forecast: 8-week average, short-history tier, consumed by the order",
               "Dự báo: trung bình 8 tuần, bậc lịch sử ngắn, trừ bởi đơn hàng", mode="system job on queue jobs", rule="ADR-0024 rules 10-13; holistic F0",
               inputs={"item": "ABS", "history_weeks": len(W.abs_history)}, outputs={"tier": tier, "weekly_forecast": avg, "check_results": checks,
                                                                                       "forecast_days": len(daily), "consumption_by_order": consumed},
               deterministic="n = 12 weeks: 8 <= n < 52 gives the 8-week average, unindexed, with forecast_history_insufficient; daily spread with carry; "
                             "consumption within forecast_consumption_days, backward then forward")

    # 2 planning run: MTO production planned order, explosion, net requirements
    prun = new_id("planning_run")
    ins(db, "planning_run", id=prun, planning_date=pdate, forecast_run_id=fr, requested_by_user_id=planner["id"], started_at=now())
    cfg_item = W.items[W.cfg_item]["id"]
    need = rd
    start, finish = pure.sub_working_days(need, 2), pure.sub_working_days(need, 1)
    po_prod = new_id("planned_order")
    ins(db, "planned_order", id=po_prod, item_id=cfg_item, warehouse_id=W.wh, order_type="production", need_date=need, for_demand_supply_line_id=W.dsl[1]["id"],
        quantity=W.dsl[1]["qty"], order_quantity=W.dsl[1]["qty"], order_uom_id=W.uom["H87"], uom_numerator=1, uom_denominator=1, uom_factor_source="identity",
        release_date=start, production_version_id=W.pv, planned_start_date=start, planned_end_date=finish, availability_date=need,
        planning_run_id=prun)
    ins(db, "planned_order_pegging", id=new_id("planned_order_pegging"), planned_order_id=po_prod, pegging_target_kind="demand_line",
        demand_supply_line_id=W.dsl[1]["id"], quantity=W.dsl[1]["qty"])
    W.code_of[po_prod] = f"planned production {W.cfg_item}"
    explosion = pure.explode(W.MODEL, W.COMP, W.cfg, W.dsl[1]["qty"])
    comp_rows = []
    for n, (item, qty) in enumerate(explosion, 1):
        cid = new_id("planned_order_component")
        ins(db, "planned_order_component", id=cid, planned_order_id=po_prod, line_number=n, component_item_id=item, warehouse_id=W.wh, quantity=qty, requested_date=start)
        comp_rows.append((cid, item, qty))
    iwp, sis = {}, {}
    for item, ss, lot, fixed, recv in db.all("select item_id, safety_stock_quantity, lot_size_method, fixed_lot_quantity, receiving_days from item_warehouse_planning where replenishment_source='purchase'"):
        iwp[item] = {"safety": D(ss), "lot": lot, "fixed": D(fixed) if fixed else None, "receiving": recv}
    for sup, item, proc, transit, mn, mult, ou in db.all("select supplier_partner_id, item_id, supplier_processing_days, transit_days, minimum_order_quantity, order_multiple, order_uom_id from supplier_item where is_preferred"):
        conv = U.to_inventory(db, ou, item=item)
        sis[item] = {"supplier": sup, "proc": proc, "transit": transit, "min": D(mn), "mult": D(mult) if mult else None, "order_uom": ou,
                     "f": conv["factor"], "source": conv["source"], "dec_order": U.dec_of(ou), "dec_inv": U.dec_of(conv["inventory_uom_id"])}
    all_orders, all_exc = [], []
    for item in sorted(iwp, key=lambda i: W.code_of[i]):
        code = W.code_of[item]
        dem = [{"day": start, "qty": q, "peg": {"pegging_target_kind": "planned_order", "target_planned_order_id": po_prod, "planned_order_component_id": cid}}
               for cid, it, q in comp_rows if it == item]
        if item == abs_:
            dem += [{"day": rd, "qty": so_abs["qty"], "peg": {"pegging_target_kind": "demand_line", "demand_supply_line_id": so_abs["id"]}}]
            dem += [{"day": dday, "qty": D(q.numerator) / D(q.denominator), "peg": {"pegging_target_kind": "forecast", "forecast_date": dday}} for dday, q in daily if q > 0]
        if not dem and L.on_hand(db, item)[0] >= iwp[item]["safety"]:
            continue
        stock = L.on_hand(db, item)[0]
        orders, exc = net_node(code, dem, stock, iwp[item], sis[item], pdate, end)
        all_orders += orders
        all_exc += exc
    W.planned = {}
    seqs = {}
    for o in all_orders:
        it = W.items[o["item"]]["id"]
        key = (it, o["need_date"])
        seqs[key] = seqs.get(key, 0) + 1
        oid = new_id("planned_order")
        ins(db, "planned_order", id=oid, item_id=it, warehouse_id=W.wh, order_type="purchase", supplier_partner_id=o["supplier"], need_date=o["need_date"],
            sequence=seqs[key], quantity=o["quantity"], order_quantity=o["order_quantity"], order_uom_id=o["order_uom"], uom_numerator=o["f"].numerator,
            uom_denominator=o["f"].denominator, uom_factor_source=o["source"], rounding_excess_quantity=o["rounding_excess"], release_date=o["release_date"],
            planning_run_id=prun)
        o["id"] = oid
        W.code_of[oid] = f"planned purchase {o['item']} {o['quantity']}"
        W.planned.setdefault(o["item"], []).append(o)
        for pg in o["pegging"]:
            ins(db, "planned_order_pegging", id=new_id("planned_order_pegging"), planned_order_id=oid, **pg)
    exc_rows = []
    for e in all_exc:
        po_ = next((o for o in all_orders if o["item"] == e["item"]), None)
        eid = new_id("planning_exception")
        ins(db, "planning_exception", id=eid, planning_run_id=prun, kind=e["kind"], exception_key=f"{e['kind']}:{e['item']}:WH1", item_id=W.items[e["item"]]["id"],
            warehouse_id=W.wh, supplier_partner_id=po_["supplier"] if po_ else None, planned_order_id=po_["id"] if po_ else None,
            lateness_days=e.get("lateness_days"), evidence=jsonable(e["evidence"]))
        exc_rows.append({**e, "id": eid})
    counts = {"planned_orders": len(all_orders) + 1, "exceptions": len(exc_rows)}
    upd(db, "planning_run", {"id": prun}, state="completed", completed_at=now(), output_counts=counts, input_hash=sha(counts), output_hash=sha([o["id"] for o in all_orders]))
    TRACE.step("system", "job RunPlanning (on behalf of the planner)", "RunPlanning", "Planning run: make to order, explosion, net requirements",
               "Chạy hoạch định: sản xuất theo đơn, bung định mức, nhu cầu ròng", mode="system job, regenerative, one per company",
               rule="ADR-0024 rules 14-21; ADR-0036 rules 1-9; ADR-0046 rule 12",
               outputs={"production_planned_order": {"item": W.cfg_item, "quantity": W.dsl[1]["qty"], "start": start, "end": finish, "availability": need,
                                                     "pegged_to": "sales order line 1"},
                        "components": [{"item": W.code_of[i], "quantity": q} for _, i, q in comp_rows],
                        "purchase_planned_orders": [{"item": o["item"], "quantity": o["quantity"], "order_quantity": f"{fmt(o['order_quantity'])} {U.code_of(o['order_uom'])}",
                                                     "need": o["need_date"], "release": o["release_date"],
                                                     "arrival": o["availability_date"], "late_days": o["late_days"]} for o in all_orders],
                        "exceptions": [{"kind": e["kind"], "item": e["item"], "lateness_days": e.get("lateness_days")} for e in exc_rows]},
               events=[P.emit(db, "PlanningCompleted", "planning_run", prun, sysp, "RunPlanning")],
               deterministic="make-to-order netting per sales line; linear sizing rounded up per line; day-by-day projection with safety stock as a "
                             "floor; lot size, supplier minimum and multiple; lead time = supplier working days + transit + receiving")
    items = []
    for e in exc_rows:
        items.append(P.raise_item(db, "planning_exception", "planning_exception", e["id"], ("role", "buyer"), due_days=3, details={"kind": e["kind"], "item": e["item"]}))
    TRACE.step("system", "consumer planning_work_items", "raise planning_exception", "Exceptions become work items", "Ngoại lệ thành việc cần xử lý",
               mode="system consumer of PlanningCompleted", rule="ADR-0024 rule 21; ADR-0042 rule 18; holistic P7 (owner buyer for purchased nodes)",
               outputs={"work_items": [{"kind": e["kind"], "item": e["item"]} for e in exc_rows]}, work_items=items)

    # 3 the planning agent on the FRAME-L exception
    fx = next(e for e in exc_rows if e["kind"] == "shortage_inside_lead_time" and e["item"] == "FRAME-L")
    fitem = items[exc_rows.index(fx)]
    run_ = P.start_run(db, "planning", "work_item", fitem["id"], planner, scope_kind="subject", subject=("planning_exception", fx["id"]))
    win = db.val("select conversion_window_days from planning_setting")
    fo = W.planned["FRAME-L"][0]
    delta = [o for o in all_orders if o["supplier"] == W.partners["S-DELTA"] and fo["release_date"] <= o["release_date"] <= fo["release_date"] + dt.timedelta(days=win)]
    lt = db.one("select mean_days, standard_deviation_days, sample_count from supplier_item_lead_time where item_id=%s", (W.items["FRAME-L"]["id"],))
    planned_lt = (fo["availability_date"] - fo["release_date"]).days
    gap = abs(D(planned_lt) - D(lt[0])) / D(lt[0]) * 100
    cands = [{"handle": "c1", "action": "ConvertPlannedOrder", "orders": ["FRAME-L"], "effect": f"FRAME-L {fmt(fo['quantity'])} released today, arrives {fo['availability_date']}, "
              f"{fo['late_days']} days after the need date {fo['need_date']}"},
             {"handle": "c2", "action": "ConvertPlannedOrder x" + str(len(delta)), "orders": [o["item"] for o in delta],
              "effect": f"one Delta request inside the {win}-day conversion window: " + ", ".join(f"{o['item']} {fmt(o['quantity'])}" for o in delta) +
                        f"; FRAME-L still arrives {fo['availability_date']}"},
             {"handle": "c3", "action": "parameter change (supplier lead time)", "orders": [],
              "effect": f"planned lead time {planned_lt} days vs stored mean {fmt(D(lt[0]))} days (sd {fmt(D(lt[1]))}, {lt[2]} receipts): {gap:.0f}% apart (threshold 20%)"}]
    if gap <= 20:
        cands = cands[:2]
    TRACE.step("det", "planning workflow code", "D1 gather + D2 candidate_actions", "Code gathers pegging and computes the candidate actions",
               "Mã tất định thu thập liên kết nhu cầu và tính các phương án", mode="agent workflow code, deterministic; the run is never tainted",
               rule="ADR-0051 rules 23-24 (and the P25 note: stored lead-time statistics)",
               inputs={"exception": "shortage_inside_lead_time FRAME-L", "pegging": f"planned production {W.cfg_item} -> sales order line 1"},
               outputs={"candidates": cands, "stock_transfer": "not offered (one warehouse)"},
               deterministic="candidates and their effects come from code; the LLM only explains and picks a handle")
    facts = (f"Exception: shortage inside lead time, item FRAME-L, warehouse WH1.\nNeed: {fmt(fo['quantity'])} on {fo['need_date']} for production of 2 frame units "
             f"(sales order {W.so['number']}, delivery requested {rd}).\nStock 0. Supplier Delta: {sis[W.items['FRAME-L']['id']]['proc']} working days processing, "
             f"{sis[W.items['FRAME-L']['id']]['transit']} days transit, 1 receiving day. Earliest arrival {fo['availability_date']}, {fo['late_days']} days late.\n"
             f"Stored lead time statistics: mean {fmt(D(lt[0]))} days, standard deviation {fmt(D(lt[1]))}, {lt[2]} receipts.\nCandidates:\n" +
             "\n".join(f"- {c['handle']}: {c['action']} ({', '.join(c['orders']) or 'parameter'}): {c['effect']}" for c in cands))
    ex, rec = llm_step(db, run_, "explain", "analysis", "PlanningExplainOutput", EXPLAIN_SCHEMA, SYS_EXPLAIN, facts,
                       {"explanation": f"FRAME-L cần {fo['quantity']} vào {fo['need_date']} nhưng sớm nhất đến {fo['availability_date']}, trễ {fo['late_days']} ngày. "
                                       "Nên chuyển ngay các đơn kế hoạch của Delta trong cửa sổ gộp để đặt một lần và đề nghị nhà cung cấp giao gấp.",
                        "recommended": __import__("os").environ.get("SIM_PLANNING_FALLBACK", "c2"), "reason_codes": ["shortage_inside_lead_time", "consolidation"]}, 600)
    bad_nums = stray_numbers(ex["explanation"], numbers_in(facts) | {D(x) for x in range(0, 32)})
    handle_ok = ex["recommended"] in [c["handle"] for c in cands] + ["none"]
    TRACE.step("llm", "planning agent (LLM, seat analysis)", "L1 explain", "LLM explains the exception and recommends a candidate",
               "LLM giải thích ngoại lệ và đề xuất phương án", mode="agent run, untainted (may_read_untrusted false)", rule="ADR-0051 rule 24 L1",
               outputs={"recommended": ex["recommended"], "explanation": ex["explanation"]},
               llm=llm_view(rec, "Explain with the given numbers only; pick an offered handle",
                            ("accepted: handle offered; every number in the text appears in the input" if handle_ok and not bad_nums else
                             f"checked: handle offered {handle_ok}; numbers not in the input {bad_nums}")))
    TRACE.check("the planning agent's handle was offered and its numbers appear in the input", handle_ok and not bad_nums, {"handle": ex["recommended"], "stray": bad_nums}, "ADR-0051 rule 24")
    choice = next((c for c in cands if c["handle"] == ex["recommended"]), None) if handle_ok else None
    agent = P.Actor("agent", run=run_, on_behalf_of=planner)
    delta_orders = [o for o in all_orders if o["item"] in cands[1]["orders"]]
    if choice and choice["handle"] in ("c1", "c2"):
        conv = [o for o in all_orders if o["item"] in choice["orders"]]
        items_cp = [{"command_type": "ConvertPlannedOrder", "payload": {"planned_order": str(o["id"]), "item": o["item"], "quantity": fmt(o["quantity"])},
                     "target_table": "planned_order", "target_id": o["id"], "changes": [{"field": "state", "old": "proposed", "new": "converted"}]} for o in conv]
    elif choice:
        conv = []
        si_id = db.val("select id from supplier_item where supplier_partner_id=%s and item_id=%s", (W.partners["S-DELTA"], W.items["FRAME-L"]["id"]))
        items_cp = [{"command_type": "UpdateSupplierItem", "payload": {"supplier_item": str(si_id), "item": "FRAME-L", "supplier_processing_days": 14},
                     "target_table": "supplier_item", "target_id": si_id, "changes": [{"field": "supplier_processing_days", "old": 8, "new": 14}]}]
    else:
        conv, items_cp = [], []
    cp = None
    if items_cp:
        plan = {"items": [{k: v for k, v in it.items() if k != "target_id"} for it in items_cp],
                "evidence": {"pegging": f"{W.cfg_item} -> {W.so['number']}", "explanation": ex["explanation"][:400]}}
        cp = P.create_doc(db, "change_proposal", agent, header={"plan": jsonable(plan), "plan_hash": sha(plan), "evidence": [{"table": "planning_exception", "id": str(fx["id"])}],
                                                                "reason": ex["explanation"][:500], "document_date": W.today},
                          work_item=fitem["id"], workflow_step="planning.propose", header_table="change_proposal", number="CP planning")
        for i, it in enumerate(items_cp):
            ins(db, "change_proposal_item", id=new_id("change_proposal_item"), change_proposal_id=cp["id"], item_index=i, command_type=it["command_type"], schema_version=1,
                payload=it["payload"], target_table=it["target_table"], target_id=it["target_id"], field_changes=it["changes"])
        P.record_tool(db, run_, "planning.propose", "CreateChangeProposal", "execute", {"items": len(items_cp)}, None)
        P.audit(db, "CreateChangeProposal", agent, doc=cp, subject_table="change_proposal", subject_id=cp["id"])
        P.link_item(db, fitem["id"], "change_proposal", cp["id"], "draft")
    P.note_item(db, fitem["id"], "agent_run", run_["id"], ex["explanation"][:1200])
    P.end_run(db, run_, "drafted" if cp else "no_action")
    TRACE.step("llm", "planning agent (tool call, no LLM)", "CreateChangeProposal", "The agent drafts the recommended action as a change proposal",
               "Agent soạn đề xuất theo phương án được chọn", mode="agent run, draft only, proposal-bound", rule="ADR-0051 rule 24 D3; ADR-0036 rule 12; ADR-0024 rule 23",
               outputs={"recommended": ex["recommended"], "change_proposal": "CP planning" if cp else None,
                        "items": [f"{it['command_type']} {it['payload'].get('item')} {it['payload'].get('quantity') or it['payload'].get('supplier_processing_days')}" for it in items_cp],
                        "is_tainted": cp["tainted"] if cp else None},
               events=[P.emit(db, "ChangeProposalCreated", "change_proposal", cp["id"], agent, "CreateChangeProposal")] if cp else None,
               notes=("UpdateSupplierItem: module planning, leaf supplier_item at edit (ADR-0024 rule 23 note, 32e7b1c)" if not conv and cp else None))
    if cp:
        dec, res = P.submit(db, cp, pa, {"amount": 0}, "SubmitChangeProposal")
        TRACE.step("person", f"{planner['name']} (production_planner)", "SubmitChangeProposal", "The planner submits the proposal", "Kế hoạch viên gửi duyệt đề xuất",
                   mode="direct", rule="ADR-0051 rule 25; ADR-0043 rule 9 floor 7", outputs={"state": P.doc_state(db, cp["id"])}, decision=P.decision_summary(dec),
                   policy=[P.policy_line(dec)], events=res["events"], work_items=res["items"])
        approval_walk(db, cp, ["purchasing_manager", "owner"], "Checked pegging and supplier facts", "ApproveChangeProposal",
                      "The purchasing manager approves the proposal", "Trưởng phòng mua hàng duyệt đề xuất", "ADR-0051 rule 25 note; ADR-0055 rule 5 note")
        exe = P.system_for(pm)
        exe_id = new_id("change_proposal_execution")
        ins(db, "change_proposal_execution", id=exe_id, change_proposal_id=cp["id"], document_version_id=cp["version_id"], executed_at=now())
        if not conv:
            upd(db, "supplier_item", {"id": items_cp[0]["target_id"]}, supplier_processing_days=14)
            a = P.audit(db, "UpdateSupplierItem", exe, effect_class="master_data_change", subject_table="supplier_item", subject_id=items_cp[0]["target_id"], proposal_bound=True)
            ins(db, "change_proposal_execution_item", change_proposal_execution_id=exe_id, item_index=0, audit_record_id=a)
            P.set_state(db, cp, "closed", closed_reason="fulfilled")
            TRACE.step("system", "executing consumer", "UpdateSupplierItem", "The executor updates the lead-time parameter",
                       "Hệ thống cập nhật thông số thời gian dẫn", mode=f"system on behalf of {pm['name']} (the approver, A13)", rule="ADR-0024 rule 23; ADR-0029 rule 3",
                       outputs={"supplier_item": "Delta / FRAME-L", "supplier_processing_days": "8 -> 14", "effect": "the next planning run plans FRAME-L earlier"})
    # conversion of the Delta planned orders: by the executor (c1, c2) or directly by the planner (otherwise; no policy point)
    if conv:
        conv_actor, conv_user, how = P.system_for(pm), pm, f"system on behalf of {pm['name']} (the approver whose approval completed the plan, A13)"
    else:
        conv = delta_orders
        conv_actor, conv_user, how = P.system_for(planner), planner, f"the planner converts directly (ConvertPlannedOrder, no policy point, ADR-0043 rule 17); drafts as system on behalf of {planner['name']}"
        P.audit(db, "ConvertPlannedOrder", pa, subject_table="planned_order", subject_id=conv[0]["id"])
    rr = new_id("replenishment_request")
    ins(db, "replenishment_request", id=rr, requested_by_user_id=conv_user["id"])
    for i, o in enumerate(conv, 1):
        upd(db, "planned_order", {"id": o["id"]}, state="converted")
        ins(db, "replenishment_request_line", replenishment_request_id=rr, line_number=i, origin_planned_order_id=o["id"], item_id=W.items[o["item"]]["id"],
            warehouse_id=W.wh, order_type="purchase", supplier_partner_id=o["supplier"], quantity=o["order_quantity"], uom_id=o["order_uom"],
            uom_numerator=o["f"].numerator, uom_denominator=o["f"].denominator, uom_factor_source=o["source"], inventory_quantity=o["quantity"],
            need_date=o["need_date"], release_date=o["release_date"])
        if cp and items_cp[0]["command_type"] == "ConvertPlannedOrder":
            a = P.audit(db, "ConvertPlannedOrder", conv_actor, subject_table="planned_order", subject_id=o["id"], proposal_bound=True)
            ins(db, "change_proposal_execution_item", change_proposal_execution_id=exe_id, item_index=i - 1, audit_record_id=a)
    if cp and items_cp[0]["command_type"] == "ConvertPlannedOrder":
        P.set_state(db, cp, "closed", closed_reason="fulfilled")
    ev = [P.emit(db, "PlannedOrderConverted", "planned_order", conv[0]["id"], conv_actor, "ConvertPlannedOrder"),
          P.emit(db, "ReplenishmentRequested", "replenishment_request", rr, conv_actor, "RequestReplenishment")]
    pr_lines = []
    for i, o in enumerate(conv, 1):
        it = W.items[o["item"]]
        pr_lines.append(("purchase_request_line", dict(id=new_id("purchase_request_line"), purchase_request_id="__DOC__", line_number=i, item_id=it["id"],
                                                       quantity=o["order_quantity"], uom_id=o["order_uom"], uom_numerator=o["f"].numerator,
                                                       uom_denominator=o["f"].denominator, uom_factor_source=o["source"], inventory_quantity=o["quantity"], warehouse_id=W.wh,
                                                       requested_date=o["need_date"], suggested_supplier_id=o["supplier"], origin_planned_order_id=o["id"])))
    prq = P.create_doc(db, "purchase_request", conv_actor, header={"buyer_id": W.employee["buyer"], "document_date": W.today}, lines=pr_lines,
                       number=P.next_number(db, "purchase_request", "PRQ"), owner_employee_id=W.employee["buyer"])
    for lid, item, q, rdate, opo in db.all("select id, item_id, inventory_quantity, requested_date, origin_planned_order_id from purchase_request_line where purchase_request_id=%s", (prq["id"],)):
        ins(db, "demand_supply_line", id=new_id("demand_supply_line"), item_id=item, warehouse_id=W.wh, direction="supply", open_quantity=q, requested_date=rdate,
            source_kind="purchase_request_line", purchase_request_line_id=lid, origin_planned_order_id=opo, hold_reasons=["not_approved"])
    P.audit(db, "CreatePurchaseRequest", conv_actor, doc=prq, subject_table="purchase_request", subject_id=prq["id"])
    W.prq, W.converter = prq, conv_user
    P.resolve_item(db, fitem["id"], "planned orders converted")
    ev.append(P.emit(db, "PurchaseRequestCreated", "purchase_request", prq["id"], conv_actor, "CreatePurchaseRequest"))
    TRACE.step("system", "inventory request_replenishment + purchasing consumer of ReplenishmentRequested", "ConvertPlannedOrder x" + str(len(conv)) + " -> CreatePurchaseRequest",
               "The Delta planned orders are converted; purchasing drafts one purchase request", "Chuyển các đơn kế hoạch của Delta; mua hàng soạn một đề nghị mua",
               mode=how, rule="ADR-0024 rule 22; ADR-0047 rule 9 (A20 converter wording); ADR-0055 rule 16 note (A13)",
               outputs={"replenishment_request": len(conv), "purchase_request": prq["number"], "lines": [f"{o['item']} {fmt(o['quantity'])}" for o in conv],
                        "drafted_on_behalf_of": conv_user["name"], "supply_rows": "unreleased until approval"}, events=ev)

    # 4 the planner converts the production planned order directly (no policy point): draft production order in the same transaction
    with db.tx():
        upd(db, "planned_order", {"id": po_prod}, state="converted")
        prod_id = new_id("document")
        conv_actor = P.system_for(planner)
        comps = db.all("select line_number, component_item_id, quantity, requested_date, id from planned_order_component where planned_order_id=%s order by line_number", (po_prod,))
        lines = [("production_order_component", dict(id=new_id("production_order_component"), production_order_id="__DOC__", line_number=n, component_item_id=it,
                                                     required_quantity=q, issue_warehouse_id=W.wh, consumption_method="manual", requested_date=rdt))
                 for n, it, q, rdt, _ in comps]
        lines.append(("production_order_output", dict(id=new_id("production_order_output"), production_order_id="__DOC__", line_number=1, output_item_id=cfg_item,
                                                      output_type="main", planned_quantity=W.dsl[1]["qty"], requested_date=need)))
        prod = P.create_doc(db, "production_order", conv_actor, doc_id=prod_id, header={"order_type": "standard", "item_id": cfg_item, "production_warehouse_id": W.wh,
                                                                                         "production_version_id": W.pv, "bill_of_materials_revision_id": W.bom_rev,
                                                                                         "product_configuration_id": W.cfg_id, "good_quantity": W.dsl[1]["qty"],
                                                                                         "planned_output_quantity": W.dsl[1]["qty"], "planned_start_date": start,
                                                                                         "planned_end_date": finish, "scheduling_direction": "backward",
                                                                                         "origin_planned_order_id": po_prod, "for_demand_supply_line_id": W.dsl[1]["id"]},
                            lines=lines, number=P.next_number(db, "production_order", "MO"))
        for cid, it, q, rdt in db.all("select id, component_item_id, required_quantity, requested_date from production_order_component where production_order_id=%s", (prod_id,)):
            ins(db, "demand_supply_line", id=new_id("demand_supply_line"), item_id=it, warehouse_id=W.wh, direction="demand", open_quantity=q, requested_date=rdt,
                source_kind="production_order_component", production_order_component_id=cid, origin_planned_order_id=po_prod, hold_reasons=["not_approved"])
        out = db.val("select id from production_order_output where production_order_id=%s", (prod_id,))
        ins(db, "demand_supply_line", id=new_id("demand_supply_line"), item_id=cfg_item, warehouse_id=W.wh, direction="supply", open_quantity=W.dsl[1]["qty"],
            requested_date=need, source_kind="production_order_output", production_order_output_id=out, for_demand_supply_line_id=W.dsl[1]["id"],
            origin_planned_order_id=po_prod, hold_reasons=["not_approved"])
    P.audit(db, "ConvertPlannedOrder", pa, subject_table="planned_order", subject_id=po_prod)
    W.production_order = prod
    TRACE.step("person", f"{planner['name']} (production_planner)", "ConvertPlannedOrder (production)", "The planner converts the production planned order",
               "Kế hoạch viên chuyển đơn sản xuất kế hoạch thành lệnh sản xuất", mode="direct; no policy point (ADR-0043 rule 17); "
               "production.contract.create_production_order_from_plan in the same transaction (system on behalf of the converter)",
               rule="ADR-0024 rule 22; ADR-0036 rule 12; ADR-0034 rule 4", outputs={"production_order": prod["number"], "state": "draft", "components": len(comps),
                                                                                    "output_supply_for": "sales order line 1 (for_demand_supply_line_id)"},
               events=[P.emit(db, "ProductionOrderCreated", "production_order", prod_id, conv_actor, "ConvertPlannedOrder")])
    est = W.estimate
    pin = {"amount": est * W.dsl[1]["qty"], "has_component_shortage": True, "is_content_edited": False, "is_rework": False}
    dec, res = P.submit(db, prod, pa, pin, "SubmitProductionOrder")
    TRACE.step("person", f"{planner['name']} (production_planner)", "SubmitProductionOrder (release)", "The planner releases the production order: the company rule asks for approval",
               "Kế hoạch viên phát hành lệnh sản xuất: quy tắc công ty yêu cầu duyệt", mode="direct", rule="ADR-0034 rule 5 (P13 inputs); DS-17 sample rule; ADR-0055 rule 2 (pool mo)",
               inputs=pin, outputs={"state": P.doc_state(db, prod_id)}, decision=P.decision_summary(dec), policy=[P.policy_line(dec)], events=res["events"], work_items=res["items"])
    approval_walk(db, prod, "owner", "Release for the Gamma Showroom order; FRAME-L expedited", "ApproveProductionOrder",
                  "The owner approves the release", "Giám đốc duyệt phát hành lệnh sản xuất", "ADR-0055 rule 7 (the planner, as converter, is a writer)")
    co = new_id("cost_object")
    ins(db, "cost_object", id=co, code=f"CO-{prod['number']}", name=f"Production order {prod['number']}", kind="production_order", production_order_id=prod_id)
    upd(db, "production_order", {"id": prod_id}, cost_object_id=co)
    W.cost_object = co
    W.code_of[co] = f"CO-{prod['number']}"
    db.x("update demand_supply_line set hold_reasons='{}' where production_order_component_id in (select id from production_order_component where production_order_id=%s) or production_order_output_id=%s", (prod_id, out))
    TRACE.step("system", "production handler in the approval's transaction", "release: cost object + rows", "Approval opens the cost object and releases the rows",
               "Duyệt xong: mở đối tượng tập hợp chi phí và giải phóng nhu cầu", mode="same transaction, deterministic", rule="ADR-0035 rule 1; ADR-0047 rules 18-19 (B2)",
               outputs={"cost_object": f"CO-{prod['number']}", "component_demand_rows": len(comps), "output_supply_row": 1})
    # checks
    TRACE.check("forecast tier is unindexed (12 weeks) with forecast_history_insufficient", tier == "unindexed" and "forecast_history_insufficient" in checks, tier, "holistic F0")
    TRACE.check("the production planned order is pegged to the sales order line", db.val("select count(*) from planned_order_pegging where planned_order_id=%s and demand_supply_line_id=%s", (po_prod, W.dsl[1]["id"])) == 1)
    TRACE.check("FRAME-L shortage inside lead time raised a work item for the buyer", any(e["kind"] == "shortage_inside_lead_time" and e["item"] == "FRAME-L" for e in exc_rows))
    TRACE.check("the planning run was never tainted", db.val("select tainted_at is null from agent_run where id=%s", (run_["id"],)))
    TRACE.check("the purchase request was drafted on behalf of the converter (the approver when the proposal converted, A13)",
                db.val("select on_behalf_of_id from document_version where document_id=%s and version=1", (prq["id"],)) == W.converter["id"], W.converter["name"], "ADR-0055 rule 16 note")
    TRACE.check("the production order was created in the conversion's transaction with origin_planned_order_id",
                db.val("select origin_planned_order_id from production_order where id=%s", (prod_id,)) == po_prod)
    return True
