# Review r4 of ADR-0058 "Configurable workflows" and ADR-0059 "AI tuning and development of deterministic functions" — verdict: NOT YET

0 blocking, 1 should-fix, 4 nits. The one should-fix is a single column and two sentences.
File:line refer to the review copy (`base-ds-uom` with `apply_workflows.py` applied): "0058" = `adr/0058-configurable-workflows.md`, "0059" = `adr/0059-ai-tuning-and-development-of-deterministic-functions.md`, "DDL" = `design/DS-28-34-configuration-artifacts.sql`, "t22"/"t23" = the lab files.

What I ran:
- No git in `~/Projects/NativeFlows`. Copies of `base-ds-uom` and `base-uom-sim` in `/tmp`; the bases were not touched.
- `apply_workflows.py` applies cleanly to both: 73 writes over 34 files each.
- Full lab on the ds-uom copy, each test on its own fresh database:
  - `t22_workflows.py --load` 128/128, `t23_ai_artifacts.py --load` 100/100;
  - t07 38/38, t08 46/46, t09 60/60, t10 69/69, t11 163/163, t12 186/186, t13 24/24, t14 83/83, t15 146/146, t16 99/99, t17 114/114;
  - t01 to t06 exit with an error at start under my invocation, as in round 3; t01 and t06 do the same on an unpatched copy, so the drafts do not cause it. Not verified.
- On the `base-uom-sim` copy: t12 188/188, t22 128/128, t23 100/100.
- No run hit "out of shared memory". No duplicate catalog codes; 155 invariants match DS-16 on both copies.
- Cleanup done: every `nativeflows_lab_rv58_*` database dropped, the three `/tmp` copies deleted. This file is the only file written.

## Round-3 items

| Item | Status | Note |
| --- | --- | --- |
| S1 trigger for the narrowed-scope item and `owner_inactive` | Fixed, one gap | The daily job `RunAutomationOwnerScopeCheck` reads assignments and their dates, so a lapse by date is caught without an event; `owner_inactive` works from it. The narrowed-or-widened decision cannot be made from what is stored: S1 below |
| S2 re-evaluation pass rule | Fixed | The acting figure only (99% at or above the floor and below the maximum, none to another partner); the example now passes on 410 of 412 (99.5%), which I recomputed; `too_few_cases` leaves the evidence unmarked. See N1 |
| S3 unverified drafts | Fixed | A draft under the unverified or third-party cap carries ADR-0048's flag and is never auto-posted, account rules included; INV-682, EC-168 and the example follow; the bank-fee question is in open-questions.md |
| S4 writer of the outdated marker | Fixed | `policy.contract.mark_auto_post_evidence_outdated(company, function_code, by_id)`; hook `artifact_in_force_changed` declared by `configuration`, registered by `policy`, wired by `app`, both in layer 2; `EnablePolicyRule` stores the function code; the ADR-0022 and ADR-0043 notes name it |
| N1 to N6 | Applied | Declared reference paths with a schema-derived CI check and a property test; a pinned table version can be neither retired nor demoted; `assisted` to `active` of the version in force does not mark; the window is the function's `reevaluation_window_days`; key versions are never rotated in place |

## Should-fix

**S1. The job cannot tell a lost scope value from a widened scope, because only a hash is stored (0058:82 rule 9; DDL:38 `owner_scope_hash`; t22:236-251).**
- Rule 9: "when the hash changed and the scope lost a dimension value, it raises `automation_owner_scope_narrowed`; a widened scope only updates the hash." A changed hash says only that something changed. Which values were there before is not stored anywhere.
- The lab shows the gap: `daily_owner_check(stored_hash, stored_scope, ...)` takes the stored scope as a second argument and computes `old - new` from it. The DDL and the ADR have no such column, so W20e passes on data the design does not keep.
- What the hash contains has two further faults:
  - it lists each assignment in force (branches, warehouses, owner scope), not the effective scope. Splitting one assignment into two with the same reach, or replacing one by an equal one, changes the hash with no change of scope;
  - for owner scope `team` or `department` it holds the level, not who is in the team or department. A reorganisation narrows what the owner sees and leaves the hash unchanged.
- The lab's lost test compares branches only; a lost warehouse or a lower owner scope (`company` to `own`) counts as "widened".
- Fix:
  - store the scope itself: `automation_rule.owner_scope jsonb`, the canonical effective scope (the union of branch IDs, the union of warehouse IDs, "all" where an assignment is unscoped, and the owner scope level with the resolved organisation unit IDs). Branch and warehouse IDs are not hidden values. Keep the hash only as a quick equality test, or drop it;
  - narrowed means: a stored branch, warehouse or organisation unit is missing from the new scope, "all" became a list, or the owner scope level is lower. Anything else that differs is widened and only updates the stored scope;
  - the item names the lost values, so `company_owner` sees what the rule no longer covers;
  - pass the stored scope from the same column in t22, and add cases for a lost warehouse, a lowered owner scope and a reshuffle with equal reach (no item).

## Nits

- **N1.** 0059:56: "below the function's small-company minimum of cases" does not say which minimum. The lab uses 50 and counts acting proposals (at or above the floor and below the maximum), not all cases in the window (t23:274-279). Name it as its own declared value. With 50 acting proposals, 99% means all 50. Say that a `too_few_cases` re-evaluation is repeated by the monitor until it can be judged or the next evidence replaces it; otherwise a small company's release is never judged.
- **N2.** 0058:82: `automation` reads ADR-0054's tables "through the `permissions` contract". Add `permissions` to `automation`'s imports in rule 1 and in the ADR-0022 note.
- **N3.** 0058:82: the stored scope is set "when an `automation_owner_scope_narrowed` item is resolved". Say that the daily job does not raise a second item while one is open for the rule (the open key covers it), and that it updates the stored scope only on resolution, so the item keeps showing the difference.
- **N4.** t01 to t06 could not be run under the combined loader on either copy. Not caused by these drafts, but the lab README should say how they are run.

## The drafter's own decisions

- **Narrowed raises, widened only updates:** the right rule; it needs the stored scope (S1).
- **What the hash contains:** per-assignment rows and scope levels are the wrong content (S1).
- **The minimum for re-evaluation:** 50 acting proposals is a sound conservative value; name it and repeat the check (N1).

## Confirmed sound

- `owner_inactive` from the daily job covers a disabled account and an assignment that lapsed by date, with the item for `company_owner`.
- The re-evaluation judges only the acting figure, so a function whose suggestions score 91.2% does not lose auto-post that still meets 99% where it acts.
- Unverified and third-party drafts never act, whatever the evidence counts; ADR-0048's guard holds for account rules.
- The marker is written inside the transaction of every pointer move, retirement and failed re-evaluation, through a hook between two layer-2 modules; no module imports `policy`.
- A pinned table version is neither retired nor demoted while a current or shadow rule version pins it.
- Everything confirmed in rounds 1 to 3 still holds on both bases.
