Module: agents    Chunk: 6 of 8    Source ADRs: ADR-0062, ADR-0063, ADR-0064
Build step(s): 1, 3    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `agents` compiled spec, chunk 6: product engineering workflow, agent wake-up and drift settings, data processing, production agent types

## Purpose

This chunk states the part of `agents` law on: the `product_engineering` agent type's entry points, drafting steps, estimate, release proposal, tainted read scope and budgets; the wake-up mode, drift action and analysis example settings of agent types; the data-processing permissions, the gate for personal values and the policy schema; the analysis narrative mode; and the frame of the production agent types, which are Phase 2. `agents` sits at layer 5 (ADR-0064.R1); it drafts through the registered commands of other modules and owns none of their tables. The runtime, the other workflows and the assistant are in the other chunks.

## Entities and tables

This chunk's rules define no table of the module; the owned table is stated in another chunk.

Reads: `interaction`, `import_batch`, `uom_alias` (DS-18), `item_barcode`, `partner_item`, `item_manufacturer_part`, `product`, `product_category`, `product_category_requirement`, `code_series` (`master_data`); `change_proposal_item` (`documents`); `bill_of_materials_revision`, `cost_estimate`, `cost_estimate_gap`, `costing_sheet`, `production_order`, `production_version`, `production_structure` (`production`); `document_extraction`, `extraction_field_trust` (`attachments`); `analysis_question` (`query`); `agent_type`, `data_processing_permission` (`agent_runs`); settings `master_data.product_code.assignment`, `master_data.product_code.prefix_source`, `master_data.product_code.pad_width`, `production.costing_sheet.required`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ListItemCandidate` | query, verb level `read` (`List`); owner module not stated | not stated | Returns id, code, name, unit, category and status of items only; the first declared tainted projection (R1029) | none | not stated |

`SetDataProcessingPermission` and `EndDataProcessingPermission` (R1037, R1038, R1043) have their rows in chunk 5.

Jobs and workflow steps, not registered commands: `RunDataProcessingProviderCheck` (at startup and daily; leaf `data_processing`) suspends permissions and raises `data_processing_permission_suspended` (R1038). The steps D1 to D8 and L1 to L4 of `product_engineering` are workflow steps (R1008-R1027). A run ends `routing_blocked` when a required personal value may not be sent (R1039), and `not_applicable` when L1's limits are exceeded (R1010).

## Rules

### Product engineering (Phase 2 agent type, design kept): entry points and start

R1001. `product_engineering` is a Phase 2 agent type, registered with mode `off` and no workflow code in Phase 1 (ADR-0078.R2); its rules apply when it is brought forward. Entry points (ADR-0050.R15), as entry, subject, taint and scope:
- E1, a person's own note: an interaction of kind `note` with `is_untrusted` false (ADR-0052.R10), started by that person; untainted; reads the catalog within the person's rights.
- E2, a person's own spreadsheet: an import batch of the bill-of-materials and routing templates (ADR-0062.R18); tainted at start (ADR-0044.R15); scope `import_batch`.
- E3, outside content: not a subject in Phase 1; a person verifies the extraction, then starts E1 on a note that names it.
- Continuation: a draft bill of materials revision the run drafted (R1006); untainted, unless a run that wrote any draft the release proposal releases was tainted; then tainted, with scope kind `subject`.
Source: ADR-0062.R2

R1002. E3, the strict reading: a drawing, request or spreadsheet from a customer or supplier is outside content and, like the configuring quotation path (ADR-0051.R14 note), never starts a drafting run. A person verifies its extraction with purpose `product_source` (ADR-0057.R23), writes a note in their own words that names the extraction and the rows they vouch for, and starts the run on the note.
Source: ADR-0062.R2

R1003. What E1 reads of a named extraction: the extraction must be `verified`; the run reads only the normalized values that `extraction_field_trust` reports trusted, with their field IDs (quantities, codes, resolved units and dimensions that fit their shapes and passed every rule, or that a person confirmed; ADR-0057.R17), never its free text, raw text or evidence. The views serve only trusted values unless asked, and workflow code never asks, so the run stays untainted. These rows enter at D2 as component lines whose source is an evidence link (the extraction field IDs), not a span of the note. Whether this reading holds is the author's (value trust).
Source: ADR-0062.R2

R1004. E2 under the literal scope: an E2 run reads its batch's rows and what recorded provenance reaches from them (ADR-0050.R25): the items that the batch's own validation resolved deterministically. It cannot read the catalog to rank candidates, so rows left unresolved go to a person, with redacted candidate counts (ADR-0050.R27). It writes drafts through the draft commands, which are `is_draft_only` (R1020), and writes no free text from batch rows into them: operation descriptions and names are the person's own text or stay empty, and headers get generated names. The projection of R1029 widens this for the agent type version that uses it.
Source: ADR-0062.R2

R1005. Who starts: a person with `start_agent:product_engineering` (leaf `agent_product_engineering`) starts a run on their note or batch, as an `agent_task` (ADR-0042.R11). The run acts for that person (ADR-0050.R15).
Source: ADR-0062.R3

R1006. Continuation: the agent type also declares the work item kinds `product_release_ready` and `product_item_proposal_ended` (ADR-0062.R14). A continuation run re-runs checks and the estimate and drafts the release proposal (steps D6 to D8), with no LLM step but the optional L4. It starts by the wake-up of `product_release_ready` after binding, or when a person starts the agent on the draft bill of materials revision (for example after filling a gap), which is the subject of a continuation. The start handler reads the audit records of the commands that wrote every draft the release proposal will release (the bill of materials revision, the routing revision, the cost estimate, and any other draft it names). A writing run counts as tainted when it has a `tainted_at`, whenever it was set. If any does, the continuation starts tainted (`taint_source_kind` `tainted_row`) with scope kind `subject`: the draft revision, its child rows (components and outputs) and the rows their keys name (component items with their products and categories' requirements, units), the draft estimate found by its one reverse key (`cost_estimate.bill_of_materials_revision_id`), and that estimate's routing revision (`routing_revision_id`) with its operations and work centers; the pairing of bill of materials and routing is the draft estimate's two revision IDs. Child rows and the reverse key go beyond the recorded provenance of ADR-0050.R25, which covers IDs a row carries; this reading belongs to the grouped tainted-read question of spec 03 rule 1. A tainted continuation of an engineering change leaves the impact evidence (where-used, open orders, stock) to a person. A release proposal drafted from an E2 batch therefore stays tainted, also when only its routing came from the batch.
Source: ADR-0062.R3

R1007. Agent type declaration of `product_engineering`: scope kinds `subject` (E1 and continuations) and `import_batch` (E2); subject tables `interaction`, `import_batch` and `bill_of_materials_revision`; `may_read_untrusted` true (E2 rows); field classes none, so the run never sees cost or margin (ADR-0050.R12 note).
Source: ADR-0062.R3

### Product engineering (Phase 2): drafting steps

R1008. D1 `gather`: the note (or the batch rows), the trusted fields of a named extraction, and the product categories, work centers and activity types the run may read.
Source: ADR-0062.R4

R1009. L1 `structure_note` (seat drafting, per routing; E1 only). Input: the note's text, as the person wrote it. Output `ProductEngineeringStructureOutput` 1.0.0: `product` (category hint text, attribute name and value texts), `components` (description text, code text if any, supplier or manufacturer name text if any, quantity as stated, unit text, scrap as stated, `source_span`), `operations` (description text, work center hint, setup and run time as stated with their unit text, `source_span`), `outputs` (co- and by-products as stated).
Source: ADR-0062.R5

R1010. L1 spans and checks: a span is one line or one sentence of the note, at most 200 characters. Checks (ADR-0050.R36): every value appears in its span and every span in the note; every quantity, time and percentage is a decimal that appears in its span; a code is kept only when it appears in its span as a whole token; at most 100 components and 30 operations, else the run ends `not_applicable` for a person.
Source: ADR-0062.R5

R1011. L1 category: a category hint that matches no category by exact code or name, nor by ranking with a lead (ADR-0051.R1), leaves the `product` for a person: no item proposal is drafted for it, and the note says so. E2 skips L1: the template's columns are the structure.
Source: ADR-0062.R5

R1012. D2 `normalize`, code only: units through the unit text resolution of ADR-0056 (partner item text, `uom_alias`, unit code; unresolved text stays unresolved and the line goes to a person); decimals by the company's formats; attribute values against the category's attributes by exact code or name. The trusted rows of a named extraction (R1003) enter here as lines.
Source: ADR-0062.R6

R1013. D3 `resolve_components`, per component line, each step only when the previous found nothing:
- exact item code: the line's code text equal to an active item's code;
- barcode: the code text equal to an active item's `item_barcode`;
- supplier code: equal to a `partner_item` code of the supplier the line names, which must hold the active supplier role;
- manufacturer part number: equal (normalized: upper-cased, separators removed) to an `item_manufacturer_part` row of the manufacturer the line names;
- ranking: `rank_candidates` (ADR-0051.R1) over active items, always blocked by the unit's quantity kind and, when the line states a category, by that category, on description text and attribute values.
Source: ADR-0062.R7

R1014. D3 outcomes: a step that finds several active items gives them to L2 as candidates (at most five, else to a person); it never picks one. A supplier code or part number whose supplier or manufacturer the line does not name is not used at the supplier-code and part-number steps; its hits, if any, join the ranking's candidates. Auto-accept: a ranked candidate scoring at least 92 and leading the next by at least 8 is accepted without an LLM only when neither the line nor the candidate carries attribute tokens (tokens with digits, such as `M8x20`, `3mm` or `100x200`); when either does, every attribute token of the line must equal one of the candidate's and every blocking attribute must match, otherwise the candidate goes to L2. Every line keeps its resolution method and the candidates considered. Codes found in the code, barcode, supplier-code and part-number steps are whole values, never fragments.
Source: ADR-0062.R7

R1015. L2 `choose_component` (seat classification), for lines left with candidates. Input: the line's description, unit and stated attributes, and at most 5 candidates (handle, code, name, unit, category, key attributes); no price, cost, supplier or stock. Output `ProductEngineeringChooseOutput` 1.0.0: `choice` (a handle, or `new_item_needed`), `reason_code` (`exact_name`, `synonym`, `attribute_match`, `no_match`), and with `new_item_needed` the attributes it found, each with its `source_span`.
Source: ADR-0062.R8

R1016. L2 checks: the handle was offered; `new_item_needed` carries at least one attribute with a span; numbers in attributes appear in their spans. A line with neither stays unresolved for a person. L2 never gives a code, a standard time, a rate or a price that is not in the line's source (Principle 13; ADR-0050.R36).
Source: ADR-0062.R8

R1017. D4 `propose_items`: one change proposal for every new item of the run (`product_engineering.items`). Items: `CreateProduct` with its single item (ADR-0018.R2), or `CreateItem` for a variant of an existing product; each item has a stable `change_proposal_item.id`, which drafts refer to (ADR-0062.R14). The category drives the defaults (ADR-0018.R3; `product_category` defaults) and the required attributes (`product_category_requirement`, ADR-0062.R11); a missing required attribute is listed in the proposal's evidence and checked again at release. The inventory unit is the category's default, else the unit the line states.
Source: ADR-0062.R9

R1018. Numbering at execution: the payload carries no code. The executing command issues it from the company's `code_series` row for record kind `product` (DS-20; one row per company, or per category with its short code as prefix; no fiscal year and no branch, unlike document series), moved only by the numbering lock helper (ADR-0008.R10), skipping any code already in use; simulation consumes no number. The model never composes a code. This behavior is the default of the settings `master_data.product_code.assignment` (`sequence`), `master_data.product_code.prefix_source` (`category_short_code`) and `master_data.product_code.pad_width` (6), per company and category (ADR-0063.R22).
Source: ADR-0062.R9, ADR-0062.R9.N1

R1019. D4 names and duplicates: the product's name is generated by code from the category's name and the attribute values in the category's attribute order, in the company's language; the person may edit it before submitting. Each item carries the candidates of D3 and L2 that the workflow rejected, with the reason (`no_match` from L2, a failed blocking attribute, a different unit kind, an attribute token that differs), and the server's own duplicate check on normalized name and attributes in its plan (check result `item_duplicate_suspected`).
Source: ADR-0062.R9

R1020. D5 `draft_structures`, draft commands: `CreateBillOfMaterials`, `CreateBillOfMaterialsRevision`, `UpdateBillOfMaterialsRevision`, the same three for routings, and `CreateCostEstimate` are effect class `other` and registered `is_draft_only` (ADR-0033.R2 and ADR-0035.R14 notes), so an E2 run may run them. A bill of materials header has no effect without a released revision and a production version, which are proposal-bound; its name is generated by code from the output's code or proposal item, never copied from untrusted text.
Source: ADR-0062.R10

R1021. D5 bill of materials: a new header (or a new draft revision of an existing one): the main output, components with quantity as stated, unit, scrap only if stated, phantom only if stated, operation numbers only if the source pairs them. A main output or component that is a new item refers to its proposal item (`proposed_change_proposal_item_id`) instead of an item (ADR-0062.R14). Co-products and by-products must be existing items; a new one waits for its item's approval. A pending component's line is written in the proposed item's inventory unit with the identity snapshot (ADR-0056.R9) when the source states that unit; a line stated in another unit is left for after binding, in the note.
Source: ADR-0062.R10

R1022. D5 routing: `CreateRouting` and a draft revision: one operation per stated operation; the work center chosen among existing ones by exact code or name, else by `rank_candidates` and L3 `choose_work_center` (seat classification, at most 5 candidates, the same checks as L2); times only when stated in a span. Setup and run time are flagged separately: `is_setup_duration_stated` and `is_run_duration_stated`. An unstated time is written as 0 with its flag false, and no activity row stands for it; a reader and the release guard know it is not a real zero.
Source: ADR-0062.R10

R1023. D6 `check`: `GetBillOfMaterialsRevisionCheck` on the draft (ADR-0033.R15), plus the pending-item check of ADR-0062.R14; and `GetProductReadinessCheck` (module `production`, computed query at `read` on `production_structure`; item or proposal item, date): the category's requirements (`product_category_requirement`: attributes, dimensions, weights, barcode, supplier item, bill of materials, routing, production version, cost estimate, classification), every make item has a bill of materials and a routing, every internal operation's work center has activity rates for the date, every component has a price on the estimate's price basis or a released estimate, units convert. Each missing requirement is a check result `readiness_requirement_missing` with its code.
Source: ADR-0062.R11

R1024. D7 `estimate`: `CreateCostEstimate` computes on the draft revisions (ADR-0035.R14 note): `production_version_id` may be empty for a draft estimate, which names the draft bill of materials and routing revisions and the costing lot quantity. Gaps, never zero: a missing purchase price, activity rate, activity quantity, pending item, unstated setup or run time, missing routing, costing sheet row without a valid rate, or missing costing sheet is a `cost_estimate_gap` row (`material_price_missing`, `activity_rate_missing`, `activity_quantity_missing`, `component_item_pending`, `setup_duration_unstated`, `run_duration_unstated`, `routing_missing`, `costing_rate_missing` naming the sheet and row, `costing_sheet_missing` when no sheet exists while `production.costing_sheet.required` is true; ADR-0072.R7, ADR-0072.R9) and is left out of the total, which the response states as incomplete with the check result `cost_estimate_gap`. A released estimate has no gap and a production version (`cost_estimate_incomplete`). Like costs, rates are never written by the model (ADR-0072.R18).
Source: ADR-0062.R12, ADR-0062.R12.N1

R1025. D7 delta and code costs: when the output item has a released estimate valid on the costing date, the new estimate names it in `previous_cost_estimate_id`, and the response gives the difference per cost component and per line. The estimate is never computed or adjusted by the model and never sent to it.
Source: ADR-0062.R12

R1026. D8 `evidence_and_release`: one change proposal for the release (`product_engineering.release`), drafted when no proposal item is pending. Items: `ReleaseBillOfMaterialsRevision`, `ReleaseRoutingRevision`, and for a new output `CreateProductionVersion` (ADR-0033.R13); the cost estimate is released separately by `ReleaseCostEstimate` once the version exists and no gap remains. Evidence pack, in the proposal's `evidence`: the sources (the note, the extraction and its fields, or the batch rows, each with its evidence link); every resolution decision with its method, candidates and reasons; the check results of D6; the estimate with its gaps and delta, rendered by code; the effectivity (`start_date`); and the item proposal that preceded it.
Source: ADR-0062.R13

R1027. D8 approval: a person submits the release proposal; the approver is an eligible person of the proposal's pool other than the human the run acted for (ADR-0055.R7, condition 5; spec 03 rule 5); approval routing uses the company's thresholds. L4 `write_summary` (seat drafting, optional) writes a summary for the approver of the sources, resolution decisions and check results; its input excludes the estimate and every cost, price and rate; the cost section of the pack is rendered by code; every number in the summary equals a number of its input (ADR-0050.R36).
Source: ADR-0062.R13

### Product engineering (Phase 2): limits, tainted reads, quality and budgets

R1028. The model drafts quantity structure only: which components, which operations, quantities and times as stated in a source span or an extraction's evidence. It never produces a cost, price, rate or margin; those come only from `CreateCostEstimate`, price lists and activity rates, and no model input holds them.
Source: ADR-0062.R16

R1029. Tainted read scope: the deterministic matching query `ListItemCandidate` (the D3 steps as one query; ADR-0004.R21 allows only `Get`, `List`, `Evaluate` and `Render` as query verbs) returns only id, code, name, unit, category and status of items, never prices, costs, partners, stock or free-text notes; it is the first declared tainted projection (ADR-0063.R16). A new `product_engineering` agent type version uses the projection. Without it the literal scope holds: E2 rows that need the catalog go to a person (R1004), and E3 goes through a person's note.
Source: ADR-0062.R17, ADR-0062.R17.N1

R1030. Quality, budgets and promotion of `product_engineering` (ADR-0051.R4, ADR-0051.R7, ADR-0051.R9 notes):
- thresholds: golden set 90%; shadow agreement 90%; at least 30 compared cases;
- shadow comparator: per drafted revision, against the revision a person released for the same note or batch within 30 days: component set (item, quantity, unit) and operation set (operation number, work center); equal when every line the agent resolved equals and it resolved at least half of the person's lines;
- per-run ceilings: 30 LLM calls, 150 tool calls, 300,000 input tokens, 20,000 output tokens, USD 2.00, 900 seconds, 5,000 rows per run; no daily budget of its own, the company's daily cap being the only daily tier (ADR-0078.R7).
Source: ADR-0062.R20

R1031. Later than Phase 1: a separate change request (a work item) beside the change order (the proposal); an engineering structure imported from CAD or PLM (STEP AP242 or PLM CSV) linked to the manufacturing structure, with out-of-date detection; reading drawing title blocks and parts lists; similar-drawing search; duplicates by embeddings; proposal references on co-products and by-products; release policies per company.
Source: ADR-0062.R21

R1032. Lab check `t21_product_engineering.py`: pure functions for the resolution order, exactly one hit per step, scoped supplier codes and part numbers, the attribute-token rule and the limit of five candidates, the `new_item_needed` path, the model never introducing numbers absent from its source and bounded spans, estimate gaps that are not zero with split setup and run times, release blocked while proposed items are pending, binding with the unit snapshot, and no cost in L4's input; with `--load`, on the schema of `load_all.py`: a draft bill of materials and routing referring to proposal items by ID, release refused, a header pending again and a revision inserted released both refused, cross-company references refused, then binding and release allowed, and a draft estimate with gaps that cannot be released.
Source: ADR-0062.R23

### Agent type settings: wake-up, drift and analysis examples

R1033. Agent wake-up modes (ADR-0058.R7; ADR-0050.R12, ADR-0050.R16): the setting `agents.<agent_type>.wake_up_mode.<kind>`, scope `agent_type`, values `always`, `by_rule`, `off`, default `always`, so an upgrade changes nothing. `always`: `agent_wake_up` starts the agent. `by_rule`: `agent_wake_up` skips the kind, and only an automation rule with action `start_agent` and its own conditions starts the agent; items no rule starts stay with people. `off`: every item goes to people.
Source: ADR-0063.R11

R1034. Only kinds an agent type version declares `configurable` accept the wake-up setting. The Phase 1 `purchase_invoice` declaration declares `supplier_invoice_received` `configurable` (ADR-0078.R1); the quotation agent's `inbound_message_matched` follows in its next version, when that Phase 2 type is brought forward (ADR-0078.R2). "Configurable" means that the company chooses the mode, with `always` as the default; ADR-0058.R7's "configurable means configured" applies only under `by_rule`. Conditions of such rules read trusted metadata only: the receiving mailbox or channel, the partner matched by address (never by a model), whether the partner is known, branch, document source and attachment type. Narrowing (`by_rule`, `off`) is one person with `edit` on `agent`; widening is a proposal. Hard: no agent wakes an agent; a rule never widens tools, scope, budget or taint handling; no trigger on approval, posting or send events.
Source: ADR-0063.R11

R1035. Drift action (ADR-0051.R5; ADR-0059.R21): the setting `agents.<agent_type>.drift_action`, scope `agent_type`, values `signal`, `pause_new_runs`, `demote_to_shadow`, default `signal`. When the quality monitor raises `agent_quality_below_threshold`, `pause_new_runs` also makes the effective mode `off` for new runs until a person resolves the item, and `demote_to_shadow` makes it `shadow` until the type is promoted again (ADR-0050.R14); until Phase 2, `demote_to_shadow` acts as `pause_new_runs` (ADR-0078.R5). Hard: drift that outdates auto-post evidence always suspends auto-post (ADR-0063.R10); artifacts keep their automatic demotion (ADR-0059.R21).
Source: ADR-0063.R12

R1036. Analysis agent examples (ADR-0060.R25): settings `artifacts.analysis.min_verified_examples` (default 30, bounds 0 to 500) and `artifacts.analysis.allow_synthetic_only_promotion` (default true), company. Below the minimum, with synthetic-only promotion allowed, the evidence is the synthetic CI report and every answer shows "evaluated on the synthetic suite only". When verified examples reach the minimum, the daily evaluation `RunAnalysisEvaluation` starts automatically, which in Phase 1 is the analysis agent's evaluation in use, with no shadow mode (ADR-0078.R6); a result below the threshold raises `agent_quality_below_threshold` and applies the drift action (R1035). Promotion on the synthetic report is accepted by default; a company may require local examples first.
Source: ADR-0063.R13

### Data processing: permissions, personal values and policy schema

R1037. The personal vision seat (ADR-0057.R20, ADR-0057.R21): a company may permit the installation's cloud provider for `extraction_vision_personal` through a `data_processing_permission` row (company, data class, seat class, provider, region, optional `purposes` from `supplier_invoice`, `contact_card`, `inquiry_lines`, `product_source`); default: no row, so the seat is off. The provider registry (DS-37 adapter configuration) holds per provider endpoint `retention_days` (0 for zero retention), `abuse_review` (`human`, `automated`, `none`), `is_training_on_customer_data` (must be false; an endpoint that says true is refused at startup) and `terms_ref` (the data-processing terms in force). A permission records the terms reference and retention it was approved under.
Source: ADR-0063.R14

R1038. The leaf `data_processing` under `agent` (module `agents`) holds `SetDataProcessingPermission` and `EndDataProcessingPermission`, so a data-protection role can approve without the right to manage agents; changes stay four-eyes proposals (ADR-0057.R20). When the registry changes an endpoint's region or terms reference under an active permission, `RunDataProcessingProviderCheck` (at startup and daily) sets the permission's `suspended_at` and raises `data_processing_permission_suspended` for `company_owner`; a suspended permission covers nothing until a new one is approved. Hard: the seat has no tools; `routing_switch` stays the company's kill switch; no sensitive personal data class in Phase 1; images are sent or refused whole. The seat may use the cloud provider under a permission; adding it to spec 17's seat list stays the author's (open question of ADR-0057.R21).
Source: ADR-0063.R14

R1039. One gate for personal values (ADR-0050.R9; ADR-0057.R20): the gateway applies the regime policy and the company's permissions to every request that carries a `personal` value, field values included, not only to whole attachments and the vision seat. Without a permission covering the data class, seat class, provider and region, personal values become typed placeholders or shape masks; a step whose template marks the value required is not sent and the run ends `routing_blocked`. With `routing_switch` on, everything personal is stripped whatever the permissions say.
Source: ADR-0063.R15

R1040. The setting `data_processing.never_send_fields`, company, a list of `table.field` paths, default empty, can only narrow: listed fields are stripped even where permitted. A company whose field-level personal values went to personal seats with the switch off needs its permissions approved; the upgrade raises `setting_review_required` (ADR-0063.R5). Hard: labels from the schema are never lowered; the exact-text residual scan; the log is written before the call.
Source: ADR-0063.R15

R1041. Analysis questions (ADR-0060.R21): the label stays `personal`; a question may name a person, and a pseudonymized question is still personal. The setting `analysis.pseudonymize_known_subjects`, company, default true: before the gateway call, code replaces each match of the company's own personal records that the asker may read (individual and sole-proprietor partners, contacts, employees) with a handle such as `[partner:<id>]`, which the planner may use as a filter value and code dereferences. The processing log records the handles substituted, never the values. Under R1039, the question reaches the router and planner seats when a permission covers them; otherwise placeholders apply, and with the switch on nothing is sent.
Source: ADR-0063.R17

R1042. The data-processing policy schema (ADR-0057.R20; ADR-0053.R1): the regime setting `data_processing.policy` holds per data class `model_processing` (`allowed`, `forbidden`, `company_option`), `cross_border` (`allowed`, `requires_assessment`, `forbidden`, `company_option`), `assessment_kind` (a package code), `assessment_deadline_days` (from the first transfer), `allowed_countries` (an optional list of ISO codes), `max_provider_retention_days`, `requires_no_training`, and `exemptions` (package-declared conditions of core-registered condition types, as ADR-0053.R3's deductibility conditions). The first schema's fields read as the widened ones: `allowed` true or false as `model_processing` `allowed` or `forbidden`, `assessment_for_cross_border` true or false as `cross_border` `requires_assessment` or `allowed`; packages move to the new fields at their next release.
Source: ADR-0063.R18

R1043. The policy schema fails closed, with no core default (ADR-0016.R10). A package may only tighten the core floors (no sensitive personal values in Phase 1, whole images only, logging always on, no provider that trains on customer data). A permission is refused with `data_processing_not_permitted` when its provider's `retention_days` exceeds `max_provider_retention_days` or its country is outside `allowed_countries`. The core holds no country content; country packages state their values.
Source: ADR-0063.R18

R1044. Analysis narrative mode (ADR-0060.R23): the setting `analysis.narrative_mode`, values `facts_only`, `claim_plan`, `free_prose`; the installation value is the maximum and a company may only lower it; default `claim_plan`. `free_prose` is not selectable in Phase 1 (it is outside the bounds); it unlocks for a language and model version only when the evaluation suite shows at least 80% of ordinary sentences accepted and zero accepted sentences with an unbacked number, rank or direction. Even then prose is labelled model-written, shown beside the key facts, and dropped for the claim plan on any unbacked number.
Source: ADR-0063.R25

### Production agent types (Phase 2)

R1045. The production agent capabilities, as capability, agent type, output and whether it runs without a person per run (ADR-0034.R5, ADR-0034.R9, ADR-0034.R12, ADR-0034.R17 fix the safety frame):
- C1 release readiness and shortage triage: `production`; an explanation in a work item note, the verdict is code; yes (read-only).
- C2 component reservation sweep: `production`; reservations through `ReserveProductionOrderComponent`; yes, deterministic, no LLM.
- C3 shortage resolution: `production`; a draft, a drafted change order or a change proposal; no.
- C4 order exceptions and rescheduling: `production`; a draft update or drafted change order; no.
- C5 technical completion and stalled orders: `production`; a change proposal for `CompleteProductionOrder`, or a note; no.
- C6 shop-floor capture: `production_capture` (tainted); draft confirmations, issues and receipts, a person posts; no.
- C7 variance ranking and explanation: `production_variance`; an explanation of checked claims; yes (read-only).
- C8 standards feedback: `production`; a work item with code-computed statistics; no.
Release timing, tolerances, grace days, thresholds, candidate kinds, capture sources and the production import's auto-post and its evidence are registry settings in the shape of ADR-0063, each with a safe default that reproduces today's behavior; only the locks of R1052 are hard.
Source: ADR-0064.D0

R1046. The production agent types of `agents` (layer 5) run on the runtime of ADR-0050 and the common rules of ADR-0051.R1 to ADR-0051.R9; no new module; they read through registered queries and write through the commands of `production`, `inventory`, `planning` and `documents`. The types are Phase 2; the production core and its manual capture stay in Phase 1; `production` reads no outside content, never taints and is the first of them to bring forward when a Phase 2 agent is chosen (ADR-0078.R2). Declarations, as scope kind and subject tables, `may_read_untrusted`, field classes, claimable work item kinds and leaf (capability `start_agent:<type>` at `edit`):
- `production`: `subject` on `production_order`, `production_version`; false; none; `production_component_shortage`, `production_order_exception`, `production_completion_candidate`, `production_order_stalled`, `production_standard_review`; `agent_production`.
- `production_capture`: `subject` on `production_order`, resolved from a `document_extraction` (ADR-0064.R19); true; none; `shop_floor_report_extracted`; `agent_production_capture`.
- `production_variance`: `subject` on `analysis_question`, `production_order`; false; `cost`; none, started by schedule, event or question; `agent_production_variance`.
Source: ADR-0064.R1, ADR-0064.R1.N2

R1047. Seeded templates: `production_planner` holds `agent_production` and `agent_production_variance` at `edit`, `shop_floor_lead` holds `agent_production_capture`, and `chief_accountant` holds `agent_production_variance` (ADR-0054.R24); the owner and IT administrator get them through their `agent` level. Every claimable kind is declared `wake_up: always`, and no type declares `configurable_triggers` (ADR-0050.R12, ADR-0058 note). Taint and promotion evidence stay apart: a tainted capture run never runs the sweep or reads other orders; a clean `production` run never reads a report's free text. These declarations apply when the types are brought forward (Phase 2).
Source: ADR-0064.R1, ADR-0064.R1.N2

R1048. The `production` type has the subject table `costing_sheet`. It drafts costing sheets, site assignments, detailed components and mappings only as change proposals, and rates only from a person's stated source or `GetCostingRateSuggestion`; the model never sees a rate (ADR-0072.R18).
Source: ADR-0064.R1.N1

R1049. Boundary with planning: planned orders, their firming and conversion stay with the `planning` agent (ADR-0051.R23 to ADR-0051.R25; ADR-0036.R12). The production agent works on production orders from `CreateProductionOrder` until they are closed, and no production tool list holds a planned-order command.
Source: ADR-0064.R2

R1050. Common to the production agent types: every quantity, date and amount comes from a deterministic function or is a stated value with its source (a span or an extraction field); every number in model text appears in the step's input (ADR-0050.R36). Workflow code builds each command from a checked output, simulates it, checks the plan, then executes it with the simulated `plan_hash` (ADR-0050.R32). Output schemas are `<AgentType><Step>Output`, version 1.0.0.
Source: ADR-0064.R3

R1051. Modes of the production agent types: `off` (the default), `shadow`, `assisted`, promoted by frozen evidence (ADR-0050.R14). Setting every production agent type to `off` stops a running sweep at its next call boundary, because the runtime checks the effective mode before each tool call (`EC-217`). Runs from events and schedules act for the agent type setting's `workflow_owner_id` (ADR-0050.R14), which names the accountable human per agent type; no `production_owner_id` exists.
Source: ADR-0064.R3

R1052. Hard locks of the production agent types; no setting, policy rule or decision table changes them:
- no agent releases, posts, approves, issues or sends; enforced by tool lists (ADR-0050.R30; `INV-214`, `INV-730`);
- no model-originated quantity, date, price or cost; enforced by output checks (ADR-0050.R36), quantities copied as stated (`INV-733`);
- a tainted capture draft is posted only by a person; enforced by ADR-0043.R9 floor 3 and `is_approval_hold_allowed: false` (`INV-732`; `EC-216`, `EC-209`);
- proposal-bound commands stay proposal-bound: completion, reopen, planned orders, master data and `TransferStockReservation`; enforced by the registry (ADR-0029.R2; ADR-0064.R24);
- no reservation moves from one order to another without an approved change proposal, and no released order's version or revisions change; enforced by ADR-0064.R24 and ADR-0034.R8 (`INV-734`);
- exceptions close only when a deterministic run no longer raises them; agents never close them; enforced by the work item kinds' resolution `system` (`INV-737`).
Source: ADR-0064.R4

## Invariants

`INV-730`, `INV-732` and `INV-737` belong to Phase 2 agent types, which cannot run in Phase 1 (ADR-0078.R2).

Statements are those of `invariants.csv`; this chunk holds the rows whose catalog source names a rule of this chunk first.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-730` | `production_agent_tool_lists` | day (first step: the production core step, number pending author) | No tool list of a `production`, `production_capture` or `production_variance` agent type version holds a posting command, a `Submit`, `Post`, `Approve`, `Issue` or `Send` command, `StartAgentRun`, `TransferStockReservation`, `CompleteProductionOrder`, `ReopenProductionOrder`, `ImportOperationConfirmation` or a planned-order command. | R1046, R1052 |
| `INV-732` | `capture_drafts_posted_by_people` | day (first step: the production core step, number pending author) | Every posted production issue, operation confirmation or production receipt whose version a `production_capture` run wrote was posted by a human. | R1052; ADR-0064.R19 |
| `INV-737` | `production_exceptions_closed_by_runs` | day (first step: the production core step, number pending author) | Every closed `production_order_exception`, `production_component_shortage`, `production_completion_candidate`, `production_order_stalled` and `production_standard_review` work item, and every closed `planning_exception` of the production kinds, was closed by a planning run or `RunProductionOrderCheck`, never by an agent run. | R1052; ADR-0064.R12, ADR-0064.R17 |

## Edge cases

`EC-216` and `EC-217` belong to Phase 2 agent types, which cannot run in Phase 1 (ADR-0078.R2).

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-185` | `wake_up_by_rule` | The purchase invoice agent's `supplier_invoice_received` is set to `by_rule` with a rule on one supplier; an incoming e-invoice record of that supplier starts the agent, one of another supplier stays with people. A Phase 1 case, re-hosted on `purchase_invoice` (ADR-0078.R9a). | `must_succeed` | R1033, R1034; ADR-0063.R11, ADR-0078.R1 |
| `EC-216` | `tainted_capture_draft_policy_auto_approve` | A policy rule would let a tainted capture draft through without a person; floor 3 makes it `human_post`. | `must_succeed` | R1052; ADR-0043.R9 |
| `EC-217` | `production_agents_halted_mid_sweep` | Every production agent type is set to `off` during a sweep; it stops at its next call boundary. | `must_succeed` | R1051 |

## Settings

| Key | Value type | Scopes | Core default | Rule |
| --- | --- | --- | --- | --- |
| `agents.<agent_type>.wake_up_mode.<kind>` | enum (`always`, `by_rule`, `off`) | `agent_type` | `always` | R1033, R1034; ADR-0078.R1 |
| `agents.<agent_type>.drift_action` | enum (`signal`, `pause_new_runs`, `demote_to_shadow`; until Phase 2 `demote_to_shadow` acts as `pause_new_runs`) | `agent_type` | `signal` | R1035; ADR-0078.R5, ADR-0078.R15 |
| `artifacts.analysis.min_verified_examples` | integer (0..500) | `company` | 30 | R1036 |
| `artifacts.analysis.allow_synthetic_only_promotion` | boolean | `company` | `true` | R1036 |
| `data_processing.never_send_fields` | field list (`table.field` paths; can only narrow) | `company` | empty | R1040 |
| `data_processing.policy` | object (schema of R1042) | `regime` (package release) | `fail_closed`, no core default | R1042, R1043 |
| `analysis.pseudonymize_known_subjects` | boolean | `company` | `true` | R1041 |
| `analysis.narrative_mode` | enum (`facts_only`, `claim_plan`; `free_prose` outside the bounds in Phase 1) | `installation`, `company` (installation value is the maximum) | `claim_plan` | R1044 |

The product code settings (R1018) and `production.costing_sheet.required` (R1024) are read from the settings of `master_data` and `production`.

## Conflicts

CONFLICT ADR-0063.R11: the Phase 1 `purchase_invoice` declaration declares `supplier_invoice_received` `configurable`, and the quotation agent's kind waits for that Phase 2 type, governed by ADR-0078.R1 and ADR-0078.R2 (R1034).
CONFLICT ADR-0063.R13: the evaluation that starts at the minimum of verified examples is the daily `RunAnalysisEvaluation` without shadow mode in Phase 1, governed by ADR-0078.R6 (R1036).
CONFLICT ADR-0062.R20: `product_engineering` is a Phase 2 type (ADR-0078.R2) and has no daily budget of its own, governed by ADR-0078.R7 (R1030).
CONFLICT ADR-0062.R2: the rules of `product_engineering` apply when the Phase 2 type is brought forward, governed by ADR-0078.R2 (R1001).
CONFLICT ADR-0064.R1: the production agent types move to Phase 2 and the production core with its manual capture stays in Phase 1, by the later note ADR-0064.R1.N2 (ADR-0078.R2); stated in R1046 and R1047.
CONFLICT ADR-0064.R1.N2: this superseding note of ADR-0078 governs the phase of the production agent types; folded into R1046 and R1047.
CONFLICT ADR-0062.R17: the interim literal scope is replaced by the answered projection `ListItemCandidate` of ADR-0062.R17.N1 (ADR-0063.R16); stated in R1029.
CONFLICT ADR-0062.R9: the interim, flagged product numbering becomes the default of the product code settings by ADR-0062.R9.N1 (ADR-0063.R22); the interim mark is dropped in R1018.

## Trace

| Source | Where |
| --- | --- |
| ADR-0062.R2 | R1001-R1004 |
| ADR-0062.R3 | R1005-R1007 |
| ADR-0062.R4 | R1008 |
| ADR-0062.R5 | R1009-R1011 |
| ADR-0062.R6 | R1012 |
| ADR-0062.R7 | R1013, R1014 |
| ADR-0062.R8 | R1015, R1016 |
| ADR-0062.R9 | R1017-R1019 |
| ADR-0062.R9.N1 | R1018 |
| ADR-0062.R10 | R1020-R1022 |
| ADR-0062.R11 | R1023 |
| ADR-0062.R12 | R1024, R1025 |
| ADR-0062.R12.N1 | R1024 |
| ADR-0062.R13 | R1026, R1027 |
| ADR-0062.R16 | R1028 |
| ADR-0062.R17 | R1029 |
| ADR-0062.R17.N1 | R1029 |
| ADR-0062.R20 | R1030 |
| ADR-0062.R21 | R1031 |
| ADR-0062.R23 | R1032 |
| ADR-0063.R11 | R1033, R1034 |
| ADR-0063.R12 | R1035 |
| ADR-0063.R13 | R1036 |
| ADR-0063.R14 | R1037, R1038 |
| ADR-0063.R15 | R1039, R1040 |
| ADR-0063.R17 | R1041 |
| ADR-0063.R18 | R1042, R1043 |
| ADR-0063.R25 | R1044 |
| ADR-0064.D0 | R1045 |
| ADR-0064.R1 | R1046, R1047 |
| ADR-0064.R1.N1 | R1048 |
| ADR-0064.R1.N2 | R1046, R1047 |
| ADR-0064.R2 | R1049 |
| ADR-0064.R3 | R1050, R1051 |
| ADR-0064.R4 | R1052 |
