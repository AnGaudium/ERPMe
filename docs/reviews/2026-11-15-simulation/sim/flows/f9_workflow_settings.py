"""Flow 9: configured workflows and settings (ADR-0058 rules 8-13, 18-24; ADR-0059 rules 6, 12; ADR-0063 rules 2-4).
A decision table routes a review and an automation rule raises it, both acting as system on behalf of the rule's owner and
inside the owner's record scope; a setting tightening is one person's immediate act, a loosening needs an approved proposal
from someone else, and the loosened value outdates the evidence of the enabled auto-post rule. No LLM call."""
import datetime as dt
import uuid
from decimal import Decimal as D

from .core import TRACE, W, ins, upd, new_id, now, sha, set_day
from . import platform as P
from . import commerce as C
from . import xdesign as X
from .common import approval_walk, probe

ROUTE_INPUTS = [{"code": "x", "type": "amount", "domain": [0, 10 ** 15]}]
ROUTE_ROWS = [{"cells": {"x": {"min": 20000000, "max": 50000000}}, "out": {"reviewer_role": "purchasing_manager"}},
              {"cells": {"x": {"min": 50000000}}, "out": {"reviewer_role": "chief_accountant"}}]


def run(db):
    TRACE.start_flow(9, "Workflow configuration and settings", "Cấu hình quy trình và thiết lập",
                     "A decision table and an automation rule route a purchase-order review, acting for their owner and only inside the owner's scope; "
                     "a setting tightening is immediate, a loosening needs another person's approval and outdates the stored auto-post evidence.")
    set_day("2026-11-30")
    T = X.lab("t22_workflows")
    owner, pm, buyer, ca = (W.user[k] for k in ("owner", "purchasing_manager", "buyer", "chief_accountant"))
    oa, pma, ba, caa = (P.person(k) for k in ("owner", "purchasing_manager", "buyer", "chief_accountant"))
    # simulation assumption (design gap): in the role templates only owner and it_administrator hold leaf configuration, and the
    # it_administrator cannot approve proposals, so an activation drafted by the owner has no eligible approver; the purchasing
    # manager gets configuration edit here so that she drafts and submits and the owner approves
    P.ROLE_LEVELS.setdefault("purchasing_manager", {})["configuration"] = ("edit", False)
    P.TYPE_NODE.update({"artifact_version_state": "configuration", "company_setting": "policy", "automation_rule": "configuration"})
    bolt, CART = W.items["BOLT-M8"], W.uom["x-carton"]

    # 1 a second warehouse; the purchasing manager's assignment is scoped to WH1 ------------------------------------------------
    wh2, zn2, bn2 = new_id("warehouse"), new_id("zone"), new_id("bin")
    with db.tx():
        ins(db, "warehouse", id=wh2, code="WH2", name="Branch store (sample)", kind="physical", default_bin_id=bn2, working_calendar_id=W.cal)
        ins(db, "zone", id=zn2, warehouse_id=wh2, code="DEFAULT", name="Default")
        ins(db, "bin", id=bn2, warehouse_id=wh2, zone_id=zn2, code="DEFAULT", barcode="WH2-DEFAULT", bin_type="storage")
    W.code_of[wh2] = "WH2"
    ra = db.val("select id from role_assignment where user_account_id=%s", (pm["id"],))
    ins(db, "role_assignment_scope", role_assignment_id=ra, warehouse_id=W.wh)
    P.audit(db, "UpdateRoleAssignment", oa, subject_table="role_assignment", subject_id=ra)
    cells = [{"branch": "all", "warehouse": str(w), "level": lvl} for (w,), lvl in
             zip(db.all("select warehouse_id from role_assignment_scope where role_assignment_id=%s", (ra,)),
                 [db.val("select owner_scope_read from role_assignment where id=%s", (ra,))])]
    TRACE.step("person", f"{owner['name']} (owner)", "CreateWarehouse + UpdateRoleAssignment", "A branch store WH2 opens; the purchasing manager covers WH1 only",
               "Mở kho chi nhánh WH2; trưởng phòng mua hàng chỉ phụ trách WH1", mode="direct", rule="ADR-0054 rules 13-15",
               outputs={"warehouse": "WH2", "purchasing_manager_scope": [{"warehouse": "WH1", "owner_scope_read": cells[0]["level"]}]})

    # 2 the decision table and the automation rule, drafted by their owner -----------------------------------------------------------
    dt_id, dtv = new_id("decision_table"), new_id("decision_table_version")
    table = {"inputs": ROUTE_INPUTS, "outputs": [{"code": "reviewer_role", "type": "role_template"}], "rows": ROUTE_ROWS, "policy": "unique"}
    tests_t = [{"x": 25000000, "expect": "purchasing_manager"}, {"x": 75000000, "expect": "chief_accountant"}, {"x": 5000000, "expect": "decision_no_match"}]
    test_res = []
    for t in tests_t:
        r = T.evaluate_table(table, {"x": t["x"]})
        test_res.append({**t, "got": r if isinstance(r, str) else r["reviewer_role"]})
    with db.tx():
        ins(db, "decision_table", id=dt_id, code="po_review_route", name="Purchase order review route (sample)", owner_user_id=pm["id"], recorded_at=now())
        ins(db, "decision_table_version", id=dtv, decision_table_id=dt_id, version=1, hit_policy="unique", inputs=[{"code": "amount_company", "type": "amount", "domain": {"min": 0}}],
            outputs=table["outputs"], tests=tests_t, content_hash=sha(table), registry_version="0.1.0", drafted_by_kind="human", drafted_by_id=pm["id"],
            on_behalf_of_id=pm["id"], drafting_window_to=W.today, recorded_at=now())
        for n, r in enumerate(ROUTE_ROWS, 1):
            ins(db, "decision_table_row", decision_table_version_id=dtv, row_number=n, cells={"amount_company": r["cells"]["x"]}, outputs=r["out"], recorded_at=now())
    rule = {"trigger_event_type": "PurchaseOrderSubmitted", "conditions": [{"field": "amount_company", "operator": "ge", "value": 20000000}],
            "actions": [{"kind": "raise_work_item", "work_item_kind": "automation_task", "owner": {"decision_table_version_id": str(dtv), "output": "reviewer_role",
                                                                                                 "no_match": "skip"}, "due_days": 1,
                         "text": "Review this purchase order before it is sent"}]}
    ar, arv = new_id("automation_rule"), new_id("automation_rule_version")
    with db.tx():
        ins(db, "automation_rule", id=ar, code="large_po_review", name="Large purchase order review (sample)", owner_user_id=pm["id"], owner_scope={"cells": cells},
            recorded_at=now())
        ins(db, "automation_rule_version", id=arv, automation_rule_id=ar, version=1, trigger_event_type=rule["trigger_event_type"], conditions=rule["conditions"],
            actions=rule["actions"], tests=[{"event": {"amount_company": 25000000}, "expect": "acted"}], decision_table_version_ids=[dtv],
            content_hash=sha(rule), registry_version="0.1.0", drafted_by_kind="human", drafted_by_id=pm["id"], on_behalf_of_id=pm["id"],
            drafting_window_to=W.today, recorded_at=now())
    P.audit(db, "CreateAutomationRuleVersion", pma, subject_table="automation_rule", subject_id=ar, draft_only=True)
    upd(db, "decision_table_version", {"id": dtv}, state="backtested")
    ok_pin, msg_pin = probe(db, "rule leaves draft before its table is active", lambda: upd(db, "automation_rule_version", {"id": arv}, state="backtested"))
    read_ok, read_why = P.can(pm, "GetPurchaseOrder", node="purchase_order")
    TRACE.step("person", f"{pm['name']} (purchasing_manager)", "CreateDecisionTableVersion + CreateAutomationRuleVersion",
               "The owner drafts a route table and a rule: amount >= 20 M raises a review for the routed role", "Chủ sở hữu soạn bảng định tuyến và quy tắc: >= 20 triệu thì giao xem xét",
               mode="drafts (is_draft_only); conditions are triples, no script", rule="ADR-0058 rules 2, 8, 18-20, 22",
               outputs={"decision_table": {"code": "po_review_route", "hit_policy": "unique", "rows": [{"amount_company": r["cells"]["x"], **r["out"]} for r in ROUTE_ROWS],
                                           "tests": test_res},
                        "rule": {"code": "large_po_review", **rule}, "owner_read_right_on_subject": read_why},
               deterministic="stored tests run by evaluate_table: half-open ranges, unique hit policy, decision_no_match below 20 M",
               notes=["the table version reaches backtested after its tests; the rule version cannot: " + msg_pin,
                      "so a new rule and the new table it pins cannot both be backtested before one activation proposal (design gap)"])
    TRACE.check("the database refuses a rule version leaving draft while its pinned table version is only backtested", ok_pin, msg_pin, "ADR-0058 rule 20")
    TRACE.check("the route table's stored tests pass (25 M -> purchasing_manager, 75 M -> chief_accountant, 5 M -> no match)",
                all(t["got"] == t["expect"] for t in test_res), test_res, "ADR-0058 rules 19, 22")

    # 3 activation through a change proposal: the owner submits (consent), another person approves ---------------------------------
    cp, dec, res = X.person_proposal(db, "purchasing_manager", "CP rule activation", "Activate large_po_review v1 with po_review_route v1",
                                     [("SetArtifactVersionState", {"automation_rule_version_id": str(arv), "state": "active"}, "automation_rule_version",
                                       [{"field": "state", "new": "active"}]),
                                      ("SetArtifactVersionState", {"decision_table_version_id": str(dtv), "state": "active"}, "decision_table_version",
                                       [{"field": "state", "new": "active"}])])
    TRACE.step("person", f"{pm['name']} (purchasing_manager)", "SubmitChangeProposal (SetArtifactVersionState)", "The owner submits the activation, which records her consent",
               "Chủ sở hữu gửi đề xuất kích hoạt, đồng thời ghi nhận sự đồng ý", mode="direct; SetArtifactVersionState is proposal-bound", rule="ADR-0058 rules 9, 24",
               decision=P.decision_summary(dec), events=res["events"], work_items=res["items"])
    approval_walk(db, cp, ["owner", "chief_accountant"], "Review route checked against the tests", "ApproveChangeProposal",
                  "The owner approves the activation", "Giám đốc duyệt kích hoạt", "ADR-0058 rule 24 (neither the submitter nor the drafter)")
    with db.tx():
        upd(db, "decision_table_version", {"id": dtv}, state="active", effective_from=W.today, change_proposal_id=cp["id"])
        upd(db, "decision_table", {"id": dt_id}, current_version_id=dtv)
        upd(db, "automation_rule", {"id": ar}, owner_confirmed_at=now(), owner_confirmed_user_id=pm["id"])
        upd(db, "automation_rule_version", {"id": arv}, state="backtested")      # possible only now that the pinned table is active
        upd(db, "automation_rule_version", {"id": arv}, state="active", effective_from=W.today, change_proposal_id=cp["id"])
        upd(db, "automation_rule", {"id": ar}, current_version_id=arv)
        P.set_state(db, cp, "closed", closed_reason="fulfilled")
    P.audit(db, "SetArtifactVersionState", P.system_for(owner), subject_table="automation_rule_version", subject_id=arv, proposal_bound=True)
    TRACE.step("system", "executor of the approved proposal (under the configuration_state lock)", "SetArtifactVersionState x2",
               "The table and the rule become active; the pointer moves", "Bảng và quy tắc có hiệu lực; con trỏ phiên bản dịch chuyển",
               mode="execution of the approved proposal", rule="ADR-0058 rules 21, 24; ADR-0059 rule 12",
               outputs={"automation_rule.current_version_id": "large_po_review v1", "owner_confirmed": pm["name"], "effective_from": W.today})

    # 4 two purchase orders are submitted: WH1 (in the owner's scope) and WH2 (outside it) --------------------------------------------
    def order(actor, wh, cartons):
        lp = C.price_line(db, W.price_lists["BUY-OMEGA"], W.today, D(cartons), "x-carton", item=bolt["id"])
        po = P.create_doc(db, "purchase_order", actor, header={"partner_id": W.partners["S-OMEGA"], "partner_name": "Omega Fasteners (sample)", "currency": "VND",
                                                              "price_list_id": W.price_lists["BUY-OMEGA"], "payment_term_id": W.terms["NET30"]["id"],
                                                              "buyer_id": W.employee["buyer"], "document_date": W.today},
                          lines=[("purchase_order_line", dict(id=new_id("purchase_order_line"), purchase_order_id="__DOC__", line_number=1, item_id=bolt["id"],
                                                              quantity=D(cartons), uom_id=CART, uom_numerator=24, uom_denominator=1, uom_factor_source="product",
                                                              inventory_quantity=D(cartons * 24), warehouse_id=wh, requested_date=W.today + dt.timedelta(days=7),
                                                              list_unit_price=lp["list_price"], net_unit_price=lp["net_unit_price"], line_amount=lp["amount"]))],
                          number=P.next_number(db, "purchase_order", "PO"), partner_id=W.partners["S-OMEGA"])
        C.write_steps(db, po["id"], 1, lp["list_price"], lp["net_unit_price"], lp["amount"])
        d_, r_ = P.submit(db, po, actor, {"amount": lp["amount"]}, "SubmitPurchaseOrder")
        ev = next(e for e in r_["events"] if e["event"] == "PurchaseOrderSubmitted")
        return po, lp["amount"], ev

    def dispatch(po, amount, ev, wh):
        """automation_dispatch for one event: version in force, owner scope, facts, conditions, guards, then each action."""
        evrow = db.one("select causation_chain_id, causation_depth from outbox_event where id=%s", (ev["id"],))
        in_scope = any(c["warehouse"] in ("all", str(wh)) for c in cells)
        if not in_scope:
            n = db.val("select skipped_count from automation_scope_skip where automation_rule_id=%s and business_date=%s", (ar, W.today))
            if n:
                db.x("update automation_scope_skip set skipped_count=skipped_count+1 where automation_rule_id=%s and business_date=%s", (ar, W.today))
            else:
                ins(db, "automation_scope_skip", automation_rule_id=ar, business_date=W.today, skipped_count=1, recorded_at=now())
            return {"evaluated": False, "reason": "outside the owner's record scope (not a match, counted)"}, None
        facts = {"amount_company": int(amount), "warehouse": "WH1"}
        cond = [{"field": c["field"], "operator": c["operator"], "value": c["value"], "read": facts[c["field"]],
                 "result": T.eval_condition("amount", c["operator"], c["value"], facts[c["field"]])} for c in rule["conditions"]]
        route = T.evaluate_table(table, {"x": int(amount)})
        role = None if route == "decision_no_match" else route["reviewer_role"]
        exe = new_id("automation_execution")
        actions = []
        if all(c["result"] for c in cond) and role:
            X_actor = P.system_for(pm)
            P.CHAIN_OVERRIDE.update({"id": evrow[0], "depth": evrow[1] + 1, "rule": arv})
            try:
                wi = P.raise_item(db, "automation_task", "automation_execution", exe, ("role", role), due_days=1,
                                  details={"text": rule["actions"][0]["text"], "purchase_order": po["number"], "rule": "large_po_review v1"},
                                  open_key=f"automation:{arv}:{ev['id']}:1")
                aid = P.audit(db, "RaiseAutomationWorkItem", X_actor, subject_table="automation_execution", subject_id=exe, draft_only=True, internal_only=True)
            finally:
                P.CHAIN_OVERRIDE.clear()
            actions.append({"kind": "raise_work_item", "command": "RaiseAutomationWorkItem", "key": f"automation:{arv}:{ev['id']}:1", "outcome": "done",
                            "audit_record": str(aid), "owner": f"role {role}"})
        ins(db, "automation_execution", id=exe, automation_rule_id=ar, automation_rule_version_id=arv, mode="live", event_id=ev["id"], event_type="PurchaseOrderSubmitted",
            business_date=W.today, subject_table="purchase_order", subject_id=po["id"], subject_version=po["version"], warehouse_id=wh, document_id=po["id"],
            causation_chain_id=evrow[0], causation_depth=evrow[1], outcome="acted" if actions else "skipped", condition_results=cond,
            input_hash=sha(facts), action_results=actions, is_tainted=False, on_behalf_of_id=pm["id"], recorded_at=now())
        P.audit(db, "RecordAutomationExecution", P.system_for(pm), subject_table="automation_execution", subject_id=exe, internal_only=True)
        return {"evaluated": True, "conditions": cond, "route": route, "actions": actions, "chain": str(evrow[0]), "event_depth": evrow[1]}, aid if actions else None

    poA, amtA, evA = order(ba, W.wh, 100)
    outA, aidA = dispatch(poA, amtA, evA, W.wh)
    adepth = db.one("select causation_depth, automation_rule_version_id, actor_kind, on_behalf_of_id from audit_record where id=%s", (aidA,))
    TRACE.step("system", "consumer automation_dispatch (system on behalf of the rule's owner)", "RaiseAutomationWorkItem + RecordAutomationExecution",
               f"{poA['number']} (WH1, {amtA:,.0f}) matches: the table routes the review to the purchasing manager",
               f"{poA['number']} (WH1) khớp: bảng định tuyến giao xem xét cho trưởng phòng mua hàng", mode="transactional consumer; each action in its own savepoint",
               rule="ADR-0058 rules 9-13, 17, 20", inputs={"event": "PurchaseOrderSubmitted", "purchase_order": poA["number"]},
               outputs={**outA, "action_audit": {"causation_depth": adepth[0], "automation_rule_version_id": "large_po_review v1" if adepth[1] == arv else adepth[1],
                                                  "actor_kind": adepth[2], "on_behalf_of": pm["name"] if str(adepth[3]) == str(pm["id"]) else adepth[3]}},
               deterministic="facts read once with the owner's scope; conditions and the pinned table version evaluated before any action; idempotency key per action")
    poB, amtB, evB = order(oa, wh2, 120)
    outB, _ = dispatch(poB, amtB, evB, wh2)
    skips = db.val("select skipped_count from automation_scope_skip where automation_rule_id=%s and business_date=%s", (ar, W.today))
    n_exec_B = db.val("select count(*) from automation_execution where subject_id=%s", (poB["id"],))
    TRACE.step("system", "consumer automation_dispatch", "(not evaluated) + automation_scope_skip", f"{poB['number']} (WH2, {amtB:,.0f}) is outside the owner's scope: not evaluated, counted",
               f"{poB['number']} (WH2) ngoài phạm vi của chủ sở hữu: không đánh giá, chỉ đếm", mode="transactional consumer", rule="ADR-0058 rule 9",
               outputs={**outB, "automation_scope_skip": skips, "executions_recorded": n_exec_B})
    TRACE.check("the rule acted once inside the owner's scope, as system for the owner, at chain depth 1 with its rule version",
                outA["evaluated"] and outA["actions"] and adepth[0] == 1 and adepth[1] == arv and adepth[2] == "system" and str(adepth[3]) == str(pm["id"]), adepth, "ADR-0058 rules 9, 12")
    TRACE.check("the WH2 order is not evaluated and only counted (automation_scope_skip = 1, no execution row)", not outB["evaluated"] and skips == 1 and n_exec_B == 0,
                {"skips": skips, "executions": n_exec_B}, "ADR-0058 rule 9")

    # 5 settings: a tightening is immediate -----------------------------------------------------------------------------------------
    X.load_setting_definitions(db)
    S = X.lab("t24_settings")
    k_t = "cash.bank_charge.min_evidence_lines"
    sid_t, kind_t, repl_t = X.write_setting(db, k_t, 8, ca, "Bank charges need two more months of clean lines")
    P.audit(db, "UpdateCompanySetting", caa, subject_table="setting_value", subject_id=sid_t, human_only=True)
    TRACE.step("person", f"{ca['name']} (chief_accountant)", "UpdateCompanySetting (tighten)", f"{k_t}: 6 -> 8, in force at once",
               f"{k_t}: 6 -> 8, có hiệu lực ngay", mode="direct, human_only; one person holding edit on the leaf", rule="ADR-0063 rule 3",
               outputs={"replaced_value": repl_t, "value": 8, "change_kind": kind_t, "effective_from": W.today, "in_force_now": X.get_setting(db, k_t)},
               deterministic="trg_setting_value_check_insert derives the replaced value and the change kind from the direction higher_tighter")
    TRACE.check("a tightening is accepted directly and is in force the same day", kind_t == "tighten" and X.get_setting(db, k_t) == 8, kind_t, "ADR-0063 rule 3")

    # 6 an enabled auto-post rule with stored evidence (company history), then a loosening by proposal ----------------------------------
    prl, prv = new_id("policy_rule"), new_id("policy_rule_version")
    evidence = {"proposals": 312, "posted_unchanged": 310, "statement_months": 2, "max_error_rate_percent": 1, "rule_of_three_min": 300}
    ins(db, "policy_rule", id=prl, code="bank_receipt_auto_post")
    ins(db, "policy_rule_version", id=prv, policy_rule_id=prl, version=1, effective_from=dt.date(2026, 11, 2), action="post", document_type="bank_receipt",
        actor_kind="system", effect="allow", owner_user_id=ca["id"], amount_company_max=D(50000000), is_confirmation_required=True, is_enabled=True,
        shadow_evidence=evidence)
    k_l = "auto_post.max_error_rate"
    try:
        S.update_setting(S.S[k_l], D(1), D(2), str(ca["id"]), {"policy": "full"})
        refused = None
    except ValueError as e:
        refused = str(e)
    ok_db, msg_db = probe(db, "loosen without proposal", lambda: X.write_setting(db, k_l, 2, ca, "direct attempt"))
    TRACE.step("person", f"{ca['name']} (chief_accountant)", "UpdateCompanySetting (loosen, direct)", f"{k_l}: 1 -> 2 directly is refused",
               f"{k_l}: 1 -> 2 trực tiếp bị từ chối", mode="direct attempt; then a database probe", rule="ADR-0063 rule 3; DS-28 ck_setting_value_loosen",
               status="rejected (expected)", outputs={"command": refused, "database": msg_db,
                                                       "enabled_auto_post_rule": {"code": "bank_receipt_auto_post", "evidence": evidence}})
    cp2, dec2, res2 = X.person_proposal(db, "owner", "CP setting loosen", "Allow 2% error on proven bank auto-posting",
                                        [("UpdateCompanySetting", {"key": k_l, "value": 2, "scope": "company"}, "setting_value", [{"field": k_l, "old": 1, "new": 2}])])
    TRACE.step("person", f"{owner['name']} (owner)", "SubmitChangeProposal (UpdateCompanySetting)", "The owner submits the loosening as a proposal with a reason",
               "Nới lỏng được gửi thành đề xuất kèm lý do", mode="direct", rule="ADR-0063 rule 3; ADR-0029", decision=P.decision_summary(dec2), events=res2["events"],
               work_items=res2["items"], notes="the chief accountant holds policy at full but no change_proposal edit (role templates), so the owner submits and she approves")
    el_self = P.eligibility(db, cp2, cp2["decision"], owner, "ApproveChangeProposal")
    approval_walk(db, cp2, ["chief_accountant"], "Error ceiling 2% accepted for proven paths", "ApproveChangeProposal", "The chief accountant approves the loosening",
                  "Kế toán trưởng duyệt nới lỏng", "ADR-0063 rule 3 (leaf at full, not the submitter)")
    owner_full = P.row_for("chief_accountant", "policy")[0][0]
    with db.tx():
        sid_l, kind_l, repl_l = X.write_setting(db, k_l, 2, owner, "Allow 2% error on proven bank auto-posting", proposal=cp2["id"], approver=ca["id"])
        outdated = []
        if db.val("select outdates from setting_definition where setting_key=%s", (k_l,)) == "auto_post" and kind_l == "loosen":
            for (v,) in db.all("""select id from policy_rule_version where is_enabled and action='post' and effect='allow' and actor_kind in ('system','integration')
                                  and shadow_evidence is not null and shadow_evidence_outdated_by is null"""):
                upd(db, "policy_rule_version", {"id": v}, shadow_evidence_outdated_by=sid_l)
                outdated.append(str(v))
        P.set_state(db, cp2, "closed", closed_reason="fulfilled")
    P.audit(db, "UpdateCompanySetting", P.system_for(ca), subject_table="setting_value", subject_id=sid_l, proposal_bound=True)
    may_post = db.val("select shadow_evidence_outdated_by is null from policy_rule_version where id=%s", (prv,))
    TRACE.step("system", "executor of the approved proposal", "UpdateCompanySetting (loosen) + mark evidence outdated",
               f"{k_l} = 2 from today; the auto-post rule's evidence is outdated and it stops auto-posting",
               f"{k_l} = 2 từ hôm nay; bằng chứng của quy tắc tự ghi sổ hết hiệu lực, quy tắc ngừng tự ghi sổ", mode="same transaction as the setting row",
               rule="ADR-0063 rule 3 (outdates: auto_post); ADR-0059 rule 6",
               outputs={"change_kind": kind_l, "replaced_value": repl_l, "changed_by": owner["name"], "approved_by": ca["name"], "approver_level_on_policy": owner_full,
                        "submitter_could_approve": el_self["eligible"], "outdated_rule_versions": ["bank_receipt_auto_post v1"] if outdated else [],
                        "rule_may_auto_post": bool(may_post), "re_arm": "a new rule version with new evidence"},
               notes="policy_rule_version stores no link to the setting keys its evidence depends on; for this general key every enabled auto-post rule depends on it (design gap for per-class keys)")
    TRACE.check("the loosening needed an approved proposal by someone other than the submitter", refused == "proposal_required" and ok_db and not el_self["eligible"]
                and kind_l == "loosen", {"command": refused, "db": msg_db}, "ADR-0063 rule 3")
    TRACE.check("the loosened value outdated the enabled auto-post rule's evidence", outdated == [str(prv)] and not may_post, outdated, "ADR-0063 rule 3; ADR-0059 rule 6")
    return True
