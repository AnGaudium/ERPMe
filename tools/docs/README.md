# tools/docs: rule units, index, dossiers and doc-lint (S3)

Four deterministic tools that turn the ADRs into machine-readable rule units, a rule index, one dossier per module,
and a lint for compiled specs ([compiled-spec-template.md](../../docs/design/compiled-spec-template.md)). Python 3.12,
standard library only, no LLM calls. Output is sorted and carries no timestamps, so a rerun on the same tree gives the
same bytes. Every tool exits non-zero on failure.

## Run

```
tools/docs/run_all.sh [OUT_DIR]        # index, units, dossiers, tests; OUT_DIR defaults to ~/Projects/NativeFlows-lab/fable/s3-out
python tools/docs/extract_rules.py --out OUT/units.jsonl [--markers-out OUT/conflict-markers.jsonl] [--strict]
python tools/docs/build_index.py [--check]                 # writes docs/design/generated/rule-index.csv
python tools/docs/build_dossiers.py --out OUT/dossiers     # <module>.md, cross.md, MODULES.csv
python tools/docs/doc_lint.py SPEC.md [SPEC-2.md ...] --module M [--json]
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
| `doc_lint.py` | the compiled spec, the index, the DDL and catalogs | findings on stdout |

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
conflict_markers, xrefs_adrs, xrefs_rules, xrefs_inv, xrefs_ec, xrefs_ds, xrefs_oq, dangling`.

A rule's `text` is its own lines only; its notes are separate units. When rule text resumes after a note, the gap is
one blank line in `text`, and `line_end` is the rule's last own line.

## Parsing rules

- A rule starts at `N. ` or `Na. ` in column 0, inside `### Rules` (or anywhere in the Decision when there is no
  `### Rules`). It ends at the next rule, a group line, a `###`/`##` heading.
- A group is a line that is only bold text, optionally followed by a parenthesis (`**GR/IR** (F12)`).
- A note starts at `Note:` or `Note (<balanced parenthesis>):` indented 0-4 spaces. It runs for its paragraph. After
  a blank line, a block indented deeper than the note (or at 4 or more for a note indented 4) continues the note;
  any other block returns to the rule. `note_author` is the parenthesis verbatim, `note_date` its first date.
- Cross-references: `ADR-NNNN` (also as a link), then optionally `rule N`, `rules N, M`, `rules N-M`, `rules N to M`,
  `rules N and M`, or `R6, R8` (ADR-0003). `ADR-0022 rule 4` -> `ADR-0022.R4`. Also `INV-n`, `EC-n`, `DS-n`, `OQ-n`.
  A reference to a rule or ADR not in the units is `dangling`.
- Literal markers: the word `CONFLICT` in capitals, except SQL `ON CONFLICT`, the template's `CONFLICT <rule id>`
  and the word in backticks.

## Heuristics (named in code, counted in the extractor summary)

- **relation** of a note: `superseded-by` when it says "superseded by"; else `supersedes` when it says one of
  `supersedes, overrides, replaces, is/are replaced by, no longer applies, is withdrawn, is/are dropped`; else
  `amends`. A rule whose text says "superseded by" carries `relation = superseded-by`.
- **conflict flag** of a note: any of `conflict*, contradict*, no longer, instead of, replaces, reversed, overturn*,
  is wrong, corrected` (case-insensitive, whole words except the starred prefixes).
- **tables** of a unit: a `CREATE TABLE` name (min 4 characters) as a whole word inside inline code or a fenced
  block.
- **catalog rows**: first-column keys of catalogs whose first column is unique (5 catalogs with repeating keys are
  skipped and reported), min 4 characters, in code; keys with `<placeholder>` parts match either form; `INV-n` and
  `EC-n` anywhere, matched to the catalog key by number. A key spelled like a table is credited to the table only.
- **modules** of a unit: the primary module of its ADR (`primary_module`, from the committed
  [adr-primary-module.csv](adr-primary-module.csv)) plus the owners of its tables; a note also takes its owner's
  modules. When more than 3 modules besides the primary one are named, `modules` is `<primary>;cross` and the full
  list is in `modules_all`. No unit is unassigned. In a dossier a unit is `primary` (its ADR's primary module) or
  `shared` (it names a table the module owns).
- **adr-primary-module.csv** (`adr,module,role`): one `primary` row per ADR, `secondary` rows for the other modules
  gen_overview declares for it (shown in the dossier header, no other effect). It was seeded from gen_overview's
  declared modules and the ADR titles (S3 pilot, 2026-11-21). `process` is a non-code module for process ADRs
  (ADR-0001 to 0005, 0022, 0073): it gets a dossier flagged non-code and no tables. The tools refuse an ADR
  without a primary, with two, or with a module that is not in ADR-0022 rule 2 and not `process`.
- **build step**: the first `step N` / `build step N` (vocabulary of spec 11) in the unit, for a note else in its
  owner; else the ADR's step: the first in its header and `.D0`, else the step it names most often.
- **tokens** are bytes / 3.5. `chunks_needed` = tokens / 30,000 rounded up (ADR-0073 rule 6 context pack).

## Dossier content

Per module: its units (primary and shared), the `.E` and `.U` sections of its primary ADRs, the DDL of its owned
tables, the CSV rows of every catalog row its units reference, and the full rows of every invariant and edge case
referenced by its units or by those `.E`/`.U` sections, or whose `area` is the module. So sections 5 and 6 of the
template can be written from the dossier alone.

## Lint checks

L1 trace covers every module ID, a `Where` cell is not empty and `not applicable:` has a reason (any other `Where`
that is not an R-number or a heading of the spec is a warning); L2 owned tables and **owned** catalog rows backticked
in the body. A catalog row is owned when a unit whose primary module is this module references it, unless its
catalog has a `module` column naming another module; invariants and edge cases whose `area` is the module are
owned too. Rows of other modules are not required and may be listed under `Reads`; L3 proposed rules only
under `## Proposed (not law)` or with `[proposed]`, never on accepted rules; L4 no bare number before a counted noun,
`<!-- count:KIND -->N<!-- /count -->` recomputed (tables, columns, rules, notes, sections, settings, invariants,
edge-cases, catalog-rows; other kinds such as commands are a finding, as the index cannot count them); L5 every
CONFLICT-marked unit as `CONFLICT <id>: <resolution>`, every conflict-flagged note as `CONFLICT` or
`FALSE-POSITIVE <id>` under `## Conflicts`; L6 hard limit 16,000 tokens per file, section sizes reported; L7 trace IDs
exist; L8 a cross-module reference `<module> R-<n>` (or `` `<module> ADR-nnnn…` ``) names a module of ADR-0022
rule 2 (or `process`, `cross`) and a numeric rule: `R-scrap`, `R-3` without a module and `nosuch R-1` are findings;
L9 every setting key referenced by any unit of the module (primary or shared) is backticked in the body or in `Reads`.
Several files given together are the chunks of one module: L1, L2, L5 and L9 run over all of them.

## Blind spots

- A bare `rule N` without an ADR number (a reference inside the same ADR) is not a cross-reference.
- Prose that amends a rule without starting with `Note` (for example ADR-0026 rule 1, "The side table is ...") is
  rule text, not a note. A paragraph after a note at the same indent is read as rule text; it may be the note's
  continuation (about 6 cases, e.g. ADR-0035 rule 9 "This replaces ...").
- `Note (author's delegation, 2026-11-19) adds 3 definitions:` (ADR-0063 line 258) has no colon after the parenthesis
  and is not a note.
- ADR-0003's two notes after the R10 schedule attach to `.D1` (the schedule), although the second amends R5.
  ADR-0005's paragraph "Everything else is technical" after rule 11 is read as rule 11 text.
- ADR-0002's tool tables and its numbered "Performance and resources" list sit under `## Context`; they are section
  text, not rules.
- Conflict phrases are noisy by design ("reversed" is also an accounting word). Relations are phrase-based and do not
  say which part of a rule is superseded.
- Tables and keys are matched only in code spans; a table named in plain prose is not counted. One-word table names
  (`item`, `partner`, `site`) also match enum values or concepts written in code; the index summary lists them.
- Module assignment is the ADR's primary module plus table ownership. A rule about a third module that names none
  of its tables does not reach that module's dossier. The primary module was chosen by hand for ADRs with several
  candidates; see adr-primary-module.csv.
- `doc_lint` L4 recognises digits only, not number words, and allows one word between the number and the noun.
