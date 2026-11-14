# Design assessment 1 (2026-11-14)

**What was assessed.** The author asked for a hard, independent assessment of the whole design before code. It covered the architecture and seven business flows:
- CPQ;
- O2C;
- demand planning;
- P2P;
- end-to-end information flow;
- goods flow;
- finance flow.

For each flow it asked two questions: does the design hold enough information for the flow to work, and is the workflow agentic-first?

**Snapshot.** `9ac727f`: ADR-0001 to ADR-0024, DS-04/06/14/16/17, the catalogs and the open questions. DS-41 (ADR-0025) was accepted afterwards and was not assessed.

**How it was run.** A deterministic workflow of five agents, all reading the read-only snapshot:
1. An independent architect, with no context from the builder, reconstructed the architecture, data model and per-flow dataflow from the documents alone ([01-reconstruction.md](01-reconstruction.md)).
2. Three assessors worked in parallel on the reconstruction and the sources:
   - reviewer, for completeness and consistency ([02-review.md](02-review.md));
   - adversarial critic, who tried to break each flow ([03-critique.md](03-critique.md));
   - optimizer, for simplification and operability ([04-optimize.md](04-optimize.md)).
3. An adjudicator checked every critical and high finding against the sources and merged duplicates ([05-adjudication.md](05-adjudication.md)).

The builder (Claude Opus 5.5) wrote this synthesis.

## Verdict

**No finding survived as critical.** The core needs no redesign. Every assessor found these parts rigorous and resistant to attack:
- the command envelope;
- simulate/execute with `plan_hash`;
- idempotency;
- versioned documents with approvals bound to the version;
- segregation of duties through `origin_agent_run_id`;
- the universal journal and material documents;
- stock locking, costing and landed cost;
- warehouse management;
- planning;
- the outbox;
- posting periods;
- the localization boundary.

**Two findings are high** and must be fixed before the code that depends on them:

| Id | Finding | Fix | Author? |
| --- | --- | --- | --- |
| F2 (+F-1) | The open-item model is needed from step 1 (journal foreign key and trigger) and step 4 (INV-30..32, opening balances), but only DS-25 designs it, at step 6. B3 forbids core changes after step 5 | A step 0 ADR for the open-item core: table, kinds, due dates, amounts per currency, settlement links, posting interface. DS-25 keeps payments, bank formats and netting | Design is technical. Moving build steps is the author's |
| O-1 (+F1) | A posted sales invoice whose e-invoice is rejected or never issued has no correction path. Posting makes it immutable, and e-invoiced types are never reversible | Amend ADR-0009 before step 5: package pre-validation in simulation, and an "issuing / not issued" state that allows reversal of an unissued invoice. Add edge cases for rejection and outage | Legal treatment is the author's |

**Medium findings, grouped into the work they imply.**
1. **Ownership gaps** for cross-cutting entities:
   - `open_item` (F2);
   - the `derivation_trace` schema (needed from step 1, and for price and tax traces);
   - `agent_run`, `work_item` and attachments: referenced by layer-2 modules but owned by layer 5 or by nobody;
   - the `customs_declaration` module;
   - the transfer order document, used by ADR-0020, 0023 and 0024 and owned by none;
   - `company`, `branch`, `cost_center`, `project`;
   - the `employee` foreign key in DS-06, which conflicts with ADR-0019's employees-as-partners;
   - full data export and management reporting;
   - the list of synchronous and asynchronous read models that spec 07 requires;
   - provision, bad-debt and write-down computations.
2. **Document line identity and change orders.**
   - Line rows must keep their `id` across versions, and a referenced line cannot be deleted. Reservations, tasks and pegging point at lines (A-1).
   - Updating an approved, partly fulfilled order returns it to draft and orphans its reservations and tasks (O-2). Whether a changed order stays in force is the author's.
3. **A proposal carrier for non-document changes** (A-2 + F3). Agents propose master data, mappings, planning parameters and bank accounts, but approvals and segregation of duties bind only to document versions. Fix: a non-posting document type such as `master_data_change`, and the policy engine widened to registered non-posting actions (DS-28).
4. **Agent safety hardening.**
   - Taint lives only on events, so stored drafts launder it (F4; requirement on DS-32 and DS-33).
   - Consumers act with system rights, not intersected with the originating agent (F16).
   - "Agent auto-post" is undefined and contradicts "deterministic code only" (F6, X-1).
   - The policy engine's call point is contradictory (A-3).
   - Approval binds content, not the decision context (F7).
   - The read scope of a tainted run contradicts what the quotation workflow needs (F15, C-5; the author clarifies).
5. **P2P and O2C seams.**
   - A price difference into a soft-locked earlier period blocks ordinary invoice posting (F5; extends the author's open question).
   - GR/IR is not reconcilable per line, invoice-before-receipt is undefined, and no invariant exists (F12).
   - The credit check has no lock position and no exposure data at step 5 (F9).
   - Copying partner data at posting changes approved content (C-7).
   - There is no seam for goods sold but held, invoice before delivery, or consignment (F13; the author decides).
   - Mass imports exceed batch and timeout limits (F14).
6. **Simplifications** proposed by the optimizer, to be decided one by one:
   - one implicit bin instead of two stock-key modes (OPT-05);
   - one queue machinery (OPT-08);
   - `plan_hash` and document versions (OPT-01);
   - one home for a demand line's open quantity (OPT-03);
   - one shape for exceptions (OPT-10);
   - storage for the dated negative-stock check (OPT-07).
7. **Scope** (author): a cut of the Phase 1 warehouse and planning lists (OPT-12); group-currency logic deferred while the columns stay (OPT-13).
8. **Catalog and consistency fixes:**
   - three transaction keys break ADR-0015 rule 2 (A-6);
   - invariants are missing for hard floors, GR/IR and document-written read models (A-7);
   - stale counts (L-1);
   - INV-07 does not fit non-posting numbering (L-6);
   - an unverified closing rule is checked off in the open questions (L-5; the author must look).

## Flows

| Flow | Information | Agentic-first | Blocking gaps |
| --- | --- | --- | --- |
| CPQ | Partial: intake and safety designed; prices, quotation and policy deferred to DS-20/22/28/34 (owned) | Yes in design; the human approver is the real check on LLM item mapping | Tainted-run read scope (author); price trace; proposal carrier |
| O2C | Partial: reservation, pick, pack, ship and COGS designed in depth; documents, receivables and tax deferred | Yes; bank-matching auto-post must be defined as deterministic code | E-invoice dead end (high); open items timing (high); change orders; credit lock |
| Demand planning | Designed (ADR-0024); phase pending the author | Yes: deterministic runs, pegging as trace, drafts only | Transfer order owner; proposal carrier for parameters |
| P2P | Partial: receipt, customs and landed cost designed in depth; documents and matching deferred | Yes; mapping approvals need the carrier | GR/IR per line; price difference into soft-locked periods; customs module owner |
| Information flow | Partial: inputs, commands, ledgers and outbox designed; outputs deferred | Yes; agent answers need provenance | Export and management reporting owner; derivation trace schema; sync/async list; natural-key deduplication of external inputs |
| Goods flow | Complete | Yes | Concurrent pick release lock; sold-but-held seam (author) |
| Finance flow | Partial: FX, periods and close designed; AR/AP, cash, VAT and reports deferred | Yes; close and reversal human-only | Open items timing (high); auto-post definition; opening-balance import atomicity |

## Proposed remediation (hardening batch before step 1 code)

The order follows the critic's "order of fixes" (03, section 6):

1. **Before step 1 code:**
   - open-item core ADR (F2);
   - cross-cutting ownership ADR: layer-2 homes for `agent_run`, `work_item` and attachments; the `derivation_trace` schema; owners for customs declaration and the transfer order; company, branch, cost center, project; the employee foreign key; the read-model list; the export and reporting owner;
   - catalog fixes.
2. **Before step 3:** document line identity across versions, with an invariant (A-1).
3. **Before step 4:** import mechanism for mass and opening-balance batches (F14).
4. **Before step 5:**
   - e-invoiced document lifecycle (O-1, plus an author question);
   - change orders (O-2, plus an author question);
   - proposal carrier for non-document changes (A-2);
   - agent safety hardening (F4, F6, F7, F15, F16, A-3);
   - credit lock (F9);
   - GR/IR line reference and invariant (F12);
   - the sold-but-held axis (F13, author).
5. **Simplifications and scope:** decided one by one; scope cuts are the author's.

## Questions for the author raised by this assessment

1. E-invoice rejected or never issued: may the unissued invoice be reversed, or must it be corrected by a credit note and reissue?
2. Does a changed, approved, partly fulfilled order stay in force, or go back to draft?
3. The read scope of an agent run that has read a customer email: may it read company-wide price lists, stock and purchase history for the quotation?
4. Goods sold but held, invoice before delivery, consignment: in scope for Phase 1, or only a reserved axis?
5. Build order: may the open-item core be designed and built from step 1, ahead of DS-25?
6. Scope cuts proposed by the optimizer for Phase 1 warehouse management, planning and group currency.
7. Look at the closing rule (911/421 every period) that the open questions mark as answered, although it is unverified (L-5).
