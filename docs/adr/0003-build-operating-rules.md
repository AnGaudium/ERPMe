# ADR-0003: Build operating rules

Status: accepted (2026-11-14). Answers drafted by an agent on the author's instruction to choose the simplest workable option; the author accepted them by that instruction. Amended before its first merge (2026-11-14): R3 and R10 changed by the author's decision. R5: who accepts design items in stage 1 of the six-stage policy is set by [ADR-0005](0005-technical-decisions-delegated.md). Design items: DS-17, DS-18, DS-30, DS-34, DS-37, DS-40. Related decisions: D3, D11, D15, D16.

## Decision

The fourteen operating questions raised while writing the [runbook](../runbook/README.md) are answered by rules R1–R14 below. Each rule picks the option with the fewest moving parts that still protects the gates. None changes a decided item, a gate, scope or the build order. No rule sets an accounting, tax or legal rule: where a question touches law, the rule fixes only the process and the deadline.

| # | Question | Rule |
| --- | --- | --- |
| R1 | What is the small dataset at step 0, when no commands exist? | At step 0 the small synthetic dataset is the business-event log plus the input files the simulator writes, reproducible from (simulator version, seed, dataset version). It contains every EC v1 edge case at least once **as events**. Each EC-xx in the DS-17 catalog carries a "first executable step"; the coverage report counts an edge case as exercised only when its events ran through commands at or after that step |
| R2 | When is staging stood up? | Not before step 10. Until then the test server is the only environment besides CI. Staging is built at step 10 from the DS-37 deployment documentation, which also tests that documentation. Phase 0's pipeline is GitHub → test server |
| R3 | Is the repository public from step 0? | Yes. The existing repository `AnGaudium/ERPMe` is made public now. No organization is created until the first co-maintainer joins; the repository is then transferred, which keeps issues, pull requests and redirects. Commits keep the author's own email. The repository only ever holds synthetic data (D16), so nothing is lost by being public early |
| R4 | Core coverage threshold | 90% branch coverage, measured with coverage.py through pytest-cov, enforced by CI from step 1 on the core packages: ledger, inventory and costing, posting, tax, localization loader, command registry. Other packages are reported, not enforced. The threshold is a floor; tests are never written only to raise it |
| R5 | Policy for reviewing AI-written code; DCO for agent commits | The policy is the six-stage unit of work in [runbook/README.md](../runbook/README.md#the-unit-of-work); no separate document. Every commit carries `Signed-off-by:` from the human who submits it, because only a person can make the DCO certification; the agent appears as `Co-Authored-By:`. CI rejects a commit without a sign-off from the first push to the public repository |
| R6 | Test-run budgets | CI on a commit finishes in 15 minutes or less; anything slower moves to the nightly run. The nightly run finishes in 6 hours or less; the medium replay inside it in 4 hours or less, otherwise slowness is filed as a defect. The test-scenario model spends USD 5 or less per night, stopped by a circuit breaker while the deterministic part continues. Before go-live the test server is deployed only by the nightly run, so "after every deploy" is the nightly run. Agent budgets stay with DS-32 |
| R7 | Where are defects tracked? | In the GitHub issue tracker, label `defect`, always, before and after step 5. The work queue holds business work only (glossary: work_item is distinct from technical jobs), so development defects never enter it. The dedupe key (failing check + first failing command type) is the issue title |
| R8 | When is an agent "done" for step 10? | Draft-only mode, with: replay evaluation green in CI; every hard-floor test green; and on the synthetic dataset at least 90% of cases produce a draft equal to the simulator's known answer (mapping, match, quotation lines), unless DS-34 sets a higher threshold for that workflow. The simulator generated the truth, so accuracy is computed deterministically; the eval judge is needed only for free text (quotation wording). Auto-posting stays off until shadow mode on the pilot's real transactions passes |
| R9 | How is "no slower than MISA" measured? | One outside accountant who uses MISA daily, paid. One simulated day of at least 50 documents spread over the 6 hand-built screen types, synthetic data only. The accountant enters it in ERPMe first (after at most 1 hour of training), then the same day in MISA. Metric: elapsed time until every document is entered correctly. Pass when ERPMe time ≤ MISA time. ERPMe goes first so the learning effect favors MISA, which makes a pass conservative |
| R10 | Who verifies legal rules, by when? | The core is generic and holds no country rules, so no contracted verifier is engaged now. The author verifies the Vietnam package rules against the original legal text. The basic US package is built from public primary sources (DS-38). Either way, an open legal question is closed only with the source (document, article, date) and the name of the person who verified it ([runbook/escalation.md](../runbook/escalation.md#unverified-legal-rules)), by the step in the table below. The independent check comes from the pilot's chief accountant, who reviews the rules the pilot uses during the step 11 rehearsal against the pilot's real books (R11). Packages for other countries come after Vietnam and the US, with legal sources required by CI ([risks.md](../risks.md)) |
| R11 | Go-live with unverified rules? | No. Every localization rule the pilot's transactions use must be verified before the step 11 gate. A rule the pilot does not use (e.g. the TT133 regime for a TT99 pilot) may stay flagged, and is disabled for that company |
| R12 | Where do staging with real data and production run? | Both on servers operated by the author, located in Vietnam, staging as a separate database and stack from production. Only the author has access to staging; the pilot's users access only production. Real data is on staging only while a rehearsal or a migration test runs, and is deleted within 7 days after it. The legal basis for the author processing the pilot's data (processor obligations under Law 91/2025/QH15) is added to the legal verification list for step 11 |
| R13 | Fallback if the pilot must stop after go-live? | Fix forward is the default: every operation works without LLMs (Principle 12), and hotfixes follow the runbook. Abort is the owner's and chief accountant's decision: documents of the open period are re-entered in the old system from ERPMe's full data export. The pilot keeps its old system installed and licensed, closed for entry, until the Phase 1 gate. The last clean abort point is before the first VAT return is filed from ERPMe |
| R14 | Release freeze around closing days and tax deadlines | Defined by events, not dates: the feature-release window opens when the previous period is locked and its tax return, if one is due, is filed; it closes 5 working days before month end. No feature release outside the window. Hotfixes for defects that block operation may ship at any time, with their regression scenario. No legal deadline is hard-coded |

**R10 verification schedule** (each item is an existing line in [open-questions.md](../open-questions.md)):

| Needed before the gate of | Items |
| --- | --- |
| Step 1 | TT99 FX rules (413, 515, 635); reversal as storno or swapped sides; posting date of a reversal when the original period is locked |
| Step 2 | Dependent unit with its own tax ID: company or branch |
| Step 3 | Landed cost from a closed period; rate that values an import receipt; receipt-versus-invoice rate difference; GR/IR account and its B01 line; TT99 standard-cost method and removal of 611/631 |
| Step 6 | Book rate for realized FX after a revaluation |
| Step 7 | Decree 70/2025; VAT deduction for invoices of VND 5 million or more |
| Step 8 | FX revaluation: reverse and repost, or post the delta |
| Step 10 | TT133 status; B03 for TT133 businesses |
| Step 11 | Implementing decree of the Personal Data Protection Law; processor obligations (R12) |

## Context

The runbook needs these answers to be executable; the specification left them open ([open-questions.md](../open-questions.md)). The project has one author, so each rule is judged by the work it adds per week, not only by what it protects.

## Options considered

| # | Chosen | Rejected, and why |
| --- | --- | --- |
| R1 | Event log covers all of EC v1 at step 0; execution coverage grows per step | Only step 1 edge cases at step 0: the log would need reworking at every step, against "the same log drives every step" ([12-testing.md](../spec/12-testing.md)) |
| R2 | Staging at step 10 | Staging from step 0: a second environment to maintain for 10 steps with no user and no real data |
| R3 | Current repository, public now; organization later | Private until step 10: hides public ADRs and roadmap that [18-license-governance.md](../spec/18-license-governance.md) wants public. Create an organization first: no benefit before a co-maintainer exists, and a later transfer costs nothing |
| R4 | 90% branch on core packages | One number for all code: pushes tests for UI glue; no threshold: risks.md and governance require one |
| R5 | The runbook is the policy | A separate review-policy ADR: two documents saying the same thing drift apart |
| R6 | Fixed time and money caps | No caps: cost drift; per-run token accounting dashboards: too much tooling now |
| R7 | GitHub issues always | Move defects into the work queue at step 5: mixes development defects with the customer's business work |
| R8 | Ground truth from the simulator | LLM judge for every agent: non-deterministic scoring, against Principle 13 |
| R9 | Same day, ERPMe first | Two different days: harder to compare; MISA first: favors ERPMe |
| R10 | The author verifies Vietnam rules, US rules from public sources; the pilot's chief accountant checks at step 11 | A contracted verifier from step 1: cost and coordination before any customer exists. Weakness of the chosen option: no independent check until step 11, so a misreading can stay in golden scenarios for months; the revisit condition below limits that |
| R11 | No unverified rule in use at go-live | Go live with flags and an accountant's waiver: the gate is strict because there is no parallel run (D11) |
| R12 | Author-operated servers in Vietnam | Customer premises: the author cannot support and hotfix within the 30–50% support time. Location chosen as the conservative option until residency rules are verified |
| R13 | Fix forward; abort by re-entry; old system kept until the Phase 1 gate | A parallel run: excluded by D11 |
| R14 | Event-defined window | A fixed day count before legal deadlines: would hard-code legal dates |

## Constraints that come with the decision

- DS-17's edge-case catalog has a "first executable step" column (R1).
- DS-18 includes coverage enforcement, DCO check and the CI time limit (R4, R5, R6).
- DS-37 covers staging, built at step 10 (R2); DS-40 covers the abort procedure, the old-system retention and the staging deletion rule (R12, R13).
- DS-34 may raise, never lower, the 90% agent threshold (R8).

## Revisit when

- CI stays above 15 minutes or the nightly above 6 hours after moving work: revisit R6.
- The test-scenario model finds no new defect for 4 consecutive weeks at USD 5 per night: lower the cap.
- A partner joins as co-maintainer: revisit R5 (second reviewer with merge rights).
- Legal review finds that R12's location or processing arrangement is not lawful: revisit R12.
- During the step 11 rehearsal the pilot's chief accountant disputes a rule, or two or more defects trace back to a misread rule: engage an independent verifier for the remaining rules (revisit R10).

## Documents updated

- [docs/open-questions.md](../open-questions.md): the fourteen questions closed with links to R1–R14; the GitHub organization question closed by R3.
- [docs/spec/10-roadmap.md](../spec/10-roadmap.md): Phase 0 pipeline (R2).
- [docs/spec/12-testing.md](../spec/12-testing.md): defects go to the issue tracker (R7); budgets (R6).
- [docs/spec/18-license-governance.md](../spec/18-license-governance.md): review policy and coverage threshold point here (R4, R5).
- [docs/runbook/](../runbook/README.md): README, steps-0-4, steps-5-9, go-live, testing-operations, escalation.
- [docs/adr/README.md](README.md): index row.
