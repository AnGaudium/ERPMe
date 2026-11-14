# Continuous testing operations

How the testing described in [12-testing.md](../spec/12-testing.md) is run day to day. The rule from that file governs everything here: **the model only proposes scenarios; deterministic code judges right and wrong.** The model never computes expected results. Tools are fixed by ADR-0002 (pytest on real PostgreSQL via testcontainers, never SQLite; Hypothesis stateful testing). The harness design is DS-16; the simulator design is DS-17.

## Environments

| Environment | Runs | Data | From |
| --- | --- | --- | --- |
| Local / agent workspace | Unit tests, testcontainers PostgreSQL, small dataset | Synthetic only | Step 0 |
| CI (GitHub Actions) | Every commit; must be green to merge | Small dataset | Step 0 |
| Test server | Nightly and after every deploy: medium replay, long Hypothesis runs, test-scenario model, concurrency tests, coverage and comparison reports | Synthetic only (medium; large from step 10) | Step 0 |
| Staging | Release candidates; step 11 rehearsal; migration tests after go-live | Synthetic; real data only during a rehearsal or migration test, deleted within 7 days after it | Step 10 ([ADR-0003](../adr/0003-build-operating-rules.md) R2, R12) |
| Production | The pilot | Pilot data | Go-live |

Pilot data never enters the repository, CI or the test server.

## What runs where

| Check | CI (every commit) | Test server (nightly, after deploy) |
| --- | --- | --- |
| ruff, pyright strict, import-linter contracts | Yes | — |
| Unit and module tests on real PostgreSQL | Yes | — |
| Hypothesis state machine with invariants after every step | Short profile | Long profile |
| Small dataset replay, every invariant after every simulated day | Yes | — |
| Medium dataset replay | — | Yes, from the step it can be replayed |
| Large dataset replay | — | From step 10 |
| Golden scenarios | Yes | Yes |
| Naive recomputation comparison | Small | Medium, large |
| Regression scenarios (frozen defects) | All | All |
| Parallel tests: stock posting per (item, warehouse), outbox, idempotency | Short | Long |
| Test-scenario model (LLM proposes situations) | — | Yes, within budget |
| Agent replay evaluation (recorded LLM responses) | Yes, from the first agent | — |
| Agent real-LLM evaluation | Whenever a model or prompt changes; the change requires passing it (Principle 11) | — |
| Edge-case coverage report | Small | Medium, large |

## Running the simulator

- A run is identified by (simulator version, seed, dataset version). The same triple reproduces the same business-event log exactly; any failure is replayed from it ([12-testing.md](../spec/12-testing.md#synthetic-dataset)).
- The business-event log is versioned. A new event type or field raises the log version; old logs remain readable by the adapters.
- Each build step adds an adapter that translates events into the commands that exist at that step. Adapters of earlier steps are kept, so the same log can be replayed at any step.
- The simulator also writes the input files agents read: e-invoice XML, bank statement files, emails with quotation requests, migration files.
- The simulator records what happened in business terms (quantities, prices, payments, rates). It never writes expected balances; those come from the naive recomputation and the golden scenarios.
- Names, tax IDs and addresses are generated. The dataset is CC0 ([18-license-governance.md](../spec/18-license-governance.md)). Where generated logs are stored is decided in DS-17.
- Extending the simulator for a step: add events and edge cases first (B4), then the adapter, then confirm the small dataset still covers every edge case at least once.

## The nightly run

1. Deploy `main` to the test server.
2. Regenerate or load the datasets for the current simulator version.
3. Replay the medium dataset (large from step 10) day by day through the current adapters; check every invariant after every simulated day.
4. Compare with the naive recomputation and the golden scenarios.
5. Run long Hypothesis profiles and parallel tests.
6. Run the test-scenario model: it proposes unusual but realistic situations as business events; the same adapters execute them; invariants and recomputation judge them.
7. Publish the nightly report: run ID, simulator triple, invariants (pass, fail with first failing day), reference differences, edge-case coverage, replay time per simulated day, LLM spend, new defects.

Before go-live the test server is deployed only by the nightly run, so the after-deploy run is the nightly run ([ADR-0003](../adr/0003-build-operating-rules.md) R6). A failing nightly blocks merges until the author has triaged it.

## Budgets

Limits ([ADR-0003](../adr/0003-build-operating-rules.md) R6): CI on a commit 15 minutes or less (slower checks move to the nightly run); nightly run 6 hours or less; medium replay inside it 4 hours or less, otherwise slowness is a defect; test-scenario model USD 5 or less per night, stopped by a circuit breaker while the deterministic part continues. Agent budgets (per agent, per company, per day) follow [03-agent-safety.md](../spec/03-agent-safety.md), rule 8, with values set in DS-32. The Friday review checks spend against the limits.

## Defects to regression scenarios

1. **Detect:** an invariant fails, a reference comparison differs, or a parallel test fails.
2. **Deduplicate:** a defect is keyed by the failing check and the first failing command type; a repeat adds an occurrence to the existing defect, not a new one ([12-testing.md](../spec/12-testing.md)).
3. **Reproduce:** from the simulator triple and the day, or from the Hypothesis seed; shrink to the shortest failing sequence.
4. **Freeze:** the shortest sequence becomes a regression scenario in CI, failing, before the fix (stage 2 in [README.md](README.md#the-unit-of-work)).
5. **Classify:** core defect (fix in the lowest layer it belongs to); reference error (the author corrects the golden scenario or the recomputation and records why); spec gap (open question; the agent decides a technical gap under [ADR-0005](../adr/0005-technical-decisions-delegated.md), the author decides the rest).
6. **Fix and close:** the regression scenario turns green and stays in CI permanently.

Defects live in the GitHub issue tracker, label `defect`, titled with the dedupe key, before and after step 5. The work queue (DS-29) holds business work only ([ADR-0003](../adr/0003-build-operating-rules.md) R7).

## Coverage reports

- **Edge-case coverage:** per run, each EC-xx with its injection frequency target and actual count, and whether the scenario exercising it passed. An edge case counts as exercised only when its events ran through commands at or after its first executable step (DS-17 catalog column, [ADR-0003](../adr/0003-build-operating-rules.md) R1). Gate views: edge cases for steps 1–3 (step 4 gate), every edge case (step 10 gate).
- **Invariant report:** each INV-xx with checks run and failures.
- **Reference comparison report:** per company and period, differences between core, naive recomputation and golden results.
- **Code coverage:** 90% branch coverage on the core packages, enforced from step 1; other packages reported only ([ADR-0003](../adr/0003-build-operating-rules.md) R4).
- **Agent metrics** (from the first agent): drafts accepted unedited, share of deterministic steps, LLM cost per document ([14-agent-workflows.md](../spec/14-agent-workflows.md)).

## Outside this approach's reach

As [12-testing.md](../spec/12-testing.md) says: concurrency defects get dedicated parallel tests; misreading regulations is caught by an accountant or auditor review ([escalation.md](escalation.md#unverified-legal-rules)); data-entry speed is measured with real users (step 9 gate).
