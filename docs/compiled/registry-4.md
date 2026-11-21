Module: registry    Chunk: 4 of 5    Source ADRs: ADR-0063
Build step(s): 1    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `registry`, chunk 4

## Purpose

`registry` owns the command registry and the settings registry. This chunk states the settings law of ADR-0063 that the
registry itself carries: the asymmetric change path (tighten at once, loosen by proposal), bounds and scopes, setup and
upgrades, the cross-cutting hard locks, the declared tainted projections, the extension point registry, the commands and
queries of the settings registry, and the catalog rows of ADR-0063 with the definitions later ADRs registered. The
definition and storage of a setting (ADR-0063.R1, ADR-0063.R2) stand in chunk 3; operating presets and the setup phase
(ADR-0067) in chunk 5. The settings of other areas (ADR-0063 rules 7 to 27) are stated by the modules that use them.

## Entities and tables

DDL: `docs/design/DS-28-settings.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `extension_point` | Installation data: one row per extension point a module declares, written at startup; no runtime in Phase 1 (R631) | `id` (uuid5 of `extension_point:<code>`, computed by the loader); `code` unique | none | `registry` |

Named by the rules of this chunk, with their rows in the chunks whose rules define them: `setting_definition` and
`setting_value` (ADR-0063.R1, ADR-0063.R2), `company_setup_acknowledgement` and `setting_preset` (ADR-0067). This chunk
uses these columns of `setting_value`: `change_kind` (`tighten`, `loosen`, `neutral`), `effective_from`,
`change_proposal_id`, `approved_by_user_id`, `setup_acknowledgement_id`, `preset_code` and `preset_version`.

Reads: `company` (`first_operating_posting_at`), `policy_rule_version` (`shadow_evidence`, `evidence_setting_keys`, `shadow_evidence_outdated_by`), `change_proposal`, `posting_period`, `item`, `product`, `data_processing_permission`, `bank_statement_line`, `lot`, `automation_rule`, `policy_rule`, `document`, `role`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `UpdateCompanySetting` | A person (`human_only`, on no agent tool list); leaf `company_setting`, and `edit` on the key's leaf; a loosening is `is_proposal_bound` and its approver holds the key's leaf at `full` | Key, scope, value, reason, effective date; evidence where the definition asks for it | Effect class `master_data_change`; change-tracked; writes a `setting_value` row (R602 to R610) | not stated | `proposal_required`, `approver_is_submitter`, `setting_effective_date_invalid`, `setting_out_of_bounds`, `setting_scope_invalid` |
| `RunSettingUpgradeCheck` | `system` job at startup and upgrade; `is_internal_only`; leaf `company_setting` | not stated | Effect class `other`; writes definitions and changed installation values; raises `setting_review_required` (R616) | not stated | not stated |
| `ListSettingDefinition` (query) | leaf `company_setting`; the catalog level of the verb `List` is `read`; agents read it as reference data (ADR-0063.R1) | not stated | Lists the `setting_definition` rows as reference data | none (query) | not stated |
| `ListSettingValue` (query) | leaf `company_setting`; the catalog level of the verb `List` is `read` | not stated | The value history with old, new, actor and reason | none (query) | not stated |
| `EvaluateSetting` (query) | leaf `company_setting`; the catalog level of the verb `Evaluate` is `read` | Key, scope and date | The effective value with its source | none (query) | not stated |

Commands and queries of other modules that R634 lists: `UpdateCompanyRegimeOption` (`localization`),
`RunDataProcessingProviderCheck`, `SetDataProcessingPermission` and `EndDataProcessingPermission` (`agents`),
`ListItemCandidate` (`master_data`; returns `tainted_projection_cap_reached`, R626) and `GetArtifactVersionContent`
(`configuration`). Named by the rules and registered elsewhere: `AcknowledgeCompanySetup` (ADR-0067) and
`EnablePolicyRule` (ADR-0043).

Codes of R640 bound to no command of this chunk: `product_code_immutable` and `product_code_taken` (ADR-0063.R22).

Authorization area of `registry` for these commands: `company_setting` under `administration` (catalog
`authorization-areas.csv`: company settings and numbering configuration).

## Rules

### The asymmetric change path

R601. Each setting definition declares its direction: `higher_tighter`, `lower_tighter`, `true_tighter`, `false_tighter`, `subset_tighter`, `superset_tighter`, an order from loosest to tightest (`order:a<b<c`), or `neutral`. A change is a tightening, a loosening or neutral by comparing the new value with the effective value it replaces at that scope.
Source: ADR-0063.R3

R602. A tightening is immediate, by one person holding `edit` on the definition's leaf, through `UpdateCompanySetting` (R633). It never waits for an approval, so reducing autonomy is always one person's act.
Source: ADR-0063.R3

R603. A loosening is accepted only from the execution of an approved change proposal (ADR-0029, ADR-0043.R12), except on the setup path of R604. A person with `edit` on the leaf submits it with a reason and, where the definition asks for it, evidence. A person holding the leaf at `full` who is neither the submitter (`approver_is_submitter`) nor a writer of the proposal (ADR-0055.R7, condition 5) approves it. A direct loosening returns `proposal_required`. As for agent promotions (ADR-0050.R14), the small-company mode does not lift `approver_is_submitter` here, so a one-person company cannot loosen a setting by proposal, the first raise of `cash.bank_charge.auto_post_ceiling` from 0 included; it runs on the core defaults or tighter, or on what it set on the setup path.
Source: ADR-0063.R3, ADR-0063.R3.N2

R604. Before go-live (`company.first_operating_posting_at` is null: no journal entry outside the migration fiscal year), a loosening of a key whose `outdates` is `none` is accepted without a proposal from the implementer an owner acknowledged (`AcknowledgeCompanySetup`), at a scope other than `installation` and never for an `auto_post.*` key (ADR-0067.R9). The `setting_value` row records the acknowledgement (`setup_acknowledgement_id`) instead of a proposal and approver, so a one-person company can set its policy at implementation. After go-live R603 applies in full, and `setup_loosening_review` lists the setup loosenings for the owner (ADR-0067.R7, ADR-0067.R8, ADR-0067.R9, ADR-0067.R10).
Source: ADR-0063.R3.N2

R605. A change takes effect from the execution of the approval, or from the first day of the next posting period where the definition says `period_start`; it is never backdated. A date that breaks this returns `setting_effective_date_invalid`.
Source: ADR-0063.R3

R606. A definition with `outdates: auto_post` makes the executing transaction of a loosening mark stored evidence as outdated: `policy_rule_version.shadow_evidence_outdated_by` names the new `setting_value` row (the marker of ADR-0059.R6; DS-05 states the marker's statement on the column). The mark goes on the company's enabled auto-post rule versions whose evidence is not yet outdated and whose `evidence_setting_keys` contain the key, and on no other. Re-arming needs a new rule version with new evidence.
Source: ADR-0063.R3, ADR-0063.R3.N1

R607. The dependency of evidence on a key is declared, not inferred. `EnablePolicyRule` stores with the evidence the registered keys with `outdates: auto_post` that the evidence hook read when it judged the evidence, in `policy_rule_version.evidence_setting_keys` (set once with `shadow_evidence`, never empty), and their values in force in `shadow_evidence.settings`; the hook returns both (ADR-0043.R14). A cascade rule lists `auto_post.max_error_rate` and the `cash.auto_post.*` keys it read; a `bank_charge` rule also lists the `cash.bank_charge.*` keys; an import rule of ADR-0064 lists the `production.confirmation.*` and `production.mes_import.*` keys. The dependency is per key: a loosening at one scope of a scoped key, such as one money account's `cash.bank_charge.codes`, marks every rule version that lists the key.
Source: ADR-0063.R3.N1

R608. With `outdates: promotion`, evidence is judged under the thresholds in force when its promotion executes. Stored evidence that was insufficient never becomes sufficient by a later loosening: the promotion needs new evidence.
Source: ADR-0063.R3

R609. A neutral change is made directly by a person holding `edit` on the leaf, with a reason, from the date the definition allows.
Source: ADR-0063.R3

R610. No agent and no rule changes a setting: `UpdateCompanySetting` is `human_only` and on no agent tool list (ADR-0050.R30), and an automation rule never changes a setting (ADR-0058.R3).
Source: ADR-0063.R3

### Bounds and scopes

R611. Hard bounds are part of the definition: a closed numeric range, an open range (`0..`, at least 0), the allowed values of an enumeration, or a schema. A value outside them, a fractional value of an integer type, or a value that breaks an order between settings the registry declares (such as `automation.breaker_consecutive` at least `automation.breaker_failures`) returns `setting_out_of_bounds`. No bound includes a value that switches off a hard lock (R621).
Source: ADR-0063.R4

R612. A key accepts values only at its declared scopes. An unknown key, an undeclared scope or a scope reference that names no record of the company returns `setting_scope_invalid`. A narrower scope changes the value for its records through the same path: overriding a company value with a looser category value is a loosening.
Source: ADR-0063.R4

R613. A key with a placeholder exists only for the values the registry lists for it: document types and fields that declare trust settings, agent types and their kinds, extension points, and the date AIs of ADR-0063.R26.
Source: ADR-0063.R4

### Setup and upgrades

R614. At implementation the setup flow shows the registry grouped by `area`, each setting with its core default, bounds, direction and meaning. A company starts on the core defaults, which are the safe values. Setting a value during setup follows R601 to R613: a first value is compared with the core default it replaces, so it is direct for a tightening or a neutral value and a proposal for a loosening, except on the setup path before go-live (R604).
Source: ADR-0063.R5, ADR-0063.R5.N1

R615. Operating presets apply a named, versioned set of values through the checks of R614, each value recorded with the preset's code and version (`preset_code`, `preset_version`). The preset `standard` reproduces the core defaults (ADR-0067.R2, ADR-0067.R3, ADR-0067.R4, ADR-0067.R5, ADR-0067.R6, ADR-0067.R9).
Source: ADR-0063.R5.N1

R616. Nothing is silent on upgrade. A new setting's core default reproduces the behavior before it, unless that behavior was unsafe. Then the ADR that adds it says so, and the upgrade step `RunSettingUpgradeCheck` raises `setting_review_required` for `company_owner` in every company the change affects, naming the key, the old behavior and the new default.
Source: ADR-0063.R5

R617. These defaults of ADR-0063 are tightenings against the behavior before it: personal values on every request need a permission (ADR-0063.R15); a near-duplicate invoice holds payment until a person reviews it (ADR-0063.R27); an OCR confidence floor of 0.90 for trusted fields (ADR-0063.R7); at most 500 executions of one rule per hour (ADR-0063.R21) and at most 200 active rules (ADR-0063.R20); analysis questions are pseudonymized before a model call (ADR-0063.R17).
Source: ADR-0063.R5

R618. These defaults of ADR-0063 are loosenings against the behavior before it: demotion is judged only over at least 30 decisions (ADR-0063.R10), because fewer decisions demote on noise; declared projections are read by tainted runs by default (R627), a reading that is confirmed (R628); the best-before date does not fill a lot's expiry date (ADR-0063.R26), so fewer lots are blocked by expiry, because a quality date is not a safety date.
Source: ADR-0063.R5, ADR-0063.R16.N1

R619. New behavior of ADR-0063 is off or unchanged by default: the `bank_charge` class (ADR-0063.R9) and LLM-originated rules (ADR-0063.R8) are both off; wake-up modes (`always`), drift actions (`signal`), the breaker settings (5, 60, 20), product codes, unit names, the purchase return options and the narrative mode keep the behavior before ADR-0063.
Source: ADR-0063.R5

R620. The designs of ADR-0063.R15, ADR-0063.R21 and ADR-0063.R26 are not built yet, so no installation changes; `setting_review_required` is raised for any company that exists when a change is built.
Source: ADR-0063.R5

### Hard locks

R621. The cross-cutting hard locks are kept few, each with its reason. No setting value relaxes one:
- Numbers come only from code (Principle 13); analysis prose is dropped on any unbacked number (ADR-0063.R25). Reason: a wrong figure in an ERP is a booking or a decision; model text is not a source of figures.
- The audit trail, and the processing log written before every model call (ADR-0050.R10). Reason: accountability and the processing record cannot depend on a setting.
- Agents never submit, post, send or approve on their own authority; auto-post only on the evidence-gated deterministic paths (ADR-0043.R9), of which the auto-post gateway of ADR-0065 is one. Reason: spec 03 rules 1, 5 and 6; segregation of duties.
- Taint persists, and a tainted run writes drafts only (ADR-0029, ADR-0050.R25); a checked tainted draft may be posted by `system` only under ADR-0065.R10. Reason: the prompt-injection containment; no setting may open an exit for outside content.
- Labels from the schema are never lowered; an unknown kind counts as personal; sensitive personal values are never sent in Phase 1 (ADR-0050.R9). Reason: detection-based masking misses data; the schema knows.
- The automation circuit breaker cannot be turned off, its failure definition is fixed, and the depth cap stays 3 (ADR-0063.R21). Reason: termination and bounded side effects.
- No AI-written code runs without a human review of its source and a reproducible build (R630 to R632; ADR-0059.R24). For repository code the lock reads: no AI-written code is merged unless every required check and two independent model reviews pass (ADR-0073). Reason: code is reviewed before it runs; a model cannot ship code.
- Check digits and other integrity checks of standards (GS1, IBAN, tax ID rules). Reason: they are the standard, not a preference.
- Every learned or probabilistic matching path that auto-posts (the scored matches of the bank cascade and of matching rules, tuned parameter sets) needs evidence of N proposals with at least (1 − `auto_post.max_error_rate`) posted unchanged, N ≥ 3 ÷ `auto_post.max_error_rate`, the rate never above 2% (ADR-0063.R10); a confirmed wrong auto-post suspends auto-post at once. Reason: a threshold without an evidence floor is not a control an audit can rely on.
- An `llm_suggestion` draft is never auto-posted (ADR-0063.R8). Reason: spec 03 rule 1 at run time.
Source: ADR-0063.R6, ADR-0063.R6.N1, ADR-0063.R6.N2

R622. The auto-post gateway's own hard locks join the list of R621: no LLM in the checker, fail closed, read-only evaluation, system execution, the plan check and confirmation. On the gateway a confirmed wrong auto-post suspends the whole document type (ADR-0065.R7, ADR-0065.R10, ADR-0065.R16).
Source: ADR-0063.R6.N1

R623. For the repository, the mechanical layers of ADR-0073 and two model reviews take the place of the human review of source. A model still cannot ship code: only the author merges, and only when every required check is green (ADR-0073.R16). The extension approval of R631, by a person with a technical role, is unchanged.
Source: ADR-0063.R6.N2

R624. A deterministic `bank_charge` rule (ADR-0063.R9: a configured bank transaction code on that money account, a debit, no counterparty account, an amount cap, period-end confirmation) is not a learned or probabilistic path. It is governed by its determinism, its cap and the confirmation.
Source: ADR-0063.R6

R625. The list of R621 is the cross-cutting set. The "Hard:" bullets of ADR-0063 rules 7 to 27 (in this chunk R632) are scope limits of each setting: no value of that setting relaxes them.
Source: ADR-0063.R6

### Tainted reads of declared projections

R626. The registry attribute `tainted_projection` on a query's result model names the columns a tainted run receives (ADR-0050.R27; ADR-0062.R17; ADR-0029.R14). CI accepts only closed shapes (ID, code, unit, status, category, date, quantity) and `internal` names, never prices, costs, stock, partner columns, `personal` columns or free text. The first instance is `ListItemCandidate` (ADR-0062.R17 called it `ResolveItemCandidates`; ADR-0004.R21 allows only `Get`, `List`, `Evaluate` and `Render` as query verbs): id, code, name, unit, category and status of items, by typed match keys (code, barcode, normalized name), at most 20 rows per call and at most 10 calls per run; rows restricted to another partner are excluded. Beyond the call cap it returns `tainted_projection_cap_reached`.
Source: ADR-0063.R16

R627. The setting `agents.tainted_reference_reads` (company, with an optional per-agent-type value) is `literal` or `declared_projections`, default `declared_projections`. An agent type version uses a projection only when it names the query on its tool list.
Source: ADR-0063.R16

R628. Declared projections join the reference data of the literal scope (ADR-0050.R27, item 4) as the reading of spec 03 rule 1, and the reading is confirmed: ADR-0050.R27 stays, declared projections are the only read beyond its items 1 to 3, the tainted catalog read for matching is answered by them, and the readings (a) to (r) of the cited ADRs stand as readings of that rule. The setting only narrows the reading back to the literal scope, so no setting widens the floor (ADR-0029.R14). The run stays tainted; projected calls are recorded in the step's `context_refs` with the projection version and the row count.
Source: ADR-0063.R16, ADR-0063.R16.N1

### Extension points

R630. Phase 1 ships the extension point registry only (ADR-0059.R24 stands). A module may declare an `extension_point` (installation data written at startup): code, module, typed input and output schemas, a code default, ceilings for fuel, memory and deadline, the decision kind (`score`, `classification`, `derivation`, `validation`) and `is_gate_feeding`, whether its output may feed a gate (default false). No runtime ships in Phase 1.
Source: ADR-0063.R19

R631. After Phase 1 the runtime is WebAssembly with deterministic fuel metering, under `extensions.wasm_enabled` (installation, default false; its bound is false while no runtime exists) and, per company and point, `extensions.<point>.max_fuel` (10,000,000 instructions, bounds 100,000 to 50,000,000 and the point's ceiling), `extensions.<point>.max_memory_bytes` (8 MiB, bounds 1 to 16 MiB) and `extensions.<point>.deadline_ms` (50, bounds 5 to 250). An extension module follows the lifecycle of ADR-0059: pinned by content hash, tests approved first, a reproducible build from reviewed source, and approval by a person with a technical role. A trap, exhausted fuel or a timeout returns the code default.
Source: ADR-0063.R19

R632. Hard limits of extensions: no host imports for I/O, clock, randomness, network or database; metering always on; no extension at approval, posting, rights or settings decisions (the decision kinds exclude them); an output feeds an acting gate only where the point declares it and after the evidence of ADR-0051.R18.
Source: ADR-0063.R19

### Commands and queries of the settings registry

R633. The commands and queries of module `registry`:
- `UpdateCompanySetting`: effect class `master_data_change`; leaf `company_setting`, and `edit` on the key's leaf; `human_only`; change-tracked; a loosening `is_proposal_bound` (R603); on no agent tool list.
- `RunSettingUpgradeCheck`: effect class `other`; leaf `company_setting`; system job at startup and upgrade; `is_internal_only`; writes definitions and changed installation values, raises `setting_review_required`.
- `ListSettingDefinition`, `ListSettingValue`, `EvaluateSetting`: queries; leaf `company_setting`; definitions as reference data; the value history with old, new, actor and reason; the effective value with its source for a key, scope and date.
Source: ADR-0063.R28

R634. ADR-0063 registers or changes these commands and queries of other modules:
- `UpdateCompanyRegimeOption` (ADR-0016), module `localization`, `master_data_change`, leaf `regime_option`: writes `setting_value` rows under R601 to R613, and from `period_start` where declared.
- `RunDataProcessingProviderCheck`, module `agents`, `other`, leaf `data_processing`: system job at startup and daily; `is_internal_only`; suspends permissions (ADR-0063.R14).
- `SetDataProcessingPermission`, `EndDataProcessingPermission` (ADR-0057), module `agents`, `master_data_change`, leaf `data_processing`.
- `ListItemCandidate`, module `master_data`, query, leaf `product`: the declared tainted projection (R626).
- `GetArtifactVersionContent`, module `configuration`, query, leaf `configuration`: canonical JSON and content hash for export (ADR-0063.R20).
Source: ADR-0063.R28

### Catalog rows

R640. The catalog rows of the settings registry:
- Settings catalog: `settings.csv` (`docs/catalogs/settings.csv`, version 0.1.0, with a row in the catalogs README) is authoritative for the registered definitions: those of ADR-0063 rules 7 to 27 and those later ADRs registered (R641 to R648). Its `source` column names the rule or note that registers each definition.
- The reserved `crm.interaction_retention_days` (ADR-0052.R30) is not registered: the retention class `crm_interaction` of ADR-0079.R9 takes its place.
- Errors (DS-04): `setting_out_of_bounds`, `setting_scope_invalid` (validation); `setting_effective_date_invalid` and `product_code_immutable` (precondition); `tainted_projection_cap_reached` (permission); `product_code_taken` (conflict). Loosening without a proposal reuses `proposal_required`, and a self-approval `approver_is_submitter`.
- Work item kinds: `setting_review_required` (module `registry`, subject `company`, `company_owner`, `days:5`, person), `data_processing_permission_suspended` (`agents`, subject `data_processing_permission`, `company_owner`, `days:1`, person), `automation_rule_rate_limited` (`automation`, subject `automation_rule`, the rule's owner, `days:1`, person), `auto_post_suspended` (`policy`, subject `policy_rule`, `rule_owner`, `days:1`, person) and `duplicate_document_review` (`purchasing`, subject `document`, `role:accountant`, `days:2`, person).
- Authorization leaf `data_processing` under `agent` (module `agents`), ADR-0054.R7.
- DDL: `DS-28-settings.sql` holds `setting_definition`, `setting_value` with its insert trigger and row-level security, and `extension_point`; `DS-36-document-intake.sql`: `data_processing_permission` has `purposes`, `provider_terms_ref`, `provider_retention_days`, `suspended_at` and `suspension_reason`; `DS-05-platform.sql`: `bank_statement_line.bank_transaction_code`, match basis `bank_charge_rule`, and the outdated marker's comment; `DS-28-34-configuration-artifacts.sql`: execution outcome `rate_limited`; `DS-20-master-data.sql`: `lot.best_before_date`.
- Invariants `INV-700` to `INV-718` of the block INV-700 to INV-729 (areas `platform`, `safety`, `cash`, `master_data`, `inventory`), and edge cases `EC-180` to `EC-193` of the block EC-180 to EC-199.
Source: ADR-0063.R29, ADR-0063.R29.N17, ADR-0079.R9

R641. Later ADRs registered these definitions; each row's `source` names the ADR, and each new default reproduces the behavior before it:
- ADR-0064.R23: production, planning and agent settings.
- ADR-0065.R8: the `auto_post.<document_type>.*` keys, `auto_post.allow_tainted_drafts`, `auto_post.confirmation_cadence` and the `auto_post.purchase_invoice.*` keys.
- ADR-0066.R4: `work_case.<kind>.mode`, `work_case.<kind>.due_days` and `work.landing_page.<role_template>`. Their direction is `neutral`, because a case grants no right and relaxes no check; by default every kind is `off` and everyone lands on the work queue.
- ADR-0067.R11: `ui.post_review` (default `always`) and `ui.post_review_max_amount` (default 0).
- ADR-0069.R13: `ledger.business_unit.default` and `ledger.business_unit.required_on_profit_and_loss`, in the area `ledger`.
- ADR-0070.R13 and ADR-0070.R14: `quality.usage_decision.separate_from_results` and `quality.usage_decision.auto_accept`.
- ADR-0071.R19: `production.operation.start_when_waiting` and `production.operation.stop_reason_on_pause`.
- ADR-0072.R19: `production.costing_sheet.required`, default false.
- ADR-0074.R22: one boolean per reason kind, from `documents.reason_required.cancel` to `documents.reason_required.other_issue`, leaf `reason`.
- ADR-0075.R15: the regime keys of the count movement types and `stock_count.bin_difference_method`.
- ADR-0076.R11: `messaging.email_notifications`, `messaging.digest_hour` and `messaging.message_retention_days`, leaf `messaging_administration`.
- ADR-0024.R21: `planning.container_underfilled_pct` and `planning.cancel_horizon_days`.
- ADR-0077.R13: `assist.max_cost_per_run`, the cost of one assistant run in USD, company scope, default 0.20, bounds 0.01 to 0.50 (the assistant's interim cost ceiling is USD 0.50; ADR-0078.R1, ADR-0078.R7), lower is tighter.
- ADR-0080.R5: `tax.destination_party`, `tax.services_place_of_supply` (a regime key a package sets and flags), `tax.treatment_rederive_on_change`, `tax.treatment_override.allowed` and `tax.treatment_override.reason_required`.
Source: ADR-0063.R29.N1, ADR-0063.R29.N3, ADR-0063.R29.N4, ADR-0063.R29.N5, ADR-0063.R29.N6, ADR-0063.R29.N7, ADR-0063.R29.N8, ADR-0063.R29.N9, ADR-0063.R29.N10, ADR-0063.R29.N11, ADR-0063.R29.N12, ADR-0063.R29.N14, ADR-0063.R29.N15, ADR-0063.R29.N16, ADR-0063.R29.N20

R642. Agent cost and run limits live in this registry. The notes on ADR-0050.R22, ADR-0013.R10, ADR-0038.R15 and ADR-0042.R12 register their definitions, `source` naming the ADR whose note registers them. `agents.installation_daily_max_cost` and `attachments.delete_grace_days` are deployment values (`operator`); `agents.company_daily_max_cost` takes an installation maximum, as `analysis.narrative_mode` does. The defaults reproduce the behavior before them except `agents.internal_reserve_share` (0.40), a tightening for agent types that read outside content (R616), which raises `setting_review_required` in any company that exists when it is built. The registry holds no per-agent-type daily cost key, daily run count key or run ceiling key of ADR-0050.R22: per-run ceilings live in the agent type declarations (ADR-0078.R1, ADR-0078.R7).
Source: ADR-0063.R29.N2, ADR-0063.R29.N15

R643. The bounds of `cash.auto_post.accept_llm_originated_rules` are `true|false` (ADR-0065).
Source: ADR-0063.R29.N3

R644. The catalog `setting-presets.csv` lists the operating presets `standard` and `quickflows` over the definitions. A preset never sets a value outside a definition's bounds or touches a hard lock of R621.
Source: ADR-0063.R29.N5

R645. The registry holds `movement_type.sales_return_receipt.value_source` and `movement_type.sales_return_receipt.costing_role`, required regime settings with no core default, as the purchase return pair of ADR-0063.R24 (ADR-0020.R5), and `journal.manual_posting_to_control_accounts`, at regime level with core default false (ADR-0014.R10).
Source: ADR-0063.R29.N13

R646. The registry holds `data_protection.breach_notification_hours` (scopes regime and company, core default unset; ADR-0079.R16) and the retention settings `agents.run_step_retention_days` (ADR-0050.R19), `analysis.question_retention_days` (ADR-0060.R11), `attachments.evidence_retention_years` (ADR-0038.R15; a legal period, core default unset), `outbox.event_retention_days` (ADR-0013.R15) and `commands.idempotency_retention_days` (ADR-0008.R19). Each has this dotted registry key with an area segment, as ADR-0063.R2 asks, stated by a note on its rule.
Source: ADR-0063.R29.N17

R647. The registry holds `costing.exchange_rate_difference_to_stock` (boolean, core default true; ADR-0047.R13) and `landed_cost.unplanned_cost_treatment` (`distribute_to_items` or `separate_account`, core default `distribute_to_items`; ADR-0021.R12). Both are regime keys a regime may open as company options, changed only from a period start, as the keys of ADR-0063.R24; their defaults reproduce the behavior before them.
Source: ADR-0063.R29.N18

R648. The registry holds `tax.default_item_tax_group` for the three-level tax classification (ADR-0041.R7): company scope, value type `code` naming an active `item_tax_group`, core default unset, direction neutral, leaf `tax_setup`, effective at once. It is the company default a product takes when neither it nor a category up its parent chain names an item tax group.
Source: ADR-0063.R29.N19

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk; `INV-700` (source ADR-0063 rules 1 and 2) stands with chunk 3, and the rows from `INV-704` to `INV-718` not listed here stand with the modules whose rules they protect.

| Invariant | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-701` | day | `setting_loosening_approved`: Every `setting_value` with `change_kind` `loosen` names an executed, approved change proposal whose approver is neither its submitter nor a writer of it. Area `safety`. | R603 |
| `INV-702` | day | `setting_effective_dates`: No `setting_value` takes effect before the business date it was recorded on, and every value of a `period_start` key takes effect on the first day of a posting period. Area `platform`. | R605 |
| `INV-703` | day | `setting_loosening_outdates_evidence`: Every loosening of a key with `outdates` `auto_post` marked the evidence of every dependent enabled auto-post rule version of the company outdated in its own transaction. Area `safety`. | R606, R607; ADR-0059.R6 |
| `INV-710` | day | `tainted_projection_columns`: Every response a tainted run received from a declared projection held only the projection's columns, at most 20 rows, and within the run's call cap. Area `safety`. Flagged in the catalog: declared projections as a reading of spec 03 rule 1 (the reading is confirmed, R628). | R626 |
| `INV-713` | day | `extension_points_bounded`: Every extension point's ceilings lie within the core maxima, its decision kind is not an approval, posting, rights or settings decision (a database check), and no extension ran while `extensions.wasm_enabled` was false. Area `platform`. | R630, R631, R632 |

Source finding: the catalog statement of `INV-701` makes no exception for the setup-path loosenings of R604, which name an acknowledgement and no proposal (ADR-0067.R9); the statement is kept as the catalog has it, and `INV-800` (row in chunk 5) checks those loosenings.

## Edge cases

| Edge case | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-180` | `setting_tighten_then_loosen`: A controller lowers `cash.bank_charge.auto_post_ceiling` at once; raising it again directly returns `proposal_required`; a proposal approved by a second person takes effect and marks the dependent auto-post rule's evidence outdated. | `must_reject:proposal_required` for the direct raise; `must_succeed` otherwise | R602, R603, R606 |
| `EC-181` | `setting_out_of_bounds`: `automation.breaker_failures` 0 and `automation.breaker_consecutive` below the failures setting are refused with `setting_out_of_bounds`; a self-approved loosening is refused with `approver_is_submitter`. | `must_reject:setting_out_of_bounds` | R611, R603 |
| `EC-188` | `tainted_projection_read`: A tainted purchase invoice run lists item candidates through the projection (at most 20 rows, no prices); its eleventh call returns `tainted_projection_cap_reached`; with `agents.tainted_reference_reads` `literal` the call returns `tainted_read_out_of_scope`. | `must_reject:tainted_projection_cap_reached` for the eleventh call; `must_succeed` otherwise | R626, R627 |

`EC-185` to `EC-193`, except `EC-188`, have their rows in chunk 5 (ADR-0063.E.N1); `EC-182` to `EC-184` stand with the modules whose rules their catalog source names.

## Settings

Values are those of `settings.csv`.

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `agents.tainted_reference_reads` | enum `literal`, `declared_projections`; direction `order:declared_projections<literal`; leaf `agent` | `company`, `agent_type` | `declared_projections` | R627, R628 |
| `extensions.wasm_enabled` | boolean, bounds `false`; `false_tighter`; storage `deployment`; leaf `operator` | `installation` | `false` | R631 |
| `extensions.<point>.max_fuel` | integer, bounds 100000 to 50000000; `lower_tighter`; leaf `configuration` | `company` | 10000000 | R631 |
| `extensions.<point>.max_memory_bytes` | integer, bounds 1048576 to 16777216; `lower_tighter`; leaf `configuration` | `company` | 8388608 | R631 |
| `extensions.<point>.deadline_ms` | integer, bounds 5 to 250; `lower_tighter`; leaf `configuration` | `company` | 50 | R631 |

The other keys that the rules of this chunk name (R603, R607, R611, R621, R641 to R648) have their rows with the modules whose rules use them; `settings.csv` is authoritative for their types, bounds and defaults.

## UI annotations

Work item kind of module `registry` named by this chunk (catalog `work-item-kinds.csv`): `setting_review_required`, subject table `company`, owner rule `company_owner`, due rule `days:5`, resolution `person`, not agent-resolvable; the item names the key, the old behavior and the new default (R616). The sources of this chunk hold no floorplan, tile or field annotation of ADR-0077.

## Conflicts

CONFLICT ADR-0063.R3.N2: the note adds the setup path before go-live to the loosening rule; R604 states it and R603 names the exception, governed by ADR-0063.R3.N2 with ADR-0067.R9, whose conditions (scope not `installation`, no `auto_post.*` key) R604 also states.
CONFLICT ADR-0063.R5.N1: the note replaces "a proposal for a loosening, as later" by the setup-path exception before go-live; R614 states the wording of ADR-0063.R5.N1.
CONFLICT ADR-0063.R5: the mark "open for the author's confirmation" on declared projections is dropped in R618, because ADR-0063.R16.N1 confirms the reading; the setup wording follows ADR-0063.R5.N1.
CONFLICT ADR-0063.R16: the bullet "Partly answered ... open for the author's confirmation" is dropped; ADR-0063.R16.N1 confirms the reading and R628 states it as decided.
CONFLICT ADR-0063.R6: the lock on AI-written code is restated for repository code by ADR-0063.R6.N2 (ADR-0073 mechanical layers and model reviews); R621 and R623 state both readings.
CONFLICT ADR-0063.R29: superseded in part by ADR-0079.R9, whose retention class `crm_interaction` stands for the reserved retention key; the typed totals of the rule and its notes are not restated, the catalog `settings.csv` is authoritative (R640).
CONFLICT ADR-0063.R29.N17: the note decides that `crm.interaction_retention_days` is not registered and ADR-0079.R9 governs retention of that class; R640 and R646 state the registered keys only.
CONFLICT ADR-0063.R29.N14: the bounds 0.01 to 2 of `assist.max_cost_per_run` are narrowed to 0.01 to 0.50 by the later note ADR-0063.R29.N15 (ADR-0078); R641 states the narrowed bounds.
CONFLICT ADR-0063.R29.N2: the sentence on per-agent-type budget keys with core default `unset` no longer holds, because ADR-0063.R29.N15 removes those keys; R642 states their absence.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0063.R3 | R601-R603, R605, R606, R608-R610 |
| ADR-0063.R3.N1 | R606, R607 |
| ADR-0063.R3.N2 | R603, R604 |
| ADR-0063.R4 | R611-R613 |
| ADR-0063.R5 | R614, R616-R620 |
| ADR-0063.R5.N1 | R614, R615 |
| ADR-0063.R6 | R621, R624, R625 |
| ADR-0063.R6.N1 | R621, R622 |
| ADR-0063.R6.N2 | R621, R623 |
| ADR-0063.R16 | R626-R628 |
| ADR-0063.R16.N1 | R618, R628 |
| ADR-0063.R19 | R630-R632 |
| ADR-0063.R28 | R633, R634 |
| ADR-0063.R29 | R640 |
| ADR-0063.R29.N1 | R641 |
| ADR-0063.R29.N2 | R642 |
| ADR-0063.R29.N3 | R641, R643 |
| ADR-0063.R29.N4 | R641 |
| ADR-0063.R29.N5 | R641, R644 |
| ADR-0063.R29.N6 | R641 |
| ADR-0063.R29.N7 | R641 |
| ADR-0063.R29.N8 | R641 |
| ADR-0063.R29.N9 | R641 |
| ADR-0063.R29.N10 | R641 |
| ADR-0063.R29.N11 | R641 |
| ADR-0063.R29.N12 | R641 |
| ADR-0063.R29.N13 | R645 |
| ADR-0063.R29.N14 | R641 |
| ADR-0063.R29.N15 | R641, R642 |
| ADR-0063.R29.N16 | R641 |
| ADR-0063.R29.N17 | R640, R646 |
| ADR-0063.R29.N18 | R647 |
| ADR-0063.R29.N19 | R648 |
| ADR-0063.R29.N20 | R641 |
