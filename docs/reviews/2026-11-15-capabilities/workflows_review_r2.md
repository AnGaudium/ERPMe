# Review r2 of ADR-0058 "Configurable workflows" and ADR-0059 "AI tuning and development of deterministic functions" — verdict: NOT YET

0 blocking, 7 should-fix, 11 nits. Base: branch `ds-uom` at ec0c126 (ADR-0056 accepted), with `apply_workflows.py` applied (69 writes over 33 files).
File:line refer to the review copy: "0058" = `adr/0058-configurable-workflows.md`, "0059" = `adr/0059-ai-tuning-and-development-of-deterministic-functions.md`, "DDL" = `design/DS-28-34-configuration-artifacts.sql`, "DS-04" = `design/DS-04-command-envelope.md`.

What I ran:
- `load_all.py` on a fresh database: 307 tables.
- `t22_workflows.py --load`: 112/112 pass. `t23_ai_artifacts.py --load`: 85/85 pass. Each on a freshly created database.
- My own probes on the loaded DDL (cited in S5, S6, N1 and the round-1 table).
- Cleanup done: `erpme_lab_rv58` dropped, `/tmp/rv58` deleted, repo untouched (clean, HEAD ec0c126). This file is the only file written.

## Round-1 items

| Item | Status | Note |
| --- | --- | --- |
| B1 scope and field classes | Fixed in substance | Owner checked at validation and execution; readers filtered. Two residues: S1, S2 |
| S1 writers and consent | Fixed | Three writers, INV-687; consent held by `ck_automation_rule_owner_confirmed` (probe); see N1 |
| S2 owner gone, breaker | Fixed | `owner_inactive` on last assignment; window on business time, declared a timer; 20 in a row |
| S3 refusals and atomicity | Fixed | Independent actions, by-design skips outside the breaker; EC-160 restated |
| S4 `start_agent` | Fixed | Allowed where the agent type accepts the table; acts for the workflow owner; INV-670 restated |
| S5 permission for work items | Fixed | The owner's read right on the subject; DS-04 step 4 says so |
| S6 graph completeness | Fixed | Discriminator values with wildcard; chain inheritance for agent runs; my probe is W26. Schedules are a warning only, see N6 |
| S7 checks where the set changes | Fixed | At execution, enable, rollback, demotion; `configuration_state` lock in class 3 (ADR-0027 note) |
| S8 completeness | Fixed | Not required; typed `decision_no_match`; pairwise overlap; proof capped at 100,000 box operations |
| S9 binding and content hash | Fixed, one gap | Pinned and inside the hash; the state of a pinned version is not held: S6 |
| S10 out-of-sample | Fixed | Window NOT NULL; minimum count and previews held by the database (probes); undated sources refused |
| S11 held-out cases | Partly | The case tables are filtered; linked and derived rows are not: S3 |
| S12 LLM-derived gates | Fixed | `is_gate_field` allowlist with lineage in CI |
| S13 cascade guards | Fixed | Tied is a safety cap and never acts; `cap_company_rule`; steps 3–4 score; see N4, S7 |
| S14 parameters hash | Fixed, one gap | Hash without the function version; line records four values. The release path has a hole: S5 |
| S15 re-arming | Fixed, one gap | Evidence must be newer than the last demotion; "newer" is not defined: S4 |
| S16 thresholds | Fixed | Per function, with minimums; `crm` stays a setting |
| S17 carriers | Fixed | One carrier for matching rules; report definitions get draft versions; see S7 |
| S18 layering | Fixed | Validators in `configuration`; hooks `artifact_checks` and `auto_post_eligibility` |
| S19 DDL guards | Fixed | Probes: insert as `active` refused; `draft → active` refused; leaving shadow and retiring clear pointers; cap checks null-safe |
| S20 deprecation item | Fixed | Kind `artifact_reference_deprecated`, move `deprecation_found` |
| S21 example figures | Fixed | 3,753 / 3,423 / 3,523 / 3,385 give 78.0%, 91.2%, 73.2%, 96.1%; I recomputed them |
| Nits N1–N14 | Applied | Depth has no default and needs ≥ 1 with a rule version; row-level security is written out and forced (probe) |

## Should-fix

**S1. Out of the owner's scope is silent, and that hides misconfiguration (0058:79 rule 9, 0058:96 rule 11, 0058:153 rule 23, DS-04 row `automation_owner_scope_insufficient`).**
- A subject outside the owner's record scope is "not evaluated, as a non-match" and leaves no record. A lost field class or permission is a refusal that reaches the breaker. The two cases get opposite treatment.
- So a company-wide rule owned by a person with one branch covers one branch, and nothing says so: validation passes, the replay counts only in-scope events, and the diff looks complete.
- When the owner's scope is narrowed later, the rule shrinks with it, with no record, no work item and no breaker.
- DS-04's row for `automation_owner_scope_insufficient` lists "the record or owner scope of the subject" as a refusal, and its "Automation chains" bullet applies step 5 to the owner. Both contradict the non-match of rule 9.
- Fix, keeping the non-match (it is the right behaviour for a branch manager's rule):
  - record a value-free execution `skipped_owner_scope` (subject and scope dimensions only; readers' filtering already hides it from the owner), or at least a daily count per rule;
  - validation and the replay return a check result `automation_owner_scope_limited` with the owner's scope and the number of window events outside it, shown in the proposal;
  - a consumer raises a work item for `company_owner` when the scope of an owner of a rule in force is narrowed;
  - correct the two DS-04 texts; flag the choice in open-questions.md.

**S2. A hash shown in place of a hidden value gives the value away (0058:95-97 rule 11, EC-167, t22:53).**
- Readers without a field class see "its hash". Condition values are amounts, percents, quantities and codes. An unsalted SHA-256 of `4.50` is found by trying the few thousand possible values, and equal values show as equal hashes. The lab's hash is unsalted and truncated.
- ADR-0017 rule 10 says the field is omitted. The stored row can keep the value and still omit it at read; "a stored record must keep" is no reason to show a hash.
- The same holds for personal values hashed at write.
- Fix: at read, omit the value and the per-condition result for a class the reader lacks, with a marker such as `is_class_filtered`; store personal values with a keyed hash under a company secret, or omit them too. State the residue: an `acted` outcome still tells such a reader that the conditions held.

**S3. Held-out filtering covers only the case tables (0059:42 rule 3, 0059:145-146 rule 16, t23:163-170).** A drafting run can still learn held-out outcomes through:
- **rows that point at a case:** the receipt or payment proposed or posted from a held-out line, its lines and settlements. They carry the partner and the settled items, which is the label. They have other IDs, so the ID-set check does not see them either;
- **stored results:** evidence figures and changed samples, shadow outcomes (they hold `case_id` and the outcome in force), monitor snapshots, `GetAutoPostShadowEvaluation` and automation executions. Rule 15 dates these reads but does not filter them;
- **no closed list:** nothing checks that every query on a drafting agent type's tool list can apply the filter. Only aggregates are refused.
- Fix:
  - the function's declaration names its case tables and the columns of other tables that reference a case; the query layer filters rows by those columns too, and the ID-set check maps `result_refs` through them;
  - a registry CI check: a drafting agent type's tool list holds only queries registered as held-out filtered; reads of evidence, shadow outcomes, snapshots and executions are off its tool list, or return only its own artifact's rows without per-case detail;
  - evidence records whether the drafter was a filtered run or a person, so the approver knows what "held-out" means for a person's draft.

**S4. "Evidence newer than the latest demotion" has no defined order (0059:77 rule 6, 0059:220 INV-682, ADR-0043 rule 14 note, DDL `artifact_transition`).**
- `artifact_transition` has only `recorded_at` (probe: no business date). ADR-0007 rule 10 forbids `recorded_at` as a condition, and a business date cannot order an enable and a demotion on the same day.
- Fix: no time comparison. The demotion, rollback or invalidation marks the dependent auto-post rule's stored evidence as outdated (a column on the policy rule version naming the transition), in the same transaction; `EnablePolicyRule` with new evidence clears it. `auto_post_eligibility` and INV-682 read the marker.

**S5. A function release under core defaults has no subject, no owner and no place for its re-evaluation (0059:53 rule 4, 0059:212 rule 28, 0059:237 example, DDL `artifact_promotion_evidence`).**
- A release no longer switches auto-post off, so `artifact_function_changed` and the re-evaluation are the only control. The common case is a company on core defaults with auto-post enabled under H0.
- There the "version in force" is no version: `artifact_version_id` is NOT NULL, so the re-evaluation cannot be stored (probe), and a company that never created a parameter set has no subject for the item.
- `created_by_user_id` is NOT NULL, but the monitor job writes the re-evaluation.
- Fix: allow a null `artifact_version_id` and `created_by_user_id` for stage `reevaluation` (checks: null version only for that stage, a person for every other stage); create the `parameter_set` row for each tunable function with the company (owner `company_owner`) or make the item's subject the policy rule when there is none; say that auto-post under H0 continues only while the re-evaluation meets the function's thresholds, else the rule's evidence is marked outdated as in S4.

**S6. Nothing says which decision table versions a rule may pin (0058:64 rule 8, 0058:138 rule 20, DDL `decision_table_version_ids`).**
- Probe: a rule version that pins a table version still in `draft`, and an ID that does not exist, leaves draft. A draft table can then change under a frozen rule, and INV-677 fails.
- A pinned version may be retired while a rule in force uses it.
- Fix: a rule version leaves draft only when every pinned version exists, belongs to the company and is out of draft and not retired (a trigger, or a link table `automation_rule_version_table` with keys); retiring a table version that a current or shadow rule version pins is refused. Add both to t22.

**S7. Matching rules that name an account are left out (0059:97 rule 10; ADR-0048 rule 9).**
- ADR-0048 rule 9: a company rule "maps a description token or a counterparty account to a partner or an account" (t08 B14: a bank fee to `bank_charge`). Rule 10 now says "a rule names the partner only; steps 3 and 4 still find and score the items". An account rule has no open items for steps 3–4, so its confirm-mode score, its evidence ("people matched every one of them to that partner") and its ambiguity rule are undefined.
- Fix: say that an account rule drafts the document to that account; in confirm mode its score is `cap_company_rule` under the counterparty caps; its evidence is later lines that people posted to that account; two rules naming different targets suggest.

## Nits

- **N1.** DDL:`automation_rule`: `owner_confirmed_at` survives an owner change (probe), so stale consent is not held. Store `owner_confirmed_user_id` and check that it equals `owner_user_id`.
- **N2.** 0058:80: "the old version stays in force until the change executes" should read "the old owner".
- **N3.** 0058:90: with no `done`, say whether a mix of `refused` and `failed` is `failed`.
- **N4.** 0059:72: the order constraints omit `score_account_amount` > `score_account_subset`. In the example, `show_min_score` 61 would also drop third-party drafts capped at 60, not only the 230 tied ones.
- **N5.** 0059:152: a minimum of 10 held-out cases at 95% means 10 of 10. Say that the minimums never lower ADR-0051 rule 18's 300 proposals.
- **N6.** 0058:112: a loop through a scheduled job is only a check result. Flag it in open-questions.md, with the hash-at-read and scope choices and `artifacts.proposal_ttl_days`.
- **N7.** 0059:212: `artifact_function_changed` names several owners, but a work item has one; say one item per owner, with the owner in its key.
- **N8.** 0059:116, 121: retiring the version in force clears the pointer in the trigger (probe). Say so in rule 13, with its transition and, for a parameter set, the marker of S4.
- **N9.** 0059:200: say who may call `CreateBankMatchingRuleVersion` besides the consumer (a person; an agent tool list or not), and name the identity command for `bank_matching_rule`.
- **N10.** 0059:103: `CreateReportDefinition` changes from `master_data_change` to a draft-only command by a note on ADR-0049 rule 11. That is a real change of an accepted command; list it in the Decision and in the step log at acceptance.
- **N11.** 0058:104: a run a person starts on an item that a rule raised begins a new chain; say that this is intended (a person is in the loop).

## The builder's decisions, as asked

- **Outcome set, `partial` counting toward the breaker:** sound. A refused or failed action is a fault whether or not another action succeeded, and the same-target index covers `partial`, so a later event in the chain does not retry. See N3.
- **Out of scope silent, lost class refused:** the non-match is right; the silence is not (S1).
- **Hashes applied at read:** filtering at read is right; showing a hash is not (S2).
- **Owner change proposal-bound for that field only:** sound; `UpdateAgentTypeSetting` is the precedent. See N1, N2.
- **`configuration_state` lock:** sound; one row per company, class 3, row-level security on.
- **Small-company minimums 50/30/10/30:** acceptable as flagged values; see N5.
- **`ConfirmAutomationRuleOwnership`:** sound, off agent tool lists. **`CreateBankMatchingRuleVersion`:** sound as the single carrier; see N9, S7.
- **New columns on `bank_statement_line`:** sound; the together-or-none check is null-safe and the columns are in the append-only list.

## Confirmed sound

- Everything in the round-1 list still holds on the new base: numbering is unique (INV-670 to INV-687, EC-156 to EC-167; 155 invariants, matching DS-16), no collision with ADR-0056's blocks.
- Depth counting, chain inheritance for agent runs and the database checks (0 to 3, at least 1 with a rule version, `depth_exceeded` only at 3).
- No agent wakes an agent; a rule's agent start on outside content starts a tainted run, as `agent_wake_up`'s does.
- Evidence: out-of-sample strict, minimum count, previews and re-evaluations never sufficient, held-out flag checked by hash in the database.
- The L1 and L2 worked examples compute, and the spec 03 rule 1 question on LLM-read tokens is in open-questions.md for the author.
