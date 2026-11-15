# Holistic review: master data, CPQ, pricing, O2C, P2P, inventory (HEAD 5536f9c) + architect decisions

2 blocking, 19 should-fix, 5 nits. "accept" = apply the reviewer's fix as a note on the named carrier (all ADRs accepted: notes at rule ends only).

Queued findings:
- Q1 lookahead (ADR-0046 r8): accept. leads_to_violation true only when the value adds a violation (code + rule/table + characteristics) absent from the baseline; lookahead covers characteristics with no user or rule value, defaulted ones included. Fix lab t06 line ~235 accordingly.
- Q2 below-cost (ADR-0045 r5): accept. Net amount after document-discount allocation, per inventory unit, company currency, free goods excluded (ADR-0047 r22).
- Q3 human price-list change (ADR-0029 r5): accept note (list binds agents and origin-agent chains; humans direct unless a direct_master_data_change deny rule exists; only bank accounts seeded). Add open question (author): seed a deny rule for SetPriceListEntries (dual control on prices)?
- Q4 configuration estimate (ADR-0046 r14, ADR-0020 r11): accept note naming cost_estimate; selection = latest released estimate for the item with costing date <= posting date, preferring the version whose warehouse is in the line's valuation area; basis = ADR-0035 r14 default (flagged); failure: item stays usable for quotations and orders, production receipt rejects with preliminary_price_missing as ADR-0035 r4 says (fix the "stays usable" wording to be precise).
- Q5 taint through O2C: accept technical fix (notes ADR-0047 r2, ADR-0023 r16, ADR-0029 r8 and r11): is_tainted = OR over all source line versions on Create and on every Update adding source lines; stock and production handlers set it too; rule 11 aligned to ADR-0043 floor 3; workflow offers ClearTaint at quotation approval. Open question (author): does approval of a quotation by a person other than the run's human stop inheritance to derived documents?
- Q6 tainted CPQ read scope: AUTHOR (already open questions 36, 40, 41). Sim/video decision: show the design-compliant path: an e-mail-triggered (tainted) run resolves partner items only and hands over; a person starts the configuration run from an internal note (untainted). Mention in the final report to the author.

Findings:
- B1 quotation lines without item vs INV-113 (ADR-0046 r18, ADR-0018 r2): accept.
- B2 receipts/deliveries against unapproved orders (ADR-0047 r18-19): accept. Rows created unreleased; sales/purchasing release at approval via the hold interface generalised to a hold reason (not_approved, credit_hold); inventory rejects pick release, delivery, receipt on unreleased rows with a named error (e.g. demand_supply_not_released).
- S1 proposal_required for agent lines (ADR-0045 r16): accept.
- S2 copied prices exempt from re-pricing (ADR-0047 r16): accept.
- S3 copy preconditions per type pair (ADR-0047 r2): accept (source must be approved or later; one source document per Create for deliveries unless stated).
- S4 quotation spec (ADR-0047 r3): accept (sales order header/lines without demand; warehouse optional, checked at copy; partner needs active customer role).
- S5 rejected sales order demand (ADR-0047 r19): accept (unreleased rows not demand; Reject un-releases).
- S6 returns vs closed orders (ADR-0047 r5, r11): accept.
- S7 pick release reserves when no reservation (ADR-0023 r14): accept.
- S8 credit hold work item: accept, kind credit_hold (module sales, subject sales_order, owner role:accountant), resolved by ReleaseCreditHold or hold clearing (ADR-0047 r23).
- S9 no stock sale without order: accept, error sales_order_required (ADR-0047 r6).
- S10 expense-line account key: accept, name the key and determinants (item group); add to transaction-keys.csv and TT99 determination if missing (ADR-0047 r12).
- S11 three-way match price (V(I+q)-V(I))/q (ADR-0047 r14): accept.
- S12 CreatePartner defaults + command list (ADR-0045 r13): accept (company settings for default partner group per role; command list with payload shapes).
- S13 SetPriceListEntries semantics (ADR-0045 r7): accept (upsert by key; auto end-date predecessor; past-start entries only end-dated).
- S14 default-list currency (ADR-0045 r5): when currencies differ the document carries no list; prices manual, is_price_outside_list set.
- S15 find_price final signature note on ADR-0045 r4: accept.
- S16 purchase list fallback (ADR-0047 r10): accept.
- S17 line options without model (ADR-0046 r9): accept.
- S18 unknown cost in policy (ADR-0043 r3): accept, condition is_cost_unknown with a seeded approval rule.
- S19 DDL for commercial/inventory: a separate agent drafts it (DS-22/DS-09/DS-42).
- N1-N5: accept (module warehouse -> inventory in work-item-kinds rows; ADR-0020 r4 count note; ADR-0029 spliced notes: add a clarifying note, do not move accepted text; service_receipt row in ADR-0047 r1 + service_receipt_line_id (coordinate: the production fix also adds the registry row; write yours to skip if present); price commands: drop one of master_data_change / is_proposal_bound via note).
