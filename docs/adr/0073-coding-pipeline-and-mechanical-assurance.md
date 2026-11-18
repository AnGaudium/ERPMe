# ADR-0073: Coding pipeline and mechanical assurance

Status: proposed (2026-11-18) under ADR-0005 (builder Claude Opus 5.5).
Design items: DS-18 (repository and engineering conventions), DS-04 (command registry), DS-16 (harness). Related decisions: D2, D3, D14, D15. Build principles B2, B4, B7. ADR-0002, ADR-0003, ADR-0004, ADR-0005, ADR-0008, ADR-0022, ADR-0027, ADR-0059, ADR-0063.

## Decision

These are the author's decisions of 2026-11-18. Governance is his under ADR-0005 item 9, and this ADR records what he decided. It fixes how product code is specified, written and checked from step 0 work package 5 on.

The author does not read code. Line-by-line review by a person is therefore replaced by mechanical assurance, which works in this order:

1. what the database enforces;
2. what static checks refuse;
3. tests the coding model cannot change;
4. mutation testing;
5. two independent model reviews;
6. branch protection with no override.

The author reviews behavior at each gate instead.

The pipeline:

- Specs are typed Python declarations, one per command or query.
- Claude Sonnet 5.5 drafts the declarations, and Claude Opus 5.5 or Claude Fable 5.2 reviews them.
- Claude Haiku 5.5 writes the service bodies and new tests of one work package at a time, confined to an allowlist of files.
- Stop rule 11 holds, and a package is never rescued by a stronger model after a failure.

| Topic | Before | Now |
| --- | --- | --- |
| Spec of a command | Registry fields in the code (ADR-0008 rule 1) | One Python declaration module, checked by pyright and `nativeflows-dev check` (rules 1–3) |
| Who codes | A builder agent (runbook); a local model was planned | Claude Haiku 5.5 for command and query packages; Claude Opus 5.5 for platform code and first-of-kind packages, assigned up front (rule 4) |
| What the coder may change | Module boundaries (ADR-0022) | An allowlist per work package, enforced by a hook and by a CI guard read from the base branch (rules 6–9) |
| Sensitive changes | Reviewed by the author line by line (ADR-0005; runbook stage 5) | Mutation testing plus two model reviews as required check runs; the author reviews behavior (rules 14–17) |
| Merge | The author merges when CI is green | The same, and branch protection makes every required check binding, with no override (rule 16) |
| Gate evidence | Runbook verification lines | Those, plus a mechanical summary and a plain-Vietnamese acceptance report with a demo (rules 17, 21) |

### Rules

**Specs as Python declarations**

1. Declarations:
   - **One module per command or query.** `backend/src/nativeflows/<module>/declarations/<snake_case type>.py` holds the payload model, the result model and one `CommandDeclaration` or `QueryDeclaration` named `DECLARATION`. `contract.py` re-exports the models that other modules use, so ADR-0022 rule 4 is unchanged.
   - **Fields.** A declaration carries exactly the registry fields of ADR-0008 rule 1 and its notes:
     - type, schema version and scope;
     - subject table and allowed states;
     - permission leaf (and a minimum level above the verb's);
     - effect class and the registry flags of rule 1's notes (`human_only`, `is_proposal_bound`, `is_policy_in_handler`, `is_internal_only`, `is_draft_only` and the others);
     - error codes, and check codes with `is_hashed`;
     - the posting interfaces it calls, as the contract functions themselves;
     - the events it emits, with discriminator values;
     - the locks it takes, by registered name (ADR-0027 rule 10).

     A query declares rule 1's query fields.
   - **Typed.** Catalog values are `Literal` types that `generate` writes from the catalogs (rule 2): authorization leaves, error and check codes, event types, lock names, and tables with their states. So pyright strict refuses an unknown value while the declaration is being written. A renamed posting interface fails type checking.
   - **One place.** No registry field is declared anywhere else: no decorator, no YAML, nothing in handler code.
   - **Pending.** A declaration without a handler is pending. It is not dispatched (`unknown_command_type`) and not generated into a transport. `check` lists pending declarations.
   - **No YAML layer.** A YAML-to-code generator would be a second source of truth, and a framework built before it is needed (B7).
2. Generation, scaffolding and validation:
   - **`nativeflows-dev generate`** stays as ADR-0022 rule 17 defines it. It derives from declarations that have a handler. It also writes the `Literal` catalog types that declarations import.
   - **`nativeflows-dev scaffold <module>.<snake_case type>`** runs once per declaration and writes three files:
     - `handlers/<name>.py`, a complete thin handler that calls `services/<name>.py` and returns its result;
     - `services/<name>.py`, a typed stub;
     - `backend/tests/<module>/test_<name>.py`, one test function per declared error code plus one for success, each failing with the marker `to be written: <work package id>`.

     It refuses to overwrite an existing file and is never rerun. `scaffold --check` verifies that the handler is byte-equal to fresh scaffold output.
   - **Validator in `nativeflows-dev check`.** Each declaration is checked against:
     - ADR-0004 naming: verb list, glossary noun, case;
     - the catalogs: error codes against DS-04's catalog, check codes and event types against their catalogs;
     - the authorization areas: the leaf exists, and its area belongs to the module or is shared;
     - its subject table: owned by the module, with states taken from that table's states;
     - posting interfaces that exist in the named contracts;
     - lock names in the lock-order registry;
     - ADR-0027 rule 17 (`Post` and `Reverse` commands are `posting`);
     - the flag combinations that rule 1's notes forbid.

     Each failure prints `file:line`, the rule ID and a one-line fix (ADR-0022 rule 13).
3. Run-time conformance. In test and development, `context` records every posting interface call, lock, event, error code and check code of a run. It raises `declaration_violation` when the handler does something its declaration does not list, the same way the lock helper raises `lock_order_violation` (ADR-0022 rule 13 note). Production does not record.

**Seats**

4. The development seats. Spec 17's Builder seat is the product's runtime customization seat (templates, rules, plugins, websites), not the development coder. These are the development seats:

   | Seat | Model | Writes | Never |
   | --- | --- | --- | --- |
   | Declaration drafter | Claude Sonnet 5.5 | Declarations chunk by chunk (the commands and queries of one DS item or one part of a step), with their work package manifests (rule 6) | Services, golden values |
   | Declaration reviewer | Claude Opus 5.5 or Claude Fable 5.2 | Review under ADR-0005's acceptance rule | Its own drafts |
   | Coder | Claude Haiku 5.5 (replaces the earlier plan for a local Gemma model) | The `services/` body and the new tests of one work package | Any file outside its allowlist (rule 9) |
   | Platform coder | Claude Opus 5.5, assigned up front | Code that is not one command or query: registry and dispatcher, `numeric`, `clock`, `db` and its lock helpers, migrations with triggers and RLS, `outbox`, `nativeflows_dev`, harness, simulator; the first package of each kind (rule 6) | Golden values |
   | Reference-results writer | Claude Sonnet 5.5 or Claude Opus 5.5, never the package's coder | Invariant code, property tests, SQL tests of triggers and policies, adapters (stage 2, B4) | Golden values |
   | Model reviewers | `model-review-a`: Claude Fable 5.2; `model-review-b`: Claude Opus 5.5 (rule 15) | Verdicts as check runs | Fixes |

   The recomputation writer and the test-scenario model are unchanged (runbook).
5. Measurement. The first 3 to 5 packages that the coder seat writes run one at a time, and at least one of them posts money. For each package the step log's Friday line and the step 1 gate report record:
   - **review rounds:** declaration review rounds, and model review runs until both pass;
   - **stops:** stop rule 11 stops;
   - **escaped defects:** `defect` issues traced to the package and found after its merge, by the nightly run, a later package or a gate;
   - **cost per merged change:** API cost of every seat (the package's share of its declaration chunk, coding, reviews and reruns), divided by merged pull requests;
   - **time and mutation:** wall time and the mutation score.

   The numbers calibrate package size, the context pack, the checklists and the interim thresholds. They do not reselect the coder. Changing the coder is the author's decision, by ADR.

**Work packages and confinement**

6. A work package is one command or query. Its manifest is `docs/runbook/work-packages/wp-<step>-<nnn>.toml`. The declaration drafter writes it with the declaration chunk, and it is reviewed and merged with that chunk, before coding starts.
   - **Fields:**
     - `id`, `step`, `ds_items` and `declaration`;
     - `seat` (Claude Haiku 5.5 unless assigned up front, with `seat_reason`);
     - `adr_rules` (for example `ADR-0008 rule 4`);
     - `contracts`: the posting interfaces and queries it may call, equal to its declaration's;
     - `golden_example`: a merged package of the same kind, meaning the same effect class and verb group;
     - `allowlist`.
   - **Allowlist shape** (validated by `check`): `services/<name>.py` of its declaration, the scaffolded test file, and new files `backend/tests/<module>/test_<name>_*.py`. Nothing else for the coder seat. A platform package lists its own files, still never the read-only classes of rule 9 unless producing that class is the package's purpose (a migration package lists its migration).
   - **First of its kind.** With no golden example yet, the first package of each kind is assigned up front to the platform coder. Once merged, it is the golden example.
   - **Context pack.** `nativeflows-dev work-package <id> --context` assembles one Markdown file:
     - the declaration;
     - the exact text of each listed ADR rule with its notes, cut by rule number;
     - the contracts' signatures and docstrings;
     - the golden example's declaration, service and tests;
     - the allowlist, the module's `AGENTS.md` and the stop rules.

     Nothing else goes in. Above 30,000 tokens (interim), the package is split.
7. Flow:
   1. **Declaration pull request.** A chunk of declarations and manifests. It is accepted under ADR-0005 and merged by the author when green.
   2. **Start.** `nativeflows-dev work-package <id> --start` cuts `step-<n>-<short-title>`, runs `scaffold` and `generate`, and commits the output as `Scaffold <id>`; a tool writes this commit, not a model. It refuses to start while an open package's allowlist overlaps.
   3. **Coding.** The coder session reads only the context pack. It writes inside the allowlist, runs `check --fast` and `test <its tests>`, and commits.
   4. **Code pull request.** Every required check of rule 20 runs.
   5. **Merge.** The author merges once branch protection allows it (rule 16).
8. The allowlist is enforced twice:
   - **Hook (the fence).** The session runs with `NATIVEFLOWS_WORK_PACKAGE=<id>`, and `.claude/settings.json` sets a `PreToolUse` hook on Edit, Write, NotebookEdit and Bash that calls `nativeflows-dev work-package <id> --allows`.
     - **File tools.** An edit outside the allowlist is denied, with the allowlist in the reason.
     - **Bash.** Only these pass: `nativeflows-dev check --fast`, `nativeflows-dev test` on the package's tests, `git status`, `git diff`, and `git add` and `git commit` of allowlisted paths. Every other command is denied.
   - **CI `scope-guard` (the gate).** It runs from a base-side `pull_request_target` workflow and reads the manifest from the base branch, so a pull request cannot widen its own allowlist. Every changed file must be one of:
     - in the allowlist;
     - a scaffold output that passes `scaffold --check`;
     - a generated file (checked by `generate --check` in `check`).

     Every scaffolded test name must remain, and no `to be written` marker may remain. The hook is a convenience; the guard is the gate (ADR-0022 rule 13 note).
9. Read-only to the coding model. This follows from the allowlist shape, and the manifest check refuses these paths for the coder seat:
   - existing tests, meaning every test file outside its allowlist;
   - invariants (`invariants.csv`, `nativeflows_testkit/invariants/`);
   - golden and regression scenarios (`tests/scenarios/`, `l10n/*/tests/golden/`);
   - the naive recomputation (`nativeflows_reference`, stop rule 5);
   - property and SQL tests;
   - generated files;
   - DDL and migrations;
   - catalogs, declarations and manifests;
   - `.github/`, `.claude/`, `pyproject.toml` and `tools/`.

**Stop rule 11**

10. Stops are never rescued:
    - **The stop.** After two red attempts at the same fix (the same failing check, test or review finding), the coder stops. It commits `WIP (blocked):` and reports what failed and what it tried (escalation.md).
    - **No rescue.** A stopped package is never handed to a stronger model. The declaration drafter re-specifies it (declaration, context pack, or a split into smaller packages) for the same seat, or asks the author when the cause is on ADR-0005's reserved list.
    - **Seat fixed up front.** A stronger model is assigned only up front, in the manifest's `seat` and `seat_reason`. A package's seat never changes after its first coding attempt.
    - **Review findings.** Two failed review rounds on the same finding count as two red attempts.

**Mechanical assurance, strongest first**

11. **(a) Database enforcement**, already designed and kept: posted-row triggers (ADR-0009 rule 14), RLS (ADR-0017 rule 19), CHECK and balance constraints (DS-06), and the lock helpers (ADR-0008 rule 10; ADR-0027 rule 10). SQL tests on real PostgreSQL 18, run as the product roles (ADR-0022 rule 7), prove each one with a refused write and an allowed write. This is the strongest layer because it holds whatever the Python does.
12. **(b) Static checks.** These are kept as decided: ruff, pyright strict, import-linter, the complexity and size limits, the `Any` ban, and ADR-0022 rule 13's checks. Added:
    - **Float for money.** The rule 13 Floats check is extended to `float(` calls and to float literals in arithmetic in sensitive paths.
    - **Raw SQL outside the data-access files.** SQL text may appear only in migrations, in `db` and in a module's private `tables.py`. SQL text means `sqlalchemy.text`, `exec_driver_sql`, `psycopg.sql`, or a string literal that starts with a SQL verb. `tables.py` is the module's data-access file, the "repository" in the author's words; ADR-0022 rule 3 has no other data-access layer. Services build statements with SQLAlchemy Core.
    - **Direct writes to helper-owned tables.** A table declared in `tables.py` with `written_by=<helper>` receives INSERT, UPDATE and DELETE only from that helper's module. This covers the serialized tables (ADR-0008 rule 10; ADR-0026 rule 3), `idempotency_record`, `outbox_event`, `event_subject` and the audit tables, and extends the Serialized tables check from references to every write path.
    - **No scaffold leftovers.** No scaffold marker and no `NotImplementedError` may remain in merged code. The declaration validator (rule 2) and the manifest check (rule 6) run here too.
13. **(c) Tests the coder cannot change** (rule 9), written in stage 2 before the code (B4):
    - invariants (DS-16);
    - golden and regression scenarios;
    - the naive recomputation;
    - property-based tests (Hypothesis) for money arithmetic: rounding, conversion, and largest-remainder allocation summing exactly (ADR-0006);
    - property-based tests for posting balance: every journal entry from any posting interface balances per transaction currency and company currency, and a reversal nets to zero; from step 3, stock movements conserve quantity and value per item and valuation area;
    - the SQL tests of rule 11;
    - run-time conformance (rule 3).

    90% branch coverage on the core packages is unchanged (ADR-0003 R4; ADR-0022 rule 16).
14. **(d) Mutation testing** on the sensitive packages:
    - **Which paths.** Money (`numeric`, `ledger`, `tax`, account determination), stock posting and costing (`inventory` and costing services), idempotency (`registry`), posting and numbering (`documents`), `outbox`, and the trigger and policy SQL (migrations, `provision/`). One path list in `.github/assurance.toml` is read by the labeler, the mutation job and the review job.
    - **Python** uses mutmut, pinned in `uv.lock`, which selects tests by coverage. It is a new library in a category ADR-0002 does not cover, and this ADR records it.
    - **SQL** uses `nativeflows_dev.mutation_sql`, which has five fixed operators: negate a comparison; drop one term of an AND or OR in a predicate; delete a RAISE; swap OLD and NEW; replace a policy's USING or WITH CHECK with `true`. Each mutant is applied in a throwaway database and the SQL tests run. Five operators in one file are not a framework (B7).
    - **Score.** (killed + timed out) ÷ (mutants − mutants on lines marked `# pragma: no mutate  # equivalent: <reason>`). Marks are counted like suppressions (ADR-0022 rule 13 note), shown in the pull request summary, and checked by both reviewers.
    - **Thresholds (interim).**
      - On a pull request, the `mutation` job needs a score of at least 90% over mutants on the changed lines of sensitive paths, with marked lines at most 5% of the changed sensitive lines.
      - On the full run after the nightly run, and at each gate, each sensitive package needs at least 85%.
      - A fall of more than 2 points between gates opens a `defect` issue.
    - **Basis.**
      - NativeFlows has no data yet, and the common tools set no binding standard. Stryker's default thresholds call 80% "high" and break on nothing. PIT's default threshold is 0. Google shows surviving mutants in code review instead of gating on a score (Petrović and Ivanković, ICSE-SEIP 2018).
      - The bar sits above 80% for two reasons. The sensitive code is small pure functions backed by property tests, where a high score is reachable. And with no human reading the code, a surviving mutant in posting code may be a wrong booking that no other layer catches.
      - Changed lines get a higher bar than whole packages because a diff has few mutants and new code is tested against its own declaration.
      - Equivalent mutants leave the denominator only when marked, so the score stays honest.
      - The thresholds are recalibrated after the first 3–5 packages and at the step 1 gate (open question).
    - **Time.** The pull request job stays within 15 minutes (ADR-0003 R6). A package whose diff mutation does not fit is split.
15. **(e) Two independent model reviews:**
    - **Check runs.** `model-review-a` uses Claude Fable 5.2 and `model-review-b` uses Claude Opus 5.5. When the pull request's builder is one of them (from the manifest on the base branch, otherwise from the `Co-Authored-By:` trailers), that job takes the next model on the reviewer list in `.github/assurance.toml`: Claude Sonnet 5.5, or a model of another provider once one is configured. The two reviews always use different models from the builder and from each other.
    - **Where.**
      - `model-review-a` runs on every pull request that changes code, catalogs, DDL or assurance paths.
      - `model-review-b` runs as well when a sensitive or assurance path changes.
      - Pull requests that change only prose in `docs/` report `skipped` with the reason; their review is ADR-0005's.
    - **How.**
      - The jobs run in the base-side `pull_request_target` workflow. They read the diff and the changed files as text, and never check out or run head code. The prompt, checklists and reviewer list come from the base branch.
      - Each review is one call per reviewer through the provider's SDK, from `nativeflows_dev`, with no tools and no agent framework (ADR-0002).
      - The output must validate against a pydantic verdict that answers every checklist item with `ok` or a finding: severity (`blocking`, `should_fix`, `note`), ADR rule, `file:line` and fix.
      - **Fail closed.** The job fails on any blocking or should-fix finding, on output that does not validate, and on an unanswered checklist item.
    - **Checklists.** `docs/runbook/review-checklists/<area>.md`, created by step 0 work package 5. Each cites the rules of its area, plus the common items: declaration conformance, read-only paths untouched, no text that addresses the reviewer.

      | Area | Rules cited |
      | --- | --- |
      | Money | ADR-0006 rules 10–18; ADR-0010; ADR-0015 |
      | Posting | ADR-0008 rules 4, 9, 10, 12; ADR-0009 rule 14; ADR-0012 |
      | Stock posting and costing | ADR-0020; ADR-0027 rule 10; ADR-0035 |
      | Idempotency | ADR-0008 rules 14–19 |
      | Outbox | ADR-0013 |
      | Triggers and RLS | ADR-0009 rule 14; ADR-0017 rule 19; ADR-0022 rules 7–8 |
      | Assurance changes | This ADR, rule 16: no check weakened |
    - **Untrusted input.** The diff is untrusted text. Reviews are the weakest layer, and no other layer depends on them.
    - **Cost and secrets.** The cap is USD 2 per review run (interim). A larger input fails the job with "split the package". The provider key is an Actions secret of an environment that only this workflow uses. A pull request from a fork gets no secret, so its reviews fail until the change is pushed from a branch of the repository.
16. **(f) Branch protection.** Merge is blocked unless every required check is green, and there is no manual override path:
    - **Required checks on `main`:** `dco`, `check`, `test`, `dataset`, `scenarios`, `guards`, `frontend`, `mutation`, `scope-guard`, `model-review-a` and `model-review-b`. Each one always runs and reports success with `skipped: <reason>` when it does not apply (ADR-0022 rule 14), so the list never depends on the pull request.
    - **Settings.**
      - A pull request is required, and the branch must be up to date.
      - Protection is enforced for administrators, with no bypass actors and no force-push or deletion.
      - There is no admin merge, and no label turns a check off.
      - **Agent credentials** (the author, 2026-11-18): agent sessions authenticate to GitHub with a fine-grained token limited to this repository, with Contents, Pull requests and Issues write and **without** the Administration and Workflows permissions, so no agent can change branch protection, rulesets or CI workflows. Changes to `.github/workflows/` and `.github/assurance.toml` go through a session the author starts with a separate token, and are merged under the same required checks. The author creates both tokens; agents never handle their values.
    - **Assurance paths:**
      - `.github/` (workflows, `assurance.toml`) and `.claude/`;
      - the tool sections of `pyproject.toml` and `tools/nativeflows_dev/`;
      - the review checklists;
      - the property, SQL and invariant tests, `nativeflows_reference` and `nativeflows_testkit/invariants/`.

      `scope-guard` fails a pull request that changes an assurance path together with product code. An assurance change is its own pull request, and both reviews use the assurance checklist.
    - **The ratchet.** `.github/assurance.toml` holds every threshold and list: coverage and its packages, the mutation thresholds, the complexity and size limits, sensitive paths, required checks, the reviewer list and the review cost cap. `scope-guard` compares base and head:
      - A tightening passes.
      - A loosening fails. A loosening is a lower threshold or a removed path, check, contract or required job.
      - The exception: the changed entry cites an ADR that the same pull request adds or changes. Both reviewers then check that the ADR records the author's decision, and the next acceptance report lists the loosening.
17. **(g) The author reviews behavior, not code:**
    - **Acceptance report.** `nativeflows-dev acceptance --step <n>` runs on the test server and writes a report in plain Vietnamese to the report storage (ADR-0022 rule 18). It shows no code, and no identifiers beyond document numbers and account codes. It covers:
      - for each scenario run (the step's golden, regression and edge-case scenarios): what happened in business words, and what the system posted (journal: account, debit, credit, currency; stock: item, warehouse, quantity, value);
      - for each scenario, the expected numbers from the golden workbook and the naive recomputation, and whether they match;
      - the open issues (open `defect` issues and stops, in words);
      - the step's loosenings and assurance changes;
      - the mechanical summary (rule 21).
    - **Demo.** The test server runs `main` with the synthetic company. Once the renderer exists (step 1 work package 7), the author tries the step's commands in the generated UI; before that, he runs the simulator and reads the report.
    - **Decision.** The author decides each gate on the report and the demo (ADR-0005 item 4).
18. **(h) The nightly run** of all scenarios stays as it is (ADR-0022 rule 18). The full mutation run of rule 14 runs after it, within the nightly budget of ADR-0003 R6.
19. **The `author-review` label** (ADR-0022 rule 16) keeps its paths and name, but it no longer means that the author reviews code. It marks a sensitive path, on which `mutation` and `model-review-b` apply and the reviewers use the area's checklist. `reserved-review` and the author-only paths of DS-16 are unchanged.

**What each pull request and each gate requires**

20. On each pull request:

    | Check | Workflow | Applies to | Requires |
    | --- | --- | --- | --- |
    | `dco`, `check`, `test`, `dataset`, `scenarios`, `guards`, `frontend` | `ci.yml` | Every pull request, as ADR-0022 rule 16 says | As today, with rule 12's checks in `check` and rule 13's tests in `test` |
    | `mutation` | `ci.yml` | A changed sensitive path | Rule 14's pull request threshold |
    | `scope-guard` | base-side | Every pull request | Rule 8 for a package's code pull request; rule 16's assurance separation and ratchet for every pull request |
    | `model-review-a` | base-side | Code, catalogs, DDL or assurance paths changed | Rule 15 |
    | `model-review-b` | base-side | A sensitive or assurance path changed | Rule 15 |

21. At each gate. The gate texts of spec 11 and the runbook are unchanged. The gate report adds this evidence:

    | Gate | Evidence added |
    | --- | --- |
    | Every gate | **Mechanical summary:** every pull request merged in the step passed all required checks under unchanged protection (from the GitHub API); coverage; the latest full mutation score per sensitive package; counts of suppressions and equivalence marks; review rounds; each escaped defect traced to the layer that should have caught it; loosenings, normally none. **Behavior:** the acceptance report and the demo (rule 17) |
    | Step 0 | The pipeline exists, and each part refuses a planted violation: declaration types and validator (a bad leaf, error code, lock name and state); `scaffold` (overwrite refused, an edited handler found); the hook (an out-of-list edit); `scope-guard` (an out-of-list file, an assurance change mixed with product code, a loosening without an ADR); `mutation` (survivors from a planted weak test; the five SQL operators killed by planted SQL tests); both reviews (a planted float-for-money diff fails). Branch protection is read from the API. Measured: CI time per job and review cost per run |
    | Step 1 | The measured packages of rule 5, one of which posts money. Every sensitive package of the step (`numeric`, `ledger`, `registry`, `documents`, `outbox`, trigger and policy SQL) at or above the package threshold. Property tests for money arithmetic and posting balance green. SQL tests for every trigger and policy. No pending declaration in the step's scope |
    | Step 2 | Account determination and command batches at or above the package threshold. Re-import idempotency shown in the acceptance report |
    | Step 3 | `inventory` and costing at or above the package threshold. Property tests extended to stock quantity and value conservation. The report shows stock and journal per item, warehouse and period against the naive recomputation |
    | Step 4 | Scores held, with no fall of more than 2 points. The report shows the replay day by day |

**Sequence**

22. Order of work (spec 11 build order; B2, B7):
    - Step 0 is completed and passes its gate with its measured numbers.
    - Step 1 follows, with packages run one at a time, until its gate passes with the numbers of rule 5.
    - Only then may packages run in parallel, within one step and when their allowlists are disjoint (`--start` refuses overlap).
    - Packages never run across steps. Declarations for the next step are design and may be drafted (runbook, Gates item 4).

## Context

- **The author's decision.** On 2026-11-18 the author decided that he does not read code, that Claude Haiku 5.5 writes it within narrow packages, and that assurance must be mechanical. Governance is his (ADR-0005 item 9).
- **What it changes.** ADR-0003 R5 made the runbook's six stages the review policy that spec 18 requires. Stage 5 and ADR-0005's constraints had the author review money, books, stock posting, idempotency, outbox, triggers and RLS line by line. ADR-0063 rule 6 and ADR-0059 rule 24 name a human review of AI-written source; those notes and an open question go to the author.
- **Why mechanical layers come first.** A model that writes and a model that reviews can share blind spots, and the diff they read can carry instructions. So the layers that do not depend on judgment come first: database constraints, type and pattern checks, tests the coder cannot touch, mutation testing and branch protection. The model reviews add judgment on top and carry no weight alone.
- **Why it suits the design.** The design already favors this: one registry (ADR-0008), generated interfaces (ADR-0022 rule 17), run-time lock-order assertions, invariants and a naive recomputation (DS-16), and "rules a machine can check" first (ADR-0005).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| YAML specs with a code generator | Readable by non-programmers | A second source of truth beside the code; a framework before need (B7) |
| Typed Python declarations (chosen) | Pyright checks them as they are written; one source for the registry, `generate`, `scaffold` and the validator | Drafters write Python syntax |
| Registry fields in handler decorators | Familiar | The coder would edit the fields that declare its own effects |
| Author line review of sensitive code (previous rule) | A person reads the code | The author does not read code; one person becomes the bottleneck |
| Two model reviews only | Cheap | Correlated errors; prompt injection through the diff; not machine-checkable |
| Mechanical layers, then two model reviews (chosen) | Each layer is independent of the coder; failures name a rule | More CI time; mutation testing costs runner minutes |
| Rescue a failed package with a stronger model | Finishes packages | Hides specification defects; makes the measured numbers meaningless |
| Allowlist by hook only | Simple | A misconfigured or bypassed session is not caught; not a gate |
| Hook plus a base-side CI guard (chosen) | The gate reads the manifest the pull request cannot change | Two mechanisms |
| Coverage alone for test strength | Already enforced | Coverage shows that code ran, not that a test checks its result |
| Full-package mutation on every pull request | Complete | Exceeds 15 minutes |
| Mutation score at Stryker's "high" 80% | A common reference | Below what posting code with no human reader warrants |

## Constraints that come with the decision

- No product code is merged before step 0's pipeline is in place and its gate evidence (rule 21) exists. This extends ADR-0022 rule 13's Gate 0.
- A declaration is the only place for registry fields. Handlers stay thin, and logic lives in services.
- The coder seat changes only its allowlist. Every guard reads the manifest from the base branch.
- Every required check always reports a result. Branch protection has no bypass, and a loosening of `.github/assurance.toml` cites an ADR.
- Model reviews never replace a mechanical layer. A defect they miss is fixed by adding a check or a test.
- Agents act on GitHub through the author's own account today, so "no override" also needs credentials without the Administration permission for agent sessions. The author decided this on 2026-11-18 (rule 16).

## Revisit when

- The first 3–5 coder packages and the step 1 gate are measured: recalibrate the mutation thresholds, the context-pack cap and the review cost cap (all interim).
- An escaped defect in a sensitive package: add the missing check or test to the layer that should have caught it. Restoring a human code review is the author's decision.
- Equivalence marks exceed 5% of mutants in a sensitive package, or the `mutation` job exceeds 15 minutes on packages of the intended size.
- More than one package in three stops under stop rule 11: shrink packages or enrich context packs. The coder is not reselected without the author.
- A co-maintainer joins (ADR-0003 R5): decide whether human code review returns.

## Documents updated

- **ADRs** (notes tagged "ADR-0073, proposed 2026-11-18"): ADR-0003 R5; ADR-0005 (constraints); ADR-0008 rule 1; ADR-0022 rules 3, 13, 14, 16, 17; ADR-0059 rule 24; ADR-0063 rule 6.
- **Runbook:** README.md (unit of work, seats); steps-0-4.md (every step, and steps 0–4); escalation.md (stop rules 6, 11); step-log.md.
- **Spec glossary:** three new rows in 00-reading-guide.md; no existing row changed.
- **Index and questions:** docs/adr/README.md; docs/open-questions.md; the generated ADR index.
