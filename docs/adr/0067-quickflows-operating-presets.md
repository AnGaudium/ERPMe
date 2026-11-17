# ADR-0067: QuickFlows mode: operating presets for small teams

Status: proposed (2026-11-17) under ADR-0005 (builder Claude Opus 5.5).
Design items: DS-28 (settings, policy and configuration), DS-30 (UI), DS-15 (segregation of duties), DS-04 (errors), DS-20 (company), DS-16 and DS-17. Related decisions: D2, D5. Principles 2, 3, 12. ADR-0004, ADR-0005, ADR-0008, ADR-0009, ADR-0010, ADR-0017, ADR-0023, ADR-0029, ADR-0031, ADR-0033, ADR-0034, ADR-0038, ADR-0040, ADR-0043, ADR-0044, ADR-0047, ADR-0050, ADR-0054, ADR-0055, ADR-0063, ADR-0065; spec 02, 03, 14, 18.

## Decision

The author's proposal of 2026-11-17: a **QuickFlows mode** lets a lean company work as fast as the entry-level systems it compares with (MISA, Odoo) without breaking the safety and audit invariants. A lean company here has one to three key people, or is a fast-moving workshop. The chief architect's decisions on the proposal are applied here.

**A preset, not a branch.** QuickFlows is an **operating preset**: a named, versioned bundle of values for things the core already has: settings of the ADR-0063 registry, seeded policy rules (ADR-0043), company settings with their own commands, and defaults the setup flow fills on new records. Applying a preset is an ordinary series of commands through their usual paths, recorded with the preset code and version. No business code reads the preset name, and no code says `if quickflows`. A value changed after the preset is applied simply diverges, and a query shows the drift. Two presets are seeded: `standard` (the core defaults) and `quickflows`.

**Three speed levers:**
- **One-click post.** A company setting `ui.post_review` (`always`, the default, or `on_exceptions`). With `on_exceptions`, the Post button still simulates, and the client executes at once with `expected_plan_hash` when the server reports no review reason: a human actor, no effective taint, no agent-written version, no check results, no policy flag, and an amount at or below `ui.post_review_max_amount`. Otherwise the plan panel opens as today. Simulate, execute and `plan_hash` stay intact; the execution is marked in its audit record. The implementer sets the maximum at setup; until then it is 0 and every post is reviewed.
- **Governance for thin teams.** Posting from draft below a risk amount is policy configuration that the core already supports (ADR-0009 rule 11; ADR-0043 rule 7): the preset seeds rules that require approval from the risk amount up and on warning flags. In the small-company mode (ADR-0054 rule 20), the owner or chief accountant may approve an untainted draft that an agent wrote on their behalf from an event or schedule, as a recorded segregation exception reviewed at period end, under a reading of spec 03 rule 5 decided by the author's delegation to the chief architect (2026-11-17). In the same mode, the person a tainted run acted for may clear its versions one by one, each clearance a recorded exception.
- **Lean defaults.** No bin management and direct outbound for new warehouses (already the core defaults, ADR-0023, ADR-0031), and backflush at receipt for new bill-of-materials components (ADR-0033, ADR-0034).

**Setup before go-live.** ADR-0063 rule 3 leaves a one-person company unable to loosen any setting, so QuickFlows would be impossible after go-live for exactly the companies it targets. Before go-live, which this ADR defines as "no journal entry outside the migration period yet", the owner may acknowledge an implementer, who then sets loosenings without a second approver. After go-live the asymmetric path applies again. A work item lists the setup loosenings for the owner's review at the first period close.

**What does not change:** the hard locks of ADR-0063 rule 6, simulate-then-execute with `plan_hash` (ADR-0008 rules 9–13), the policy floors (ADR-0043 rule 9), taint persistence (ADR-0029 rules 9–11) and its clearance rule outside the small-company mode (rule 8), agents only drafting, and spec 18's single edition: QuickFlows is a preset, not an edition.

### Rules

**Scope and name**

1. QuickFlows is the name of the seeded preset `quickflows`, not an edition, a module or a flag.
   - **No preset branches.** No handler, consumer, job, policy function or query outside the registry's preset code reads a preset code, and none reads `setting_value.preset_code` to decide anything. A CI check fails on the literal preset codes anywhere under `backend/src/` except `registry`'s preset loader and its tests.
   - **One edition.** Spec 18's "one edition only" stands: every company can apply every preset.

**Operating presets**

2. A preset is installation data, registered in code by `registry` like setting definitions (ADR-0063 rule 1) and written at startup into `setting_preset` and `setting_preset_item` ([DS-28-settings.sql](../design/DS-28-settings.sql)).
   - **Identity.** `preset_code` (lowercase, one segment) and `preset_version` (an integer, raised on any change of the preset's items). A version is never edited.
   - **Items,** one per (preset, version, `item_kind`, `item_key`):
     - `parameter`: a value the implementer enters when applying, with its type and bounds (for example `risk_amount`, an amount in company currency, at least 0). A parameter has no default, because an amount depends on the currency (ADR-0063 rule 9).
     - `setting`: a registry key at scope `company` and its value, or `param:<name>`.
     - `policy_rule`: a policy rule template (rule 15): actions, document type, actor kind, conditions, effect and approval procedure.
     - `command_setting`: a company setting that has its own commands outside the registry, such as `permissions.small_company_mode` (ADR-0054 rule 20), applied only through those commands and their checks.
     - `record_default`: a field value the setup flow fills when it creates records of a kind (rule 18).
   - **The catalog.** [setting-presets.csv](../catalogs/setting-presets.csv) (owner DS-28) lists every item, seeded now and generated from the registry once `registry` exists, like the settings catalog. Agents read presets as reference data through `ListSettingPresetItem`.
3. Hard rules, checked at registry startup and by the lab:
   - **Inside the registry.** A `setting` item names a registered key with storage `setting_value`, scope `company`, a leaf that is neither `package` nor `operator`, and a core default that is not `fail_closed`. Its value lies within the definition's bounds; a parameter's bounds lie within the bounds of every key it fills.
   - **No hard lock.** No item touches a cross-cutting hard lock of ADR-0063 rule 6, a key whose loosening outdates auto-post or promotion evidence, an agent type's mode, a data-processing permission or an auto-post rule. A `policy_rule` item never has effect `allow`, so a preset never lifts a non-human baseline (ADR-0043 rule 7) or lets a non-human post.
   - **Standard covers the others.** `standard` lists, at its core default, every `setting`, `command_setting` and `record_default` key that any other preset lists, so a company can always return to the core values. `standard` has no `policy_rule` items: the core seed of ADR-0043 rule 15 is the standard.
   - **A looser preset is a loosening.** Applying a preset never bypasses ADR-0063 rule 3: each setting item is compared with the value in force and is a tightening, a loosening or neutral like any other change.
4. Applying a preset:
   - **The plan.** `EvaluateSettingPreset` (preset, version, parameter values) returns, per item, the effective value in force, the preset's value, the change kind (`tighten`, `loosen`, `neutral` or `unchanged`) and the path: `direct`, `setup` (rule 9) or `proposal`. A parameter outside its bounds returns `setting_out_of_bounds`.
   - **The commands.** The setup flow sends the tightening, neutral and setup-path items as one command batch (ADR-0008 rule 20): `UpdateCompanySetting` per setting item, `CreatePolicyRule` and `EnablePolicyRule` per policy rule and action, and the item's own command per `command_setting` item. After go-live it sends the loosening setting items as one change proposal (ADR-0063 rule 3). Every item keeps its own permission, leaf and check.
   - **The record.** `UpdateCompanySetting` takes optional `preset_code` and `preset_version`, stored on the `setting_value` row; the other commands of a preset batch carry the preset code and version in their audit record's `reason` (ADR-0038 rule 2).
   - **Additive.** Applying a preset sets the items it lists. It never removes or disables a rule, setting or record another preset or a person made, and it skips items whose value is already in force. A `command_setting` item whose command refuses (for example `small_company_mode_not_allowed`) is reported in the plan and left out of the batch, which runs all or nothing (ADR-0008 rule 20).
5. Drift and later changes:
   - **Divergence is normal.** A person may change any value afterwards through the usual path. Nothing re-applies a preset by itself, and no value depends on the preset at run time.
   - **The drift view.** `ListSettingPresetDrift` lists, for the preset and version a company applied last (the latest `setting_value` row with a `preset_code`), the `setting` and `command_setting` items whose value in force differs from the preset's, with the change that made it differ.
6. The seeded presets, version 1:

   | Item kind | Key | `standard` | `quickflows` |
   | --- | --- | --- | --- |
   | `parameter` | `risk_amount` | none | entered at application; amount in company currency, at least 0; the approval threshold |
   | `setting` | `ui.post_review` | `always` | `on_exceptions` |
   | `setting` | `ui.post_review_max_amount` | `0` | not listed: the implementer sets it at setup (rule 11) |
   | `command_setting` | `permissions.small_company_mode` | `false` | `true`, through `EnableSmallCompanyMode` while its bound holds |
   | `policy_rule` | `quickflows.from_risk_amount` | none | `submit` and `post`, every document type, actor `human`, `require_approval` with `standard` from `amount_company_min` = `risk_amount` |
   | `policy_rule` | `quickflows.credit_exceeded` | none | `submit` and `post`, every type, actor `human`, `require_approval` with `standard` when `is_credit_exceeded` |
   | `policy_rule` | `quickflows.cost_unknown` | none | the same when `is_cost_unknown` |
   | `policy_rule` | `quickflows.price_below_cost` | none | the same when `is_price_below_cost` |
   | `record_default` | `warehouse.is_bin_managed` | `false` | `false` |
   | `record_default` | `warehouse.outbound_flow` | `direct` | `direct` |
   | `record_default` | `bill_of_materials_component.consumption_method` | `manual` | `backflush_at_receipt` |

**Setup before go-live**

7. The setup phase:
   - **Checked first.** ADR-0044 defines no company-level go-live state, only the migration's states (rule 1), and opening documents post during a migration (rule 3). The phase is therefore defined here.
   - **Definition.** A company is in its setup phase while `company.first_operating_posting_at` is null. The ledger sets it, once, in the transaction of the first journal entry of the company whose posting period lies outside the migration fiscal year (ADR-0044 rule 2), in the pattern of `account.has_posting` (ADR-0010 rule 12): an `UPDATE … WHERE first_operating_posting_at IS NULL`, which locks the company row. Opening documents of a migration do not end the phase; the first ordinary posting does.
   - **Serialized.** A setup-path command reads the company row `FOR SHARE` through `registry`'s contract before it writes, so it and the first operating posting cannot overlap. The phase never reopens.
   - **Existing companies.** The upgrade that adds the column sets it from the company's first such journal entry.
8. The owner's acknowledgement:
   - **`AcknowledgeCompanySetup`** (`registry`, `human_only`, `master_data_change`, leaf `company_setting` at `full`; the actor holds an assignment of the `owner` role template): names the implementer, a user account with an assignment in the company, which may be the owner. It writes a `company_setup_acknowledgement` row (owner, implementer, reason, `acknowledged_at`).
   - **`RevokeCompanySetupAcknowledgement`** by an owner sets `revoked_at` once.
   - **Only before go-live.** Both are refused with `setup_phase_closed` once the phase has ended.
9. Setup-path loosenings:
   - **Accepted directly** by `UpdateCompanySetting` with a `setup_acknowledgement_id` when all hold: the company is in its setup phase; the acknowledgement is the company's and not revoked; the actor is its implementer and holds `edit` on the key's leaf; the key's scope is `company` or narrower, never `installation`; and the key's `outdates` is `none`. Otherwise `setup_phase_closed` (after go-live) or `setup_acknowledgement_invalid`.
   - **No second approver.** The row records the acknowledgement instead of a proposal and approver; a tightening or neutral change made in the same batch carries no acknowledgement. Bounds, installation maxima and every other check of ADR-0063 rules 2–4 apply.
   - **Kept on the ordinary path:** keys that outdate auto-post or promotion evidence, agent promotions (ADR-0050 rule 14), data-processing permissions (ADR-0057 rule 20) and policy rules that let a non-human post (ADR-0043 rule 14). Before go-live there is no evidence for them anyway.
   - **The database holds it.** The `setting_value` trigger accepts a loosening without a proposal only with an active acknowledgement of the same company whose implementer is `changed_by_user_id`, for a key with `outdates` `none`, while `first_operating_posting_at` is null.
10. After go-live:
    - **Back to the asymmetric path.** ADR-0063 rule 3 applies again in full; a one-person company cannot loosen any setting.
    - **The review.** The first setup-path loosening raises `setup_loosening_review` for `company_owner` (open key: the company); later ones add evidence. It lists each loosening with its old and new value, and, while `ui.post_review` is `on_exceptions` and `ui.post_review_max_amount` is still 0, a reminder that the maximum is unset. The close checklist of every period shows it while it is open, without blocking the lock, like `segregation_review_due` (ADR-0054 rule 20). The owner resolves it after reviewing the list.

**One-click post**

11. Settings (ADR-0063 rule 1; [settings.csv](../catalogs/settings.csv)), company scope, leaf `company_setting`:
    - **`ui.post_review`:** `always` (default, today's behavior) or `on_exceptions`. `always` is tighter.
    - **`ui.post_review_max_amount`:** an amount in company currency, default 0, at least 0, lower is tighter. With 0 every post is reviewed, whatever `ui.post_review` says.

    Switching to `on_exceptions` or raising the maximum is a loosening: by proposal after go-live, or on the setup path before it.

    **The maximum is the implementer's.** The preset `quickflows` sets `ui.post_review` to `on_exceptions` but not the maximum, because a preset cannot know the company currency. The setup flow asks for it next to the preset's `risk_amount`; until it is set it stays 0, so every post is reviewed, and `setup_loosening_review` reminds the owner (rule 10).
12. Review reasons. The simulate response of a `Post<Type>` command carries `review_reasons`, computed by the dispatcher from the run, never by the client (ADR-0040 rule 2). It is empty only when all hold:
    - `ui.post_review` is `on_exceptions` on the business date, and `ui.post_review_max_amount` is above 0;
    - the actor kind is `human` (never `agent`, `integration` or `system`);
    - the command is a single command, not a batch item or a bulk review (ADR-0042 rule 12 note), and its type is not a correction type (ADR-0009 rule 23);
    - the document's current version has no effective taint (ADR-0029 rule 9);
    - no version of the document was written by an agent run and none carries an origin agent run (ADR-0017 rule 16), so a person always sees an agent's draft before posting it (spec 14);
    - the response has no check result, hashed or not (ADR-0040 rule 10), so negative stock, capacity and similar warnings always show;
    - the policy decision is `allowed` without confirmation, and no boolean condition of the policy input is true (`is_credit_exceeded`, `is_price_below_cost`, `is_price_outside_list`, `is_cost_unknown`, `is_match_exceeded`, `is_direct_expense`, `is_bank_account_recent`, `is_rate_unusual`, and any added later);
    - the policy input's amount in company currency is at or below `ui.post_review_max_amount`.

    The codes are `post_review_always`, `actor_not_human`, `not_single_post`, `correction_document`, `document_tainted`, `agent_written`, `checks_present`, `policy_flag` (with the flags), `policy_outcome` and `amount_above_maximum`.
13. Execution without the panel:
    - **The call.** When `review_reasons` is empty and the setting is `on_exceptions`, the client sends `mode: execute` at once with `expected_plan_hash`, the simulation's `as_of_date` and the new envelope field `is_review_skipped: true` (optional, default false, outside the request hash like `mode`).
    - **Checked again.** The dispatcher recomputes the review reasons in the execution, after the handler and before commit. If any applies, it rolls back and returns `post_review_required` with the reasons, and the client shows the plan panel. An agent, integration or system actor that sends the field gets the same error.
    - **The record.** `audit_record.is_review_skipped` is true. The response, with the plan and `plan_hash`, is stored as for every execution (ADR-0008 rule 16), and the document history shows the plan and "posted without review".
    - **Principle 2.** Every post is still simulated and executed against its `plan_hash`; only the display of the plan moves to the exceptions. Decided by the author's delegation to the chief architect (2026-11-17): Principle 2 holds. The plan is still computed, re-checked by the server before commit, stored and viewable; a person chose to post, and every non-routine condition forces the review. The core default stays `always`.

**Governance for thin teams**

14. ADR-0017 rule 17's interim stands: a human with the right to post may post a draft, an agent's included, without approval when the policy requires none. Whether the human who triggered the agent may do so stays the author's open question. QuickFlows relies on that interim and does not decide it.
15. Posting from draft below a risk amount is policy configuration, with no new mechanism:
    - **Already possible.** `Post` from `draft` is a policy point (ADR-0029 rule 6), and the baseline for a `human` actor is empty (ADR-0043 rule 7), so a person posts directly from draft wherever no matching rule requires approval (ADR-0009 rule 11).
    - **What the preset seeds** (rule 6): rules for actor `human` at `submit` and `post` that require the `standard` procedure from the risk amount up, and whenever the credit limit is exceeded, the cost is unknown or the price is below cost. Below the risk amount and without those flags, a person posts straight from draft; at or above it, or with a flag, the document is submitted and approved. The rule set stays monotonic (ADR-0043 rule 11).
    - **Unchanged seeds.** The core's seeded rules stay: approval for every `general_journal` (ADR-0048 rule 15), a purchase invoice outside the match tolerances (ADR-0047 rule 14), and credit exceeded and unknown cost at `submit` (ADR-0043 rule 15). A company may change them as policy, as always.
16. Approving an agent's draft in the small-company mode:
    - **The reading.** Spec 03 rule 5 reads "the person who triggers an agent must not approve that agent's drafts". This ADR reads "the person who triggers" as the human whose own act started the run: a start command, a note or message they wrote, or a work item they handed to the agent. A run started by an event or schedule acts for the agent type's `workflow_owner_id` (ADR-0050 rule 14), who is accountable for it (spec 03 rule 3) but did not trigger it. Under this reading ADR-0017 rule 16's check, which refuses every approver the run acted for, is stricter than the floor, and the small-company mode may relax the stricter part. The reading is decided by the author's delegation to the chief architect (2026-11-17); the spec 03 wording stays the author's to align (open question).
    - **When it applies.** While `permissions.small_company_mode` is on, `Approve<Type>` that ADR-0017 rule 16 would refuse runs as a recorded exception when all hold: every agent run that wrote a version acting for the approver was started by an event or schedule, not by the approver's own act; the version being approved has no effective taint, either never tainted or cleared by a `ClearTaint`, a self-clearance under rule 17 included (ADR-0029 rule 8); and the approver holds an assignment of the `owner` or `chief_accountant` role template and is eligible for the stage (ADR-0055 rule 7).
    - **The record.** Each case writes a `segregation_exception` of kind `own_agent_draft_approval` and is reviewed with the period's other exceptions through `segregation_review_due` and `ConfirmSegregationReview` (ADR-0054 rule 20).
    - **Still refused:** a run the approver started by their own act (`segregation_of_duties`), a tainted version, and every approval outside the small-company mode.
17. Self-clearance of taint in the small-company mode, decided by the author's delegation to the chief architect (2026-11-17), because a company of one or two people could otherwise never clear its own tainted drafts:
    - **Allowed narrowly.** While `permissions.small_company_mode` is on, the human for whom a tainted run acted may run `ClearTaint` on that run's versions, which ADR-0029 rule 8 otherwise refuses with `segregation_of_duties`.
    - **One by one.** One `ClearTaint` per version, with a reason, as a single command: never a batch item, a bulk review or a case-level confirmation (ADR-0066 rule 18); otherwise `segregation_of_duties`.
    - **The record.** Each self-clearance writes a `segregation_exception` of kind `own_run_taint_clearance` and is reviewed with the period's other exceptions through `segregation_review_due` and `ConfirmSegregationReview` at period close (ADR-0054 rule 20).
    - **Never for automation.** A version whose only clearances are self-clearances counts as tainted for the auto-post gateway's tainted-draft eligibility (ADR-0065 rule 10) and never feeds agent promotion or auto-post evidence (ADR-0050 rule 14; ADR-0059 rule 18). A self-clearance is a clearance whose actor is the human the tainting run acted for, derived from the rows, so no new column is needed.
    - **Outside the mode** ADR-0029 rule 8 applies unchanged. One-click post still never applies to an agent-written draft (rule 12).

**Lean defaults**

18. Record defaults are not settings, and no master-data flag becomes a setting:
    - **Warehouses.** `is_bin_managed` false (ADR-0031 rules 7, 9, with `default_bin_id`) and `outbound_flow` `direct` (ADR-0023 rule 1) are already the column defaults; the preset lists them so that the drift view and the setup flow show them.
    - **Bills of materials.** The setup flow, and phase 2 of a migration (ADR-0044 rule 3 note on bills of materials), fill `consumption_method` `backflush_at_receipt` on new components where the source states none (ADR-0033; ADR-0034 rule 12), so the workshop records only production orders and output receipts.
    - **Scope.** A record default fills a field only when the setup flow creates a record and the person leaves the field unchanged. After setup, forms and imports use the column defaults; a person sets the flag per record as always.

**Commands, catalogs and checks**

19. Commands and queries:

    | Command or query | Module | Effect class | Leaf | Notes |
    | --- | --- | --- | --- | --- |
    | `AcknowledgeCompanySetup`, `RevokeCompanySetupAcknowledgement` | `registry` | `master_data_change` | `company_setting` at `full`, by an owner | `human_only`; setup phase only (rule 8) |
    | `UpdateCompanySetting` (ADR-0063) | `registry` | `master_data_change` | unchanged | Gains optional `preset_code`, `preset_version` and `setup_acknowledgement_id` (rules 4, 9) |
    | `EvaluateSettingPreset`, `ListSettingPresetItem`, `ListSettingPresetDrift` | `registry` | query | `company_setting` | The plan of rule 4, the items as reference data, the drift of rule 5 |

    Envelope (DS-04): the optional field `is_review_skipped`. Command response: `review_reasons` on the simulation of `Post<Type>`.
20. Catalog rows:
    - **Settings:** `ui.post_review` and `ui.post_review_max_amount`, `source` naming this ADR; the settings catalog holds 109 definitions.
    - **Presets:** [setting-presets.csv](../catalogs/setting-presets.csv) (new), version 0.1.0, with a row in the catalogs README.
    - **Errors** (DS-04): `post_review_required` and `setup_phase_closed` (precondition), `setup_acknowledgement_invalid` (permission).
    - **Work item kind:** `setup_loosening_review` (module `registry`, subject `company`, `company_owner`, `days:30`, person).
    - **DDL:** [DS-28-settings.sql](../design/DS-28-settings.sql): `setting_preset`, `setting_preset_item`, `company_setup_acknowledgement`, and on `setting_value` the columns `preset_code`, `preset_version` and `setup_acknowledgement_id` with the trigger's setup check; [DS-20-master-data.sql](../design/DS-20-master-data.sql): `company.first_operating_posting_at`; [DS-15-access.sql](../design/DS-15-access.sql): `segregation_exception.kind` `own_agent_draft_approval` and `own_run_taint_clearance`; [DS-05-platform.sql](../design/DS-05-platform.sql): `audit_record.is_review_skipped`. The ledger's statement that sets `first_operating_posting_at` (rule 7) is added to the journal line trigger of [DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql) at acceptance, because the draft trigger does not yet read the entry's fiscal year; until then rule 7 states it.
    - **Invariants** INV-800 to INV-805 of the block INV-800 to INV-809 and **edge cases** EC-250 to EC-256 of the block EC-250 to EC-259, listed in the section "Edge cases and invariants" below.

## Context

- **The ask.** Owners of small companies compare an ERP with entry-level accounting and ERP products on clicks per document. NativeFlows asks for a plan review on every post (ADR-0040 rule 9), an approval wherever a rule requires one, and a second person for every loosening (ADR-0063 rule 3). For a team of one to three people this is ceremony without a second pair of eyes.
- **What already exists.**
  - The policy table lets a person post from draft wherever no rule requires approval (ADR-0009 rule 11; ADR-0043 rule 7).
  - The small-company mode turns segregation refusals into recorded exceptions with a period review (ADR-0054 rule 20).
  - Warehouses default to no bins and direct outbound (ADR-0023, ADR-0031), and components may backflush at receipt (ADR-0034).
  - The settings registry has bounds, directions and an append-only history (ADR-0063).
- **What was missing:**
  - a way to apply a coherent set of values at once and see later drift;
  - a path for setup before go-live, because ADR-0063 rule 3 left one-person companies on the core defaults for ever;
  - a post button that does not stop on clean documents;
  - a way for an owner who is the workflow owner of every agent to approve agents' drafts.
- **Practice.**
  - SAP Business One and S/4HANA Cloud configure a company before go-live in implementation activities, often by a partner, and switch to controlled change afterwards; SAP Best Practices ship preconfigured content applied as ordinary configuration.
  - Odoo and entry-level products post with one click and show warnings only when something is off.
  - Audit practice accepts compensating controls in small entities where segregation is not possible: an owner's documented periodic review of exceptions.
- **Constraints.** Spec 03's preamble says no setting relaxes rule 1, rule 5 or the "Human only" rows; ADR-0005 reserves hard floors and governance for the author. The author delegated the three questions of this ADR (Principle 2 under one-click post, the reading of spec 03 rule 5, self-clearance of taint) to the chief architect on 2026-11-17, to decide what fits small and medium businesses; rules 13, 16 and 17 record the decisions, and the spec 03 wording stays the author's.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Preset as a bundle of existing settings, rules and defaults, applied by ordinary commands (chosen) | One mechanism; every value keeps its own checks and history; drift is visible; no branch in code | The preset is not itself a control: a company can diverge freely |
| A `quickflows_mode` flag read by business code | Simple to explain | Hidden branches everywhere; untestable combinations; contradicts ADR-0063's one registry |
| A separate QuickFlows edition | Clear marketing | Spec 18 allows one edition only |
| Setup phase marked by the first operating journal entry (chosen) | Deterministic, serialized by a row lock, reuses the `has_posting` pattern; opening documents do not count | A new column and a ledger statement |
| Setup phase marked by an explicit go-live command | Explicit | A company can forget it and stay in setup with live postings; one more gate on every posting |
| Setup loosenings by the owner's upfront acknowledgement of an implementer, reviewed at the first close (chosen) | Works for one person; the owner is accountable; the review lists every loosening | The review comes after the fact |
| Each setup loosening approved by the owner | Two people where there are two | Impossible for a one-person company without lifting `approver_is_submitter` |
| Review reasons computed by the server, re-checked at execution (chosen) | Deterministic, testable, the client computes nothing; a client bug cannot skip review | A response field and an envelope field |
| Auto-execute decided by the client from the plan | No server change | Business logic in the client (ADR-0040 rule 2); unverifiable |
| One-click post also for agent-written drafts | Faster | A person would post an agent's work unseen; spec 14 says a person confirms before posting |
| Owner approval of event-started agent drafts as a reading of spec 03 rule 5 (chosen) | Solves the one-person case without a setting relaxing a floor | Spec 03's wording still to be aligned |
| Self-clearance of taint in the small-company mode, one version at a time, logged, never counted for automation (chosen) | A one- or two-person company can clear its own tainted drafts; the period review sees every case | One person both reads the outside content and clears it |
| Self-clearance forbidden in every company | Strict | A one-person company could never clear a tainted draft |
| A setting that lifts ADR-0017 rule 16 in small companies | Simple | A customer setting relaxing a spec 03 floor, which spec 03 forbids |
| Master-data flags as registry settings | One place for every value | Warehouse and component flags are per record and checked per record; a setting would duplicate them |

## Consequences

- **For lean companies:** a one-person company applies `quickflows` during setup, enters a risk amount and a post review maximum, and then posts clean documents below them with one click and without approval; anything above the amount, flagged, tainted or agent-written stops for review or approval as today.
- **For other companies:** nothing changes. Every new value defaults to today's behavior, and `standard` reproduces the core defaults.
- **For agents:** nothing changes. Agents read presets as reference data, never apply them, and one-click post never applies to their drafts.
- **For auditors:** every preset value is an ordinary `setting_value` row, policy rule or command with its preset recorded; setup loosenings name the owner's acknowledgement and are listed for review; every post without a shown plan is marked in its audit record; every owner approval of an agent's draft and every self-clearance of taint is a segregation exception.
- **For the build:** the registry's preset tables, `EvaluateSettingPreset` and the setup path land with `registry` at step 1; the review reasons and `is_review_skipped` with the dispatcher and the plan panel; the governance rules with `policy` and `permissions` at step 5. The work is small-model friendly: two tables of reference data, one pure function for review reasons, one trigger branch.
- **Revisit when:**
  - the author aligns spec 03 differently from the reading of rule 16;
  - period reviews show self-clearances followed by corrections, which would argue for a second person after all;
  - a second preset (for example a distribution or service profile) needs item kinds this ADR lacks;
  - companies ask for presets per branch or per warehouse.

## Documents updated

- **ADRs** (notes tagged "ADR-0067, 2026-11-17 (proposed)"):
  - [ADR-0008](0008-command-envelope-and-registry.md) rule 13;
  - [ADR-0017](0017-permission-envelope.md) rule 16;
  - [ADR-0029](0029-proposals-and-agent-safety.md) rule 8;
  - [ADR-0038](0038-audit-and-observability.md) rule 2;
  - [ADR-0040](0040-ui-architecture.md) rule 9;
  - [ADR-0043](0043-policy-and-approval.md) rules 13, 15;
  - [ADR-0044](0044-data-migration-and-export.md) rule 3;
  - [ADR-0054](0054-users-roles-and-authorizations.md) rule 20;
  - [ADR-0065](0065-deterministic-auto-post-gateway.md) rule 10;
  - [ADR-0063](0063-configurable-policy-settings.md) rules 3, 5, 29.
- **Catalogs:** [setting-presets.csv](../catalogs/setting-presets.csv) (new), [settings.csv](../catalogs/settings.csv) (2 definitions), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv), the [catalogs README](../catalogs/README.md).
- **Design files:** [DS-28-settings.sql](../design/DS-28-settings.sql), [DS-20-master-data.sql](../design/DS-20-master-data.sql), [DS-15-access.sql](../design/DS-15-access.sql), [DS-05-platform.sql](../design/DS-05-platform.sql), [DS-04-command-envelope.md](../design/DS-04-command-envelope.md) (envelope field, response field, errors), [DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md) and [DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md) (code blocks), [architecture-overview.md](../design/architecture-overview.md), [architecture-core.md](../design/architecture-core.md) and the generated appendices.
- **The lab:** `lab/t24_settings.py` checks the presets catalog against the settings catalog.
- **Open questions:** [docs/open-questions.md](../open-questions.md), section "QuickFlows presets": Principle 2's operation, the reading of spec 03 rule 5 and self-clearance of taint, answered by the author's delegation to the chief architect (2026-11-17); the alignment of the spec 03 wording; and the interim choices.
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md).
- **Not changed:** `docs/spec/`, including the glossary; the rows for operating preset, setup phase and review reason come with acceptance.

## Edge cases and invariants

**Invariants** (DS-16; block INV-800 to INV-809, INV-800 to INV-805 taken; first step 5):

- **INV-800** `setup_loosening_acknowledged` (area `safety`): every `setting_value` with a `setup_acknowledgement_id` was recorded while its company's `first_operating_posting_at` was null or later, by that acknowledgement's implementer, under an acknowledgement of the same company given by a holder of the `owner` role template and not revoked at that instant, for a key whose scope is not `installation` and whose `outdates` is `none`.
- **INV-801** `review_skip_conditions` (area `safety`): every `audit_record` with `is_review_skipped` true belongs to a single executed `Post<Type>` by actor kind `human`, on a date when `ui.post_review` was `on_exceptions` and `ui.post_review_max_amount` was above 0, of a document version without effective taint and without agent-written or origin-run versions, with no check codes, a policy decision `allowed` without confirmation and no true policy flag, and an amount at or below that maximum.
- **INV-802** `presets_within_registry` (area `platform`): every `setting_preset_item` of kind `setting` names a registered company-scope key with storage `setting_value`, `outdates` `none` and a core default that is not `fail_closed`, with a value within its bounds or a parameter of the same preset version whose bounds lie within them; no `policy_rule` item has effect `allow`; and `standard` lists every setting, command setting and record default key another preset lists.
- **INV-803** `own_agent_draft_approval_bounded` (area `safety`): every approval of a document version by a human for whom an agent run wrote a version of that document has a `segregation_exception` of kind `own_agent_draft_approval`, recorded while `permissions.small_company_mode` was on, every such run having been started by an event or schedule, the approved version without effective taint, and the approver holding the `owner` or `chief_accountant` role template.
- **INV-804** `setup_phase_marker` (area `platform`): `company.first_operating_posting_at` is null exactly while the company has no journal entry outside the migration fiscal year, and is not later than the `recorded_at` of the first such entry.
- **INV-805** `own_run_taint_clearance_bounded` (area `safety`): every `taint_clearance` whose actor is the human the tainting run acted for was recorded while `permissions.small_company_mode` was on, by a single `ClearTaint` command with a reason, and has a `segregation_exception` of kind `own_run_taint_clearance`; and no `policy_decision` with `auto_post_decision` `auto_post` and no agent promotion evidence counts a version whose only clearances are such.

**Edge cases** (DS-17; block EC-250 to EC-259, EC-250 to EC-256 taken; first step 5):

- **EC-250** `quickflows_setup_one_person`: the only user of a new company acknowledges themself as implementer and applies `quickflows` with a risk amount, then sets `ui.post_review_max_amount`; `ui.post_review` `on_exceptions` and the maximum are recorded as setup loosenings without a second approver, the small-company mode is enabled, four policy rules are created, and `setup_loosening_review` is raised.
- **EC-251** `setup_path_closed_after_go_live`: after the first ordinary sales invoice posts, a setup-path loosening is refused with `setup_phase_closed`, and a direct loosening returns `proposal_required`; a migration's opening entries before it did not end the phase.
- **EC-252** `one_click_post_clean`: under `quickflows`, a person posts a clean sales invoice below the post review maximum and the risk amount; the simulation returns no review reason, the client executes at once, the audit record has `is_review_skipped`, and the history shows the plan.
- **EC-253** `one_click_post_exception`: the same person posts an invoice above the post review maximum, then a goods delivery with a negative-stock check result; both return review reasons and open the panel; a client that sends `is_review_skipped` anyway gets `post_review_required` and nothing is committed.
- **EC-254** `owner_approves_event_agent_draft`: in the small-company mode, the purchase invoice agent drafts an invoice from a supplier e-mail for the owner as workflow owner; the chief accountant clears its taint; the owner approves it above the risk amount, and a `own_agent_draft_approval` exception is recorded; a draft from a run the owner started with their own note is refused with `segregation_of_duties`.
- **EC-255** `preset_drift_and_tighten`: after `quickflows`, the owner sets `ui.post_review` back to `always` at once (a tightening); `ListSettingPresetDrift` lists it, and the next post shows the panel.
- **EC-256** `self_clear_taint_small_company`: in a one-person company with the small-company mode on, the owner clears the purchase invoice agent's tainted draft with a reason; an `own_run_taint_clearance` exception is recorded, the gateway still treats the draft as tainted (`require_human`), and a bulk clearance of two such drafts is refused with `segregation_of_duties`; with the mode off, the single clearance is refused with `segregation_of_duties`.
