"""Scenario: configurable workflows (ADR-0058), as pure functions and on the DDL drafts.

Run: python t22_workflows.py [--load]
  The pure checks (part W) always run. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there and loads every DDL file of design/, and the database checks (part D) run.
  NATIVEFLOWS_DOCS points at the docs/ tree (default ~/Projects/NativeFlows/docs); NATIVEFLOWS_LAB_DIR at lab.py and load_all.py
  (default: this file's directory).

W: the rules of ADR-0058 as lab functions over a small registry: condition evaluation by type and operator (rule 8);
   validation of triggers, gate fields and actions, and the automation-allowed registry check (rules 4-6, 14); the
   permission each action needs and the by-design skips (rules 8-9); the owner's scope and field classes and the reader's
   filter (rules 9, 11); cycle detection over rule graphs with discriminator nodes, undeclared emit values and consumer
   edges, against brute-force reachability on random graphs, with the review's probe (rule 15); scheduled-job feedback;
   the static depth against brute-force path enumeration, and the runtime cap (rules 12, 15); the same-rule-same-target
   guard (rule 13); field-change triggers (rule 14); idempotency keys (rule 17); the circuit breaker in a window and in a
   row (rule 16); independent actions and execution outcomes (rule 10); evaluate-all-then-act order independence (rule
   10); decision tables: exact pairwise overlap against brute force, a capped box-subtraction completeness proof that
   never reports a false gap, out-of-domain inputs, no-match handling, aggregators under shuffled rows (rules 18-20);
   the replay diff (rule 23).
D: with --load, on all DDL: versions inserted only as drafts, editable in draft and immutable after, the allowed and
   refused moves, deletes of drafts only, pointers only to versions in force of the same rule, the owner's confirmation,
   no demotion of a version in force, pointers cleared on retirement and on leaving shadow, frozen table rows and
   parameter values, parameter bounds and safety caps, the execution keys, outcomes and chain-target index, the depth
   checks on executions, outbox events and audit records, immutable execution rows, forced row-level security.
Not covered: commands, the dispatcher itself, consumers, the upgrade job, UI.
"""
import hashlib, itertools, json, os, random, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import RESULTS, conn, expect, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
random.seed(58)
INF = float("inf")


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def refused(fn):
    try:
        fn()
    except ValueError as e:
        return str(e)
    return None


def h(v):
    return hashlib.sha256(json.dumps(v, default=str).encode()).hexdigest()[:16]


# ======================================================================= the registry (lab vocabulary)
# condition fields: (type, field class or None, is_gate_field)
EVENTS = {
    "SalesOrderApproved": {"table": "sales_order", "fields": {"amount_company": ("amount", None, True), "margin_percent": ("amount", "margin", True),
                           "warehouse_code": ("code", None, True), "is_rush": ("boolean", None, True), "customer_note": ("text", None, False),
                           "agent_purpose": ("code", None, False)}, "watchable": None, "disc": None, "replayable": True},
    "SalesOrderChanged": {"table": "sales_order", "fields": {"amount_company": ("amount", None, True), "requested_delivery_date": ("date", None, True)},
                          "watchable": {"requested_delivery_date", "amount_company"}, "disc": None, "replayable": True},
    "PartnerUpdated": {"table": "partner", "fields": {"credit_limit": ("amount", None, True), "partner_group": ("code", None, True)},
                       "watchable": {"credit_limit", "partner_group"}, "disc": None, "replayable": False},
    "PurchaseRequestCreated": {"table": "purchase_request", "fields": {"amount_company": ("amount", None, True)}, "watchable": None, "disc": None, "replayable": True},
    "PurchaseOrderCreated": {"table": "purchase_order", "fields": {"amount_company": ("amount", None, True)}, "watchable": None, "disc": None, "replayable": True},
    "WorkItemRaised": {"table": "work_item", "fields": {"kind": ("code", None, True)}, "watchable": None, "disc": "kind", "replayable": True},
}
COMMANDS = {  # command: (effect class, verb, is_draft_only, is_automation_allowed, human_only, proposal_bound, emits [(event, discriminator values or None)])
    "CreatePurchaseRequest": ("other", "Create", True, True, False, False, [("PurchaseRequestCreated", None)]),
    "CreatePurchaseOrder": ("other", "Create", True, True, False, False, [("PurchaseOrderCreated", None)]),
    "RaiseAutomationWorkItem": ("other", "Raise", True, True, False, False, [("WorkItemRaised", ("automation_task", "automation_notice"))]),
    "UpdatePurchaseRequest": ("other", "Update", True, False, False, False, [("PurchaseRequestChanged", None)]),
    "CreateChangeProposal": ("other", "Create", True, False, False, False, [("ChangeProposalCreated", None)]),
    "SubmitPurchaseOrder": ("other", "Submit", False, False, False, False, [("PurchaseOrderSubmitted", None)]),
    "PostSalesInvoice": ("posting", "Post", False, False, False, False, [("SalesInvoicePosted", None)]),
    "UpdatePartner": ("master_data_change", "Update", False, False, False, True, [("PartnerUpdated", None)]),
    "SendOutboundMessage": ("outbound_send", "Send", False, False, False, False, [("OutboundMessageSent", None)]),
    "StartAgentRun": ("other", "Start", False, False, False, False, [("AgentRunStarted", None)]),
    "SetSalesOrderDeliveryBlock": ("other", "Set", False, False, False, False, [("SalesOrderBlocked", None)]),
}
HOLDS = {"SetSalesOrderDeliveryBlock"}          # a hold interface a module registered (rule 6; Phase 1 registers none)
AGENTS = {"quotation": {"triggers": {("WorkItemRaised", "work_item")}, "subject_tables": {"work_item", "inbound_message"}}}
CONSUMERS = [("PurchaseOrderCreated", ("SalesOrderChanged", None))]   # registered consumer edges: subscribed -> (emitted, discriminator values)


def registry_ok(cmd):
    """Rule 5: is_automation_allowed implies a Create of a draft, is_draft_only, and none of the forbidden classes, verbs or flags."""
    eff, verb, draft_only, allowed, human_only, bound, _ = COMMANDS[cmd]
    if not allowed:
        return True
    if cmd == "RaiseAutomationWorkItem":
        return draft_only
    return verb == "Create" and cmd != "CreateChangeProposal" and draft_only and eff not in ("posting", "master_data_change", "outbound_send") and not human_only and not bound


TYPE_OPS = {"amount": {"eq", "ne", "lt", "le", "gt", "ge", "between", "is_null", "is_not_null", "decision"},
            "date": {"eq", "ne", "lt", "le", "gt", "ge", "between", "is_null", "is_not_null"},
            "code": {"eq", "ne", "in", "not_in", "is_null", "is_not_null", "decision"},
            "boolean": {"eq", "ne", "is_null", "is_not_null"}}


def eval_condition(ftype, op, value, actual, tables=None):
    """ADR-0058 rule 8: typed operators; between is half-open [min, max); decision handles no match as the rule states."""
    if op not in TYPE_OPS[ftype]:
        raise ValueError(f"operator {op} not allowed for {ftype}")
    if op == "is_null":
        return actual is None
    if op == "is_not_null":
        return actual is not None
    if op == "decision":
        table, output, on_no_match = value
        res = evaluate_table(tables[table], {"x": actual})
        return on_no_match if res == "decision_no_match" else bool(res[output])
    if actual is None:
        return False
    return {"eq": lambda: actual == value, "ne": lambda: actual != value, "in": lambda: actual in value, "not_in": lambda: actual not in value,
            "lt": lambda: actual < value, "le": lambda: actual <= value, "gt": lambda: actual > value, "ge": lambda: actual >= value,
            "between": lambda: value[0] <= actual < value[1]}[op]()


def validate_rule(rule, owner=None):
    """Rules 4-9, 14, 20: the trigger, watched fields, gate fields and actions against the registry, and the owner's classes."""
    out = []
    ev = EVENTS.get(rule["trigger"])
    if ev is None:
        return ["trigger_not_registered"]
    if ev["watchable"] is not None:
        if not rule.get("watched"):
            out.append("trigger_unwatched")
        elif not set(rule["watched"]) <= ev["watchable"]:
            out.append("watched_field_not_watchable")
    used = []
    for f, op, v in rule.get("conditions", []):
        spec = ev["fields"].get(f)
        if spec is None:
            out.append(f"unknown_field:{f}"); continue
        if not spec[2]:
            out.append(f"not_a_gate_field:{f}"); continue
        if op not in TYPE_OPS[spec[0]]:
            out.append(f"operator_type:{f}")
        if op == "decision" and (len(v) != 3 or v[2] is None):
            out.append(f"no_match_unhandled:{f}")
        used.append(f)
    for a in rule["actions"]:
        k = a["kind"]
        if k == "create_draft":
            if a["command"] not in COMMANDS or not COMMANDS[a["command"]][3]:
                out.append(f"automation_command_not_allowed:{a.get('command')}")
            for fld, src in a.get("payload", {}).items():
                spec = ev["fields"].get(src[1]) if src[0] == "field" else None
                if src[0] == "field" and spec is None:
                    out.append(f"payload_field:{fld}")
                elif src[0] == "field" and not spec[2]:
                    out.append(f"payload_not_gate:{fld}")
                elif src[0] == "field":
                    used.append(src[1])
        elif k == "start_agent":
            if (rule["trigger"], a["subject_table"]) not in AGENTS.get(a["agent_type"], {}).get("triggers", set()):
                out.append("agent_kind_not_declared")
        elif k == "set_hold":
            if a["command"] not in HOLDS:
                out.append("hold_not_registered")
        elif k not in ("raise_work_item", "notify"):
            out.append(f"action_kind:{k}")
    if not 1 <= len(rule["actions"]) <= 5:
        out.append("actions_count")
    if owner is not None:
        need = {ev["fields"][f][1] for f in used if ev["fields"][f][1]}
        if not need <= owner["classes"]:
            out.append("automation_owner_scope_insufficient:" + ",".join(sorted(need - owner["classes"])))
        for a in rule["actions"]:
            if action_permission(a, rule) not in owner["perms"]:
                out.append(f"permission_denied:{action_permission(a, rule)}")
    return out


def action_permission(a, rule):
    """Rule 8's table: the permission checked for the owner."""
    k = a["kind"]
    if k in ("create_draft", "set_hold"):
        return a["command"]
    if k in ("raise_work_item", "notify"):
        return "Get:" + EVENTS[rule["trigger"]]["table"]          # read right on the subject, with scope
    if k == "start_agent":
        return "start_agent:" + a["agent_type"]


def plan_action(a, tainted, agent_chain, subject_table):
    """Rule 9, decided before acting: (run, None) or (skip, reason). Skips never count toward the breaker."""
    k = a["kind"]
    if k == "start_agent":
        if agent_chain:
            return ("skipped", "agent_chain")
        if tainted and subject_table not in AGENTS[a["agent_type"]]["subject_tables"]:
            return ("skipped", "subject_not_accepted")
        return ("run", None)
    if k == "set_hold" and tainted:
        return ("skipped", "tainted")
    return ("run", None)


def in_scope(subject, owner):
    return subject["branch"] in owner["branches"]


def read_executions(records, reader):
    """Rule 11: rows only inside the reader's scope; for a class the reader lacks, value and result are omitted with a marker."""
    out = []
    for r in records:
        if r["branch"] not in reader["branches"]:
            continue
        conds = [c if c["class"] is None or c["class"] in reader["classes"] else {"field": c["field"], "is_class_filtered": True} for c in r["conditions"]]
        out.append(dict(r, conditions=conds))
    return out


def store_value(value, label, company_key):
    """Rule 11: a personal value is stored under an HMAC with the company's key (or omitted); never a plain hash."""
    import hmac
    return "hmac:" + hmac.new(company_key, json.dumps(value).encode(), hashlib.sha256).hexdigest() if label == "personal" else value


def scope_limited(rule, owner, events):
    """Rule 9: validation and replay count the window events outside the owner's scope."""
    n = sum(1 for e in events if e["type"] == rule["trigger"] and e.get("branch", "B1") not in owner["branches"])
    return ("automation_owner_scope_limited", n) if n else None


def scope_narrowed_items(old_scope, new_scope, rules_owned):
    """Rule 9: a narrowed scope of the owner of rules in force raises one item per rule for company_owner."""
    return [("automation_owner_scope_narrowed", r, "company_owner") for r in rules_owned] if set(new_scope) < set(old_scope) else []


LEVELS = ["own", "team", "department", "branch", "company"]


def scope_cells(assignments, day, org, perm):
    """Rule 9, per rule: one cell per assignment in force whose role grants the condition source's read permission, split to single
    values (branch or all, warehouse or all, level, units, employees). ADR-0054 rule 15: assignments combine by any."""
    cells = set()
    for a in assignments:
        if not (a["valid_from"] <= day and (a["valid_to"] is None or day <= a["valid_to"])) or perm not in a["perms"]:
            continue
        units = tuple(sorted(a.get("units", ()))) if a["owner_scope"] in ("team", "department") else ()
        emps = tuple(sorted({m for u in units for m in org.get(u, ())}))
        for b in (a["branches"] or ("all",)):
            for w in (a["warehouses"] or ("all",)):
                cells.add((b, w, a["owner_scope"], units, emps))
    return cells


def covered(cell, new_cells):
    b, w, lv, _, emps = cell
    return any((nb in (b, "all")) and (nw in (w, "all")) and LEVELS.index(nl) >= LEVELS.index(lv)
               and (lv not in ("team", "department") or nl not in ("team", "department") or set(emps) <= set(ne))
               for nb, nw, nl, _, ne in new_cells)


def any_assignment(assignments, day):
    return any(a["valid_from"] <= day and (a["valid_to"] is None or day <= a["valid_to"]) for a in assignments)


class OwnerCheck:
    """Rule 9: RunAutomationOwnerScopeCheck over the column automation_rule.owner_scope (a set of cells); one open item per rule."""
    def __init__(self, stored, perm="Get:sales_order"):
        self.owner_scope, self.perm, self.open_item, self.disabled = stored, perm, None, None

    def run(self, assignments, day, org, account_active=True):
        if not account_active or not any_assignment(assignments, day):
            self.disabled = "owner_inactive"
            return "owner_inactive"                              # the only case for company_owner
        new_ = scope_cells(assignments, day, org, self.perm)
        if new_ == self.owner_scope:
            return None
        lost = sorted(c for c in self.owner_scope if not covered(c, new_))
        if lost:
            if self.open_item is None:
                self.open_item = ("automation_owner_scope_narrowed", "rule_owner", lost)
                return self.open_item
            return "item_open"
        self.owner_scope = new_
        return "updated"

    def resolve(self, assignments, day, org):
        self.open_item = None
        self.owner_scope = scope_cells(assignments, day, org, self.perm)


def pins_ok(rule, tables_state):
    """Rule 20: only assisted or active versions of the company's tables may be pinned."""
    return all(tables_state.get(v) in ("assisted", "active") for v in rule.get("pins", []))


# ======================================================================= the rule graph (rule 15)
def node_of_trigger(rule):
    return (rule["trigger"], rule.get("disc"))


def emitted_nodes(rule):
    out = set()
    for a in rule["actions"]:
        if a["kind"] == "create_draft" or a["kind"] == "set_hold":
            for e, vals in COMMANDS[a["command"]][6]:
                out |= {(e, v) for v in vals} if vals else {(e, None)}
        elif a["kind"] == "raise_work_item":
            out.add(("WorkItemRaised", "automation_task"))
        elif a["kind"] == "notify":
            out.add(("WorkItemRaised", "automation_notice"))
        elif a["kind"] == "start_agent":
            out.add(("AgentRunStarted", None))
    return out


def matches_node(trigger_node, node):
    """A trigger without a discriminator hears every value; an emit without a declared value reaches every trigger (conservative)."""
    return trigger_node[0] == node[0] and (trigger_node[1] is None or node[1] is None or trigger_node[1] == node[1])


def graph_edges(rules, consumers):
    """Edges between rules: r1 -> r2 when an event r1 may emit (directly, or through consumer edges) triggers r2."""
    def closure(nodes):
        seen, todo = set(nodes), list(nodes)
        while todo:
            n = todo.pop()
            for sub, (b, vals) in consumers:
                if sub == n[0]:
                    for m in ({(b, v) for v in vals} if vals else {(b, None)}):
                        if m not in seen:
                            seen.add(m); todo.append(m)
        return seen
    edges = {r["code"]: set() for r in rules}
    for r1 in rules:
        reach = closure(emitted_nodes(r1))
        for r2 in rules:
            if any(matches_node(node_of_trigger(r2), n) for n in reach):
                edges[r1["code"]].add(r2["code"])
    return edges


def find_cycle_through(edges, start):
    stack, seen = [(start, [start])], set()
    while stack:
        n, path = stack.pop()
        for m in sorted(edges[n]):
            if m == start:
                return path + [start]
            if m not in seen:
                seen.add(m); stack.append((m, path + [m]))
    return None


def act_depths(edges):
    """Rule 15: the depth at which each rule can act: 1 + the most rule edges on a path into it (acyclic graphs)."""
    preds = {n: {a for a, bs in edges.items() if n in bs} for n in edges}
    memo = {}
    def depth(n):
        if n not in memo:
            memo[n] = 1 + max((depth(p) for p in preds[n]), default=0)
        return memo[n]
    return {n: depth(n) for n in edges}


def activation_check(active, candidate, consumers=CONSUMERS):
    """Rule 15: refuse a cycle through the candidate, or any rule acting beyond depth 3 with it (disabled rules included in active)."""
    rules = active + [candidate]
    edges = graph_edges(rules, consumers)
    cyc = find_cycle_through(edges, candidate["code"])
    if cyc:
        return ("automation_rule_cycle", cyc)
    d = act_depths(edges)
    if max(d.values()) > 3:
        return ("automation_depth_exceeded", {k: v for k, v in d.items() if v > 3})
    return None


def schedule_feedback(candidate, jobs, consumers=CONSUMERS):
    """Rule 15: a scheduled job is a source; warn when the candidate writes a table a job reads and the job's events reach its trigger."""
    tables = {EVENTS[e]["table"] for e, _ in emitted_nodes(candidate) if e in EVENTS}
    for j in jobs:
        if tables & set(j["reads"]):
            if any(matches_node(node_of_trigger(candidate), (e, v)) for e, v in j["emits"]):
                return "automation_schedule_feedback"
    return None


# ======================================================================= the runtime (rules 9, 10, 12, 13, 16, 17)
class Runtime:
    """A dispatch loop: events carry (chain, depth); each matched rule acts once per chain and subject, at depth + 1."""
    def __init__(self, rules, consumers=(), breaker=(5, 60), in_a_row=20, owner=None):
        self.rules, self.consumers, self.breaker, self.in_a_row = rules, list(consumers), breaker, in_a_row
        self.owner = owner or {"perms": {action_permission(a, r) for r in rules for a in r["actions"]}, "classes": {"margin"}, "branches": {"B1", "B2"}}
        self.executions, self.keys, self.disabled, self.audit = [], set(), {}, []
        self.counted = {}
        self.scope_skips = {}

    def emit(self, ev_):
        queue = [ev_]
        while queue:
            e = queue.pop(0)
            queue += self.dispatch(e)

    def dispatch(self, e):
        out = []
        subj = {"branch": e.get("branch", "B1")}
        cands = [r for r in self.rules if r["trigger"] == e["type"] and (r.get("disc") is None or r.get("disc") == e.get("disc")) and r["code"] not in self.disabled]
        if not in_scope(subj, self.owner):
            for r in cands:                                         # rule 9: a non-match, counted per rule and day, value-free
                k = (r["code"], e.get("date", "2026-11-20"))
                self.scope_skips[k] = self.scope_skips.get(k, 0) + 1
            cands = []
        matched = [r for r in cands if all(eval_condition(EVENTS[e["type"]]["fields"][f][0], op, v, e["facts"].get(f)) for f, op, v in r.get("conditions", []))]
        for r in sorted(matched, key=lambda r: r["code"]):      # facts first (above), then act
            rec = {"rule": r["code"], "event": e["id"], "chain": e["chain"], "subject": e["subject"], "depth": e["depth"], "actions": []}
            if e["depth"] >= 3:
                rec["outcome"] = "depth_exceeded"
            elif any(x["rule"] == r["code"] and x["chain"] == e["chain"] and x["subject"] == e["subject"] and x["outcome"] in ("acted", "partial") for x in self.executions):
                rec["outcome"] = "skipped_same_target"
            else:
                for i, a in enumerate(r["actions"], 1):
                    plan, why = plan_action(a, e.get("tainted", False), e.get("agent_chain", False), EVENTS[e["type"]]["table"])
                    key = f"automation:{r['code']}@v{r.get('version', 1)}:{e['id']}:{i}"
                    if plan == "skipped":
                        rec["actions"].append(("skipped", why)); continue
                    if a.get("fails_hard"):
                        rec["actions"].append(("failed", "internal_error")); continue
                    if a.get("fails") or action_permission(a, r) not in self.owner["perms"]:
                        rec["actions"].append(("refused", "permission_denied")); continue
                    rec["actions"].append(("done", key))
                    if key in self.keys:
                        continue                                    # a replayed key returns its stored response
                    self.keys.add(key)
                    for et, disc in sorted(emitted_nodes({"actions": [a]}), key=str):
                        if a["kind"] == "notify" and disc == "automation_task":
                            continue
                        self.audit.append((key, e["chain"], e["depth"] + 1))
                        out.append({"id": key + ":" + et, "type": et, "disc": disc, "chain": e["chain"], "depth": e["depth"] + 1,
                                    "subject": e["subject"] + "+" if a.get("new_target") else a.get("target", e["subject"]), "facts": a.get("facts", {}), "t": e["t"]})
                kinds = [s for s, _ in rec["actions"]]
                done_, bad = "done" in kinds, any(s in ("refused", "failed") for s in kinds)
                rec["outcome"] = ("partial" if bad else "acted") if done_ else ("failed" if "failed" in kinds else "refused" if bad else "skipped")
                self.count(r["code"], rec["outcome"], e["t"])
            self.executions.append(rec)
        for sub, (b_, vals) in self.consumers:                      # consumer edges keep the chain and depth
            if sub == e["type"] and e.get("via_consumer", 0) < 6:
                out.append({**e, "id": e["id"] + ":c", "type": b_, "disc": None, "via_consumer": e.get("via_consumer", 0) + 1})
        return out

    def count(self, code, outcome, t):
        """Rule 16: refused, failed and partial count, in a window (business date and time) or in a row; skips never."""
        hist = self.counted.setdefault(code, [])
        hist.append((t, outcome in ("refused", "failed", "partial")))
        n, window = self.breaker
        recent = [tt for tt, bad in hist if bad and t - window < tt <= t]
        streak = 0
        for _, bad in reversed(hist):
            if not bad:
                break
            streak += 1
        if len(recent) >= n or streak >= self.in_a_row:
            self.disabled[code] = "circuit_breaker"


def ev(etype, facts, subject="SO-1", chain="c1", depth=0, eid=None, disc=None, t=0, **kw):
    return {"id": eid or f"{etype}:{subject}:{chain}:{t}", "type": etype, "facts": facts, "subject": subject, "chain": chain, "depth": depth, "disc": disc, "t": t, **kw}


# ======================================================================= decision tables (rules 18-20)
AGG = {"max": max, "min": min, "any": any, "all": all,
       "union": lambda xs: frozenset().union(*xs), "intersection": lambda xs: frozenset.intersection(*xs)}


def cell_match(cell, x):
    if cell is None:
        return True
    if "in" in cell:
        return x in cell["in"]
    if "is" in cell:
        return x is cell["is"]
    return cell.get("min", -INF) <= x < cell.get("max", INF)


def in_domain(i, x):
    if x is None:
        return False
    if i["type"] == "code":
        return x in i["domain"]
    if i["type"] == "boolean":
        return isinstance(x, bool)
    return i["domain"][0] <= x < i["domain"][1]


def evaluate_table(table, inputs):
    """Rule 19-20: out of domain raises; no match is the typed outcome decision_no_match."""
    for i in table["inputs"]:
        if not in_domain(i, inputs.get(i["code"])):
            raise ValueError("decision_input_out_of_domain")
    rows = [r for r in table["rows"] if all(cell_match(r["cells"].get(i["code"]), inputs[i["code"]]) for i in table["inputs"])]
    if not rows:
        return "decision_no_match"
    if table["policy"] == "unique":
        if len(rows) != 1:
            raise ValueError(f"unique table matched {len(rows)} rows")
        return dict(rows[0]["out"])
    return {o["code"]: AGG[o["agg"]]([r["out"][o["code"]] for r in rows]) for o in table["outputs"]}


def box_of(table, row=None):
    """A row's box (or the domain) as one set or interval per input."""
    b = []
    for i in table["inputs"]:
        c = row["cells"].get(i["code"]) if row else None
        if i["type"] == "code":
            b.append(("set", frozenset(i["domain"]) & frozenset(c["in"]) if c else frozenset(i["domain"])))
        elif i["type"] == "boolean":
            b.append(("set", frozenset({c["is"]}) if c else frozenset({False, True})))
        else:
            lo, hi = i["domain"]
            b.append(("iv", (max(lo, c.get("min", -INF)), min(hi, c.get("max", INF))) if c else (lo, hi)))
    return b


def dim_inter(a, b):
    if a[0] == "set":
        return ("set", a[1] & b[1])
    return ("iv", (max(a[1][0], b[1][0]), min(a[1][1], b[1][1])))


def dim_empty(d):
    return not d[1] if d[0] == "set" else d[1][0] >= d[1][1]


def dim_minus(a, b):
    """a minus b in one dimension, as a list of pieces."""
    if a[0] == "set":
        r = a[1] - b[1]
        return [("set", r)] if r else []
    (lo, hi), (blo, bhi) = a[1], b[1]
    out = []
    if lo < min(hi, blo):
        out.append(("iv", (lo, min(hi, blo))))
    if max(lo, bhi) < hi:
        out.append(("iv", (max(lo, bhi), hi)))
    return out


def boxes_intersect(a, b):
    return all(not dim_empty(dim_inter(x, y)) for x, y in zip(a, b))


def subtract(a, b):
    """Box a minus box b, as disjoint boxes."""
    if not boxes_intersect(a, b):
        return [a]
    out, cur = [], list(a)
    for k in range(len(a)):
        for piece in dim_minus(cur[k], b[k]):
            out.append(cur[:k] + [piece] + cur[k + 1:])
        cur[k] = dim_inter(cur[k], b[k])
    return out


class NotProven(Exception):
    pass


def completeness(table, cap=100_000):
    """Rule 19: depth-first box subtraction; returns ('proven', None), ('gap', witness) or ('not_proven', None) at the cap."""
    rows = [box_of(table, r) for r in table["rows"]]
    ops = [0]
    def uncovered(box, j):
        for k in range(j, len(rows)):
            if boxes_intersect(box, rows[k]):
                ops[0] += 1
                if ops[0] > cap:
                    raise NotProven()
                for piece in subtract(box, rows[k]):
                    w = uncovered(piece, k + 1)
                    if w is not None:
                        return w
                return None
        return box                                               # meets no remaining row: a gap
    try:
        g = uncovered(box_of(table), 0)
    except NotProven:
        return ("not_proven", None)
    if g is None:
        return ("proven", None)
    names = [i["code"] for i in table["inputs"]]
    return ("gap", {n: (min(d[1]) if d[0] == "set" else d[1][0]) for n, d in zip(names, g)})


def validate_table(table):
    """Rule 19: order-free aggregators for monotone; exact pairwise overlap for unique. Completeness is a check result only."""
    if table["policy"] == "monotone" and any(o.get("agg") not in AGG for o in table["outputs"]):
        return ("aggregator_not_allowed", None)
    if table["policy"] == "unique":
        boxes = [(r["n"], box_of(table, r)) for r in table["rows"]]
        for (n1, b1), (n2, b2) in itertools.combinations(boxes, 2):
            if boxes_intersect(b1, b2):
                return ("decision_table_overlap", [n1, n2])
    return None


def brute_points(table):
    axes = []
    for i in table["inputs"]:
        if i["type"] == "code":
            axes.append(sorted(i["domain"]))
        elif i["type"] == "boolean":
            axes.append([False, True])
        else:
            lo, hi = i["domain"]
            vals = {lo}
            for r in table["rows"]:
                c = r["cells"].get(i["code"]) or {}
                for b in (c.get("min"), c.get("max")):
                    if b is not None:
                        vals |= {b, b - 1, b + 1}
            axes.append(sorted(v for v in vals if lo <= v < hi))
    return [dict(zip([i["code"] for i in table["inputs"]], p)) for p in itertools.product(*axes)]


def hits_at(table, p):
    return sum(all(cell_match(r["cells"].get(k), v) for k, v in p.items()) for r in table["rows"])


# ======================================================================= W: pure checks
print("== W: rules as lab functions")
OWNER = {"perms": {"Get:sales_order", "CreatePurchaseRequest", "CreatePurchaseOrder", "start_agent:quotation"}, "classes": set(), "branches": {"B1"}}
# -- condition evaluation (rule 8)
check("W01 gt and ge on an amount: 500,000,001 > 500,000,000, 500,000,000 is not, and ge includes it",
      eval_condition("amount", "gt", 500_000_000, 500_000_001) and not eval_condition("amount", "gt", 500_000_000, 500_000_000)
      and eval_condition("amount", "ge", 500_000_000, 500_000_000))
check("W02 between is half-open: the lower bound matches, the upper does not",
      eval_condition("amount", "between", (100, 200), 100) and not eval_condition("amount", "between", (100, 200), 200))
check("W03 in and not_in on codes; is_null and is_not_null on any type; a null value fails every comparison",
      eval_condition("code", "in", {"NORTH", "SOUTH"}, "NORTH") and eval_condition("code", "not_in", {"NORTH"}, "EAST")
      and eval_condition("amount", "is_null", None, None) and not eval_condition("amount", "gt", 0, None) and not eval_condition("code", "ne", "X", None))
check("W04 an operator that does not fit the type is refused (gt on a code, in on a boolean)",
      refused(lambda: eval_condition("code", "gt", "A", "B")) and refused(lambda: eval_condition("boolean", "in", {True}, True)))
rule_alert = {"code": "large_order_warehouse_alert", "trigger": "SalesOrderApproved", "conditions": [("amount_company", "gt", 500_000_000)],
              "actions": [{"kind": "raise_work_item", "owner": "role:warehouse_keeper", "due_days": 1}]}
check("W05 the worked example validates for its owner: transition trigger, amount gate field, the read right on sales orders", validate_rule(rule_alert, OWNER) == [], validate_rule(rule_alert, OWNER))
# -- gate fields and actions (rules 4-7)
bad_field = dict(rule_alert, conditions=[("customer_note", "eq", "urgent"), ("agent_purpose", "eq", "x"), ("nope", "eq", 1)])
check("W06 only gate fields are condition fields: untrusted text and an agent-filled field are refused, an unknown field too",
      validate_rule(bad_field) == ["not_a_gate_field:customer_note", "not_a_gate_field:agent_purpose", "unknown_field:nope"], validate_rule(bad_field))
forbidden = ["PostSalesInvoice", "SubmitPurchaseOrder", "UpdatePartner", "SendOutboundMessage", "StartAgentRun", "UpdatePurchaseRequest", "CreateChangeProposal"]
fs = [validate_rule(dict(rule_alert, actions=[{"kind": "create_draft", "command": c}])) for c in forbidden]
check("W07 create_draft refuses posting, Submit, master data, outbound, agent-start, draft updates and CreateChangeProposal (automation_command_not_allowed)",
      all(f == [f"automation_command_not_allowed:{c}"] for f, c in zip(fs, forbidden)), fs)
check("W08 create_draft accepts an automation-allowed Create with a payload from a gate field",
      validate_rule(dict(rule_alert, actions=[{"kind": "create_draft", "command": "CreatePurchaseRequest", "payload": {"note_amount": ("field", "amount_company")}}])) == [])
check("W09 a payload field may not come from a non-gate field",
      validate_rule(dict(rule_alert, actions=[{"kind": "create_draft", "command": "CreatePurchaseRequest", "payload": {"text": ("field", "customer_note")}}])) == ["payload_not_gate:text"])
saved = dict(COMMANDS)
COMMANDS["X1"] = ("posting", "Post", False, True, False, False, [])
COMMANDS["X2"] = ("other", "Update", True, True, False, False, [])
bad_reg = [registry_ok("X1"), registry_ok("X2")]
COMMANDS.clear(); COMMANDS.update(saved)
check("W10 the registry check: every automation-allowed command is a draft-creating Create of no forbidden class; a posting or an update declared allowed fails it",
      all(registry_ok(c) for c in COMMANDS) and bad_reg == [False, False])
check("W11 start_agent needs the agent type to declare the trigger; set_hold needs a registered hold command",
      validate_rule(dict(rule_alert, actions=[{"kind": "start_agent", "agent_type": "quotation", "subject_table": "sales_order"}])) == ["agent_kind_not_declared"]
      and validate_rule(dict(rule_alert, actions=[{"kind": "set_hold", "command": "UpdatePartner"}])) == ["hold_not_registered"]
      and validate_rule(dict(rule_alert, trigger="WorkItemRaised", conditions=[], actions=[{"kind": "start_agent", "agent_type": "quotation", "subject_table": "work_item"}])) == [])
check("W12 one to five actions", validate_rule(dict(rule_alert, actions=[])) == ["actions_count"]
      and validate_rule(dict(rule_alert, actions=[{"kind": "notify"}] * 6)) == ["actions_count"])
# -- permissions per action (rule 8)
acts = [{"kind": "create_draft", "command": "CreatePurchaseRequest"}, {"kind": "raise_work_item"}, {"kind": "notify"},
        {"kind": "start_agent", "agent_type": "quotation"}, {"kind": "set_hold", "command": "SetSalesOrderDeliveryBlock"}]
check("W13 the permission per action: the command's own, the subject's read right for work items and notices, start_agent:<type>",
      [action_permission(a, rule_alert) for a in acts] == ["CreatePurchaseRequest", "Get:sales_order", "Get:sales_order", "start_agent:quotation", "SetSalesOrderDeliveryBlock"])
check("W14 an owner without the read right on sales orders cannot raise a work item from them (internal-only RaiseAutomationWorkItem is checked by that right)",
      validate_rule(rule_alert, dict(OWNER, perms={"CreatePurchaseRequest"})) == ["permission_denied:Get:sales_order"])
# -- taint and agent chains, decided before acting (rule 9)
res = [plan_action(a, tainted=True, agent_chain=False, subject_table="inbound_message")[0] for a in acts]
check("W15 on a tainted outside-content subject: drafts, work items, notices and start_agent of an agent type accepting that table run; set_hold is skipped",
      res == ["run", "run", "run", "run", "skipped"], res)
check("W16 start_agent is skipped on an agent's chain, and on a tainted subject the agent type does not accept; untainted it runs",
      plan_action(acts[3], False, True, "work_item") == ("skipped", "agent_chain") and plan_action(acts[3], True, False, "sales_order") == ("skipped", "subject_not_accepted")
      and plan_action(acts[3], False, False, "sales_order") == ("run", None))
# -- owner scope, field classes and reader filtering (rules 9, 11)
margin_rule = dict(rule_alert, code="low_margin", conditions=[("margin_percent", "lt", 5)])
check("W17 an owner without the margin class cannot activate a rule on a margin field (automation_owner_scope_insufficient); with it, it validates",
      validate_rule(margin_rule, OWNER) == ["automation_owner_scope_insufficient:margin"] and validate_rule(margin_rule, dict(OWNER, classes={"margin"})) == [])
check("W18 ... nor carry a margin value in a payload",
      validate_rule(dict(rule_alert, actions=[{"kind": "create_draft", "command": "CreatePurchaseRequest", "payload": {"m": ("field", "margin_percent")}}]), OWNER)
      == ["automation_owner_scope_insufficient:margin"])
rt_s = Runtime([rule_alert], owner=dict(OWNER, perms={"Get:sales_order"}))
rt_s.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, subject="SO-B2", branch="B2", chain="s1"))
rt_s.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, subject="SO-B1", branch="B1", chain="s2"))
check("W19 a rule whose owner covers branch B1 never evaluates an order of B2 (no execution record, a value-free daily count of 1); the B1 order acts",
      [(x["subject"], x["outcome"]) for x in rt_s.executions] == [("SO-B1", "acted")] and rt_s.scope_skips == {("large_order_warehouse_alert", "2026-11-20"): 1}, rt_s.scope_skips)
recs = [{"branch": "B1", "conditions": [{"field": "margin_percent", "class": "margin", "value": 3.2}, {"field": "amount_company", "class": None, "value": 9e8}]},
        {"branch": "B2", "conditions": [{"field": "amount_company", "class": None, "value": 7e8}]}]
seen = read_executions(recs, {"branches": {"B1"}, "classes": set()})
check("W20 a reader without B2 sees none of its executions; a reader without margin gets the margin value and result omitted with is_class_filtered, no hash; other values plainly",
      len(seen) == 1 and seen[0]["conditions"][0] == {"field": "margin_percent", "is_class_filtered": True} and seen[0]["conditions"][1]["value"] == 9e8
      and read_executions(recs, {"branches": {"B1", "B2"}, "classes": {"margin"}})[0]["conditions"][0]["value"] == 3.2)
key_a, key_b = b"company-a-secret", b"company-b-secret"
sv = store_value("Nguyen Van A", "personal", key_a)
check("W20b a personal value is stored as an HMAC under the company key, not its plain hash, and differs between companies; other values are kept",
      sv.startswith("hmac:") and sv[5:] != hashlib.sha256(json.dumps("Nguyen Van A").encode()).hexdigest() and sv != store_value("Nguyen Van A", "personal", key_b)
      and store_value(9e8, "internal", key_a) == 9e8)
win = [ev("SalesOrderApproved", {"amount_company": 9e8}, subject=f"S{i}", branch="B1" if i % 3 else "B2") for i in range(30)]
check("W20c validation and replay return automation_owner_scope_limited with the count of window events outside the owner's scope; a company-wide owner gets none",
      scope_limited(rule_alert, OWNER, win) == ("automation_owner_scope_limited", 10) and scope_limited(rule_alert, dict(OWNER, branches={"B1", "B2"}), win) is None)
check("W20d a narrowed owner scope raises one automation_owner_scope_narrowed item per rule in force for company_owner; a widened one raises none",
      scope_narrowed_items({"B1", "B2"}, {"B1"}, ["r1", "r2"]) == [("automation_owner_scope_narrowed", "r1", "company_owner"), ("automation_owner_scope_narrowed", "r2", "company_owner")]
      and scope_narrowed_items({"B1"}, {"B1", "B2"}, ["r1"]) == [])
# -- field-change triggers (rule 14)
upd = {"code": "credit_watch", "trigger": "PartnerUpdated", "conditions": [], "actions": [{"kind": "notify"}]}
check("W21 an update trigger without watched fields is invalid (trigger_unwatched); a non-watchable field is refused",
      validate_rule(upd) == ["trigger_unwatched"] and validate_rule(dict(upd, watched=["name"])) == ["watched_field_not_watchable"])


def fires(rule, event):
    w = rule.get("watched")
    return event["type"] == rule["trigger"] and (EVENTS[event["type"]]["watchable"] is None or bool(set(w or ()) & set(event.get("changed_fields", ()))))


wr = dict(upd, watched=["credit_limit"])
check("W22 a watched update fires only when changed_fields intersect the watched fields; a transition always fires",
      fires(wr, {"type": "PartnerUpdated", "changed_fields": ["credit_limit", "phone"]}) and not fires(wr, {"type": "PartnerUpdated", "changed_fields": ["phone"]})
      and fires(rule_alert, {"type": "SalesOrderApproved"}))
# -- cycles (rule 15)
self_loop = {"code": "notify_on_any_task", "trigger": "WorkItemRaised", "disc": "automation_task", "actions": [{"kind": "raise_work_item"}]}
r_ = activation_check([], self_loop)
check("W23 a rule raising an automation_task on any automation_task is refused as a cycle (the worked example)",
      r_ and r_[0] == "automation_rule_cycle" and r_[1] == ["notify_on_any_task", "notify_on_any_task"], r_)
check("W24 the discriminator splits nodes: the same rule with action notify (automation_notice) passes", activation_check([], dict(self_loop, actions=[{"kind": "notify"}])) is None)
ra = {"code": "A", "trigger": "PurchaseRequestCreated", "actions": [{"kind": "raise_work_item"}]}
rb = {"code": "B", "trigger": "WorkItemRaised", "disc": "automation_task", "actions": [{"kind": "create_draft", "command": "CreatePurchaseRequest"}]}
r_ = activation_check([ra], rb)
check("W25 a two-rule loop is refused when its second rule is activated, naming the path B -> A -> B", r_ and r_[0] == "automation_rule_cycle" and r_[1] == ["B", "A", "B"], r_)
probe = {"code": "P", "trigger": "WorkItemRaised", "disc": "automation_task", "actions": [{"kind": "create_draft", "command": "CreatePurchaseRequest"}]}
probe_consumers = [("PurchaseRequestCreated", ("WorkItemRaised", None))]          # a consumer raising work items of undeclared kinds
r_ = activation_check([], probe, consumers=probe_consumers)
check("W26 the review's probe fails activation: a rule on WorkItemRaised[automation_task] drafting a purchase request, answered by a consumer that raises work items without declared kinds",
      r_ and r_[0] == "automation_rule_cycle", r_)
check("W27 ... and passes when the consumer declares that it raises only another kind",
      activation_check([], probe, consumers=[("PurchaseRequestCreated", ("WorkItemRaised", ("purchase_request_review",)))]) is None)
rc = {"code": "C", "trigger": "SalesOrderChanged", "watched": ["amount_company"], "actions": [{"kind": "create_draft", "command": "CreatePurchaseOrder"}]}
check("W28 a cycle through a registered consumer edge (PurchaseOrderCreated -> SalesOrderChanged) is found, and without the edge the rule passes",
      (activation_check([], rc) or ("",))[0] == "automation_rule_cycle" and activation_check([], rc, consumers=[]) is None)
disabled_rule = dict(ra, disabled=True)
check("W29 disabled rules stay in the graph: enabling B next to a disabled A is still refused", (activation_check([disabled_rule], rb) or ("",))[0] == "automation_rule_cycle")
job = {"reads": ["purchase_request"], "emits": [("WorkItemRaised", "automation_task")]}
check("W30 a scheduled job is a source: a rule writing purchase requests that a nightly job turns into automation tasks it listens to gets automation_schedule_feedback",
      schedule_feedback(probe, [job], consumers=[]) == "automation_schedule_feedback" and schedule_feedback(rule_alert, [job], consumers=[]) is None)


def brute_has_cycle_through(edges, start):
    reach, frontier = set(), set(edges[start])
    while frontier:
        reach |= frontier
        frontier = {m for n in frontier for m in edges[n]} - reach
    return start in reach


agree = 0
for trial in range(300):
    n = random.randint(2, 7)
    names = [f"r{i}" for i in range(n)]
    edges = {a: {b for b in names if random.random() < 0.25} for a in names}
    s = random.choice(names)
    agree += (find_cycle_through(edges, s) is not None) == brute_has_cycle_through(edges, s)
check("W31 cycle detection agrees with brute-force reachability on 300 random rule graphs", agree == 300, agree)
# -- depth (rules 12, 15)
r1 = {"code": "R1", "trigger": "SalesOrderApproved", "actions": [{"kind": "create_draft", "command": "CreatePurchaseRequest"}]}
r2 = {"code": "R2", "trigger": "PurchaseRequestCreated", "actions": [{"kind": "create_draft", "command": "CreatePurchaseOrder"}]}
r3 = {"code": "R3", "trigger": "PurchaseOrderCreated", "actions": [{"kind": "raise_work_item"}]}
r4 = {"code": "R4", "trigger": "WorkItemRaised", "disc": "automation_task", "actions": [{"kind": "notify"}]}
check("W32 three chained rules act at depths 1, 2 and 3 and pass", activation_check([r1, r2], r3, consumers=[]) is None
      and act_depths(graph_edges([r1, r2, r3], [])) == {"R1": 1, "R2": 2, "R3": 3})
r_ = activation_check([r1, r2, r3], r4, consumers=[])
check("W33 a fourth rule on the chain would act at depth 4 and is refused (automation_depth_exceeded)", r_ == ("automation_depth_exceeded", {"R4": 4}), r_)


def brute_depths(edges):
    best = {}
    for start in edges:
        stack = [(start, 1)]
        while stack:
            nd, d = stack.pop()
            best[nd] = max(best.get(nd, 0), d)
            for m in edges[nd]:
                stack.append((m, d + 1))
    return best


ok_d = 0
for trial in range(200):
    n = random.randint(2, 7)
    names = [f"r{i}" for i in range(n)]
    edges = {a: {b for b in names[i + 1:] if random.random() < 0.35} for i, a in enumerate(names)}
    ok_d += act_depths(edges) == brute_depths(edges)
check("W34 the static depth equals brute-force path enumeration on 200 random acyclic graphs", ok_d == 200, ok_d)
loop_rule = {"code": "L", "trigger": "SalesOrderChanged", "conditions": [], "actions": [{"kind": "create_draft", "command": "CreatePurchaseOrder", "target": "SO-9"}]}
rt = Runtime([loop_rule], consumers=CONSUMERS)
rt.emit(ev("SalesOrderChanged", {}, subject="SO-9", chain="cx"))
outs = [x["outcome"] for x in rt.executions]
check("W35 an undeclared loop through a consumer acts at depth 1 only, then the same-target guard stops it; nothing runs at depth 4",
      outs[0] == "acted" and set(outs[1:]) <= {"skipped_same_target", "depth_exceeded"} and max(d for _, _, d in rt.audit) <= 3, outs)
rt2 = Runtime([dict(loop_rule, code="LN", actions=[{"kind": "create_draft", "command": "CreatePurchaseOrder", "new_target": True}])], consumers=CONSUMERS)
rt2.emit(ev("SalesOrderChanged", {}, subject="SO-0", chain="cy"))
check("W36 a rule acting on a new target each round passes the same-target guard, and the depth cap bounds the chain at 3 with depth_exceeded recorded",
      max(d for _, _, d in rt2.audit) == 3 and any(x["outcome"] == "depth_exceeded" for x in rt2.executions), sorted({d for _, _, d in rt2.audit}))
# -- same rule, same target (rule 13)
rt3 = Runtime([rule_alert])
rt3.emit(ev("SalesOrderApproved", {"amount_company": 620_000_000}, subject="SO-1043", chain="k1", t=1))
rt3.emit(ev("SalesOrderApproved", {"amount_company": 620_000_000}, subject="SO-1043", chain="k1", eid="second", t=2))
rt3.emit(ev("SalesOrderApproved", {"amount_company": 620_000_000}, subject="SO-1043", chain="k2", t=3))
check("W37 the rule acts once per chain and subject: a second match in chain k1 is skipped_same_target, a new chain acts again",
      [x["outcome"] for x in rt3.executions] == ["acted", "skipped_same_target", "acted"], [x["outcome"] for x in rt3.executions])
rt3.emit(ev("SalesOrderApproved", {"amount_company": 400_000_000}, subject="SO-1044", chain="k3", t=4))
check("W38 an order of 400,000,000 does not match, and non-matches leave no execution record", len(rt3.executions) == 3)
# -- idempotency (rule 17)
rt4 = Runtime([dict(rule_alert, actions=[{"kind": "raise_work_item"}, {"kind": "notify"}])])
e_ = ev("SalesOrderApproved", {"amount_company": 9e8}, subject="SO-7", chain="r1", eid="EV7")
rt4.emit(e_)
keys_first = sorted(rt4.keys)
rt4.executions.clear()
rt4.emit(e_)
check("W39 keys are automation:<rule version>:<event>:<n>, one per action, and a retried delivery adds none",
      keys_first == ["automation:large_order_warehouse_alert@v1:EV7:1", "automation:large_order_warehouse_alert@v1:EV7:2"] and sorted(rt4.keys) == keys_first, keys_first)
# -- independent actions and outcomes (rule 10; EC-160)
two = dict(rule_alert, code="draft_and_agent", trigger="WorkItemRaised", conditions=[], disc="inbound_message_matched",
           actions=[{"kind": "create_draft", "command": "CreatePurchaseRequest"}, {"kind": "start_agent", "agent_type": "quotation", "subject_table": "work_item"}])
rt5 = Runtime([two])
rt5.emit(ev("WorkItemRaised", {"kind": "inbound_message_matched"}, subject="WI-1", chain="a1", disc="inbound_message_matched", agent_chain=True, tainted=True))
x = rt5.executions[0]
check("W40 EC-160: on an agent's chain the draft is done, the agent start skipped by design, and the execution is acted",
      x["actions"][0][0] == "done" and x["actions"][1] == ("skipped", "agent_chain") and x["outcome"] == "acted", x)
half = dict(rule_alert, code="half", actions=[{"kind": "raise_work_item"}, {"kind": "create_draft", "command": "CreatePurchaseRequest", "fails": True}])
rt6 = Runtime([half]); rt6.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, chain="h1"))
check("W41 actions are independent: one done and one refused give outcome partial, and the done action's work item stays",
      rt6.executions[0]["outcome"] == "partial" and len(rt6.keys) == 1)
mix = dict(rule_alert, code="mix", actions=[{"kind": "create_draft", "command": "CreatePurchaseRequest", "fails": True}, {"kind": "create_draft", "command": "CreatePurchaseOrder", "fails_hard": True}])
rt6r = Runtime([dict(rule_alert, code="ref", actions=[{"kind": "create_draft", "command": "CreatePurchaseRequest", "fails": True}])]); rt6r.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, chain="m0"))
rtm = Runtime([mix]); rtm.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, chain="m1"))
check("W41b with no action done, a refusal and a failure give failed; refusals alone give refused", rtm.executions[0]["outcome"] == "failed" and rt6r.executions[0]["outcome"] == "refused")
# -- circuit breaker (rule 16)
failing = dict(rule_alert, code="owner_lost_right", actions=[{"kind": "create_draft", "command": "CreatePurchaseRequest", "fails": True}])
rt7 = Runtime([failing], breaker=(5, 60))
for i, t in enumerate([0, 10, 20, 30]):
    rt7.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, subject=f"S{i}", chain=f"b{i}", t=t))
w42 = "owner_lost_right" not in rt7.disabled
rt7.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, subject="S5", chain="b5", t=40))
check("W42 four refusals within 60 minutes do not trip the breaker; the fifth does (circuit_breaker), and a disabled rule is not evaluated",
      w42 and rt7.disabled.get("owner_lost_right") == "circuit_breaker" and (rt7.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, subject="S6", chain="b6", t=41)) or len(rt7.executions) == 5))
rt8 = Runtime([failing], breaker=(5, 60))
for i in range(19):
    rt8.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, subject=f"S{i}", chain=f"z{i}", t=i * 200))
w43a = "owner_lost_right" not in rt8.disabled
rt8.emit(ev("SalesOrderApproved", {"amount_company": 9e8}, subject="S19", chain="z19", t=19 * 200))
check("W43 refusals spread beyond the window still trip the breaker at 20 in a row (19 do not)", w43a and rt8.disabled.get("owner_lost_right") == "circuit_breaker")
skipper = dict(two, code="skipper", actions=[{"kind": "start_agent", "agent_type": "quotation", "subject_table": "work_item"}])
rt9 = Runtime([skipper])
for i in range(30):
    rt9.emit(ev("WorkItemRaised", {"kind": "inbound_message_matched"}, subject=f"W{i}", chain=f"q{i}", disc="inbound_message_matched", agent_chain=True, t=i))
check("W44 by-design skips never count: 30 skipped executions in 30 minutes leave the rule enabled",
      "skipper" not in rt9.disabled and {x["outcome"] for x in rt9.executions} == {"skipped"})
# -- evaluate all, then act (rule 10)
hold_a = {"code": "A_hold", "trigger": "SalesOrderApproved", "conditions": [("is_rush", "eq", True)], "actions": [{"kind": "notify"}]}
hold_b = {"code": "B_big", "trigger": "SalesOrderApproved", "conditions": [("amount_company", "gt", 1)], "actions": [{"kind": "raise_work_item"}]}
outcomes = set()
for perm in itertools.permutations([hold_a, hold_b, rule_alert]):
    rtp = Runtime(list(perm))
    rtp.emit(ev("SalesOrderApproved", {"amount_company": 9e8, "is_rush": True}, chain="p"))
    outcomes.add(tuple(sorted((x["rule"], x["outcome"]) for x in rtp.executions)))
check("W45 the outcomes of rules on one event do not depend on rule order (all 6 orders give the same set)", len(outcomes) == 1, outcomes)
# -- decision tables (rules 18-20)
IN = [{"code": "warehouse_code", "type": "code", "domain": {"NORTH", "SOUTH", "EAST"}}, {"code": "amount_company", "type": "amount", "domain": (0, INF)}]
OUT = [{"code": "owner_role"}, {"code": "due_days"}]
draft_rows = [
    {"n": 1, "cells": {"warehouse_code": {"in": {"NORTH", "SOUTH"}}, "amount_company": {"min": 500_000_000, "max": 2_000_000_000}}, "out": {"owner_role": "warehouse_keeper", "due_days": 1}},
    {"n": 2, "cells": {"warehouse_code": {"in": {"NORTH", "SOUTH"}}, "amount_company": {"min": 1_500_000_000}}, "out": {"owner_role": "warehouse_manager", "due_days": 1}},
    {"n": 3, "cells": {"warehouse_code": {"in": {"EAST"}}, "amount_company": {"min": 500_000_000}}, "out": {"owner_role": "warehouse_keeper", "due_days": 2}}]
t_draft = {"policy": "unique", "inputs": IN, "outputs": OUT, "rows": draft_rows}
check("W46 the worked example's draft table: rows 1 and 2 overlap (decision_table_overlap)", validate_table(t_draft) == ("decision_table_overlap", [1, 2]), validate_table(t_draft))
rows_fixed = [dict(draft_rows[0], cells={"warehouse_code": {"in": {"NORTH", "SOUTH"}}, "amount_company": {"min": 500_000_000, "max": 1_500_000_000}})] + draft_rows[1:]
t_fixed = dict(t_draft, rows=rows_fixed)
cp = completeness(t_fixed)
check("W47 the fixed table is accepted; its completeness proof reports decision_table_gap with a witness below 500,000,000 that truly matches no row",
      validate_table(t_fixed) is None and cp[0] == "gap" and cp[1]["amount_company"] < 500_000_000 and hits_at(t_fixed, cp[1]) == 0, cp)
check("W48 (SOUTH, 1,600,000,000) gives the warehouse manager in 1 day; (EAST, 100) is decision_no_match",
      evaluate_table(t_fixed, {"warehouse_code": "SOUTH", "amount_company": 1_600_000_000}) == {"owner_role": "warehouse_manager", "due_days": 1}
      and evaluate_table(t_fixed, {"warehouse_code": "EAST", "amount_company": 100}) == "decision_no_match")
check("W49 a null input, a code not in the version's list or a negative amount is decision_input_out_of_domain",
      all(refused(lambda v=v: evaluate_table(t_fixed, v)) == "decision_input_out_of_domain"
          for v in ({"warehouse_code": None, "amount_company": 5}, {"warehouse_code": "WEST", "amount_company": 5}, {"warehouse_code": "EAST", "amount_company": -1})))
tables_ = {"big": {"policy": "unique", "inputs": [{"code": "x", "type": "amount", "domain": (0, INF)}], "outputs": [{"code": "is_big"}],
                   "rows": [{"n": 2, "cells": {"x": {"min": 10}}, "out": {"is_big": True}}]}}
check("W50 the decision operator applies the rule's no-match handling (false here) and refuses a use without one",
      eval_condition("amount", "decision", ("big", "is_big", False), 12, tables_) and not eval_condition("amount", "decision", ("big", "is_big", False), 9, tables_)
      and validate_rule(dict(rule_alert, conditions=[("amount_company", "decision", ("big", "is_big", None))])) == ["no_match_unhandled:amount_company"])


def rand_table(policy, n_rows=None, n_num=1):
    rows = []
    for n in range(1, (n_rows or random.randint(2, 6)) + 1):
        cells = {"w": random.choice([None, {"in": {"A"}}, {"in": {"A", "B"}}, {"in": {"C"}}]), "f": random.choice([None, {"is": True}, {"is": False}])}
        for k in range(n_num):
            lo, hi = random.choice([None, 0, 100, 200, 300]), random.choice([None, 150, 250, 400])
            c = {}
            if lo is not None: c["min"] = lo
            if hi is not None and (lo is None or hi > lo): c["max"] = hi
            cells[f"x{k}"] = c or None
        rows.append({"n": n, "cells": cells, "out": {"o": random.randint(1, 9), "s": frozenset({random.randint(1, 3)})}})
    return {"policy": policy, "inputs": [{"code": "w", "type": "code", "domain": {"A", "B", "C"}}, {"code": "f", "type": "boolean"}]
            + [{"code": f"x{k}", "type": "amount", "domain": (0, 1000)} for k in range(n_num)],
            "outputs": [{"code": "o", "agg": "max"}, {"code": "s", "agg": "union"}], "rows": rows}


agree_o = agree_c = 0
for trial in range(300):
    t_ = rand_table("unique", n_num=random.randint(1, 2))
    pts = brute_points(t_)
    hits = [hits_at(t_, p) for p in pts]
    got = validate_table(t_)
    agree_o += (got is not None) == (max(hits) > 1)
    c_ = completeness(t_)
    agree_c += (c_[0] == "proven" and 0 not in hits) or (c_[0] == "gap" and 0 in hits and hits_at(t_, c_[1]) == 0)
ORG = {"T1": ["E1", "E2", "E3"], "T2": ["E4"]}
RD = {"Get:sales_order"}
ASG = [{"branches": ("B1",), "warehouses": ("W1", "W2"), "owner_scope": "team", "units": ("T1",), "perms": RD, "valid_from": "2026-01-01", "valid_to": None},
       {"branches": ("B2",), "warehouses": ("W3",), "owner_scope": "branch", "perms": RD, "valid_from": "2026-01-01", "valid_to": "2026-11-30"}]
D = "2026-11-20"
S0 = scope_cells(ASG, D, ORG, "Get:sales_order")


def oc_run(asg, day=D, org=ORG, stored=None, **kw):
    return OwnerCheck(stored or S0).run(asg, day, org, **kw)


check("W20e the stored cells: one per permission-bearing assignment and single branch and warehouse, with level, units and employees; an unchanged scope raises nothing",
      S0 == {("B1", "W1", "team", ("T1",), ("E1", "E2", "E3")), ("B1", "W2", "team", ("T1",), ("E1", "E2", "E3")), ("B2", "W3", "branch", (), ())}
      and oc_run(ASG, "2026-11-25") is None)
r_lapse = oc_run(ASG, "2026-12-01")
check("W20f the B2 assignment lapses by date (no event): narrowed for the rule's owner, naming the uncovered B2 cell",
      r_lapse == ("automation_owner_scope_narrowed", "rule_owner", [("B2", "W3", "branch", (), ())]), r_lapse)
check("W20g a lost warehouse alone is narrowed", oc_run([dict(ASG[0], warehouses=("W1",)), ASG[1]])[2] == [("B1", "W2", "team", ("T1",), ("E1", "E2", "E3"))])
check("W20i a reorganisation that moves E3 out of the owner's team is narrowed", oc_run(ASG, org={"T1": ["E1", "E2"], "T2": ["E3", "E4"]})[0] == "automation_owner_scope_narrowed")
COMP = [{"branches": ("B1",), "warehouses": None, "owner_scope": "company", "perms": RD, "valid_from": "2026-01-01", "valid_to": None},
        {"branches": ("B2",), "warehouses": None, "owner_scope": "company", "perms": RD, "valid_from": "2026-01-01", "valid_to": None}]
SC = scope_cells(COMP, D, ORG, "Get:sales_order")
r_probe = oc_run([COMP[0], dict(COMP[1], owner_scope="own")], stored=SC)
check("W20o the review's probe: B2 lowered from company to own while B1 stays is narrowed, naming the B2 cell (a flat union saw nothing)",
      r_probe == ("automation_owner_scope_narrowed", "rule_owner", [("B2", "all", "company", (), ())]), r_probe)
other_role = {"branches": ("B2",), "warehouses": None, "owner_scope": "company", "perms": {"Get:purchase_order"}, "valid_from": "2026-01-01", "valid_to": None}
r_perm = oc_run([COMP[0], dict(COMP[1], valid_to="2026-11-19"), other_role], stored=SC)
check("W20p the only permission-bearing B2 assignment ends while another role's B2 assignment remains: narrowed",
      r_perm == ("automation_owner_scope_narrowed", "rule_owner", [("B2", "all", "company", (), ())]), r_perm)
SW = [dict(COMP[0], owner_scope="company"), dict(COMP[1], owner_scope="branch")]
r_swap = oc_run([dict(SW[0], owner_scope="branch"), dict(SW[1], owner_scope="company")], stored=scope_cells(SW, D, ORG, "Get:sales_order"))
check("W20q a level swap between two branches (B1 company -> branch, B2 branch -> company) is narrowed, naming B1",
      r_swap == ("automation_owner_scope_narrowed", "rule_owner", [("B1", "all", "company", (), ())]), r_swap)
shuffle = [dict(ASG[0], warehouses=("W1",)), dict(ASG[0], warehouses=("W2",)), ASG[1]]
check("W20j an equal-reach reshuffle (one assignment split into two with the same reach) stays silent", oc_run(shuffle) is None)
merge = [{"branches": ("B1", "B2"), "warehouses": None, "owner_scope": "company", "perms": RD, "valid_from": "2026-01-01", "valid_to": None}]
check("W20j2 ... and so does merging two company assignments into one with the same reach", oc_run(merge, stored=SC) is None)
wide = ASG + [{"branches": None, "warehouses": None, "owner_scope": "company", "perms": RD, "valid_from": "2026-11-01", "valid_to": None}]
ow = OwnerCheck(S0)
check("W20k a wider scope (an unscoped company assignment) only updates the stored cells", ow.run(wide, D, ORG) == "updated" and ("all", "all", "company", (), ()) in ow.owner_scope and ow.open_item is None)
check("W20l after that, losing the unscoped assignment is narrowed", ow.run(ASG, D, ORG)[2] == [("all", "all", "company", (), ())])
ok_ = OwnerCheck(S0); first = ok_.run([dict(ASG[0], warehouses=("W1",)), ASG[1]], D, ORG); second = ok_.run(ASG[:1], D, ORG)
check("W20m while the item is open no second item is raised and the stored cells stay; resolving it stores the new cells",
      first[0] == "automation_owner_scope_narrowed" and second == "item_open" and ok_.owner_scope == S0
      and (ok_.resolve(ASG[:1], D, ORG) or ok_.owner_scope == scope_cells(ASG[:1], D, ORG, "Get:sales_order")) and ok_.open_item is None)
check("W20n owner_inactive (the only case for company_owner) when no assignment is in force or the account is disabled",
      oc_run([dict(a, valid_to="2026-11-30") for a in ASG], "2026-12-02") == "owner_inactive" and oc_run(ASG, account_active=False) == "owner_inactive")
check("W50b a rule may pin only assisted or active table versions: a draft, retired or unknown pinned version is refused",
      pins_ok({"pins": ["t1"]}, {"t1": "active"}) and pins_ok({"pins": ["t2"]}, {"t2": "assisted"}) and not pins_ok({"pins": ["t3"]}, {"t3": "draft"})
      and not pins_ok({"pins": ["t4"]}, {"t4": "retired"}) and not pins_ok({"pins": ["x"]}, {}))
check("W51 the pairwise overlap check agrees with brute force over bound points on 300 random unique tables", agree_o == 300, agree_o)
check("W52 the completeness proof agrees with brute force on the same tables: proven exactly when no point is uncovered, and every gap witness matches no row", agree_c == 300, agree_c)
big = rand_table("monotone", n_rows=200, n_num=4)
t0 = time.time()
cb = completeness(big, cap=100_000)
dt = time.time() - t0
check("W53 at 200 rows and 6 inputs the proof stops at its work cap or finishes, never claims a false gap, within 60 seconds",
      cb[0] in ("proven", "not_proven", "gap") and (cb[0] != "gap" or hits_at(big, cb[1]) == 0) and dt < 60, (cb[0], round(dt, 1)))
mono_ok = 0
for trial in range(200):
    t_ = rand_table("monotone")
    t_["rows"].append({"n": 99, "cells": {}, "out": {"o": 0, "s": frozenset()}})
    p = {"w": random.choice(["A", "B", "C"]), "x0": random.randint(0, 999), "f": random.choice([True, False])}
    base = evaluate_table(t_, p)
    sh = dict(t_, rows=random.sample(t_["rows"], len(t_["rows"])) + t_["rows"][:2])
    mono_ok += evaluate_table(sh, p) == base
check("W54 monotone outputs (max, union) are the same under shuffled and duplicated rows in 200 random tables", mono_ok == 200, mono_ok)
check("W55 sum and first are not offered as aggregators",
      validate_table(dict(t_fixed, policy="monotone", outputs=[{"code": "due_days", "agg": "sum"}])) == ("aggregator_not_allowed", None)
      and validate_table(dict(t_fixed, policy="monotone", outputs=[{"code": "due_days", "agg": "first"}])) == ("aggregator_not_allowed", None))
# -- the replay diff (rule 23)


def replay(current, candidate, events):
    diff, unrec = [], 0
    for e in events:
        if not EVENTS[e["type"]]["replayable"]:
            unrec += 1
        def outcome(r):
            return r is not None and all(eval_condition(EVENTS[e["type"]]["fields"][f][0], op, v, e["facts"].get(f)) for f, op, v in r["conditions"])
        a, b = outcome(current), outcome(candidate)
        if a != b:
            diff.append((e["subject"], a, b, e["facts"].get("amount_company", 0)))
    return {"added": sum(1 for d in diff if d[2]), "removed": sum(1 for d in diff if d[1]), "amount_added": sum(d[3] for d in diff if d[2]),
            "not_reconstructable": unrec, "changed": diff}


v3 = dict(rule_alert, conditions=[("amount_company", "gt", 200_000_000)])
amounts = [random.choice([1e8, 1.5e8, 2.5e8, 3e8, 4.5e8, 6e8, 9e8, 1.2e9]) for _ in range(412)]
evs = [ev("SalesOrderApproved", {"amount_company": a}, subject=f"SO-{i}", eid=f"E{i}") for i, a in enumerate(amounts)]
rd = replay(rule_alert, v3, evs)
cur_n = sum(1 for a in amounts if a > 5e8); cand_n = sum(1 for a in amounts if a > 2e8)
check("W56 the replay of a lowered threshold lists exactly the orders between 200,000,000 and 500,000,000 as added, none removed, with their amount sum",
      rd["added"] == cand_n - cur_n and rd["removed"] == 0 and rd["amount_added"] == sum(a for a in amounts if 2e8 < a <= 5e8), (rd["added"], rd["removed"]))
check("W57 a first version replays against none: every event it would act on is added", replay(None, rule_alert, evs)["added"] == cur_n)
pe = [ev("PartnerUpdated", {"credit_limit": 5}, subject="P1"), ev("PartnerUpdated", {"credit_limit": 9}, subject="P2")]
rp = replay({"conditions": [("credit_limit", "gt", 6)]}, {"conditions": [("credit_limit", "gt", 4)]}, pe)
check("W58 events of a trigger that is not replayable are counted not_reconstructable", rp["not_reconstructable"] == 2 and rp["added"] == 1, rp)

# ======================================================================= D: database checks (--load)
if "--load" in sys.argv:
    import psycopg  # noqa: E402,F401
    import uuid as _uuid
    from load_all import load_all  # noqa: E402
    dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = load_all(dsn, DOCS)
    check("D01 load_all.py loads every DDL file of design/ with the configuration file", n_tables > 200, n_tables)
    c = conn(); c.autocommit = True
    X = c.execute
    NEW = {"automation_rule", "automation_rule_version", "automation_execution", "automation_scope_skip", "configuration_state", "decision_table", "decision_table_version",
           "decision_table_row", "parameter_set", "parameter_set_version", "parameter_set_value", "artifact_promotion_evidence", "artifact_transition",
           "artifact_shadow_outcome", "golden_case_label", "artifact_monitor_snapshot"}
    nulls = X("select table_name from information_schema.columns where table_schema='nativeflows' and column_name='company_id' and is_nullable='NO' and table_name = any(%s)",
              (sorted(NEW),)).fetchall()
    forced = X("select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where nspname='nativeflows' and relname = any(%s) and relrowsecurity and relforcerowsecurity",
               (sorted(NEW),)).fetchone()[0]
    pol = X("select count(distinct tablename) from pg_policies where schemaname='nativeflows' and policyname='company_policy' and tablename = any(%s)", (sorted(NEW),)).fetchone()[0]
    check("D02 the sixteen configuration tables exist with company_id NOT NULL, forced row-level security and the company policy",
          len(nulls) == len(NEW) == forced == pol == 16, (len(nulls), forced, pol))
    cc = {(t_, col): d for t_, col, d in X("select table_name, column_name, column_default from information_schema.columns where table_schema='nativeflows' and table_name in ('outbox_event','audit_record')").fetchall()}
    check("D03 outbox_event and audit_record carry causation_chain_id, causation_depth (no default) and automation_rule_version_id",
          all((t_, col) in cc for t_ in ("outbox_event", "audit_record") for col in ("causation_chain_id", "causation_depth", "automation_rule_version_id"))
          and cc[("outbox_event", "causation_depth")] is None and cc[("audit_record", "causation_depth")] is None)
    I = {k: new() for k in ["u", "u2", "co", "rule", "rule2", "v1", "v2", "v3", "v4", "w1", "tab", "tv1", "ps", "pv1"]}
    t = str(I["co"])[-8:]
    X("insert into currency (code, minor_unit) values ('USD', 2) on conflict do nothing")
    for k in ("u", "u2"):
        X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I[k], f"u22{k}{t}"))
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','USD','UTC','l10n_test','test','warehouse',%s,'en')", (I["co"], "C22-" + t, I["u"]))
    X("select set_config('nativeflows.company_id', %s, false)", (str(I["co"]),))
    H = hashlib.sha256(b"x").hexdigest()
    ACT = json.dumps([{"kind": "raise_work_item", "owner": "role:warehouse_keeper", "due_days": 1}])
    for k, code in (("rule", "large_order_warehouse_alert"), ("rule2", "other_rule")):
        X("insert into automation_rule (id, company_id, code, name, owner_user_id, recorded_at) values (%s,%s,%s,%s,%s,now())", (I[k], I["co"], code, code, I["u"]))

    def version(cx, vid, rule="rule", n=1, state="draft"):
        cx.execute("""insert into automation_rule_version (id, company_id, automation_rule_id, version, trigger_event_type, conditions, actions, state, content_hash,
                      registry_version, drafted_by_kind, drafted_by_id, on_behalf_of_id, drafting_window_to, recorded_at)
                      values (%s,%s,%s,%s,'SalesOrderApproved','[{"field":"amount_company","operator":"gt","value":500000000}]',%s,%s,%s,'1.0.0','human',%s,%s,'2026-11-15',now())""",
                   (vid, I["co"], I[rule], n, ACT, state, H, I["u"], I["u"]))

    def D_bad(name, match, fn):
        def run(cx):
            cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, True, match)

    def D_good(name, fn):
        def run(cx):
            cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, False)
    D_bad("D04 a version is inserted only as a draft (not active, not shadow)", "inserted only as drafts", lambda cx: version(cx, new(), n=9, state="active"))
    D_bad("D05 every draft has a drafting window", "drafting_window_to", lambda cx: cx.execute(
        """insert into automation_rule_version (id, company_id, automation_rule_id, version, trigger_event_type, actions, content_hash, registry_version, drafted_by_kind,
           drafted_by_id, on_behalf_of_id, recorded_at) values (%s,%s,%s,8,'SalesOrderApproved',%s,%s,'1','human',%s,%s,now())""", (new(), I["co"], I["rule"], ACT, H, I["u"], I["u"])))
    version(c, I["v1"])
    D_good("D06 a draft version changes freely (conditions edited)", lambda cx: cx.execute(
        "update automation_rule_version set conditions='[{\"field\":\"amount_company\",\"operator\":\"gt\",\"value\":400000000}]' where id=%s", (I["v1"],)))
    D_bad("D07 a draft leaves draft only to backtested (draft -> active refused)", "leaves draft only to backtested",
          lambda cx: cx.execute("update automation_rule_version set state='active', effective_from='2026-11-20' where id=%s", (I["v1"],)))
    X("update automation_rule_version set state='backtested' where id=%s", (I["v1"],))
    D_bad("D08 out of draft, the content is immutable (artifact_version_immutable)", "immutable once out of draft",
          lambda cx: cx.execute("update automation_rule_version set conditions='[]' where id=%s", (I["v1"],)))
    D_bad("D09 ... and so are the pinned table versions", "immutable once out of draft",
          lambda cx: cx.execute("update automation_rule_version set decision_table_version_ids=array[%s]::uuid[] where id=%s", (new(), I["v1"])))
    D_bad("D10 a version never returns to draft", "cannot return to draft", lambda cx: cx.execute("update automation_rule_version set state='draft' where id=%s", (I["v1"],)))
    D_bad("D11 an automation rule version has no assisted stage", "ck_automation_rule_version_no_assisted",
          lambda cx: cx.execute("update automation_rule_version set state='assisted', effective_from='2026-11-20' where id=%s", (I["v1"],)))
    D_bad("D12 active needs effective_from", "ck_automation_rule_version_effective", lambda cx: cx.execute("update automation_rule_version set state='active' where id=%s", (I["v1"],)))
    D_bad("D13 a backtested version is not deleted (only drafts are)", "deleted only in draft", lambda cx: cx.execute("delete from automation_rule_version where id=%s", (I["v1"],)))
    D_bad("D14 the current pointer may not name a backtested version", "artifact_version_not_eligible",
          lambda cx: cx.execute("update automation_rule set current_version_id=%s, owner_confirmed_at=now(), owner_confirmed_user_id=%s where id=%s", (I["v1"], I["u"], I["rule"])))
    X("update automation_rule_version set state='active', effective_from='2026-11-20' where id=%s", (I["v1"],))
    D_bad("D15 a version in force needs the owner's confirmation (automation_owner_not_confirmed)", "ck_automation_rule_owner_confirmed",
          lambda cx: cx.execute("update automation_rule set current_version_id=%s where id=%s", (I["v1"], I["rule"])))
    X("update automation_rule set current_version_id=%s, owner_confirmed_at=now(), owner_confirmed_user_id=%s where id=%s", (I["v1"], I["u"], I["rule"]))
    D_bad("D15b an owner change keeps no stale consent: the confirmation names the old owner, so the rule in force is refused until the new owner consents",
          "ck_automation_rule_owner_confirmed", lambda cx: cx.execute("update automation_rule set owner_user_id=%s where id=%s", (I["u2"], I["rule"])))
    D_good("D15c ... and the change with consent cleared and given again by the new owner is accepted", lambda cx: (
        cx.execute("update automation_rule set owner_user_id=%s, owner_confirmed_at=now(), owner_confirmed_user_id=%s where id=%s", (I["u2"], I["u2"], I["rule"])),
        cx.execute("update automation_rule set owner_user_id=%s, owner_confirmed_at=now(), owner_confirmed_user_id=%s where id=%s", (I["u"], I["u"], I["rule"]))))
    D_bad("D16 effective_from is set once", "set once", lambda cx: cx.execute("update automation_rule_version set effective_from='2026-12-01' where id=%s", (I["v1"],)))
    version(c, I["v2"], rule="rule2")
    X("update automation_rule_version set state='backtested' where id=%s", (I["v2"],))
    X("update automation_rule_version set state='active', effective_from='2026-11-20' where id=%s", (I["v2"],))
    D_bad("D17 a pointer may not name another rule's version (composite key)", "fk_automation_rule_current_version",
          lambda cx: cx.execute("update automation_rule set current_version_id=%s where id=%s", (I["v2"], I["rule"])))
    D_bad("D18 a version in force is not demoted while the pointer names it", "move the current pointer first",
          lambda cx: cx.execute("update automation_rule_version set state='shadow' where id=%s", (I["v1"],)))
    D_good("D19 after the pointer moves off it, the version is demoted to shadow and may be the shadow pointer", lambda cx: (
        cx.execute("update automation_rule set current_version_id=null where id=%s", (I["rule"],)),
        cx.execute("update automation_rule_version set state='shadow' where id=%s", (I["v1"],)),
        cx.execute("update automation_rule set shadow_version_id=%s where id=%s", (I["v1"], I["rule"]))))
    D_bad("D20 the shadow pointer may not name an active version", "must name a shadow version",
          lambda cx: cx.execute("update automation_rule set shadow_version_id=%s where id=%s", (I["v2"], I["rule2"])))
    X("update automation_rule_version set state='retired' where id=%s", (I["v1"],))
    check("D21 retiring a shadow version clears the shadow pointer that names it",
          X("select shadow_version_id from automation_rule where id=%s", (I["rule"],)).fetchone()[0] is None)
    X("update automation_rule set current_version_id=%s, owner_confirmed_at=now(), owner_confirmed_user_id=%s where id=%s", (I["v2"], I["u"], I["rule2"]))
    X("update automation_rule_version set state='retired' where id=%s", (I["v2"],))
    check("D22 retiring the version in force clears the current pointer",
          X("select current_version_id from automation_rule where id=%s", (I["rule2"],)).fetchone()[0] is None)
    D_bad("D23 retired is final", "retired, which is final", lambda cx: cx.execute("update automation_rule_version set state='active' where id=%s", (I["v2"],)))
    version(c, I["v3"], n=2)
    D_bad("D24 a draft is deleted, not retired", "drafts are deleted", lambda cx: cx.execute("update automation_rule_version set state='retired' where id=%s", (I["v3"],)))
    D_good("D25 a draft is deleted", lambda cx: cx.execute("delete from automation_rule_version where id=%s", (I["v3"],)))
    version(c, I["v4"], n=3)
    X("update automation_rule_version set state='backtested' where id=%s", (I["v4"],))
    X("update automation_rule_version set state='shadow' where id=%s", (I["v4"],))
    X("update automation_rule set shadow_version_id=%s where id=%s", (I["v4"], I["rule"]))
    X("update automation_rule_version set state='active', effective_from='2026-11-21' where id=%s", (I["v4"],))
    check("D26 leaving shadow (promotion to active) clears the shadow pointer that names it",
          X("select shadow_version_id from automation_rule where id=%s", (I["rule"],)).fetchone()[0] is None)
    # decision tables: rows frozen with their version, 200 rows
    X("insert into decision_table (id, company_id, code, name, owner_user_id, recorded_at) values (%s,%s,'warehouse_alert_owner','W',%s,now())", (I["tab"], I["co"], I["u"]))
    X("""insert into decision_table_version (id, company_id, decision_table_id, version, hit_policy, inputs, outputs, content_hash, registry_version, drafted_by_kind,
         drafted_by_id, on_behalf_of_id, drafting_window_to, recorded_at) values (%s,%s,%s,1,'unique','[{"code":"amount_company","type":"amount"}]','[{"code":"owner_role"}]',%s,'1.0.0','human',%s,%s,'2026-11-15',now())""",
      (I["tv1"], I["co"], I["tab"], H, I["u"], I["u"]))
    X("""insert into decision_table_row (company_id, decision_table_version_id, row_number, cells, outputs, recorded_at) values (%s,%s,1,'{}','{"owner_role":"warehouse_keeper"}',now())""",
      (I["co"], I["tv1"]))
    D_bad("D27 a table has at most 200 rows", "ck_decision_table_row_row_number", lambda cx: cx.execute(
        "insert into decision_table_row (company_id, decision_table_version_id, row_number, cells, outputs, recorded_at) values (%s,%s,201,'{}','{}',now())", (I["co"], I["tv1"])))
    D_bad("D28 a monotone or unique policy only", "ck_decision_table_version_hit_policy",
          lambda cx: cx.execute("update decision_table_version set hit_policy='first' where id=%s", (I["tv1"],)))
    X("update decision_table_version set state='backtested' where id=%s", (I["tv1"],))
    D_bad("D29 rows of a backtested table version are frozen (insert)", "frozen with their version", lambda cx: cx.execute(
        "insert into decision_table_row (company_id, decision_table_version_id, row_number, cells, outputs, recorded_at) values (%s,%s,2,'{}','{}',now())", (I["co"], I["tv1"])))
    D_bad("D30 ... and (update)", "frozen with their version", lambda cx: cx.execute("update decision_table_row set outputs='{}' where decision_table_version_id=%s", (I["tv1"],)))
    TV2 = new()
    X("""insert into decision_table_version (id, company_id, decision_table_id, version, hit_policy, inputs, outputs, content_hash, registry_version, drafted_by_kind,
         drafted_by_id, on_behalf_of_id, drafting_window_to, recorded_at) values (%s,%s,%s,2,'unique','[{"code":"x","type":"amount"}]','[{"code":"o"}]',%s,'1','human',%s,%s,'2026-11-15',now())""",
      (TV2, I["co"], I["tab"], H, I["u"], I["u"]))

    def pinned(cx, vid, pins, n):
        cx.execute("""insert into automation_rule_version (id, company_id, automation_rule_id, version, trigger_event_type, actions, decision_table_version_ids, content_hash,
                      registry_version, drafted_by_kind, drafted_by_id, on_behalf_of_id, drafting_window_to, recorded_at)
                      values (%s,%s,%s,%s,'SalesOrderApproved',%s,%s,%s,'1','human',%s,%s,'2026-11-15',now())""", (vid, I["co"], I["rule2"], n, ACT, pins, H, I["u"], I["u"]))
        cx.execute("update automation_rule_version set state='backtested' where id=%s", (vid,))
    D_bad("D30b a rule version may not leave draft pinning a draft table version", "not an assisted or active version", lambda cx: pinned(cx, new(), [TV2], 20))
    D_bad("D30c ... nor an unknown one", "not an assisted or active version", lambda cx: pinned(cx, new(), [new()], 21))
    X("update decision_table_version set state='active', effective_from='2026-11-20' where id=%s", (I["tv1"],))
    PV = new()
    pinned(c, PV, [I["tv1"]], 22)
    X("update automation_rule_version set state='shadow' where id=%s", (PV,))
    X("update automation_rule set shadow_version_id=%s where id=%s", (PV, I["rule2"]))
    D_bad("D30d a pinned table version cannot be retired while a shadow or current rule version pins it (decision_table_version_in_use)", "decision_table_version_in_use",
          lambda cx: cx.execute("update decision_table_version set state='retired' where id=%s", (I["tv1"],)))
    D_bad("D30d2 ... nor demoted to shadow (decision_table_version_in_use)", "decision_table_version_in_use",
          lambda cx: cx.execute("update decision_table_version set state='shadow' where id=%s", (I["tv1"],)))
    D_bad("D30d3 the stored owner scope is a JSON object", "ck_automation_rule_owner_scope", lambda cx: cx.execute("update automation_rule set owner_scope='[]' where id=%s", (I["rule"],)))
    D_good("D30d4 ... holding the effective scope", lambda cx: cx.execute("update automation_rule set owner_scope=%s where id=%s", (json.dumps({"cells": sorted(map(list, S0))}), I["rule"])))
    X("insert into automation_scope_skip (company_id, automation_rule_id, business_date, skipped_count, recorded_at) values (%s,%s,'2026-11-20',3,now())", (I["co"], I["rule"]))
    D_good("D30e the scope skip count rises", lambda cx: cx.execute("update automation_scope_skip set skipped_count=4 where automation_rule_id=%s", (I["rule"],)))
    D_bad("D30f ... and never falls, and is never deleted", "counts only rise", lambda cx: cx.execute("update automation_scope_skip set skipped_count=1 where automation_rule_id=%s", (I["rule"],)))
    # Final simulation review, 2026-11-15: a rule version and the table version it pins, activated together (ADR-0058 rules 20, 24 notes).
    TV3, TV4, PV2 = new(), new(), new()
    for tv, n_ in ((TV3, 3), (TV4, 4)):
        X("""insert into decision_table_version (id, company_id, decision_table_id, version, hit_policy, inputs, outputs, content_hash, registry_version, drafted_by_kind,
             drafted_by_id, on_behalf_of_id, drafting_window_to, recorded_at) values (%s,%s,%s,%s,'unique','[{"code":"x","type":"amount"}]','[{"code":"o"}]',%s,'1','human',%s,%s,'2026-11-15',now())""",
          (tv, I["co"], I["tab"], n_, H, I["u"], I["u"]))
        X("update decision_table_version set state='backtested' where id=%s", (tv,))
    X("update decision_table_version set state='retired' where id=%s", (TV4,))
    D_good("D30g a rule version leaves draft pinning a backtested table version, so its replay can be stored before the table is in force",
           lambda cx: pinned(cx, PV2, [TV3], 23))
    D_bad("D30h ... but not a retired one", "not an assisted or active version", lambda cx: pinned(cx, new(), [TV4], 24))
    D_bad("D30i the rule version does not go active while its pinned table version is only backtested (a rule in force pins only assisted or active versions)",
          "not an assisted or active version", lambda cx: cx.execute("update automation_rule_version set state='active', effective_from='2026-11-22' where id=%s", (PV2,)))
    D_good("D30j it may run in shadow pinning the backtested table version", lambda cx: cx.execute("update automation_rule_version set state='shadow' where id=%s", (PV2,)))
    D_bad("D30l one proposal raising the rule version before its table version is refused, so a half activation never commits", "not an assisted or active version",
          lambda cx: (cx.execute("update automation_rule_version set state='active', effective_from='2026-11-22' where id=%s", (PV2,)),
                      cx.execute("update decision_table_version set state='active', effective_from='2026-11-22' where id=%s", (TV3,))))
    D_good("D30k ... and table first, in one transaction, both come into force (rule 24 note)", lambda cx: (
        cx.execute("update decision_table_version set state='active', effective_from='2026-11-22' where id=%s", (TV3,)),
        cx.execute("update automation_rule_version set state='active', effective_from='2026-11-22' where id=%s", (PV2,))))
    # executions: keys, outcomes, the chain-target index and the depth checks
    EV1, CH = new(), new()
    def uuid_of(s): return _uuid.uuid5(_uuid.NAMESPACE_URL, s)

    def execution(cx, vid=None, event=None, mode="live", outcome="acted", depth=0, chain=None, subject="SO-1043", err=None):
        acted = outcome in ("acted", "partial", "would_act", "skipped")
        cx.execute("""insert into automation_execution (id, company_id, automation_rule_id, automation_rule_version_id, mode, event_id, event_type, business_date, subject_table,
                      subject_id, causation_chain_id, causation_depth, outcome, condition_results, input_hash, action_results, error_code, is_tainted, on_behalf_of_id, recorded_at)
                      values (%s,%s,%s,%s,%s,%s,'SalesOrderApproved','2026-11-20','sales_order',%s,%s,%s,%s,'[]',%s,%s,%s,false,%s,now())""",
                   (new(), I["co"], I["rule"], vid or I["v4"], mode, event or EV1, uuid_of(subject), chain or CH, depth, outcome, H,
                    '[{"kind":"raise_work_item","outcome":"done"}]' if acted else "[]",
                    None if err is False else ("permission_denied" if outcome in ("refused", "failed", "partial") else None), I["u"]))
    execution(c)
    D_bad("D31 one execution per rule version, event and mode (the idempotency key)", "automation_execution_automation_rule_version_id_event_id_mo",
          lambda cx: execution(cx, outcome="skipped_same_target"))
    D_bad("D32 the same rule acts once per chain and subject (ux_automation_execution_chain_target)", "ux_automation_execution_chain_target",
          lambda cx: execution(cx, event=new()))
    D_bad("D33 ... and a partial execution counts as acting there too", "ux_automation_execution_chain_target", lambda cx: execution(cx, event=new(), outcome="partial"))
    D_good("D34 a skipped_same_target record of the same chain is accepted, and so is the same subject in another chain",
           lambda cx: (execution(cx, event=new(), outcome="skipped_same_target"), execution(cx, event=new(), chain=new())))
    D_bad("D35 an execution acts only on an event below depth 3 (its actions run at depth + 1 <= 3)", "ck_automation_execution_acted_depth",
          lambda cx: execution(cx, event=new(), chain=new(), depth=3))
    D_good("D36 ... and records depth_exceeded at depth 3", lambda cx: execution(cx, event=new(), chain=new(), depth=3, outcome="depth_exceeded"))
    D_bad("D37 depth_exceeded only at depth 3", "ck_automation_execution_depth_exceeded", lambda cx: execution(cx, event=new(), chain=new(), depth=0, outcome="depth_exceeded"))
    D_good("D38 a skipped execution (every action skipped by design) carries no error code", lambda cx: execution(cx, event=new(), chain=new(), outcome="skipped"))
    D_bad("D39 a partial execution names its refusal", "ck_automation_execution_error", lambda cx: execution(cx, event=new(), chain=new(), outcome="partial", err=False))
    D_bad("D40 would_act only in shadow", "ck_automation_execution_mode_outcome", lambda cx: execution(cx, event=new(), chain=new(), outcome="would_act"))
    D_bad("D41 execution rows are never updated", "never updated or deleted", lambda cx: cx.execute("update automation_execution set outcome='failed' where event_id=%s", (EV1,)))
    X("insert into event_subject (subject_table, subject_id, last_sequence, recorded_at) values ('sales_order',%s,1,now()) on conflict do nothing", (I["w1"],))

    def outbox(cx, depth, chain=True, rule_version=None):
        cx.execute("""insert into outbox_event (id, company_id, event_type, schema_version, subject_table, subject_id, subject_sequence, payload, actor_kind, actor_id,
                      business_date, command_type, causation_chain_id, causation_depth, automation_rule_version_id, recorded_at)
                      values (%s,%s,'SalesOrderApproved',1,'sales_order',%s,1,'{}','system',%s,'2026-11-20','RaiseAutomationWorkItem',%s,%s,%s,now())""",
                   (new(), I["co"], I["w1"], I["u"], new() if chain else None, depth, rule_version))
    D_good("D42 an event at depth 3 is accepted", lambda cx: outbox(cx, 3, rule_version=I["v4"]))
    D_bad("D43 the database refuses an event at depth 4 (ck_outbox_event_causation_depth)", "ck_outbox_event_causation_depth", lambda cx: outbox(cx, 4))
    D_bad("D44 an event naming a rule version is at depth 1 or more", "ck_outbox_event_automation_depth", lambda cx: outbox(cx, 0, rule_version=I["v4"]))
    D_bad("D45 every event carries a causation chain", "causation_chain_id", lambda cx: outbox(cx, 0, chain=False))
    D_bad("D46 the depth has no default: an event that omits it is refused", "causation_depth", lambda cx: cx.execute(
        """insert into outbox_event (id, company_id, event_type, schema_version, subject_table, subject_id, subject_sequence, payload, actor_kind, actor_id,
           business_date, command_type, causation_chain_id, recorded_at) values (%s,%s,'X',1,'sales_order',%s,1,'{}','system',%s,'2026-11-20','X',%s,now())""",
        (new(), I["co"], I["w1"], I["u"], new())))

    def audit(cx, depth, rule_version):
        cx.execute("""insert into audit_record (id, company_id, business_date, command_type, schema_version, effect_class, is_human_only, is_proposal_bound, is_draft_only,
                      is_internal_only, actor_kind, actor_id, causation_chain_id, causation_depth, automation_rule_version_id, recorded_at)
                      values (%s,%s,'2026-11-20','RaiseAutomationWorkItem',1,'other',false,false,true,true,'system',%s,%s,%s,%s,now())""",
                   (new(), I["co"], I["u"], new(), depth, rule_version))
    D_bad("D47 the database refuses an audit record at depth 4 (ck_audit_record_causation_depth)", "ck_audit_record_causation_depth", lambda cx: audit(cx, 4, I["v4"]))
    D_bad("D48 an audit record naming a rule version is at depth 1 or more", "ck_audit_record_automation_depth", lambda cx: audit(cx, 0, I["v4"]))
    # parameter values: bounds, safety caps and frozen rows
    X("insert into parameter_set (id, company_id, function_code, owner_user_id, recorded_at) values (%s,%s,'cash.match_bank_line',%s,now())", (I["ps"], I["co"], I["u"]))
    X("""insert into parameter_set_version (id, company_id, parameter_set_id, version, function_version, parameters_hash, content_hash, registry_version, drafted_by_kind, drafted_by_id,
         on_behalf_of_id, drafting_window_to, recorded_at) values (%s,%s,%s,1,'1.2.0',%s,%s,'1.0.0','human',%s,%s,'2026-07-31',now())""", (I["pv1"], I["co"], I["ps"], H, H, I["u"], I["u"]))

    def pval(cx, code, value, lo, hi, default, cap=False, vtype="score", nullable=False):
        cx.execute("""insert into parameter_set_value (company_id, parameter_set_version_id, parameter_code, value_type, value, is_nullable, default_value, min_value, max_value,
                      is_safety_cap, recorded_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())""", (I["co"], I["pv1"], code, vtype, value, nullable, default, lo, hi, cap))
    pval(c, "show_min_score", 61, 0, 100, 0)
    D_bad("D49 a value outside its bounds is refused (parameter_out_of_bounds)", "ck_parameter_set_value_in_bounds", lambda cx: pval(cx, "subset_search_size", 9, 1, 8, 6, vtype="integer"))
    D_bad("D50 a safety cap's maximum is its core default, so it can only be lowered", "ck_parameter_set_value_cap",
          lambda cx: pval(cx, "cap_paid_by_third_party", 60, 0, 70, 60, cap=True))
    D_bad("D51 the cap check is null-safe: a safety cap without a default is refused", "ck_parameter_set_value_cap",
          lambda cx: pval(cx, "cap_x", 10, 0, 60, None, cap=True))
    D_bad("D52 a safety cap is never off (not nullable, never null)", "ck_parameter_set_value_cap_set",
          lambda cx: pval(cx, "cap_y", None, 0, 60, 60, cap=True, nullable=True))
    D_bad("D53 a score is whole", "ck_parameter_set_value_whole", lambda cx: pval(cx, "score_account_subset", 66.5, 0, 100, 70))
    X("update parameter_set_version set state='backtested' where id=%s", (I["pv1"],))
    D_bad("D54 parameter values are frozen with their version", "frozen with their version", lambda cx: cx.execute(
        "update parameter_set_value set value=70 where parameter_set_version_id=%s", (I["pv1"],)))
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
