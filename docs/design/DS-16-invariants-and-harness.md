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

The product is `nativeflows` (ADR-0004 rule 7). Test tooling lives in separate top-level packages that the product never imports. Their names are fixed here and in DS-17, and enforced by DS-18:

| Package | Holds | May import |
| --- | --- | --- |
| `nativeflows_events` (DS-17) | Business-event log schema, reader, writer | standard library, pydantic |
| `nativeflows_client` | `CommandClient` protocol and its transports | the dispatcher's in-process entry point (the registry module's public dispatch function, ADR-0008; module name per DS-18), `nativeflows.numeric`, an HTTP and an MCP client library |
| `nativeflows_adapters` (DS-17) | Per-step event → command adapters | `nativeflows_events`, `nativeflows_client` |
| `nativeflows_simulator` (DS-17) | The business simulator | `nativeflows_events` |
| `nativeflows_testkit` | Invariant registry and checks, state machines, scenario runner, reports, `nativeflows-check` and `nativeflows-scenario` CLIs | `nativeflows_events`, `nativeflows_adapters`, `nativeflows_client`, `nativeflows.numeric` |
| `nativeflows_reference` | Naive recomputation | standard library only |

1. Commands reach the core only through `nativeflows_client.CommandClient`, a protocol with three transports: `in_process` (the dispatcher's in-process transport, ADR-0008), `rest` and `mcp`. Scenarios, replays and state machines work with any transport; a run selects one, and the step 4 gate runs REST and MCP. Nothing in the harness writes core tables.
2. Invariant checks read the database with plain SQL as the role `nativeflows_check`:
   - It may only SELECT, and RLS applies to it.
   - Each check sets `nativeflows.company_id`; global checks set `nativeflows.company_ids` (ADR-0017).
   - It never has `BYPASSRLS`.
   - DS-18 creates the role, as a follow-up to ADR-0017 rule 18.

   Checks never use core repository code, so a defect in a shared helper cannot hide in the check meant to catch it.
3. The naive recomputation never reads the database or core code. Its inputs are plain files in the run directory:
   - the event log as JSON, validated against the published schema `docs/catalogs/business-events.schema.json` (DS-17);
   - `regime_snapshot.json`: the regime settings, rounding modes and templates the run uses, copied by `nativeflows_testkit` from the package data files, never computed by the core.

   It needs only `docs/` and its own folder, as the runbook's recomputation writer row requires ([README.md](../runbook/README.md)). Its pull requests record that it was written from a sparse checkout without the product's source (its path is DS-18's).

## 2. Invariant catalog

4. The catalog is [docs/catalogs/invariants.csv](../catalogs/invariants.csv), owned by DS-16. Its columns:

   | Column | Content |
   | --- | --- |
   | `code` | `INV-nn`, or `INV-nnn` from INV-100 ([ADR-0033](../adr/0033-production-master-data.md) rule 16), never reused |
   | `name` | snake_case |
   | `area` | `ledger`, `platform`, `inventory`, `receivables_payables`, `documents`, `warehouse`, `planning`, `subledger`, `safety`, `production`, `tax`, `cash`, `reporting`, `crm` or `master_data` (ADR-0056) |
   | `check_point` | rule 10 |
   | `first_step` | The first build step at which the data it checks can exist; from then on it must have code and pass |
   | `flagged` | The open question it depends on, if its statement restates an interim rule |
   | `keys` | The business key fields a violation reports |
   | `source`, `added_in`, `statement` | |

   Codes are grouped: 01–19 ledger and platform, 20–29 inventory, 30–39 receivables and payables, 40–49 documents, 50–59 warehouse (ADR-0023), 60–69 planning (ADR-0024), 70–79 subledgers (ADR-0025), 80–89 agent safety and platform integrity (ADR-0027, ADR-0029), 90–93 commercial documents ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 23) and 94–97 cash and bank ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 20), where INV-92 and INV-97 have area `ledger`; INV-98 is cash ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 17) and INV-99 is ledger (a journal line's posting date and fiscal year are its entry's, [ADR-0014](../adr/0014-universal-journal.md) rule 5 note). INV-37 (GR/IR) has area `ledger` but sits in 30–39 beside the open-item checks, INV-38 (partner accounts while `ledger` is activated, [ADR-0015](../adr/0015-account-determination.md) rule 11 note) is the next free code there, and INV-48 has area `inventory` but sits in 40–49 because 20–29 is full. INV-100 to INV-199 are production, area `production`; [ADR-0033](../adr/0033-production-master-data.md) rule 16 reserves INV-100 to INV-102 and PAR-12 until the production core step is numbered; ADR-0034 and [ADR-0035](../adr/0035-production-costing.md) reserve INV-103 to INV-108 and PAR-13. [ADR-0036](../adr/0036-multi-level-mrp.md) reserves INV-109 and INV-110, [ADR-0037](../adr/0037-subcontracting.md) INV-111 and INV-112, and [ADR-0046](../adr/0046-product-configuration.md) rule 18 INV-113 to INV-115; all sixteen are in the catalog (rule 5 note). The naive recomputation (rule 29) gains cost-object nodes ([ADR-0035](../adr/0035-production-costing.md) rule 20). INV-56 was restated by [ADR-0031](../adr/0031-design-simplifications.md) rule 11, which strengthens it. Group 80–89 is full with INV-89 ([ADR-0038](../adr/0038-audit-and-observability.md) rule 8); further safety and platform invariants use INV-200 to INV-299: INV-200 is the company check of the audit keys that stay single-column (S2 schema review R5-N1, 2026-11-21) and INV-201 is unused; INV-202 to INV-205 are policy and work queue checks ([ADR-0043](../adr/0043-policy-and-approval.md), [ADR-0042](../adr/0042-work-queue.md)); INV-206 to INV-209 are unused ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md)); INV-210 to INV-216 are the agent runtime's ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md)); INV-217 to INV-219 are unused; INV-220 to INV-239 are the block of users, roles and approval stages ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 25; [ADR-0055](../adr/0055-approval-pools-and-stages.md)), of which INV-220 to INV-231 are taken; tax invariants use INV-300 to INV-399, area `tax` ([ADR-0041](../adr/0041-tax-engine.md) rule 12), of which INV-300 to INV-302 are taken (INV-302: a company's own tax rows are approved and shadow no package key, ADR-0041 rule 4 note of 2026-11-21). Reporting and printing invariants use INV-400 to INV-499, area `reporting` ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 31). INV-410 to INV-419 are agent-assisted analysis ([ADR-0060](../adr/0060-agent-assisted-reporting-and-analysis.md) rule 35), of which INV-410 to INV-414 are taken, INV-413 and INV-414 with area `safety`. Configurable workflows and decision artifacts use INV-670 to INV-699, areas `safety` and `platform` ([ADR-0058](../adr/0058-configurable-workflows.md) rule 28; [ADR-0059](../adr/0059-ai-tuning-and-development-of-deterministic-functions.md) rule 28); INV-670 to INV-687 are taken. Configurable policy settings use INV-700 to INV-729 ([ADR-0063](../adr/0063-configurable-policy-settings.md) rule 29); INV-700 to INV-718 are taken. Barcode invariants use INV-620 to INV-639, area `master_data` ([ADR-0061](../adr/0061-barcodes.md) rule 27); INV-620 to INV-624 are taken. Document intake and product engineering invariants use INV-640 to INV-669 ([ADR-0057](../adr/0057-document-intake-and-extraction.md), [ADR-0062](../adr/0062-product-engineering-workflow.md)): INV-640 to INV-646 (areas `platform`, `safety` and `tax`) and INV-650 to INV-655 (areas `production` and `safety`, first step the production core step) are taken. The test package `l10n_xx` declares `data_processing.policy` ([DS-16-l10n_xx/settings.yaml](DS-16-l10n_xx/settings.yaml)). Production agent invariants use INV-730 to INV-759, areas `safety`, `production` and `planning` ([ADR-0064](../adr/0064-production-agent.md)); INV-730 to INV-741 are taken, with no first step until the production core step is numbered. The deterministic auto-post gateway uses INV-760 to INV-789, area `safety`, first step 6 ([ADR-0065](../adr/0065-deterministic-auto-post-gateway.md), accepted 2026-11-21); INV-760 to INV-764 are taken, and INV-84 is restated. Work cases use INV-790 to INV-799, areas `platform` and `safety`, first step 5 ([ADR-0066](../adr/0066-work-cases.md), accepted 2026-11-21); INV-790 to INV-793 are taken. Operating presets and the setup phase use INV-800 to INV-809, areas `platform` and `safety`, first step 5 ([ADR-0067](../adr/0067-quickflows-operating-presets.md), accepted 2026-11-21); INV-800 to INV-805 are taken. Sites and logistics master data use INV-810 to INV-819 ([ADR-0068](../adr/0068-sites-and-core-logistics-payment-master-data.md), accepted 2026-11-21), of which INV-810 to INV-812 are taken; business units INV-820 to INV-829 ([ADR-0069](../adr/0069-business-unit-dimension.md)), of which INV-820 to INV-823 are taken, first step 1; quality INV-830 to INV-839 ([ADR-0070](../adr/0070-quality-management-core.md)), of which INV-830 to INV-834 are taken, first step 5; shop-floor execution INV-840 to INV-849 ([ADR-0071](../adr/0071-work-orders-and-shop-floor-execution.md)), of which INV-840 to INV-845 are taken, with no first step until the production core step is numbered. The costing sheet and cost component structure use INV-850 to INV-859 ([ADR-0072](../adr/0072-costing-sheet-and-cost-component-structure.md), accepted 2026-11-21), of which INV-850 to INV-854 are taken, also with no first step yet. Version 0.1.0 has 276 invariants. A hash test ([ADR-0031](../adr/0031-design-simplifications.md) rule 4) checks that a batch creating a record with a server-generated ID and referring to it in a later item hashes equally in simulate and execute. Later items add rows with the next free code in their group. Rows written before the ADRs listed their own codes (most of INV-01 to INV-32) name a source ADR that does not cite the code; the catalog is authoritative, and later ADRs list their codes in their catalog rule. CRM invariants use INV-500 to INV-599, area `crm` ([ADR-0052](../adr/0052-minimal-crm.md) rule 34); INV-49, area `documents`, takes the last free code of the documents group 40–49. Units of measure invariants use INV-600 to INV-619, areas `documents`, `inventory` and `master_data` ([ADR-0056](../adr/0056-multiple-units-of-measure.md) rule 25); INV-600 to INV-606 are taken (INV-606: a row's unit is a core unit or its own company's, S2 schema review R5-N1). Data-structure additions and stock documents use INV-860 to INV-869, areas `master_data`, `receivables_payables`, `documents` and `inventory` ([ADR-0074](../adr/0074-core-data-structure-additions.md), [ADR-0075](../adr/0075-stock-documents.md), accepted 2026-11-21); all ten are taken. INV-870 to INV-879 are the remaining stock documents ([ADR-0075](../adr/0075-stock-documents.md) rules 11 to 15), area `inventory`, of which INV-870 to INV-872 are taken. INV-880 to INV-889 are internal messaging and notifications ([ADR-0076](../adr/0076-internal-messaging-and-notifications.md), accepted 2026-11-21), of which INV-880 to INV-884 are taken. INV-890 to INV-899 are personal data protection ([ADR-0079](../adr/0079-personal-data-protection.md), accepted 2026-11-21), areas `platform` and `safety`, first step 5, of which INV-890 to INV-894 are taken.
5. Each catalog row has exactly one check, registered with `@invariant("INV-21")` in `nativeflows_testkit.invariants`. A CI test compares catalog and registry:
   - a row whose `first_step` is at or below `[tool.nativeflows] build_step` (DS-18) and has no check fails;
   - a check without a row fails;
   - a row above the current step may have a check, which runs in report-only mode.

   Note: INV-100 to INV-115 are in the catalog with an empty `first_step` and the `flagged` value "ADR-0032 rule 7: production core step (number pending author)". Until the author numbers the step, an empty `first_step` counts as above the current step: a check may exist and runs report-only. Numbering the step fills the column ([ADR-0033](../adr/0033-production-master-data.md) rule 16) (holistic review 2026-11-15, item P20).
6. The author decides (ADR-0005 item 3):
   - removing or weakening an invariant;
   - changing a check so a failure passes;
   - changing the recomputation to make a failure pass;
   - changing an invariant when the author answers an open question named in its `flagged` column.

   Adding an invariant or making a check stricter is technical. CI labels `reserved-review` every pull request that touches `invariants.csv`, `nativeflows_testkit/invariants/`, `nativeflows_reference/` or any author-only path (rule 22).

## 3. Checks, outcomes and violations

7. A check is a function `(connection, scope) -> list[Violation]`:
   - It runs read-only in one REPEATABLE READ snapshot, so all checks of a check point see one state.
   - It is preferably one set-based SQL query returning the violating rows.
   - It never raises for bad data: bad data is a violation. An exception means the check itself is broken; that is reported separately, and `nativeflows-check` exits with 2.
   - `scope` is a company, optionally narrowed to `as_of` or to the documents a command wrote.
   - `day` checks may run incrementally on a day's documents, with a full run at each month end and at the end of a run.
8. Before every check point the harness runs the outbox delivery workers in process, in a deterministic order, until no delivery is pending (ADR-0013). Checks therefore never race asynchronous consumers. A delivery left `held` is a violation of INV-13.
9. Checks that need state across check points keep it in a state directory (`--state <dir>` for `nativeflows-check`, in memory for state machines):
   - INV-08 fingerprints are SHA-256 over the canonical JSON of a posted document's header without `state`, its versions, journal entries and lines, and material lines. `state` may change only from `posted` to `reversed` (ADR-0009 rule 14).
   - INV-11 compares a company's fingerprints of business tables before and after a retry: documents, versions, journal entries and lines, material lines, stock tables, open items, outbox events, deliveries and `idempotency_record`. Audit, technical-queue and telemetry tables are excluded.

   The append-only triggers themselves are tested by SQL-level tests in DS-18, not by the harness.
10. `check_point` values:
    - `command`: checked around each command by the command protocol (rule 15): INV-11, INV-12, INV-14, INV-15, INV-18, INV-19.
    - `day`: after every simulated day of a replay and after every step of a state machine.
    - `run`: once at the end. None in 0.1.0.

    A check that cannot be evaluated in a given setting, such as a `command` check from `nativeflows-check`, reports `not_evaluated`, never pass.
11. A violation is a JSON object (schema `docs/catalogs/violation.schema.json`) with these fields:
    - `check`: `INV-nn` or `INV-nnn`; `REF-<kind>-<pair>` for a reference difference (rule 30); or `PAR-nn` for a parallel test (rule 31).
    - `company`.
    - `keys`: business keys, per the catalog's `keys` column.
    - `expected` and `actual`: strings, either canonical decimals (ADR-0006 rule 13) or IDs and hashes.
    - `message`.
    - `first_failing`: the first command after which the check failed, with `command_id`, `command_type`, `idempotency_key`, the event reference, the simulator triple or Hypothesis seed, and `sim_day`.

    When one event maps to several commands, the first failing command is the first in the adapter's order. When a replay fails at a day check, the harness replays that day again in a fresh company, with checks after every command, to fill `first_failing`. For a reference difference it bisects by day, then by event, recomputing the naive result on each prefix. The defect dedupe key is `check` plus `first_failing.command_type` ([testing-operations.md](../runbook/testing-operations.md#defects-to-regression-scenarios); ADR-0003 R7).
12. `nativeflows-check` runs the registry read-only against a database and prints violations and `not_evaluated` results as JSON lines:
    - options: `--company`, `--as-of`, `--only INV-..`, `--area`, `--state <dir>`;
    - exit codes: 0 clean, 1 violations, 2 a broken check;
    - coding agents use it locally, and the test server after each replay day;
    - it may run against production only with the read-only role, on a standby replica or with `statement_timeout`, never with write rights ([ADR-0038](../adr/0038-audit-and-observability.md) rule 9);
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

    Amendment ([ADR-0053](../adr/0053-core-neutrality.md) rule 9): core examples create their company with the fictional test package `l10n_xx` (regime `test`, `test_fixture` settings, a chart of about 30 accounts, two or three tax codes and one deductibility rule), not with the Vietnam package, so core property tests never depend on the overlay. `l10n_vn` runs in its package-level golden tests (`l10n/l10n_vn/tests/golden/`) and its dataset profiles (DS-17).
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
    - `expected.csv` is generated from the workbook by `nativeflows-scenario export`, deterministically. Export needs cached values (`data_only=True`), so the workbook must be saved from a spreadsheet program. CI regenerates the file and fails on any difference, which keeps a reviewable text form without a second source of truth.
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
    | `report_line` | `report` (code), `line`, `from`, `to`; company amounts ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 32) |

    - Balances are closing balances, signed debit positive (ADR-0014 rule 6).
    - Quantities are in the inventory unit.
    - `document_ref` is the event's scenario-local `ref`, never a core-assigned number.
    - Rows with equal keys are summed (e.g. several `journal_line` rows of one document and account).
    - Each kind's table in the workbook has a `complete` flag; the export writes it to `expected_complete.csv` (`kind`, `complete`). When true, unlisted keys of that kind must be zero or absent. The export schema fixes the layout of the `expected` sheet: one table per kind, starting at a header row whose first cell is `kind`.
25. Regression scenarios:
    - `nativeflows-scenario freeze` writes the shortest failing event sequence, taken from a Hypothesis failure or from a (triple, day).
    - While its defect is open, the scenario carries `expected_failure: {check, since_commit}`, a strict expected failure: CI stays green while it fails with exactly that check, and turns red if it passes or fails differently. An agent may add the field in the commit that creates the scenario, and the fix removes it; both make CI stricter. Adding it to an existing scenario, changing its `check`, or using it on a golden scenario is the author's.
    - It always runs every invariant and the core-versus-naive comparison, so defects found only by reference comparison are frozen too. An `expected.csv` is optional and written only by the author.
    - Defects found by parallel tests are frozen as parallel tests (rule 31).
26. In a `pending_verification` scenario only the comparisons involving the golden value (`REF-…-golden_core`, `REF-…-golden_naive`) are report-only and never count as matched; invariants, the outcome oracle and core-versus-naive still fail CI. Such scenarios are listed in every gate report. Only the author changes `status` (ADR-0003 R10).
27. Golden expected values are the author's (ADR-0005 item 3; runbook step 0). An agent may draft `scenario.yaml` without `status`, and may commit a regenerated `expected.csv` that CI verifies against the workbook. CI fails when a commit with an agent's `Co-Authored-By` trailer changes an author-only path. That check is a tripwire; the control is the author's line-by-line review of every `reserved-review` pull request (rule 6).
28. The scenario runner replays events through the adapter of `build_step` or a later step, with the command protocol of rule 15, so scenarios written at step 1 keep running later:
    - After each event it runs the `day` checks.
    - At the end it compares expected values with core query results by exact equality: `GetTrialBalance` (per account, period, currency and amount kind), `ListJournalLine`, `GetStockBalance` (ADR-0020), and the open-item and average-cost queries their items add. `report_line` rows compare with `GetStatutoryReport` ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 15).
    - `GetTrialBalance` is a requirement this item places on the ledger module at step 1.

## 7. Naive recomputation and comparison

29. `nativeflows_reference` computes expected results from the run directory alone (rule 3), in the same row format as `expected.csv`. It is deliberately simple: plain loops over events, `fractions.Fraction` for every intermediate value, rounding only where the specification rounds (modes from `regime_snapshot.json`), and no caching.

    | Step | Results |
    | --- | --- |
    | 1 | Trial balance per account and period, in transaction and company currency, and in group currency where the installation sets one (journal-level events and the step 1 projection documented by DS-17) |
    | 3 | Stock quantity and value per item, warehouse and date; periodic average per item, valuation area and period, with transfers solved; cost of goods sold; landed cost allocations and the locked-period split (ADR-0020 rules 11–13; ADR-0021) |
    | 4 | Open items and their open amounts, from opening balances on (ADR-0026) |
    | 6 | Carrying amounts on settlement; realized FX |
    | 7 | VAT per tax code and return line |
    | 8 | Unrealized FX revaluation; closing entries; statutory report lines from the definitions in the regime snapshot ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 32) |

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
    | PAR-11 | 3 | Two pick releases for the same item and warehouse at once never allocate the same units ([ADR-0030](../adr/0030-commercial-seams-and-imports.md) rule 12) |

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
- DS-18: role `nativeflows_check`; `[tool.nativeflows] build_step`; the `reserved-review` label and the author-path tripwire; field classes in generated schemas; package `nativeflows_client` and the import contracts of section 1; CI with two installations.
- Ledger module (step 1): query `GetTrialBalance`.
- DS-36: decided, [ADR-0038](../adr/0038-audit-and-observability.md) rule 9. DS-16 also adds the property test that change capture is complete (rule 3).
- DS-30: DS-16 adds the property test that a command `ListAllowedCommand` reports as allowed never fails simulation with `invalid_state_transition`, `permission_denied`, `human_only`, `segregation_of_duties` or `change_pending` ([ADR-0040](../adr/0040-ui-architecture.md) rule 8).
- Work package 7 creates the JSON Schemas `violation`, `scenario` and `comparison` in `docs/catalogs/` by hand, with catalogs README rows; DS-17's work package creates `business-events` (generated, CI diff).
- The runbook README's note on replacing invariant descriptions with IDs can now be done; it is the author's document.

## Documents updated

- [docs/catalogs/invariants.csv](../catalogs/invariants.csv): new, version 0.1.0.
- [docs/catalogs/README.md](../catalogs/README.md): invariants row.
- [docs/design/backlog.md](backlog.md): DS-16 row links here.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for invariant, check point, outcome class, golden, regression and proposed scenario, naive recomputation, violation, `nativeflows-check` and `nativeflows-scenario`, test tooling packages.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
