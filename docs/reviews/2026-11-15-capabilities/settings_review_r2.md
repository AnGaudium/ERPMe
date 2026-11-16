# Review r2: draft ADR-0063 "Configurable policy settings" (independent reviewer, ADR-0005), 2026-11-15

Verdict: **REVISE** (0 blocking, 3 should-fix, 2 nits).

References: `ADR` = drafts/ds-settings/0063-configurable-policy-settings.md, `DDL` = DS-28-settings.sql, `APPLY` = apply_settings.py (line numbers given by `grep -n` on the quoted text).

## What was run

- Fresh /tmp copy of base-integrated, `apply_settings.py`: 94 writes over 42 files.
- Fresh database per lab, `--load`: t24 111/111, t12 190/190, t15 146/146, t18 187/187, t19 177/177, t20 184/184, t22 140/140, t23 102/102. `check_package` (tt99): RESULT PASS.
- DDL probes: 24 inserts against the new trigger, 4 trigger-bypass routes and 6 row-level-security cases under a non-superuser role.
- Database, probe role and /tmp copy removed afterwards.

## Round 1 items

Fixed and verified: S1 (scope of the evidence floor; no exception, no question, INV-705 column empty), S3 (forged bounds, type, direction, allowed values and an undeclared scope are all refused; `extensions.wasm_enabled` true and `free_prose` refused), S4, S5, S6, S7, S8, S9, N1 to N4, N6, N7, N8 (the value true is refused by the database).
Trigger bypass routes refused for a plain role: disabling the trigger, `session_replication_role`, replacing the function, COPY.
Not fully fixed: S2 (below). N5 was fixed in a way that raises S2 of this round.

## Blocking

None.

## Should-fix

**S1. The asymmetric path now trusts `replaced_value` instead of the label (round 1 S2, residual).** DDL:101, DDL:202-209; ADR:29 ("whatever label it carries, a first value looser than the core default included").
The honest cases are refused (first value 1000 against default 200; 150 to 900 labelled `tighten`; bank-charge ceiling 0 to 500). The same loosenings are accepted with no proposal when the row names a false replaced value:
- first value 1000 naming 1000 as replaced: `neutral`;
- 150 to 900 naming 1000: `tighten`;
- bank-charge ceiling 500 naming 500: `neutral`;
- a code added to `cash.bank_charge.codes` naming a larger list: `tighten`;
- any loosening with `replaced_value` JSON `null`: `neutral` (it passes the "must name" test because it is not SQL null).
The draft leaves this to INV-702, which detects a day later; the trigger can prevent it with the lookup it already does for installation values.
Fix: the trigger derives the replaced value itself: the row in force for the same company, key, scope, scope reference and placeholder values on `effective_from` (rule 2's order), else the company row for a narrower scope, else the core default. It fills `replaced_value` when null, refuses a given value that differs, and refuses a JSON type other than the value's. Add lab cases for the five probes.

**S2. `installation_read_policy` departs from ADR-0017 rule 19 without a note, and the draft contradicts itself.** DDL:223-230; ADR:25 against ADR:29 and DDL:11 (both still say installation rows are readable only under `installation`).
Rule 19 says null-company rows are visible only under the explicit value `installation`, and that a missing setting sees nothing. Probe: a session with no company setting now reads the installation rows, including the operators' account ids and reasons. ADR-0017 is not touched by `apply_settings.py`.
Fix, one of: (a) keep rule 19 and read the maximum through a security-definer function in the `nativeflows_claim` pattern that returns only key, placeholder values, value and `effective_from` (the trigger and `get_setting` call it); or (b) keep the policy, append a note to ADR-0017 rule 19 naming this exception and its reason, and correct ADR:29 and DDL:11. (a) exposes less.

**S3. Rule 8's bound of false left stale text behind.** ADR:283 and the EC-183 row in APPLY; the answered question "A human-approved bank matching rule whose token an LLM read" in APPLY; ADR:83.
EC-183 (`must_succeed`) still says "after the company enables it by proposal ... its matches count toward auto-post", which the bound refuses (probe: `ck_setting_value_in_bounds`). The open question is ticked as "configurable, off by default; when a company enables it", which no company can do until the author rewords spec 03 rule 1.
Fix: EC-183 asserts that enabling is refused with `setting_out_of_bounds` and that the match stays `human_post`; the question becomes "Partly answered: designed, bounded false until the author decides the spec 03 wording (below)"; ADR:83 says the same.

## Nits

- **N1.** DDL:92, DDL:170-216: the trigger does not check that the keys of `placeholder_values` are the placeholders of the key (probe: a wake-up mode row with `{"zz": "1"}` accepted). Compare the key set with the `<...>` segments of `setting_key`.
- **N2.** DDL:193-201: a company row backdated before the installation row passes the maximum check (probe). `get_setting` still applies the maximum at read time, and backdating is INV-702, so say in the comment that the write check is a convenience and the read rule is the control.
