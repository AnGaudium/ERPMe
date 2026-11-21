Module: numeric    Chunk: whole    Source ADRs: ADR-0006
Build step(s): 0    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: numeric

## Purpose

`numeric` owns the ID model and the numeric model of the core: the single-column `id uuid` key of every table, the
PostgreSQL domains of schema `types` and the Python types of `nativeflows.numeric` for money, quantities, unit prices,
exchange rates and percentages, their canonical JSON form, and every rounding and currency conversion. It is a layer-1
foundation module (ADR-0022.R2) and owns no table, command or setting. It does not own the rules for IDs in commands
(ADR-0006.R3, ADR-0006.R5), the rounding line of a journal entry on the system account `rounding_gain` or
`rounding_loss` (ADR-0006.R20), or the ban on absorbing a rounding difference into inventory value or cost without its
own line (ADR-0006.R21).

## Entities and tables

None: the module owns no table. Its database objects are the domains of schema `types` (R10), which holds no tables.

Reads: `currency` (minor unit, `rounding_mode`), `incoterm`, `barcode`, `setting_definition`, `setting_preset`,
`setting_preset_item`, `extension_point`, `event_consumer`, `public_mail_domain`, `planning_setting`, `planning_state`,
`production_structure`, `configuration_state`, `system_account`, `audit_record`, `audit_change`, `audit_denial`,
`journal_line`.

## Commands and queries

None: the sources register no command or query for `numeric`.

Contract functions of `nativeflows.numeric`, not registered commands: `convert_amount(amount, from_currency,
to_currency, rate)` (R14); `round_amount(value, currency)`, `round_quantity(value, unit)`, `round_unit_price(value)`,
`round_exchange_rate(value)`, `round_percent(value)` (R18). Python types: `Amount`, `Quantity`, `UnitPrice`,
`ExchangeRate`, `Percent` (R10). The sources name no error code for the rejections of R13 and R17.

## Rules

### Identifiers

R1. Every table's primary key is one column, `id uuid` (ADR-0004.R12). No table has a composite primary key. Tables of
third-party libraries are excluded (ADR-0004.R9). The rule holds for every table of the design DDL, with the exception
classes E1 (R2), E2 (R3) and E3 (R4) only. `id` has no default (R6), except `barcode.id DEFAULT uuidv7()`, whose rows
the barcode trigger writes. Partitioned tables need no exception: they are partitioned by range of `id` (R22), so `id`
alone is their key. The lab's `gen_overview.py --check` fails on any other primary key.
Source: ADR-0006.R1, ADR-0006.R1.N2

R2. **E1:** an installation reference catalog of a published standard keeps its natural `code` key. The class holds
`currency` (ISO 4217) and `incoterm` (ICC Incoterms, also UN/ECE Recommendation 5) and no other table. Foreign keys to
them keep their column names (`transaction_currency`, `incoterm_code`; ADR-0004.R12 note; ADR-0011.R2); profiles and
documents carry `incoterm_code`, as they carry `currency` (ADR-0068.R18). The CI allowlist of the class is
`KEY_ALLOWLIST` in the lab's `gen_overview.py` (the DS-18 check takes it over); a further entry needs a note at
ADR-0006.R1.
Source: ADR-0006.R1.N1, ADR-0006.R1.N2

R3. **E2:** an installation registry (`setting_definition`, `setting_preset`, `setting_preset_item`,
`extension_point`, `event_consumer`, `public_mail_domain`) has `id uuid` = uuid5 of the namespace of R7 and
`'<table>:<key>'`, computed by the loader as for core catalogs, with the old key kept `UNIQUE`; its foreign keys by key
stay.
Source: ADR-0006.R1.N2

R4. **E3:** a one-row-per-company table (`planning_setting`, `planning_state`, `production_structure`,
`configuration_state`) has `id` and `UNIQUE (company_id)`.
Source: ADR-0006.R1.N2

R5. Every other table with a natural or composite key has `id uuid PRIMARY KEY` and keeps that key as the named
constraint `uq_<table>_<columns>` (ADR-0004.R15; `uq_<table>_key` where that name would exceed 63 bytes, ADR-0004.R6);
the foreign keys that target the natural key keep working against it.
Source: ADR-0006.R1.N2

R6. IDs are UUID version 7, generated in the command layer with Python's `uuid.uuid7()`. A column default `uuidv7()`
covers rows written by database code (for example triggers). This requires Python 3.14 or later and PostgreSQL 18 or
later (DS-18).
Source: ADR-0006.R2

R7. Rows of a catalog shipped with the core (system accounts, transaction keys, movement types, and any later core
catalog) have `id = uuid5(f244ce09-3c6c-4c82-af14-918bdeca6be3, "<table>:<code>")`, for example
`uuid5(…, "system_account:inventory")` for the system account `inventory`. Core catalogs are global: they have no
`company_id`. The same row has the same `id` in every installation, test and document.
Source: ADR-0006.R4

R8. An `id` carries no business meaning. Business code never reads the timestamp inside a UUID version 7; recording
time is its own column (DS-03). The only use of that timestamp is partition bounds (R22).
Source: ADR-0006.R6

R9. In JSON, an `id` is the canonical lowercase hyphenated string.
Source: ADR-0006.R7

### Numeric kinds

R10. Each kind of number has one PostgreSQL domain in the schema `types` (which holds no tables, so domain names never
collide with table names) and one Python type in `nativeflows.numeric`:
- `types.amount`, `Amount`, base type `numeric(24, 4)`: money in any currency, stored at the currency's minor unit (R17).
- `types.quantity`, `Quantity`, base type `numeric(24, 6)`: quantities in any unit, stored at the unit's decimal
  places, at most 6 (DS-20).
- `types.unit_price`, `UnitPrice`, base type `numeric(28, 10)`: price or cost per unit, stored at 10 decimal places.
- `types.exchange_rate`, `ExchangeRate`, base type `numeric(30, 15)`: an exchange rate as published (R14), stored at
  15 decimal places.
- `types.percent`, `Percent`, base type `numeric(9, 6)`: a percentage written as percent (8 means 8%), stored at 6
  decimal places.
Source: ADR-0006.R8

R11. A column holding a percentage ends in `_percent` (`discount_percent`); its value is the percent, never a
fraction. `_percent` is part of the suffix table of ADR-0004.R13.
Source: ADR-0006.R9

R12. No floating-point type is used for these values anywhere: not `real`, `double precision` or `money` in
PostgreSQL, not `float` in Python. CI rejects them in migrations and in core code (DS-18).
Source: ADR-0006.R12

R13. In JSON (REST, MCP, events), every value of the kinds of R10 is a string. Input must match
`^-?(0|[1-9][0-9]*)(\.[0-9]+)?$` (no exponent, no leading zeros, no more decimal places than the domain's scale); a
JSON number is rejected. Output is canonical: fixed-point, no exponent, no trailing zeros after the decimal point, no
decimal point for whole numbers, and `0` for zero (never `-0`), for example `"1000"`, `"12.5"`. `nativeflows.numeric`
defines each type with a validator that accepts only strings, a serializer that writes the canonical form, and the
JSON Schema `{"type": "string", "pattern": …}`; Pydantic's defaults are not used, because they accept numbers and may
emit `1E+3`. TypeScript receives `string`. `plan_hash` (DS-04) uses the canonical form.
Source: ADR-0006.R13

### Conversion

R14. An exchange rate is stored as its source publishes it, with the currencies that say its direction (columns and
rate types decided by DS-10). Converting an amount between currencies is done only by
`nativeflows.numeric.convert_amount(amount, from_currency, to_currency, rate)`, which multiplies or divides according
to the rate's direction and rounds once with `round_amount`. No other code converts.
Source: ADR-0006.R10

R15. A conversion between units of measure is stored as a pair of positive integers, `numerator` and `denominator`:
one alternative unit equals `numerator / denominator` stock units. The factor is exact; rounding of converted
quantities and the data model are DS-20. A document line stores this factor as its conversion snapshot
(`uom_numerator`, `uom_denominator`, `uom_factor_source`) and never reads it again. Each product unit is classified
exact or inexact at its decimal places: exact when `numerator × 10^dI` is divisible by `denominator × 10^dE`
(ADR-0056.R7, ADR-0056.R9).
Source: ADR-0006.R11, ADR-0006.R11.N1

R16. Converting a quantity to the stock unit (R15) never changes the line's amount. How unit cost is derived from it
is DS-09.
Source: ADR-0006.R19

### Rounding

R17. An `amount` is stored at the minor unit of its currency, which each `currency` row carries from ISO 4217;
`types.amount` keeps 4 decimal places so every ISO 4217 currency fits. An input amount, including one taken from an
external document, with more decimal places than its currency allows is rejected, never rounded silently; intake keeps
the source document as evidence (DS-24). A `quantity` input with more decimal places than its unit allows is rejected
the same way. An amount the core computes is rounded by R18.
Source: ADR-0006.R14

R18. All rounding goes through `nativeflows.numeric` (`round_amount(value, currency)`, `round_quantity(value, unit)`,
`round_unit_price(value)`, `round_exchange_rate(value)`, `round_percent(value)`). No other code calls
`Decimal.quantize` or `round` on these values; CI checks this (DS-18). `round_quantity` takes an optional rounding mode
from the list of R20, and the mode follows the use (ADR-0056.R8): `up` for requirements (component requirements,
ADR-0033.R6), planning proposals, supplier minimums and multiples, issue multiples and backflush; `half_up` for
receipts, deliveries, invoices, returns, credits, counts, transfers and issues a person enters.
Source: ADR-0006.R15, ADR-0006.R15.N1

R19. Arithmetic uses one decimal context, applied with `decimal.localcontext()` inside each `nativeflows.numeric`
function (the decimal context is per thread and per async task, so it is never set globally): precision 60 significant
digits, rounding mode `ROUND_HALF_UP`, traps on `InvalidOperation`, `DivisionByZero` and `Overflow`. The largest
product of a pair of domain values has 54 digits, so sums and products are exact; a division is rounded once, by the
`round_*` function for the value being stored or compared.
Source: ADR-0006.R16

R20. The rounding mode is configured per currency: the `currency` table has `rounding_mode`, one of `half_up` (half
away from zero, Python `ROUND_HALF_UP`, the same as PostgreSQL `round()` on `numeric`: 2.5 → 3, −2.5 → −3),
`half_even`, `down` (toward zero) and `up` (away from zero). The default is `half_up`, and a localization package may
set the default per currency. `round_amount` uses the mode of the amount's currency. A localization package may also
declare a mode for a named calculation; until that legal rule is verified it is flagged configuration (reading guide,
rule 4). Where rounding happens for tax (per line or per document) is DS-23.
Source: ADR-0006.R17

R21. A computed line amount is rounded per line: `round_amount(quantity × unit_price, currency)`; discounts are
DS-22. Document totals are sums of rounded line amounts.
Source: ADR-0006.R18

### Partitioning

R22. Tables that ADR-0002 partitions by month (outbox, agent run logs) are partitioned by range of `id`, whose UUID
version 7 prefix orders rows by recording time, so the single-column key holds. `audit_record` and `audit_change` are
append-only and partitioned the same way; `audit_denial` is not partitioned (ADR-0038.R6). Procrastinate is dropped
(OPT-08; ADR-0031.R15 note; ADR-0002 note) subject to a spike at step 0: once the spike confirms it, there are no
Procrastinate tables to exclude; if the spike needs more than one small module, Procrastinate stays and its own tables
are excluded as third-party tables (R1).
Source: ADR-0006.R22, ADR-0006.R22.N1

R23. The append-only ledger tables keep the single-column `id` key and are not partitioned in Phase 1. The scheme is
decided by an ADR when a company's journal nears 100,000,000 lines (ADR-0002 revisit condition). Range of `id` is one
option, with the limit that it prunes by recording time, not by posting date or fiscal year. `journal_line` carries
`posting_date` and `fiscal_year_id` (ADR-0014.R5 note), copied from its entry at insert and never changed, which keeps
a scheme by date or fiscal year available to that ADR; the primary key stays `id`. This rule governs in place of
ADR-0002's sentence that the primary key is chosen for partitioning by fiscal year and its revisit line "partition by
fiscal year". Audit tables are the exception: they are partitioned by R22 (ADR-0038.R6). NativeFlows has no
company-size limit: the Phase 1 choice is not a ceiling, and ten times the Phase 1 targets must stay possible without
restructuring (go-live runbook, step 10).
Source: ADR-0006.R23, ADR-0006.R23.N1, ADR-0006.R23.N2

## Invariants

None: the invariant catalog holds no `INV` row for `numeric`.

## Edge cases

None: the edge-case catalog holds no `EC` row for `numeric`.

## Settings

None: the module has no setting key; the rounding mode is the column `rounding_mode` of `currency` (R20).

## UI annotations

None: the sources hold no ADR-0077 annotation for this module.

## Conflicts

CONFLICT ADR-0006.R22: the exclusion of Procrastinate's own tables is governed by ADR-0006.R22.N1 (Procrastinate dropped, conditional on the step 0 spike), stated in R22.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0006.D0 | Purpose |
| ADR-0006.R1 | R1 |
| ADR-0006.R1.N1 | R2 |
| ADR-0006.R1.N2 | R1-R5 |
| ADR-0006.R2 | R6 |
| ADR-0006.R4 | R7 |
| ADR-0006.R6 | R8 |
| ADR-0006.R7 | R9 |
| ADR-0006.R8 | R10 |
| ADR-0006.R9 | R11 |
| ADR-0006.R10 | R14 |
| ADR-0006.R11 | R15 |
| ADR-0006.R11.N1 | R15 |
| ADR-0006.R12 | R12 |
| ADR-0006.R13 | R13 |
| ADR-0006.R14 | R17 |
| ADR-0006.R15 | R18 |
| ADR-0006.R15.N1 | R18 |
| ADR-0006.R16 | R19 |
| ADR-0006.R17 | R20 |
| ADR-0006.R18 | R21 |
| ADR-0006.R19 | R16 |
| ADR-0006.R22 | R22 |
| ADR-0006.R22.N1 | R22 |
| ADR-0006.R23 | R23 |
| ADR-0006.R23.N1 | R23 |
| ADR-0006.R23.N2 | R23 |
