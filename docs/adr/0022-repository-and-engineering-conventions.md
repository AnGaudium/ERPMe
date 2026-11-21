# ADR-0022: Repository and engineering conventions

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-18. Related decisions: D3, D14. Principles 1, 10, 13. Build principles B2, B6, B7, B8. ADR-0001 to ADR-0010, ADR-0013 to ADR-0017, ADR-0020, ADR-0021, DS-14, DS-16, DS-17.

## Decision

NativeFlows is one repository and one uv workspace:
- the product is the distribution `nativeflows`, made of modules in fixed layers;
- test tooling lives in separate distributions that the product never imports;
- localization packages live under `l10n/`.

Modules talk to each other only through their contracts:
- commands and events, as spec 07 requires;
- in-process posting interfaces, which run inside the calling command's transaction and plan. One `Post<Type>` can then write the journal, stock, number and state together, as ADR-0009 and ADR-0020 need.

All tables are in one PostgreSQL schema `nativeflows`, plus `types` for domains and `procrastinate` for the job queue. Each table has one owning module, and lock helpers register in one global lock order.

Note (S2 closure, 2026-11-21): Procrastinate is dropped by the author's decision of 2026-11-19 (OPT-08; [ADR-0031](0031-design-simplifications.md) rule 15 note; [ADR-0002](0002-core-technology-tools.md) note): once confirmed, there is no schema `procrastinate`. A spike at step 0 confirms it; if the spike needs more than one small module, Procrastinate stays and this text stands.

Checks:
- One developer CLI, `nativeflows-dev`, runs every check. CI jobs call only its subcommands, so an agent reproduces any failure with one command.
- CI runs on GitHub-hosted runners, in parallel jobs of 15 minutes or less.
- The nightly run is started by a timer on the test server, not by GitHub, so nothing from the public repository can start code there.
- Generated interfaces are committed and checked.

### Rules

**Layout**

1. Top level:

   | Path | Holds |
   | --- | --- |
   | `pyproject.toml` | uv workspace root, with members as globs (`backend`, `tools/*`, `l10n/*/code`) so a sparse checkout still resolves. Holds shared ruff, pyright, import-linter, pytest and coverage settings, and `[tool.nativeflows] build_step`, raised by the author's commit at each gate (DS-16 rule 5) |
   | `uv.lock` | The one lock file |
   | `backend/` | Distribution `nativeflows`: `src/nativeflows/<module>/`, `migrations/` (Alembic), `provision/` (rule 7), `tests/`, `generated/` (rule 17) |
   | `tools/<package>/` | Distributions `nativeflows_dev`, `nativeflows_events`, `nativeflows_client`, `nativeflows_simulator`, `nativeflows_adapters`, `nativeflows_testkit`, `nativeflows_reference`. Each has its own `pyproject.toml` and `tests/`. `nativeflows_reference` and its tests need only the standard library (DS-16 rule 3) |
   | `l10n/l10n_<country>/` | Localization packages (ADR-0016 rule 1; layout DS-14). Each package's code in `code/` is its own distribution |
   | `frontend/` | The React app (from step 1, DS-30) |
   | `tests/scenarios/` | Regression, package-neutral golden and kept proposed scenarios (DS-16 rule 22). Regime-dependent goldens live in `l10n/<package>/tests/golden/` |
   | `datasets/` | Lock files (DS-17 rule 26) |
   | `docs/` | Specification, ADRs, design, catalogs, runbook |
   | `.github/` | Workflows, pull request template, `dco.toml` (rule 15) |
   | `.claude/skills/` | Coding-agent skills (rule 23) |
   | `deploy/` | Test server files from step 0 (rule 18); the rest is DS-37 |

**Modules, contracts and layers**

2. Modules of `nativeflows` (ADR-0004 rule 7) by layer. A module imports only from lower layers. A module is created by the first work package that needs it (B7). New modules beyond this list are added by ADR. Exception within layer 3: `tax` may import the `ledger` contract to post tax adjustments, and `ledger` never imports `tax`; settlements reach `tax` through the `OpenItemSettled` event ([ADR-0041](0041-tax-engine.md) rule 15). Within layer 2, `work` and `policy` are imported downward: `registry` imports both, `documents`, `outbox`, `permissions`, `attachments` and `agent_runs` import `work`, `policy` imports `work`, and neither imports the others ([ADR-0042](0042-work-queue.md); [ADR-0043](0043-policy-and-approval.md) rule 1).

   | Layer | Modules |
   | --- | --- |
   | 6 · Composition | `app`: registers every module's handlers, consumers and queries; startup checks; entry points (rule 5) |
   | 5 · Interfaces | `api` (REST and MCP generated from the registry), `query` (read-only layer, DS-33), `agents` (after step 4), `sdk` (rule 4), `imports` (staged data imports, [ADR-0030](0030-commercial-seams-and-imports.md) rule 9) |
   | 4 · Commercial | `sales`, `purchasing`, `cash` (from steps 5–6), `reporting` (from step 5, interim until the author decides the build order, [ADR-0049](0049-statutory-reporting-and-printing.md) rule 30), `crm`, `planning` ([ADR-0024](0024-planning.md); it reads `production.contract`'s planning function and structures ([ADR-0036](0036-multi-level-mrp.md) rule 3) and `inventory.contract`'s `demand_supply_line` and hands over through `inventory.contract.request_replenishment`) |
   | 3 · Core business | `ledger` (journal, accounts, account determination, multi-currency), `inventory` (material documents, stock, costing, landed cost, and the warehouse management tables of [ADR-0023](0023-warehouse-management.md)), `master_data` (partners, products, warehouses, units, currencies, working calendars per [ADR-0033](0033-production-master-data.md) rule 11), `tax`; `production` (Phase 1 per [ADR-0032](0032-phase-1-scope-with-production.md); master data per [ADR-0033](0033-production-master-data.md)) and `assets` (Phase 3) per [ADR-0025](0025-later-phase-seams.md) |
   | 2 · Platform | `registry` (command registry, dispatcher, envelope, idempotency; its public entry point `nativeflows.registry.dispatch`), `documents` (lifecycle, versions, numbering), `periods`, `permissions`, `outbox`, `audit`, `localization` (loader), `db` (engine, session settings, RLS context, the generic lock helper and the lock-order registry, the `MetaData` naming convention), `agent_runs`, `work`, `attachments`, `work`, `policy` ([ADR-0027](0027-cross-cutting-ownership.md) rule 1; `documents` and `permissions` may import the `agent_runs` contract; `documents` may import the `attachments` contract, [ADR-0038](0038-audit-and-observability.md) rule 14) |
   | 1 · Foundation | `numeric` (ADR-0006), `clock` (ADR-0007), `ids`, `i18n`, `errors` |

   `agent_runs` (layer 2), `agents` and `query` (layer 5) and their imports: [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 1.

   Hooks: a module may declare a hook that another module of the same or a higher layer registers and `app` (layer 6) wires, so no import goes sideways or up; used for the auto-post evidence and the outbound content check ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 36; [ADR-0051](0051-agent-workflows.md) rule 18). Also `master_data`'s partner e-mail domain hook, which `crm` registers ([ADR-0052](0052-minimal-crm.md) rule 5).

   Note: `reporting` imports only contracts of layers 1 to 3 and no other layer-4 module; names of records that other layer-4 modules own reach its prints through the hook `print_relation_resolver`. Agents reach its queries through `query` ([ADR-0049](0049-statutory-reporting-and-printing.md) rules 1, 25).

   Note: access and approval decisions use functions that `master_data`, `documents`, `permissions`, `periods` and `policy` register with the dispatcher, wired by `app`; work item visibility is a registered function too. No new import between layer-2 modules is needed ([ADR-0054](0054-users-roles-and-authorizations.md) rule 2; [ADR-0055](0055-approval-pools-and-stages.md) rule 1).

   Note: layer 2 lists `work` twice; it is one module.

   Note ([ADR-0057](0057-document-intake-and-extraction.md), 2026-11-15): `attachments` declares the hook `document_reader`; modules and packages register pure readers on it and `app` wires them, so `attachments` imports no module and no package. No new module: the extraction tables belong to `attachments`, mapping rules to `master_data`, the data-processing permission's table to `agent_runs` and its commands to `agents` ([ADR-0057](0057-document-intake-and-extraction.md) rule 1).

   Note ([ADR-0058](0058-configurable-workflows.md), 2026-11-15): new modules `configuration` (layer 2: the configuration and artifact tables, the pure evaluators, validators and graph check, `get_parameters`; it imports the `registry` contract and `work`) and `automation` (layer 5: the automation consumer, replay, evidence, the monitor and the upgrade check; it imports `registry`, the `configuration`, `work` and `permissions` contracts and the contracts of the layer 3–4 modules whose tunable functions it evaluates, and none of its layer-5 peers). `configuration` declares the hook `artifact_checks`, which `automation` registers and `app` wires, for the checks that read layer 3–5 data (rule 1; [ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md) rule 2).

   Note ([ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), 2026-11-15): a module that owns a tunable function or an artifact kind registers, with its declaration, the pure functions `backtest`, `compare` and `monitor` in its contract; `automation` calls them. `policy`'s auto-post evidence hook gains `auto_post_eligibility`, which `cash` registers, so the policy floor for cascade drafts needs no import of `cash`. `configuration` declares the hook `artifact_in_force_changed`, which `policy` registers (calling its contract function `mark_auto_post_evidence_outdated`) and `app` wires (rule 2).

   Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), 2026-11-15): `query` also owns the analysis layer: the catalog of facts, measures and dimensions, the plan validator, compiler and executor, and the tables `analysis_question`, `saved_analysis`, `saved_analysis_version` and `analysis_example`. Besides `db`, `registry` and `agent_runs` it now imports the `work` contract, downward, to raise `analysis_answer_disputed` and `analysis_catalog_request`. `agents` adds the `analysis` workflow, which reaches `query` only through the dispatcher. No external semantic engine runs in the core (rule 1).

   Note ([ADR-0066](0066-work-cases.md), 2026-11-21): `work` also owns `work_case` and `work_case_link` and imports nothing new. `ListWorkCaseTimeline` is a query of `query` over views in schema `query`, and the consumer `work_case_opener` belongs to `automation`, which already imports the `configuration` and `work` contracts ([ADR-0066](0066-work-cases.md) rules 2, 6, 17).

   Note ([ADR-0066](0066-work-cases.md), 2026-11-21): the system resolver of rule 15 lives in `automation` (layer 5), beside `work_case_opener`, not in `work`: `work` is layer 2 and may not read document states. The resolver reads the linked targets' states through their modules' contracts and runs the command `ResolveWorkCase` as `system`. Beyond `configuration` and `work`, the resolver imports the contract of `documents` (layer 2), which owns both `document.state` and the `change_proposal` document type (ADR-0009 rule 4; ADR-0029) ([ADR-0066](0066-work-cases.md) rules 13, 15).

   Note ([ADR-0069](0069-business-unit-dimension.md), 2026-11-21): `ledger` declares the hook `business_unit_defaults`; `master_data` registers it, so `ledger` reads the business unit defaults of master records without an import inside layer 3.

   Note (S1 review, 2026-11-21): same-layer modules may not import each other (rule 2), so the derivation of the business unit runs through the hook `business_unit_defaults`; the hook is required, not optional.

   Note ([ADR-0070](0070-quality-management-core.md), 2026-11-21): new module `quality` (layer 4: inspection plans, lots, results, usage decisions and nonconformances). It imports the contracts of `inventory`, `production`, `master_data`, `documents`, `work`, `attachments` and `policy`, and no layer-4 peer. `inventory`, `purchasing`, `production`, `sales` and `crm` never import it, and an import-linter contract checks this. It changes stock and production data only through commands its consumers dispatch. It is not part of the CRM-only profile.

   Note (S2 findings closure, 2026-11-21; finding 12, D14): within layer 3 a module may import another layer-3 module's `contract` and call its interfaces, such as posting interfaces and pure functions, in one direction only: the caller imports the module that owns the interface, and the owner never imports the caller back. The `tax` to `ledger` sentence above is one case of this rule, and rule 6's "except their `contract`" already allows it. Examples: `inventory` and `production` call `ledger.contract.write_journal_entry` (rule 4); `production` calls `master_data.contract.evaluate_condition` ([ADR-0046](0046-product-configuration.md) rule 1). Import-linter's layer contract lists each allowed pair and fails on a cycle. `ledger` imports no other layer-3 contract: it reads master data defaults through the hook of the ADR-0069 note above. Layer 4 importing a layer-3 contract is downward and needs no exception.

   Note (S2 findings closure, 2026-11-21; author's decision of 2026-11-17, [ADR-0052](0052-minimal-crm.md)): CRM-only is a deployment profile, not an edition: one product and one codebase, with the activated module set kernel, `master_data` partners and contacts, `crm`, `agents` and `query`, intake, analysis and automation. `crm` never depends on `ledger`, `tax`, `inventory`, `cash` or `production`. An import-linter contract enforces it:
   - **Name:** `crm_independent_of_accounting`.
   - **Type and source:** `forbidden`, source module `nativeflows.crm`; indirect imports count.
   - **Forbidden modules:** `nativeflows.ledger`, `nativeflows.tax`, `nativeflows.inventory`, `nativeflows.cash`, `nativeflows.production`.

   Commercial screens and the partner timeline degrade when the accounting modules are not activated: they show no accounting entries and offer no accounting actions. The database side (partner account links that may be empty, and a record of which modules are activated) is done in the DDL by another work item.

   Note (S2 findings closure, 2026-11-21): `registry` owns `module_activation` ([DS-28-settings.sql](../design/DS-28-settings.sql)), one row per company and module, which records the modules a company runs, such as the CRM-only deployment profile. `crm` imports nothing from `ledger`, `tax`, `inventory`, `cash` or `production`, and an import-linter contract checks it ([ADR-0052](0052-minimal-crm.md) rule 1 note).

3. Shape of each module:
   - A module that owns tables or commands has:
     - `contract.py`, the only part other modules import (rule 4);
     - `handlers/`;
     - `tables.py`, private;
     - `services/`, private;
     - `AGENTS.md`, at most 40 lines;
     - tests in `backend/tests/<module>/`.
   - Foundation modules and `db` publish through their `__init__`.

   Note ([ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): a module that owns commands or queries also has `declarations/`, one file per command or query (ADR-0008 rule 1 note). `contract.py` re-exports the payload and result models that other modules use. `handlers/<name>.py` is the thin handler that `nativeflows-dev scaffold` writes once. The logic is in `services/<name>.py`, which together with new tests is all that a coder work package writes (ADR-0073 rules 2, 6).

   Note (S2 findings closure, 2026-11-21; finding 13, D15): a module that owns consumers, queries or auto-post checkers also has:
   - `consumers/`: registered outbox consumers ([ADR-0013](0013-outbox-and-events.md) rule 6);
   - `queries/`: registered read-only query handlers ([ADR-0008](0008-command-envelope-and-registry.md) rule 1);
   - `checkers/`: registered auto-post checkers, one per document type the module owns ([ADR-0065](0065-deterministic-auto-post-gateway.md) rule 2, accepted 2026-11-21).

   `app` imports them as it imports `handlers/` (rule 5).
4. A module's `contract.py` holds three things:
   - its command, query and event schemas;
   - its **posting interfaces**: plain functions that take the caller's `context`, such as `ledger.contract.write_journal_entry`, `inventory.contract.move_stock`, `documents.contract.assign_number` and `periods.contract.check_posting`;
   - the interfaces that localization packages implement for it, such as `ledger.contract.ExchangeRateFetcher`.

   Posting interfaces run in the calling command's transaction and become part of its plan. They have no permission, idempotency or policy step of their own: the outer command is the one the actor called and was authorized for. They read and write only through `context` (ADR-0008 rule 4). They are never exposed on REST or MCP.

   This is how "modules call each other only through commands and events" (spec 07) is read for synchronous posting. The accounting interface in SAP works the same way. Asynchronous work still goes through events and consumers (ADR-0013). `sdk` re-exports the package-facing interfaces from the owning contracts and defines none itself.
5. The composition root `nativeflows.app`:
   - imports every module's `handlers/` to register them. Import-linter exempts it from the layer contract, and nothing imports it;
   - is loaded by `nativeflows.registry.dispatch` on first use through a declared entry point (`importlib.metadata` group `nativeflows.app`), never by a static import, so the in-process transport of `nativeflows_client` sees a full registry and the layer contract holds; `dispatch` is the registry module's named exception to rule 3;
   - runs the startup checks: the `environment` setting is present (rule 9); package data and code versions match (ADR-0016 rule 3); the catalog versions are the ones loaded.

   Entry points:

   | Entry point | Runs |
   | --- | --- |
   | `nativeflows serve` | API server |
   | `nativeflows worker --queue <name>` | Delivery workers and Procrastinate job workers (rule 12) |
   | `nativeflows admin migrate` | Rule 8 |
   | `nativeflows admin bootstrap` | ADR-0017 rule 7 |

   Note (S2 closure, 2026-11-21): Procrastinate is dropped by the author's decision of 2026-11-19 (OPT-08; [ADR-0031](0031-design-simplifications.md) rule 15 note; [ADR-0002](0002-core-technology-tools.md) note): once confirmed, `nativeflows worker` runs only outbox workers, the `jobs` and `pdf` queues included (rule 12). A spike at step 0 confirms it; if the spike needs more than one small module, Procrastinate stays and this text stands.

6. Import-linter contracts:
   - The layers of rule 2.
   - Independence between modules of layers 3 and 4, except their `contract`.
   - `nativeflows` imports no tool package and no `l10n_*`.
   - `l10n_*` imports only `nativeflows.sdk` (ADR-0016 rule 17).
   - Handlers import no network, file, LLM or job library. This is a `forbidden` contract, so it catches transitive imports (ADR-0008 rule 4).
   - The tool packages follow DS-16 section 1 exactly:

     | Package | May import |
     | --- | --- |
     | `nativeflows_events` | standard library, pydantic |
     | `nativeflows_client` | `nativeflows.registry.dispatch`, `nativeflows.numeric`, HTTP and MCP client libraries |
     | `nativeflows_adapters` | `nativeflows_events`, `nativeflows_client` |
     | `nativeflows_simulator` | `nativeflows_events` |
     | `nativeflows_testkit` | `nativeflows_events`, `nativeflows_adapters`, `nativeflows_client`, `nativeflows.numeric` |
     | `nativeflows_reference` | standard library only |

   A `forbidden` contract lets only `nativeflows.agents.gateway.adapters` import a provider library ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 4).

   Note (S2 findings closure, 2026-11-21): the CRM-only profile adds the contract `crm_independent_of_accounting` (rule 2 note); layer-3 imports of a layer-3 `contract` follow the rule 2 note on same-layer imports.

**Database**

7. Schemas, ownership and roles:
   - **Schemas.** One database. All tables are in schema `nativeflows`, domains are in `types` (ADR-0006), and Procrastinate's tables are in schema `procrastinate`. There is no schema per module: foreign keys cross modules and are declared by table name; one schema keeps RLS generation simple.
   - **Ownership.** Every `nativeflows` table is declared in exactly one module's `tables.py`. A CI check fails on a table owned twice or not at all; it exempts `alembic_version`, partitions and schema `procrastinate`.
   - **Roles.** Roles are cluster-level, so `backend/provision/roles.sql`, run as a superuser before any migration, creates the roles of ADR-0017 rule 18 and `nativeflows_check` (DS-16 rule 2: SELECT only, subject to RLS, never `BYPASSRLS`). The test fixture and the test server use the same file. Migrations only grant.

   Views are in schema `query`, owned by the role `nativeflows_query_owner`, which `provision/roles.sql` creates ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 42–43).

   Note (S2 closure, 2026-11-21): Procrastinate is dropped by the author's decision of 2026-11-19 (OPT-08; [ADR-0031](0031-design-simplifications.md) rule 15 note; [ADR-0002](0002-core-technology-tools.md) note): once confirmed, there is no schema `procrastinate` to hold or exempt. A spike at step 0 confirms it; if the spike needs more than one small module, Procrastinate stays and this text stands.
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
   - The claim function of ADR-0017 is a hand-written `SECURITY DEFINER` function owned by `nativeflows_claim`, with its own test.
   - Before go-live (B8), merged migrations may be squashed only in the author's commit that raises `build_step` at a gate. The test server rebuilds its database from empty every night.
   - Procrastinate's schema SQL is applied by an Alembic migration that pins its version.
   - `nativeflows admin migrate` runs Alembic, then loads the core catalogs, then the localization package data. Deployment and tests use this one command.

   Note (S2 closure, 2026-11-21): Procrastinate is dropped by the author's decision of 2026-11-19 (OPT-08; [ADR-0031](0031-design-simplifications.md) rule 15 note; [ADR-0002](0002-core-technology-tools.md) note): once confirmed, no migration applies Procrastinate's schema SQL. A spike at step 0 confirms it; if the spike needs more than one small module, Procrastinate stays and this text stands.
9. Session and runtime settings:
   - **How settings are applied.** Per role with `ALTER ROLE … SET` in `provision/roles.sql`, and with `SET LOCAL` inside a transaction when a registered job needs longer:
     - every session runs in UTC;
     - `lock_timeout` is 5 s;
     - `transaction_timeout` is 30 s for commands and queries, 4 min for consumer transactions (inside ADR-0013's 5-minute lease), and 15 min for registered long jobs (period-end costing, planning and forecast runs per [ADR-0024](0024-planning.md) rule 17, close tasks, import chunks per [ADR-0030](0030-commercial-seams-and-imports.md) rule 9);
     - `idle_in_transaction_session_timeout` is 60 s;
     - `statement_timeout` is 30 s for `nativeflows_readonly` (DS-33 may lower it).
   - **Timeouts and limits.** Exceeding a timeout returns `concurrent_update` or `timeout` (ADR-0008 rule 11). Request bodies are limited to 10 MiB (`request_too_large`), and batches to 1,000 items (`batch_too_large`); larger imports are staged ([ADR-0030](0030-commercial-seams-and-imports.md) rule 9). A batch that cannot finish within its timeout should be split by the caller. Attachments use their own upload endpoint and limit ([ADR-0038](0038-audit-and-observability.md) rule 13).
   - **Rate limits.** Token buckets per actor (not per actor kind), held in memory per API process (no Redis, ADR-0002), with these defaults:

     | Actor kind | Requests per second | Burst |
     | --- | --- | --- |
     | Human | 20 | 40 |
     | Agent | 5 | 10 |
     | Integration | 50 | 100 |

     `system` actors are exempt. Exceeding the limit returns `rate_limited`.
   - **`environment`.** The installation setting `environment` (`production`, `test`, `simulation`; ADR-0007 rule 15) is required at startup from `NATIVEFLOWS_ENVIRONMENT`. It is stored on first start and can never change away from `production`. In `test` and `simulation`, every external lookup and gateway (tax ID lookup, e-invoice, bank, exchange-rate fetchers, e-mail) is replaced by a recording stub (DS-17 rule 19; DS-24, DS-25).

   `statement_timeout` is 10 s for queries of agent runs on `nativeflows_readonly`; 30 s stays for other callers ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 43).
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
    - `TID251` bans these qualified names: `datetime.datetime.now`, `datetime.datetime.utcnow`, `datetime.date.today`, `time.time` (ADR-0007; `nativeflows.clock` is exempt), and `random` inside `nativeflows`.
    - `ruff format`; pyright strict on every distribution; pytest with pytest-xdist, testcontainers, Hypothesis and pytest-cov (branch).
12. Outbox workers (ADR-0013):
    - `nativeflows worker --queue events|integrations|jobs|pdf`.
    - Workers wake on `NOTIFY nativeflows_outbox`, sent by the emitting transaction, and poll every 5 s as a fallback.
    - Retry delay after attempt n is min(2ⁿ s, 1 h), up to the consumer's `max_attempts`, after which the delivery is held (ADR-0013 rule 8).
    - A daily job creates `outbox_event` partitions 3 months ahead and drops expired ones under ADR-0013 rule 15. The same job creates audit partitions 3 months ahead and drops none ([ADR-0038](0038-audit-and-observability.md) rule 6).
    - Procrastinate's stalled-job retry runs from the `jobs` worker, with a heartbeat of 30 s and stalled after 5 min.
    - Step 1 work package 6 implements this rule.

    Note (S2 findings closure, 2026-11-21; finding 3): the queues are `events|integrations|jobs|pdf|agents`. `agents` runs the `agent_runner` consumer ([ADR-0013](0013-outbox-and-events.md) rule 13 and its rule 6 note; [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 16).

    Note (S2 findings closure, 2026-11-21): the bullet on Procrastinate's stalled-job retry is superseded by the author's decision of 2026-11-19 to drop Procrastinate (OPT-08; [ADR-0031](0031-design-simplifications.md) rule 15 note; [ADR-0002](0002-core-technology-tools.md) note). The `jobs` queue runs on the outbox workers, and a stalled run is retried through the consumer lease and heartbeat of [ADR-0013](0013-outbox-and-events.md) rule 7, once the step 0 spike confirms it. The other mentions of Procrastinate and schema `procrastinate` (the paragraph before rule 1, rules 5, 7 and 8) and [ADR-0013](0013-outbox-and-events.md) rule 13 and [ADR-0006](0006-id-and-numeric-model.md) rule 22 stay as written until that spike.
13. `nativeflows_dev.checks` holds the checks no tool provides, each named after the rule it enforces. Each failure reports `file:line`, the rule ID and a one-line fix:
    - **Floats.** No floating-point types in migrations, and none for amounts, quantities, prices, rates or percentages in `nativeflows` (ADR-0006 rule 12). Other floats, such as timeouts, need a `# float-ok: <reason>` comment.
    - **Rounding and conversion.** Neither happens outside `nativeflows.numeric` (ADR-0006 rules 10, 15).
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

    Note ([ADR-0063](0063-configurable-policy-settings.md), 2026-11-15): transaction-level advisory locks (`pg_advisory_xact_lock`) are allowed on handler and trigger paths, because they end with the transaction; session-level advisory locks stay banned. The first user is the settings trigger, which serializes changes per company and key ([ADR-0063](0063-configurable-policy-settings.md) rule 2).

    Note (coding-rules gate, 2026-11-16; chief architect under ADR-0005, the author asked that the way code is written and checked be fixed before the first line of product code):
    - **Gate 0.** No product code (anything under `nativeflows` beyond the empty module skeleton) is merged until `nativeflows-dev check` exists and passes on that skeleton with every contract of rule 6 and every check of rule 13 implemented, or reporting `skipped` with its reason where its inputs do not exist yet (rule 14). CI runs the same command, and `main` is protected: the CI checks are required and no direct push. Pre-commit hooks are a convenience, not the gate.
    - **Tools stay as decided.** pyright strict (no second type checker), ruff with the rule sets above, import-linter configured in `pyproject.toml`, checks in `nativeflows_dev.checks`.
    - **Size and complexity,** chosen for review by people and small coding models: ruff `C901` with `max-complexity = 10`; the `PL` limits at 6 arguments, 12 branches, 6 returns and 50 statements per function; at most 400 lines per Python file outside `generated/` and migrations (a rule 13 check). Raising a limit for one function needs `# noqa: <code>  # reason`, counted in the check summary.
    - **Suppressions.** No bare `# noqa` or `# type: ignore`: each names its code and a reason after it; `typing.Any` is banned in `nativeflows` by `TID251` except in adapters and `generated/`. A rule 13 check counts suppressions per module, and an increase is shown in the pull request summary.
    - **Lock order is checked at run time,** not by parsing: the lock helper of `db` raises `lock_order_violation` in test and development when a lock is taken out of the registered order (ADR-0027 rule 10). The static check only forbids `FOR UPDATE`, `pg_advisory_xact_lock` and raw lock SQL outside the helper.
    - **Database access through `context` only** is enforced by the `forbidden` import contract of rule 6 (handlers import no database library) and by a rule 13 check that forbids `.execute(` on any object not reached from the handler's `context` argument.
    - **Floats:** the rule 13 check also flags `Decimal(<float>)`, `json.loads` without `parse_float=Decimal`, and `float`, `real` or `double precision` columns in migrations.
    - **Two speeds.** `nativeflows-dev check --fast` (ruff, format, import-linter and the rule 13 checks on changed files) for pre-commit and agents' inner loop; the full `check` (adds pyright and generated-file drift through `generate --check`) on pre-push and CI.
    - **Agents read the rules in one place:** the root `AGENTS.md` points to this note and to `docs/design/architecture-core.md` section A5; every failure prints `file:line`, the rule ID and a one-line fix (rule 13).

    Note ([ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): new checks.
    - **Declaration validator:** ADR-0073 rule 2.
    - **Floats:** extended to `float(` calls and to float literals in arithmetic in sensitive paths.
    - **Raw SQL:** only in migrations, `db` and a module's private `tables.py`, its data-access file.
    - **Helper-owned tables:** a table declared with `written_by=<helper>` is written only from that helper's module.
    - **Scaffold leftovers:** no scaffold marker or `NotImplementedError` in merged code.
    - **Manifests:** the work package manifest check (allowlist shape).
    - **Mutation marks:** `# pragma: no mutate` only with `# equivalent: <reason>`, counted like suppressions.

    Thresholds and lists move into the ratchet file `.github/assurance.toml`, which may be tightened freely and loosened only with an ADR (ADR-0073 rules 12, 14, 16).

    Note ([ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), 2026-11-21): the UI annotation checks join `nativeflows_dev.checks`: required annotations, known keys with renderers, label keys, `scale-from` pairing, at most 8 default list columns and 6 header facets, actions and value help naming registered commands and queries, assist actions only `is_draft_only`, custom component names registered, and a conflict-free shortcut map (ADR-0077 rule 19).

    Note (S2 findings closure, 2026-11-21; finding 14): eight checks have a rule but no check yet. They are built in the coding kit's lint and check deliverable and join this list, each named after its rule:
    - **Client-side money arithmetic:** [ADR-0040](0040-ui-architecture.md) rule 2.
    - **Permission, visibility or policy checks inside handlers:** [ADR-0008](0008-command-envelope-and-registry.md) rule 5.
    - **References by `code` in command payloads:** [ADR-0006](0006-id-and-numeric-model.md) rule 5.
    - **A column named `status`:** [ADR-0004](0004-naming-conventions.md) rule 13.
    - **PostgreSQL `ENUM` types:** [ADR-0004](0004-naming-conventions.md) rule 14.
    - **Country rules in the core:** [ADR-0053](0053-core-neutrality.md) rule 1. Only reviewers apply this test today, so the check is a heuristic: it flags candidates (country words, legal citations, account numbers in core code) for review and does not fail the build on its own.
    - **Imports of lab code:** the lab README says the lab is "never imported by the product".
    - **Writes to change-tracked tables outside the `context` helpers:** the DS-18 guard of [ADR-0038](0038-audit-and-observability.md) rule 3. It is not in the list above, and it is part of the gate's backlog (coding-rules gate note above).

    Note (2026-11-16 additions review, 2026-11-21): the "Database access through `context` only" bullet of the coding-rules gate note now reads: (1) only `db` imports `psycopg`, by a `forbidden` contract on `nativeflows` except `nativeflows.db`; services and `tables.py` may import `sqlalchemy` (ADR-0073 rule 12); (2) `.execute(`, `.executemany(`, `.exec_driver_sql(` and `.scalars(` calls appear only in `db`, migrations and a module's `tables.py`; (3) every public function of `tables.py` takes the connection as its first parameter, typed `db.Connection`, which a service passes from `context.db`. No check follows values through calls.

    Note (2026-11-16 additions review, 2026-11-21): the static lock check scans Python under `nativeflows` outside `nativeflows.db` and forbids the strings `FOR UPDATE`, `FOR NO KEY UPDATE`, `FOR SHARE`, `FOR KEY SHARE`, `LOCK TABLE` and `pg_advisory`, and the call `.with_for_update(`. SQL in migrations (trigger and function bodies) is outside this check; its locks are the ADR-0063 note above and ADR-0027 rule 10's trigger locks, proved by the SQL tests of ADR-0073 rule 11.

    Note (2026-11-16 additions review, 2026-11-21): type suppressions are written `# pyright: ignore[<rule>]  # <reason>`; `# type: ignore` is refused (pyright `enableTypeIgnoreComments = false`), and pyright `reportUnnecessaryTypeIgnoreComment` is an error. The suppression count includes them.

    Note (2026-11-16 additions review, 2026-11-21): the `Any` exemption is the ruff per-file-ignores globs `backend/src/nativeflows/**/adapters/**` and `**/generated/**`.

    Note (2026-11-16 additions review, 2026-11-21): changed files are those differing from `git merge-base HEAD origin/main`, plus untracked files; cross-file rule 13 checks always run whole in `--fast`.

    Note (2026-11-16 additions review, 2026-11-21): `lock_order_violation` and `declaration_violation` are test and development exceptions (subclasses of `AssertionError`), never API error codes; they are not in DS-04's catalog and no declaration lists them.

    Note (2026-11-16 additions review, 2026-11-21): `check` runs `generate --check` as its last step; the rule 14 row of `generate` stays for local use.

**One command for agents and CI**

14. `nativeflows-dev` subcommands. Each prints a JSON summary as its last line with `--json`; at `build_step` 0 a subcommand whose inputs do not exist yet reports `skipped` with the reason:

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
    | `frontend` | Typecheck, lint, build, Vitest, UI hint checks, Vietnamese key check, size budgets ([ADR-0040](0040-ui-architecture.md) rule 18); `skipped` until `frontend/` exists | `frontend` |
    | `nightly` | The nightly run (rule 18) | — |
    | `ci` | Every CI job's subcommands, in order | — |

    Note ([ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): new subcommands.
    - **`scaffold <declaration> [--check]`:** one-time handler, service stub and test skeleton; `--check` verifies the handler is unchanged.
    - **`work-package <id> --start|--context|--allows <path>|--check`:** start a package, print its context pack, answer the hook, guard a pull request.
    - **`mutation [--diff <base>|--package <name>]`:** job `mutation`.
    - **`review --seat a|b`:** jobs `model-review-a` and `model-review-b`, run from the base branch.
    - **`acceptance --step <n>`:** the plain-Vietnamese acceptance report, on the test server.

    `scope-guard` runs `work-package --check` and the ratchet comparison (ADR-0073 rules 2, 6–8, 14–17).

**CI**

15. DCO, per ADR-0003 R5:
    - **Range.** The check runs at the pull request (`base..head`) and on pushes to `main` (`before..after`); CI fetches with `fetch-depth: 0`. Merge commits are skipped. A squash or rebase merge made in the GitHub UI carries no sign-off, so the check's fix text tells the author to use a merge commit or include the sign-off line.
    - **The rule.** Every other commit carries `Signed-off-by:` matching its author. An agent appears only as `Co-Authored-By:`, recognized by the agent e-mail patterns in `.github/dco.toml` (e.g. `noreply@anthropic.com`). Bot identities are listed there only with the author's approval.
    - **Agent sign-offs (interim).** Who may type the author's sign-off is governance (ADR-0005 item 9), beside ADR-0003 R5's "only a person can make the DCO certification". By the author's instruction of 2026-11-14 in the design session, agents in his sessions add his sign-off on his behalf; he confirms this when merging. Whether this continues, or agents never pass `-s` and the author signs off with `git rebase --signoff` before pushing, is an open question.
    - **Dependabot.** It stays off until the author approves its bot identity.

    Note (author's delegation, 2026-11-19): the current practice is kept: agents add the author's `Signed-off-by` under his standing instruction of 2026-11-14, and he confirms it by approving each merge. No commit is made without a sign-off; Dependabot stays off. Revisit when a co-maintainer joins (ADR-0003 R3, R5).
16. `ci.yml`:
    - **Triggers and runners.** Runs on `pull_request` and on `push` to `main`, on GitHub-hosted `ubuntu-24.04` runners, with top-level `permissions: contents: read` and actions pinned by commit SHA.
    - **Jobs.** `dco`, `check`, `test`, `dataset`, `scenarios`, `guards` and `frontend` run in parallel, each with `timeout-minutes: 15` (ADR-0003 R6). DS-16 rule 21's part budgets apply in the job that runs each part.
    - **Coverage.** Coverage comes from the `test` job only. 90% branch coverage is enforced per package by `nativeflows-dev test --cov` from `build_step` 1 on `ledger`, `inventory`, `registry`, `documents` (where posting and numbering live), `tax` and `localization`. This maps ADR-0003 R4's list; R4 itself is the author's.
    - **Labels.** A separate `pull_request_target` workflow, whose only permission is `pull-requests: write`, reads only the changed-file list, never checks out the head, and applies the labels `reserved-review` and `author-review`. `author-review` marks paths of money, stock posting, idempotency, outbox, triggers and RLS (runbook stage 5).
    - **Branch protection.** The author sets branch protection and the required jobs, and the setting "require approval for all external contributors".

    Note ([ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): by the author's decision of 2026-11-18, `author-review` no longer means that the author reviews code. It marks a sensitive path, on which `mutation` and `model-review-b` apply and the reviewers use the area's checklist.
    - **New jobs.** `mutation` in `ci.yml`. `scope-guard`, `model-review-a` and `model-review-b` in a base-side `pull_request_target` workflow that never checks out or runs head code.
    - **Required checks.** `dco`, `check`, `test`, `dataset`, `scenarios`, `guards`, `frontend`, `mutation`, `scope-guard`, `model-review-a` and `model-review-b`. Each always runs and reports `skipped: <reason>` when it does not apply.
    - **Branch protection.** A pull request is required and must be up to date. Protection is enforced for administrators, with no bypass actors and no override.
    - **Coverage** is unchanged (ADR-0073 rules 14–20).
17. Generated files:
    - `nativeflows-dev generate` writes into `backend/generated/`:
      - the JSON Schemas of commands, queries and events, with each field's field class (ADR-0017 rule 10; DS-16 rule 16);
      - `openapi.json`;
      - the MCP tool list;
      - the `SystemAccount`, `TransactionKey` and `MovementType` types (ADR-0010, ADR-0015).
    - It writes the TypeScript types, the annotated JSON Schemas (`x-nativeflows-*`, [ADR-0040](0040-ui-architecture.md) rule 4) and the i18n catalogs into `frontend/src/generated/`, and the business-event schema and example log into `docs/catalogs/` (DS-17 rule 2).
    - Output is sorted and stable. A merge conflict in it is resolved by rerunning the command.
    - The files are committed, and CI fails on any difference, so every public API change shows in review (ADR-0008).

    Note ([ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): `generate` derives the registry outputs from the declarations of ADR-0008 rule 1's note, for declarations that have a handler. It also writes, from the catalogs, the `Literal` types that declarations use: authorization leaves, error and check codes, event types, lock names, and tables with their states. `nativeflows-dev scaffold <declaration>` is separate and runs once. It writes the handler, the service stub and the test skeleton, refuses to overwrite, and is never rerun (ADR-0073 rule 2).

    Note ([ADR-0074](0074-core-data-structure-additions.md), 2026-11-21): the schema of a command or query that names a table with `custom_values` carries it as an object annotated `x-nativeflows-custom-values`; the company's own keys are read at run time, so no generated file depends on a company (ADR-0074 rule 11).

    Note ([ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), 2026-11-21): `generate` emits the closed vocabulary of ADR-0077 (24 `x-nativeflows-*` keys) from the declarations, and the renderer's key map is compared with it by `check` (ADR-0077 rules 8, 19).

**Test server and nightly**

18. The test server:
    - **Host.** A Linux host with Docker, configured from `deploy/test-server/`. It holds synthetic data only. It shares no files, database or user with any other project on the machine; on a shared host it uses rootless Docker or a dedicated VM, since Docker access is root. Which machine hosts it is the author's decision (open question).
    - **Nightly run.** A systemd timer at 19:00 UTC (02:00 in Vietnam) pulls `main` and runs `nativeflows-dev nightly`: the run in [testing-operations.md](../runbook/testing-operations.md#the-nightly-run), including regeneration of the small and medium datasets against their locks (DS-17 rule 17).
    - **Credentials.** The run reports through a fine-grained token limited to this repository's issues, opening or updating `defect` issues titled with the dedupe key (ADR-0003 R7). The test-scenario model's key stays on the server. No GitHub event can start code there.
    - **Reports.** `nativeflows-dev nightly` writes the full report to a dated directory in the server's report storage (`/srv/nativeflows-test/reports/<date>/`, configured in `deploy/test-server/`), and posts its summary (run ID, invariants, reference differences, coverage, timings, spend, new defects) as a comment on one pinned `nightly` issue through the same token.
    - **Cache.** Dataset runs are cached by triple and never edited in place.

    Note (author's delegation, 2026-11-19): the test server is a dedicated Linux user on GB10 with rootless Docker, isolated from other projects and from the author's account, the pattern of [ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md)'s coder user. Its setup needs the author's `sudo`; the commands are prepared for him. Revisit when the replays need more than GB10 gives.
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
22. The pull request template is the runbook's five-line description (IDs, what changed, documents updated, reference results, open questions), plus the `nativeflows-dev ci --json` summary.

**Agent instructions**

23. Agent instructions:
    - **Root.** `AGENTS.md` at the root is the one instruction file; `CLAUDE.md` holds `@AGENTS.md`.
    - **Per directory.** `AGENTS.md` files in `backend/`, each module, `tools/`, `l10n/` and `frontend/` hold at most 40 lines of local rules. Each sits next to a one-line `CLAUDE.md` importing it, because Claude Code loads nested `CLAUDE.md` files but not nested `AGENTS.md`.
    - **Skills.** Recurring tasks have skills in `.claude/skills/`: `new-command`, `new-migration`, `new-invariant`, `new-edge-case`, `new-adr`, `posting-change-review`, and DS-38's localization skill later. Each points at the governing ADR and ends with the `nativeflows-dev` command that proves the task done. Reviewers on other providers read the same files as Markdown.
    - **ADR template.** [docs/adr/template.md](template.md) stays the template.

**Frontend**

24. Frontend conventions; DS-30 adds the rest:
    - file names are kebab-case, except where TanStack Router's file conventions fix them;
    - components are exported in PascalCase;
    - generated types are never edited;
    - layout of `frontend/src/` and tests: [ADR-0040](0040-ui-architecture.md) rule 18.

**Licences**

25. Licences follow [18-license-governance.md](../spec/18-license-governance.md), which puts "SDK, command schemas, client libraries" under Apache-2.0 for external integrations:
    - `backend/generated/` (command schemas) and `tools/nativeflows_client` carry Apache-2.0, declared per path in `pyproject.toml` and a `LICENSE` file;
    - the licence of `nativeflows.sdk`, which re-exports interfaces of AGPL modules for in-process packages, is the author's (open question); interim AGPL-3.0;
    - the rest is AGPL-3.0; the dataset is CC0.

    Note (author's delegation, 2026-11-19): confirmed: `nativeflows.sdk` is AGPL-3.0, because it runs in the same process; the command schemas and `nativeflows_client` are Apache-2.0. Spec 18 now reads "client library and command schemas" instead of "SDK".

## Context

DS-18 is the last step 0 design item. The repo skeleton, CI and the test server are built from it (step 0 work packages 5–6). It owns the constraints earlier items left to it:

- ADR-0003: R4–R7.
- ADR-0004: modules, schemas, naming checks.
- ADR-0006: versions, `types`, float and rounding checks.
- ADR-0007: ruff rules, `tzdata`, `btree_gist`, UTC, `environment`, banned database functions.
- ADR-0008: timeouts, rate limits, CI checks for rules 4, 9 and 10, generation.
- ADR-0038: CI guard that only the `context` write helpers write `is_change_tracked` tables (rule 3).
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
| One `nativeflows` distribution with layered modules (chosen) | One install; import-linter sees all | A large package |
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
  - glossary rows for module (updated), posting interface, composition root, `build_step`, `nativeflows-dev`, `nativeflows_check`;
  - `sdk`, `db` and `crm` in the allowed abbreviations.
- [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql): header note on schema placement.
- [AGENTS.md](../../AGENTS.md): current phase and `nativeflows-dev`.
- [docs/design/backlog.md](../design/backlog.md): DS-18 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): test server host; sign-off practice and bot identities; licence of `nativeflows.sdk`.
- [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md) rule 27: the dataset has its own CI job.
- [docs/runbook/testing-operations.md](../runbook/testing-operations.md): environments point here.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
