# Research: configurable workflows, AI-tuned deterministic functions, and agentic workflow architecture

Date: 2026-11-15. Scope: input for the ERPMe architect. Three topics: (1) configuring business processes without code, and where configuration ends and code begins; (2) using AI to tune existing deterministic functions or build new ones; (3) cross-cutting agentic workflow architecture in enterprise software, 2024 to 2026.

## How to read this

- **Claim tags.** `[doc]` official vendor or project documentation; `[blog]` vendor engineering or product blog, trade press, or practitioner blog; `[paper]` research paper or preprint; `[inference]` my synthesis or judgement, not stated by a source.
- **Source quality.** Several vendor product pages are marketing. Where the only source was secondary, the claim says so. Specific numbers from vendors (hit rates, accuracy) are self-reported and unaudited.
- **Naming.** Only vendors and products are named. No customer names.
- **ERPMe context assumed.** A strict deterministic core: commands with plan hashes (ADR-0008); the LLM never computes numbers or posts; agents draft, people submit and approve through the policy table (ADR-0043) and approval pools (ADR-0055); agent types are versioned code with fixed tool lists, a taint model and shadow to assisted promotion with frozen evidence (ADR-0029, ADR-0050, ADR-0051); change proposals for master data; golden sets and replay evaluation; an outbox (ADR-0013) and a work queue (ADR-0042).

## Executive summary

1. **Every mature platform converged on the same split** `[inference]`: business users configure *parameters, decision tables, conditions and routing* over a fixed, vendor-owned vocabulary of events and actions; anything that needs new vocabulary is code. SAP Flexible Workflow (preconditions in an app, new conditions through a BAdI), Dynamics 365 workflow editor (conditions and hierarchies, new workflow types in X++), ServiceNow (flows for most things, business rules when ordering or same-transaction semantics matter) and Agentforce ("if you can express a decision as code, it should be written as logic") all draw the line in roughly the same place.
2. **The failure modes are well documented and repeat across vendors.** Self-triggering loops (Power Automate warns at save; ServiceNow caps indirect recursion at 3 by default; Odoo keeps a per-chain "already done" set); unspecified execution order between automations on the same object (Salesforce); running instances silently picking up new decision versions when bound to "latest" (Camunda); transports overwriting decision-table data (BRF+); versions that cannot be undeployed (SAP Build decisions, per community reports); history kept only for days (n8n tiers); and runaway error-flooding turned off by the platform (Zapier auto-off).
3. **For ERPMe Phase 1, do not build a general workflow engine or a scripting language.** Use three configuration tiers already latent in the design: (a) parameters and the policy table; (b) typed decision tables with order-independent hit policies; (c) event-condition-action automation rules whose actions are only registered commands or drafts, executed through the normal command envelope and policy. Everything else is code in a package, reviewed like code.
4. **AI should never edit running logic; it proposes versioned artifacts that a deterministic engine executes, and evidence decides promotion.** This is the pattern behind SAP Cash Application (two confidence thresholds: show-proposal vs auto-clear), BlackLine and Oracle Account Reconciliation (suggested vs confirmed match rules), FICO-style champion/challenger, MLflow-style alias promotion and Temporal-style replay testing. ERPMe already has the right primitives: change proposals, golden sets, replay, shadow to assisted promotion. Extend them from agent types to *every AI-produced artifact*: parameter sets, decision tables, matching rule sets, report definitions and (later) extension code.
5. **The agentic platforms of 2025 to 2026 all retreated from pure LLM orchestration toward hybrid, deterministic graphs with bounded LLM steps** (Agentforce Agent Script and hybrid reasoning, Copilot Studio agent flows, Oracle workflow agents, LangGraph graphs, Microsoft Agent Framework workflows, SAP Joule Studio 2.0 approval loops). Prompt-injection research converged on architectural defences (dual LLM, plan-then-execute, CaMeL capabilities, FIDES information-flow labels) rather than filters. ERPMe's taint model and fixed tool lists sit squarely in this mainstream; the main gaps worth closing are calibrated abstention, cost budgets as hard limits, OTel-compatible traces, and a single registry of every versioned "decision artifact".

---

# Topic 1: Configurable workflows

## 1.1 What the major systems do

### SAP S/4HANA Flexible Workflow
- Business process experts configure approval workflows per *scenario* (purchase requisition, purchase order, supplier invoice) in the Manage Workflows apps. A workflow has **start conditions** (preconditions) that decide whether it starts, and **steps** with their own conditions; an unmet step condition marks the step skipped. `[doc]` https://learning.sap.com/courses/sap-workflow-overview-basics-strategy-and-extensibility/explaining-sap-fiori-applications-and-building-blocks-for-flexible-workflow ; https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-sourcing-and-procurement/defining-workflows-in-sourcing-and-procurement_a17030df-33b7-4c0e-a8c6-31ec490618e9
- Workflows are evaluated **in a defined order and only the first matching one starts**; a default workflow must sit last and be active. `[blog]` https://www.zarantech.com/blog/?p=11798 (community, consistent with SAP Learning)
- **The configuration/code line is explicit:** new conditions are added by developers through BAdIs (`SWF_WORKFLOW_CONDITION_DEF` defines a condition, `SWF_WORKFLOW_CONDITION_EVAL` evaluates it), filtered to a scenario. Users then pick the new condition in the app. `[blog]` https://blogs.sap.com/2019/12/03/sap-s-4hana-cloud-flexible-workflow-with-new-custom-pre-condition-for-purchase-requisition/
- Lesson `[inference]`: the vendor owns the vocabulary (scenario, condition, agent rule, step type); customers compose it. Adding vocabulary is code.

### SAP BRF+ (Business Rule Framework plus) and SAP Build Process Automation decisions
- BRF+ is an ABAP rules engine with decision tables, decision trees, formulas and rulesets; it supports **per-object versioning**, **simulation** of functions or single expressions, and a processing trace; historic and inactive versions can be simulated. `[blog]` https://en.wikipedia.org/wiki/BRFplus ; https://blogs.sap.com/2012/07/24/latest-improvements-in-brfplus/
- Pitfalls documented in SAP notes: transporting a whole application can **overwrite decision-table data** maintained in the target system; separate guidance exists for transporting only the changed entry. Versioning tabs are hidden unless expert mode is on. `[doc]` KBA 3386566 https://userapps.support.sap.com/sap/support/knowledge/en/3386566 ; KBA 3293958 https://userapps.support.sap.com/sap/support/knowledge/en/3293958
- SAP Build Process Automation (BTP) has **decisions** (decision tables plus text rules). A project is **released** (an immutable snapshot with a semantic version, starting 1.0.0) and then **deployed**; only deployed decisions are callable, through REST. Release and deploy are per project, not per rule. `[doc]` https://learning.sap.com/courses/SAP-Build-Experience/312-1_Automation_Run-Process ; `[blog]` https://blogs.sap.com/2023/07/18/create-and-consume-decisions-in-sap-build-process-automation/ ; https://blog.sap-press.com/central-decision-management-in-sap-build-process-automation
- Community reports of **no undeploy/unrelease** and **"maximum versions reached"** errors. `[blog]` https://groups.community.sap.com/t5/technology-q-a/re-maximum-versions-reached-for-the-decision-error/qaq-p/12763724/comment-id/4816931 (may be fixed in later releases)

### Microsoft Dynamics 365 Finance and Supply Chain: workflow editor and business events
- The workflow editor configures approval workflows for a **workflow type** defined in code. Configuration covers activation conditions (which workflow applies when several share a type, with a default), approval steps that are always required or conditional, and a **managerial or configurable hierarchy** for assignment. Conditions can be tested in a Test form. `[doc]` https://learn.microsoft.com/en-ca/dynamics365/fin-ops-core/fin-ops/organization-administration/configure-workflow-properties ; https://learn.microsoft.com/en-nz/dynamics365/fin-ops-core/fin-ops/organization-administration/configure-approval-step-workflow
- **Versioning:** a workflow has many versions, **only one active**; saving offers "activate the new version"; a version must be **free of errors and warnings** to be activated. `[doc]` (AX 2012 docs, still the model in F&O) https://learn.microsoft.com/zh-cn/previous-versions/dynamicsax-2012/appuser-itpro/activate-a-workflow ; https://learn.microsoft.com/en-us/training/modules/setup-use-basic-budgeting-finance/implement-workflow
- **Business events** publish application, workflow and alert events to external endpoints and Power Automate ("When a Business Event occurs"). Workflow business events let external flows take part in approvals. `[doc]` https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/business-events/home-page ; https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/business-events/how-to/how-to-workflow
- Lesson `[inference]`: the ERP keeps approval *semantics* inside (workflow types, hierarchies, delegation) and pushes *integration and side automation* outside through events. Events are the stable contract.

### Microsoft Power Automate and Power Platform governance
- Microsoft's own anti-pattern guidance: cloud flows **can trigger themselves**; on save, Power Automate warns "Actions in this flow may result in an infinite trigger loop"; mitigations are **trigger conditions** (skipped runs cost nothing) and an early **Terminate** guard. It also warns against nested loops, per-record loops over large sets (use batch/bulk), and doing ETL in flows. `[doc]` https://learn.microsoft.com/en-us/power-automate/guidance/coding-guidelines/avoid-anti-patterns
- Governance: **Managed Environments**, **DLP policies** classifying connectors (business / non-business / blocked), **solutions** (unmanaged in dev, managed in test and prod, blocking ad hoc production edits) and built-in **Pipelines** for ALM. `[doc]` https://learn.microsoft.com/en-us/power-platform/guidance/white-papers/managed-environment-activation ; `[blog]` https://www.microsoft.com/en-us/power-platform/blog/2022/10/12/the-future-of-low-code-governance-with-managed-environments-for-power-platform/
- Copilot can **generate a flow from a description**, explain an existing flow, and propose edits; English only for description-based creation, cloud flows only. `[doc]` https://learn.microsoft.com/power-automate/create-cloud-flow-using-copilot ; https://learn.microsoft.com/power-automate/create-cloud-flow-from-description

### Odoo: automation rules, server actions, Studio
- **Automation rules** (module `base_automation`) run one or more **server actions** on a trigger: field-value changes (stage, user, tag, state, priority), create/write/delete, archive, UI on-change, time-based (relative to a date field, creation or update), mail received/sent, and **webhook**. Server actions update or create records, send mail, run other actions, or **execute Python code**. Studio exposes this no-code. `[doc]` https://www.odoo.com/documentation/18.0/applications/studio/automated_actions.html ; https://www.odoo.com/documentation/18.0/developer/reference/backend/actions.html
- **Loop guard in code:** a context dict `__action_done` maps each rule to the records it already processed in the current call chain; records are marked done *before* actions run so nested writes cannot re-trigger the same rule on the same records; rules on write fire only if a watched field actually changed. `[doc]` (source) https://github.com/odoo/odoo/blob/18.0/addons/base_automation/models/base_automation.py
- Lesson `[inference]`: "execute Python code" in a server action is where configuration silently becomes unreviewed code inside the database; that is the line ERPMe should not cross in Phase 1.

### ServiceNow Flow Designer (Workflow Studio)
- ServiceNow recommends **flows instead of business rules** in most cases, but keeps business rules when logic must run in a specific order relative to other business rules, must run immediately before or after a database write in the same thread, or only calls a script include. `[doc]` https://www.servicenow.com/docs/r/zurich/application-development/flow-designer.html
- **Recursion:** direct recursion (a flow calling itself) is prevented; **indirect recursion is capped by `com.glide.hub.flow_engine.indirect_recursion_limit`, default 3**; beyond the limit further triggers are ignored. `[doc]` https://www.servicenow.com/docs/r/build-workflows/workflow-studio/flow-designer-system-properties.html
- **Execution details** are stored per run in a flow context record, governed by execution-setting records. `[doc]` https://www.servicenow.com/docs/r/build-workflows/workflow-studio/flow-execution-settings.html
- Testing: the built-in test bypasses trigger conditions; the Automated Test Framework (ATF) is the regression tool; practitioners report regression breakage across platform releases as a recurring problem. `[blog]` https://www.servicenow.com/community/now-platform-blog/best-practices-for-using-the-flow-designer/ba-p/2281636 ; https://testgrid.io/blog/servicenow-workflow-regression-testing/

### Salesforce Flow (and Agentforce for Flow)
- Record-triggered flows run before-save or after-save within the platform's **order of execution**; several record-triggered flows on the same object historically ran in **no guaranteed order**, leading to the "one flow per object per context" convention and later the Flow Trigger Explorer and ordering features. `[doc]` https://developer.salesforce.com/docs/atlas.en-us.238.0.apexcode.meta/pages/apex_triggers_order_of_execution.htm ; `[blog]` https://www.apexhours.com/?p=5695
- Recursion: same-transaction recursion surfaces as governor-limit errors ("too many DML statements"); prevention relies on tight entry criteria ("only when specific fields change") and prior-value checks. `[blog]` (secondary sources; consistent with Salesforce guidance)
- **Testing:** debug runs can **roll back**; a debug run of a record-triggered flow can be **converted into a flow test** with assertions; tests can be associated with flow versions (Spring '26). `[doc]` https://trailhead.salesforce.com/fr/content/learn/modules/flow-implementation-2/debug-flows-as-another-user ; https://admin.salesforce.com/blog/2021/learn-moar-in-winter-22-with-flow-enhancements ; `[blog]` https://salesforcebreak.com/2026/01/29/spring-26-debug-flow-builder/
- **Einstein / Agentforce for Flow** drafts a flow from a prompt; practitioners report wrong formulas and stress human review before activation. `[doc]` https://admin.salesforce.com/blog/2023/einstein-for-flow-for-salesforce-admins ; `[blog]` https://www.salesforce.com/blog/agentic-ai-for-flow/ ; https://salesforcebreak.com/2025/03/24/agentforce-assisted-flow-build-experience/

### Camunda: BPMN and DMN
- Deploying a changed model registers a **new version**; **running instances keep the version they started with**, new instances use the latest. Running instances can be **migrated** explicitly with a mapping plan (Operate, REST, gRPC), keeping identity and audit history. Camunda advises versioning only `.bpmn` and `.dmn` files, keeping dependent code backward compatible or creating `-v2` artifacts referenced only by the new model, and splitting processes longer than about six months at idle points. `[doc]` https://docs.camunda.io/docs/components/best-practices/operations/versioning-process-definitions/
- **Binding:** a call activity calls the **latest** called process by default, but can bind to the version **deployed together** with the parent, or a specific version. Community reports the same concern for business-rule tasks bound to the latest DMN: a DMN change affects in-flight instances. `[doc]` same page; `[blog]` https://forum.camunda.io/t/can-i-specify-a-specific-version-of-the-dmn-decision-table-to-use-in-a-business-rule-task/38976
- **DMN hit policies:** Unique (default; error if more than one rule matches), Any, Priority, First, Collect (with SUM/MIN/MAX/COUNT aggregators), Rule order; Camunda's best practice favours **Unique** because it forces complete, non-overlapping tables. `[doc]` https://docs.camunda.io/docs/components/modeler/dmn/decision-table-hit-policy/ ; https://docs.camunda.io/docs/components/best-practices/modeling/choosing-the-dmn-hit-policy/
- 2026: Camunda positions process-instance migration for "agentic processes" (agent definitions are versioned with the process). `[blog]` https://camunda.com/blog/2026/01/migrate-your-agentic-processes-without-disruption-using-process-instance-migration/

### Temporal and durable execution
- Workflow code must be **deterministic**; side effects go in Activities. Changes to running workflows need **patching** (per-change branches) or **Worker Versioning** (pin workflows to a code revision; "We strongly recommend using Worker Versioning"). `[doc]` https://docs.temporal.io/develop/python/workflows/versioning
- **Safe deployment:** replay existing event histories against new code in development (checked-in histories), pre-deployment and at deployment time; gate the rollout with a "verify" worker that replays recent production histories before the rest deploy; pinned workflows stay on their version, auto-upgrade ones move. `[doc]` https://docs.temporal.io/develop/safe-deployments
- Lesson `[inference]`: **replay of recorded histories against new logic** is the most transferable testing idea in the whole survey. ERPMe's replay evaluation for agents is the same idea; it should also apply to configuration.

### Zapier and n8n
- Zapier: failed steps auto-replay up to 5 times; runs halted by **flood protection** (triggered at 100+ items from one poll) are *held*, not errored, and are not auto-replayed; a Zap that errors on 95% of runs over 7 days (minimum 20 runs) is **turned off automatically**. `[doc]` https://help.zapier.com/hc/en-us/articles/14167175792909-Decide-how-your-Zap-handles-errors-with-advanced-settings ; https://help.zapier.com/hc/en-us/articles/37454233721869-How-to-troubleshoot-held-Zap-or-step-runs
- n8n: a version is created on save, restore or Git pull; versions live in the instance database; **history retention depends on plan** (from about a day to 30 days per secondary sources); Git-backed environments are a paid feature, so many teams export JSON on a schedule. `[doc]` https://docs.n8n.io/build/manage-workflows/view-change-history ; `[blog]` https://community.n8n.io/t/versioning-and-deploying-n8n-workflows-across-dev-staging-and-production/295660

## 1.2 Where the line between configuration and code sits

A spectrum, from safest to most powerful `[inference, synthesised from the systems above]`:

| Tier | What users change | Examples | Who can change | Risk |
|---|---|---|---|---|
| 0. Parameters | Scalars, tolerances, thresholds, lists | Matching tolerance, auto-clear threshold, approval amount limits | Key user via change proposal | Low; bounded domain |
| 1. Decision tables | Rows of a typed table with a fixed hit policy | BRF+, DMN, SAP Build decisions, D365 activation conditions, ERPMe `policy_rule` | Key user, reviewed | Low-medium; overlap and gaps are checkable |
| 2. Declarative automation over a fixed vocabulary | Event + condition + action, actions picked from a registered list | Odoo automation rules without Python, SAP Flexible Workflow, D365 workflow editor, Power Automate with approved connectors | Key user or admin, reviewed, tested | Medium; loops, ordering, side effects |
| 3. Orchestration graphs | Multi-step, long-running processes with waits and compensation | BPMN in Camunda, ServiceNow flows, Salesforce orchestrations, Temporal workflows | Developer or process engineer | High; versioning of in-flight instances |
| 4. Scripts in configuration | Arbitrary code stored as data | Odoo "execute Python code", ServiceNow script steps, Power Automate inline code | Developer, often unreviewed | Highest; bypasses code review and upgrade testing |
| 5. Code | New vocabulary: new event types, actions, conditions, workflow types | SAP BAdIs, D365 X++ workflow types, ServiceNow spokes | Developer, code review, CI | Normal software risk |

The consistent vendor rule `[inference]`: **vocabulary is code; composition is configuration.** Systems get into trouble at tier 4, where composition quietly turns into unreviewed vocabulary, and at tier 3, where versioning of in-flight instances becomes the dominant cost.

## 1.3 Pitfalls (with evidence)

1. **Self-triggering and indirect loops.** Power Automate warns at save; ServiceNow caps indirect recursion (default 3); Odoo tracks per-chain done sets; Salesforce shows governor-limit failures. `[doc]` links above. Loops also burn quotas (Zapier flood protection, Power Automate run limits).
2. **Unspecified ordering.** Multiple automations on the same object with no defined order (Salesforce historically) make results depend on deployment accidents. `[doc]`
3. **"Latest" binding drift.** Decisions and subprocesses bound to the latest version change behaviour of in-flight work (Camunda call activities and business-rule tasks). `[doc]` `[blog]`
4. **In-flight instance versioning.** Every long-running orchestration engine needs a story for running instances: pin, migrate or patch (Camunda, Temporal). The cost grows with process duration. `[doc]`
5. **Silent breakage on upgrade.** Configurations reference fields, actions and connectors that the vendor or an extension changes; regression suites (ATF, flow tests, replay) are the only defence and are often missing. `[blog]` https://testgrid.io/blog/servicenow-workflow-regression-testing/
6. **Transport and environment drift.** BRF+ transports overwriting table data; Power Platform's answer is managed solutions plus pipelines; n8n's answer is paid Git sync. `[doc]`
7. **Irreversible lifecycle operations.** Versions that cannot be undeployed, version-count ceilings (SAP Build community reports). `[blog]`
8. **Opaque debugging.** Useful systems keep per-run execution records (ServiceNow flow contexts, Zapier run history, Temporal event history); short retention (n8n tiers, Copilot Studio test results kept 89 days) limits audits. `[doc]`
9. **Shadow IT and data leakage.** Citizen automations connecting business data to personal or external services; DLP connector classes exist for this reason. `[doc]`
10. **Scripts in configuration** bypass code review, static analysis and upgrade testing (Odoo Python server actions). `[inference]`
11. **Error floods and partial side effects.** Retries without idempotency duplicate side effects; Zapier's auto-off after sustained failure is a circuit breaker. `[doc]`
12. **AI-generated automations look right and are subtly wrong.** Practitioner reports of erroneous generated formulas in Agentforce for Flow; Copilot generation limited in scope. `[blog]`

## 1.4 Transferable patterns

- **P1.1 Fixed vocabulary, composed by configuration.** Event types, actions and condition fields are a published, versioned registry owned by code. `[inference]`
- **P1.2 Immutable versions, one active per scope, validation before activation** (D365, SAP Build, Camunda). `[doc]`
- **P1.3 Pin the version at start; migrate explicitly** (Camunda, Temporal pinned workers). `[doc]`
- **P1.4 Order-independent combination or explicit priority** (DMN Unique / Collect-with-aggregator; ERPMe `policy_rule` already takes the maximum per dimension). `[doc]` `[inference]`
- **P1.5 Trigger on change predicates, not on "any write"** (Odoo watched fields, Salesforce entry criteria, Power Automate trigger conditions). `[doc]`
- **P1.6 Causation-chain loop guards with a small depth cap** (ServiceNow 3; Odoo per-chain set). `[doc]`
- **P1.7 Circuit breakers and flood protection** (Zapier). `[doc]`
- **P1.8 Replay recorded histories against the new version before activation** (Temporal). `[doc]`
- **P1.9 Tests travel with the artifact; debug runs become tests** (Salesforce convert-to-test, BRF+ simulation). `[doc]`
- **P1.10 Per-execution trace record**: version, inputs, matched rows, outputs. `[doc]`
- **P1.11 Events as the integration contract** (D365 business events). `[doc]`

## 1.5 Design recommendations for ERPMe (Topic 1)

### Phase 1

**W1. Adopt three configuration tiers and no more.** `[inference]`
- Tier 0: parameters (typed, bounded, effective-dated).
- Tier 1: decision tables (typed inputs from a published schema, typed outputs, restricted hit policies).
- Tier 2: automation rules (event, condition, action), where the action is one of: create a draft document or change proposal through a registered command; create a work item (ADR-0042); send a notification from a template; call a registered command allowed for the "automation" actor kind under the policy table.
- Everything else is code in a module or an l10n/extension package, reviewed and tested like code.
- *Tradeoff:* less flexible than Odoo or Power Automate; some customer requests become small code changes. This is consistent with "easy for AI to use": a closed vocabulary is far easier for agents to read, generate and verify than open scripts.

**W2. Do not build a BPMN engine or a general orchestration engine in Phase 1.** `[inference]`
- The document lifecycle, policy table, approval pools and stages, work queue and outbox already cover approvals and hand-offs, which are the bulk of ERP "workflow".
- Approval routing is configured through `policy_rule` rows and approval pool membership (tier 1), not through a step designer.
- *Tradeoff:* multi-document, long-running processes (engineering change orders, new product introduction, RMA) stay as code-defined document flows in Phase 1. This avoids the in-flight-instance versioning cost (pitfall 4) until real cases exist.

**W3. Every configuration artifact is a versioned record changed only through a change proposal.** `[inference, from D365/SAP Build/Camunda]`
- Immutable versions, at most one active version per scope (company, document type, action) and effective date.
- Activation requires: schema validation passing, the artifact's own test cases passing, and an approval through the same proposal flow as master data (ADR-0029), so AI-drafted configuration carries taint and needs a person.
- Each decision record and each automation execution stores the **artifact version ID** it used. In-flight documents are evaluated against the version active at evaluation time, and the record says which. (ERPMe documents are short-lived, so "pin per evaluation, record the version" is enough; no migration machinery.)

**W4. Order independence by construction.** `[inference, from DMN and ADR-0043]`
- Decision tables allow only two hit policies in Phase 1: **Unique** (overlaps are a validation error at activation) and **monotone combine** (each output dimension combined by max/min/union, as `policy_rule` already does).
- Automation rules on the same event never depend on order: each rule sees the same committed event; rules cannot see each other's effects within the same dispatch. If two rules would act on the same target, activation warns.
- *Tradeoff:* "First" hit policy is the most intuitive for business users; we trade that intuition for results that never depend on row order.

**W5. Loop and runaway guards in the dispatcher, not left to rule authors.** `[doc-backed patterns]`
- Every outbox event carries a **causation chain ID and depth**. An automation-originated command inherits the chain; the dispatcher refuses to run automation rules beyond depth 3 (ServiceNow default) and never runs the same rule twice on the same target within one chain (Odoo pattern).
- Triggers are **change predicates** ("status changed to X", "amount changed"), never "on any write".
- **Static cycle check at activation:** build the graph "rule consumes event type E, may emit event types F" from the command registry; refuse or warn on cycles (Power Automate warns at save).
- **Per-rule rate limit and circuit breaker:** pause a rule automatically after N failures or M executions per hour, and create a work item for the owner (Zapier auto-off).
- **Idempotency key** per (rule version, triggering event ID) so retries never duplicate effects.

**W6. Tests, simulation and replay before activation.** `[doc-backed patterns]`
- Each decision table and automation rule stores **test cases** (input, expected output) alongside it; a debug run in the UI can be saved as a test (Salesforce pattern).
- **What-if replay:** before activation, run the candidate version over the last N days of recorded events or decision inputs (from the outbox and decision records) and show a diff against the active version: which documents would have had a different outcome, with amounts. This is Temporal-style replay applied to configuration, and it reuses the replay suite ERPMe already plans for agents.
- *Tradeoff:* decision inputs must be stored in full (or reconstructable as of a point in time) for replay. That is a storage cost, but ERPMe's audit design (ADR-0038) already leans this way.

**W7. Explainable execution records.** `[doc-backed]`
- For each evaluation: artifact ID and version, input snapshot hash (and the inputs for decisions with money impact), matched rows, output, causation chain. Queryable by agents through the read-only query layer, so "why was this routed to pool X?" is answerable by an agent without guessing.

**W8. Upgrade safety for configuration.** `[inference, from ATF/flow-test lessons]`
- Configuration may reference only registry items (command names, event types, schema field paths) that carry a version and a deprecation status.
- On every core or package upgrade, CI (and the tenant upgrade job) re-validates every active artifact and runs its tests and a short replay; a broken reference blocks the upgrade or deactivates the artifact with a work item, never fails silently at run time.
- Registry items are deprecated with a window, not removed.

### Later phases

- **W9. Expression language for conditions** (Phase 2). Phase 1 conditions are structured (field, operator, value), like ADR-0043. If structured conditions become limiting, add a **non-Turing-complete, side-effect-free expression language** with linear-time evaluation and static type checking (CEL or a FEEL subset). `[inference]` Never Python in configuration.
- **W10. Durable orchestration for long-running, cross-document processes** (Phase 2 or 3), when real cases appear (ECO, NPI, RMA, subcontracting rounds). Options: an embedded durable-execution library over Postgres, or an external engine. Requirements: version pinning at start, explicit migration, replay testing of histories (Temporal model), steps that only call registered commands. *Tradeoff:* significant engineering and operational cost; defer until at least two concrete processes need it.
- **W11. Tenant environments and pipelines** (Phase 2). Sandbox tenant → test → production promotion of configuration bundles with diffs, as Power Platform solutions and pipelines do. Phase 1 uses change proposals inside one tenant with replay instead.
- **W12. Visual designer** (Phase 2+). The data model above (tiers 0 to 2) is designer-friendly; build the designer after the data model is stable. Agents can author the same artifacts through commands from day one.

---

# Topic 2: Using AI to tune existing deterministic functions or build new ones

## 2.1 What products do

### Matching in finance tools (the most mature "AI tunes a deterministic function" domain)
- **SAP Cash Application (ML).** Trained on historical clearing data; produces matching proposals with confidence. Two configurable thresholds: **target accuracy for proposal** (above it, the proposal is shown to the accountant) and **target auto-clear accuracy** (above it, the item is cleared automatically). Below the proposal threshold nothing is shown. The model is retrained periodically. `[doc]` https://learning.sap.com/courses/sap-s-4hana-cloud-for-contract-accounting-invoicing/explaining-the-sap-cash-application-and-machine-learning ; https://help.sap.com/doc/9a9beb477fab46399799c0d042d2328c/1.0/en-US/c217f286d1d54833b7e6cffc9cbb7af9_1.pdf ; https://learning.sap.com/courses/managing-cash-application-for-fi-ca/reviewing-the-sap-cash-application-daily-process-flow
- **SAP ISLM (Intelligent Scenario Lifecycle Management)** in S/4HANA: train embedded or side-by-side models on in-system data, then **deploy and activate** a specific trained model version for the business application. `[doc]` https://assets.dm.ux.sap.com/webinars/2021-12-31-sap-btp-customer-value-network-global/pdfs/islm_overview.pdf
- **BlackLine Transaction Matching.** Rules are either **automatic** or **suggest** matches for review; suggested passes run from least to most stringent; approvers review system-generated suggestions with segregation of duties. 2025: "Matching Agents" that **suggest new pass rules and improve existing ones**. `[blog]` https://www.blackline.com/blog/human-wisdom-process-intelligence/ ; https://www.cpapracticeadvisor.com/2025/05/09/blackline-expands-agentic-ai-capabilities-to-accelerate-future-ready-financial-operations/160783/
- **Oracle Account Reconciliation (Transaction Matching).** Match rules with amount and date tolerances; rule types **Suggested** vs **Confirmed**, plus "No Ambiguous" variants; users confirm or discard suggestions; a **Predict Match** job runs when "Enable Predictive AI" is set. `[doc]` https://docs.oracle.com/en/cloud/saas/account-reconcile-cloud/adarc/admin_trans_match_about_match_rules.html ; https://docs.oracle.com/en/cloud/saas/account-reconcile-cloud/adarc/reconcile_trans_match_run_automatch_100x12869896.html ; https://docs.oracle.com/en/cloud/saas/account-reconcile-cloud/raarc/reconcile_trans_match_confirm_suggested_matching_dialog.html
- **HighRadius Cash Application.** Markets "hit rate" (share of payments auto-matched without manual work) in the mid-90s per case studies, and a set of specialised agents; no public documentation of how rules learn from corrections. `[blog]` https://www.highradius.com/product/automated-cash-application/ (marketing, unaudited)
- **Microsoft.** Business Central bank reconciliation with Copilot: AI matching on top of rule-based matching plus G/L suggestions for leftovers; **nothing is saved until the user selects "Keep it"**. Dynamics 365 Finance advanced bank reconciliation: rule-based matching rules with automatic posting/settlement options (no confirmed Copilot matching in Finance as of this search). `[doc]` https://learn.microsoft.com/en-us/dynamics365/business-central/faqs-bank-reconciliation ; https://learn.microsoft.com/en-us/dynamics365/release-plan/2024wave2/finance-supply-chain/dynamics365-finance/matching-rule-enhancement-advanced-bank-reconciliation

**Common shape** `[inference]`: a deterministic rule engine (passes, tolerances) remains the executor; ML or an LLM either (a) scores candidate matches, gated by two thresholds, or (b) **proposes new rules** that a person approves. Auto-action is a separate, higher threshold. Humans confirm suggestions; segregation of duties applies to the approval.

### Copilots that propose automations
- **Power Automate Copilot** generates and edits cloud flows from natural language and explains flows; the maker reviews in the designer. `[doc]` https://learn.microsoft.com/power-automate/create-cloud-flow-using-copilot
- **Salesforce Einstein / Agentforce for Flow** drafts flows from prompts and summarises flows; practitioners report errors and insist on review. `[doc]` https://admin.salesforce.com/blog/2023/einstein-for-flow-for-salesforce-admins ; `[blog]` https://salesforcebreak.com/2025/03/24/agentforce-assisted-flow-build-experience/
- Common shape `[inference]`: the copilot produces a *draft artifact in the platform's own declarative format*, rendered in the normal editor, activated by a person. None of them auto-activates generated automations.

## 2.2 Techniques and research

### Program synthesis and programming by example
- **PROSE / FlashFill:** restrict the search to a domain-specific language, search deductively over version-space algebras, **rank** candidate programs, and resolve ambiguity by **asking the user about distinguishing inputs** (active learning) or letting them navigate alternatives. `[paper]` https://www.microsoft.com/en-us/research/publication/programming-examples/ ; https://arxiv.org/pdf/1703.03539
- Transfer `[inference]`: an LLM proposing a matching rule from examples has the same ambiguity problem; the remedy is the same: generate several candidates, find inputs on which they disagree, and ask a person to label those few cases.

### LLM-generated decision tables and rules
- **Legal text to DMN** (95 target models): giving the LLM **explicit input/output specifications** produced compact tables with correct interfaces; without them models over-generated inputs and over-complex tables; outcome agreement with gold models only about 51 to 53%; authors recommend experts define I/O, LLM drafts, experts verify. `[paper]` https://arxiv.org/pdf/2604.17153
- **Self-healing DMN generation:** run generated DMN on a deterministic engine, regenerate on failure; reports a small residual error rate. `[paper]` https://csitjournal.khmnu.edu.ua/index.php/csit/article/download/486/317/1583
- **Exam regulations to BPMN/DMN with an LLM** examines whether generated tables are constructible and sound. `[paper]` https://scitepress.org/publishedPapers/2025/134816/pdf/index.html ; earlier GPT-3 study https://ceur-ws.org/Vol-3485/paper3896.pdf
- **Rule induction with LLMs on tabular data:** zero-shot decision trees from LLM knowledge sometimes beat data-driven trees on small datasets; RLIE combines LLM-proposed rules with logistic-regression weighting and notes rule interactions are often ignored. `[paper]` https://arxiv.org/html/2409.18594v2 ; https://arxiv.org/abs/2510.19698

### Evaluator-driven generation
- **AlphaEvolve:** an LLM proposes code diffs; a **user-supplied automated evaluator** scores candidates (often in cascades from cheap to expensive); the best survive. The evaluator is the ceiling, and a weak evaluator gets exploited. `[blog]` https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- **Tests as specification:** benchmarks where tests are the prompt show instruction-following and long-context loss as bottlenecks; generated code is often functional but misaligned with the provided tests. `[paper]` https://arxiv.org/abs/2505.09027 ; https://arxiv.org/abs/2402.13521
- **Eval-driven development for agents:** combine code-based, model-based and human graders; separate capability evals from regression evals; evals resolve spec ambiguity. `[blog]` https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

### Backtesting, champion/challenger, shadow, model governance
- **SR 11-7** (US bank model risk guidance): validation = conceptual soundness, **ongoing monitoring**, and **outcomes analysis** (compare outputs to actual outcomes; backtesting on periods not used in development); predetermined thresholds trigger review. `[doc]` https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm
- **Champion/challenger** in decision management: the champion is the current strategy; each challenger varies one thing; challengers get a small share of live decisions (often under 10%) after **batch simulation** on historical data. `[blog]` https://www.fico.com/blogs/benefits-championchallenger-testing-decision-management ; https://www.fico.com/blogs/adaptive-control-technology-architecture ; product https://devcloud.fico.com/en/products/fico-blaze-advisor-decision-rules-management-system
- **MLflow model registry:** stages deprecated in favour of **aliases** (`@champion`, `@challenger`); promotion and rollback are alias moves; gating logic is written around the registry. `[doc]` https://mlflow.org/docs/latest/model-registry.html ; `[blog]` https://lakefs.io/blog/mlflow-model-registry/
- **Prompt management with labels:** immutable prompt versions, labels such as `production` pointing to one version, protected labels, experiments on datasets gating promotion in CI. `[doc]` https://langfuse.com/docs/prompt-management/features/prompt-version-control ; https://langfuse.com/resources/engineering/prompt-cicd
- **Feature flags:** OpenFeature standardises evaluation with an evaluation context and hooks; stale flags are the main debt and must be removed after rollout. `[doc]` https://openfeature.dev/specification/glossary/

### Human review of AI-written code; sandboxing
- Users with an AI assistant wrote **less secure code** on four of five tasks and were **more confident** it was secure. `[paper]` https://arxiv.org/abs/2211.03622
- A 2025 study of 80 tasks across 100+ models found security flaws in about **45%** of generated samples, with no improvement over time. `[blog]` (vendor research) https://www.veracode.com/resources/genai-code-security-report/
- **Sandboxing generated code:** shared-kernel containers are considered insufficient for untrusted code; options are microVMs (Firecracker), user-space kernels (gVisor) or WebAssembly (capability-based, no ambient authority, best for pure functions). `[blog]` https://fly.io/learn/firecracker-vs-gvisor/

### Rules as data vs rules as code
- **Rules as data** (DMN, BRF+, decision tables): analysable (overlap, completeness), diffable, editable by key users, executed by a trusted engine. **Rules as code** (Catala for legislation, general code): expressive, testable with normal tools, needs developers. Catala shows a middle path: a DSL with default logic ("rule, then exceptions"), literate code next to legal text, and a verified compiler. `[paper]` https://arxiv.org/abs/2103.03198
- **Report definitions:** grounding LLM-generated analytics in a governed semantic layer raised answer accuracy substantially in a small vendor benchmark versus raw text-to-SQL; the vendor recommends the semantic layer for governed numbers and raw SQL only for exploration. `[blog]` https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026 (small benchmark, vendor sells the layer)

## 2.3 Pitfalls

1. **Goodhart on the evaluation set.** Search optimises what is measured (AlphaEvolve's stated limitation). A generator that sees the golden set will overfit it. `[blog]`
2. **Selection bias in historical labels.** Historical "matches" are only those people made; unmatched or wrongly matched items are under-labelled; tuning on them rewards reproducing past mistakes. `[inference]`
3. **Look-ahead leakage in backtests.** Using data that would not have been known at decision time (later payments, later master data). SR 11-7 requires out-of-sample periods. `[doc]` `[inference]`
4. **Uncalibrated confidence.** Model or LLM confidence used directly as a gate; LLM verbalised confidence is especially unreliable. `[paper]` https://arxiv.org/abs/2407.18370
5. **Silent retraining.** Periodic retraining (SAP Cash Application updates its model) changes behaviour without a visible version change unless the platform versions models (ISLM activation). `[doc]` `[inference]`
6. **Rule interaction.** A new rule that is good alone can steal matches from a better rule or create ambiguity (RLIE's observation; Oracle's "No Ambiguous" rule variants exist for this). `[paper]` `[doc]`
7. **Automation bias in review.** Reviewers rubber-stamp AI output; developers are more confident in AI code (Perry et al.). `[paper]`
8. **Generated code security.** High flaw rates in generated code; never run it unsandboxed. `[blog]` `[paper]`
9. **Under-specified generation.** Without explicit I/O contracts, LLMs over-generate inputs and complexity (legal DMN study). `[paper]`
10. **Flag and version debt.** Stale challengers, flags and shadow configurations that nobody removes. `[blog]`
11. **Wrong-but-plausible actions within permissions** (Business Central agent security commentary): an approved rule can still produce permitted, plausible, wrong postings at scale. `[blog]` https://demiliani.com/2026/11/04/giving-an-ai-agent-the-keys-to-business-central-practical-security-tips/

## 2.4 Transferable patterns

- **P2.1 AI proposes an artifact; a deterministic engine executes it; evidence decides promotion.** (Every matching product; every flow copilot; MLflow; FICO.) `[inference]`
- **P2.2 Two thresholds: show vs act.** (SAP Cash Application.) `[doc]`
- **P2.3 Suggested vs confirmed rules; suggest-mode before auto-mode.** (BlackLine, Oracle.) `[doc]` `[blog]`
- **P2.4 Typed I/O contract first, then generation.** (Legal DMN study; PROSE DSL restriction.) `[paper]`
- **P2.5 Disagreement-driven labelling** of a few cases to disambiguate candidates. (PROSE.) `[paper]`
- **P2.6 Batch simulation → shadow → small live share → full.** (FICO, SR 11-7.) `[blog]` `[doc]`
- **P2.7 Pointer-based promotion with instant rollback** (aliases, labels, "one active version"). `[doc]`
- **P2.8 Held-out evaluation the generator never sees; evaluator cascades from cheap to expensive.** (AlphaEvolve.) `[blog]`
- **P2.9 Ongoing monitoring with predefined demotion thresholds.** (SR 11-7.) `[doc]`
- **P2.10 Code only in a sandbox with capability grants, plus human review assisted by static analysis.** `[blog]` `[paper]`

## 2.5 Design recommendations for ERPMe (Topic 2)

### Phase 1

**A1. One lifecycle for every AI-produced "decision artifact".** `[inference]`
- Artifact kinds: **parameter set** (thresholds, tolerances), **decision table version**, **matching rule set** (ordered passes with tolerances), **report definition** (a declarative spec over the read-only query layer), and later **extension function** (code).
- States: `draft → backtested → shadow → assisted → active`, with `retired`. This is the agent-type promotion ladder (ADR-0051) generalised to artifacts. Each transition is a change proposal approved by a person; drafts produced by agents are tainted (ADR-0029) and need a human proposer.
- "Active version per scope" is a pointer; rollback is moving the pointer back, effective immediately, recorded as a command.
- *Tradeoff:* more ceremony for a one-line threshold change. Mitigate with small, fast evidence bundles for parameter sets.

**A2. A frozen evidence bundle is required for each promotion.** `[doc-backed: SR 11-7, Temporal replay, FICO]`
- Backtest on a **time-split** historical window: the window used to draft or fit the artifact is disjoint from, and earlier than, the evaluation window; all inputs reconstructed as of decision time (no look-ahead).
- Metrics against the current champion: precision of automatic actions, coverage (share automated or suggested), number and money value of decisions that change, false auto-actions in money terms, and abstention rate.
- Golden-set results, including a **held-out golden set the generating agent never sees**.
- A sample of **changed decisions** for a person to inspect (the diff, not the totals).
- The bundle is frozen with hashes of data window, artifact version and engine version, like the agent shadow evidence.

**A3. Matching in Phase 1: deterministic passes; AI proposes rules and thresholds, never matches directly with auto-clear.** `[doc-backed: BlackLine, Oracle, SAP]`
- Bank and open-item matching use ordered rule passes with tolerances, each pass marked **confirm** or **suggest**, and an ambiguity rule (if more than one candidate satisfies a pass, it becomes a suggestion, never an auto-match).
- An agent may analyse manual matches and overrides and **propose** a new pass, a tolerance change or a pass reordering, as a change proposal with the evidence bundle.
- Auto-confirm passes require a person to approve the rule, with segregation of duties (rule proposer ≠ approver), and require backtested precision above a configured target at the chosen tolerance.
- *Tradeoff:* lower automation rate than an ML scorer at first. Gain: every auto-match is explainable by a rule ID and version, which auditors and the Vietnamese overlay will want.

**A4. Confidence that gates anything must be calibrated on ERPMe's own outcomes.** `[paper-backed]`
- Two thresholds per artifact (show-suggestion, auto-act), both **parameters** in the artifact, chosen from the backtest curve (precision vs coverage) to meet a target precision; never an LLM's self-reported confidence.
- In Phase 1 the auto-act threshold is disabled by default (assisted only), matching the agent shadow → assisted stance.

**A5. Report definitions are declarative specs over the query layer, not SQL.** `[blog-backed]`
- An agent drafts a report definition (measures and dimensions from the query layer's published catalogue, filters, grouping, layout). The engine validates it against the schema and the requester's read scope, executes it deterministically, and the LLM never computes or restates numbers.
- Saving a report for others is an artifact change (A1) with a small evidence bundle: sample output on a fixed period, compared with a hand-checked known answer for at least one cell.

**A6. No AI-generated code runs in production in Phase 1.** `[paper-backed]`
- AI may write code for the ERPMe codebase or a customer package only through the normal repository path: tests first, human code review, static analysis, CI with the invariant harness.
- *Tradeoff:* company-specific functions wait for a developer. Given the security evidence, this is the right default.

**A7. Monitoring and automatic demotion.** `[doc-backed: SR 11-7]`
- For each active artifact, track the override rate (people reversing or changing its outcomes), the suggestion acceptance rate, and the abstention rate. Predefined thresholds demote it automatically to `assisted` (or to the previous version) and open a work item; promotion back needs a new evidence bundle.

### Later phases

**A8. ML scorers behind the same lifecycle** (Phase 2). Add learned match scoring (SAP Cash Application style) as another artifact kind: a model version with a frozen training window, calibrated thresholds, and the same backtest → shadow → assisted → active ladder. Retraining always produces a new version; never mutate a model in place (the ISLM "activate a trained model" pattern). `[doc]` `[inference]`

**A9. Champion/challenger on live traffic** (Phase 2). For artifacts where outcomes are observable soon (matching, pricing suggestions), route a small share of *suggestions* (not postings) to a challenger and compare acceptance and override rates. Postings stay with the champion. `[blog]` `[inference]`

**A10. Generated extension functions in a sandbox** (Phase 3). Company-specific validation or pricing functions as **pure functions** with typed inputs and outputs, compiled to WebAssembly (or run in gVisor/microVM), with no I/O, CPU/memory/time limits and capability-based access only to values passed in. Required: tests written and approved before the code, property-based tests, human code review with static analysis, the A2 evidence bundle, and the result consumed as a *proposal* by deterministic core code (the function never posts). `[blog]` `[paper]` `[inference]`
- *Tradeoff:* a sandbox runtime and a function ABI are real engineering. The payoff is that a customer-specific rule no longer requires a core release.

**A11. A small rules DSL** (Phase 3, only if decision tables plus expressions prove insufficient). Prefer a total, side-effect-free DSL with default-logic structure (Catala-like "rule, then exceptions"), which is easier for both people and LLMs to verify than general code. `[paper]` `[inference]`

**A12. Disagreement-driven labelling UI** (Phase 2). When an agent proposes several candidate rules, show the reviewer the few historical cases where candidates disagree and ask for labels (PROSE pattern). Turns review from "read this rule" into "decide these five cases". `[paper]` `[inference]`

---

# Cross-cutting: agentic workflow architecture in enterprises (2024 to 2026)

## 3.1 What the major systems and research do

### Framework guidance
- **Anthropic, "Building effective agents":** distinguishes **workflows** (LLMs and tools orchestrated through predefined code paths) from **agents** (LLMs directing their own process and tools). Patterns: prompt chaining with programmatic gates, routing, parallelization (sectioning, voting), **orchestrator-workers**, **evaluator-optimizer**. Start with the simplest solution; use agents only for open-ended problems where steps cannot be hard-coded and the model's decisions can be trusted; use maximum-iteration stopping conditions, sandboxed testing and guardrails; keep it simple, make planning transparent, and design the agent-computer interface (tool docs and tests) carefully. `[blog]` https://www.anthropic.com/engineering/building-effective-agents
- **Anthropic, "Writing effective tools for agents":** tools are a contract between deterministic systems and non-deterministic agents; choose few, namespaced tools; return meaningful, token-efficient context; iterate tool descriptions with evaluations. `[blog]` https://www.anthropic.com/engineering/writing-tools-for-agents
- **OpenAI Agents SDK:** **input guardrails** (first agent; parallel by default, or blocking so the agent never runs if the tripwire fires), **output guardrails** (final agent), **tool guardrails** (before/after each function-tool call, including delegated agents); tripwires raise exceptions. **Human-in-the-loop:** `needs_approval` on a tool (boolean or per-call function); the run pauses with interruptions; state serialises to `RunState` and resumes after `approve`/`reject`; the docs advise server-side storage of state, reviewer identity verification and **idempotency keys** so approved side effects are not repeated after a crash. Tracing is on by default. `[doc]` https://openai.github.io/openai-agents-python/guardrails/ ; https://openai.github.io/openai-agents-python/human_in_the_loop/
- **LangGraph:** explicit graphs; a **checkpointer** saves state at every super-step into threads; `interrupt()` pauses for human input and resumes with a command; **time travel** replays or forks from earlier checkpoints; the resumed node re-executes from the top, so side effects before an interrupt can repeat; `recursion_limit` caps steps (`GraphRecursionError`). `[doc]` https://docs.langchain.com/oss/python/langgraph/persistence ; https://docs.langchain.com/oss/python/langgraph/use-time-travel ; https://reference.langchain.com/python/langgraph/errors/GraphRecursionError ; `[blog]` https://levelup.gitconnected.com/your-langgraph-node-runs-twice-after-interrupt-thats-by-design-99ad00fc48ef
- **Microsoft:** Copilot Studio **agent flows** are deterministic workflows agents call as tools; **generative orchestration** is the default for new agents; guidance recommends hybrids, deterministic for identity verification and consent, generative for open-ended steps ("Don't try to make the whole journey either fully scripted or fully generative"). Built-in **agent evaluation** with test sets (up to 100 cases), graders, and a REST API for CI. **Microsoft Agent Framework** (2025) succeeds Semantic Kernel and AutoGen, with graph-based workflows for explicit orchestration. `[doc]` https://learn.microsoft.com/en-us/microsoft-copilot-studio/flows-overview ; https://learn.microsoft.com/microsoft-copilot-studio/guidance/generative-orchestration ; https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/voice-agents-control-conversation ; https://learn.microsoft.com/microsoft-copilot-studio/analytics-agent-evaluation-intro ; https://learn.microsoft.com/en-us/microsoft-copilot-studio/analytics-agent-evaluation-rest-api ; `[blog]` https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/

### Enterprise application vendors
- **Salesforce Agentforce.** Atlas reasoning engine routes a request to a **topic** (now "subagent") with its **actions**; the **Einstein Trust Layer** provides masking, toxicity filtering, zero data retention with model providers and logging. 2025 to 2026: **Agent Script** and **hybrid reasoning** separate deterministic execution from LLM reasoning. Key rules from Salesforce's architecture guide: "if you can express a decision as code, it should be written as logic"; actions hidden unless an `available when` condition holds ("The LLM can't call an action it can't access"); guard clauses run unconditionally; **never let the LLM set a gate variable**; close gates or use `has_run` flags to prevent loops; deterministic paths give reproducible audit trails. Testing Center runs batch test suites stored as metadata. `[doc]` https://architect.salesforce.com/docs/architect/fundamentals/guide/hybrid-reasoning-agentforce-builder-agent-script ; https://trailhead.salesforce.com/content/learn/modules/reasoning-in-artificial-intelligence/discover-the-atlas-reasoning-engine ; `[blog]` https://developer.salesforce.com/blogs/2026/08/migrate-legacy-agents-to-the-new-agentforce-builder ; https://stackoverflow.blog/2025/05/28/a-deep-dive-into-building-an-agent-framework-for-salesforce/
- **SAP Joule agents / Joule Studio.** Agent builder on the same framework as SAP's prebuilt agents, with tools and MCP servers; agents cannot exceed human authorisation; minimal OData scopes; separate audit logs. Approval gates are built from confirmation cards, SAP Build Process Automation approval steps or Task Center tasks. Trade press reports customers needed hard rules and approval gates the first version lacked; Joule Studio 2.0 (Sapphire 2026) adds agentic flows with sub-agents, approval loops and compliance logging. `[doc]` https://www.sap.com/sweden/documents/2026/06/526001c1-567f-0010-bca6-c68f7e60039b.html ; `[blog]` https://news.sap.com/2026/05/new-joule-studio-enterprise-scale-agentic-development/ ; https://www.cio.com/article/4240684/sap-wants-joule-to-run-business-workflows-not-just-answer-questions.html
- **Oracle AI Agent Studio for Fusion.** Templates, tools, LLM choice, explicit **approval steps** in agent workflows; October 2025 added **deterministic workflow agents** with loops, branching and human-in-the-loop approvals integrated with Fusion workflows; partner templates vetted against a readiness checklist. `[doc]` https://docs.oracle.com/en/cloud/saas/fusion-ai/aiaas/get-started.html ; `[blog]` https://blogs.oracle.com/fusioninsider/new-oracle-ai-agent-studio-for-fusion-apps ; https://siliconangle.com/2025/10/15/oracles-ai-agent-studio-gets-enterprise-controls-llm-flexibility-deterministic-workflows/
- **ServiceNow AI Agents.** AI Agent Studio, agentic workflows, AI Agent Orchestrator. An AI agent action in a flow runs **autonomous** (no approval) or **supervised** (the flow pauses until a designated user authorises). Launch guidance: reads autonomous, writes supervised, relax as confidence grows. `[doc]` https://www.servicenow.com/docs/r/0MvJg~UYByX0VxWLomI71w/uLwlQhnQq4tIhZoPkbDpyg ; https://www.servicenow.com/docs/r/zurich/intelligent-experiences/exploring-ai-agents.html ; `[blog]` https://www.techtarget.com/ai/news/366618614/ServiceNow-intros-AI-agent-studio-and-orchestrator
- **Workday Agent System of Record.** A registry to onboard first- and third-party agents, define roles and responsibilities, apply role-based access, audit, monitor and **budget and forecast costs**; integrated with Microsoft Entra Agent ID for agent identities. `[doc]` https://www.workday.com/en-be/artificial-intelligence/agent-system-of-record.html ; `[blog]` https://en-hk.newsroom.workday.com/2025-02-11-The-Next-Generation-of-Workforce-Management-is-Here-Workday-Unveils-New-Agent-System-of-Record
- **Dynamics 365 Business Central agents** (Sales Order Agent and others): in-product notifications bring humans in; outgoing customer messages reviewed before sending (configurable); effective permissions are the **intersection** of the agent's permissions and the assigning user's; agents cannot configure users or other agents; least privilege; an activity timeline for audit. `[doc]` https://learn.microsoft.com/en-us/dynamics365/business-central/faqs-sales-order-taker-agent ; https://learn.microsoft.com/en-ca/dynamics365/business-central/dev-itpro/ai/ai-development-toolkit-best-practices

### Security research: prompt injection, permissions, taint
- **Dual LLM pattern:** a privileged LLM with tools sees only trusted input; a quarantined LLM without tools processes untrusted content; a non-LLM controller passes references, never raw quarantined output, to the privileged model. `[blog]` https://simonwillison.net/2023/Apr/25/dual-llm-pattern/
- **CaMeL:** extract control flow and data flow from the trusted query into a program; a custom interpreter tracks data provenance as **capabilities** and enforces policies before each tool call, so untrusted data cannot change the program's path; residual side channels remain. `[paper]` https://arxiv.org/abs/2503.18813
- **Design patterns for securing LLM agents** (six patterns): action-selector (strongest), **plan-then-execute**, LLM map-reduce, dual LLM, code-then-execute, context-minimisation. Plan-then-execute stops new tools from being introduced by injected content but still exposes tool arguments. `[paper]` https://arxiv.org/abs/2506.08837
- **FIDES (information-flow control for agents):** confidentiality and integrity labels on data in a lattice; deterministic policy checks on tool calls; planner keeps risky tool output in variables it does not read; with policy checks, all AgentDojo injection attacks were stopped. Argues IFC beats human confirmation prompts, which cause fatigue and invite social engineering. `[paper]` https://arxiv.org/abs/2505.23643
- **Spotlighting** (delimiting, datamarking, encoding untrusted text) reduces indirect injection success substantially with little task cost; one layer of defence in depth. `[paper]` https://arxiv.org/html/2403.14720v1
- **AgentDojo:** a stateful benchmark of tasks and injection cases with **deterministic utility and security checks over environment state** (no LLM judge). `[paper]` https://arxiv.org/abs/2406.13352
- **OWASP Top 10 for LLM Applications 2025:** prompt injection is #1; **Excessive Agency** (excessive functionality, permissions, autonomy) expanded for agents. `[doc]` https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
- **MCP tool annotations** (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) are hints and must be treated as untrusted unless the server is trusted. `[doc]` https://modelcontextprotocol.io/specification/draft/server/tools

### Evals, confidence and observability
- **Evals:** code-based graders where possible, model graders for open text, human graders for calibration; capability vs regression suites. `[blog]` https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- **Selective prediction with guarantees:** calibrate an abstention threshold on labelled data to guarantee a target agreement with humans, trading coverage for precision; cascades from cheap to strong models. `[paper]` https://arxiv.org/abs/2407.18370
- **OpenTelemetry GenAI semantic conventions:** spans for model calls (`{gen_ai.operation.name} {gen_ai.request.model}`), agent creation and invocation, tool execution; content not recorded by default; still in Development status. `[doc]` https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/ ; https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
- **Prompt and dataset versioning** with labels and CI experiments. `[doc]` https://langfuse.com/docs/prompt-management/features/prompt-version-control

## 3.2 Common patterns, and where ERPMe stands

| Pattern | Industry evidence | ERPMe today (from ADR titles and brief) | Gap or action |
|---|---|---|---|
| **Deterministic orchestration with bounded LLM steps** | Anthropic workflows; Agentforce hybrid reasoning and Agent Script; Copilot Studio agent flows; Oracle workflow agents; LangGraph graphs; SAP Joule 2.0 | Agent types are versioned code with fixed tool lists | Aligned. Make each LLM step's output a typed schema validated before use. |
| **Typed tool contracts** | Anthropic tool guidance; OpenAI tool guardrails; MCP annotations; Agentforce `available when` | Fixed tool lists; commands with plan hashes | Add per-tool side-effect class and precondition gating, enforced server-side. |
| **Confidence and abstention** | SAP Cash Application thresholds; selective prediction research | Shadow → assisted promotion | Add calibrated abstention per agent type and artifact; abstain to the work queue. |
| **HITL queues** | OpenAI interruptions; LangGraph interrupts; ServiceNow supervised mode; Business Central notifications | Work queue, approval pools, policy table | Aligned. Approve at business granularity (a proposal with a diff), not per tool call. |
| **Audit** | Trust Layer logging; Business Central timeline; Workday registry | Audit and observability ADR; frozen evidence | Add OTel-compatible spans linked to command IDs. |
| **Cost budgets** | Workday cost forecasting; max_turns, recursion limits | Budgets in agent runtime (ADR-0050 lists "budgets never exceeded") | Make budgets hierarchical (run, agent type per day, tenant per month) and hard. |
| **Versioning of prompts and models** | Langfuse labels; MLflow aliases; Camunda versions agent definitions with the process | Versioned agent types | Version = code + prompts + model snapshot ID + tool list + schemas; any change re-runs replay. |
| **Regression evals** | Copilot Studio evaluation API; Agentforce Testing Center; AgentDojo deterministic checks | Golden sets, replay suite, evaluation job in CI | Aligned. Add held-out sets and injection canaries per agent type. |

## 3.3 Pitfalls

1. **Pure LLM orchestration is non-reproducible and hard to audit** ("the agent decided" is weak evidence in a compliance review). `[doc]` Salesforce architecture guide.
2. **Confirmation fatigue.** Per-action prompts train people to click yes; IFC research argues for deterministic policy instead. `[paper]` FIDES.
3. **Side effects repeated on resume** (LangGraph node re-execution; OpenAI SDK idempotency advice). `[doc]`
4. **Parallel guardrails let the agent spend tokens and call tools before the tripwire fires.** Use blocking mode for anything with side effects. `[doc]` OpenAI SDK.
5. **Tool annotations and model-declared intent are not enforcement.** `[doc]` MCP.
6. **Excessive agency through broad tools** (one "execute query" or "call API" tool). `[doc]` OWASP.
7. **LLM judges fooled by the same injection.** Prefer deterministic state checks for security evals (AgentDojo). `[paper]`
8. **Model drift under a fixed name.** Provider model aliases change underneath; pin snapshots. `[inference]`
9. **Unbounded loops and cost** (recursion limits exist because loops happen). `[doc]`
10. **Taint laundering by a human edit** (ERPMe's own ADR-0029 finding F4), echoed by CaMeL/FIDES: provenance must survive transformations, and clearing taint must be an explicit, recorded act. `[inference]`

## 3.4 Design recommendations for ERPMe (cross-cutting)

### Phase 1

**X1. Keep "workflow first, agent second" as a rule in the agent-type definition.** `[blog: Anthropic; doc: Salesforce]`
- Each agent type is a fixed graph. LLM nodes are limited to: classify, extract into a typed schema, draft text, propose a structured artifact. Branching, gating, sequencing, arithmetic and validation are code.
- Gate variables (for example "inquiry is a quotation request", "customer identified") are set only by deterministic code from validated outputs, never by the LLM directly (Agentforce rule).

**X2. Typed tool contracts with a side-effect class, enforced by the runtime.** `[doc: OpenAI, MCP, Agentforce]`
- Each tool declares: input and output schemas; side-effect class (`read`, `draft`, `propose`; no `post` or `submit` class exists for agents); idempotency key rule; read scope; taint behaviour (does its output taint the run).
- Tools are visible to the LLM only when their preconditions hold in the run state (Agentforce `available when`), which also shrinks the prompt.
- The runtime, not the tool description, enforces all of this.

**X3. Make the taint model an information-flow model with plan-then-execute.** `[paper: CaMeL, FIDES, design patterns]`
- The agent type's plan (which tools, in which order, with which argument sources) is fixed by code or produced before any untrusted content is read.
- Untrusted content (incoming e-mail, e-invoices, attachments, web) is processed only by a **quarantined extraction step** with no tools, whose output is a typed schema; free text from it is carried as a labelled value and never placed into the instruction channel of a privileged step.
- Labels propagate through every derived value and document version (already started with `document_version.is_tainted` and `derived_from_version_id`); a tainted value can fill a draft but cannot select a tool, a recipient outside the read scope, or a command.
- Spotlighting/datamarking of untrusted text as defence in depth only.
- Injection canary cases in each golden set (ADR-0050 already lists canary tests).

**X4. HITL at business granularity, durable and idempotent.** `[doc: OpenAI SDK, LangGraph, ServiceNow]`
- The unit a person approves is a draft document or change proposal with a diff and the evidence, delivered as a work item, not a tool call.
- Run state is persisted server-side; resuming after approval re-executes nothing with side effects (idempotency key per command, which the command envelope's plan hash already supports).
- Supervised vs autonomous is a property of the agent type version's promotion state, never a runtime switch the LLM can influence.

**X5. Calibrated abstention.** `[paper: selective prediction]`
- Each agent type and artifact has an abstention rule derived from golden-set calibration: if the deterministic validators fail, or the calibrated score is below threshold, or the extraction has missing required fields, the run abstains and creates a work item with what it found.
- Track coverage (non-abstained share) and precision as the two promotion metrics; promotion requires a target precision at a stated coverage.

**X6. Hard, hierarchical budgets.** `[doc: max_turns, recursion_limit; blog: Workday cost tracking]`
- Per run: maximum LLM calls, tokens, tool calls, wall time. Per agent type per day and per tenant per month: token and money ceilings. On breach the run stops cleanly and abstains; the type is paused if daily caps trip repeatedly (circuit breaker), with a work item for the owner.

**X7. One version identity for everything the LLM touches.** `[doc: Langfuse, MLflow, Camunda]`
- Agent type version = code hash + prompt hashes + **pinned model snapshot ID** + tool list + schema versions + parameter set. Any change produces a new version that must pass replay on the golden sets (including held-out) before shadow.
- A provider model deprecation is treated as an agent-type change, not an operational detail.

**X8. Observability compatible with OpenTelemetry GenAI conventions.** `[doc: OTel]`
- Emit spans for agent invocation, each LLM call and each tool call with the GenAI attribute names, linked to the command ID, document ID, agent run ID and work item ID. Content stored in ERPMe's own audit tables under its retention rules; spans carry hashes and references only (OTel's default of not recording content fits privacy needs).

**X9. A single registry of agent types and decision artifacts.** `[doc: Workday ASOR, Business Central]`
- One queryable inventory: agent types and their versions, decision artifacts (A1) and their versions, owner, promotion state, permissions (as the intersection with the assigning user, Business Central style), budgets, recent metrics. Agents can read it through the query layer; only people change it.

**X10. Deterministic graders first.** `[paper: AgentDojo; blog: Anthropic evals]`
- Golden-set checks assert on resulting state (draft fields, proposed rows, chosen command, refusal) rather than on prose. Model graders only for the quality of drafted text, calibrated against human labels.

### Later phases

- **X11. Orchestrator-worker agents** (Phase 2+) for open-ended analysis (for example "why did margin drop on product family X"), still read-only, outputting a report definition (A5) and a narrative with every number coming from the query layer. `[blog: Anthropic]`
- **X12. Evaluator-optimizer loops for artifact generation** (Phase 2): an agent drafts a matching rule set or decision table, the deterministic backtester scores it, the agent revises, within a budget; the held-out set is never shown to the loop (AlphaEvolve lesson). `[blog]` `[inference]`
- **X13. External agent interoperability** (Phase 3): expose ERPMe commands to external agents (MCP or similar) only as `draft`/`propose` tools with the same policy, taint and budget enforcement, and register external agents in X9 with their own identities. `[doc: Workday/Entra Agent ID; MCP]`

---

# Consolidated recommendation list

| ID | Recommendation | Phase | Main tradeoff |
|---|---|---|---|
| W1 | Three configuration tiers: parameters, decision tables, event-condition-action rules over registered commands; everything else is code | 1 | Less flexibility than open low-code; much easier to verify and for agents to use |
| W2 | No BPMN/orchestration engine; approvals via policy table, pools, work queue | 1 | Long multi-document processes stay in code |
| W3 | Immutable, effective-dated config versions activated through change proposals; record version per evaluation | 1 | Ceremony for small changes |
| W4 | Only Unique or monotone-combine hit policies; rules never depend on order | 1 | Less intuitive than "first match" |
| W5 | Causation chain depth cap 3, same-rule-same-target once per chain, change-predicate triggers, static cycle check, circuit breakers, idempotency | 1 | Some legitimate cascades need a code-level flow |
| W6 | Tests stored with artifacts; what-if replay against recorded history before activation | 1 | Storage of decision inputs |
| W7 | Explainable execution records readable by agents | 1 | Storage |
| W8 | Config references only versioned registry items; re-validate and replay on upgrade | 1 | Registry discipline in core development |
| W9 | Non-Turing-complete expression language (CEL/FEEL subset) | 2 | New surface to secure |
| W10 | Durable orchestration with pinned versions and replay | 2–3 | Large engineering cost |
| W11 | Tenant environments and promotion pipelines | 2 | Operational complexity |
| W12 | Visual designer over the same artifacts | 2+ | UI cost |
| A1 | One lifecycle for AI-produced artifacts: draft → backtested → shadow → assisted → active | 1 | Process overhead |
| A2 | Frozen evidence bundle: time-split backtest, champion comparison, held-out golden set, changed-decision sample | 1 | Requires as-of reconstruction of inputs |
| A3 | Matching: deterministic passes (confirm/suggest, ambiguity → suggest); AI proposes rules and tolerances | 1 | Lower initial automation rate |
| A4 | Two calibrated thresholds (show, act); auto-act off by default | 1 | Slower path to automation |
| A5 | Report definitions as declarative specs over the query layer | 1 | Query layer catalogue must be rich enough |
| A6 | No AI-generated code in production; AI code only via repo review | 1 | Customer-specific logic waits for developers |
| A7 | Monitoring with automatic demotion on override-rate thresholds | 1 | Tuning of thresholds |
| A8 | ML scorers as versioned artifacts, never retrained in place | 2 | ML ops cost |
| A9 | Champion/challenger on suggestions, never on postings | 2 | Needs volume to be meaningful |
| A10 | Sandboxed pure extension functions (Wasm or microVM) with tests-first review | 3 | Runtime and ABI engineering |
| A11 | Small default-logic rules DSL if needed | 3 | Language design cost |
| A12 | Disagreement-driven labelling for candidate rules | 2 | UI work |
| X1 | Workflow-first agent types; LLM never sets gate variables | 1 | Less "magic" |
| X2 | Typed tools with side-effect class and precondition visibility, runtime-enforced | 1 | Tool authoring effort |
| X3 | Plan-then-execute plus quarantined extraction plus label propagation | 1 | Some tasks become harder to automate |
| X4 | HITL on proposals with diffs; durable, idempotent resume | 1 | — |
| X5 | Calibrated abstention to the work queue | 1 | Needs labelled golden sets per type |
| X6 | Hard hierarchical budgets with circuit breakers | 1 | Occasional false stops |
| X7 | Version identity includes pinned model snapshot and prompts | 1 | Re-evaluation on every provider change |
| X8 | OTel GenAI-compatible spans linked to commands | 1 | Conventions still in Development status |
| X9 | One registry of agent types and decision artifacts | 1 | — |
| X10 | Deterministic graders first | 1 | Prose quality needs separate grading |
| X11 | Read-only orchestrator-worker analysis agents | 2+ | Cost and latency |
| X12 | Evaluator-optimizer loops for artifact drafting | 2 | Overfitting risk; mitigated by held-out sets |
| X13 | External agents only as draft/propose tools under the same controls | 3 | Integration surface |

# Open questions for the architect

1. **Automation actor.** Do automation rules act as a dedicated system actor kind in the policy table, or as the person who activated the rule (Business Central intersects agent and assigning-user permissions)? Recommendation `[inference]`: a dedicated actor kind, with the rule's approver recorded, and a floor that automation can never post or submit beyond what ADR-0043 floors allow.
2. **Decision input retention.** How long are full decision inputs kept for replay and backtests, given storage and personal-data rules? This bounds W6 and A2.
3. **Golden-set labelling ownership.** Who labels held-out sets per tenant, and how are tenant-specific golden sets kept out of the public repository?
4. **Threshold for introducing W10.** Which two concrete long-running processes would justify a durable orchestration engine?
5. **Phase 1 matching scope.** Is bank-statement matching in Phase 1 (ADR-0048), and is the target "suggest only" for the first customer go-live?

# Source index (by topic)

**Workflow and rules platforms**
- SAP: https://learning.sap.com/courses/sap-workflow-overview-basics-strategy-and-extensibility/explaining-sap-fiori-applications-and-building-blocks-for-flexible-workflow ; https://blogs.sap.com/2019/12/03/sap-s-4hana-cloud-flexible-workflow-with-new-custom-pre-condition-for-purchase-requisition/ ; https://en.wikipedia.org/wiki/BRFplus ; https://userapps.support.sap.com/sap/support/knowledge/en/3386566 ; https://learning.sap.com/courses/SAP-Build-Experience/312-1_Automation_Run-Process ; https://blog.sap-press.com/central-decision-management-in-sap-build-process-automation
- Microsoft: https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/business-events/home-page ; https://learn.microsoft.com/en-ca/dynamics365/fin-ops-core/fin-ops/organization-administration/configure-workflow-properties ; https://learn.microsoft.com/en-us/power-automate/guidance/coding-guidelines/avoid-anti-patterns ; https://learn.microsoft.com/en-us/power-platform/guidance/white-papers/managed-environment-activation
- Odoo: https://www.odoo.com/documentation/18.0/applications/studio/automated_actions.html ; https://github.com/odoo/odoo/blob/18.0/addons/base_automation/models/base_automation.py
- ServiceNow: https://www.servicenow.com/docs/r/zurich/application-development/flow-designer.html ; https://www.servicenow.com/docs/r/build-workflows/workflow-studio/flow-designer-system-properties.html
- Salesforce: https://developer.salesforce.com/docs/atlas.en-us.238.0.apexcode.meta/pages/apex_triggers_order_of_execution.htm ; https://admin.salesforce.com/blog/2021/learn-moar-in-winter-22-with-flow-enhancements
- Camunda: https://docs.camunda.io/docs/components/best-practices/operations/versioning-process-definitions/ ; https://docs.camunda.io/docs/components/modeler/dmn/decision-table-hit-policy/
- Temporal: https://docs.temporal.io/develop/safe-deployments ; https://docs.temporal.io/develop/python/workflows/versioning
- Zapier and n8n: https://help.zapier.com/hc/en-us/articles/14167175792909-Decide-how-your-Zap-handles-errors-with-advanced-settings ; https://docs.n8n.io/build/manage-workflows/view-change-history

**AI-tuned deterministic functions**
- https://learning.sap.com/courses/sap-s-4hana-cloud-for-contract-accounting-invoicing/explaining-the-sap-cash-application-and-machine-learning ; https://www.blackline.com/blog/human-wisdom-process-intelligence/ ; https://docs.oracle.com/en/cloud/saas/account-reconcile-cloud/adarc/admin_trans_match_about_match_rules.html ; https://learn.microsoft.com/en-us/dynamics365/business-central/faqs-bank-reconciliation ; https://learn.microsoft.com/power-automate/create-cloud-flow-using-copilot ; https://admin.salesforce.com/blog/2023/einstein-for-flow-for-salesforce-admins
- https://www.microsoft.com/en-us/research/publication/programming-examples/ ; https://arxiv.org/pdf/2604.17153 ; https://arxiv.org/html/2409.18594v2 ; https://deepmind.google/discover/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ ; https://arxiv.org/abs/2505.09027 ; https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm ; https://www.fico.com/blogs/benefits-championchallenger-testing-decision-management ; https://mlflow.org/docs/latest/model-registry.html ; https://openfeature.dev/specification/glossary/ ; https://arxiv.org/abs/2211.03622 ; https://www.veracode.com/resources/genai-code-security-report/ ; https://fly.io/learn/firecracker-vs-gvisor/ ; https://arxiv.org/abs/2103.03198 ; https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026

**Agentic architecture**
- https://www.anthropic.com/engineering/building-effective-agents ; https://www.anthropic.com/engineering/writing-tools-for-agents ; https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents ; https://openai.github.io/openai-agents-python/guardrails/ ; https://openai.github.io/openai-agents-python/human_in_the_loop/ ; https://docs.langchain.com/oss/python/langgraph/persistence ; https://learn.microsoft.com/en-us/microsoft-copilot-studio/flows-overview ; https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/
- https://architect.salesforce.com/docs/architect/fundamentals/guide/hybrid-reasoning-agentforce-builder-agent-script ; https://news.sap.com/2026/05/new-joule-studio-enterprise-scale-agentic-development/ ; https://docs.oracle.com/en/cloud/saas/fusion-ai/aiaas/get-started.html ; https://www.servicenow.com/docs/r/0MvJg~UYByX0VxWLomI71w/uLwlQhnQq4tIhZoPkbDpyg ; https://www.workday.com/en-be/artificial-intelligence/agent-system-of-record.html ; https://learn.microsoft.com/en-us/dynamics365/business-central/faqs-sales-order-taker-agent
- https://simonwillison.net/2023/Apr/25/dual-llm-pattern/ ; https://arxiv.org/abs/2503.18813 ; https://arxiv.org/abs/2506.08837 ; https://arxiv.org/abs/2505.23643 ; https://arxiv.org/html/2403.14720v1 ; https://arxiv.org/abs/2406.13352 ; https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ ; https://modelcontextprotocol.io/specification/draft/server/tools ; https://arxiv.org/abs/2407.18370 ; https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/ ; https://langfuse.com/docs/prompt-management/features/prompt-version-control
