# DS-16: Invariant catalog and test harness

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Kind: specification and catalog; the harness code is step 0 work package 7. Related decisions: D14, D16. Principles 2, 5, 6, 10. Build principles B2, B4. ADR-0002, ADR-0003 (R1, R4, R6, R7), ADR-0004, ADR-0005 (item 3), ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0017, ADR-0020, ADR-0021, DS-17. Spec [12-testing.md](../spec/12-testing.md); runbook [testing-operations.md](../runbook/testing-operations.md).

This specification fixes how right and wrong are judged:
- the invariant catalog and how each invariant becomes code;
- the outcome oracle for accepted and rejected commands;
- the Hypothesis state machines;
- the scenario format for golden, regression and proposed scenarios;
- the naive recomputation;
- the reports.

The rule from [12-testing.md](../spec/12-testing.md) governs it: **the model only proposes scenarios; deterministic code judges right and wrong.**

## 1. Packages and independence

The product is `erpme` (ADR-0004 rule 7). Test tooling lives in separate top-level packages that the product never imports. Their names are fixed here and in DS-17, and enforced by DS-18:

| Package | Holds | May import |
| --- | --- | --- |
| `erpme_events` (DS-17) | Business-event log schema, reader, writer | standard library, pydantic |
| `erpme_client` | `CommandClient` protocol and its transports | the dispatcher's in-process entry point (the registry module's public dispatch function, ADR-0008; module name per DS-18), `erpme.numeric`, an HTTP and an MCP client library |
| `erpme_adapters` (DS-17) | Per-step event → command adapters | `erpme_events`, `erpme_client` |
| `erpme_simulator` (DS-17) | The business simulator | `erpme_events` |
| `erpme_testkit` | Invariant registry and checks, state machines, scenario runner, reports, `erpme-check` and `erpme-scenario` CLIs | `erpme_events`, `erpme_adapters`, `erpme_client`, `erpme.numeric` |
| `erpme_reference` | Naive recomputation | standard library only |

1. Commands reach the core only through `erpme_client.CommandClient`, a protocol with three transports: `in_process` (the dispatcher's in-process transport, ADR-0008), `rest` and `mcp`. Scenarios, replays and state machines work with any transport; a run selects one, and the step 4 gate runs REST and MCP. Nothing in the harness writes core tables.
2. Invariant checks read the database with plain SQL as the role `erpme_check`:
   - It may only SELECT, and RLS applies to it.
   - Each check sets `erpme.company_id`; global checks set `erpme.company_ids` (ADR-0017).
   - It never has `BYPASSRLS`.
   - DS-18 creates the role, as a follow-up to ADR-0017 rule 18.

   Checks never use core repository code, so a defect in a shared helper cannot hide in the check meant to catch it.
3. The naive recomputation never reads the database or core code. Its inputs are plain files in the run directory:
   - the event log as JSON, validated against the published schema `docs/catalogs/business-events.schema.json` (DS-17);
   - `regime_snapshot.json`: the regime settings, rounding modes and templates the run uses, copied by `erpme_testkit` from the package data files, never computed by the core.

   It needs only `docs/` and its own folder, as the runbook's recomputation writer row requires ([README.md](../runbook/README.md)). Its pull requests record that it was written from a sparse checkout without the product's source (its path is DS-18's).

## 2. Invariant catalog

4. The catalog is [docs/catalogs/invariants.csv](../catalogs/invariants.csv), owned by DS-16. Its columns:

   | Column | Content |
   | --- | --- |
   | `code` | `INV-nn`, never reused |
   | `name` | snake_case |
   | `area` | `ledger`, `platform`, `inventory`, `receivables_payables`, `documents`, `warehouse`, `planning`, `subledger` or `safety` |
   | `check_point` | rule 10 |
   | `first_step` | The first build step at which the data it checks can exist; from then on it must have code and pass |
   | `flagged` | The open question it depends on, if its statement restates an interim rule |
   | `keys` | The business key fields a violation reports |
   | `source`, `added_in`, `statement` | |

   Codes are grouped: 01–19 ledger and platform, 20–29 inventory, 30–39 receivables and payables, 40–49 documents, 50–59 warehouse (ADR-0023), 60–69 planning (ADR-0024), 70–79 subledgers (ADR-0025), 80–89 agent safety and platform integrity (ADR-0027). Version 0.1.0 has 61 invariants. Later items add rows with the next free code in their group.
5. Each catalog row has exactly one check, registered with `@invariant("INV-21")` in `erpme_testkit.invariants`. A CI test compares catalog and registry:
   - a row whose `first_step` is at or below `[tool.erpme] build_step` (DS-18) and has no check fails;
   - a check without a row fails;
   - a row above the current step may have a check, which runs in report-only mode.
6. The author decides (ADR-0005 item 3):
   - removing or weakening an invariant;
   - changing a check so a failure passes;
   - changing the recomputation to make a failure pass;
   - changing an invariant when the author answers an open question named in its `flagged` column.

   Adding an invariant or making a check stricter is technical. CI labels `reserved-review` every pull request that touches `invariants.csv`, `erpme_testkit/invariants/`, `erpme_reference/` or any author-only path (rule 22).

## 3. Checks, outcomes and violations

7. A check is a function `(connection, scope) -> list[Violation]`:
   - It runs read-only in one REPEATABLE READ snapshot, so all checks of a check point see one state.
   - It is preferably one set-based SQL query returning the violating rows.
   - It never raises for bad data: bad data is a violation. An exception means the check itself is broken; that is reported separately, and `erpme-check` exits with 2.
   - `scope` is a company, optionally narrowed to `as_of` or to the documents a command wrote.
   - `day` checks may run incrementally on a day's documents, with a full run at each month end and at the end of a run.
8. Before every check point the harness runs the outbox delivery workers in process, in a deterministic order, until no delivery is pending (ADR-0013). Checks therefore never race asynchronous consumers. A delivery left `held` is a violation of INV-13.
9. Checks that need state across check points keep it in a state directory (`--state <dir>` for `erpme-check`, in memory for state machines):
   - INV-08 fingerprints are SHA-256 over the canonical JSON of a posted document's header without `state`, its versions, journal entries and lines, and material lines. `state` may change only from `posted` to `reversed` (ADR-0009 rule 14).
   - INV-11 compares a company's fingerprints of business tables before and after a retry: documents, versions, journal entries and lines, material lines, stock tables, open items, outbox events, deliveries and `idempotency_record`. Audit, technical-queue and telemetry tables are excluded.

   The append-only triggers themselves are tested by SQL-level tests in DS-18, not by the harness.
10. `check_point` values:
    - `command`: checked around each command by the command protocol (rule 15): INV-11, INV-12, INV-14, INV-15, INV-18, INV-19.
    - `day`: after every simulated day of a replay and after every step of a state machine.
    - `run`: once at the end. None in 0.1.0.

    A check that cannot be evaluated in a given setting, such as a `command` check from `erpme-check`, reports `not_evaluated`, never pass.
11. A violation is a JSON object (schema `docs/catalogs/violation.schema.json`) with these fields:
    - `check`: `INV-nn`; `REF-<kind>-<pair>` for a reference difference (rule 30); or `PAR-nn` for a parallel test (rule 31).
    - `company`.
    - `keys`: business keys, per the catalog's `keys` column.
    - `expected` and `actual`: strings, either canonical decimals (ADR-0006 rule 13) or IDs and hashes.
    - `message`.
    - `first_failing`: the first command after which the check failed, with `command_id`, `command_type`, `idempotency_key`, the event reference, the simulator triple or Hypothesis seed, and `sim_day`.

    When one event maps to several commands, the first failing command is the first in the adapter's order. When a replay fails at a day check, the harness replays that day again in a fresh company, with checks after every command, to fill `first_failing`. For a reference difference it bisects by day, then by event, recomputing the naive result on each prefix. The defect dedupe key is `check` plus `first_failing.command_type` ([testing-operations.md](../runbook/testing-operations.md#defects-to-regression-scenarios); ADR-0003 R7).
12. `erpme-check` runs the registry read-only against a database and prints violations and `not_evaluated` results as JSON lines:
    - options: `--company`, `--as-of`, `--only INV-..`, `--area`, `--state <dir>`;
    - exit codes: 0 clean, 1 violations, 2 a broken check;
    - coding agents use it locally, and the test server after each replay day;
    - whether it may run against production is decided in DS-36;
    - it never repairs data.
13. The invariant report lists, for each check, its runs, failures, `not_evaluated` counts and first violation. It also lists accepted and rejected command counts per command type and the share of `may_reject` events (rule 14), so that share cannot grow unnoticed.

**Outcome oracle**

14. A core that rejected every command would satisfy every `day` invariant. So each event carries an `outcome` class, set before execution from the simulator's or the state machine's own model, never from the core:
    - `must_succeed`;
    - `must_reject`, with an error code;
    - `may_reject`, with the allowed codes, for the few cases the model cannot predict, such as concurrency.

    INV-19 fails on any other outcome. The recomputation reads only the event log with these classes. For `may_reject` events it takes the actual outcome as a recorded input, and the comparison report lists them.

## 4. Command protocol and state machines

15. Every command the harness sends, in state machines, scenarios and replays alike, goes through the same protocol:
    1. It is simulated.
    2. It is executed with the simulation's `plan_hash` (INV-12).
    3. Its outcome is compared with its class (INV-19).
    4. Its responses are checked for field classes (INV-15).
    5. Its emitted events are compared with the simulation (INV-18).
    6. For postings, the period rule is checked against the harness's own model of period states and capabilities (INV-14).

    Events marked `retry: true` are sent a second time with the same idempotency key (INV-11). Retries are part of the event log, drawn by Hypothesis or by the simulator seed, never by an unseeded random choice.
16. Commands run as at least two actors: one with every field class, and a restricted one without `cost` and `margin`. Field classes are read from the generated schemas (DS-18), which makes INV-15 meaningful; events in which the restricted actor sets a `cost` or `margin` field carry `must_reject` with `permission_denied`. Idempotency keys are `<run nonce>:<event ref>:<n>`, with `n` the command's position in the adapter's output, within ADR-0008's 128-character limit, so replays in one database never collide; the nonce is in every report.
17. `LedgerMachine`, extended per step (`InventoryMachine` at step 3, and so on), is a `RuleBasedStateMachine`:
    - Its rules draw business events in the DS-17 schema, with their outcome class and retry flag, through Hypothesis strategies. The step's adapter turns them into commands, so state machines, the simulator and scenario files share one path, and a shrunk failure is frozen directly as a regression scenario (rule 25).
    - Bundles hold the business codes created so far.
    - Drawing implausible events is part of the strategies, so it shrinks too.
    - Once approvals exist (step 5), it draws agent-drafted documents followed by an approval attempt by the same human, expecting `segregation_of_duties` (INV-17).
18. Isolation:
    - Each example creates a fresh company through `CreateCompany` with the Vietnam package and its own company-scoped exchange-rate source.
    - Examples run in one test database per worker (testcontainers PostgreSQL, ADR-0002), and RLS scopes every check to the example's company.
    - At session end, a global check confirms that no example changed another company's row fingerprints. This catches leaks that RLS-scoped checks cannot see.
    - Group currency is installation-wide and fixed after the first posting (ADR-0011 rule 6), so CI runs two installations: one without and one with a group currency.
19. Business dates move through `business_date_override` per company (ADR-0007 rule 15); `clock.now()` is never overridden. Backdated events choose earlier posting dates in open periods. The scenario runner does the same.
20. Hypothesis profiles:

    | Profile | Settings |
    | --- | --- |
    | `ci` | `derandomize=True`, 50 examples, 30 steps, no deadline |
    | `nightly` | Random seed recorded in the report, 2,000 examples, 200 steps |
    | `debug` | One example, verbose |

    At the end of each example the naive trial balance is compared with the core's, which backs the step 1 gate's "trial balance correct" on random sequences.

## 5. CI time budget

21. Within the 15-minute CI job limit (ADR-0003 R6; jobs in DS-18), each part is measured against its budget:

    | Part | Budget |
    | --- | --- |
    | Hypothesis `ci`, both installations | 4 min |
    | Small dataset replay with checks | 4 min |
    | Scenarios | 2 min |

    Unit tests and parallel tests share the rest of the test job. A part over budget fails CI with its timing. When time is short, the number of examples is reduced first, then `day` checks become incremental; the set of invariants is never reduced.

## 6. Scenarios

22. A scenario is a directory `<root>/<kind>/<id>/`:
    - Regime-dependent golden scenarios live in their localization package, under `l10n/<package>/tests/golden/<id>/` (ADR-0016 component table; DS-14), and run as the package's mandatory tests (ADR-0016 rule 15).
    - The root `tests/scenarios/` holds regression scenarios, package-neutral golden scenarios and kept proposals. The runner discovers both roots.

    The three kinds:
    - `golden`: built by the author.
    - `regression`: a frozen defect.
    - `proposed`: events only, from the test-scenario model; the schema forbids expected values. Proposals are transient unless they find a defect, in which case they become regression scenarios.

    Author-only paths: every `workbook.xlsx`, every `expected.csv` of a regression scenario (hand-written by the author; for goldens the file is generated, rule 23), the `status` field of `scenario.yaml`, and `expected_failure` except as rule 25 allows.
23. Files of a scenario (JSON Schemas in `docs/catalogs/`):
    - `scenario.yaml` holds:
      - `id`, `title` and `kind`;
      - `status`: `verified`, or `pending_verification` when the scenario depends on a flagged rule;
      - `localization_package`, its version and regime;
      - `regime_settings`: overrides for the flagged settings it assumes;
      - `build_step` and `event_log_version`;
      - `events`, in the DS-17 schema, with business codes, scenario-local `ref`s, outcome classes and retry flags;
      - `defect` (regression only): issue number and dedupe key;
      - `expected_failure` (rule 25).
    - `workbook.xlsx` (golden only) is the author's hand-built calculation and the single source of expected values (ADR-0002: golden scenarios read from hand-built spreadsheets). Its sheet `expected` has one table per kind.
    - `expected.csv` is generated from the workbook by `erpme-scenario export`, deterministically. Export needs cached values (`data_only=True`), so the workbook must be saved from a spreadsheet program. CI regenerates the file and fails on any difference, which keeps a reviewable text form without a second source of truth.
24. `expected.csv` has named columns, never positional ones: `kind`, the key columns of that kind, `amount_kind` (`transaction`, `company` or `group`) or `unit`, and `value`.

    | `kind` | Key columns |
    | --- | --- |
    | `account_balance` | `account` (operational code) or `system_account`; `period` or `as_of`; `currency` |
    | `stock_quantity` | `item`, `warehouse`, `lot`, `as_of` |
    | `stock_value` | `item`, `warehouse`, `as_of` |
    | `average_cost` | `item`, `valuation_area`, `period` |
    | `open_item` | `partner`, `document_ref`, `currency` |
    | `journal_line` | `document_ref`, `account`, `item`, `warehouse`, `currency` |
    | `document_count` | `document_type`, `state` |

    - Balances are closing balances, signed debit positive (ADR-0014 rule 6).
    - Quantities are in the inventory unit.
    - `document_ref` is the event's scenario-local `ref`, never a core-assigned number.
    - Rows with equal keys are summed (e.g. several `journal_line` rows of one document and account).
    - Each kind's table in the workbook has a `complete` flag; the export writes it to `expected_complete.csv` (`kind`, `complete`). When true, unlisted keys of that kind must be zero or absent. The export schema fixes the layout of the `expected` sheet: one table per kind, starting at a header row whose first cell is `kind`.
25. Regression scenarios:
    - `erpme-scenario freeze` writes the shortest failing event sequence, taken from a Hypothesis failure or from a (triple, day).
    - While its defect is open, the scenario carries `expected_failure: {check, since_commit}`, a strict expected failure: CI stays green while it fails with exactly that check, and turns red if it passes or fails differently. An agent may add the field in the commit that creates the scenario, and the fix removes it; both make CI stricter. Adding it to an existing scenario, changing its `check`, or using it on a golden scenario is the author's.
    - It always runs every invariant and the core-versus-naive comparison, so defects found only by reference comparison are frozen too. An `expected.csv` is optional and written only by the author.
    - Defects found by parallel tests are frozen as parallel tests (rule 31).
26. In a `pending_verification` scenario only the comparisons involving the golden value (`REF-…-golden_core`, `REF-…-golden_naive`) are report-only and never count as matched; invariants, the outcome oracle and core-versus-naive still fail CI. Such scenarios are listed in every gate report. Only the author changes `status` (ADR-0003 R10).
27. Golden expected values are the author's (ADR-0005 item 3; runbook step 0). An agent may draft `scenario.yaml` without `status`, and may commit a regenerated `expected.csv` that CI verifies against the workbook. CI fails when a commit with an agent's `Co-Authored-By` trailer changes an author-only path. That check is a tripwire; the control is the author's line-by-line review of every `reserved-review` pull request (rule 6).
28. The scenario runner replays events through the adapter of `build_step` or a later step, with the command protocol of rule 15, so scenarios written at step 1 keep running later:
    - After each event it runs the `day` checks.
    - At the end it compares expected values with core query results by exact equality: `GetTrialBalance` (per account, period, currency and amount kind), `ListJournalLine`, `GetStockBalance` (ADR-0020), and the open-item and average-cost queries their items add.
    - `GetTrialBalance` is a requirement this item places on the ledger module at step 1.

## 7. Naive recomputation and comparison

29. `erpme_reference` computes expected results from the run directory alone (rule 3), in the same row format as `expected.csv`. It is deliberately simple: plain loops over events, `fractions.Fraction` for every intermediate value, rounding only where the specification rounds (modes from `regime_snapshot.json`), and no caching.

    | Step | Results |
    | --- | --- |
    | 1 | Trial balance per account and period, in transaction and company currency, and in group currency where the installation sets one (journal-level events and the step 1 projection documented by DS-17) |
    | 3 | Stock quantity and value per item, warehouse and date; periodic average per item, valuation area and period, with transfers solved; cost of goods sold; landed cost allocations and the locked-period split (ADR-0020 rules 11–13; ADR-0021) |
    | 4 | Open items and their open amounts, from opening balances on (ADR-0026) |
    | 6 | Carrying amounts on settlement; realized FX |
    | 7 | VAT per tax code and return line |
    | 8 | Unrealized FX revaluation; closing entries |

    Rules the specification leaves to the regime are read from the snapshot, never hard-coded, so a flagged rule changes both references together.
30. The reference comparison report compares, for each run, company, period and key, the core result, the naive result and, where present, the golden value:
    - Equality is exact, with no tolerance. Any difference fails the run as `REF-<kind>-<pair>` (e.g. `REF-stock_value-core_naive`).
    - Output goes to `comparison.json` (schema in `docs/catalogs/`) and `comparison.md`, which shows the first 50 differences per kind.
    - The report names which pairs differ and never decides which one is right. That is the author's decision (ADR-0005 item 3), recorded in the defect's classification.

    All reports carry the triple or seed, the run nonce, the git commit and the catalog versions.

## 8. Parallel tests

31. Parallel tests carry IDs `PAR-nn`; the table below is their catalog, and CI compares it with the registered tests as for invariants. Each opens several connections, holds them at a barrier and releases them together. It confirms real overlap by observing a lock wait in `pg_stat_activity`; a run that saw no contention is retried up to 5 times and then fails. Version 0.1.0:

    | ID | First step | Conflict |
    | --- | --- | --- |
    | PAR-01 | 3 | Issues of the same (item, warehouse) |
    | PAR-02 | 1 | Documents in the same number series |
    | PAR-03 | 1 | The same idempotency key from two clients |
    | PAR-04 | 1 | Outbox delivery with two workers, and a worker crash with reclaim: each consumer's effect is applied exactly once (ADR-0013 rule 7) |
    | PAR-05 | 1 | Period lock against a concurrent posting (ADR-0012 rule 9) |
    | PAR-06 | 3 | Two putaways of different items into the last free bin (ADR-0023 rule 10) |
    | PAR-07 | 3 | A handling-unit move against a pick from that unit |
    | PAR-08 | 3 | Two confirmations of one warehouse task |
    | PAR-09 | 3 | Long profile only: 8 concurrent confirmations of one item in different bins; p95 above 1 s triggers ADR-0023's revisit line |
    | PAR-10 | 1 | Two settlements of one open item at once (ADR-0026 rule 14) |

    Each test asserts the outcome: exactly one wins where one must, and the others fail with their codes. Then it runs every `day` check. CI runs a short profile; the test server runs a long one.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| State machines draw business events through adapters (chosen) | One path with the simulator and scenarios; shrunk failures are scenarios | Needs an adapter from step 1 |
| State machines draw commands | No adapter | A second path; failures cannot be replayed as scenarios |
| Company per example in one database (chosen) | Fast; exercises multi-company | Installation-wide settings need two installations; leaks need a global check |
| Database per example, or rollback | Full isolation | Slow, or hides commit-time behavior (deferred triggers, outbox) |
| Workbook as single source, CSV generated (chosen) | Author works in a spreadsheet; review sees text; no transcription | A spreadsheet program must save cached values |
| Checks through core queries | Less SQL | A shared defect can hide in both |
| Comparison with tolerance | Fewer false alarms | Hides rounding defects; decimals are exact |

## Open points

None reserved to the author beyond ADR-0005 item 3, which this specification applies. Requirements this item places on others:
- DS-17: events carry `outcome`, `retry` and scenario-local `ref`; `docs/catalogs/business-events.schema.json`; the step 1 projection document in `docs/`.
- DS-18: role `erpme_check`; `[tool.erpme] build_step`; the `reserved-review` label and the author-path tripwire; field classes in generated schemas; package `erpme_client` and the import contracts of section 1; CI with two installations.
- Ledger module (step 1): query `GetTrialBalance`.
- DS-36: whether `erpme-check` may run against production.
- Work package 7 creates the JSON Schemas `violation`, `scenario` and `comparison` in `docs/catalogs/` by hand, with catalogs README rows; DS-17's work package creates `business-events` (generated, CI diff).
- The runbook README's note on replacing invariant descriptions with IDs can now be done; it is the author's document.

## Documents updated

- [docs/catalogs/invariants.csv](../catalogs/invariants.csv): new, version 0.1.0.
- [docs/catalogs/README.md](../catalogs/README.md): invariants row.
- [docs/design/backlog.md](backlog.md): DS-16 row links here.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for invariant, check point, outcome class, golden, regression and proposed scenario, naive recomputation, violation, `erpme-check` and `erpme-scenario`, test tooling packages.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
