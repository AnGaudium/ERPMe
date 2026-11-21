Module: agents    Chunk: 5 of 8    Source ADRs: ADR-0051, ADR-0057, ADR-0059, ADR-0060, ADR-0062
Build step(s): 3, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `agents`, chunk 5

## Purpose

`agents` (layer 5) owns the agent types, their workflows and the agent commands; the run tables belong to `agent_runs`
(layer 2). This chunk states the agents that come later, the catalog rows of the agent workflows, the agent type
`document_reader`, the data-processing policy and the vision seat, the purchase invoice agent on PDF-only supplier
invoices, the agent constants of `rank_candidates`, the agent type `analysis` (scope, steps, explanation, abstention,
modes and evidence) and the agent type `product_engineering`. The analysis catalog, questions and answers belong to
`query`; intake extractions belong to `attachments`.

## Entities and tables

The rules of this chunk define no table owned by `agents`. They constrain tables of other modules:

- `data_processing_permission` (owner `agent_runs`, DDL `docs/design/DS-36-document-intake.sql`): written by `SetDataProcessingPermission` and `EndDataProcessingPermission` (R824 to R826).
- `document_extraction` (owner `attachments`): the subject of `document_reader` runs and of the purchase invoice agent 1.1.0 (R813, R834); `document_reader` appends extraction fields to it (R817).
- `analysis_question`, `analysis_example` (owner `query`): the subjects of `analysis` runs (R839).

Reads: `agent_run`, `agent_type_setting`, `work_item`, `attachment`, `partner`, `item`, `setting_value`, `company`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `SetDataProcessingPermission` | Leaf `data_processing`, verb Set at declared minimum level `full`; accepted only from the execution of an approved change proposal whose approver differs from its submitter; effect class `master_data_change`, change-tracked, `is_proposal_bound`, on no agent tool list | Data class, seat class, provider and processing region of the registry, optional `purposes`, assessment attachment and date where needed | Writes a `data_processing_permission` row with the terms reference and retention it was approved under; the handler copies the region's country and computes `is_cross_border` (R823, R825; ADR-0063.R14) | not stated | `approver_is_submitter`, `data_processing_not_permitted` |
| `EndDataProcessingPermission` | Leaf `data_processing`, verb End at declared minimum level `full`; `human_only`; on no tool list | The permission | Narrows or ends it directly (R826) | not stated | not stated |

Jobs, not commands: `RunAnalysisEvaluation` (system job of `agents`, actor `system`, R873). Commands and queries of `agents`
that the catalog rows of R806 name are defined by the rules of ADR-0050 in other chunks: `RunAgentQualityCheck`,
`GetAgentShadowEvaluation`, `CreateAgentPromotionEvidence`, `GetAgentTypeSetting`.

Error codes bound to no command of this chunk: `shadow_evidence_insufficient` (R807); `e_invoice_record_unreadable`,
`e_invoice_supplier_mismatch` (R808); `regime_configuration_missing` and `data_processing_not_permitted` at the gateway
(R822, R827); `agent_scope_unresolved` (R835). Run outcomes set here: `not_applicable`, `drafted`, `routing_blocked`,
`budget_exceeded` and the abstentions of R870.

## Rules

### Agents that come later

R801. Payment reminders come later, designed by their own ADR before their step on ADR-0050 and the common rules of ADR-0051: reminder drafts from `RunDunning` (ADR-0048.R17) with text written in the customer's language, sent by a person.
Source: ADR-0051.R29

R802. The period-close assistant comes later, designed by its own ADR before its step: it runs the close checklist queries, reconciles, explains differences and flags anomalies, with the analysis seat; untainted, read-only plus notes. It and the variance agent are workflows on the analysis layer: their figures come from `EvaluateAnalysisPlan`, contributions and the stored production variance split, rendered as key facts by code, and their explanations are narrative plans of checked claim templates (ADR-0060 rules 18, 19, 23, 38).
Source: ADR-0051.R29, ADR-0051.R29.N2

R803. The production agents (design item DS-57, before the production core step; ADR-0032.R5) cover plan proposals, shortages and variances: reservations of components (`ReserveProductionOrderComponent`, which ADR-0034 lets the production agent run directly), the capture agent's tainted drafts of confirmations (ADR-0034.R12), the variance agent's ranking (ADR-0035.R15), and the master-data workflow that drafts bills of materials and routings and proposes their release (ADR-0033.R15). The plan, reservation, capture and variance part is designed as the agent types `production`, `production_capture` and `production_variance` (ADR-0064), under the area `production`; the master-data part is designed as `product_engineering` (ADR-0062). All four are Phase 2 agent types; the production core and its manual capture stay in Phase 1 (ADR-0078.R2).
Source: ADR-0051.R29, ADR-0051.R29.N1, ADR-0051.R29.N2, ADR-0051.R29.N3

R804. Other agents come later, each designed by its own ADR: the warehouse agent's proposals for putaway rules, pick-face levels and count plans (ADR-0023.R21), repeat-sales suggestions and quotation follow-ups (spec 13).
Source: ADR-0051.R29

### Catalog rows of the agent workflows

R805. Work item kinds of the agent workflows:
- `inbound_message_matched` (`crm`, interaction, `role:sales_clerk`, `days:1`, person); `inbound_message` remains the name of its table in `crm` (ADR-0052.R13, ADR-0052.R15; owner rule ADR-0054.R11);
- `supplier_invoice_received` (module `tax`, subject `e_invoice_record`, DS-24's pending table, `role:accountant`, `days:2`, person);
- `agent_quality_below_threshold` (`agents`, agent type, `company_owner`, `days:5`, person);
- `import_duplicate_suspected` (`imports`, import row, `document_owner`: the batch's creator, ADR-0051.R27; `days:1`, person).
Source: ADR-0051.R30, ADR-0051.R30.N1, ADR-0051.R30.N2, ADR-0051.R30.N3

R806. Command and query catalog rows: `RecordBankLineSuggestion` (`cash`, `is_draft_only`); `RunAgentQualityCheck` (`agents`, system job); `GetAgentShadowEvaluation` (`agents`, ADR-0050.R41; Phase 2, it feeds no Phase 1 promotion, ADR-0078.R6); `CreateAgentPromotionEvidence` and `GetAgentTypeSetting` (`agents`, ADR-0050.R14); `GetAutoPostShadowEvaluation` (`cash`) with the evidence hook of ADR-0051.R18; `UpdateImportBatch` (`imports`, DS-21, `is_draft_only`).
Source: ADR-0051.R30

R807. The error `shadow_evidence_insufficient` (precondition, not retryable) refuses a promotion to `assisted`, or the enabling of an auto-post rule, that lacks the evidence ADR-0051.R4 and ADR-0051.R18 require; in Phase 1 the evidence for `assisted` is the stored evaluation result of ADR-0078.R6, and for `active` the draft acceptance of ADR-0065.R11.
Source: ADR-0051.R30

R808. Rows for the intake seam (ADR-0051.R20 note): the errors `e_invoice_record_unreadable` and `e_invoice_supplier_mismatch` (validation) and the check result `e_invoice_signature_unverified`.
Source: ADR-0051.R30.N2

R809. Edge cases of the agent workflows (DS-17):
- `EC-79`: a quotation e-mail asks the agent to add another customer's prices and to send the quotation at once; the run stays in its scope, any out-of-scope read is refused, and nothing is sent;
- `EC-80`: an e-mail from an unknown sender whose tax ID belongs to an existing partner; the proposal carries the redacted duplicate check, a person rejects it, and an approval by the workflow owner would fail with `segregation_of_duties`;
- `EC-81`: a supplier e-invoice line without a mapping; the agent chooses among the supplier's items, the mapping is proposed, and after approval the next invoice maps without an LLM;
- `EC-82`: a bank line whose description names an invoice in free text; the suggestion leads to a tainted draft without a score, which an enabled auto-post rule does not post;
- `EC-83`: a quotation run whose worker crashes after an LLM call; the retry replays the recorded step and drafts once.
`EC-79`, `EC-80` and `EC-83` start from Phase 2 agent types and cannot run in Phase 1; the checks of `EC-79` and `EC-83` are re-hosted on `purchase_invoice` and the assistant (ADR-0078.R9a).
Source: ADR-0051.R30

R810. The DS-17 event `customer_inquiry_received` (an e-mail from an unknown sender, step 5) belongs to the sales group (area `sales`).
Source: ADR-0051.R30

### The agent type `document_reader`

R811. Trigger: the agent type `document_reader` (ADR-0050.R12) declares the work item kind `document_extraction_review`. The wake-up consumer (ADR-0050.R16) starts a run when the kind is raised in a company where the agent type is not `off` and the seat is usable for the company (R829); otherwise the item stays with people, who key or confirm the fields on the verification screen.
Source: ADR-0057.R11

R812. Precheck: step `D0` ends the run `not_applicable` without an LLM call when the extraction's kind has no pages (XML, spreadsheet, e-mail), when no required field is missing or illegible, or when the extraction is under full review.
Source: ADR-0057.R11

R813. Scope and taint: scope kind `subject`, the extraction row. `document_extraction` is an outside-content subject table, so the run starts tainted (ADR-0050.R15). It reads its subject, the subject's words, fields and rule runs, and its attachment's pages; that this lies in the tainted read scope is a reading put to the author (open question).
Source: ADR-0057.R11

R814. No tools: the tool list of `document_reader` holds no query and no command for the model. Workflow code renders the pages, calls the gateway and writes the result.
Source: ADR-0057.R11

R815. Input per page: the rendered page image, re-encoded without metadata (ADR-0057.R19), and the OCR words of that page as `(word_number, line_number, text, box)`, datamarked (ADR-0057.R18); plus the purpose's field list with types. At most `intake.vision_max_pages` pages (default 10) per run; a longer document stays with people.
Source: ADR-0057.R11

R816. Output schema `DocumentReaderPageOutput` 1.0.0: per field path `{value_raw, word_ids, page, status}`, with `status` one of `found`, `not_found`, `illegible`. It has no confidence field (ADR-0050.R35).
Source: ADR-0057.R11

R817. Writing: after alignment (ADR-0057.R12), `CreateExtractionFields` (module `attachments`, effect class `other`, `is_draft_only`, on this agent type's list for workflow code only) appends the rows, method `vision_aligned` or `vision_unaligned`, with the run as `agent_run_id`, and the rule run that follows, in the same transaction. That appending rows to an outside subject's extraction is a draft-only write is a reading put to the author (open question). The run ends `drafted` and unclaims the item, which goes back to its owner for verification.
Source: ADR-0057.R11

R818. The seat of `document_reader` is `extraction_vision_personal` (R828).
Source: ADR-0057.R11

R819. Promotion thresholds of `document_reader`: golden set 95% of aligned fields equal to the known value; and, before `assisted`, the replay of a company golden set of at least 50 real documents per purpose labelled by people who hold the purpose's `approve` level, with calibrated thresholds per field (ADR-0057.R13). In Phase 1 that replay replaces the live shadow-agreement criterion (95% over at least 50 documents per purpose); live shadow runs return in Phase 2 (ADR-0078.R6).
Source: ADR-0057.R34, ADR-0057.R34.N1

R820. Per-run ceilings of `document_reader`: 12 LLM calls, 10 tool calls, 150,000 input tokens, 8,000 output tokens, USD 0.80, 300 seconds, 500 rows per run. It has no daily budget of its own: the company's daily cap is the only daily tier (ADR-0078.R7).
Source: ADR-0057.R34

R821. Field-agreement comparator of `document_reader`: per field, the aligned value against the person's confirmed value; a case is equal when every aligned field equals and no unaligned value was confirmed unchanged. In Phase 1 it measures quality in use on stored output (ADR-0078.R15), not on live shadow runs.
Source: ADR-0057.R34, ADR-0057.R34.N1

### Data-processing policy

R822. The data-processing policy is core and regime-neutral. The regime setting `data_processing.policy` (ADR-0016.R9) is registered by the core without a default. Per data class (`internal`, `personal`, `sensitive_personal`) it states whether processing by a model provider is allowed and whether processing in another country than the company's needs a recorded assessment; its schema is widened per data class by ADR-0063.R18. A regime that declares no value makes every check fail closed with `regime_configuration_missing` (ADR-0016.R10). Every package states its policy, the test package `l10n_xx` included (ADR-0053.R9); a regime may open it as an option for companies (ADR-0016.R11).
Source: ADR-0057.R20, ADR-0057.R20.N1

R823. The provider registry: each provider endpoint of the installation declares in its adapter configuration (DS-37) the processing region and its country. A permission names a provider and region of that registry; the handler copies the region's country and computes `is_cross_border` against the company's country. The proposer types neither.
Source: ADR-0057.R20

R824. Company permissions: `data_processing_permission` (owner `agent_runs`, company data, change-tracked) lists what the company permits: data class, seat class, provider, processing region and country, whether it is cross-border, the assessment attachment and date where one is needed, who approved it, and dates. A permission may name purposes and records the provider's terms and retention; it is suspended when the registry changes the endpoint's region or terms (ADR-0063.R14).
Source: ADR-0057.R20, ADR-0057.R20.N1

R825. `SetDataProcessingPermission` (module `agents`, effect class `master_data_change`, change-tracked, `is_proposal_bound`, on no agent tool list, verb Set with the declared minimum level `full` on the leaf `data_processing`) is accepted only from the execution of an approved change proposal whose approver differs from its submitter (`approver_is_submitter`), like a promotion (ADR-0050.R14). Its check refuses a permission that the regime policy forbids, or a cross-border one without an assessment where the policy requires one (`data_processing_not_permitted`).
Source: ADR-0057.R20, ADR-0057.R20.N1

R826. `EndDataProcessingPermission` (module `agents`, `human_only`, verb End with the declared minimum level `full` on the leaf `data_processing`, on no tool list) narrows or ends a permission directly.
Source: ADR-0057.R20, ADR-0057.R20.N1

R827. Enforcement: the gateway evaluates the policy and the company's permissions before every request that carries a personal value, a whole-attachment item (R830) or goes to a seat of class `extraction_vision_personal`, in every run mode (live, shadow in Phase 2, replay against the provider, evaluation and golden-set replays). It refuses the request with `data_processing_not_permitted` when no active permission covers the item's data class, the seat class, the provider and its registered region; the run ends `routing_blocked` (ADR-0063.R15).
Source: ADR-0057.R20, ADR-0057.R20.N1

### The vision seat `extraction_vision_personal`

R828. The seat class `extraction_vision_personal` is defined in the design layer: required capabilities structured output and image and PDF input; reasoning `low`; temperature 0 where supported; data class `personal` (ADR-0050.R9); no tools.
Source: ADR-0057.R21

R829. The seat is usable for a company only when an active `data_processing_permission` covers data class `personal`, this seat class and the installation's provider and region; a company may permit the installation's cloud provider for this seat through such a permission. Otherwise the reason it is unusable is "no permitted provider configured", whatever the regime. With the routing switch on, Phase 1 still sends no personal value to any model (spec 17), so a run ends `routing_blocked`; the local adapter stays designed but not enabled (ADR-0050.R5).
Source: ADR-0057.R21, ADR-0057.R21.N1

R830. Whole-attachment items: a page image is a context item kind `attachment_page`, carrying the attachment's label as a whole. The gateway sends or refuses it as a whole and never strips part of an image. It logs the call in the processing log with the attachment as the row sent (ADR-0050.R10).
Source: ADR-0057.R21

R831. Adding the seat to spec 17's seat list stays the author's (open question). Until then the seat exists in `seatmap.yaml` only and is used only as R828 to R830 allow.
Source: ADR-0057.R21, ADR-0057.R21.N1

### PDF-only supplier invoices

R832. Ladder for a PDF-only supplier invoice: an embedded XML is parsed first (rung 2). Otherwise the text layer, confirmed by OCR, and OCR words with the package's label anchors and the supplier's mapping rules (rungs 5 and 6); vision only where the seat is enabled.
Source: ADR-0057.R26

R833. Full human verification: every required field is confirmed by a person; there is no automatic posting and no automatic match, and the extraction never reaches `extracted` from rungs 5 to 7.
Source: ADR-0057.R26

R834. A `purchasing` consumer of `DocumentExtractionVerified` raises `supplier_invoice_extracted` (subject the extraction) for a verified supplier-invoice extraction without an e-invoice record. The purchase invoice agent 1.1.0 declares that kind and accepts `document_extraction` as a subject (ADR-0051.R20 note); its area is `purchasing`.
Source: ADR-0057.R26

R835. Scope of the purchase invoice agent on an extraction: the supplier whose normalized tax ID equals the verified `seller_tax_id`, when exactly one active supplier has it; otherwise `agent_scope_unresolved`.
Source: ADR-0057.R26

R836. Inputs, from the current confirmed fields: `seller_tax_id`, `invoice_number` and the package's key fields as the partner reference, `issue_date` as the supplier invoice date, `currency`, `net_total`, `tax_amount`, `gross_total`, and per `lines[n]`: `seller_item_code`, `item_name` (free text, untrusted), `unit_text`, `quantity`, `unit_price`, `line_amount`, `tax_rate`.
Source: ADR-0057.R26

R837. Steps: D1 is the duplicate key check (ADR-0057.R15), then D2 to D5 of ADR-0051.R21. The run starts tainted, as every run on an outside subject.
Source: ADR-0057.R26

### Agent constants

R838. The fuzzy acceptance constants of `rank_candidates` (92 and 8) stay constants of the agent type version in Phase 1, changed by a new version with an evaluation (ADR-0051.R1 note); no Phase 1 agent type declares a parameter set (ADR-0078.R6). Phase 2: a later agent type version may instead declare them as a tunable parameter set; the current version's `parameters_hash` then enters its behavior hash, so a promoted parameter set makes the agent run as `shadow` until it is promoted again (ADR-0050.R14).
Source: ADR-0059.R7

### The agent type `analysis`: declaration

R839. Subjects and scope of `analysis` (ADR-0050.R12): scope kind `subject`, one `analysis_question` row (ADR-0060.R21), or one `analysis_example` row for evaluation runs (ADR-0060.R25 as stated in R873). Questions are typed by a signed-in person of the company (`CreateAnalysisQuestion` is `human_only`) and are not outside content, so the run starts clean.
Source: ADR-0060.R20

R840. `analysis` declares `may_read_untrusted: false`, so the run never taints (ADR-0050.R28).
Source: ADR-0060.R20

R841. `analysis` declares the field classes `cost` and `margin`. A run sees a class only when its human holds it too (ADR-0050.R12 note).
Source: ADR-0060.R20

R842. Tool list of `analysis`: read tools for the LLM steps `ListAnalysisCatalog`, `ListAnalysisDimensionMember`, `GetAnalysisPlanExplanation`, `ListSavedAnalysis`, `GetSavedAnalysis`, `ListAnalysisExample`. Workflow code also calls `EvaluateAnalysisPlan`, `ListAnalysisCellRow`, `GetAnalysisQuestion`, the command `UpdateAnalysisAnswer` and `CreateChangeProposal`. Nothing that posts, sends or exports.
Source: ADR-0060.R20

R843. Seats of `analysis` (spec 17): classification with personal data for the router (L1), which uses the cloud classification model while the routing switch is off (spec 17's reference seatmap); data Q&A for planning (L2); data Q&A for plain explanations and analysis for contribution plans (L3), which receive no question text. The question is personal (ADR-0060.R21), so a seat whose class is below `personal` never receives it (ADR-0050.R9). Before the router step, names of the company's own personal records in the question are replaced by handles while `analysis.pseudonymize_known_subjects` reads true, the default (ADR-0063.R17).
Source: ADR-0060.R20, ADR-0060.R20.N1

R844. Budgets of `analysis` per run (ADR-0050.R22; maximums, flagged for the author): 14 LLM calls (one route, three plan attempts with at most two member lookups each, two explanations: 12; and two of ADR-0050.R35's schema retries), 40 tool calls, 140,000 input tokens, 12,000 output tokens, USD 0.95, 180 seconds, 2,000 rows read (result rows count). It has no daily budget of its own: the company's daily cap binds it, and as an internal type it draws on the reserve (ADR-0078.R7). A run that needs more ends `budget_exceeded` and its question `failed`.
Source: ADR-0060.R20

R845. Constants of the `analysis` version: at most 3 plan attempts (one plan and two repairs), at most 2 member lookups per attempt, at most 5 examples as context, defaults `limit` 20 and `top` 10.
Source: ADR-0060.R20

R846. Holders of `start_agent:analysis` (leaf `agent_analysis`, ADR-0060.R36) may start `analysis`.
Source: ADR-0060.R20

### The agent type `analysis`: steps

R847. Step `D1 load`: the question; the catalog; the verified saved analyses and examples the asker may see: those with visibility `company`, and the asker's own private ones. Another user's private analysis is never matched, offered as a hint, or revealed by a badge.
Source: ADR-0060.R22

R848. Step `D2 match_verified`: a normalized question (Unicode case folding, whitespace collapsed, trailing punctuation dropped; letters with diacritics stay distinct) equal to a verified example's or a verified saved analysis version's trigger question gives that plan, with no model. Only exact equality is accepted. A hit skips L1 and L2. D2 and L1 read only the set of D1.
Source: ADR-0060.R22

R849. Step `L1 route` (seat classification with personal data): input the question and up to 5 similar verified questions as handles, ranked by `rank_candidates` (ADR-0051.R1) as hints only. Output `AnalysisRouteOutput`: `kind` (`analysis`, `not_analysis`, `candidate`), `candidate` (a handle or none), `language`. Check: the handle was offered. `candidate` takes that plan, and its badge is computed from its hash like every other (ADR-0060.R26); `not_analysis` (a request to post, send or change data) ends the run with `not_applicable` and a note written by code that points to the right screen.
Source: ADR-0060.R22

R850. Step `L2 plan` (seat data Q&A): input the question, the business date and fiscal calendar facts, the catalog entries retrieved by synonym and token match (at most 15 measures, every dimension), the measures the human may not read named as such, and at most 5 nearest verified examples. Read tool `ListAnalysisDimensionMember` for member lookups, at most two per attempt. Output `AnalysisPlanOutput`: `kind` (`plan`, `clarify`, `clarify_member`, `out_of_coverage`, `not_permitted`), with `plan`, or `term` and 2–4 `options`, or a lookup handle, or `nearest` (measure codes).
Source: ADR-0060.R22

R851. Checks of L2 on codes and keys: codes exist; options and nearest name catalog objects; `term` is a catalog term (an ambiguous term or a synonym); member keys came from a lookup result of this run (ADR-0050.R36).
Source: ADR-0060.R22

R852. Stated-value check of L2 (ADR-0050.R36): every absolute date, named period, `n`, `limit` and `top` in the plan appears in the question. The question is normalized first: number words to digits and month names to month numbers through the language's lists, dates parsed in ISO form and the company's locale formats. A named period needs its year in the question and its month or quarter by number, name or "Q" form; the model never completes a missing year. `limit` and `top` the question does not state are left empty and code fills the defaults. A plan that fails is sent back like a validation error; after the last repair the run abstains `ambiguous_term` with period options, never `output_invalid`.
Source: ADR-0060.R22

R853. Member and KPI checks of L2: when a lookup for one search text returned more than one member and the plan uses one of them, code ends the run `ambiguous_member` with that lookup's handles, whatever the model chose; `clarify_member` is the model's own way to ask. A plan holds no KPI field: an agent never proposes a target or threshold.
Source: ADR-0060.R22

R854. Step `D3 validate` calls `GetAnalysisPlanExplanation`; violations go back to L2 with their codes and paths, at most twice; then R870 maps the last code to an abstention. Step `D4 run` calls `EvaluateAnalysisPlan`; its error codes map by R870.
Source: ADR-0060.R22

R855. Step `D5 facts`: code marks the largest and smallest member rows (`is_max`, `is_min`) on complete results only, and only when the extreme is unique (on a tie no cell is marked), for values and contributions alike, and offers the key facts of R859: the totals, the top members, the changes and the contribution rows, at most 12, each with a fact handle.
Source: ADR-0060.R22

R856. Step `L3 explain` (seat data Q&A, or analysis for contribution plans): input the restatement written by code, cell handles with values, kinds and flags, member handles with their labels where the label is `internal` (personal labels stay handles, ADR-0060.R31), the offered key facts, the scope and truncation flags and the checks; no question text. Output `AnalysisExplainOutput`: `facts` (at most 5 fact handles, each one of the 12 offered, none twice) and `narrative` (at most 8 steps of R861); the schema has no free-text field. Checks: R858 to R864.
Source: ADR-0060.R22

R857. Step `D6 answer`: `UpdateAnalysisAnswer` with the key facts, the narrative plan and the steps code dropped. The UI renders both by code at display time.
Source: ADR-0060.R22

### The agent type `analysis`: explanation

R858. The explanation is key facts and a narrative plan, both rendered by code (ADR-0050.R36, made structural). In Phase 1 the model writes no text that reaches the person (`INV-413`).
Source: ADR-0060.R23

R859. Every number an answer states is a key fact that code renders from a fixed template set of the output language, with values formatted by locale, currency, unit and scale (ADR-0040.R2). English forms:
- `value`: `<measure> for <member>: <value> (<period>)`, or `(as of <date>)` for a balance or a current-snapshot measure;
- `total`: `<measure>, total: <value> (<period>)`;
- `change`: `<measure> for <member> changed from <a> to <b> (<signed change>, <direction word>)`;
- `share`: `<member>: <share> of <measure> (<period>)`;
- `contribution`: `<member> contributed <signed change> to the change in <measure> (<period> against <compare period>)`.
Source: ADR-0060.R23

R860. The direction word (rose, fell, was unchanged) is computed from the sign. Code offers up to 12 facts, each with a handle (D5); the model may pick up to 5 of them, each one of the offered handles and none twice (ADR-0050.R36); without a pick code shows its own: the total, the largest member and the changes.
Source: ADR-0060.R23

R861. The model's `narrative` is an ordered list of at most 8 steps, each `{"claim": <claim template code>, "facts": {<role>: <fact handle>}}`. Every fact handle is one of the 12 offered; the model names no member: code renders `{member}` from the fact's own row; codes and handles are short identifiers, and the schema rejects any other field or value. A plan that breaks the schema is invalid output (ADR-0050.R35's retries), and then the answer shows the key facts alone.
Source: ADR-0060.R23

R862. Code renders every sentence from a closed catalog of claim templates per language; each template declares its roles and a deterministic precondition on the served cells. English sentences and preconditions:
- `largest_value`: `{member} has the largest {measure}.`; a member row (not a total or other row) marked `is_max`, on a complete result with at least two member rows;
- `smallest_value`: `{member} has the smallest {measure}.`; a member row marked `is_min`, on a complete result with at least two member rows;
- `largest_contributor`: `{member} is the largest contributor to the change in {measure}.`; a member contribution row; the total change is not zero; the contribution has its sign and is the unique largest of that sign;
- `largest_offset`: `{member} is the largest offset to the change in {measure}.`; a member contribution row; the total change is not zero; the contribution has the opposite sign and is the unique largest of that sign;
- `most_of_change`: `{member} explains most of the change in {measure}.`; a member contribution row; the total change is not zero; the contribution has its sign and more than half of the sum of all contributions of that sign, the other row included, so at most one member qualifies;
- `rose`, `fell`: `{measure} rose for {member}.` / `{measure} fell for {member}.`; a member row's change cell above, or below, the flat band;
- `flat`: `{measure} was almost unchanged for {member}.`; a member row's absolute change at most the flat band: 1% of the absolute base value (0 when the base is 0), a constant of the agent type version;
- `same_direction`: `{measure} moved in the same direction for {member_a} and {member_b}.`; two distinct facts of member rows, of the same measure and the same comparison, both changes outside the flat band, with the same sign;
- `opposite_direction`: `{measure} moved in opposite directions for {member_a} and {member_b}.`; as `same_direction`, with opposite signs;
- `scope_note`: `These figures cover only the records you may see.`; `is_scope_filtered`;
- `also`, `meanwhile`: `Also,` / `Meanwhile,` before the next sentence; rendered only between two rendered sentences.
Source: ADR-0060.R23

R863. `{member}` (and `{member_a}`, `{member_b}`) renders the fact's whole row: every grouped member of it, and for a pinned basis the pinned member too, so a claim about one cell never reads as a claim about one of its members. `{measure}` renders as the measure's catalog label; each sentence ends with the citation markers of its facts, which open the key facts. A member renders as a marker, a chip or link in the UI: the chip is the control, and a label's text is data, never interpolated outside its chip. A CI check holds that no claim template and no catalog label contains a digit, a number word or a unit word.
Source: ADR-0060.R23

R864. Before rendering, code evaluates each step's precondition on the served cells. A failing step is dropped and recorded in `narrative_dropped_steps` with its claim and reason; the rest are rendered. Every direction, rank and quantity word comes from code, after code has checked it. The rendered narrative is a pure function of the plan, the cells, the member labels and the catalog: no string from the model reaches it except through a handle that code resolves.
Source: ADR-0060.R23

R865. A language without a claim catalog and key-fact templates gets key facts only, in the company's default language, or in English when that language has none either. The core ships English; a package supplies the catalog for its language.
Source: ADR-0060.R23

R866. The restatement is written by code from the plan: measures, dimensions, filters, absolute range, time dimension, basis.
Source: ADR-0060.R23

R867. What remains open to the model is a true but unhelpful choice or order of claims; the key facts and the table beside them bound it.
Source: ADR-0060.R23

R868. The setting `analysis.narrative_mode` (`facts_only`, `claim_plan`, the default; `free_prose` outside the bounds in Phase 1) chooses how answers explain; its installation value is a maximum that a company may only lower. Free prose written by the model is not used in Phase 1; after Phase 1 it unlocks per language and model version at 80% acceptance with no unbacked claim, measured by an evaluation suite that reports the prose acceptance rate (ADR-0063.R25).
Source: ADR-0060.R23, ADR-0060.R23.N1

### The agent type `analysis`: abstention

R869. Abstention is a typed outcome of a completed run, tuned for precision: a wrong answer costs more than an abstention. The model never falls back to SQL or to arithmetic of its own.
Source: ADR-0060.R24

R870. Outcomes of an `analysis` run, with when and what the person sees:
- `answered`: a result, verified or generated; restatement, table or chart, key facts, narrative, scope note, badge, `as_of`, the "how this was computed" fold;
- `ambiguous_term`: L2 returns `clarify`, or after the last repair the plan still fails the stated-value check (period options), or the code is `analysis_plan_invalid`, `unknown_measure`, `unknown_dimension`, `currency_mixed`, `unit_mixed`, `dimension_required`, `time_range_invalid` or `filter_value_unknown`; 2–4 options from the catalog (currency or unit choices for the mixing codes, periods for the time codes); choosing one asks again;
- `ambiguous_member`: decided by code when a lookup for one search text returned several members and the plan uses one of them, or L2 returns `clarify_member`; the candidate members, rendered by code from their handles for the person within their rights; choosing one asks again;
- `out_of_coverage`: L2 returns `out_of_coverage`, or the last code is `dimension_not_shared`, `fan_out_refused` or `measure_not_additive`; no measure answers this; the nearest measures; an offer to log a catalog request (`analysis_catalog_request`, owner `company_owner`);
- `not_permitted`: L2 returns `not_permitted`, or the code is `analysis_not_permitted` or `permission_denied` (no repair); what is missing (a field class, a fact, an owner scope), never data;
- `data_not_ready`: `analysis_data_not_ready`; why: before the cut-over, a migration is loading, or the figure exists only for today;
- `too_broad`: `analysis_too_broad` or `timeout`; a request to narrow, with the limit that tripped.
Source: ADR-0060.R24

R871. These outcomes extend ADR-0050.R17's table and the check `ck_agent_run_outcome` of DS-05-platform.sql: all are state `completed`, and the run's `agent_task` item is resolved. A question whose run ends `routing_blocked` or `not_applicable` is `abstained` too.
Source: ADR-0060.R24

### The agent type `analysis`: modes and evidence

R872. In mode `assisted`, `analysis` answers people's questions; the answer goes only to the asker (ADR-0050.R14; ADR-0051.R4).
Source: ADR-0060.R25

R873. Evaluation in use: the daily evaluation job `RunAnalysisEvaluation` (system job of `agents`, actor `system`) starts one run per verified example of the company, with the example as subject, acting for the person who released the example (that person's scope and field classes apply); it starts automatically from `artifacts.analysis.min_verified_examples` verified examples. The run does not call `UpdateAnalysisAnswer`, because an example has no question row: its plan, hashes, key facts and narrative plan stay in the run's recorded steps (ADR-0050.R41), which the comparator reads. The comparator counts a case equal when the run's `analysis_resolved_hash` equals the example's, or when both results are equal on the same snapshot.
Source: ADR-0060.R25, ADR-0060.R25.N1, ADR-0060.R25.N2

R874. Promotion evidence is a stated exception: an analysis run drafts nothing a person later resolves, so there are no shadow cases of ADR-0051.R4. `CreateAgentPromotionEvidence` freezes instead the version's CI evaluation report (ADR-0060.R29) and, when the company has at least `artifacts.analysis.min_verified_examples` verified examples (default 30), the evaluation of R873 over them (at least 90% equal, no wrong answer on an example whose expected outcome is an abstention). Below that minimum the synthetic CI report alone is the evidence while `artifacts.analysis.allow_synthetic_only_promotion` reads true (the default). The proposal to set `assisted` names that snapshot; a person other than the submitter approves it.
Source: ADR-0060.R25, ADR-0060.R25.N1, ADR-0060.R25.N2

R875. The `analysis` agent type version declares the catalog hash it was evaluated with, so a catalog change is a new version. In Phase 1 a version, or a catalog change that makes a new version, without a passing evaluation runs as `off` (ADR-0078.R6).
Source: ADR-0060.R25, ADR-0060.R25.N2

R876. In Phase 1 `analysis` has no `shadow` mode: `check` refuses it.
Source: ADR-0060.R25.N2

### The agent type `product_engineering`

R877. `product_engineering` is an agent type of `agents` (layer 5) on the runtime of ADR-0050 and the common rules of ADR-0051 rules 1–9. It reads through registered queries and writes through the commands of `production` (ADR-0033.R2), `master_data` (ADR-0045) and `documents` (`CreateChangeProposal`); no new module. Its leaf is `agent_product_engineering` under `agent` (capability `start_agent:product_engineering` at `edit`); the template `production_planner` holds it at `edit`. It is a Phase 2 agent type, with its design and DDL kept as seams (ADR-0078.R2).
Source: ADR-0062.R1, ADR-0062.R1.N1

## Invariants

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-413` | `analysis_sentences_rendered_by_code` | day, from step 5 | Every user-visible sentence of an analysis answer is rendered by code, from a key-fact template or from a claim template whose precondition held on the served cells; every stored narrative plan holds only claim codes, roles and handles. | R858 to R864; ADR-0050.R36, ADR-0078.R8 |

## Settings

The rows of the settings these rules use stand in chunk 6, with the rules of their catalog sources: `data_processing.policy` (R822, R825, R827), `analysis.pseudonymize_known_subjects` (R843), `analysis.narrative_mode` (R868), `artifacts.analysis.min_verified_examples` (R873, R874) and `artifacts.analysis.allow_synthetic_only_promotion` (R874).

`intake.vision_max_pages` (default 10, R815) is named by ADR-0057.R11 but absent from `settings.csv`.

## Conflicts

CONFLICT ADR-0051.R30: the owner rule is now `role:sales_clerk` (ADR-0051.R30.N1, ADR-0054.R11) and the kind is named `inbound_message_matched` (ADR-0051.R30.N3, ADR-0052.R15); R805 states the current names. `GetAgentShadowEvaluation` and the evidence behind `shadow_evidence_insufficient` follow ADR-0078.R6 in Phase 1, and the edge cases of Phase 2 types follow ADR-0078.R9a (R806, R807, R809).
CONFLICT ADR-0051.R30.N2: the work item kind `supplier_invoice_received` moves to module `tax` and the intake seam rows are added; R805 and R808 state the current catalog.
CONFLICT ADR-0057.R20: ADR-0057.R20.N1 (ADR-0063.R14, R15, R18) moves both permission commands to the leaf `data_processing` and extends the gate to every request carrying a personal value, which answers the rule's open question; stated in R822 and R824 to R827.
CONFLICT ADR-0057.R34.N1: in Phase 1 the live shadow-agreement criterion is replaced by the company golden set replay and the comparator works on stored output (ADR-0078.R6, ADR-0078.R15); stated in R819 and R821.
CONFLICT ADR-0060.R20.N1: known personal subject names in the question are replaced by handles before the router step under the pseudonymization setting (ADR-0063.R17); stated in R843.
CONFLICT ADR-0060.R23: the open question on free prose is settled by ADR-0060.R23.N1 (ADR-0063.R25): the narrative mode setting bounds prose out of Phase 1 and fixes the unlock at 80% acceptance; stated in R868.
CONFLICT ADR-0060.R25: the flagged synthetic-only promotion became settings by ADR-0060.R25.N1 (ADR-0063.R13), and shadow mode is replaced by the daily evaluation in use and mode off by ADR-0060.R25.N2 (ADR-0078.R6); stated in R873 to R876.
CONFLICT ADR-0057.R34: the daily values per company of `document_reader` are dropped; the company's daily cap is the only daily tier, governed by ADR-0078.R7 (R820).
CONFLICT ADR-0060.R20: the daily values per company and business date of `analysis` are dropped; the company's daily cap and the internal reserve bind it, governed by ADR-0078.R7 (R844).
CONFLICT ADR-0059.R7: no Phase 1 agent type declares a parameter set, so the tunable-constants path and its drop to `shadow` are Phase 2, governed by ADR-0078.R6 (R838).
CONFLICT ADR-0051.R29: the production agent types and `product_engineering` are Phase 2 types, governed by ADR-0078.R2 (R803).
CONFLICT ADR-0062.R1.N1: the agent type `product_engineering` moves to Phase 2 with its design and DDL kept as seams (ADR-0078.R2); stated in R877.

## Trace

| Source | Where |
| --- | --- |
| ADR-0051.R29 | R801-R804 |
| ADR-0051.R29.N1 | R803 |
| ADR-0051.R29.N2 | R802, R803 |
| ADR-0051.R29.N3 | R803 |
| ADR-0051.R30 | R805-R807, R809, R810 |
| ADR-0051.R30.N1 | R805 |
| ADR-0051.R30.N2 | R805, R808 |
| ADR-0051.R30.N3 | R805 |
| ADR-0057.R11 | R811-R818 |
| ADR-0057.R20 | R822-R827 |
| ADR-0057.R20.N1 | R822, R824-R827 |
| ADR-0057.R21 | R828-R831 |
| ADR-0057.R21.N1 | R829, R831 |
| ADR-0057.R26 | R832-R837 |
| ADR-0057.R34 | R819-R821 |
| ADR-0057.R34.N1 | R819, R821 |
| ADR-0059.R7 | R838 |
| ADR-0060.R20 | R839-R846 |
| ADR-0060.R20.N1 | R843 |
| ADR-0060.R22 | R847-R857 |
| ADR-0060.R23 | R858-R868 |
| ADR-0060.R23.N1 | R868 |
| ADR-0060.R24 | R869-R871 |
| ADR-0060.R25 | R872-R875 |
| ADR-0060.R25.N1 | R873, R874 |
| ADR-0060.R25.N2 | R873-R876 |
| ADR-0062.R1 | R877 |
| ADR-0062.R1.N1 | R877 |
