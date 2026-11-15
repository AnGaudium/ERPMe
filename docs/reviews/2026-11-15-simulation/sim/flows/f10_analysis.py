"""Flow 10: a question becomes a checked analysis plan (ADR-0060 rules 7-10, 21-24). The LLM writes only a plan of catalog
codes and, later, a narrative plan of claim codes and fact handles; code validates the plan, computes the cells, renders the
key facts and renders only the claims whose preconditions hold on the served cells. Three LLM calls (L1 plan, its retry after a typed refusal, L3 narrative)."""
import datetime as dt
from decimal import Decimal as D

from .core import TRACE, W, ins, upd, new_id, now, sha, set_day, jsonable
from . import platform as P
from . import xdesign as X
from .common import llm_step, llm_view, probe

QUESTION = "Which suppliers did we buy the most from this month?"
PLAN_SCHEMA = {"type": "object", "required": ["plan_version", "measures"], "properties": {"plan_version": {"type": "integer"},
               "measures": {"type": "array", "items": {"type": "string"}}, "dimensions": {"type": "array"}, "time": {"type": "object"},
               "with_total_row": {"type": "boolean"}}}
NARR_SCHEMA = {"type": "object", "required": ["steps"], "properties": {"steps": {"type": "array"}}}
SYS_PLAN = ("You turn a business question into an analysis plan of catalog codes only (measures, dimensions, a time range). "
            "Answer JSON {plan_version, measures, dimensions, time, with_total_row}. Never write a number from the data.")
SYS_NARR = ("You order claims about served facts. Answer JSON {steps: [{claim, facts: {role: handle}}]} using only the claim codes "
            "and fact handles offered. No free text, no member names, no numbers.")


def run(db):
    TRACE.start_flow(10, "Agent-assisted analysis", "Phân tích có trợ giúp của agent",
                     "A purchasing manager asks a question; the LLM proposes a plan of catalog codes, code validates it and computes the answer, "
                     "key facts are rendered by code, and the LLM's narrative plan is rendered only where each claim's precondition holds.")
    set_day("2026-11-30")
    A = X.lab("t18_analysis")
    pm = W.user["purchasing_manager"]
    P.BUDGET["analysis"] = (4, 20, 0.20)
    if "analysis" not in W.agent_type_ids:
        aid = new_id("agent_type")
        ins(db, "agent_type", id=aid, code="analysis", name="Analysis")
        W.agent_type_ids["analysis"] = aid
        decl = {"version": "1.0.0", "may_read_untrusted": False}
        ins(db, "agent_type_version", id=new_id("agent_type_version"), agent_type_code="analysis", version="1.0.0", content_hash=sha(decl),
            behavior_hash=sha({"b": decl}), declaration=decl, field_classes=[])

    # 1 the question ----------------------------------------------------------------------------------------------------------------
    qid = new_id("analysis_question")
    ins(db, "analysis_question", id=qid, asked_by_user_id=pm["id"], question_text=QUESTION, language="en", asked_at=now())
    P.audit(db, "AskAnalysisQuestion", P.person("purchasing_manager"), subject_table="analysis_question", subject_id=qid)
    task = P.raise_item(db, "agent_task", "analysis_question", qid, ("user", pm["id"]), due_days=1)
    run_ = P.start_run(db, "analysis", "person", task["id"], pm, started_by_kind="human", started_by=pm, subject=("analysis_question", qid))
    upd(db, "analysis_question", {"id": qid}, agent_run_id=run_["id"])
    TRACE.step("person", f"{pm['name']} (purchasing_manager)", "AskAnalysisQuestion + StartAgentRun", "A question in her own words starts an analysis run",
               "Câu hỏi bằng lời của người dùng khởi động một lượt phân tích", mode="direct; the run acts for the asker, untainted", rule="ADR-0060 rules 21-22",
               inputs={"question": QUESTION}, outputs={"analysis_question": "open", "agent_run": "analysis 1.0.0"})

    # 2 L1: the plan of catalog codes ------------------------------------------------------------------------------------------------
    catalog = ", ".join(f"{c} ({m['fact']})" for c, m in A.MEAS.items() if m["fact"] == "purchase_line_overview")
    partners = {str(p): c for p, c in db.all("select id, code from partner")}
    ctx = {"business_date": W.today, "fy_month": 1, "cutover": dt.date(2026, 1, 1), "members": {"partner": set(partners)},
           "member_count": {"partner": len(partners)}}
    actor = {"facts": set(A.FACTS) - A.NOT_OWNER_SCOPED, "classes": set(), "wide": False, "agent": True}
    base = {"plan_version": 1, "measures": ["purchase_net_amount"], "dimensions": [{"dimension": "partner"}],
            "time": {"dimension": "posting_date", "range": {"relative": "this_month"}}, "with_total_row": True}
    fixtures = [base, dict(base, limit=5, with_other_row=True)]
    feedback, attempts = "", []
    for attempt in range(2):
        plan, rec = llm_step(db, run_, "plan", "analysis", "AnalysisPlanOutput", PLAN_SCHEMA, SYS_PLAN,
                             f"Question: {QUESTION}\nBusiness date: {W.today}\nMeasures: {catalog}\nDimensions: partner, item, item_group, posting_date" + feedback,
                             fixtures[attempt])
        errs = A.validate(plan, actor, ctx)
        attempts.append({"attempt": attempt + 1, "errors": [list(e) for e in errs]})
        TRACE.step("llm", "analysis agent (LLM, seat analysis)", "L1 plan" + (" (retry with the refusal)" if attempt else ""),
                   "The LLM proposes a plan of catalog codes, no numbers" if not attempt else "The LLM corrects its plan from the typed refusal",
                   "LLM đề xuất kế hoạch chỉ gồm mã danh mục" if not attempt else "LLM sửa kế hoạch theo lỗi có kiểu", mode="agent run, untainted",
                   rule="ADR-0060 rules 7, 22", outputs={"plan": plan, "validation": [list(e) for e in errs] or "valid"},
                   llm=llm_view(rec, "Plan of catalog codes only", "validated by code" if not errs else f"refused by validate: {errs}"))
        if not errs:
            break
        feedback = "\nYour plan was refused: " + "; ".join(f"{a}: {c}" for a, _, c in errs)
    try:
        ph = A.analysis_plan_hash(plan)
    except Exception:  # noqa: BLE001
        ph = sha(plan)
    TRACE.step("det", "query layer validate_analysis_plan (pure function)", "ValidateAnalysisPlan", "Code checks every attempt against the catalog and the asker's rights",
               "Mã kiểm tra từng lần đề xuất theo danh mục và quyền của người hỏi", mode="pure function; at most 3 attempts", rule="ADR-0060 rules 8-10, 24",
               outputs={"attempts": attempts, "analysis_plan_hash": ph, "time_range": "this_month = 2026-11-01 .. 2026-11-30"})
    TRACE.check("a plan without a limit is refused (analysis_too_broad) and the corrected plan validates", errs == [] and len(attempts) == 2
                and attempts[0]["errors"] and attempts[0]["errors"][0][0] == "analysis_too_broad", attempts, "ADR-0060 rules 10, 24")

    # 3 D: the cells, computed by code from posted purchase invoices of the month ------------------------------------------------------
    rows = db.all("""select d.partner_id, sum(l.line_amount) from purchase_invoice_line l join document d on d.id=l.purchase_invoice_id
                     where d.state='posted' and d.document_date between %s and %s group by d.partner_id order by 2 desc, 1""",
                  (dt.date(2026, 11, 1), dt.date(2026, 11, 30)))
    cells, members, offered = {}, {}, {}
    for n, (pid, amt) in enumerate(rows, 1):
        cid = f"c{n}"
        members[str(pid)] = partners[str(pid)]
        cells[cid] = {"kind": "value", "row_kind": "member", "measure": "purchase_net_amount", "members": [str(pid)], "value": str(amt), "basis": "VND", "scale": 0}
        offered[f"f{n}"] = cid
    total = sum(D(c["value"]) for c in cells.values())
    cells["t"] = {"kind": "value", "row": "total", "measure": "purchase_net_amount", "members": [], "value": str(total), "basis": "VND", "scale": 0}
    A.mark_extremes(cells)
    facts = A.default_facts(cells)
    mnames = {"purchase_net_amount": "purchase net amount"}
    key_facts = [A.key_fact(f, cells, members, mnames, period="November 2026") for f in facts]
    TRACE.step("det", "query layer: compiled plan over the purchase line view + render_key_facts", "RunAnalysisPlan + key facts",
               "Code computes the cells and renders the key facts", "Mã tính các ô số liệu và trình bày các dữ kiện chính", mode="query and pure renderer",
               rule="ADR-0060 rules 12, 23", outputs={"cells": {k: {"member": members.get((v["members"] or [""])[0], "total"), "value": v["value"],
                                                                    "is_max": v.get("is_max"), "is_min": v.get("is_min")} for k, v in cells.items()},
                                                     "key_facts": key_facts},
               deterministic="sum of posted purchase invoice line amounts by supplier for the month; unique maximum and minimum marked; templates fill the numbers")
    TRACE.check("key facts are rendered by code from the computed cells", any(f"{D(cells['t']['value']):,.0f}" in k for k in key_facts), key_facts, "ADR-0060 rule 23")

    # 4 L3: the narrative plan; code renders only claims whose preconditions hold ----------------------------------------------------
    hs = list(offered)
    narr, rec2 = llm_step(db, run_, "narrate", "analysis", "AnalysisNarrativeOutput", NARR_SCHEMA, SYS_NARR,
                          "Claims: " + ", ".join(A.CLAIMS["en"]) + "\nFacts: " + ", ".join(f"{h} = member row {i + 1}" for i, h in enumerate(hs)),
                          {"steps": [{"claim": "largest_value", "facts": {"fact": hs[0]}}, {"claim": "largest_value", "facts": {"fact": hs[-1]}},
                                     {"claim": "smallest_value", "facts": {"fact": hs[-1]}}]})
    steps = narr["steps"]
    nerr = A.validate_narrative(steps, offered, cells)
    sentences, dropped = A.render_narrative(steps, offered, cells, members, mnames, {"member_rows": len(rows), "truncated": False})
    TRACE.step("llm", "analysis agent (LLM, seat analysis)", "L3 narrative plan", "The LLM orders claims by code and handle only",
               "LLM sắp xếp các nhận định chỉ bằng mã và tham chiếu", mode="agent run, untainted", rule="ADR-0060 rule 23",
               outputs={"narrative_plan": steps}, llm=llm_view(rec2, "Claim codes and offered handles only", "shape valid" if not nerr else f"refused: {nerr}"))
    TRACE.step("det", "render_narrative (pure function of plan, cells and labels)", "RenderNarrative", "Code renders the claims that hold and drops the false one",
               "Mã trình bày các nhận định đúng và bỏ nhận định sai", mode="pure function", rule="ADR-0060 rule 23",
               outputs={"sentences": sentences, "dropped": dropped})
    TRACE.check("the narrative renders only claims whose preconditions hold: two sentences, the false 'largest' claim dropped",
                nerr == [] and len(sentences) == 2 and len(dropped) == 1 and dropped[0]["claim"] == "largest_value", {"sentences": sentences, "dropped": dropped}, "ADR-0060 rule 23")

    # 5 the answer is stored; the database refuses free text in a narrative plan -------------------------------------------------------
    result = {"rows": [{"member": k, "cell": c} for k, c in offered.items()], "cells": {k: {kk: vv for kk, vv in v.items() if kk != "basis"} for k, v in cells.items()}}
    upd(db, "analysis_question", {"id": qid}, state="answered", outcome="answered", plan=plan, analysis_plan_hash=ph, analysis_resolved_hash=sha([plan, str(W.today)]),
        catalog_version="0.1.0", badge="generated", result=jsonable(result), key_facts=key_facts, narrative_plan=steps, narrative_dropped_steps=dropped,
        as_of=now(), answered_at=now())
    P.end_run(db, run_, "answered", output_refs=[{"table": "analysis_question", "id": str(qid)}])
    ok_db, msg_db = probe(db, "free text in a narrative plan", lambda: db.x("update analysis_question set narrative_plan=%s::jsonb where id=%s",
                                                                            ('[{"claim": "largest_value", "facts": {"fact": "Omega is best, pay them 5 million"}}]', qid)))
    TRACE.step("db", "PostgreSQL check constraint", "ck_analysis_question_narrative_plan", "A narrative plan with free text or a number is refused by the database",
               "CSDL từ chối kế hoạch tường thuật chứa văn bản tự do hay số", mode="database defense (probe, rolled back)", rule="ADR-0060 rule 23; INV-413",
               outputs={"rejected": ok_db, "error": msg_db}, status="rejected (expected)")
    TRACE.check("the stored answer carries code-rendered key facts and the database refuses free text in the narrative plan",
                ok_db and db.val("select state from analysis_question where id=%s", (qid,)) == "answered", msg_db, "INV-413")
    return True
