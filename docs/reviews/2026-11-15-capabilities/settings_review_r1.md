# Review r1: draft ADR-0063 "Configurable policy settings" (independent reviewer, ADR-0005), 2026-11-15

Verdict: **REVISE** (0 blocking, 9 should-fix, 8 nits).

References: `ADR` = drafts/ds-settings/0063-configurable-policy-settings.md, `DDL` = DS-28-settings.sql, `CSV` = catalogs/settings.csv, `APPLY` = apply_settings.py, `T24` = t24_settings.py.

## What was run

- base-integrated copied to /tmp, `apply_settings.py` applied: 94 writes over 42 files; a second run fails on its first anchor with nothing written (as documented).
- Fresh database per lab, `--load`: t24 96/96, t12 190/190, t15 146/146, t18 187/187, t19 177/177, t20 184/184, t22 140/140, t23 102/102. `check_package` (tt99): RESULT PASS.
- Direct DDL probes on a loaded database (16 inserts, 8 row-level-security cases under a non-superuser role). Results are cited in the findings.
- Row-level security holds: no setting sees nothing; a company sees only its rows; installation rows only under `installation`; `company_ids` reads only; inserts for another company, of an installation row from a company session, and through `company_ids` are refused.
- Country content: none found in the ADR, DDL, catalog, notes, catalog rows or open-question additions.
- Database dropped and /tmp copy removed afterwards.

## Blocking

None.

## Should-fix

**S1. The bank-charge "exception" contradicts the architect's ruling.** ADR:61 (hard-lock row), ADR:64 ("the one stated exception ... (open question)"), ADR:245; APPLY:315 (INV-705 exception column), APPLY:444 (new open question), APPLY:483 (L-30 text); T24:457-458 (check A14 asserts the exception sentence).
Fix: scope the hard lock at ADR:61 to "learned or probabilistic matching paths"; replace ADR:64 with one sentence that a deterministic `bank_charge` rule (configured bank transaction code on that money account, debit, no third-party account, amount cap, period-end confirmation) is governed by its determinism and its cap, not by a statistical bound; drop the item from ADR:245, the open question, the INV-705 exception column and the L-30 wording; change A14 to assert the scope sentence.

**S2. The database does not hold the asymmetric path; it trusts the row label.** DDL:94, DDL:108-109; ADR:29 ("the database refuses ... a loosening without a proposal"), ADR:46.
Probes accepted, with no proposal and no approver: a first value looser than the core default labelled `initial` (`automation.max_active_rules` 1000 against default 200); a looser value labelled `tighten` (150 to 900); the same labelled `neutral`. The first case is the common one (the first raise of `cash.bank_charge.auto_post_ceiling` from 0), and rule 5 itself writes it as `initial`.
Fix: copy `direction` (and `direction_order`) and the replaced effective value (the core default for a first row) onto the row; add a check that derives tighten, loosen or neutral for numeric, boolean and ordered types and requires proposal and approver for a loosening; make "first row" `previous_value IS NULL` instead of a change kind. List types may stay command-checked, and the ADR should say so. Add lab checks for the three probes.

**S3. Copied type, bounds and scope are not tied to the definition.** DDL:82-92, DDL:110-121; ADR:29, ADR:252 and the INV-700 catalog row ("a database check").
Probes accepted: forged `max_value` 1e9 with value 999999; a company-only key at scope `product_category`; `value_type` boolean on an integer key; `extensions.wasm_enabled` true and `analysis.narrative_mode` `free_prose` through forged `allowed_values` (both are Phase 1 bounds the ADR relies on).
Fix: a `BEFORE INSERT` trigger on `setting_value` that compares `value_type`, bounds, allowed values (and direction, S2) with the `setting_definition` row and checks `scope_kind = ANY (scopes)`; or soften the three texts to "checked by the command". Lab D13 then also needs a forged-copy case.

**S4. "Proven at 95% confidence" is not what rule 10 proves.** ADR:61, ADR:84, ADR:256; CSV:10.
The rule of three needs zero errors. The gate allows (1 - rate) unchanged, so the exact one-sided 95% upper bound is 2.56% for 3 changed of 300 (the default) and 5.09% for 3 of 150 (the 2% setting). The hard lock "never above 2%, proven at 95%" is therefore not met even by the default.
Fix, one of: (a) keep the gate and today's 300 at 99%, and restate the lock and rule 10 as what holds: an observed error rate at most the ceiling over at least ceil(3 / rate) proposals, the 95% bound equal to the rate only when none was changed; or (b) keep the lock and add "exact 95% upper bound of changed / n at most 2%" to the gate, and then list it in rule 5 as a behavior change (300 with 2 or 3 changed no longer qualifies). (a) changes nothing on upgrade.

**S5. The bank-charge counterparty condition is weaker than the ruling.** ADR:79, ADR:257 (INV-705), the ADR-0048 note in APPLY; T24:465.
"Names no counterparty account owned by a partner" lets a debit to an unknown third-party account with a charge code qualify; the ruling and decision A3 say "no third-party account". The determinism argument of S1 depends on it.
Fix: "names no counterparty account (`counterparty_account_number` is null)", in the rule, the invariant, the note and the lab function, with a lab case for an unknown account.

**S6. Rule 7 contradicts its own bounds.** ADR:70-71; CSV:4.
"Nothing loosens past the core default" against `intake.trust.ocr_min_confidence` default 0.90 with bounds from 0.80; decision A1 allows loosening below the default with extraction-mapping evidence.
Fix: "loosening, also below the core default down to the lower bound, needs the evidence; nothing loosens past the bounds or the shape table".

**S7. Rule 5's list of behavior changes is incomplete.** ADR:48; the items at ADR:70, ADR:86, ADR:126, ADR:143, ADR:147.
Defaults or rules that do not reproduce the accepted ADRs and are not listed: an OCR confidence floor of 0.90 (ADR-0057 rule 17 has none, while ADR:69 says it "stands as written"); demotion judged only over at least 30 decisions (ADR-0059 rule 21 has no floor, and this one makes demotion slower); the flood guard of 500 per hour and the cap of 200 active rules (ADR-0058 has neither); pseudonymized analysis questions (ADR-0060 has none).
Fix: list them in rule 5 with their direction (four tighter, the demotion floor looser with its reason), and correct ADR:69.

**S8. ADR-0004 boolean naming.** DDL:137 `may_feed_gate`; ADR:138.
Fix: `is_gate_feeding` (the rule is `is_<adjective>` or `has_<noun>`); name the provider registry field of ADR:107 `is_training_on_customer_data` when it reaches a schema.

**S9. Two questions are marked answered but are not.** APPLY:418 with APPLY:280 and ADR:85; APPLY:406 with APPLY:445 and ADR:245.
(a) Promotion and demotion thresholds: only the case minimums and the window are registered; the 95% precision, the golden-case threshold, the demotion formula and the held-out share are not in the catalog, although the ADR-0059 rule 18 note says "the values are registered settings". Fix: register them, or mark the question partly answered and correct the note.
(b) The tainted catalog read is ticked while a new question asks the author to confirm the same reading, with the default already on. Fix: leave it open as "partly answered" until confirmed, or (if decision D3 stands as the answer) reduce the new question to the spec 03 wording, as for rule 8.

## Nits

- **N1.** DDL:22: the key pattern accepts `a<b` and `>x<` (read from the pattern, not probed). Use `^([a-z][a-z0-9_]*|<[a-z][a-z0-9_]*>)(\.([a-z][a-z0-9_]*|<[a-z][a-z0-9_]*>))*$`.
- **N2.** DDL:86, DDL:123; ADR:32: `placeholder_values` is not part of the lookup index or of the "value in force" rule, so two AIs of one day 00 key at company scope are told apart only by convention. Add it to both.
- **N3.** DDL:94: add `CHECK ((change_kind = 'initial') = (previous_value IS NULL))` if `initial` stays (probe: `initial` with a previous value accepted). A draft proposal and a backdated `effective_from` are accepted too; they are INV-701 and INV-702 work, and the DDL header could say so.
- **N4.** DDL:97, DDL:108; ADR:31: an installation value recorded by the startup step needs a `user_account` in `changed_by_user_id`, and an installation loosening needs a second one with no proposal. Say which accounts the operator path writes.
- **N5.** ADR:25: a company session cannot see installation rows (probe), so say how `get_setting` reads an installation maximum (loaded at startup, or a security-definer read).
- **N6.** CSV:40-42 against ADR:30; DDL:69: company options have `storage` `regime_setting` in the catalog but live in `setting_value` by rule 2; the comment at DDL:69 is unclear.
- **N7.** ADR:49-62: the table holds 10 locks, and the rules hold about 20 more "Hard:" bullets without reasons. Say that the table is the cross-cutting set and the bullets are scope limits of each setting, or move the real locks into the table.
- **N8.** ADR:74-77 against ADR-0029 rule 14: until the author rewords spec 03 rule 1, consider the bound `false` only for `cash.auto_post.accept_llm_originated_rules` (the pattern of `extensions.wasm_enabled`), so that no company enables it before the floor is reworded. Also state in rule 3 that a one-person company cannot loosen anything, the first bank-charge ceiling included.

## Judged and found sound

- One registry extending ADR-0016 rule 10; no second mechanism; no existing regime-option table is duplicated.
- ADR-0053: required regime keys stay fail-closed; purchase return keeps the regime keys instead of a core default (a justified departure from decision M3).
- ADR-0029 rule 14 for projections: the setting only narrows.
- ADR-0004 command and query names (t12 passes); `ListItemCandidate` renames the query of ADR-0062 correctly.
- Directions and bounds in the catalog read correctly for all 51 rows; no bound switches off a hard lock.
- The hard-lock table matches decision P4 plus the `llm_suggestion` lock.
