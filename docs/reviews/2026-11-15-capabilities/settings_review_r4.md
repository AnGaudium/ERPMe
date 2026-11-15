# Review r4: draft ADR-0063 "Configurable policy settings" (independent reviewer, ADR-0005), 2026-11-15

Verdict: **REVISE** (0 blocking, 1 should-fix, 2 nits).

References: `DDL` = drafts/ds-settings/DS-28-settings.sql, `T24` = t24_settings.py, `APPLY` = apply_settings.py.

## What was run

- Fresh /tmp copy of base-integrated, `apply_settings.py`: 95 writes over 43 files.
- Fresh database per lab, `--load`: t24 122/122, t12 190/190, t15 146/146, t18 187/187, t19 177/177, t20 184/184, t22 140/140, t23 102/102. `check_package` (tt99): RESULT PASS.
- Probes as a plain application role holding TEMPORARY, with the read function owned by a no-login role without superuser or BYPASSRLS and EXECUTE revoked from PUBLIC.
- Database, probe roles and /tmp copy removed afterwards.

## Round 3 items

- **S1 fixed.** Both functions carry `search_path = erpme, pg_temp` and schema-qualified names. Refused: a temporary `setting_definition` with wider bounds (session path `erpme, types, public`, `erpme` alone, and `pg_temp` first); a temporary `setting_is_looser`; a temporary `setting_value` against the trigger's lookup of the value in force. The read function returns the real installation value with a temporary `setting_value` present, also with `pg_temp` first.
- **N1 fixed.** Without an EXECUTE grant the function is refused; the comment names the roles step.
- **N2:** serialized, but the chosen lock raises the finding below.

## Blocking

None.

## Should-fix

**S1. The `FOR UPDATE` lock on `setting_definition` needs UPDATE privilege on the definitions, which defeats the trigger.** DDL: the line `SELECT * INTO d FROM erpme.setting_definition WHERE setting_key = NEW.setting_key FOR UPDATE` in `setting_value_check_insert`, and the comment above the function; T24:1031 (D24w).
PostgreSQL requires UPDATE privilege for `SELECT ... FOR UPDATE`, and the trigger runs as the inserting role. Probes as a plain role:
- with SELECT only on `setting_definition`, every insert into `setting_value` fails with "permission denied for table setting_definition", an honest tightening included;
- with UPDATE granted so that inserts work, the same role rewrites a definition (`max_value` of `automation.max_active_rules` set to 1000000), which is the forgery the trigger exists to stop; rule 1 says nobody edits definitions.
The lab does not see it because it runs as a superuser. The row lock also serializes one key across all companies.
Fix: replace the row lock by `PERFORM pg_advisory_xact_lock(hashtextextended('setting_value:' || coalesce(NEW.company_id::text, 'installation') || ':' || NEW.setting_key, 0))` before the lookups (no privilege needed, per company and key), read the definition with a plain SELECT, and state in the DDL header that application roles get SELECT only on `setting_definition`. Run D24u, D24v and D24w under a non-superuser role with SELECT and INSERT only, so the lab meets this case.

## Nits

- **N1.** APPLY, the ADR-0017 rule 18 note: it says every trigger function and security-definer function pins `search_path = erpme, pg_temp`, but the trigger functions of the other DDL files do not yet. Say "from DS-28-settings.sql on; the earlier files follow in DS-18", or add a backlog line.
- **N2.** T24:1031: D24w proves the wait by a lock timeout only. After the fix, also assert that the second change, once the first commits, is compared with the first one's value (a loosening against it is refused).
