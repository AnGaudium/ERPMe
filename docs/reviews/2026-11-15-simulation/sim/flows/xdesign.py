"""Helpers for flows 7-11 (ADR-0057 to ADR-0064): the validation lab's reference functions loaded by name, the settings
registry (DS-28-settings) and change proposals. Simulation code, not product code."""
import ast
import json
import os
from decimal import Decimal as D
from types import SimpleNamespace

from .core import W, ins, new_id, now, sha, jsonable
from . import platform as P

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
LABDIR = os.path.join(DOCS, "reviews/2026-11-14-design-validation/lab")
_LIBS = {}
# up to this marker every top-level statement but a check runs (tables built by loops and calls); after it, definitions only
FULL_UNTIL = {"t19_barcode": "P: pure checks"}


def lab(name):
    """The definitions of a lab script (imports, functions, classes, constant assignments), without its checks: the design's
    'rules as code'. Each top-level statement runs on its own; a statement that fails (a check-only assignment) is skipped."""
    if name in _LIBS:
        return _LIBS[name]
    path = os.path.join(LABDIR, name + ".py")
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    marker = FULL_UNTIL.get(name)
    stop = next((i + 1 for i, l in enumerate(src.splitlines()) if marker and marker in l), 0)
    ns = {"__name__": "lab_" + name, "__file__": path}
    import contextlib, io
    for node in tree.body:
        if node.lineno < stop or isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)) and "check(" in ast.unparse(node):
                continue
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(ast.Module([node], []), path, "exec"), ns)
            except Exception:  # noqa: BLE001
                pass
    _LIBS[name] = SimpleNamespace(**ns)
    return _LIBS[name]


# ======================================================================= settings registry (ADR-0063; DS-28-settings)
def num(v):
    """A JSON value for a jsonb column: numbers stay numbers (the sim's encoder turns Decimals into strings)."""
    if isinstance(v, D) or (isinstance(v, float)):
        v = D(str(v))
        return int(v) if v == v.to_integral_value() else float(v)
    return v


def load_setting_definitions(db):
    """setting_definition rows from catalogs/settings.csv (installation data written at startup)."""
    if db.val("select count(*) from setting_definition"):
        return
    S = lab("t24_settings")
    W.SETTINGS = {}
    for r in S.SET:
        t = r["value_type"]
        b = S.bounds_of(r)
        dflt = S.default_of(r)
        dkind = dflt if dflt in ("fail_closed", "unset") else "value"
        dirn, order = S.direction_of(r)
        core = None if dkind != "value" else num(dflt)
        ins(db, "setting_definition", setting_key=r["key"], area=r["area"], scopes=r["scope"].split(";"), storage=r["storage"], value_type=t,
            default_kind=dkind, core_default=core, min_value=b.get("min"), max_value=b.get("max"),
            allowed_values=b.get("values"), direction=dirn, direction_order=order, leaf_code=r["leaf"], change_effect=r["change_effect"],
            outdates=r["outdates"], source=r["source"], registry_version=r["added_in"], recorded_at=now())
        W.SETTINGS[r["key"]] = r


def setting_row(key):
    return lab("t24_settings").S[key]


def get_setting(db, key, scope_kind="company", scope_ref="", placeholders=None, on=None):
    """get_setting: the company value in force on the date, else the core default (rule 2 order, reduced)."""
    on = on or W.today
    v = db.val("""select value from setting_value where company_id=%s and setting_key=%s and scope_kind=%s and scope_ref=%s
                  and placeholder_values=%s and effective_from<=%s order by effective_from desc, recorded_at desc limit 1""",
               (W.co, key, scope_kind, scope_ref, json.dumps(placeholders or {}), on))
    if v is None and scope_kind != "company":
        v = db.val("""select value from setting_value where company_id=%s and setting_key=%s and scope_kind='company'
                      and placeholder_values=%s and effective_from<=%s order by effective_from desc, recorded_at desc limit 1""",
                   (W.co, key, json.dumps(placeholders or {}), on))
    if v is None:
        v = json.loads(db.val("select core_default::text from setting_definition where setting_key=%s", (key,)))
    return v


def write_setting(db, key, value, user, reason, scope_kind="company", scope_ref="", proposal=None, approver=None):
    """The setting_value row; the trigger derives replaced_value and change_kind."""
    sid = new_id("setting_value")
    ins(db, "setting_value", id=sid, setting_key=key, scope_kind=scope_kind, scope_ref=scope_ref, value=num(value),
        value_type=setting_row(key)["value_type"], direction=db.val("select direction from setting_definition where setting_key=%s", (key,)),
        reason=reason, effective_from=W.today, changed_by_user_id=user["id"], change_proposal_id=proposal, approved_by_user_id=approver,
        registry_version="0.1.0", change_kind=None)
    kind, repl = db.one("select change_kind, replaced_value from setting_value where id=%s", (sid,))
    return sid, kind, repl


# ======================================================================= change proposals by a person (ADR-0029)
def person_proposal(db, user_tpl, number, reason, items, plan_extra=None):
    """A change proposal drafted and submitted by a person: items are (command, payload, target_table, field_changes)."""
    actor = P.person(user_tpl)
    plan = {"items": [{"command": c, "payload": p} for c, p, _, _ in items], **(plan_extra or {})}
    cp = P.create_doc(db, "change_proposal", actor, header={"plan": plan, "plan_hash": sha(plan), "evidence": [], "reason": reason,
                                                           "document_date": W.today}, header_table="change_proposal", number=number)
    for i, (c, p, tt, fc) in enumerate(items):
        ins(db, "change_proposal_item", id=new_id("change_proposal_item"), change_proposal_id=cp["id"], item_index=i, command_type=c, schema_version=1,
            payload=p, target_table=tt, field_changes=fc)
    P.audit(db, "CreateChangeProposal", actor, doc=cp, subject_table="change_proposal", subject_id=cp["id"])
    dec, res = P.submit(db, cp, actor, {"amount": 0}, "SubmitChangeProposal")
    return cp, dec, res
