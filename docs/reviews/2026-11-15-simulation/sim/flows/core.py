"""Simulation runtime: database, deterministic IDs and clock, row tracking, trace, LLM gateway.

Simulation code, not product code. Every row goes to the design tables loaded from the DDL; the few tables without
DDL are in ../sim_stubs.sql and are named as stubs in the README.
"""
import datetime as dt
import hashlib
import json
import os
import random
import re
import time
import urllib.request
import uuid
from decimal import Decimal as D, ROUND_HALF_UP
from fractions import Fraction

import psycopg
from psycopg.types.json import Jsonb, set_json_dumps

DSN = os.environ.get("ERPME_SIM_DSN", "host=127.0.0.1 port=5561 dbname=erpme_sim user=lab password=lab")
LLM_URL = os.environ.get("ERPME_SIM_LLM_URL", "http://127.0.0.1:18083/v1/chat/completions")
LLM_MODEL = os.environ.get("ERPME_SIM_LLM_MODEL", "/models/gemma-4-31b-it-Q8_0/gemma-4-31B-it-Q8_0.gguf")
LLM_MODE = os.environ.get("SIM_LLM", "live")          # live | off (labelled fallback fixtures, for dry runs)
LLM_GAP = float(os.environ.get("SIM_LLM_GAP", "4"))   # seconds between calls: the machine is shared
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = dt.timezone(dt.timedelta(hours=7))
SEED = "erpme-sim-2026-11-15"


# ------------------------------------------------------------------ values
def d(s):
    return dt.date.fromisoformat(s)


def money(x):
    """VND has no minor unit; half up (ADR-0006 rule 18)."""
    if isinstance(x, Fraction):
        x = D(x.numerator) / D(x.denominator)
    return D(x).quantize(D(1), rounding=ROUND_HALF_UP)


def fmt(x):
    if isinstance(x, D):
        if x == x.to_integral_value():
            return format(x.quantize(D(1)), "f")
        return format(x.normalize(), "f")
    return x


def jsonable(o):
    if isinstance(o, Fraction):
        o = D(o.numerator) / D(o.denominator) if o.denominator != 1 else D(o.numerator)
        o = o.quantize(D("0.0000000001")) if o != o.to_integral_value() else o
    if isinstance(o, D):
        return fmt(o)
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    if isinstance(o, (set, frozenset)):
        return sorted(jsonable(x) for x in o)
    if isinstance(o, tuple):
        return [jsonable(x) for x in o]
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [jsonable(x) for x in o]
    return o


def J(o):
    return json.dumps(jsonable(o), ensure_ascii=False, sort_keys=True)


set_json_dumps(J)


def sha(o):
    return hashlib.sha256(json.dumps(jsonable(o), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


# ------------------------------------------------------------------ world, clock, IDs
class World:
    pass


W = World()
W.today = d("2026-11-01")
W.flow = 0
W.minute = 0
W.code_of = {}            # id -> readable code for the trace
W.user = {}               # template -> user dict


def set_day(day):
    W.today = d(day) if isinstance(day, str) else day
    W.minute = 0


def now():
    """Deterministic business clock: 08:00 on the business day plus one minute per call."""
    W.minute += 1
    return dt.datetime.combine(W.today, dt.time(8, 0), TZ) + dt.timedelta(minutes=W.minute)


_streams = {}


def new_id(stream="row"):
    """Deterministic UUIDs, one random stream per (flow, stream), so a different LLM answer in one place shifts
    no ID elsewhere."""
    key = f"{W.flow}:{stream}"
    r = _streams.get(key)
    if r is None:
        r = _streams[key] = random.Random(hashlib.sha256(f"{SEED}:{key}".encode()).hexdigest())
    return uuid.UUID(bytes=bytes(r.getrandbits(8) for _ in range(16)), version=4)


def reset_streams():
    _streams.clear()


# ------------------------------------------------------------------ database
class DB:
    def __init__(self):
        self.cx = psycopg.connect(DSN + " options=-csearch_path=erpme")
        self.cx.autocommit = True
        self.cols = {}

    def set_company(self, company_id):
        # FORCE ROW LEVEL SECURITY on the platform tables (ADR-0022 rule 8): the session names its company.
        self.cx.execute("select set_config('erpme.company_id', %s, false)", (str(company_id),))

    def load_columns(self):
        self.cols = {}
        for t, c, nul, dflt, udt in self.cx.execute(
                "select table_name, column_name, is_nullable, column_default, udt_name from information_schema.columns where table_schema='erpme'"):
            self.cols.setdefault(t, {})[c] = (nul == "YES", dflt, udt)

    def x(self, sql, args=None):
        return self.cx.execute(sql, args)

    def one(self, sql, args=()):
        return self.cx.execute(sql, args).fetchone()

    def val(self, sql, args=()):
        r = self.cx.execute(sql, args).fetchone()
        return r[0] if r else None

    def all(self, sql, args=()):
        return self.cx.execute(sql, args).fetchall()

    def tx(self):
        return self.cx.transaction()


DBX = None   # set by run_all


class Effects:
    """Rows written and journal lines posted since the last trace step."""
    def __init__(self):
        self.rows, self.journal = {}, []

    def add(self, table, n=1):
        self.rows[table] = self.rows.get(table, 0) + n

    def take(self):
        r = {"rows_written": dict(sorted(self.rows.items()))} if self.rows else {}
        if self.journal:
            r["journal_entries"] = self.journal
        self.rows, self.journal = {}, []
        return r


EFF = Effects()


def _adapt(v):
    if isinstance(v, dict) or (isinstance(v, list) and v and isinstance(v[0], dict)):
        return Jsonb(v)
    return v


def ins(db, table, **cols):
    """Insert one row into erpme.<table>; fills company_id and recorded_at when the table has them."""
    meta = db.cols.get(table)
    if meta is None:
        raise KeyError(f"no table erpme.{table}")
    if "company_id" in meta and "company_id" not in cols and getattr(W, "co", None):
        cols["company_id"] = W.co
    if "recorded_at" in meta and "recorded_at" not in cols:
        cols["recorded_at"] = now()
    if "uom_factor_source" in meta:
        from . import uom as _u
        cols = _u.fill_block(db, table, cols)
    for k in cols:
        if k not in meta:
            raise KeyError(f"erpme.{table} has no column {k}")
    keys = list(cols)
    vals = [Jsonb(cols[k]) if meta[k][2] == "jsonb" and cols[k] is not None and not isinstance(cols[k], Jsonb) else _adapt(cols[k]) for k in keys]
    db.x("insert into %s (%s) values (%s)" % (table, ",".join('"%s"' % k for k in keys), ",".join(["%s"] * len(keys))), vals)
    EFF.add(table)
    return cols.get("id")


def upd(db, table, where, **cols):
    """Update erpme.<table> rows matching where (dict of column -> value)."""
    sets = ",".join('"%s"=%%s' % k for k in cols)
    conds = " and ".join('"%s"=%%s' % k for k in where)
    meta = db.cols.get(table, {})
    vals = [Jsonb(v) if meta.get(k, (0, 0, ""))[2] == "jsonb" and v is not None and not isinstance(v, Jsonb) else _adapt(v) for k, v in cols.items()]
    db.x(f"update {table} set {sets} where {conds}", vals + list(where.values()))
    EFF.add(f"{table} (update)")


# ------------------------------------------------------------------ trace
LANES = {"person": "human", "llm": "agent_llm", "det": "deterministic", "system": "system", "db": "deterministic"}
LANE_NAMES = {"person": "person", "llm": "LLM agent", "det": "deterministic function", "system": "deterministic function (system job)",
              "db": "database"}


class Trace:
    def __init__(self):
        self.steps, self.flows, self.flow, self.n, self.seq = [], [], None, 0, 0

    def start_flow(self, num, name, name_vi, summary):
        self.flow = num
        W.flow = num
        f = next((x for x in self.flows if x["flow"] == num), None)
        self.n = sum(1 for s in self.steps if s["flow"] == num)     # a flow split in two parts keeps numbering 1..N
        if f is None:
            self.flows.append({"flow": num, "name": name, "name_vi": name_vi, "summary": summary, "status": "running", "checks": []})
        EFF.take()

    def check(self, name, ok, detail="", rule=""):
        f = next(f for f in self.flows if f["flow"] == self.flow)
        f["checks"].append({"name": name, "ok": bool(ok), "detail": jsonable(detail), "rule": rule})
        print(("    PASS " if ok else "    FAIL ") + name + (f" -- {detail}" if detail and not ok else ""))
        return ok

    def step(self, lane, actor, command, title, title_vi, mode="", inputs=None, outputs=None, rule="", policy=None,
             decision=None, approval=None, events=None, work_items=None, llm=None, deterministic=None, notes=None, status="ok"):
        assert lane in LANES, lane
        self.n += 1
        self.seq += 1
        fn = command
        if lane == "db" and not re.match(r"^(ex|ck|uq|fk|trg)_", fn):
            fn = "ck_" + fn
        s = {"seq": self.seq, "flow": self.flow, "step": self.n, "title": title, "title_vi": title_vi,
             "lane": lane, "lane_name": LANE_NAMES[lane], "actor_kind": LANES[lane], "actor": actor, "mode": mode,
             "function": fn, "command": command, "rule": rule,
             "inputs": jsonable(inputs or {}), "outputs": jsonable(outputs or {}),
             "policy": policy or [], "db_effects": EFF.take(), "status": status}
        if decision:
            s["policy_decision"] = jsonable(decision)
        if approval:
            s["approval"] = jsonable(approval)
        if events:
            s["events"] = jsonable(events)
        if work_items:
            s["work_items"] = jsonable(work_items)
        if deterministic:
            s["deterministic"] = deterministic
        if llm:
            s["llm"] = llm
        if notes:
            s["notes"] = notes if isinstance(notes, list) else [notes]
        self.steps.append(s)
        print(f"  [{self.flow}.{self.n:02d}] {lane:6s} {command[:40]:40s} {title}")
        return s


TRACE = Trace()


# ------------------------------------------------------------------ LLM gateway (OpenAI-compatible, local Gemma)
LLM_STATS = {"live": 0, "fallback": 0, "calls": []}
_last_call = [0.0]


def _post(payload, timeout):
    req = urllib.request.Request(LLM_URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def parse_json(text):
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    m = re.search(r"\{.*\}", t, re.S)
    return json.loads(m.group(0) if m else t)


def call_llm(call_name, system, user, schema_check, fallback, max_tokens=700):
    """One exchange: thinking off, response_format json_object, temperature 0. A schema failure or an HTTP error gets
    one retry after a pause; then the labelled fallback fixture is used (never shown as a live answer)."""
    raw, parsed, errors, attempts, live, usage = None, None, [], 0, False, {}
    if LLM_MODE == "live":
        for attempt in range(3):
            attempts = attempt + 1
            wait = LLM_GAP - (time.time() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            try:
                resp = _post({"model": LLM_MODEL, "temperature": 0, "max_tokens": max_tokens,
                              "chat_template_kwargs": {"enable_thinking": False},
                              "response_format": {"type": "json_object"},
                              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, timeout=300)
                _last_call[0] = time.time()
                raw = resp["choices"][0]["message"].get("content") or ""
                usage = resp.get("usage") or {}
                parsed = parse_json(raw)
                errs = schema_check(parsed)
                if errs:
                    raise ValueError("schema: " + "; ".join(errs))
                live = True
                break
            except Exception as e:  # noqa: BLE001 - timeouts, HTTP errors, invalid JSON or schema
                _last_call[0] = time.time()
                errors.append(f"attempt {attempt + 1}: {type(e).__name__}: {str(e)[:200]}")
                parsed = None
                time.sleep(15 * (attempt + 1))
    if not live:
        raw = "LLM unavailable - fallback fixture" + (f" (errors: {'; '.join(errors)})" if errors else " (SIM_LLM=off)")
        parsed = fallback
        LLM_STATS["fallback"] += 1
    else:
        LLM_STATS["live"] += 1
    LLM_STATS["calls"].append({"flow": TRACE.flow, "call": call_name, "mode": "live" if live else "fallback_fixture", "attempts": attempts})
    print(f"      LLM {call_name}: {'live' if live else 'FALLBACK'} after {attempts} attempt(s)")
    return {"call_name": call_name, "model": LLM_MODEL, "mode": "live" if live else "fallback_fixture",
            "label": "live LLM answer" if live else "LLM unavailable - fallback fixture (recorded response, not a live answer)",
            "attempts": attempts, "system_prompt": system, "input_text": user, "raw_output": raw, "parse_ok": True,
            "parsed": jsonable(parsed), "errors": errors, "usage": usage}


# ------------------------------------------------------------------ small schema checker for LLM outputs
def check_schema(obj, schema, path="$"):
    """schema: {"type": "object", "required": [...], "properties": {...}} with types object, array, string, number,
    integer, boolean, enum (list), nullable via "null": True. Returns a list of errors."""
    errs = []
    t = schema.get("type")
    if obj is None:
        return [] if schema.get("null") else [f"{path}: null"]
    if "enum" in schema:
        if obj not in schema["enum"]:
            errs.append(f"{path}: {obj!r} not in {schema['enum']}")
        return errs
    if t == "object":
        if not isinstance(obj, dict):
            return [f"{path}: not an object"]
        for k in schema.get("required", []):
            if k not in obj:
                errs.append(f"{path}.{k}: missing")
        for k, sub in schema.get("properties", {}).items():
            if k in obj:
                errs += check_schema(obj[k], sub, f"{path}.{k}")
        if schema.get("additional") is not None and isinstance(schema["additional"], dict):
            for k, v in obj.items():
                if k not in schema.get("properties", {}):
                    errs += check_schema(v, schema["additional"], f"{path}.{k}")
    elif t == "array":
        if not isinstance(obj, list):
            return [f"{path}: not an array"]
        if "max" in schema and len(obj) > schema["max"]:
            errs.append(f"{path}: more than {schema['max']} items")
        for i, v in enumerate(obj):
            errs += check_schema(v, schema.get("items", {}), f"{path}[{i}]")
    elif t == "string":
        if not isinstance(obj, str):
            errs.append(f"{path}: not a string")
        elif "maxlen" in schema and len(obj) > schema["maxlen"]:
            errs.append(f"{path}: longer than {schema['maxlen']}")
    elif t == "number":
        if isinstance(obj, bool) or not isinstance(obj, (int, float, str)):
            errs.append(f"{path}: not a number")
        else:
            try:
                D(str(obj))
            except Exception:  # noqa: BLE001
                errs.append(f"{path}: not a number")
    elif t == "integer":
        if isinstance(obj, bool) or not isinstance(obj, int):
            errs.append(f"{path}: not an integer")
    elif t == "boolean":
        if not isinstance(obj, bool):
            errs.append(f"{path}: not a boolean")
    elif t == "any":
        pass
    return errs


def fold(s):
    """Case and diacritics folding (ADR-0002) for span and name checks."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s.replace("đ", "d").replace("Đ", "D").lower()).strip()


def number_tokens(text):
    """Each number written in a text with its possible readings (thousands separators of either style)."""
    out = []
    for m in re.findall(r"\d[\d.,]*", text or ""):
        m = m.rstrip(".,")
        reads = set()
        for cand in {m.replace(",", "").replace(".", ""), m.replace(",", ""), m.replace(".", "").replace(",", ".")}:
            try:
                reads.add(D(cand).normalize())
            except Exception:  # noqa: BLE001
                pass
        out.append((m, reads))
    return out


def stray_numbers(text, allowed):
    """Numbers in the text none of whose readings is allowed."""
    allowed = {D(a).normalize() for a in allowed}
    return [m for m, reads in number_tokens(text) if not (reads & allowed)]


def numbers_in(text):
    """Numbers written in a text, with thousands separators of either style removed."""
    out = set()
    for m in re.findall(r"\d[\d.,]*", text or ""):
        m = m.rstrip(".,")
        for cand in {m.replace(",", "").replace(".", ""), m.replace(",", ""), m.replace(".", "").replace(",", ".")}:
            try:
                out.add(D(cand).normalize())
            except Exception:  # noqa: BLE001
                pass
    return out
