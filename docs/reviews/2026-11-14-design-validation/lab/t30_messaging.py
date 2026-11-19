"""Scenario: internal messaging and notifications (ADR-0076). Not product code.

Run: python t30_messaging.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs).

F: the fan-out (rule 6): one notification per recipient and message, of the strongest kind; nobody for the author, a member
   at none or a person who cannot read now; work items to the owning user, to an approval stage's eligible members up to 20,
   never to a role.
M: mentions (rule 5): at most 20, the <@n> tokens matching the list.
E: the mail run (rule 7): immediate kinds due 5 minutes after creation, digest kinds at the digest hour in the recipient's time
   zone; the re-check at send (active account with an address, active assignment, read access, preference, company switch);
   one grouped e-mail per person and run; events older than an hour never mail.
A: access (rules 1-3): public and private channels, current members only (left_at), direct members, record threads by the
   record's read permission with owner scope.
K, R: direct keys (rule 2) and retention (rule 10): bodies cleared after the 30-day grace of a lowered value.
With --load: the DDL (the shape of each kind, the subject allowlist, the direct key format, unique channel names, one thread per
record, gapless sequences per conversation, replies in the same conversation, cleared bodies, mentions by position, one
notification per recipient and message and one unread per work item, the e-mail outcome, preferences), the retention update
with a young reply, and the catalogs (settings, both leaves, every role template's level).
Not covered: commands, the consumers, the SMTP call, live updates.
"""
import csv, os, re, sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from fx_adr74 import DOCS, RESULTS, build, check, conn, ins, new, reset_and_load, trial  # noqa: E402

STRENGTH = ("mention", "direct_message", "reply", "followed")
DEFAULT_EMAIL = {"mention": "immediate", "direct_message": "immediate", "work_item": "immediate", "reply": "digest", "followed": "digest"}


# ======================================================================= reference functions
def fan_out(kind, msg, members, can_read):
    """members: {user: notify_level} of current members. Returns {user: notification kind}."""
    out = {}
    repliers = set(msg.get("earlier_repliers", ())) | ({msg["parent_author"]} if msg.get("parent_author") else set())
    for u in set(members) | set(msg["mentions"]) | repliers:
        if u == msg["author"] or not can_read(u) or members.get(u) == "none":
            continue
        kinds = []
        if u in msg["mentions"]:
            kinds.append("mention")
        if kind == "direct" and u in members:
            kinds.append("direct_message")
        if u in repliers:
            kinds.append("reply")
        if kind in ("record", "channel") and members.get(u) == "all":
            kinds.append("followed")
        if kinds:
            out[u] = min(kinds, key=STRENGTH.index)
    return out


def work_item_recipients(item, stage_members=()):
    if item["owner_kind"] == "user":
        return [item["owner_user"]]
    if item["owner_kind"] == "approval_stage":
        return sorted(stage_members) if len(stage_members) <= 20 else []
    return []


def mentions_ok(body, mentioned):
    if len(mentioned) > 20:
        return "mention_limit"
    tokens = sorted({int(n) for n in re.findall(r"<@(\d+)>", body)})
    return None if tokens == list(range(1, len(mentioned) + 1)) else "validation_failed"


def due(kind, created, pref, tz, digest_hour):
    mode = pref.get(kind, DEFAULT_EMAIL[kind])
    if mode == "off":
        return None
    if mode == "immediate":
        return created + timedelta(minutes=5)
    local = created.astimezone(ZoneInfo(tz))
    d = local.replace(hour=digest_hour, minute=0, second=0, microsecond=0)
    return (d if d > local else d + timedelta(days=1)).astimezone(timezone.utc)


def mail_run(pending, now, recipients, company_on=True):
    """pending: notifications with recipient, kind, created, read, event_age_minutes. Returns ({recipient: [ids]}, dropped ids)."""
    groups, dropped = {}, []
    for n in pending:
        r = recipients[n["recipient"]]
        if n["read"] or n.get("replay") or n.get("event_age_minutes", 0) > 24 * 60:
            dropped.append(n["id"]); continue
        d = due(n["kind"], n["created"], r["pref"], r["tz"], r["digest_hour"])
        if d is None or not company_on or not (r["active"] and r["email"] and r["assigned"] and r["can_read"](n)):
            dropped.append(n["id"]); continue
        if d <= now:
            groups.setdefault(n["recipient"], []).append(n["id"])
    return groups, dropped


def can_read(user, conv, rows, record_readers=frozenset()):
    """rows: {user: left_at or None}."""
    member = user in rows and rows[user] is None
    if conv["kind"] == "channel":
        return member or (not conv["private"] and user in conv["company_users"])
    if conv["kind"] == "direct":
        return member
    return user in record_readers


def direct_key(users, actor):
    u = sorted(set(users))
    if actor not in u or not 2 <= len(u) <= 8:
        raise ValueError("validation_failed")
    return ",".join(u)


def retention_cutoff(days, set_on, today, previous_days=0):
    """The days in force: a lowered value applies 30 days after it was set."""
    if days == 0:
        return None
    lowered = previous_days == 0 or days < previous_days
    in_force = days if not lowered or today >= set_on + timedelta(days=30) else previous_days
    return None if in_force == 0 else today - timedelta(days=in_force)


# ======================================================================= F
rec_members = {"lan": "all", "minh": "mentions", "hoa": "all", "tuan": "none"}
f1 = fan_out("record", {"author": "lan", "mentions": ["minh"]}, rec_members, lambda u: True)
check("F01 a mention in a record thread notifies the mentioned person (mention) and followers at all (followed); never the author or a follower at none",
      f1 == {"minh": "mention", "hoa": "followed"}, f1)
f2 = fan_out("record", {"author": "lan", "mentions": ["hoa"], "parent_author": "hoa"}, {"hoa": "all"}, lambda u: True)
check("F02 one notification per recipient, the strongest kind: mentioned, replied to and following gives one mention", f2 == {"hoa": "mention"}, f2)
f3 = fan_out("direct", {"author": "lan", "mentions": []}, {"lan": "all", "minh": "mentions", "hoa": "none"}, lambda u: True)
check("F03 a direct message notifies every other member not at none", f3 == {"minh": "direct_message"}, f3)
f4 = fan_out("record", {"author": "lan", "mentions": ["minh"]}, {"hoa": "all"}, lambda u: u not in ("hoa", "minh"))
check("F04 a person who cannot read the record now gets nothing, even as a follower or a mention", f4 == {}, f4)
f5 = fan_out("channel", {"author": "lan", "mentions": [], "parent_author": "minh", "earlier_repliers": ["hoa"]}, {"minh": "mentions", "hoa": "mentions", "tuan": "mentions"}, lambda u: True)
check("F05 a reply notifies the parent's author and earlier repliers; a channel member at mentions gets nothing else", f5 == {"minh": "reply", "hoa": "reply"}, f5)
check("F06 a work item notifies its owning user; an approval stage's eligible members when at most 20, else nobody; a role nobody",
      work_item_recipients({"owner_kind": "user", "owner_user": "lan"}) == ["lan"]
      and work_item_recipients({"owner_kind": "approval_stage"}, {"a", "b", "c"}) == ["a", "b", "c"]
      and work_item_recipients({"owner_kind": "approval_stage"}, {str(i) for i in range(25)}) == []
      and work_item_recipients({"owner_kind": "role"}) == [])

# ======================================================================= M
check("M01 the body's tokens must match the picked mentions; more than 20 is mention_limit",
      mentions_ok("hi <@1> and <@2>", ["a", "b"]) is None and mentions_ok("hi <@1>", ["a", "b"]) == "validation_failed"
      and mentions_ok("hi <@3>", ["a"]) == "validation_failed" and mentions_ok("x", [str(i) for i in range(21)]) == "mention_limit")

# ======================================================================= E
t0 = datetime(2026, 11, 19, 3, 0, tzinfo=timezone.utc)              # 10:00 in Asia/Ho_Chi_Minh
ok_r = {"active": True, "email": "x@example.com", "assigned": True, "can_read": lambda n: True, "pref": {}, "tz": "Asia/Ho_Chi_Minh", "digest_hour": 17}
check("E01 an immediate kind is due 5 minutes after creation; a digest kind at 17:00 local, or the next day after it",
      due("mention", t0, {}, "Asia/Ho_Chi_Minh", 17) == t0 + timedelta(minutes=5)
      and due("followed", t0, {}, "Asia/Ho_Chi_Minh", 17) == datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
      and due("reply", datetime(2026, 11, 19, 11, 0, tzinfo=timezone.utc), {}, "Asia/Ho_Chi_Minh", 17) == datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc))
pend = [{"id": i, "recipient": "minh", "kind": "direct_message", "created": t0, "read": False} for i in range(50)]
g, dr = mail_run(pend, t0 + timedelta(minutes=6), {"minh": ok_r})
check("E02 fifty quick direct messages give one e-mail to the person in the next run", list(g) == ["minh"] and len(g["minh"]) == 50 and dr == [])
g, dr = mail_run([{"id": 1, "recipient": "minh", "kind": "mention", "created": t0, "read": True}], t0 + timedelta(minutes=6), {"minh": ok_r})
check("E03 a notification read before the run is never e-mailed", g == {} and dr == [1])
gone = dict(ok_r, assigned=False)
g, dr = mail_run([{"id": 1, "recipient": "minh", "kind": "followed", "created": t0, "read": False}], datetime(2026, 11, 19, 10, 1, tzinfo=timezone.utc), {"minh": gone})
check("E04 a person whose role assignment ended gets no digest; the notification is dropped (EC-349)", g == {} and dr == [1])
for name, r in (("no address", dict(ok_r, email=None)), ("disabled", dict(ok_r, active=False)), ("lost access", dict(ok_r, can_read=lambda n: False)),
                ("preference off", dict(ok_r, pref={"mention": "off"}))):
    g, dr = mail_run([{"id": 1, "recipient": "minh", "kind": "mention", "created": t0, "read": False}], t0 + timedelta(minutes=6), {"minh": r})
    check(f"E05 re-check at send: {name} drops the notification from e-mail", g == {} and dr == [1])
g, dr = mail_run([{"id": 1, "recipient": "minh", "kind": "mention", "created": t0, "read": False}], t0 + timedelta(minutes=6), {"minh": ok_r}, company_on=False)
check("E06 the company switch off drops pending notifications, so no backlog is sent later", g == {} and dr == [1])
g, dr = mail_run([{"id": 1, "recipient": "minh", "kind": "mention", "created": t0, "read": False, "event_age_minutes": 1500}], t0 + timedelta(minutes=6), {"minh": ok_r})
g2, dr2 = mail_run([{"id": 2, "recipient": "minh", "kind": "mention", "created": t0, "read": False, "replay": True}], t0 + timedelta(minutes=6), {"minh": ok_r})
g3, _ = mail_run([{"id": 3, "recipient": "minh", "kind": "mention", "created": t0, "read": False, "event_age_minutes": 600}], t0 + timedelta(minutes=6), {"minh": ok_r})
check("E07 a notification from a ReplayEvents delivery or an event older than 24 hours is never e-mailed; one 10 hours late still is",
      g == {} and dr == [1] and g2 == {} and dr2 == [2] and g3 == {"minh": [3]})

# ======================================================================= A, K, R
pub = {"kind": "channel", "private": False, "company_users": {"lan", "minh", "hoa"}}
priv = {"kind": "channel", "private": True, "company_users": {"lan", "minh", "hoa"}}
check("A01 a public channel is readable by any company user; a private one by current members only, not by one who left",
      can_read("hoa", pub, {}) and can_read("lan", priv, {"lan": None}) and not can_read("hoa", priv, {"lan": None, "hoa": t0}))
check("A02 a direct conversation by its current members; a record thread only by the record's readers now (owner scope included), following or not",
      can_read("lan", {"kind": "direct"}, {"lan": None}) and not can_read("lan", {"kind": "direct"}, {"lan": t0})
      and can_read("hoa", {"kind": "record"}, {}, {"hoa"}) and not can_read("minh", {"kind": "record"}, {"minh": None}, {"hoa"}))
check("K01 the same people give the same key in any order", direct_key(["b", "a", "c"], "a") == direct_key(["c", "b", "a"], "c") == "a,b,c")
bad = 0
for users, actor in ((["a"], "a"), ([str(i) for i in range(9)], "0"), (["a", "b"], "c")):
    try:
        direct_key(users, actor)
    except ValueError:
        bad += 1
check("K02 2 to 8 members, the actor among them (a third party cannot open the pair's conversation)", bad == 3)
today = date(2026, 11, 19)
check("R01 retention 0 keeps everything; a value lowered from 0 to 365 applies only 30 days after it was set; a raise applies at once",
      retention_cutoff(0, today, today) is None and retention_cutoff(365, today, today) is None
      and retention_cutoff(365, today - timedelta(days=31), today) == today - timedelta(days=365)
      and retention_cutoff(730, today, today, previous_days=365) == today - timedelta(days=730))

# ======================================================================= X: the DDL (--load)
if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("X00 load_all.py loads every DDL file with DS-63-messaging.sql", n_tables > 0, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    I = build(c)
    for k in ("u2", "u3", "u4"):
        I[k] = new()
        X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,%s,'en','x',now())", (I[k], k + I["t"], k))
    NOW = datetime.now(timezone.utc)

    def conv(cx, kind, **o):
        v = dict(id=new(), company_id=I["co"], kind=kind, created_by_user_account_id=I["user"]); v.update(o)
        return ins(cx, "conversation", **v)
    ch = conv(c, "channel", name="sales")
    dk = ",".join(sorted([str(I["user"]), str(I["u2"])]))
    conv(c, "direct", direct_key=dk)
    so = new()
    th = conv(c, "record", subject_table="document", subject_id=so)
    n_conv = X("select count(*) from conversation where company_id=%s", (I["co"],)).fetchone()[0]
    check("X01 a channel, a direct conversation and a record thread are stored", n_conv == 3, n_conv)
    trial("X02 a channel needs a name", lambda cx: conv(cx, "channel"), "ck_conversation_shape")
    trial("X03 a channel name is a lower-case slug", lambda cx: conv(cx, "channel", name="Sales Team"), "ck_conversation_name")
    trial("X04 channel names are unique in the company", lambda cx: conv(cx, "channel", name="sales"), "ux_conversation_channel_name")
    trial("X05 a direct key is 2 to 8 sorted IDs", lambda cx: conv(cx, "direct", direct_key="x,y"), "ck_conversation_direct_key")
    trial("X05b a direct key's IDs are strictly ascending, so unsorted or repeated IDs are refused", lambda cx: conv(cx, "direct", direct_key="ffffffff-ffff-7fff-bfff-ffffffffffff,00000000-0000-7000-8000-000000000000"), "ck_conversation_direct_key_sorted")
    trial("X05c a direct key never repeats a person", lambda cx: conv(cx, "direct", direct_key="00000000-0000-7000-8000-000000000000,00000000-0000-7000-8000-000000000000"), "ck_conversation_direct_key_sorted")
    trial("X06 one direct conversation per member set", lambda cx: conv(cx, "direct", direct_key=dk), "ux_conversation_direct_key")
    trial("X07 one thread per record", lambda cx: conv(cx, "record", subject_table="document", subject_id=so), "ux_conversation_record_subject")
    trial("X08 a record thread's subject is on the allowlist", lambda cx: conv(cx, "record", subject_table="user_account", subject_id=new()), "ck_conversation_subject_table")

    def member(cx, cid, user, **o):
        v = dict(company_id=I["co"], conversation_id=cid, user_account_id=user, joined_at=NOW); v.update(o)
        ins(cx, "conversation_member", **v)
    member(c, th, I["user"]); member(c, th, I["u2"], notify_level="mentions")
    check("X09 a member defaults to notify level all and read sequence 0",
          X("select notify_level, last_read_sequence from conversation_member where conversation_id=%s and user_account_id=%s", (th, I["user"])).fetchone() == ("all", 0))
    trial("X10 a notify level is all, mentions or none", lambda cx: member(cx, ch, I["u3"], notify_level="loud"), "ck_conversation_member_notify_level")

    def msg(cx, cid, seq, **o):
        v = dict(id=new(), company_id=I["co"], conversation_id=cid, sequence=seq, author_user_account_id=I["user"], body="hello"); v.update(o)
        return ins(cx, "message", **v)
    m1 = msg(c, th, 1, body="Can you check the delivery date? <@1>")
    r1 = msg(c, th, 2, parent_message_id=m1, author_user_account_id=I["u2"], body="Yes, Friday.")
    X("update conversation set last_sequence=2 where id=%s", (th,))
    check("X11 a message and its reply carry sequences 1 and 2 of their conversation",
          [r[0] for r in X("select sequence from message where conversation_id=%s order by sequence", (th,)).fetchall()] == [1, 2])
    trial("X12 a sequence is used once per conversation", lambda cx: msg(cx, th, 2), "message_conversation_id_sequence_key")
    trial("X13 a reply belongs to the same conversation", lambda cx: msg(cx, ch, 1, parent_message_id=m1), "message_company_id_conversation_id_parent_message_id_fkey")
    trial("X14 a body is at most 8,000 characters", lambda cx: msg(cx, th, 9, body="x" * 8001), "ck_message_body")
    trial("X15 a withdrawn message has an empty body", lambda cx: msg(cx, th, 9, withdrawn_at=NOW), "ck_message_body_cleared")
    trial("X16 a message has a body unless withdrawn or removed", lambda cx: msg(cx, th, 9, body=""), "ck_message_body_present")
    # retention clears the parent's body while a young reply keeps pointing at it
    X("update message set body='', body_removed_at=now() where id=%s", (m1,))
    kept = X("select count(*) from message where conversation_id=%s", (th,)).fetchone()[0]
    check("X17 retention clears an old parent's body; the young reply and its link stand (no delete blocked by the reply key)", kept == 2, kept)
    gap = X("""select count(*) from conversation c where c.last_sequence <> (select count(*) from message m where m.conversation_id = c.id)
               or exists (select 1 from message m where m.conversation_id = c.id and m.sequence > c.last_sequence)""").fetchone()[0]
    check("X18 INV-881 in SQL: every conversation's messages hold the sequences 1 to its last_sequence", gap == 0, gap)
    ins(c, "message_mention", company_id=I["co"], message_id=r1, position=1, user_account_id=I["u3"])
    trial("X19 a person is mentioned once per message", lambda cx: ins(cx, "message_mention", company_id=I["co"], message_id=r1, position=2, user_account_id=I["u3"]), "message_mention_message_id_user_account_id_key")
    trial("X20 at most 20 mentions per message", lambda cx: ins(cx, "message_mention", company_id=I["co"], message_id=r1, position=21, user_account_id=I["u4"]), "ck_message_mention_position")

    def note(cx, **o):
        v = dict(id=new(), company_id=I["co"], recipient_user_account_id=I["u2"], kind="mention", actor_user_account_id=I["user"], conversation_id=th, message_id=r1)
        v.update(o); return ins(cx, "notification", **v)
    n1 = note(c, email_pending=True)
    trial("X21 one notification per recipient and message", lambda cx: note(cx, kind="followed"), "ux_notification_recipient_message")
    trial("X22 a message notification names its conversation and message", lambda cx: note(cx, recipient_user_account_id=I["u3"], message_id=None), "ck_notification_source")
    trial("X23 a work item notification names its work item", lambda cx: note(cx, kind="work_item", recipient_user_account_id=I["u3"], conversation_id=None, message_id=None), "ck_notification_source")
    trial("X24 the notification's message is of its conversation", lambda cx: note(cx, recipient_user_account_id=I["u3"], conversation_id=ch), "notification_company_id_conversation_id_message_id_fkey")
    em = new()
    ins(c, "notification_email", id=em, company_id=I["co"], recipient_user_account_id=I["u2"], email_kind="immediate")
    X("update notification set email_pending=false, notification_email_id=%s where id=%s", (em, n1))
    trial("X25 a notification is never both pending and carried", lambda cx: cx.execute("update notification set email_pending=true where id=%s", (n1,)), "ck_notification_email")
    trial("X26 an outcome comes with its time, and a failure reason only on failed", lambda cx: cx.execute("update notification_email set outcome='sent' where id=%s", (em,)), "ck_notification_email_outcome_at")
    X("update notification_email set outcome='unknown', outcome_at=now() where id=%s", (em,))
    check("X27 an unknown outcome is final (never resent)", X("select outcome from notification_email where id=%s", (em,)).fetchone()[0] == "unknown")
    trial("X28 an e-mail mode is immediate, digest or off",
          lambda cx: ins(cx, "notification_preference", company_id=I["co"], user_account_id=I["u2"], kind="mention", email_mode="hourly"), "ck_notification_preference_email_mode")

    S = {r["key"]: r for r in csv.DictReader(open(os.path.join(DOCS, "catalogs", "settings.csv"), encoding="utf-8"))}
    want = {"messaging.email_notifications": "true", "messaging.digest_hour": "17", "messaging.message_retention_days": "0"}
    check("X29 the three messaging settings are in the catalog with their defaults, leaf messaging_administration",
          all(S.get(k, {}).get("core_default") == v and S[k]["leaf"] == "messaging_administration" for k, v in want.items())
          and not [k for k in S if k.startswith("messaging.") and k not in want])
    tpl = [r["template"] for r in csv.DictReader(open(os.path.join(DOCS, "catalogs", "role-templates.csv"), encoding="utf-8"))]
    lv = {}
    for r in csv.DictReader(open(os.path.join(DOCS, "catalogs", "role-template-levels.csv"), encoding="utf-8")):
        if r["node"] in ("messaging", "messaging_administration"):
            lv[(r["template"], r["node"])] = r["level"]
    ok_lv = all(lv.get((t, "messaging")) == ("full" if t in ("owner", "it_administrator") else "read" if t == "auditor" else "edit") for t in tpl)
    ok_adm = {t for (t, n) in lv if n == "messaging_administration"} == {"owner", "it_administrator"}
    check("X30 every template holds messaging at edit (the auditor read, the owner and IT administrator full); only those two hold messaging_administration", ok_lv and ok_adm, lv)
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
