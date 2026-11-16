"""Platform rules as pure Python over the design tables: permissions (ADR-0054), documents and versions with taint
(ADR-0009, ADR-0029), events and audit (ADR-0013, ADR-0038), work items (ADR-0042), policy and approval pools
(ADR-0043, ADR-0055), change proposals (ADR-0029), agent runs (ADR-0050). Simulation code, not product code.
"""
import csv
import os
import re
from decimal import Decimal as D

from .core import (EFF, W, J, jsonable, ins, upd, new_id, now, sha, TRACE)

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
CAT = os.path.join(DOCS, "catalogs")
LEVELS = ["none", "read", "edit", "post", "full"]


def read_csv(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ======================================================================= catalogs
AREAS = {r["code"]: r["parent_code"] or None for r in read_csv(os.path.join(CAT, "authorization-areas.csv"))}
VERB_LEVEL = {r["verb"]: r["level"] for r in read_csv(os.path.join(CAT, "authorization-verb-levels.csv"))}
ROLE_LEVELS = {}
for _r in read_csv(os.path.join(CAT, "role-template-levels.csv")):
    ROLE_LEVELS.setdefault(_r["template"], {})[_r["node"]] = (_r["level"], _r["can_approve"] == "true")
TEMPLATES = read_csv(os.path.join(CAT, "role-templates.csv"))
SEGREGATION = read_csv(os.path.join(CAT, "segregation-rules.csv"))
WORK_ITEM_KINDS = {r["code"]: r for r in read_csv(os.path.join(CAT, "work-item-kinds.csv"))}

# command type (without its verb) -> authorization node, where the snake-case name is not itself a node
TYPE_NODE = {"partner": "partner", "contact": "partner", "partner_item": "partner", "partner_email_domain": "partner",
             "price_list": "price_list", "price_list_entries": "price_list", "price_list_option_extras": "price_list",
             "price_list_characteristic_rates": "price_list", "item": "product", "interaction": "interaction",
             "planned_order": "planned_order", "planning": "planning_run", "forecast": "forecast",
             "bank_statement": "bank_statement", "bank_line": "bank_statement", "bank_line_suggestion": "bank_statement",
             "e_invoice_record": "purchase_invoice", "e_invoice_supplier": "purchase_invoice",
             "sales_invoice_e_invoice_outcome": "sales_invoice", "credit_hold": "sales_order", "sales_history": "forecast",
             "role_assignment": "role", "partner_bank_account": "partner_bank_account", "general_journal": "general_journal",
             "outbound_message": "outbound_message", "change_proposal": "change_proposal", "agent_run": "agent", "uom_alias": "product", "product_uom": "product", "uom": "product",
             }


def split_command(command):
    m = re.match(r"^([A-Z][a-z]+)([A-Z]\w*)$", command)
    verb, rest = m.group(1), m.group(2)
    snake = re.sub(r"(?<!^)([A-Z])", r"_\1", rest).lower()
    return verb, snake


def node_of(command):
    verb, snake = split_command(command)
    if snake in TYPE_NODE:
        return TYPE_NODE[snake]
    if snake in AREAS:
        return snake
    raise KeyError(f"no authorization node for {command}")


def row_for(template, node):
    """The most specific row of the template on the node or an ancestor (ADR-0054 rule 9)."""
    rows = ROLE_LEVELS.get(template, {})
    n = node
    while n:
        if n in rows:
            return rows[n], n
        n = AREAS.get(n)
    return ("none", False), None


def can(user, command, node=None):
    """(allowed, explanation). Approve and Reject come from can_approve; other verbs from their level."""
    verb, _ = split_command(command)
    node = node or node_of(command)
    (level, approve), at = row_for(user["template"], node)
    if verb in ("Approve", "Reject"):
        ok = approve and level != "none"
        return ok, f"{user['template']} on {at or node}: level {level}, can_approve {str(approve).lower()}"
    need = VERB_LEVEL.get(verb, "edit")
    ok = LEVELS.index(level) >= LEVELS.index(need)
    return ok, f"{user['template']} on {at or node}: level {level}, {verb} needs {need}"


def can_start_agent(user, agent_type):
    (level, _), _ = row_for(user["template"], f"agent_{agent_type}")
    return LEVELS.index(level) >= LEVELS.index("edit")


# ======================================================================= actors
class Actor:
    """The actor context of a command (ADR-0017 rule 16)."""
    def __init__(self, kind, user=None, on_behalf_of=None, run=None, origin_run=None, label=None):
        self.kind, self.user, self.on_behalf_of, self.run, self.origin_run = kind, user, on_behalf_of, run, origin_run
        self.label = label

    @property
    def actor_id(self):
        if self.kind == "human":
            return self.user["id"]
        if self.kind == "agent":
            return self.run["id"]          # the agent run ID (sim review 16, note on ADR-0009)
        return W.system_id

    @property
    def human(self):
        return self.user if self.kind == "human" else self.on_behalf_of

    @property
    def tainted(self):
        return bool((self.run and self.run.get("tainted")) or (self.origin_run and self.origin_run.get("tainted")))

    def describe(self):
        if self.label:
            return self.label
        if self.kind == "human":
            return f"{self.user['name']} ({self.user['template']})"
        if self.kind == "agent":
            return f"{self.run['agent_type']} agent run, for {self.on_behalf_of['name']}" + (" (tainted)" if self.run.get("tainted") else "")
        return "system" + (f" on behalf of {self.on_behalf_of['name']}" if self.on_behalf_of else "")


def person(template):
    return Actor("human", user=W.user[template])


def system_for(user, origin_run=None):
    return Actor("system", on_behalf_of=user, origin_run=origin_run)


# ======================================================================= audit and events
CHAIN_OVERRIDE = {}  # set while an automation action runs: {"id", "depth", "rule"} (ADR-0058 rule 12)


def chain_for(actor, command):
    """ADR-0058 rule 12 causation chain: new at a person's, transport's or scheduled job's command (one per command and clock
    instant, so the audit row and the events of one command share it); inherited by everything an agent run does."""
    import uuid as _u
    if CHAIN_OVERRIDE:
        return CHAIN_OVERRIDE
    run = actor.origin_run or actor.run
    key = f"run:{run['id']}" if run else f"cmd:{actor.actor_id}:{command}:{now().isoformat()}"
    return {"id": _u.uuid5(_u.NAMESPACE_URL, "nativeflows-sim-chain:" + key), "depth": 0, "rule": None}


COMMAND_FLAGS = {}   # command -> (effect_class, is_human_only, is_proposal_bound, is_draft_only, is_internal_only)


def audit(db, command, actor, effect_class="other", subject_table=None, subject_id=None, doc=None, policy_decision_id=None,
          check_codes=(), human_only=False, proposal_bound=False, draft_only=False, internal_only=False, plan_hash=None, reason=None):
    aid = new_id("audit_record")
    ch = chain_for(actor, command)
    ins(db, "audit_record", id=aid, causation_chain_id=ch["id"], causation_depth=ch["depth"], automation_rule_version_id=ch["rule"], business_date=W.today, command_type=command, schema_version=1, effect_class=effect_class,
        is_human_only=human_only, is_proposal_bound=proposal_bound, is_draft_only=draft_only, is_internal_only=internal_only,
        actor_kind=actor.kind, actor_id=actor.actor_id, on_behalf_of_id=(actor.on_behalf_of or {}).get("id"),
        agent_run_id=(actor.run or {}).get("id"), origin_agent_run_id=(actor.origin_run or actor.run or {}).get("id"),
        policy_decision_id=policy_decision_id, subject_table=subject_table, subject_id=subject_id,
        document_id=doc["id"] if doc else None, document_version=doc["version"] if doc else None,
        plan_hash=plan_hash, check_codes=list(check_codes), reason=reason)
    return aid


def emit(db, event_type, subject_table, subject_id, actor, command, payload=None, tainted=False):
    seq = db.val("select last_sequence from event_subject where subject_table=%s and subject_id=%s", (subject_table, subject_id))
    if seq is None:
        seq = 1
        ins(db, "event_subject", subject_table=subject_table, subject_id=subject_id, last_sequence=1)
    else:
        seq += 1
        upd(db, "event_subject", {"subject_table": subject_table, "subject_id": subject_id}, last_sequence=seq)
    eid = new_id("outbox_event")
    ch = chain_for(actor, command)
    ins(db, "outbox_event", id=eid, causation_chain_id=ch["id"], causation_depth=ch["depth"], automation_rule_version_id=ch["rule"], event_type=event_type, schema_version=1, subject_table=subject_table, subject_id=subject_id,
        subject_sequence=seq, payload=payload or {"id": str(subject_id)}, actor_kind=actor.kind, actor_id=actor.actor_id,
        on_behalf_of_id=(actor.on_behalf_of or {}).get("id"), agent_run_id=(actor.run or {}).get("id"),
        origin_agent_run_id=(actor.origin_run or actor.run or {}).get("id"), is_tainted=bool(tainted or actor.tainted),
        business_date=W.today, command_type=command)
    return {"event": event_type, "id": str(eid), "subject": subject_table, "tainted": bool(tainted or actor.tainted)}


# ======================================================================= work items (ADR-0042)
def raise_item(db, kind, subject_table, subject_id, owner, due_days=1, details=None, tainted=False, origin_event=None,
               origin_run=None, open_key=None):
    wid = new_id("work_item")
    okind, oval = owner
    cols = {"owner_kind": okind, "owner_user_id": oval if okind == "user" else None, "owner_role": oval if okind == "role" else None,
            "owner_approval_stage_id": oval if okind == "approval_stage" else None}
    import datetime as _dt
    ins(db, "work_item", id=wid, kind=kind, subject_table=subject_table, subject_id=subject_id,
        open_key=open_key or f"{kind}:{subject_id}", state="open", due_date=W.today + _dt.timedelta(days=due_days),
        details=details or {}, is_tainted=tainted, origin_event_id=origin_event, origin_agent_run_id=origin_run, version=1, **cols)
    W.code_of[wid] = kind
    return {"id": wid, "kind": kind, "owner": f"{okind}:{W.code_of.get(oval, oval)}", "tainted": tainted, "state": "open"}


def claim_item(db, item_id, by_kind, by_id):
    import datetime as _dt
    t = now()
    v = db.val("select version from work_item where id=%s", (item_id,))
    upd(db, "work_item", {"id": item_id}, state="claimed", claimed_by_kind=by_kind, claimed_by_id=by_id, claimed_at=t,
        claim_expires_at=(t + _dt.timedelta(minutes=30)) if by_kind == "agent_run" else None, version=v + 1)


def unclaim_item(db, item_id):
    v = db.val("select version from work_item where id=%s", (item_id,))
    upd(db, "work_item", {"id": item_id}, state="open", claimed_by_kind=None, claimed_by_id=None, claimed_at=None,
        claim_expires_at=None, version=v + 1)


def resolve_item(db, item_id, resolution, state="done"):
    v = db.val("select version from work_item where id=%s", (item_id,))
    upd(db, "work_item", {"id": item_id}, state=state, resolution=resolution if state == "done" else None, resolved_at=now(),
        claimed_by_kind=None, claimed_by_id=None, claimed_at=None, claim_expires_at=None, version=v + 1)
    return {"id": item_id, "kind": W.code_of.get(item_id), "state": state, "resolution": resolution}


def link_item(db, item_id, target_table, target_id, link_kind="draft"):
    ins(db, "work_item_link", id=new_id("work_item_link"), work_item_id=item_id, target_table=target_table, target_id=target_id, link_kind=link_kind)


def note_item(db, item_id, author_kind, author_id, text, untrusted=False):
    ins(db, "work_item_note", id=new_id("work_item_note"), work_item_id=item_id, author_kind=author_kind,
        author_id=author_id if author_kind != "system" else None, body_text=text, is_untrusted=untrusted)


# ======================================================================= documents and versions (ADR-0009, ADR-0029)
LINE_TABLES = {
    "quotation": [("quotation_line", "quotation_id")], "sales_order": [("sales_order_line", "sales_order_id")],
    "purchase_request": [("purchase_request_line", "purchase_request_id")], "purchase_order": [("purchase_order_line", "purchase_order_id")],
    "goods_receipt": [("goods_receipt_line", "goods_receipt_id")], "delivery": [("delivery_line", "delivery_id")],
    "sales_invoice": [("sales_invoice_line", "sales_invoice_id")], "purchase_invoice": [("purchase_invoice_line", "purchase_invoice_id")],
    "change_proposal": [("change_proposal_item", "change_proposal_id")], "bank_receipt": [("payment_line", "payment_id")],
    "bank_payment": [("payment_line", "payment_id")], "production_order": [("production_order_component", "production_order_id"),
                                                                           ("production_order_output", "production_order_id")],
    "production_issue": [("production_issue_line", "production_issue_id")], "production_receipt": [("production_receipt_line", "production_receipt_id")],
    "landed_cost": [("landed_cost_line", "landed_cost_id")],
}
HEADER_TABLE = {"bank_receipt": "payment", "bank_payment": "payment"}
SKIP_SNAPSHOT = {"id", "company_id", "recorded_at"}


def snapshot(db, doc_type, doc_id):
    header_table = HEADER_TABLE.get(doc_type, doc_type)
    h = db.one(f"select row_to_json(t)::jsonb from {header_table} t where id=%s", (doc_id,)) if header_table in db.cols else None
    content = {"header": {k: v for k, v in (h[0] if h else {}).items() if k not in SKIP_SNAPSHOT}}
    for table, fk in LINE_TABLES.get(doc_type, []):
        rows = db.all(f"select row_to_json(t)::jsonb from {table} t where {fk}=%s order by 1", (doc_id,))
        content[table] = sorted(({k: v for k, v in r[0].items() if k not in SKIP_SNAPSHOT | {"id"}} for r in rows), key=J)
    return content


def effective_taint(db, version_id):
    r = db.one("select v.is_tainted and not exists (select 1 from taint_clearance c where c.document_version_id=v.id) "
               "from document_version v where v.id=%s", (version_id,))
    return bool(r and r[0])


def latest_version(db, doc_id):
    return db.one("select id, version, is_tainted from document_version where document_id=%s order by version desc limit 1", (doc_id,))


def create_doc(db, doc_type, actor, header=None, lines=None, number=None, derived_from=None, partner_id=None, document_date=None,
               work_item=None, workflow_step=None, owner_employee_id=None, header_table=None, doc_id=None, lines_first=False):
    """CreateX: document row, header row (same id), line rows and version 1. Taint follows ADR-0029 rule 8 and the
    holistic note on ADR-0047 rule 2: an OR over the run's taint and every source version's effective taint."""
    doc_id = doc_id or new_id("document")
    human = actor.human
    ins(db, "document", id=doc_id, document_type=doc_type, state="draft", version=1, number=number, partner_id=partner_id,
        document_date=document_date or W.today, owner_employee_id=owner_employee_id, created_by_user_id=human["id"],
        origin_work_item_id=work_item, workflow_step=workflow_step, draft_ordinal=1 if work_item else None)
    table = header_table or HEADER_TABLE.get(doc_type, doc_type)
    if header is not None and not lines_first:
        ins(db, table, id=doc_id, **header)
    for ltable, row in (lines or []):
        ins(db, ltable, **{k: (doc_id if v == "__DOC__" else v) for k, v in row.items()})
    if header is not None and lines_first:
        ins(db, table, id=doc_id, **header)
    sources = derived_from if isinstance(derived_from, (list, tuple)) else ([derived_from] if derived_from else [])
    inherited = any(effective_taint(db, v) for v in sources)
    tainted = bool(actor.tainted or inherited)
    content = snapshot(db, doc_type, doc_id)
    vid = new_id("document_version")
    ins(db, "document_version", id=vid, document_id=doc_id, version=1, content=content, version_hash=sha(content),
        actor_kind=actor.kind, actor_id=actor.actor_id, on_behalf_of_id=(actor.on_behalf_of or {}).get("id") if actor.kind != "human" else None,
        agent_run_id=(actor.run or {}).get("id") if actor.kind == "agent" else None,
        origin_agent_run_id=(actor.origin_run or {}).get("id") if actor.origin_run else ((actor.run or {}).get("id") if actor.kind == "agent" else None),
        is_tainted=tainted, derived_from_version_id=sources[0] if sources else None)
    if number:
        W.code_of[doc_id] = number
    return {"id": doc_id, "type": doc_type, "number": number, "version": 1, "version_id": vid, "tainted": tainted,
            "inherited_taint": inherited, "header_table": table}


def new_version(db, doc, actor, header_changes=None, line_changes=None, extra=None):
    """UpdateX: writes the changes and a new version (ADR-0009 rule 9); an edit ends any approval round."""
    table = doc["header_table"]
    if header_changes:
        upd(db, table, {"id": doc["id"]}, **header_changes)
    for ltable, where, cols in (line_changes or []):
        upd(db, ltable, where, **cols)
    for ltable, row in (extra or []):
        ins(db, ltable, **row)
    prev = latest_version(db, doc["id"])
    content = snapshot(db, doc["type"], doc["id"])
    v = prev[1] + 1
    vid = new_id("document_version")
    tainted = bool(actor.tainted or effective_taint(db, prev[0]))
    ins(db, "document_version", id=vid, document_id=doc["id"], version=v, content=content, version_hash=sha(content),
        actor_kind=actor.kind, actor_id=actor.actor_id, on_behalf_of_id=(actor.on_behalf_of or {}).get("id") if actor.kind != "human" else None,
        agent_run_id=(actor.run or {}).get("id") if actor.kind == "agent" else None,
        origin_agent_run_id=(actor.origin_run or {}).get("id") if actor.origin_run else None, is_tainted=tainted)
    upd(db, "document", {"id": doc["id"]}, version=v)
    doc.update(version=v, version_id=vid, tainted=tainted)
    return doc


def set_state(db, doc, state, number=None, **extra):
    cols = {"state": state}
    if state in ("posted",):
        cols["posted_at"] = now()
    if number:
        cols["number"] = number
        doc["number"] = number
        W.code_of[doc["id"]] = number
    cols.update(extra)
    upd(db, "document", {"id": doc["id"]}, **cols)
    doc["state"] = state


def doc_state(db, doc_id):
    return db.val("select state from document where id=%s", (doc_id,))


def writers(db, doc_id):
    """The design's document-actors function (DS-05 document_actor), as loaded."""
    return {(str(u), role) for u, role in db.all("select user_account_id, actor_role from document_actor(%s)", (doc_id,))}


def next_number(db, doc_type, prefix):
    row = db.one("select id, next_value from numbering_series where document_type=%s and company_id=%s", (doc_type, W.co))
    if row is None:
        sid = new_id("numbering_series")
        ins(db, "numbering_series", id=sid, document_type=doc_type, fiscal_year_id=W.fiscal_year, prefix=prefix, next_value=2,
            format="{prefix}-{year}-{counter:4}")
        n = 1
    else:
        sid, n = row
        upd(db, "numbering_series", {"id": sid}, next_value=n + 1)
    return f"{prefix}-{W.today.year}-{n:04d}"


# ======================================================================= policy (ADR-0043) and pools (ADR-0055)
NO_POSTING_STEP = {"quotation", "sales_order", "purchase_request", "purchase_order", "production_order", "change_proposal",
                   "outbound_message", "period_unlock_request"}
MAY_NOT_WAIT_REGIME = {"sales_invoice", "sales_return", "credit_note", "debit_note"}


def _cond(rv, inputs):
    """Half-open bounds, booleans match only true (ADR-0043 rule 3)."""
    amt = D(str(inputs.get("amount", 0)))
    if rv["amount_company_min"] is not None and amt < rv["amount_company_min"]:
        return False
    if rv["amount_company_max"] is not None and amt >= rv["amount_company_max"]:
        return False
    if rv["discount_percent_min"] is not None and D(str(inputs.get("discount_percent", 0))) < rv["discount_percent_min"]:
        return False
    if rv["margin_percent_max"] is not None:
        m = inputs.get("margin_percent")
        if m is None or D(str(m)) >= rv["margin_percent_max"]:
            return False
    for b in ("is_price_below_cost", "is_price_outside_list", "is_credit_exceeded", "is_match_exceeded", "is_direct_expense",
              "is_bank_account_recent", "is_rate_unusual", "is_cost_unknown"):
        if rv[b] and not inputs.get(b):
            return False
    return True


def policy_rules(db, action, doc_type, actor_kind):
    rows = db.all("""select r.code, v.id, v.version, v.document_type, v.actor_kind, v.amount_company_min, v.amount_company_max,
                            v.discount_percent_min, v.margin_percent_max, v.is_price_below_cost, v.is_price_outside_list, v.is_credit_exceeded,
                            v.is_match_exceeded, v.is_direct_expense, v.is_bank_account_recent, v.is_rate_unusual, v.is_cost_unknown,
                            v.effect, p.code, p.rank, v.policy_rule_id, p.id
                       from policy_rule_version v join policy_rule r on r.id=v.policy_rule_id
                       left join approval_procedure p on p.id=v.approval_procedure_id
                      where v.is_enabled and v.effective_from <= %s and v.action=%s
                        and (v.document_type is null or v.document_type=%s) and (v.actor_kind is null or v.actor_kind=%s)
                      order by r.code""", (W.today, action, doc_type, actor_kind))
    keys = ["code", "version_id", "version", "document_type", "actor_kind", "amount_company_min", "amount_company_max", "discount_percent_min",
            "margin_percent_max", "is_price_below_cost", "is_price_outside_list", "is_credit_exceeded", "is_match_exceeded",
            "is_direct_expense", "is_bank_account_recent", "is_rate_unusual", "is_cost_unknown", "effect", "procedure", "rank",
            "rule_id", "procedure_id"]
    return [dict(zip(keys, r)) for r in rows]


def select_pool(db, doc_type, inputs):
    rows = db.all("""select t.position, t.condition_input, p.id, p.code from approval_pool_document_type t join approval_pool p on p.id=t.approval_pool_id
                      where t.document_type=%s order by t.position desc""", (doc_type,))
    for pos, cond, pid, code in sorted(rows, key=lambda r: (r[0] == 0, r[0])):
        if pos == 0 or inputs.get(cond):
            return pid, code, (f"selector row {cond}" if pos else "default row")
    pid, code = db.one("select id, code from approval_pool where code='general'")
    return pid, code, "no row for the type: general"


def plan_for(db, pool_id, rank):
    rows = db.all("""select id, sequence, code, min_rank, required_approvals, scope_binding, escalation_role_id, due_days
                       from approval_stage where approval_pool_id=%s and is_active and min_rank <= %s order by sequence""", (pool_id, rank))
    return [{"id": str(r[0]), "sequence": r[1], "code": r[2], "min_rank": r[3], "k": r[4], "scope_binding": r[5],
             "escalation_role_id": r[6], "due_days": r[7]} for r in rows]


def evaluate_policy(db, doc, action, actor, inputs):
    """ADR-0043 rules 5-10 and floors (rule 9), ADR-0055 rules 3-6. Writes the policy_decision row."""
    doc_type = doc["type"]
    matched = [r for r in policy_rules(db, action, doc_type, actor.kind) if _cond(r, inputs)]
    floors, notes = [], []
    rank, rule_for_rank, human_post, deny = None, None, False, False
    for r in matched:
        if r["effect"] == "deny":
            deny = True
        elif r["effect"] == "require_approval" and (rank is None or r["rank"] > rank):
            rank, rule_for_rank = r["rank"], r
        elif r["effect"] == "require_human_post":
            human_post = True
    tainted = effective_taint(db, doc["version_id"])
    if actor.kind != "human":
        human_post = True
        floors.append("baseline: a non-human actor starts from human_post (ADR-0043 rule 7)")
        if action == "submit" and tainted:
            floors.append("floor 3: tainted version, non-human submit gets at least the lowest rank")
            rank = rank or 10
        if action in ("post", "issue") and tainted:
            floors.append("floor 3: tainted version, non-human post gets human_post (INV-84)")
        if actor.kind == "agent" and action in ("post", "issue"):
            floors.append("floor 4: agents only draft")
        if actor.kind == "system" and action in ("post", "issue") and (actor.origin_run or doc.get("agent_written")):
            floors.append("floor 5: an LLM never contributes to an auto-post")
    if doc_type == "change_proposal" and action == "submit" and rank is None:
        rank = 10
        floors.append("floor 7: a change proposal's submit always needs at least the lowest rank")
    if action == "submit" and doc_type in NO_POSTING_STEP and human_post and actor.kind != "human":
        rank = rank or 10
        human_post = False
        floors.append("floor 8: no posting step, human_post becomes the lowest rank")
    if doc_type in MAY_NOT_WAIT_REGIME and W.settings.get("documents.issuance_without_delay") and rank is not None:
        human_post, rank = True, None
        floors.append("rule 10: the type may not wait under l10n_vn (documents.issuance_without_delay): a rank becomes human_post")
    if tainted and actor.kind == "human":
        notes.append("tainted version handled by a person: allowed (ADR-0029 rule 11)")
    outcome = "denied" if deny else ("approval_required" if rank is not None else ("human_only" if human_post else "allowed"))
    pool_id = pool_code = sel = None
    plan = None
    proc_id = None
    if rank is not None:
        pool_id, pool_code, sel = select_pool(db, doc_type, inputs)
        plan = plan_for(db, pool_id, rank)
        proc_id = db.val("select id from approval_procedure where rank=%s", (rank,))
        if not plan:
            raise RuntimeError("approval_plan_empty (ADR-0055 rule 5)")
    did = new_id("policy_decision")
    ins(db, "policy_decision", id=did, document_id=doc["id"], document_version_id=doc["version_id"], action=action,
        actor_kind=actor.kind, actor_id=actor.actor_id, on_behalf_of_id=(actor.on_behalf_of or {}).get("id"), outcome=outcome,
        policy_rule_id=rule_for_rank["rule_id"] if rule_for_rank else None, policy_rule_version=rule_for_rank["version"] if rule_for_rank else None,
        matching_rules=[{"rule": r["code"], "version": r["version"]} for r in matched], approval_procedure_id=proc_id,
        required_rank=rank, human_post=(outcome == "human_only"), policy_input_hash=sha(inputs), policy_input=jsonable(inputs),
        approval_pool_id=pool_id, approval_plan=plan, decided_at=now())
    dec = {"id": did, "action": action, "document_type": doc_type, "actor_kind": actor.kind, "outcome": outcome, "rank": rank,
           "matched_rules": [r["code"] for r in matched], "floors": floors, "notes": notes, "inputs": jsonable(inputs),
           "pool": pool_code, "pool_selection": sel, "plan": [{"stage": s["code"], "min_rank": s["min_rank"], "k": s["k"]} for s in (plan or [])],
           "plan_raw": plan, "is_tainted": tainted, "policy_input_hash": sha(inputs)}
    return dec


def policy_line(dec):
    s = f"policy {dec['document_type']}.{dec['action']} by {dec['actor_kind']}: {dec['outcome']}"
    if dec["rank"]:
        s += f" (rank {dec['rank']}, pool {dec['pool']}, stages {', '.join(p['stage'] for p in dec['plan'])})"
    if dec["matched_rules"]:
        s += "; rules: " + ", ".join(dec["matched_rules"])
    if dec["floors"]:
        s += "; " + "; ".join(dec["floors"])
    return s


def decision_summary(dec):
    return {k: dec[k] for k in ("outcome", "rank", "pool", "pool_selection", "plan", "matched_rules", "floors", "notes", "inputs", "is_tainted")}


# ======================================================================= approval eligibility (ADR-0055 rule 7)
CP_TARGET = {"CreatePartner": "CreatePartner", "CreateContact": "CreateContact", "CreatePartnerItem": "CreatePartnerItem",
             "ConvertPlannedOrder": "ConvertPlannedOrder", "FirmPlannedOrder": "FirmPlannedOrder", "UpdatePlannedOrder": "UpdatePlannedOrder",
             "SetPriceListEntries": "SetPriceListEntries"}


def stage_members(db, stage_id):
    users = set()
    for kind, uid, rid in db.all("select member_kind, user_account_id, role_id from approval_stage_member where approval_stage_id=%s", (stage_id,)):
        if kind == "user":
            users.add(str(uid))
        else:
            for (u,) in db.all("select user_account_id from role_assignment where role_id=%s and valid_from<=%s and (valid_to is null or valid_to>=%s)",
                               (rid, W.today, W.today)):
                users.add(str(u))
    return users


def segregation_pairs(db, doc, user, approve_command):
    """ADR-0054 rule 19 pairs relevant to an approval: price_list_vs_sales_approval (relation none: holds a side-a
    permission) and the per-document relations."""
    broken = []
    for r in SEGREGATION:
        side_b = r["side_b"].split(";")
        if approve_command not in side_b:
            continue
        if r["document_relation"] == "none":
            if any(can(user, c)[0] for c in r["side_a"].split(";")):
                broken.append(r["code"])
        elif r["document_relation"] == "settled_item" and doc["type"] in ("bank_payment", "cash_payment"):
            pass
    return broken


def eligibility(db, doc, dec, user, approve_command, stage=None):
    stage = stage or current_stage(db, doc, dec)
    if stage is None:
        return {"eligible": False, "why": "no open stage"}
    members = stage_members(db, stage["id"])
    perm_ok, perm_why = can(user, approve_command, node=None if doc["type"] != "change_proposal" else "change_proposal")
    w = writers(db, doc["id"])
    is_writer = (str(user["id"]), "writer") in w
    counted = db.val("""select count(*) from approval where policy_decision_id=%s and decision='approved' and actor_id=%s""", (dec["id"], user["id"]))
    seg = segregation_pairs(db, doc, user, approve_command)
    target = []
    if doc["type"] == "change_proposal":
        for (ct,) in db.all("select command_type from change_proposal_item where change_proposal_id=%s order by item_index", (doc["id"],)):
            ok, why = can(user, CP_TARGET.get(ct, ct))
            target.append({"command": ct, "ok": ok, "why": why})
    conds = {"1_human": True, "2_member": str(user["id"]) in members, "2_permission": perm_ok, "5_not_writer": not is_writer,
             "6_not_counted": counted == 0, "7_no_segregation_pair": not seg}
    if target:
        conds["target_permissions"] = all(t["ok"] for t in target)
    ok = all(conds.values())
    return {"user": user["name"], "template": user["template"], "stage": stage["code"], "eligible": ok, "conditions": conds,
            "permission": perm_why, "segregation": seg, "target": target,
            "is_submitter": (str(user["id"]), "submitter") in w}


def current_stage(db, doc, dec):
    for s in dec["plan_raw"] or []:
        n = db.val("select count(*) from approval where policy_decision_id=%s and approval_stage_id=%s and decision='approved'", (dec["id"], s["id"]))
        if n < s["k"]:
            return s
    return None


def strands(db, doc, dec, user, approve_command):
    """ADR-0055 rule 7 condition 8: would counting this person at the current stage leave a later stage unfillable?"""
    plan = dec["plan_raw"] or []
    cur = current_stage(db, doc, dec)
    later = [s for s in plan if s["sequence"] > cur["sequence"]]
    used = {str(r[0]) for r in db.all("select actor_id from approval where policy_decision_id=%s and decision='approved'", (dec["id"],))} | {str(user["id"])}
    for st in later:
        others = [u for u in W.users_list if str(u["id"]) not in used and eligibility(db, doc, dec, u, approve_command, stage=st)["eligible"]]
        if len(others) < st["k"]:
            return True
    return False


def candidates(db, doc, dec, approve_command):
    stage = current_stage(db, doc, dec)
    users = [u for u in W.users_list if str(u["id"]) in stage_members(db, stage["id"])]
    return [eligibility(db, doc, dec, u, approve_command) for u in users]


def submit(db, doc, actor, inputs, command):
    """SubmitX: policy point; approval_required -> pending_approval with the first stage's work item, else approved."""
    if actor.kind != "human":
        raise RuntimeError("origin_run_submit_not_allowed / agents never submit (ADR-0050 rule 30)")
    ok, why = can(actor.user, command)
    if not ok:
        return None, {"error": "permission_denied", "why": why}
    dec = evaluate_policy(db, doc, "submit", actor, inputs)
    items, events = [], []
    if dec["outcome"] == "approval_required":
        set_state(db, doc, "pending_approval")
        st = dec["plan_raw"][0]
        it = raise_item(db, "approval_pending", "document", doc["id"], ("approval_stage", st["id"]), due_days=st["due_days"],
                        details={"document_type": doc["type"], "stage": st["code"], "decision": str(dec["id"])}, tainted=dec["is_tainted"],
                        open_key=f"approval_pending:{doc['id']}:{st['code']}")
        items.append(it)
        W.code_of[st["id"]] = f"{dec['pool']}.{st['code']}"
    elif dec["outcome"] in ("allowed", "human_only"):
        set_state(db, doc, "approved")
    else:
        raise RuntimeError(f"policy {dec['outcome']}")
    audit(db, command, actor, doc=doc, policy_decision_id=dec["id"], subject_table=doc["header_table"], subject_id=doc["id"])
    events.append(emit(db, f"{camel(doc['type'])}Submitted", doc["header_table"], doc["id"], actor, command, tainted=dec["is_tainted"]))
    if doc.get("state") == "approved":
        events.append(emit(db, f"{camel(doc['type'])}Approved", doc["header_table"], doc["id"], actor, command, tainted=dec["is_tainted"]))
    doc["decision"] = dec
    return dec, {"items": items, "events": events}


def approve(db, doc, user, reason, command):
    """ApproveX by a person at the current stage (ADR-0055 rules 7-9). Raises if not eligible."""
    dec = doc["decision"]
    el = eligibility(db, doc, dec, user, command)
    if not el["eligible"]:
        raise RuntimeError(f"approver_not_eligible: {el}")
    st = current_stage(db, doc, dec)
    actor = Actor("human", user=user)
    ins(db, "approval", id=new_id("approval"), document_id=doc["id"], document_version_id=doc["version_id"], policy_decision_id=dec["id"],
        decision="approved", reason=reason, actor_kind="human", actor_id=user["id"], approval_stage_id=st["id"],
        approval_pool_id=db.val("select approval_pool_id from approval_stage where id=%s", (st["id"],)), decided_at=now())
    item_id = db.val("select id from work_item where kind='approval_pending' and subject_id=%s and state in ('open','claimed') order by recorded_at desc limit 1",
                     (doc["id"],))
    items, events = [], []
    if item_id:
        items.append(resolve_item(db, item_id, "approved"))
    nxt = current_stage(db, doc, dec)
    if nxt is None:
        set_state(db, doc, "approved")
        events.append(emit(db, f"{camel(doc['type'])}Approved", doc["header_table"], doc["id"], actor, command, tainted=dec["is_tainted"]))
    else:
        items.append(raise_item(db, "approval_pending", "document", doc["id"], ("approval_stage", nxt["id"]), due_days=nxt["due_days"],
                                details={"stage": nxt["code"]}, open_key=f"approval_pending:{doc['id']}:{nxt['code']}"))
    audit(db, command, actor, doc=doc, policy_decision_id=dec["id"], subject_table=doc["header_table"], subject_id=doc["id"])
    return el, {"items": items, "events": events, "stage": st["code"], "state": doc_state(db, doc["id"])}


def camel(snake):
    return "".join(p.capitalize() for p in snake.split("_"))


# ======================================================================= agent runs (ADR-0050)
BUDGET = {"customer_onboarding": (6, 30, 0.30), "quotation": (25, 80, 1.50), "bank_matching": (3, 10, 0.05),
          "purchase_invoice": (15, 60, 0.60), "planning": (10, 80, 1.00)}


def start_run(db, agent_type, trigger_kind, work_item, on_behalf_of, started_by_kind="system", started_by=None, scope_kind="subject",
              scope_partner=None, subject=None, taint_source=None):
    rid = new_id("agent_run")
    llm, tools, cost = BUDGET[agent_type]
    t = now()
    taint = {}
    if taint_source:
        taint = {"tainted_at": t, "taint_source_kind": taint_source[0], "taint_source_table": taint_source[1], "taint_source_id": taint_source[2]}
    ins(db, "agent_run", id=rid, agent_type_code=agent_type, agent_type_version="1.0.0", seatmap_hash=sha({"seat": "local-gemma"}),
        mode="live", trigger_kind=trigger_kind, work_item_id=work_item, subject_table=subject[0] if subject else None,
        subject_id=subject[1] if subject else None, started_by_kind=started_by_kind, started_by_id=(started_by or {}).get("id"),
        on_behalf_of_id=on_behalf_of["id"], scope_kind=scope_kind, scope_partner_id=scope_partner,
        budget={"max_llm_calls": llm, "max_tool_calls": tools, "max_cost": str(cost)}, state="running", started_at=t, **taint)
    if work_item:
        claim_item(db, work_item, "agent_run", rid)
    run = {"id": rid, "agent_type": agent_type, "agent_type_id": W.agent_type_ids[agent_type], "tainted": bool(taint_source),
           "on_behalf_of": on_behalf_of, "work_item": work_item, "llm_calls": 0, "tool_calls": 0, "ordinal": 0, "started": t}
    W.code_of[rid] = f"{agent_type} run"
    return run


def run_step(db, run, kind, step_code, seat=None, request=None, response=None, tool_name=None, mode=None, request_id=None,
             validation_errors=None, error_code=None, usage=None):
    run["ordinal"] += 1
    sid = new_id("agent_run_step")
    ins(db, "agent_run_step", id=sid, agent_run_id=run["id"], ordinal=run["ordinal"], step_code=step_code, kind=kind,
        request_step_id=request_id, seat=seat, provider="llama.cpp (local)" if seat else None, model="gemma-4-31b-it" if seat else None,
        template_code=step_code if seat else None, template_version="1.0.0" if seat else None, output_schema_version="1.0.0" if seat else None,
        request_hash=sha(request or response or {"step": step_code, "n": run["ordinal"]}), reserved_amount=0 if kind == "llm_request" else None,
        request_body=request if kind == "llm_request" else None, response_body=response if kind == "llm_response" else None,
        validation_errors=validation_errors, tool_name=tool_name, mode=mode, error_code=error_code,
        input_token_count=(usage or {}).get("prompt_tokens"), output_token_count=(usage or {}).get("completion_tokens"))
    return sid


def record_llm(db, run, step_code, seat, rec, validation_errors=None):
    rq = run_step(db, run, "llm_request", step_code, seat=seat, request={"system": rec["system_prompt"], "user": rec["input_text"]})
    run_step(db, run, "llm_response", step_code, seat=seat, response={"raw": rec["raw_output"], "mode": rec["mode"]}, request_id=rq,
             validation_errors=validation_errors, usage=rec.get("usage"))
    run["llm_calls"] += 1
    u = rec.get("usage") or {}
    db.x("update agent_run set llm_call_count=llm_call_count+1, input_token_count=input_token_count+%s, output_token_count=output_token_count+%s where id=%s",
         (u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0, run["id"]))
    EFF.add("agent_run (update)")


def record_tool(db, run, step_code, tool_name, mode, request, result):
    rq = run_step(db, run, "tool_request", step_code, tool_name=tool_name, mode=mode, request=request)
    run_step(db, run, "tool_result", step_code, tool_name=tool_name, mode=mode, response=None, request_id=rq)
    run["tool_calls"] += 1
    db.x("update agent_run set tool_call_count=tool_call_count+1 where id=%s", (run["id"],))


def end_run(db, run, outcome, output_refs=None):
    t = now()
    upd(db, "agent_run", {"id": run["id"]}, state="completed", outcome=outcome, ended_at=t,
        duration_ms=int((t - run["started"]).total_seconds() * 1000), output_refs=output_refs or [])
    if run["work_item"]:
        db_state = db.val("select state from work_item where id=%s", (run["work_item"],))
        if db_state == "claimed":
            unclaim_item(db, run["work_item"])
