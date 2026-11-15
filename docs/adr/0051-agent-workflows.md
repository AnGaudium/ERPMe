# ADR-0051: Agent workflows

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-34. Related decisions: D12, D16. Principles 2, 3, 8, 11, 12, 13. ADR-0003, ADR-0005, ADR-0017, ADR-0019, ADR-0023, ADR-0024, ADR-0029, ADR-0030, ADR-0033, ADR-0034, ADR-0035, ADR-0036, ADR-0041, ADR-0042, ADR-0043, ADR-0044, ADR-0045, ADR-0046, ADR-0047, ADR-0048, [ADR-0050](0050-agent-runtime-and-query-layer.md); spec 03, 13, 14, 17.

## Decision

Six agent types are designed now, each as a code-orchestrated workflow on the runtime of ADR-0050:
- `customer_onboarding`: proposes a new customer and its contacts from an inbound e-mail of an unknown sender;
- `quotation`: drafts a quotation from a customer's request, configuring products through `EvaluateConfiguration`;
- `bank_matching`: reads free-text bank descriptions that the deterministic cascade could not use, and suggests;
- `purchase_invoice`: drafts a purchase invoice from a stored supplier e-invoice and proposes the item mappings it lacked;
- `planning`: explains planning exceptions and drafts the deterministic actions as change proposals;
- `data_migration`: maps columns and old accounts in draft import batches and proposes duplicate merges.

**Deterministic first.** Each step tries stored rules and mappings, then lookups, then fuzzy matching with a deterministic score, and only then an LLM. The LLM never computes a price, tax, quantity, account, match or score. It reads, chooses among candidates that code gave it, and writes text. Code checks every output. A resolution the LLM contributes is proposed as a stored mapping or rule, so the next case is deterministic.

**People decide.** Agents draft documents and change proposals. People submit, approve, post and send. Only the deterministic bank cascade may ever auto-post, under an enabled policy rule with shadow evidence.

**Evidence before trust.** An agent type is `off`, then `shadow` (it runs without effect and is compared with what people did), then `assisted` (it drafts). Promotion needs shadow evidence above a threshold of at least 90%, set per workflow. Payment reminders, a period-close assistant and the production agents come later.

**The literal read scope.** A run that read a customer's e-mail or a supplier's invoice reads only that partner's records, its own drafts and reference data (ADR-0050 rule 27). So in those runs the LLM chooses only among items the partner already has a relation with; other lines go to a person. Tainted quotation runs also skip writing the quotation text, because it would carry server-computed prices to the model (open question). When the author widens the scope (open question), a new agent type version uses it.

### Rules

**Common rules**

1. Deterministic first (Principle 13; spec 14):
   - **Order of each step:** stored rules and mappings → exact lookup → fuzzy match with a deterministic score → LLM for what remains.
   - **Fuzzy acceptance.** `agents.workflows.rank_candidates` scores candidates by `rapidfuzz` token-set ratio on text folded for case and diacritics (ADR-0002). A candidate is accepted without an LLM when its score is at least 92 and leads the next by at least 8. Otherwise the top candidates (at most 5, or 10 where stated) go to an LLM step. The constants belong to the agent type version; changing them is a new version with an evaluation (ADR-0050 rule 12).
   - **What the LLM never does:** compute or choose a price, discount, tax, quantity to post, account, match or score (ADR-0050 rule 36). A stated value (a quantity a customer wrote) is copied as stated, checked against its source span, and shown as stated.
2. Stored resolutions (Principle 13):
   - **Mappings.** An item the LLM chose for a supplier line becomes a `partner_item` change proposal (ADR-0019 rule 6). A token it found in bank descriptions may become a `bank_matching_rule` proposal (rule 19). Column mappings of a migration become the migration's mapping profile (rule 28).
   - **Metric.** The deterministic share (resolved without an LLM ÷ all resolved) is recorded per run and must rise over time (spec 14).
3. Each workflow below states: trigger and scope; inputs; deterministic steps; LLM steps with purpose, input, output schema and checks; outputs; human gates; policy thresholds; shadow metrics and promotion; failure handling. LLM steps use the seats of spec 17. Output schemas are pydantic models named `<AgentType><Step>Output`, version 1.0.0.
4. Modes and promotion (ADR-0050 rule 14; spec 14 "an agent gains permissions only with evidence"):
   - **Into `shadow`.** Allowed once the agent type version passed its golden set (ADR-0003 R8; ADR-0050 rule 39).
   - **Into `assisted`.** The evidence is frozen first: `CreateAgentPromotionEvidence` reads `GetAgentShadowEvaluation` for the company over the shadow period once and stores an immutable snapshot (ADR-0050 rule 14). A proposal for `UpdateAgentTypeSetting` to `assisted` names that snapshot and is rejected with `shadow_evidence_insufficient` unless the snapshot shows all of these: the version in shadow is the version being promoted; at least the workflow's minimum number of compared cases (rule 7) over at least 10 business days; agreement at or above the workflow's threshold; and no case in which the shadow output named a record outside its scope. The snapshot's figures stay with the setting's change, together with `promoted_version` and `promoted_seat_models` (ADR-0050 rule 14); execution only checks that the behavior hash and seat models still equal the snapshot's (`promotion_evidence_stale`). The change runs from a change proposal that a person submits and a person other than the submitter approves (ADR-0050 rule 14).
   - **Down** to `shadow` or `off` is always allowed.
   - **A new version, constants or model.** An assisted agent type whose version, constants (fuzzy thresholds) or seat models differ from the promoted ones runs as `shadow` by the computed effective mode (ADR-0050 rule 14); lowering budgets does not change that. The stored mode stays the person's choice, and no hidden command changes it. The golden set is synthetic, so only real cases show whether a threshold or model behaves the same.
   - **Data migration** is the stated exception: it runs before go-live, so its evidence is a staging rehearsal (rule 28).
5. Quality monitor:
   - **The job.** `RunAgentQualityCheck` (daily system job, `agents`) computes, per company and assisted agent type, the 30-day share of drafts accepted unedited and of drafts rejected or canceled (rule 6).
   - **The signal.** When agreement falls 10 points below the workflow's threshold, it raises `agent_quality_below_threshold` (owner `company_owner`) with the figures. It does not demote by itself; a person decides.
6. Policy and posting:
   - **Agents never submit, post, issue or send** (ADR-0050 rule 30). People submit agent drafts, and the company's policy table applies at their `Submit` and `Post` (DS-28); agents set no discount or manual price.
   - **Tainted drafts** are posted only by a person (ADR-0043 rule 9, floor 3).
   - **Auto-post** exists only for the deterministic bank cascade (rule 18), never for a draft an LLM contributed to (floor 5).
7. Metrics, for shadow comparison and the quality monitor (spec 14 "measuring agent value"):
   - **Agreement:** the workflow comparator's verdict per case: equal, partly equal, different.
   - **Editing:** fields changed between the agent's first version and the version a person submits or approves.
   - **Deterministic share** (rule 2), **LLM cost per case**, **handling time** from raise to resolution against the baseline measured before the agent was enabled, and **defects found later**: documents of the agent's origin work items that were reversed, corrected or canceled after approval.

   Thresholds and minimum cases:

   | Agent type | Golden set (ADR-0003 R8 or higher) | Shadow agreement to promote | Minimum compared cases |
   | --- | --- | --- | --- |
   | `customer_onboarding` | 90% | 90% | 30 |
   | `quotation` | 90% | 90% | 50 |
   | `bank_matching` | 90% | 90% | 100 lines |
   | `purchase_invoice` | 95% | 95% | 50 invoices |
   | `planning` | 90% | 90% | 30 exceptions |
   | `data_migration` | 95% | rule 28's rehearsal criteria | rule 28 |

8. Drafts and keys:
   - **One batch per output.** Each document or proposal is created in one command (or one command batch) at the end of its step, simulated and checked first (ADR-0050 rule 32). A run never leaves half a document.
   - **Draft keys** (ADR-0030 rule 11): `workflow_step` is `<agent_type>.<step_code>` as named below; `draft_ordinal` is 1 unless stated.
   - **Links and notes.** The run links each draft to its work item (`link_kind` `draft`, ADR-0042 rule 3) and writes one work item note saying what it did and what it left. A note that quotes outside content is untrusted.
9. Budgets per run (ADR-0050 rule 22; maximums, which companies may lower). The values are the agent's proposal, flagged for the author, and every daily cost stays below the company cap of USD 50:

   | Agent type | LLM calls | Tool calls | Input tokens | Output tokens | Cost (USD) | Seconds | Rows read | Daily cost per company (USD) | Daily runs |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | `customer_onboarding` | 6 | 30 | 60,000 | 6,000 | 0.30 | 180 | 500 | 5 | 200 |
   | `quotation` | 25 | 80 | 250,000 | 20,000 | 1.50 | 600 | 3,000 | 20 | 200 |
   | `bank_matching` | 3 | 10 | 15,000 | 2,000 | 0.05 | 120 | 100 | 5 | 1,000 |
   | `purchase_invoice` | 15 | 60 | 120,000 | 10,000 | 0.60 | 300 | 2,000 | 15 | 500 |
   | `planning` | 10 | 80 | 200,000 | 10,000 | 1.00 | 600 | 5,000 | 10 | 300 |
   | `data_migration` | 400 | 3,000 | 3,000,000 | 200,000 | 15.00 | 3,600 | 200,000 | 40 | 20 |

10. The literal read scope (ADR-0050 rule 27; ADR-0029 rule 14) in these workflows:
    - **Tainted runs choose among related items only.** A tainted `quotation` run reads items only through the partner's `partner_item_overview` rows and its earlier document lines. A tainted `purchase_invoice` run reads the supplier's `partner_item` and `supplier_item` rows and its open purchase order lines. Lines that need anything else stay unresolved and go to a person.
    - **Configuration** reads the product's model. That is catalog data, so tainted `quotation` runs do not configure (rule 14).
    - **Tainted quotation runs skip L5** (rule 15): the text would carry the draft's server-computed prices and taxes to the model. Such a run still sees them in its own draft's plan (ADR-0050 rule 27); the open question asks the author about both.
    - **Golden answers** follow this scope (ADR-0050 rule 39).
    - **Widening.** If the author widens the scope for quotations (catalog, the partner's price list, available to promise), a new `quotation` version reads them; the same question is asked for purchase invoices (open question).

**Customer onboarding** (spec 13 "intake" and "enrichment"; ADR-0019 rules 4, 15, 19)

11. Trigger, scope and inputs:
    - **Trigger.** A work item `interaction_unmatched` (ADR-0019 rule 15) for an inbound e-mail whose sender authentication passes. The agent type declares this kind. Runs act for the workflow owner (ADR-0050 rule 15).
    - **Scope** `subject`: the interaction, which is outside content, so the run starts tainted (ADR-0050 rule 15). It reads no partner, because none is matched (ADR-0019 rule 15).
    - **Inputs** (`interaction_overview` with `include_untrusted`): sender address and display name, subject, body text, sender authentication; reference data: the package's administrative units and tax ID rules.
12. Steps:
    - **D1 `precheck`.** The message is inbound, its sender authentication passed and it has a body; otherwise the run ends `not_applicable`. The run cannot look for the sender among existing partners itself (its scope is the subject); ADR-0019 rule 15's matching already found none, and the server-side duplicate checks of D2 cover the rest.
    - **L1 `classify_message`** (seat classification with personal data): input the subject and body. Output `CustomerOnboardingClassifyOutput`: `intent` (`new_customer_inquiry`, `existing_partner_new_address`, `supplier_offer`, `spam_or_unrelated`, `other`), `language` (an IETF language tag, checked against the languages of the core and the active packages). Check: enumerations. Anything but `new_customer_inquiry` ends the run `not_applicable` with a note of the intent.
    - **L2 `extract_partner`** (seat classification with personal data): output `CustomerOnboardingExtractOutput`: `partner_kind` (`organization`, `sole_proprietorship`, `individual`, `unknown`; ADR-0053 rule 7), `legal_name`, `trade_name`, `tax_id`, `addresses` (kind, lines, subdivision text, country code), `phones`, `contacts` (name, job title, e-mail, phone, preferred language), and for every value a `source_span` quoted from the e-mail.
      - **Checks:** each value appears in its span and the span in the e-mail (ADR-0050 rule 36); the tax ID passes the package's validation (ADR-0019 rule 4) or is dropped with a note; e-mails and phones are normalized by the package's rules or dropped; the subdivision text maps to an administrative unit code by exact lookup or stays as text; `unknown` kind keeps every field personal (ADR-0019 rule 7).
      - **Code, not the LLM,** adds the sender as the first contact and the sender's domain as the partner's e-mail domain when it is not a public domain.
    - **D2 `propose`.** `CreateChangeProposal` with items `CreatePartner` (role customer; kind, names, tax ID, addresses and e-mail domain as its payload allows) and one `CreateContact` per contact. The server computes the plan, including the duplicate checks of ADR-0019 rules 4 and 19 (`partner_duplicate_suspected`); the run sees them redacted to counts (ADR-0050 rule 27). Step `customer_onboarding.propose`.
13. Outputs, gates and the rest:
    - **Outputs:** the change proposal, a note with the intent and what was left out, and the draft link on the item.
    - **Human gates.** The run creates the proposal as a draft. A person submits it (ADR-0029 rule 3), and a person approves it (always at least the lowest rank, ADR-0043 rule 9, floor 7). The workflow owner, on whose behalf the run acted, cannot approve it (`segregation_of_duties`, ADR-0017 rule 16). After the partner exists, a person confirms the interaction's match (ADR-0019 rule 15) and resolves the item. A person may then run the tax ID lookup of ADR-0019 rule 18 on the new partner; its differences are proposals. The agent calls no outside lookup.
    - **Policy thresholds:** none beyond the floors.
    - **Shadow comparator.** The proposal against the partner a person created and linked to that interaction within 14 days: equal when kind, normalized legal name, tax ID, e-mail domain and the set of contact e-mails all match.
    - **Failures.** `routing_blocked` when the switch is on (the body is personal): the item stays with people. An invalid output stops the run (ADR-0050 rule 35). Suspected duplicates do not stop it; the approver decides.

**Quotation** (spec 13 "quotation"; spec 14 workflow 3; ADR-0046, ADR-0047)

14. Trigger, scope and inputs:
    - **Triggers.** A work item `inbound_message` (raised by `crm` when an inbound e-mail is matched to exactly one partner, ADR-0019 rule 15), or a person who starts the agent on an interaction, which gets an `agent_task` (ADR-0042 rule 11).
    - **Scope** `partner`: the interaction's matched partner (ADR-0050 rule 15), which must hold the active customer role; otherwise no run starts.
    - **Two cases.** An inbound e-mail is outside content, so a run on it starts tainted (ADR-0050 rule 15), also when a person starts it, and works under rule 10. A run a person starts on their own internal note (an interaction with `is_untrusted` false) is not tainted, so it may read the catalog and configure; if it later receives untrusted data, rule 10 applies from then on, and nothing it read before may enter a prompt or the draft (ADR-0050 rule 25).
    - **Inputs:** `interaction_overview` (with `include_untrusted` for an e-mail), `partner_overview`, `contact_overview`, `partner_item_overview`, the partner's earlier lines from `document_line_overview`, `GetCreditExposure`; in untainted runs also `item_overview`, `configuration_model_overview`, `EvaluateConfiguration`, `GetConfigurationEstimate` and `GetAvailableToPromise`. Note: the kind is renamed `inbound_message_matched`; `crm` raises it for messages whose sender authentication passed, matched automatically or by `MatchInteraction` ([ADR-0052](0052-minimal-crm.md) rule 15).
15. Steps:
    - **L1 `classify_message`** (seat classification with personal data): output `QuotationClassifyOutput`: `intent` (`quotation_request`, `order`, `complaint`, `payment_question`, `delivery_question`, `other`), `language`. Anything but `quotation_request` ends the run `not_applicable` with a note.
    - **L2 `extract_request`** (seat classification with personal data): output `QuotationExtractOutput`: `lines` (description text, quantity as stated, unit text, requested date text, `characteristic_hints` as name and value texts, `source_span`), `customer_reference`, `requested_delivery_date`. Checks: spans; each quantity is a positive decimal that appears in its span; dates parse; at most 50 lines (more ends the run `not_applicable`, for a person).
    - **D1 `resolve_items`**, per line:
      1. the partner's own code (`partner_item`) found as a whole token in the line;
      2. an item code or barcode found as a whole token, among the candidates the run may read (rule 10 in tainted runs; the catalog otherwise);
      3. `rank_candidates` over the same candidates (rule 1).
    - **L3 `choose_item`** (seat classification with personal data, since the line text is an extract of the e-mail), only for lines left open with candidates: input the line's text and unit and at most 5 candidates (handle, code, name, units). Output `QuotationChooseItemOutput`: `choice` (a handle or `none`), `reason_code` (`exact_name`, `synonym`, `attribute_match`, `no_match`). Checks: the handle was offered; the line's unit text maps to one of the item's units by the unit tables, else the line keeps the item's sales unit and a note. Lines with `none` stay unresolved.
    - **L4 `configure`** (seat drafting), for lines whose item belongs to a configurable product, in untainted runs only. The model may call one read tool, `evaluate_configuration`; its results come back through the dispatcher's query path and reach the model as labelled context items (ADR-0050 rule 8). Input: the hints and the product's characteristics and allowed values. Output `QuotationConfigureOutput`: values by characteristic code (value code or number). The workflow code calls `EvaluateConfiguration` with them; a violation or missing characteristic is fed back, at most 3 rounds. Checks: every number appears in a hint's span; the final evaluation `is_complete` with no violation. Otherwise the line is drafted with the values that passed, which a draft allows (ADR-0046), and a note lists what is missing. In tainted runs configurable lines are left unresolved with their hints in the note.
    - **D2 `draft_quotation`.** `CreateQuotation` for the scope partner with the resolved lines: item or configuration values, unit and stated quantity. The agent passes no price, discount or tax: the pricing procedure prices the lines (ADR-0047 rule 16) and the tax engine computes taxes. Checks on the simulated plan: every item came from D1 or L3; the partner is the scope partner; no manual price or discount; `price_missing` and other check results go into the note. Step `quotation.draft`.
    - **D3 `checks`.** `GetCreditExposure` for the partner, and in untainted runs `GetAvailableToPromise` per stock line and `GetConfigurationEstimate` for new configurations. Findings go into the note. Margin, below-cost and credit conditions are evaluated by policy at `Submit` (ADR-0043 rule 3), not by the agent.
    - **L5 `write_text`** (seat drafting), in untainted runs only (rule 10): input the customer's name, the draft's lines as priced in its plan, the validity date and the language. Output `QuotationTextOutput`: `cover_text`, `reply_subject`, `reply_body` (at most 4,000 characters). Checks: every number in the text equals a number of the draft (quantity, price, total, date); no other partner's name; no check result `outbound_content_flagged` in the plans of the quotation update and the reply draft (ADR-0050 rule 36). The cover text goes onto the quotation's note, and the reply becomes an outbound message draft (ADR-0019 rule 17) on the same work item, step `quotation.reply`.
16. Outputs, gates and the rest:
    - **Outputs:** the quotation draft, the reply draft, a note listing unresolved lines and findings, and the links.
    - **Human gates.** A salesperson reviews, completes the unresolved lines, and submits the quotation (a policy point with discount, margin, below-cost and credit conditions, ADR-0043 rule 3). A person sends the reply; the gate checks consent and content (ADR-0019 rule 17).
    - **Policy thresholds** are the company's rules on quotation submit; the agent sets none.
    - **Shadow comparator.** Per quotation, against the quotation a person created for the same interaction: line agreement on item or configuration hash, unit and quantity. A case is equal when every line the agent resolved is equal and it resolved at least half of the person's lines. Free text is scored by the eval judge on the golden set only.
    - **Failures.** Unresolved lines are a normal result. `routing_blocked`, invalid output and budgets follow ADR-0050 rule 17.

**Bank matching** (spec 14 workflow 4; ADR-0048 rules 8–9)

17. Trigger, scope and steps:
    - **Trigger.** A work item `bank_line_unmatched` (ADR-0048 rule 9), which the agent type declares. Runs act for the workflow owner (ADR-0050 rule 15).
    - **Scope** `subject`: the statement line, which is outside content, so the run starts tainted (ADR-0050 rule 15).
    - **Inputs:** `bank_statement_line_overview` for that line, with `include_untrusted`.
    - **D1.** The cascade already ran at import and found nothing, which is why the item exists.
    - **L1 `read_description`** (seat classification with personal data, because descriptions are personal, ADR-0050 rule 9): output `BankMatchingReadOutput`: `reference_tokens` (at most 5), `payer_name_text`, `stable_payer_token`, `purpose` (`invoice_payment`, `advance`, `refund`, `salary`, `tax`, `bank_charge`, `internal_transfer`, `loan`, `unknown`). Checks: every reference token is a whole token of the description and reference-shaped as rule 18 requires, or it is dropped; the payer name and the stable token are substrings of the description after folding, at least 3 characters long.
    - **D2 `record_suggestion`.** `RecordBankLineSuggestion` (module `cash`, effect class `other`, `is_draft_only`) stores the tokens, name, purpose and run on the line, all `is_untrusted`, and emits `BankLineSuggestionRecorded`, which carries IDs only (ADR-0013 rule 4). Step `bank_matching.suggest`. The run then ends `drafted` or `no_action`. It never matches, posts or reads partners.
18. The deterministic follow-up and auto-post:
    - **Re-run of the cascade.** A `cash` consumer of `BankLineSuggestionRecorded` runs `match_bank_line` once more, with the suggested tokens added as reference tokens at step 2 only, under step 2's guards: each token must be a whole token of the description and reference-shaped, at least four characters with a digit or the package's pattern for its invoice numbers (ADR-0048 rule 9), and all the items its tokens name must belong to one partner. If it finds items of exactly one partner, it drafts the receipt or payment as ADR-0048 rule 9 does, as `system` on behalf of the run's human (ADR-0013 rule 9), marked `match_basis` `llm_suggestion` and with no score. The draft carries the run as its origin, so it is tainted (ADR-0029 rules 8, 12) and a person posts it (ADR-0043 rule 9, floors 3 and 5). Its data never returns to the run.
    - **Auto-post** applies only to cascade matches with a score and no LLM contribution, under an enabled rule (ADR-0048 rule 9; ADR-0043 rule 14). Its shadow evidence is `GetAutoPostShadowEvaluation` (module `cash`; document types, score floor, amount maximum, date range): of the cascade's proposals at or above the floor and below the maximum in the range, the share that people posted unchanged. `EnablePolicyRule` for such a rule obtains that result through an evidence hook that `policy` declares and `cash` registers for its document types, wired by `app` (layer 6), so `policy` imports no layer-4 module. It stores the result and is rejected with `shadow_evidence_insufficient` unless it covers at least 300 proposals over at least two statement months, with at least 99% posted unchanged and no proposal posted to another partner.
19. Rules, gates and the rest:
    - **Rule proposals.** When a person posts a document matched to a line that carried a `stable_payer_token`, or matches such a line by hand, a `cash` consumer creates a `bank_matching_rule` change proposal as a draft (token → that partner; it never submits it) if the token appears in at least two of that partner's lines in the last 90 days and in no other partner's lines. The proposal copies an untrusted token, so its version is written tainted, as a version derived from untrusted content (ADR-0029 rules 8, 10), a person submits it (ADR-0029 rule 3), and a person approves it (ADR-0029 rule 5).
    - **Human gates.** A person posts the drafted document or matches the line, which resolves the item; a person approves rule proposals.
    - **Shadow comparator.** A shadow run records its tokens but nothing persists, so no consumer runs. The comparator runs the pure `match_bank_line` on the line with the shadow tokens added at step 2, under the same guards as rule 18, and compares its proposal with the person's final match: equal when partner and settled items are equal. A proposal of nothing counts as different when the person matched the line to an invoice.
    - **Failures.** No usable token: a note, outcome `no_action`. With the routing switch on, descriptions are personal and L1 cannot be sent, so every run ends `routing_blocked` (ADR-0050 rule 9).

**Purchase invoice** (spec 14 workflow 1; ADR-0047 rules 12–14; ADR-0041 rule 10)

20. Trigger, scope and inputs:
    - **Trigger.** A work item `supplier_invoice_received`, raised for a stored incoming e-invoice record (`e_invoice_record`, DS-24's pending table). The incoming intake is the e-invoice add-on (DS-24). Until it exists, the same record is created when a person imports an XML file through the package's reader, and the agent starts from that. The agent never parses a raw attachment itself.
    - **Scope** `partner`: the supplier whose normalized tax ID equals the record's verified seller tax ID, when exactly one active supplier has it (ADR-0050 rule 15), and only if the record's signature check passed (DS-24's reader). Without a passed signature check, a run starts only after the person who imported the record has confirmed its supplier on the record. Otherwise `StartAgentRun` fails with `agent_scope_unresolved` and the item stays with people (the supplier may need onboarding).
    - **Taint.** The record's structured fields (seller tax ID, the fields of the package's supplier-invoice key, ADR-0030 rule 10, dates, amounts, rates) are not untrusted; its free text (item names, notes) is (ADR-0029 rule 10). The record is outside content, so the run starts tainted (ADR-0050 rule 15).
    - **Inputs:** the record's header and lines, `partner_overview`, `partner_item_overview` (the supplier's `partner_item` and `supplier_item` rows), the supplier's open purchase order lines from `document_line_overview` with ordered, received and invoiced quantities.
21. Steps:
    - **D1 `check_record`.** The status check of the reader (DS-24); the signature check, or the person's supplier confirmation, was already required to start (rule 20). The duplicate key (ADR-0030 rule 10; ADR-0047 rule 12): the draft's simulation returns `duplicate_external_document`, and the run ends `not_applicable` naming the existing document, which is in scope.
    - **D2 `map_lines`.** Per line: the supplier's item code against `partner_item`; else the supplier's `supplier_item` code; else `rank_candidates` over the supplier's related items (rule 10). The unit maps through `partner_item`'s unit, else the unit tables.
    - **L1 `choose_item`** (seat classification; the personal seat when the supplier is an individual or a sole proprietorship, ADR-0050 rule 9), for unmapped lines: input the line's name and unit and at most 10 candidates from the supplier's related items. Output `PurchaseInvoiceChooseItemOutput`: `choice` (handle or `none`), `reason_code`. Checks: the handle was offered; the line's unit converts to one of the item's units; otherwise `none`.
    - **D3 `select_order_line`**, per mapped goods line: the purchase order named in the record's order reference, if any, and its line for the item; else the only open line for the item; else the oldest open line whose received but uninvoiced quantity covers the line; else unresolved. Pure, on canonical order (date, then ID).
    - **D4 `draft_invoice`.** `CreatePurchaseInvoice` with the header from the record (supplier, `partner_reference`, `supplier_invoice_date`, currency, rate as stated) and the resolved lines: `goods` lines with their order line, quantity, unit price and the supplier's stated tax copied from the record (ADR-0041 rule 10). Unresolved lines are not drafted. Checks on the simulated plan: lines and order lines come from D2, L1 and D3; header totals equal the record's when nothing was left out, else the note gives the difference; the three-way match results (`match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt`) go into the note. Step `purchase_invoice.draft`.
    - **D5 `propose_mappings`.** One change proposal with a `CreatePartnerItem` item for each line L1 resolved, with the record as evidence. Step `purchase_invoice.mapping`.
22. Outputs, gates and the rest:
    - **Outputs:** the draft invoice, the mapping proposal, a note with unresolved lines, differences and check results.
    - **Human gates.** An accountant completes, submits and posts the invoice. The three-way match condition `is_match_exceeded` requires approval (ADR-0047 rule 14); a tainted draft needs a person to post (ADR-0043 rule 9). The run creates the mapping proposal as a draft; a person submits it (ADR-0029 rule 3), and a person other than the workflow owner approves it, after which the next invoice maps deterministically.
    - **Policy thresholds:** the company's purchase invoice rules (amount, `is_match_exceeded`, direct expense).
    - **Shadow comparator.** Against the purchase invoice posted with the same supplier invoice key: per line, item, order line, quantity and unit; equal when all drafted lines are equal and the header matches.
    - **Failures.** No supplier, or more than one: no run. An unreadable record: `not_applicable`. Unresolved lines are normal.

**Planning** (ADR-0024 rule 23; ADR-0036 rules 11–12)

23. Trigger, scope and inputs:
    - **Triggers.** Work items `planning_exception` and `capacity_overload` (ADR-0042 rule 18), which the agent type declares, and runs a planner starts on an item and warehouse.
    - **Scope.** The data is internal; the agent type declares `may_read_untrusted: false`, so its runs never become tainted (ADR-0050 rule 28) and read within the permission intersection.
    - **Inputs:** the exception, `ListPegging`, `GetProjectedAvailability`, `planned_order_overview`, `demand_supply_overview`, `stock_overview`, `GetAvailableToPromise` for other warehouses, `partner_item_overview` for supplier terms, `ListCapacityLoad`, `GetCapacityLevelingProposal`, `forecast_accuracy`.
24. Steps:
    - **D1 `gather`:** pegging, projection and the planned orders involved.
    - **D2 `candidate_actions`**, computed by code from the exception code, each with its effect on the projection:
      - a shortage inside lead time: firm and convert the proposed planned order now; or a stock transfer from a warehouse whose available to promise covers it;
      - supplier minimums or container fill: the consolidation of planned orders inside the conversion window that meets the minimum (ADR-0024 rule 23);
      - capacity overload: the leveling proposal's new dates (ADR-0036 rule 12);
      - a missing parameter, or a lead time that differs from the median of the last 10 receipts by more than 20%: a parameter change with that evidence.
    - **L1 `explain`** (seat analysis): input the exception facts, pegging rows, projection buckets and the candidates with their computed effects. Output `PlanningExplainOutput`: `explanation` (at most 1,200 characters), `recommended` (a candidate handle or `none`), `reason_codes`. Checks: the handle was offered; every number in the text appears in the input.
    - **D3 `propose`.** One change proposal with the recommended candidate's commands (`UpdatePlannedOrder`, `FirmPlannedOrder`, `ConvertPlannedOrder`, which are proposal-bound, ADR-0036 rule 12; or a parameter or lead-time update, ADR-0024 rule 23), with pegging and projection as evidence and the explanation as the reason. With `none`, only the note. Step `planning.propose`.
25. Outputs, gates and the rest:
    - **Outputs:** the proposal and a note with the explanation.
    - **Human gates.** The run creates the proposal as a draft. A planner submits it (ADR-0029 rule 3), and a planner other than the human the run acted for approves it (ADR-0017 rule 16); the executing consumer converts, and the drafts it creates follow their own approval (ADR-0024 rule 22). Sending to a supplier stays a separate approved step.
    - **Policy thresholds:** proposals always need approval (ADR-0043 rule 9, floor 7); automatic conversion stays an open question (ADR-0043 rule 17).
    - **Shadow comparator.** The recommended action against what the planner did on the same exception before it closed: equal when the action type, the planned order and the quantity and dates are equal.
    - **Failures.** No candidate: explanation only, outcome `no_action`.

**Data migration** (spec 14 workflow 2; ADR-0044 rule 15)

26. Trigger, scope and inputs:
    - **Trigger.** A person starts the agent on a draft import batch of a migration in `draft` or `loading` (`agent_task`; `start_agent:data_migration`).
    - **Scope** `import_batch` (spec 03 rule 1). The batch is outside content, so the run starts tainted (ADR-0050 rule 15; ADR-0044 rule 15).
    - **Inputs:** `import_row_overview` of the batch with raw values, the import template's schema for the batch's phase (registry metadata), the migration's mapping profile (outside the batch: a reading flagged with ADR-0050 rule 27), and reference data (ADR-0050 rule 27): the package chart template, units, currencies, administrative units, tax ID rules.
27. Steps:
    - **D1 `map_columns`:** exact header match to template field paths; then the core and package synonym lists; then the migration's mapping profile for the same old system and header.
    - **L1 `map_columns`** (seat data migration), for headers left: input header names, five sample values per column and the target fields (path, meaning, type). Output `DataMigrationMapColumnsOutput`: per column, a field path or `none`, and a transform (`none`, `date_dmy`, `date_mdy`, `decimal_comma`, `decimal_point`, `split_code_name`). Checks: each path is a field of the phase's template; one field takes at most one column; at least 95% of the sample values parse with the transform; otherwise `none`.
    - **D2 `normalize`:** tax IDs, phones, addresses (administrative unit codes), dates and decimals by the package's and core's rules. Values that fail stay raw with a row error.
    - **D3 `map_accounts`:** old account codes equal to a package chart template code map directly.
    - **L2 `map_accounts`** (seat data migration), for old accounts left: input the old code and name and at most 10 template accounts by `rank_candidates`. Output `DataMigrationMapAccountsOutput`: `choice` (handle or `none`). Checks: the handle was offered. Accounts that need a company split stay for a person (ADR-0044 rule 6).
    - **D4 `find_duplicates`:** rows of the batch with an equal normalized key (tax ID, e-mail, code), and pairs whose name score is between 85 and 95.
    - **L3 `judge_duplicates`** (seat data migration), for the pairs in that band: output `DataMigrationDuplicateOutput`: `verdict` (`same`, `different`, `unsure`), `reason_code`. Checks: enumerations.
    - **D5 `update_batch`.** `UpdateImportBatch` (DS-21's command on draft batches, `is_draft_only`) writes the mapping, the normalized values, the old account map and the merge suggestions for pairs that are equal by key or judged `same`; each suggestion raises `import_duplicate_suspected` for the batch's creator. The migration's mapping profile is updated in the same batch. Then `ValidateImportBatch` simulates the batch (ADR-0044 rule 5); its errors go into the note. Duplicate checks against existing company partners return redacted (ADR-0050 rule 27). Step `data_migration.update`.
28. Outputs, gates and the rest:
    - **Outputs:** the updated draft batch, the mapping profile, duplicate work items, the validation result and a note.
    - **Human gates.** A person reviews the batch, decides merges, and runs it (`RunImport`, `human_only`); only a person completes or reverses a migration (ADR-0044 rules 5, 12, 14).
    - **Policy thresholds:** none; import chunks are consequence postings of the person who runs them (ADR-0043 rule 5).
    - **Personal data.** Contacts in import files are personal, so their column samples go only to the data migration seat, class `personal`. With the switch on, they are replaced by shape masks (character class and length, ADR-0050 rule 9), so L1 maps those columns from their headers and shapes; ADR-0044 rule 16's local model waits for the author's answer.
    - **Promotion evidence, the stated exception to rule 4.** Migration runs before go-live, so production has no shadow cases. The evidence is a staging rehearsal (ADR-0003 R12; ADR-0044 rule 1) with the agent in `shadow` on the version being promoted, meeting all of these:
      - it covers every phase's batches of one complete rehearsal;
      - at least 95% of the agent's column mappings and 95% of its old-account mappings equal those of the batches the person ran, over at least 100 mapped columns;
      - no shadow output read or wrote outside its batch;
      - the rehearsal's reconciliation passed (ADR-0044 rule 11).

      The rehearsal's `evaluation_report.json`, with the hash of the staging snapshot it ran on, is attached to `CreateAgentPromotionEvidence`, which freezes its figures and version in the snapshot instead of reading `GetAgentShadowEvaluation`; the change proposal for `UpdateAgentTypeSetting` names that snapshot. The person who submits the proposal vouches for the report, and a person other than the submitter approves it.
    - **Failures.** A batch larger than the run's row budget is handled in several runs, each on a range of rows; budgets stop a run cleanly between ranges.

**Later agents**

29. These agents come later, each designed by its own ADR before its step, on ADR-0050 and the common rules here:
    - **Payment reminders:** reminder drafts from `RunDunning` (ADR-0048 rule 17) with text written in the customer's language, sent by a person.
    - **Period-close assistant:** runs the close checklist queries, reconciles, explains differences and flags anomalies, with the analysis seat; untainted, read-only plus notes.
    - **Production** (design item DS-57, before the production core step; ADR-0032 rule 5): plan proposals, shortages and variances: reservations of components (`ReserveProductionOrderComponent`, which ADR-0034 lets the production agent run directly), the capture agent's tainted drafts of confirmations (ADR-0034 rule 12), the variance agent's ranking (ADR-0035 rule 15), and the master-data workflow that drafts bills of materials and routings and proposes their release (ADR-0033 rule 15).
    - **Others:** the warehouse agent's proposals for putaway rules, pick-face levels and count plans (ADR-0023 rule 21), repeat-sales suggestions and quotation follow-ups (spec 13).

**Catalogs**

30. Catalog rows:
    - **Work item kinds:** `inbound_message` (`crm`, interaction, `role:sales`, `days:1`, person); `supplier_invoice_received` (`purchasing`, `e_invoice_record`, DS-24's pending table, `role:accountant`, `days:2`, person); `agent_quality_below_threshold` (`agents`, agent type, `company_owner`, `days:5`, person); `import_duplicate_suspected` (`imports`, import row, `document_owner`, `days:1`, person). `inbound_message` is renamed `inbound_message_matched` ([ADR-0052](0052-minimal-crm.md) rule 15).
    - **Commands and queries:** `RecordBankLineSuggestion` (`cash`, `is_draft_only`); `RunAgentQualityCheck` (`agents`, system job); `GetAgentShadowEvaluation` (`agents`, ADR-0050 rule 41); `CreateAgentPromotionEvidence` and `GetAgentTypeSetting` (`agents`, ADR-0050 rule 14); `GetAutoPostShadowEvaluation` (`cash`) with the evidence hook of rule 18; `UpdateImportBatch` (`imports`, DS-21, `is_draft_only`).
    - **Error:** `shadow_evidence_insufficient` (precondition, not retryable): a promotion to `assisted`, or the enabling of an auto-post rule, lacks the evidence rules 4 and 18 require.
    - **Edge cases** (DS-17):
      - **EC-79:** a quotation e-mail asks the agent to add another customer's prices and to send the quotation at once; the run stays in its scope, any out-of-scope read is refused, and nothing is sent;
      - **EC-80:** an e-mail from an unknown sender whose tax ID belongs to an existing partner; the proposal carries the redacted duplicate check, a person rejects it, and an approval by the workflow owner would fail with `segregation_of_duties`;
      - **EC-81:** a supplier e-invoice line without a mapping; the agent chooses among the supplier's items, the mapping is proposed, and after approval the next invoice maps without an LLM;
      - **EC-82:** a bank line whose description names an invoice in free text; the suggestion leads to a tainted draft without a score, which an enabled auto-post rule does not post;
      - **EC-83:** a quotation run whose worker crashes after an LLM call; the retry replays the recorded step and drafts once.
    - **DS-17 event:** `customer_inquiry_received` (an e-mail from an unknown sender, step 5), in the sales group.

## Context

Spec 14 names four first workflows and the planning agent; ADR-0032 adds a production agent. ADR-0003 R8 defines "done" for step 10 on the synthetic dataset and lets this ADR raise the 90% threshold. Earlier ADRs left workflow obligations here: change proposals for non-document changes (ADR-0029), draft keys (ADR-0030 rule 11), shadow evidence and unattended postings (ADR-0043 rules 5, 14), the bank matching agent (ADR-0048), the configuring quotation agent (ADR-0046), the planning agent (ADR-0024 rule 23, ADR-0036 rule 12) and the migration agent (ADR-0044 rule 15).

The literal read scope is the main constraint. Spec 14 has the LLM map item descriptions in quotations and supplier invoices, which needs the catalog, while spec 03 rule 1 limits a run that read a customer's e-mail to that partner's records. Until the author decides, this ADR keeps the floor and lets the LLM choose only among items the partner already has a relation with. A person's own notes do not taint, so a salesperson can still get full drafting from notes.

SAP practice, concepts only: intelligent scenarios in S/4HANA (cash application, invoice matching) learn from accountants' decisions and propose; postings stay rule-based with tolerance groups. ERPMe stores what was learned as visible rules and mappings instead of a hidden model (spec 03 rule 9).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Code-orchestrated steps with LLM choices among code's candidates (chosen) | Deterministic, replayable, checkable; LLM cannot invent records | Lower recall where candidates miss the right item |
| Free agent with tools | Flexible | Against Principle 13; hard to replay; injection reaches decisions |
| Literal read scope now, wider version after the author decides (chosen) | Keeps the hard floor | Fewer resolved lines in tainted runs |
| Read the catalog in tainted runs now | Better drafts | Relaxes a hard floor without the author (ADR-0005 item 7) |
| Bank suggestion recorded, cascade re-run by a consumer (chosen) | The run never sees partners; the draft is deterministic and tainted | One more consumer |
| LLM proposes the match directly | Simpler | Reads other partners' items; its output would score |
| Shadow before assisted, with a minimum of cases (chosen) | Evidence, not impression (spec 14) | Slower start per company |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0019 rule 15: matched inbound messages raise `inbound_message`;
  - ADR-0023 rule 21, ADR-0033 rule 15, ADR-0034 rule 17, ADR-0035 rule 15: their agents are later agents of rule 29;
  - ADR-0024 rule 23 and ADR-0036 rule 12: the planning agent of rules 23–25;
  - ADR-0029 rule 14: rule 10's effects and the question for purchase invoices;
  - ADR-0030 rule 11: workflow step codes;
  - ADR-0042 rule 18: the new kinds;
  - ADR-0043 rule 5: the bank cascade's auto-post is the only unattended workflow posting; rule 14: the evidence of rule 18;
  - ADR-0044 rule 15: rules 26–28 and `UpdateImportBatch`;
  - ADR-0046 rule 8: the configuring loop of rule 15;
  - ADR-0048 rule 9: the suggestion and the re-run of rule 18;
  - ADR-0032 rule 5: the production agent as DS-57.
- **DS-04:** `shadow_evidence_insufficient`; the commands and queries of rule 30.
- **Backlog:** DS-57, the production agent.
- **Catalogs:** the four kinds; EC-79 to EC-83.
- **DS-17:** the event `customer_inquiry_received`; input e-mails for onboarding and injection cases; the known answers of each golden set.
- **DS-21:** `UpdateImportBatch` and the mapping profile. **DS-24:** the stored incoming e-invoice record and its reader. **DS-35:** the outbound message draft and the interaction confirmation commands.
- **Open questions:** the same read-scope question for purchase invoices; the purchase invoice agent's dependency on the e-invoice add-on.

## Revisit when

- The author answers the read-scope question.
- The deterministic share of a workflow stops rising for three months, or a workflow's shadow agreement stays below its threshold for a quarter.
- DS-24 builds the incoming e-invoice intake, or vision models are wanted for scanned invoices.

## Documents updated

- **ADRs:** notes in [ADR-0019](0019-partners-and-crm-foundation.md), [ADR-0023](0023-warehouse-management.md), [ADR-0024](0024-planning.md), [ADR-0029](0029-proposals-and-agent-safety.md), [ADR-0030](0030-commercial-seams-and-imports.md), [ADR-0033](0033-production-master-data.md), [ADR-0034](0034-production-orders-and-shop-floor.md), [ADR-0035](0035-production-costing.md), [ADR-0036](0036-multi-level-mrp.md), [ADR-0042](0042-work-queue.md), [ADR-0043](0043-policy-and-approval.md), [ADR-0044](0044-data-migration-and-export.md), [ADR-0046](0046-product-configuration.md), [ADR-0048](0048-cash-bank-receivables-payables.md).
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [edge-cases.csv](../catalogs/edge-cases.csv).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
