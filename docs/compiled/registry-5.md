Module: registry    Chunk: 5 of 5    Source ADRs: ADR-0063, ADR-0065, ADR-0067
Build step(s): 1, 5, 6, 7    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `registry` compiled spec, chunk 5: auto-post checkers, operating presets, the setup phase, post review

## Purpose

`registry` owns the command registry and the settings registry (layer 1 of ADR-0022.R2). This chunk states the dispatcher's
part in the auto-post gateway and the checker declaration (ADR-0065), the operating presets `standard` and `quickflows`,
the setup phase and the owner's acknowledgement, and the one-click post with its review reasons (ADR-0067), and the lab
check of the settings registry (ADR-0063.R30). As the owner of the rest it also carries the rows of owned tables, catalog
rows and settings that no other chunk writes.

## Entities and tables

DDL: `docs/design/DS-28-settings.sql` (presets, acknowledgement, module activation); `docs/design/DS-30-ui.sql` (`list_variant`).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `setting_preset` | Installation data: one row per preset version, written at startup (R814) | `id` (uuid5 of `setting_preset:<preset_code>:<preset_version>`, computed by the loader); (`preset_code`, `preset_version`) unique | none | `registry` |
| `setting_preset_item` | Installation data: one row per preset version, item kind and item key (R815) | `id` (uuid5 of `setting_preset_item:<preset_code>:<preset_version>:<item_kind>:<item_key>`, computed by the loader); `uq_setting_preset_item_key` (`preset_code`, `preset_version`, `item_kind`, `item_key`) | `setting_preset` | `registry` |
| `company_setup_acknowledgement` | An owner's acknowledgement of an implementer who may set loosenings before go-live; never deleted, only revoked once (`revoked_at` with `revoked_by_user_id`) (R833, R834) | `id`; (`company_id`, `id`) unique | `company` | `registry` |
| `list_variant` | A saved view of one `List<Noun>` query, personal or shared with a role (ADR-0077.R10a, primary `app`) | `id`; (`company_id`, `id`) unique | `company`; `role` by `shared_role_id` | `registry` |
| `module_activation` | Company data, updated in place: whether a module of ADR-0022.R2 is active for a company, read by the CRM-only profile (ADR-0022.R2.N14) and the partner accounts of `INV-38` (ADR-0015.R11.N1) | `id`; (`company_id`, `module`) unique | `company` | `registry` |

The `setting_value` columns `preset_code`, `preset_version` and `setup_acknowledgement_id` belong to the row of `setting_value` in chunk 3.

Source finding: `module_activation` has DDL (`DS-28-settings.sql`, owner `registry`) but no rule of `registry` defines it; only the notes ADR-0022.R2.N14 and ADR-0015.R11.N1 of other modules name it, so its row stands here as the owner of the rest.

Reads: `company` (`first_operating_posting_at`, `valuation_area_level`; `master_data`); `audit_record` (`is_review_skipped`; `audit`); `segregation_exception` (`permissions`); `policy_rule` (`policy`); `warehouse`, `bill_of_materials_component` (`master_data`); `account` (`ledger`).

## Commands and queries

Authorization: the function leaf `company_setting` (catalog `authorization-areas.csv`, module `registry`); the verbs `Evaluate` and `List` are at level `read` in `authorization-verb-levels.csv`, `Post` at `post`.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `AcknowledgeCompanySetup` | `human_only`; effect class `master_data_change`; leaf `company_setting` at `full`; the actor holds an assignment of the `owner` role template | implementer (a user account with an assignment in the company, may be the owner), reason | Writes a `company_setup_acknowledgement` row (R833) | not stated | `setup_phase_closed` |
| `RevokeCompanySetupAcknowledgement` | `human_only`; `master_data_change`; leaf `company_setting` at `full`, by an owner | the acknowledgement | Sets `revoked_at` once (R834) | not stated | `setup_phase_closed` |
| `EvaluateSettingPreset` | query; leaf `company_setting` | preset, version, parameter values | Returns the plan per item (R821) | none | `setting_out_of_bounds` |
| `ListSettingPresetItem` | query; leaf `company_setting`; agents read it as reference data | not stated | The preset items (R816) | none | not stated |
| `ListSettingPresetDrift` | query; leaf `company_setting` | not stated | The drift of the last applied preset (R826) | none | not stated |

`UpdateCompanySetting` (row in chunk 4) gains optional `preset_code`, `preset_version` and `setup_acknowledgement_id` (R823, R835), and returns `setup_phase_closed` or `setup_acknowledgement_invalid` on the setup path.

Envelope and response of every `Post<Type>` command: the envelope field `is_review_skipped`, the simulate response field `review_reasons`, and the error `post_review_required` (R844 to R847).

Contract functions, hooks and jobs, not registered commands of `registry`: the pure function `policy.contract.evaluate_auto_post` and the internal command `RecordAutoPostDecision` (`policy`); the hook `auto_post_checker`; `registry.contract.get_setting`; the system job `RunAutoPostGateway` (`automation`) (R801 to R804).

Commands of other modules that these rules name: `CreatePolicyRule`, `EnablePolicyRule` (`policy`); `EnableSmallCompanyMode` (`permissions`, refusing with `small_company_mode_not_allowed`); `CreateCompany` (`master_data`). The `list_variant` commands `CreateListVariant`, `UpdateListVariant`, `DeleteListVariant` and the query `ListListVariant` are stated by ADR-0077.R10a (primary `app`); a shared variant needs the capability `share_list_variant` at `edit` on the leaf `list_variant` of `registry`, a personal one is checked on `general_access`.

## Rules

### The auto-post gateway hook

R801. `policy` owns the auto-post gateway: the pure function `policy.contract.evaluate_auto_post`, the generic rules of ADR-0065.R5, the decision record (ADR-0065.R6) and the internal command `RecordAutoPostDecision` (ADR-0065.R21).
Source: ADR-0065.R1

R802. `policy` declares the hook `auto_post_checker`. A module registers, per document type it owns, one checker implementation; `app` (layer 6) wires it. `policy` imports no module above it (ADR-0022.R2; ADR-0043.R1).
Source: ADR-0065.R1

R803. The inputs that `policy` cannot read itself are passed in by the dispatcher (`registry`), which already reads them for the actor context: the generic settings of ADR-0065.R8 with their values and sources (`registry.contract.get_setting`), the draft version's effective taint, the agent run that wrote it, that run's agent type, behavior hash and effective mode (ADR-0050.R14), and the simulation result.
Source: ADR-0065.R1

R804. The runner is the system job `RunAutoPostGateway` of module `automation` (layer 5), which already imports `registry` for dispatch and the contracts of layers 3 and 4 (ADR-0058.R1). It is not an automation rule: it runs no company-composed action, and its only posting path is a gateway decision (ADR-0065.R13).
Source: ADR-0065.R1

R805. The gateway stays in Phase 1 as designed. The agent `active` mode it needs keeps the in-use draft acceptance evidence of ADR-0065.R11, with no live agent shadow. `auto_post_advisor` (ADR-0065.R18) is a Phase 2 agent type, because it reads months of gateway outcomes that do not exist before go-live; until then people propose gateway settings and decision tables, and the assistant in `act` mode may draft them on request. The purchase invoice checker lands at build step 7, after the purchase invoice manual path (ADR-0078.R1, ADR-0078.R2, ADR-0078.R5, ADR-0078.R6, ADR-0078.R8).
Source: ADR-0065.R1.N1

R806. Each checker declares, with a version, in the registry vocabulary (DS-04):
- `document_type` and `actor_kind` (`system`, or `integration` for an import);
- `runner`: `gateway_job` (ADR-0065.R3) or `own` (the module's existing trigger, ADR-0065.R20);
- `rules`: the ordered list of its rule codes, each with the decision it gives on failure (`require_human` or `reject`) and the values it reports;
- `facts`: the input schema of its decision point `auto_post.<document_type>` (ADR-0058.R18), every fact a registered gate field (ADR-0059.R20), with the code default `require_human` for `decision_no_match`;
- `accepts_tainted` (true or false), and the plan fields whose amounts and quantities need a verification result (ADR-0065.R10);
- `allowed_check_codes`: check results that do not stop an auto-post (empty for every Phase 1 checker);
- its evidence function (ADR-0065.R14) and the settings keys it reads.
Source: ADR-0065.R2

R807. The registry refuses a second checker for one document type. The placeholder `<document_type>` of the keys of ADR-0065.R8 lists the document types whose checker declares `runner: gateway_job`; in Phase 1 that is `purchase_invoice` only.
Source: ADR-0065.R2

### Operating presets

R810. QuickFlows is an operating preset: a named, versioned bundle of values for things the core already has: settings of the ADR-0063 registry, seeded policy rules (ADR-0043), company settings with their own commands, and defaults the setup flow fills on new records. Applying a preset is an ordinary series of commands through their usual paths, recorded with the preset code and version; no business code reads the preset name. A value changed after the preset is applied diverges, and a query shows the drift. The speed levers beside the presets are the one-click post (R841 to R849) and posting from draft below a risk amount (R851 to R853).
Source: ADR-0067.D0

R811. QuickFlows changes none of these: the hard locks of ADR-0063.R6; simulate-then-execute with `plan_hash` (ADR-0008 rules 9 to 13); the policy floors (ADR-0043.R9); taint persistence (ADR-0029 rules 9 to 11) and its clearance rule outside the small-company mode (ADR-0029.R8); agents only drafting; and spec 18's single edition. In the small-company mode (ADR-0054.R20) the owner or chief accountant may approve an untainted draft that an agent wrote on their behalf from an event or schedule, and the person a tainted run acted for may clear its versions one by one, each a recorded segregation exception (ADR-0067.R16, ADR-0067.R17).
Source: ADR-0067.D0

R812. QuickFlows is the name of the seeded preset `quickflows`, not an edition, a module or a flag. Spec 18's "one edition only" stands: every company can apply every preset.
Source: ADR-0067.R1

R813. No handler, consumer, job, policy function or query outside the registry's preset code reads a preset code, and none reads `setting_value.preset_code` to decide anything. A CI check fails on the literal preset codes anywhere under `backend/src/` except `registry`'s preset loader and its tests.
Source: ADR-0067.R1

R814. A preset is installation data, registered in code by `registry` like setting definitions (ADR-0063.R1) and written at startup into `setting_preset` and `setting_preset_item` (`docs/design/DS-28-settings.sql`). Its identity is `preset_code` (lowercase, one segment) and `preset_version` (an integer, raised on any change of the preset's items). A version is never edited.
Source: ADR-0067.R2

R815. A preset has one item per (preset, version, `item_kind`, `item_key`), of these kinds:
- `parameter`: a value the implementer enters when applying, with its type and bounds (for example `risk_amount`, an amount in company currency, at least 0); a parameter has no default, because an amount depends on the currency (ADR-0063.R9);
- `setting`: a registry key at scope `company` and its value, or `param:<name>`;
- `policy_rule`: a policy rule template (R851 to R853): actions, document type, actor kind, conditions, effect and approval procedure;
- `command_setting`: a company setting that has its own commands outside the registry, such as `permissions.small_company_mode` (ADR-0054.R20), applied only through those commands and their checks;
- `record_default`: a field value the setup flow fills when it creates records of a kind (R854 to R857).
Source: ADR-0067.R2

R816. The catalog `setting-presets.csv` (owner DS-28) lists every item, seeded now and generated from the registry once `registry` exists, like the settings catalog. Agents read presets as reference data through `ListSettingPresetItem`.
Source: ADR-0067.R2

R817. Checked at registry startup and by the lab: a `setting` item names a registered key with storage `setting_value`, scope `company`, a leaf that is neither `package` nor `operator`, and a core default that is not `fail_closed`. Its value lies within the definition's bounds; a parameter's bounds lie within the bounds of every key it fills.
Source: ADR-0067.R3

R818. No preset item touches a cross-cutting hard lock of ADR-0063.R6, a key whose loosening outdates auto-post or promotion evidence, an agent type's mode, a data-processing permission or an auto-post rule. A `policy_rule` item never has effect `allow`, so a preset never lifts a non-human baseline (ADR-0043.R7) or lets a non-human post.
Source: ADR-0067.R3

R819. `standard` lists, at its core default, every `setting`, `command_setting` and `record_default` key that any other preset lists, so a company can always return to the core values. `standard` has no `policy_rule` items: the core seed of ADR-0043.R15 is the standard.
Source: ADR-0067.R3

R820. Applying a preset never bypasses ADR-0063.R3: each setting item is compared with the value in force and is a tightening, a loosening or neutral like any other change.
Source: ADR-0067.R3

R821. `EvaluateSettingPreset` (preset, version, parameter values) returns, per item, the effective value in force, the preset's value, the change kind (`tighten`, `loosen`, `neutral` or `unchanged`) and the path: `direct`, `setup` (R835) or `proposal`. A parameter outside its bounds returns `setting_out_of_bounds`.
Source: ADR-0067.R4

R822. The setup flow sends the tightening, neutral and setup-path items as one command batch (ADR-0008.R20): `UpdateCompanySetting` per setting item, `CreatePolicyRule` and `EnablePolicyRule` per policy rule and action, and the item's own command per `command_setting` item. After go-live it sends the loosening setting items as one change proposal (ADR-0063.R3). Every item keeps its own permission, leaf and check.
Source: ADR-0067.R4

R823. `UpdateCompanySetting` takes optional `preset_code` and `preset_version`, stored on the `setting_value` row; the other commands of a preset batch carry the preset code and version in their audit record's `reason` (ADR-0038.R2).
Source: ADR-0067.R4

R824. Applying a preset is additive: it sets the items it lists, never removes or disables a rule, setting or record another preset or a person made, and skips items whose value is already in force. A `command_setting` item whose command refuses (for example `small_company_mode_not_allowed`) is reported in the plan and left out of the batch, which runs all or nothing (ADR-0008.R20).
Source: ADR-0067.R4

R825. Divergence is normal: a person may change any value afterwards through the usual path. Nothing re-applies a preset by itself, and no value depends on the preset at run time.
Source: ADR-0067.R5

R826. `ListSettingPresetDrift` lists, for the preset and version a company applied last (the latest `setting_value` row with a `preset_code`), the `setting` and `command_setting` items whose value in force differs from the preset's, with the change that made it differ.
Source: ADR-0067.R5

R827. The seeded presets, version 1, are `standard` and `quickflows`. Their `parameter`, `setting` and `command_setting` items:
- `parameter` `risk_amount`: `standard` none; `quickflows` entered at application, an amount in company currency, at least 0, the approval threshold;
- `setting` `ui.post_review`: `standard` `always`; `quickflows` `on_exceptions`;
- `setting` `ui.post_review_max_amount`: `standard` `0`; `quickflows` does not list it: the implementer sets it at setup (R842);
- `command_setting` `permissions.small_company_mode`: `standard` `false`; `quickflows` `true`, through `EnableSmallCompanyMode` while its bound holds.
Source: ADR-0067.R6

R828. The `policy_rule` items of `quickflows` version 1 (`standard` has none):
- `quickflows.from_risk_amount`: `submit` and `post`, every document type, actor `human`, `require_approval` with `standard` from `amount_company_min` = `risk_amount`;
- `quickflows.credit_exceeded`: `submit` and `post`, every type, actor `human`, `require_approval` with `standard` when `is_credit_exceeded`;
- `quickflows.cost_unknown`: the same when `is_cost_unknown`;
- `quickflows.price_below_cost`: the same when `is_price_below_cost`.
Source: ADR-0067.R6

R829. The `record_default` items of version 1, as `standard` / `quickflows`:
- `warehouse.is_bin_managed`: `false` / `false`;
- `warehouse.outbound_flow`: `direct` / `direct`;
- `bill_of_materials_component.consumption_method`: `manual` / `backflush_at_receipt`;
- `company.valuation_area_level`: `site` / `company` (ADR-0068.R7).
Source: ADR-0067.R6

### The setup phase

R830. A company is in its setup phase while `company.first_operating_posting_at` is null. ADR-0044 defines no company-level go-live state, only the migration's states (ADR-0044.R1), and opening documents post during a migration (ADR-0044.R3), so the phase is defined here.
Source: ADR-0067.R7

R831. The ledger sets `first_operating_posting_at` once, in the transaction of the first journal entry of the company whose posting period lies outside the migration fiscal year (ADR-0044.R2), in the pattern of `account.has_posting` (ADR-0010.R12): an `UPDATE … WHERE first_operating_posting_at IS NULL`, which locks the company row. Opening documents of a migration do not end the phase; the first ordinary posting does. For existing companies, the upgrade that adds the column sets it from the company's first such journal entry.
Source: ADR-0067.R7

R832. A setup-path command reads the company row `FOR SHARE` through `registry`'s contract before it writes, so it and the first operating posting cannot overlap. The phase never reopens.
Source: ADR-0067.R7

R833. `AcknowledgeCompanySetup` (`registry`, `human_only`, `master_data_change`, leaf `company_setting` at `full`; the actor holds an assignment of the `owner` role template) names the implementer, a user account with an assignment in the company, which may be the owner. It writes a `company_setup_acknowledgement` row (owner, implementer, reason, `acknowledged_at`).
Source: ADR-0067.R8

R834. `RevokeCompanySetupAcknowledgement` by an owner sets `revoked_at` once. `AcknowledgeCompanySetup` and `RevokeCompanySetupAcknowledgement` are refused with `setup_phase_closed` once the setup phase has ended.
Source: ADR-0067.R8

R835. `UpdateCompanySetting` with a `setup_acknowledgement_id` accepts a loosening directly when all hold: the company is in its setup phase; the acknowledgement is the company's and not revoked; the actor is its implementer and holds `edit` on the key's leaf; the key's scope is `company` or narrower, never `installation`; and the key's `outdates` is `none`. Otherwise it returns `setup_phase_closed` (after go-live) or `setup_acknowledgement_invalid`.
Source: ADR-0067.R9

R836. A setup-path loosening needs no second approver: the `setting_value` row records the acknowledgement instead of a proposal and approver; a tightening or neutral change made in the same batch carries no acknowledgement. Bounds, installation maxima and every other check of ADR-0063 rules 2 to 4 apply.
Source: ADR-0067.R9

R837. These stay on the ordinary path in the setup phase: every `auto_post.*` key, `cash.auto_post.*` included (turning a document type to `shadow` or `live` and every other gateway loosening needs a second person, ADR-0065.R8); keys that outdate auto-post or promotion evidence; agent promotions (ADR-0050.R14); data-processing permissions (ADR-0057.R20); and policy rules that let a non-human post (ADR-0043.R14). Before go-live there is no evidence for them anyway.
Source: ADR-0067.R9

R838. The database holds the setup path: the `setting_value` trigger accepts a loosening without a proposal only with an active acknowledgement of the same company whose implementer is `changed_by_user_id`, for a key with `outdates` `none` that is not an `auto_post.*` key, while `first_operating_posting_at` is null.
Source: ADR-0067.R9

R839. After go-live ADR-0063.R3 applies again in full; a one-person company cannot loosen any setting.
Source: ADR-0067.R10

R840. The first setup-path loosening raises `setup_loosening_review` for `company_owner` (open key: the company); later ones add evidence. It lists each loosening with its old and new value, and, while `ui.post_review` is `on_exceptions` and `ui.post_review_max_amount` is still 0, a reminder that the maximum is unset. The close checklist of every period shows it while it is open, without blocking the lock, like `segregation_review_due` (ADR-0054.R20). The owner resolves it after reviewing the list.
Source: ADR-0067.R10

### Post review

R841. The keys `ui.post_review` and `ui.post_review_max_amount` (ADR-0063.R1; `settings.csv`) have company scope and leaf `company_setting`. `ui.post_review` is `always` (default, today's behavior) or `on_exceptions`; `always` is tighter. `ui.post_review_max_amount` is an amount in company currency, default 0, at least 0, lower is tighter; with 0 every post is reviewed, whatever `ui.post_review` says.
Source: ADR-0067.R11

R842. Switching to `on_exceptions` or raising the maximum is a loosening: by proposal after go-live, or on the setup path before it. The preset `quickflows` sets `ui.post_review` to `on_exceptions` but not the maximum, because a preset cannot know the company currency. The setup flow asks for the maximum next to the preset's `risk_amount`; until it is set it stays 0, so every post is reviewed, and `setup_loosening_review` reminds the owner (R840).
Source: ADR-0067.R11

R843. The plan panel is a floorplan of its own (`plan_panel`); for agent-written drafts it adds a field-level diff against the previous version and the taint badge, so `on_exceptions` never skips it for them (ADR-0077.R1, ADR-0077.R3).
Source: ADR-0067.R11.N1

R844. The simulate response of a `Post<Type>` command carries `review_reasons`, computed by the dispatcher from the run, never by the client (ADR-0040.R2). It is empty only when all hold:
- `ui.post_review` is `on_exceptions` on the business date, and `ui.post_review_max_amount` is above 0;
- the actor kind is `human` (never `agent`, `integration` or `system`);
- the command is a single command, not a batch item or a bulk review (ADR-0042.R12 note), and its type is not a correction type (ADR-0009.R23);
- the document's current version has no effective taint (ADR-0029.R9);
- no version of the document was written by an agent run and none carries an origin agent run (ADR-0017.R16), so a person always sees an agent's draft before posting it (spec 14);
- the response has no check result, hashed or not (ADR-0040.R10), so negative stock, capacity and similar warnings always show;
- the policy decision is `allowed` without confirmation, and no boolean condition of the policy input is true (`is_credit_exceeded`, `is_price_below_cost`, `is_price_outside_list`, `is_cost_unknown`, `is_match_exceeded`, `is_direct_expense`, `is_bank_account_recent`, `is_rate_unusual`, and any added later);
- the policy input's amount in company currency is at or below `ui.post_review_max_amount`.
Source: ADR-0067.R12

R845. The review reason codes are `post_review_always`, `actor_not_human`, `not_single_post`, `correction_document`, `document_tainted`, `agent_written`, `checks_present`, `policy_flag` (with the flags), `policy_outcome` and `amount_above_maximum`.
Source: ADR-0067.R12

R846. When `review_reasons` is empty and the setting is `on_exceptions`, the client sends `mode: execute` at once with `expected_plan_hash`, the simulation's `as_of_date` and the envelope field `is_review_skipped: true` (optional, default false, outside the request hash like `mode`).
Source: ADR-0067.R13

R847. The dispatcher recomputes the review reasons in the execution, after the handler and before commit. If any applies, it rolls back and returns `post_review_required` with the reasons, and the client shows the plan panel. An agent, integration or system actor that sends the field gets the same error.
Source: ADR-0067.R13

R848. For an execution without the panel `audit_record.is_review_skipped` is true. The response, with the plan and `plan_hash`, is stored as for every execution (ADR-0008.R16), and the document history shows the plan and "posted without review".
Source: ADR-0067.R13

R849. Every post is still simulated and executed against its `plan_hash`; only the display of the plan moves to the exceptions. Principle 2 holds (decided by the author's delegation to the chief architect, 2026-11-17): the plan is still computed, re-checked by the server before commit, stored and viewable; a person chose to post, and every non-routine condition forces the review. The core default stays `always`.
Source: ADR-0067.R13

R850. The interim of ADR-0017.R17 stands: a human with the right to post may post a draft, an agent's included, without approval when the policy requires none. Whether the human who triggered the agent may do so stays the author's open question. QuickFlows relies on that interim and does not decide it.
Source: ADR-0067.R14

R851. Posting from draft below a risk amount is policy configuration, with no new mechanism. `Post` from `draft` is a policy point (ADR-0029.R6), and the baseline for a `human` actor is empty (ADR-0043.R7), so a person posts directly from draft wherever no matching rule requires approval (ADR-0009.R11).
Source: ADR-0067.R15

R852. The preset seeds (R828) rules for actor `human` at `submit` and `post` that require the `standard` procedure from the risk amount up, and whenever the credit limit is exceeded, the cost is unknown or the price is below cost. Below the risk amount and without those flags, a person posts straight from draft; at or above it, or with a flag, the document is submitted and approved. The rule set stays monotonic (ADR-0043.R11).
Source: ADR-0067.R15

R853. The core's seeded rules stay: approval for every `general_journal` (ADR-0048.R15), a purchase invoice outside the match tolerances (ADR-0047.R14), and credit exceeded and unknown cost at `submit` (ADR-0043.R15). A company may change them as policy, as always.
Source: ADR-0067.R15

### Record defaults

R854. Record defaults are not settings, and no master-data flag becomes a setting. For warehouses, `is_bin_managed` false (ADR-0031 rules 7, 9, with `default_bin_id`) and `outbound_flow` `direct` (ADR-0023.R1) are already the column defaults; the preset lists them so that the drift view and the setup flow show them.
Source: ADR-0067.R18

R855. The setup flow, and phase 2 of a migration (the note of ADR-0044.R3 on bills of materials), fill `consumption_method` `backflush_at_receipt` on new bill-of-materials components where the source states none (ADR-0033; ADR-0034.R12), so the workshop records only production orders and output receipts.
Source: ADR-0067.R18

R856. A record default fills a field only when the setup flow creates a record and the person leaves the field unchanged. After setup, forms and imports use the column defaults; a person sets the flag per record as always.
Source: ADR-0067.R18

R857. `company.valuation_area_level` is set by `CreateCompany` and fixed after setup, so a preset applied later could never fill it. `CreateCompany` takes an optional preset code, and that preset's record defaults fill the fields the command leaves unset (ADR-0068.R7).
Source: ADR-0067.R18

### Commands and catalog rows of ADR-0067

R858. The commands and queries of presets and the setup phase:
- `AcknowledgeCompanySetup`, `RevokeCompanySetupAcknowledgement`: module `registry`, effect class `master_data_change`, leaf `company_setting` at `full`, by an owner; `human_only`; setup phase only (R833, R834);
- `UpdateCompanySetting` (ADR-0063): module `registry`, `master_data_change`, leaf unchanged; it gains optional `preset_code`, `preset_version` and `setup_acknowledgement_id` (R823, R835);
- `EvaluateSettingPreset`, `ListSettingPresetItem`, `ListSettingPresetDrift`: module `registry`, queries on leaf `company_setting`: the plan of R821, the items as reference data, the drift of R826.
Source: ADR-0067.R19

R859. The envelope (DS-04) gains the optional field `is_review_skipped`; the command response gains `review_reasons` on the simulation of `Post<Type>`.
Source: ADR-0067.R19

R860. ADR-0067 adds these catalog rows: the settings `ui.post_review` and `ui.post_review_max_amount`, `source` naming ADR-0067; the presets catalog `setting-presets.csv` (new), version 0.1.0, with a row in the catalogs README; the errors (DS-04) `post_review_required` and `setup_phase_closed` (precondition) and `setup_acknowledgement_invalid` (permission); the work item kind `setup_loosening_review` (module `registry`, subject `company`, `company_owner`, `days:30`, person); the invariants `INV-800` to `INV-805` of the block `INV-800` to `INV-809`, and the edge cases `EC-250` to `EC-256` of the block `EC-250` to `EC-259`.
Source: ADR-0067.R20

R861. The DDL of ADR-0067: `docs/design/DS-28-settings.sql` holds `setting_preset`, `setting_preset_item`, `company_setup_acknowledgement`, and on `setting_value` the columns `preset_code`, `preset_version` and `setup_acknowledgement_id` with the trigger's setup check; `DS-20-master-data.sql` holds `company.first_operating_posting_at`; `DS-15-access.sql` holds `segregation_exception.kind` `own_agent_draft_approval` and `own_run_taint_clearance`; `DS-05-platform.sql` holds `audit_record.is_review_skipped`. The ledger's statement that sets `first_operating_posting_at` (R831) is added to the journal line trigger of `DS-06-universal-journal.sql` at acceptance, because the draft trigger does not yet read the entry's fiscal year; until then R831 states it.
Source: ADR-0067.R20

### Lab check and edge cases of the settings registry

R862. The lab check `t24_settings.py` covers: the catalog is checkable (every row has scope, a default or fail-closed, bounds, a direction and a known leaf; the default lies within its bounds; every key ADR-0063 names is in the catalog and the reverse); the change path as a pure function (tightening immediate, loosening only by an approved proposal from another person, outdating evidence) and in the database (the derived change kind, a first value looser than the core default, copies tied to the definition, the installation maximum); bounds as a property test over random values; the gates of ADR-0063 rules 8 and 9; the default of ADR-0063.R11 reproducing today's wake-ups; the bounds, breaker and flood guard of ADR-0063.R21; the period-start rule of ADR-0063.R24; and the default of ADR-0063.R26.
Source: ADR-0063.R30

R863. With `--load`, `t24_settings.py` checks the DDL: definitions loaded from the catalog under their checks, values outside bounds refused by the database, loosening without a proposal or approved by its proposer refused, rows append-only, installation rows only under the installation setting, extension point ceilings and decision kinds, suspension pairs, and the new columns and values.
Source: ADR-0063.R30

R864. The quotation agent is a Phase 2 agent type. In Phase 1 `EC-185` is re-hosted on the `purchase_invoice` agent's `supplier_invoice_received`, set to `by_rule` with a rule on one supplier, and the catalog row says so (ADR-0078.R9a). The edge cases `EC-186` to `EC-193` of ADR-0063 follow it unchanged (section Edge cases; `EC-188` in chunk 4).
Source: ADR-0063.E.N1

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows of ADR-0067.

Cited and not written in this module, their catalog sources being rules of other modules: `INV-38` (`module_activation`; ADR-0015.R11.N1, rows in `ledger` and `master_data`), `INV-84` (ADR-0029.R9, ADR-0029.R11, ADR-0065.R12), `INV-88` (ADR-0029.R8) and `INV-730` (ADR-0064.R1, ADR-0064.R4).

| Invariant | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-800` | day | `setup_loosening_acknowledged`: Every `setting_value` with a `setup_acknowledgement_id` was recorded while its company's `first_operating_posting_at` was null or later, by that acknowledgement's implementer, under an acknowledgement of the same company given by a holder of the `owner` role template and not revoked at that instant, for a key whose scope is not `installation`, whose `outdates` is `none`, and that is not an `auto_post.*` key. Area `safety`. | R833, R835, R838 |
| `INV-801` | day | `review_skip_conditions`: Every `audit_record` with `is_review_skipped` true belongs to a single executed `Post` command by actor kind `human`, on a date when `ui.post_review` was `on_exceptions` and `ui.post_review_max_amount` above 0, of a document version without effective taint and without agent-written or origin-run versions, with no check codes, a policy decision `allowed` without confirmation and no true policy flag, and an amount at or below that maximum. Area `safety`. | R844, R847, R848 |
| `INV-802` | day | `presets_within_registry`: Every `setting_preset_item` of kind `setting` names a registered company-scope key with storage `setting_value`, `outdates` `none` and a core default that is not `fail_closed`, with a value within its bounds or a parameter of the same preset version whose bounds lie within them; no `policy_rule` item has effect `allow`; and the preset `standard` lists every setting, command setting and record default key another preset lists. Area `platform`. | R817, R818, R819 |
| `INV-803` | day | `own_agent_draft_approval_bounded`: Every approval of a document version by a human for whom an agent run wrote a version of that document has a `segregation_exception` of kind `own_agent_draft_approval`, recorded while `permissions.small_company_mode` was on, every such run having been started by an event or schedule, the approved version without effective taint, and the approver holding the `owner` or `chief_accountant` role template. Area `safety`. | R811; ADR-0067.R16, ADR-0054.R20 |
| `INV-804` | day | `setup_phase_marker`: `company.first_operating_posting_at` is null exactly while the company has no journal entry outside the migration fiscal year, and is not later than the `recorded_at` of the first such entry. Area `platform`. | R830, R831 |
| `INV-805` | day | `own_run_taint_clearance_bounded`: Every `taint_clearance` whose actor is the human the tainting run acted for was recorded while `permissions.small_company_mode` was on, by a single `ClearTaint` command with a reason, and has a `segregation_exception` of kind `own_run_taint_clearance`; no `policy_decision` has `auto_post_decision` `auto_post` in mode `live` for a draft whose only clearances are such self-clearances; and no `agent_promotion_evidence` figure counts such a version. Area `safety`. | R811; ADR-0067.R17, ADR-0029.R8 |

## Edge cases

Statements are those of `edge-cases.csv`.

| Edge case | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-250` | `quickflows_setup_one_person`: The only user of a new company acknowledges themself as implementer and applies `quickflows` with a risk amount, then sets `ui.post_review_max_amount`; `ui.post_review` `on_exceptions` and the maximum are recorded as setup loosenings without a second approver, the small-company mode is enabled, the policy rules `quickflows.from_risk_amount`, `quickflows.credit_exceeded`, `quickflows.cost_unknown` and `quickflows.price_below_cost` are created, and `setup_loosening_review` is raised. | `must_succeed` | R822, R833, R835, R840 |
| `EC-251` | `setup_path_closed_after_go_live`: A migration's opening entries do not end the setup phase; after the first ordinary sales invoice posts, a setup-path loosening is refused with `setup_phase_closed` and a direct loosening returns `proposal_required`. | `must_reject:setup_phase_closed`, `must_reject:proposal_required` | R831, R835, R839 |
| `EC-252` | `one_click_post_clean`: Under `quickflows` a person posts a clean sales invoice below the post review maximum and the risk amount; the simulation returns no review reason, the client executes at once, the audit record has `is_review_skipped`, and the history shows the plan. | `must_succeed` | R844, R846, R848 |
| `EC-253` | `one_click_post_exception`: The same person posts an invoice above the post review maximum, then a goods delivery with a negative-stock check result; both return review reasons and open the plan panel; a client that sends `is_review_skipped` anyway gets `post_review_required` and nothing is committed. | `must_reject:post_review_required` | R844, R847 |
| `EC-254` | `owner_approves_event_agent_draft`: In the small-company mode the purchase invoice agent drafts an invoice from a supplier e-mail for the owner as workflow owner; the chief accountant clears its taint; the owner approves it above the risk amount and an `own_agent_draft_approval` exception is recorded; a draft from a run the owner started with their own note is refused with `segregation_of_duties`. | `must_succeed`, `must_reject:segregation_of_duties` | R811; ADR-0067.R16 |
| `EC-255` | `preset_drift_and_tighten`: After `quickflows` the owner sets `ui.post_review` back to `always` at once (a tightening); `ListSettingPresetDrift` lists it, and the next post shows the plan panel. | `must_succeed` | R825, R826 |
| `EC-256` | `self_clear_taint_small_company`: In a one-person company with the small-company mode on, the owner clears the purchase invoice agent's tainted draft with a reason; an `own_run_taint_clearance` exception is recorded, the gateway still treats the draft as tainted (`require_human`), and a bulk clearance of two such drafts is refused with `segregation_of_duties`; with the mode off, the single clearance is refused with `segregation_of_duties`. | `must_succeed`, `must_reject:segregation_of_duties` | R811; ADR-0067.R17 |
| `EC-185` | `wake_up_by_rule`: The purchase invoice agent's `supplier_invoice_received` is set to `by_rule` with a rule on one supplier; an incoming e-invoice record of that supplier starts the agent, one of another supplier stays with people. Area `tax`, first step 7. | `must_succeed` | R864; ADR-0063.R11 |
| `EC-186` | `personal_values_without_permission`: With the routing switch off and no permission, a drafting step receives placeholders and a step that needs the value ends `routing_blocked`; the upgrade raised `setting_review_required`. | `must_succeed` | R864; ADR-0063.R15 |
| `EC-187` | `provider_terms_change`: The provider registry changes an endpoint's terms reference; the permission is suspended, vision runs end `routing_blocked`, and `data_processing_permission_suspended` is raised. | `must_succeed` | R864; ADR-0063.R14 |
| `EC-189` | `automation_flood_guard`: A mass import fires a rule 600 times in one hour; 500 executions act, 100 are `rate_limited`, one `automation_rule_rate_limited` item is raised, and the breaker does not trip. | `must_succeed` | R864; ADR-0063.R21 |
| `EC-190` | `purchase_return_option_from_period_start`: A company switches the purchase return option mid-period and is refused with `setting_effective_date_invalid`; from the next period start it succeeds, and a return in that period is valued at the preliminary price with the difference to the price difference key. | `must_reject:setting_effective_date_invalid`, `must_succeed` | R864; ADR-0063.R24 |
| `EC-191` | `day00_reject_category`: A category set to `reject` refuses a (17) with day 00 as `gs1_invalid` (`date`), while another category reads it as the month's last day. | `must_reject:gs1_invalid`, `must_succeed` | R864; ADR-0063.R26 |
| `EC-192` | `near_duplicate_payment_held`: A second invoice of the same seller, one minor unit apart and three days later, posts with its open item blocked for payment and a `duplicate_document_review`; resolving it as not a duplicate releases the block. | `must_succeed` | R864; ADR-0063.R27 |
| `EC-193` | `product_code_manual_category`: A category with manual codes refuses a duplicate code with `product_code_taken`, and once a sales order refers to its item a code change returns `product_code_immutable`. | `must_reject:product_code_taken`, `must_succeed` | R864; ADR-0063.R22 |

## Settings

Values are those of `settings.csv`.

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `ui.post_review` | enum `always`, `on_exceptions`; direction `order:on_exceptions<always`; storage `setting_value`; leaf `company_setting`; `immediate`; `outdates` `none` | `company` | `always` | R827, R841, R842, R844 |
| `ui.post_review_max_amount` | amount, bounds `0..`; `lower_tighter`; storage `setting_value`; leaf `company_setting`; `immediate`; `outdates` `none` | `company` | 0 | R827, R841, R842, R844 |

`permissions.small_company_mode` (R815, R827) is a `command_setting`: a company setting with its own commands outside the registry (ADR-0054.R20), with no row in `settings.csv`. The preset parameter `risk_amount` is not a setting.

Reads: `messaging.message_retention_days` (`work`; ADR-0076.R10, retention of messages in `setting_value` history); `cash.bank_charge.auto_post_ceiling`, `automation.breaker_failures`, `automation.breaker_consecutive`, `agents.tainted_reference_reads` (named by the edge cases above; rows with the rules that use them).

## UI annotations

- Floorplan: the plan panel is its own floorplan `plan_panel`, opened over the route by the simulate response of `Post<Type>`; for agent-written drafts it adds a field-level diff against the previous version and the taint badge, and `on_exceptions` never skips it for them (R843, R844).
- Work item kind of module `registry` (catalog `work-item-kinds.csv`): `setup_loosening_review`, subject table `company`, owner rule `company_owner`, due rule `days:30`, resolution `person`, not agent-resolvable; it lists every setup loosening with its old and new value, reminds the owner while `ui.post_review` is `on_exceptions` and `ui.post_review_max_amount` is still 0, and shows on the close checklist while open without blocking the lock (R840).
- The sources of this chunk hold no tile or field annotation of ADR-0077.

## Conflicts

CONFLICT ADR-0065.R1: the build line placing the purchase invoice checker at step 6 is corrected to step 7, after the manual purchase invoice path, by the later note ADR-0065.R1.N1 (ADR-0078); R805 states it.
CONFLICT ADR-0067.R6: the seeded table gains the record default `company.valuation_area_level` (`site` in standard, `company` in quickflows) from the later ADR-0068.R7; R829 lists it.
CONFLICT ADR-0067.R18: the company defaults bullet, filling `company.valuation_area_level` through an optional preset code of `CreateCompany`, comes from ADR-0068.R7 and governs; R857 states it.
CONFLICT ADR-0063.E.N1: the catalog row of the wake-up edge case moves from the quotation agent, now a Phase 2 type, to the purchase invoice agent under ADR-0078.R9a; R864 and the Edge cases row state the moved case.

## Trace

| Source | Where |
| --- | --- |
| ADR-0063.R30 | R862, R863 |
| ADR-0063.E.N1 | R864 |
| ADR-0065.R1 | R801-R804 |
| ADR-0065.R1.N1 | R805 |
| ADR-0065.R2 | R806, R807 |
| ADR-0067.D0 | R810, R811 |
| ADR-0067.R1 | R812, R813 |
| ADR-0067.R2 | R814-R816 |
| ADR-0067.R3 | R817-R820 |
| ADR-0067.R4 | R821-R824 |
| ADR-0067.R5 | R825, R826 |
| ADR-0067.R6 | R827-R829 |
| ADR-0067.R7 | R830-R832 |
| ADR-0067.R8 | R833, R834 |
| ADR-0067.R9 | R835-R838 |
| ADR-0067.R10 | R839, R840 |
| ADR-0067.R11 | R841, R842 |
| ADR-0067.R11.N1 | R843 |
| ADR-0067.R12 | R844, R845 |
| ADR-0067.R13 | R846-R849 |
| ADR-0067.R14 | R850 |
| ADR-0067.R15 | R851-R853 |
| ADR-0067.R18 | R854-R857 |
| ADR-0067.R19 | R858, R859 |
| ADR-0067.R20 | R860, R861 |
| ADR-0073.R12 | ref: ADR-0073.R12 |
| ADR-0076.R10 | ref: ADR-0076.R10 |
| ADR-0077.R10a | ref: ADR-0077.R10a |
| ADR-0079.R7.N3 | ref: ADR-0079.R7.N3 |
