# ADR-0005: Technical decisions are delegated to agents

Status: accepted (2026-11-14) by the author. Written on the author's instruction: "All technical issues are decided by the agent. The overriding goal is that the system is easy for AI to use." This ADR is on its own reserved list (item 9); the author accepted it as written, including items 2 and 11. Design items: all DS items. Related decisions: D2, D3, D12, D15. Build principles B1, B2, B3. ADR-0003 R5.

## Decision

Agents decide every technical question and accept technical ADRs and DS files themselves, under the acceptance rule below. The author keeps the decisions in "Reserved for the author". When technical options compete, the option that is easiest for AI agents to use wins, after correctness, Principles 1–13, the gates, the hard floors and the decided items. The author may reopen any agent decision at any time with a new ADR.

### Reserved for the author

1. Accounting, tax and legal rules, including their verification status (reading guide, rule 4).
2. Decided items D1–D17, including the technical ones (D4, D13, D14 and the tools chosen in ADR-0002), because each is a project-wide foundation; scope, gates and the build order, including B3 (a commercial document never changes the core).
3. Golden-scenario expected values; which reference is right when the core, the naive recomputation and a golden scenario disagree; removing or weakening an invariant (INV-xx), or changing the naive recomputation to make a failure pass.
4. Whether a gate has passed, including re-confirming a gate after a layer's contract changed (B2).
5. Merges to `main`; pushing to the public repository and opening pull requests (on the author's request only); releases and their timing after go-live.
6. Pilot selection, go-live, and anything said to the pilot customer.
7. Weakening, or changing beyond its DS file, the hard floors and safety mechanisms: untrusted content, segregation of duties, "Human only" actions (closing periods, reversing posted documents), permission intersection and the routing switch ([03-agent-safety.md](../spec/03-agent-safety.md), D12); relaxing a policy threshold; raising a budget set in ADR-0003 R6 or by DS-32; changes to `seatmap.yaml` taking effect without passing the evaluation suite.
8. Real company or personal data, and anything about the pilot's data.
9. The project's governance: ADR-0003, this ADR, and the runbook's review, merge, escalation and gate rules.
10. Changing the meaning of a Principle (Principles 1–13). Aligning wording with an accepted ADR without changing meaning is technical.
11. Business behavior that users or the customer see and the spec does not state, e.g. how an exceeded credit limit affects an order, or who approves a general journal entry.

   Note (the author's delegation, 2026-11-21; recorded by the chief architect): the author's words (2026-11-21, in translation; [decisions.md](../decisions.md), delegation note): the chief architect decides on his own initiative; nothing is an overstep of his authority, because the author does not see enough of the whole picture to decide; a choice about 50/50 becomes configurable. The same day the author said that the chief architect runs fully autonomously to the end of this step, merging this pull request included; recorded as said, for this step (build step 0, session S2). The chief architect's reading: merges after it follow the same autonomy only if the author says so again. How this maps onto the items above is the chief architect's reading, item by item: (1) delegated; values of law still need a verified source and stay flagged configuration until they have one (a matter of truth, not authority); (2) scope and the build order delegated; gates as in (4); the decided items D1–D17 are not reopened without a new ADR; (3) kept: golden-scenario values, which reference is right when they disagree, and removing or weakening an invariant or changing the naive recomputation stay the author's (the lab rule stays; adding or tightening a check is technical); (4) not delegated as a judgment: a gate passes on its mechanical criteria and the verdict of a reviewer on a different model, reported to the author; the builder does not judge his own gate; (5) the merge of this step's pull request by the author's word above, a grant for one step; later merges, pushes to `main` and releases stay the author's, and pushing to the public repository and opening pull requests stay on his request (outward); (6) kept (outward: the pilot); (7) hard floors stay floors: they change only within their DS file and are never weakened; (8) kept: real data never enters the repository; (9) kept: the project's governance stays the author's; recording his own words on it, as this note does, is not a change of it, and the record is reviewed on a different model; (10) kept: a Principle's meaning is a foundation, like D1–D17; aligning wording stays technical; (11) delegated: decided, recorded and reported. Delegated in short: items 1, 2 (scope and the build order) and 11, the decisions on accounting rules, scope, build order and business behavior, as [AGENTS.md](../../AGENTS.md) states in one sentence (revised 2026-11-21 after document review round 7, X1). Every decision taken under the delegation is recorded with its reason and reviewed by an agent on a different model; a choice found evenly balanced becomes a configurable setting ([ADR-0063](0063-configurable-policy-settings.md)).

Everything else is technical, including: identifiers and the glossary, data model and DDL, key and column types, module and repository layout, command, event and error formats, algorithms that implement a written rule, test and CI design that keeps every invariant, tooling configuration, adding a library (by ADR when it opens a category ADR-0002 does not cover, and never one on ADR-0002's "deliberately not used" list), changing an accepted technical ADR (by a new ADR that supersedes it), and changing a layer's contract after its gate for a measured reason that a commercial document did not trigger (B2, by ADR, with the affected verification rerun and the gate re-confirmed by the author).

### How a technical ADR or DS file is accepted

1. A builder agent drafts it and records every choice and the options rejected.
2. A reviewer agent on a different model from the builder reviews it against the spec, D1–D17 and this ADR (step 0 "How agents are used" in [steps-0-4.md](../runbook/steps-0-4.md)).
3. It is accepted when the review leaves no blocking or should-fix finding. The status line reads `accepted (YYYY-MM-DD) under ADR-0005, reviewed by <reviewer model>`, and the step log gets one line.
4. If builder and reviewer still disagree on a blocking or should-fix finding after two review rounds, the item goes to the author.
5. A DS item that mixes both kinds of decision is split: the technical part is accepted under this ADR; each reserved decision in it stays flagged configuration or goes to [open-questions.md](../open-questions.md) for the author. The item is done when the technical part is accepted and those points are listed (design "done" rule).

### What "easy for AI to use" means

When technical options compete, prefer, in this order:

1. One way to do each thing: one name per concept, one format per kind of data, no aliases.
2. Rules a machine can check (CI, the command registry, import-linter) over rules that need judgment.
3. Explicit over implicit: inputs, preconditions and effects written in schemas and files, never in hidden state or convention alone.
4. Errors that name the rule that failed and how to fix it.
5. Widely used, well-documented tools and patterns over novel ones (ADR-0002).
6. Small, self-contained documents and modules with reference IDs, so an agent loads only what it needs.
7. Fewest moving parts (as in ADR-0003).

## Context

The project has one author and AI agents write most documents and code ([runbook/README.md](../runbook/README.md#who-does-what)). The runbook made the author accept every ADR and DS file, which puts 18 step 0 design items and every later technical choice on one person's queue. Most of those choices are technical and reversible before go-live (B8). The decisions that can hurt the books, the customer, the law or the project's own rules (reserved items 1–11) stay with the author. The agents are also the main users of the code, the documents and the command layer (Principles 1, 10), so their ease of use is the measure of a good technical choice.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Agents decide technical questions; author keeps a fixed reserved list (chosen) | Removes the author from the critical path of step 0; the reserved list keeps the risky decisions with the author | A wrong technical choice is caught only by the reviewer agent until the author reads it |
| Author accepts every ADR and DS file (previous rule) | Every design choice seen by a person | One person becomes the bottleneck for 18 items before code and 22 more later |
| Agents decide only "small" technical questions (previous reading guide, rule 5) | Narrow delegation | "Small" needs judgment, so agents ask anyway; not machine-checkable |
| Delegate the technical decided items D4, D13, D14 too | Literal reading of "all technical issues" | Each is a foundation every module depends on; reversing one by agent ADR would cost more than asking. The author can add them by amending item 2 |

## Constraints that come with the decision

- Every technical decision is written down (ADR, DS file or a recorded choice in the work package), so the author can audit and reopen it.
- Changes touching money, books, stock posting, idempotency, outbox, triggers or RLS are still reviewed by the author line by line before merge (runbook stage 5). Before such a change goes beyond its DS file, the agent updates the DS file under this ADR.
- An agent never marks a legal rule verified and never sets golden values.

Note ([ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): the author decided on 2026-11-18 (governance, item 9) that the second constraint no longer applies to code. Changes touching money, books, stock posting, idempotency, outbox, triggers or RLS are not read by the author. They pass ADR-0073's mechanical layers and two model reviews, on models different from the builder and from each other, recorded as required check runs (rules 11–19). Updating the DS file first still holds. For code, step 2 of the acceptance rule is the review check runs. The development seats are ADR-0073 rule 4: Claude Sonnet 5.5 drafts declarations, Claude Opus 5.5 or Claude Fable 5.2 reviews them, and Claude Haiku 5.5 codes. Under the second revisit condition below, the missing mechanical check or test is added first; whether the author's code review returns is his decision.

## Revisit when

- Two or more technical decisions accepted under this ADR are reversed by the author within one build step: narrow the delegation.
- A defect that reaches a gate review traces back to a technical decision no person read: add the author's review for that kind of decision.
- A co-maintainer joins (ADR-0003 R3, R5): decide whether they share the reserved list.

## Documents updated

- [AGENTS.md](../../AGENTS.md): rule pointing here.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): rule 5.
- [docs/runbook/README.md](../runbook/README.md): stage 1 owner; "The author always decides"; split of time.
- [docs/runbook/escalation.md](../runbook/escalation.md): introduction; stop rules 1, 3, 4, 6, 7; "Never decided by an agent".
- [docs/runbook/steps-0-4.md](../runbook/steps-0-4.md): step 0 "How agents are used".
- [docs/runbook/testing-operations.md](../runbook/testing-operations.md): spec gaps.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
- [docs/adr/0003-build-operating-rules.md](0003-build-operating-rules.md): note that the R5 policy's stage 1 owner changes here.
- [docs/adr/template.md](template.md): status form for agent-accepted ADRs.
- [docs/adr/README.md](README.md): index row.
