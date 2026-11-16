# Capability check: six capabilities against the NativeFlows design

Repo `~/Projects/NativeFlows`, branch `holistic-review`, HEAD `32e7b1c`, read on 2026-11-15. Read-only check of `docs/` plus the unapplied draft `NativeFlows-lab/drafts/ds-uom/0056-multiple-units-of-measure.md`.

Citations are `file:line` under `docs/` where the line was read with numbers, otherwise `file rule N`. Quotes are short and exact. "Not found" means a grep over `adr/`, `spec/`, `design/`, `catalogs/` and `open-questions.md` returned nothing; it is not proof of absence in `research/`, `reviews/` or `runbook/`, which were not searched.

Verdicts in short: 1 partly, 2 partly, 3 partly (mostly not), 4 partly, 5 partly, 6 covered with gaps.

---

## 1. Configurable workflows

**Verdict: partly covered.** Approval routing and thresholds are company data in Phase 1. Everything else that makes up a "workflow" (document lifecycles, agent workflow steps, triggers, work item kinds) is code or registry data, fixed per release. Spec 16 describes the customization model, but no ADR designs it.

**What exists**

- Policy as data. `adr/0043` Decision: "Policy is a deterministic threshold table per company". Rules match action, document type, actor kind and ordered conditions (amount, discount, margin, below cost, outside list, credit exceeded). Rules are versioned with `effective_from` (rule 3) and a rule set must be monotonic (rule 11).
- Approval pools and stages as data. `adr/0055` Decision: "An `approval_pool` per company groups document types"; "Each pool has ordered stages. A stage has members (users and roles), a number of approvals required ... ('k of n'), a minimum rank, and optional escalation and due days."
- Agent types are code. `adr/0050:95`: "Agent types are code, versioned as one artifact". `adr/0050:97`: "Nobody edits them." `adr/0050:39`: "No agent framework ... Workflows are plain code".
- What a company may set per agent type. `adr/0050:108`: `agent_type_setting` holds `mode` (`off`, `shadow`, `assisted`), `workflow_owner_id` and "lowered budget values". Nothing else.
- Triggers are declared in code. `adr/0050:96`: an agent type declares "the work item kinds it may claim". `adr/0050:130`: the wake-up consumer reacts to `WorkItemRaised` "for kinds an agent type declares".
- Document lifecycles are fixed. `adr/0009:16`: each type "is registered once" and "The registry generates its commands from the verb list". States are the fixed list of `adr/0009:27` and `:44`.
- Work item kinds are a registry catalog. `adr/0042:16`: "Kinds are a registry catalog". `adr/0042:28`: "the generator writes it from the registry". 44 kinds in `catalogs/work-item-kinds.csv`; owner and due rules are per kind in code, not per company.
- Spec 16 names the target model. `spec/16-customization.md:23`: level 1 "User-defined fields, policy thresholds, approval procedures | Declared as metadata". `:25`: level 3 "'When X then Y', alerts, bank matching rules | Declarative rule language, not code". `:26`: level 4 plugins with "before/after-command hooks".

**What is missing**

- No ADR for spec 16. `open-questions.md:123`: "Policy-engine rule language and customer self-configuration (after Phase 1; Phase 1 uses a threshold table)."
- No "when X then Y" automation, no company-defined alerts or work item kinds, no company-defined document states or extra steps, no company control over which agent runs on which trigger beyond `off`/`shadow`/`assisted`.
- No company-configurable agent workflow steps. A changed step, constant or prompt is a new agent type version in the core repo.
- No extension point design: `adr/0022` only has internal module hooks wired by `app`; the plugin SDK is a "revisit when" (`adr/0022:342`).

**Phase**

- Design: threshold table plus multi-stage pools in Phase 1; rule language, user-defined fields, plugins and the customer pipeline after Phase 1.
- Spec: `spec/10-roadmap.md:44`: "Policy engine: a threshold table per action type, no rule language yet. One-level approval." `spec/10-roadmap.md:53` lists "user-defined fields and tables, plugin SDK, per-customer AI customization pipeline ... multi-level approval" after Phase 1. `spec/16-customization.md:3`: "This file describes work after Phase 1."
- Match: yes, except one drift. ADR-0055 puts multi-stage approval in Phase 1 at the author's request (2026-11-15), while spec 07 (`:48`–`:49`) and spec 10 (`:44`, `:53`) still say multi-level approval and escalation come after Phase 1. Author-owned text to update.

**Constraints**

- `spec/03-agent-safety.md:5`: rule 1, rule 5 and the "Human only" rows "are hard floors. No policy, threshold or customer setting can relax them."
- `spec/03-agent-safety.md:8`: "each agent type has a fixed tool list, never inferred from the prompt". A configurable workflow may not let a company add tools to an agent.
- `spec/16-customization.md:5`: "every customization is additive and never modifies core source code."
- `adr/0050:131`: "No agent wakes an agent." Any trigger configuration must keep this registry check.
- ADR-0043 rule 11 (monotonic rule sets) must hold for any richer rule language.

**Direction.** Keep three layers and say so in one short ADR that implements spec 16 levels 1 and 3 on top of what exists: (a) policy rules, pools and stages stay the only approval configuration; (b) add a small declarative "automation rule" as company data, proposal-bound, of the form event or work item kind plus conditions over registered fields gives one of a closed action list (raise a work item of a company kind, assign an owner, start an already-registered agent type in its own scope, notify); (c) agent workflow steps and document lifecycles stay code, changed only by a new version through the evaluation gate. The grammar should follow ADR-0046's (no code, order-independent), be simulated on the synthetic dataset before it is enabled, and never be able to post, send, approve or widen a tool list. Decide whether a thin form of (b) is Phase 1; the threshold table and pools already cover the approval part.

---

## 2. AI fine-tuning existing deterministic functions, or building new ones

**Verdict: partly covered.** The design has a strong pattern for AI proposing *data* that makes the next case deterministic (mappings, matching rules, parameters, report definitions), with evidence and human approval. It has no mechanism for AI tuning the constants of core deterministic functions, and AI-authored rules or code exist only as the after-Phase-1 pipeline of spec 16, with no ADR.

**What exists**

- Stored resolutions. `adr/0051:15`: "A resolution the LLM contributes is proposed as a stored mapping or rule, so the next case is deterministic." `adr/0051:33`: "The deterministic share ... is recorded per run and must rise over time".
- Bank matching rule proposals. `adr/0048:137`: "`bank_matching_rule` (company data, proposal-bound) maps a description token or a counterparty account to a partner or an account." `adr/0051:161`: a `cash` consumer "creates a `bank_matching_rule` change proposal as a draft" when the token appears in at least two of that partner's lines in 90 days and in no other partner's; the version is tainted and a person submits and approves it.
- Item mappings. `adr/0051:186`: "One change proposal with a `CreatePartnerItem` item for each line L1 resolved".
- Planning parameters tuned from evidence. `adr/0051:206`: "a lead time that differs ... by more than 20%: a parameter change with that evidence", computed by code, proposed by the agent.
- Agent constants are versioned and re-qualified. `adr/0051:29`: "The constants belong to the agent type version; changing them is a new version with an evaluation". `adr/0051:39`: a changed version, constants or model "runs as `shadow` by the computed effective mode". Frozen promotion evidence: `adr/0050:112`.
- Auto-post rule with shadow evidence. `adr/0051:157`: `EnablePolicyRule` is rejected "unless it covers at least 300 proposals over at least two statement months, with at least 99% posted unchanged".
- Report definitions as data. `adr/0049:120`: "A company may add its own statements and books as company data". `adr/0049:124`: "agents reach them only through change proposals".
- Other rule data that agents can propose: promotions (`adr/0047:199`, "proposal-bound"), putaway rules and count plans (`adr/0023:251`), configuration rules in "a small declarative grammar with no code" (`adr/0046:23`).
- Change proposal carrier. `adr/0029` rule 2: allowed targets are `master_data_change` commands and commands registered `is_proposal_bound`.
- Harness. `adr/0050` rule 38 (replay, "The determinism contract"), rule 39 (golden sets from the synthetic dataset), rule 40 (evaluation run on every template, schema, version or seatmap change).
- AI-authored rules and code, after Phase 1. `spec/16-customization.md:34`: "The builder agent ... creates a branch, writes the change and its tests. It runs in a sandbox with no production credentials." `:35`: CI "blocks any change outside `extensions/`, `skills/` and `tests/`" and runs "a review agent independent of the builder". `:37`: "Plugins (level 4) also need approval from someone with a technical role." Seats exist: `spec/17:44` Builder, `spec/17:45` Reviewer.

**What is missing**

- No tuning path for core deterministic constants. The bank cascade's scores (95, 100, 90, 80, 70, 60), the 5-day window and the subset size of 6 are fixed in `adr/0048:129`–`:135`; the fuzzy acceptance 92 and lead 8 are in `adr/0051:29`. None is a versioned parameter set that can be evaluated in shadow and promoted per company. The only tunable is the auto-post rule's score floor and amount maximum.
- No declarative rule language (spec 16 level 3) and no design for validations or pricing rules as company data beyond promotions and price lists.
- No ADR for the builder pipeline, the customer repo, `extensions/`, the plugin API or contract tests.
- No artifact for "a deterministic function proposed by AI": nothing between a data row (rule, mapping) and a core code change by commit.
- No generic "candidate rule back-test": only the bank auto-post rule has an evidence hook (`adr/0043:166`). A proposed matching rule is approved by a person without a replay over past lines.

**Phase**

- Design: rule and mapping proposals, versioned constants and the harness are Phase 1. Builder pipeline, rule language and plugins after Phase 1.
- Spec: `spec/14-agent-workflows.md:21` gives the LLM "propose new matching rules" in Phase 1. `spec/10-roadmap.md:11` puts "AI customization pipeline per customer" in Phase 3; `spec/10-roadmap.md:53` after Phase 1. Match: yes.

**Constraints**

- `spec/03-agent-safety.md:15`: "No hidden memory: anything an agent 'learns' ... must be deterministically computed data stored in the system, viewable and editable." So no fine-tuned model weights or opaque learned scorers as the store of what was learned; `adr/0051:285`: "NativeFlows stores what was learned as visible rules and mappings instead of a hidden model".
- Principle 13 and `adr/0051:30`: the LLM never computes "a price, discount, tax, quantity to post, account, match or score". AI may author a rule; the rule, not the model, computes.
- `spec/03-agent-safety.md:7`: "a match an LLM contributed to is never auto-posted". A rule derived from untrusted text is tainted until a human approves it (`adr/0051:161`); after approval the master data is trusted (ADR-0029 rule 10, "the human approval is the trust boundary").
- `spec/14-agent-workflows.md:39`: "An agent gains permissions only with evidence, never by impression."
- Spec 16: additive only, sandboxed builder, independent reviewer, approval engine promotes.
- Hard floors cannot be tuned (`spec/03:5`).

**Direction.** Generalize what bank matching already does into one "tunable deterministic parameter set" pattern: each deterministic function that has constants (cascade scores and windows, fuzzy thresholds, duplicate bands, forecast parameters) declares them as a versioned, company-scoped parameter set with core defaults; an untainted analysis run may propose a new version as a change proposal whose evidence is a deterministic back-test (the pure function replayed over the company's own resolved history, old against new, in the style of `GetAutoPostShadowEvaluation`); promotion needs the evidence threshold and a second person, and a change of parameters drops any dependent auto-post rule back to needing fresh evidence. For new rules, extend the evidence hook of ADR-0043 rule 14 to every proposal-bound rule table so a proposed rule always arrives with its replay result. New deterministic code stays spec 16 level 4: write the missing ADR for the builder pipeline, and state there that the golden sets and replay harness of ADR-0050 are the test bed customizations must pass.

---

## 3. Multimodal input

**Verdict: partly covered, and mostly not for images.** E-mail intake, attachment storage with taint, and the structured e-invoice XML path are designed. No workflow lets a model read an image or a PDF, no path turns an image into structured data, and none of the four named inputs (business card, PDF invoice, attachment of an inquiry, delivery note photo) is covered end to end.

**What exists**

- Capability flag only. `spec/17:9`: a seat declares "image and PDF reading". `adr/0050:53`: adapters publish "image and PDF input" flags. The only seat that requires it is Builder (`spec/17:44`), for customization, not for business input.
- Attachments. ADR-0038 rule 13 allowed types: "PDF; PNG, JPEG and WebP (not SVG); XML; CSV; XLSX ... and e-mail messages". Scan state machine, rule 14: bytes "not `clean` are never served, to people or agents". `adr/0038:137`: "Attachments from outside content are untrusted".
- Taint on attachment content. `adr/0050:163`: `taint_source_kind` includes `outside_attachment`. `adr/0050:211`: a run is tainted before it gets "the content of an attachment whose source kind is outside content".
- E-mail intake. `adr/0052:122`: "Intake is deterministic code ... It calls no LLM and never classifies content." `adr/0052:125`: "`CreateAttachment` for the raw message and for each part of an allowed type". `adr/0052:94`: attachments "from inbound e-mail are untrusted". Connector: IMAP in Phase 1 (`adr/0052:110`).
- Customer inquiries by e-mail. Onboarding inputs are "sender address and display name, subject, body text" (`adr/0051:93`). Quotation runs on `inbound_message_matched` (`adr/0051:111`, `:114`) and read `interaction_overview`. Both read the body only; attachments are not an input of any step.
- Supplier invoices. `adr/0051:169`: "The agent never parses a raw attachment itself." The reader is "network-free and deterministic, it parses one XML file" (`adr/0051:176`). `ImportEInvoiceRecord` "takes an attached XML file", is run "by a person, or by the add-on's intake job as `system`; on no agent tool list" (`adr/0051:177`). Structured fields are trusted, free text is untrusted (`adr/0051:171`, `:175`).
- Named but not designed: `adr/0051:324` revisit when "vision models are wanted for scanned invoices"; `adr/0034:189`: "The capture agent drafts confirmations from messages, photos or voice"; `adr/0033:184`: "Agents draft bills of materials and routings from spreadsheets or drawings"; `spec/16:29`: the customer provides an old template as "PDF, Excel, photo".

**What is missing**

- Business card photo to contact: nothing. No upload-and-extract flow, no agent type, no seat.
- Mailbox to supplier invoice: spec 14 line 5 names "the receiving mailbox" as a source, but no step routes an XML part of an inbound e-mail to `ImportEInvoiceRecord`; the incoming intake belongs to the DS-24 add-on (`design/backlog.md:77`, `open-questions.md:44`). Until then a person imports the XML by hand. PDF-only invoices (foreign suppliers, scans) have no path at all.
- Inquiry attachments (a PDF request, a spreadsheet of lines, a drawing): stored and linked, never read by a workflow.
- Delivery note photos, voice: not designed. Voice appears only as a deferred phrase in ADR-0034; `spec/13-crm.md:32` puts call recording and transcription after the MVP.
- No gateway design for binary inputs. `adr/0050:73`: workflow code passes context items as "(field path, row reference, value)" and "Code never passes a free string"; the routing switch strips labelled *values* (`adr/0050:79`). An image cannot be stripped field by field, so the label and routing rules for a whole attachment are undefined.
- No "extraction record": no table holding fields extracted from a document with page or region evidence (the image equivalent of `source_span`, `adr/0051:98`).
- No seat for vision with personal data. The two extraction seats require only "Structured output" (`spec/17:36`–`:37`).

**Phase**

- Design: e-mail intake and XML are Phase 1; every image or PDF reading case is deferred or absent.
- Spec: `spec/09-mvp-scope.md:7` and `spec/10-roadmap.md:7` put "email intake" and the purchase invoice and quotation agents in Phase 1; `spec/14:7`: "email first, chat channels after Phase 1". No spec asks for image or voice input in Phase 1. Match: yes for what is designed. One drift: spec 09/10 still place e-invoice intake in Phase 1 while the author moved it to an add-on (`open-questions.md:30`).

**Constraints**

- `spec/03-agent-safety.md:7`: a run that read untrusted content "must not send anything out, change master data or post". Every photo, PDF or voice note from outside is untrusted, so such a run only drafts, in the scope of one partner (or its subject when there is none).
- A photo taken by an employee is still outside content when it pictures a third party's document (a supplier's delivery note, a business card). Only a person's own note is trusted (`adr/0051:113`).
- Extracted numbers: copied as stated and checked against their source (`adr/0051:30`), never computed by the model.
- Data classes (`spec/17:23`): contacts are `personal` by default, so a business card is personal. Phase 1 with the routing switch on: personal values are removed and the run ends `routing_blocked` (`adr/0050:79`); "Sensitive personal values are never sent to any model in Phase 1" (`adr/0050:80`). Every personal value sent is logged (`adr/0050:84`–`:87`).
- Attachment must be scan state `clean` before any parsing (ADR-0038 rule 14).
- Agents never run `ImportEInvoiceRecord` or master data commands directly; contacts and partners go through change proposals (`adr/0051:100`).

**Direction.** Add one generic seam instead of four features: a deterministic `document_extraction` record owned by `attachments` or `crm` (attachment, kind, extracted fields with page and region evidence, all free text `is_untrusted`, data label inherited from the attachment as a whole), filled first by deterministic readers (XML, text-layer PDF, XLSX) and only then by a vision step on a new seat "extraction with image and PDF reading", whose data class is `personal` so a whole-attachment label can be enforced by the gateway (send or block, no partial strip). Existing workflows then start from that record exactly as `purchase_invoice` starts from `e_invoice_record`: business card to a `CreateContact` change proposal (reuse `customer_onboarding`'s L2 and D2), inquiry attachment to extra quotation lines, PDF invoice to a draft purchase invoice with unverified-signature handling, delivery note photo to a draft goods receipt. Separately, close the mailbox-to-e-invoice route in the core: a `system` consumer that hands XML parts of authenticated inbound mail to `ImportEInvoiceRecord`. Voice stays after the MVP with call recording.

---

## 4. Agent-assisted master data creation

**Verdict: partly covered.** The commands, checks and the proposal carrier are all there, and partners and item mappings have workflows. No designed agent drafts a product, item, BOM or routing from a description, drawing or spreadsheet, or runs its cost estimate; that is named and deferred to DS-57.

**What exists**

- Partners and contacts. `adr/0051:8`: `customer_onboarding` "proposes a new customer and its contacts from an inbound e-mail of an unknown sender".
- Mappings. `adr/0051:186` (`CreatePartnerItem` proposals); migration column and account mapping (`adr/0051:230`, `:233`).
- Migration loads master data. `adr/0044:51`: phase 2 is "partners ..., products and items, warehouses and bins, price lists". `spec/14:6`: "map master data from the Excel template".
- Planning parameters. `adr/0051:208`: parameter or lead-time updates as change proposals.
- BOM and routing commands are built for agents. `adr/0033:25`: "Agents read the structures through deterministic queries. They draft revisions freely, and a release ... reaches the books only through a change proposal". `adr/0033:36`: draft commands "are `other` ... so agents run them directly". `adr/0033:38`: `ReleaseBillOfMaterialsRevision`, `ReleaseRoutingRevision` are effective commands. `adr/0033:181`: `GetBillOfMaterialsRevisionCheck` "An agent attaches the result to its change proposal as evidence."
- The intended workflow, in one sentence. `adr/0033:184`: "Agents draft bills of materials and routings from spreadsheets or drawings, then propose the release ... DS-34 designs the master-data workflow." Then `adr/0033:186`: "The master-data workflow is a later agent".
- Cost estimates. `adr/0035:151`: "`CreateCostEstimate` computes it on the server. `ReleaseCostEstimate` freezes it ... Both are effect class `other`". `adr/0046:172`: `GetConfigurationEstimate` is a pure function for a configuration before the item exists.
- Placeholder. `adr/0051:256`: DS-57 includes "the master-data workflow that drafts bills of materials and routings and proposes their release". `design/backlog.md:69`: DS-57 status "ADR", not written.

**What is missing**

- No agent type, steps, inputs, output schemas, comparator or golden set for product, item, BOM or routing drafting. No row for it in the thresholds or budgets tables of ADR-0051.
- No workflow for creating products and items outside migration (a new product from a supplier catalogue, a description or a customer drawing), and no supplier onboarding counterpart of `customer_onboarding`.
- Migration phases do not list BOMs, routings, work centers or production versions (`adr/0044:49`–`:56`), although production is Phase 1. A manufacturer's largest master data set has no import path.
- No step that chains draft BOM, draft routing, `GetBillOfMaterialsRevisionCheck`, `CreateCostEstimate` and a comparison with the old cost into one evidence pack.
- Drawings need the vision seam of capability 3.

**Phase**

- Design: production, BOM, routing and costing are Phase 1 (ADR-0032); the master-data agent is DS-57, "designed before the production core step" (`adr/0032:54`).
- Spec: `spec/09-mvp-scope.md:12` still says "Assembly (Phase 2)" with routing "Later"; `spec/10-roadmap.md:9` has Phase 2 assembly; `spec/14:10` does not list a master-data agent at all. Mismatch, already flagged for the author in `open-questions.md:122`.

**Constraints**

- A run that reads a customer's or supplier's file or drawing is tainted: it "must not ... change master data" (`spec/03:7`). It may only draft and propose; `spec/14:34`: "Change master data (partner, item, price) | Requires approval". Proposals always need approval (ADR-0043 rule 9, floor 7), and the human the run acted for cannot approve (`spec/03:11`).
- Tainted read scope: such a run cannot read the item catalog to find existing components (`adr/0051:82`), which makes BOM drafting from outside files nearly useless until the author answers the read-scope question (`open-questions.md:43`). A person's own spreadsheet imported as a batch is scope `import_batch`.
- Quantities and codes are copied as stated; cost is computed only by `CreateCostEstimate`, never by the model (Principle 13). `cost` and `margin` are field classes the agent type must declare (`adr/0050:101`).

**Direction.** Write DS-57's master-data part as a seventh workflow, `product_engineering`, with two entry points: a batch (`import_batch` scope, reusing the data migration column mapper, and adding BOM, routing, work center and production version templates to ADR-0044's phase 2) and a person's own note or file (untainted, full catalog). Steps: resolve each component against existing items by code, barcode, supplier code and `rank_candidates`; the LLM chooses among candidates or marks "new item needed"; code drafts `CreateProduct` and `CreateItem` proposals for the new ones and draft BOM and routing revisions; code runs `GetBillOfMaterialsRevisionCheck` and `CreateCostEstimate` on the drafts; the release proposal carries the check, the estimate and the difference to the previous estimate as evidence. The model never supplies a factor, price or time that is not in its source span.

---

## 5. Agent-assisted reporting and analysis

**Verdict: partly covered.** The read side is designed and safe (semantic views, MCP resources, statutory report engine with drill-down, seats for Q&A and analysis). There is no analysis agent, no way for the query layer to aggregate on request, and no dashboards or saved management reports.

**What exists**

- Query layer. `adr/0050:23`: "Agents and reports read through semantic views in schema `query`, served by the read-only role `nativeflows_readonly` with short timeouts, pagination and row limits." Rule 44: "No client sends SQL, and agents never write SQL". Rule 46: MCP resources `nativeflows://query/views`. Rule 51: 17 initial views.
- Management reporting. Rule 53: `system_account_turnover` "so figures agree with the books"; "Management reports are views and exports, never documents."
- Statutory engine. `adr/0049:11`: "Every figure is an exact sum of journal lines ... Every figure can be drilled down to the journal lines behind it." Company-defined statements and books: `adr/0049:120`. The reporting queries (`GetStatutoryReport`, `ListBookRow`, `ListReportLineContribution`) may be on agent tool lists (ADR-0050 rule 52 note).
- List export. Rule 54: `CreateListExport` writes `.xlsx` as the requester; "Agents never export".
- Seats. `spec/17:42`: "Data Q&A | Answer questions through the read-only query layer". `spec/17:43`: "Analysis | Period-close assistant, explaining differences, anomaly reports".
- Number safety for text. `adr/0050:279`: "every number in it must equal a number of the step's input or of the draft". Used by planning's `explain` (`adr/0051:207`).
- Named later agents. `adr/0051:255`: period-close assistant "explains differences and flags anomalies ...; untainted, read-only plus notes". `adr/0035:160`: "The variance agent (DS-34) ranks orders by variance". `spec/13-crm.md:21`: "Weekly pipeline summary".

**What is missing**

- No agent type for data Q&A or analysis: the seat exists without a workflow, tool list, golden set or budget.
- No aggregation in the query builder. Rule 47 offers equality, `in`, ranges, `contains`, sort and paging, with at most 200 rows per page for agents. Apart from `system_account_turnover` and `forecast_accuracy` there are no aggregate views. A question such as "sales by item group by month" would force the model to add rows itself, which Principle 13 forbids.
- No dashboards, KPI definitions, saved queries or scheduled management reports. "Dashboard" in the design means only the operations dashboard (`adr/0038:122`).
- No ad hoc report definition over views (company report definitions cover journal-based statements and books only).
- `open-questions.md:127` still lists "management reporting and BI" among unanswered partner questions.

**Phase**

- Design: query layer, statutory reports and list export in Phase 1; analysis agents later.
- Spec: `spec/09-mvp-scope.md:16` has the "read-only query layer" in the MVP; `spec/14:10` lists the period-close assistant under "Next"; `spec/15-migration-ux-docs.md:16`: "Excel export on every list". No spec promises an analysis agent or dashboards in Phase 1. Match: yes.

**Constraints**

- Principle 13: the LLM "never computes numbers". Every figure in an answer must be returned by a registered query and pass the number check of `adr/0050:279`.
- `spec/03-agent-safety.md:10`: "The query layer and MCP apply the same filters" (field classes, record scope, owner scope). The agent's rights are the intersection with the asking person's.
- Keep the run untainted: views "omit `is_untrusted` columns unless asked" (ADR-0029 rule 10). An analysis agent should declare `may_read_untrusted: false` like planning (`adr/0051:198`), otherwise its scope collapses to one partner.
- Audit data "is never on an agent's tool list" (`adr/0050:23`). Agents do not export files (rule 54).
- Data class: the Data Q&A seat is "Per routing"; the Analysis seat is "Non-personal" (`spec/17:42`–`:43`), so personal columns are stripped for analysis.
- Budgets and the 10-second statement timeout for agent runs (rule 43).

**Direction.** Add a small deterministic "measure" layer to `query`: declared aggregate queries (measure, allowed dimensions from the canonical dimension list, period grain, filters) that the builder turns into one `SELECT ... GROUP BY`, with the same scope and field-class rules and a drill-down query to the rows behind each cell, as ADR-0049 does for report lines. On top of it define one untainted agent type, `analysis`, on the Data Q&A and Analysis seats: the model picks a declared measure, dimensions and filters, code runs it, and the answer text passes the existing number check and carries links to the query and its drill-down. Saved questions become company data ("report view": measure, dimensions, filters, layout), which also gives dashboards and scheduled summaries without a second mechanism. The period-close assistant and the variance agent become workflows on the same layer.

---

## 6. Barcode capability

**Verdict: covered for Phase 1 warehouse operation, with gaps in standards, labels and detail.** The data model, scanning as commands, label printing for bins and handling units, and the PWA are all designed and placed in Phase 1. GS1 parsing, lot, serial and item labels, a scan resolver and the PWA's UX spec are missing.

**What exists**

- Item barcodes. `adr/0018:36`: "`item_barcode` (`item_id`, `uom_id`, `barcode`, unique per company) gives each packaging unit its own barcode; scanning a carton barcode enters one carton, converted to the inventory unit." DDL: `design/DS-20-master-data.sql:514`–`:522`, primary key (`company_id`, `barcode`).
- Bins. `adr/0023:73`: bin `barcode` "Unique in the company, so a scan resolves without the warehouse; default: the code".
- Handling units. `adr/0023:106`: "A `handling_unit` holds `code` and `barcode` (unique in the company)". `adr/0023:109`: "Scanning a unit moves all its content in one task."
- Scans are commands. `adr/0023:22`: "Every scan is an ordinary command with an idempotency key." `adr/0023:214`: "`ConfirmWarehouseTask` records the scanned source and target bins, the handling units, lot or serials". Serials: `adr/0023:200`, `:234`. `adr/0023:235`: "a scan never posts a count difference".
- Printing. `adr/0023:254`: "Printing (DS-27) covers bin labels, handling-unit labels, putaway and pick lists on paper, and confirmation from a desktop screen, so warehouses without phones work from step 5." `adr/0049:252`: print subjects include "warehouse labels and lists". `adr/0049:302`: step 5.
- Scanner technology. `adr/0002:46`: "Same app as a PWA; scanning with the browser BarcodeDetector API, fallback @zxing/browser". Device floor: Chrome on Android 10 (`adr/0040:203`). `design/backlog.md:43`: DS-31 "Warehouse PWA: receipt, issue, transfer and count flows; barcode per packaging unit", step 9.
- Units. Draft `0056:151`: the proposed unit of a line follows "a scanned barcode: the barcode's unit". `0056:217`: `GetItemUnits` returns each unit's barcodes.
- Agents. `adr/0051:124`: the quotation agent resolves "an item code or barcode found as a whole token". `adr/0050:346`: `item_overview` includes barcodes.

**What is missing**

- GS1. No parsing of GS1 application identifiers (GTIN, lot, expiry, serial in one scan), no GTIN check-digit validation, no barcode type column on `item_barcode`. GS1 appears only as a later item, "EDI unit mappings and GS1 hierarchy export" (draft `0056:269`); "SSCC labels with carrier integration" is later (`adr/0023:42`).
- Labels for items, lots and serials. Print subjects name bins, handling units and lists only. Lots and serials have a `code` (`adr/0020:45`) but no label subject, so received goods without a supplier barcode cannot be labelled.
- Barcode rendering in print. No symbology (Code 128, EAN-13, QR, DataMatrix) and no generator library is chosen for the WeasyPrint worker; a grep for these terms returns nothing.
- A scan resolver. No query that takes one scanned string and returns what it is (item and unit, bin, handling unit, lot, serial). Uniqueness is per table; nothing says an item barcode cannot equal a bin or handling-unit barcode.
- Commands for maintaining `item_barcode` are not named in the ADRs I read (the table is in the DDL; I found no `CreateItemBarcode` or equivalent in ADR-0045).
- The PWA UX spec (DS-31) is not written; ADR-0040 delegates scanning to it (`adr/0040:235`). Hardware keyboard-wedge scanners on desktop screens are not mentioned. Offline scanning is after Phase 1 (`adr/0023:254`).
- No barcode on printed documents (pick list lines, production order papers) is specified, and shop-floor scanning is only a DS-31 heading.

**Phase**

- Design: Phase 1 (data at step 2, core step 3, labels step 5, PWA step 9).
- Spec: `spec/09-mvp-scope.md:11`: "lots and serials ..., barcode, stock count"; `spec/10-roadmap.md:7`: "multiple warehouses and barcode"; `spec/11-build-order.md:45`: "warehouse screens with barcode"; `spec/07-shared-foundation.md:36`: "Barcode per packaging unit"; `spec/15-migration-ux-docs.md:17`: "Warehouse screens work well on cheap Android phones over weak networks." Match: yes.

**Constraints**

- A scan is a command by a person with an idempotency key; it goes through permissions, simulation and policy like any command, and never posts a count difference by itself.
- Text decoded from a supplier's or customer's label is outside content when it is stored as free text; structured values (GTIN, lot code) should be validated and looked up, never trusted as instructions. No spec 17 issue: barcodes are not personal data.
- Agents only draft warehouse tasks (`adr/0023:247`); they do not confirm scans.

**Direction.** One short ADR (or an ADR-0018/0023 amendment with DS-31): add `barcode_type` to `item_barcode` (GTIN-8/12/13/14, internal) with check-digit validation; a pure core parser for GS1 element strings (application identifiers 01, 10, 17, 21, 37, 00 at least) behind a single registered query `ResolveBarcode` that returns typed candidates across items, bins, handling units, lots and serials, with a rule that these namespaces may not collide within a company; print subjects for item, lot and serial labels, with the symbologies and the generator library chosen in the print worker (Code 128 and GS1-128 for logistics, EAN-13 for retail units, QR or DataMatrix for dense lot and serial data); and a statement that desktop screens accept keyboard-wedge scanners in every code field. SSCC with carrier integration and offline scanning stay later, as decided.

---

## Summary

| # | Capability | Verdict | Designed today | Main gap | Phase in design | Matches spec 09/10/14 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Configurable workflows | Partly | Policy threshold table, approval pools and stages as data; agent mode, owner and budgets per company | No rule language or automation rules; agent steps, triggers, lifecycles and work item kinds are code; no ADR for spec 16 | Approval config Phase 1; the rest after | Yes; spec 07/10 still say multi-level approval is after Phase 1 while ADR-0055 has it in Phase 1 |
| 2 | AI tuning or building deterministic functions | Partly | Rule, mapping, parameter and report-definition proposals; versioned agent constants with shadow and frozen evidence; golden sets and replay | Core constants (cascade scores) not tunable; no back-test for proposed rules; builder pipeline of spec 16 has no ADR | Proposals Phase 1; AI-authored rules and code after | Yes |
| 3 | Multimodal input | Partly (mostly not) | E-mail intake, attachments with taint, XML e-invoice record and reader, capability flags | No image or PDF reading by any workflow; no extraction record; no vision seat for personal data; no mailbox-to-e-invoice route in core; voice absent | E-mail and XML Phase 1; images undesigned | Yes for what is designed; e-invoice intake moved to an add-on while spec 09/10 keep it in Phase 1 |
| 4 | Agent-assisted master data | Partly | Customer onboarding, item mappings, migration of items, agent-ready BOM and routing draft commands, server-computed cost estimates | The product, BOM and routing drafting workflow is only a DS-57 placeholder; no BOM or routing import; no supplier or item onboarding | Production Phase 1; agent before the production core step | No: spec 09/10 still put assembly in Phase 2 (flagged, open-questions:122) |
| 5 | Agent-assisted reporting and analysis | Partly | Read-only query layer, MCP resources, statutory engine with drill-down, company report definitions, list export, Q&A and Analysis seats | No analysis agent; no aggregation on request; no dashboards, KPIs or saved reports | Read layer Phase 1; analysis agents later | Yes |
| 6 | Barcode | Covered, with gaps | `item_barcode` per unit, bin and handling-unit barcodes, scans as commands, bin and HU labels, PWA with BarcodeDetector, unit from scan | No GS1 parsing or check digits, no item, lot or serial labels, no symbology choice, no scan resolver, DS-31 UX spec unwritten | Phase 1 | Yes |

Hard floors that every extension above must keep: untrusted content limits a run to one scope and to drafts (spec 03 rule 1); the triggering person never approves (rule 5); close and reversal stay human only (spec 14 table); tool lists are fixed (rule 2); nothing learned is hidden (rule 9); the LLM never computes a number (Principle 13); personal data follows the label and the routing switch in the gateway, not the prompt (spec 17).
