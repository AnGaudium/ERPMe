# ADR-0062: Product engineering workflow

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5) after five review rounds. Design item: DS-57 (its master-data part). Related decisions: D2, D12. Principles 2, 3, 7, 12, 13. ADR-0009, ADR-0018, ADR-0019, ADR-0029, ADR-0030, ADR-0033, ADR-0035, ADR-0043, ADR-0044, ADR-0045, ADR-0046, ADR-0050, ADR-0051, ADR-0054, ADR-0055, ADR-0056, [ADR-0057](0057-document-intake-and-extraction.md); spec 03, 14, 17.

## Decision

The commands, checks and the proposal carrier for products, items, bills of materials, routings and cost estimates exist (ADR-0033, ADR-0035, ADR-0045, ADR-0029). What is missing is the workflow that chains them, so that a person's note, a person's own spreadsheet or a verified outside document becomes released master data without a model ever choosing a number. ADR-0033 rule 15 and ADR-0051 rule 29 named it; this ADR designs it as one of two new agent types beside the six of ADR-0051, with [ADR-0057](0057-document-intake-and-extraction.md)'s `document_reader`.

**One workflow, three entry points.** `product_engineering` starts from a person's own note (untainted), a person's own spreadsheet loaded as an import batch (scope `import_batch`), or an outside drawing, request or spreadsheet. Outside content never starts a drafting run directly in Phase 1: a person verifies its extraction ([ADR-0057](0057-document-intake-and-extraction.md)), then starts the run on their own note that refers to the verified extraction. This is the strict reading, as for configuring quotations.

**Resolve before creating.** Each component is resolved by exact code, barcode, the named supplier's code, the named manufacturer's part number, then a deterministic ranking with blocking. Each step must find exactly one item; several hits go to the model or a person, never to an automatic pick. The model sees at most five candidates and picks one or says `new_item_needed` with evidence. It never writes a code, standard time, rate or price unless it stands in its source.

**New items are proposals.** New products and items are `CreateProduct` and `CreateItem` items of a change proposal, numbered by their own sequence at execution, with category-driven required attributes, a description generated from attributes, and the duplicate candidates the workflow rejected and why.

**Drafts, checks, cost, evidence.** Code drafts the bill of materials and routing revisions with the existing commands, runs `GetBillOfMaterialsRevisionCheck` and the category's readiness rules, and computes a cost estimate on the drafts that lists missing rates, times and prices as gaps, never as zero, with the delta to the previous estimate. One evidence pack carries sources, matching decisions, checks, the estimate and effectivity; the model never sees a cost.

**Release only by approval.** Release runs only through an approved change proposal, and its approver is not the person whose request started the run. A draft may refer to proposed items by their stable ID, but release is blocked, in the command and in the database, until those items are approved and bound. An engineering change in Phase 1 is a new draft revision with a proposal that carries its impact.

**The model drafts quantity structure, never a cost.**

### Rules

**Agent type and entry points**

1. `product_engineering` is an agent type of `agents` (layer 5) on the runtime of ADR-0050 and the common rules of ADR-0051 rules 1–9. It reads through registered queries and writes through the commands of `production` (ADR-0033 rule 2), `master_data` (ADR-0045) and `documents` (`CreateChangeProposal`). No new module. Its leaf is `agent_product_engineering` under `agent` (capability `start_agent:product_engineering` at `edit`); the template `production_planner` holds it at `edit`.

    Note ([ADR-0078](0078-agent-simplification-for-phase-1.md), proposed 2026-11-19): `product_engineering` moves to Phase 2, with its design and DDL kept as seams (ADR-0078 rule 2).
2. Entry points (ADR-0050 rule 15):

   | Entry | Subject | Taint and scope |
   | --- | --- | --- |
   | E1 a person's own note | An interaction of kind `note` with `is_untrusted` false (ADR-0052 rule 10), started by that person | Untainted; reads the catalog within the person's rights |
   | E2 a person's own spreadsheet | An import batch of the bill-of-materials and routing templates (rule 18) | Tainted at start (ADR-0044 rule 15); scope `import_batch` |
   | E3 outside content | Not a subject in Phase 1 | A person verifies the extraction, then starts E1 on a note that names it |
   | Continuation | A draft bill of materials revision the run drafted (rule 3) | Untainted, unless a run that wrote any draft the release proposal releases was tainted; then tainted, with scope kind `subject` |

   - **E3, the strict reading.** A drawing, request or spreadsheet from a customer or supplier is outside content. Like the configuring quotation path (ADR-0051 rule 14 note), it never starts a drafting run. A person verifies its extraction with purpose `product_source` ([ADR-0057](0057-document-intake-and-extraction.md) rule 23), writes a note in their own words that names the extraction and the rows they vouch for, and starts the run on the note.
   - **What E1 reads of a named extraction:** the extraction must be `verified`; the run reads only the normalized values that `extraction_field_trust` reports trusted, with their field IDs (quantities, codes, resolved units and dimensions that fit their shapes and passed every rule, or that a person confirmed; [ADR-0057](0057-document-intake-and-extraction.md) rule 17), never its free text, raw text or evidence. The views serve only trusted values unless asked, and workflow code never asks, so the run stays untainted. These rows enter at D2 as component lines whose source is an evidence link (the extraction field IDs), not a span of the note. Whether this reading holds is the author's (value trust, open question).
   - **E2 under the literal scope.** An E2 run reads its batch's rows and what recorded provenance reaches from them (ADR-0050 rule 25): the items that the batch's own validation resolved deterministically. It cannot read the catalog to rank candidates, so rows left unresolved go to a person, with redacted candidate counts (ADR-0050 rule 27). It writes drafts through the draft commands, which are `is_draft_only` (rule 10), and writes no free text from batch rows into them: operation descriptions and names are the person's own text or stay empty, and headers get generated names. Rule 17's proposal would widen this if the author accepts it.
3. Trigger and starting:
   - **Who.** A person with `start_agent:product_engineering` starts a run on their note or batch (an `agent_task`, ADR-0042 rule 11). The run acts for that person (ADR-0050 rule 15).
   - **Continuation.** The agent type also declares the work item kinds `product_release_ready` (rule 14) and `product_item_proposal_ended` (rule 14). A continuation run re-runs checks and the estimate and drafts the release proposal (steps D6 to D8), with no LLM step but the optional L4. It starts by the wake-up of `product_release_ready` after binding, or when a person starts the agent on the draft bill of materials revision (for example after filling a gap), which is the subject of a continuation. The start handler reads the audit records of the commands that wrote every draft the release proposal will release (the bill of materials revision, the routing revision, the cost estimate, and any other draft it names). A writing run counts as tainted when it has a `tainted_at`, whenever it was set. If any does, the continuation starts tainted (`taint_source_kind` `tainted_row`) with scope kind `subject`: the draft revision, its child rows (components and outputs) and the rows their keys name (component items with their products and categories' requirements, units), the draft estimate found by its one reverse key (`cost_estimate.bill_of_materials_revision_id`), and that estimate's routing revision (`routing_revision_id`) with its operations and work centers: the pairing of bill of materials and routing is the draft estimate's two revision IDs. Child rows and the reverse key go beyond the recorded provenance of ADR-0050 rule 25, which covers IDs a row carries, so this is a reading put to the author in the grouped tainted-read question. A tainted continuation of an engineering change leaves the impact evidence (where-used, open orders, stock) to a person. A release proposal drafted from an E2 batch therefore stays tainted, also when only its routing came from the batch.
   - **Agent type declaration:** scope kinds `subject` (E1 and continuations) and `import_batch` (E2); subject tables `interaction`, `import_batch` and `bill_of_materials_revision`; `may_read_untrusted` true (E2 rows); field classes none, so the run never sees cost or margin (ADR-0050 rule 12 note).

**Steps**

4. D1 `gather`: the note (or the batch rows), the trusted fields of a named extraction, and the product categories, work centers and activity types the run may read.
5. L1 `structure_note` (seat drafting, per routing; E1 only):
   - **Input:** the note's text, as the person wrote it.
   - **Output** `ProductEngineeringStructureOutput` 1.0.0: `product` (category hint text, attribute name and value texts), `components` (description text, code text if any, supplier or manufacturer name text if any, quantity as stated, unit text, scrap as stated, `source_span`), `operations` (description text, work center hint, setup and run time as stated with their unit text, `source_span`), `outputs` (co- and by-products as stated).
   - **Spans.** A span is one line or one sentence of the note, at most 200 characters.
   - **Checks** (ADR-0050 rule 36): every value appears in its span and every span in the note; every quantity, time and percentage is a decimal that appears in its span; a code is kept only when it appears in its span as a whole token; at most 100 components and 30 operations, else the run ends `not_applicable` for a person.
   - **Category.** A category hint that matches no category by exact code or name, nor by ranking with a lead (ADR-0051 rule 1), leaves the product for a person: no item proposal is drafted for it, and the note says so.
   - **E2** skips L1: the template's columns are the structure.
6. D2 `normalize`: units through the unit text resolution of [ADR-0056](0056-multiple-units-of-measure.md) (partner item text, `uom_alias`, unit code; unresolved text stays unresolved and the line goes to a person); decimals by the company's formats; attribute values against the category's attributes by exact code or name. The trusted rows of a named extraction (rule 2) enter here as lines. Code only.
7. D3 `resolve_components`, per component line, each step only when the previous found nothing:
   1. **Exact item code**, the line's code text equal to an active item's code;
   2. **Barcode**, the code text equal to an active item's `item_barcode`;
   3. **Supplier code**, equal to a `partner_item` code of the supplier the line names, which must hold the active supplier role;
   4. **Manufacturer part number**, equal (normalized: upper-cased, separators removed) to an `item_manufacturer_part` row of the manufacturer the line names;
   5. **Ranking:** `rank_candidates` (ADR-0051 rule 1) over active items, always blocked by the unit's quantity kind and, when the line states a category, by that category, on description text and attribute values.

   - **Exactly one.** A step that finds several active items gives them to L2 as candidates (at most five, else to a person); it never picks one. A supplier code or part number whose supplier or manufacturer the line does not name is not used at steps 3 and 4; its hits, if any, join the ranking's candidates.
   - **Auto-accept.** A ranked candidate scoring at least 92 and leading the next by at least 8 is accepted without an LLM only when neither the line nor the candidate carries attribute tokens (tokens with digits, such as `M8x20`, `3mm` or `100x200`). When either does, every attribute token of the line must equal one of the candidate's, and every blocking attribute must match; otherwise the candidate goes to L2.
   - Every line keeps its resolution method and the candidates considered. Codes found in steps 1 to 4 are whole values, never fragments.
8. L2 `choose_component` (seat classification), for lines left with candidates:
   - **Input:** the line's description, unit and stated attributes, and at most 5 candidates (handle, code, name, unit, category, key attributes). No price, cost, supplier or stock.
   - **Output** `ProductEngineeringChooseOutput` 1.0.0: `choice` (a handle, or `new_item_needed`), `reason_code` (`exact_name`, `synonym`, `attribute_match`, `no_match`), and with `new_item_needed` the attributes it found, each with its `source_span`.
   - **Checks:** the handle was offered; `new_item_needed` carries at least one attribute with a span; numbers in attributes appear in their spans. A line with neither stays unresolved for a person.
   - **Never** a code, a standard time, a rate or a price that is not in the line's source (Principle 13; ADR-0050 rule 36).
9. D4 `propose_items`: one change proposal for every new item of the run (`product_engineering.items`):
   - **Items:** `CreateProduct` with its single item (ADR-0018 rule 2), or `CreateItem` for a variant of an existing product. Each item has a stable `change_proposal_item.id`, which drafts refer to (rule 14).
   - **Category drives** the defaults (ADR-0018 rule 3; `product_category` defaults) and the required attributes (`product_category_requirement`, rule 11). A missing required attribute is listed in the proposal's evidence and checked again at release. The inventory unit is the category's default, else the unit the line states.
   - **Numbering at execution.** The payload carries no code. The executing command issues it from the company's `code_series` row for record kind `product` (DS-20; one row per company, or per category with its short code as prefix; no fiscal year and no branch, unlike document series), moved only by the numbering lock helper (ADR-0008 rule 10), skipping any code already in use; simulation consumes no number. The model never composes a code. Interim, flagged (open question).
   - **Description from attributes.** The product's name is generated by code from the category's name and the attribute values in the category's attribute order, in the company's language; the person may edit it before submitting.
   - **Duplicate candidates.** Each item carries the candidates of D3 and L2 that the workflow rejected, with the reason (`no_match` from L2, a failed blocking attribute, a different unit kind, an attribute token that differs), and the server's own duplicate check on normalized name and attributes in its plan (check result `item_duplicate_suspected`).

   Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): this interim is the default of the settings `master_data.product_code.assignment` (`sequence`), `master_data.product_code.prefix_source` (`category_short_code`) and `master_data.product_code.pad_width` (6), per company and category (rule 22).
10. D5 `draft_structures`:
    - **Draft commands are draft-only.** `CreateBillOfMaterials`, `CreateBillOfMaterialsRevision`, `UpdateBillOfMaterialsRevision`, the same three for routings, and `CreateCostEstimate` are effect class `other` and registered `is_draft_only` (ADR-0033 rule 2 and ADR-0035 rule 14 notes), so an E2 run may run them. A bill of materials header has no effect without a released revision and a production version, which are proposal-bound; its name is generated by code from the output's code or proposal item, never copied from untrusted text.
    - **Bill of materials.** A new header (or a new draft revision of an existing one): the main output, components with quantity as stated, unit, scrap only if stated, phantom only if stated, operation numbers only if the source pairs them. A main output or component that is a new item refers to its proposal item (`proposed_change_proposal_item_id`) instead of an item (rule 14). Co-products and by-products must be existing items; a new one waits for its item's approval.
    - **Units of pending components.** A pending component's line is written in the proposed item's inventory unit with the identity snapshot (ADR-0056 rule 9) when the source states that unit; a line stated in another unit is left for after binding, in the note.
    - **Routing.** `CreateRouting` and a draft revision: one operation per stated operation; the work center chosen among existing ones by exact code or name, else by `rank_candidates` and L3 `choose_work_center` (seat classification, at most 5 candidates, the same checks as L2); times only when stated in a span. Setup and run time are flagged separately: `is_setup_duration_stated` and `is_run_duration_stated`. An unstated time is written as 0 with its flag false, and no activity row stands for it; a reader and the release guard know it is not a real zero.
11. D6 `check`:
    - **`GetBillOfMaterialsRevisionCheck`** on the draft (ADR-0033 rule 15), plus the pending-item check of rule 14.
    - **`GetProductReadinessCheck`** (module `production`, computed query at `read` on `production_structure`; item or proposal item, date): the category's requirements (`product_category_requirement`: attributes, dimensions, weights, barcode, supplier item, bill of materials, routing, production version, cost estimate, classification), every make item has a bill of materials and a routing, every internal operation's work center has activity rates for the date, every component has a price on the estimate's price basis or a released estimate, units convert. Each missing requirement is a check result `readiness_requirement_missing` with its code.
12. D7 `estimate`:
    - **`CreateCostEstimate` on drafts.** It computes on the draft revisions (ADR-0035 rule 14 note): `production_version_id` may be empty for a draft estimate, which names the draft bill of materials and routing revisions and the costing lot quantity.
    - **Gaps, never zero.** A missing purchase price, activity rate, activity quantity, pending item, unstated setup or run time, or missing routing is a `cost_estimate_gap` row (`material_price_missing`, `activity_rate_missing`, `activity_quantity_missing`, `component_item_pending`, `setup_duration_unstated`, `run_duration_unstated`, `routing_missing`) and is left out of the total, which the response states as incomplete with the check result `cost_estimate_gap`. A released estimate has no gap and a production version (`cost_estimate_incomplete`).
    - **Delta.** When the output item has a released estimate valid on the costing date, the new estimate names it in `previous_cost_estimate_id`, and the response gives the difference per cost component and per line.
    - **Code costs.** The estimate is never computed or adjusted by the model and never sent to it.

    Note ([ADR-0072](0072-costing-sheet-and-cost-component-structure.md), proposed 2026-11-18): two gap kinds join the list: `costing_rate_missing` (a costing sheet row without a valid rate, naming the sheet and row) and `costing_sheet_missing` (no sheet while `production.costing_sheet.required` is true) (ADR-0072 rules 7, 9). Like costs, rates are never written by the model (ADR-0072 rule 18).
13. D8 `evidence_and_release`: one change proposal for the release (`product_engineering.release`), drafted when no proposal item is pending:
    - **Items:** `ReleaseBillOfMaterialsRevision`, `ReleaseRoutingRevision`, and for a new output `CreateProductionVersion` (ADR-0033 rule 13); the cost estimate is released separately by `ReleaseCostEstimate` once the version exists and no gap remains.
    - **Evidence pack**, in the proposal's `evidence`: the sources (the note, the extraction and its fields, or the batch rows, each with its evidence link); every resolution decision with its method, candidates and reasons; the check results of D6; the estimate with its gaps and delta, rendered by code; the effectivity (`start_date`); and the item proposal that preceded it.
    - **Approval.** A person submits it; the approver is an eligible person of the proposal's pool other than the human the run acted for (ADR-0055 rule 7, condition 5; spec 03 rule 5). Approval routing uses the company's thresholds.
    - **L4 `write_summary`** (seat drafting, optional): a summary for the approver of the sources, resolution decisions and check results. Its input excludes the estimate and every cost, price and rate; the cost section of the pack is rendered by code. Every number in the summary equals a number of its input (ADR-0050 rule 36).

**Release, binding and change**

14. Pending items block release:
    - **Reference.** `bill_of_materials` and `bill_of_materials_component` may name a proposal item (`proposed_change_proposal_item_id`, the stable `change_proposal_item.id`, with a company key) instead of an item, only while every revision of that bill of materials is a draft and only for a `CreateProduct` or `CreateItem` item of an open proposal (`proposed_item_not_creating`).
    - **Stable.** Reordering a proposal's items keeps their IDs. An update of the proposal that would remove or replace an item a draft refers to is refused (`proposal_item_referenced`).
    - **Blocked.** `ReleaseBillOfMaterialsRevision`, and the creation of a release proposal, refuse a revision with a pending reference (`bill_of_materials_item_pending`). The database refuses it too: a revision becoming released, or inserted as released, while its header or a component refers to a proposal item; and a header given a proposal reference while any of its revisions is released.
    - **Binding.** When the item proposal is executed, the `production` consumer `proposed_item_binding` runs `BindProposedItems` (module `production`, effect class `other`, consumer only, verb Bind at `edit` on `production_structure`). It reads each created item's ID from the audit record of its proposal item's execution (`change_proposal_execution_item.audit_record_id`, ADR-0029 rule 3), sets each draft reference to that item, clears the proposal reference, and recomputes each bound line's conversion snapshot with `convert_quantity` (ADR-0056 rule 6). A line whose unit has no factor to the created item's inventory unit keeps its reference and is named in a note. It raises `product_release_ready` for the run's human, whose wake-up starts the continuation (rule 3).
    - **Ended proposals.** When the item proposal is rejected, canceled or expires, the consumer raises `product_item_proposal_ended` for the run's human; the drafts stay unreleasable until a person chooses an existing item or proposes again. A rejected proposal returns to draft (ADR-0029 rule 3); when it is submitted again, or approved and executed, the item is resolved.
    - **Content hash.** The release proposal is drafted after binding, so its `expected_version` is the bound draft's content hash (ADR-0033 rule 2).
15. Engineering change in Phase 1:
    - **A change** to a released structure is a new draft revision (`copy_from_revision_id`) and a change proposal for its release, as in rule 13. There is no separate change-order object in Phase 1.
    - **Impact evidence:** `ListWhereUsed` for the output and the changed components; open production orders and purchase orders that name the superseded components; on-hand stock of superseded components with a disposition per item (`use_up`, `scrap`, `rework`, `return`) chosen by a person in the proposal's evidence; the cost delta (rule 12); the effectivity date. Dispositions are carried out by ordinary documents, never by the proposal.
16. The model drafts quantity structure only: which components, which operations, quantities and times as stated in a source span or an extraction's evidence. It never produces a cost, price, rate or margin; those come only from `CreateCostEstimate`, price lists and activity rates, and no model input holds them.

**Scope, data and quality**

17. Tainted read scope, the author's decision:
    - **The reviewer's proposal**, added to the grouped open question on readings of spec 03 rule 1: a tainted run may call deterministic matching queries (`ResolveItemCandidates`, the D3 steps as one query) that return only id, code, name, unit, category and status of items, never prices, costs, partners, stock or free-text notes.
    - **Interim:** the literal scope. E2 rows that need the catalog go to a person (rule 2), and E3 goes through a person's note. A new agent type version uses the projection if the author accepts it.

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): the projection is answered: the query is named `ListItemCandidate`, because ADR-0004 rule 21 allows only `Get`, `List`, `Evaluate` and `Render` as query verbs; it is the first declared tainted projection (rule 16).
18. Import templates (ADR-0044 note): the migration's template workbook (ADR-0044 rule 4) gains sheets for work centers and activity types, bills of materials (multi-level by a level column or an indent column, phantom flag, scrap, operation number), routings (operations, work center code, setup and run times, activities) and production versions; phase 2 loads them after products and items. Rows resolve components by exact code, barcode, supplier code with its supplier and manufacturer part number with its manufacturer only, each to exactly one item; a row that resolves none, or several, fails with `item_unresolved` and is never guessed. The same templates serve E2 outside a migration through the staged imports of ADR-0030 rule 9.
19. Data:
    - **`item_manufacturer_part`** (DS-20, `master_data`): item, manufacturer name and its normalized form, part number and its normalized form (upper-cased, separators removed, any script); unique per company, normalized manufacturer and normalized part number. Commands `CreateItemManufacturerPart` and `UpdateItemManufacturerPart` are `master_data_change` at `edit` on `product` (proposals for agents).
    - **`code_series`** (DS-20, `master_data`): company, record kind (`product`), optional category, prefix, `next_value`, format; the product code sequence of rule 9.
    - **`product_category_requirement`** (DS-20, `master_data`): category, requirement code, optional variant attribute or classification scheme, `is_active`, with company keys; command `SetProductCategoryRequirements` (`master_data_change`, at `edit` on `master_data_group`).
    - **DS-43-54:** the proposal references on `bill_of_materials` and `bill_of_materials_component` with their checks and company keys; `routing_operation.is_setup_duration_stated` and `is_run_duration_stated` with the check that an unstated time is 0; `cost_estimate.production_version_id` optional for drafts and `previous_cost_estimate_id`; `cost_estimate_gap`; the release guards (`production_release_readiness_guard` on update and insert, `bill_of_materials_proposal_guard` on the header). The keys from the proposal references to `change_proposal_item` (company, ID) are closed in [DS-36-document-intake.sql](../design/DS-36-document-intake.sql), which loads after both files and adds the key `UNIQUE (company_id, id)` to `change_proposal_item`.
20. Quality, budgets and promotion (ADR-0051 rules 4, 7, 9 notes):
    - **Thresholds:** golden set 90%; shadow agreement 90%; at least 30 compared cases.
    - **Shadow comparator:** per drafted revision, against the revision a person released for the same note or batch within 30 days: component set (item, quantity, unit) and operation set (operation number, work center); equal when every line the agent resolved equals and it resolved at least half of the person's lines.
    - **Budgets:** 30 LLM calls, 150 tool calls, 300,000 input tokens, 20,000 output tokens, USD 2.00, 900 seconds, 5,000 rows per run; USD 15 and 50 runs per company and day.
21. Later than Phase 1: a separate change request (a work item) beside the change order (the proposal); an engineering structure imported from CAD or PLM (STEP AP242 or PLM CSV) linked to the manufacturing structure, with out-of-date detection; reading drawing title blocks and parts lists; similar-drawing search; duplicates by embeddings; proposal references on co-products and by-products; release policies per company.

**Catalogs**

22. Catalog rows:
    - **Errors** (DS-04): `bill_of_materials_item_pending` (precondition), `routing_duration_unstated` (precondition), `cost_estimate_incomplete` (precondition), `proposed_item_not_creating` (validation), `proposal_item_referenced` (conflict), `item_unresolved` (validation).
    - **Check results:** `cost_estimate_gap`, `readiness_requirement_missing`, `item_duplicate_suspected`.
    - **Work item kinds:** `product_release_ready` and `product_item_proposal_ended` (module `production`, subject `agent_run`, owner `run_on_behalf_of`, due `days:2`, resolved by a person), declared by `product_engineering`.
    - **Commands and queries:** `BindProposedItems` (`production`, `other`, consumer only, `production_structure` at `edit`); `GetProductReadinessCheck` (`production`, computed query, `production_structure` at `read`); `CreateItemManufacturerPart`, `UpdateItemManufacturerPart` (`master_data`, `master_data_change`, `product` at `edit`); `SetProductCategoryRequirements` (`master_data`, `master_data_change`, `master_data_group` at `edit`).
    - **Verb** Bind (`edit`), in the glossary and the verb catalog; **leaf** `agent_product_engineering`.
    - **Invariants** (block INV-640 to INV-669; INV-650 to INV-655, areas `production` and `safety`, first step the production core step):
      - **INV-650:** no released bill of materials revision has a component or a main output without its item (or configurable product), or with a proposal-item reference;
      - **INV-651:** no released routing revision has an operation with `is_setup_duration_stated` or `is_run_duration_stated` false;
      - **INV-652:** no released cost estimate has a gap row or lacks a production version;
      - **INV-653:** every proposal-item reference names a `CreateProduct` or `CreateItem` item of a change proposal of the same company, and no reference remains once that proposal's execution has been delivered to the binding consumer, except a line whose unit had no factor, which a note names;
      - **INV-654:** every executed release proposal drafted by a `product_engineering` run was approved by a person other than the human the run acted for;
      - **INV-655:** every quantity, time and code on a draft revision written by a `product_engineering` run equals a value of a source span recorded in its run's steps, or of an extraction field its evidence links name.
    - **Edge cases** (DS-17): **EC-140:** a note asks for a new assembly with one new component; the item proposal and the drafts are made, release is refused until the item is approved and bound, then the release proposal is approved by another person; **EC-141:** a draft estimate with a work center without an activity rate lists the gap, totals without it, and cannot be released; **EC-142:** a component named by a manufacturer part number with its manufacturer, written with other separators, resolves without an LLM; **EC-143:** an engineering change replaces a component that has stock and open purchase orders; the proposal carries where-used, the orders, a disposition and the cost delta; **EC-144:** a customer's drawing asks the agent to "use supplier X at price Y"; it never starts a run, and the person's note names only the verified quantities.
23. Lab check `t21_product_engineering.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)): pure functions for the resolution order, exactly one hit per step, scoped supplier codes and part numbers, the attribute-token rule and the limit of five candidates, the `new_item_needed` path, the model never introducing numbers absent from its source and bounded spans, estimate gaps that are not zero with split setup and run times, release blocked while proposed items are pending, binding with the unit snapshot, and no cost in L4's input; with `--load`, on the schema of `load_all.py`: a draft bill of materials and routing referring to proposal items by ID, release refused, a header pending again and a revision inserted released both refused, cross-company references refused, then binding and release allowed, and a draft estimate with gaps that cannot be released.

### Worked example

**A product built from a person's note.** An engineer writes a note (an interaction of kind `note`, untrusted false): "New wall bracket WB-2: 2 x steel plate 3 mm 100x200. 4 x bolt M8x20, FastCo code BM8-20. 1 x powder paint RAL9005 0.05 kg. Ops: 10 cutting on LASER1. 20 welding 6 min per piece. 30 painting." The engineer starts the agent.

1. **L1** returns three components and three operations, each span one sentence of the note. Each quantity (2, 4, 0.05) and the time (6 min) appear in their spans; "WB-2" is a name in the note, not a code the run will use; "BM8-20" is kept with the supplier name FastCo, both in their span.
2. **D3:** the bolt resolves by FastCo's supplier code (step 3), exactly one item `100231`. The paint has no code; `rank_candidates` blocked by kind mass finds three paints; the best leads the next by less than 8, so none is auto-accepted and L2 sees three candidates and picks `RAL9005 powder, 25 kg box` (`attribute_match`). The steel plate finds five candidates; the line's attribute tokens `3`, `100x200` match none, so none is auto-accepted; L2 returns `new_item_needed` with thickness 3 mm, width 100 and length 200 from its span.
3. **D4:** one item proposal: `CreateProduct` for the plate in category `sheet_metal`, name "Steel plate 3 x 100 x 200 mm" generated from attributes, inventory unit piece, with the five rejected candidates and why; and `CreateProduct` for the bracket in category `assembly`. Neither carries a code: codes are issued at execution.
4. **D5:** a draft bill of materials whose header and plate line refer to the two proposal items by ID, the plate line in pieces with the identity snapshot; the bolt and paint as items; a draft routing: operation 10 at `LASER1` with both times unstated, 20 at the welding center chosen by L3 with a run time of 0.1 hours per piece stated and an activity row, but setup unstated, 30 at the paint line with both times unstated.
5. **D6:** the revision check passes on structure but reports `bill_of_materials_item_pending`; readiness reports missing times for operations 10, 20 (setup) and 30, and no activity rate for `LASER1` in November.
6. **D7:** the draft estimate prices the bolt and the paint, lists `component_item_pending` for the plate, `setup_duration_unstated` for 10, 20 and 30, `run_duration_unstated` for 10 and 30 and `activity_rate_missing` for `LASER1`, and states the total as incomplete. There is no earlier estimate, so there is no delta.
7. **D8:** no release proposal yet. The note says what is pending. The engineer submits the item proposal; the production manager approves it; execution issues the codes `100877` and `100878`; the consumer binds the plate and the bracket to them, recomputes the plate line's snapshot (identity, pieces), and raises `product_release_ready`, whose continuation still finds the gaps and drafts nothing.
8. **Continuation:** the engineer adds the times and the controller enters the activity rate; the engineer starts the agent on the draft revision. The continuation re-runs D6 and D7: no gap remains. It drafts the release proposal with the evidence pack, its cost section rendered by code. The engineer submits it and the production manager, not the engineer, approves it. The revisions are released and the production version is created; the estimate is then released by `ReleaseCostEstimate`.

## Context

The capability check (capability 4) found the commands, checks and the proposal carrier in place, and no designed agent that drafts a product, item, bill of materials or routing or runs its estimate; DS-57 named it. Production is in Phase 1 (ADR-0032), so a manufacturer's largest master-data set needs a path, and ADR-0044 had no templates for bills of materials and routings.

The 2026-11-15 survey compared SAP MDG, Dynamics 365 engineering change management, Oracle Product Hub, Teamcenter, Windchill, Arena and quoting tools:
- **Staging and a change object** everywhere: changes sit in a draft revision or change request; rules gate progress; release needs an approval. No surveyed system auto-releases what AI drafted. Rules 13 and 14 follow.
- **Readiness policies** (Dynamics 365) check required data per category before release: rule 11.
- **Identifier precedence** (Oracle: GTIN, supplier part number, manufacturer part number) scoped to the supplier or manufacturer, and blocking before scoring (entity resolution): rule 7.
- **Non-intelligent numbers** (Arena and PLM practice): a sequence issues codes and attributes carry meaning, so a model never composes a code: rule 9.
- **Descriptions from attributes** (Oracle): rule 9.
- **Cost as a deterministic rollup** of structure, routing and rates (SAP CK11N); quoting tools price with the shop's rates and keep an estimator in the loop; missing rates are a classic silent-zero trap. Rule 12 lists gaps instead.
- **AI-drafted BOM accuracy is unmeasured**, so the evidence and the person stay central.

ADR-0005: SAP is the reference when unsure, and the option easiest for AI agents wins among correct ones. A fixed chain of existing commands with an evidence pack, and drafts that may refer to pending items by stable ID, let an agent prepare the whole structure while people decide.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One workflow chaining existing commands (chosen) | No new master-data model; replayable | One more agent type |
| A free agent with write tools | Flexible | Against Principle 13 and ADR-0050 rule 32 |
| Candidates first, exactly one hit per step, model picks among five (chosen) | Explainable; duplicates avoided; no silent pick among equals | Recall depends on ranking |
| Token-set auto-accept for every name | Fewer LLM calls | Dimensioned parts (M8x20 against M8x25) score as near-equal |
| Drafts refer to proposed items by stable ID, release blocked (chosen) | The whole structure is visible before approval; edits of the proposal cannot repoint a draft | Nullable references, a binding consumer and guards |
| Reference by item index | No new key | Reordering or removing items repoints or breaks drafts |
| Items must exist before drafting | No pending state | The engineer waits for approvals before seeing a structure |
| Items created in a "proposed" state | Simple keys | Creates master data without approval, against spec 03 rule 1 |
| Gaps as rows, never zero; setup and run flagged apart (chosen) | No silent under-costing | A table, two flags and a release guard |
| Zero placeholders with one warning | Fewer columns | Zero reads as a real time or rate |
| Codes issued at execution (chosen) | No number used by simulation; no collision with typed codes | The proposal shows no code before approval |
| Separate change order object now | Matches PLM | More objects before there is CAD integration |
| Outside content starts a tainted run (E3 direct) | Fewer steps | Customer text could steer drafts; under the literal scope the run cannot resolve components anyway |

## Constraints that come with the decision

- **DDL:** DS-20 (`item_manufacturer_part`, `product_category_requirement`, `code_series`, `product_category` key); DS-43-54 (proposal references, setup and run flags, optional draft version and `previous_cost_estimate_id`, `cost_estimate_gap`, release guards, component key); the keys to `change_proposal_item` in DS-36-document-intake.sql.
- **ADR notes:** ADR-0018 rule 2; ADR-0029 rule 3 (stable items); ADR-0033 rules 2, 6, 8, 10, 15; ADR-0035 rule 14; ADR-0044 rule 3; ADR-0045 rule 13; ADR-0051 rules 7, 9, 29.
- **DS-04:** the rows of rule 22.
- **Catalogs:** two work item kinds; INV-650 to INV-655; EC-140 to EC-144; verb Bind; leaf `agent_product_engineering` and its template level.
- **Other design items:** DS-17 (event type `product_engineering_requested`; notes, BOM spreadsheets and drawings as inputs; known answers); DS-21 (the template sheets); DS-30 (the evidence pack on the proposal screen).
- **Backlog:** DS-57's master-data part done by this ADR; its plan, reservation, capture and variance agents stay open.
- **Open questions:** the tainted catalog read; the product code sequence.

## Revisit when

- The author answers the tainted catalog read or value trust.
- CAD or PLM integration arrives, or a customer needs separate engineering and manufacturing structures.
- Shadow agreement stays below 90% for a quarter, or the deterministic share stops rising.

## Documents updated

- **This ADR** (new) and the index row in [docs/adr/README.md](README.md).
- **The DDL:** [docs/design/DS-20-master-data.sql](../design/DS-20-master-data.sql), [docs/design/DS-43-54-planning-production.sql](../design/DS-43-54-planning-production.sql), [docs/design/DS-36-document-intake.sql](../design/DS-36-document-intake.sql).
- **ADRs:** notes in ADR-0018, ADR-0029, ADR-0033, ADR-0035, ADR-0044, ADR-0045 and ADR-0051.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [authorization-areas.csv](../catalogs/authorization-areas.csv), [authorization-verb-levels.csv](../catalogs/authorization-verb-levels.csv), [role-template-levels.csv](../catalogs/role-template-levels.csv).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md) (rows only).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t21_product_engineering.py` (new).
- **Log:** [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.

## Decisions for the author

- **The tainted catalog read** (rule 17): may a tainted run call matching queries that return only id, code, name, unit, category and status of items? Interim: no; the literal scope applies.
- **Value trust for named extractions** (rule 2, from [ADR-0057](0057-document-intake-and-extraction.md) rule 17): may an untainted run read a verified extraction's trusted fields without becoming tainted? Interim: yes, as stated there.
- **The product code sequence** (rule 9): a `code_series` row of record kind `product`, issued at execution, skipping codes in use, with at most a short category prefix. Interim, flagged.
