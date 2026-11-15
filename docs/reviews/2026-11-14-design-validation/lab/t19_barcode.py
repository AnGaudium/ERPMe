"""Scenario: barcodes (ADR-0061), as pure functions and on the DDL drafts.

Run: python t19_barcode.py [--load]
  The pure checks (part P) always run. With --load, ERPME_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas erpme and types there and loads every DDL file of design/, and the database checks (part D) run.
  ERPME_DOCS points at the docs/ tree (default ~/Projects/ERPMe/docs); ERPME_LAB_DIR at lab.py and load_all.py
  (default: this file's directory). Part D needs ADR-0056's unit columns (uom.name, the product_uom rows, the line unit
  block).

P: the rules of ADR-0061 as lab functions: GS1 check digits (GTIN-8, 12, 13, 14, SSCC; the worked examples with the
   fictional company prefix 8931234); the transport (suffix, GS substitute in element strings only, symbology
   identifiers, unlisted identifiers, control characters); element strings with and without FNC1/GS, predefined against
   variable length, AIs that are fixed but not predefined; validation reasons (format, length, check digit, date,
   required and forbidden pairs, repeated AIs, the lost-separator trace and its exceptions); dates with the century
   window and day 00; 310n decimals and units; GS1 Digital Link from the rightmost key; normalization and the internal
   code format; the registry's cross-type and padded-digits uniqueness, retirement and return to the owner, the SSCC
   reuse period and reserved document prefixes; legacy codes (kept as they are, read before the guarded rules and as an
   EAN-13 or UPC-A fallback, legacy_code_gtin_like); the resolution order and every typed issue, numeric lots without
   an identifier, (01)(10)(21) as one serial; scan-to-confirm; serial capture; GS1 capture conflicts; measures never
   rounded; the lot label rule; GTIN-14 generation; the whole-number check of barcoded document formats.
   The AI table here is a hand-written lab subset; the product generates it from the GS1 Barcode Syntax Dictionary.
D: with --load, on all DDL: the registry, its functions and triggers; the database refusing a code across types (a bin
   code equal to an item barcode), a value not normalized, a wrong check digit, an SSCC on a bin, a numeric code not
   marked legacy, a legacy code equal to a GTIN or to another legacy code on padded digits, also from two connections
   at once, a change of is_legacy_barcode or is_barcoded, and a second generation prefix; lot and serial codes kept as
   they come; a removed barcode reserved, released and revived for its own item or bin; an item barcode moved to
   another item; lot, serial, handling unit and barcoded document barcodes registered; a receipt scan creating the lot
   with its expiry and receiving one carton as 24 pieces, and variable measures in kilograms and grams, with ADR-0056's
   unit block; INV-620.
Not covered: commands, the dispatcher, RLS policies, the PWA, label rendering.
"""
import calendar
import csv
import datetime as dt
import os
import re
import sys
import uuid
from decimal import Decimal as D_
from fractions import Fraction as F
from urllib.parse import parse_qsl, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("ERPME_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from lab import RESULTS, conn, expect, new  # noqa: E402

DOCS = os.path.expanduser(os.environ.get("ERPME_DOCS", "~/Projects/ERPMe/docs"))
CAT = os.path.join(DOCS, "catalogs")
NS = uuid.UUID("f244ce09-3c6c-4c82-af14-918bdeca6be3")           # ADR-0006 rule 4
TODAY = dt.date(2026, 11, 15)                                     # the business date of the step (rule 5)


def check(name, ok, detail=""):
    RESULTS.append((bool(ok), name, str(detail)))
    print(("PASS " if ok else "FAIL ") + name + (" -- " + str(detail) if detail != "" else ""))


def raises(fn, *a, **k):
    """The error code a lab function raises, or None."""
    try:
        fn(*a, **k)
    except LabError as e:
        return e.code
    return None


class LabError(Exception):
    def __init__(self, code, **details):
        super().__init__(code)
        self.code, self.details = code, details


# ======================================================================= the GS1 parser (rules 1-6)
GS = "\x1d"
CS82 = set("!\"%&'()*+,-./0123456789:;<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz")
assert len(CS82) == 82
# Predefined lengths by the AI's first two digits, AI included (rule 2).
PRE = {"00": 20, "01": 16, "02": 16, "03": 16, "04": 18, "20": 4, "41": 16,
       **{str(p): 8 for p in range(11, 20)}, **{str(p): 10 for p in range(31, 37)}}
AI = {}


def ai(code, kind, lo, hi, csum=False, date=None, req=(), ex=(), unit=None, decimals=False):
    AI[code] = dict(kind=kind, lo=lo, hi=hi, csum=csum, date=date, req=req, ex=ex, unit=unit, decimals=decimals)


# Lab subset of the table: kind N or X, min and max data length, linters, required alternatives and exclusions.
ai("00", "N", 18, 18, csum=True)
ai("01", "N", 14, 14, csum=True, ex=("02",))
ai("02", "N", 14, 14, csum=True, req=(("37",),), ex=("01",))
ai("10", "X", 1, 20, req=(("01",), ("02",), ("8006",)))
for d_ in ("11", "12", "13", "15", "16", "17"):
    ai(d_, "N", 6, 6, date="yymmd0", req=(("01",), ("02",), ("8006",)))
ai("20", "N", 2, 2, req=(("01",), ("02",)))
ai("21", "X", 1, 20, req=(("01",), ("8006",)))
ai("30", "N", 1, 8, req=(("01",), ("02",)))
ai("37", "N", 1, 8, req=(("02",), ("8026",)))
for base, unit in (("310", "KGM"), ("311", "MTR"), ("314", "MTK"), ("315", "LTR"), ("316", "MTQ"), ("320", "LBR"), ("330", "KGM_GROSS")):
    for n_ in range(6):
        ai(base + str(n_), "N", 6, 6, req=(("01",), ("02",), ("00",)), unit=unit, decimals=True)
ai("400", "X", 1, 30)
ai("414", "N", 13, 13, csum=True)
ai("254", "X", 1, 20, req=(("414",),))
ai("7003", "N", 10, 10, date="yymmddhhmi", req=(("01",), ("02",)))
ai("8006", "N", 18, 18)
ai("8026", "N", 18, 18)
for d_ in range(90, 100):
    ai(str(d_), "X", 1, 90 if d_ > 90 else 30)
# The generator's guard (rule 1): the AI length follows from its first two digits.
AILEN = {}
for code_ in AI:
    assert AILEN.setdefault(code_[:2], len(code_)) == len(code_), code_
for p_, total in PRE.items():
    for code_, spec in AI.items():
        if code_.startswith(p_):
            assert spec["lo"] == spec["hi"] == total - len(code_), code_
MEASURE_UNITS = {"KGM", "MTR", "MTK", "LTR", "MTQ"}               # core units of ADR-0056; others are ignored (rule 5)
DL_PRIMARY = {"01": ("22", "10", "21"), "00": (), "414": ("254",), "8006": ("22", "10", "21")}


def check_digit(data):
    """Rule 4: weights 3, 1, 3, ... from the rightmost data digit; (10 - sum mod 10) mod 10."""
    s = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(data)))
    return (10 - s % 10) % 10


def key_valid(digits):
    return digits.isdigit() and len(digits) >= 2 and check_digit(digits[:-1]) == int(digits[-1])


def gs1_date(yymmdd, ai_code, today):
    """Rule 5: the sliding century window against the business date; day 00 as the month's last or first day."""
    yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    cur = today.year
    diff = yy - cur % 100
    century = cur // 100 + (-1 if diff >= 51 else 1 if diff <= -50 else 0)
    year = century * 100 + yy
    if not 1 <= mm <= 12:
        raise LabError("gs1_invalid", reason="date", ai=ai_code)
    if dd == 0:
        if ai_code in ("12", "15", "16", "17"):
            return dt.date(year, mm, calendar.monthrange(year, mm)[1]), "month"
        if ai_code in ("11", "13"):
            return dt.date(year, mm, 1), "month"
        raise LabError("gs1_invalid", reason="date", ai=ai_code)
    try:
        return dt.date(year, mm, dd), "day"
    except ValueError:
        raise LabError("gs1_invalid", reason="date", ai=ai_code) from None


def check_element(code, value, today):
    spec = AI[code]
    if spec["kind"] == "N" and not value.isdigit():
        raise LabError("gs1_invalid", reason="format", ai=code)
    if spec["kind"] == "X" and not set(value) <= CS82:
        raise LabError("gs1_invalid", reason="format", ai=code)
    if not spec["lo"] <= len(value) <= spec["hi"]:
        raise LabError("gs1_invalid", reason="length", ai=code)
    if spec["csum"] and not key_valid(value):
        raise LabError("gs1_invalid", reason="check_digit", ai=code)
    if spec["date"] == "yymmd0":
        return gs1_date(value, code, today)
    if spec["date"] == "yymmddhhmi":
        d, _ = gs1_date(value[:6], "17x", today) if value[4:6] != "00" else (None, None)
        if d is None or not (int(value[6:8]) < 24 and int(value[8:10]) < 60):
            raise LabError("gs1_invalid", reason="date", ai=code)
        return d, "minute"
    if spec["decimals"]:
        return (D_(int(value)) / (10 ** int(code[3])), spec["unit"]), None
    return value, None


def split_elements(data):
    """Rule 2: split an element string into (AI, value) pairs. A leading GS is dropped; GS after a predefined element is
    tolerated; other AIs end at GS or at the end."""
    out, pos = [], 0
    if data.startswith(GS):
        pos = 1
    while pos < len(data):
        if data[pos] == GS:
            pos += 1
            continue
        p2 = data[pos:pos + 2]
        n = AILEN.get(p2)
        code = data[pos:pos + n] if n else p2
        if not n or code not in AI:
            raise LabError("gs1_invalid", reason="ai_unknown", ai=code)
        pos += n
        if p2 in PRE:
            dl = PRE[p2] - n
            value = data[pos:pos + dl]
            if len(value) < dl or GS in value:
                raise LabError("gs1_invalid", reason="length", ai=code)
            pos += dl
        else:
            end = data.find(GS, pos)
            end = len(data) if end < 0 else end
            value, pos = data[pos:end], end
        out.append((code, value))
    return out


def separator_suspect(pairs, today):
    """Rule 3: the last variable X element ends with characters that parse completely as valid predefined-length
    elements, at least a date or a key."""
    if not pairs:
        return False
    last_code, last_value = pairs[-1]
    if AI[last_code]["kind"] != "X" or last_code in PRE:
        return False
    for k in range(1, len(last_value)):
        try:
            tail_pairs = split_elements(last_value[k:])
        except LabError:
            continue
        if tail_pairs and all(c[:2] in PRE for c, _ in tail_pairs) and all((AI[c]["date"] or AI[c]["csum"]) for c, _ in tail_pairs):
            try:
                for c, v in tail_pairs:
                    check_element(c, v, today)
            except LabError:
                continue
            return True
    return False


def validate(pairs, today, raw_tail_check=True):
    """Rule 3: element checks, repeated AIs, required and forbidden pairs, and (unless the caller handles its exceptions)
    the lost-separator trace. Returns elements."""
    elements = {}
    for code, value in pairs:
        if code in elements and elements[code]["raw"] != value:
            raise LabError("gs1_invalid", reason="repeated_differs", ai=code)
        v, precision = check_element(code, value, today)
        elements[code] = dict(raw=value, value=v, precision=precision)
    for code in elements:
        for x in AI[code]["ex"]:
            if x in elements:
                raise LabError("gs1_invalid", reason="pair_forbidden", ai=code)
        if AI[code]["req"] and not any(all(r in elements for r in alt) for alt in AI[code]["req"]):
            raise LabError("gs1_invalid", reason="pair_required", ai=code)
    if raw_tail_check and separator_suspect(pairs, today):
        raise LabError("gs1_invalid", reason="separator_suspect", ai=pairs[-1][0])
    return elements


def parse_element_string(data, today=TODAY):
    return validate(split_elements(data), today)


def parse_digital_link(uri, today=TODAY):
    """Rule 6: the rightmost primary key segment followed only by its qualifiers, in the table's order, starts the keys;
    numeric query keys are attributes; percent-decoded; a short GTIN padded to 14; never fetched."""
    m = re.match(r"^https?://([^/?#]+)(/[^?#]*)?(?:\?([^#]*))?(?:#.*)?$", uri)
    if not m:
        raise LabError("gs1_invalid", reason="format", ai="dl")
    domain, path_, query = m.group(1), m.group(2) or "", m.group(3) or ""
    segs = [unquote(s) for s in path_.split("/") if s]
    starts = [i for i in range(len(segs) - 1) if segs[i] in DL_PRIMARY and (len(segs) - i) % 2 == 0]
    if not starts:
        raise LabError("gs1_invalid", reason="format", ai="dl")
    start = starts[-1]
    keys = segs[start:]
    pairs = [(keys[i], keys[i + 1]) for i in range(0, len(keys), 2)]
    primary, order = pairs[0][0], DL_PRIMARY[pairs[0][0]]
    idx = [order.index(c) if c in order else -1 for c, _ in pairs[1:]]
    if -1 in idx or idx != sorted(idx):
        raise LabError("gs1_invalid", reason="format", ai="dl")
    if primary == "01" and len(pairs[0][1]) in (8, 12, 13) and pairs[0][1].isdigit():
        pairs[0] = ("01", pairs[0][1].zfill(14))
    for k, v in parse_qsl(query, keep_blank_values=True):
        if k.isdigit() and k in AI:
            pairs.append((k, v))
    elements = validate(pairs, today, raw_tail_check=False)
    return elements, domain


# ======================================================================= transport, normalization, internal codes
GS1_IDS = {"]C1", "]e0", "]d2", "]Q3", "]J1"}
INTERNAL = re.compile(r"^[A-Z][A-Z0-9./_-]{0,47}$")
SUBSTITUTE = "~"


def transport(raw, identifier=None):
    """Rule 2: one trailing suffix removed, an embedded AIM prefix split off, control characters refused. The GS
    substitute is mapped only in data classified as an element string (as_element_string)."""
    if len(raw) > 512:
        raise LabError("scan_malformed")
    for suffix in ("\r\n", "\r", "\n", "\t"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    if identifier is None and raw.startswith("]") and len(raw) >= 3:
        identifier, raw = raw[:3], raw[3:]
    if any((ord(ch) < 32 and ch != GS) or ord(ch) == 127 for ch in raw):
        raise LabError("scan_malformed")
    return identifier, raw


def as_element_string(body):
    return body.replace(SUBSTITUTE, GS)


def normalize(value):
    """Rule 7: GTIN-8, 12 and 13 padded to 14 digits; letters upper case."""
    if value.isdigit() and len(value) in (8, 12, 13):
        return value.zfill(14)
    return value if value.isdigit() else value.upper()


def internal_code_ok(code):
    return bool(INTERNAL.match(code)) and code.isascii()


def gtin14_from(gtin13, indicator):
    """Rule 10: a case GTIN-14 from a GTIN-13 of the same item and an indicator digit 1 to 8."""
    assert 1 <= indicator <= 8 and key_valid(gtin13) and len(gtin13) == 13
    data = str(indicator) + gtin13[:12]
    return data + str(check_digit(data))


def lot_label(code, gtin=None, barcode=None):
    """Rules 8, 21: a lot or serial code that fits (10) or (21) goes into GS1 data with the item's GTIN; any other is
    printed through its own internal barcode."""
    fits = 1 <= len(code) <= 20 and set(code) <= CS82
    if fits and gtin:
        return ("gs1_datamatrix", "]d2" + "01" + gtin + "10" + code)
    if barcode:
        return ("datamatrix", barcode)
    if fits:
        return ("datamatrix", code)
    raise LabError("lot_label_needs_barcode")                 # the creating command generates one (INV-622)


def numbering_barcode_problems(fmt, prefix, codes, counter_width=None):
    """Rule 9: every number a barcoded type's format can produce must be an internal code of at most 48 characters.
    codes: placeholder -> list of the company's values (branch codes, fiscal year codes)."""
    problems = []
    if not fmt.startswith("{prefix}") or fmt[len("{prefix}"):len("{prefix}") + 1] not in ("/", "-", "."):
        problems.append("prefix_separator")
    parts = re.split(r"(\{[a-z_]+(?::\d+)?\})", fmt)
    longest = ""
    for p_ in parts:
        if not p_:
            continue
        m_ = re.fullmatch(r"\{([a-z_]+)(?::(\d+))?\}", p_)
        if m_ is None:
            if not re.fullmatch(r"[A-Za-z0-9./_-]*", p_):
                problems.append(f"literal:{p_}")
            longest += p_
        elif m_.group(1) == "prefix":
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9./_-]*", prefix):
                problems.append("prefix")
            longest += prefix
        elif m_.group(1) == "counter":
            longest += "9" * int(m_.group(2) or counter_width or 6)
        else:
            values = codes.get(m_.group(1), [])
            for v in values:
                if not re.fullmatch(r"[A-Za-z0-9./_-]+", v):
                    problems.append(f"{m_.group(1)}:{v}")
            longest += max(values, key=len) if values else ""
    if len(longest) > 48:
        problems.append("length")
    return problems


# ======================================================================= the registry (rules 7-10)
OWNER_TYPES = ("item_unit", "bin", "handling_unit", "lot", "serial", "document")
SSCC_REUSE_MONTHS = 12                                            # barcode.sscc_reuse_months, unverified (rule 7)


class Registry:
    def __init__(self):
        self.rows = {}                    # barcode -> dict(type, owner, retired_type, retired_owner, legacy, enc, retired_months)
        self.reserved_prefixes = set()    # reserved strings of barcoded document types

    def register(self, btype, value, owner, legacy=False):
        """Rules 7-8; returns the check results of the command (legacy_code_gtin_like). The code retired from the same
        type and owner comes back to it."""
        norm = value.upper() if legacy else normalize(value)
        if value != norm:
            raise LabError("barcode_not_normalized", normalized=norm)
        if legacy:
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9./_-]{0,47}", value):
                raise LabError("barcode_format_invalid", reason="legacy")
            enc = "internal"
        else:
            enc = "gtin" if re.fullmatch(r"\d{14}", value) else "sscc" if re.fullmatch(r"\d{18}", value) else "internal"
            if enc != "internal" and not key_valid(value):
                raise LabError("barcode_format_invalid", reason="check_digit")
            if enc == "internal" and not internal_code_ok(value):
                raise LabError("barcode_format_invalid", reason="internal")
            if enc != "internal" and not ((btype, enc) in (("item_unit", "gtin"), ("handling_unit", "sscc"))):
                raise LabError("barcode_format_invalid", reason="encoding")
        if btype != "document" and any(value.startswith(p) for p in self.reserved_prefixes):
            raise LabError("barcode_prefix_reserved")
        old = self.rows.get(value)
        if old and old["type"] == "internal" and old["retired_type"] == btype and old["retired_owner"] == owner and old["legacy"] == legacy:
            old.update(type=btype, owner=owner, retired_type=None, retired_owner=None, retired_months=None)
            return []
        if old:
            raise LabError("barcode_taken", type=old["type"])
        if value.isdigit() and len(value) <= 14:                  # ux_barcode_numeric_padded
            for b, r in self.rows.items():
                if b.isdigit() and len(b) <= 14 and b.zfill(14) == value.zfill(14):
                    raise LabError("barcode_taken", type=r["type"], reason="padded_digits")
        self.rows[value] = dict(type=btype, owner=owner, retired_type=None, retired_owner=None, legacy=legacy, enc=enc, retired_months=None)
        return ["legacy_code_gtin_like"] if legacy and value.isdigit() and len(value) in (8, 12, 13, 14) and key_valid(value) else []

    def retire(self, value, months_ago=0):
        row = self.rows[value]
        row.update(retired_type=row["type"], retired_owner=row["owner"], type="internal", owner=None, retired_months=months_ago)

    def delete_reservation(self, value):
        """DeleteBarcodeReservation: a reserved or retired row; a retired SSCC only after the reuse period."""
        row = self.rows[value]
        assert row["type"] == "internal"
        if row["enc"] == "sscc" and row["retired_type"] and (row["retired_months"] or 0) < SSCC_REUSE_MONTHS:
            raise LabError("barcode_reuse_period_running")
        del self.rows[value]

    def run_sscc_cleanup(self, own_prefixes):
        """RunRetiredSsccCleanup (rule 7): deletes retired SSCCs past the reuse period whose company prefix is not one of
        the company's own; returns what it deleted."""
        gone = [b for b, r in self.rows.items() if r["enc"] == "sscc" and r["retired_type"] and (r["retired_months"] or 0) >= SSCC_REUSE_MONTHS
                and not any(b[1:1 + len(p)] == p for p in own_prefixes)]
        for b in gone:
            del self.rows[b]
        return gone

    def delete_prefix(self, prefixes, prefix):
        """DeleteGs1CompanyPrefix (rule 11): refused while a registry GTIN or SSCC, live or retired, lies under the prefix
        (its digits after the indicator or extension digit start with it)."""
        if any(r["enc"] in ("gtin", "sscc") and b[1:1 + len(prefix)] == prefix for b, r in self.rows.items()):
            raise LabError("gs1_prefix_in_use")
        prefixes.pop(prefix)

    def legacy_by_digits(self, digits):
        """A numeric legacy code whose digits padded to 14 equal these (rule 13 steps 2-3)."""
        if not digits.isdigit() or len(digits) > 14:
            return None
        return next((b for b, r in self.rows.items() if r["legacy"] and b.isdigit() and len(b) <= 14 and b.zfill(14) == digits.zfill(14)), None)

    def reserve_prefix(self, prefix):
        if not re.fullmatch(r"[A-Z][A-Z0-9]*[/.-]", prefix):
            raise LabError("barcode_prefix_reserved")
        if any(p.startswith(prefix) or prefix.startswith(p) for p in self.reserved_prefixes):
            raise LabError("barcode_prefix_reserved")
        if any(b.startswith(prefix) and r["type"] != "document" for b, r in self.rows.items()):
            raise LabError("barcode_prefix_reserved")
        self.reserved_prefixes.add(prefix)


# ======================================================================= EvaluateBarcode (rules 12-14) and confirm (rule 15)
def classify(identifier, body, camera_format=None):
    """Rule 13 steps 1-2. Returns (encoding, heuristic)."""
    if identifier in GS1_IDS:
        return "gs1", False
    if identifier in ("]E0", "]E4") or (identifier == "]I1" and body.isdigit() and len(body) == 14):
        return "gtin", False
    if identifier in ("]Q1", "]d1") and body.startswith(("http://", "https://")):
        return "dl", False
    if identifier is not None:
        return "plain", False                                     # ]C0, ]A0, ]I1 otherwise and every unlisted identifier
    if camera_format in ("ean_13", "ean_8", "upc_a", "upc_e", "itf"):
        return "gtin", True
    if re.match(r"^https?://", body) and re.search(r"/(01|00|414|8006)/", body):
        return "dl", True
    if body[:1].isalpha():
        return "plain", True
    gs1 = as_element_string(body)
    if gs1.startswith(GS) or (GS in gs1[1:] and gs1[:1].isdigit()):
        return "gs1", True
    if body.isdigit() and len(body) in (8, 12, 13, 14) and key_valid(body):
        return "gtin", True
    if body[:1].isdigit():
        try:
            pairs = split_elements(gs1)
            if pairs and pairs[0][0] in DL_PRIMARY:
                validate(pairs, TODAY)
                return "gs1", True
        except LabError:
            pass
    return "plain", True                                          # a numeric lot code goes on to the registry and context steps


def resolve(scan, reg, data, context=None, today=TODAY):
    """Rules 12-14: typed candidates or typed issues, never a guess. `data` holds the typed rows of the lab company:
    item_barcode {barcode: (item, unit)}, lots {(item, code): id}, serials {(item, code): id}."""
    context = context or {}
    out = dict(encoding=None, elements={}, candidates=[], issues=[], checks=[])
    try:
        ident, body = transport(scan["raw"], scan.get("symbology_identifier"))
    except LabError as e:
        out["issues"].append(e.code)
        return out
    legacy_hit = reg.rows.get(body.upper(), {}).get("legacy") or reg.legacy_by_digits(body)
    if ident is None and legacy_hit:
        enc, heuristic = "plain", False                           # a registered legacy code skips the guarded rules (rule 13 step 2)
    else:
        enc, heuristic = classify(ident, body, scan.get("camera_format"))
    if heuristic:
        out["checks"].append("scan_heuristic_used")
    out["encoding"] = enc
    cands = []
    if enc in ("gs1", "dl"):
        try:
            if enc == "dl":
                el = parse_digital_link(body, today)[0]
            else:
                gs1 = as_element_string(body)
                pairs = split_elements(gs1)
                el = validate(pairs, today, raw_tail_check=False)
                if separator_suspect(pairs, today) and not scan.get("confirmed_as_read"):
                    proven = GS in gs1[1:] or scan.get("decoder") == "wasm"
                    item = data["item_barcode"].get(el.get("01", {}).get("raw"), (None,))[0]
                    last = pairs[-1][1]
                    known = {c for (i, c) in data["lots"] if i == item} | {c for (i, c) in data["serials"] if i == item} | {
                        e.get("code") for e in context.get("expected", ())}
                    if not proven and last not in known:
                        raise LabError("gs1_invalid", reason="separator_suspect", ai=pairs[-1][0])
        except LabError as e:
            out["issues"].append(e.code)
            out["details"] = e.details
            return out
        out["elements"] = el
        if any(k in el for k in ("414", "254", "253", "8003", "8004", "400")) or any(
                k[:3] in ("320", "330") for k in el) or any(k.isdigit() and 90 <= int(k) <= 99 for k in el if len(k) == 2):
            out["checks"].append("gs1_element_ignored")
        if "00" in el:
            row = reg.rows.get(el["00"]["raw"])
            if row and row["type"] == "handling_unit":
                cands.append(dict(type="handling_unit", id=row["owner"], code=el["00"]["raw"]))
            elif row:
                out["issues"].append("barcode_retired")
            elif "handling_unit" in context.get("capture", ()):
                cands.append(dict(type="handling_unit", id=None, code=el["00"]["raw"]))
        key = "01" if "01" in el else "02" if "02" in el else None
        if key:
            gtin = el[key]["raw"]
            row = reg.rows.get(gtin)
            if row is None:
                out["issues"].append("barcode_unknown")
                out["details"] = dict(key="gtin")
            elif row["type"] != "item_unit":
                out["issues"].append("barcode_retired")
            else:
                item, unit = data["item_barcode"][gtin]
                qty, qunit = F(1), unit
                if "30" in el:
                    qty = F(int(el["30"]["raw"]))
                if key == "02" and "37" in el:
                    qty = F(int(el["37"]["raw"]))
                measure = [k for k in el if AI[k]["decimals"] and AI[k]["unit"] in MEASURE_UNITS]
                if measure:
                    v, u = el[measure[0]]["value"]
                    qty, qunit = F(str(v)), u
                expiry = el.get("17", el.get("15", {})).get("value")
                lot = el.get("10", {}).get("raw")
                if "21" in el:                                    # (01)(21), with (10) one serial that carries the lot (rule 13)
                    code = el["21"]["raw"]
                    cands.append(dict(type="serial", id=data["serials"].get((item, code)), item_id=item, uom_id=unit, serial_code=code,
                                      lot_code=lot, lot_id=data["lots"].get((item, lot)) if lot else None, expiry_date=expiry,
                                      quantity=F(1), quantity_uom_id=unit))
                elif lot is not None:
                    cands.append(dict(type="lot", id=data["lots"].get((item, lot)), item_id=item, uom_id=unit, lot_code=lot,
                                      quantity=qty, quantity_uom_id=qunit, expiry_date=expiry))
                else:
                    cands.append(dict(type="item_unit", id=gtin, item_id=item, uom_id=unit, quantity=qty, quantity_uom_id=qunit))
    elif enc in ("gtin", "plain"):
        value = normalize(body)
        row = reg.rows.get(value)
        if row is None:
            alt = body.upper() if reg.rows.get(body.upper(), {}).get("legacy") else reg.legacy_by_digits(body)
            if alt:
                value, row = alt, reg.rows[alt]                   # legacy codes, also as the fallback of an unregistered GTIN (rule 13 step 3)
        if row and row["type"] == "internal":
            out["issues"].append("barcode_retired")
            out["details"] = dict(retired_type=row["retired_type"])
        elif row:
            c_ = dict(type=row["type"], id=value if row["type"] == "item_unit" else row["owner"], code=value)
            if row["type"] == "item_unit":
                c_.update(item_id=data["item_barcode"][value][0], uom_id=data["item_barcode"][value][1], quantity=F(1))
            cands.append(c_)
        else:
            lots = [(i, l) for (i, c), l in data["lots"].items() if c == body]
            sers = [(i, s) for (i, c), s in data["serials"].items() if c == body]
            item = context.get("item_id")
            if lots or sers:
                if item is None:
                    out["issues"].append("lot_needs_item" if lots else "serial_needs_item")
                else:
                    cands += [dict(type="lot", id=l, item_id=i, lot_code=body) for i, l in lots if i == item]
                    cands += [dict(type="serial", id=s, item_id=i, serial_code=body) for i, s in sers if i == item]
                    if not cands:
                        out["issues"].append("barcode_unknown")
            else:
                out["issues"].append("barcode_unknown")
    if not cands and not out["issues"]:
        out["issues"].append("barcode_unknown")
    if context.get("mode") == "confirm" and context.get("expected"):
        out["unfiltered"] = cands
        cands = [c for c in cands if any(c["type"] == e["type"] and (e.get("id") is None or c.get("id") == e["id"])
                                         and (e.get("item_id") is None or c.get("item_id") == e["item_id"]) for e in context["expected"])]
    if len(cands) > 1:
        out["issues"].append("barcode_ambiguous")
    out["candidates"] = cands
    return out


def confirm(scan, reg, data, expected, today=TODAY):
    """Rule 15: a posting step accepts only what it expects."""
    r = resolve(scan, reg, data, dict(mode="confirm", expected=expected, item_id=expected[0].get("item_id")), today)
    if r["issues"] and not r["candidates"]:
        if r.get("unfiltered"):
            raise LabError("scan_mismatch")
        raise LabError("scan_unresolved", issues=r["issues"])
    if not r["candidates"]:
        raise LabError("scan_mismatch", expected=expected)
    if len(r["candidates"]) > 1:
        raise LabError("scan_unresolved", issues=["barcode_ambiguous"])
    return r["candidates"][0]


# ======================================================================= capture (rules 17-19)
UNITS = {"H87": ("count", 0), "KGM": ("mass", 3), "GRM": ("mass", 0), "MTR": ("length", 3), "LTR": ("volume", 3), "x-carton": ("count", 0)}
GLOBAL = {("KGM", "GRM"): (1000, 1)}
ITEMS = {"i_pcs": ("H87", {"x-carton": (24, 1)}), "i_kg": ("KGM", {}), "i_g": ("GRM", {}), "i_cnt": ("H87", {})}


def round_half_up(x, dec):
    y = F(x) * 10 ** dec
    s, a = (-1 if y < 0 else 1), abs(y)
    h = a + F(1, 2)
    return F(s * (h.numerator // h.denominator), 10 ** dec)


def convert_capture(item, q, unit):
    """Rule 18 with ADR-0006 rule 14 and ADR-0056 rules 6, 8, 9: the AI's unit is the entered unit; the measure is never
    rounded (extra zero decimals are dropped, any other extra decimal is too_many_decimal_places); the inventory
    quantity converts as for receipts."""
    inv, pus = ITEMS[item]
    q = F(q)
    if (q * 10 ** UNITS[unit][1]).denominator != 1:
        raise LabError("too_many_decimal_places")
    if unit == inv:
        n, d, src = 1, 1, "identity"
    elif unit in pus:
        (n, d), src = pus[unit], "product"
    elif (unit, inv) in GLOBAL:
        (n, d), src = GLOBAL[(unit, inv)], "global"
    elif (inv, unit) in GLOBAL:
        d, n = GLOBAL[(inv, unit)]
        src = "global"
    else:
        raise LabError("uom_not_allowed")
    return dict(quantity=q, uom_id=unit, uom_numerator=n, uom_denominator=d, uom_factor_source=src,
                inventory_quantity=round_half_up(q * F(n, d), UNITS[inv][1]))


def capture_lot(candidate, existing_lot=None, typed=None):
    """Rule 17: a scanned value differing from a typed value or a stored lot date stops with gs1_capture_conflict."""
    typed = typed or {}
    if "lot_code" in typed and typed["lot_code"] != candidate["lot_code"]:
        raise LabError("gs1_capture_conflict", field="lot_code")
    if existing_lot and candidate.get("expiry_date") and existing_lot.get("expiry_date") not in (None, candidate["expiry_date"]):
        raise LabError("gs1_capture_conflict", field="expiry_date")
    return dict(code=candidate["lot_code"], expiry_date=candidate.get("expiry_date") or (existing_lot or {}).get("expiry_date"))


def confirm_serials(task_item, task_quantity, scans, reg, data, hu_contents=None):
    """Rule 19: per-unit scans with a running count and duplicate check; a closed handling unit taken whole confirms its
    serials at once."""
    got, counts = [], []
    for s in scans:
        r = resolve(s, reg, data, dict(item_id=task_item))
        if r["candidates"] and r["candidates"][0]["type"] == "handling_unit":
            serials = (hu_contents or {}).get(r["candidates"][0]["id"], [])
            if len(serials) + len(got) > task_quantity or any(i != task_item for i, _ in serials):
                raise LabError("scan_mismatch", reason="unpack_first")
            for _, code in serials:
                if code in got:
                    raise LabError("serial_already_scanned")
                got.append(code)
            counts.append(len(got))
            continue
        if r["issues"] and not r["candidates"]:
            raise LabError("scan_unresolved", issues=r["issues"])
        c_ = r["candidates"][0]
        if c_["type"] != "serial" or c_["item_id"] != task_item:
            raise LabError("scan_mismatch")
        if c_["serial_code"] in got:
            raise LabError("serial_already_scanned")
        got.append(c_["serial_code"])
        counts.append(len(got))
    return got, [f"{n} of {task_quantity}" for n in counts]


# ======================================================================= P: pure checks
# --- check digits (rule 4)
check("P01 the worked example: data digits 893123456789 give check digit 7, GTIN-13 8931234567897", check_digit("893123456789") == 7)
check("P02 GTIN-13 4006381333931 is valid and 4006381333932 is not", key_valid("4006381333931") and not key_valid("4006381333932"))
check("P03 GTIN-8 96385074 is valid and 96385075 is not", key_valid("96385074") and not key_valid("96385075"))
check("P04 GTIN-12 036000291452 is valid and 036000291453 is not", key_valid("036000291452") and not key_valid("036000291453"))
check("P05 the case GTIN-14 with indicator 1 is 18931234567894: the check digit changes with the indicator (4, not 7)",
      check_digit("1893123456789") == 4 and key_valid("18931234567894") and not key_valid("18931234567897"))
check("P06 padding keeps the check digit: 08931234567897 is valid", key_valid("08931234567897") and normalize("8931234567897") == "08931234567897")
check("P07 the SSCC example 389312340000000005 is valid and ...006 is not", key_valid("389312340000000005") and not key_valid("389312340000000006"))
check("P08 GTIN-8 and GTIN-12 normalize to 14 digits", (normalize("96385074"), normalize("036000291452")) == ("00000096385074", "00036000291452"))

# --- element strings (rule 2)
G14 = "08931234567897"
GV = "9893123456789" + str(check_digit("9893123456789"))     # a variable-measure trade item (indicator 9)
GC = "0893123450001" + str(check_digit("0893123450001"))     # a serial-tracked item
e = parse_element_string("01" + G14 + "17261130" + "10LOT-A1")
check("P09 (01)(17)(10) without any separator: fixed-length elements first, the variable lot last",
      (e["01"]["raw"], e["17"]["value"], e["10"]["raw"]) == (G14, dt.date(2026, 11, 30), "LOT-A1"), e)
e = parse_element_string("01" + G14 + "10ABC" + GS + "17261130")
check("P10 a variable element that is not last ends at GS", (e["10"]["raw"], e["17"]["value"]) == ("ABC", dt.date(2026, 11, 30)), e)
_, body = transport("]C1" + "01" + G14 + "10ABC~17261130\r")
e = parse_element_string(as_element_string(body))
check("P11 the wedge transport: suffix removed, AIM prefix split off, the ~ substitute mapped back to GS in an element string", e["10"]["raw"] == "ABC" and "17" in e and "~" in body, e)
e = parse_element_string(GS + "01" + G14 + "17261130")
check("P12 a leading GS (FNC1 sent by a decoder) is dropped", e["01"]["raw"] == G14)
e = parse_element_string("01" + G14 + GS + "17261130")
check("P13 a GS after a predefined-length element is tolerated", e["17"]["value"] == dt.date(2026, 11, 30))
check("P14 (7003) is fixed at 10 digits but not predefined: without GS the next AI runs into it and it is refused (length)",
      raises(parse_element_string, "01" + G14 + "7003261130120010A") == "gs1_invalid"
      and "7003" in parse_element_string("01" + G14 + "70032611301200" + GS + "10A"))
check("P15 an AI the table does not hold is gs1_invalid ai_unknown", raises(parse_element_string, "29123") == "gs1_invalid")
try:
    parse_element_string("01" + G14 + "10ABCDEFGHIJKLMNOPQRSTU")
except LabError as ex:
    r15 = ex.details
check("P16 a lot longer than 20 characters is gs1_invalid length", r15 == dict(reason="length", ai="10"), r15)
try:
    parse_element_string("01" + G14 + "10AB#C")
except LabError as ex:
    r16 = ex.details
check("P17 '#' is outside GS1 character set 82: gs1_invalid format", r16["reason"] == "format", r16)
try:
    parse_element_string("01" + "08931234567890")
except LabError as ex:
    r17 = ex.details
check("P18 a GTIN with a wrong check digit inside an element string is gs1_invalid check_digit", r17["reason"] == "check_digit", r17)
check("P19 a predefined element cut short (01 with 13 digits at the end) is refused", raises(parse_element_string, "01" + G14[:-1]) == "gs1_invalid")

# --- validation (rule 3)
def reason(data):
    try:
        parse_element_string(data)
    except LabError as ex_:
        return ex_.details.get("reason")
    return None


check("P20 (21) without (01) or (8006) is pair_required", reason("21SN-1") == "pair_required")
check("P21 (01) with (02) is pair_forbidden", reason("01" + G14 + "02" + G14 + "3712") == "pair_forbidden")
check("P22 (02) needs (37): alone it is pair_required, with (37) it parses", reason("02" + G14) == "pair_required" and reason("02" + G14 + "3712") is None)
check("P23 (37) needs (02) or (8026)", reason("3712") == "pair_required")
check("P24 a repeated AI with the same value is accepted, with another value it is repeated_differs",
      reason("01" + G14 + "10A" + GS + "10A") is None and reason("01" + G14 + "10A" + GS + "10B") == "repeated_differs")
check("P25 the lost separator: (10) before (17) without GS leaves 'LOT1717261130' as lot, which ends in a valid (17): separator_suspect",
      reason("01" + G14 + "10LOT1717261130") == "separator_suspect")
check("P26 ... while a lot ending in digits that are no valid date passes", reason("01" + G14 + "10LOT1717261399") is None)

# --- dates (rule 5)
d_ = lambda yymmdd, ai_="17", today=TODAY: gs1_date(yymmdd, ai_, today)[0]
check("P27 century window in 2026: 76 is 2076 and 77 is 1977", (d_("760101").year, d_("770101").year) == (2076, 1977))
check("P28 the window follows the business date, never the wall clock: in 2075, 25 is 2125", d_("250101", today=dt.date(2075, 6, 1)).year == 2125)
check("P29 day 00 is the last day of the month for (17) and (15), including February of a leap year",
      (d_("260200"), d_("240200", "15"), d_("261100")) == (dt.date(2026, 2, 28), dt.date(2024, 2, 29), dt.date(2026, 11, 30)))
check("P30 day 00 is the first day for (11) production and (13) packaging, with precision month",
      gs1_date("260200", "11", TODAY) == (dt.date(2026, 2, 1), "month") and d_("260300", "13") == dt.date(2026, 3, 1))
check("P31 impossible dates are gs1_invalid date: month 13, 29 February 2025; 29 February 2024 is valid",
      reason("01" + G14 + "17261301") == "date" and reason("01" + G14 + "17250229") == "date" and reason("01" + G14 + "17240229") is None)

# --- measures (rule 5)
m_ = lambda s: parse_element_string("01" + GV + s)
check("P32 3102 001156 is 11.56 kg", m_("3102001156")["3102"]["value"] == (D_("11.56"), "KGM"))
check("P33 the fourth digit is the decimal position: 3105 012345 is 0.12345 kg, 3100 000012 is 12 kg",
      m_("3105012345")["3105"]["value"] == (D_("0.12345"), "KGM") and m_("3100000012")["3100"]["value"] == (D_(12), "KGM"))
check("P34 3106 does not exist (0 to 5 decimals): ai_unknown", reason("01" + GV + "3106001156") == "ai_unknown")
check("P35 311n is metres and 315n litres", m_("3113001500")["3113"]["value"] == (D_("1.5"), "MTR") and m_("3151000750")["3151"]["value"] == (D_("75"), "LTR"))
check("P36 the variable-measure GTIN with indicator 9 is computed, never copied: 98931234567890", GV == "98931234567890" and key_valid(GV))

# --- Digital Link (rule 6)
el, dom = parse_digital_link("https://id.example.com/01/" + G14 + "/10/LOT%2FA1?17=261130&linkType=all")
check("P37 Digital Link: path keys, a percent-decoded lot, a numeric query attribute; non-AI query keys ignored",
      (el["01"]["raw"], el["10"]["raw"], el["17"]["value"], dom) == (G14, "LOT/A1", dt.date(2026, 11, 30), "id.example.com") and "linkType" not in el, el)
el, _ = parse_digital_link("https://example.com/products/en/01/8931234567897/21/SN-0001")
check("P38 a path prefix before the primary key is skipped and a GTIN-13 is padded to 14", (el["01"]["raw"], el["21"]["raw"]) == (G14, "SN-0001"), el)
check("P39 qualifiers out of order (/21 before /10) are refused", raises(parse_digital_link, "https://e.com/01/" + G14 + "/21/X/10/Y") == "gs1_invalid")
check("P40 a Digital Link GTIN with a wrong check digit is gs1_invalid", raises(parse_digital_link, "https://e.com/01/08931234567890") == "gs1_invalid")
check("P41 a URI without a primary key segment is no Digital Link", raises(parse_digital_link, "https://e.com/catalog/item/42") == "gs1_invalid")

# --- normalization and internal codes (rules 7-8)
check("P42 internal codes: A-03-02, HU-000123, PO/FY2026/000012 and W1-DEFAULT fit the format",
      all(internal_code_ok(c) for c in ("A-03-02", "HU-000123", "PO/FY2026/000012", "W1-DEFAULT")))
check("P43 not internal codes: a leading digit, lower case, a space, a non-ASCII letter, 49 characters",
      not any(internal_code_ok(c) for c in ("1A", "a-1", "A B", "Ä-1", "A" * 49)) and internal_code_ok("A" * 48))
check("P44 a wedge with caps lock: a-03-02 normalizes to A-03-02", normalize("a-03-02") == "A-03-02")
check("P45 the GS substitute ~ is outside character set 82 and the internal format; it is mapped in element strings only, never in a Digital Link",
      "~" not in CS82 and not internal_code_ok("A~1") and transport("A~1")[1] == "A~1")

# --- the registry (rule 7, 9)
REG = Registry()
DATA = dict(item_barcode={}, lots={}, serials={})
for code_, item_, unit_ in ((G14, "i_pcs", "H87"), ("18931234567894", "i_pcs", "x-carton"), (GV, "i_kg", "KGM"), ("I-0001", "i_pcs", "H87")):
    REG.register("item_unit", code_, ("ib", code_))
    DATA["item_barcode"][code_] = (item_, unit_)
REG.register("bin", "A-03-02", "bin_a0302")
REG.register("bin", "A-03-04", "bin_a0304")
REG.register("handling_unit", "389312340000000005", "hu_1")
REG.register("handling_unit", "HU-000123", "hu_2")
DATA["lots"] = {("i_pcs", "LOT-A1"): "lot_a1_pcs", ("i_kg", "LOT-A1"): "lot_a1_kg", ("i_kg", "LOT-K9"): "lot_k9"}
DATA["serials"] = {("i_cnt", "SN-0001"): "s1", ("i_cnt", "SN-0002"): "s2", ("i_cnt", "SN-0003"): "s3", ("i_pcs", "SN-0001"): "s_other"}
check("P46 cross-type uniqueness: a bin with the code an item unit holds is barcode_taken", raises(REG.register, "bin", "I-0001", "b") == "barcode_taken")
check("P47 ... and a lot label code equal to a handling unit's is barcode_taken", raises(REG.register, "lot", "HU-000123", "l") == "barcode_taken")
check("P48 values must be stored normalized: a GTIN-13 or a lower-case code is barcode_not_normalized",
      raises(REG.register, "item_unit", "4006381333931", "x") == raises(REG.register, "bin", "b-1", "x") == "barcode_not_normalized")
check("P49 a GTIN with a wrong check digit, and an SSCC on a bin, are barcode_format_invalid",
      raises(REG.register, "item_unit", "04006381333932", "x") == raises(REG.register, "bin", "389312340000000012", "x") == "barcode_format_invalid")
REG.register("bin", "B-01", "bin_b01")
REG.retire("B-01")
REG.register("bin", "B-01-NEW", "bin_b01")
check("P50 a changed bin barcode stays reserved: the old code cannot go to another object", raises(REG.register, "handling_unit", "B-01", "hu") == "barcode_taken")
REG.register("lot", "L-000009", "lot_x")
REG.retire("L-000009")
REG.delete_reservation("L-000009")
REG.register("lot", "L-000009", "lot_y")
check("P51 after DeleteBarcodeReservation the code may be used again", REG.rows["L-000009"]["owner"] == "lot_y")
REG.reserve_prefix("PO/")
check("P52 reserved document prefixes: a bin coded PO/1 is refused, another barcoded type may not take P/ or PO/X/",
      raises(REG.register, "bin", "PO/1", "b") == "barcode_prefix_reserved" and raises(REG.reserve_prefix, "PO/X/") == "barcode_prefix_reserved"
      and raises(REG.reserve_prefix, "GR/") is None)
REG.register("document", "PO/FY2026/000012", "doc_po12")
check("P53 a reserved prefix that a registered bin code already starts with is refused", raises(REG.reserve_prefix, "A-") == "barcode_prefix_reserved")

# --- resolution order and typed issues (rules 13-14)
R_ = lambda raw, ident=None, ctx=None, cam=None: resolve(dict(raw=raw, symbology_identifier=ident, camera_format=cam), REG, DATA, ctx)
r = R_("]C1" + "01" + G14 + "17261130" + "10LOT-A1")
check("P54 ]C1: a GS1 element string; (01)+(10) gives one lot candidate with item, unit, quantity 1 and expiry",
      r["encoding"] == "gs1" and len(r["candidates"]) == 1 and r["candidates"][0]["type"] == "lot"
      and (r["candidates"][0]["item_id"], r["candidates"][0]["id"], r["candidates"][0]["expiry_date"]) == ("i_pcs", "lot_a1_pcs", dt.date(2026, 11, 30)), r)
r = R_("0108931234567897", "]C0")
check("P55 ]C0: a plain Code 128 starting with 01 is never parsed as GS1 (barcode_unknown, no elements)",
      r["encoding"] == "plain" and r["issues"] == ["barcode_unknown"] and r["elements"] == {}, r)
r = R_("0108931234567897")
check("P56 the same data without an identifier parses completely as (01) with a valid key: GS1, flagged scan_heuristic_used",
      r["encoding"] == "gs1" and r["candidates"][0]["type"] == "item_unit" and "scan_heuristic_used" in r["checks"], r)
r = R_("8931234567897", "]E0")
check("P57 ]E0: an EAN-13 resolves through the registry as GTIN-14 to the item unit (piece)",
      r["candidates"] == [dict(type="item_unit", id=G14, code=G14, item_id="i_pcs", uom_id="H87", quantity=F(1))], r)
r = R_("18931234567894", "]I1")
check("P58 ]I1: the ITF-14 case GTIN proposes the carton unit with quantity 1 (one carton, ADR-0056 rule 13)",
      (r["candidates"][0]["uom_id"], r["candidates"][0]["quantity"]) == ("x-carton", 1), r)
r = R_("8931234567897")
check("P59 13 digits with a valid check digit and no identifier: a GTIN, flagged as heuristic", r["encoding"] == "gtin" and "scan_heuristic_used" in r["checks"], r)
r = R_("a-03-02\r")
check("P60 an internal code typed by a wedge in lower case resolves to bin A-03-02", r["candidates"][0]["id"] == "bin_a0302", r)
r = R_("B-01", "]C0")
check("P61 a retired code gives barcode_retired with the type it had, never another object",
      r["issues"] == ["barcode_retired"] and r["details"] == dict(retired_type="bin") and r["candidates"] == [], r)
r = R_("ZZ-404", "]C0")
check("P62 an unknown internal code is barcode_unknown", r["issues"] == ["barcode_unknown"], r)
r = R_("]C1" + "01" + "04006381333931" + "10X")
check("P63 an unknown GTIN is barcode_unknown with details.key gtin", r["issues"] == ["barcode_unknown"] and r["details"] == dict(key="gtin"), r)
r1, r2 = R_("LOT-K9", "]C0"), R_("LOT-K9", "]C0", dict(item_id="i_kg"))
check("P64 a bare lot code needs an item even when only one item has it: lot_needs_item; with the task's item it resolves",
      r1["issues"] == ["lot_needs_item"] and r2["candidates"][0]["id"] == "lot_k9", (r1, r2))
r = R_("SN-0002", "]C0")
check("P65 a bare serial code without an item is serial_needs_item", r["issues"] == ["serial_needs_item"], r)
PAL = "]C1" + "00389312340000000005" + "02" + G14 + "3724" + GS + "10LOT-A1"
r = R_(PAL)
check("P66 a pallet label (00)(02)(37)(10) on a search screen: two candidates (handling unit, lot of the contained item): barcode_ambiguous",
      sorted(c["type"] for c in r["candidates"]) == ["handling_unit", "lot"] and "barcode_ambiguous" in r["issues"], r)
r = R_(PAL, ctx=dict(mode="confirm", expected=[dict(type="handling_unit")]))
check("P67 ... and in a step that expects a handling unit, the context leaves the unit", [c["id"] for c in r["candidates"]] == ["hu_1"] and not r["issues"], r)
r = R_(PAL, ctx=dict(mode="confirm", expected=[dict(type="lot", item_id="i_pcs")]))
check("P68 ... and a receipt step expecting a lot gets the contained item, lot LOT-A1 and 24 from (37)",
      (r["candidates"][0]["lot_code"], r["candidates"][0]["quantity"]) == ("LOT-A1", 24), r)
r = R_("A-03\x0702")
check("P69 a control character other than GS and the suffix is scan_malformed", r["issues"] == ["scan_malformed"], r)
r = R_("]C1" + "414" + "8931234567897" + "254" + "SHELF-3")
check("P70 (414)+(254) location keys are read and reported gs1_element_ignored in Phase 1", "gs1_element_ignored" in r["checks"] and "414" in r["elements"], r)
r = R_("]C1" + "01" + G14 + "10LOT1717261130")
check("P71 a resolver never guesses past a suspected lost separator: gs1_invalid separator_suspect and no candidate",
      r["issues"] == ["gs1_invalid"] and r["details"]["reason"] == "separator_suspect" and not r["candidates"], r)
r = R_("https://id.example.com/01/" + G14 + "/10/LOT-A1?17=261130", "]Q1")
check("P72 ]Q1 with https: a Digital Link resolves like the element string (the lot of the item), nothing fetched",
      r["encoding"] == "dl" and r["candidates"][0]["id"] == "lot_a1_pcs", r)
r = R_("]C1" + "01" + GV + "3102001156")
check("P73 a variable-measure label proposes 11.56 in kg as quantity", (r["candidates"][0]["quantity"], r["candidates"][0]["quantity_uom_id"]) == (F("11.56"), "KGM"), r)
r = R_("]C1" + "01" + GV + "3202002500")
check("P74 a pound measure (320n) is not a core unit: ignored, the quantity stays 1 in the barcode's unit",
      "gs1_element_ignored" in r["checks"] and r["candidates"][0]["quantity"] == 1, r)
r = R_("4006381333931", cam="ean_13")
check("P75 a camera result without identifier uses its format as a stand-in: ean_13 is a GTIN", r["encoding"] == "gtin" and r["issues"] == ["barcode_unknown"], r)

# --- scan-to-confirm (rule 15)
check("P76 confirm: the expected source bin A-03-02 scanned as A-03-04 is scan_mismatch, never a silent replacement",
      raises(confirm, dict(raw="A-03-04", symbology_identifier="]C0"), REG, DATA, [dict(type="bin", id="bin_a0302")]) == "scan_mismatch")
check("P77 confirm: the expected bin scanned correctly returns it", confirm(dict(raw="A-03-02", symbology_identifier="]C0"), REG, DATA,
                                                                         [dict(type="bin", id="bin_a0302")])["id"] == "bin_a0302")
check("P78 confirm: an unknown or retired scan on a posting step is scan_unresolved",
      raises(confirm, dict(raw="ZZ-404", symbology_identifier="]C0"), REG, DATA, [dict(type="bin")]) == "scan_unresolved"
      and raises(confirm, dict(raw="B-01", symbology_identifier="]C0"), REG, DATA, [dict(type="bin")]) == "scan_unresolved")
check("P79 confirm: a lot of another item than the task's is scan_mismatch",
      raises(confirm, dict(raw="]C1" + "01" + GV + "3102001156" + "10LOT-K9"), REG, DATA, [dict(type="lot", item_id="i_pcs")]) == "scan_mismatch")
check("P80 confirm: a bin scanned where a lot of the item is expected is scan_mismatch",
      raises(confirm, dict(raw="A-03-02", symbology_identifier="]C0"), REG, DATA, [dict(type="lot", item_id="i_pcs")]) == "scan_mismatch")

# --- serial capture (rule 19)
REG.register("item_unit", GC, ("ib", "cnt"))
DATA["item_barcode"][GC] = ("i_cnt", "H87")
SER = lambda code: dict(raw="]C1" + "01" + GC + "21" + code)
got, counts = confirm_serials("i_cnt", 3, [SER("SN-0001"), SER("SN-0002"), SER("SN-0003")], REG, DATA)
check("P81 serials per unit: three (01)(21) scans with a running count 1 of 3 to 3 of 3", got == ["SN-0001", "SN-0002", "SN-0003"] and counts[-1] == "3 of 3", counts)
check("P82 a serial scanned twice in one confirmation is serial_already_scanned",
      raises(confirm_serials, "i_cnt", 3, [SER("SN-0001"), SER("SN-0001")], REG, DATA) == "serial_already_scanned")
check("P83 a (01)(21) of another item's GTIN is scan_mismatch",
      raises(confirm_serials, "i_cnt", 1, [dict(raw="]C1" + "01" + G14 + "21SN-0001")], REG, DATA) == "scan_mismatch")
HU = {"hu_2": [("i_cnt", "SN-0001"), ("i_cnt", "SN-0002"), ("i_cnt", "SN-0003")]}
got, _ = confirm_serials("i_cnt", 3, [dict(raw="HU-000123", symbology_identifier="]C0")], REG, DATA, HU)
check("P84 a closed handling unit taken whole confirms all its serials with one scan", got == ["SN-0001", "SN-0002", "SN-0003"], got)
check("P85 a handling unit with more serials than the task takes must be unpacked first",
      raises(confirm_serials, "i_cnt", 2, [dict(raw="HU-000123", symbology_identifier="]C0")], REG, DATA, HU) == "scan_mismatch")

# --- capture conflicts (rule 17)
cand = R_("]C1" + "01" + G14 + "17261231" + "10LOT-A1")["candidates"][0]
check("P86 a scanned expiry differing from the existing lot's is gs1_capture_conflict",
      raises(capture_lot, cand, dict(expiry_date=dt.date(2026, 11, 30))) == "gs1_capture_conflict")
check("P87 a typed lot code differing from the scanned one is gs1_capture_conflict", raises(capture_lot, cand, None, dict(lot_code="LOT-B2")) == "gs1_capture_conflict")
check("P88 a new lot takes the scanned code and expiry", capture_lot(cand) == dict(code="LOT-A1", expiry_date=dt.date(2026, 12, 31)))
e15 = R_("]C1" + "01" + G14 + "15270300" + "10LOT-C3")["candidates"][0]
check("P89 (15) best before fills the expiry when (17) is absent, day 00 as the month's last day", e15["expiry_date"] == dt.date(2027, 3, 31), e15)

# --- variable-measure conversion (rule 18 with ADR-0056)
c1 = convert_capture("i_kg", F("11.56"), "KGM")
check("P90 11.56 kg into an item kept in kg: identity, 11.560", (c1["uom_factor_source"], c1["inventory_quantity"]) == ("identity", F("11.56")), c1)
c2 = convert_capture("i_g", F("11.56"), "KGM")
check("P91 11.56 kg into an item kept in grams: entered in KGM, the catalog's 1000/1, 11560 g",
      (c2["uom_id"], c2["uom_numerator"], c2["uom_factor_source"], c2["inventory_quantity"]) == ("KGM", 1000, "global", 11560), c2)
check("P92 a measure into an item kept in pieces without a kilogram unit is uom_not_allowed", raises(convert_capture, "i_pcs", F("11.56"), "KGM") == "uom_not_allowed")
c3 = convert_capture("i_kg", F(str(parse_element_string("01" + GV + "3105115600")["3105"]["value"][0])), "KGM")
check("P93 a measure is never rounded: 3105 115600 (1.15600 kg) has zero extra decimals and enters as 1.156; 3105 012345 is too_many_decimal_places",
      c3["quantity"] == F("1.156") and raises(convert_capture, "i_kg", F("0.12345"), "KGM") == "too_many_decimal_places", c3)
c4 = convert_capture("i_pcs", 1, "x-carton")
check("P94 one carton from a carton GTIN: product factor 24/1, 24 pieces", (c4["uom_factor_source"], c4["inventory_quantity"]) == ("product", 24), c4)

# --- lab table guard (rule 1)
check("P95 the lab table keeps the generator's guard: every AI's length follows from its first two digits, and predefined prefixes agree",
      all(len(c) == AILEN[c[:2]] for c in AI))

# --- legacy codes (rule 8)
chk = REG.register("bin", "123456", "bin_legacy", legacy=True)
check("P96 an old numeric bin label loads as a legacy code (no check result); the same digits without the flag are barcode_format_invalid",
      chk == [] and REG.rows["123456"]["enc"] == "internal" and raises(REG.register, "bin", "123457", "b") == "barcode_format_invalid")
chk = REG.register("item_unit", "4006381333931", ("ib", "legacy"), legacy=True)
DATA["item_barcode"]["4006381333931"] = ("i_pcs", "x-carton")
check("P97 a legacy numeric code that passes a GTIN check digit is registered as it is (13 digits, never padded) with legacy_code_gtin_like",
      chk == ["legacy_code_gtin_like"] and "04006381333931" not in REG.rows and "4006381333931" in REG.rows)
check("P98 a GTIN equal to that legacy code padded to 14 digits is barcode_taken, and so is a legacy code equal to a registered GTIN",
      raises(REG.register, "item_unit", "04006381333931", "x") == "barcode_taken" and raises(REG.register, "bin", "8931234567897", "b", legacy=True) == "barcode_taken")
check("P99 legacy codes are stored in upper case and use the internal characters only",
      raises(REG.register, "bin", "ab-1", "b", legacy=True) == "barcode_not_normalized" and raises(REG.register, "bin", "AB 1", "b", legacy=True) == "barcode_format_invalid")
r1, r2 = R_("123456"), R_("123456", "]C0")
check("P100 a legacy code scanned without an identifier resolves at the registry, before the guarded rules (no scan_heuristic_used); with ]C0 the same",
      r1["candidates"][0]["id"] == "bin_legacy" and "scan_heuristic_used" not in r1["checks"] and r2["candidates"][0]["id"] == "bin_legacy", (r1, r2))
r = R_("4006381333931", "]E0")
check("P101 an old item number printed as EAN-13 (]E0): no GTIN 04006381333931 is registered, so the scanned digits resolve as the legacy code (a carton)",
      r["candidates"][0]["type"] == "item_unit" and r["candidates"][0]["uom_id"] == "x-carton" and not r["issues"], r)
r = R_("4006381333931")
check("P102 ... and without an identifier it is the legacy code, never a guessed GTIN", r["candidates"][0]["id"] == "4006381333931" and "scan_heuristic_used" not in r["checks"], r)
REG.register("bin", "0108931234567897", "bin_old_01", legacy=True)
r = R_("0108931234567897")
check("P103 a legacy code that looks like a GS1 element string is never parsed as GS1", r["encoding"] == "plain" and r["candidates"][0]["id"] == "bin_old_01" and r["elements"] == {}, r)

# --- review round 1 (S1-S11, nits)
REG.register("item_unit", "123456789012", ("ib", "upc_legacy"), legacy=True)
DATA["item_barcode"]["123456789012"] = ("i_pcs", "H87")
r = R_("0123456789012", "]E0")
check("P104 S1: a 12-digit legacy code scanned as UPC-A through ]E0 (13 digits with a leading zero) resolves by padded digits",
      r["candidates"][0]["id"] == "123456789012" and not r["issues"], r)
check("P105 S1: two numeric legacy codes that differ only by leading zeros are one code (barcode_taken)",
      raises(REG.register, "bin", "0123456789012", "b", legacy=True) == "barcode_taken")
DATA["lots"][("i_kg", "2511047")] = "lot_numeric"
r1, r2 = R_("2511047", ctx=dict(item_id="i_kg")), R_("2511047")
check("P106 S2: a numeric lot code without an identifier falls through to the registry and context steps: with the task's item it resolves, without it lot_needs_item",
      r1["candidates"][0]["id"] == "lot_numeric" and r2["issues"] == ["lot_needs_item"], (r1, r2))
DATA["lots"][("i_pcs", "B11250101")] = "lot_datecoded"
check("P107 S3: a date-coded lot C11250101 trips the trace (it ends in a valid (11) date) when nothing proves the transport and the lot is unknown",
      reason("01" + G14 + "10C11250101") == "separator_suspect" and R_("]C1" + "01" + G14 + "10C11250101")["issues"] == ["gs1_invalid"])
rk = R_("]C1" + "01" + G14 + "10B11250101")
rg = R_("]C1" + "01" + G14 + GS + "10C11250101")
rw = resolve(dict(raw="]C1" + "01" + G14 + "10C11250101", decoder="wasm"), REG, DATA)
rc = resolve(dict(raw="]C1" + "01" + G14 + "10C11250101", confirmed_as_read=True), REG, DATA)
check("P108 S3: no stop when the value is an existing lot of the item (B11250101), when a GS elsewhere proves the transport, when the WebAssembly decoder read it, or when the person confirms it as read",
      rk["candidates"][0]["id"] == "lot_datecoded" and all(x["candidates"] and not x["issues"] for x in (rg, rw, rc)), (rk, rg, rw, rc))
R5 = Registry()
R5.register("bin", "R-01", "bin_r")
R5.retire("R-01")
R5.register("bin", "R-01X", "bin_r")
R5.retire("R-01X")
check("P109 S5: a bin changed from R-01 to R-01X may change back (the code returns to its owner); another bin cannot take R-01X",
      R5.register("bin", "R-01", "bin_r") == [] and R5.rows["R-01"]["type"] == "bin" and raises(R5.register, "bin", "R-01X", "bin_other") == "barcode_taken")
R5.register("handling_unit", "389312340000000005", "hu_s")
R5.retire("389312340000000005", months_ago=3)
r_early = raises(R5.delete_reservation, "389312340000000005")
R5.rows["389312340000000005"]["retired_months"] = 13
check("P110 S5: a retired SSCC cannot be released within barcode.sscc_reuse_months (12, unverified), and can after it",
      r_early == "barcode_reuse_period_running" and raises(R5.delete_reservation, "389312340000000005") is None and "389312340000000005" not in R5.rows)
check("P111 S8: the label rule: a lot code that fits (10) goes into GS1 data; LOT 2026/11 or a 21-character code is printed through its own barcode, which the creating command generates",
      lot_label("LOT-A1", G14)[1] == "]d2" + "01" + G14 + "10LOT-A1" and lot_label("LOT 2026/11", G14, "L-000042") == ("datamatrix", "L-000042")
      and raises(lot_label, "L" * 21, G14) == "lot_label_needs_barcode")
r = R_("]C1" + "01" + GC + "10LOTA" + GS + "21SN-0003")
check("P112 S10: (01)(10)(21) gives one serial candidate that carries the lot", len(r["candidates"]) == 1 and r["candidates"][0]["type"] == "serial"
      and (r["candidates"][0]["serial_code"], r["candidates"][0]["lot_code"]) == ("SN-0003", "LOTA"), r)
r = R_("https://e.com/01/" + G14 + "/10/A~B", "]Q1")
check("P113 nit 3: ~ in a Digital Link is a character, never the GS substitute (the lot A~B fails character set 82, nothing is split)",
      r["issues"] == ["gs1_invalid"] and r["details"] == dict(reason="format", ai="10"), r)
check("P114 nit 4: an unlisted identifier (]I0, ]L0) is plain data; ]I1 is a GTIN only with 14 digits",
      classify("]I0", "18931234567894") == ("plain", False) and classify("]L0", "123") == ("plain", False)
      and classify("]I1", "18931234567894") == ("gtin", False) and classify("]I1", "123456") == ("plain", False))
el, _ = parse_digital_link("https://e.com/00/01/" + G14)
check("P115 nit 5: a Digital Link path /00/01/{gtin} reads as (01) from the rightmost primary key", list(el) == ["01"], el)
check("P116 nit 14: generate gtin14 builds the case GTIN from the item's GTIN-13 and an indicator, with a new check digit",
      gtin14_from("8931234567897", 1) == "18931234567894" and key_valid(gtin14_from("8931234567897", 2)) and gtin14_from("8931234567897", 2)[0] == "2")
R6 = Registry()
SUP, OWN, NEW_ = "359012340000000018", "389312340000000012", "359012340000000025"
for code_ in (SUP, OWN, NEW_):
    assert key_valid(code_), code_
    R6.register("handling_unit", code_, "hu_" + code_[-3:])
R6.retire(SUP, months_ago=13)
R6.retire(OWN, months_ago=13)
R6.retire(NEW_, months_ago=2)
check("P118 review 2: the daily job releases a supplier's SSCC past the reuse period, keeps one retired two months ago, and never touches an SSCC under the company's own prefix",
      R6.run_sscc_cleanup(["8931234"]) == [SUP] and OWN in R6.rows and NEW_ in R6.rows and R6.register("handling_unit", SUP, "hu_new") == [])
PFX = {"8931234": dict(is_active=True)}                          # gs1_company_prefix rows of the company
check("P119 review 3: a prefix that holds only a retired SSCC cannot be deleted (gs1_prefix_in_use); a prefix with nothing under it can",
      raises(R6.delete_prefix, PFX, "8931234") == "gs1_prefix_in_use" and "8931234" in PFX
      and raises(R6.delete_prefix, dict(PFX, **{"7777777": dict(is_active=True)}), "7777777") is None)
PFX["8931234"]["is_active"] = False
R6.rows[OWN]["retired_months"] = 40
check("P120 review 3: after the prefix is deactivated it still counts as the company's own: the job leaves its retired SSCC alone",
      R6.run_sscc_cleanup(list(PFX)) == [] and OWN in R6.rows)
FMT = "{prefix}/{fiscal_year_code}/{counter:6}"
check("P117 S4: the default format with codes in the internal set passes; a branch code with a space, a '+' in a fiscal year code, a number over 48 characters or a format not starting with the prefix is numbering_barcode_invalid",
      numbering_barcode_problems(FMT, "PO", {"fiscal_year_code": ["FY2026"]}) == []
      and numbering_barcode_problems("{prefix}/{branch_code}/{counter:6}", "PO", {"branch_code": ["HCM 01"]}) == ["branch_code:HCM 01"]
      and numbering_barcode_problems(FMT, "PO", {"fiscal_year_code": ["2026+"]}) == ["fiscal_year_code:2026+"]
      and numbering_barcode_problems(FMT, "PO", {"fiscal_year_code": ["F" * 40]}) == ["length"]
      and numbering_barcode_problems("{fiscal_year_code}/{prefix}/{counter:6}", "PO", {"fiscal_year_code": ["FY"]}) == ["prefix_separator"])


# ======================================================================= D: database checks (--load)
if "--load" in sys.argv:
    import psycopg  # noqa: E402
    from load_all import load_all  # noqa: E402

    class FractionDumper(psycopg.adapt.Dumper):
        oid = psycopg.adapters.types["numeric"].oid
        def dump(self, obj):
            return str(D_(obj.numerator) / D_(obj.denominator)).encode()
    psycopg.adapters.register_dumper(F, FractionDumper)
    dsn = os.environ.get("ERPME_LAB_DSN", "host=127.0.0.1 port=5561 dbname=erpme_lab user=lab")
    n_tables = load_all(dsn, DOCS)
    check("D01 load_all.py loads every DDL file of design/ into one schema", n_tables > 200, n_tables)
    c = conn(); c.autocommit = True
    X = c.execute
    trg = sorted(r[0] for r in X("select tgname from pg_trigger where tgname like 'trg_%%_register'").fetchall())
    check("D02 the registry trigger is on item_barcode, bin, lot, serial_number, handling_unit and document",
          trg == sorted(["trg_item_barcode_register", "trg_bin_register", "trg_lot_register", "trg_serial_number_register",
                         "trg_handling_unit_register", "trg_document_register"]), trg)
    f_ = X("select gs1_check_digit_valid('08931234567897'), gs1_check_digit_valid('08931234567890'), gs1_check_digit_valid('389312340000000005'),"
           " barcode_normalize('8931234567897'), barcode_normalize('a-03-02'), barcode_normalize('96385074')").fetchone()
    check("D03 the database functions agree with the lab: check digits, normalization of GTIN-13, GTIN-8 and lower case",
          f_ == (True, False, True, "08931234567897", "A-03-02", "00000096385074"), f_)

    U = {}
    with c.transaction():
        for r_ in csv.DictReader(open(os.path.join(CAT, "units.csv"), encoding="utf-8")):
            U[r_["code"]] = uuid.uuid5(NS, f"uom:{r_['code']}")
            X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,%s,%s)",
              (U[r_["code"]], r_["code"], r_["name"], r_["quantity_kind"], r_["decimal_places"]))
        for r_ in csv.DictReader(open(os.path.join(CAT, "unit-conversions.csv"), encoding="utf-8")):
            X("insert into uom_conversion (id, from_uom_id, to_uom_id, numerator, denominator) values (%s,%s,%s,%s,%s)",
              (uuid.uuid5(NS, f"uom_conversion:{r_['from_code']}:{r_['to_code']}"), U[r_["from_code"]], U[r_["to_code"]], r_["numerator"], r_["denominator"]))
    I = {k: new() for k in ["user", "co", "ig", "vc", "itg", "w", "z", "b", "supp", "p_pcs", "i_pcs", "p_kg", "i_kg", "p_g", "i_g", "hut", "pu_ct"]}
    t = str(I["co"])[-8:].upper()
    B = '{"kind": "company_decision"}'
    X("insert into currency (code, minor_unit) values ('USD', 2) on conflict do nothing")
    X("insert into user_account (id, login, display_name, language, password_hash, created_at) values (%s,%s,'Lab user','en','x',now())", (I["user"], "u19" + t.lower()))
    X("insert into company (id,code,legal_name,company_currency,time_zone,localization_package,accounting_regime,valuation_area_level,fiscal_calendar_owner_id,default_language)"
      " values (%s,%s,'Co','USD','UTC','l10n_xx','xx','warehouse',%s,'en')", (I["co"], "C19-" + t, I["user"]))
    X("select set_config('erpme.company_id', %s, false)", (str(I["co"]),))
    U["x-carton"] = new()
    X("insert into uom (id, company_id, code, name, quantity_kind, decimal_places) values (%s,%s,'x-carton','Carton','count',0)", (U["x-carton"], I["co"]))
    X("insert into item_group (id, company_id, code, name, basis) values (%s,%s,'g','G',%s)", (I["ig"], I["co"], B))
    X("insert into valuation_class (id, company_id, code, name, basis) values (%s,%s,'v','V',%s)", (I["vc"], I["co"], B))
    X("insert into item_tax_group (id, company_id, code, name, basis) values (%s,%s,'s','S',%s)", (I["itg"], I["co"], B))

    def product(pk, ik, code, inv, tracking="none"):
        X("""insert into product (id, company_id, code, name, product_type, item_group_id, valuation_class_id, inventory_uom_id, purchase_uom_id, sales_uom_id,
             item_tax_group_id, tracking) values (%s,%s,%s,%s,'stock',%s,%s,%s,%s,%s,%s,%s)""",
          (I[pk], I["co"], code, code, I["ig"], I["vc"], U[inv], U[inv], U[inv], I["itg"], tracking))
        X("insert into item (id, company_id, product_id, code) values (%s,%s,%s,%s)", (I[ik], I["co"], I[pk], code))
    product("p_pcs", "i_pcs", "PCS", "H87", "lot")
    product("p_kg", "i_kg", "BULK-KG", "KGM")
    product("p_g", "i_g", "BULK-G", "GRM")
    X("insert into product_uom (id, company_id, product_id, inventory_uom_id, uom_id, numerator, denominator, is_exact) values (%s,%s,%s,%s,%s,24,1,true)",
      (I["pu_ct"], I["co"], I["p_pcs"], U["H87"], U["x-carton"]))
    with c.transaction():
        X("insert into warehouse (id, company_id, code, name, kind, default_bin_id) values (%s,%s,'W1','W1','physical',%s)", (I["w"], I["co"], I["b"]))
        X("insert into zone (id, company_id, warehouse_id, code, name) values (%s,%s,%s,'DEFAULT','Default')", (I["z"], I["co"], I["w"]))
        X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'DEFAULT','W1-DEFAULT','storage')", (I["b"], I["co"], I["w"], I["z"]))
    X("insert into partner (id, company_id, code, name, partner_kind, country) values (%s,%s,'SUPP','Supplier (sample)','organization','XX')", (I["supp"], I["co"]))
    X("insert into partner_role (company_id, partner_id, role) values (%s,%s,'supplier')", (I["co"], I["supp"]))
    X("insert into handling_unit_type (id, company_id, code, name) values (%s,%s,'PAL','Pallet')", (I["hut"], I["co"]))
    ib_cols = {r_[0] for r_ in X("select column_name from information_schema.columns where table_schema='erpme' and table_name='item_barcode'").fetchall()}

    def item_barcode(cx, item, unit, code, legacy=False):
        v = dict(company_id=I["co"], item_id=I[item], uom_id=U[unit], barcode=code, is_legacy_barcode=legacy)
        if "id" in ib_cols:                                         # the revised ADR-0056 gives item_barcode a surrogate key
            v = dict(id=new(), **v)
        cx.execute(f"insert into item_barcode ({', '.join(v)}) values ({', '.join(['%s'] * len(v))})", list(v.values()))

    def bin_(cx, code, barcode, legacy=False):
        cx.execute("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type, is_legacy_barcode) values (%s,%s,%s,%s,%s,%s,'storage',%s)",
                   (new(), I["co"], I["w"], I["z"], code, barcode, legacy))

    def X_bad(name, match, fn):
        def run(cx):
            cx.execute("select set_config('erpme.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, True, match)

    def X_good(name, fn):
        def run(cx):
            cx.execute("select set_config('erpme.company_id', %s, true)", (str(I["co"]),))
            fn(cx)
        expect(name, run, False)

    G_VAR_KG = "9893123456789" + str(check_digit("9893123456789"))
    G_VAR_G = "9893123456790" + str(check_digit("9893123456790"))
    item_barcode(c, "i_pcs", "H87", G14)
    item_barcode(c, "i_pcs", "x-carton", "18931234567894")
    item_barcode(c, "i_pcs", "H87", "I-0001")
    item_barcode(c, "i_kg", "KGM", G_VAR_KG)
    item_barcode(c, "i_g", "GRM", G_VAR_G)
    reg = dict(X("select barcode, barcode_type || '/' || encoding from barcode where company_id = %s", (I["co"],)).fetchall())
    check("D04 the trigger registers item barcodes (GTIN and internal) and the default bin, typed and encoded",
          reg == {G14: "item_unit/gtin", "18931234567894": "item_unit/gtin", "I-0001": "item_unit/internal", G_VAR_KG: "item_unit/gtin",
                  G_VAR_G: "item_unit/gtin", "W1-DEFAULT": "bin/internal"}, reg)
    X_bad("D05 a bin whose barcode equals an item barcode is refused by the registry's key (EC-121)", "barcode_taken", lambda cx: bin_(cx, "A-01", "I-0001"))
    X_bad("D06 ... and so is a bin carrying an item's GTIN", "ck_barcode_type_encoding", lambda cx: bin_(cx, "A-02", G14))
    X_bad("D07 a GTIN-13 not padded to 14 digits is barcode_not_normalized", "barcode_not_normalized", lambda cx: item_barcode(cx, "i_pcs", "H87", "4006381333931"))
    X_bad("D08 a GTIN-14 with a wrong check digit is barcode_format_invalid", "barcode_format_invalid", lambda cx: item_barcode(cx, "i_pcs", "H87", "04006381333932"))
    X_bad("D09 a lower-case bin barcode is barcode_not_normalized", "barcode_not_normalized", lambda cx: bin_(cx, "a-03", "w1-a03"))
    X_bad("D10 an SSCC on a bin is refused (a bin holds an internal code only)", "ck_barcode_type_encoding", lambda cx: bin_(cx, "A-04", "389312340000000005"))
    X_bad("D11 an internal code with a leading digit and letters fits no encoding", "ck_barcode_format", lambda cx: bin_(cx, "A-05", "1A-05"))
    X_good("D12 a handling unit with an SSCC registers as handling_unit / sscc",
           lambda cx: cx.execute("insert into handling_unit (id, company_id, code, barcode, handling_unit_type_id, warehouse_id, bin_id) values (%s,%s,'HU1','389312340000000005',%s,%s,%s)",
                                 (new(), I["co"], I["hut"], I["w"], I["b"])))
    check("D13 ... and the registry holds it", X("select barcode_type, encoding from barcode where barcode = '389312340000000005'").fetchone() == ("handling_unit", "sscc"))
    X("delete from item_barcode where barcode = 'I-0001'")
    row = X("select barcode_type, retired_type, retired_at is not null from barcode where barcode = 'I-0001'").fetchone()
    check("D14 a removed item barcode stays reserved: type internal, retired_type item_unit", row == ("internal", "item_unit", True), row)
    X_bad("D15 ... so a bin cannot take the code", "barcode_taken", lambda cx: bin_(cx, "A-06", "I-0001"))
    X("delete from barcode where company_id = %s and barcode = 'I-0001' and barcode_type = 'internal'", (I["co"],))   # DeleteBarcodeReservation
    X_good("D16 after DeleteBarcodeReservation a bin may take the code", lambda cx: bin_(cx, "A-06", "I-0001"))
    bid = new()
    X("insert into bin (id, company_id, warehouse_id, zone_id, code, barcode, bin_type) values (%s,%s,%s,%s,'B-01','B-01','storage')", (bid, I["co"], I["w"], I["z"]))
    X("update bin set barcode = 'B-01-NEW' where id = %s", (bid,))
    rows = dict(X("select barcode, barcode_type || '/' || coalesce(retired_type, '') from barcode where barcode in ('B-01', 'B-01-NEW')").fetchall())
    check("D17 a changed bin barcode retires the old one (EC-125) and registers the new one", rows == {"B-01": "internal/bin", "B-01-NEW": "bin/"}, rows)
    X("update bin set barcode = 'B-01' where id = %s", (bid,))
    rows = dict(X("select barcode, barcode_type || '/' || coalesce(retired_type, '') from barcode where barcode in ('B-01', 'B-01-NEW')").fetchall())
    check("D17b S5: the bin changes back to B-01: the trigger revives its own retired row, and B-01-NEW is now the retired one", rows == {"B-01": "bin/", "B-01-NEW": "internal/bin"}, rows)
    X_good("D18 S8: a lot code with a space and a slash is kept as it comes", lambda cx: cx.execute(
        "insert into lot (id, company_id, item_id, code, barcode) values (%s,%s,%s,'LOT 2026/11','L-000099')", (new(), I["co"], I["i_pcs"])))
    X_good("D19 S8: a serial code of 25 characters is kept as it comes", lambda cx: cx.execute(
        "insert into serial_number (id, company_id, item_id, code) values (%s,%s,%s,%s)", (new(), I["co"], I["i_pcs"], "S" * 25)))
    X("insert into lot (id, company_id, item_id, code, barcode) values (%s,%s,%s,'LOT-Z9','L-000001')", (new(), I["co"], I["i_pcs"]))
    X("insert into serial_number (id, company_id, item_id, code, barcode) values (%s,%s,%s,'SN-0001','SN-000001')", (new(), I["co"], I["i_kg"]))
    X("insert into lot (id, company_id, item_id, code) values (%s,%s,%s,'LOT-NOLABEL')", (new(), I["co"], I["i_pcs"]))
    rows = dict(X("select barcode, barcode_type from barcode where barcode in ('L-000001', 'SN-000001')").fetchall())
    n_reg = X("select count(*) from barcode where company_id = %s", (I["co"],)).fetchone()[0]
    check("D20 lot and serial label codes register as lot and serial; a lot without a label code registers nothing",
          rows == {"L-000001": "lot", "SN-000001": "serial"} and n_reg == 12, (rows, n_reg))

    def doc(cx, dtype, number=None, barcoded=False, state="approved"):
        d = new()
        cx.execute("insert into document (id, company_id, document_type, state, version, created_by_user_id, partner_id, number, is_barcoded, document_date, recorded_at)"
                   " values (%s,%s,%s,%s,1,%s,%s,%s,%s,'2026-11-15','2026-11-15T08:00:00Z')", (d, I["co"], dtype, state, I["user"], I["supp"], number, barcoded))
        return d
    d_po = doc(c, "purchase_order", "PO/FY2026/000001", True)
    d_draft = doc(c, "goods_receipt", None, True, "draft")
    check("D21 a numbered barcoded document registers its number as type document; an unnumbered one registers nothing yet",
          X("select barcode_type from barcode where barcode = 'PO/FY2026/000001'").fetchone() == ("document",)
          and X("select count(*) from barcode where barcode_type = 'document'").fetchone()[0] == 1)
    X("update document set number = 'gr/fy2026/000001' where id = %s", (d_draft,))
    check("D22 numbering a barcoded draft registers the number in upper case",
          X("select barcode_type from barcode where barcode = 'GR/FY2026/000001'").fetchone() == ("document",))
    X_bad("D23 a second barcoded document type with the same number is refused by the registry", "barcode_taken",
          lambda cx: doc(cx, "sales_order", "PO/FY2026/000001", True))
    X_good("D24 a document type that is not barcoded may repeat the number (uniqueness per type, ADR-0009)",
           lambda cx: doc(cx, "journal_entry", "PO/FY2026/000001", False))

    # ---- a receipt scan capturing lot and expiry (EC-119), then variable measures (EC-122)
    raw = "]C1" + "01" + "18931234567894" + "17" + "261100" + "10" + "LOT-A1"
    ident, body = transport(raw)
    el = parse_element_string(body)
    btype = X("select barcode_type from barcode where company_id = %s and barcode = %s", (I["co"], el["01"]["raw"])).fetchone()[0]
    item_id, uom_id = X("select item_id, uom_id from item_barcode where company_id = %s and barcode = %s", (I["co"], el["01"]["raw"])).fetchone()
    lot_new = capture_lot(dict(lot_code=el["10"]["raw"], expiry_date=el["17"]["value"]))
    unit_code = X("select code from uom where id = %s", (uom_id,)).fetchone()[0]
    cap = convert_capture("i_pcs", 1, unit_code)
    lot_id = new()

    def ins(cx, table, **v):
        cx.execute(f"insert into {table} ({', '.join(v)}) values ({', '.join(['%s'] * len(v))})", list(v.values()))
        return v.get("id")
    with c.transaction():                                         # one receipt command: the new lot and the line
        ins(c, "lot", id=lot_id, company_id=I["co"], item_id=item_id, code=lot_new["code"], expiry_date=lot_new["expiry_date"])
        d_gr = new()
        ins(c, "document", id=d_gr, company_id=I["co"], document_type="goods_receipt", state="posted", version=1, created_by_user_id=I["user"],
            partner_id=I["supp"], document_date="2026-11-15", recorded_at="2026-11-15T08:00:00Z", posted_at="2026-11-15T08:00:00Z")
        ins(c, "goods_receipt", id=d_gr, company_id=I["co"], partner_id=I["supp"], partner_name="Supplier (sample)", document_date="2026-11-15", posting_date="2026-11-15")
        gl1 = ins(c, "goods_receipt_line", id=new(), company_id=I["co"], goods_receipt_id=d_gr, line_number=1, item_id=item_id, quantity=cap["quantity"],
                  uom_id=uom_id, uom_numerator=cap["uom_numerator"], uom_denominator=cap["uom_denominator"], uom_factor_source=cap["uom_factor_source"],
                  inventory_quantity=cap["inventory_quantity"], warehouse_id=I["w"], lot_id=lot_id)
    got = X("""select l.code, l.expiry_date, g.quantity, u.code, g.uom_numerator, g.uom_denominator, g.uom_factor_source, g.inventory_quantity
               from goods_receipt_line g join lot l on l.id = g.lot_id join uom u on u.id = g.uom_id where g.id = %s""", (gl1,)).fetchone()
    check("D25 a receipt scan of a carton label (01)(17 day 00)(10): the registry says item_unit, the GTIN gives the carton, the lot is created with expiry 2026-11-30, and 1 carton is received as 24 pieces at 24/1 product (ADR-0056)",
          btype == "item_unit" and (got[0], got[1], int(got[2]), got[3], got[4], got[5], got[6], int(got[7])) == ("LOT-A1", dt.date(2026, 11, 30), 1, "x-carton", 24, 1, "product", 24), got)
    stored = dict(expiry_date=X("select expiry_date from lot where id = %s", (lot_id,)).fetchone()[0])
    el2 = parse_element_string("01" + "18931234567894" + "17" + "261231" + "10" + "LOT-A1")
    check("D26 a later scan of the same lot with another expiry is gs1_capture_conflict against the stored lot",
          raises(capture_lot, dict(lot_code=el2["10"]["raw"], expiry_date=el2["17"]["value"]), stored) == "gs1_capture_conflict")
    lines = []
    for n_, (gt, item_) in enumerate(((G_VAR_KG, "i_kg"), (G_VAR_G, "i_g")), start=2):
        el3 = parse_element_string("01" + gt + "3102001156")
        q, unit = el3["3102"]["value"]
        cap3 = convert_capture(item_, F(str(q)), unit)
        lines.append(ins(c, "goods_receipt_line", id=new(), company_id=I["co"], goods_receipt_id=d_gr, line_number=n_, item_id=I[item_], quantity=cap3["quantity"],
                         uom_id=U[cap3["uom_id"]], uom_numerator=cap3["uom_numerator"], uom_denominator=cap3["uom_denominator"],
                         uom_factor_source=cap3["uom_factor_source"], inventory_quantity=cap3["inventory_quantity"], warehouse_id=I["w"]))
    got = X("""select g.quantity::text, u.code, g.uom_numerator, g.uom_factor_source, g.inventory_quantity::text from goods_receipt_line g
               join uom u on u.id = g.uom_id where g.id = any(%s) order by g.line_number""", (lines,)).fetchall()
    check("D27 variable measure 3102 001156: 11.56 kg into the kg item (identity) and into the gram item (entered in KGM, 1000/1 global, 11560 g); the database's unit block accepts both",
          got == [("11.560000", "KGM", 1, "identity", "11.560000"), ("11.560000", "KGM", 1000, "global", "11560.000000")], got)
    X_bad("D28 the ADR-0056 check still guards a captured line: 11.56 kg recorded as 11 g is refused", "ck_goods_receipt_line_uom_quantity",
          lambda cx: ins(cx, "goods_receipt_line", id=new(), company_id=I["co"], goods_receipt_id=d_gr, line_number=9, item_id=I["i_g"], quantity=F("11.56"),
                         uom_id=U["KGM"], uom_numerator=1000, uom_denominator=1, uom_factor_source="global", inventory_quantity=11, warehouse_id=I["w"]))
    # ---- legacy codes (rule 8, EC-128)
    bin_(c, "OLD-1", "123456", legacy=True)
    check("D29 an old numeric bin label loads as a legacy code: type bin, encoding internal, is_legacy",
          X("select barcode_type, encoding, is_legacy from barcode where barcode = '123456'").fetchone() == ("bin", "internal", True))
    X_bad("D30 the same kind of numeric code without is_legacy_barcode is refused", "ck_barcode_format", lambda cx: bin_(cx, "OLD-2", "123457"))
    item_barcode(c, "i_pcs", "x-carton", "4006381333931", legacy=True)
    check("D31 a legacy 13-digit item code is registered as it is, never padded to a GTIN",
          X("select barcode_type, encoding, is_legacy from barcode where barcode = '4006381333931'").fetchone() == ("item_unit", "internal", True)
          and X("select count(*) from barcode where barcode = '04006381333931'").fetchone()[0] == 0)
    X_bad("D32 a GTIN equal to that legacy code padded to 14 digits is barcode_taken", "barcode_taken",
          lambda cx: item_barcode(cx, "i_kg", "KGM", "04006381333931"))
    X_bad("D33 a legacy code equal to a registered GTIN padded to 14 digits is barcode_taken", "barcode_taken",
          lambda cx: item_barcode(cx, "i_kg", "KGM", "8931234567897", legacy=True))
    X_bad("D34 a legacy code is stored in upper case", "barcode_not_normalized", lambda cx: bin_(cx, "OLD-3", "ab-1", legacy=True))
    X_good("D35 a handling unit of the old system keeps its numeric label as a legacy code",
           lambda cx: cx.execute("insert into handling_unit (id, company_id, code, barcode, is_legacy_barcode, handling_unit_type_id, warehouse_id, bin_id)"
                                 " values (%s,%s,'HU-OLD','000777',true,%s,%s,%s)", (new(), I["co"], I["hut"], I["w"], I["b"])))
    X_bad("D36 S1: two numeric legacy codes that differ only by leading zeros are refused by the padded index", "barcode_taken",
          lambda cx: bin_(cx, "OLD-4", "0123456", legacy=True))
    X_bad("D37 nit 2: is_legacy_barcode never changes", "is_legacy_barcode", lambda cx: cx.execute("update bin set is_legacy_barcode = false where barcode = '123456'"))
    X_bad("D38 S4: is_barcoded of a document never changes", "immutable", lambda cx: cx.execute("update document set is_barcoded = false where id = %s", (d_po,)))
    # S5: UpdateItemBarcode moves a barcode to another item; a barcode deleted and re-created on its own item comes back
    X("update item_barcode set item_id = %s, uom_id = %s where barcode = %s", (I["i_g"], U["GRM"], G14))
    check("D39 S5: moving an item barcode to another item and unit keeps its registry row as it is",
          X("select barcode_type, retired_type from barcode where barcode = %s", (G14,)).fetchone() == ("item_unit", None)
          and X("select item_id from item_barcode where barcode = %s", (G14,)).fetchone()[0] == I["i_g"])
    X("delete from item_barcode where barcode = %s", (G14,))
    X_bad("D40 S5: another item cannot take the deleted barcode", "barcode_taken", lambda cx: item_barcode(cx, "i_kg", "KGM", G14))
    X_good("D41 S5: the item it was deleted from takes it back (the trigger revives the row)", lambda cx: item_barcode(cx, "i_g", "GRM", G14))
    check("D42 ... and the row is item_unit again, with no retired owner", X("select barcode_type, retired_owner_id from barcode where barcode = %s", (G14,)).fetchone() == ("item_unit", None))
    # S11: GS1 company prefixes
    X("insert into gs1_company_prefix (id, company_id, prefix, is_generation_prefix) values (%s,%s,'8931234',true)", (new(), I["co"]))
    X_good("D43 S11: a second prefix may be added beside it", lambda cx: cx.execute(
        "insert into gs1_company_prefix (id, company_id, prefix) values (%s,%s,'893987654')", (new(), I["co"])))
    X_bad("D44 S11: only one prefix generates", "ux_gs1_company_prefix_generation", lambda cx: cx.execute(
        "update gs1_company_prefix set is_generation_prefix = true where prefix = '893987654'"))
    X_bad("D45 S11: a prefix is digits", "ck_gs1_company_prefix_prefix", lambda cx: cx.execute(
        "insert into gs1_company_prefix (id, company_id, prefix) values (%s,%s,'89A123')", (new(), I["co"])))
    X_bad("D46 S11: a nine-digit prefix has 1,000 item references, so the reference stops at 1000", "ck_gs1_company_prefix_reference", lambda cx: cx.execute(
        "update gs1_company_prefix set next_item_reference = 1001 where prefix = '893987654'"))
    X_bad("D46b review 2: a prefix that starts another of the company's prefixes is refused by the exclusion constraint", "ex_gs1_company_prefix_overlap", lambda cx: cx.execute(
        "insert into gs1_company_prefix (id, company_id, prefix) values (%s,%s,'8931')", (new(), I["co"])))
    X_bad("D46c review 2: ... and so is one that another starts", "ex_gs1_company_prefix_overlap", lambda cx: cx.execute(
        "insert into gs1_company_prefix (id, company_id, prefix) values (%s,%s,'89312345')", (new(), I["co"])))
    X_bad("D46d review 2: an empty lot code is refused", "ck_lot_code_not_empty", lambda cx: cx.execute(
        "insert into lot (id, company_id, item_id, code) values (%s,%s,%s,'')", (new(), I["co"], I["i_pcs"])))
    X_bad("D46e review 2: an empty serial code is refused", "ck_serial_number_code_not_empty", lambda cx: cx.execute(
        "insert into serial_number (id, company_id, item_id, code) values (%s,%s,%s,'')", (new(), I["co"], I["i_pcs"])))
    v624 = X("""select a.prefix, b.prefix from gs1_company_prefix a join gs1_company_prefix b on a.company_id = b.company_id and a.id <> b.id
                 and b.prefix like a.prefix || '%%'""").fetchall()
    check("D46f INV-624 holds: no two prefixes of a company overlap", v624 == [], v624)
    X_bad("D46g review 3: the generation prefix must be active", "ck_gs1_company_prefix_generation_active", lambda cx: cx.execute(
        "update gs1_company_prefix set is_active = false where prefix = '8931234'"))
    X_good("D46h review 3: a prefix that generates nothing is deactivated, not deleted", lambda cx: cx.execute(
        "update gs1_company_prefix set is_active = false where prefix = '893987654'"))
    import threading
    import time
    p1, p2 = conn(), conn()
    for cx_ in (p1, p2):
        cx_.execute("set transaction isolation level repeatable read")
    p1.execute("insert into gs1_company_prefix (id, company_id, prefix) values (%s,%s,'5013')", (new(), I["co"]))
    pres = {}

    def second_prefix():
        try:
            p2.execute("insert into gs1_company_prefix (id, company_id, prefix) values (%s,%s,'501334')", (new(), I["co"]))
            p2.commit()
            pres["ok"] = True
        except Exception as e:  # noqa: BLE001
            pres["err"] = str(e).splitlines()[0]
            p2.rollback()
    th_ = threading.Thread(target=second_prefix)
    th_.start()
    time.sleep(1.5)
    p1.commit()
    th_.join(15)
    n_ = X("select count(*) from gs1_company_prefix where company_id = %s and prefix in ('5013', '501334')", (I["co"],)).fetchone()[0]
    check("D46i review 3: two overlapping prefixes inserted at once at REPEATABLE READ: the exclusion constraint lets only one commit",
          "ok" not in pres and n_ == 1, (pres, n_))
    p1.close()
    p2.close()
    # B1: the padded collision from two connections at once
    import threading
    import time
    base = "500011263792"
    leg = base + str(check_digit(base))
    c1, c2 = conn(), conn()
    for cx_ in (c1, c2):
        cx_.execute("select set_config('erpme.company_id', %s, false)", (str(I["co"]),))
    item_barcode(c1, "i_pcs", "H87", leg, legacy=True)            # not committed yet
    res = {}

    def second():
        try:
            item_barcode(c2, "i_kg", "KGM", "0" + leg)
            c2.commit()
            res["ok"] = True
        except Exception as e:  # noqa: BLE001
            res["err"] = str(e).splitlines()[0]
            c2.rollback()
    th = threading.Thread(target=second)
    th.start()
    time.sleep(1.5)
    waited = th.is_alive()
    c1.commit()
    th.join(15)
    both = X("select count(*) from barcode where barcode in (%s, %s)", (leg, "0" + leg)).fetchone()[0]
    check("D47 B1: a legacy code and the GTIN of its padded digits inserted from two connections at once: the second waits, then fails with barcode_taken; one row stays",
          waited and "barcode_taken" in res.get("err", "") and both == 1, (waited, res, both))
    c1.close()
    c2.close()
    INV620 = """
      with owners as (
        select company_id, barcode, 'item_unit' as t, is_legacy_barcode as legacy from item_barcode
        union all select company_id, barcode, 'bin', is_legacy_barcode from bin
        union all select company_id, barcode, 'handling_unit', is_legacy_barcode from handling_unit
        union all select company_id, barcode, 'lot', false from lot where barcode is not null
        union all select company_id, barcode, 'serial', false from serial_number where barcode is not null
        union all select company_id, upper(number), 'document', false from document where is_barcoded and number is not null)
      select 'missing', o.barcode from owners o left join barcode b on b.company_id = o.company_id and b.barcode = o.barcode and b.barcode_type = o.t
         and b.is_legacy = o.legacy
       where b.barcode is null
      union all
      select 'orphan', b.barcode from barcode b left join owners o on o.company_id = b.company_id and o.barcode = b.barcode and o.t = b.barcode_type
       where b.barcode_type <> 'internal' and o.barcode is null"""
    v620 = X(INV620).fetchall()
    check("D48 INV-620 holds on everything written above: no typed barcode without its registry row of the same legacy flag, no registry row without its owner", v620 == [], v620)
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
