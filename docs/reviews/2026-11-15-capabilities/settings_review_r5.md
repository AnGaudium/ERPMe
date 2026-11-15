# Review r5: draft ADR-0063 "Configurable policy settings" (independent reviewer, ADR-0005), 2026-11-15

Verdict: **ACCEPT** (0 blocking, 0 should-fix, 1 nit).

## What was run

- Fresh /tmp copy of base-integrated, `apply_settings.py`: 97 writes over 44 files.
- Fresh database per lab, `--load`: t24 125/125, t12 190/190, t15 146/146, t18 187/187, t19 177/177, t20 184/184, t22 140/140, t23 102/102. `check_package` (tt99): RESULT PASS.
- Probes as a plain login role (not superuser) with SELECT and INSERT on `setting_value`, SELECT only on `setting_definition`, and TEMPORARY granted to keep the temp-table attempts possible; the read function owned by a no-login role without BYPASSRLS, EXECUTE revoked from PUBLIC.
- Database, probe roles and /tmp copy removed afterwards; the lab's own role `lab_t24_app` is not left behind.

## Round 4 items

- **S1 fixed.** The trigger takes `pg_advisory_xact_lock` on a hash of (company, key) and reads the definition with a plain SELECT.
  - An honest tightening works with SELECT only on `setting_definition`; a loosening without a proposal is still refused.
  - UPDATE, INSERT and DELETE on `setting_definition` are refused for the application role.
  - Temp-table attempts stay refused: a temporary `setting_definition` (also with `pg_temp` first), and temporary `pg_advisory_xact_lock` and `setting_is_looser` functions.
  - On three real connections as the plain role: another company changing the same key does not wait; a second change of the same key in the same company waits; once the first commits, the second (140 against the committed 100) is judged a loosening and refused.
  - The ADR-0022 rule 13 note agrees with ADR-0008 rule 9, which bans only session-level advisory locks because they survive a rollback.
- **N1 fixed.** The ADR-0017 rule 18 note is scoped to functions from DS-28-settings.sql on, with a backlog line for the earlier files.
- **N2 fixed.** D24x checks the comparison against the committed value, and the D24 checks run under a non-superuser role.

## Blocking

None.

## Should-fix

None.

## Nit

- **N1.** DS-28-settings.sql, `setting_value_check_insert`: the lock key is a 64-bit hash, so two different (company, key) pairs can collide. The effect is only an unneeded wait, never a missed lock; one clause in the comment would say so.

## Standing notes for acceptance (not findings)

- Left to the author as open questions by the draft: the spec 03 rule 1 wording for LLM-originated rules (the setting is bounded false until then), the spec 16 and spec 10 wording, the spec 17 seat list, and confirmation of the declared-projection reading (default on).
- Left to commands and invariants by design: that a loosening's proposal is approved and executed (INV-701), effective dates (INV-702), and that a scope reference names a record of the company.
