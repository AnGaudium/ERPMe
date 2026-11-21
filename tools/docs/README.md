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
python tools/docs/build_dossiers.py --out OUT/dossiers     # <module>.md, cross.md, unassigned.md, MODULES.csv
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
| `build_dossiers.py` | same as the index | `<module>.md` per module of ADR-0022 rule 2, `cross.md`, `unassigned.md`, `MODULES.csv` |
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
- **modules** of a unit: the owners of its tables; else the modules gen_overview declares for its ADR; else
  `unassigned`. A note takes its owner's modules plus the owners of its own tables. More than 3 modules ->
  `modules = cross`, the full list in `modules_all`.
- **build step**: the first `step N` / `build step N` (vocabulary of spec 11) in the unit, for a note else in its
  owner; else the ADR's step: the first in its header and `.D0`, else the step it names most often.
- **tokens** are bytes / 3.5. `chunks_needed` = tokens / 30,000 rounded up (ADR-0073 rule 6 context pack).

## Lint checks

L1 trace covers every module ID; L2 owned tables and catalog rows backticked in the body; L3 proposed rules only
under `## Proposed (not law)` or with `[proposed]`, never on accepted rules; L4 no bare number before a counted noun,
`<!-- count:KIND -->N<!-- /count -->` recomputed (tables, columns, rules, notes, sections, settings, invariants,
edge-cases, catalog-rows; other kinds such as commands are a finding, as the index cannot count them); L5 every
CONFLICT-marked unit as `CONFLICT <id>: <resolution>`, every conflict-flagged note as `CONFLICT` or
`FALSE-POSITIVE <id>` under `## Conflicts`; L6 hard limit 16,000 tokens per file, section sizes reported; L7 trace IDs
exist. Several files given together are the chunks of one module: L1, L2 and L5 run over all of them.

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
- Module assignment uses only table ownership and gen_overview's declared ADRs; a rule about a module that names no
  table and whose ADR declares no module is `unassigned`.
- `doc_lint` L4 recognises digits only, not number words, and allows one word between the number and the noun.
