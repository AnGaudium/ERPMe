Module: clock    Chunk: whole    Source ADRs: ADR-0007
Build step(s): 0    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `clock`

## Purpose

`clock` (`nativeflows.clock`) owns the time model: the two kinds of time (business dates and system timestamps), the
types `BusinessDate` and `Instant`, the functions `clock.now()` and `clock.today(company)`, and the rules for
`recorded_at`, time zones, durations and ranges. It is a layer-1 module (ADR-0022.R2) and owns no table: the override
table of the business date belongs to `periods`, and the fiscal calendar (fiscal years and posting periods as data) is
law of `periods`. Which date selects an exchange rate, a tax rate or a due date is not decided here (DS-10, DS-23 and
the localization package decide it).

## Entities and tables

None: `clock` is a layer-1 module and owns no table (R27).

Reads: `business_date_override` (owner `periods`, DDL `docs/design/DS-05-platform.sql`, one row per company), through
a hook; `company.time_zone` (owner `master_data`).

## Commands and queries

None: the sources name no registered command or query of `clock`.

Contract functions (not registered commands): `clock.now()` (R15, R22), `clock.today(company)` (R22, R23).
Hook: `periods` registers the reader of `business_date_override`, `app` wires it (R27).
Database convention: shared trigger function `set_recorded_at`, trigger `trg_<table>_set_recorded_at`, `refuse_truncate` (R12 to R14).
The command that writes `business_date_override` is not named by the sources (R26).
Error code bound to no named command: `as_of_date_out_of_range` (raised by the dispatcher, R24).

## Rules

### Kinds of time and types

R1. There are two kinds of time and they never mix. Business dates are calendar dates (`date`, no time zone) chosen by people or source documents. System timestamps are instants (`timestamptz`, stored and sent in UTC) set only by the system. The current instant always comes from the real database transaction time; the current business date comes from one clock function that tests and the simulator can set per company. The dimensions `document_date` and `posting_date` of the analysis catalog carry the dates of R8 and R9.
Source: ADR-0007.D0

R2. A business date is a PostgreSQL `date` with a name ending in `_date` (ADR-0004.R13). It has no time zone and is never converted between time zones.
Source: ADR-0007.R1

R3. A system timestamp is a PostgreSQL `timestamptz` with a name ending in `_at`. `timestamp without time zone` is not used. Database sessions and application servers run with time zone UTC.
Source: ADR-0007.R2

R4. `nativeflows.clock` defines the types `BusinessDate` and `Instant` with their own validators, serializers and JSON Schemas, as ADR-0006.R13 does for numbers. In JSON a `BusinessDate` is `YYYY-MM-DD`. An `Instant` is written as RFC 3339 in UTC with exactly 6 fractional digits and `Z` (`2026-11-14T03:04:05.000000Z`). On input an `Instant` must carry an offset; any offset is accepted and converted to UTC. A value without an offset, with more than 6 fractional digits, or with second `60` is rejected.
Source: ADR-0007.R3

R5. In Python every `datetime` is timezone-aware: `Instant` uses Pydantic's `AwareDatetime` at every boundary, and ruff's `DTZ` rules catch naive constructors (DS-18). Time zone conversion is done only in Python with `zoneinfo` and a pinned `tzdata` package, never in PostgreSQL.
Source: ADR-0007.R4

R6. A duration is an integer whose name states its unit: `retention_days`, `timeout_seconds`. The PostgreSQL `interval` type is not used in tables or JSON. Calendar arithmetic such as payment terms in months is defined by the DS item that owns it.
Source: ADR-0007.R5

R7. A range of business dates is inclusive at both ends: `start_date`, `end_date`; `end_date` null means open-ended, except where a table requires it (ADR-0007.R18). A range of timestamps is half-open: `starts_at` included, `ends_at` excluded.
Source: ADR-0007.R6

### Dates and timestamps of a document

R8. `document_date` is the date printed on the document. For a document from an external source (an e-invoice, a customs declaration, a bank statement) it is taken from the source as given.
Source: ADR-0007.R7

R9. `posting_date` exists on documents that post (DS-05). It decides the posting period, the fiscal year, the numbering series (DS-05) and balances as of a date (Principle 5). The command that posts a document requires an explicit `posting_date`; the core sets no default. A localization package may define a default per document type for drafts and the UI as flagged configuration. Which date selects an exchange rate, a tax rate or a due date is decided by DS-10, DS-23 and the localization package.
Source: ADR-0007.R8

R10. A late purchase invoice whose month is locked defaults its `posting_date` to the first day of the earliest open period; the document date and the tax date stay as they are.
Source: ADR-0007.R8.N1

R11. `recorded_at` is on every row and every row version of every table, catalogs and system markers included, and is the instant of the last write; the rule has no exception (the first journal line's update of `account.has_posting` refreshes it as well, `journal_line_check_insert` in `docs/design/DS-06-universal-journal.sql`). It is set by the system, on INSERT and on UPDATE, and a client's value is never kept. `recorded_at` is never the start of a row's validity; a row that needs one carries its own column (`product_uom.created_at`, ADR-0056.R4). Other system timestamps name their own event (`posted_at` is the instant a document was posted) and follow ADR-0004.R13. The audit log stores them (Principle 5; DS-36).
Source: ADR-0007.R9, ADR-0007.R9.N1, ADR-0007.R9.N2, ADR-0007.R9.N3

R12. Every table of the design DDL has `recorded_at timestamptz NOT NULL DEFAULT now()` and the trigger `trg_<table>_set_recorded_at` with the shared function `set_recorded_at`, which sets `NEW.recorded_at := now()`: `BEFORE INSERT OR UPDATE` on tables updated in place, `BEFORE INSERT` on append-only tables. Append-only tables are those whose guard trigger refuses every update outside an erasure; no pure log without a guard remains (`outbox_event` and `derivation_trace` have guard triggers, and the lab's `PURE_LOGS` is empty). Each design file ends with one generated section that defines the function and attaches the triggers in one DO block to all of the file's tables.
Source: ADR-0007.R9.N2, ADR-0007.R16.N1, ADR-0007.R16.N2

R13. A `BEFORE INSERT` trigger whose function reads `NEW.recorded_at` must sort after `trg_<table>_set_recorded_at`, or it sees the client's value. `document_version_check_taint` compares a run's `tainted_at` and a clearance's `cleared_at` with `NEW.recorded_at` (ADR-0029.R8, `INV-88`); its trigger is named `trg_document_version_taint_check`.
Source: ADR-0007.R9.N3

R14. The generated section of each design file refuses TRUNCATE (`refuse_truncate`) on every append-only table, every table with a `BEFORE DELETE` guard and every table with `company_id` (ADR-0017.R19), beside the hand-written journal and stock ones. Labs that need a row written in the past use the lab-only helper `insert_aged` of lab.py, which disables the one trigger for one statement. The lab's `gen_overview.py --check` fails on a table without the column or a design file whose section does not list exactly its tables, compares every section with what `schema_phase_b.py` writes, and refuses DDL it cannot read.
Source: ADR-0007.R9.N2, ADR-0007.R9.N3

R15. All system timestamps written in one database transaction use one instant: the transaction start time (`now()` in PostgreSQL), obtained through `clock.now()`. Commands that share a transaction (a command batch) share one instant, and the order of `recorded_at` is not the commit order.
Source: ADR-0007.R10

R16. `recorded_at` and other `_at` columns are never used as an ordering key, a sync cursor, or a condition in business logic; ordering within a day is defined by DS-06 and DS-09.
Source: ADR-0007.R10

R17. `plan_hash` (DS-04) excludes system-set `_at` fields and includes business dates and client-supplied instants in the canonical forms of R4.
Source: ADR-0007.R11

### Time zones

R18. Each company has `time_zone`, an IANA name, validated against `zoneinfo.available_timezones()`. Aliases are valid; code compares time zones only by converting, never by name. It is used only to turn an instant into that company's business date. Branches use their company's time zone.
Source: ADR-0007.R12

R19. A single local time is never converted to an instant. The only reverse conversion is a whole local day to an instant range: both of its midnights are converted with `zoneinfo`; code never adds 24 hours, because days around a daylight-saving change are 23 or 25 hours long.
Source: ADR-0007.R13

R20. Users see timestamps in their own time zone (a user preference, UI only); dates are shown as stored.
Source: ADR-0007.R14

### The clock

R22. `clock.now()` returns the real transaction time and is never overridden, except frozen inside unit tests; such tests do not compare it with database `now()` in triggers and defaults, which stays real.
Source: ADR-0007.R15

R23. `clock.today(company)` returns the company's current business date: the date of `clock.now()` in the company's time zone, unless a row in `business_date_override` sets it for that company, or the command run carries a pinned date (R24, R25).
Source: ADR-0007.R15, ADR-0007.R15.N1

R24. A command envelope may carry `as_of_date` (ADR-0008.R7). Inside that command run every `clock.today(company)` read returns it, in simulate and in execute, and the events the command emits carry it as `business_date`. The accepted range is the business date that `clock.today(company)` returns without it, or the day before; the dispatcher refuses any other date with `as_of_date_out_of_range`. Every simulation returns the `as_of_date` it used, so a client that executes after midnight sends that date and gets the same plan. `posting_date` stays explicit (R9) and is never taken from `as_of_date`.
Source: ADR-0007.R15.N1, ADR-0007.R15.N3

R25. The range check of R24 applies only to envelopes received over a transport (REST, MCP, the UI). An internal caller (ADR-0013.R9 consumers under the event's `business_date`, R29 jobs under their enqueued date, the ADR-0065 gateway job) pins the run's business date in process the same way, with no range check, so a retried or released delivery does the same work on any later day.
Source: ADR-0007.R15.N1, ADR-0007.R15.N4

R26. `business_date_override` is read by every process (servers, Procrastinate workers). The command that writes it is refused unless the installation's `environment` setting is `test` or `simulation`; in `production` the clock ignores the table. The business simulator (DS-17) sets it to the simulated date, so a replay of the same seed gives the same business dates; `recorded_at` stays real and is excluded from reference comparisons.
Source: ADR-0007.R15

R27. `business_date_override` is owned by `periods`, because layer 1 modules own no tables; `clock` reads it through a hook that `periods` registers and `app` wires (ADR-0022.R2). Its DDL is in `docs/design/DS-05-platform.sql`, one row per company.
Source: ADR-0007.R15.N2

R28. No Python code outside `clock` calls `datetime.now()`, `date.today()` or `time.time()`; ruff's banned-API rule (`TID251`) enforces this (DS-18). `time.monotonic()` is allowed for measuring timeouts. Database code (triggers, defaults) may use `now()` only for `_at` values; `current_date`, `now()::date`, `localtimestamp`, `clock_timestamp()` and `statement_timestamp()` are not used. Business dates come only from `clock.today(company)` or from input. Generating a UUID version 7 reads the system clock, which is allowed because business code never reads that timestamp (ADR-0006.R6).
Source: ADR-0007.R16

R29. A scheduled or queued job that depends on a business date receives it as an explicit parameter, per company, fixed when the job is enqueued, so a retry after midnight does the same work.
Source: ADR-0007.R17

R30. Reports across companies select by date range, never by fiscal year code, because companies may have different fiscal years.
Source: ADR-0007.R23

## Invariants

None: no invariant has the area `clock`. `INV-88` (`taint_inherited`, check point `day`, source ADR-0029.R8) depends on the trigger order of R13.

## Edge cases

None: the catalog holds no edge case of `clock`.

## Settings

None: `settings.csv` holds no key of `clock`.

R26 names the installation's `environment` setting (values `test`, `simulation`, `production`); it is absent from `settings.csv`.

## UI annotations

None: the sources hold no ADR-0077 annotation for this module.

## Conflicts

CONFLICT ADR-0007.R9: "on rows updated in place" and "set by the system" are widened to every table and to INSERT; governed by ADR-0007.R9.N1 and ADR-0007.R9.N3, stated in R11.
CONFLICT ADR-0007.R9.N2: the trigger is attached to every table, append-only ones included, not to all except them; governed by ADR-0007.R9.N3, stated in R12.
CONFLICT ADR-0007.R16.N1: `BEFORE UPDATE` only and no trigger on append-only tables no longer hold; governed by ADR-0007.R16.N2, stated in R12.
CONFLICT ADR-0007.R15.N1: the range of one day before or after is narrowed to the business date or the day before; governed by ADR-0007.R15.N3, stated in R24.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0007.D0 | R1 |
| ADR-0007.R1 | R2 |
| ADR-0007.R2 | R3 |
| ADR-0007.R3 | R4 |
| ADR-0007.R4 | R5 |
| ADR-0007.R5 | R6 |
| ADR-0007.R6 | R7 |
| ADR-0007.R7 | R8 |
| ADR-0007.R8 | R9 |
| ADR-0007.R8.N1 | R10 |
| ADR-0007.R9 | R11 |
| ADR-0007.R9.N1 | R11 |
| ADR-0007.R9.N2 | R11, R12, R14 |
| ADR-0007.R9.N3 | R11, R13, R14 |
| ADR-0007.R10 | R15, R16 |
| ADR-0007.R11 | R17 |
| ADR-0007.R12 | R18 |
| ADR-0007.R13 | R19 |
| ADR-0007.R14 | R20 |
| ADR-0007.R15 | R22, R23, R26 |
| ADR-0007.R15.N1 | R23, R24, R25 |
| ADR-0007.R15.N2 | R27 |
| ADR-0007.R15.N3 | R24 |
| ADR-0007.R15.N4 | R25 |
| ADR-0007.R16 | R28 |
| ADR-0007.R16.N1 | R12 |
| ADR-0007.R16.N2 | R12 |
| ADR-0007.R17 | R29 |
| ADR-0007.R23 | R30 |
