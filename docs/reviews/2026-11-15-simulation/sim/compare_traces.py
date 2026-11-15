"""Compare two traces apart from the LLM text: python3 compare_traces.py a.json b.json

Ignored: meta.run_at, token usage, and inside each LLM step the raw output, parsed JSON, errors and attempts; outputs of
LLM steps (they echo the LLM's JSON) and free-text fields written by the LLM (explanation, cover text, notes on work items).
Everything else (steps, lanes, commands, rows written, journal lines, decisions, checks, invariants) must be equal."""
import json
import sys

LLM_TEXT_KEYS = {"raw_output", "parsed", "errors", "attempts", "usage"}


def norm(t):
    steps = []
    for s in t["steps"]:
        s = dict(s)
        if s.get("llm"):
            s["llm"] = {k: v for k, v in s["llm"].items() if k not in LLM_TEXT_KEYS and k != "deterministic_outcome" and k != "input_text"}
            s["outputs"] = "(LLM output)"
        for k in ("inputs", "outputs", "approval"):
            if isinstance(s.get(k), dict):
                s[k] = {kk: vv for kk, vv in s[k].items() if kk not in ("explanation", "reply_subject", "reply_chars", "recommended_text")}
        steps.append(s)
    return {"steps": steps, "flows": t["flows"], "invariants": t["invariants"]}


def diff(a, b, path="", out=None):
    out = [] if out is None else out
    if type(a) is not type(b):
        out.append(f"{path}: {str(a)[:80]} != {str(b)[:80]}")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: only in one trace")
            else:
                diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append(f"{path}: {str(a)[:80]} != {str(b)[:80]}")
    return out


if __name__ == "__main__":
    a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
    d = diff(norm(a), norm(b))
    print(f"{len(d)} difference(s) apart from the LLM text")
    for x in d[:40]:
        print(" ", x)
    sys.exit(1 if d else 0)
