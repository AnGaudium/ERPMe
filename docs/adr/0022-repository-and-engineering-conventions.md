# ADR-0022: Repository and engineering conventions

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-18. Related decisions: D3, D14. Principles 1, 10, 13. Build principles B2, B6, B7, B8. ADR-0001 to ADR-0010, ADR-0013 to ADR-0017, ADR-0020, ADR-0021, DS-14, DS-16, DS-17.

## Decision

ERPMe is one repository and one uv workspace:
- the product is the distribution `erpme`, made of modules in fixed layers;
- test tooling lives in separate distributions that the product never imports;
- localization packages live under `l10n/`.

Modules talk to each other only through their contracts:
- commands and events, as spec 07 requires;
- in-process posting interfaces, which run inside the calling command's transaction and plan. One `Post<Type>` can then write the journal, stock, number and state together, as ADR-0009 and ADR-0020 need.

All tables are in one PostgreSQL schema `erpme`, plus `types` for domains and `procrastinate` for the job queue. Each table has one owning module, and lock helpers register in one global lock order.

Checks:
- One developer CLI, `erpme-dev`, runs every check. CI jobs call only its subcommands, so an agent reproduces any failure with one command.
- CI runs on GitHub-hosted runners, in parallel jobs of 15 minutes or less.
- The nightly run is started by a timer on the test server, not by GitHub, so nothing from the public repository can start code there.
- Generated interfaces are committed and checked.

### Rules

**Layout**

1. Top level:

   | Path | Holds |
   | --- | --- |
   | `pyproject.toml` | uv workspace root, with members as globs (`backend`, `tools/*`, `l10n/*/code`) so a sparse checkout still resolves. Holds shared ruff, pyright, import-linter, pytest and coverage settings, and `[tool.erpme] build_step`, raised by the author's commit at each gate (DS-16 rule 5) |
   | `uv.lock` | The one lock file |
   | `backend/` | Distribution `erpme`: `src/erpme/<module>/`, `migrations/` (Alembic), `provision/` (rule 7), `tests/`, `generated/` (rule 17) |
   | `tools/<package>/` | Distributions `erpme_dev`, `erpme_events`, `erpme_client`, `erpme_simulator`, `erpme_adapters`, `erpme_testkit`, `erpme_reference`. Each has its own `pyproject.toml` and `tests/`. `erpme_reference` and its tests need only the standard library (DS-16 rule 3) |
   | `l10n/l10n_<country>/` | Localization packages (ADR-0016 rule 1; layout DS-14). Each package's code in `code/` is its own distribution |
   | `frontend/` | The React app (from step 1, DS-30) |
   | `tests/scenarios/` | Regression, package-neutral golden and kept proposed scenarios (DS-16 rule 22). Regime-dependent goldens live in `l10n/<package>/tests/golden/` |
   | `datasets/` | Lock files (DS-17 rule 26) |
   | `docs/` | Specification, ADRs, design, catalogs, runbook |
   | `.github/` | Workflows, pull request template, `dco.toml` (rule 15) |
   | `.claude/skills/` | Coding-agent skills (rule 23) |
   | `deploy/` | Test server files from step 0 (rule 18); the rest is DS-37 |

**Modules, contracts and layers**

2. Modules of `erpme` (ADR-0004 rule 7) by layer. A module imports only from lower layers. A module is created by the first work package that needs it (B7). New modules beyond this list are added by ADR.

   | Layer | Modules |
   | --- | --- |
   | 6 · Composition | `app`: registers every module's handlers, consumers and queries; startup checks; entry points (rule 5) |
   | 5 · Interfaces | `api` (REST and MCP generated from the registry), `query` (read-only layer, DS-33), `agents` (after step 4), `sdk` (rule 4) |
   | 4 · Commercial | `sales`, `purchasing`, `cash` (from steps 5–6), `crm`, `planning` ([ADR-0024](0024-planning.md); it reads `inventory.contract`'s `demand_supply_line` and hands over through `inventory.contract.request_replenishment`) |
   | 3 · Core business | `ledger` (journal, accounts, account determination, multi-currency), `inventory` (material documents, stock, costing, landed cost, and the warehouse management tables of [ADR-0023](0023-warehouse-management.md)), `master_data` (partners, products, warehouses, units, currencies), `tax`; `production` (Phase 2) and `assets` (Phase 3) per [ADR-0025](0025-later-phase-seams.md) |
   | 2 · Platform | `registry` (command registry, dispatcher, envelope, idempotency; its public entry point `erpme.registry.dispatch`), `documents` (lifecycle, versions, numbering), `periods`, `permissions`, `outbox`, `audit`, `localization` (loader), `db` (engine, session settings, RLS context, the generic lock helper and the lock-order registry, the `MetaData` naming convention), `agent_runs`, `work`, `attachments` ([ADR-0027](0027-cross-cutting-ownership.md) rule 1; `documents` and `permissions` may import the `agent_runs` contract) |
   | 1 · Foundation | `numeric` (ADR-0006), `clock` (ADR-0007), `ids`, `i18n`, `errors` |

3. Shape of each module:
   - A module that owns tables or commands has:
     - `contract.py`, the only part other modules import (rule 4);
     - `handlers/`;
     - `tables.py`, private;
     - `services/`, private;
     - `AGENTS.md`, at most 40 lines;
     - tests in `backend/tests/<module>/`.
   - Foundation modules and `db` publish through their `__init__`.
4. A module's `contract.py` holds three things:
   - its command, query and event schemas;
   - its **posting interfaces**: plain functions that take the caller's `context`, such as `ledger.contract.write_journal_entry`, `inventory.contract.move_stock`, `documents.contract.assign_number` and `periods.contract.check_posting`;
   - the interfaces that localization packages implement for it, such as `ledger.contract.ExchangeRateFetcher`.

   Posting interfaces run in the calling command's transaction and become part of its plan. They have no permission, idempotency or policy step of their own: the outer command is the one the actor called and was authorized for. They read and write only through `context` (ADR-0008 rule 4). They are never exposed on REST or MCP.

   This is how "modules call each other only through commands and events" (spec 07) is read for synchronous posting. The accounting interface in SAP works the same way. Asynchronous work still goes through events and consumers (ADR-0013). `sdk` re-exports the package-facing interfaces from the owning contracts and defines none itself.
5. The composition root `erpme.app`:
   - imports every module's `handlers/` to register them. Import-linter exempts it from the layer contract, and nothing imports it;
   - is loaded by `erpme.registry.dispatch` on first use through a declared entry point (`importlib.metadata` group `erpme.app`), never by a static import, so the in-process transport of `erpme_client` sees a full registry and the layer contract holds; `dispatch` is the registry module's named exception to rule 3;
   - runs the startup checks: the `environment` setting is present (rule 9); package data and code versions match (ADR-0016 rule 3); the catalog versions are the ones loaded.

   Entry points:

   | Entry point | Runs |
   | --- | --- |
   | `erpme serve` | API server |
   | `erpme worker --queue <name>` | Delivery workers and Procrastinate job workers (rule 12) |
   | `erpme admin migrate` | Rule 8 |
   | `erpme admin bootstrap` | ADR-0017 rule 7 |

6. Import-linter contracts:
   - The layers of rule 2.
   - Independence between modules of layers 3 and 4, except their `contract`.
   - `erpme` imports no tool package and no `l10n_*`.
   - `l10n_*` imports only `erpme.sdk` (ADR-0016 rule 17).
   - Handlers import no network, file, LLM or job library. This is a `forbidden` contract, so it catches transitive imports (ADR-0008 rule 4).
   - The tool packages follow DS-16 section 1 exactly:

     | Package | May import |
     | --- | --- |
     | `erpme_events` | standard library, pydantic |
     | `erpme_client` | `erpme.registry.dispatch`, `erpme.numeric`, HTTP and MCP client libraries |
     | `erpme_adapters` | `erpme_events`, `erpme_client` |
     | `erpme_simulator` | `erpme_events` |
     | `erpme_testkit` | `erpme_events`, `erpme_adapters`, `erpme_client`, `erpme.numeric` |
     | `erpme_reference` | standard library only |

**Database**

7. Schemas, ownership and roles:
   - **Schemas.** One database. All tables are in schema `erpme`, domains are in `types` (ADR-0006), and Procrastinate's tables are in schema `procrastinate`. There is no schema per module: foreign keys cross modules and are declared by table name; one schema keeps RLS generation simple.
   - **Ownership.** Every `erpme` table is declared in exactly one module's `tables.py`. A CI check fails on a table owned twice or not at all; it exempts `alembic_version`, partitions and schema `procrastinate`.
   - **Roles.** Roles are cluster-level, so `backend/provision/roles.sql`, run as a superuser before any migration, creates the roles of ADR-0017 rule 18 and `erpme_check` (DS-16 rule 2: SELECT only, subject to RLS, never `BYPASSRLS`). The test fixture and the test server use the same file. Migrations only grant.
8. Migrations:
   - Alembic keeps one linear history in `backend/migrations/`. CI fails on more than one head and on any migration that does not upgrade an empty database to head.
   - The first migration creates the extensions `btree_gist` (ADR-0007) and `pg_trgm` (ADR-0002), the schemas, and the domains in `types`.
   - Triggers, RLS policies, functions and grants are written by hand; autogenerate may draft table changes.
   - RLS is generated by a versioned helper, `rls_v1`, that writes literal SQL into the migration, so later changes to the helper never rewrite history. It covers:
     - the company policy (ADR-0017 rule 19);
     - the `company_ids` read policy;
     - installation-scoped rows;
     - `FORCE ROW LEVEL SECURITY`;
     - per-role grants.

     A test compares live `pg_policies` with the expected definitions.
   - The claim function of ADR-0017 is a hand-written `SECURITY DEFINER` function owned by `erpme_claim`, with its own test.
   - Before go-live (B8), merged migrations may be squashed only in the author's commit that raises `build_step` at a gate. The test server rebuilds its database from empty every night.
   - Procrastinate's schema SQL is applied by an Alembic migration that pins its version.
   - `erpme admin migrate` runs Alembic, then loads the core catalogs, then the localization package data. Deployment and tests use this one command.
9. Session and runtime settings:
   - **How settings are applied.** Per role with `ALTER ROLE … SET` in `provision/roles.sql`, and with `SET LOCAL` inside a transaction when a registered job needs longer:
     - every session runs in UTC;
     - `lock_timeout` is 5 s;
     - `transaction_timeout` is 30 s for commands and queries, 4 min for consumer transactions (inside ADR-0013's 5-minute lease), and 15 min for registered long jobs (period-end costing, planning and forecast runs per [ADR-0024](0024-planning.md) rule 17, close tasks);
     - `idle_in_transaction_session_timeout` is 60 s;
     - `statement_timeout` is 30 s for `erpme_readonly` (DS-33 may lower it).
   - **Timeouts and limits.** Exceeding a timeout returns `concurrent_update` or `timeout` (ADR-0008 rule 11). Request bodies are limited to 10 MiB (`request_too_large`), and batches to 1,000 items (`batch_too_large`). A batch that cannot finish within its timeout should be split by the caller.
   - **Rate limits.** Token buckets per actor (not per actor kind), held in memory per API process (no Redis, ADR-0002), with these defaults:

     | Actor kind | Requests per second | Burst |
     | --- | --- | --- |
     | Human | 20 | 40 |
     | Agent | 5 | 10 |
     | Integration | 50 | 100 |

     `system` actors are exempt. Exceeding the limit returns `rate_limited`.
   - **`environment`.** The installation setting `environment` (`production`, `test`, `simulation`; ADR-0007 rule 15) is required at startup from `ERPME_ENVIRONMENT`. It is stored on first start and can never change away from `production`. In `test` and `simulation`, every external lookup and gateway (tax ID lookup, e-invoice, bank, exchange-rate fetchers, e-mail) is replaced by a recording stub (DS-17 rule 19; DS-24, DS-25).
10. Locks. The lock-order registry in `db` holds the one global order, asserted per command (each batch item and each consumer command separately) (superseded by the complete order of [ADR-0027](0027-cross-cutting-ownership.md) rule 10):
    1. period area state rows, share lock (ADR-0012 rule 9);
    2. `stock_value` rows ascending by item and warehouse ID, then lot and serial quantity rows (ADR-0020 rule 9);
    3. numbering counters (ADR-0009);
    4. `event_subject` rows, taken when the dispatcher writes the command's events after the handler returns (ADR-0013 rules 3, 4).

    With warehouse management the full order is [ADR-0023](0023-warehouse-management.md) rule 10: period rows, the warehouse task row, handling unit rows, `stock_value` rows, `stock_quantity` rows, bin rows, partner rows and open item rows ([ADR-0026](0026-open-item-core.md) rule 14), numbering counters, `event_subject` rows.

    The owning modules (`periods`, `inventory`, `documents`, `outbox`) implement their helpers on the generic helper and register them with their position; the helper raises in tests when one command takes locks out of order. A deadlock across items of one batch is detected by PostgreSQL and returned as `concurrent_update` (ADR-0008 rule 11).

**Tools and custom checks**

11. Tools and versions:
    - Python 3.14 and PostgreSQL 18 (ADR-0006). The test image is pinned by digest. `tzdata` is pinned.
    - uv; ruff with rule sets `E`, `F`, `W`, `I`, `N`, `UP`, `B`, `DTZ`, `TID`, `S`, `PL`.
    - `TID251` bans these qualified names: `datetime.datetime.now`, `datetime.datetime.utcnow`, `datetime.date.today`, `time.time` (ADR-0007; `erpme.clock` is exempt), and `random` inside `erpme`.
    - `ruff format`; pyright strict on every distribution; pytest with pytest-xdist, testcontainers, Hypothesis and pytest-cov (branch).
12. Outbox workers (ADR-0013):
    - `erpme worker --queue events|integrations|jobs|pdf`.
    - Workers wake on `NOTIFY erpme_outbox`, sent by the emitting transaction, and poll every 5 s as a fallback.
    - Retry delay after attempt n is min(2ⁿ s, 1 h), up to the consumer's `max_attempts`, after which the delivery is held (ADR-0013 rule 8).
    - A daily job creates `outbox_event` partitions 3 months ahead and drops expired ones under ADR-0013 rule 15.
    - Procrastinate's stalled-job retry runs from the `jobs` worker, with a heartbeat of 30 s and stalled after 5 min.
    - Step 1 work package 6 implements this rule.
13. `erpme_dev.checks` holds the checks no tool provides, each named after the rule it enforces. Each failure reports `file:line`, the rule ID and a one-line fix:
    - **Floats.** No floating-point types in migrations, and none for amounts, quantities, prices, rates or percentages in `erpme` (ADR-0006 rule 12). Other floats, such as timeouts, need a `# float-ok: <reason>` comment.
    - **Rounding and conversion.** Neither happens outside `erpme.numeric` (ADR-0006 rules 10, 15).
    - **Database time functions.** None of the banned ones appear in SQL (ADR-0007 rule 16).
    - **Identifiers.** No identifier is longer than 63 bytes or on a reserved list (ADR-0004 rules 4, 6).
    - **Serialized tables.** These are referenced only by their registered helpers and by migrations (ADR-0008 rule 10).
    - **Session locks and settings.** No `pg_advisory_lock`, no sequences and no non-`LOCAL` `SET` on handler and trigger paths. A harness test snapshots every sequence before and after a simulation (ADR-0008 rule 9).
    - **Catalogs:**
      - system accounts, including the comparison with the latest released tag (ADR-0010 rule 16);
      - transaction keys (ADR-0015) and movement types (ADR-0020);
      - invariants and parallel tests against their registries (DS-16 rules 5, 31);
      - edge cases against injectors and the business-event schema (DS-17 rules 22, 23);
      - `inventory_value_role` declared by every document type that posts value-only inventory lines (ADR-0020 rule 12).
    - **Packages.** Localization packages pass validation (ADR-0016 rule 15).
    - **Generated test data.** Every generated tax ID carries the fictional prefix (DS-17 rule 19).
    - **Documents.** Relative Markdown links resolve, and per-directory `AGENTS.md` files are within 40 lines.
    - **Licences and workflows.** Dependency licences are on the allowlist ([18](../spec/18-license-governance.md)). No workflow uses a self-hosted runner, and actions are pinned by commit SHA.

**One command for agents and CI**

14. `erpme-dev` subcommands. Each prints a JSON summary as its last line with `--json`; at `build_step` 0 a subcommand whose inputs do not exist yet reports `skipped` with the reason:

    | Subcommand | Runs | CI job |
    | --- | --- | --- |
    | `check` | ruff, format check, pyright, import-linter, rule 13 checks | `check` |
    | `generate [--check]` | Rule 17; `--check` regenerates and fails on any difference | `check` |
    | `dco <range>` | Rule 15 | `dco` |
    | `test [path] [--cov]` | pytest on PostgreSQL as the product roles (rule 7); per-package coverage enforcement (rule 16) | `test` |
    | `hypothesis --profile ci` | DS-16 state machines on two installations | `test` |
    | `parallel --profile ci` | PAR tests | `test` |
    | `dataset small` | Generate twice, compare with each other and the lock; check that the version moved when output changed; write the summary diff to the job summary and an artifact (DS-17 rules 13, 17, 26); replay through the current step's adapter with invariants | `dataset` |
    | `scenarios` | Golden scenarios in both roots, regression and kept proposed scenarios, the workbook export check (DS-16 rule 23) | `scenarios` |
    | `guards` | Lists the author-only and `reserved-review` paths a change touches (DS-16 rules 6, 22, 25, 27; `docs/design/DS-17-step-1-projection.md`) and fails when an agent-co-authored commit changes an author-only path | `guards` |
    | `frontend` | Typecheck, lint, build; `skipped` until `frontend/` exists | `frontend` |
    | `nightly` | The nightly run (rule 18) | — |
    | `ci` | Every CI job's subcommands, in order | — |

**CI**

15. DCO, per ADR-0003 R5:
    - **Range.** The check runs at the pull request (`base..head`) and on pushes to `main` (`before..after`); CI fetches with `fetch-depth: 0`. Merge commits are skipped. A squash or rebase merge made in the GitHub UI carries no sign-off, so the check's fix text tells the author to use a merge commit or include the sign-off line.
    - **The rule.** Every other commit carries `Signed-off-by:` matching its author. An agent appears only as `Co-Authored-By:`, recognized by the agent e-mail patterns in `.github/dco.toml` (e.g. `noreply@anthropic.com`). Bot identities are listed there only with the author's approval.
    - **Agent sign-offs (interim).** Who may type the author's sign-off is governance (ADR-0005 item 9), beside ADR-0003 R5's "only a person can make the DCO certification". By the author's instruction of 2026-11-14 in the design session, agents in his sessions add his sign-off on his behalf; he confirms this when merging. Whether this continues, or agents never pass `-s` and the author signs off with `git rebase --signoff` before pushing, is an open question.
    - **Dependabot.** It stays off until the author approves its bot identity.
16. `ci.yml`:
    - **Triggers and runners.** Runs on `pull_request` and on `push` to `main`, on GitHub-hosted `ubuntu-24.04` runners, with top-level `permissions: contents: read` and actions pinned by commit SHA.
    - **Jobs.** `dco`, `check`, `test`, `dataset`, `scenarios`, `guards` and `frontend` run in parallel, each with `timeout-minutes: 15` (ADR-0003 R6). DS-16 rule 21's part budgets apply in the job that runs each part.
    - **Coverage.** Coverage comes from the `test` job only. 90% branch coverage is enforced per package by `erpme-dev test --cov` from `build_step` 1 on `ledger`, `inventory`, `registry`, `documents` (where posting and numbering live), `tax` and `localization`. This maps ADR-0003 R4's list; R4 itself is the author's.
    - **Labels.** A separate `pull_request_target` workflow, whose only permission is `pull-requests: write`, reads only the changed-file list, never checks out the head, and applies the labels `reserved-review` and `author-review`. `author-review` marks paths of money, stock posting, idempotency, outbox, triggers and RLS (runbook stage 5).
    - **Branch protection.** The author sets branch protection and the required jobs, and the setting "require approval for all external contributors".
17. Generated files:
    - `erpme-dev generate` writes into `backend/generated/`:
      - the JSON Schemas of commands, queries and events, with each field's field class (ADR-0017 rule 10; DS-16 rule 16);
      - `openapi.json`;
      - the MCP tool list;
      - the `SystemAccount`, `TransactionKey` and `MovementType` types (ADR-0010, ADR-0015).
    - It writes the TypeScript types into `frontend/src/generated/`, and the business-event schema and example log into `docs/catalogs/` (DS-17 rule 2).
    - Output is sorted and stable. A merge conflict in it is resolved by rerunning the command.
    - The files are committed, and CI fails on any difference, so every public API change shows in review (ADR-0008).

**Test server and nightly**

18. The test server:
    - **Host.** A Linux host with Docker, configured from `deploy/test-server/`. It holds synthetic data only. It shares no files, database or user with any other project on the machine; on a shared host it uses rootless Docker or a dedicated VM, since Docker access is root. Which machine hosts it is the author's decision (open question).
    - **Nightly run.** A systemd timer at 19:00 UTC (02:00 in Vietnam) pulls `main` and runs `erpme-dev nightly`: the run in [testing-operations.md](../runbook/testing-operations.md#the-nightly-run), including regeneration of the small and medium datasets against their locks (DS-17 rule 17).
    - **Credentials.** The run reports through a fine-grained token limited to this repository's issues, opening or updating `defect` issues titled with the dedupe key (ADR-0003 R7). The test-scenario model's key stays on the server. No GitHub event can start code there.
    - **Reports.** `erpme-dev nightly` writes the full report to a dated directory in the server's report storage (`/srv/erpme-test/reports/<date>/`, configured in `deploy/test-server/`), and posts its summary (run ID, invariants, reference differences, coverage, timings, spend, new defects) as a comment on one pinned `nightly` issue through the same token.
    - **Cache.** Dataset runs are cached by triple and never edited in place.
19. Dependencies and releases:
    - **Vulnerability audit.** The nightly run audits `uv.lock` and the npm lock.
    - **New runtime dependencies.** A pull request that adds one says why the ADR-0002 tools do not cover it.
    - **Versions.** The core version is semver, 0.x before go-live.
    - **Tag formats.** `core/v<semver>` and `catalog/<name>/v<semver>` (e.g. `catalog/edge-cases/v1.0.0` at the step 0 gate). ADR-0010 rule 16 compares the system accounts catalog with its latest tag. Releases and LTS are DS-37.

**Commits, branches and pull requests**

20. Branch names follow the runbook ([README.md](../runbook/README.md)):
    - `ds-xx-short-title`;
    - `step-n-short-title`;
    - `fix-short-title`;
    - `docs-short-title`.
21. Commit messages:
    - an imperative subject of 72 characters or less;
    - a body citing reference IDs (AGENTS.md);
    - the sign-off of rule 15;
    - `Co-Authored-By:` for the agent.

    No force-push to `main`; only the author merges.
22. The pull request template is the runbook's five-line description (IDs, what changed, documents updated, reference results, open questions), plus the `erpme-dev ci --json` summary.

**Agent instructions**

23. Agent instructions:
    - **Root.** `AGENTS.md` at the root is the one instruction file; `CLAUDE.md` holds `@AGENTS.md`.
    - **Per directory.** `AGENTS.md` files in `backend/`, each module, `tools/`, `l10n/` and `frontend/` hold at most 40 lines of local rules. Each sits next to a one-line `CLAUDE.md` importing it, because Claude Code loads nested `CLAUDE.md` files but not nested `AGENTS.md`.
    - **Skills.** Recurring tasks have skills in `.claude/skills/`: `new-command`, `new-migration`, `new-invariant`, `new-edge-case`, `new-adr`, `posting-change-review`, and DS-38's localization skill later. Each points at the governing ADR and ends with the `erpme-dev` command that proves the task done. Reviewers on other providers read the same files as Markdown.
    - **ADR template.** [docs/adr/template.md](template.md) stays the template.

**Frontend**

24. Frontend conventions; DS-30 adds the rest:
    - file names are kebab-case, except where TanStack Router's file conventions fix them;
    - components are exported in PascalCase;
    - generated types are never edited.

**Licences**

25. Licences follow [18-license-governance.md](../spec/18-license-governance.md), which puts "SDK, command schemas, client libraries" under Apache-2.0 for external integrations:
    - `backend/generated/` (command schemas) and `tools/erpme_client` carry Apache-2.0, declared per path in `pyproject.toml` and a `LICENSE` file;
    - the licence of `erpme.sdk`, which re-exports interfaces of AGPL modules for in-process packages, is the author's (open question); interim AGPL-3.0;
    - the rest is AGPL-3.0; the dataset is CC0.

## Context

DS-18 is the last step 0 design item. The repo skeleton, CI and the test server are built from it (step 0 work packages 5–6). It owns the constraints earlier items left to it:

- ADR-0003: R4–R7.
- ADR-0004: modules, schemas, naming checks.
- ADR-0006: versions, `types`, float and rounding checks.
- ADR-0007: ruff rules, `tzdata`, `btree_gist`, UTC, `environment`, banned database functions.
- ADR-0008: timeouts, rate limits, CI checks for rules 4, 9 and 10, generation.
- ADR-0010: the catalog loader, generated type and tags.
- ADR-0013: workers, `NOTIFY`, backoff, retention, stalled jobs.
- ADR-0014: trigger tests.
- ADR-0016: package location, contracts, package CI, SDK, startup check.
- ADR-0017: roles, FORCE RLS, policies, the claim function, bootstrap.
- ADR-0020: lock order, value role check.
- DS-16 and DS-17: their requirement lists.

Tools are fixed by ADR-0002. The goal set by ADR-0005 is a repository that agents work in easily: one command, machine-readable output, short local instructions, and contracts enforced by tools rather than remembered.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| In-process posting interfaces in `contract.py` (chosen) | One transaction and one plan per `Post<Type>`; no internal command exposed; same as SAP's accounting interface | A second contract form beside commands |
| Nested dispatch of internal commands | One mechanism | Re-checks permissions and idempotency per step; needs plan merging and a hidden exposure class |
| Nightly from a timer on the test server (chosen) | Nothing from GitHub can run code on the server; no runner to secure | Reports need a token on the server |
| Self-hosted GitHub runner | Nightly visible in Actions | On a public user repository, labels do not restrict workflows; a fork could reach the Docker socket |
| One `erpme` distribution with layered modules (chosen) | One install; import-linter sees all | A large package |
| Schema per module | Visible ownership | Harder cross-module keys and RLS; ownership is checked by CI instead |
| CI calls tools directly | Familiar | Local and CI drift |
| GitHub DCO app | No code | A third-party app; it cannot recognize agent co-authors |

## Constraints that come with the decision

- Step 0 work package 5 builds this skeleton. "CI green on the empty skeleton" means every job runs and passes, with `skipped` and a reason where its inputs do not exist yet.
- The author sets branch protection, the external-contributor approval setting, the test server host, the Dependabot identity and the sign-off practice (open questions).
- ADR-0008: note on rule 4 (posting interfaces). ADR-0013: note on its DS-18 line (rule 12).
- DS-30: frontend within rule 24. DS-32: agent budgets. DS-33: query timeouts. DS-37: deployment beyond the test server.

## Revisit when

- The CI critical path exceeds 12 minutes for two weeks (ADR-0003 R6).
- Third-party plugins arrive: consider splitting `sdk` into its own distribution.

## Documents updated

- [docs/adr/0004-naming-conventions.md](0004-naming-conventions.md) rule 7, [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md) rule 4, [docs/adr/0013-outbox-and-events.md](0013-outbox-and-events.md), [docs/adr/0017-permission-envelope.md](0017-permission-envelope.md) rule 18: notes.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md):
  - glossary rows for module (updated), posting interface, composition root, `build_step`, `erpme-dev`, `erpme_check`;
  - `sdk`, `db` and `crm` in the allowed abbreviations.
- [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql): header note on schema placement.
- [AGENTS.md](../../AGENTS.md): current phase and `erpme-dev`.
- [docs/design/backlog.md](../design/backlog.md): DS-18 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): test server host; sign-off practice and bot identities; licence of `erpme.sdk`.
- [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md) rule 27: the dataset has its own CI job.
- [docs/runbook/testing-operations.md](../runbook/testing-operations.md): environments point here.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
