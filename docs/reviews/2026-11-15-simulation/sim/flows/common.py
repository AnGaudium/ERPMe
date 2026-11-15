"""Helpers shared by the flow scripts: LLM steps with their records, database-defense probes, approval walks."""
from .core import TRACE, W, EFF, call_llm, check_schema, jsonable
from . import platform as P


def llm_step(db, run, step_code, seat, schema_name, schema, system, user, fallback, max_tokens=700):
    """One L-step of ADR-0051: the call, its validated JSON, and the agent_run_step rows. Returns (parsed, rec)."""
    rec = call_llm(f"{run['agent_type']}.{step_code}", system, user, lambda o: check_schema(o, schema), fallback, max_tokens)
    errs = check_schema(rec["parsed"], schema)
    P.record_llm(db, run, f"{run['agent_type']}.{step_code}", seat, rec, validation_errors=errs or None)
    rec["output_schema"] = f"{schema_name} 1.0.0"
    rec["seat"] = seat
    return rec["parsed"], rec


def llm_view(rec, prompt_summary, outcome):
    out = {k: rec[k] for k in ("call_name", "model", "mode", "label", "attempts", "system_prompt", "input_text", "raw_output", "parse_ok",
                               "parsed", "errors", "output_schema", "seat")}
    out["prompt_summary"] = prompt_summary
    out["deterministic_outcome"] = outcome
    return out


def probe(db, label, fn):
    """Run fn in a transaction that must fail; returns the database's error text (the transaction rolls back)."""
    saved = dict(EFF.rows)
    try:
        with db.tx():
            fn()
        msg, ok = "accepted (unexpected)", False
    except Exception as e:  # noqa: BLE001
        msg, ok = str(e).splitlines()[0], True
    EFF.rows = saved
    return ok, msg


def approval_walk(db, doc, approvers, reason, command, title, title_vi, rule):
    """Per required stage: the eligibility of every member (deterministic step), then the first preferred person who is
    eligible and would strand no later stage (ADR-0055 rule 7 condition 8) approves."""
    if isinstance(approvers, str):
        approvers = [approvers]
    dec = doc["decision"]
    last = None
    while P.doc_state(db, doc["id"]) == "pending_approval":
        cands = P.candidates(db, doc, dec, command)
        table = [{"person": c["user"], "template": c["template"], "eligible": c["eligible"],
                  "failed": [k for k, v in c["conditions"].items() if not v], "submitter": c["is_submitter"]} for c in cands]
        stage = cands[0]["stage"] if cands else None
        chosen, stranded = None, []
        for tpl in approvers:
            u = W.user[tpl]
            if not any(c["eligible"] and c["template"] == tpl for c in cands):
                continue
            if P.strands(db, doc, dec, u, command):
                stranded.append(u["name"])
                continue
            chosen = tpl
            break
        TRACE.step("det", "dispatcher: approval eligibility (registered functions of policy, permissions, documents)", f"ListAllowedCommand({command})",
                   f"Who may approve {doc['type']} {doc.get('number') or ''} at stage {dec['pool']}.{stage}",
                   f"Ai được duyệt {doc['type']} {doc.get('number') or ''} ở bước {dec['pool']}.{stage}",
                   mode="query, deterministic", rule="ADR-0055 rule 7 conditions 1-8; ADR-0017 rule 16; ADR-0054 rule 19",
                   inputs={"document": doc.get("number") or str(doc["id"]), "pool": dec["pool"], "stage": stage, "plan": dec["plan"]},
                   outputs={"candidates": table, "eligible": [c["person"] for c in table if c["eligible"]], "would_strand_a_later_stage": stranded},
                   deterministic="members of the stage, holding Approve<Type>, not a writer of any version (document_actor()), "
                                 "not counted yet, no segregation pair; for a change proposal also the target permissions; no stranded stage")
        if chosen is None:
            raise RuntimeError(f"approval_stage_unsatisfiable at {dec['pool']}.{stage}: {table}")
        el, res = P.approve(db, doc, W.user[chosen], reason, command)
        TRACE.step("person", f"{W.user[chosen]['name']} ({chosen})", command, title + ("" if len(dec["plan"]) == 1 else f" (stage {res['stage']})"),
                   title_vi + ("" if len(dec["plan"]) == 1 else f" (bước {res['stage']})"), mode="direct, human_only",
                   rule=rule, inputs={"reason": reason}, outputs={"state": res["state"], "stage": f"{dec['pool']}.{res['stage']}"},
                   approval={"stage": f"{dec['pool']}.{res['stage']}", "conditions": el["conditions"], "permission": el["permission"]},
                   events=res["events"], work_items=res["items"])
        last = (el, res)
    return last
