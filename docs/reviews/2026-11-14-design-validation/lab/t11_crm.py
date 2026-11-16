"""Scenario: DS-35 minimal CRM (ADR-0052) on the DS-20, DS-35 and DS-06 DDL loaded together.

Run: python t11_crm.py [--load]
  NATIVEFLOWS_LAB_DSN must name a throwaway database; --load drops and rebuilds schemas nativeflows and types there.
  NATIVEFLOWS_DOCS points at the docs/ tree to load (default ~/Projects/NativeFlows/docs); NATIVEFLOWS_LAB_DIR at lab.py and
  load_ds06.py (default: this file's directory).

D: the natural key of inbound messages (ADR-0052 rule 13): provider key per mailbox, one canonical row per
   Message-ID and content hash, copies that must share hashes and interaction and point to a canonical row, reused
   Message-IDs, own messages.
I: interaction checks (rule 6): contacts inside their partner, company keys, directions, matches, tasks, untrusted
   inbound e-mail, lowercase contact e-mail (DS-20). T: the append-only trigger with and without the erasure setting
   (rule 7). C: complaint states (rule 20). P: processing bases (rule 23). K: match candidates (rule 15).
O, V: outbound recipients only from the message's partner, content by hash, delivery attempts (rules 27-28).
F: a model of ADR-0009 rule 14's final-state trigger on the two crm document types and document_version, with
   sending frozen like issuing, and erasure of content rows that never touches header or version (rules 24, 25, 27).
L, E, G: links between rows of one partner (rule 9), e-mail domains, processing log, typed headers.
Y: content rows: deletes only inside the generated Delete of a draft, and the salt blanked only by erasure (rules 7, 24, 27).
Q: the mailbox probe result behind is_authentication_verified (rule 11).
M: company_id and recorded_at coverage, top-to-bottom load order, no personal text on document headers (rule 3).
S: name normalization and trigram search (rule 17).
A, W, B, N (pure functions, no database): the RFC 8601 parser and sender authentication (rule 14), own-message
   recognition (rule 13), the matching cascade with its candidate order (rule 15) also on shuffled inputs, and the
   core fold table (rule 17).
Not covered: commands, consumers, the connector and its probe, the timeline query and erasure across modules.
"""
import hashlib, os, random, re, subprocess, sys, tempfile, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import conn, new, RESULTS  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("NATIVEFLOWS_DOCS", "~/Projects/NativeFlows/docs"))
DESIGN = os.path.join(DOCS, "design")
STUBS = os.path.join(DOCS, "reviews/2026-11-14-design-validation/lab/00_stubs.sql")
# Lab-only stub additions: the shared document row's columns of ADR-0052 rule 18, pg_trgm (ADR-0022 rule 8), and
# document_version (ADR-0009 rule 9), which the documents module owns.
EXTRA_STUBS = """SET search_path = nativeflows;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
ALTER TABLE document ADD COLUMN partner_id uuid, ADD COLUMN document_date date, ADD CONSTRAINT uq_document_company_id_id UNIQUE (company_id, id);
CREATE TABLE document_version (id uuid PRIMARY KEY, company_id uuid NOT NULL, document_id uuid NOT NULL REFERENCES document (id),
  version integer NOT NULL, content jsonb NOT NULL, recorded_at timestamptz NOT NULL, UNIQUE (document_id, version));
"""
# Lab model of ADR-0009 rule 14 (owned by documents; DS-36 builds the real one): header and line rows of a document in
# a final state, or in a frozen non-final state (issuing, ADR-0028 rule 6; sending, ADR-0052 rule 27), never change;
# a document row in a final state never changes except posted -> reversed; versions are never updated or deleted.
# Content tables only refuse new rows once frozen; their erasure is the append-only trigger's business (rule 7).
FINAL_STATE_MODEL = """SET search_path = nativeflows;
CREATE FUNCTION lab_document_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_ids uuid[]; v_state text;
BEGIN
    v_ids := ARRAY[]::uuid[];
    IF TG_OP <> 'INSERT' THEN v_ids := v_ids || (to_jsonb(OLD) ->> TG_ARGV[0])::uuid; END IF;
    IF TG_OP <> 'DELETE' THEN v_ids := v_ids || (to_jsonb(NEW) ->> TG_ARGV[0])::uuid; END IF;
    FOR v_state IN SELECT state FROM document WHERE id = ANY (v_ids) LOOP
        IF v_state IN ('posted', 'reversed', 'canceled', 'closed', 'issuing', 'sending') THEN
            RAISE EXCEPTION '% of a document in state % is immutable (ADR-0009 rule 14)', TG_TABLE_NAME, v_state USING ERRCODE = 'check_violation';
        END IF;
    END LOOP;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE FUNCTION lab_document_row_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state IN ('posted', 'reversed', 'canceled', 'closed') THEN
        IF TG_OP = 'UPDATE' AND OLD.state = 'posted' AND NEW.state = 'reversed'
           AND (to_jsonb(OLD) - 'state') = (to_jsonb(NEW) - 'state') THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'document in state % is immutable (ADR-0009 rule 14)', OLD.state USING ERRCODE = 'check_violation';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE FUNCTION lab_never_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% rows are never updated or deleted (ADR-0009 rule 14)', TG_TABLE_NAME USING ERRCODE = 'check_violation';
END $$;
CREATE TRIGGER lab_document_row_frozen BEFORE UPDATE OR DELETE ON document FOR EACH ROW EXECUTE FUNCTION lab_document_row_frozen();
CREATE TRIGGER lab_document_version_never BEFORE UPDATE OR DELETE ON document_version FOR EACH ROW EXECUTE FUNCTION lab_never_change();
CREATE TRIGGER lab_frozen BEFORE INSERT OR UPDATE OR DELETE ON outbound_message FOR EACH ROW EXECUTE FUNCTION lab_document_frozen('id');
CREATE TRIGGER lab_frozen BEFORE INSERT OR UPDATE OR DELETE ON outbound_message_recipient FOR EACH ROW EXECUTE FUNCTION lab_document_frozen('outbound_message_id');
CREATE TRIGGER lab_frozen BEFORE INSERT OR UPDATE OR DELETE ON data_subject_request FOR EACH ROW EXECUTE FUNCTION lab_document_frozen('id');
CREATE TRIGGER lab_frozen BEFORE INSERT ON outbound_message_content FOR EACH ROW EXECUTE FUNCTION lab_document_frozen('outbound_message_id');
CREATE TRIGGER lab_frozen BEFORE INSERT ON data_subject_request_content FOR EACH ROW EXECUTE FUNCTION lab_document_frozen('data_subject_request_id');
"""


def check(name, got, want):
    ok = got == want
    RESULTS.append((ok, name, str(got)))
    print(("PASS " if ok else "FAIL ") + f"{name} -- {got}")


# ======================================================================= A: RFC 8601 parser and sender authentication
class ParseError(Exception):
    pass


TSPECIALS = set('()<>@,;:\\"/[]?=')


def tokenize(s):
    """RFC 8601 / RFC 2045 lexer: tokens, quoted strings and specials; comments and whitespace (CFWS) are dropped.
    Unterminated quotes or comments raise ParseError (fail closed)."""
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch in " \t\r\n":
            i += 1
        elif ch == "(":
            depth, i = 1, i + 1
            while i < n and depth:
                if s[i] == "\\":
                    i += 2; continue
                depth += {"(": 1, ")": -1}.get(s[i], 0); i += 1
            if depth:
                raise ParseError("unterminated comment")
        elif ch == ")":
            raise ParseError("unbalanced comment")
        elif ch == '"':
            buf, i = [], i + 1
            while i < n and s[i] != '"':
                if s[i] == "\\" and i + 1 < n:
                    i += 1
                buf.append(s[i]); i += 1
            if i >= n:
                raise ParseError("unterminated quoted string")
            out.append(("qs", "".join(buf))); i += 1
        elif ch in TSPECIALS:
            out.append(("sp", ch)); i += 1
        elif ord(ch) < 32 or ord(ch) == 127:
            raise ParseError("control character")
        else:
            j = i
            while j < n and s[j] not in TSPECIALS and s[j] not in " \t\r\n" and ord(s[j]) >= 32:
                j += 1
            out.append(("tok", s[i:j])); i = j
    return out


def parse_authres(field):
    """authserv-id [version] (; none | 1*resinfo); resinfo = ; method[/version] = result [reason = value] *propspec.
    Returns (authserv_id, [(method, result, {ptype.property: value})])."""
    t = tokenize(field)
    pos = [0]
    def peek(k=0):
        return t[pos[0] + k] if pos[0] + k < len(t) else (None, None)
    def take(kind=None, val=None):
        tk = peek()
        if tk[0] is None or (kind and tk[0] != kind) or (val is not None and tk[1] != val):
            raise ParseError(f"expected {kind or ''} {val or ''} at {pos[0]}")
        pos[0] += 1
        return tk
    def value():
        tk = peek()
        if tk[0] in ("tok", "qs"):
            pos[0] += 1; return tk[1]
        raise ParseError("value expected")
    authserv = value()
    if peek()[0] == "tok" and peek()[1].isdigit():
        take("tok")
    results = []
    if peek() == (None, None):
        raise ParseError("no result")
    while peek()[0] is not None:
        take("sp", ";")
        method = take("tok")[1].lower()
        if peek() == ("sp", "/"):
            take("sp", "/"); take("tok")
        if method == "none" and peek()[0] is None and not results:
            return authserv, []
        take("sp", "=")
        result = take("tok")[1].lower()
        props = {}
        while peek()[0] == "tok":
            name = take("tok")[1].lower()
            if name == "reason":
                take("sp", "="); value(); continue
            if "." not in name:
                if peek() == ("tok", ".") or (peek()[0] == "tok" and peek()[1].startswith(".")):
                    name += take("tok")[1].lower()
                    if name.endswith("."):
                        name += take("tok")[1].lower()
                else:
                    raise ParseError("ptype.property expected")
            take("sp", "=")
            local = None
            if peek()[0] in ("tok", "qs") and peek(1) == ("sp", "@"):
                local = value()
            if peek() == ("sp", "@"):
                take("sp", "@"); dom = take("tok")[1]
                v = f"{local}@{dom}" if local is not None else f"@{dom}"
            else:
                v = value() if local is None else local
            props[name] = v
        results.append((method, result, props))
    return authserv, results


def from_addresses(from_fields):
    """The mailboxes of the RFC 5322 From fields (minimal: display names, quotes, comments, angle brackets, groups)."""
    addrs = []
    for f in from_fields:
        parts, buf, q, a, c = [], "", False, False, 0
        for ch in f:
            if c:
                c += {"(": 1, ")": -1}.get(ch, 0); continue
            if ch == '"':
                q = not q
            elif not q and ch == "(":
                c = 1; continue
            elif not q and ch == "<":
                a = True
            elif not q and ch == ">":
                a = False
            if ch == "," and not q and not a:
                parts.append(buf); buf = ""
            else:
                buf += ch
        parts.append(buf)
        for p in parts:
            p = p.strip()
            if not p or p.endswith(":;") or p.endswith(";"):
                continue
            m = re.search(r"<([^<>]*)>\s*$", p)
            spec = (m.group(1) if m else p).strip()
            if re.fullmatch(r"[^@\s]+@[^@\s]+", spec):
                addrs.append(spec.lower())
    return addrs if len(from_fields) == 1 else addrs + [None]


def authenticate(fields, authserv_id, from_fields, verified=True):
    """Rule 14. fields: Authentication-Results values, top first. Returns (passed, reason)."""
    if not verified:
        return False, "mailbox_not_verified"
    senders = from_addresses(from_fields)
    if len(senders) != 1 or senders[0] is None:
        return False, "from_not_single"
    from_domain = senders[0].split("@", 1)[1]
    ours = None
    for f in fields:
        try:
            first = tokenize(f)
            sid = first[0][1] if first and first[0][0] in ("tok", "qs") else None
        except ParseError:
            sid = None
        if sid is None:
            return False, "results_unparsable"
        if sid.lower() == authserv_id.lower():
            try:
                ours = parse_authres(f)
            except ParseError:
                return False, "results_unparsable"
            break
    if ours is None:
        return False, "no_trusted_results"
    dmarc = {(r, p.get("header.from", "").lower()) for m, r, p in ours[1] if m == "dmarc"}
    if len({r for r, _ in dmarc}) > 1:
        return False, "dmarc_conflict"
    if dmarc:
        r, hfrom = next(iter(dmarc))
        if r == "pass":
            if hfrom == from_domain:
                return True, "dmarc_pass"
            if hfrom:
                return False, "dmarc_header_from_mismatch"
        elif r != "none":
            return False, f"dmarc_{r}"
    if any(m == "dkim" and r == "pass" and p.get("header.d", "").lower() == from_domain for m, r, p in ours[1]):
        return True, "dkim_aligned"
    return False, "not_aligned"


AS = "mx.company.example"
def ar(*methods, server=AS):
    return f"{server}; " + "; ".join(methods)
FROM = ["Lan <lan@acme.example>"]
def auth(fields, from_fields=FROM, verified=True):
    return authenticate(fields, AS, from_fields, verified)[0]

check("A01 DMARC pass passes", auth([ar("spf=fail", "dkim=fail header.d=x.example", "dmarc=pass header.from=acme.example")]), True)
check("A02 DMARC fail fails, even with an aligned DKIM pass", auth([ar("dkim=pass header.d=acme.example", "dmarc=fail header.from=acme.example")]), False)
check("A03 DMARC none (no policy) and DKIM aligned exactly passes", auth([ar("spf=none", "dkim=pass header.d=acme.example", "dmarc=none header.from=acme.example")]), True)
check("A04 strict alignment: DKIM of the parent domain does not pass a subdomain", auth([ar("dkim=pass header.d=acme.example", "dmarc=none")], ["a@mail.acme.example"]), False)
check("A05 SPF pass alone never passes", auth([ar("spf=pass smtp.mailfrom=acme.example", "dmarc=none")]), False)
check("A06 results of another server are ignored", auth([ar("dmarc=pass header.from=acme.example", server="relay.other.example")]), False)
check("A07 the topmost field of our server wins over a lower one", auth([ar("dmarc=fail header.from=acme.example"), ar("dmarc=pass header.from=acme.example")]), False)
check("A08 no Authentication-Results field fails", auth([]), False)
check('A09 a quoted string is one value: smtp.mailfrom="a; dmarc=pass"@x carries no DMARC result',
      auth([ar('spf=pass smtp.mailfrom="a; dmarc=pass"@x')]), False)
check("A10 a comment holding dmarc=pass is not a result", auth([ar("spf=pass (dmarc=pass header.from=acme.example) smtp.mailfrom=acme.example")]), False)
check("A11 DMARC temperror fails closed, even with aligned DKIM", auth([ar("dkim=pass header.d=acme.example", "dmarc=temperror")]), False)
check("A12 DMARC permerror fails closed", auth([ar("dkim=pass header.d=acme.example", "dmarc=permerror")]), False)
check("A13 DMARC absent falls through to aligned DKIM", auth([ar("spf=pass smtp.mailfrom=acme.example", "dkim=pass (good) header.d=acme.example")]), True)
check("A14 two From addresses are not authenticated", auth([ar("dmarc=pass header.from=acme.example")], ["lan@acme.example, boss@acme.example"]), False)
check("A15 a From with no address (empty group) is not authenticated", auth([ar("dmarc=pass header.from=acme.example")], ["undisclosed:;"]), False)
check("A16 an unterminated quoted string in our field fails closed", auth([ar('dmarc=pass header.from="acme.example')]), False)
check("A17 an unreadable field above ours fails closed", auth(['"mx.company.example; dmarc=pass', ar("dmarc=pass header.from=acme.example")]), False)
check("A18 DMARC pass for another From domain fails", auth([ar("dmarc=pass header.from=other.example")]), False)
check("A19 a mailbox whose probe has not passed authenticates nothing", auth([ar("dmarc=pass header.from=acme.example")], verified=False), False)
check("A20 a quoted display name with a comma is one From address", auth([ar("dmarc=pass header.from=acme.example")], ['"Lan, Sales" <lan@acme.example>']), True)
check("A21 two From fields are not authenticated", auth([ar("dmarc=pass header.from=acme.example")], FROM + FROM), False)


# ======================================================================= W: own messages (rule 13)
MAILBOXES = {"in@company.example", "sales@company.example"}
def is_own(msg, sent):
    """sent: {message_id_hash: sent_content_hash}. Own only when authenticated From is a company mailbox, or the
    content hash equals the sent one; otherwise a reused Message-ID."""
    if msg["mid"] not in sent:
        return False
    return (msg["auth"] and msg["from"] in MAILBOXES) or msg["hash"] == sent[msg["mid"]]
SENT = {"h-q12": "c-q12"}
check("W01 our Message-ID from an authenticated company mailbox is own", is_own({"mid": "h-q12", "auth": True, "from": "sales@company.example", "hash": "c-x"}, SENT), True)
check("W02 a company mailbox address without authentication is not own", is_own({"mid": "h-q12", "auth": False, "from": "sales@company.example", "hash": "c-x"}, SENT), False)
check("W03 the same content hash as sent is own, whoever forwarded it", is_own({"mid": "h-q12", "auth": False, "from": "x@else.example", "hash": "c-q12"}, SENT), True)
check("W04 an outside sender reusing our Message-ID is a reused Message-ID", is_own({"mid": "h-q12", "auth": True, "from": "x@else.example", "hash": "c-x"}, SENT), False)


# ======================================================================= B: matching (rule 15)
REASONS = ["several_partners", "contact_email_unauthenticated", "domain_unauthenticated", "tax_id_in_content", "name_similarity"]


def match(msg, d):
    """Rule 15. msg: auth, sender, domain, refs (hashes), tax_ids. d: partners {id: (code, active, superseded_by, tax_id)},
    contacts [(id, partner, email, active)], domains [(partner, domain, active)], outbound {hash: (partner, recipients)},
    public (set). Returns (partner, contact, method, candidates): one candidate per partner with its best reason,
    ordered by reason as listed, score descending, partner code; at most ten."""
    def live(p):
        seen = set()
        while p is not None and d["partners"][p][2] and p not in seen:
            seen.add(p); p = d["partners"][p][2]
        return p if p is not None and d["partners"][p][1] else None

    def contacts_of(p, email):
        return sorted(c for c, cp, e, a in d["contacts"] if a and e == email and cp == p)   # a contact stays with its own partner

    sender, domain = msg["sender"], msg["domain"]
    s1 = set()
    for h in msg["refs"]:
        if h in d["outbound"]:
            op, recips = d["outbound"][h]
            p = live(op)
            if p and (sender in recips or contacts_of(p, sender)):
                s1.add(p)
    s2 = {live(cp) for c, cp, e, a in d["contacts"] if a and e == sender} - {None}
    s3 = set() if domain in d["public"] else {live(p) for p, dom, a in d["domains"] if a and dom == domain} - {None}   # public at match time
    cands = set()
    if msg["auth"]:
        for method, found in (("reply", s1), ("contact_email", s2), ("domain", s3)):
            if len(found) == 1:
                p = next(iter(found))
                cs = contacts_of(p, sender) if method != "domain" else []
                return p, (cs[0] if len(cs) == 1 else None), method, []
            if found:
                cands |= {(p, "several_partners", None) for p in found}
                break
    else:
        cands |= {(p, "contact_email_unauthenticated", None) for p in s2}
        cands |= {(p, "domain_unauthenticated", None) for p in s3}
    by_tax = {}
    for p, (code, active, sup, tax) in d["partners"].items():
        if tax and live(p) == p:
            by_tax.setdefault(tax, set()).add(p)
    for t in msg.get("tax_ids", ()):
        cands |= {(p, "tax_id_in_content", None) for p in by_tax.get(t, ())}
    key = lambda c: (REASONS.index(c[1]), -(c[2] or 0), d["partners"][c[0]][0])
    best = {}
    for c in sorted(cands, key=key):
        best.setdefault(c[0], c)
    ordered = sorted(best.values(), key=key)[:10]
    return None, None, None, [(p, r) for p, r, s in ordered]


D = {
    "partners": {"P1": ("C001", True, None, "0101"), "P2": ("C002", True, None, "0202"), "P3": ("C003", True, None, None),
                 "OLD": ("C000", False, "P3", None), "G1": ("C010", True, None, "0303"), "G2": ("C011", True, None, None)},
    "contacts": [("c1", "P1", "lan@acme.example", True), ("c2", "P2", "shared@both.example", True), ("c3", "P3", "shared@both.example", True),
                 ("c4", "OLD", "minh@old.example", True), ("c5", "P1", "gone@acme.example", False), ("c6", "P2", "user@gmail.com", True)],
    "domains": [("P1", "acme.example", True), ("G1", "group.example", True), ("G2", "group.example", True), ("P2", "beta.example", False),
                ("P3", "freemail.example", True)],
    "outbound": {"h-q12": ("P1", {"buyer@acme.example"})},
    "public": {"gmail.com", "freemail.example"},   # gmail.com is kept on purpose: the rule under test is about a real public mail domain
}
def m(sender, auth=True, refs=(), tax_ids=()):
    return {"auth": auth, "sender": sender, "domain": sender.split("@")[1], "refs": set(refs), "tax_ids": set(tax_ids)}
CASES = [
    ("B01 a reply from a recipient of our message matches its partner", m("buyer@acme.example", refs=["h-q12"]), ("P1", None, "reply", [])),
    ("B02 a reply from an unknown address of another domain falls through to unmatched", m("x@nowhere.example", refs=["h-q12"]), (None, None, None, [])),
    ("B03 an authenticated contact address matches partner and contact", m("lan@acme.example"), ("P1", "c1", "contact_email", [])),
    ("B04 a contact address at two partners stays unmatched", m("shared@both.example"), (None, None, None, [("P2", "several_partners"), ("P3", "several_partners")])),
    ("B05 a partner domain matches the partner without a contact", m("new.person@acme.example"), ("P1", None, "domain", [])),
    ("B06 a public mail domain never matches by domain", m("someone@gmail.com"), (None, None, None, [])),
    ("B07 a contact at a public domain still matches by address", m("user@gmail.com"), ("P2", "c6", "contact_email", [])),
    ("B08 an unauthenticated sender gives one candidate per partner, with its best reason", m("lan@acme.example", auth=False), (None, None, None, [("P1", "contact_email_unauthenticated")])),
    ("B09 a superseded partner's contact matches the successor", m("minh@old.example"), ("P3", None, "contact_email", [])),
    ("B10 a domain on two partners stays unmatched", m("a@group.example"), (None, None, None, [("G1", "several_partners"), ("G2", "several_partners")])),
    ("B11 a tax ID in the body gives a candidate, never a match", m("x@nowhere.example", tax_ids=["0202"]), (None, None, None, [("P2", "tax_id_in_content")])),
    ("B12 an inactive domain does not match", m("gone@beta.example"), (None, None, None, [])),
    ("B13 an inactive contact is not used; the domain still matches", m("gone@acme.example"), ("P1", None, "domain", [])),
    ("B14 a domain listed as public after its row was made is skipped at match time", m("x@freemail.example"), (None, None, None, [])),
    ("B15 candidates order by reason, then partner code; a partner under two reasons counts once",
     m("a@group.example", tax_ids=["0303", "0101"]), (None, None, None, [("G1", "several_partners"), ("G2", "several_partners"), ("P1", "tax_id_in_content")])),
]
for name, msg, want in CASES:
    check(name, match(msg, D), want)
rng = random.Random(35)
stable = True
for _ in range(200):
    D2 = dict(D, contacts=rng.sample(D["contacts"], len(D["contacts"])), domains=rng.sample(D["domains"], len(D["domains"])),
              partners=dict(rng.sample(list(D["partners"].items()), len(D["partners"]))))
    stable &= all(match(msg, D2) == want for _, msg, want in CASES)
check("B16 200 shuffles of contacts, domains and partners give the same results", stable, True)


# ======================================================================= N: name normalization (rule 17)
CORE_FOLD = {"đ": "d", "ð": "d", "ł": "l", "ø": "o", "ß": "ss", "æ": "ae", "œ": "oe", "þ": "th", "ı": "i", "ħ": "h"}


def normalize_name(name, stop_words=(), fold_pairs=None):
    """Rule 17: lowercase, NFKD with marks removed, the core fold table plus package pairs, punctuation to spaces,
    spaces collapsed, stop words removed."""
    folds = dict(CORE_FOLD, **(fold_pairs or {}))
    s = "".join(ch for ch in unicodedata.normalize("NFKD", name.lower()) if not unicodedata.combining(ch))
    s = "".join(folds.get(ch, ch) for ch in s)
    s = " ".join(re.sub(r"[\W_]+", " ", s).split())
    padded = f" {s} "
    for w in sorted(stop_words, key=len, reverse=True):
        while f" {w} " in padded:
            padded = padded.replace(f" {w} ", " ")
    return " ".join(padded.split())


STOP = ["cong ty", "tnhh", "co phan", "cp"]     # sample package stop words (l10n_vn's are package data, unverified)
check("N01 a Vietnamese name normalizes without marks and with the package's stop words", normalize_name("Công ty TNHH Thương mại Đơn Mẫu Một", STOP), "thuong mai don mau mot")
check("N02 case, punctuation and spacing do not matter, and stop words go", normalize_name("  ĐƠN-MẪU,  Co. Phan  ", STOP), "don mau")
check("N03 the core fold table is language-neutral", normalize_name("Łódź Øresund STRASSE Straße Æther Œuvre Þór Ðorđe"), "lodz oresund strasse strasse aether oeuvre thor dorde")
check("N04 a package fold pair adds to the core table", normalize_name("Ŧest", fold_pairs={"ŧ": "t"}), "test")

# ======================================================================= load
def load():
    with tempfile.TemporaryDirectory() as tmp:
        combined = os.path.join(tmp, "combined.sql")
        with open(combined, "w", encoding="utf-8") as out:
            for f in ("DS-20-master-data.sql", "DS-35-crm.sql", "DS-06-universal-journal.sql"):
                out.write(open(os.path.join(DESIGN, f), encoding="utf-8").read() + "\n")
        ordered = subprocess.run([sys.executable, os.path.join(LAB, "load_ds06.py"), combined], check=True, capture_output=True, text=True)
        print(ordered.stderr.strip().replace("\n", " | ")[:300])
        cx = conn(); cx.autocommit = True
        cx.execute(open(STUBS, encoding="utf-8").read())
        cx.execute(EXTRA_STUBS)
        cx.execute("SET search_path = nativeflows;\n" + ordered.stdout)
        cx.execute(FINAL_STATE_MODEL)
        cx.close()

if "--load" in sys.argv:
    load()

# ======================================================================= fixture
c = conn(); c.autocommit = True
X = c.execute
I = {k: new() for k in ["user", "co", "co2", "p1", "p2", "pind", "pc2", "c1", "c1b", "c2", "cc2", "mb", "mb2", "mbc2",
                        "i1", "m1", "d1", "dc2", "pur", "pur2", "ev", "s_a", "s_b", "s_c", "s_d", "out_i"]}
t = str(I["co"])[-8:]
H = lambda s: (s * 64)[:64]
HX = lambda s: hashlib.sha256(s.encode()).hexdigest()
SALT = "0123456789abcdef0123456789abcdef"
X("insert into currency (code, minor_unit) values ('VND', 0) on conflict do nothing")
X("insert into user_account values (%s)", (I["user"],))
for k, code in (("co", "C11-"), ("co2", "C11B-")):
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,legal_form,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','VND','Asia/Ho_Chi_Minh','l10n_vn','tt99','joint_stock','warehouse',%s,'vi')", (I[k], code + t, I["user"]))
for k, co, kind in (("p1", "co", "organization"), ("p2", "co", "organization"), ("pind", "co", "individual"), ("pc2", "co2", "organization"),
                    ("s_a", "co", "organization"), ("s_b", "co", "organization"), ("s_c", "co", "organization"), ("s_d", "co", "organization")):
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,%s,'P',%s,'VN')", (I[k], I[co], k + t, kind))
for k, co, p, email in (("c1", "co", "p1", "lan@acme.example"), ("c1b", "co", "p1", "hoa@acme.example"), ("c2", "co", "p2", "an@beta.example"), ("cc2", "co2", "pc2", "x@c2.example")):
    X("insert into contact (id, company_id, partner_id, name, email) values (%s,%s,%s,'N',%s)", (I[k], I[co], I[p], email))
for k, co, code in (("mb", "co", "IN"), ("mb2", "co", "SALES"), ("mbc2", "co2", "IN")):
    X("insert into mailbox (id, company_id, code, name, email_address, connector_kind, connector_settings, credential_ref, authserv_id, owner_user_id, recorded_at)"
      " values (%s,%s,%s,'M',%s,'imap','{}','secret/x','mx.company.example',%s,now())", (I[k], I[co], code, code.lower() + "@company.example", I["user"]))
def interaction(cx, iid=None, **o):
    v = dict(id=iid or new(), company_id=I["co"], kind="email", direction="inbound", occurred_at="2026-11-15T03:00:00Z", is_untrusted=True)
    v.update(o)
    cols = list(v) + ["recorded_at"]
    cx.execute(f"insert into interaction ({', '.join(cols)}) values ({', '.join(['%s'] * len(v))}, now())", list(v.values()))
    return v["id"]
def inbound(cx, **o):
    v = dict(id=new(), company_id=I["co"], mailbox_id=I["mb"], provider_message_key=str(new()), message_id_hash=H("a"), content_hash=H("b"),
             sender_authentication="{}", is_sender_authenticated=True, received_at="2026-11-15T03:00:00Z", interaction_id=I["i1"])
    v.update(o)
    cols = list(v) + ["recorded_at"]
    cx.execute(f"insert into inbound_message ({', '.join(cols)}) values ({', '.join(['%s'] * len(v))}, now())", list(v.values()))
    return v["id"]
interaction(c, I["i1"], subject="Need a price")
X("insert into interaction_content (interaction_id, company_id, body_text, recorded_at) values (%s,%s,'Hello',now())", (I["i1"], I["co"]))
inbound(c, id=I["m1"], provider_message_key="1:100", sender_address="lan@acme.example")
interaction(c, I["ev"], kind="note", direction="internal", is_untrusted=False, partner_id=I["pind"], match_method="entered", matched_at="2026-11-15T03:00:00Z")
interaction(c, I["out_i"], kind="email", direction="outbound", is_untrusted=False, partner_id=I["p1"], match_method="entered", matched_at="2026-11-15T03:00:00Z")
for k, co, p in (("d1", "co", "p1"), ("dc2", "co2", "pc2")):
    X("insert into document (id, company_id, document_type, partner_id) values (%s,%s,'quotation',%s)", (I[k], I[co], I[p]))
X("insert into processing_purpose (id, company_id, code, name, is_consent_required, message_types, basis, recorded_at) values (%s,%s,'marketing','M',true,'{marketing}','{\"source\": \"core_template\"}',now())", (I["pur"], I["co"]))

def trial(name, fn, should_fail, match_text=None):
    class Rollback(Exception):
        pass
    cx = conn()
    try:
        with cx.transaction():
            fn(cx); cx.execute("set constraints all immediate"); raise Rollback()
    except Rollback:
        ok, detail = not should_fail, "succeeded (rolled back)"
    except Exception as e:
        msg = str(e).splitlines()[0]
        ok, detail = should_fail and (match_text is None or match_text in msg), "failed: " + msg
    finally:
        cx.close()
    RESULTS.append((ok, name, detail)); print(("PASS " if ok else "FAIL ") + name + " -- " + detail)

def erasing(cx):
    cx.execute("select set_config('nativeflows.erasure_command_id', 'lab', true)")

# ---- D: inbound messages and the natural key
trial("D01 a second fetch of one provider key in one mailbox is refused", lambda cx: inbound(cx, provider_message_key="1:100", content_hash=H("c")), True, "duplicate key")
trial("D02 the same provider key in another mailbox is accepted", lambda cx: inbound(cx, mailbox_id=I["mb2"], provider_message_key="1:100", content_hash=H("c"), interaction_id=interaction(cx)), False)
trial("D03 the same message as a second canonical row is refused", lambda cx: inbound(cx, mailbox_id=I["mb2"], interaction_id=interaction(cx)), True, "ux_inbound_message_natural_key")
trial("D04 a copy in a second mailbox pointing to the first, same interaction, is accepted", lambda cx: inbound(cx, mailbox_id=I["mb2"], duplicate_of_inbound_message_id=I["m1"]), False)
trial("D05 a copy with another interaction is refused", lambda cx: inbound(cx, mailbox_id=I["mb2"], duplicate_of_inbound_message_id=I["m1"], interaction_id=interaction(cx)), True, "fk_inbound_message_duplicate")
trial("D06 a copy with another content hash is refused", lambda cx: inbound(cx, mailbox_id=I["mb2"], duplicate_of_inbound_message_id=I["m1"], content_hash=H("d")), True, "fk_inbound_message_duplicate")
trial("D07 a reused Message-ID with other content is kept as its own row", lambda cx: inbound(cx, content_hash=H("e"), interaction_id=interaction(cx)), False)
trial("D08 a copy needs a Message-ID hash", lambda cx: inbound(cx, mailbox_id=I["mb2"], duplicate_of_inbound_message_id=I["m1"], message_id_hash=None), True, "ck_inbound_message_duplicate_has_message_id")
trial("D09 an own message with the same hashes is outside the natural key", lambda cx: inbound(cx, mailbox_id=I["mb2"], is_own_message=True, interaction_id=interaction(cx, kind="email", direction="outbound", is_untrusted=False)), False)
trial("D10 a message cannot use another company's mailbox", lambda cx: inbound(cx, mailbox_id=I["mbc2"], content_hash=H("f")), True, "foreign key")
def copy_of_copy(cx):
    mb3 = new()
    cx.execute("insert into mailbox (id, company_id, code, name, email_address, connector_kind, connector_settings, credential_ref, authserv_id, owner_user_id, recorded_at)"
               " values (%s,%s,'THIRD','M','third@company.example','imap','{}','secret/x','mx.company.example',%s,now())", (mb3, I["co"], I["user"]))
    first_copy = inbound(cx, mailbox_id=I["mb2"], duplicate_of_inbound_message_id=I["m1"])
    inbound(cx, mailbox_id=mb3, duplicate_of_inbound_message_id=first_copy)
trial("D11 a copy pointing to another copy is refused: copies target the canonical row", copy_of_copy, True, "fk_inbound_message_duplicate")
def copy_of_own(cx):
    own = inbound(cx, mailbox_id=I["mb2"], is_own_message=True, content_hash=H("9"), interaction_id=I["out_i"])
    inbound(cx, mailbox_id=I["mb"], duplicate_of_inbound_message_id=own, content_hash=H("9"), interaction_id=I["out_i"])
trial("D12 a copy pointing to an own message is refused", copy_of_own, True, "fk_inbound_message_duplicate")
trial("D13 erasure blanks the sender authentication results; nothing else may", lambda cx: cx.execute(
    "update inbound_message set sender_authentication='{\"erased\": true}' where id=%s", (I["m1"],)), True, "inbound_message.sender_authentication is append-only")

# ---- I: interactions
trial("I01 a contact of another partner is refused", lambda cx: interaction(cx, partner_id=I["p2"], contact_id=I["c1"], match_method="contact_email", matched_at="2026-11-15T03:00:00Z"), True, "fk_interaction_contact")
trial("I02 a partner of another company is refused", lambda cx: interaction(cx, partner_id=I["pc2"], match_method="domain", matched_at="2026-11-15T03:00:00Z"), True, "foreign key")
trial("I03 a contact needs its partner", lambda cx: interaction(cx, contact_id=I["c1"]), True, "ck_interaction_contact_partner")
trial("I04 an inbound e-mail is always untrusted", lambda cx: interaction(cx, is_untrusted=False), True, "ck_interaction_inbound_email_untrusted")
trial("I05 an automatic match method only fits an inbound e-mail", lambda cx: interaction(cx, kind="call", partner_id=I["p1"], match_method="domain", matched_at="2026-11-15T03:00:00Z"), True, "ck_interaction_automatic_match")
trial("I06 a note is internal", lambda cx: interaction(cx, kind="note", direction="outbound", is_untrusted=False), True, "ck_interaction_direction")
trial("I07 an e-mail is never internal", lambda cx: interaction(cx, direction="internal"), True, "ck_interaction_direction")
trial("I08 a task needs a due date and an assignee", lambda cx: interaction(cx, kind="task", direction="internal", is_untrusted=False, due_date="2026-11-20"), True, "ck_interaction_task")
trial("I09 only a task has a due date", lambda cx: interaction(cx, kind="call", direction="outbound", is_untrusted=False, due_date="2026-11-20"), True, "ck_interaction_task")
trial("I10 a partner needs a match method and time", lambda cx: interaction(cx, partner_id=I["p1"]), True, "ck_interaction_matched")
trial("I11 a valid follow-up task is accepted", lambda cx: interaction(cx, kind="task", direction="internal", is_untrusted=False, due_date="2026-11-20", assignee_user_id=I["user"],
                                                                  partner_id=I["p1"], match_method="entered", matched_at="2026-11-15T03:00:00Z"), False)
trial("I12 a contact e-mail is stored lowercase (DS-20)", lambda cx: cx.execute(
    "insert into contact (id, company_id, partner_id, name, email) values (%s,%s,%s,'N','Lan@Acme.example')", (new(), I["co"], I["p1"])), True, "ck_contact_email_lower")

# ---- T: append-only trigger
trial("T01 matching an unmatched interaction is allowed", lambda cx: cx.execute(
    "update interaction set partner_id=%s, contact_id=%s, match_method='confirmed', matched_at=now(), version=version+1, recorded_at=now() where id=%s", (I["p1"], I["c1"], I["i1"])), False)
trial("T02 the kind of an interaction never changes", lambda cx: cx.execute("update interaction set kind='call', direction='outbound' where id=%s", (I["i1"],)), True, "is append-only")
trial("T03 the subject changes only under erasure", lambda cx: cx.execute("update interaction set subject='edited' where id=%s", (I["i1"],)), True, "interaction.subject is append-only")
trial("T04 interactions are never deleted", lambda cx: cx.execute("delete from interaction where id=%s", (I["ev"],)), True, "interaction rows are never deleted")
trial("T05 erasure blanks the subject", lambda cx: (erasing(cx), cx.execute("update interaction set subject=null, erased_at=now() where id=%s", (I["i1"],))), False)
trial("T06 content is not edited outside erasure", lambda cx: cx.execute("update interaction_content set body_text='x' where interaction_id=%s", (I["i1"],)), True, "interaction_content.body_text is append-only")
trial("T07 erasure blanks the content", lambda cx: (erasing(cx), cx.execute("update interaction_content set body_text=null, erased_at=now() where interaction_id=%s", (I["i1"],))), False)
trial("T08 the sender address of an inbound message changes only under erasure", lambda cx: cx.execute("update inbound_message set sender_address=null where id=%s", (I["m1"],)), True, "inbound_message.sender_address is append-only")
def participant_twice(cx, second):
    pid = new()
    cx.execute("insert into interaction_participant (id, company_id, interaction_id, role, email_address, recorded_at) values (%s,%s,%s,'from','lan@acme.example',now())", (pid, I["co"], I["i1"]))
    cx.execute("update interaction_participant set contact_id=%s where id=%s", (I["c1"], pid))
    if second:
        cx.execute("update interaction_participant set contact_id=%s where id=%s", (I["c1b"], pid))
trial("T09 a participant's contact is set once", lambda cx: participant_twice(cx, False), False)
trial("T10 a participant's contact is not changed after", lambda cx: participant_twice(cx, True), True, "interaction_participant.contact_id is append-only")
trial("T11 erasure blanks an inbound message's raw fields, generated columns untouched", lambda cx: (erasing(cx), cx.execute(
    "update inbound_message set message_id=null, sender_address=null, sender_display_name=null, sender_domain=null, sender_authentication='{\"erased\": true}', parse_notes='[]', erased_at=now() where id=%s", (I["m1"],))), False)

# ---- C: complaints
def complaint(cx, **o):
    v = dict(id=new(), company_id=I["co"], partner_id=I["p1"], category="delivery", title="Late delivery", opened_at="2026-11-15T03:00:00Z")
    v.update(o)
    cols = list(v) + ["recorded_at"]
    cx.execute(f"insert into complaint ({', '.join(cols)}) values ({', '.join(['%s'] * len(v))}, now())", list(v.values()))
    return v["id"]
trial("C01 a closed complaint needs closed_at", lambda cx: complaint(cx, state="closed"), True, "ck_complaint_closed")
trial("C02 an open complaint has no closed_at", lambda cx: complaint(cx, closed_at="2026-11-16T03:00:00Z"), True, "ck_complaint_closed")
trial("C03 only open and closed are states", lambda cx: complaint(cx, state="resolved"), True, "ck_complaint_state")
trial("C04 a complaint's contact belongs to its partner", lambda cx: complaint(cx, contact_id=I["c2"]), True, "fk_complaint_contact")
trial("C05 a title is empty only after erasure", lambda cx: complaint(cx, title=None), True, "ck_complaint_title")
def close_reopen(cx):
    k = complaint(cx, contact_id=I["c1"])
    cx.execute("update complaint set state='closed', closed_at='2026-11-16T03:00:00Z', version=2 where id=%s", (k,))
    cx.execute("update complaint set state='open', closed_at=null, version=3 where id=%s", (k,))
trial("C06 close and reopen are accepted", close_reopen, False)
trial("C07 closing before opening is refused", lambda cx: complaint(cx, state="closed", closed_at="2026-11-14T03:00:00Z"), True, "ck_complaint_closed_after_opened")
trial("C08 a complaint's linked document row carries the complaint's partner", lambda cx: cx.execute(
    "insert into complaint_document (company_id, complaint_id, partner_id, document_id, recorded_at) values (%s,%s,%s,%s,now())", (I["co"], complaint(cx), I["p2"], I["d1"])), True, "fk_complaint_document_complaint")

# ---- P: processing bases
def basis(cx, **o):
    v = dict(id=new(), company_id=I["co"], contact_id=I["c1"], processing_purpose_id=I["pur"], lawful_basis="consent", started_at="2026-11-15T03:00:00Z", evidence_interaction_id=I["ev"])
    v.update(o)
    cols = list(v) + ["recorded_at"]
    cx.execute(f"insert into processing_basis ({', '.join(cols)}) values ({', '.join(['%s'] * len(v))}, now())", list(v.values()))
    return v["id"]
trial("P01 consent needs its evidence", lambda cx: basis(cx, evidence_interaction_id=None), True, "ck_processing_basis_consent_evidence")
trial("P02 a basis has one subject, not two", lambda cx: basis(cx, partner_id=I["pind"]), True, "ck_processing_basis_subject")
trial("P03 a basis has a subject", lambda cx: basis(cx, contact_id=None), True, "ck_processing_basis_subject")
trial("P04 one current consent per subject and purpose", lambda cx: (basis(cx), basis(cx)), True, "ux_processing_basis_current")
def withdraw_then_new(cx):
    b = basis(cx)
    cx.execute("update processing_basis set ended_at='2026-11-16T03:00:00Z', end_reason='withdrawn' where id=%s", (b,))
    basis(cx)
trial("P05 after a withdrawal a new consent is accepted", withdraw_then_new, False)
def end_twice(cx):
    b = basis(cx)
    cx.execute("update processing_basis set ended_at='2026-11-16T03:00:00Z', end_reason='withdrawn' where id=%s", (b,))
    cx.execute("update processing_basis set ended_at=null, end_reason=null where id=%s", (b,))
trial("P06 an ended basis never reopens", end_twice, True, "is append-only")
trial("P07 an end needs its reason", lambda cx: basis(cx, ended_at="2026-11-16T03:00:00Z"), True, "ck_processing_basis_end")
trial("P08 bases are never deleted", lambda cx: cx.execute("delete from processing_basis where id=%s", (basis(cx),)), True, "never deleted")
trial("P09 one current basis per partner subject too", lambda cx: (basis(cx, contact_id=None, partner_id=I["pind"]), basis(cx, contact_id=None, partner_id=I["pind"])), True, "ux_processing_basis_current")
trial("P10 the purpose's message types are a closed list", lambda cx: cx.execute(
    "insert into processing_purpose (id, company_id, code, name, is_consent_required, message_types, basis, recorded_at) values (%s,%s,'x','X',true,'{newsletter}','{}',now())", (new(), I["co"])), True, "ck_processing_purpose_message_types")

# ---- K: match candidates
def candidate(cx, p, reason, rank):
    cx.execute("insert into interaction_match_candidate (company_id, interaction_id, partner_id, reason, rank, recorded_at) values (%s,%s,%s,%s,%s,now())", (I["co"], I["i1"], I[p], reason, rank))
trial("K01 two candidates cannot share a rank", lambda cx: (candidate(cx, "p1", "several_partners", 1), candidate(cx, "p2", "several_partners", 1)), True, "duplicate key")
trial("K02 a partner is a candidate once per interaction, with its best reason", lambda cx: (candidate(cx, "p1", "contact_email_unauthenticated", 1), candidate(cx, "p1", "domain_unauthenticated", 2)), True, "duplicate key")
trial("K03 distinct partners and ranks are accepted", lambda cx: (candidate(cx, "p1", "several_partners", 1), candidate(cx, "p2", "several_partners", 2)), False)

# ---- O, V: outbound messages, content and delivery
def outbound(cx, partner="p1", mid="m", state="draft", subject="Your quotation", body="Dear customer"):
    oid = new()
    ch = HX("content:" + mid)
    cx.execute("insert into document (id, company_id, document_type, partner_id) values (%s,%s,'outbound_message',%s)", (oid, I["co"], I[partner]))
    cx.execute("insert into outbound_message_content (company_id, outbound_message_id, content_hash, content_salt, subject, body_text, recorded_at) values (%s,%s,%s,%s,%s,%s,now())", (I["co"], oid, ch, SALT, subject, body))
    cx.execute("insert into outbound_message (id, company_id, mailbox_id, partner_id, message_type, content_hash, message_id, message_id_hash, recorded_at)"
               " values (%s,%s,%s,%s,'reply',%s,%s,%s,now())", (oid, I["co"], I["mb"], I[partner], ch, f"<{oid}@company.example>", HX(mid)))
    cx.execute("insert into document_version (id, company_id, document_id, version, content, recorded_at) values (%s,%s,%s,1,%s,now())",
               (new(), I["co"], oid, '{"content_hash": "%s", "message_type": "reply"}' % ch))
    if state != "draft":
        cx.execute("update document set state=%s where id=%s", (state, oid))
    return oid
def recipient(cx, oid, partner, contact):
    cx.execute("insert into outbound_message_recipient (company_id, outbound_message_id, partner_id, contact_id, role, recorded_at) values (%s,%s,%s,%s,'to',now())", (I["co"], oid, I[partner], I[contact]))
def attempt(cx, oid, n=1, **o):
    v = dict(id=new(), company_id=I["co"], outbound_message_id=oid, attempt_number=n, requested_at="2026-11-15T04:00:00Z")
    v.update(o)
    cols = list(v) + ["recorded_at"]
    cx.execute(f"insert into outbound_message_delivery ({', '.join(cols)}) values ({', '.join(['%s'] * len(v))}, now())", list(v.values()))
    return v["id"]
SENT_OK = dict(outcome="sent", outcome_at="2026-11-15T04:01:00Z", sent_at="2026-11-15T04:01:00Z", sent_content_hash=H("5"))
trial("O01 a recipient must be a contact of the message's partner", lambda cx: recipient(cx, outbound(cx, mid="1"), "p1", "c2"), True, "fk_outbound_message_recipient_contact")
trial("O02 a recipient row cannot claim another partner than the message's", lambda cx: recipient(cx, outbound(cx, mid="2"), "p2", "c2"), True, "fk_outbound_message_recipient_message")
def change_partner(cx):
    oid = outbound(cx, mid="3"); recipient(cx, oid, "p1", "c1")
    cx.execute("update outbound_message set partner_id=%s where id=%s", (I["p2"], oid))
trial("O03 the partner cannot change while recipients exist", change_partner, True, "fk_outbound_message_recipient_message")
def header_without_content(cx):
    oid = new()
    cx.execute("insert into document (id, company_id, document_type, partner_id) values (%s,%s,'outbound_message',%s)", (oid, I["co"], I["p1"]))
    cx.execute("insert into outbound_message (id, company_id, mailbox_id, partner_id, message_type, content_hash, message_id, message_id_hash, recorded_at)"
               " values (%s,%s,%s,%s,'reply',%s,'<x@company.example>',%s,now())", (oid, I["co"], I["mb"], I["p1"], H("4"), H("4")))
trial("O04 a header refers to its content row by hash", header_without_content, True, "fk_outbound_message_content")
trial("O05 one Message-ID per company", lambda cx: (outbound(cx, mid="5"), outbound(cx, mid="5")), True, "message_id_hash")
trial("O06 a valid message with a recipient is accepted", lambda cx: recipient(cx, outbound(cx, mid="6"), "p1", "c1"), False)
trial("V01 one attempt in flight per message", lambda cx: (lambda o: (attempt(cx, o, 1), attempt(cx, o, 2)))(outbound(cx, mid="7")), True, "ux_outbound_message_delivery_open")
trial("V02 a sent attempt needs sent_at, the sent content hash and the interaction", lambda cx: attempt(cx, outbound(cx, mid="8"), outcome="sent", outcome_at="2026-11-15T04:01:00Z"), True, "ck_outbound_message_delivery_sent")
def outcome_twice(cx):
    a = attempt(cx, outbound(cx, mid="9"))
    cx.execute("update outbound_message_delivery set outcome='failed', outcome_at=now(), failure_reason='550 mailbox unknown' where id=%s", (a,))
    cx.execute("update outbound_message_delivery set outcome='sent', sent_at=now(), sent_content_hash=%s, interaction_id=%s where id=%s", (H("5"), I["out_i"], a))
trial("V03 an outcome is set once", outcome_twice, True, "outbound_message_delivery.outcome is append-only")
def fail_then_send(cx):
    o = outbound(cx, mid="a")
    attempt(cx, o, 1, outcome="failed", outcome_at="2026-11-15T04:01:00Z", failure_reason="550 mailbox unknown")
    attempt(cx, o, 2, interaction_id=I["out_i"], **SENT_OK)
trial("V04 a failed attempt then a sent one is accepted", fail_then_send, False)
trial("V05 at most one sent attempt per message", lambda cx: (lambda o: (attempt(cx, o, 1, interaction_id=I["out_i"], **SENT_OK), attempt(cx, o, 2, interaction_id=I["out_i"], **SENT_OK)))(outbound(cx, mid="b")), True, "ux_outbound_message_delivery_sent")
def blank_reason(cx, erase):
    a = attempt(cx, outbound(cx, mid="c"), outcome="failed", outcome_at="2026-11-15T04:01:00Z", failure_reason="550 lan@acme.example unknown")
    if erase:
        erasing(cx)
    cx.execute("update outbound_message_delivery set failure_reason=null, erased_at=now() where id=%s", (a,))
trial("V06 a failure reason is not blanked outside erasure", lambda cx: blank_reason(cx, False), True, "is append-only")
trial("V07 erasure blanks a failure reason", lambda cx: blank_reason(cx, True), False)
def delivery_recipient_address(cx, erase):
    a = attempt(cx, outbound(cx, mid="d"))
    cx.execute("insert into outbound_message_delivery_recipient (company_id, outbound_message_delivery_id, contact_id, role, email_address, recorded_at) values (%s,%s,%s,'to','lan@acme.example',now())", (I["co"], a, I["c1"]))
    if erase:
        erasing(cx)
    cx.execute("update outbound_message_delivery_recipient set email_address=null, erased_at=now() where outbound_message_delivery_id=%s", (a,))
trial("V08 a delivery recipient's address changes only under erasure", lambda cx: delivery_recipient_address(cx, False), True, "is append-only")
trial("V09 erasure blanks a delivery recipient's address", lambda cx: delivery_recipient_address(cx, True), False)

# ---- F: final-state model (ADR-0009 rule 14; ADR-0028 rule 6; ADR-0052 rules 24, 25, 27)
trial("F01 a closed message's header never changes", lambda cx: cx.execute("update outbound_message set message_type='general' where id=%s", (outbound(cx, mid="e", state="closed"),)), True, "immutable")
trial("F02 the header is frozen in sending, like issuing", lambda cx: cx.execute("update outbound_message set message_type='general' where id=%s", (outbound(cx, mid="f", state="sending"),)), True, "immutable")
trial("F03 no recipient is added in sending", lambda cx: recipient(cx, outbound(cx, mid="g", state="sending"), "p1", "c1"), True, "immutable")
trial("F04 a closed document row never changes", lambda cx: cx.execute("update document set state='draft' where id=%s", (outbound(cx, mid="h", state="closed"),)), True, "immutable")
trial("F05 document versions are never updated", lambda cx: cx.execute("update document_version set content='{}' where document_id=%s", (outbound(cx, mid="i"),)), True, "never updated")
def erase_closed(cx):
    oid = outbound(cx, mid="j", state="closed")
    before = cx.execute("select h.*, v.content from outbound_message h join document_version v on v.document_id=h.id where h.id=%s", (oid,)).fetchone()
    erasing(cx)
    cx.execute("update outbound_message_content set subject=null, body_text=null, content_salt=null, erased_at=now() where outbound_message_id=%s", (oid,))
    after = cx.execute("select h.*, v.content from outbound_message h join document_version v on v.document_id=h.id where h.id=%s", (oid,)).fetchone()
    left = cx.execute("select count(*) from outbound_message_content where erased_at is not null and (subject is not null or body_text is not null or content_salt is not null)").fetchone()[0]
    if before != after or left:
        raise RuntimeError("header or version changed, or erased content not blank (INV-504)")
trial("F06 erasure blanks a closed message's content row and salt; header and version stay (INV-504)", erase_closed, False)
trial("F07 the content of a closed message changes only under erasure", lambda cx: cx.execute(
    "update outbound_message_content set body_text='edited' where outbound_message_id=%s", (outbound(cx, mid="k", state="closed"),)), True, "is append-only")
trial("F08 no new content row for a closed message", lambda cx: cx.execute(
    "insert into outbound_message_content (company_id, outbound_message_id, content_hash, subject, body_text, recorded_at) values (%s,%s,%s,'s','b',now())",
    (I["co"], outbound(cx, mid="l", state="closed"), H("7"))), True, "immutable")

def dsr(cx, state="draft", proof=None):
    rid, ch = new(), H("8")
    cx.execute("insert into document (id, company_id, document_type) values (%s,%s,'data_subject_request')", (rid, I["co"]))
    cx.execute("insert into data_subject_request_content (company_id, data_subject_request_id, content_hash, content_salt, requester_name, requester_email, identity_proof_hash, recorded_at)"
               " values (%s,%s,%s,%s,'Lan','lan@acme.example',%s,now())", (I["co"], rid, ch, SALT, proof))
    cx.execute("insert into data_subject_request (id, company_id, request_kind, contact_id, due_date, content_hash, recorded_at) values (%s,%s,'deletion',%s,'2026-12-15',%s,now())", (rid, I["co"], I["c1"], ch))
    if state != "draft":
        cx.execute("update document set state=%s where id=%s", (state, rid))
    return rid
trial("F09 a closed data subject request's header never changes", lambda cx: cx.execute("update data_subject_request set due_date='2026-12-31' where id=%s", (dsr(cx, "closed"),)), True, "immutable")
def close_blank(cx, touch_proof):
    rid = dsr(cx, "closed", proof=H("6"))
    erasing(cx)
    extra = ", identity_proof_hash=null" if touch_proof else ""
    cx.execute(f"update data_subject_request_content set requester_name=null, requester_email=null, content_salt=null, erased_at=now(){extra} where data_subject_request_id=%s", (rid,))
trial("F10 erasure blanks a closed request's requester data", lambda cx: close_blank(cx, False), False)
trial("F11 the identity-proof hash survives erasure", lambda cx: close_blank(cx, True), True, "data_subject_request_content.identity_proof_hash is append-only")
trial("F12 a header refers to its request content by hash", lambda cx: cx.execute(
    "insert into data_subject_request (id, company_id, request_kind, due_date, content_hash, recorded_at) values (%s,%s,'access','2026-12-15',%s,now())", (I["d1"], I["co"], H("1"))), True, "fk_data_subject_request_content")

# ---- Y: content rows: draft deletes and the salt (rules 7, 24, 27)
def deleting(cx, doc):
    cx.execute("select set_config('nativeflows.document_delete_id', %s, true)", (str(doc),))
def draft_delete(cx, state="draft", setting="own"):
    oid = outbound(cx, mid="y" + state + setting, state=state)
    if setting == "own":
        deleting(cx, oid)
    elif setting == "other":
        deleting(cx, I["d1"])
    cx.execute("delete from outbound_message where id=%s", (oid,))
    cx.execute("delete from outbound_message_content where outbound_message_id=%s", (oid,))
    if cx.execute("select count(*) from outbound_message_content where outbound_message_id=%s", (oid,)).fetchone()[0]:
        raise RuntimeError("content row left")
trial("Y01 the generated Delete of a draft removes its content rows", lambda cx: draft_delete(cx), False)
trial("Y02 content rows are never deleted outside a Delete", lambda cx: draft_delete(cx, setting="none"), True, "never deleted")
trial("Y03 the Delete setting does not reach a submitted message", lambda cx: draft_delete(cx, state="approved"), True, "never deleted")
trial("Y04 a Delete of another document does not reach this one", lambda cx: draft_delete(cx, setting="other"), True, "never deleted")
def dsr_delete(cx):
    rid = dsr(cx)
    deleting(cx, rid)
    cx.execute("delete from data_subject_request where id=%s", (rid,))
    cx.execute("delete from data_subject_request_content where data_subject_request_id=%s", (rid,))
trial("Y05 the Delete of a draft request removes its content row", dsr_delete, False)
trial("Y06 a content row has its salt until erasure", lambda cx: cx.execute(
    "insert into outbound_message_content (company_id, outbound_message_id, content_hash, subject, recorded_at) values (%s,%s,%s,'s',now())", (I["co"], I["d1"], H("3"))), True, "ck_outbound_message_content_salt_kept")
trial("Y07 the salt changes only under erasure", lambda cx: cx.execute(
    "update outbound_message_content set content_salt=null, erased_at=now() where outbound_message_id=%s", (outbound(cx, mid="y7"),)), True, "is append-only")

# ---- Q: the mailbox probe (rule 11)
def verify(cx, result):
    cx.execute("update mailbox set is_authentication_verified=true, authentication_checked_at=now(), authentication_probe_result=%s where id=%s", (result, I["mb"]))
trial("Q01 a mailbox is verified only after a passed probe", lambda cx: verify(cx, "probe_no_field"), True, "ck_mailbox_verified")
trial("Q02 a transport error keeps the last verified state", lambda cx: (verify(cx, "passed"), verify(cx, "transport_error")), False)
# ---- L, E, G: links, domains, log, headers
def link(cx, **o):
    v = dict(id=new(), company_id=I["co"], interaction_id=I["ev"], partner_id=I["pind"])
    v.update(o)
    cols = list(v) + ["recorded_at"]
    cx.execute(f"insert into interaction_link ({', '.join(cols)}) values ({', '.join(['%s'] * len(v))}, now())", list(v.values()))
trial("L01 a link has exactly one target", lambda cx: link(cx, document_id=I["d1"], complaint_id=complaint(cx, partner_id=I["pind"])), True, "ck_interaction_link_target")
trial("L02 a link cannot reach another company's document", lambda cx: link(cx, document_id=I["dc2"]), True, "foreign key")
trial("L03 one link per target", lambda cx: (link(cx, document_id=I["d1"]), link(cx, document_id=I["d1"])), True, "duplicate key")
trial("L04 a link needs a matched interaction", lambda cx: link(cx, interaction_id=I["i1"], partner_id=I["p1"], document_id=I["d1"]), True, "fk_interaction_link_interaction")
trial("L05 a link to another partner's complaint is refused", lambda cx: link(cx, complaint_id=complaint(cx)), True, "fk_interaction_link_complaint")
def unmatch_linked(cx):
    link(cx, complaint_id=complaint(cx, partner_id=I["pind"]))
    cx.execute("update interaction set partner_id=null, contact_id=null, match_method=null, matched_at=null, version=version+1 where id=%s", (I["ev"],))
trial("L06 unmatching an interaction with a link is refused until the link is removed", unmatch_linked, True, "interaction_link")
trial("L07 a link to the same partner's complaint is accepted", lambda cx: link(cx, complaint_id=complaint(cx, partner_id=I["pind"])), False)
def domain(cx, p, dom, **o):
    v = dict(id=new(), company_id=I["co"], partner_id=I[p], domain=dom)
    v.update(o)
    cols = list(v) + ["recorded_at"]
    cx.execute(f"insert into partner_email_domain ({', '.join(cols)}) values ({', '.join(['%s'] * len(v))}, now())", list(v.values()))
trial("E01 a domain is stored in lowercase", lambda cx: domain(cx, "p1", "Acme.Example"), True, "ck_partner_email_domain_domain")
trial("E02 a domain once per partner", lambda cx: (domain(cx, "p1", "acme.example"), domain(cx, "p1", "acme.example")), True, "duplicate key")
trial("E03 one domain on two partners is accepted (email_domain_shared)", lambda cx: (domain(cx, "p1", "group.example"), domain(cx, "p2", "group.example")), False)
trial("E04 a package row of the public list names its package", lambda cx: cx.execute("insert into public_mail_domain (domain, source, recorded_at) values ('mail.example', 'package', now())"), True, "ck_public_mail_domain_package")
trial("E05 an empty domain needs erasure", lambda cx: domain(cx, "pind", None), True, "ck_partner_email_domain_erased")
trial("E06 an erased personal domain is empty and inactive", lambda cx: domain(cx, "pind", None, is_active=False, erased_at="2026-11-15T05:00:00Z"), False)
trial("G01 a log subject has table and ID together", lambda cx: cx.execute(
    "insert into personal_data_processing_log (id, company_id, processing_kind, subject_id, recorded_at) values (%s,%s,'llm_send',%s,now())", (new(), I["co"], new())), True, "ck_personal_data_processing_log_subject")
trial("G02 a typed header belongs to its document's company", lambda cx: cx.execute(
    "insert into data_subject_request (id, company_id, request_kind, due_date, content_hash, recorded_at) values (%s,%s,'access','2026-12-15',%s,now())", (I["dc2"], I["co"], H("8"))), True, "foreign key")
def log_update(cx):
    lid = new()
    cx.execute("insert into personal_data_processing_log (id, company_id, processing_kind, recorded_at) values (%s,%s,'export',now())", (lid, I["co"]))
    cx.execute("update personal_data_processing_log set recipient='x' where id=%s", (lid,))
trial("G03 processing log rows are never updated", log_update, True, "never updated or deleted")

# ---- M: coverage and load order
ddl = open(os.path.join(DESIGN, "DS-35-crm.sql"), encoding="utf-8").read()
tables = re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", ddl, re.S)
missing = [n for n, body in tables if n != "public_mail_domain" and not re.search(r"^\s+company_id\s+uuid NOT NULL", body, re.M)]
check(f"M01 all {len(tables) - 1} company tables of DS-35 carry company_id (missing: {missing or 'none'})", missing, [])
live = {r[0] for r in X("select tablename from pg_tables where schemaname='nativeflows'").fetchall()}
check("M02 every DS-35 table exists in the loaded schema", sorted(n for n, _ in tables if n not in live), [])
names = [n for n, _ in tables]
late = [(n, r) for i, (n, body) in enumerate(tables) for r in re.findall(r"REFERENCES (\w+)", body) if r in names and names.index(r) > i]
check("M03 DS-35 loads top to bottom: no table references a later one", late, [])
no_rec = [n for n, body in tables if not re.search(r"^\s+recorded_at\s+timestamptz NOT NULL", body, re.M)]
check("M04 every DS-35 table carries recorded_at", no_rec, [])
TEXT = {"subject", "body_text", "requester_name", "requester_email", "requester_phone", "outcome_note", "email_address"}
header_text = sorted(r[0] + "." + r[1] for r in X("select table_name, column_name from information_schema.columns where table_schema='nativeflows' and table_name in "
                                                  "('outbound_message', 'outbound_message_recipient', 'data_subject_request')").fetchall() if r[1] in TEXT)
check("M05 the two document headers and their lines hold no personal text", header_text, [])

# ---- S: normalized names and trigram search
for k, raw in (("s_a", "Công ty TNHH Mẫu Một"), ("s_b", "Công ty CP Mẫu Một Trading"), ("s_c", "Ví Dụ Ba"), ("s_d", "Mẫu Mười")):
    X("insert into partner_search_key (partner_id, company_id, normalized_name, recorded_at) values (%s,%s,%s,now())", (I[k], I["co"], normalize_name(raw, STOP)))
def search(q, threshold=0.6):
    rows = X("select k.partner_id from partner_search_key k join partner p on p.id=k.partner_id where k.company_id=%s and similarity(k.normalized_name, %s) >= %s"
             " order by similarity(k.normalized_name, %s) desc, p.code limit 10", (I["co"], q, threshold, q)).fetchall()
    return [r[0] for r in rows]
q = normalize_name("CÔNG TY TNHH MẪU MỘT", STOP)
check("S01 a differently written name finds the same partner first", search(q)[:1], [I["s_a"]])
check("S02 an unrelated name is not a candidate", I["s_c"] in search(q), False)
check("S03 the trigram index exists", X("select count(*) from pg_indexes where indexname='ix_partner_search_key_normalized_name'").fetchone()[0], 1)
check("S04 DS-20's contact phone index exists for the duplicate search", X("select count(*) from pg_indexes where indexname='ix_contact_company_id_phone'").fetchone()[0], 1)
c.close()

print(sum(1 for r in RESULTS if r[0]), "/", len(RESULTS), "passed")
