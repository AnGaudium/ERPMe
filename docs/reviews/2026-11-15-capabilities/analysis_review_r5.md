# ADR-0060 "Agent-assisted reporting and analysis" — independent review, round 5 (2026-11-15)

Base: a `/tmp` copy of `base-integrated` (ADR-0061 and ADR-0057/0062 accepted). The draft applies cleanly (62 writes, 31 files).
"Reproduced" means run against the lab's own `validate_narrative`, `render_narrative`, `precondition` and `resolve_saved`, or by evaluating the DDL check expression in PostgreSQL.

## Lab results

| Load | Scripts | Result |
| --- | --- | --- |
| `load_all.py`, fresh database each | t18 174/174, t17 117/117, t12 190/190, t15 146/146, t19 177/177, t20 184/184, t21 93/93, t14 83/83, t16 99/99, t11 163/163 | pass |
| Standard load (extensions, `00_stubs.sql`, `load_ds06.py` over DS-20 + DS-56 + DS-06) | t01 16/16, t02 6/6, t03 4/4, t04 5/5, t05 62/62, t06 60/60, t07 38/38, t08 46/46, t09 60/60, t10 69/69, t13 24/24 | pass |
| `check_package.py` | regime `tt99`: RESULT PASS | pass |
| Catalog CSV files | 15 files, every row has its header's field count; no duplicate code in the files this draft touches | pass |

No "out of shared memory" occurred. Database dropped and the copy deleted afterwards. No git was run in `~/Projects/NativeFlows`.

## Verdict: NOT YET

0 blocking, 5 should-fix, 5 nits. The number problem is closed: no model string reaches the output, and a number cannot enter the explanation. What remains is that some claim sentences are false although their precondition "held", because the precondition checks less than the sentence says. Each fix is small and local to rule 23.

## Should-fix

**S1. With two grouped dimensions, a sentence names one member of a cell that belongs to two.** (reproduced)
- Where: rule 23, narrative plan ("every member handle names a member of the row of a fact the step uses") and the claim table.
- The largest cell is (Item group A, November 2026). Both plans pass and render: "⟦November 2026⟧ has the largest Net revenue [1]." and "⟦Item group A⟧ has the largest Net revenue [1]." Neither follows from the cell: it is the largest combination, not the largest month or group. The same holds for `rose`, `fell`, `flat` and the contribution claims, and for a pinned currency or product, where `is_max` is taken within one member.
- Fix: remove member handles from the plan. Code renders `{member}` from the fact itself, with every member of the fact's row ("⟦Item group A⟧ in ⟦November 2026⟧"), and for a pinned basis adds the pinned member ("among ⟦USD⟧ amounts"). The model then chooses only claims and facts.

**S2. `same_direction` and `opposite_direction` accept facts of different measures, and the same fact twice.** (reproduced)
- A net revenue change for group A and a cost of goods sold change for group B render "Net revenue moved in the same direction for ⟦Item group A⟧ and ⟦Item group B⟧": the measure comes from the first fact only.
- The same handle in both roles renders "… for ⟦Item group A⟧ and ⟦Item group A⟧ [1] [1]."
- Fix: precondition: two distinct facts of the same measure and the same comparison.

**S3. The contribution claims overstate when contributions have mixed signs, when the total is zero, and on ties.** (reproduced)
- With A +80, B +70, C −100 and a total of +50, the plan renders "A explains most of the change", "B explains most of the change" and "C is the largest contributor to the change", all three together. C works against the change.
- +300 against a total of +50 also "explains most of the change".
- With a total change of zero, "is the largest contributor to the change" still renders.
- Ties: the rule does not say which cell is `is_max` when two members are equal; "the largest" is then not true of either.
- Fix:
  - `most_of_change`: the member's change has the sign of the total, the total is not zero, and the change is more than half of the sum of all contributions with that sign (other row included). At most one member can then qualify.
  - `largest_contributor`: the total is not zero and the contribution has the sign of the total; add a claim `largest_offset` for the largest contribution of the opposite sign.
  - `is_max` and `is_min` are set only when the extreme is unique; on a tie no cell is marked, for values and contributions alike.
  - Only member rows qualify, never the other row or the total.

**S4. The role set of saved narrative plans is incomplete and one role is positional.** (reproduced)
- Where: rule 26, "Running".
- `{member, measure}` resolves to the value cell only, so `rose`, `fell`, `flat` and the direction claims cannot be saved for a named member: there is no way to name a change, share or contribution cell.
- `first_change` is "the first change cell", which is a position in row order under another name; the rule exists to exclude that. The lab resolves neither `first_change` nor `largest_contribution`.
- With two grouped dimensions a single member key does not identify a cell.
- Fix: a saved reference is `{role}` or `{members: {<dimension>: <key>, …}, measure, kind}` with `kind` one of `value`, `change`, `share`, `contribution`, and the full coordinate of the row. Roles: `total`, `total_change`, `max`, `min`, `largest_contribution`, each with a measure. Drop `first_change`. A reference that resolves to no cell or to several drops its step. Add lab cases for each role and for a change cell by member key.

**S5. The row check on `narrative_plan` does not hold what its comment says.** (reproduced)
- Where: `DS-33-analysis.sql`, `ck_analysis_question_narrative_plan` and `ck_saved_analysis_version_narrative_plan`.
- Accepted by the check: a role key with free text (`{"facts": {"Revenue tripled to 500!": "f1"}}`), a numeric claim with an array of numbers (`{"claim": 12500, "facts": [500, 3.5]}`), and nested objects with free-text keys under `members`. The regular expression is applied to string values only, not to keys, and nothing fixes the types.
- None of this can be rendered, because the command validates against the claim catalog. But INV-413 says every stored plan holds only claim codes, roles and handles, and the saved-analysis column is written by people.
- Fix: `claim` is a string; `facts` and `members`, when present, are objects; every key at every depth matches the identifier pattern (a `$.**.keyvalue().key` test); every leaf is a string. Add the three rows above to the lab's refused cases.

## Nits

1. Connectors. After a dropped step, `[fell (dropped), also, rose]` renders "Also, Net revenue rose for ⟦Item group B⟧" as the first sentence; a plan that starts with a connector does the same. Not false, but odd. Render a connector only between two rendered sentences. A connector before a dropped step and a trailing connector are already discarded correctly.
2. The claim table gives "complete results only" for `largest_value` and not for `smallest_value`; the lab applies it to both.
3. A member label may itself read as a claim ("Tripled to 500" renders "Net revenue rose for ⟦Tripled to 500⟧"). Labels are company master data, not model text, and the chip marks them as names; say in rule 23 that the chip is the control, and that label text is never interpolated outside a chip.
4. With no member handles (S1) the plan step is `{claim, facts}`; the lab's rule that member handles may come from either fact's row then disappears.
5. `largest_value` on a result with one member row is true and empty; require at least two member rows.

## The five questions

- **Can a model-controlled string reach the output?** No. Claims, roles and handles are identifiers; an unknown claim, a free-text role, an extra field or a handle that was not offered makes the plan invalid (reproduced). The only text that is not a template is member labels and catalog labels, which code resolves. A member's label could carry a claim only if a person named a record that way (nit 3).
- **Are the preconditions sound?** `flat` is sound, also at a zero base: the band is then zero, so only an exact zero is "almost unchanged" and any positive change is `rose`. `most_of_change`, `largest_contributor` and ties are not (S3); the direction pair is not (S2); every member claim is unsound with two grouped dimensions (S1).
- **Do connectors mislead after a dropped step?** No false statement; an orphan "Also," can open the text (nit 1).
- **Is the saved-plan role set enough?** No (S4).
- **Is a key-facts-only answer usable for Phase 1?** Yes. The restatement, the table or chart and the key facts answer the question; the narrative adds a few checked sentences. It is the right trade for Phase 1, and the dropped-step metric shows where the catalog should grow.

## Round-4 items

| Item | Status |
| --- | --- |
| B1 numbers written as words | Closed by design: no model text reaches the person |
| S1 order and direction synonyms, uncited sentences | Closed by design: every sentence is a claim template with a precondition; S1 to S3 above concern those preconditions |
| S2 fallback rate and gate | Closed: free prose deferred behind an acceptance gate (open question); dropped steps counted per claim |
| S3 positional references in saved templates | Mostly fixed: by role or member key and measure, re-checked on every render; S4 above remains |
| Nits | Applied: member chips, as-of date in the `value` template, picked facts among the 12 offered and none twice |
