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
python tools/docs/doc_lint.py SPEC.md [SPEC-2.md ...] --module M [--index-commit SHA] [--json]
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
conflict_markers, superseded_by, xrefs_adrs, xrefs_rules, xrefs_inv, xrefs_ec, xrefs_ds, xrefs_oq, dangling`.

The index adds `primary_module` (one or more), `modules`, `modules_all`, `tables`, `catalog_rows`, `build_step` and
`superseded_by` (the units that supersede a rule).

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
  `rules N and M`, or `R6, R8` (ADR-0003). `ADR-0022 rule 4` -> `ADR-0022.R4`. Also `INV-n`, `EC-n`, `DS-n`, `OQ-n`.
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

The full list is the docstring of `doc_lint.py`; in short:

- **L0** front matter (`Module` equal to `--module`, `Chunk`, `Source ADRs`, `Build step(s)`, `Generated from index`
  compared with the index file's last commit, `Compiled by`) and the template's eleven `##` sections, in order,
  no others; `Purpose` and `Trace` in every chunk, all eleven across the chunks.
- **L1** every module ID is traced; each `Where` is R-numbers (ranges allowed) defined as `R<n>.` in `## Rules` or
  `## Proposed (not law)` (not on a `Reads` line; `R50` counts when `R50a.` exists), a heading of the spec, or
  `not applicable: <reason>`, which is refused for rules; `Reads` and empty cells are refused; other values are
  warnings. Fewer R-numbers than 25% of the module's rule IDs is a finding.
- **L2** owned tables and **owned** catalog rows backticked in the body. A row is owned when a unit whose primary
  module is this module references it, unless its catalog has a `module` column naming another module; invariants
  and edge cases whose `area` is the module are owned too. Other modules' rows may stand under `Reads`.
- **L3** proposed rules (cited as `ADR-0070.R12` or `ADR-0070 rule 12`) only under `## Proposed (not law)` or with
  `[proposed]`, never accepted ones; a proposed ID's trace R-numbers must be stated that way.
- **L4** no typed count: digits or number words before a counted noun (up to two words between, backticks included)
  or after it (`Tables owned: 10`); citations (`rule 15 note`, `step 7 events`, `INV-12`) and quoted thresholds
  (`at most 12 columns`) pass. Count markers are recomputed (tables, rules, catalog-rows, settings; also notes,
  sections, columns, invariants, edge-cases). On the pilot `quality` spec L4 raises 1 finding, a real count.
- **L5** `## Conflicts` entries: `CONFLICT <id>: <reason>` and `FALSE-POSITIVE <id>: <reason>` with 25 characters or
  more, `OPEN <id>: ...` with an `OQ-nnn` or an open-questions anchor, every ID in the index. Listed must be every
  CONFLICT-marked unit (as CONFLICT or OPEN), every conflict-flagged note and every note whose relation is
  `supersedes` or `superseded-by`.
- **L6** hard limit 16,000 tokens per file; **L7** trace IDs exist.
- **L8** `<module> R-<n>` names a module of ADR-0022 rule 2 (or `process`, `cross`) and a numeric rule; a backticked
  `` `<word> ADR-nnnn` `` names a module too.
- **L9** every setting key referenced by any unit of the module is backticked in the body or `Reads`.
- **L10** every rule of the module that another unit supersedes, or whose text says it is superseded, is listed
  under `## Conflicts`.

Several files given together are the chunks of one module: L1, L2, L5, L9, L10 and the section list run over all
of them.

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
