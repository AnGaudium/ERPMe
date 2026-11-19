# Implementation runbook

The operating manual the author and the AI agents follow to execute the build plan from Build step 0 to the Phase 1 gate. It says **how** the work is run. **What** is built, in which order and to which gate is set by [11-build-order.md](../spec/11-build-order.md), [10-roadmap.md](../spec/10-roadmap.md) and [decisions.md](../decisions.md); this runbook never overrides them. If the runbook and those files disagree, they win (precedence in [00-reading-guide.md](../spec/00-reading-guide.md)) and the difference is recorded in [open-questions.md](../open-questions.md).

## Files

| File | Covers |
| --- | --- |
| [README.md](README.md) | This overview and the operating rhythm |
| [steps-0-4.md](steps-0-4.md) | Phase 0: steps 0–4, ending at the Phase 0 gate (= step 4 gate) |
| [steps-5-9.md](steps-5-9.md) | Phase 1 build: steps 5–9 and the three Phase 1 agents |
| [go-live.md](go-live.md) | Steps 10–11, cut-over, the first three monthly closes, support mode, the Phase 1 gate |
| [testing-operations.md](testing-operations.md) | Test server, simulator, nightly runs, budgets, defects to regression scenarios, coverage reports |
| [escalation.md](escalation.md) | When an agent stops and asks; what an agent never decides; unverified legal rules |
| [step-log.md](step-log.md) | Dated record of gate decisions and one line per weekly review |

## How to use it

- **Starting a session (any agent):** read [AGENTS.md](../../AGENTS.md), then this file, then the section of the step you work in, then [escalation.md](escalation.md). The step section tells you which design items (DS-xx) must exist before you write anything.
- **Planning the week (author):** open the current step's section, pick the next work packages in order, check their DS-xx dependencies in [backlog.md](../design/backlog.md), and check the step's gate against the latest nightly report.
- **At a gate:** use the step's "Verification" and "Exit gate" lines as the checklist. Only the author declares a gate passed (see [escalation.md](escalation.md)).
- Every step section has the same headings: entry criteria, design items, work packages, how agents are used, verification, exit gate (copied word for word from [11-build-order.md](../spec/11-build-order.md)), artifacts, risks, fallback.

Invariant and edge-case identifiers (INV-xx, EC-xx) are assigned by DS-16 and DS-17. Until those catalogs exist, this runbook names invariants and edge cases by their description in [12-testing.md](../spec/12-testing.md); replace descriptions with IDs when the catalogs land.

## Operating rhythm

### The unit of work

A **work package** is the smallest piece that can be merged on its own and keeps `main` green. It belongs to exactly one build step and names the DS-xx items it implements. It flows through six stages; a stage is never skipped.

| Stage | What happens | Who | Output |
| --- | --- | --- | --- |
| 1 · Design | If the DS-xx item is not done, it is done first: ADR in `docs/adr/`, spec in `docs/design/`, or catalog in `docs/catalogs/`. Open points go to [open-questions.md](../open-questions.md) | Builder agent drafts; a reviewer agent on a different model reviews; technical items are accepted under [ADR-0005](../adr/0005-technical-decisions-delegated.md), items on its reserved list by the author | DS file, backlog row linked |
| 2 · Reference results (B4) | Invariants, golden scenarios, edge cases and simulator events that the package must satisfy exist before or with the code: new INV-xx in the DS-16 catalog, new EC-xx in the DS-17 catalog, simulator event types and the adapter for this step, golden spreadsheets | Builder agent drafts invariants, events and adapters; the author builds golden expected values by hand | Catalog rows, golden files, adapter |
| 3 · Implementation | Code and tests on a branch, inside the module boundaries of DS-18 | Builder agent | Branch with commits |
| 4 · Tests and invariants | CI on every commit: ruff, pyright strict, import-linter contracts, pytest on real PostgreSQL, Hypothesis short profile, small synthetic dataset replay with every invariant, all regression scenarios, agent replay evaluation where agents exist | CI | Green CI run |
| 5 · Independent review | A reviewer agent that did not write the change reviews the diff against the DS file and the spec. Changes that touch money, books, stock posting, idempotency, outbox, triggers or RLS are also reviewed by the author line by line | Reviewer agent; author | Review notes resolved |
| 6 · Merge | The author merges to `main`. Documents affected by the change are updated in the same pull request | Author | Merged change |

A work package is done when it is merged, the documents it affects are updated, the next nightly run is green, and any new open question is recorded.

This six-stage flow is the project's policy for reviewing AI-written code required by [18-license-governance.md](../spec/18-license-governance.md) ([ADR-0003](../adr/0003-build-operating-rules.md) R5).

Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), proposed 2026-11-18; the author's decision of 2026-11-18): for code, the stages run as follows.

- **Stage 1** adds the declarations. Claude Sonnet 5.5 drafts them chunk by chunk, with each package's manifest (allowlist and context pack), and Claude Opus 5.5 or Claude Fable 5.2 reviews them.
- **Stage 2** adds property tests and SQL tests, written by a seat other than the coder. They are read-only to it.
- **Stage 3.** `nativeflows-dev work-package <id> --start` scaffolds the package. Claude Haiku 5.5 then writes only the `services/` body and the new tests in its allowlist, fenced by a hook. Platform code and the first package of each kind are assigned up front to Claude Opus 5.5. After two red attempts the coder stops, and the package is never rescued by a stronger model.
- **Stage 4** adds `mutation` and `scope-guard`.
- **Stage 5.** The author no longer reviews code. Two model reviews on different models, `model-review-a` and `model-review-b`, are required check runs. On paths of money, books, stock posting, idempotency, outbox, triggers and RLS, both reviews and mutation testing apply.
- **Stage 6.** Branch protection blocks the merge until every required check is green, with no override. The author merges, and reviews behavior at each gate from a plain-Vietnamese acceptance report and a demo on the test server. His stage 5 time moves there.

In "Who does what" below, the Builder row's pointer to spec 17's Builder seat is model guidance only. That seat is the product's runtime customization seat, not the development coder; the development seats are ADR-0073 rule 4.

### Branches, commits and pull requests

- `main` is always green on CI. Nobody commits to `main` directly; every change arrives by a pull request merged by the author.
- Branch names: `ds-xx-short-title` for design items; `step-n-short-title` for implementation (e.g. `step-1-reversal`); `fix-short-title` for defects; `docs-short-title` for documentation-only changes.
- One pull request = one work package. A pull request touching two build steps is split.
- Commit messages and pull-request descriptions cite the reference IDs they act on (Principle n, Dn, step n, Bn, DS-xx, INV-xx, EC-xx, ADR-nnnn), as [AGENTS.md](../../AGENTS.md) requires.
- The pull-request description has five lines: IDs; what changed; documents updated; reference results added (INV, EC, golden, regression); open questions added or closed.
- A defect fix always includes the regression scenario that reproduces it ([testing-operations.md](testing-operations.md#defects-to-regression-scenarios)).
- Contributions use DCO, not a CLA (D3). Every commit carries `Signed-off-by:` from the human who submits it; an agent appears only as `Co-Authored-By:`. CI rejects unsigned commits from the first push ([ADR-0003](../adr/0003-build-operating-rules.md) R5).
- The repository `AnGaudium/NativeFlows` is public; an organization comes only when the first co-maintainer joins ([ADR-0003](../adr/0003-build-operating-rules.md) R3).
- Defects are GitHub issues labelled `defect`, titled with their dedupe key ([ADR-0003](../adr/0003-build-operating-rules.md) R7).

### Who does what

The author is one person with final say (BDFL, [18-license-governance.md](../spec/18-license-governance.md)). AI agents write most of the documents and code. Agents work in roles; one session holds one role.

| Role | Does | Must not | Model guidance |
| --- | --- | --- | --- |
| Builder | Drafts DS files, writes code, tests, simulator events and adapters, documentation | Merge; decide accounting, tax or legal rules; compute golden expected values | The Builder seat in [17-seatmap-data-classification.md](../spec/17-seatmap-data-classification.md) (very high reasoning) |
| Reviewer | Reviews a builder's change against the DS file, the spec and this runbook; lists defects and missing reference results | Review its own work; fix the change itself in the same session | The Reviewer seat: a different model from the builder, ideally a different provider; for changes touching money and books, the reference model listed there |
| Recomputation writer | Writes the independent naive recomputation from the specification only ([12-testing.md](../spec/12-testing.md)) | Read the core code; share a session with a builder | Any builder-class model, in a session with only `docs/` and the recomputation folder |
| Test-scenario model | Proposes unusual but realistic business situations on the test server | Compute expected results or judge pass/fail; deterministic code judges | Configured in the test server, within the nightly budget |
| Eval judge (from the first agent) | Scores the agent evaluation suite | Score a model of its own kind | The Eval judge seat |

**The author always decides** (the reserved list in [ADR-0005](../adr/0005-technical-decisions-delegated.md)): every accounting, tax and legal rule; golden-scenario expected values; whether a gate has passed; every merge and push; any change to decided items, scope, gates, build order or governance (only by a new ADR); pilot selection and go-live; release timing after go-live. Agents decide everything technical and accept technical ADRs and DS files after an independent review. The stop rules are in [escalation.md](escalation.md).

**Split of time before go-live (guidance, not a rule):** the author spends most time on stages 1, 2 and 5 (decisions on the reserved list, golden scenarios, review of money and books) and on legal verification; agents carry stages 3 and 4. From go-live the support reservation applies ([go-live.md](go-live.md#support-mode)).

### Weekly cadence

| When | What | Output |
| --- | --- | --- |
| Every morning (15 min) | Read the nightly report: invariant failures, reference-comparison differences, edge-case coverage, budget use. Triage new defects | Defects filed; failing nightly blocks merges until understood |
| Monday | Plan the week: next work packages from the current step, DS dependencies checked, open questions due this step listed | Week list in [step-log.md](step-log.md) |
| During the week | Work packages through the six stages; several builder sessions may run in parallel only on work packages that touch different files | Merged changes |
| Friday | Weekly review: progress against the step's gate checklist; coverage trend; budget use; open questions added and closed; documents in sync with code (below); one line in the step log | Updated gate checklist, step log line |
| At each gate | Gate review ([Gates](#gates)); review [risks.md](../risks.md) at the Phase 0 and Phase 1 gates | Gate record |

### Open questions

- **Raising:** anyone (author or agent) adds a line to [open-questions.md](../open-questions.md), prefixed with the reference IDs it blocks, e.g. `(DS-10, step 6)`. An agent that raises a blocking question also stops that work package ([escalation.md](escalation.md)).
- **Due date:** a question is due by the step that needs it, taken from the DS item's "Needed by" column in [backlog.md](../design/backlog.md). The Monday plan lists questions due in the current or next step.
- **Closing:** tick the box and link the answer (an ADR, a DS file, a decision row, or a verified legal source). A legal question is closed only with the source and the name of the person who verified it ([escalation.md](escalation.md#unverified-legal-rules)).

### Keeping documents in sync with code

- The pull request that changes behavior also changes the documents that describe it. An ADR that changes the design updates every affected document in the same change ([AGENTS.md](../../AGENTS.md)).
- Glossary: a new code identifier is added to the glossary in [00-reading-guide.md](../spec/00-reading-guide.md) in the same change (DS-01).
- Catalogs (system accounts, transaction keys, movement types, edge cases) change only together with their owning DS item ([catalogs/README.md](../catalogs/README.md)).
- The reviewer checks document sync as part of stage 5. The Friday review samples the week's merges for drift.

### Gates

1. The builder prepares a gate report: the gate text, and for each condition the evidence (nightly run ID, coverage report, reference-comparison report, golden scenario results).
2. A reviewer agent checks the report against the gate text word for word and lists any condition without evidence.
3. The author decides pass or fail and records it in the step log with the date. A gate is a condition, not a date (D15).
4. On fail, the step's fallback applies. No work on the next layer starts before the gate passes (B2); design items for the next step may be drafted.
