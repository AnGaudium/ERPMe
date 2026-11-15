# Review r6 of ADR-0058 "Configurable workflows" and ADR-0059 "AI tuning and development of deterministic functions" — verdict: ACCEPT

0 blocking, 0 should-fix, 3 nits. The nits need no further review round.
File:line refer to the review copy (`base-integrated` with `apply_workflows.py` applied): "0058" = `adr/0058-configurable-workflows.md`, "0059" = `adr/0059-ai-tuning-and-development-of-deterministic-functions.md`, "t22" = `lab/t22_workflows.py`.

What I ran:
- No git in `~/Projects/ERPMe`. A `/tmp` copy of `base-integrated`; the base was not touched.
- `apply_workflows.py` applies cleanly: 73 writes over 34 files, lab findings L-27 and L-28.
- With `--load`, each on its own fresh database: t22 140/140, t23 102/102, t12 189/189, t15 146/146, t17 117/117, t19 177/177, t20 184/184, t21 93/93, t11 163/163, t14 83/83, t16 99/99.
- With the standard load in one session, each on its own fresh database, no load errors: t01 16/16, t02 6/6, t03 4/4, t04 5/5, t05 62/62, t06 60/60, t07 38/38, t08 46/46, t09 60/60, t10 69/69, t13 24/24.
- `check_package.py` on the `DS-19-vietnam-tt99` package: RESULT PASS, SELF-TEST PASS.
- CSV check (my own): all 13 catalog files parse with a constant column count; no duplicate code in `invariants.csv`, `edge-cases.csv` or `work-item-kinds.csv`; 173 invariants, which DS-16 states.
- No run hit "out of shared memory".
- Cleanup done: every `erpme_lab_rv58_*` database dropped, the `/tmp` copy deleted. This file is the only file written.

## Round-5 items

| Item | Status | Note |
| --- | --- | --- |
| S1 flat union | Fixed | `owner_scope` is, per rule, a set of cells: one per assignment in force whose role grants the condition source's permission, split to single values (branch or `all`, warehouse or `all`, level, and for `team` and `department` the units with their employees). A stored cell is covered by a new cell with the same or `all` branch and warehouse, a level at least as high and, for `team` and `department`, all its employees; the scope narrowed when a stored cell is not covered. The lab's `covered` matches the text |
| My probe | In the lab | W20o: B2 lowered from `company` to `own` while B1 stays is narrowed and names the B2 cell. W20p: the only permission-bearing B2 assignment ends while another role's remains. W20q: a level swap between two branches. W20j, W20j2: an equal-reach split and a merge stay silent. W20k, W20l: widening only updates, and a later loss is seen |
| N1 frequent items for teams | Applied | The item goes to the rule's owner; `company_owner` is involved only for `owner_inactive`; the catalog row and the ADR-0042 note agree |
| N2 widening | Applied | One step to the smallest window that holds 50 acting proposals, capped at 180 days; at the cap the attempt repeats daily; unjudged stays open for a person |
| N3 standard load | Resolved | The one-session load runs every older lab |

## Nits

- **N1.** 0058:82: say "the read owner scope level". An assignment carries a read and an edit owner scope (ADR-0054 rule 13), and the condition source is a query, so the read one is meant.
- **N2.** 0058:82: the narrowed-scope item now goes only to the rule's owner. That is sound, since the owner answers for the rule and the daily count and the check result remain. Add it to the round-2 line of open-questions.md, which still says "a work item when the scope narrows" without saying for whom.
- **N3.** The lab README should give the one-session command of the standard load for t01 to t10 and t13 (round 5, N3), if it does not yet.

## Confirmed sound, over six rounds

- **Escalation.** Automation-allowed commands only create drafts. The owner consents, must hold every permission, field class and the read of the trigger, at validation and at each execution. Subjects outside the owner's scope are counted non-matches. Readers see values only within their own scope and classes, by omission. Three writers are barred from approving a rule's draft. No agent wakes an agent; a start on outside content gives a tainted run.
- **Loop guards.** Depth counts automation actions, capped at 3 and held by the database; chains are inherited by consumers and by agent runs started from events; one action per rule, chain and subject; the graph check knows discriminator values, treats undeclared emits as wildcards, and runs under a company lock at every activation, enable, rollback, demotion and upgrade.
- **Decision tables.** `unique` and `monotone` only; pairwise overlap; no-match and out-of-domain are typed outcomes; pinned versions inside the rule's content hash, held by triggers.
- **Lifecycle and evidence.** Versions are inserted as drafts and frozen after; pointers are held by triggers; every draft has a drafting window; backtests are strictly later, with minimum counts and recorded attempts; held-out cases are filtered for drafting runs through case tables and declared paths, with a closed tool list; gates read an allowlist of fields with no LLM lineage.
- **Bank cascade.** Safety caps can only be lowered; tied, unverified and third-party drafts never act; the parameters hash excludes the function version; evidence is marked outdated in the transaction of every pointer move and never re-arms by itself; a release is re-evaluated on the acting figure.
- **Layering and DDL.** `configuration` in layer 2 with its validators, `automation` in layer 5, hooks wired by `app`; company keys, forced row-level security and null-safe checks on all tables.
- **Consistency.** Accepted ADRs are changed by dated notes only, with the two changed commands named; the patch leaves every lab of ADR-0056, ADR-0057, ADR-0061 and ADR-0062 passing; no Vietnam-specific value in the core, no customer information.
- **For the author** (in open-questions.md): which agent triggers become configurable; the thresholds and minimums; whether an approved rule built on an LLM-read token may feed an auto-post; whether bank fees should ever auto-post; sandboxed extension functions.
