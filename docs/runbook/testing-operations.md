# Continuous testing operations

How the testing described in [12-testing.md](../spec/12-testing.md) is run day to day. The rule from that file governs everything here: **the model only proposes scenarios; deterministic code judges right and wrong.** The model never computes expected results. Tools are fixed by ADR-0002 (pytest on real PostgreSQL via testcontainers, never SQLite; Hypothesis stateful testing). The harness design is DS-16; the simulator design is DS-17.

## Environments

| Environment | Runs | Data | From |
| --- | --- | --- | --- |
| Local / agent workspace | Unit tests, testcontainers PostgreSQL, small dataset | Synthetic only | Step 0 |
| CI (GitHub Actions) | Every commit; must be green to merge | Small dataset | Step 0 |
| Test server | Nightly and after every deploy: medium replay, long Hypothesis runs, test-scenario model, concurrency tests, coverage and comparison reports | Synthetic only (medium; large from step 10) | Step 0 |
| Staging | Release candidates; step 11 rehearsal with the pilot's real data | Synthetic; pilot data only during step 11 and later | See the open question on when staging is stood up |
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

The same run, shortened, follows every deploy to the test server. A failing nightly blocks merges until the author has triaged it.

## Budgets

Each nightly run has a wall-clock limit and an LLM spend limit for the test-scenario model; a circuit breaker stops the model when the limit is reached and the deterministic part of the run continues. Agent budgets (per agent, per company, per day) follow [03-agent-safety.md](../spec/03-agent-safety.md), rule 8. The values are not set in the specification; they are an open question (DS-16, DS-17, DS-32). The Friday review checks spend against the limits.

## Defects to regression scenarios

1. **Detect:** an invariant fails, a reference comparison differs, or a parallel test fails.
2. **Deduplicate:** a defect is keyed by the failing check and the first failing command type; a repeat adds an occurrence to the existing defect, not a new one ([12-testing.md](../spec/12-testing.md)).
3. **Reproduce:** from the simulator triple and the day, or from the Hypothesis seed; shrink to the shortest failing sequence.
4. **Freeze:** the shortest sequence becomes a regression scenario in CI, failing, before the fix (stage 2 in [README.md](README.md#the-unit-of-work)).
5. **Classify:** core defect (fix in the lowest layer it belongs to); reference error (the author corrects the golden scenario or the recomputation and records why); spec gap (open question; the author decides).
6. **Fix and close:** the regression scenario turns green and stays in CI permanently.

The spec says defects go to the work queue, which is built in step 5 (DS-29). Where defects are tracked before then is an open question.

## Coverage reports

- **Edge-case coverage:** per run, each EC-xx with its injection frequency target and actual count, and whether the scenario exercising it passed. Gate views: edge cases for steps 1–3 (step 4 gate), every edge case (step 10 gate). Each edge case therefore needs a build-step attribute in the DS-17 catalog.
- **Invariant report:** each INV-xx with checks run and failures.
- **Reference comparison report:** per company and period, differences between core, naive recomputation and golden results.
- **Code coverage:** the core coverage threshold required by [18-license-governance.md](../spec/18-license-governance.md); the value is an open question (DS-18).
- **Agent metrics** (from the first agent): drafts accepted unedited, share of deterministic steps, LLM cost per document ([14-agent-workflows.md](../spec/14-agent-workflows.md)).

## Outside this approach's reach

As [12-testing.md](../spec/12-testing.md) says: concurrency defects get dedicated parallel tests; misreading regulations is caught by an accountant or auditor review ([escalation.md](escalation.md#unverified-legal-rules)); data-entry speed is measured with real users (step 9 gate).
