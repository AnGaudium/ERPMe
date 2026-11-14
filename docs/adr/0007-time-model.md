# ADR-0007: Time model

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Amended before its first merge (2026-11-14) by the author's answer on fiscal years (rule 21). Design item: DS-03. Related decisions: D4, D8, D15, D16. Principles 2, 5, 6, 9. ADR-0004, ADR-0005, ADR-0006.

## Decision

There are two kinds of time and they never mix: business dates are calendar dates (`date`, no time zone) chosen by people or source documents; system timestamps are instants (`timestamptz`, stored and sent in UTC) set only by the system. A posting document carries a `document_date` (printed on it), a `posting_date` (decides its period, fiscal year and numbering series, given explicitly at posting) and rows carry a `recorded_at` (when the system recorded them). Each company has one IANA time zone, used only to turn an instant into that company's date. The current instant always comes from the real database transaction time; the current business date comes from one clock function that tests and the simulator can set per company. The fiscal calendar is stored as data: contiguous fiscal years per company with regular posting periods inside, found by date-range lookup and immutable once used.

### Rules

**Kinds of time**

1. A business date is a PostgreSQL `date` with a name ending in `_date` (ADR-0004 rule 13). It has no time zone and is never converted between time zones.
2. A system timestamp is a PostgreSQL `timestamptz` with a name ending in `_at`. `timestamp without time zone` is not used. Database sessions and application servers run with time zone UTC.
3. `erpme.clock` defines the types `BusinessDate` and `Instant` with their own validators, serializers and JSON Schemas, as ADR-0006 rule 13 does for numbers, because the library defaults differ (Python writes `+00:00` and drops zero microseconds). In JSON a `BusinessDate` is `YYYY-MM-DD`. An `Instant` is written as RFC 3339 in UTC with exactly 6 fractional digits and `Z`, e.g. `2026-11-14T03:04:05.000000Z`. On input an `Instant` must carry an offset (any offset is accepted and converted to UTC); a value without an offset, with more than 6 fractional digits, or with second `60` is rejected.
4. In Python every `datetime` is timezone-aware: `Instant` uses Pydantic's `AwareDatetime` at every boundary, and ruff's `DTZ` rules catch naive constructors (DS-18). Time zone conversion is done only in Python with `zoneinfo` and a pinned `tzdata` package, never in PostgreSQL, whose time zone database can differ.
5. A duration is an integer whose name states its unit: `retention_days`, `timeout_seconds`. The PostgreSQL `interval` type is not used in tables or JSON. Calendar arithmetic such as payment terms in months is defined by the DS item that owns it.
6. A range of business dates is inclusive at both ends: `start_date`, `end_date`; `end_date` null means open-ended, except where a table requires it (rule 18). A range of timestamps is half-open: `starts_at` included, `ends_at` excluded.

**Dates and timestamps of a document**

7. `document_date`: the date printed on the document. For a document from an external source (an e-invoice, a customs declaration, a bank statement) it is taken from the source as given.
8. `posting_date` exists on documents that post (DS-05). It decides the posting period, the fiscal year, the numbering series (DS-05) and balances as of a date (Principle 5). The command that posts a document requires an explicit `posting_date`; the core sets no default. A localization package may define a default per document type for drafts and the UI as flagged configuration, because which date to use is an accounting rule (see open questions). Which date selects an exchange rate, a tax rate or a due date is decided by DS-10, DS-23 and the localization package, not by this ADR.
9. `recorded_at`: the instant the command that wrote a row ran, on every row and every row version; on rows updated in place (stock balance, number counters; ADR-0002) it is the instant of the last write. It is set by the system, never accepted from a client. Other system timestamps name their own event (`posted_at` is the instant a document was posted) and follow ADR-0004 rule 13. The audit log stores them (Principle 5; DS-36).
10. All system timestamps written in one database transaction use one instant: the transaction start time (`now()` in PostgreSQL), obtained through `clock.now()`. Commands that share a transaction (a command batch) therefore share one instant, and the order of `recorded_at` is not the commit order. `recorded_at` and other `_at` columns are never used as an ordering key, a sync cursor, or a condition in business logic; ordering within a day is defined by DS-06 and DS-09.
11. `plan_hash` (DS-04) excludes system-set `_at` fields and includes business dates and client-supplied instants in the canonical forms of rule 3.

**Company time zone and the clock**

12. Each company has `time_zone`, an IANA name such as `Asia/Ho_Chi_Minh`, validated against `zoneinfo.available_timezones()`. Aliases such as `Asia/Saigon` are valid; code compares time zones only by converting, never by name. It is used only to turn an instant into that company's business date. Branches use their company's time zone.
13. A single local time is never converted to an instant. The only reverse conversion is a whole local day to an instant range: both of its midnights are converted with `zoneinfo`; code never adds 24 hours, because days around a daylight-saving change are 23 or 25 hours long (the US company in the large dataset).
14. Users see timestamps in their own time zone (a user preference, UI only); dates are shown as stored.
15. `clock.now()` returns the real transaction time and is never overridden, except frozen inside unit tests; such tests do not compare it with database `now()` in triggers and defaults, which stays real. `clock.today(company)` returns the company's current business date: the date of `clock.now()` in the company's time zone, unless a row in `business_date_override` sets it for that company. That table is read by every process (servers, Procrastinate workers), and the command that writes it is refused unless the installation's `environment` setting is `test` or `simulation`; in `production` the clock ignores the table. The business simulator (DS-17) sets it to the simulated date, so a replay of the same seed gives the same business dates; `recorded_at` stays real and is excluded from reference comparisons.
16. No other Python code calls `datetime.now()`, `date.today()` or `time.time()`; ruff's banned-API rule (`TID251`) enforces this (DS-18). `time.monotonic()` is allowed for measuring timeouts. Database code (triggers, defaults) may use `now()` only for `_at` values; `current_date`, `now()::date`, `localtimestamp`, `clock_timestamp()` and `statement_timestamp()` are not used, because sessions run in UTC and would give the wrong date. Business dates come only from `clock.today(company)` or from input. Generating a UUID version 7 reads the system clock, which is allowed because business code never reads that timestamp (ADR-0006 rule 6).
17. A scheduled or queued job that depends on a business date receives it as an explicit parameter, per company, fixed when the job is enqueued, so a retry after midnight does the same work.

**Fiscal calendar**

18. A company's fiscal calendar is data: `fiscal_year` rows with `start_date`, `end_date` and a `code` (e.g. `2026`), contiguous and non-overlapping per company, `end_date` not null, each split into regular `posting_period` rows (also with `end_date` not null) that are contiguous and non-overlapping inside it. Non-overlap is enforced by an exclusion constraint on `daterange(start_date, end_date, '[]')` per company (PostgreSQL extension `btree_gist`), and contiguity by the command that creates the rows. Special periods for year-end adjustments share dates with a regular period, are chosen explicitly, and are designed in DS-12 together with period states and closing.
19. The fiscal year and regular posting period of a date are found by looking up the row whose range contains it, never computed from a formula, so a short or long first fiscal year and non-calendar fiscal years need no code.
20. Once a posting exists in a fiscal year, its range and the ranges of its posting periods never change. A change of fiscal year is made by creating a new, shorter or longer, fiscal year after the last used one.
21. The default fiscal year is the calendar year; a company may declare other fiscal years when it needs to (author's decision, 2026-11-14). `CreateFiscalYear` checks only the rules of this ADR (contiguity, rule 18; immutability, rule 20).
22. At posting, a `posting_date` outside every fiscal year of the company is rejected with an error that names `CreateFiscalYear`. Drafts and documents that never post are not checked. Who creates the next fiscal year, and when, is DS-12.
23. Reports across companies select by date range, never by fiscal year code, because companies may have different fiscal years.

## Context

DS-03 is needed by DS-04 (envelope), DS-05 (lifecycle, numbering per fiscal year of the posting date), DS-06 (journal), DS-10 (daily rates) and DS-12 (periods). Constraints:

- Point-in-time figures use the posting date; the audit log stores the recording timestamp (Principle 5).
- Numbering comes from a series per document type, fiscal year of the posting date and branch ([07-shared-foundation.md](../spec/07-shared-foundation.md#document-lifecycle-numbering-and-posting-periods)).
- Backdated documents in an open period re-cost that period and later open periods (07), so posting dates in the past are normal and must never happen by accident.
- The simulator runs a calendar day by day and must be reproducible from (seed, dataset version) ([12-testing.md](../spec/12-testing.md#synthetic-dataset)).
- The product serves several countries (D8) and companies in one instance; consolidation sums companies (06, rule 7).
- ADR-0005: among correct options, the one easiest for AI agents wins; accounting rules and unstated business behavior stay with the author.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Dates without time zone for business, `timestamptz` UTC for system (chosen) | A date means the same everywhere; no conversion bugs on accounting dates | Two kinds of time to learn |
| Store every time as a timestamp | One type | An invoice dated 14 Nov becomes 13 Nov in another time zone; periods shift |
| Local timestamps per company (`timestamp without time zone`) | Matches what users see | Ambiguous around offset changes; cannot compare across companies |
| `posting_date` required at posting (chosen) | No accidental backdating; the accounting choice stays in the localization package | One more field for every posting command |
| `posting_date` defaults to `document_date` | Less input | Silently posts a late invoice into an earlier period, which re-costs it; decides an accounting rule in the core |
| Overridable `clock.now()` | One override for everything | Simulated instants in `recorded_at` would corrupt the audit trail |
| Clock read directly where needed | No module to call | Tests and the simulator cannot set the date; replays differ |
| Fiscal calendar computed from a start month | No rows to keep | Breaks for a short or long first year and for changes of fiscal year; hides the rule in code |
| Inclusive date ranges, half-open timestamp ranges (chosen) | Matches how people write date ranges (1 Jan–31 Dec) and how instants are compared | Two range conventions; the suffix (`_date` or `_at`) tells which applies |
| `interval` for durations | Native type | Its text form differs by setting; agents misread `1 mon` |

## Constraints that come with the decision

- DS-04: the envelope carries no client timestamp; `recorded_at` is set by the command layer; posting commands require `posting_date`; `plan_hash` per rule 11.
- DS-05: numbering series keyed by the fiscal year found from `posting_date` (rule 19).
- DS-06: journal entries carry `document_date`, `posting_date` and `recorded_at`; same-day ordering defined there (rule 10).
- DS-10: daily rates keyed by business date; which date selects a rate.
- DS-12: special periods, period states, who creates the next fiscal year (rules 18, 22).
- DS-17: the simulator writes `business_date_override` (rule 15).
- DS-18: ruff `DTZ` and `TID251`; pinned `tzdata`; PostgreSQL extension `btree_gist`; servers and database sessions in UTC; the installation `environment` setting; a CI check for the banned database functions (rule 16).
- DS-24: e-invoice date and signing time (see open questions).

## Revisit when

- A localization package needs a business date that depends on the time of day (e.g. a legal cut-off hour): add a rule here instead of handling it inside that package.
- A company needs more than one time zone for its branches.

## Documents updated

- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for document date, posting date, recording timestamp, company time zone, fiscal year, clock.
- [docs/design/backlog.md](../design/backlog.md): DS-03 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): fiscal year rules in Vietnam; which date drives the VAT period and the posting date; e-invoice date versus signing time.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
