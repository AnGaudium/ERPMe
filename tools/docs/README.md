# tools/docs: rule units, index, dossiers and doc-lint (S3)

Four deterministic tools that turn the ADRs into machine-readable rule units, a rule index, one dossier per module,
and a lint for compiled specs ([compiled-spec-template.md](../../docs/design/compiled-spec-template.md)). Python 3.12,
standard library only, no LLM calls. Output is sorted and carries no timestamps, so a rerun on the same tree gives the
same bytes. Every tool exits non-zero on failure.

## Run

```
tools/docs/run_all.sh [--out DIR]      # index, units, dossiers, tests; without --out a new temporary directory
python tools/docs/extract_rules.py --out OUT/units.jsonl [--markers-out OUT/conflict-markers.jsonl] [--strict]
python tools/docs/build_index.py [--check]                 # writes docs/design/generated/rule-index.csv
python tools/docs/build_dossiers.py --out OUT/dossiers     # <module>.md, cross.md, MODULES.csv
python tools/docs/doc_lint.py SPEC.md [SPEC-2.md ...] --module M [--index-commit SHA] [--partial] [--strict] [--json]
python -m unittest discover tools/docs/tests
```

Only `docs/design/generated/rule-index.csv` is committed. Units, markers and dossiers are large and go outside the
repository.

## Reads and writes

| Tool | Reads | Writes |
| --- | --- | --- |
| `extract_rules.py` | `docs/adr/[0-9]*.md`; for markers also `docs/spec`, `docs/design` | units JSON Lines; marker JSON Lines; summary on stdout |
| `build_index.py` | ADRs, `docs/design/**/*.sql`, `docs/catalogs/*.csv`, ADR-0022 rule 2 through `gen_overview.py` | `docs/design/generated/rule-index.csv` |
| `build_dossiers.py` | same as the index | `<module>.md` per module of ADR-0022 rule 2 and `process`, `cross.md`, `MODULES.csv` |
| `doc_lint.py` | the compiled spec, the index, the ADRs (rule texts, vocabulary), the DDL and catalogs, `docs/open-questions.md`, other modules' compiled specs beside the linted file, git (index commit) | findings on stdout |

`nfdocs.py` holds the shared parsing. The table -> owner mapping and the ADR -> declared modules mapping are
**imported** from `docs/reviews/2026-11-14-design-validation/lab/gen_overview.py` (`module_map`, `parse_ddl`,
`declared_by_module`), not copied, so the index and `module-cards.md` agree by construction.

## Unit IDs

- Rule: `ADR-0026.R6`; rule with a letter: `ADR-0078.R9a`. ADR-0003's rules are the table rows `R1`..`R14`
  (`ADR-0003.R6`). A numbered list that restarts at 1 under a new `###` heading (ADR-0005) is list 2, 3...:
  `ADR-0005.L2.R1`; the first list keeps `ADR-0005.R1`, which is what "ADR-0005 rule n" means.
- Note: `<owner>.N<k>`, numbered in order inside its owner: `ADR-0026.R6.N2`, `ADR-0002.C.N1`, `ADR-0025.H.N1`.
- Section: `.H` header (title and status), `.D0` Decision text before the rules, `.D1`.. Decision text after a `###`
  heading or a group without a rule, `.W` worked examples, `.C` context, `.O` options, `.K` constraints or
  consequences, `.E` edge cases, `.V` revisit, `.U` documents updated, `.A` decisions for the author, `.X` unknown.

The index holds rules, notes and the Decision text units (`.D*`, `.W`), because Decision text is normative (all of
ADR-0001's decision is `.D0`). The other sections are in the units file only.

## Unit fields

`id, kind (rule|note|section), adr, rule_no, group, section, parent, text (verbatim), source_file, line_start,
line_end, adr_status (accepted|proposed|superseded), note_author, note_date, relation, conflict, conflict_phrases,
conflict_markers, superseded_by, xrefs_adrs, xrefs_rules, xrefs_inv, xrefs_ec, xrefs_ds, xrefs_oq, dangling`.

The index adds `primary_module` (one or more), `modules`, `modules_all`, `tables`, `catalog_rows`, `build_step`,
`superseded_by` (the units that supersede a rule) and `stable_key` (see below).

A rule's `text` is its own lines only; its notes are separate units. When rule text resumes after a note, the gap is
one blank line in `text`, and `line_end` is the rule's last own line.

## Parsing rules

- A rule starts at `N. ` or `Na. ` in column 0, inside `### Rules` (or anywhere in the Decision when there is no
  `### Rules`). It ends at the next rule, a group line, a `###`/`##` heading.
- A group is a line that is only bold text, optionally followed by a parenthesis (`**GR/IR** (F12)`).
- A note starts at `Note:` or `Note (<balanced parenthesis>):` indented 0-4 spaces, or `Note (<parenthesis>) <short
  verb phrase>:` (ADR-0063 line 258, "adds 3 definitions:"). It runs for its paragraph. After a blank line the next
  block is judged against the rule's content column (3 under `1. `, 4 under `12. `, 0 for section text): deeper than
  the note, or at the note's indent when the note sits deeper than the column, continues the note; at the note's
  indent when the note sits at the column, it continues only when the note so far holds a table, a list or a line
  ending in `:`; anything else returns to the rule. `note_author` is the parenthesis verbatim, `note_date` its first
  date.
- Inbound supersession: a sentence of unit X with `supersedes|replaces|overrides` marks the rules named within six
  words after the verb (and chained by `,`/`and`) `superseded_by` X; a rule named just before the verb, outside a
  parenthesis, supersedes X's own rule; `superseded ... by <rule>` marks X's own rule. Example: ADR-0026.R14 <-
  ADR-0027.R10.
- Cross-references: `ADR-NNNN` (also as a link), then optionally `rule N`, `rules N, M`, `rules N-M`, `rules N to M`,
  `rules N and M`, or `R6, R8` (ADR-0003); also `rule N of ADR-NNNN` and `rules N and M of ADR-NNNN`. `ADR-0022 rule 4` -> `ADR-0022.R4`. Also `INV-n`, `EC-n`, `DS-n`, `OQ-n`.
  A reference to a rule or ADR not in the units is `dangling`.
- Literal markers: the word `CONFLICT` in capitals, except SQL `ON CONFLICT`, the template's `CONFLICT <rule id>`
  and the word in backticks.

## Heuristics (named in code, counted in the extractor summary)

- **relation** of a note: `superseded-by` when it says "superseded by"; else `supersedes` when it says one of
  `supersedes, overrides, replaces, is/are replaced by, no longer applies, is withdrawn, is/are dropped, now reads,
  now has, is stale`, a code term followed by `becomes` or `moves to`, or `moves to Phase n`; else `amends`. On a
  read of the 30 notes the S3 review widening added, about 2 are wrong (ADR-0010.R1.N1, ADR-0048.R19.N1). A rule
  whose text says "superseded by" carries `relation = superseded-by`.
- **conflict flag** of a note: any of `conflict*, contradict*, no longer, instead of, replaces, reversed, overturn*,
  is wrong, corrected` (case-insensitive, whole words except the starred prefixes).
- **tables** of a unit: a `CREATE TABLE` name (min 4 characters) as a whole word inside inline code or a fenced
  block.
- **catalog rows**: first-column keys of catalogs whose first column is unique (5 catalogs with repeating keys are
  skipped and reported), min 4 characters, in code; keys with `<placeholder>` parts match either form; `INV-n` and
  `EC-n` anywhere, matched to the catalog key by number. A key spelled like a table is credited to the table only.
- **modules** of a unit: its primary modules plus the owners of its tables; a note also takes its owner's modules.
  Primary modules: those of its rule in [rule-module-overrides.csv](rule-module-overrides.csv) (`adr, rule_from,
  rule_to, module, role`; a rule listed there is primary in each listed module and NOT in the ADR's default, `9a`
  counts as 9), else the ADR's primary module from [adr-primary-module.csv](adr-primary-module.csv). A note takes its
  rule's primaries. When more than 3 modules besides the primaries are named, `modules` is `<primaries>;cross` and
  the full list is in `modules_all`. No unit is unassigned; `build_index` fails when a module that owns tables is
  primary for no rule. In a dossier a unit is `primary` or `shared` (it names a table the module owns).
- **overrides** were set by reading the rules of ADR-0019, 0025, 0027, 0030, 0031, 0047, 0062 and 0077 (S3 review
  B3). 40 ADRs have a primary module that owns under 70% of the tables their rules name; the others were left, as
  their rules mostly read other modules' tables by design (agents, reporting, query).
- **adr-primary-module.csv** (`adr,module,role`): one `primary` row per ADR, `secondary` rows for the other modules
  gen_overview declares for it (shown in the dossier header, no other effect). It was seeded from gen_overview's
  declared modules and the ADR titles (S3 pilot, 2026-11-21). `process` is a non-code module for process ADRs
  (ADR-0001 to 0005, 0022, 0073): it gets a dossier flagged non-code and no tables. The tools refuse an ADR
  without a primary, with two, or with a module that is not in ADR-0022 rule 2 and not `process`.
- **build step**: the first `step N` / `build step N` (vocabulary of spec 11) in the unit, for a note else in its
  owner; else the ADR's step: the first in its header and `.D0`, else the step it names most often.
- **tokens** are bytes / 3.5, not checked against a tokenizer. `chunks_needed` = dossier tokens / 30,000 rounded up
  (ADR-0073 rule 6 context pack); `spec_chunks_est` = 0.55 x dossier tokens / 12,000 rounded up (the template's
  expected spec size and soft target per chunk).

## Dossier content

Per module: its units (primary and shared), the `.E` and `.U` sections of its primary ADRs, the DDL of its owned
tables, the CSV rows of every catalog row its units reference, and the full rows of every invariant and edge case
referenced by its units or by those `.E`/`.U` sections, or whose `area` is the module. So sections 5 and 6 of the
template can be written from the dossier alone. A superseded rule carries `SUPERSEDED by <id>` in its heading.

## Lint checks

The lint connects the trace table to the rule bodies and closes the known shortcuts. Whether a statement says what
its sources say is the template's different-model spot check; the lint prints what that check and the chief
architect must read. The full list, with every threshold, is the docstring of `doc_lint.py`; in short:

**Output.** Line 1 is `LINT PASS findings=0`, `LINT FAIL findings=N` or `LINT PARTIAL findings=0 deferred=N`. Line 2
is `measured: module=… files=… units=… rules=… primary_rules=… notes=… sections=… tables=… r_numbers=… trace_rows=…
traced_units=…`, so a pass that measured nothing is visible. Then the findings (`L<n> <file>:<line>: <message>`),
warnings, deferred counts, sizes, and per file `retention` (share of source rule identifiers kept) and `size-ratio`
(statement bytes / source rule bytes). Last: the REVIEW LIST (entries counted per kind), the SUPERSEDED RULES and
the STABLE-KEY MISMATCHES. Exit 0 on PASS and PARTIAL, 1 on FAIL, 2 on bad input.

**Refused (exit 2).** A missing file or the same file twice; `--module cross` and any module that is primary for no
rule (their units are compiled in their primary modules); `process` without `--allow-process`.

**Before every check** invisible characters (zero-width, joiners, soft hyphen, bidi marks) are removed, Unicode
spaces become a space, and HTML comments (count markers kept), ```` ``` ```` and `~~~` fences and indented code
blocks (4 spaces or a tab after a blank line, outside a list) are blanked. Nothing inside them counts, front matter
included.

- **L0** front matter (`Module` equal to `--module`, `Chunk`, `Source ADRs`, `Build step(s)`, `Generated from index`,
  `Compiled by`).
  - Index: `Generated from index` (7 or more hex digits) is the last commit of the index file, or `--index-commit`,
    which must be a commit; the index file must equal its version in that commit. An index that differs and a commit
    that cannot be read are findings.
  - Chunks: one file is `whole` or `1 of 1`; several files are `k of n` with one n, each k once, 1..n all given. A
    lone chunk of n > 1 is a finding and prints a NOTICE; with `--partial` the module-level checks that need the
    other chunks (missing IDs, missing sections, owned names, coverage, R-numbers and entries of other chunks) are
    counted as `deferred` and line 1 says `LINT PARTIAL`. The chunk's own checks still run.
  - Sections: the template's eleven, in order, no others; `Purpose` and `Trace` in every chunk, all eleven across
    the chunks. Each has content (a `###` heading is not content). `None` needs a reason (`None (reason)` or
    `None: reason`) for Commands and queries, Invariants, Edge cases, Settings and UI annotations; it may stand bare
    for Conflicts and Proposed (not law); for Entities and tables only when the module owns no table; never for
    Purpose, Rules and Trace.
- **L1** trace and rule bodies.
  - Every module ID is traced; the trace table and the set of R-numbers are not empty.
  - An R-number is defined by `R<n>.` (at most 3 spaces of indent) in `## Rules` or `## Proposed (not law)`, outside
    a `Reads` paragraph, up to the next blank line, once in the module's files.
  - Its statement (the text before `Source:`) has 12 or more letters and digits after markup, tags and entities are
    removed, 2 or more distinct words (3 letters or more) that occur in the ADRs, no placeholder (`TBD`, `TODO`,
    `FIXME`, `to be compiled|written|…`, `see|per|as in|follows the source`, `as stated|written|given in the
    source`, `lorem ipsum`) outside backticks, and repeats no other.
  - `Source:` is required; its IDs (`ADR-nnnn.Rk`; `.Nj` after an ID is a note of it) exist in the index and are
    units of the module (L7).
  - **Source/trace agreement**, both directions, across chunks: a unit traced to R-n is in the Source of R-n, and a
    unit in the Source of R-n is traced to R-n. Exception: an ID that supersedes a unit of R-n may stand in its
    Source without a trace row, also when it is another module's unit (L10).
  - `Where` of a rule: defined R-numbers (`R3`, `R3-R7`, `R50a-R50e`; `R50` means `R50a`..), or `ref:` when the
    module is not primary for it. Of a note: R-numbers, `ref:` or `not applicable: <reason>` (the whole cell). Of a
    Decision text unit (`.D*`, `.W`): also an existing heading of the spec. A heading may be added to an R-number,
    never stand alone for a rule or a note. Any other part, a heading that does not exist, `Reads` and an empty
    cell are findings.
  - `ref: ADR-nnnn.Rk` is the unit's own ID, its parent rule's ID or an ID its index row cross-references.
    `ref: <module> R-<n>` names a primary module of the unit; when that module's compiled spec lies beside the
    linted file (`<module>.md`, `<module>-<k>.md`), R-n is defined there and its Source holds the unit's ID.
  - At most 15% of the module's units are `not applicable`. Coverage: the rule units mapped to an R-number whose
    Source cites them, counting at most 4 IDs per R-number, are 60% or more of the rule units not traced as `ref:`.
- **L2** owned tables and **owned** catalog rows backticked in the body, outside `Reads` paragraphs and the trace
  table. A row is owned when a unit whose primary module is this module references it, unless its catalog has a
  `module` column naming another module; invariants and edge cases whose `area` is the module are owned too.
- **L3** proposed rules (cited as `ADR-0070.R12`, `ADR-0070 rule 12`, `ADR-0070, rule 12`, `rule 12 of|in ADR-0070`,
  `ADR-0070 (rule 12)`, `ADR 0070 rule 12`, `ADR-0070 §12`, `Rule`, `rules 12 through 14`) only under
  `## Proposed (not law)` or with `[proposed]`, never accepted ones. A proposed unit's R-numbers are stated that
  way; an accepted unit's R-numbers are defined under `## Rules` without `[proposed]`; a proposed Decision text
  unit names only headings of `## Proposed (not law)`.
- **L4** no typed count: digits, number words (`two` and up, `twenty-one`, `a dozen`) or Roman numerals of I, V, X
  before a counted noun (up to three words between), after it (`Tables owned: 10`, `Tables owned — 10`,
  `Owned tables (10)`), glued to it (`16tables`, `16-table`), or in a table row (`| Owned tables | 16 |`,
  `| 16 | owned tables |`). Bold, italics, links, tags and `&nbsp;` are removed first; a code span that is a number,
  a word or a phrase is read as text, any other span (`days:5`) is a name. `one` is not a count; citations
  (`rule 15 note`, `7 of rule`, `INV-12`, `rules 22–23`) and `at most|at least|up to|more than|fewer than|less than`
  pass; `exactly` and `only` do not. On the ADR rule and note text it fires 78 times (75 before round 3; the 3 new
  ones are real counts, `**Settings:** 11 definitions`); on the pilot `quality` spec once, a real count. Count
  markers are recomputed.
- **L5** `## Conflicts`: every line is an entry, its continuation, a `###` heading, blank, or the single line
  `None`. Entries are `CONFLICT <id>: <reason>`, `FALSE-POSITIVE <id>: <reason>`, `OPEN <id>: <text>`; a list
  marker, bold, backticks, `CONFLICT: <id>` and a table row are read as entries; any other line, and an entry line
  outside `## Conflicts`, is a finding.
  - Every ID is a unit of the module; one ID has entries of one kind.
  - A CONFLICT or FALSE-POSITIVE reason has 25 characters or more and 4 or more distinct words (3 letters or more)
    that occur in the ADRs; one reason, or a near copy at 0.8 similarity, serves at most 3 entries of its kind.
  - OPEN quotes, in double quotes, 20 or more characters of an unchecked entry of `docs/open-questions.md`. That
    file numbers no questions (entries are `- [ ]` list items under `##` headings; `OQ-074`, `OQ-116` and `OQ-150`
    occur in it only as mentions), so an `OQ-nnn` counts only when an unchecked entry starts with it; an
    `open-questions.md#anchor` must be a heading of the file.
  - FALSE-POSITIVE is for conflict-flagged notes only; an ID without flag, marker or supersession may be CONFLICT
    or OPEN.
  - Required: every CONFLICT-marked unit (CONFLICT or OPEN); every conflict-flagged note (its own entry; the
    parent's does not serve); every note whose relation is `supersedes` or `superseded-by` as CONFLICT naming the
    governing text (an ADR unit ID or an R-number) or OPEN, on the note or its parent rule, never FALSE-POSITIVE,
    unless its Where is `ref:`.
- **L6** hard limit 16,000 tokens per file; **L7** trace, Source and `ref:` IDs exist and, for trace and Source,
  are units of the module.
- **L8** `<module> R-<n>` (also in `ref:`) names a module of ADR-0022 rule 2 (or `process`, `cross`) and a numeric
  rule; a backticked `` `<word> ADR-nnnn` `` names a module too.
- **L9** every setting key referenced by any unit of the module is backticked in the body; a `Reads` paragraph
  serves for a key the module does not own.
- **L10** every rule of the module that another unit supersedes, or whose text says it is superseded, has, unless
  its Where is `ref:`, an OPEN entry or a CONFLICT that names a superseding ID (any ADR unit ID or R-number when
  the index names none); with a CONFLICT, that superseding ID is in the Source of every R-number the rule is traced
  to. The lint cannot judge that the statement is the new text: every such rule is printed under SUPERSEDED RULES
  and belongs to the spot check (template acceptance step 2).
- **L11** identifier retention: a source rule (not superseded, no superseding note) whose text holds 3 or more
  distinct identifiers in backticks, traced to R-numbers whose statements hold none of them in backticks, is a
  finding. An identifier is a code span that is one name of 4 or more characters. Calibration on the pilot
  `quality` spec (honest text): 349 of 393 identifiers kept (89%); the lowest rule keeps 6 of 35 (its content is a
  table of the spec); size ratio 0.81. The lazy probe keeps 0 of 382, ratio 0.01.
- Warning **W2**: a Source cell's `#<stable_key>` differs from the index; listed under STABLE-KEY MISMATCHES, a
  finding with `--strict`. (W0, W1 and W3 of earlier rounds are findings now: L0, L1, L10.)

Several files given together are the chunks of one module: every module-level check runs over all of them.

## Note IDs move; compile against one index commit

Note IDs are positional (`ADR-0063.R29.N13` is the 13th note of the rule). When a note is inserted before others,
or a parser fix splits one (S3 review: ADR-0063 line 258), the later notes are renumbered by a re-extraction. So a
compiled spec is compiled against one committed index: L0 fails when `Generated from index` is not the index's last
commit in HEAD, and the spec is re-linted (and re-traced) after every index commit. The index column `stable_key`
(first 12 hex of sha1 of the unit's whitespace-normalised text) may follow an ID in a Source cell
(`ADR-0063.R29.N13 #abc123def456`); the lint warns (W2) when it no longer matches, names the ID that now holds that
text and lists the row under STABLE-KEY MISMATCHES.

## Blind spots

- A bare `rule N` without an ADR number (a reference inside the same ADR) is not a cross-reference.
- Prose that amends a rule without starting with `Note` (for example ADR-0026 rule 1, "The side table is ...") is
  rule text, not a note. The note boundary rule fixes the 8 cases of the S3 review; a note that introduces nothing
  (no `:`, list or table) and is followed by its own continuation paragraph at the rule's column is still cut short.
- ADR-0003's two notes after the R10 schedule attach to `.D1` (the schedule), although the second amends R5.
  ADR-0005's paragraph "Everything else is technical" after rule 11 is read as rule 11 text.
- ADR-0002's tool tables and its numbered "Performance and resources" list sit under `## Context`; they are section
  text, not rules.
- Conflict phrases are noisy by design ("reversed" is also an accounting word). Relations are phrase-based and do not
  say which part of a rule is superseded.
- Tables and keys are matched only in code spans; a table named in plain prose is not counted. One-word table names
  (`item`, `partner`, `site`) also match enum values or concepts written in code; the index summary lists them.
- Module assignment is the primary modules plus table ownership. A rule about a third module that names none of its
  tables does not reach that module's dossier. Primary modules were chosen by hand; see the two CSV files. A sample of
  20 rules after the overrides: 19 right (the miss: ADR-0041.R21, the Vietnamese draft, reads as localization).
- Inbound supersession is found only in sentences with the verbs above; 11 rules are linked today.
- `doc_lint` L4 knows number words up to `hundred` only; `cross` units reach other modules only through `cross.md`.
- `doc_lint` cannot judge meaning. A statement that keeps the identifiers and cites the right sources but says
  something else passes L1 and L11; a CONFLICT that names the superseding ID while the statement keeps the old text
  passes L10. Both are the spot check's (template acceptance step 2). "Words that occur in the ADRs" is a
  vocabulary test, not a grammar test.
- A definition ends at the first blank line: a `Source:` in a later paragraph is not read (finding "no Source").
  Text inside code fences and indented code blocks counts for nothing, also not for L2.
