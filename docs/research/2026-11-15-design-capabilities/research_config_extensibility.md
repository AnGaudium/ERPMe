# Research: customer extensibility, customization levels and safe extension code

Date: 2026-11-15. Scope: the four open items of DS-28 and DS-34 on extension code, the placement of levels 1 and 3, configurable agent triggers, and the circuit breaker's bounds. Inputs: `docs/open-questions.md` (the L3 code, spec 16 levels, automation choices and agent trigger items), ADR-0058, ADR-0059 rules 23–24, spec 16 and spec 10. This report complements `research_workflows_ai_rules.md` (the W1–W12 and A1–A10 survey) and does not repeat it. Tags: `[doc]` vendor documentation, `[blog]` secondary source, `[inference]` my reading.

## 1. Survey

### 1.1 What ships on day one, and where configuration ends

| Platform | Day-one levels (no code) | Code level | Where the line sits |
| --- | --- | --- | --- |
| SAP S/4HANA Cloud | Key-user apps: custom fields, custom logic, flexible workflow start and step conditions in *Manage Workflows* | "ABAP for key users" (a restricted language version) in cloud BAdIs; ABAP Cloud on stack over released APIs; BTP side by side | New workflow conditions need a BAdI (`SWF_WORKFLOW_CONDITION_DEF`); the clean core model (A–D, August 2025) grades an extension by its least clean part `[doc][blog]` |
| Dynamics 365 F&O and Dataverse | Business rules, Power Automate flows, workflow editor | X++ extensions (Chain of Command), Dataverse plug-ins | Overlayering is impossible since 8.0: Microsoft hard-sealed its models and overlayered code does not compile `[doc]` |
| Oracle Fusion | Approval rules in BPM Worklist (AMX): rule sets, If-conditions on attributes, approver lists or groups; no nested conditions | Groovy in Application Composer, limited to a list of allowed classes and methods; anything else raises a security violation | Approval routing is configuration; validation and triggers are restricted script `[doc]` |
| NetSuite | SuiteFlow workflows on server triggers (before load, before submit, after submit, scheduled) | SuiteScript with governance units | Workflow actions and scripts share one unit model `[doc]` |
| Odoo | Automation rules (on save with watched fields, date-based, webhook) and Studio | Server actions running Python under `safe_eval` | Python sits inside configuration; `safe_eval` checks bytecode opcodes, and a rewrite was proposed because opcodes change each Python release `[doc][blog]` |
| Salesforce | Flow (record-triggered with entry conditions) | Apex under governor limits | "If you can express a decision as code, it should be written as logic" (Agentforce guidance, cited in the earlier survey) |
| Shopify | Settings in apps | Functions: WebAssembly modules, deterministic, metered | The function computes; the platform applies the result `[doc]` |
| Workday Extend | Business process configuration | Extend apps and orchestrations | Apps move Implementation → Sandbox → Production and cannot be removed once installed `[blog]` |

Every platform ships key-user configuration (fields, conditions, approval routing, event-triggered automation) at go-live. Code always arrives through a separate channel with its own review: a restricted language, a governed runtime, or a sealed extension model. None of the surveyed vendors lets a key user's configuration change vendor code, and the two that allow scripts in configuration (Odoo `safe_eval`, Oracle Groovy) restrict them by allowlists that need constant upkeep. `[inference]`

### 1.2 Limits and circuit breakers, with their defaults

**Per-execution quotas are fixed by the platform:**
- **Salesforce Apex:** 10,000 ms CPU synchronous and 60,000 ms asynchronous; 6 MB heap (12 MB asynchronous); 100 SOQL queries (200 asynchronous); 150 DML statements. A heap breach raises an uncatchable `LimitException`. `[doc]`
- **NetSuite SuiteScript, units per execution:** user event 1,000; workflow action 1,000 per state; Suitelet 1,000; client 1,000 per script; RESTlet 5,000; scheduled 10,000; custom plug-in 10,000. A breach terminates the script. `[doc]`
- **Shopify Functions:** binary 256 KiB; linear memory 10 MiB; stack 512 kB; 11 million instructions, 128 kB input and 40 kB output for carts of up to 200 lines (scaling above that); logs 1 kB. "Shopify doesn't allow nondeterminism in functions": no clock, no randomness. Network access exists only for custom apps on Enterprise stores. `[doc]`
- **Dataverse:** a hard 2-minute limit per message operation including synchronous plug-ins; a call depth of 8 that loop detection enforces and that cannot be raised (the depth figure comes from secondary sources and a Microsoft knowledge article). `[doc][blog]`
- **ServiceNow:** transaction quota rules cancel long transactions, and admins configure them (maximum duration, SQL time); community reports put the default for business rules near 298 seconds. `[doc][blog]`

**Configurable values sit inside vendor bounds.** Power Automate is the clearest model `[doc]`:
- trigger concurrency is off by default; when on, it runs 1–100 with a default of 25;
- apply-to-each parallelism is 1–50, default 1;
- Until loops default to 60 iterations, maximum 5,000;
- action nesting depth is 8, and a flow holds at most 500 actions;
- a run lasts at most 30 days.

**Failure-based auto-disable is common:**
- Power Automate turns off a flow that fails continuously for 14 days, or that is throttled continuously for 14 days, and emails the owners. It cannot be opted out of. `[doc]`
- Zapier turns off Zaps with a high error ratio by default, but an editor may tick "keep running if errors occur". Its flood protection holds 100+ trigger events that arrive at once, and paid plans may adjust that limit. `[doc]`
- Generic breakers such as Resilience4j expose every threshold as a setting (failure rate, window size, minimum calls, wait in the open state) and close again automatically through a half-open state. Business automation tools instead stay off until a person acts. `[doc][inference]`

### 1.3 Promotion and upgrade safety

- **SAP public cloud: three systems.** Key-user extensions are built in the development system's customizing tenant and put in a software collection (*Export Software Collection*). The collection is imported into test and forwarded to production. Collections are not imported automatically during upgrades. `[blog]`
- **Power Platform:** pipelines deploy to Managed Environments. A stage can require a pre-deployment approval, done through Power Automate approvals, and delegated deployments run as a service account. `[doc][blog]`
- **Salesforce:** UAT in a sandbox, then change sets, DevOps Center or the CLI. Agentforce Testing Center is meant for sandboxes, because tests in production change records and use credits. `[doc]`
- **Workday Extend:** promotion levels, and no uninstall once an app is installed. `[blog]`
- **ServiceNow AI Control Tower:** a steward approval that can block an AI asset's deployment. It is inactive by default, and its approval tasks can include legal, security and data review. `[doc]`
- **Microsoft Copilot Studio:** governed by Power Platform DLP policies, with per-capability admin toggles, code interpreter among them. Microsoft states that code runs in a fresh, quota-limited VM each time. A 2026 third-party disclosure claims a sandbox escape through prompt injection, so isolation claims for AI-run code need an independent check. `[doc][blog]`
- **D365 upgrades:** the sealed models are the guarantee: extensions compile against published extension points. SAP's guarantee is released APIs plus the clean core grade. `[doc]`

### 1.4 Sandboxing code

- **WebAssembly with Wasmtime** gives two CPU caps and a memory cap `[doc]`:
  - fuel (`Config::consume_fuel`) is deterministic, counted per instruction, so the same input always stops at the same point;
  - epoch interruption is a cheaper wall-clock deadline;
  - `StoreLimitsBuilder::memory_size` caps linear memory, which is unlimited by default.

  A module sees only the host functions it is given, so "no I/O" is the default rather than a filter.
- **Firecracker** isolates whole programs `[doc][blog]`:
  - a minimal device model of five or six virtio devices;
  - per-VM token-bucket rate limiters on bytes and operations;
  - a jailer that sets up chroot, namespaces, cgroups and seccomp, and is mandatory in production.

  It suits untrusted programs that need a runtime, not pure functions.
- **Shopify's choice** of Wasm with a deterministic instruction budget, for business logic inside a transaction, is the closest precedent to ERPMe's A10. `[inference]`

## 2. Recommendations

The author's direction is few hard locks and settings that each company applies at implementation. In each item below, a **hard lock** is something that keeps a core guarantee: determinism, no hidden authority, auditability, or termination. Everything else becomes a bounded setting.

### R1. L3 sandboxed extension functions

**When.**
- **Phase 1** ships only the seam: a registry kind `extension_point`, which a module declares at a decision point. The declaration holds a typed input and output schema, a code default, ceilings, and whether the output may feed a gate. No runtime ships in Phase 1, and ADR-0059 rule 24 stands.
- **After Phase 1**, enable a Wasm runtime (Wasmtime) for pure functions only. The decision triggers when at least two real needs fail at L1 and L2 and would otherwise become package code. A microVM is not needed for pure functions; keep Firecracker for level 5 external apps if they are ever hosted.

**Settings.**

| Setting | Scope | Safe default | Bounds | Who changes it |
| --- | --- | --- | --- | --- |
| `extensions.wasm_enabled` | deployment | `false` | boolean | Deployment operator, plus a company change proposal approved by `company_owner` |
| `extensions.<point>.max_fuel` | company × point | 10,000,000 instructions | 100,000 up to the point's registry ceiling (a core constant, at most 50,000,000) | Holder of the `configuration` leaf at `full`, by change proposal |
| `extensions.<point>.max_memory_bytes` | company × point | 8 MiB | 1 MiB up to the ceiling, at most 16 MiB | Same |
| `extensions.<point>.deadline_ms` (epoch) | company × point | 50 ms | 5 ms up to the ceiling, at most 250 ms | Same |
| `extensions.max_module_bytes`, `max_input_bytes`, `max_output_bytes` | deployment | 256 KiB, 128 KiB, 32 KiB | Core ceilings only | Deployment operator |

A company may lower any value at once. Raising a value needs a change proposal with segregation of duties.

**Gates.**
- **Lifecycle.** The module is an L2-style artifact under ADR-0059's lifecycle: draft → backtested → shadow → assisted → active.
- **Pinned by hash.** The module is identified by its content hash (SHA-256 of the Wasm binary plus its reproducible build manifest) and pinned by the decision point's version, as ADR-0058 rule 20 pins decision tables.
- **Tests first.** A person approves the tests before the code exists.
- **Before evidence:** static checks (no imports beyond the host ABI, no WASI) and a reproducible build from reviewed source in the customer repository (spec 16's pipeline).
- **Evidence:** a backtest on a later window, held-out golden cases, and a shadow period.
- **Approval:** a person with a technical role (spec 16, level 4), who is neither the drafter nor the submitter.
- **At run time:** a trap, fuel exhaustion or a timeout returns the point's code default, records `extension_trapped`, and counts toward the breaker of R4.
- **At upgrade:** `RunArtifactUpgradeCheck` re-runs the module's tests against the new ABI version.

**Hard locks.**
- No host imports for I/O, clock, randomness, network or database. Inputs arrive as typed values, and the output is a typed value that core code validates. This keeps the function pure and replayable.
- Fuel metering always on, with no "unlimited" value. Termination is a core guarantee.
- AI-written code never activates without a human review of the source. Rule 24's spirit stays: the running system never loads a module that has no reviewed source and reproducible build.
- An extension output feeds an auto-post or other acting gate only where the registry declared it may, and only after ADR-0051 rule 18's evidence. The output is deterministic, but the gate's trust is earned per point.
- No extension at approval, posting, rights or settings decisions. This keeps ADR-0058 rule 3's list of what never becomes configurable.

### R2. Levels 1 and 3 in Phase 1 as structured rules

**Yes.** Every surveyed ERP ships key-user conditions, approval routing and event-triggered automation at go-live: SAP flexible workflow, Oracle AMX, SuiteFlow, Odoo automation rules, Flow and Power Automate. Implementers expect it. ADR-0058's form (parameters, typed decision tables, event-condition-action rules over a registry vocabulary, no language) is stricter than any of them and so safe to ship. The author-owned text should change as follows:
- **Spec 16:** split level 1 into 1a and 1b, and narrow level 3.
  - **1a, Phase 1:** settings, parameter sets, policy thresholds, approval pools and decision tables.
  - **1b, after Phase 1:** user-defined fields and tables, as spec 10 already says.
  - **Level 3, Phase 1:** "structured rules over a registry vocabulary, no rule language", controlled by stored tests, a replay diff and a change proposal, in place of "simulation on the synthetic dataset" alone.
- **Spec 10:** change "no rule language yet" to "no rule language; structured decision tables and automation rules (ADR-0058)".

**Settings.**

| Setting | Scope | Safe default | Bounds | Who changes it |
| --- | --- | --- | --- | --- |
| `automation.dispatch_paused` (company-wide stop) | company | `false` | boolean | Pausing: anyone holding `configuration` at `full`, at once, audited. Resuming: a change proposal, after a person reviews why it was paused |
| `automation.max_active_rules` | company | 200 | 1–1,000 | Change proposal |
| `automation.replay_window_days` | company | 30 | 7–90 (within the 400-day outbox retention) | Change proposal |
| `automation.replay_min_events` | company | 20 | 0–1,000; at 0, the diff is shown but there is no count gate | Change proposal |

There is no setting that enables the feature: with no rules, nothing runs. A company opts in by activating its first rule.

**Promotion.**
- **Phase 1:** inside one deployment, through evidence plus a change proposal (ADR-0058 rule 24).
- **Optional, low cost and flagged:** export an artifact version as canonical JSON with its content hash, and import it into another deployment of the same customer (staging → production) only as a draft. The draft then runs its own tests, replay and proposal on the target's data. That gives SAP-style software collections without a pipeline engine; the full W11 pipelines stay after Phase 1.

**Hard locks.**
- No scripts, expressions or SQL in artifacts.
- The action vocabulary of ADR-0058 rule 8, and the list of what a rule can never do (rule 3).
- The gate-field allowlist and the taint rules.
- The depth cap of 3.
- Unique and monotone hit policies, and pinned table versions.

The surveyed platforms' documented failures (loops, ordering, drift to "latest", scripts) are exactly what these prevent. The numeric limits (200 rows and 6 inputs per decision table, 5 actions per rule, 100,000 box operations) can remain core constants in Phase 1. Make them settings only when a company hits one, because they bound validation cost, not business behaviour.

### R3. Configurable agent triggers

**Which.** Make the two candidates configurable in the next versions of their agent types:
- the quotation agent's `inbound_message_matched`;
- the purchase invoice agent's `supplier_invoice_received`.

Defer the bank statement agent's per-account wake-up until bank matching has auto-post evidence. Keep the data migration agent person-started. The pattern matches the market: Salesforce starts agent actions from record-triggered flows, Copilot Studio gives autonomous agents event triggers with conditions, and the agent's capabilities stay a versioned artifact while the start condition is configuration.

**How.** ADR-0058 rule 7 reads "configurable means configured": without a rule, the item stays with people. That would silently stop the agent for every company that upgrades. Use an explicit mode instead.

| Setting | Scope | Safe default | Values | Who changes it |
| --- | --- | --- | --- | --- |
| `agents.<agent_type>.wake_up_mode.<kind>` | company × agent setting | `always` (today's behaviour) | `always`, `by_rule`, `off` | The agent setting's `workflow_owner`, by change proposal with segregation of duties |

- With `by_rule`, `agent_wake_up` skips the kind, and only automation rules with `start_agent` and their own conditions start the agent.
- The activation proposal for `by_rule` must name at least one active rule, or acknowledge that items go to people.
- `off` sends every item to people.

**Condition fields.** Only deterministic metadata can steer a start:
- the receiving mailbox or channel;
- the sender's partner, matched by address and not by an LLM;
- whether the partner is known;
- branch, document source and attachment type.

Never the message body, and never an amount the LLM extracted: these are `is_untrusted` or LLM-fed, and ADR-0058 rule 4 already excludes them.

**Audit and promotion.**
- Each mode change is a change-tracked setting, recorded with the agent type version.
- Making a kind configurable is a new agent type version under ADR-0050's ladder.
- Each `start_agent` rule passes ADR-0058's evidence (the replay shows which past messages would have started the agent).

**Hard locks.**
- No agent wakes an agent: an event with an origin agent run never satisfies `start_agent`.
- A trigger cannot start an agent type on outside content unless that type accepts the subject table.
- Rules may only narrow when an agent starts. They never widen its tools, subject tables or rights.
- No agent trigger on approval, posting or send events.

### R4. Automation circuit breaker

**Keep the defaults and make all three values settings.** The defaults are 5 refusals or failures in 60 minutes, or 20 in a row. Market practice is fixed per-execution quotas plus auto-disable on sustained failure, which only Zapier lets a user switch off. ERPMe's breaker disables a rule that can create drafts and work items, so staying off until a person re-enables it is right. A half-open auto-retry suits network calls, not business side effects.

| Setting | Scope | Safe default | Bounds | Who changes it |
| --- | --- | --- | --- | --- |
| `automation.breaker_failures` | company; optional per-rule override in the rule version | 5 | 1–50 | Tightening: `configuration` at `full`, at once. Loosening: change proposal |
| `automation.breaker_window_minutes` | company; per-rule override | 60 | 5–1,440 | Same |
| `automation.breaker_consecutive` | company; per-rule override | 20 | 3–200, and never below `breaker_failures` | Same |
| `automation.max_executions_per_rule_per_hour` (flood guard, new) | company; per-rule override | 500 | 10–10,000 | Same |

- **Per-rule overrides** live in the rule version's content, so they go through its hash, replay and proposal. A high-volume rule can tolerate more failures, and a sensitive one can tolerate fewer.
- **The flood guard** follows Power Automate throttling and Zapier flood protection. When it trips, the consumer records `rate_limited`, which does not count as a failure, and holds further executions of that rule until the next hour. It raises one work item per rule per day. This answers a burst no failure count catches, such as a mass import firing a rule thousands of times.
- **Audit.** Every change to a breaker setting is change-tracked with the old and new value. Each trip records the counted executions in the `automation_rule_disabled` item.

**Hard locks.**
- The breaker cannot be turned off: no value means "never", and the bounds exclude it.
- What counts stays fixed: refused, failed and partial count; skips by design, `skipped_same_target`, `depth_exceeded` and `rate_limited` do not.
- Re-enabling is always a person's `EnableAutomationRule` on the same version, after the graph check. There is no automatic half-open state.
- The trip runs under the consumer's permission, not the owner's.
- The depth cap of 3 stays a core constant. Dataverse holds its depth limit fixed for the same reason.

## Sources

- SAP clean core levels: https://news.sap.com/2025/08/extend-sap-s4hana-cloud-right-way-clean-clear/ ; https://www.asug.com/insights/sap-updates-clean-core-guidance-to-help-customers-clarify-extensibility-criteria ; https://www.sap.com/uk/documents/2024/09/20aece06-d87e-0010-bca6-c68f7e60039b.html
- SAP key-user custom logic: https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition/using-key-user-in-app-extensibility-to-create-custom-business-logic ; https://community.sap.com/t5/enterprise-resource-planning-blogs-by-sap/key-user-extensibility-on-sap-s-4hana-cloud-adding-custom-business-logic/bc-p/13340956
- SAP flexible workflow: https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-sourcing-and-procurement/defining-workflows-in-sourcing-and-procurement_a17030df-33b7-4c0e-a8c6-31ec490618e9 ; https://blogs.sap.com/2019/12/03/sap-s-4hana-cloud-flexible-workflow-with-new-custom-pre-condition-for-purchase-requisition/
- SAP 3-system landscape: https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-sap/leverage-the-flexibility-of-sap-s-4hana-cloud-public-edition-on-a-3-system/ba-p/13549322 ; https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition/transporting-key-user-in-app-extensions_e359072e-46d4-4571-9395-35b42f7b845e
- Dynamics 365 extensibility and sealing: https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/extensibility/extensibility-home-page ; https://learn.microsoft.com/en-sg/dynamics365/fin-ops-core/dev-itpro/extensibility/changes-80 ; https://learn.microsoft.com/en-sg/dynamics365/fin-ops-core/dev-itpro/extensibility/app-sealing-faq
- Dataverse limits: https://learn.microsoft.com/en-us/power-apps/maker/data-platform/low-code-plug-ins-tips ; https://community.dynamics.com/article/KA-25677
- Power Automate limits: https://learn.microsoft.com/en-us/power-automate/limits-and-config
- Power Platform pipelines: https://learn.microsoft.com/mt-mt/power-platform/alm/pipelines ; https://learn.microsoft.com/en-us/training/modules/extend-pipeline/exercise-add-approval-stage-pipeline ; https://www.matthewdevaney.com/the-complete-power-platform-pipelines-alm-setup-guide/configure-pre-deployment-stage-approvals/
- Oracle approval rules and Groovy: https://docs.oracle.com/en/cloud/saas/financials/25a/faiex/how-you-define-approval-rules.html ; https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25b/faipr/configure-approval-rules.html ; https://docs.oracle.com/en/cloud/saas/applications-common/25a/oacex/overview-of-groovy-scripts.html ; https://docs.oracle.com/cd/E36909_01/fusionapps.1111/e20388/F1071033AN1931B.htm
- NetSuite: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N3351480.html ; https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_N3350651.html ; https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4071954788.html ; https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4077993199.html
- Odoo: https://www.odoo.com/documentation/18.0/applications/studio/automated_actions.html ; https://mergebot.odoo.com/odoo/upgrade-util/pull/75 ; https://www.odoo.com/forum/help-1/how-to-use-import-module-in-automated-action-in-odoosh-110-136386
- Salesforce Apex limits: https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexref/apex_gov_limits.htm
- Agentforce Testing Center: https://www.salesforce.com/au/news/press-releases/2024/11/20/agentforce-testing-center-announcement/ ; https://gearset.com/solutions/agentforce/
- Shopify Functions: https://shopify.dev/docs/api/functions ; https://shopify.dev/changelog/shopify-functions-input-size-limit-increased-to-128kb ; https://shopify.dev/docs/apps/build/functions/optimize-instruction-counts
- Workday Extend: https://confluence.admin.virginia.edu/download/attachments/113858408/Workday%20Extend%20App%20Lifecycle.pdf?api=v2 ; https://doc.workday.com/admin-guide/en-us/workday-ai/agents/workday-built-agents/deployment-agent-in-implementation-environments/concept--deployment-agent-in-implementation-enviro.html
- ServiceNow: https://www.servicenow.com/docs/r/platform-administration/platform-performance/c_TransactionQuotas.html ; https://www.servicenow.com/docs/r/platform-administration/platform-performance/c_DefaultQuotaRules.html ; https://www.servicenow.com/docs/r/intelligent-experiences/sn-ai-impl-governance.html ; https://www.servicenow.com/docs/r/intelligent-experiences/ai-control-tower/explore-approvals.html
- Copilot Studio: https://learn.microsoft.com/en-us/microsoft-copilot-studio/admin-data-loss-prevention ; https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/code-interpreter-security ; https://www.beyondtrust.com/blog/entry/copilot-studio-sandbox-escape
- Zapier: https://help.zapier.com/hc/en-us/articles/8496216132621-Zap-is-not-running ; https://community.zapier.com/how-do-i-3/removing-flood-protection-from-a-specific-zap-96
- Resilience4j circuit breaker: https://resilience4j.readme.io/docs/circuitbreaker
- Wasmtime: https://docs.wasmtime.dev/api/wasmtime/trait.ResourceLimiter.html ; https://docs.wasmtime.dev/api/src/wasmtime/runtime/limits.rs.html
- Firecracker: https://github.com/firecracker-microvm/firecracker/blob/main/docs/design.md ; https://lwn.net/Articles/775736/ ; https://fly.io/learn/firecracker-vm/
