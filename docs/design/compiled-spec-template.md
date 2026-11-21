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
   case under `## Conflicts` as `CONFLICT <rule id>: <how resolved>`. If the order does not decide it, the entry says
   `OPEN` and goes to `docs/open-questions.md`.
3. **Proposed is not law.** A rule of a proposed ADR goes only under `## Proposed (not law)`, or carries `[proposed]`.
4. **Generated numbers.** Never type a count of tables, rules, columns, settings, commands or queries. Write
   `<!-- count:tables -->N<!-- /count -->`; the lint recomputes it. Identifiers, thresholds and defaults taken from a rule
   are quoted from it, not counted.
5. **Plain, short sentences** (AGENTS.md). One rule, one numbered statement, one predicate. IDs in backticks.
6. **Law of other modules** is referenced by the other module's compiled spec and rule ID (`ledger R-12`), never restated.

## Required sections, in this order

Front matter, as a first block:

```
Module: <module>    Chunk: <n of m | whole>    Source ADRs: <ADR-nnnn, …>
Build step(s): <n, …>    Generated from index: <rule-index.csv commit>    Compiled by: <model>, <date>
```

| # | Section | Content | Share of budget |
| --- | --- | --- | --- |
| 1 | `## Purpose` | Two to five sentences: what the module owns, what it does not, its layer (ADR-0022 rule 2). | 2% |
| 2 | `## Entities and tables` | One row per owned table: name, one-line meaning, key, parent, owner module. Columns are in the DDL file, which the spec names (`docs/design/<file>.sql`); do not copy DDL. Other modules' tables it reads are listed apart, as "Reads". | 10% |
| 3 | `## Commands and queries` | One row per command or query: name, actor/authorization (area and verb level), input in one line, effect, emitted events, error codes. Registered names only. | 15% |
| 4 | `## Rules` | Numbered `R1…Rn` (the module's own numbering, stable inside the file). Each rule: statement, then `Source: ADR-nnnn.Rk[, ….Nj]`. Notes are folded in. Group by topic with `###` headings. | 45% |
| 5 | `## Invariants` | Each `INV-nn` that concerns the module, with its check point, in one line, and the rule (R-number) it protects. | 5% |
| 6 | `## Edge cases` | Each `EC-nn` of the module: the case and the required outcome (`must_succeed` or `must_reject:<code>`). | 5% |
| 7 | `## Settings` | Each setting key of the module: value type, scopes, core default (or "unset"), and the rule that uses it. | 5% |
| 8 | `## UI annotations` | The annotations of ADR-0077 the module's declarations carry: floorplan per route, titles, facets, field annotations, work item kinds, tiles. Headless modules write `None (headless step)`. | 5% |
| 9 | `## Conflicts` | Every `CONFLICT <rule id>: <resolution>` (rule of compiling 2), also those found by the extractor's conflict flag that proved harmless: `FALSE-POSITIVE <note id>`. | 3% |
| 10 | `## Proposed (not law)` | Rules of proposed ADRs, or none. | as needed |
| 11 | `## Trace` | Table `Source | Where`: one row per source rule and note ID of the module in the rule index, `Where` is the spec's R-number, section or `not applicable: <reason>` (only for non-normative notes such as thanks, review credits, history). No ID may be missing; none may be invented. | 10% |

Heading levels: `#` title, `##` sections above, `###` topics inside. Lint chunks by `## ` headings.

## Size budget

- A **context pack** for the Haiku coder is at most **30,000 tokens** (ADR-0073 rule 6, interim). It holds the declaration,
  the golden example, the signatures and the allowlist as well, so the module's share is **at most 16,000 tokens** of
  compiled spec (about 56,000 bytes; the lint estimates tokens as bytes ÷ 3.5).
- Hard limit per compiled-spec file: **16,000 tokens**. Soft target: 12,000. A larger module is split into **chunks**, each its
  own file named `<module>-<n>.md`, cut at `###` topics, never inside a rule. Every chunk repeats sections 1 (short) and 11
  (its own rows only) and carries its slice of 2–8. The module's `Conflicts` live in the chunk of the rule concerned.
- The trace table is the largest fixed cost (about 25 bytes per source ID). A module with more than about 1,200 source IDs
  needs chunking for that reason alone.
- If the dossier of a module is under 16,000 tokens, the compiled spec is under it too; if it is over, the compiled spec
  targets 55% of the dossier (the rest is history, review credits and DDL the compile drops). Measure the first compile; if
  the ratio is above 70%, the module is a poor candidate and S4 reports it instead of compiling it.

## Acceptance of a compiled spec (mechanical first)

1. `doc_lint.py <file> --module <m>` prints `LINT PASS`.
2. A reviewer on a different model spot-checks **20 rules** drawn by seed from the trace table: each statement is
   what the source rules and notes say, and nothing in the spec lacks a source.
3. Every `CONFLICT` and `OPEN` entry has been seen by the chief architect; an `OPEN` entry has an open question.
