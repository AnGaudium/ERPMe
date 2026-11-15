# Review r3: draft ADR-0063 "Configurable policy settings" (independent reviewer, ADR-0005), 2026-11-15

Verdict: **REVISE** (0 blocking, 1 should-fix, 2 nits).

References: `ADR` = drafts/ds-settings/0063-configurable-policy-settings.md, `DDL` = DS-28-settings.sql.

## What was run

- Fresh /tmp copy of base-integrated, `apply_settings.py`: 94 writes over 42 files.
- Fresh database per lab, `--load`: t24 119/119, t12 190/190, t15 146/146, t18 187/187, t19 177/177, t20 184/184, t22 140/140, t23 102/102. `check_package` (tt99): RESULT PASS.
- DDL probes as a plain application role, with `setting_installation_value` owned by a no-login role that has neither superuser nor BYPASSRLS and one policy on null-company rows (the shape the DDL comment describes): 15 inserts against the trigger lookup, 6 function and visibility cases, 4 search-path cases.
- Database, probe roles and /tmp copy removed afterwards.

## Round 2 items

- **S1 fixed.** The trigger fills `replaced_value` and refuses a different one. Refused: a false replaced value, JSON null, a first value naming itself, a true replaced value with a false label, a backdated loosening, a category row looser than the company row. A backdated tightening against the core default is accepted and is harmless (the later row stays in force).
- **S2 fixed.** No installation row is visible to a company session or to a session with no company setting. The function returns only key, value and date, returns nothing for a company-held key, and works under an owner without BYPASSRLS; the trigger's maximum check works through it.
- **S3 fixed.** EC-183 is `must_reject:setting_out_of_bounds|must_succeed`; the question is "Partly answered"; ADR rule 8 agrees.
- **N1, N2 fixed.** Placeholder keys must equal the key's placeholders; the comment states that the read rule is the control.

## Blocking

None.

## Should-fix

**S1. Both new functions resolve their tables through the caller's search path, so a temporary table bypasses the trigger and feeds the security-definer function.** DDL:174-175 (`SET search_path = erpme`, unqualified `setting_value`); DDL:189, 195, 222, 227 (unqualified `setting_definition` and `setting_value`, no search path on the trigger function).
PostgreSQL searches `pg_temp` first for tables unless it is listed, also under `SET search_path = erpme`. Probes as a plain role with the default TEMPORARY privilege:
- a temporary `setting_definition` copied from the real one with `max_value` and `direction` changed: `automation.max_active_rules` 5000 is accepted without a proposal as `neutral` (bound 1000), with the session path `erpme, types, public` and with `erpme` alone;
- a temporary `setting_value` with SELECT granted to public: `setting_installation_value` returns the caller's row (`free_prose` as the installation maximum).
This is the round 1 S3 guarantee ("ties every copy to `setting_definition`") and the standard rule for SECURITY DEFINER functions.
Fix: schema-qualify every table in both functions (`erpme.setting_definition`, `erpme.setting_value`, `d erpme.setting_definition%ROWTYPE`) and the call `erpme.setting_installation_value`, and declare `SET search_path = erpme, pg_temp` on both functions. Add two lab checks that repeat the probes. The other trigger functions of the design share the unqualified style; that is outside this ADR, but a line in the DDL header or DS-18 that application roles get no TEMPORARY privilege would close it design-wide.

## Nits

- **N1.** DDL:172: EXECUTE on `setting_installation_value` is granted to PUBLIC by default, so a session with no company setting can call it. It returns only deployment maxima, so nothing leaks, but say in the comment that the roles step revokes it from PUBLIC and grants it to the application roles.
- **N2.** DDL:222-235: two concurrent inserts for one key each see the value in force before the other, so a tightening and a later-recorded smaller tightening can end as a net loosening without a proposal. Say in the comment that the command serializes changes per company and key (a row lock or an advisory lock), as the numbering helper does.
