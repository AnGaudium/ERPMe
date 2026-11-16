# Research: configurable data-processing policy for LLMs, and prompt-injection containment

Date: 2026-11-15. Scope: input for the holistic review of the open questions on the personal vision seat, field-level personal values, the tainted catalog read, the analysis question label and the data-processing policy of `l10n_vn` (`docs/open-questions.md`; ADR-0050 rules 5, 9, 10, 25–28; ADR-0051; ADR-0053 note on rule 9; ADR-0057 rules 11, 17–21, 30; ADR-0060 rule 21; ADR-0062 rule 17). Research only: the ADRs and the open questions decide.

Direction followed: survey best practice, keep hard locks few, make policy configurable at implementation, keep country law in localization packages.

## 1. Where NativeFlows stands

- **Labels from the schema.** Every field has a label (`internal`, `personal`, `sensitive_personal`), evaluated per row (partner kind). An unknown kind counts as personal (ADR-0050 rule 9).
- **`routing_switch`.** A company setting, default off. When on, the gateway replaces personal values with typed placeholders, scans the request for leftovers and blocks a step that needs a removed value. Sensitive personal values never leave in Phase 1.
- **Seat data classes.** Each seat declares the highest label it accepts.
- **Processing log.** Every call that carries a personal value is logged before it is sent: provider, model, and (table, field, row).
- **`data_processing.policy`.** A regime setting with no core default. Per data class it says whether a model provider may process the data, and whether processing abroad needs a recorded assessment. With no value, every check fails closed.
- **`data_processing_permission`.** Company rows naming data class, seat class, provider, region and assessment. They are set through an approved change proposal whose approver is not its submitter. Today the gate covers only whole attachments and the vision seat.
- **Taint.** Outside free text taints a run. A tainted run may run only `is_draft_only` commands, and it reads only the literal scope: subject or partner rows, its work item, its own drafts and reference data.

## 2. Survey: what vendors let customers configure

| Vendor | What is configurable | Scope | Default | Who changes it | Regional expression |
| --- | --- | --- | --- | --- | --- |
| Microsoft 365 Copilot (Anthropic as subprocessor) | Enable a provider. Restrict it to users or groups. Separate opt-in for models with provider-side retention | Tenant, then users or groups | On in most commercial regions. Off ("No users") in the EU, EFTA and UK, because those models were outside the EU Data Boundary. Retention models off everywhere | AI Administrator or Global Administrator | The default depends on the tenant's region. The provider's terms (Microsoft DPA or Anthropic's DPA) are named per option |
| Microsoft Purview DLP for Copilot | Block Copilot from processing content with chosen sensitivity labels | Tenant policy, per label | None (opt-in policy) | Compliance admins | Labels, not countries |
| Dynamics 365 and Power Platform | "Move data across regions" consent for Copilot features. Business Central has its own toggle | Environment (Power Platform), tenant (Business Central) | Business Central: allowed from version 25.0, and turning it off disables Copilot. Power Platform: consent needed where no local endpoint exists | Global or Power Platform admin | Consent is needed only when the environment's geography has no in-region model endpoint |
| Salesforce Einstein Trust Layer | Data masking per data type (pattern and ML detection). Zero data retention with LLM partners. Audit data | Org, per data type | Masking on for certain types once Data 360 is set up. **Masking is disabled for agents** | Setup admins | Retention is contractual. Masking and demasking are logged in Data 360 |
| SAP Generative AI Hub (orchestration) | A data-masking module: anonymize (irreversible) or pseudonymize (reversible), per entity type. Choice of model from several vendors | Orchestration configuration (per scenario) | Off until configured | AI Launchpad users with configuration rights | Residency depends on the deployment and model. SAP's EU AI Cloud offers EU residency |
| ServiceNow Now Assist | Data Privacy for Now Assist: regex patterns, masking technique per policy, placeholders restored after the response. "Data overflow processing" bursts traffic to Azure at peaks | Instance, per pattern and policy | Overflow allowed by default (opt-out). Privacy patterns must be configured | `now_assist_data_privacy_admin` role (privacy), data steward role (overflow) | Opt out of overflow to keep traffic in ServiceNow data centers. Some third-party skills may still leave the region |
| Oracle Fusion AI | Little customer configuration. Models are hosted inside OCI, and Oracle states that no customer data goes to third-party model providers | Vendor-fixed | Fixed | Not applicable | Residency by architecture, not by setting |
| Zoho Zia | Zia on or off per feature. Optional BYOK to OpenAI with a privacy notice that must be accepted. Zoho's own LLM runs in Zoho data centers | Organization or team | Off until an admin enables it | Org or team admin | Zia LLM is deployed in US, India and EU data centers. With BYOK, the provider's terms apply |
| Odoo 19 | AI app with an Odoo-provided connection, or the company's own OpenAI or Gemini key. Provider choice per agent | Database, per AI agent | Odoo's connection | Settings admin | None beyond the provider choice |
| AWS Bedrock | Geographic and global cross-region inference profiles. SCPs deny regions. Guardrails sensitive-information filters per PII entity (BLOCK, ANONYMIZE, NONE), set separately for input and output | Account or organization, per profile and guardrail | In-region unless a cross-region profile is chosen. Prompts are not used for training | IAM and organization admins | Geography is a property of the inference profile, enforced by SCP |
| Azure OpenAI / Foundry | Standard, Data Zone (US, EU) or Global deployments. Modified abuse monitoring (no human review) on approval | Deployment | Abuse monitoring on. No training on prompts. Data at rest stays in the chosen geography | Subscription owners. Modified monitoring needs Microsoft's approval | Deployment type sets the processing area |
| Presidio (open source) | Analyzer (NER, patterns, checksums, custom recognizers), anonymizer, image redactor (including DICOM) | Library | Not applicable | Developers | Not applicable. It warns there is "no guarantee that Presidio will find all sensitive information" |

**Patterns across vendors.**
1. **The provider is a subprocessor that the tenant opts into, with a default that depends on region.** Microsoft is the clearest case: the same toggle defaults on in one region and off in another. Users and groups narrow it further, and models whose retention terms differ need their own opt-in.
2. **Region is an attribute of the endpoint or deployment.** Bedrock profiles, Azure Data Zones, ServiceNow overflow and Power Platform geographies all work this way. The customer picks an endpoint; nobody types a country into a request. NativeFlows's provider registry already follows this pattern.
3. **Masking by detection is the norm, and it is weak.** Salesforce, ServiceNow, SAP and Bedrock all detect PII with patterns or ML. Salesforce disables masking for agents because it breaks grounding, and Presidio states that detection is incomplete. NativeFlows's schema labels are stronger: the system knows which fields are personal before it sends them. Detection should only add protection, never lower a label.
4. **No vendor redacts whole document images by default before sending them to a cloud vision model.** Whole images go to the model under the provider's contract (DPA, no training, zero or limited retention) and the region controls. Redaction tools exist, but none claims completeness. So a page image is controlled as a whole, by permission, which matches ADR-0057 rule 19 ("redaction never makes an image non-personal").
5. **A named role makes the change.** Microsoft uses AI Administrator, ServiceNow a data privacy admin and a data steward. Data protection is a separate duty from running agents.
6. **A master kill switch exists beside the fine-grained settings,** for example disabling the subprocessor or opting out of overflow. NativeFlows's `routing_switch` plays this role.

## 3. Survey: prompt-injection containment

- **OWASP LLM01:2025** says no fool-proof prevention exists. Its mitigations are: constrain behavior; validate output formats deterministically; filter input and output; least privilege, with functions handled in code; human approval for high-risk actions; segregate and mark external content; and adversarial testing.
- **Spotlighting** (Hines et al., 2024) marks untrusted text by delimiting, datamarking or encoding it. NativeFlows uses delimiters and datamarking. Both lower the attack rate; neither is a control.
- **Lethal trifecta** (Willison, 2025): private data, untrusted content and an exfiltration channel together. Removing any one leg breaks the attack path. A read-only tool that reads private data is a leg, but it is dangerous only when the run also has a way out.
- **Design patterns** (Beurer-Kellner et al., 2025): action-selector, plan-then-execute, map-reduce, dual LLM, code-then-execute and context-minimization. Under plan-then-execute, tools may still be called after untrusted data has been read, as long as the plan was fixed before; the paper warns that injection can still steer the tools' arguments. Under dual LLM, the quarantined model has no tools and returns symbolic references that code dereferences.
- **CaMeL** (Debenedetti et al., Google DeepMind, 2025) derives control flow from the trusted query only. Values carry capabilities (sources, readers), and policies are checked when a tool is called. It reports 77% of AgentDojo tasks solved with provable security, against 84% undefended.
- **FIDES** (Costa et al., Microsoft, 2025) adds confidentiality and integrity labels with deterministic enforcement:
  - Consequential tools need a trusted context.
  - Egress tools may send data only to authorized readers.
  - **Read-only tools carry no policy, but labels propagate through them.**
  - Low-integrity results can be hidden in variables. They are inspected by a quarantined LLM whose output type is constrained (bool ⊑ enum ⊑ string), and a low-capacity output carries less injection risk.

**Answer: may a run that has read untrusted input call read-only lookups?** The literature says yes, under four conditions:
1. The lookup is deterministic, and its arguments cannot widen what it reveals.
2. Its result carries labels that propagate. Here, the run stays tainted.
3. Every sink is controlled. Exfiltration needs an egress, and the only egress in NativeFlows is drafts that people later send. A draft is a slow, reviewed exfiltration channel, so what a tainted run may copy into a draft that goes to an outside party is the real question.
4. The result's information is bounded: closed shapes, few rows, no free text. This follows FIDES' capacity lattice and NativeFlows's numeric projections.

None of these sources supports opening the whole master data. All of them support narrow, declared projections.

## 4. Recommendations

### R1. The personal vision seat and the cloud provider for whole personal page images

**Recommendation.** A company may permit the installation's cloud provider for `extraction_vision_personal`. It does not need to wait for a local provider. This matches industry practice: whole images go to cloud vision under contract, region and retention controls, and are never treated as made safe by redaction. Spec 17 should gain the seat (the author's call).

- **Setting:** the existing `data_processing_permission` row (data class `personal`, seat class `extraction_vision_personal`, provider endpoint, region).
- **Registry additions:** add to the provider registry (DS-37) `retention_days` (0 for zero retention), `abuse_review` (`human`, `automated`, `none`), `trains_on_customer_data` (must be false) and `terms_ref` (the DPA in force), so a permission names terms as well as a region. Microsoft's separate opt-in for models with retention shows why.
- **Scope:** company × data class × seat class × provider endpoint and region. A company may also limit it per purpose (`supplier_invoice`, `contact_card`, `inquiry_lines`, `product_source`) through an optional `purposes` list on the row.
- **Default:** no permission, so the seat is disabled and the work stays with people.
- **Bounds:**
  - The permission is refused when the regime's policy forbids it, when `trains_on_customer_data` is true, or when `retention_days` exceeds the regime's `max_provider_retention_days`.
  - `intake.vision_max_pages` may only be lowered.
- **Who may change it:** raising, through a change proposal with a distinct approver (existing). Also recommended: a dedicated leaf `data_processing` under `agent`, so a data-protection officer can approve without the right to manage agents. Narrowing: `EndDataProcessingPermission`, directly (existing).
- **Audit trail:**
  - The change-tracked permission row, with its assessment attachment.
  - One processing-log entry per call: attachment ID, page numbers, provider, region and model snapshot.
  - A work item when the provider registry changes a region or terms under an active permission. The permission is then suspended until it is approved again.
- **Hard locks:**
  - The image is sent or refused whole, after metadata is stripped.
  - The seat has no tools, no memory and a typed output.
  - The gateway enforces the gate in every run mode.
  - `routing_switch` on blocks everything (the master kill switch).
  - `sensitive_personal` is never sent in Phase 1.

  Reason: these are the containment and accountability floors. Making them configurable would make the policy unauditable.

### R2. Policy for field-level personal values on every request

**Recommendation.** Yes: one gate for every request that carries a personal or sensitive value. A single rule is easier for AI and auditors to reason about than a gate for attachments plus a switch for fields. No vendor in the survey splits the provider decision by item kind; Microsoft's subprocessor toggle covers all content.

- **Setting:** `data_processing_permission` rows for every seat class with data class `personal` or `per_routing` (the data migration, drafting, data Q&A, analysis and vision seats).
- **What happens without a permission:**
  - The gateway degrades rather than fails: personal values become typed placeholders or shape masks, exactly as with the switch on today.
  - A step that needs the value is not sent, and the run ends `routing_blocked`.
  - `routing_switch` stays as the company-wide override that strips everything personal whatever the permissions say.
- **Scope:** company × data class × seat class × provider and region.
- **Default:**
  - No permission, so placeholders are used. A safe default, in line with the EU-style opt-in.
  - The implementation wizard proposes the permissions the regime allows, for a person to approve.
  - Migration note: today, with the switch off, personal values are sent. A company that relied on that needs its permissions approved when it upgrades.
- **Bounds:** the regime's policy and the provider's terms (R1). An optional per-field opt-out list (`data_processing.never_send_fields`, company) lets a customer keep chosen fields out even when they are permitted. It works like a sensitivity-label DLP rule and can only narrow.
- **Who may change it:** as in R1.
- **Audit trail:** the processing log (existing). A daily summary per company, seat and provider makes the log reviewable.
- **Hard locks:**
  - Labels come from the schema and are never lowered by configuration. An unknown kind counts as personal.
  - The exact-text residual scan before sending.
  - The log is committed before the call.
  - No sensitive personal values in Phase 1.
  - A PII detector (Presidio-like) may run on `internal` free text as a second line that can only raise a label, never lower one. Reason: vendors that rely on detection admit it misses data. NativeFlows's labels from the schema are its advantage.

### R3. What a tainted run may read from catalogs

**Recommendation.** Accept the reviewer's projection as a general mechanism, not a one-off. FIDES lets read-only tools run with labels propagating, and plan-then-execute allows fixed tools after untrusted input. The risk to control is egress through drafts. Bounding the information the projection carries controls it.

- **Registry attribute:** `tainted_projection` on a query's result model. It lists the columns a tainted run receives. CI checks that each column is a closed shape (ID, code, unit, status, category, date, quantity) or an `internal` name.
- **Never projectable:** columns labelled `personal`, prices, costs, stock, partner columns and free-text notes. That list is the hard lock.
- **First instance:** `ResolveItemCandidates`, returning id, code, name, unit, category and status.
- **Company setting:** `agents.tainted_reference_reads`. Values: `literal` (the scope of ADR-0050 rule 27 only) or `declared_projections`. Scope: company, with an optional per-agent-type override that can only lower. Agent type versions opt in by naming the projected queries on their tool list.
- **Default:** `declared_projections` for queries whose projection holds only closed shapes and internal names. Reason: the literal scope makes product engineering and invoice matching useless, and with these bounds the projection carries little information.
- **Bounds:**
  - At most 20 candidates per call and a per-run cap on calls, so an injection cannot enumerate the catalog.
  - Arguments are typed match keys (code, barcode, normalized name), never free filters.
  - Rows restricted to another partner (customer-owned parts, another partner's `partner_item`) are excluded, because "which customer buys this part" is confidential.
- **Who may change it:** a person with `full` on `agent` may lower it directly. Raising it from `literal` goes through a change proposal.
- **Audit trail:**
  - The dispatcher records each projected call in `context_refs` with the projection version and the row count.
  - Denials are recorded.
  - INV-642-style checks verify that only projected columns were served.
- **Hard locks:** the run stays tainted (labels propagate); only `is_draft_only` writes; the excluded column classes; the redaction of command responses. Reason: these keep the trifecta broken, because the only egress, drafts reviewed by people, cannot carry prices, partners or personal data from outside the scope.

### R4. The text of a question to the analysis agent

**Recommendation.** Keep the label `personal`, not `internal`: user prompts are customer content under every vendor's DPA, and a question may name a person. Two changes remove most of the practical cost.

1. Under R2, a question reaches the router and planner seats whenever a permission covers them. With the switch off and no permission, placeholders apply. With the switch on, nothing is sent (as now).
2. **Deterministic pseudonymization of known data subjects.** Before the gateway call, code matches the question against the company's own personal records (individual and sole-proprietor partners, contacts, employees) that the asker may read. Each match is replaced by a handle such as `[partner:123]`, which the planner can use as a filter value and code dereferences. This is the symbolic-reference idea from dual LLM and CaMeL. It beats generic NER because NativeFlows knows its data subjects, and it also helps the planner resolve names.

- **Setting:** `analysis.pseudonymize_known_subjects`. Scope: company. Default on. Bounds: on or off. Who: `full` on `agent`. Audit: the processing log records the question row as sent, plus the handles substituted (IDs, never values).
- **Hard locks:**
  - The label cannot be configured down to `internal`. A pseudonymized question is still `personal`, because unknown names can remain, just as a redacted image is still personal.
  - Logging cannot be turned off.
  - Retention blanking (`analysis_question_retention_days`).

### R5. How a localization package configures cross-border rules (VN only as the example)

**Recommendation.** Widen the core-registered schema of `data_processing.policy`, so that packages express law as data and the core names no law. Per data class, it holds:

- `model_processing`: `allowed`, `forbidden` or `company_option`.
- `cross_border`: `allowed`, `requires_assessment`, `forbidden` or `company_option`.
- `assessment_kind`: a package code, such as `xx_transfer_assessment`.
- `assessment_filing`: whether a filing is required, its deadline in days from the first transfer, and the triggers for refiling (a new provider, region or data class).
- `allowed_destination_countries`: an optional allow list, for adequacy-style regimes.
- `max_provider_retention_days` and `requires_no_training`.
- `exemptions`: package-declared conditions of core-registered condition types (for example a company size class, a data subject kind or a purpose), applied like the deductibility conditions of ADR-0053.

- **Scope:** regime row (package, optionally per accounting regime), dated by `effective_from`. A company may pick among options the regime opens, through `UpdateCompanyRegimeOption` (audited).
- **Default:** none in the core. A missing value fails closed (`regime_configuration_missing`). The test package `l10n_xx` declares a fictional policy.
- **Bounds:**
  - A package may tighten the core floors but never loosen them: no sensitive personal values in Phase 1, whole images only, logging always on.
  - `unverified` values fail closed in production (ADR-0016 rule 12). This is right: a pilot cannot go live on an unchecked legal rule.
- **Who may change it:**
  - Package authors, by package release, with CI validation.
  - Companies, only within the options the regime opens.
  - A permission that needs an assessment attaches it, through the four-eyes proposal of R1.
- **Audit trail:**
  - Dated regime-setting rows with their basis.
  - Permission rows with the assessment attachment, its date and the filing reference.
  - A work item `data_processing_assessment_due` before a filing deadline or a refiling trigger.
  - Suspension of the permission when a trigger fires without a new assessment.
- **VN example (package data, `unverified`):**
  - `personal`: model processing allowed; cross-border `requires_assessment` with `assessment_kind: vn_transfer_impact_assessment`, filed with the Ministry of Public Security within 60 days of the start of the transfer (Law 91/2025/QH15, Decree 356/2025/NĐ-CP, as summarized by secondary sources).
  - `sensitive_personal`: `forbidden` in the first version.
  - Exemptions the decree is reported to contain (for example, some employee-data transfers and micro or household businesses) become condition rows only once they are verified against the decree text.
  - Whether processing by a model provider counts as a "transfer" or as a processing service is itself unverified, so the package should keep the stricter reading until a lawyer confirms it.
- **Hard locks:** core neutrality (no law in the core); fail closed without a policy; the core floors above. Reason: a global core cannot carry one country's rules, and a missing policy must never mean "allowed".

## 5. Sources

- Microsoft, Claude models from Anthropic in Microsoft Online Services: https://learn.microsoft.com/en-us/microsoft-365/copilot/connect-to-ai-subprocessor
- Microsoft message center MC1546438 (Claude in the EU Data Boundary, December 2026): https://mc.merill.net/message/MC1546438
- Microsoft Purview, Microsoft 365 Copilot policy location: https://learn.microsoft.com/en-us/purview/dlp-microsoft365-copilot-location-learn-about
- Power Platform, turn on copilots and generative AI features (move data across regions): https://learn.microsoft.com/power-platform/admin/geographical-availability-copilot
- Business Central, enable AI and data movement: https://learn.microsoft.com/dynamics365/business-central/enable-ai
- Salesforce Trailhead, LLM data masking in the Einstein Trust Layer: https://trailhead.salesforce.com/content/learn/modules/llm-data-masking-in-the-einstein-trust-layer/explore-llm-data-masking
- SAP, orchestration data masking tutorial: https://developers.sap.com/tutorials/ai-core-orchestration-consumption-opt-v2.html
- SAP, data residency and digital sovereignty for AI: https://learning.sap.com/courses/building-confidence-in-ai-with-sap/data-residency-and-digital-sovereignty-for-ai
- SAP, responsible AI: https://www.sap.com/mena/products/artificial-intelligence/ai-ethics.html
- ServiceNow, configuring Data Privacy for Now Assist: https://www.servicenow.com/docs/r/GypxAX2jEErwkCxugICKdg/9ARV0FIokXFj4xfSDAsvCA
- ServiceNow, Now Assist data overflow processing: https://www.servicenow.com/docs/r/pt-BR/intelligent-experiences/enable-ai-experiences/configure-na-data-overflow.html
- ServiceNow, data sharing and overflow in AI Control Tower: https://www.servicenow.com/docs/r/zurich/intelligent-experiences/ai-control-tower/data.html
- Oracle, response to customer questions about GenAI: https://blogs.oracle.com/fusioninsider/post/our-response-to-customer-questions-about-genai
- Oracle, data handling in OCI Generative AI Agents: https://docs.oracle.com/en-us/iaas/Content/generative-ai-agents/data-handling.htm
- Zoho, Zia privacy principles: https://help.zoho.com/portal/en/kb/workdrive/zia-ai/articles/zia-privacy-principles
- Odoo 19, AI API keys: https://www.odoo.com/documentation/19.0/applications/productivity/ai/apikeys.html
- AWS, geographic cross-Region inference: https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html
- AWS, securing Bedrock cross-Region inference: https://aws.amazon.com/blogs/machine-learning/securing-amazon-bedrock-cross-region-inference-geographic-and-global/
- AWS, Bedrock data protection: https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html
- AWS, Guardrails sensitive information filters: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html
- Azure OpenAI, data privacy: https://learn.microsoft.com/en-us/legal/cognitive-services/openai/data-privacy
- Azure OpenAI, abuse monitoring: https://learn.microsoft.com/azure/ai-services/openai/concepts/abuse-monitoring
- Microsoft Presidio: https://github.com/microsoft/presidio
- OWASP LLM01:2025 Prompt Injection: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- Hines et al., Spotlighting (2024): https://arxiv.org/abs/2403.14720
- Willison, The lethal trifecta (2025): https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Beurer-Kellner et al., Design Patterns for Securing LLM Agents against Prompt Injections (2025): https://arxiv.org/abs/2506.08837
- Debenedetti et al., CaMeL: Defeating Prompt Injections by Design (2025): https://arxiv.org/abs/2503.18813
- Costa et al., Securing AI Agents with Information-Flow Control (FIDES, 2025): https://arxiv.org/abs/2505.23643
- EY Vietnam, legal alert on Decree 356/2025/NĐ-CP: https://www.ey.com/en_vn/technical/tax/tax-and-law-updates/legal-alert-march-2026-decree-no-356-2025-nd-cp-providing-detailed-guidance-for-implementation-of-personal-data-protection-law
- Vietnam Briefing, key requirements under Decree 356: https://www.vietnam-briefing.com/news/vietnam-personal-data-protection-regulation-decree-356.html
- FPF, issue brief on Vietnam's data protection regime (January 2026): https://fpf.org/wp-content/uploads/2026/01/January-2026-FPF-Issue-Brief-Making-Sense-of-Vietnams-Latest-Data-Protection-and-Governance-Regime-1.pdf

**Verification notes.**
- Microsoft's documents disagree on when Claude moves into the EU Data Boundary (December 2026, per MC1546438).
- ServiceNow's documents describe the overflow default in two ways; this report reads it as allowed by default with an opt-out.
- The 60-day filing deadline and the exemptions under Decree 356 come from secondary sources; the decree text was not read.
- The Salesforce developer guide returned 403; Trailhead was used instead.
