# ADR-0004: Naming conventions

Status: accepted (2026-11-14). Drafted by an agent; the author delegated all technical decisions to the agent, with ease of use by AI agents as the overriding goal, and accepted by that instruction. [ADR-0006](0006-id-and-numeric-model.md) rule 9 adds the suffix `_percent` to rule 13. [ADR-0014](0014-universal-journal.md) rule 5: currency code columns (`transaction_currency` etc.) are foreign keys to `currency.code` without the `_id` suffix, an exception to rule 12. Design item: DS-01. Related decisions: D4, D8, D13, D14. Principles 1, 2, 5, 7, 8, 9, 10.

## Decision

Every code identifier is an English word or phrase from the glossary in [00-reading-guide.md](../spec/00-reading-guide.md), written in one form from the database column to the TypeScript type, with no aliases. Tables, columns, modules and fields are `snake_case`; command types and event types are `PascalCase`. A command type is a verb from the command verb list followed by a glossary noun (`PostGoodsReceipt`); an event type is that noun followed by the verb's event form (`GoodsReceiptPosted`). Table names are unique across the whole database. Abbreviations are allowed only from the list in the glossary. This ADR fixes names only: where tables live, key composition, column types, lifecycle rules and schemas belong to the DS items named in each rule. The rules below are the full convention; the glossary holds the words.

### Rules

**General**

1. Identifiers use English words from the glossary, in American spelling. When the glossary has no word for a new concept, the change that introduces the identifier adds a glossary row (AGENTS.md).
2. No abbreviations except those in the glossary's allowed-abbreviations table. `quantity`, not `qty`; `receivable`, not `ar`. In `PascalCase`, an allowed abbreviation is written as a word: `Fx`, `Vat`, `GrIr`.
3. One identifier end to end: a database column, the pydantic field, the JSON key, the MCP argument and the generated TypeScript property have the same name. No `alias`, no camelCase conversion in the API.
4. An identifier is never a word marked reserved for PostgreSQL in Appendix C of the PostgreSQL documentation, a Python keyword, or a name reserved by pydantic `BaseModel` (the `model_` prefix, `schema`, `json`, `dict`, `copy`). Use a more specific glossary word instead (`sales_order`, not `order`).
5. Official codes from law or standards (accounting regimes, statutory forms) appear only as data or inside the localization package that owns them, lowercased (`tt99`, `b01`). The owning DS item (DS-19, DS-23, DS-26) fixes the form of codes that contain other characters, such as `01/GTGT`. Account numbers such as 131 are data, never identifiers.

   Note: statutory report and book codes follow the form of return forms: lowercase, every non-alphanumeric character as `_` (the TT99 form `B01-DN` is `b01_dn`), the official label kept as data ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 2).
6. Identifiers are at most 63 bytes, PostgreSQL's limit. CI checks every database identifier, including the names a naming convention generates (checked before SQLAlchemy shortens them), sequence, partition and trigger names, and rejects a longer name instead of letting it be truncated.

**Modules and packages**

7. The Python distribution and top-level package is `nativeflows`; each module is `nativeflows.<module>`. A module name is one or two lowercase English words in `snake_case` (e.g. `ledger`, `master_data`). DS-18 decides the module list and whether modules map to PostgreSQL schemas; if a module has its own schema, the schema has the module's name. Decided in [ADR-0022](0022-repository-and-engineering-conventions.md) rules 2, 7: one schema `nativeflows`; test tooling lives in separate top-level packages `nativeflows_<tool>` that the product never imports.
8. Localization packages are named `l10n_<country>`, with the ISO 3166-1 alpha-2 code in lowercase (`l10n_vn`, `l10n_us`). An accounting regime inside a package is identified by its official code in lowercase (`tt99`, `tt133`). How a package is packaged and loaded is DS-14.

**Database objects**

9. Table names are singular `snake_case` nouns from the glossary (`journal_entry`, `material_document`) and unique across the whole database, so a glossary identifier names one table. Tables created by a third-party library (Alembic's `alembic_version`, Procrastinate's `procrastinate_*`) keep the library's names and are outside these rules.
10. A line table is `<header>_line` unless the glossary names it otherwise (`journal_line`).
11. A link table for a many-to-many relation is named after the relation when the glossary has a word for it; otherwise `<table_a>_<table_b>` in alphabetical order.
12. A surrogate key column is named `id`; whether a table's primary key also contains other columns (e.g. for partitioning) is decided by DS-02 and DS-06. A foreign key column is `<relation>_id`, where the relation name is the referenced table's name (`partner_id`, `company_id`) or, when a table refers to the same table more than once or the glossary names the relation, that relation name (`reversal_of_id` for the relation `reversal_of`). There are no exceptions to the `_id` suffix, so an agent can tell every foreign key by its name.

    Note (S2 schema phase B, 2026-11-21): a foreign key column that references the natural unique `code` or `key` column of a reference catalog (`currency`, `incoterm`: class E1 of the [ADR-0006](0006-id-and-numeric-model.md) rule 1 note) or of an installation registry (class E2) keeps its name, e.g. `transaction_currency`, `incoterm_code`, `setting_key`, `consumer`. Every foreign key to an `id` is `<relation>_id`. Every table's surrogate key is the single column `id` (ADR-0006 rule 1 note); a former composite key is a named `UNIQUE` constraint.
13. Column suffixes and prefixes by meaning. The examples show the form only; the actual columns of each table are decided by DS-02, DS-03, DS-06 and DS-10.

| Kind | Form | Example |
| --- | --- | --- |
| Boolean | `is_<adjective>` or `has_<noun>` | `is_postable`, `has_lot` |
| Point in time | `<event>_at` | `posted_at` |
| Calendar date | `<meaning>_date` | `posting_date` |
| Amount | `<currency type>_amount`, currency types from the glossary; how debit and credit are represented is DS-06 | `transaction_amount`, `company_amount` |
| Quantity | `quantity`, or `<unit role>_quantity` when more than one unit is stored | `quantity`, `purchase_quantity` |
| Count | `<noun>_count` | `line_count` |
| Lifecycle state | `state`, for every lifecycle, work items included; never `status` | `state` |
| Human-readable key, display text | `code`, `name` | `code`, `name` |

14. Enumerated values are lowercase `snake_case` English words (`pending_approval`, `soft_locked`). They are stored as `text` with a `CHECK` constraint or as a reference table, never as a PostgreSQL `ENUM` type, so a value can be added or retired in an ordinary migration. Their UI labels go through i18n.
15. Constraint and index names come from one SQLAlchemy `MetaData` naming convention: `pk_<table>`, `fk_<table>_<column>`, `uq_<table>_<columns>`, `ix_<table>_<columns>`, `ck_<table>_<name>`, where every `CHECK` constraint is given an explicit `<name>`. Triggers, which the convention does not cover, are named by hand `trg_<table>_<purpose>`.
16. Other database objects: views are named like tables, as nouns, with no prefix, and share the database-wide uniqueness of rule 9 (placement is DS-33); sequences keep PostgreSQL's default `<table>_<column>_seq`; partitions are `<table>_<yyyy>` or `<table>_<yyyy>_<mm>`; database roles are `nativeflows_<purpose>` (the roles themselves are DS-15).

    Placement: views are in schema `query`, named as nouns that never equal a table name ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 42).

**Commands, queries and events**

17. A command type is `PascalCase` verb + noun: a verb from the command verb list in the glossary, then a glossary noun (`CreatePurchaseOrder`, `PostGoodsReceipt`, `MatchBankLine`). The pydantic class has the same name. The verb list gives each verb's intent only; which states and preconditions allow a command is decided by DS-05 and the DS item that owns the noun.
18. Simulation is a mode of every command (Principle 2), never a separate command type: there is no `SimulatePostGoodsReceipt`.
19. The `snake_case` form of a command type is derived mechanically (`post_goods_receipt`) and used for the MCP tool name and the Python handler function. It is at most 64 characters, the tool-name limit of the Anthropic API used behind the LLM gateway (ADR-0002). The REST path is decided in DS-04 and uses one of the two forms.
20. A new verb is added to the verb list, with its intent and event form, in the same change as the first command that needs it. A verb never takes a second meaning; a different action gets a different verb.
21. Read-only operations are queries, not commands: `Get<Noun>` returns one record, `List<Noun>` returns a filtered list. They carry no idempotency key and change nothing. Query names follow the same format, `snake_case` derivation and 64-character limit as command types (rules 17 and 19).

    Note (catalog review, 2026-11-15): `Evaluate<Noun>` is a third query form: it computes a result from the inputs it is given and stores nothing, as `EvaluateConfiguration` does ([ADR-0046](0046-product-configuration.md) rule 17). Its verb is in the glossary's verb list and in authorization-verb-levels.csv at level `read`, and the registry accepts `Get`, `List` and `Evaluate` as the first word of a query. `WorkItemRaised` takes the verb Raise, added to the same lists.
22. An event type is `PascalCase` noun + the verb's event form from the verb list and names a fact that happened (`GoodsReceiptPosted`). A command `<Verb><Noun>` that succeeds emits `<Noun><event form>` when it emits an event. Event types are unique across modules; the event schema and its versioning are decided in DS-13.

**Code**

23. Python follows PEP 8 naming, checked by ruff's `N` rules. File naming for TypeScript is decided in DS-18 and DS-30, because the router generates some file names. Decided: kebab-case, as ADR-0022 rule 24 says ([ADR-0040](0040-ui-architecture.md) rule 18).

## Context

DS-01 must be decided before DS-02 to DS-18, because every later design item names tables, columns, commands and events ([backlog.md](../design/backlog.md)). Constraints:

- English source for code, data model and command names; Vietnamese is shipped as a translation (D8, Principle 1, [06-localization.md](../spec/06-localization.md)). Transliterated Vietnamese identifiers are forbidden (reading guide, rule 6).
- pydantic v2 command schemas are the single source for JSON Schema, REST, MCP and the TypeScript types (ADR-0001, ADR-0002, Principle 10). Any renaming between layers would have to be written and kept in sync by hand.
- SQLAlchemy 2 Core and Alembic generate constraint names; PostgreSQL truncates identifiers longer than 63 bytes, and SQLAlchemy shortens convention names with a hash suffix, both without error.
- Modules call each other only through commands and events, checked by import-linter ([07-shared-foundation.md](../spec/07-shared-foundation.md#extensibility-and-upgrades)). The module list and the database layout are decided in DS-18.
- The author's overriding goal for technical choices is that the system is easy for AI agents to use; when options compete, the more uniform and machine-checkable one wins.
- Most code is written by AI agents (ADR-0001). The format rules (case, regular expression, verb list, length) can be checked by the command registry and CI; the choice of glossary word is checked by the reviewer (runbook stage 5).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Commands: `PascalCase` verb + noun, closed verb list (chosen) | Principle 1 already uses `PostGoodsReceipt`; one verb per action | A verb must be added before its first command |
| Commands: dotted lowercase (`ledger.goods_receipt.post`) | Module visible in the name | Longer; a second style next to Principle 1 |
| Commands: free choice of verb | No list to maintain | Agents invent synonyms (`Book`, `Commit`, `Finalize` for one action) |
| Fields: one `snake_case` name end to end (chosen) | No mapping; database, API and generated types agree | TypeScript code reads `snake_case` properties |
| Fields: camelCase JSON with pydantic aliases | Idiomatic TypeScript | Two names per field and a mapping to keep in sync |
| Tables: singular, unique across the database (chosen) | Matches the glossary; one identifier, one table | None found |
| Tables: plural, or prefixed per module (`ledger_journal_line`) | Common in other frameworks; module visible | Plural differs from the glossary; prefixes are long and change when a table moves |
| Enumerated values: `text` + `CHECK` or reference table (chosen) | Values added or retired in an ordinary migration | Valid values live in a constraint, not a type |
| Enumerated values: PostgreSQL `ENUM` | Compact, typed | Values cannot be removed or reordered; restrictions when adding one inside a transaction |
| Events: `PascalCase` past tense (chosen) | Fact and intent have different names; same style as commands | None found |
| Events: same name as the command | One name | Blurs the command (intent) and the event (fact) |

## Constraints that come with the decision

- DS-04: the command registry rejects a command type or query that does not match `^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+$`, whose first word is not in the verb list (`Get` or `List` for a query), or whose `snake_case` form exceeds 64 characters; it derives the `snake_case` form; it defines no field aliases.
- DS-13: event types follow rule 22; the registry rejects duplicates across modules.
- DS-18: ruff `N` rules enabled; one `MetaData` naming convention for all modules; a CI check rejects identifiers longer than 63 bytes before truncation (rule 6) and identifiers on the reserved lists (rule 4).
- Every DS item that introduces a table, column, command, event or verb adds its new words to the glossary in the same change.

## Revisit when

- Generated constraint names exceed 63 bytes often enough that more than five shortenings are needed: add abbreviations to the allowed list.
- A client that must be supported cannot consume `snake_case` JSON.
- The verb list passes 30 verbs: check for synonyms and merge.

## Documents updated

- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): rules 6 and 7 point here; glossary rows added; command verb list and allowed abbreviations added.
- [docs/design/backlog.md](../design/backlog.md): DS-01 row links to this ADR.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): three questions raised by this ADR, closed by it: foreign key column for `reversal_of`; `state` for work items; `derivation_trace` for Principle 6's trace.
- [docs/spec/02-principles.md](../spec/02-principles.md): Principle 8 says a work item has a state.
- [docs/runbook/step-log.md](../runbook/step-log.md): DS-01 entry.
- [AGENTS.md](../../AGENTS.md): naming rule points here.
