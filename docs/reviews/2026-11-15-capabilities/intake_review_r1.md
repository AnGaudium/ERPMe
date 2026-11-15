# Review r1: ADR-0057 Document intake and extraction; ADR-0062 Product engineering workflow

Date: 2026-11-15. Reviewer: independent (read-only). Base: holistic-review 32e7b1c + ADR-0056 draft (snapshot `ds-uom.bak-r2`) + `drafts/ds-intake/apply_intake.py`.

## Verdict: NOT YET

3 blocking, 19 should-fix, 16 nits.

Lab on the review copy (own database, dropped afterwards): t20 105/105, t21 68/68, t12 186/186, t16 99/99, all with `--load`. One first run of t12 and t16 failed with `out of shared memory` and passed on rerun; other sessions were using the same container, so I count it as transient. Findings marked "probe" were executed against the loaded schema in rolled-back transactions.

File references: `0057`, `0062` and `DS-36` are the drafts in `drafts/ds-intake/` (same line numbers as applied); other files are the applied review copy.

## Blocking

**B1. Value trust widens the floor for string-shaped types.** 0057:138 (rule 17), 0057:141, DS-36:135-136, t20 `is_untrusted` (line 168), 0062:35.
- Rule 17 trusts every field whose `value_type` is not `text` once "every validation rule passed". For `code`, `unit`, `url`, `email`, `phone`, `bank_account` and `currency` no rule bounds the content, and for purposes `inquiry_lines` and `product_source` rule 14 lists no rule at all, so the condition is vacuously true.
- Probe: a `parsed` field of type `code` holding a 560-character instruction, with empty `rule_results`, is accepted with `is_untrusted` false; the same for `url`, `unit` and `email`. A `human` row may also change a path's type from `text` to `code` and become trusted.
- It contradicts the precedent it cites: ADR-0051 rule 20 (line 181) keeps `seller_item_code` and `unit_text` untrusted. So the claim "narrows rather than widens" (0057:141) is wrong for codes and units, and it extends the rule from signed XML to OCR of attacker-made pixels and to outside spreadsheets.
- Flow: an outside RFQ spreadsheet reaches `extracted` with no person; its `code` and `unit` cells are trusted; an E1 run (untainted, full catalog read) reads them (0062:35) and passes the unit and code text to L2.
- Fix: (a) trust needs a closed shape per type, checked as a mandatory rule: decimals, dates, ISO currency, tax ID and IBAN by check digit, `code` by a short length and a fixed character set without whitespace, `unit` only as a resolved unit code; `url`, `email`, `phone` and unresolved unit text stay untrusted. (b) require at least one passed rule (`jsonb_array_length(rule_results) > 0`) and `passed` strictly boolean true in the DDL check. (c) a correction keeps the path's value type. (d) restate 0057:141 honestly: it widens the sources and narrows the conditions. (e) say that trust means "carries no instruction", not "is true".

**B2. Trust flags are frozen on append-only rows while the rules are re-run.** 0057:86, 0057:121-125, 0057:138-139, 0057:174, DS-36:201-202, INV-642.
- Rules are cross-field and "re-run on every correction", but `rule_results` and `is_untrusted` cannot change after insert (probe: both updates refused as append-only). A total stays trusted after a corrected line makes its arithmetic rule fail. INV-642 would then be violated by design, or the re-run result has nowhere to live.
- The reverse also fails: `VerifyExtractionFields` only sets the verification on the existing row, so a person-confirmed `vision_aligned` or rule-failed row stays `is_untrusted` true forever, against "or that a person confirmed" (ADR-0029 note; 0062:35). Example 2 confirms with Enter, example 5 "into a human row"; the two disagree.
- Fix: either compute trust at read time from the current row, the latest rule run and the verification (store rule runs in their own append-only table keyed by extraction and run), or make every confirmation and every rule-state change append a new row. State which, and make INV-642 match.

**B3. The mailbox route rests authenticity on a signature check that does not identify the seller.** 0057:72 (rule 6), 0057:189-190 (rule 25), ADR-0051 rule 20.
- Rule 25 drops sender authentication because "the signature is the authenticity check". Rule 6 checks the signature "against the certificate in the file and the trusted authorities the package lists". Nothing requires the signing certificate's subject to be the seller, nor that the certificate was valid at the signing time. Any holder of a valid certificate can sign an invoice naming another supplier's tax ID; it gets `signature_state` passed, trusted fields, and an agent run in that supplier's scope with no person confirming.
- Before this ADR an employee imported the file; now any outside sender does.
- Fix: `passed` means: signature valid, chain to a listed authority, certificate valid at the signing time, and the certificate's subject identifier equals the seller tax ID (the mapping is the package's). Anything else is `failed` or a new state `signer_mismatch`, and needs `ConfirmEInvoiceSupplier`. Say that revocation cannot be checked offline and is the add-on's status check. Add an edge case.

## Should-fix

**S1. A forged or unsigned XML can take the supplier-invoice key.** 0057:128, 0057:190, EC-134.
- `ImportEInvoiceRecord` refuses a second record with the same key. If a record with a failed or absent signature is imported first (EC-134 says the agent "waits for a person's supplier confirmation", so a record exists), the genuine signed invoice is then refused as `duplicate_external_document`.
- Rule 25 imports "when rung 1 gives a valid record", and a failed signature forces `needs_review`, so whether a record is imported before or after the review is undefined; `e_invoice_intake` listens only to `DocumentExtractionRecorded`. EC-134's "every field is untrusted" is true of the extraction only: the record's structured fields stay not untrusted under ADR-0051 rule 20.
- Fix: decide one path. Suggested: a record without a passed signature does not hold the key against a later record with a passed one (the later one supersedes it, with a work item), and state when the import happens and what the record's fields are.

**S2. Alignment can be gamed by composing a value from scattered words.** 0057:108-111 (rule 12), t20 `align`.
- The check only requires that the value equals the concatenation of the cited words. The words may be any words of the page, in any order. A model can cite "9" from one line and "000.000" from another and get an aligned amount that is printed nowhere; it then counts as machine-checked on the screen (rule 22).
- Fix: cited words must be consecutive in reading order on one line (adjacent boxes, same baseline), and the region is their union. Add the lab case.
- Also align the lab with the text: the lab treats `currency`, `unit`, `email` and `url` by the near-match path; the ADR's exact list is "numbers, dates, tax IDs, amounts and codes with digits".

**S3. The hidden-text test is not positional.** 0057:145 (rule 18), 0057:92, t20 `hidden_text`.
- "No OCR counterpart on that page" is implemented as set membership: a hidden word counts as confirmed if the same word is visible anywhere on the page. Hidden text built from words that are visible elsewhere sets no flag, gets `is_on_render` true and takes part in rung 5.
- Rung 5 evidence is `char_span` with no region, so the screen cannot show the reviewer where the value stands.
- Fix: a text-layer word is confirmed only by an OCR word of equal normalized text whose box overlaps it; rung 5 evidence carries the region too. Add a note that text visible to OCR but not to people (tiny or low-contrast) is caught only by the evidence box.

**S4. The companion PDF rule does not fit the state machine and assumes too much.** 0057:191, 0057:79, DS-36:219-222.
- "Its request ends `rejected`" needs `pending → rejected`, which rule 7 and the trigger refuse (probe), and `RejectDocumentExtraction` is `human_only`.
- The two extractions run as separate jobs; nothing orders the PDF after the XML, so the PDF may already be at rung 6 with a work item or a vision run.
- Any PDF beside a parsed XML is taken as its rendering without a check. A second, different invoice sent as PDF in the same message is silently dropped, and a person is shown an unverified "rendering" that may differ from the XML.
- Fix: add a system-only end state (for example `superseded`, reason `rendering_of_parsed_xml`); process a message's XML parts first; link the PDF as "companion as received, unverified", only when its deterministic key fields (number, total) do not contradict the XML, else treat it as its own document; with several XML parts say which record it joins.

**S5. Unauthenticated mail can spend OCR and vision budget and flood review items.** 0057:38, 0057:189.
- The route handles every allowed attachment, not only XML. For PDFs and spreadsheets there is no signature, yet sender authentication is "not required" for all of them. Anyone can mail documents to the address and consume the reader's daily budget (USD 10, 300 runs) and the owner's queue.
- `partner_id` "for a mailbox, rule 25" is never defined in rule 25; it selects the mapping rules used.
- The mailbox owner must hold `edit` on the purpose's leaf or every delivery fails and is held (ADR-0013 rule 9); nothing checks this at `UpdateMailbox`.
- Fix: limit "not required" to XML with a passed signature; for other parts require an authenticated sender matched to a partner, else one triage item per message and no vision run until a person opens it; partner = the message's matched partner only when authenticated; check the owner's rights when the purpose is set; add a per-mailbox daily cap.

**S6. A verified PDF extraction has no way to start the purchase invoice agent.** 0057:197, ADR-0051 rule 20 note.
- The only trigger is `supplier_invoice_received`, whose subject is an `e_invoice_record`. No work item kind, no subject-table declaration and no mapping from `extraction_field` rows to the agent's inputs is given, and "from D2 on" skips D1.
- Fix: name the kind raised by `DocumentExtractionVerified` (or create the record from the verified fields), the scope resolver, the inputs, and that it is a new agent type version.

**S7. New readings of spec 03 rule 1 are not put to the author.** 0057:102, 0057:106, open-questions grouped entry.
- A tainted `subject` run reads the subject row only (ADR-0050 rule 27). The reader also reads child tables (`extraction_word`, `extraction_field`) and the attachment's bytes. `RecordExtractionFields` writes append-only rows as `is_draft_only`.
- Fix: add both as items of the grouped tainted-read question, interim as stated.

**S8. The data-processing policy: a second core default, not recorded, and open by omission.** 0057:154, 0057:155-157, ADR-0016 rule 10, ADR-0053 rules 8-9.
- ADR-0016 rule 10 says exactly one key has a core default; this adds another without a note there or on ADR-0053. With a default, a package that omits the key silently permits personal data abroad without an assessment. The regime-neutral and fail-closed choice is the ordinary one: no core default, so a missing value is `regime_configuration_missing` and each package states its policy.
- The neutrality itself is sound: no national rule is in the core, the Vietnamese values are package data and `unverified`, so they fail closed in production.
- `is_cross_border` and `processing_region` are typed by the proposer; no installation setting gives "the region in force" (0057:157). Fix: the adapter configuration declares the region and its country, and the handler computes `is_cross_border`.
- Golden-set replays and evaluations send company pages too; say the gateway gate covers them (INV-645 names only reader runs).

**S9. Erasure cannot find the rows and ignores accounting retention.** 0057:152.
- "The subject's personal fields" has no locator. ADR-0052 rule 25 lists rows by contact, address or partner. A card extraction has no link to the contact its proposal created; words are not typed by subject.
- Fields of a supplier invoice of an individual are evidence of an accounting document, which ADR-0019 rule 10 keeps for the legal retention period.
- Fix: define the subject's extractions (by `partner_id`, by the subject's inbound messages, by a result link to the created contact), keep extractions linked to accounting documents until retention ends, and add notes to ADR-0019 rule 10 and ADR-0052 rule 25.

**S10. Authorization catalogs are not covered.** 0057:39, 0057:173-178, 0062:38, 0062:122, `catalogs/authorization-*.csv`.
- Verbs `Correct`, `Propose`, `Bind` and `End` have no row in `authorization-verb-levels.csv` nor in the glossary (ADR-0054 rule 9: CI fails).
- Leaves `contact` and `bill_of_materials` do not exist (the catalog has `partner` and `production_structure`).
- No leaves `agent_document_reader` and `agent_product_engineering` (ADR-0054 rule 24), so `start_agent:product_engineering` cannot be granted.
- `Record` and `Complete` are at level `post` and `Reject` needs the approval flag, so "a person with `edit`" cannot complete or reject a verification as rule 23 implies. The verification commands name no leaf.
- Fix: add the rows; state leaf and level for each new command.

**S11. Keys across companies.** DS-36:189-190, DS-20 (applied):594-608, DS-43-54 (applied):1250.
- Probe: a bill of materials of company 2 may name a proposal item of company 1. Fix: `ALTER TABLE change_proposal_item ADD UNIQUE (company_id, change_proposal_id, item_index)` and make both keys composite with `company_id`.
- Probe: a `product_category_requirement` of company 2 may name a category of company 1; its `company_id` has no key at all when no attribute or scheme is named. Fix: composite key to the category (add the unique key on `product_category` if missing).
- `cost_estimate_gap.bill_of_materials_component_id` references `(id)` alone. Fix: composite.

**S12. A proposal-item reference is not stable.** 0062:68, 0062:91-93, ADR-0029 rule 1.
- The reference is (proposal, `item_index`). A person may edit the proposal before submitting (rule 9), and `UpdateChangeProposal` recomputes the items; a failed execution writes a new version. Removing or reordering items either breaks on the key or silently repoints the draft to another item.
- Fix: refuse removing or reordering an item that a draft references (name the error), or reference `change_proposal_item.id`. State where `BindProposedItems` reads the created item's ID (the execution's audit rows).

**S13. The release guard leaves two ways around it.** DS-43-54 (applied):1398-1423, 0062:92, INV-650.
- Probe: the header of a bill of materials with a released revision can be set back to a proposal item. Probe: a revision inserted directly as `released` on a pending header is accepted. "The database refuses the release too" holds only for the update from draft.
- Fix: a trigger on `bill_of_materials` refusing a proposal reference when any revision is not a draft; run the readiness guard on insert too.
- `bill_of_materials_output` has no proposal reference, so a new co-product or by-product cannot be drafted; say that outputs must be existing items.

**S14. E2 cannot write anything.** 0062:31, 0062:73, ADR-0033 rule 2, ADR-0050 rule 26.
- An E2 run starts tainted and may run only `is_draft_only` commands. `CreateBillOfMaterials`, the revision and routing commands and `CreateCostEstimate` are `other` but not registered `is_draft_only`, so each is refused with `tainted_run_not_allowed`. `CreateBillOfMaterials` also creates a header that is not a draft, with a name taken from untrusted text.
- Fix: register the draft commands `is_draft_only` by notes on ADR-0033 rule 2 and ADR-0035 rule 14 and justify the header, or drop E2's drafting and let the person's import load structures directly.

**S15. Component resolution does not handle several hits, and 92/8 is unsafe for parts.** 0062:51-58, t21 `resolve`.
- Steps 2 to 4 say "equal to", not "exactly one". A supplier code is unique per partner only; a manufacturer part number is unique per manufacturer and the source may name none. The lab models one item per code.
- The auto-accept uses the token-set ratio, which is 100 when one name's tokens are a subset of the other's: "steel plate 3 mm 100x200" matches a generic "Steel plate" at 100 with no rival, and "M8x20" against "M8x25" scores about 90. The constants were set for names, not dimensioned parts.
- The ADR blocks by category "or" unit kind; the lab uses both.
- Fix: each step needs exactly one active item, else its hits go to L2; auto-accept only when every numeric and dimension token of the line equals the candidate's and the blocking attributes match; make text and lab agree.

**S16. Binding ignores the unit snapshot of ADR-0056.** 0062:93, DS-43-54 component columns, t21 (`[1, 1, "identity"]`).
- A component carries `uom_numerator`, `uom_denominator` and `uom_factor_source` with no default. For a pending item these are unknowable; the lab writes identity. At binding the created item's inventory unit may differ from the line's unit.
- Fix: a pending component is written with the proposed inventory unit and identity; `BindProposedItems` verifies or recomputes the snapshot and leaves the reference pending with a work item when no factor exists.

**S17. One flag for setup and run time still writes a silent zero.** 0062:72, DS-43-54 (applied):528, example step 4.
- "Welding 6 min per piece" states a run time and no setup. The operation is written with `is_duration_stated` true and setup 0, which reads as a real zero: the trap rule 12 names.
- Fix: two flags (setup, run), or treat an unstated setup as a gap of its own. Also check `is_duration_stated OR (setup_duration = 0 AND run_duration = 0)`.

**S18. Gaps in the steps of ADR-0062.** 0062:44-49, 0062:81, 0062:86, INV-655.
- L4 summarizes "the evidence", which contains the estimate, but rule 12 says the estimate is never returned to the model and rule 3 declares no field classes. Fix: L4's input excludes the estimate and every cost; the cost section is rendered by code.
- For E3, L1 reads only the note. How the fields of the named extraction become component lines (they have evidence, not spans) is not stated, and INV-655 requires a source span. Fix: say the rows enter at D2 like E2 rows, and let INV-655 accept an evidence link.
- Nothing bounds a span, so the whole note can be the span of every value. Fix: a span is one line or sentence and at most a stated length.

**S19. Smaller workflow holes.** 0062:39, 0062:67, 0062:93, DS-36:139, DS-36:225-227.
- The continuation is woken once, when binding raises `product_release_ready`. In the example the gaps are filled later; nothing starts the continuation again. Fix: a person starts it (`start_agent`), or the item is re-raised when the gaps close.
- Product codes: ADR-0009 rule 15 keys a series by document type, fiscal year and branch; a product is none of these. The example shows the code inside the proposal at draft time, so simulation would consume numbers, and a code may collide with one a person typed. Fix: issue the code at execution, skip codes in use, and give the sequence its own key without a fiscal year; keep it in the open question.
- "The current value of a field is the row no other row supersedes" is not unique: the runner's row and a later vision row for the same path are both unsuperseded (probe), and a vision row may not supersede. Fix: one root row per path (unique index where `supersedes_field_id` is null) and let a machine row replace a `not_found` one.
- `signature_state` can change from `failed` to `passed` and `is_full_review_required` can be cleared (probe). Fix: both set once, like the hidden-text flag.

## Nits

1. 0062:7 "the seventh agent type": the catalog has six and `document_reader` is new too.
2. 0057:243 says block INV-640 to 669 has area `platform`; INV-642 and INV-645 are `safety`.
3. INV-653 reads differently in 0062:127 and in the catalog row.
4. EC-144 uses the event type `quotation_requested` for a product engineering case.
5. DS-20 (applied):592: the part number pattern `^[A-Z0-9]+$` refuses non-Latin part numbers, and the comment says "upper case" where the ADR says "case folded".
6. DS-36:51: `result_table` accepts any text (probe); add a closed list.
7. The database accepts a field appended to a verified extraction, a verification with no field rows, and `extracted` with a vision reader (probes). These are command rules; say so or add checks.
8. 0057:238: the work item is also resolved by `RejectDocumentExtraction`; the catalog names one command.
9. 0057:101: the reader is woken for every `needs_review`, also XML kinds with no pages and records that only failed a rule. Limit it to kinds with pages and missing fields.
10. 0057:128: run the key duplicate check as soon as the key fields are found, not only when a draft is created, so a person does not verify a duplicate.
11. 0057:149: an e-mail attachment is `personal` "unless a deterministic reader proves" otherwise, but the label is set at creation and the trigger forbids a later change. Say the label stays.
12. Review items of a mailbox go to the mailbox owner (`requested_by_user_id`); a role would fit an accounts-payable mailbox better.
13. 0057:128 and 0057:190 use "series" and "authority code" in core text; "the package's supplier-invoice key" and "clearance code" are more neutral. The legal texts themselves are correctly confined to rule 30, ADR-0003's note and DS-19.
14. ADR-0050 rules 1 and 30 need notes: the table and contract function in `agent_runs`, the two permission commands in `agents`, and their place on no tool list.
15. An expired or cancelled item proposal leaves drafts pending with no work item (0062:93).
16. 0062:5 L1: when the category hint matches no category, say the line goes to a person.

## Confirmed sound

- Core neutrality: no Vietnamese rule shapes a core rule. Decree and circular numbers appear only as `l10n_vn` content (rule 30, DS-19 settings, both `unverified`) and in ADR-0003's legal watch note. Readers, anchors, formats and the e-invoice parser are package code behind hooks.
- Principle 13: totals, taxes and line amounts are recomputed by code; no model confidence is asked for or stored; aligned values store the page's text; numbers are compared character-exact with no normalization (lab A02, A03); unaligned values cannot be verified (DDL check) and fill nothing.
- The vision step is a run without model-callable tools, tainted from its start, writing through one `is_draft_only` command, under budgets and the processing log.
- The seat is unreachable until permitted: the wake-up, the gateway check and INV-645 agree; the permission needs an approved proposal with approver other than submitter; with the routing switch on the run ends `routing_blocked`; this is stricter than spec 17's baseline. The local adapter stays disabled.
- Bank details never change master data or fill a payment (rule 16), in line with ADR-0029 rule 4.
- Ownership follows ADR-0022: tables in `attachments`, mapping rules in `master_data`, the permission in `agent_runs` with commands in `agents`, as `agent_promotion_evidence` does; readers through a hook and `DocumentReader` (ADR-0016 rule 17).
- Accepted ADRs are changed by notes only; nothing in the diff names a customer.
- ADR-0062: E1 and E3 follow the configuring-quotation path; E2 keeps the literal scope and the tainted catalog read is left to the author with interim "no"; 92/8 and five candidates match ADR-0051 rule 1; approver other than the run's human is enforced by ADR-0029 rule 3 and ADR-0055 rule 7 condition 5; the wake-up after binding is legal because approval resets the origin run; estimate gaps are rows, never zero, and release is refused in command and database for the update path (lab X08, X09, X12).
- DDL: `company_id`, composite keys, RLS with FORCE and both policies on the five DS-36 company tables, null-safe checks (`coalesce` on the signature state, paired null checks), append-only triggers with erasure-only columns, state transitions, exclusion constraint on permissions.
- Coverage: decisions 1 to 19 each have a rule. Catalog codes, DS-04 codes, work item kinds and glossary terms have no duplicates; INV-640 to 645 and 650 to 655 and EC-132 to 144 are free in the base.
