# ADR-0060 "Agent-assisted reporting and analysis" — independent review, round 4 (2026-11-15)

Bases: clean copies of `base-ds-uom` and `base-uom-sim` in `/tmp`; the draft applies cleanly to both (63 writes, 31 files each).
"Reproduced" means run against the lab's own `explain_check` and `render_prose`.

## Lab results

| Copy | Script | Result |
| --- | --- | --- |
| ds-uom | t07 38/38, t08 46/46, t09 60/60, t10 69/69, t11 163/163, t12 187/187, t13 24/24, t14 83/83, t15 146/146, t16 99/99, t17 114/114, t18 174/174 | pass |
| ds-uom | t01 to t06 | not runnable on the `load_all.py` schema; they fail the same way on the untouched base, so this is not the draft's doing |
| uom-sim | t12 189/189, t17 117/117, t18 174/174 | pass |

Fresh database for every `--load`; no "out of shared memory" occurred. Database dropped and both copies deleted afterwards.

## Verdict: NOT YET

1 blocking, 3 should-fix, 5 nits. The redesign is right: a cell value can no longer appear in prose, and every round-2 and round-3 probe is now refused or impossible. What is left is narrower: numbers and quantities written as words that the lists do not know.

## Blocking

**B1. Numbers written as words still pass.** (reproduced)
- Where: rule 23, "No digits outside markers"; `t18` `explain_check`.
- Other languages and scripts, in English prose: `had 三百 customers [1]` passes (CJK numerals are letters, not Unicode numbers), and so do `hai trăm` and `deux cents`. In a Vietnamese answer the reverse holds: English number words are not on the Vietnamese list.
- Exact quantities in plain English: `had no customers [1]`, `had none [1]`, `sold nothing [1]`, `had a single customer [1]` pass. These state zero and one. Also `several`, `many`, `a handful`, `the majority of sales`, `the bulk`, `a trio`, `a duo`.
- Character tricks: a zero-width space or soft hyphen inside "two", a Cyrillic "о" in "twо", full-width "ｔｗｏ", and "lO" all pass.
- Fix:
  - Normalize the rendered prose with NFKC, remove format characters (category Cf) before tokenizing, and refuse any letter outside the scripts of the output language.
  - Check every prose against the union of the word classes of all installed languages and the core English set, not only the output language's.
  - Add two classes: exact quantities (no, none, nothing, single, sole, lone, duo, trio and the like) and proportions (majority, minority, bulk, handful, several, many, few).
  - State the residual that then remains: a number word of a language that is not installed, written in the output script.
- If the author prefers an end to this series: in Phase 1 the model only chooses and orders key facts and picks connecting sentences from code templates. Then no model word reaches the answer. See S2.

## Should-fix

**S1. Order, direction and sign claims pass when they use other words, or no citation.** (reproduced)
- Passing without any citation: `{{m1}} dominates sales.`, `{{m1}} leads.`, `{{m1}} beats {{m2}}.`, `{{m1}} outsold {{m2}}.`, `{{m1}} is ahead of {{m2}}.` The one-row rule applies only to sentences that cite a cell, so an uncited sentence may compare any two members.
- Passing with a citation that says the opposite: `{{m1}} trails every other group [1]` and `{{m1}} ranks last [1]`, where the cell is the maximum; `{{m1}} collapsed [1]` and `sales were flat [1]`, where the change is positive.
- "largest" without a citation is refused, as intended; its synonyms are not.
- Fix: a sentence that names a member must cite a cell of that member's row, and a sentence names members of one row only, cited or not. Extend the direction class (soared, slumped, collapsed, flat, stable, improved, worsened, recovered) and add a rank class (last, next, lead, trail, dominate, beat, outsell, ahead, behind, exceed, win, lose), each bound to change cells or to `is_max`/`is_min` as now. Add this to "What remains": relations stated with words outside the lists.

**S2. The prose will often fall back, and nothing measures or bounds that.** (reproduced)
- Of 22 ordinary analysis sentences, 12 passed. Refused, for example:
  - "Monthly revenue for {{m1}} held steady" (`monthly`);
  - "This quarter {{m1}} carried the result" (`quarter`);
  - "grew over the period" (`over`);
  - "one of the strongest groups" (`one`);
  - "Figures are in company currency" (`currency`);
  - "Sales per customer were not analysed" (`per`);
  - "Most of the increase came from {{m1}}" (superlative without a maximum cell);
  - "The first half of the month" (`first`, `half`).
- "e.g." is refused twice over: `e` is a scale word, and the sentence splitter cuts at the abbreviation's full stop, which separates "fell" from its citation.
- A four-sentence text at this rate passes about one time in ten without a tightly prompted model. Each refusal costs two L3 calls, on the analysis seat for contribution plans, and the person then sees the key facts alone.
- Judgement: the fallback is acceptable for safety and for the person, because the key facts are the answer and the prose is commentary. The blocklist should stay broad; narrowing it reopens B1. What is missing is a gate and a cheaper default:
  - The evaluation suite reports the prose acceptance rate, and an agent type version asks for prose only when that rate is at least a stated threshold (for example 80%); otherwise L3 only chooses key facts.
  - Remove the pure time-grain words (`monthly`, `weekly`, `daily`, `yearly`, `annually`, `quarter` as a period) from the blocked classes: they name the grain, which the restatement already states, and are not quantities. Keep `quarter` as a fraction only after an article ("a quarter of").
  - Drop the single letters `e`, `m` and `k` as standalone words when followed by a full stop or apostrophe, and split sentences on a full stop only when a capital letter or placeholder follows.
  - Add a metric for prose refusals by error code.

**S3. A verified narration template of a saved analysis points at cells by position.**
- Where: rule 26 (`narration_template` of `saved_analysis_version`), rule 15 (`cell_id` "in row order"), rule 23.
- A saved analysis runs again each month. `{{ref:c3}}` and `{{m2}}` then mean whatever row is third or second that day, so a released sentence can come to name another member or cite another cell. The rule says the narration "is rendered by code" and does not say the checks run again.
- Fix: rule 23's checks run on every render of a saved template, with the same fallback to key facts; and a saved template refers to cells by role (`total`, `max`, `min`, `first_change`) or by member key and measure, never by position.

## Nits

1. A member whose label is only digits (an item coded "500") renders as “500” in quotes inside a sentence. Say that member markers are rendered as chips or links in the UI, so a label is never read as a quantity.
2. The `value` template shows `(<period>)`; for a balance or a current-snapshot measure it should show the as-of date.
3. Rule 22 L3: say that a fact handle the model picks must be one of the 12 offered (ADR-0050 rule 36), and that the same fact is not shown twice.
4. The unit class blocks ordinary words (`unit` in "business unit", `hour`, `point`, `score`, `pair`). Acceptable under S2's gate; list them in the prompt template so the model avoids them.
5. t01 to t06 need the older loader; note in the lab README that they do not run on `load_all.py`.

## The four questions

- **Can a numeric or quantitative claim still get through?** Yes, in words: other-language and CJK numerals, "no", "none", "a single", "majority", and character tricks (B1); order and direction through synonyms or uncited sentences (S1). Refused as intended: digits anywhere outside markers, `%`, ordinals, "twice", "half", "doubled", "tripling", "a third", "dozen", "twofold", "ten-fold", "double-digit", Roman numerals, "largest" without a citation, any value placeholder.
- **Is the blocklist too broad?** It refuses about half of ordinary sentences. That is acceptable only with the gate and the small narrowing of S2.
- **Does the DDL match the rule?** Yes, as far as a row can: both narration columns accept only `{{mN}}` and `{{ref:cN}}` and no ASCII digit or `%` outside them; `key_facts` is required for an answer and absent otherwise. Words and Unicode digits are the command's, as the comment says.
- **The builder's decisions.** Twelve facts offered and five picked: sound. Quoted labels with digits: sound, with nit 1. Extra blocked words: sound in direction, too wide on time-grain words and single letters (S2).

## Round-3 items

| Item | Status |
| --- | --- |
| B1 values built from placeholders | Closed by design: no value placeholder exists in prose; all earlier probes refused |
| S1 comparators, rate and unit words | Fixed: classes added; unit and currency words refused |
| S2 balance beside a second fact | Fixed: rule 12 and a lab case |
| S3 private saved analyses in D2 | Fixed: D1's set, release check per visibility set |
| Nits | Applied: missing year, master data permission for members without rows, shadow runs without `UpdateAnalysisAnswer` |
