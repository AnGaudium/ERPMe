# ADR-0064 Production agent (DS-57): review round 1

Reviewer: Claude Fable 5.2 (independent, ADR-0005), 2026-11-15. Target: `drafts/ds-production/` (`0064-production-agent.md`, `apply_production.py`, `t25_production_agent.py`).

**Verdict: REVISE** (1 blocking, 7 should-fix, 11 nits).

## Test results

Copy of base-integrated in `/tmp`, `apply_production.py` applied (rc 0, 47 writes over 26 files), a fresh database per script.

| Check | Result |
| --- | --- |
| t25 `--load` | 83 / 83 |
| t12 `--load` | 190 / 190 |
| t15 `--load` | 146 / 146 |
| t16 `--load` | 99 / 99 |
| t20, t21 `--load` | pass (rc 0) |
| t22 `--load` | 140 / 140 |
| t13 on the standard load | 24 / 24 |
| check_package (tt99) | RESULT PASS |

DDL probes (after t25 `--load`):
- external reference: unique per company through a partial index; an import row without one and a non-import row with one are refused; an empty string `''` is accepted (N2).
- reservation transfer link: self-reference and a source that does not exist are refused; the key carries `company_id`; a transferred row with another item than its source is accepted, and so is a two-row cycle (S1).
- exception kinds: both production kinds need `production_order_id`, `item_id` and `warehouse_id`; other kinds with an order are refused; a second open row with the same `exception_key` is refused by `ux_planning_exception_open`.
- row-level security is off on all three changed tables in the lab load, so t25's D20 proves nothing (N3).

Cleaned up: database `nativeflows_lab_rv64` dropped, `/tmp/rv64*` removed. base-integrated untouched; no git run.

## Builder-flagged points

1. **Import auto-post against ADR-0051 rule 6: right in substance.** ADR-0043 rule 14 already provides `integration` postings behind `EnablePolicyRule` with shadow evidence, no LLM is on the path (floor 5 not engaged), the default is off, and the architect decided it (decision 8). A note on rule 6 is the right form. The evidence figures and the check list are not yet fixed (S6), and the figures must be listed for the author (B1).
2. **No new hard floors: right.** Nothing is added to ADR-0043 rule 9. Locks 1 to 4 restate existing mechanisms; locks 5 and 6 are registry attributes of a new command and of new work item kinds, which is technical.
3. **DS-17 count sentence: right, and older than this draft.** The base says 109 edge cases while the catalog has 168; after the apply it says 129 against 188. The +20 increment is consistent. Fix it in a separate catalog sweep (N11).
4. **DS-52 question "answered by rule 23": not right as stated.** Rule 23 makes reservation timing a setting and rule 6 leaves release with shortage to the policy table, but the question has six parts and the default is business behavior the author confirms (ADR-0005 item 11). Add a note on those two parts and keep the box open (B1).
5. **New tainted readings: right that they are new, wrong that they are added.** The scrap reason list is company data (ADR-0034 rule 11), so it is outside ADR-0050 rule 27 item 4. The apply script writes nothing to `open-questions.md` (B1).
6. **`TransferStockReservation` only from an approved proposal: right**, on the precedent of `UpdateAgentTypeSetting`. The command's own rules have gaps (S1).

## Blocking

**B1. Reserved points are claimed as recorded, but `open-questions.md` is not edited.**
- Where: `0064-production-agent.md:107`, `:165` ("added to the grouped question"), `:292` (budgets "join the existing open question"), `:305` ("Open questions: none added"); `apply_production.py:13-14` (no open question is written).
- Why: ADR-0005 acceptance rule 5 needs every reserved point listed. These touch item 7 (untrusted content, budgets) and item 11.
- Fix: have the apply script append to the existing entries, with no new question:
  - grouped spec 03 entry (line 42): (p) a tainted `production_capture` run reads its order's child rows through the subject column; (q) it is given the company's scrap reason codes as a closed list; (r) the numeric projection of S5.
  - agent values entry (line 45): the three budget rows and thresholds of rule 28, and the import's evidence figures (S6).
  - DS-52 entry (line 69): a note that reservation timing is now `production.reservation.mode` (default unchanged) and release with shortage is ranked by policy (rule 6); the box stays open.
  - reservation priority entry (line 12): rule 7 orders production demands by requested date, where ADR-0023 rule 13's interim is first come, first served; flag it interim.
  - Then correct `:305` to name the entries extended.

## Should-fix

**S1. `TransferStockReservation` can break INV-735 and is weaker in the database than in the rule.**
- Where: `0064-production-agent.md:223` (rules), `:312` (EC-200), `:339` (INV-734); `apply_production.py:262-270`, `:308`, `:336`; `t25_production_agent.py:633-646`, `:725`.
- Problems:
  - No cap at the target line's unreserved open requirement, so an approved transfer can over-reserve the target.
  - EC-200 and P48 assume a goods receipt changes the order's version. It does not, so a stale proposal executes after the shortage cleared.
  - The DDL accepts a transferred row with another item than its source (probe).
- Fix:
  - Add "at most the target's unreserved open requirement, computed under the order lock at execution" to rule 24 and to the DS-04 row; EC-200's reject becomes `reservation_transfer_invalid`.
  - Make the link `FOREIGN KEY (company_id, transferred_from_reservation_id, item_id, warehouse_id)` against a matching unique key; add same item, warehouse and lot to INV-734.
  - Require the proposal's evidence to show the source order's resulting shortage and pegged demand.
  - Add lab cases for the target cap and the stale proposal.

**S2. `uncovered` is not well defined.**
- Where: `0064-production-agent.md:64`; `t25_production_agent.py:161-171`.
- Problem: it is allocated over "all listed lines", so it changes with the query's filters, and draft and pending orders absorb free stock ahead of approved orders although the sweep serves only approved ones. The lab keys free stock by item only.
- Fix: allocate per (item, issue warehouse) over every component line of approved, not technically complete orders of the company, before any filter; lines of draft and pending orders get their value from what is left, in the same priority. Add a lab check that a filtered call returns the same values as the unfiltered one.

**S3. Shortage items are raised on the order's own view only.**
- Where: `0064-production-agent.md:94`.
- Problem: `short` lets every order count the same free stock. In mode `off`, and in `scheduled` for lines beyond the window, three orders needing 30 against 15 free raise no `production_component_shortage`.
- Fix: raise while a line has short or uncovered above 0 within the horizon, as `is_short_only` already reads (`:66`); add the case to t25.

**S4. The shortage-candidate computation is neither fully specified nor tested.**
- Where: `0064-production-agent.md:126-136`; `t25_production_agent.py:707-718` (only the default kinds and the handle check).
- Missing: per kind, the selection rule, the quantity, whether partial cover is offered, the order and cap of candidates, and the formula of the effect on the start date and pegged demand. Open cases: several source warehouses; which donor reservations and how much for `transfer_reservation`, and the donor's resulting shortage; the covered quantity and rounding for `split_order`; an `expedite` message from a stale planning run.
- Fix: state these per kind with a total order (kind order, then effect, then document number) and a cap; test in t25 that shuffled inputs give the same list and that it equals a brute-force enumeration on small cases.

**S5. Clean agent types are filtered on documents that came from capture drafts.**
- Where: `0064-production-agent.md:91` (rule 10), `:98-108` (rule 13), `:175` (rule 20).
- Problem: a capture draft stays effectively tainted after a person posts it (ADR-0029 rule 9). Its rows are left out for `production` and `production_variance` (ADR-0050 rule 28), so `shop_floor_posting_overview` shows gaps and the drivers no longer sum for agent callers (INV-739).
- Fix: declare the numeric projection of ADR-0050 rule 28 (IDs, quantities, dates, states, codes; no free text) for `shop_floor_posting_overview` and `ListProductionOrderVarianceDriver` for agent-run callers, as rule 8 does for pegging; record the reading (B1 item r).

**S6. The import's auto-post gate is underspecified.**
- Where: `0064-production-agent.md:226`, `:229`, `:345` (INV-740).
- Problems:
  - "The figures of ADR-0051 rule 18" are bank terms (statement months, another partner) with no stated analog.
  - "No yield, activity or duplicate check result" leaves `yield_above_previous_operation` and any other check result open.
  - The command needs `operation_confirmation` at `edit`, while the auto-post is a `Post`.
- Fix: state the figures (for example at least 300 import drafts over two calendar months, at least 99% posted unchanged, none posted to another order or operation); require a plan with no check result at all; say the integration credential needs `post` on the leaf for auto-post.

**S7. `ImportOperationConfirmations` is plural.**
- Where: `0064-production-agent.md:226`, `:263`, `:335`; the notes and INV-730 in `apply_production.py:295`, `:319`.
- Problem: every other command noun is singular (`ImportBankStatement`, `ImportSalesHistory`); ADR-0004 rule 17 takes a glossary noun.
- Fix: rename to `ImportOperationConfirmation` everywhere.

## Nits

- **N1** `0064:186`: with tolerance 0 and `warn`, `yield_above_tolerance` duplicates `yield_above_previous_operation` on every later operation. Raise it only for the first operation or when the tolerance is above 0.
- **N2** `apply_production.py:254`: an empty `external_reference` is accepted. Add `btrim(external_reference) <> ''`.
- **N3** `t25_production_agent.py:893`: D20 passes with row-level security off. Assert the flags, or drop the check and leave it to t15.
- **N4** `0064:97`, `:342`; `apply_production.py:363`: rule 12 says the job closes `production_standard_review`, while the catalog says resolution `person` and INV-737 omits it. Align them.
- **N5** `0064:33-37`: declare `wake_up: always` per claimable kind and no `configurable_triggers` (ADR-0058's note on ADR-0050 rule 12).
- **N6** `0064:195`, `:199-202`, `:214-215`: grace days, stalled days, horizons and feedback minimums only decide when an item is raised. Make them `neutral`, so a change needs no proposal (the author's direction on minimal locks).
- **N7** `0064:203-206`, `:210`: say which category a `product_category` value applies to (the order's main output product).
- **N8** `apply_production.py:401-412`: glossary rows are missing for the nouns of `RunProductionOrderCheck` and `ListShortageResolutionCandidate`; the verb Transfer's intent ("another account or owner") should name a reservation's demand line.
- **N9** `0064:83`, `:126`: pegging and candidates of a production order need `planned_order` at `read`; use `production_order`, or say why.
- **N10** `0064:118-123`: say that the sweep skips orders outside the workflow owner's record scope and counts them in its note, and that a run ending on its tool-call budget is resumed by the next trigger in the same priority.
- **N11** `apply_production.py:393-394`: the DS-17 count sentence is stale in the base (109 against 168 rows). Keep the +20 and log a separate fix.

## Judged and found sound

- No agent releases, posts, approves or sends: tool lists and INV-730 cover it, and floors 3 to 5 keep capture drafts with people.
- No model-written numbers: every L step returns handles, codes or checked text.
- Capture taint: tainted from the start, scope from a trusted order number only, the same response for a missing and an out-of-scope order, draft-only commands.
- Settings: every default lies inside its bounds and reproduces ADR-0034; the vocabulary matches the ADR-0063 draft; the duplicate window cannot be switched off; auto-post is off and loosens only by proposal.
- Naming: queries use Get, List and Evaluate only; the verbs Run, Transfer and Import exist; the new events follow ADR-0009 rule 22.
- No country content.
