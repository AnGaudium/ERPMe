"""trace.json -> trace.md (readable, same content)."""
import json

LANE = {"person": "Person", "llm": "LLM agent", "det": "Deterministic function", "system": "Deterministic (system job/consumer)", "db": "Database"}


def _j(x, n=1600):
    s = json.dumps(x, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + " …"


def render(t, path):
    m = t["meta"]
    out = [f"# ERPMe six-flow simulation trace", "",
           f"Run {m['run_at']} on `{m['database']}` ({m['tables']} tables). Trace format {m['format_version']}. "
           f"LLM: {m['llm']['model']} ({m['llm']['mode']}), {m['llm']['live']} live call(s), {m['llm']['fallback']} fallback(s).", "",
           "Schema: " + m["schema"]["recipe"] + ". Lab stubs: " + ", ".join(m["schema"]["lab_stub_tables"]) +
           ". Simulation stubs (no DDL yet): " + ", ".join(m["schema"]["sim_stub_tables"]) + ".", "",
           "All names, numbers and e-mails are fictional (sample). This is a simulation of the design, not product code.", "",
           "## Cast", "", "| Person | Role template |", "| --- | --- |"]
    out += [f"| {c['name']} | {c['template']} |" for c in t["cast"]]
    out += ["", "## Results", "", "| Flow | Name | Steps | LLM calls | Checks | Status |", "| --- | --- | --- | --- | --- | --- |"]
    for f in t["flows"]:
        ok = sum(1 for c in f["checks"] if c["ok"])
        out.append(f"| {f['flow']} | {f['name']} | {f.get('steps')} | {f.get('llm_calls')} | {ok}/{len(f['checks'])} | {f['status'].upper()} |")
    out += ["", "### Invariants", "", "| Code | Check | Result | Detail |", "| --- | --- | --- | --- |"]
    for i in t["invariants"]:
        out.append(f"| {i['code']} | {i['name']} | {'PASS' if i['ok'] else 'FAIL'} | {_j(i['detail'], 200)} |")
    cur = None
    for s in t["steps"]:
        if s["flow"] != cur:
            cur = s["flow"]
            f = next(x for x in t["flows"] if x["flow"] == cur)
            out += ["", f"## Flow {cur}: {f['name']} ({f['name_vi']})", "", f["summary"], ""]
            if s["step"] != 1:
                out.append("(continued)")
        out += ["", f"### {s['flow']}.{s['step']:02d} {s['title']}", "",
                f"- Lane: **{LANE[s['lane']]}**; actor: {s['actor']}" + (f"; mode: {s['mode']}" if s.get("mode") else ""),
                f"- Command: `{s['command']}`" + (f"; rule: {s['rule']}" if s.get("rule") else ""), f"- Vietnamese title: {s['title_vi']}"]
        if s["inputs"]:
            out.append(f"- Inputs: `{_j(s['inputs'])}`")
        if s["outputs"]:
            out.append(f"- Outputs: `{_j(s['outputs'])}`")
        if s.get("deterministic"):
            out.append(f"- Deterministic layer: {s['deterministic']}")
        if s.get("policy_decision"):
            d = s["policy_decision"]
            out.append(f"- Policy decision: {d['outcome']}" + (f", rank {d['rank']}, pool {d['pool']}, plan {d['plan']}" if d.get("rank") else "")
                       + (f"; rules {d['matched_rules']}" if d.get("matched_rules") else "") + (f"; floors {d['floors']}" if d.get("floors") else ""))
        if s.get("approval"):
            out.append(f"- Approval: `{_j(s['approval'], 600)}`")
        for p in s.get("policy") or []:
            out.append(f"- Policy note: {p}")
        if s.get("events"):
            out.append("- Events: " + ", ".join(e["event"] + (" (tainted)" if e.get("tainted") else "") for e in s["events"]))
        if s.get("work_items"):
            out.append("- Work items: " + ", ".join(f"{w.get('kind')} {w.get('state')}" + (f" -> {w.get('owner')}" if w.get("owner") else "") for w in s["work_items"]))
        if s.get("llm"):
            l = s["llm"]
            out += [f"- LLM call `{l['call_name']}` ({l['label']}, {l['attempts']} attempt(s), output schema {l.get('output_schema')}, seat {l.get('seat')})",
                    f"  - Purpose: {l['prompt_summary']}", f"  - System prompt (excerpt): {l['system_prompt'][:500]}",
                    "  - Raw JSON:", "", "```json", (l["raw_output"] or "")[:2500], "```", "", f"  - Deterministic outcome: {l['deterministic_outcome']}"]
        dbe = s.get("db_effects") or {}
        if dbe.get("rows_written"):
            out.append("- Rows written: " + ", ".join(f"{k} x{v}" for k, v in dbe["rows_written"].items()))
        for e in dbe.get("journal_entries") or []:
            out += ["", f"Journal entry {e['document']} on {e['posting_date']}: {e.get('description') or ''}", "",
                    "| # | Account | Name | Debit | Credit | Detail |", "| --- | --- | --- | ---: | ---: | --- |"]
            for l in e["lines"]:
                dr = l["amount"] if l["side"] == "debit" else ""
                cr = l["amount"] if l["side"] == "credit" else ""
                det = "; ".join(str(l[k]) for k in ("transaction_key", "partner", "item", "open_item", "desc") if l.get(k))
                out.append(f"| {l['line']} | {l['account']} | {l['account_name']} | {dr} | {cr} | {det} |")
        for n in s.get("notes") or []:
            out.append(f"- Note: {n}")
    for f in t["flows"]:
        out += ["", f"## Checks, flow {f['flow']}", ""]
        out += [f"- {'PASS' if c['ok'] else 'FAIL'} {c['name']}" + (f" ({c['rule']})" if c.get("rule") else "") + (f": {_j(c['detail'], 300)}" if c.get("detail") and not c["ok"] else "")
                for c in f["checks"]]
        if f.get("error"):
            out.append(f"- ERROR: {f['error']}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
