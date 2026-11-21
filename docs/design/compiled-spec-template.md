# Compiled spec template (S3, chief architect, 2026-11-21)

A compiled spec states the **current law of one module** (or one chunk of a large module) in one file, so that a coder or
reviewer needs no ADR history. It is written from the module dossier (`tools/docs/build_dossiers.py`) and checked by
`tools/docs/doc_lint.py`. It replaces no ADR until the author's retirement gate (S4); until then the ADR text wins and a
difference is a defect of the compiled spec.

## Rules of compiling

1. **Current state only.** Fold every note into the rule it amends and state the result once. No "was", "originally",
   "Note (…)" and no history. The history stays in the ADR.
2. **Nothing new.** Every statement comes from a source rule or note, and cites it in the trace table. Where notes contradict
   each other or their rule, do not pick silently: apply the later accepted source (by date, then by ADR number), and list the
   case under `## Conflicts` as `CONFLICT <unit id>: <how resolved, naming the governing ADR unit ID or R-number>`. If the
   order does not decide it, the entry says `OPEN <unit id>: …`, quotes its entry in `docs/open-questions.md` (20 characters
   or more of an unchecked entry), and the spec does not choose.
3. **Proposed is not law.** A rule of a proposed ADR goes only under `## Proposed (not law)`, or carries `[proposed]`.
4. **Generated numbers.** Never type a count of tables, rules, catalog rows, settings, units, sections or entities (the lint
   recomputes these; do not count anything else in words, list it). Write `<!-- count:tables -->N<!-- /count -->`; the lint
   recomputes it, and the noun after it must be of that kind (`count:tables` then `rules` is a finding). Digits in any
   script, Roman, circled, superscript or CJK numerals, `12 (twelve) tables`, `Tables x12` and a number alone on the line
   under `Owned tables:` are counts too.
   Identifiers, thresholds and defaults taken from a rule are quoted from it, not counted: under `## Rules`,
   `## Invariants`, `## Edge cases` and `## Settings` the lint passes a number with a unit (`30 s`, `90 days`,
   `4 decimals`), a standard's number (`ISO 4217`) and a number+noun phrase that also occurs in a source the
   R-number's `Source:` cites, or in the catalog row of the `INV-nn`, `EC-nn` or setting key the row names; a count of
   tables, rules, catalog rows or settings of the spec itself never passes. Elsewhere these exceptions do not apply.
5. **Plain, short sentences** (AGENTS.md). One rule, one numbered statement, one predicate. IDs in backticks.
6. **Law of other modules** is referenced by the other module's compiled spec and rule number in the form `<module> R-<n>`
   (`ledger R-12`), never restated. While that module has no compiled spec yet, cite its source ID (`ADR-0014.R12`) in
   the statement, not in `Source:` (a `Source:` holds the module's own units, L7). A placeholder such as
   `inventory R-scrap` is a lint finding (L8). The `Reads` list of a section may name other modules' tables, catalog
   rows and settings without restating them.
7. **`process` is not a code module.** Its dossier (ADR-0001 to 0005, 0022, 0073) is compiled only if the author asks; the
   coder's `AGENTS.md` and the runbook carry those rules.

## Required sections, in this order

Front matter, as the first lines of the file, before the title (plain lines, or inside one code fence as shown):

```
Module: <module>    Chunk: <n of m | whole>    Source ADRs: <ADR-nnnn, …>
Build step(s): <n, … | not stated>    Generated from index: <git commit of docs/design/generated/rule-index.csv>    Compiled by: <model>, <date>
```

| # | Section | Content | Share of budget |
| --- | --- | --- | --- |
| 1 | `## Purpose` | Two to five sentences: what the module owns, what it does not, its layer (ADR-0022 rule 2). | 2% |
| 2 | `## Entities and tables` | One row per owned table: name, one-line meaning, key, parent, owner module. Columns are in the DDL file, which the spec names (`docs/design/<file>.sql`); do not copy DDL. Every owned table is named here in backticks; a table a rule defines without DDL goes on a line `Defined by rule, without DDL: `<table>``. Other modules' tables it reads are listed apart, as "Reads". | 10% |
| 3 | `## Commands and queries` | One row per command or query: name, actor/authorization (area and verb level), input in one line, effect, emitted events, error codes. Registered names only. | 15% |
| 4 | `## Rules` | Numbered `R1…Rn` (the module's own numbering, stable inside the file). A rule starts at a line `R<n>. ` after a blank line, a heading or the previous rule, and ends with its `Source: ADR-nnnn.Rk[, ….Nj]` line (required); a list or a table may stand inside it before `Source:`. A hard-wrapped line that starts with `R18.` is text, not a rule. The statements carry the rule's content: per source rule of 500 bytes or more (with its notes) they are 0.10 of its size or more, and per module 0.30 of the source rules' size with 40% of their backticked identifiers kept. The `Source` IDs of an R-number and the IDs traced to it in section 11 are the same set (a superseding ID of another module may stand in `Source` without a trace row). Notes are folded in. Accepted law stands here, never in section 10. Group by topic with `###` headings. | 45% |
| 5 | `## Invariants` | Each `INV-nn` that concerns the module, with its check point, in one line, and the rule (R-number) it protects. Every invariant whose catalog `area` is the module is named in backticks; the lint refuses `None` here while the module owns one. | 5% |
| 6 | `## Edge cases` | Each `EC-nn` of the module: the case and the required outcome (`must_succeed` or `must_reject:<code>`). Every edge case whose catalog `area` is the module is named in backticks; the lint refuses `None` here while the module owns one. | 5% |
| 7 | `## Settings` | Each setting key of the module: value type, scopes, core default (or "unset"), and the rule that uses it. Owned catalog rows of other catalogs may be listed here too. The lint refuses `None` here while the module owns a setting. In a chunked module each `INV-nn`, `EC-nn` and setting has its row in one chunk; the others cite it. | 5% |
| 8 | `## UI annotations` | The annotations of ADR-0077 the module's declarations carry: floorplan per route, titles, facets, field annotations, work item kinds, tiles. Headless modules write `None (headless step)`. | 5% |
| 9 | `## Conflicts` | One entry per line and nothing else: `CONFLICT <unit id>: <resolution>` (rule of compiling 2; required for every superseding note and superseded rule), `OPEN <unit id>: "<quote of its open question, which names the unit's ADR>"`, and, only for a note the extractor's conflict flag marked and that proved harmless, `FALSE-POSITIVE <note id>: <reason>`. A flagged note needs its own entry. A wrapped entry continues on indented lines. `None` when there is none. | 3% |
| 10 | `## Proposed (not law)` | Rules of proposed ADRs, or none. | as needed |
| 11 | `## Trace` | Table `Source | Where`: one row per source rule and note ID of the module in the rule index, `Where` is: one or more of the spec's R-numbers; or, when the module is not primary for the unit, `ref: <module> R-<n>` / `ref: ADR-nnnn.Rk` (the primary module's spec states it; the ADR ID is the unit's own or its rule's); or, for a note or a Decision text unit only, `not applicable: <reason>` (non-normative text such as review credits or history; at most 15% of the units; refused for a note that supersedes or is superseded, carries a conflict flag, or names an identifier its rule does not; every such row is printed under `NOT APPLICABLE`); or, for a Decision text unit only, a heading of the spec. Never empty; any other value is a lint finding. No ID may be missing; none may be invented; none of another module. | 10% |

`Source ADRs` lists every ADR of the units the file states (traced to an R-number; `ref:` rows need not be listed);
`Build step(s)` lists steps of the index rows of the module's units, or says `not stated`.

Heading levels: `#` title, `##` sections above, `###` topics inside. Lint chunks by `## ` headings. No section is empty:
sections 3 and 5 to 8 without content say `None: <reason>`; section 2 says `None` only when the module owns no table;
sections 9 and 10 may say `None`. Content is a sentence of 3 or more words, a list item or a table row; `---`, `-` or one
word is not. A reason has a word of 3 or more letters that is not `none`, `nothing`, `nil`, `empty`, `n/a` or `not
applicable`. A citation of a rule or note ID in a statement or a Conflicts reason must exist in the index.

## Size budget

- **Where it is used.** ADR-0073 rule 6 builds the Haiku context pack (at most 30,000 tokens, interim) from the exact text of the
  listed ADR rules and their notes. A compiled-spec chunk may stand in for those rules only after a note at ADR-0073 rule 6
  says so (S4 proposes it, the chief architect decides). Until then the compiled spec is a reading and review aid and the
  pack stays rule-cut. A work package that needs one command takes the chunk holding that command's rules plus section 2
  rows of its tables; the pack builder cuts by R-number, so a chunk is also the unit of cutting.
- The pack also holds the declaration, golden example, signatures and allowlist, so the spec share is **at most 16,000 tokens**
  (about 56,000 bytes; the lint estimates tokens as bytes ÷ 3.5, unverified against a tokenizer).
- Hard limit per file: **16,000 tokens**; soft target **12,000**. A larger module is split into chunks `<module>-<n>.md`, cut at
  `###` topics, never inside a rule. Each chunk repeats section 1 (short) and carries its own rows of 2–8 and 11. A `Conflicts`
  entry lives in the chunk of the rule concerned.
- The trace table costs about 25 bytes per source ID (1,200 IDs ≈ 8,600 tokens), so it is a large fixed cost only for the biggest
  modules; those chunk anyway.
- Expected size: about 55% of the dossier's rule and note text (the pilot on `quality`: 56%). Above 70% the module is a poor
  candidate and S4 reports it instead of compiling it. `MODULES.csv` gives `spec_chunks_est` for planning.
- `cross` units (a rule naming more than three modules) are compiled in their primary module; the other modules cite them
  as `<primary module> R-<n>` (rule 6).

## Acceptance of a compiled spec (mechanical first)

1. `doc_lint.py <file> [<chunk 2> ...] --module <m>`, with all chunks of the module together, prints `LINT PASS` and
   exits 0. `LINT PARTIAL` (exit 3, a chunk linted with `--partial`) is not a pass; a gate never gives `--partial`.
2. A reviewer on a different model spot-checks **20 rules** drawn by seed from the trace table, every rule the lint
   prints under `SUPERSEDED RULES` and every row it prints under `NOT APPLICABLE`: each statement is what the source
   rules and notes say (for a superseded rule, the superseding text and not the old one), a `not applicable` unit
   states no law, and nothing in the spec lacks a source.
3. The lint's REVIEW LIST (every `CONFLICT`, `FALSE-POSITIVE` and `OPEN` entry with its reason, counted per kind, and
   the `NOT APPLICABLE` rows and the stable-key mismatches after it) has been read by the chief architect; every
   `CONFLICT` and `OPEN` entry is accepted by them; an `OPEN` entry quotes its open question in `docs/open-questions.md`.
