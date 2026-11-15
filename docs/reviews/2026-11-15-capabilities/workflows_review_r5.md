# Review r5 of ADR-0058 "Configurable workflows" and ADR-0059 "AI tuning and development of deterministic functions" — verdict: NOT YET

0 blocking, 1 should-fix, 3 nits. The should-fix is the shape of one stored value; nothing else is open.
File:line refer to the review copy (`base-integrated` with `apply_workflows.py` applied): "0058" = `adr/0058-configurable-workflows.md`, "0059" = `adr/0059-ai-tuning-and-development-of-deterministic-functions.md`, "DDL" = `design/DS-28-34-configuration-artifacts.sql`, "t22" = `lab/t22_workflows.py`.

What I ran:
- No git in `~/Projects/ERPMe`. A `/tmp` copy of `base-integrated`, and a second unpatched copy for comparison; the base was not touched.
- `apply_workflows.py` applies cleanly: 73 writes over 34 files, lab findings L-27 and L-28, each numbered once.
- With `--load`, each on its own fresh database: t22 137/137, t23 102/102, t12 189/189, t15 146/146, t17 117/117, t19 177/177, t20 184/184, t21 93/93, t11 163/163, t14 83/83, t16 99/99.
- With the standard load (extensions, `00_stubs.sql`, the `load_ds06.py` output, then the test without `--load`), each on its own fresh database, no load errors: t01 16/16, t02 6/6, t03 4/4, t04 5/5, t05 62/62, t06 60/60, t07 38/38, t08 46/46, t09 60/60, t10 69/69, t13 24/24. t01 to t06 give the same counts on the unpatched copy.
- `check_package.py` on the `DS-19-vietnam-tt99` package: RESULT PASS, SELF-TEST PASS.
- CSV check (my own, since the lab has no script for it): all 13 catalog files parse with a constant column count; no duplicate code in `invariants.csv`, `edge-cases.csv` or `work-item-kinds.csv`; 173 invariants, which DS-16 states.
- No run hit "out of shared memory".
- Cleanup done: every `erpme_lab_rv58_*` database dropped, both `/tmp` copies deleted. This file is the only file written.

## Round-4 items

| Item | Status | Note |
| --- | --- | --- |
| S1 stored scope instead of a hash | Fixed in mechanism, one gap | `automation_rule.owner_scope` jsonb is stored and the lab reads it; narrowing is defined; one open item per rule, and the stored scope changes only on resolution; lost values are named. The stored value is flattened too far: S1 below |
| N1 re-evaluation minimum | Applied | `reevaluation_min_cases` 50 on acting proposals; daily retry widening the window by a day up to `reevaluation_max_window_days` 180; if still too few, the evidence stays unmarked and the item stays open for a person. Sound: the re-evaluation recomputes proposals under the new function version, so going further back does not mix versions |
| N2 imports | Applied | `permissions` in rule 1 and in the ADR-0022 note |
| N3 one open item | Applied | Rule 9 |
| N4 older labs | Resolved | They pass with the standard load; see N3 below |

## Should-fix

**S1. The stored scope is one flat union, so an ordinary narrowing of one assignment is not seen (0058:82 rule 9; DDL `owner_scope`; t22 `effective_scope`, `lost_values`; ADR-0054 rule 15).**
- ADR-0054 rule 15: scopes combine per assignment (record scope AND owner scope), and across assignments a row is visible "when any assignment that grants the permission allows it".
- The stored value takes the union of branches, the union of warehouses and the single highest owner scope level over all assignments in force. That loses which level goes with which branch, and it counts assignments whose role does not grant the rule's read permission.
- Probe on the lab's own functions: the owner holds branch B1 at level `company` and branch B2 at level `company`. The B2 assignment is lowered to `own`. Before and after are identical (`branch_ids` B1, B2; level `company`); `lost_values` is empty and the job returns nothing. The owner's rule has lost every B2 document that is not the owner's own.
- The same happens when the only assignment that grants the condition source's permission in B2 ends while another role's assignment in B2 remains.
- Fix, in the same column:
  - store the scope as a set of cells, one per assignment in force whose role grants the permission of the rule's condition source, split to single values: (branch ID or `all`, warehouse ID or `all`, owner scope level, the resolved unit and employee IDs for `team` and `department`);
  - a stored cell is covered when some new cell has the same or `all` branch, the same or `all` warehouse, a level at least as high, and, for `team` and `department`, all of its employee IDs. The scope narrowed when a stored cell is not covered; the item names those cells. Anything else only updates the stored scope. Splitting to single values keeps an equal-reach reshuffle silent;
  - because the cells depend on the rule's condition source, compute them per rule, not per owner;
  - add to t22 the probe above, the lost permission-bearing assignment, and a swap of levels between two branches.

## Nits

- **N1.** 0058:82: with levels `team` and `department`, every colleague who leaves the owner's team removes an employee ID and raises an item for `company_owner`. That is a true narrowing, but it will be frequent. Say so, or raise it for the rule's owner in that case.
- **N2.** 0059:56: the retry "widens the window back in time by a day each run", so a company that needs the full 180 days waits 120 daily runs. Widen in one step to the smallest window that holds 50 acting proposals, up to the maximum.
- **N3.** The standard load for t01 to t10 and t13 works only when `00_stubs.sql` and the `load_ds06.py` output go through one session, because the stubs set `search_path`; loaded in two sessions every statement fails on a missing relation. The lab README should give the one-line command.

## Confirmed sound

- The scope is stored, not hashed; the job compares stored with recomputed scope; `owner_inactive` covers a disabled account and an assignment that lapsed by date; one item per rule, with the difference kept visible until it is resolved.
- The re-evaluation's pass rule, its minimum on acting proposals and its bounded retry.
- The patch applies to the integrated base without touching the accepted ADR-0056, ADR-0057, ADR-0061 and ADR-0062 work: every lab of those ADRs passes on the patched copy.
- Everything confirmed in rounds 1 to 4 still holds.
