"""Scenario: DS-56 product configuration (ADR-0046), on the DS-20 and DS-56 DDL loaded with DS-06 (lab finding L-14).

A neutral configurable unit has item-defining characteristics width and height (numbers in mm with a step of 50),
material and mounting (lists) and size_class (a list derived from width bands by a table with ranges), and line
options color and label. The model has restrict, set, require and forbid rules, two tables and two defaults.
The lab implements ADR-0046's evaluation in rounds (rule 8), configuration records (rule 9), configured items
(rule 11), the super bill of materials explosion with conditions and linear sizing and its release checks
(rules 12-13, on a lab table, since the production DDL is not drafted), configured prices (rule 15) and estimates
(rule 14), and checks the immutability triggers and company_id coverage of DS-56.
"""
import hashlib, json, os, random, re
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from fractions import Fraction as F
from lab import *

c = conn(); c.autocommit = True
X = c.execute
B = '{"kind": "company_decision"}'
I = {k: new() for k in ["user", "co", "ig", "vc", "itg", "ea", "mm", "prod", "pl", "model", "rev", "rev2"]}
t = str(I["co"])[-8:]
X("insert into currency (code, minor_unit) values ('VND',0) on conflict do nothing")
X("insert into user_account values (%s)", (I["user"],))
X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
  " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','warehouse',%s,'vi')", (I["co"], "C6-" + t, I["user"]))
for k, code, kind, dec in (("ea", "EA6" + t, "count", 0), ("mm", "MM6" + t, "length", 0)):
    X("insert into uom (id, code, quantity_kind, decimal_places) values (%s,%s,%s,%s)", (I[k], code, kind, dec))
X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,'fg','FG',%s)", (I["ig"], I["co"], B))
X("insert into valuation_class (id, company_id, code, name, basis) values (%s,%s,'fg','FG',%s)", (I["vc"], I["co"], B))
X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,'std','Std',%s)", (I["itg"], I["co"], B))
X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
     item_tax_group_id, tracking, is_item_created_on_order, is_configurable) values (%s,%s,'UNIT','Unit','stock',%s,%s,%s,%s,%s,%s,'serial',true,true)""",
  (I["prod"], I["co"], I["ig"], I["vc"], I["ea"], I["ea"], I["ea"], I["itg"]))

# Characteristics: code -> (mode, type, list values or (min, max, step)), plus product_variant_attribute.is_required
CH = {
    "width":      ("variant", "number", (D(400), D(2000), D(50))),
    "height":     ("variant", "number", (D(300), D(1200), D(50))),
    "material":   ("variant", "list", ["aluminium", "steel", "stainless"]),
    "size_class": ("variant", "list", ["S", "M", "L"]),
    "mounting":   ("variant", "list", ["none", "wall", "floor"]),
    "color":      ("line_option", "list", ["grey", "blue"]),
    "label":      ("line_option", "list", ["text"]),
}
REQ_FLAG = {"color": False, "label": False}
A, V = {}, {}
for pos, (code, (mode, vt, spec)) in enumerate(CH.items(), 1):
    A[code] = new()
    if vt == "list":
        X("insert into variant_attribute (id, company_id, code, name, variant_mode) values (%s,%s,%s,%s,%s)", (A[code], I["co"], code + t, code, mode))
        for v in spec:
            V[(code, v)] = new()
            X("insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, code, name, is_custom) values (%s,%s,%s,%s,%s,%s,%s)",
              (V[(code, v)], I["co"], A[code], mode, v, v, code == "label"))
    else:
        lo, hi, st = spec
        X("insert into variant_attribute (id, company_id, code, name, variant_mode, value_type, uom_id, minimum_value, maximum_value, step_value, decimal_places)"
          " values (%s,%s,%s,%s,%s,'number',%s,%s,%s,%s,0)", (A[code], I["co"], code + t, code, mode, I["mm"], lo, hi, st))
    X("insert into product_variant_attribute (company_id, product_id, variant_attribute_id, position, is_required) values (%s,%s,%s,%s,%s)",
      (I["co"], I["prod"], A[code], pos, REQ_FLAG.get(code, False)))
X("insert into configuration_model (id, company_id, product_id, code, name) values (%s,%s,%s,'UNIT','Unit')", (I["model"], I["co"], I["prod"]))
RULES = [  # kind, condition, target, effect, message
    ("restrict", {"c": "width", "op": "gt", "v": 1400}, "material", {"values": ["steel", "stainless"]}, "large_needs_strong_material"),
    ("set", {"c": "size_class", "op": "eq", "v": "L"}, "mounting", {"value": "floor"}, "large_on_floor"),
    ("set", {"c": "material", "op": "eq", "v": "stainless"}, "mounting", {"value": "wall"}, "stainless_on_wall"),
    ("forbid", {"all": [{"c": "mounting", "op": "eq", "v": "wall"}, {"c": "height", "op": "gt", "v": 1000}]}, None, {}, "wall_too_tall"),
    ("require", {"c": "material", "op": "eq", "v": "steel"}, "color", {}, "steel_needs_color"),
    ("restrict", {"c": "mounting", "op": "eq", "v": "floor"}, "height", {"min": 600, "max": 1200}, "floor_min_height"),
    ("restrict", {"c": "material", "op": "eq", "v": "aluminium"}, "height", {"min": 300, "max": 550}, "aluminium_max_height"),
]
TABLES = [  # code, columns, rows
    ("size_band", ["width", "size_class"], [[{"min": 400, "max": 800}, "S"], [{"min": 850, "max": 1400}, "M"], [{"min": 1450, "max": 2000}, "L"]]),
    ("material_size", ["material", "size_class"], [["aluminium", "S"], ["aluminium", "M"], ["steel", "*"], ["stainless", "M"], ["stainless", "L"]]),
]
DEFAULTS = [("mounting", "none", {}), ("height", 600, {})]
def write_revision(cx, rid, revision, start, rules, extra_rules=()):
    cx.execute("insert into configuration_model_revision (id, company_id, configuration_model_id, product_id, revision, start_date) values (%s,%s,%s,%s,%s,%s)",
               (rid, I["co"], I["model"], I["prod"], revision, start))
    for pos, (kind, cond_, tgt, eff, msg) in enumerate(list(rules) + list(extra_rules), 1):
        cx.execute("insert into configuration_rule (id, company_id, configuration_model_revision_id, product_id, position, kind, condition, target_attribute_id, effect, message_code)"
                   " values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (new(), I["co"], rid, I["prod"], pos * 10, kind, json.dumps(cond_), A[tgt] if tgt else None, json.dumps(eff), msg))
    for code, cols, rows in TABLES:
        tid = new()
        cx.execute("insert into configuration_table (id, company_id, configuration_model_revision_id, product_id, code) values (%s,%s,%s,%s,%s)", (tid, I["co"], rid, I["prod"], code))
        for n, col in enumerate(cols, 1):
            cx.execute("insert into configuration_table_column values (%s,%s,%s,%s,%s)", (I["co"], tid, I["prod"], n, A[col]))
        for n, cells in enumerate(rows, 1):
            cx.execute("insert into configuration_table_row values (%s,%s,%s,%s,%s)", (I["co"], tid, I["prod"], n, json.dumps(cells)))
    for pos, (tgt, v, cond_) in enumerate(DEFAULTS, 1):
        cx.execute("insert into configuration_default values (%s,%s,%s,%s,%s,%s,%s)", (I["co"], rid, I["prod"], pos, A[tgt], json.dumps(v), json.dumps(cond_)))
    cx.execute("update configuration_model_revision set state='released', content_hash=%s, released_at=now() where id=%s", ("0" * 64, rid))
with c.transaction():
    write_revision(c, I["rev"], 1, "2026-01-01", RULES)
with c.transaction():   # revision 2 from 1 July adds a width limit
    write_revision(c, I["rev2"], 2, "2026-07-01", RULES, [("forbid", {"c": "width", "op": "gt", "v": 1800}, None, {}, "width_limit")])
c.close()

# ---- ADR-0046 rule 8: evaluation in rounds (pure) ----
def num(x): return D(str(x))
def norm(v): return format(v.normalize(), "f") if isinstance(v, D) else str(v)
class Model:
    def __init__(self, ch, rules, tables, defaults, required):
        self.ch, self.rules, self.tables, self.defaults, self.required = ch, rules, tables, defaults, required
def load_model(cx, rev):
    code_of = {v: k for k, v in A.items()}
    rules = [(k, cd, code_of.get(tg), ef, ms) for k, cd, tg, ef, ms in cx.execute(
        "select kind, condition, target_attribute_id, effect, message_code from configuration_rule where configuration_model_revision_id=%s order by position", (rev,))]
    tables = []
    for tid, code in cx.execute("select id, code from configuration_table where configuration_model_revision_id=%s order by code", (rev,)).fetchall():
        cols = [code_of[r[0]] for r in cx.execute("select variant_attribute_id from configuration_table_column where configuration_table_id=%s order by column_number", (tid,))]
        rows = [r[0] for r in cx.execute("select cells from configuration_table_row where configuration_table_id=%s order by row_number", (tid,))]
        tables.append((code, cols, rows))
    defaults = [(code_of[tg], v, cd) for tg, v, cd in cx.execute(
        "select target_attribute_id, value, condition from configuration_default where configuration_model_revision_id=%s order by position", (rev,))]
    req = {code_of[a] for a, r in cx.execute("select variant_attribute_id, is_required from product_variant_attribute where product_id=%s", (I["prod"],)) if r}
    req |= {k for k, (m, _, _) in CH.items() if m == "variant"}           # item-defining characteristics are always required (rule 2)
    return Model(CH, rules, tables, defaults, req)

def cond(m, cd, val):
    if not cd: return True
    if "all" in cd:
        r = [cond(m, x, val) for x in cd["all"]]; return False if False in r else (None if None in r else True)
    if "any" in cd:
        r = [cond(m, x, val) for x in cd["any"]]; return True if True in r else (None if None in r else False)
    if "not" in cd:
        r = cond(m, cd["not"], val); return None if r is None else not r
    cv, op, v = val.get(cd["c"]), cd["op"], cd.get("v")
    if op == "set": return cv is not None
    if op == "unset": return cv is None
    if cv is None: return None
    if m.ch[cd["c"]][1] == "number":
        v = [num(x) for x in v] if op in ("in", "not_in", "between") else num(v)
    return {"eq": lambda: cv == v, "ne": lambda: cv != v, "in": lambda: cv in v, "not_in": lambda: cv not in v,
            "lt": lambda: cv < v, "le": lambda: cv <= v, "gt": lambda: cv > v, "ge": lambda: cv >= v,
            "between": lambda: v[0] <= cv <= v[1]}[op]()
def initial(m, k):
    mode, vt, spec = m.ch[k]
    return frozenset(spec) if vt == "list" else (spec[0], spec[1])
def step_values(m, k, lo, hi, limit=2):
    """The step values in [lo, hi] (up to limit), exact for fractional steps."""
    base, st = m.ch[k][2][0], m.ch[k][2][2]
    n = ((lo - base) / st).to_integral_value(rounding=ROUND_CEILING) if lo > base else D(0)
    out, v = [], base + n * st
    while v <= hi and len(out) < limit:
        out.append(v); v += st
    return out
def has_step(m, k, lo, hi): return bool(step_values(m, k, lo, hi, 1))
def allowed(m, k, v, dom):
    if m.ch[k][1] == "list": return v in dom
    base, st = m.ch[k][2][0], m.ch[k][2][2]
    return dom[0] <= v <= dom[1] and (v - base) % st == 0
def single(m, k, dom):
    if m.ch[k][1] == "list": return next(iter(dom)) if len(dom) == 1 else None
    vs = step_values(m, k, dom[0], dom[1])
    return vs[0] if len(vs) == 1 else None
def cell_ok(m, col, cell, v):
    if cell == "*" or v is None: return True
    if isinstance(cell, dict): return num(cell["min"]) <= v <= num(cell["max"])
    return v == num(cell) if m.ch[col][1] == "number" else v == cell

def domains(m, val):
    """Domains from the initial ones, every true restrict and every table's narrowing on the current values."""
    dom = {k: initial(m, k) for k in m.ch}
    for kind, cd, tg, ef, ms in m.rules:
        if kind == "restrict" and cond(m, cd, val) is True:
            if m.ch[tg][1] == "list": dom[tg] = dom[tg] & frozenset(ef["values"])
            else: dom[tg] = (max(dom[tg][0], num(ef["min"])), min(dom[tg][1], num(ef["max"])))
    for code, cols, rows in m.tables:
        match = [r for r in rows if all(cell_ok(m, col, cell, val.get(col)) for col, cell in zip(cols, r))]
        for i, col in enumerate(cols):
            if val.get(col) is not None or m.ch[col][1] != "list": continue
            cells = {r[i] for r in match}
            if "*" not in cells: dom[col] = dom[col] & frozenset(cells)
    return dom
def rounds(m, val, src):
    bound = len(m.ch) + 1                     # a round changes the state only by giving values
    for _ in range(bound):
        snap = dict(val)
        dom = domains(m, snap)
        proposals = {}
        for kind, cd, tg, ef, ms in m.rules:
            if kind == "set" and cond(m, cd, snap) is True:
                proposals.setdefault(tg, set()).add(num(ef["value"]) if m.ch[tg][1] == "number" else ef["value"])
        new_vals = {}
        for k in m.ch:
            if k in snap: continue
            if k in proposals:
                if len(proposals[k]) == 1:
                    (v,) = proposals[k]
                    if allowed(m, k, v, dom[k]): new_vals[k] = v
            elif k in m.required:                 # only a required characteristic is given its single value
                s = single(m, k, dom[k])
                if s is not None: new_vals[k] = s
        if not new_vals: return dom
        for k, v in new_vals.items(): val[k] = v; src[k] = "rule"
    raise RuntimeError("evaluation bound exceeded")

def evaluate(m, chosen, lookahead=True):
    val = {k: (num(v) if m.ch[k][1] == "number" else v) for k, v in chosen.items()}
    src = {k: "user" for k in val}
    dom = rounds(m, val, src)
    shown, unset = dict(dom), [k for k in m.ch if k not in val]
    applied = True
    while applied:
        applied = False
        for tg, v, cd in m.defaults:
            v = num(v) if m.ch[tg][1] == "number" else v
            if tg not in val and cond(m, cd, val) is True and allowed(m, tg, v, dom[tg]):
                val[tg] = v; src[tg] = "default"; dom = rounds(m, val, src); applied = True; break
    viol = []
    true_rules = [r for r in m.rules if cond(m, r[1], val) is True]
    for k, v in val.items():
        if not allowed(m, k, v, dom[k]):          # every value, whatever its source, against the final domains
            msgs = sorted(ms for kind, cd, tg, ef, ms in true_rules if kind == "restrict" and tg == k
                          and not allowed(m, k, v, domains(Model(m.ch, [(kind, cd, tg, ef, ms)], [], [], set()), val)[k]))
            viol.append(("configuration_value_out_of_range", k, tuple(msgs)))
    for k in m.ch:
        sets = [r for r in true_rules if r[0] == "set" and r[2] == k]
        vals = {num(r[3]["value"]) if m.ch[k][1] == "number" else r[3]["value"] for r in sets}
        if sets and (len(vals) > 1 or val.get(k) not in vals or not allowed(m, k, val[k], dom[k])):
            viol.append(("configuration_set_conflict", k, tuple(sorted(r[4] for r in sets))))
        d = dom[k]
        if (m.ch[k][1] == "list" and not d) or (m.ch[k][1] == "number" and (d[0] > d[1] or not has_step(m, k, d[0], d[1]))):
            viol.append(("configuration_domain_empty", k, tuple(sorted(r[4] for r in true_rules if r[0] == "restrict" and r[2] == k))))
    for kind, cd, tg, ef, ms in true_rules:
        if kind == "forbid": viol.append((ms, None, ()))
    for code, cols, rows in m.tables:
        if not [r for r in rows if all(cell_ok(m, col, cell, val.get(col)) for col, cell in zip(cols, r))]:
            viol.append(("configuration_table_no_match", code, ()))
    req = set(m.required) | {r[2] for r in true_rules if r[0] == "require"}
    missing = sorted(k for k in req if k not in val)
    look = {}
    if lookahead:
        for k in unset:
            if m.ch[k][1] == "list":
                look[k] = {v: bool(evaluate(m, {**chosen, k: v}, lookahead=False)["violations"]) for v in sorted(shown[k])}
    return {"values": val, "source": src, "domain": shown, "violations": sorted(viol, key=str), "missing": missing,
            "complete": not viol and not missing, "lookahead": look}

# ---- rule 9: configuration records; rule 11: configured items ----
def canon(val):
    pairs = sorted((str(A[k]), str(V[(k, v)]) if CH[k][1] == "list" else norm(v)) for k, v in val.items())
    return json.dumps({"product": str(I["prod"]), "values": pairs}, separators=(",", ":"))
def save_configuration(cx, res):
    assert res["complete"]
    h = hashlib.sha256(canon(res["values"]).encode()).hexdigest()
    row = cx.execute("select id from product_configuration where company_id=%s and product_id=%s and content_hash=%s", (I["co"], I["prod"], h)).fetchone()
    if row: return row[0], False
    cid = new()
    with cx.transaction():
        cx.execute("insert into product_configuration values (%s,%s,%s,%s,now())", (cid, I["co"], I["prod"], h))
        for k, v in res["values"].items():
            lst = CH[k][1] == "list"
            cx.execute("insert into product_configuration_value values (%s,%s,%s,%s,%s,%s,%s)",
                       (I["co"], cid, I["prod"], A[k], CH[k][1], V[(k, v)] if lst else None, None if lst else v))
    return cid, True
def stored_hash_ok(cx, cid):
    code_of, val_of = {v: k for k, v in A.items()}, {v: k[1] for k, v in V.items()}
    vals = {code_of[a]: (val_of[vid] if vid else D(nv)) for a, vid, nv in cx.execute(
        "select variant_attribute_id, variant_attribute_value_id, numeric_value from product_configuration_value where product_configuration_id=%s", (cid,))}
    return hashlib.sha256(canon(vals).encode()).hexdigest() == cx.execute("select content_hash from product_configuration where id=%s", (cid,)).fetchone()[0]
def configured_item(cx, cid):
    """Leaving draft (rule 11): number value rows and the item appear only now."""
    rows = cx.execute("""select pcv.variant_attribute_id, pcv.variant_attribute_value_id, pcv.numeric_value from product_configuration_value pcv
                         join variant_attribute a on a.id = pcv.variant_attribute_id where pcv.product_configuration_id=%s and a.variant_mode='variant'""", (cid,)).fetchall()
    pairs = []
    with cx.transaction():
        for a, vid, nv in rows:
            if vid is None:
                code = norm(D(nv))
                r = cx.execute("select id from variant_attribute_value where variant_attribute_id=%s and numeric_value=%s", (a, nv)).fetchone()
                if r: vid = r[0]
                else:
                    vid = new()
                    cx.execute("insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, value_type, code, name, numeric_value) values (%s,%s,%s,'variant','number',%s,%s,%s)",
                               (vid, I["co"], a, code, code, nv))
            pairs.append((a, vid))
        key = sorted(p[1] for p in pairs)
        r = cx.execute("select id from item where product_id=%s and variant_key=%s::uuid[]", (I["prod"], key)).fetchone()
        if r: return r[0], False
        n = cx.execute("update product set last_item_number = last_item_number + 1 where id=%s returning code, last_item_number", (I["prod"],)).fetchone()
        iid = new()
        cx.execute("insert into item (id, company_id, product_id, code, variant_key) values (%s,%s,%s,%s,%s)", (iid, I["co"], I["prod"], f"{n[0]}-{n[1]}-{t}", key))
        for a, vid in pairs:
            cx.execute("insert into item_variant_value (company_id, item_id, product_id, variant_attribute_id, variant_attribute_value_id) values (%s,%s,%s,%s,%s)", (I["co"], iid, I["prod"], a, vid))
    return iid, True

# ---- rules 12-13: super bill of materials (lab table) ----
COMPONENTS = [  # item, condition, sizing, quantity, quantity_per_value, characteristic
    ("FRAME-S", {"c": "size_class", "op": "eq", "v": "S"}, "fixed", F(1), None, None),
    ("FRAME-M", {"c": "size_class", "op": "eq", "v": "M"}, "fixed", F(1), None, None),
    ("FRAME-L", {"c": "size_class", "op": "eq", "v": "L"}, "fixed", F(1), None, None),
    ("SIDE-RAIL", {}, "linear", F(0), F(2, 1000), "height"),          # metres: two rails of the height
    ("TOP-RAIL", {}, "linear", F(0), F(2, 1000), "width"),
    ("EXT-RAIL", {}, "linear", F(-2, 5), F(1, 1000), "width"),         # metres beyond 400 mm; zero at the minimum
    ("WALL-KIT", {"c": "mounting", "op": "eq", "v": "wall"}, "fixed", F(1), None, None),
    ("FLOOR-KIT", {"c": "mounting", "op": "eq", "v": "floor"}, "fixed", F(1), None, None),
    ("COATING-KIT", {"c": "material", "op": "eq", "v": "steel"}, "fixed", F(1), None, None),
    ("PANEL-ALU", {"c": "material", "op": "eq", "v": "aluminium"}, "fixed", F(2), None, None),
    ("PANEL-STEEL", {"c": "material", "op": "eq", "v": "steel"}, "fixed", F(2), None, None),
    ("PANEL-SS", {"c": "material", "op": "eq", "v": "stainless"}, "fixed", F(2), None, None),
]
def names_in(cd):
    if not cd: return set()
    for k in ("all", "any"):
        if k in cd: return set().union(*(names_in(x) for x in cd[k]))
    if "not" in cd: return names_in(cd["not"])
    return {cd["c"]}
def release_check(components):
    for it, cd, sz, q, qpv, ch in components:
        bad = [n for n in names_in(cd) | ({ch} if ch else set()) if CH[n][0] != "variant"]
        if bad: return ("configuration_characteristic_not_item_defining", it)
        if sz == "linear" and min(q + qpv * F(CH[ch][2][0]), q + qpv * F(CH[ch][2][1])) < 0:
            return ("configured_quantity_negative", it)                 # linear: the extremes cover every value
    return None
def explode(values, good_qty, decimals):
    out = {}
    for it, cd, sz, q, qpv, ch in COMPONENTS:
        if cond(MODEL, cd, values) is not True: continue
        req = (q + (qpv * F(str(values[ch])) if sz == "linear" else 0)) * good_qty
        if req:
            out[it] = (D(req.numerator) / D(req.denominator)).quantize(D(1).scaleb(-decimals.get(it, 0)), rounding=ROUND_CEILING)
    return out
RAILS = {"SIDE-RAIL": 1, "TOP-RAIL": 1, "EXT-RAIL": 1}
COST = {"FRAME-S": 1000000, "FRAME-M": 1600000, "FRAME-L": 2400000, "SIDE-RAIL": 120000, "TOP-RAIL": 120000, "EXT-RAIL": 120000, "WALL-KIT": 300000,
        "FLOOR-KIT": 450000, "COATING-KIT": 200000, "PANEL-ALU": 250000, "PANEL-STEEL": 300000, "PANEL-SS": 700000}
def estimate_configuration(values):
    """Rule 14: a pure function of the values; no item needed."""
    return sum(D(COST[k]) * v for k, v in explode(values, F(1), RAILS).items())

# ---- rule 15: configured price ----
def find_price(cx, values, on, item=None):
    def q(sql, args): return cx.execute(sql + " and start_date<=%s and (end_date is null or end_date>=%s)", args + (on, on)).fetchone()
    base, item_entry = None, False
    if item:
        r = q("select unit_price from price_list_entry where price_list_id=%s and item_id=%s and uom_id=%s and minimum_quantity=0", (I["pl"], item, I["ea"]))
        if r: base, item_entry = F(r[0]), True
    if base is None:
        r = q("select unit_price from price_list_entry where price_list_id=%s and product_id=%s and uom_id=%s and minimum_quantity=0", (I["pl"], I["prod"], I["ea"]))
        if r is None: return None
        base = F(r[0])
    total = base
    for k, v in values.items():
        if item_entry and CH[k][0] == "variant": continue        # the item entry replaces the item-defining part
        if CH[k][1] == "list":
            rows = cx.execute("select product_id, unit_price_extra from price_list_option_extra where price_list_id=%s and variant_attribute_value_id=%s and (product_id=%s or product_id is null)"
                              " and start_date<=%s and (end_date is null or end_date>=%s)", (I["pl"], V[(k, v)], I["prod"], on, on)).fetchall()
            pick = [r for r in rows if r[0] is not None] or rows
            total += sum((F(r[1]) for r in pick), F(0))
        else:
            r = q("select rate_per_value from price_list_characteristic_rate where price_list_id=%s and product_id=%s and variant_attribute_id=%s", (I["pl"], I["prod"], A[k]))
            if r: total += F(r[0]) * F(str(v))
    return (D(total.numerator) / D(total.denominator)).quantize(D("0.0000000001"), rounding=ROUND_HALF_UP)

def check(name, got, want):
    ok = got == want; RESULTS.append((ok, name, str(got))); print(("PASS " if ok else "FAIL ") + f"{name} -- {got}")
def trial(name, fn, match):
    class Rollback(Exception): pass
    t2 = conn()
    try:
        with t2.transaction():
            fn(t2); t2.execute("set constraints all immediate"); raise Rollback()
    except Rollback:
        ok, detail = False, "succeeded"
    except Exception as e:
        msg = str(e).splitlines()[0]; ok, detail = match in msg, "failed: " + msg
    finally:
        t2.close()
    RESULTS.append((ok, name, detail)); print(("PASS " if ok else "FAIL ") + name + " -- " + detail)
def codes(r): return sorted(v[0] for v in r["violations"])

cx = conn(); cx.autocommit = True
MODEL = load_model(cx, I["rev"])
MODEL2 = load_model(cx, I["rev2"])
# ---- E: evaluation ----
r = evaluate(MODEL, {"width": "600"})
check("E01 width 600: the size_band table narrows size_class to S, which is taken; material narrows to aluminium or steel",
      (r["values"].get("size_class"), r["source"].get("size_class"), r["domain"]["material"]), ("S", "rule", frozenset({"aluminium", "steel"})))
check("E02 defaults fill mounting and height, one at a time", (r["values"].get("mounting"), r["values"].get("height"), r["source"].get("height")), ("none", D(600), "default"))
check("E03 material is item-defining, so required: incomplete", (r["complete"], r["missing"]), (False, ["material"]))
r = evaluate(MODEL, {"width": "1600"})
check("E04 width 1600: material steel or stainless, size L, mounting floor by rule, height 600-1200",
      (r["domain"]["material"], r["values"].get("size_class"), r["values"].get("mounting"), r["domain"]["height"]),
      (frozenset({"steel", "stainless"}), "L", "floor", (D(600), D(1200))))
r = evaluate(MODEL, {"width": "600", "material": "aluminium"})
check("E05 aluminium limits height to 550, so the 600 default does not apply: height missing", (r["domain"]["height"], r["missing"]), ((D(300), D(550)), ["height"]))
r = evaluate(MODEL, {"width": "600", "material": "steel", "color": "grey"})
check("E06 a full configuration is complete", (r["complete"], r["violations"]), (True, []))
r = evaluate(MODEL, {"width": "600", "material": "steel", "color": "grey", "mounting": "wall", "height": "1100"})
check("E07 wall mounting above 1000 mm is forbidden", codes(r), ["wall_too_tall"])
r = evaluate(MODEL, {"width": "625", "material": "steel", "color": "grey"})
check("E08 a width off the 50 mm step is out of range", [v[:2] for v in r["violations"]], [("configuration_value_out_of_range", "width")])
r = evaluate(MODEL, {"width": "600", "material": "steel", "color": "grey", "mounting": "floor", "height": "500"})
check("E09 an out-of-range value names the restricting rule", r["violations"], [("configuration_value_out_of_range", "height", ("floor_min_height",))])
r = evaluate(MODEL, {"width": "1600", "material": "aluminium"})
check("E10 aluminium at 1600 mm: out of range by the restrict rule, and the two tables leave no size class",
      ([v[:2] for v in r["violations"] if v[0] == "configuration_value_out_of_range"], [v[1] for v in r["violations"] if v[0] == "configuration_domain_empty"]),
      ([("configuration_value_out_of_range", "material")], ["size_class"]))
r = evaluate(MODEL, {"width": "600", "material": "aluminium", "mounting": "floor"})
check("E11 aluminium on the floor leaves no height: an empty domain naming both rules",
      [v for v in r["violations"] if v[0] == "configuration_domain_empty"], [("configuration_domain_empty", "height", ("aluminium_max_height", "floor_min_height"))])
r = evaluate(MODEL, {"width": "1600", "mounting": "none", "material": "steel", "color": "grey"})
check("E12 a user value against a true set rule is a conflict", r["violations"], [("configuration_set_conflict", "mounting", ("large_on_floor",))])
r = evaluate(MODEL, {"width": "1600", "material": "stainless"})
check("E13 two true set rules disagreeing: a conflict naming both rules, so never complete",
      (r["complete"], [v for v in r["violations"] if v[0] == "configuration_set_conflict"]),
      (False, [("configuration_set_conflict", "mounting", ("large_on_floor", "stainless_on_wall"))]))
r = evaluate(MODEL, {"width": "600", "height": "1100"})
check("E14 lookahead: wall would break the height rule, none and floor would not", r["lookahead"]["mounting"], {"floor": False, "none": False, "wall": True})
r1, r2 = evaluate(MODEL, {"width": "600", "material": "steel", "color": "grey"}), evaluate(MODEL, {"color": "grey", "material": "steel", "width": "600.0"})
check("E15 input order and number spelling do not matter (600 = 600.0)", canon(r1["values"]) == canon(r2["values"]), True)
cfg_long = {"width": "1900", "material": "steel", "color": "grey"}
check("E16 a configuration valid under revision 1 is refused under revision 2 (copy re-evaluates: configuration_invalid)",
      (evaluate(MODEL, cfg_long)["complete"], codes(evaluate(MODEL2, cfg_long))), (True, ["width_limit"]))

# ---- R: order independence and idempotence on random models ----
def random_model(rng):
    ch = {f"k{i}": ("variant", "list", ["a", "b", "c"]) for i in range(4)}
    def term_():
        k = rng.choice(list(ch)); op = rng.choice(["eq", "ne", "in", "not_in"])
        return {"c": k, "op": op, "v": rng.choice("abc") if op in ("eq", "ne") else rng.sample("abc", 2)}
    def cond_(d=0):
        x = rng.random()
        if d < 2 and x < 0.2: return {"all": [cond_(d + 1), cond_(d + 1)]}
        if d < 2 and x < 0.35: return {"any": [cond_(d + 1), cond_(d + 1)]}
        if d < 2 and x < 0.45: return {"not": cond_(d + 1)}
        return term_()
    rules = []
    for _ in range(rng.randint(3, 9)):
        tg = rng.choice(list(ch)); kind = rng.choice(["restrict", "restrict", "set"])
        eff = {"values": rng.sample("abc", rng.randint(1, 2))} if kind == "restrict" else {"value": rng.choice("abc")}
        rules.append((kind, cond_(), tg, eff, f"m{len(rules)}"))
    tables = []
    for n in range(rng.randint(0, 2)):
        cols = rng.sample(list(ch), 2)
        tables.append((f"t{n}", cols, [[rng.choice("abc*"), rng.choice("abc*")] for _ in range(rng.randint(1, 4))]))
    return Model(ch, rules, tables, [(rng.choice(list(ch)), rng.choice("abc"), {})], set(ch))
rng, same, idem, done = random.Random(46), 0, 0, 0
for n in range(300):
    m = random_model(rng)
    chosen = {k: rng.choice("abc") for k in rng.sample(list(m.ch), rng.randint(0, 2))}
    a = evaluate(m, chosen)
    perm = Model(m.ch, rng.sample(m.rules, len(m.rules)), rng.sample(m.tables, len(m.tables)), m.defaults, m.required)
    b = evaluate(perm, dict(reversed(list(chosen.items()))))
    same += (a["values"], a["domain"], a["violations"], a["missing"]) == (b["values"], b["domain"], b["violations"], b["missing"])
    if a["complete"]:
        done += 1
        again = evaluate(m, a["values"])
        idem += again["complete"] and again["values"] == a["values"]
check("R01 300 random models: permuting rules, tables and inputs never changes the result, and the bound is never reached", same, 300)
check(f"R02 every complete result ({done} of 300) is a fixed point: evaluating its values again gives the same complete result", idem, done)

# ---- C: configurations and configured items ----
cfgA = evaluate(MODEL, {"width": "600", "material": "steel", "color": "grey"})
cfgA2 = evaluate(MODEL, {"width": "600", "material": "steel", "color": "blue"})          # differs only in a line option
cfgB = evaluate(MODEL, {"width": "1600", "height": "900", "material": "steel", "color": "grey"})
idA, newA = save_configuration(cx, cfgA)
idA_again, newA_again = save_configuration(cx, evaluate(MODEL, {"color": "grey", "material": "steel", "width": "600.0"}))
check("C01 the same choices are stored once (content-addressed)", (idA == idA_again, newA, newA_again), (True, True, False))
check("C02 the stored hash recomputes from the stored values (INV-114)", stored_hash_ok(cx, idA), True)
idA2, _ = save_configuration(cx, cfgA2); idB, _ = save_configuration(cx, cfgB)
nrows = lambda: cx.execute("select count(*) from variant_attribute_value where variant_attribute_id in (%s,%s)", (A["width"], A["height"])).fetchone()[0]
check("C03 saving configurations creates no number value rows (quotations create nothing)", nrows(), 0)
itA, nA = configured_item(cx, idA); itA2, nA2 = configured_item(cx, idA2); itB, nB = configured_item(cx, idB)
check("C04 configurations differing only in a line option share one configured item", (itA == itA2, nA, nA2), (True, True, False))
check("C05 different item-defining values make another item", (itA != itB, nB), (True, True))
check("C06 number value rows appear with the items, once per characteristic and number (A2 reuses A's)", nrows(), 4)
check("C07 item codes come from the product counter", cx.execute("select last_item_number from product where id=%s", (I["prod"],)).fetchone()[0], 2)
def bad_config(x, vt, vid, nv, attr="material"):
    cid = new()
    x.execute("insert into product_configuration values (%s,%s,%s,%s,now())", (cid, I["co"], I["prod"], "a" * 64))
    x.execute("insert into product_configuration_value values (%s,%s,%s,%s,%s,%s,%s)", (I["co"], cid, I["prod"], A[attr], vt, vid, nv))
trial("C08 a list characteristic cannot hold a number", lambda x: bad_config(x, "number", None, 5), "fk_product_configuration_value_type")
trial("C09 a number characteristic stores a number, not a value row", lambda x: bad_config(x, "number", V[("material", "steel")], None, attr="width"), "ck_product_configuration_value_one")
trial("C10 a number value row on a list characteristic is refused", lambda x: x.execute(
    "insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, value_type, code, name, numeric_value) values (%s,%s,%s,'variant','number','5','5',5)", (new(), I["co"], A["material"])), "fk_variant_attribute_value_attribute")
def line_option_number(x):
    a = new()
    x.execute("insert into variant_attribute (id, company_id, code, name, variant_mode, value_type, minimum_value, maximum_value, step_value, decimal_places) values (%s,%s,%s,'n','line_option','number',0,9,1,0)", (a, I["co"], "tmp" + t))
    x.execute("insert into variant_attribute_value (id, company_id, variant_attribute_id, variant_mode, value_type, code, name, numeric_value) values (%s,%s,%s,'line_option','number','1','1',1)", (new(), I["co"], a))
trial("C11 line-option numbers never become value rows", line_option_number, "ck_variant_attribute_value_number")
trial("C12 a list characteristic carries no number settings", lambda x: x.execute(
    "insert into variant_attribute (id, company_id, code, name, value_type, step_value) values (%s,%s,%s,'n','list',5)", (new(), I["co"], "tmp2" + t)), "ck_variant_attribute_number")
trial("C13 a configurable product must create items on order", lambda x: x.execute("update product set is_item_created_on_order=false where id=%s", (I["prod"],)), "ck_product_configurable")
# immutability (rules 4, 9)
trial("C14 a released revision cannot change", lambda x: x.execute("update configuration_model_revision set start_date='2026-02-01' where id=%s", (I["rev"],)), "revision_released")
trial("C15 a released revision gets no new rule", lambda x: x.execute(
    "insert into configuration_rule (id, company_id, configuration_model_revision_id, product_id, position, kind, condition, message_code) values (%s,%s,%s,%s,999,'forbid','{}','x')", (new(), I["co"], I["rev"], I["prod"])), "revision_released")
trial("C16 a released revision's table rows cannot change", lambda x: x.execute(
    "update configuration_table_row set cells='[\"*\",\"*\"]' where configuration_table_id in (select id from configuration_table where configuration_model_revision_id=%s)", (I["rev"],)), "revision_released")
trial("C17 a configuration cannot be changed", lambda x: x.execute("update product_configuration set created_at=now() where id=%s", (idA,)), "configuration_immutable")
trial("C18 a configuration gets no value from a later transaction", lambda x: x.execute(
    "insert into product_configuration_value values (%s,%s,%s,%s,'list',%s,null)", (I["co"], idA, I["prod"], A["label"], V[("label", "text")])), "configuration_immutable")
def savepoint_save(x):
    """C20: a configuration saved inside a savepoint (a command batch) still takes its values."""
    with x.transaction():
        cid, created = save_configuration(x, evaluate(MODEL, {"width": "800", "material": "steel", "color": "blue"}))
        n = x.execute("select count(*) from product_configuration_value where product_configuration_id=%s", (cid,)).fetchone()[0]
    return created, n
cx2 = conn()
with cx2.transaction():
    got = savepoint_save(cx2)
cx2.close()
check("C20 a configuration saved inside a savepoint takes all six values", got, (True, 6))
def move_rule(x):
    d = new()
    x.execute("insert into configuration_model_revision (id, company_id, configuration_model_id, product_id, revision, start_date) values (%s,%s,%s,%s,3,'2027-01-01')", (d, I["co"], I["model"], I["prod"]))
    x.execute("update configuration_rule set configuration_model_revision_id=%s where configuration_model_revision_id=%s and position=10", (d, I["rev"]))
trial("C21 a rule cannot be moved out of a released revision", move_rule, "revision_released")
ddl = open(os.environ.get("ERPME_DS56", os.path.expanduser("~/Projects/ERPMe/docs/design/DS-56-product-configuration.sql"))).read()
tables = re.findall(r"^CREATE TABLE (\w+)", ddl, re.M)
missing = [tb for tb in tables if not cx.execute("select 1 from information_schema.columns where table_schema='erpme' and table_name=%s and column_name='company_id'", (tb,)).fetchone()]
check(f"C19 all {len(tables)} DS-56 tables carry company_id (missing: {missing or 'none'})", missing, [])

# ---- S: structure, release checks and explosion ----
vA, vB = cfgA["values"], cfgB["values"]
check("S01 the release check passes when conditions and sizing name only item-defining characteristics", release_check(COMPONENTS), None)
check("S02 a condition on a line option is refused at release", release_check(COMPONENTS + [("PAINT-BLUE", {"c": "color", "op": "eq", "v": "blue"}, "fixed", F(1), None, None)]),
      ("configuration_characteristic_not_item_defining", "PAINT-BLUE"))
check("S03 sizing that is negative at the width minimum is refused at release", release_check(COMPONENTS + [("SPACER", {}, "linear", F(-1), F(1, 1000), "width")]),
      ("configured_quantity_negative", "SPACER"))
check("S04 600 x 600 steel: frame S, rails 1.2 m each, 0.2 m extension, coating, steel panels", explode(vA, F(1), RAILS),
      {"FRAME-S": D(1), "SIDE-RAIL": D("1.2"), "TOP-RAIL": D("1.2"), "EXT-RAIL": D("0.2"), "COATING-KIT": D(1), "PANEL-STEEL": D(2)})
check("S05 1600 x 900 steel: frame L, floor kit by rule, 3.2 m top rail", explode(vB, F(1), RAILS),
      {"FRAME-L": D(1), "SIDE-RAIL": D("1.8"), "TOP-RAIL": D("3.2"), "EXT-RAIL": D("1.2"), "FLOOR-KIT": D(1), "COATING-KIT": D(1), "PANEL-STEEL": D(2)})
check("S06 three units: 3.6 m of side rail rounded once up to whole metres", explode(vA, F(3), {})["SIDE-RAIL"], D(4))
check("S07 at the 400 mm minimum the extension is zero and dropped", "EXT-RAIL" in explode(evaluate(MODEL, {"width": "400", "material": "steel", "color": "grey"})["values"], F(1), RAILS), False)
check("S08 a line option never changes the explosion", explode(vA, F(1), RAILS) == explode(cfgA2["values"], F(1), RAILS), True)

# ---- P: configured price ----
X2 = cx.execute
X2("insert into price_list (id, company_id, code, name, kind, currency, is_default) values (%s,%s,'L6','L6','sale','VND',true)", (I["pl"], I["co"]))
X2("insert into price_list_entry (id, company_id, price_list_id, product_id, uom_id, start_date, unit_price) values (%s,%s,%s,%s,%s,'2026-01-01',5000000)", (new(), I["co"], I["pl"], I["prod"], I["ea"]))
for attr, val_, mode, amount in (("material", "stainless", "variant", 2000000), ("mounting", "floor", "variant", 800000), ("mounting", "wall", "variant", 600000), ("color", "blue", "line_option", 300000)):
    X2("insert into price_list_option_extra (id, company_id, price_list_id, product_id, variant_attribute_id, variant_attribute_value_id, variant_mode, start_date, unit_price_extra) values (%s,%s,%s,%s,%s,%s,%s,'2026-01-01',%s)",
       (new(), I["co"], I["pl"], I["prod"], A[attr], V[(attr, val_)], mode, amount))
for k, rate in (("width", 3000), ("height", 2000)):
    X2("insert into price_list_characteristic_rate (id, company_id, price_list_id, product_id, variant_attribute_id, start_date, rate_per_value) values (%s,%s,%s,%s,%s,'2026-01-01',%s)",
       (new(), I["co"], I["pl"], I["prod"], A[k], rate))
check("P01 base 5m + 600 mm x 3,000 + 600 mm x 2,000", find_price(cx, vA, "2026-06-01"), D("8000000.0000000000"))
check("P02 a blue line option adds 300k", find_price(cx, cfgA2["values"], "2026-06-01"), D("8300000.0000000000"))
check("P03 1600 x 900 floor-mounted: 5m + 800k + 4.8m + 1.8m", find_price(cx, vB, "2026-06-01"), D("12400000.0000000000"))
X2("insert into price_list_entry (id, company_id, price_list_id, item_id, uom_id, start_date, unit_price) values (%s,%s,%s,%s,%s,'2026-01-01',7500000)", (new(), I["co"], I["pl"], itA, I["ea"]))
check("P04 an item entry replaces the item-defining part; line options still add", (find_price(cx, vA, "2026-06-01", itA), find_price(cx, cfgA2["values"], "2026-06-01", itA)),
      (D("7500000.0000000000"), D("7800000.0000000000")))
trial("P05 an entry names an item or a product, not both", lambda x: x.execute(
    "insert into price_list_entry (id, company_id, price_list_id, item_id, product_id, uom_id, start_date, unit_price) values (%s,%s,%s,%s,%s,%s,'2027-01-01',1)",
    (new(), I["co"], I["pl"], itA, I["prod"], I["ea"])), "ck_price_list_entry_target")
trial("P06 product-level entries do not overlap", lambda x: x.execute(
    "insert into price_list_entry (id, company_id, price_list_id, product_id, uom_id, start_date, unit_price) values (%s,%s,%s,%s,%s,'2026-06-01',1)",
    (new(), I["co"], I["pl"], I["prod"], I["ea"])), "ex_price_list_entry_overlap")
trial("P07 an extra's mode must match its value's mode", lambda x: x.execute(
    "insert into price_list_option_extra (id, company_id, price_list_id, product_id, variant_attribute_id, variant_attribute_value_id, variant_mode, start_date, unit_price_extra) values (%s,%s,%s,%s,%s,%s,'line_option','2027-01-01',1)",
    (new(), I["co"], I["pl"], I["prod"], A["mounting"], V[("mounting", "none")])), "fk_price_list_option_extra_value")
trial("P08 number rates of one characteristic do not overlap", lambda x: x.execute(
    "insert into price_list_characteristic_rate (id, company_id, price_list_id, product_id, variant_attribute_id, start_date, rate_per_value) values (%s,%s,%s,%s,%s,'2026-03-01',1)",
    (new(), I["co"], I["pl"], I["prod"], A["width"])), "ex_price_list_characteristic_rate_overlap")
trial("P09 a number rate needs a number characteristic", lambda x: x.execute(
    "insert into price_list_characteristic_rate (id, company_id, price_list_id, product_id, variant_attribute_id, start_date, rate_per_value) values (%s,%s,%s,%s,%s,'2026-01-01',1)",
    (new(), I["co"], I["pl"], I["prod"], A["material"])), "fk_price_list_characteristic_rate_type")

# ---- K: estimates before any item exists (rule 14) ----
kA, kB = estimate_configuration(vA), estimate_configuration(vB)
check("K01 estimate of 600 x 600 steel from its values alone", kA, D("2112000.0"))
check("K02 estimate of 1600 x 900 steel", kB, D("4394000.0"))
check("K03 the two configurations' estimates differ, so their configured items start from different costs", kA != kB, True)
cx.close()
print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
