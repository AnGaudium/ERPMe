#!/usr/bin/env python3
"""Tool 4 (S3): lint a compiled spec (docs/design/compiled-spec-template.md) against the rule index and the module
scope of nfdocs.module_scope.

Usage: doc_lint.py SPEC.md [SPEC-2.md ...] --module M [--index CSV] [--index-commit SHA] [--docs DIR]
                   [--partial] [--allow-process] [--strict] [--json]

Stance: the lint connects the trace table to the rule bodies and closes the known shortcuts. Whether a statement
says what its sources say is the different-model spot check of the template; the lint prints what that check and
the chief architect must read: the REVIEW LIST (every Conflicts entry, counted per kind), the SUPERSEDED RULES and
the stable-key mismatches.

Output. Line 1: `LINT PASS findings=0`, `LINT FAIL findings=N` or, with --partial on an incomplete chunk set,
`LINT PARTIAL findings=0 deferred=N`. Line 2: `measured: ...` (units, rules, primary rules, notes, sections, tables,
R-numbers, trace rows, files). Then one finding per line (`L<n> <file>:<line>: <message>`), warnings (`W2`), the
deferred counts, sizes, the identifier retention and size ratio per file, and the lists. With --json: line 1, then
one line of JSON. Exit 0 on PASS and PARTIAL, 1 on FAIL, 2 on bad input.

Refused with exit 2: a missing or repeated file; a module without units; `--module cross` and any module that is
primary for no rule (their units are compiled in their primary modules); `process` without --allow-process.

Before every check: invisible characters (zero-width, joiners, soft hyphen, bidi marks, variation selectors) are
removed and no-break and other Unicode spaces become a space; HTML comments (count markers kept), ``` and ~~~
fences, and indented code blocks (4 spaces or a tab after a blank line, outside a list) are blanked. Nothing inside
them counts for any check, front matter included.

Several files are the chunks of one module: every module-level check runs over all of them together.

Checks:
  L0  front matter: `Module:` (equal to --module), `Chunk:` (`whole` or `k of n`), `Source ADRs:`, `Build step(s):`,
      `Generated from index:` and `Compiled by:`.
      - Index: `Generated from index` (7 or more hex digits) must be the last commit of the index file, or
        --index-commit, which must be a commit of the repository; the index file must equal its version in that
        commit. An index that differs, or a commit that cannot be read, is a finding.
      - Chunks: one file is `whole` or `1 of 1`; several files are `k of n` with one n, each k once, 1..n all given.
        An incomplete set (a lone chunk of n > 1) is a finding and prints a NOTICE; with --partial the module-level
        checks that need the other chunks are counted as `deferred`, not reported, and line 1 says `LINT PARTIAL`.
      - Sections: the template's eleven `##` sections, in its order, no others; every file has `## Purpose` and
        `## Trace`, all eleven appear across the chunks. Every section present has content (a `###` heading is not
        content). `None` is allowed for Commands and queries, Invariants, Edge cases, Settings and UI annotations
        with a reason (`None (reason)` or `None: reason`), bare for Conflicts and Proposed (not law); for Entities
        and tables only when the module owns no table; never for Purpose, Rules and Trace.
  L1  trace and rule bodies.
      - Every rule, note and Decision text ID of the module appears in the `## Trace` table. The trace table and the
        set of R-numbers are not empty.
      - An R-number is defined by `R<n>.` (at most 3 spaces of indent, optional list marker or bold) in `## Rules`
        or `## Proposed (not law)`, outside a `Reads` paragraph; it runs to the next blank line. It is defined once
        in the module's files.
      - Statement (the text before `Source:`): 12 or more letters and digits after markup, tags and entities are
        removed; 2 or more distinct words (3 letters or more) that occur in the ADRs; no placeholder (`TBD`, `TODO`,
        `FIXME`, `to be compiled|written|defined|added|done|filled`, `see|per|as in|follows the source`, `as
        stated|written|given in the source`, `lorem ipsum`) outside backticks; it repeats no other.
      - `Source:` is required. Its IDs (`ADR-nnnn.Rk`, `.Nj` after an ID for a note of it) exist in the index (L7)
        and are units of the module (L7).
      - Source/trace agreement, both directions, across chunks: a unit traced to R-n is in the Source of R-n, and a
        unit in the Source of R-n is traced to R-n. One exception: an ID that supersedes a unit of R-n (index
        `superseded_by`) may stand in its Source without a trace row, also when it is another module's unit (L10).
      - `Where` of a rule: one or more defined R-numbers (`R3`, `R3-R7`, `R50a-R50e`; `R50` means `R50a`..), or
        `ref:` when the module is not primary for it (template rule 6). A heading may be added, never alone.
      - `Where` of a note: R-numbers, `ref:`, or `not applicable: <reason>` (the whole cell). A heading alone is
        refused (a note is folded into its rule's R-number).
      - `Where` of a Decision text unit (`.D*`, `.W`): also an existing heading of the spec (any chunk).
      - Any other `Where` part, a heading that does not exist, `Reads` and an empty cell are findings.
      - `ref: ADR-nnnn.Rk` is the unit's own ID, its parent rule's ID or an ID the unit's index row cross-references.
        `ref: <module> R-<n>` names a primary module of the unit (so `process` and `cross` only when primary); when
        that module's compiled spec lies beside the linted file (`<module>.md` or `<module>-<k>.md`), R-n is defined
        there and its Source holds the unit's ID.
      - At most 15% of the module's units are `not applicable`.
      - Coverage: the rule units mapped to an R-number whose Source cites them, counting at most 4 IDs per
        R-number, are 60% or more of the rule units not traced as `ref:`.
      - A Source cell may carry the unit's `#<stable_key>` (index column); a mismatch is warning W2 and is listed
        after the REVIEW LIST (--strict makes it a finding).
  L2  every table the module owns and every catalog row it owns (module_scope `owned_rows`) is backticked in the
      body outside `Reads` paragraphs and the trace table;
  L3  a line citing a rule of a proposed ADR (`ADR-0070.R12`, `ADR-0070 rule 12`, `ADR-0070, rule 12`, `rule 12 of
      ADR-0070`, `rule 12 in ADR-0070`, `ADR-0070 (rule 12)`, `ADR 0070 rule 12`, `ADR-0070 §12`, `Rule`, `rules 12
      through 14`) is under `## Proposed (not law)` or carries `[proposed]`; a line citing only accepted rules
      carries neither; a proposed unit's R-numbers are defined under `## Proposed (not law)` or carry `[proposed]`,
      an accepted unit's R-numbers are defined under `## Rules` without `[proposed]`; a proposed Decision text unit
      names only headings of `## Proposed (not law)`;
  L4  no typed count: a number (digits, number words from two, `twenty-one`, `a dozen`, Roman numerals of I, V, X)
      before a counted noun, up to three words between, or after it (`Tables owned: 10`, `Tables owned — 10`,
      `Owned tables (10)`), glued to it (`16tables`, `16-table`), or in a table row (`| ... tables | 16 |`,
      `| 16 | owned tables |`), is a finding. Bold, italics, backticks, links, tags and `&nbsp;` are removed first.
      `one` is not a count; citations (`rule 15 note`, `7 of rule`, `INV-12`) and `at most|at least|up to|more
      than|fewer than|less than` thresholds pass; `exactly` and `only` do not.
      `<!-- count:KIND -->N<!-- /count -->` is recomputed (tables, rules, catalog-rows, settings; also notes,
      sections, columns, invariants, edge-cases);
  L5  `## Conflicts`: every line is an entry, its continuation, a `###` heading, a blank line or the single line
      `None`. An entry is `CONFLICT <id>: <reason>`, `FALSE-POSITIVE <id>: <reason>` or `OPEN <id>: <text>`; a list
      marker, bold, backticks, `CONFLICT: <id>` and a table row `| CONFLICT | <id> | <reason> |` are read as
      entries; any other line, and an entry line outside `## Conflicts`, is a finding.
      - Every ID is a unit of the module; one ID has entries of one kind.
      - A CONFLICT or FALSE-POSITIVE reason has 25 characters or more and 4 or more distinct words (3 letters or
        more) that occur in the ADRs; one reason, or one more than 0.8 similar, serves at most 3 entries of its kind.
      - OPEN quotes, in double quotes, 20 or more characters of an unchecked entry of docs/open-questions.md (the
        file numbers no questions; an `OQ-nnn` counts only when an unchecked entry starts with it); an
        `open-questions.md#anchor` must be a heading of that file.
      - FALSE-POSITIVE is for conflict-flagged notes only; an ID without flag, marker or supersession may be
        CONFLICT or OPEN.
      - Required: every unit with a CONFLICT marker (CONFLICT or OPEN); every conflict-flagged note (its own entry,
        the parent's does not serve); every note whose relation is `supersedes` or `superseded-by` (CONFLICT naming
        the governing text, an ADR unit ID or R-number, or OPEN, on the note or its parent rule; FALSE-POSITIVE is
        refused) unless its Where is `ref:`;
  L6  each file is within the hard budget (16,000 tokens, bytes / 3.5); sizes per `## ` section are reported;
  L7  every ID in the trace table and in a `Source:` exists in the index and is a unit of the module;
  L8  a cross-module reference `<module> R-<n>` (template rule 6) names a module and a numeric rule; `R-scrap`, a bare
      `R-3` and `nosuch R-1` are findings; a backticked `<word> ADR-nnnn` must name a module;
  L9  every setting key referenced by the module's units is backticked in the body (a `Reads` paragraph serves for
      a key the module does not own);
  L10 every rule of the module that another unit supersedes (index `superseded_by`) or whose text says it is
      superseded has, unless its Where is `ref:`, an OPEN entry or a CONFLICT that names a superseding ID (any ADR
      unit ID or R-number when the index names none); with a CONFLICT, the named superseding ID is in the Source of
      every R-number the rule is traced to. Every such rule is printed under SUPERSEDED RULES for the spot check;
  L11 identifier retention: a source rule (not superseded, no superseding note) whose text holds 3 or more distinct
      identifiers in backticks, traced to R-numbers whose statements hold none of them in backticks, is a finding.
      An identifier is a code span that is one name of 4 or more characters (`inspection_lot`, `quality.deviation`).
      Per file the lint prints the share of source rule identifiers kept and statement bytes / source rule bytes.
"""

import argparse
import difflib
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfdocs  # noqa: E402
import build_index  # noqa: E402

SECTIONS = ["Purpose", "Entities and tables", "Commands and queries", "Rules", "Invariants", "Edge cases", "Settings",
            "UI annotations", "Conflicts", "Proposed (not law)", "Trace"]
PER_FILE_SECTIONS = ("Purpose", "Trace")
PROPOSED_HEADING = "Proposed (not law)"
NONE_WITH_REASON = ("Commands and queries", "Invariants", "Edge cases", "Settings", "UI annotations")
NONE_BARE = ("Conflicts", PROPOSED_HEADING)
FRONT_FIELDS = ["Module", "Chunk", "Source ADRs", "Build step(s)", "Generated from index", "Compiled by"]
MIN_REASON = 25             # characters of a CONFLICT or FALSE-POSITIVE reason
MIN_REASON_WORDS = 4        # distinct ADR-vocabulary words in a reason
MIN_STATEMENT_CHARS = 12    # letters and digits of an R-number statement, markup removed
MIN_STATEMENT_WORDS = 2     # distinct ADR-vocabulary words in a statement
MAX_REASON_REUSE = 3
REASON_SIMILARITY = 0.8
MIN_COVERAGE = 0.60
MAX_IDS_PER_R = 4
MAX_NA_SHARE = 0.15
MIN_QUOTE = 20              # characters of an open question quoted by an OPEN entry
RETENTION_MIN_IDS = 3       # L11: a source rule with this many identifiers and none kept is a finding
IDENT_MIN_LEN = 4

INVISIBLE_RE = re.compile("[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180e\u200b-\u200f\u202a-\u202e"
                          "\u2060-\u206f\ufe00-\ufe0f\ufeff\U000e0000-\U000e007f]")
SPACE_RE = re.compile("[\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]")

UNIT_ID_RE = re.compile(r"ADR-\d{4}\.(?:L\d+\.)?(?:R\d+[a-z]?|D\d+|W\d*|[A-Z]\d*)(?:\.N\d+)?")
COUNT_RE = re.compile(r"<!--\s*count:([\w-]+)\s*-->\s*(\d+)\s*<!--\s*/count\s*-->")
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
UNITS = "two three four five six seven eight nine".split()
NUMBER_WORDS = UNITS + ("ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen hundred "
                        "dozen").split() + TENS
NUM = (r"(?:\d[\d,]*|(?:" + "|".join(TENS) + r")-(?:one|" + "|".join(UNITS) + r")|(?:a\s+)?(?:" +
       "|".join(NUMBER_WORDS) + r"))")
NOUNS = r"(?:tables?|rules?|columns?|settings?|commands?|queries|query|notes?|invariants?|edge cases?|modules?|" \
        r"catalog rows?|events?|chunks?)"
PLURAL_NOUNS = r"(?:tables|rules|columns|settings|commands|queries|invariants|edge cases|modules|catalog rows|" \
               r"events|chunks)"
COUNT_BEFORE_RE = re.compile(r"(?<![\w.\-/])(" + NUM + r")\s+(?!of\b|to\b)(?:[^\s|:;.()]+\s+){0,3}?" + NOUNS +
                             r"\b(?![-/]|\.\w)(?!\s*\(?\d)", re.I)
# 'rule 3' and 'note (2)' are citations, 'setting-presets.csv' is a name: not counts
ROMAN_RE = re.compile(r"(?<![\w.\-/])(?=[IVX]{2,}\s)X{0,3}(?:IX|IV|V?I{0,3})\s+" + NOUNS + r"\b", re.I)
COUNT_AFTER_RE = re.compile(r"\b(?!notes?\b)" + NOUNS + r"(?:\s+[A-Za-z]\w*)?(?:\s*[:=—]\s*|\s+[–-]\s+)(" + NUM +
                            r")\b", re.I)   # not 'Note: two', not 'rules 22–23'
COUNT_PAREN_RE = re.compile(r"\b" + PLURAL_NOUNS + r"(?:\s+[A-Za-z]\w*)?\s*\(\s*(" + NUM + r")\s*\)", re.I)
COUNT_GLUED_RE = re.compile(r"(?<![\w.\-/])\d+" + NOUNS + r"\b", re.I)
COUNT_CELL_RE = re.compile(r"\|[^|]*\b" + NOUNS + r"\b[^|]*\|\s*(" + NUM + r")\s*\|", re.I)
COUNT_CELL_REV_RE = re.compile(r"\|\s*(" + NUM + r")\s*\|\s*(?:[\w-]+\s+){0,2}" + NOUNS + r"\s*(?=\|)", re.I)
CITATION_WORDS = {"rule", "rules", "step", "steps", "phase", "layer", "layers", "section", "sections", "class", "level",
                  "floor", "round", "pass", "finding", "item", "items", "note", "notes", "chunk", "part", "version",
                  "wave", "principle", "spec", "stage", "page", "line", "lines", "s"}
THRESHOLD_RE = re.compile(r"(?:at most|at least|up to|more than|fewer than|less than)\s*$", re.I)
XREF_R_RE = re.compile(r"(?:(?<![\w-])([A-Za-z_][\w]*)\s+)?(?<![\w-])R-([\w-]*)")
XREF_ADR_RE = re.compile(r"`([a-z][a-z0-9_]*)`?\s+`?ADR-\d{4}")
WHERE_R_RE = re.compile(r"^R(\d+)([a-z]?)(?:\s*[-–]\s*R?(\d+)([a-z]?))?$")
REF_RE = re.compile(r"^ref:\s*(?:([a-z][a-z0-9_]*)\s+R-(\d+[a-z]?)|(" + UNIT_ID_RE.pattern + r"))$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
RULE_DEF_RE = re.compile(r"^ {0,3}(?:[-*+]\s+)?\*{0,2}R(\d+[a-z]?)\*{0,2}\.\*{0,2}(?:\s+(.*))?$")
READS_RE = re.compile(r"^\s*(?:[-*+]\s+)?[*_]*Reads\b")
SOURCE_SPLIT_RE = re.compile(r"\bSources?\s*:")
SOURCE_ID_RE = re.compile(r"(" + UNIT_ID_RE.pattern + r")|(?<![\w.])\.N(\d+)\b")
_MARK = r"[*_`]*"
ENTRY_RE = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)])\s+)?" + _MARK + r"(CONFLICT|FALSE-POSITIVE|OPEN)" + _MARK +
                      r"\s*:?\s*" + _MARK + r"(" + UNIT_ID_RE.pattern + r")(?![\w.])" + _MARK +
                      r"\s*[:\-–—]?\s*(.*)$")
ENTRY_LIKE_RE = re.compile(r"^\s*(?:(?:[-*+]|\d+[.)])\s+)?[*_`|\s]*(?:conflict|false[- ]positive|open)\b[*_`|\s]*:?"
                           r"[*_`|\s]*ADR-\d{4}", re.I)
NONE_RE = re.compile(r"^None(?:\.|\s*\(([^)]+)\)\.?|\s*[:.,;]\s*(\S.*))?$")
KEY_IN_CELL_RE = re.compile(r"#([0-9a-f]{12})\b")
GOVERNING_RE = re.compile(r"ADR-\d{4}\.|\bR\d+[a-z]?\b")
PLACEHOLDER_RE = re.compile(
    r"\b(?:TBD|TODO|FIXME)\b|\bto be (?:compiled|written|defined|added|done|filled)\b|\blorem ipsum\b|"
    r"\b(?:see|per|as in|as per|follows) the source(?: text| rules?| ADRs?)?\b|"
    r"\bas (?:stated|written|given) in the source\b", re.I)
WORD_RE = re.compile(r"[A-Za-z]{3,}")
IDENT_RE = re.compile(r"[A-Za-z_][\w.]*")
QUOTE_RE = re.compile(r"\"([^\"]+)\"|“([^”]+)”")
ANCHOR_RE = re.compile(r"open-questions(?:\.md)?#([\w-]+)")
OQ_ITEM_RE = re.compile(r"^- \[([ xX])\]\s+(.*)$")


def clean(text):
    """What a reader sees of the characters: no invisible characters, every Unicode space a plain space."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return INVISIBLE_RE.sub("", SPACE_RE.sub(" ", text))


def norm_citations(text):
    """Citation forms nfdocs.find_refs does not read, rewritten to the ones it reads (S4 review R3-S2)."""
    t = re.sub(r"\bADR (\d{4})\b", r"ADR-\1", text)
    t = re.sub(r"\bRules?\b", lambda m: m.group(0).lower(), t)
    t = re.sub(r"(ADR-\d{4}(?:\]\([^)]*\))?)\s*\(\s*(rules?\s+[^)]*)\)", r"\1 \2", t)
    t = re.sub(r"(ADR-\d{4}(?:\]\([^)]*\))?)\s*§+\s*(?=\d)", r"\1 rule ", t)
    t = re.sub(r"\b(rules?\s+\d[\w, –-]*?)\s+(?:in|from|under)\s+(\[?ADR-\d{4})", r"\1 of \2", t)
    return re.sub(r"(\d[a-z]?)\s+through\s+(\d)", r"\1 to \2", t)


def unit_ids_in(text):
    """IDs written as `ADR-0070.R12`, `ADR-0070 rule 12`, `ADR-0070, rule 12`, `rule 12 of ADR-0070` and the forms of
    norm_citations."""
    ids = set(UNIT_ID_RE.findall(text))
    ids.update(nfdocs.find_refs(norm_citations(text))[1])
    return ids


def source_ids(text):
    """IDs of a `Source:` list, in order; `.N2` after an ID is a note of that ID's rule."""
    out, last = [], None
    for m in SOURCE_ID_RE.finditer(text.replace("`", "")):
        if m.group(1):
            last = re.sub(r"\.N\d+$", "", m.group(1))
            out.append(m.group(1))
        elif last:
            out.append(f"{last}.N{m.group(2)}")
    extra = sorted(unit_ids_in(text) - set(out), key=nfdocs.rule_sort_key)   # 'ADR-0070 rule 12'
    return out + extra


def mask(lines):
    """Blank out code fences (``` and ~~~), HTML comments (count markers kept) and indented code blocks, keeping
    line numbers."""
    out, fence, comment = [], None, False
    for l in lines:
        if not comment:
            m = FENCE_RE.match(l)
            if fence:
                if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                        and not l.strip().strip(fence[0]):
                    fence = None
                out.append("")
                continue
            if m:
                fence = m.group(1)
                out.append("")
                continue
        s, buf, i = l, "", 0
        while i < len(s):
            if comment:
                j = s.find("-->", i)
                if j < 0:
                    i = len(s)
                    break
                comment, i = False, j + 3
            else:
                j = s.find("<!--", i)
                if j < 0:
                    buf += s[i:]
                    break
                m = COUNT_RE.match(s, j)
                if m:
                    buf += s[i:m.end()]
                    i = m.end()
                    continue
                buf += s[i:j]
                comment, i = True, j + 4
        out.append(buf)
    in_list, prev_blank, in_code = False, True, False
    for k, l in enumerate(out):
        if not l.strip():
            prev_blank = True
            continue
        x = l.expandtabs(4)
        indent = len(x) - len(x.lstrip(" "))
        if indent >= 4 and not in_list and (prev_blank or in_code):
            out[k], in_code = "", True      # an indented code block
        else:
            in_code = False
            if LIST_ITEM_RE.match(l):
                in_list = True
            elif indent < 2 and prev_blank:
                in_list = False
        prev_blank = False
    return out


def plain(text):
    """Text without markup: tags, entities, links, emphasis and backticks removed (code span content kept)."""
    t = re.sub(r"<[^>]*>", " ", text)
    t = re.sub(r"&#?\w+;", " ", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    return re.sub(r"[*`]|(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])", "", t)


def vocab_words(text, vocab):
    return {w for w in WORD_RE.findall(plain(text).lower()) if w in vocab}


def statement_problem(statement, vocab):
    """Why a statement is not real text, or None."""
    p = plain(statement)
    chars = len(re.findall(r"[A-Za-z0-9]", p))
    if chars < MIN_STATEMENT_CHARS:
        return f"has no real statement ({chars} letters and digits; {MIN_STATEMENT_CHARS} or more are needed)"
    m = PLACEHOLDER_RE.search(plain(re.sub(r"`[^`\n]*`", " ", statement)))
    if m:
        return f"holds the placeholder '{m.group(0)}'"
    words = vocab_words(statement, vocab)
    if len(words) < MIN_STATEMENT_WORDS:
        return (f"has no real statement ({len(words)} distinct words of the ADRs' vocabulary; "
                f"{MIN_STATEMENT_WORDS} or more are needed)")
    return None


def identifiers(text):
    """Distinct identifiers of a source text: inline code spans that are one name of IDENT_MIN_LEN or more."""
    spans = nfdocs.CODE_SPAN_RE.findall(re.sub(r"```.*?```", " ", text, flags=re.S))
    return {s.strip().rstrip(".") for s in spans
            if len(s.strip().rstrip(".")) >= IDENT_MIN_LEN and IDENT_RE.fullmatch(s.strip().rstrip("."))}


def span_names(text):
    """Every name inside the code spans of a statement (`role:quality_inspector` gives `quality_inspector` too)."""
    out = set()
    for s in nfdocs.CODE_SPAN_RE.findall(text):
        out.add(s.strip().rstrip("."))
        out.update(x.rstrip(".") for x in IDENT_RE.findall(s))
    return out


class Spec:
    def __init__(self, path):
        self.path = path
        self.raw = nfdocs.read(path)
        self.text = clean(self.raw)
        self.lines = self.text.split("\n")
        self.vis = mask(self.lines)          # what a reader sees as prose: no fences, comments or code blocks
        self.sections = []   # (heading, start index, end index)
        heads = [(i, l[3:].strip()) for i, l in enumerate(self.vis) if l.startswith("## ")]
        for k, (i, h) in enumerate(heads):
            self.sections.append((h, i, heads[k + 1][0] if k + 1 < len(heads) else len(self.lines)))
        self.first_heading = heads[0][0] if heads else len(self.lines)
        self.headings = {}     # normalised heading -> the `##` sections that hold it
        for i, l in enumerate(self.vis):
            if re.match(r"^#{2,3} ", l):
                self.headings.setdefault(norm_heading(l), set()).add(self.section_of(i))
        self.reads = set()     # line indexes of `Reads` paragraphs
        i = 0
        while i < len(self.vis):
            if READS_RE.match(self.vis[i]):
                while i < len(self.vis) and self.vis[i].strip() and not self.vis[i].startswith("#"):
                    self.reads.add(i)
                    i += 1
            else:
                i += 1
        self.defs = []         # every `R<n>.` definition, in order
        self._find_defs()

    def _find_defs(self):
        i = 0
        while i < len(self.vis):
            m = RULE_DEF_RE.match(self.vis[i])
            sec = self.section_of(i)
            if not (m and sec in ("Rules", PROPOSED_HEADING) and i not in self.reads):
                i += 1
                continue
            parts, j = [m.group(2) or ""], i + 1
            while j < len(self.vis) and self.vis[j].strip() and not RULE_DEF_RE.match(self.vis[j]) \
                    and not self.vis[j].startswith("#"):
                parts.append(self.vis[j].strip())
                j += 1
            text = " ".join(parts)
            cut = SOURCE_SPLIT_RE.split(text, maxsplit=1)
            self.defs.append({"n": m.group(1), "section": sec, "line": i, "text": text, "file": self.path,
                              "statement": cut[0].strip(), "has_source": len(cut) > 1,
                              "sources": source_ids(cut[1]) if len(cut) > 1 else [],
                              "proposed": sec == PROPOSED_HEADING or "[proposed]" in text})
            i = j

    def section_of(self, i):
        for h, a, b in self.sections:
            if a <= i < b:
                return h
        return None

    def section_lines(self, name):
        for h, a, b in self.sections:
            if h == name:
                return [(i, self.vis[i]) for i in range(a + 1, b)]
        return None

    def body_lines(self):
        """Visible lines after the front matter and outside the Trace section."""
        return [(i, l) for i, l in enumerate(self.vis)
                if i >= self.first_heading and self.section_of(i) != "Trace"]

    def front(self):
        text = "\n".join(self.vis[:self.first_heading])
        out = {}
        for name in FRONT_FIELDS:
            others = "|".join(re.escape(n) for n in FRONT_FIELDS if n != name)
            m = re.search(re.escape(name) + r":\s*(.*?)\s*(?=(?:" + others + r"):|$)", text, re.M)
            if m:
                out[name] = (m.group(1).strip(), text[:m.start()].count("\n"))
        return out

    def trace(self):
        rows = []
        lines = self.section_lines("Trace")
        if lines is None:
            return None
        for i, l in lines:
            s = l.strip()
            if not s.startswith("|") or re.match(r"^\|[\s:|-]+\|$", s):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and cells[0].strip("` ").lower() == "source":
                continue
            key = KEY_IN_CELL_RE.search(cells[0])
            ids = sorted(unit_ids_in(cells[0].replace("`", ""))) or [cells[0].strip("` ")]
            for uid in ids:
                rows.append((i, uid, cells[1] if len(cells) > 1 else "", key.group(1) if key else None))
        return rows

    def conflicts(self):
        """-> (entries [{line, word, id, reason}], problems [(line, message)], None lines)."""
        entries, problems, nones, cur = [], [], [], None
        lines = self.section_lines("Conflicts") or []
        for k, (i, l) in enumerate(lines):
            s = l.strip()
            if not s or s.startswith("###"):
                cur = None
                continue
            row = s
            if s.startswith("|"):
                if re.match(r"^\|[\s:|-]+\|$", s):
                    continue
                nxt = lines[k + 1][1].strip() if k + 1 < len(lines) else ""
                if re.match(r"^\|[\s:|-]+\|$", nxt):
                    continue                     # the header row of a table
                cells = [c.strip() for c in s.strip("|").split("|")]
                row = " ".join(cells[:2]) + ": " + " | ".join(cells[2:])
            m = ENTRY_RE.match(row)
            if m:
                cur = {"line": i, "word": m.group(1), "id": m.group(2), "reason": m.group(3).strip()}
                entries.append(cur)
            elif ENTRY_LIKE_RE.match(s):
                problems.append((i, "looks like an entry but is not 'CONFLICT|FALSE-POSITIVE|OPEN <unit id>: "
                                    "<reason>' (capitals, a full unit ID)"))
                cur = None
            elif NONE_RE.match(s):
                nones.append(i)
                cur = None
            elif cur is not None and not s.startswith("|"):
                cur["reason"] = (cur["reason"] + " " + s).strip()
            else:
                problems.append((i, "is not an entry ('CONFLICT|FALSE-POSITIVE|OPEN <unit id>: <reason>') or "
                                    "the single word 'None'"))
        return entries, problems, nones


def norm_heading(text):
    return re.sub(r"[`#]", "", text).strip().lower()


def where_parts(where):
    w = re.sub(r"`", "", where).strip()
    if re.match(r"(?i)^not applicable\b", w):
        return [w]                               # the reason may hold commas
    return [p.strip() for p in re.split(r"[;,]", w) if p.strip()]


def r_key(n):
    m = re.match(r"(\d+)([a-z]?)$", n)
    return int(m.group(1)), m.group(2)


def expand_where_r(part, defined):
    """-> ([defined R-numbers], [undefined ones]) for `R3`, `R3-R7`, `R50a-R50e`, or None when it is not that form.
    A bare `R50` with only `R50a`.. defined means all of them."""
    m = WHERE_R_RE.match(part)
    if not m:
        return None
    by_num = {}
    for k in defined:
        by_num.setdefault(r_key(k)[0], []).append(k)
    lo = (int(m.group(1)), m.group(2))
    hi = (int(m.group(3)), m.group(4)) if m.group(3) else lo
    got, missing = [], []
    if hi[0] < lo[0] or hi[0] - lo[0] > 200:
        for a in (lo, hi):
            (got if f"{a[0]}{a[1]}" in defined else missing).append(f"{a[0]}{a[1]}")
        return got, missing
    for a in {lo, hi}:
        if a[1] and f"{a[0]}{a[1]}" not in defined:
            missing.append(f"{a[0]}{a[1]}")
    for num in range(lo[0], hi[0] + 1):
        cands = sorted(by_num.get(num, []), key=r_key)
        if not m.group(3) and lo[1]:
            cands = [k for k in cands if r_key(k)[1] == lo[1]]
        else:
            if num == lo[0] and lo[1]:
                cands = [k for k in cands if r_key(k)[1] >= lo[1]]
            if num == hi[0] and hi[1] and m.group(3):
                cands = [k for k in cands if r_key(k)[1] <= hi[1]]
        if cands:
            got += cands
        elif not ((num == lo[0] and lo[1]) or (num == hi[0] and hi[1])):
            missing.append(str(num))
    return got, sorted(set(missing), key=r_key)


def git(args, cwd):
    try:
        out = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None, None
    return out.returncode, out.stdout.strip()


def index_state(index_path, docs, index_sha=None):
    """-> (full commit hash or None, [problems]). The commit is --index-commit when given, else the last commit of
    the index file; it must exist, and the index file must equal its version in that commit. An index file outside
    a repository (a snapshot) is compared with docs/design/generated/rule-index.csv of the docs' repository."""
    idx = os.path.realpath(index_path)
    rc, top = git(["rev-parse", "--show-toplevel"], os.path.dirname(idx))
    if rc == 0 and top:
        rel = os.path.relpath(idx, os.path.realpath(top)).replace(os.sep, "/")
    else:
        rc, top = git(["rev-parse", "--show-toplevel"], docs)
        if rc != 0 or not top:
            return None, ["cannot read a git repository; the index commit is not verified"]
        rel = os.path.relpath(os.path.join(os.path.realpath(docs), "design", "generated", "rule-index.csv"),
                              os.path.realpath(top)).replace(os.sep, "/")
    if index_sha:
        rc, sha = git(["rev-parse", "--verify", "--quiet", index_sha + "^{commit}"], top)
        if rc != 0 or not sha:
            return None, [f"--index-commit '{index_sha}' is not a commit of {top}"]
    else:
        rc, sha = git(["log", "-1", "--format=%H", "--", rel], top)
        if rc != 0 or not sha:
            return None, [f"the index file has no commit in {top}; commit it before compiling against it"]
    rc1, blob = git(["rev-parse", "--verify", "--quiet", f"{sha}:{rel}"], top)
    rc2, mine = git(["hash-object", f"--path={rel}", idx], top)
    if rc1 != 0 or not blob:
        return sha, [f"commit {sha[:12]} holds no {rel}"]
    if rc2 != 0 or mine != blob:
        return sha, [f"the index differs from its version in commit {sha[:12]}; commit it (or lint against the "
                     f"committed index) before compiling against it"]
    return sha, []


_CACHE = {}


def docs_model(docs):
    """Per docs folder, read once: module model, catalogs, unit texts by ID, ADR vocabulary, open questions."""
    key = os.path.realpath(docs)
    if key not in _CACHE:
        modules, owners, _declared, _files = nfdocs.module_model(docs)
        cats, _skipped = nfdocs.load_catalogs(docs)
        units, _parsed, _dangling = nfdocs.extract(docs)
        vocab = set()
        for u in units:
            vocab.update(WORD_RE.findall(u["text"].lower()))
        _CACHE[key] = {"modules": modules, "owners": owners, "cats": cats, "vocab": vocab,
                       "texts": {u["id"]: u["text"] for u in units}, "questions": open_questions(docs)}
    return _CACHE[key]


def squash(text):
    return " ".join(text.replace("`", "").split())


def open_questions(docs):
    """docs/open-questions.md -> {open: [text of unchecked entries], anchors: {heading slugs}}. Entries are list
    items `- [ ]` (open) and `- [x]` (answered) under `##` headings; the file numbers no questions."""
    path = os.path.join(docs, "open-questions.md")
    out = {"open": [], "anchors": set()}
    if not os.path.isfile(path):
        return out
    cur = None
    for l in nfdocs.read(path).split("\n"):
        m = OQ_ITEM_RE.match(l)
        if m:
            cur = [m.group(2)] if m.group(1) == " " else None
            if cur is not None:
                out["open"].append(cur)
        elif l.startswith("#"):
            cur = None
            slug = re.sub(r"[^\w\- ]", "", l.lstrip("#").strip().lower()).replace(" ", "-")
            out["anchors"].add(slug)
        elif cur is not None and l.strip() and not l.startswith("- "):
            cur.append(l.strip())
        else:
            cur = None
    out["open"] = [squash(" ".join(x)) for x in out["open"]]
    return out


def open_problem(reason, questions):
    """Why an OPEN entry names no open question, or None."""
    for a in ANCHOR_RE.findall(reason):
        if a not in questions["anchors"]:
            return f"'open-questions.md#{a}' is not a heading of docs/open-questions.md"
    quotes = [squash(a or b) for a, b in QUOTE_RE.findall(reason)]
    if any(len(q) >= MIN_QUOTE and any(q in item for item in questions["open"]) for q in quotes):
        return None
    for n in re.findall(r"\bOQ-\d+\b", reason):
        if any(re.match(r"\(?" + n + r"\b", item) for item in questions["open"]):
            return None
    return (f"names no open question: quote, in double quotes, {MIN_QUOTE} or more characters of an unchecked "
            f"entry of docs/open-questions.md (the file numbers no questions)")


def beside_specs(path, module):
    """Compiled spec files of another module beside the linted file: <module>.md and <module>-<k>.md."""
    d = os.path.dirname(os.path.abspath(path))
    files = [os.path.join(d, f"{module}.md")] + sorted(glob.glob(os.path.join(d, f"{module}-[0-9]*.md")))
    return [p for p in files if os.path.isfile(p)]


def similar(a, b):
    if a == b:
        return True
    sm = difflib.SequenceMatcher(None, a, b)
    return sm.real_quick_ratio() > REASON_SIMILARITY and sm.quick_ratio() > REASON_SIMILARITY \
        and sm.ratio() > REASON_SIMILARITY


def lint(paths, module, index_path, docs, index_sha=None, partial=False, allow_process=False, strict=False):
    findings, warnings, info = [], [], {"files": {}}
    deferred = Counter()

    def f(check, path, line, msg):
        findings.append({"check": check, "file": path, "line": line, "message": msg})

    rows = build_index.read_index(index_path)
    by_id = {r["id"]: r for r in rows}
    model = docs_model(docs)
    modules, owners, cats, vocab = model["modules"], model["owners"], model["cats"], model["vocab"]
    known_modules = set(modules) | nfdocs.NON_CODE_MODULES | {"cross"}
    scope = nfdocs.module_scope(rows, owners, cats, module)
    units, tables = scope["units"], scope["tables"]
    if not units and not tables:
        raise SystemExit(f"doc_lint: module '{module}' has no units and no tables in the index")
    if module == "cross":
        raise SystemExit("doc_lint: 'cross' is not a compile target; its units are compiled in their primary "
                         "modules (compiled-spec template, Size budget)")
    primary_rules = [r["id"] for r in units if r["kind"] == "rule" and module in r["primary_module"]]
    if not primary_rules:
        raise SystemExit(f"doc_lint: module '{module}' is primary for no rule; nothing to compile or measure")
    if module in nfdocs.NON_CODE_MODULES and not allow_process:
        raise SystemExit(f"doc_lint: '{module}' is not a code module (template rule 7); give --allow-process when "
                         f"the author asked for its spec")
    specs = [Spec(p) for p in paths]
    unit_ids = {r["id"] for r in units}
    children = {}
    for r in rows:
        if r["kind"] == "note" and r["parent"]:
            children.setdefault(r["parent"], []).append(r)

    def superseded(r):
        return r["kind"] == "rule" and bool(r["superseded_by"] or r["relation"] == "superseded-by")

    # L0: index commit
    sha, problems = index_state(index_path, docs, index_sha)
    for p in problems:
        f("L0", index_path, 0, p)

    # L0: front matter, chunk set, sections
    chunks = []
    for s in specs:
        fm = s.front()
        for name in FRONT_FIELDS:
            if name not in fm or not fm[name][0]:
                f("L0", s.path, 1, f"front matter field '{name}:' is missing or empty")
        if "Module" in fm and fm["Module"][0] != module:
            f("L0", s.path, fm["Module"][1] + 1, f"front matter Module '{fm['Module'][0]}' is not --module '{module}'")
        chunk = fm.get("Chunk", ("", 0))
        m = re.fullmatch(r"(\d+) of (\d+)", chunk[0])
        if chunk[0] and not (m or chunk[0] == "whole"):
            f("L0", s.path, chunk[1] + 1, f"Chunk '{chunk[0]}' is not 'whole' or 'k of n'")
        chunks.append((s.path, chunk[1] + 1, (int(m.group(1)), int(m.group(2))) if m else chunk[0]))
        if fm.get("Generated from index", ("",))[0] and sha:
            given = fm["Generated from index"][0]
            if not (re.fullmatch(r"[0-9a-f]{7,40}", given) and sha.startswith(given)):
                f("L0", s.path, fm["Generated from index"][1] + 1,
                  f"Generated from index '{given}' is not the committed index {sha[:12]}; note IDs may have moved, "
                  f"re-lint against the current index")
        names = [h for h, _a, _b in s.sections]
        for h, a, _b in s.sections:
            if h not in SECTIONS:
                f("L0", s.path, a + 1, f"section '## {h}' is not one of the template's sections")
        order = [SECTIONS.index(h) for h in names if h in SECTIONS]
        if order != sorted(order) or len(order) != len(set(order)):
            f("L0", s.path, 1, "sections are out of the template's order or repeated")
        for h in PER_FILE_SECTIONS:
            if h not in names:
                f("L0", s.path, 1, f"section '## {h}' is required in every file")
    numbered = [c for c in chunks if isinstance(c[2], tuple)]
    incomplete = False
    for path, line, c in numbered:
        if c[0] < 1 or c[0] > c[1]:
            f("L0", path, line, f"Chunk '{c[0]} of {c[1]}': k is not within 1..n")
    if len(specs) > 1:
        for path, line, c in chunks:
            if c == "whole":
                f("L0", path, line, "Chunk 'whole' in a set of several files; write 'k of n'")
        if len({c[2][1] for c in numbered}) > 1:
            f("L0", specs[0].path, 1, "the chunks disagree on n: " +
              ", ".join(sorted({f"{c[2][0]} of {c[2][1]}" for c in numbered})))
        seen = Counter(c[2][0] for c in numbered)
        for path, line, c in numbered:
            if seen[c[0]] > 1:
                f("L0", path, line, f"Chunk {c[0]} of {c[1]} is given by {seen[c[0]]} files")
    if numbered:
        n = max(c[2][1] for c in numbered)
        missing = sorted(set(range(1, n + 1)) - {c[2][0] for c in numbered})
        if missing:
            incomplete = True
            info["notice"] = (f"NOTICE: chunk(s) {', '.join(map(str, missing))} of {n} are not given; the "
                              f"module-level checks (missing IDs, sections, owned names, coverage, entries of units "
                              f"traced elsewhere) are partial")
            if not partial:
                f("L0", specs[0].path, 1, f"chunk(s) {', '.join(map(str, missing))} of {n} are not given; lint all "
                                          f"chunks together, or give --partial for a chunk alone")
    present = {h for s in specs for h, _a, _b in s.sections}
    for h in SECTIONS:
        if h not in present:
            if incomplete:
                deferred["sections not in these chunks"] += 1
            else:
                f("L0", specs[0].path, 1, f"section '## {h}' is missing")
    for s in specs:
        for h, a, b in s.sections:
            if h not in SECTIONS:
                continue
            content = [s.vis[i].strip() for i in range(a + 1, b)
                       if s.vis[i].strip() and not s.vis[i].startswith("###")]
            none = NONE_RE.match(content[0]) if len(content) == 1 else None
            if not content:
                how = " or 'None (<reason>)'" if h in NONE_WITH_REASON else (" or 'None'" if h in NONE_BARE else "")
                f("L0", s.path, a + 1, f"section '## {h}' is empty; write its content{how}")
            elif none and h in NONE_WITH_REASON and not (none.group(1) or none.group(2)):
                f("L0", s.path, a + 1, f"section '## {h}': 'None' needs a reason ('None (<reason>)')")
            elif none and h == "Entities and tables" and tables:
                f("L0", s.path, a + 1, f"section '## {h}' says None, but the module owns {len(tables)} table(s)")
            elif none and h in ("Purpose", "Rules", "Trace"):
                f("L0", s.path, a + 1, f"section '## {h}' may not be 'None'")

    # R-number definitions
    defined, heading_sections = {}, {}
    for s in specs:
        for h, secs in s.headings.items():
            heading_sections.setdefault(h, set()).update(secs)
    seen_text = {}
    for s in specs:
        for d in s.defs:
            n = d["n"]
            if n in defined:
                where = "" if defined[n]["file"] == s.path else f" of {defined[n]['file']}"
                f("L1", s.path, d["line"] + 1, f"R{n} is defined twice (first at line {defined[n]['line'] + 1}"
                                               f"{where}); an R-number names one statement")
                continue
            defined[n] = d
            problem = statement_problem(d["statement"], vocab)
            norm = re.sub(r"\W+", " ", d["statement"].lower()).strip()
            if problem:
                f("L1", s.path, d["line"] + 1, f"R{n} {problem}")
            elif norm in seen_text:
                f("L1", s.path, d["line"] + 1, f"R{n} repeats the statement of R{seen_text[norm]}")
            else:
                seen_text[norm] = n
            if not d["sources"]:
                f("L1", s.path, d["line"] + 1, f"R{n} has no 'Source:' with a unit ID")
    other_specs = {}

    def other_defs(mod, path):
        """R-number definitions of another module's compiled spec beside `path`, or None when there is none."""
        key = (mod, os.path.dirname(os.path.abspath(path)))
        if key not in other_specs:
            files = [p for p in beside_specs(path, mod) if os.path.abspath(p) not in
                     {os.path.abspath(x) for x in paths}]
            other_specs[key] = {d["n"]: d for p in files for d in Spec(p).defs} if files else None
        return other_specs[key]

    # L7 and L1: the trace table
    traced, refs_of, rs_of, na_ids, row_line, keys_bad = {}, set(), {}, set(), {}, []
    trace_rows = 0
    for s in specs:
        for i, uid, where, key in s.trace() or []:
            trace_rows += 1
            if uid not in by_id:
                f("L7", s.path, i + 1, f"trace ID {uid} is not in the rule index")
                continue
            row = by_id[uid]
            if uid not in unit_ids:
                f("L7", s.path, i + 1, f"trace ID {uid} is not a unit of module {module} (its modules: "
                                       f"{', '.join(row['modules'])}); drop the row")
                continue
            traced.setdefault(uid, (s.path, i + 1))
            row_line[uid] = (s.path, i + 1)
            if key and key != row.get("stable_key"):
                same = [r["id"] for r in rows if r.get("stable_key") == key]
                msg = (f"{s.path}:{i + 1}: {uid} #{key} does not match the index ({row.get('stable_key')})"
                       + (f"; that text is now {', '.join(same)}" if same else "; the text changed"))
                keys_bad.append(msg)
                warnings.append("W2 " + msg)
            kind, primary = row["kind"], row["primary_module"]
            parts = where_parts(where)
            if not parts:
                f("L1", s.path, i + 1, f"trace row {uid} has an empty 'Where'")
                continue
            has_r = has_ref = has_na = False
            for p in parts:
                na = re.match(r"(?i)^not applicable\s*:?\s*(.*)$", p)
                ref = REF_RE.match(p)
                rs = expand_where_r(p, defined)
                if na:
                    has_na = True
                    na_ids.add(uid)
                    if kind == "rule":
                        f("L1", s.path, i + 1, f"trace row {uid}: 'not applicable' is refused for a rule")
                    elif not na.group(1).strip():
                        f("L1", s.path, i + 1, f"trace row {uid}: 'not applicable' needs a reason")
                elif ref:
                    has_ref = True
                    refs_of.add(uid)
                    if module in primary:
                        f("L1", s.path, i + 1, f"trace row {uid}: 'ref:' is for other modules' law; {module} is "
                                               f"primary for it, state it")
                    elif ref.group(1):
                        mod, n = ref.group(1), ref.group(2)
                        if mod not in known_modules or mod == module:
                            f("L8", s.path, i + 1, f"trace row {uid}: 'ref: {mod} R-…' names no other module")
                        elif mod not in primary:
                            f("L1", s.path, i + 1, f"trace row {uid}: 'ref: {mod} R-{n}', but the primary module "
                                                   f"of {uid} is {', '.join(primary)}")
                        else:
                            theirs = other_defs(mod, s.path)
                            if theirs is not None and n not in theirs:
                                f("L1", s.path, i + 1, f"trace row {uid}: 'ref: {mod} R-{n}', but the compiled "
                                                       f"spec of {mod} beside this file defines no R{n}")
                            elif theirs is not None and uid not in theirs[n]["sources"]:
                                f("L1", s.path, i + 1, f"trace row {uid}: 'ref: {mod} R-{n}', but the Source of "
                                                       f"{mod} R{n} does not cite {uid}")
                    else:
                        target = ref.group(3)
                        if target not in by_id:
                            f("L7", s.path, i + 1, f"trace row {uid}: 'ref: {target}' is not in the rule index")
                        elif target not in {uid, row["parent"]} | set(row["xrefs_rules"]):
                            f("L1", s.path, i + 1, f"trace row {uid}: 'ref: {target}' is not {uid}, its parent "
                                                   f"rule or a rule its text cites")
                elif p.lower().startswith("reads"):
                    f("L1", s.path, i + 1, f"trace row {uid}: a 'Reads' list does not state a rule")
                elif rs is not None:
                    got, missing = rs
                    for n in missing:
                        if incomplete:
                            deferred["R-numbers of other chunks"] += 1
                            has_r = True
                        else:
                            f("L1", s.path, i + 1, f"trace row {uid}: R{n} is not defined in the spec")
                    for n in got:
                        has_r = True
                        rs_of.setdefault(uid, set()).add(n)
                        if row["status"] == "proposed" and not defined[n]["proposed"]:
                            f("L3", s.path, i + 1, f"trace row {uid} (proposed) points to R{n}, stated as law")
                        elif row["status"] != "proposed" and defined[n]["proposed"]:
                            f("L3", s.path, i + 1, f"trace row {uid} ({row['status']}) points to R{n}, stated as "
                                                   f"proposed; accepted law is defined under '## Rules'")
                elif norm_heading(p) in heading_sections:
                    if kind != "section" and len(parts) == 1:
                        f("L1", s.path, i + 1, f"trace row {uid}: a {kind} must point to an R-number"
                                               + (" or 'not applicable: <reason>'" if kind == "note" else "")
                                               + "; a heading alone is for Decision text units")
                    if row["status"] == "proposed" and heading_sections[norm_heading(p)] != {PROPOSED_HEADING}:
                        f("L3", s.path, i + 1, f"trace row {uid} (proposed) points to heading '{p}' outside "
                                               f"'## {PROPOSED_HEADING}'")
                else:
                    f("L1", s.path, i + 1, f"trace row {uid}: 'Where' part '{p}' is not an R-number, ref:, an "
                                           f"existing heading or 'not applicable: <reason>'")
            if kind in ("rule", "note") and len(parts) > 1 and not (has_r or has_ref or has_na):
                f("L1", s.path, i + 1, f"trace row {uid}: a {kind} must point to a defined R-number (or ref: when "
                                       f"another module is primary)")
    if not trace_rows:
        f("L1", specs[0].path, 0, f"the trace table is empty; module {module} has {len(units)} units")
    if not defined:
        f("L1", specs[0].path, 0, f"no R-number is defined; module {module} is primary for "
                                  f"{len(primary_rules)} rules")
    missing_ids = sorted(unit_ids - set(traced), key=nfdocs.rule_sort_key)
    if incomplete:
        deferred["units not traced in these chunks"] += len(missing_ids)
    else:
        for uid in missing_ids:
            f("L1", specs[0].path, 0, f"{uid} ({by_id[uid]['kind']}) is missing from the trace table")

    # L1 and L7: Source/trace agreement
    traced_to = {}
    for uid, ns in rs_of.items():
        for n in ns:
            traced_to.setdefault(n, set()).add(uid)
    for n in sorted(defined, key=r_key):
        d = defined[n]
        src = set(d["sources"])
        governing = {g for u in src | traced_to.get(n, set()) if u in by_id for g in by_id[u]["superseded_by"]}
        for x in sorted(src, key=nfdocs.rule_sort_key):
            if x not in by_id:
                f("L7", d["file"], d["line"] + 1, f"R{n}: Source {x} is not in the rule index")
            elif x in governing:
                continue
            elif x not in unit_ids:
                f("L7", d["file"], d["line"] + 1, f"R{n}: Source {x} is not a unit of module {module} (its "
                                                  f"modules: {', '.join(by_id[x]['modules'])})")
            elif n not in rs_of.get(x, ()):
                if incomplete and x not in traced:
                    deferred["Source IDs traced in other chunks"] += 1
                else:
                    f("L1", d["file"], d["line"] + 1, f"R{n} cites {x} in its Source, but the trace row of {x} "
                                                      f"does not point to R{n}")
        for x in sorted(traced_to.get(n, set()) - src, key=nfdocs.rule_sort_key):
            f("L1", row_line[x][0], row_line[x][1], f"trace row {x} points to R{n}, whose Source does not cite it")

    # L1: coverage and the 'not applicable' share
    rule_units = [r["id"] for r in units if r["kind"] == "rule" and r["id"] not in refs_of]
    load = Counter()
    mapped = 0
    for uid in rule_units:
        for n in sorted(rs_of.get(uid, ()), key=r_key):
            if uid in defined[n]["sources"] and load[n] < MAX_IDS_PER_R:
                load[n] += 1
                mapped += 1
                break
    if incomplete:
        deferred["coverage and 'not applicable' share not evaluated"] += 1
    else:
        if rule_units and mapped < MIN_COVERAGE * len(rule_units):
            f("L1", specs[0].path, 0, f"{mapped} of {len(rule_units)} source rules map to R-numbers whose Source "
                                      f"cites them (counting at most {MAX_IDS_PER_R} per R-number); "
                                      f"{int(MIN_COVERAGE * 100)}% is required")
        if units and len(na_ids & unit_ids) > MAX_NA_SHARE * len(units):
            f("L1", specs[0].path, 0, f"{len(na_ids & unit_ids)} of {len(units)} units are 'not applicable' (more "
                                      f"than {int(MAX_NA_SHARE * 100)}%)")

    # L11: identifier retention and size ratio
    texts = model["texts"]
    info["retention"] = {}
    for s in specs:
        total = kept_total = src_bytes = rules_n = changed = 0
        low = []
        for i, uid, _where, _key in s.trace() or []:
            r = by_id.get(uid)
            if not r or uid not in unit_ids or r["kind"] != "rule" or not rs_of.get(uid) \
                    or row_line.get(uid) != (s.path, i + 1):
                continue
            text = texts.get(uid)
            if text is None or nfdocs.stable_key(text) != r.get("stable_key"):
                changed += 1
                continue
            rules_n += 1
            src_bytes += len(text.encode("utf-8"))
            ids = identifiers(text)
            names = set()
            for n in rs_of[uid]:
                names |= span_names(defined[n]["statement"])
            kept = ids & names
            total += len(ids)
            kept_total += len(kept)
            exempt = superseded(r) or any(c["relation"] in ("supersedes", "superseded-by")
                                          for c in children.get(uid, []))
            if len(ids) >= RETENTION_MIN_IDS:
                low.append((len(kept) / len(ids), uid, len(kept), len(ids)))
                if not kept and not exempt:
                    rlist = ", ".join("R" + n for n in sorted(rs_of[uid], key=r_key))
                    f("L11", s.path, i + 1, f"{uid} holds {len(ids)} identifiers in backticks "
                                            f"({', '.join(sorted(ids)[:3])}…); the statements of {rlist} hold "
                                            f"none of them; state the rule's content or correct the trace")
        stmt_bytes = sum(len(d["statement"].encode("utf-8")) for d in s.defs if defined.get(d["n"]) is d)
        low.sort(key=lambda x: (x[0], nfdocs.rule_sort_key(x[1])))
        info["retention"][s.path] = {
            "source_rules": rules_n, "identifiers": total, "kept": kept_total,
            "share": round(kept_total / total, 3) if total else None, "text_changed": changed,
            "lowest": [f"{u} {k}/{t}" for _sh, u, k, t in low[:5]],
            "statement_bytes": stmt_bytes, "source_rule_bytes": src_bytes,
            "size_ratio": round(stmt_bytes / src_bytes, 3) if src_bytes else None}

    # L2 and L9
    def spans_of(with_reads):
        out = []
        for s in specs:
            out += nfdocs.code_spans("\n".join(l for i, l in s.body_lines() if with_reads or i not in s.reads))
        return "\n".join(out)

    proper, with_reads = spans_of(False), spans_of(True)

    def absent(check, msg):
        if incomplete:
            deferred["owned names not in these chunks"] += 1
        else:
            f(check, specs[0].path, 0, msg)

    for t in tables:
        if not nfdocs.key_regex(t).search(proper):
            absent("L2", f"owned table `{t}` is not mentioned in backticks outside 'Reads'")
    for c in scope["owned_rows"]:
        if not nfdocs.key_regex(c.split(":", 1)[1]).search(proper):
            absent("L2", f"owned catalog row {c} is not mentioned in backticks outside 'Reads'")
    for c in scope["settings"]:
        key = c.split(":", 1)[1]
        if c not in scope["owned_rows"] and not nfdocs.key_regex(key).search(with_reads):
            absent("L9", f"setting `{key}` is referenced by the module's rules but not in the body or `Reads`")

    # L3, L4, L8 per file
    columns = None
    for s in specs:
        for i, line in s.body_lines():
            sec = s.section_of(i)
            for m in XREF_R_RE.finditer(line):
                word, num = m.group(1), m.group(2)
                if word == "ref" or (line[:m.start()].rstrip().endswith("ref:")):
                    continue
                if not re.fullmatch(r"\d+[a-z]?", num or ""):
                    f("L8", s.path, i + 1, f"cross-module reference 'R-{num}' is not a rule number")
                elif word not in known_modules:
                    f("L8", s.path, i + 1, f"cross-module reference '{(word or '') + ' '}R-{num}' does not start "
                                           f"with a module name")
            for m in XREF_ADR_RE.finditer(line):
                if m.group(1) not in known_modules:
                    f("L8", s.path, i + 1, f"cross-module reference '{m.group(1)} ADR-…' names no module")
            for kind, n in count_findings(line):
                if kind is None:
                    f("L4", s.path, i + 1, f"typed count '{n}'; write <!-- count:KIND -->N<!-- /count --> or list it")
                    continue
                if kind == "columns" and columns is None:
                    columns = nfdocs.table_columns(docs)
                want = expected_count(kind, scope, columns)
                if want is None:
                    f("L4", s.path, i + 1, f"count kind '{kind}' cannot be computed from the index")
                elif want != n:
                    f("L4", s.path, i + 1, f"count:{kind} says {n}, the index gives {want}")
            if sec == "Conflicts":
                continue
            if ENTRY_RE.match(line) or ENTRY_LIKE_RE.match(line):
                f("L5", s.path, i + 1, f"a Conflicts entry outside '## Conflicts'; it is not read there")
            cited = [u for u in unit_ids_in(line) if u in by_id]
            prop = sorted(u for u in cited if by_id[u]["status"] == "proposed")
            marked = "[proposed]" in line
            in_prop = sec == PROPOSED_HEADING
            if prop and not (marked or in_prop):
                f("L3", s.path, i + 1, f"cites proposed {', '.join(prop)} outside '## {PROPOSED_HEADING}' "
                                        f"without [proposed]")
            if cited and not prop and (marked or in_prop):
                f("L3", s.path, i + 1, "accepted rule marked as proposed: " + ", ".join(sorted(cited)))

    # L5 and L10
    entries = []
    for s in specs:
        got, problems, nones = s.conflicts()
        for i, msg in problems:
            f("L5", s.path, i + 1, f"line under '## Conflicts' {msg}")
        if nones and (got or len(nones) > 1 or problems):
            f("L5", s.path, nones[0] + 1, "'None' stands beside other lines under '## Conflicts'")
        for e in got:
            e["file"] = s.path
            entries.append(e)
    of = {"CONFLICT": {}, "FALSE-POSITIVE": {}, "OPEN": {}}
    for e in entries:
        word, uid, reason, path, line = e["word"], e["id"], e["reason"], e["file"], e["line"] + 1
        of[word].setdefault(uid, []).append(reason)
        r = by_id.get(uid)
        if r is None:
            f("L5", path, line, f"{word} {uid}: not in the rule index")
        elif uid not in unit_ids:
            f("L5", path, line, f"{word} {uid}: not a unit of module {module}")
        if word in ("CONFLICT", "FALSE-POSITIVE"):
            if len(reason) < MIN_REASON:
                f("L5", path, line, f"{word} {uid}: the reason needs {MIN_REASON} characters or more")
            elif len(vocab_words(reason, vocab)) < MIN_REASON_WORDS:
                f("L5", path, line, f"{word} {uid}: the reason needs {MIN_REASON_WORDS} or more distinct words "
                                    f"of the ADRs' vocabulary")
        else:
            problem = open_problem(reason, model["questions"])
            if problem:
                f("L5", path, line, f"OPEN {uid}: {problem}")
        if word == "FALSE-POSITIVE" and r is not None and uid in unit_ids and not (
                r["kind"] == "note" and r["conflict_flag"]):
            f("L5", path, line, f"FALSE-POSITIVE {uid}: the unit carries no conflict flag; a conflict the compiler "
                                f"found is CONFLICT or OPEN")
    kinds_of = {}
    for e in entries:
        kinds_of.setdefault(e["id"], set()).add(e["word"])
    for uid in sorted(kinds_of, key=nfdocs.rule_sort_key):
        if len(kinds_of[uid]) > 1:
            first = next(e for e in entries if e["id"] == uid)
            f("L5", first["file"], first["line"] + 1, f"{uid} has entries of several kinds: "
                                                       f"{', '.join(sorted(kinds_of[uid]))}")
    for word in ("CONFLICT", "FALSE-POSITIVE"):
        group = [(e, re.sub(r"\s+", " ", e["reason"].lower())) for e in entries if e["word"] == word]
        reported = set()
        for e, text in group:
            if text in reported:
                continue
            same = [(e2, t2) for e2, t2 in group if similar(t2, text)]
            if len(same) > MAX_REASON_REUSE:
                reported.update(t2 for _e2, t2 in same)
                ids = [e2["id"] for e2, _t2 in same]
                f("L5", e["file"], e["line"] + 1,
                  f"one {word} reason (or a near copy) serves {len(same)} entries ({', '.join(ids[:5])}"
                  f"{'…' if len(ids) > 5 else ''}); give each its own reason")
    any_entry = set(kinds_of)

    def governs(uid):
        """CONFLICT naming the governing text (an ADR unit ID or an R-number), or OPEN."""
        return uid in of["OPEN"] or any(GOVERNING_RE.search(x) for x in of["CONFLICT"].get(uid, []))

    superseded_list = []
    for r in units:
        uid = r["id"]
        here = uid in traced
        if incomplete and not here:
            if r["conflict_markers"] or superseded(r) or (r["kind"] == "note" and (
                    r["conflict_flag"] or r["relation"] in ("supersedes", "superseded-by"))):
                deferred["entries of units traced in other chunks"] += 1
            if superseded(r):
                superseded_list.append(f"{uid} superseded by {', '.join(r['superseded_by']) or 'its own text'}; "
                                       f"not traced in these chunks")
            continue
        if r["conflict_markers"] and not (uid in of["CONFLICT"] or uid in of["OPEN"]):
            f("L5", specs[0].path, 0, f"{uid} carries a CONFLICT marker; list 'CONFLICT {uid}: <resolution>'")
        if r["kind"] == "note" and r["relation"] in ("supersedes", "superseded-by") and uid not in refs_of:
            if not (governs(uid) or governs(r["parent"])):
                how = "FALSE-POSITIVE is refused for it; " if uid in of["FALSE-POSITIVE"] else ""
                f("L5", specs[0].path, 0, f"{uid} (relation {r['relation']}): {how}list 'CONFLICT {uid}: <which "
                                          f"text governs, an ADR unit ID or R-number>' or OPEN")
        elif r["kind"] == "note" and r["conflict_flag"] and uid not in any_entry and uid not in refs_of:
            f("L5", specs[0].path, 0, f"{uid} (conflict flag {';'.join(r['conflict_phrases'])}) is not listed under "
                                      f"'## Conflicts' (an entry of its parent rule does not serve)")
        if superseded(r):
            by = ", ".join(r["superseded_by"]) or "its own text"
            rlist = ", ".join("R" + n for n in sorted(rs_of.get(uid, ()), key=r_key))
            where = "ref:" if uid in refs_of else (rlist or "no R-number")
            kind = ", ".join(sorted(kinds_of.get(uid, []))) or "no entry"
            superseded_list.append(f"{uid} superseded by {by}; Where {where}; entry: {kind}")
            if uid in refs_of:
                continue
            named = set()
            for reason in of["CONFLICT"].get(uid, []):
                named |= unit_ids_in(reason) & set(r["superseded_by"])
            if uid in of["OPEN"] or (not r["superseded_by"] and governs(uid)):
                continue
            if not named:
                how = "FALSE-POSITIVE is refused for it; " if uid in of["FALSE-POSITIVE"] else ""
                what = f"names {by}" if r["superseded_by"] else "names the governing text"
                f("L10", specs[0].path, 0, f"{uid} is superseded ({by}); {how}list 'CONFLICT {uid}: <reason that "
                                           f"{what}>' or OPEN")
                continue
            for n in sorted(rs_of.get(uid, ()), key=r_key):
                if not named & set(defined[n]["sources"]):
                    f("L10", defined[n]["file"], defined[n]["line"] + 1,
                      f"R{n} states {uid}, which {', '.join(sorted(named))} supersedes, but its Source does not "
                      f"cite {', '.join(sorted(named))}; state the governing text and cite it")

    # L6
    for s in specs:
        size = len(s.raw.encode("utf-8"))
        tokens = round(size / nfdocs.TOKEN_BYTES)
        per = {h: round(len("\n".join(s.lines[a:b]).encode("utf-8")) / nfdocs.TOKEN_BYTES) for h, a, b in s.sections}
        info["files"][s.path] = {"bytes": size, "est_tokens": tokens, "sections": per}
        if tokens > nfdocs.SPEC_HARD_TOKENS:
            f("L6", s.path, 0, f"{tokens} tokens (bytes / 3.5) over the hard limit {nfdocs.SPEC_HARD_TOKENS}; "
                               f"split into chunks at '###' topics")
    if strict:
        for w in warnings:
            f("W2", specs[0].path, 0, w[3:])
    review = [f"{e['word']} {e['id']}: {e['reason']}" for e in entries]
    measured = {"module": module, "files": len(specs), "units": len(units),
                "rules": sum(1 for r in units if r["kind"] == "rule"), "primary_rules": len(primary_rules),
                "notes": sum(1 for r in units if r["kind"] == "note"),
                "sections": sum(1 for r in units if r["kind"] == "section"), "tables": len(tables),
                "r_numbers": len(defined), "trace_rows": trace_rows, "traced_units": len(traced)}
    info.update(module=module, module_ids=len(unit_ids), tables=len(tables), owned_rows=len(scope["owned_rows"]),
                settings=len(scope["settings"]), defined_r=len(defined), mapped_rules=mapped,
                not_applicable=len(na_ids & unit_ids), warnings=warnings, review=review, measured=measured,
                review_counts={w: sum(1 for e in entries if e["word"] == w) for w in of},
                superseded_rules=superseded_list, key_mismatches=keys_bad, deferred=dict(sorted(deferred.items())),
                incomplete=incomplete, partial=bool(partial and incomplete))
    findings.sort(key=lambda x: (x["check"], x["file"], x["line"], x["message"]))
    return findings, info


def count_findings(line):
    """-> [(kind, n)] for count markers and [(None, text)] for typed counts in one line."""
    out = [(m.group(1), int(m.group(2))) for m in COUNT_RE.finditer(line)]
    text = COUNT_RE.sub(" ", clean(line))
    text = re.sub(r"&nbsp;|&#160;|&#x0*a0;", " ", text, flags=re.I)
    text = re.sub(r"<[^>]*>", " ", text)                       # <br>
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)       # [tables](#anchor)
    text = re.sub(r"ADR-\d{4}(?:\.[\w.]+)?|\b(?:INV|EC|DS|OQ)-\d+|\bR-?\d+[a-z]?\b", " ", text)
    # a code span that is a number, a word or a phrase is read as text (`16` tables, `12 tables`); any other span
    # is a name (`days:5`, `pack@1`) and stands as the word 'code', so that its digits are not counts
    text = re.sub(r"`([^`\n]+)`", lambda m: m.group(1) if re.fullmatch(r"[A-Za-z0-9 ,]+", m.group(1)) else "code",
                  text)
    text = re.sub(r"[*`]|(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])", "", text)
    text = re.sub(r"-(?=" + NOUNS + r"\b)", " ", text, flags=re.I)   # 16-table, owned-tables
    for rx in (COUNT_BEFORE_RE, ROMAN_RE):
        for m in rx.finditer(text):
            before = text[:m.start()]
            prev = re.findall(r"[\w-]+", before[-40:])
            if prev and prev[-1].lower() in CITATION_WORDS:
                continue
            if THRESHOLD_RE.search(before):
                continue
            out.append((None, m.group(0).strip()))
    for rx in (COUNT_AFTER_RE, COUNT_PAREN_RE, COUNT_GLUED_RE, COUNT_CELL_RE, COUNT_CELL_REV_RE):
        for m in rx.finditer(text):
            out.append((None, m.group(0).strip()))
    return out


def expected_count(kind, scope, columns):
    units, tables, cat_rows = scope["units"], scope["tables"], scope["catalog_rows"]
    k = {"rule": "rules", "note": "notes", "table": "tables", "setting": "settings", "invariant": "invariants",
         "edge-case": "edge-cases", "catalog-row": "catalog-rows", "column": "columns",
         "section": "sections"}.get(kind, kind)
    if k == "rules":
        return sum(1 for r in units if r["kind"] == "rule")
    if k == "notes":
        return sum(1 for r in units if r["kind"] == "note")
    if k == "sections":
        return sum(1 for r in units if r["kind"] == "section")
    if k == "tables":
        return len(tables)
    if k == "columns":
        return sum(len(columns.get(t, [])) for t in tables)
    if k == "settings":
        return len(scope["settings"])
    if k == "invariants":
        return sum(1 for c in cat_rows if c.startswith("invariants:"))
    if k == "edge-cases":
        return sum(1 for c in cat_rows if c.startswith("edge-cases:"))
    if k == "catalog-rows":
        return len(cat_rows)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--module", required=True)
    ap.add_argument("--index", default=nfdocs.DEFAULT_INDEX)
    ap.add_argument("--index-commit", help="commit to compare 'Generated from index' with (default: the last "
                                           "commit of the index file); the index file must equal its version there")
    ap.add_argument("--docs", default=nfdocs.DEFAULT_DOCS)
    ap.add_argument("--partial", action="store_true", help="lint a chunk without the others: module-level checks "
                                                           "are counted as deferred; the result is LINT PARTIAL")
    ap.add_argument("--allow-process", action="store_true", help="lint the non-code module 'process'")
    ap.add_argument("--strict", action="store_true", help="warnings (W2) are findings")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    for p in args.specs:
        if not os.path.isfile(p):
            print(f"doc_lint: no file {p}", file=sys.stderr)
            return 2
    if len({os.path.realpath(p) for p in args.specs}) != len(args.specs):
        print("doc_lint: the same file is given twice", file=sys.stderr)
        return 2
    try:
        findings, info = lint(args.specs, args.module, args.index, args.docs, args.index_commit,
                              partial=args.partial, allow_process=args.allow_process, strict=args.strict)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2
    n_deferred = sum(info["deferred"].values())
    if findings:
        head = f"LINT FAIL findings={len(findings)}"
    elif info["partial"]:
        head = f"LINT PARTIAL findings=0 deferred={n_deferred}"
    else:
        head = "LINT PASS findings=0"
    print(head)
    if args.json:
        print(json.dumps({"result": head, "findings": findings, "info": info}, sort_keys=True))
        return 1 if findings else 0
    ms = info["measured"]
    print("measured: " + " ".join(f"{k}={ms[k]}" for k in (
        "module", "files", "units", "rules", "primary_rules", "notes", "sections", "tables", "r_numbers",
        "trace_rows", "traced_units")))
    if info.get("notice"):
        print(info["notice"])
    for x in findings:
        print(f"{x['check']} {x['file']}:{x['line']}: {x['message']}")
    for w in info["warnings"]:
        print(w)
    for k, v in info["deferred"].items():
        print(f"deferred: {k}: {v}")
    for p, st in info["files"].items():
        print(f"size {p}: {st['bytes']} bytes, ~{st['est_tokens']} tokens; " +
              ", ".join(f"{h} ~{t}" for h, t in st["sections"].items()))
    for p, rt in info["retention"].items():
        share = "n/a" if rt["share"] is None else f"{rt['share']:.0%}"
        print(f"retention {p}: {rt['kept']} of {rt['identifiers']} identifiers of {rt['source_rules']} source "
              f"rules appear in backticks in their R-numbers ({share})"
              + (f"; lowest: {', '.join(rt['lowest'])}" if rt["lowest"] else "")
              + (f"; {rt['text_changed']} rule(s) skipped, text differs from the index" if rt["text_changed"] else ""))
        ratio = "n/a" if rt["size_ratio"] is None else f"{rt['size_ratio']:.2f}"
        print(f"size-ratio {p}: statements {rt['statement_bytes']} bytes / source rules "
              f"{rt['source_rule_bytes']} bytes = {ratio}")
    rc = info["review_counts"]
    print(f"REVIEW LIST ({len(info['review'])} entries for the chief architect; template acceptance step 3): "
          f"CONFLICT={rc['CONFLICT']} FALSE-POSITIVE={rc['FALSE-POSITIVE']} OPEN={rc['OPEN']}")
    for e in info["review"]:
        print(f"  {e}")
    print(f"SUPERSEDED RULES (read each; template acceptance step 2): {len(info['superseded_rules'])}")
    for e in info["superseded_rules"]:
        print(f"  {e}")
    print(f"STABLE-KEY MISMATCHES (the text behind a trace row changed or moved): {len(info['key_mismatches'])}")
    for e in info["key_mismatches"]:
        print(f"  {e}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
