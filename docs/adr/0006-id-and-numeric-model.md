# ADR-0006: ID and numeric model

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Amended before its first merge (2026-11-14) by the author's answers: rounding mode per currency (rule 17); rounding differences split into `rounding_gain` and `rounding_loss`, accounts declared per company (rule 20). Design item: DS-02. Related decisions: D4, D5, D10, D13, D14. Principles 2, 5, 6, 9, 10. ADR-0004, ADR-0005.

## Decision

Every table has a single-column primary key `id` of type `uuid`, version 7; rows of catalogs shipped with the core use a version 5 UUID derived from their code, so they are the same in every installation. Commands refer to records by `id` only. Money, quantities, unit prices, exchange rates and percentages each have one PostgreSQL domain and one Python type with a fixed precision; they are exact decimals everywhere and travel in JSON as strings in one canonical form. Rounding and currency conversion happen only in one module, half away from zero by default; an amount is stored at its currency's minor unit; conversion differences that unbalance an entry go to one rounding line on the system account `rounding_gain` or `rounding_loss`; and no rounding difference is ever absorbed into cost without its own line.

### Rules

**IDs**

1. Every table's primary key is one column, `id uuid` (ADR-0004 rule 12). No table has a composite primary key. Tables of third-party libraries are excluded (ADR-0004 rule 9).

   Note ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md), proposed 2026-11-17): `incoterm` (the Incoterms codes, also UN/ECE Recommendation 5) keeps its natural `code` key, like `currency`, and profiles and documents carry `incoterm_code`, as they carry `currency` (ADR-0068 rule 18).
2. IDs are UUID version 7, generated in the command layer with Python's `uuid.uuid7()`. A column default `uuidv7()` covers rows written by database code (e.g. triggers). This requires Python 3.14 or later and PostgreSQL 18 or later (DS-18).
3. A `Create` command accepts an optional `id`. If given, it must be a UUID version 7, otherwise the command is rejected; if absent, the command layer generates it. This lets one command batch refer to a record that an earlier command in the same batch creates. Idempotency (Principle 9) is unchanged. Rows of tables partitioned by `id` (rule 22) always get server-generated IDs.
4. Rows of a catalog shipped with the core (system accounts, transaction keys, movement types, and any later core catalog) have `id = uuid5(f244ce09-3c6c-4c82-af14-918bdeca6be3, "<table>:<code>")`, e.g. `uuid5(…, "system_account:inventory")`. Core catalogs are global: they have no `company_id`. The same row has the same `id` in every installation, test and document.
5. Commands refer to other records only by `id`. Human-readable keys (`code` for master data, the document number from DS-05; their uniqueness scope is set by DS-05 and DS-20) are used by queries: an agent finds an `id` with `List<Noun>` filtered by `code`, then sends the command. There is no second way to reference a record in a command. An error for an unknown `id` names the table and the `List<Noun>` query that finds valid IDs.
6. An `id` carries no business meaning. Business code never reads the timestamp inside a UUID version 7; recording time is its own column (DS-03). The only use of that timestamp is partition bounds (rule 22).
7. In JSON, an `id` is the canonical lowercase hyphenated string.

**Numeric types**

8. Each kind of number has one PostgreSQL domain in the schema `types` (which holds no tables, so domain names never collide with table names) and one Python type in `nativeflows.numeric`:

| PostgreSQL domain | Python type | Base type | Holds | Stored value |
| --- | --- | --- | --- | --- |
| `types.amount` | `Amount` | `numeric(24, 4)` | Money in any currency | At the currency's minor unit (rule 14) |
| `types.quantity` | `Quantity` | `numeric(24, 6)` | Quantities in any unit | At the unit's decimal places, at most 6 (DS-20) |
| `types.unit_price` | `UnitPrice` | `numeric(28, 10)` | Price or cost per unit | At 10 decimal places |
| `types.exchange_rate` | `ExchangeRate` | `numeric(30, 15)` | An exchange rate as published (rule 10) | At 15 decimal places |
| `types.percent` | `Percent` | `numeric(9, 6)` | A percentage written as percent: 8 means 8% | At 6 decimal places |

9. A column holding a percentage ends in `_percent` (`discount_percent`); its value is the percent, never a fraction. This adds `_percent` to the suffix table of ADR-0004 rule 13.
10. An exchange rate is stored as its source publishes it, with the two currencies that say its direction (columns and rate types decided by DS-10). Converting an amount between currencies is done only by `nativeflows.numeric.convert_amount(amount, from_currency, to_currency, rate)`, which multiplies or divides according to the rate's direction and rounds once with `round_amount`. No other code converts.
11. A conversion between units of measure is stored as two positive integers, `numerator` and `denominator`: one alternative unit equals `numerator / denominator` stock units (e.g. 1 carton = 24/1 bottles; 1 gram = 1/1000 kilogram). The factor is exact; rounding of converted quantities and the data model are DS-20.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): a document line stores this factor as its conversion snapshot (`uom_numerator`, `uom_denominator`, `uom_factor_source`) and never reads it again; each product unit is classified exact or inexact at its decimal places: exact when `numerator × 10^dI` is divisible by `denominator × 10^dE` (rules 7, 9).
12. No floating-point type is used for these values anywhere: not `real`, `double precision` or `money` in PostgreSQL, not `float` in Python. CI rejects them in migrations and in core code (DS-18).
13. In JSON (REST, MCP, events), every value of these five kinds is a string. Input must match `^-?(0|[1-9][0-9]*)(\.[0-9]+)?$` (no exponent, no leading zeros, no more decimal places than the domain's scale); a JSON number is rejected. Output is canonical: fixed-point, no exponent, no trailing zeros after the decimal point, no decimal point for whole numbers, and `0` for zero (never `-0`), e.g. `"1000"`, `"12.5"`. Pydantic's defaults do not do this (they accept numbers and may emit `1E+3`), so `nativeflows.numeric` defines each type with a validator that accepts only strings, a serializer that writes the canonical form, and the JSON Schema `{"type": "string", "pattern": …}`. TypeScript receives `string`. `plan_hash` (DS-04) uses the canonical form.

**Rounding**

14. An `amount` is stored at the minor unit of its currency, taken from ISO 4217 in the currency table (VND 0 decimal places, USD 2, KWD 3); `types.amount` keeps 4 decimal places so every ISO 4217 currency fits. An input amount, including one taken from an external document, with more decimal places than its currency allows is rejected, never rounded silently; intake keeps the source document as evidence (DS-24). A `quantity` input with more decimal places than its unit allows is rejected the same way. An amount the core computes is rounded by rule 15.
15. All rounding goes through `nativeflows.numeric` (`round_amount(value, currency)`, `round_quantity(value, unit)`, `round_unit_price(value)`, `round_exchange_rate(value)`, `round_percent(value)`). No other code calls `Decimal.quantize` or `round` on these values; CI checks this (DS-18). `round_quantity` takes an optional rounding mode from rule 17's list, e.g. `up` for component requirements ([ADR-0033](0033-production-master-data.md) rule 6).

    Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): the mode of `round_quantity` follows the use: `up` for requirements, planning proposals, supplier minimums and multiples, issue multiples and backflush; `half_up` for receipts, deliveries, invoices, returns, credits, counts, transfers and issues a person enters (rule 8).
16. Arithmetic uses one decimal context, applied with `decimal.localcontext()` inside each `nativeflows.numeric` function (the decimal context is per thread and per async task, so it is never set globally): precision 60 significant digits, rounding mode `ROUND_HALF_UP`, traps on `InvalidOperation`, `DivisionByZero` and `Overflow`. The largest product of two domain values has 54 digits, so sums and products are exact; a division is rounded once, by the `round_*` function for the value being stored or compared.
17. The rounding mode is configured per currency (author's decision, 2026-11-14): the currency table has `rounding_mode`, one of `half_up` (half away from zero, Python `ROUND_HALF_UP`, the same as PostgreSQL `round()` on `numeric`: 2.5 → 3, −2.5 → −3), `half_even`, `down` (toward zero) and `up` (away from zero); the default is `half_up`, and a localization package may set the default per currency. `round_amount` uses the mode of the amount's currency. A localization package may also declare a mode for a named calculation (e.g. VAT per line); until that legal rule is verified it is flagged configuration (reading guide, rule 4). Where rounding happens for tax (per line or per document) is DS-23.
18. A computed line amount is rounded per line: `round_amount(quantity × unit_price, currency)`; discounts are DS-22. Document totals are sums of rounded line amounts.
19. Converting a quantity to the stock unit (rule 11) never changes the line's amount. How unit cost is derived from it is DS-09.
20. Each journal line's company-currency and group-currency amounts are rounded per line (the conversion path is DS-10). If the rounded lines of an entry do not balance in company currency or in group currency, the posting logic adds one rounding line with transaction amount 0 and the difference in each unbalanced currency, posted to the operational account mapped to the system account `rounding_gain` or `rounding_loss` (DS-07 adds both to the catalog). The account is chosen by the sign of the company-currency difference, or of the group-currency difference when the company-currency difference is zero. Which operational accounts these map to is declared per company when the company is set up (author's decision, 2026-11-14); the localization package proposes defaults (see open questions). In each currency, its absolute value must not exceed half a minor unit times the number of lines of the entry; a larger difference means wrong input, and the command is rejected. Its sign per currency and its transaction currency follow DS-06.
21. No rounding difference is absorbed into inventory value or cost without its own line and derivation trace (Principle 6, [07-shared-foundation.md](../spec/07-shared-foundation.md#units-of-measure)). Costing residuals are posted as explicit lines as DS-09 defines.

**Partitioning**

22. Tables that ADR-0002 partitions by month (outbox, agent run logs; Procrastinate's own tables are excluded by rule 1) are partitioned by range of `id`, whose UUID version 7 prefix orders rows by recording time, so the single-column key holds. `audit_record` and `audit_change` are append-only and partitioned the same way; `audit_denial` is not partitioned ([ADR-0038](0038-audit-and-observability.md) rule 6).
23. The append-only ledger tables keep the single-column `id` key and are not partitioned in Phase 1. If partitioning becomes necessary (ADR-0002 revisit condition), the scheme is decided by ADR at that point. Range of `id` is one option, with the limit that it prunes by recording time, not by posting date or fiscal year. This replaces ADR-0002's sentence that the primary key is chosen for partitioning by fiscal year, and its revisit line "partition by fiscal year". Audit tables are the exception: they are partitioned by rule 22 ([ADR-0038](0038-audit-and-observability.md) rule 6).

    Note (author, 2026-11-19): NativeFlows has no company-size limit. The "SME" reasoning in the options table explains the Phase 1 choice; it is not a ceiling. The scale path is in [go-live.md](../runbook/go-live.md), step 10: ten times the Phase 1 targets must stay possible without restructuring. Ledger partitioning is decided here by ADR when a company's journal approaches 100,000,000 lines.

    Note (author's delegation, 2026-11-21; decided by the chief architect): `journal_line` carries `posting_date` and `fiscal_year_id` ([ADR-0014](0014-universal-journal.md) rule 5 note), copied from its entry, so the primary key stays `id` and the partition plan stays range of `id`; no foreign key to `journal_line` changes. Closed years are archived by detaching old `id` ranges when an ADR decides partitioning near 100,000,000 lines.

## Context

DS-02 is needed by DS-04 (command envelope), DS-06 (journal), DS-10 (multi-currency) and every table. Constraints:

- `Decimal` in Python and `NUMERIC` in PostgreSQL, no floats and no money as strings in the database (ADR-0001, ADR-0002); precision declared centrally ([07-shared-foundation.md](../spec/07-shared-foundation.md#document-lifecycle-numbering-and-posting-periods)).
- Every journal entry balances per transaction, company and group currency, with conversion differences on a rounding line on a defined system account; rounding never silently lands in cost ([05](../spec/05-accounting-inventory-core.md), [07](../spec/07-shared-foundation.md), [12-testing.md](../spec/12-testing.md)).
- Every import is a simulated command batch (D16, [15-migration-ux-docs.md](../spec/15-migration-ux-docs.md)), so a batch must be able to create a partner and then a document that refers to it. After Phase 1 an offline warehouse app queues commands ([07](../spec/07-shared-foundation.md#data-storage-and-synchronization)). Imports above 1,000 rows are staged and posted as a sequence of such batches ([ADR-0030](0030-commercial-seams-and-imports.md) rule 9).
- `plan_hash` excludes surrogate IDs (DS-04), so generated IDs do not affect simulation.
- Agents call the commands through MCP and REST and read JSON (Principle 10). ADR-0005: the option easiest for AI agents wins among correct options.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| `uuid` v7, one column (chosen) | Clients and batches can create IDs before execution; unique across tables, companies and installations; time-ordered, so index inserts stay local; not guessable through the public API | 16 bytes instead of 8; needs Python 3.14 and PostgreSQL 18 |
| `bigint` identity | Smallest, fastest joins | A batch cannot refer to a row before it exists; IDs collide across installations and synthetic datasets; sequential IDs are guessable |
| `uuid` v4 | Widely supported | Random order fragments indexes on large append-only tables |
| Composite key `(fiscal_year, id)` on ledger tables (ADR-0002's partitioning note) | Partition by fiscal year without restructuring | Every foreign key to a ledger row needs two columns; the posting date can change before posting. For an SME the journal is expected to stay within one table's limits |
| Commands accept `id` or `code` | Agents can skip a lookup | Two ways to do one thing; codes can change, IDs cannot |
| Decimals as JSON numbers | Shorter | Many JSON parsers read numbers as binary floats and lose digits |
| One `numeric` type with large scale for all values | One type | Hides the kind of a value; no per-kind check |
| Domains in the default schema | Shorter names | A domain and a table share PostgreSQL's type namespace, so `exchange_rate` could not be both |
| Rates stored in one fixed direction | One formula | Hides the published rate; an inverse with 15 decimals can differ from the official rate by a minor unit on large amounts |
| Percent stored as a fraction (0.08) | Direct multiplication | Agents and people confuse 0.08 with 8; the law and invoices write 8% |

## Constraints that come with the decision

- DS-04: `Create` commands carry an optional `id` (rule 3); command fields reference records by `id` only, and unknown-ID errors name the `List<Noun>` query (rule 5); decimal fields use the `nativeflows.numeric` types and canonical form (rule 13); errors name the rule that failed (e.g. rule 14 for too many decimal places).
- DS-06: at most one rounding line per entry, with signed amounts per currency (rule 20); a check that every stored `amount` is at its currency's minor unit.
- DS-07: system accounts `rounding_gain` and `rounding_loss` in the catalog; catalog IDs by rule 4.
- DS-09: unit cost derivation and costing residuals as explicit lines (rules 19, 21).
- DS-10: currency table with ISO 4217 minor units and `rounding_mode` (rule 17); rates stored as published; conversion only through `convert_amount` (rule 10).
- DS-16: invariants for rules 14 and 20 (amounts at minor unit; rounding line within its bound).
- DS-18: Python 3.14+, PostgreSQL 18+; schema `types` for domains, created by hand-written Alembic migrations (autogenerate does not create domains) and referenced schema-qualified (`types.amount`) in SQLAlchemy; CI rejects floating-point types and rounding or conversion outside `nativeflows.numeric` (rules 10, 12, 15).
- DS-20: unit decimal places (at most 6), the integer conversion pair and rounding of converted quantities (rule 11).

## Revisit when

- The size of `uuid` keys makes a measured query or index more than 20% slower than the same query on `bigint` keys at the large dataset size.
- A currency or unit needs more decimal places than its domain allows.
- The journal grows to where reports are measurably slow (ADR-0002): decide the partitioning by ADR (rule 23).

## Documents updated

- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for the numeric kinds, minor unit, unit conversion and the rounding line.
- [docs/adr/0002-core-technology-tools.md](0002-core-technology-tools.md): note that its partitioning sentence and revisit line are replaced by rule 23.
- [docs/adr/0004-naming-conventions.md](0004-naming-conventions.md): note that rule 9 here adds the `_percent` suffix.
- [docs/design/backlog.md](../design/backlog.md): DS-02 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): operational accounts for `rounding_gain` and `rounding_loss` in TT99; Vietnamese rounding rules for VND amounts and VAT.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
