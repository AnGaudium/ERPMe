# Review r3 of ADR-0058 "Configurable workflows" and ADR-0059 "AI tuning and development of deterministic functions" — verdict: NOT YET

0 blocking, 4 should-fix, 6 nits. The four are small and local; none reopens a design choice.
File:line refer to the review copy (`base-ds-uom` with `apply_workflows.py` applied): "0058" = `adr/0058-configurable-workflows.md`, "0059" = `adr/0059-ai-tuning-and-development-of-deterministic-functions.md`, "DDL" = `design/DS-28-34-configuration-artifacts.sql`, "DS-05" = `design/DS-05-platform.sql`.

What I ran:
- No git in `~/Projects/ERPMe`. Copies of `base-ds-uom` and `base-uom-sim` in `/tmp`; the bases were not touched.
- `apply_workflows.py` applies cleanly to both: 71 writes over 33 files each.
- Full lab on the ds-uom copy, each test on its own fresh database, and the same tests on an unpatched copy for comparison:
  - `t22_workflows.py --load` 124/124, `t23_ai_artifacts.py --load` 95/95;
  - t07 38/38, t08 46/46, t09 60/60, t10 69/69, t11 163/163, t12 186/186, t13 24/24, t14 83/83, t15 146/146, t16 99/99, t17 114/114: identical on the patched and unpatched copy;
  - t01 to t06 exit with an error at start under my invocation, identically on the unpatched copy, so the drafts do not cause it. I did not reproduce their own setups; they are not verified.
- On the `base-uom-sim` copy: t12 188/188, t22 124/124, t23 95/95.
- No run hit "out of shared memory".
- Catalogs: no duplicate codes; 155 invariants, matching DS-16, on both copies.
- Cleanup done: every `erpme_lab_rv58_*` database dropped, `/tmp/rv58`, `/tmp/rv58b`, `/tmp/rv58s` deleted. This file is the only file written.

## Round-2 items

| Item | Status | Note |
| --- | --- | --- |
| S1 silent scope non-match | Fixed, one gap | `automation_scope_skip` holds only rule, business date and a count that can only rise; check result `automation_owner_scope_limited`; DS-04 corrected. The narrowed-scope item has no trigger: S1 below |
| S2 hash in place of a value | Fixed | Value and result omitted with `is_class_filtered`; personal values under HMAC with a company key or omitted; the residue (an `acted` outcome tells the reader the conditions held) is stated in rule 11, the options table and open-questions.md. Acceptable |
| S3 held-out filtering | Fixed | Case-reference columns; closed drafting tool list by a registry CI check that refuses any query not registered as filtered (default deny; lab A25c); evidence, shadow, snapshot, execution and auto-post evaluation reads off drafting tool lists; `drafted_by_filtered_run` on evidence. See N1 |
| S4 "newer than" | Fixed in the data model, one gap | `policy_rule_version.shadow_evidence_outdated_by`, set once; `EnablePolicyRule` refuses outdated evidence and evidence whose recorded latest transition is not the latest. Who writes it across modules is not said: S4 below |
| S5 release under core defaults | Fixed, one gap | Null artifact and version only for a `reevaluation` naming the function; system creator only for that stage (lab D12b to D12d). The pass rule is undefined: S2 below |
| S6 pinned versions | Fixed | A rule version leaves draft only with pins that exist in the company and are `assisted` or `active`; a pinned version is not retired while a current or shadow rule version pins it. See N2 |
| S7 account rules | Fixed, one contradiction | Whole reference-shaped token, natural side, `cap_company_rule`, ambiguity suggests, own evidence basis. Conflict with ADR-0048 on unverified drafts: S3 below |
| N1 to N11 | Applied | Consent names the owner and is cleared on change; outcome precedence; order constraint added; minimums never lower the 300; one item per owner; retirement in force stated; the two changed accepted commands are listed in the Decision |

## Should-fix

**S1. Nothing triggers the narrowed-scope item, or `owner_inactive` when an assignment ends by date (0058:80 and 0058:82 rule 9; ADR-0054 rule 3 and its assignment rule; work-item-kinds.csv:53).**
- Both are raised by "a consumer of `automation`". ADR-0054 declares no event for `CreateRoleAssignment`, `UpdateRoleAssignment`, role changes or delegations, and the patch adds no note to it.
- An assignment ends when `valid_to` passes. No command runs, so no event can exist for it.
- "Narrows" needs something to compare with; no scope is stored for the rule.
- Today the only effect of a narrowed scope is that the daily count grows, which nobody is sent. For a lapsed last assignment the breaker's 20 refusals in a row still catch it, late.
- Fix:
  - store on `automation_rule` a hash of the owner's effective record and owner scope, set at activation, at an owner change and when the item is resolved;
  - a daily system job of `automation` recomputes it for the owner of every rule in force, raises `automation_owner_scope_narrowed` when the scope lost a dimension value, and disables with `owner_inactive` when the owner is no longer linked; this covers date expiry and role edits alike;
  - if immediate reaction is wanted too, add a note to ADR-0054 declaring the assignment and role events and let the consumer run the same check;
  - add the job to rule 27 and to t22 (W20d tests only a pure comparison).

**S2. "Auto-post continues only while the re-evaluation meets the function's thresholds" does not say which thresholds, and the worked example contradicts the obvious reading (0059:55 rule 4, 0059:152 rule 18, 0059:244 example).**
- The function's thresholds in rule 18 are promotion thresholds: suggested-decision precision of at least 95%. In the example the core defaults score 91.2%, and after release 1.3.0 "auto-post continued".
- A window with too few cases is not covered (the 60-day default for a quiet company).
- Fix: define the pass rule for a re-evaluation as the acting figure only: of the proposals at or above the auto-post rule's floor and below its maximum, at least ADR-0051 rule 18's 99% equal people's final results, and no proposal went to another partner. Below the function's small-company minimum of cases the result is `too_few_cases`: the evidence is not marked outdated, and the item says so. State it in rule 4 and assert the example's case in t23.

**S3. An account rule's draft under the unverified cap may be auto-posted; ADR-0048 says such drafts never are (0059:101 rule 10, 0059:235 EC-168, 0059:250 example; ADR-0048 rule 9 note; t23:250-253).**
- ADR-0048 rule 9's note: when no partner owns the counterparty's account, or the line names none, the draft is flagged `counterparty_unverified`, scores at most 85 "and is never auto-posted".
- Rule 10 applies that cap to an account rule without a partner (a bank fee scores 85), then says account-rule drafts are auto-posted once the auto-post evidence counts their basis. A company with a floor of 85 would then auto-post an unverified draft. The lab's `may_auto_post` has no unverified check.
- On the builder's choice of the cap: taking the 85 is the conservative reading and sound. It must bring the flag with it.
- Fix: say that a draft under the unverified or third-party cap carries ADR-0048's flag and is never auto-posted, account rules included; the evidence clause then applies only to account-rule drafts whose counterparty account a partner owns. Add the check to `auto_post_eligibility`, INV-682, EC-168 and t23. If bank fees should auto-post one day, that is a separate author question; add it to open-questions.md.

**S4. The outdated marker is written "in the same transaction", but no module is given the right or the means to write it (0059:80 rule 6, 0059:125 rule 13, 0059:176 rule 21; ADR-0022 rule 2 and its two notes; DS-05:351).**
- The column is on `policy_rule_version`, owned by `policy`. The writers are `configuration` (rollback, retirement, a new version taking force) and `automation` (demotion, failed re-evaluation).
- ADR-0022 rule 2 lets only `registry` import `policy`; the notes add no import and no hook for this, and no command or contract function is named. Nothing says how the writer finds the "dependent" rule versions.
- Fix: `EnablePolicyRule` stores the function code with the hash; `policy`'s contract gains `mark_auto_post_evidence_outdated(company, function_code, by_id)`, which sets the column on every enabled rule version whose evidence names that function; `configuration` declares a hook `artifact_in_force_changed` that `policy` registers and `app` wires, called inside the transaction of every pointer move, retirement and failed re-evaluation. Add it to the ADR-0022 note and to rule 2.

## Nits

- **N1.** 0059:42, 0059:146: a payment line or settlement reaches the bank line only through its payment, in two steps. Say "directly or through a declared path". Add a CI check derived from the schema: every foreign key to a declared case table is a declared case-reference column, and a property test that a filtered query returns no row tied to a held-out case. The registration flag is otherwise only a claim.
- **N2.** DDL `decision_table_version_check_in_use`: it refuses retirement only. A pinned version demoted to `shadow` by a direct command leaves a rule in force that fails at each execution; refuse that too, or say the rule is disabled with it.
- **N3.** 0059:80: "A new parameter set version taking force does the same." Sound: the hash differs anyway, and it prevents a later return to old evidence. Say whether raising the same version from `assisted` to `active` counts (it should not: the pointer does not move).
- **N4.** open-questions.md: flag the 60-day default window of a core-defaults re-evaluation and the unverified cap for account rules, with the other round-2 choices.
- **N5.** 0059:55: the 60-day window is a sound default (two statement months, as ADR-0051 rule 18 counts). Make it a declared value of the function, not a constant in the text.
- **N6.** 0058:96: say that the HMAC key is never rotated in place (keyed hashes would stop comparing), or that rotation keeps the old key for reading.

## The builder's own decisions

- **Unverified cap of 85 for account rules without a partner:** right cap, missing consequence (S3).
- **60-day re-evaluation window:** sound; see N4, N5. The pass rule is the open part (S2).
- **Marker set when a new version takes force:** sound; see N3.

## Confirmed sound

- The scope count holds no values and no subject: rule, business date, count; rows are never deleted and the count never falls.
- Omission with a marker replaces hashes everywhere a reader lacks a class; EC-167 and INV-686 follow.
- The drafting tool list is default-deny in the lab's model of the CI check, and INV-680 carries it.
- Stored evidence is set once and the marker is set once, so re-arming needs a new rule version; a demotion back to an earlier hash cannot re-arm.
- Re-evaluations of core defaults store without a version and with a system creator, and only that stage may.
- Pins are checked when a rule version leaves draft, for existence, company and state; a pinned version cannot be retired while in use.
- Account rules need a whole reference-shaped token and the natural side, never score without them, and two rules on a line suggest.
- Everything confirmed in rounds 1 and 2 still holds; numbering is unique on both bases.
