# Review r2: ADR-0057 Document intake and extraction; ADR-0062 Product engineering workflow

Date: 2026-11-15. Reviewer: independent (read-only). Base: branch `ds-uom`, HEAD ec0c126 (ADR-0056 accepted) + `drafts/ds-intake/apply_intake.py` (79 writes over 40 files).

## Verdict: NOT YET

0 blocking, 8 should-fix, 9 nits. The three round-1 blockers are closed in substance; what remains are residues of B1, B2, S1 and S2 and two new contradictions.

Lab, each on a fresh `erpme_lab_rv57` (dropped afterwards): t20 157/157, t21 85/85, t12 186/186, t16 99/99, all with `--load`. "Probe" means run against the loaded schema in a rolled-back transaction. t05 and t15 were not rerun.

File references: `0057`, `0062`, `DS-36` are the drafts in `drafts/ds-intake/`.

## Round-1 items

| Item | State |
| --- | --- |
| B1 value trust for string types | Closed in the main: shapes, never-trusted types, at least one rule, type kept (probe). Residue: R1, R2 |
| B2 frozen trust flags | Closed: rule runs, confirmations, the view. Residue: R3, R4 |
| B3 signature identifies the seller | Closed: four conditions, `signer_mismatch`, EC-145. New concern: R5 |
| S1 key squatting | Closed by quarantine and supersession. Residue: R6 |
| S2 alignment | Consecutive words on one line (lab, INV-641). Residue: R7 |
| S3 hidden text by position | Closed; the one-half overlap is sound (see below) |
| S4 companion PDF | Closed: `pending → rejected` for the system, XML first, matching. Nit 1 |
| S5 unauthenticated mail | Closed for OCR and vision. The daily limit itself: R6 |
| S6 verified PDF to the agent | Closed: `supplier_invoice_extracted`, agent 1.1.0, inputs, D1 |
| S7 readings put to the author | Closed: both are in the ADR and the open questions |
| S8 policy default | Closed: no default, fail closed, registry computes the country, every run mode gated, notes on ADR-0016 and ADR-0053 |
| S9 erasure | Closed: result links, the subject's extractions, accounting fields kept, notes on ADR-0019 and ADR-0052 |
| S10 authorization catalogs | Closed: verbs, leaves, template levels, leaf and level per command. Nit 2 |
| S11 company keys | Closed (lab X31 and the DDL) |
| S12 stable proposal reference | Closed: `change_proposal_item.id`, `proposal_item_referenced` |
| S13 release guard | Closed: insert and header guards (lab X11) |
| S14 E2 writes | Closed: draft commands `is_draft_only`. New concern: R8 |
| S15 resolution | Closed: exactly one hit, scoped codes, attribute tokens |
| S16 unit snapshot | Closed: identity while pending, recomputed at binding |
| S17 setup and run flags | Closed, with the zero check |
| S18 step gaps | Closed: L4 without costs, extraction rows at D2, spans bounded |
| S19 smaller holes | Closed: continuation on the draft, code at execution, one root per path, flags set once (probes) |

## Should-fix

**R1. A trusted row still carries unbounded columns.** 0057:98, 0057:173-179, DS-36:100-105, t20 `shape_ok`.
- The shape rule checks `value_normalized`. `value_raw` and `evidence` are not bounded and belong to the same row. Probe: a `quantity` row with normalized `5` and a 300-character instruction in `value_raw` is reported trusted. `evidence` holds sender text too (a sheet name, a vCard property name).
- Fix: trust covers `value_normalized` only. The query layer serves `value_raw` and `evidence` as untrusted columns always; a run that needs only trusted values gets the normalized value and the field ID. Also require normalizers to be strict (the whole raw value must parse; nothing is discarded).

**R2. The `code` shape admits words.** 0057:169, probe T6.
- 32 characters of letters with `. _ / -` hold `ignore_previous_instructions`, and a spreadsheet gives one such value per row, so a column of codes can spell a longer instruction. A person's Enter makes each trusted.
- Fix: treat `code` like `unit`: trusted only when it resolves to a record (item code, partner item code, barcode, manufacturer part), the normalized value being that record's code. An unresolved code stays untrusted and goes to a person or a tainted run. This also matches ADR-0051 rule 20, which keeps `seller_item_code` untrusted.

**R3. Trust at read is deterministic, but not fail-safe and not auditable as written.** 0057:141, 0057:173-179, 0057:300, DS-36:176-195.
- The view takes the latest run per field, not the extraction's latest run. Probe: `total` passed in run 1; run 2 evaluates only `line` and fails `lines_sum`; `total` stays trusted. "Every run evaluates every current field" is not enforced, so the view should not depend on it. Fix: a field is trusted only on results of the extraction's highest run number.
- "A new rule run follows" a correction or a vision write. Say it is in the same transaction, or the stale window of B2 reopens between the two.
- INV-642 asks what the view "reported at the step's `recorded_at`". The view has no past tense. Rule runs and confirmations have times, but the flags do not: `hidden_text_suspected` can be raised after fields were served (probe T4), with no instant stored. Fix: the dispatcher records with each context reference the trust it served and the run number it used; the flags are set only by the recording command; INV-642 compares the stored value with a recomputation from rows up to that run number.

**R4. A full rule run after every confirmation.** 0057:141, 0057:218, DS-36:144.
- A confirmation changes no value, so no rule can change, and the trust of a confirmed row already reads the earlier `shape` result. With one Enter per field, a 200-line invoice writes on the order of millions of run rows.
- Fix: runs follow recording, vision writes and corrections only; drop the trigger kind `confirmation`.

**R5. "Absent signature forces a full review" shapes the core around signed formats, and doubles the work.** 0057:93, 0057:174, 0057:235-236, DS-36:68.
- In many regimes structured invoices carry no signature at all. Under this rule every such XML has every field untrusted and needs every field confirmed by hand, so rung 1 gives nothing. A PDF with no signature is `not_applicable` and its shaped fields are trusted; the unsigned XML, which is better data, is not. That is one regime's assumption in a core rule.
- The XML's record is imported anyway and needs `ConfirmEInvoiceSupplier`. So one document raises two human tasks, and nothing consumes the field-by-field review of the extraction.
- Fix: authenticity belongs to quarantine, not to value trust. `absent` quarantines the record and needs the supplier confirmation; it does not make shaped fields untrusted and does not force a full review, unless the package's format declares the signature mandatory (then absent counts as `failed`). For an XML whose record was imported, the person's task is the record's confirmation only.

**R6. Quarantine and supersession can still be abused.** 0057:233, 0057:236, t20 `mailbox_plan`, `import_record`, `confirm_supplier`.
- The daily limit counts every part. XML parts are requested from unauthenticated senders, so 200 junk XML files in a day leave the genuine signed invoices "stored only". Fix: parts with a passed signature and parts from authenticated senders are outside the limit that unauthenticated or quarantined parts consume; give quarantined records their own lower cap and one grouped work item per sender.
- Once a person confirms a forged unsigned record, it holds the key, and the genuine signed invoice that arrives later is refused as a duplicate. Fix: a record with a passed signature that meets a key held by a confirmed, formerly quarantined record is imported and raises a conflict item, instead of being refused.
- How `e_invoice_intake` handles `duplicate_external_document` is not stated. It is a normal outcome and must not hold the delivery. Fix: it ends as a check result on the extraction, linked to the existing record.
- Say that `ConfirmEInvoiceSupplier` refuses a superseded record.

**R7. Consecutive words on one line can still compose a number.** 0057:127-128, t20 `align`.
- Two neighbouring table cells are consecutive words on one line. Quantity "2" and price "500" align as "2500", because the comparison removes spaces.
- Fix: cited words must also be adjacent: the gap between neighbours is at most a stated fraction of the word height (a normal space). Add the lab case.

**R8. An E2 run's drafts lose their taint.** 0062 rule 2 (the continuation row), rule 3, rule 10; `routing_operation.description`.
- A continuation on a draft revision is "untainted". Drafts written by a tainted E2 run are not document versions and carry no taint, and they hold free text (an operation's description). The release proposal the continuation drafts is then untainted.
- Fix: an E2 run writes no free text from batch rows into drafts (generated names only, as for the header), or a continuation on a revision drafted by a tainted run starts tainted. State which.

## Nits

1. 0057:237: a matching file name stem alone makes a PDF the rendering. Require the invoice number token as well, and render the record's own fields first on the screen.
2. The verb catalog's meaning of Verify still speaks only of mailbox authentication; `CancelDocumentExtraction` ends in state `rejected` and emits `DocumentExtractionRejected`.
3. 0057:220: a failed arithmetic rule can never be overridden, so an invoice whose printed totals differ beyond tolerance can only be cancelled. Say that this is intended, or allow verification with a recorded reason.
4. 0062 rule 2: say the named extraction must be `verified` (or `extracted`).
5. 0057:233: if a message's XML extraction never records, its other parts are never requested. Add a timeout.
6. 0057:197: the `l10n_xx` policy value is an obligation with no file yet; list it in the backlog.
7. 0062 rule 9: the series key `product` is not a document type; say where the series row lives.
8. 0057:236: several quarantined records may share one key; say they are shown together.
9. 0062 rule 14: `product_item_proposal_ended` is raised on reject, and a rejected proposal returns to draft and may be resubmitted; say the item is resolved when it is.

## Answers to the points raised

- **Trust at read:** deterministic, yes: a pure function of append-only rows and set-once flags. Auditable: not yet (R3).
- **Confirmed value trusted on shape alone:** coherent with "carries no instruction"; acceptable once R1 and R2 hold.
- **Shape table:** bounds decimals, dates, currencies, tax IDs, bank accounts and resolved units. It does not bound `code` (R2) nor the raw value and evidence (R1).
- **Absent signature:** not acceptable as a core rule (R5).
- **Renamed commands:** consistent with the verb catalog and glossary (nit 2).
- **Product codes at execution:** sound; simulation consumes nothing and typed codes are skipped (nit 7).
- **Hidden-text overlap of one half:** sound. A hidden word passes only where the same word is visible at the same place, which changes nothing a reader sees. Split or merged OCR words only push a value to rung 6.

## Confirmed sound

- No national rule in the core; "clearance code" and "the package's supplier-invoice key" replace the earlier wording; the policy has no default and fails closed.
- Numbers come from code: totals recomputed, no model confidence, exact comparison, unaligned values never confirmed (trigger), L4 sees no cost.
- The vision run has no model tools, starts tainted, and is gated in every run mode; the seat is unreachable without a four-eyes permission.
- DDL: company keys on every new reference, one root per path, type kept on correction, nothing appended to a final extraction, flags and signature state set once, `extracted` never on a vision reader, RLS on all eight DS-36 company tables (probes and lab).
- Catalogs: no duplicate codes; verbs, leaves and template levels present; accepted ADRs changed by notes only.
