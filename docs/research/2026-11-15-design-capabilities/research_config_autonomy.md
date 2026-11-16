# Research: configurable autonomy controls for AI and automation in finance ERP

Date: 2026-11-15. Scope: seven open questions in `docs/open-questions.md` (value trust, LLM-read rule tokens, bank fees, promotion and demotion thresholds, agent triggers, drift demotion, analysis-agent examples). The author asked us to follow best practice, keep hard locks few, and make policy configurable per customer. Spec 03 rule 1 stays a hard floor: a match an LLM contributed to is never auto-posted. This report reads that floor; it does not relax it.

Caveat on sources: vendor admin guides are often behind a login. Every claim below cites a public page. Where only marketing or third-party pages exist, the text says so.

## 1. What the market does

### 1.1 Classic ML matching gets confidence thresholds and auto-post; generative agents stay draft-only

- **SAP Cash Application (FI-CA).** Customizing sets three confidence bands. In SAP's own worked example they are "Post Proposals Automatically After Check" at 90%, "Save Proposals and Display From" at 70%, and "Follow-Up Uncertain Proposals After" at 50%. The job option "Adjust Confidence Rating" lowers a 90%+ proposal to 70% when its receivable cannot be cleared, and "Clear Automatically" turns auto-clearing on. These are example values, not defaults. The customer sets them after reviewing benchmark results. https://learning.sap.com/courses/managing-cash-application-for-fi-ca/step-1-configuring-cash-application. The 1MV setup guide names the same two settings, "Target Accuracy of Proposals" and "Auto-clearing Confidence": https://paionintune.z6.web.core.windows.net/Library/Setup/1MV_S4HANA2020_Set-Up_EN_XX.pdf
- **SAP training-data floor.** SAP asks for about 10,000 cleared historical items in one company code before training. https://learning.sap.com/courses/managing-cash-application-for-fi-ca/extending-contract-accounting-with-artificial-intelligence. SAP community answers call this a best-practice figure, not a hard limit, and report that about 1,000 items was too few to benchmark: https://answers.sap.com/questions/12895933/testing-sap-cash-application-and-machine-learning.html. **In practice, small companies cannot use the ML path at all.** The vendor does not lower the bar for them.
- **SAP Document AI / Document Information Extraction.** SAP's reference architecture routes on per-field confidence. Documents whose critical fields are all above a configured threshold ("typically 90%") are confirmed automatically, and the rest wait for a person. Custom business-rule validation runs through notification hooks. https://architecture.learning.sap.com/docs/ref-arch/744df4
- **Rossum.** In "Confident" automation, every field in a queue gets a confidence threshold, which can be overridden per field. The help centre gives the default as 0.975 and the API docs give 0.8, so the two sources disagree. A threshold of 0 automates fields that have no score. Built-in validation checks still block automation, and Rossum states that a threshold is not an accuracy guarantee. https://developers.rossum.ai/docs/using-ai-confidence-thresholds-for-automation-in-rossum ; https://rossum.app/api/docs/openapi/guides/automation/
- **UiPath Document Understanding.** UiPath recommends human validation in Validation Station and per-field thresholds the business accepts. Its guidance is that business rules catch bad predictions far better than confidence does, and that confidence scores are not probabilities. https://docs.uipath.com/document-understanding/automation-cloud/latest/classic-user-guide/data-extraction-validation-overview ; https://docs.uipath.com/document-understanding/automation-cloud/latest/CLASSIC-USER-GUIDE/training-high-performing-models
- **Basware SmartCoding.** Release 25.2 added a minimum confidence threshold, default 20%, below which a proposal is not applied. SmartCoding is activated per organization, and one customer case describes country-specific thresholds. https://customer.basware.com/en/features/minimum-confidence-threshold-for-smartcoding ; https://cdn.featuredcustomers.com/CustomerCaseStudy.document/basware_heidelberg-materials_957366.pdf
- **Oracle Fusion IDR.** A setup option creates recognized invoices as Incomplete, so a person must verify them before validation. I found no public confidence-based auto-validate setting. https://docs.oracle.com/en/cloud/saas/financials/26b/fappp/recognition-and-processing-options.html
- **Coupa.** The public pages describe AI OCR, PO matching and auto-approval within customer tolerances by supplier, amount or department. They are marketing pages; the admin settings are not public. https://www.coupa.com/products/ap-automation/
- **HighRadius.** The public pages give only marketing hit rates (more than 95%). They document no threshold settings. https://www.highradius.com/product/cash-application-automation/
- **Microsoft generative agents.**
  - The Business Central Payables Agent produces purchase-document drafts that a supervisor reviews and finalizes. Its setup can also require review of incoming e-mails before the agent drafts anything. https://learn.microsoft.com/en-ie/dynamics365/business-central/payables-agent ; https://learn.microsoft.com/en-ie/dynamics365/business-central/payables-agent-setup
  - Partner sources describe the Dynamics 365 Finance reconciliation agent as flagging exceptions for approval rather than resolving them. https://www.confiz.com/blog/the-invisible-accountant-how-ai-is-transforming-account-reconciliation-in-d365-finance/
  - Xero's JAX auto-reconciles only "high confidence" lines and is switched on or off per bank account. https://www.xero.com/us/campaign/auto-bank-reconciliation/

**Finding.** Vendors let classic ML auto-post above a customer-set threshold once there is enough history. LLM agents in finance ship as draft producers with a human finalizer. NativeFlows's floor (no auto-post where an LLM contributed) matches how the market treats generative AI. It is stricter than how the market treats classic ML.

### 1.2 Deterministic rules auto-post recurring items, including bank fees

| Vendor | Mechanism | Fee handling | Source |
| --- | --- | --- | --- |
| Microsoft Business Central | Text-to-Account Mapping | Posts lines straight to a G/L account with match confidence "High - Text-to-Account Mapping". Microsoft's example is bank fees. A real High match to open entries overrules the mapping. | https://learn.microsoft.com/en-us/dynamics365/business-central/receivables-how-map-text-recurring-payments-accounts-auto-reconcilliation |
| Microsoft Business Central | Payment application rules | Each rule carries its own match confidence, and Low-confidence lines need review. | https://learn.microsoft.com/en-us/dynamics365/business-central/receivables-how-set-up-payment-application-rules |
| Dynamics 365 Finance | Matching-rule action "Generate voucher" | Posts non-payment lines (interest, fees) to the ledger. "Reconcile after import" runs the default rule set unattended. A parameter can require manual matching when several documents match. Version 10.0.46 adds "Require review before posting" as a preview. | https://learn.microsoft.com/en-us/dynamics365/finance/cash-bank-management/set-up-bank-reconciliation-matching-rules ; https://learn.microsoft.com/en-us/dynamics365/finance/cash-bank-management/configure-advanced-bank-reconciliation |
| Oracle Fusion Cash Management | Bank Statement Transaction Creation Rules | Turn unreconciled lines into accounted external transactions for charges and interest. Rules are set per bank account. | https://docs.oracle.com/en/cloud/saas/financials/24d/faipp/overview-of-bank-statement-transaction-creation-rules.html |
| Workday | First-notice item rules | Create ad hoc transactions automatically for fees and interest. Reconcile-action rules run before suggest-action rules. | https://doc.workday.com/admin-guide/en-us/financial-management/cash/bank-account-reconciliation-setup/tef1559243782527.html |
| NetSuite | Auto-create rules | Rules generated from one-to-one matches create and match deposits and charges on one account. Customer payments must still be applied by hand. Users with edit access may edit the rules. | https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_158991223517.html ; https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_158991634358.html |
| QuickBooks Online | Auto-add rules | Post matching lines without review and label them AUTO. Intuit warns there is no review, and auto-add works only while fewer than 300 lines are pending. | https://quickbooks.intuit.com/learn-support/en-us/banking/how-to-set-and-use-banking-rules-for-downloaded-transactions/00/239551 |
| Xero | Bank rules | Users still confirm rule matches. Per-rule auto-reconcile is an open request on Xero's ideas forum. | https://productideas.xero.com/forums/966939-automatic-bank-reconciliation-beta/suggestions/51708832-bank-reconciliation-option-to-enable-or-disable |

Recurring patterns:

- Rule-based settings are scoped per bank account or per rule.
- Defaults are off; the rule or the automation is enabled explicitly.
- Rules carry no volume evidence gate. A rule acts once a user creates it.
- Ambiguity forces manual review.
- Rules are ordered, and precise rules run first.

### 1.3 Who may change a setting, and what evidence it needs

- **Vendor products.** Thresholds sit in admin configuration: SAP Customizing, rule pages restricted to users with edit rights. https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_156289552348.html. None of these products shows a built-in four-eyes approval on threshold changes. Customers get that from IT general controls.
- **SOX and PCAOB.** AS 2201 allows benchmarking of automated application controls only while program-change, access and operations controls are effective. https://pcaobus.org/oversight/standards/auditing-standards/details/AS2201 ; commentary: https://sapinsider.org/articles/develop-an-effective-sap-automated-controls-benchmarking-strategy/. Practitioners advise that changes to model logic, thresholds or training data go through the same change process as ERP configuration. https://www.finrep.ai/blog/ai-journal-entry-testing-and-sox-404-controls-a-2026-practitioner-walkthrough. A threshold is therefore a configuration item: it needs a change record, an approver other than the requester, and evidence that it was tested.
- **EU AI Act Art. 14.** Oversight must let people stay aware of automation bias, disregard, override or reverse an output, and stop the system with a stop button or similar procedure that leaves it in a safe state. https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14. ERP bookkeeping is generally not an Annex III high-risk use, so Art. 14 serves here as a design benchmark, not a legal duty.
- **NIST AI RMF, MANAGE 2.4.** Mechanisms and named responsibilities must exist to supersede, disengage or deactivate a system whose performance is inconsistent with its intended use. The thresholds that trigger this belong in continual monitoring, and there must be criteria for redeploying. https://myctrl.tools/frameworks/nist-ai-rmf/manage-2-4 ; https://epic.org/framing-the-risk-management-framework-actionable-instructions-by-nist-in-their-manage-section/
- **ISO/IEC 42001 Annex A.9.** Asks for documented responsible-use objectives (human oversight among them) and intended-use criteria, including criteria for human oversight. Controls are selected in the Statement of Applicability. https://www.isms.online/iso-42001/annex-a-controls/a-9-use-of-ai-systems/

**The design rule the governance sources share is asymmetry.** Reducing autonomy (stop, demote, pause) must be immediate and open to the responsible person alone. Increasing autonomy needs evidence, an approver who is not the requester, and a change record.

### 1.4 Small companies

- In vendor ML features, small companies get no lower minimum; they simply do not qualify (SAP's roughly 10,000 items).
- Rule features have no minimum at all: QuickBooks, Xero, Business Central and NetSuite let a single created rule act.
- Statistics gives a sounder answer than either. With n error-free cases, the 95% upper bound on the error rate is about 3/n (the rule of three).
  - 30 cases bound the error at about 10%.
  - 60 cases bound it at about 5%.
  - 300 cases bound it at about 1%.

  ADR-0051 rule 18's 300 proposals at 99% is exactly the rule-of-three size for a 1% error ceiling. A small company should get **more time**, not a lower bar.

## 2. Cross-cutting recommendation: one autonomy-settings registry

Every setting below should be one row in a registry (the existing `artifacts.*` and company settings), declaring:

- a default;
- a hard minimum and maximum;
- a **direction**: tightening takes effect at once on one authorized person's change; loosening needs a second person (never the requester, never the human an agent run acted for), a reason, and, where stated, attached evidence;
- effective-dated versions;
- an immutable change log that auditors can export;
- **outdating**: loosening an acting threshold marks dependent auto-post evidence outdated, as ADR-0059 rule 6 already does for parameter sets.

The default owner role is `company_owner`, delegable to a finance controller role. Turning automation off is always a one-person action; that is the stop button.

## 3. Recommendations on the seven items

### 3.1 Extraction value trust (ADR-0057 rule 17)

**Practice.** Per-field thresholds plus validation rules, defaulting high (Rossum 0.975, SAP about 90% for critical fields). Vendors agree that validation beats confidence.

**Recommendation.** Accept the interim reading. "Trusted" means the value carries no instruction, not that the value is true. Add per-field tightening controls and nothing that loosens past the shape table.

| Item | Proposal |
| --- | --- |
| Settings | `intake.trust.<document_type>.<field>.require_confirmation` (bool, default false). `intake.trust.<document_type>.min_passed_rules` (default 1, bounds 1–10). `intake.trust.ocr_min_confidence` (default 0.90, bounds 0.80–1.00, applied where the OCR engine reports one). |
| Scope | Company, per document type and field. |
| Who may change | Tightening: the intake owner alone. Loosening: a second person, plus `extraction_mapping` evidence of field agreement of at least 95% over at least 50 documents (ADR-0059 rule 18). |

**Hard locks:**
- Free text, URLs, e-mails and phones are never trusted.
- Vision (LLM) values are never trusted before a person confirms them. That is the spec 03 floor itself.
- Nothing is trusted from a failed or mismatched signature or from suspected hidden text.
- Trust never on its own auto-posts or changes master data.

### 3.2 LLM-read token in a human-approved rule feeding auto-post

**Practice.**
- Every rules vendor treats a user-created or user-confirmed rule as deterministic. NetSuite even generates rules from matches.
- Generative agents are draft-only.

**Reading of the floor.** The LLM's contribution is choosing which substring of the description to propose. Once a person approves a rule version, it is a company-owned deterministic artifact. Its later matches are computed by pure code, so no LLM takes part in the match itself. The floor should be read as covering the **run-time match path**: `match_basis = llm_suggestion` drafts and any score fed by a run. It does not cover **an approved artifact whose provenance includes an LLM proposal**. ADR-0057's value trust uses the same reading: a deterministic check plus human confirmation ends the taint.

**Recommendation.** Human approval ends the contribution only when all of these hold:
1. The token is a whole, reference-shaped token of the description; it was not generated.
2. The rule reached `active` on independent live evidence: at least 10 suggest-mode drafts, at least 99% posted unchanged (ADR-0059 rule 18).
3. The approver is neither the proposer nor the human the run acted for.
4. The rule version records `origin = llm_proposed`.
5. The auto-post rule's own 300-proposal evidence counts proposals of that basis.

| Item | Proposal |
| --- | --- |
| Setting | `cash.auto_post.accept_llm_originated_rules` (bool). |
| Default | **false** in Phase 1. The author confirms the reading first, then the company opts in. |
| Scope | Company. |
| Who may change | Turning it on: `company_owner` plus a second approver. Turning it off: one person, and it outdates dependent evidence. |

**Hard locks:**
- `llm_suggestion` drafts never auto-post.
- An LLM-proposed rule is never self-approved.
- The counterparty caps of ADR-0048 rule 9 still apply.

**The author owns this reading of spec 03.** If the author rejects it, the setting stays absent and nothing else changes.

### 3.3 Bank fees auto-posting

**Practice.** This is mainstream. Business Central text-to-account mapping (Microsoft's own example is bank fees), Dynamics "Generate voucher", Oracle transaction-creation rules, Workday first-notice rules, NetSuite auto-create rules and QuickBooks auto-add all post fees by deterministic rule, usually off by default and enabled per rule or per bank account.

**Diagnosis.** `counterparty_unverified` protects settlement against open items: who paid whom. For a charge levied by the bank that holds the account, that check asks the wrong question. The right counterparty is the account's own bank.

**Recommendation.** Add an account-rule class `bank_charge`. Its counterparty check passes when all of these hold:
- the line is a debit;
- it carries a bank transaction code that the bank-account setup lists as a charge code (ISO 20022 statements carry such family and sub-family codes; the bank's code list is configured, not hard-wired);
- it names no third-party account owned by another partner.

Then let such rules auto-post under their own evidence instead of the 300-proposal gate, which a small company might need years to collect.

| Item | Proposal |
| --- | --- |
| Settings | Per rule: `auto_post` (default **off**), `amount_max` (default 0, meaning unset; must be set to enable; bounded by a company setting `cash.bank_charge.amount_max_ceiling`). |
| Evidence | At least 6 lines over at least 3 statement months, 100% posted unchanged to that account. At a 2% error ceiling the rule of three needs about 150 lines, so this evidence is weaker. It is acceptable only because the amount cap bounds the exposure and spec 03 rule 6's period-end batch confirmation by the accountable human catches errors before close. |
| Scope | Bank account and rule. |
| Who may change | Enabling: the bank-account owner proposes, a different person approves. Disabling: one person. |

**Hard locks:**
- Never for lines that also match open items (a High match wins, as in Business Central).
- Never with more than one rule matching (ambiguity suggests).
- Never above the cap.
- Never on the LLM's `purpose = bank_charge` classification.

### 3.4 Promotion and demotion thresholds, and small-company minimums

**Recommendation.** Express the thresholds as statistical confidence, not raw counts, so small companies wait longer instead of getting a lower bar.

**Settings** (company scope, per function or kind):

| Setting | Default | Bounds |
| --- | --- | --- |
| `artifacts.<fn>.precision_target` | 95% suggest, 99% acting | — |
| `artifacts.<fn>.confidence_level` | 95% | — |
| `artifacts.<fn>.min_cases` | ADR-0059 rule 18 values | — |
| `artifacts.<fn>.max_window_days` | 90 | up to 365 |
| `auto_post.max_error_rate` | 1% | 0.1%–2% |

**Promotion test.**
- Promote when the Wilson lower bound of precision at the confidence level is at or above the target.
- For acting paths, required cases follow from the error ceiling: about 3 ÷ `max_error_rate` error-free proposals, so 300 at 1% and 150 at 2%.
- Suggest-mode (non-acting) promotions may fall to the declared small-company minimums (50 backtest, 30 live), because a person still decides every case.
- A small company extends the window up to `max_window_days` instead.

**Demotion test.**
- Keep "the larger of twice the evidenced override rate and that rate plus 5 points".
- Judge it only over at least 30 decisions, widening the window as ADR-0059 rule 4 does for re-evaluation.
- For acting paths, add an immediate trigger: any confirmed auto-post to a wrong partner or account suspends auto-post at once.

**Who may change.** Raising a target or minimum: one person. Lowering one: a second approver plus a written reason, and it outdates evidence.

**Hard lock.** The acting floor itself: `max_error_rate` is never above 2% and is always proven at 95% confidence. ADR-0051 rule 18's 300/99% becomes the default of that formula rather than a separate constant.

### 3.5 Configurable agent triggers

**Practice.**
- Microsoft lets a company decide whether incoming e-mails need review before the Payables Agent drafts anything.
- Dynamics makes reconcile-on-import a per-account toggle.
- Xero switches auto-reconciliation on per bank account.
- Triggers are customer choices everywhere.

**Recommendation.** Declare the two candidates `configurable` in the next agent type versions: the quotation agent's `inbound_message_matched` and the purchase invoice agent's `supplier_invoice_received`. Seed each company with an `automation_rule` (`start_agent`, no conditions) that reproduces today's behaviour, so nothing changes until a company edits the rule.

| Item | Proposal |
| --- | --- |
| Conditions | Only trusted attributes: partner, mailbox, document type, trusted amount range. No conditions on free text. |
| Scope | Company, per mailbox or document type. |
| Who may change | The workflow owner, under the ADR-0058 rule lifecycle (30-day replay). Narrowing or disabling a trigger is a one-person action. |

**Hard locks:**
- A trigger only starts an agent; it never widens tools, scope, budget or taint handling.
- The circuit breaker and budgets still apply.

The other four agent types stay `always` until a need appears.

### 3.6 Automatic demotion on override drift

**Practice.** NIST MANAGE 2.4 and Art. 14 ask for mechanisms that take a system out of action when it underperforms, with the thresholds defined in advance. SAP's "Adjust Confidence Rating" automatically pulls failing proposals below the auto-clear level.

**Recommendation.** Keep the asymmetry, but make the agent-type response configurable.

| Item | Proposal |
| --- | --- |
| Setting | `agents.<type>.drift_action` ∈ {`signal`, `pause_new_runs`, `demote_to_shadow`}. |
| Default | `signal`. Every draft of an assisted agent type is already reviewed by a person, so demotion moves work rather than adding safety. The real risk is rubber-stamping (automation bias, Art. 14(4)(b)). |
| Scope | Company, per agent type. |
| Who may change | Choosing a stronger action: one person. Weakening it: a second approver. |

Also add `agents.<type>.drift_signal_points` (default 10, bounds 5–30).

**Hard locks:**
- Artifacts keep their automatic demotion, because they fall back to an evidenced version.
- Any drift that outdates auto-post evidence suspends auto-post automatically.
- Re-arming always needs evidence newer than the demotion.

### 3.7 The analysis agent's minimum examples for promotion

**Context.**
- The `assisted` analysis agent answers only the asker. It posts nothing and sends nothing.
- 30 examples at 90% agreement is itself a weak gate: the Wilson lower bound is about 74%.

**Recommendation.** Accept promotion on the synthetic CI report when a company has fewer than the minimum, with three conditions:
1. Every answer shows its evidence class ("evaluated on the synthetic suite only").
2. Shadow evaluation starts automatically when verified examples reach the minimum, and a result below target triggers `drift_action`.
3. The company may require local examples first.

| Item | Proposal |
| --- | --- |
| Settings | `artifacts.analysis.min_verified_examples` (default 30, bounds 0–500). `artifacts.analysis.allow_synthetic_only_promotion` (default true). |
| Scope | Company. |
| Who may change | Raising the minimum or disallowing synthetic-only promotion: one person. Lowering: a second approver. |

**Hard locks:**
- No wrong answer on an expected-abstention example.
- Field and record permissions apply to every answer.
- A catalog change forces a new version in shadow (ADR-0060 rule 25).

## 4. What stays a hard lock, and why (short list)

1. **Spec 03 rule 1 at run time.** No auto-post of `llm_suggestion` drafts or of anything a tainted run scored. This is the author's floor and matches how vendors ship generative agents.
2. **Vision values untrusted until a person confirms them.** This is the same floor applied to extraction.
3. **Acting paths prove their error ceiling statistically.** The ceiling is at most 2%, at 95% confidence. Without this, a threshold setting is not a control a SOX or PCAOB audit could benchmark.
4. **The proposer or triggering human never approves.** Spec 03 rule 5, and SOX segregation of duties.
5. **Autonomy can always be reduced by one person at once**, and it is re-armed only on new evidence. This is the Art. 14 stop requirement and NIST MANAGE 2.4.

Everything else is a bounded, versioned company setting.
