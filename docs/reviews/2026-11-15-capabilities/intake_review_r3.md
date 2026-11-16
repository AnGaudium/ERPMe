# Review r3: ADR-0057 Document intake and extraction; ADR-0062 Product engineering workflow

Date: 2026-11-15. Reviewer: independent (read-only). Base: branch `ds-uom`, HEAD ec0c126 + `drafts/ds-intake/apply_intake.py` (83 writes over 41 files).

## Verdict: NOT YET

0 blocking, 3 should-fix, 7 nits. All eight round-2 items are addressed; R6 and R8 leave one new problem each, and the override contradicts an invariant.

Lab, each on a fresh `nativeflows_lab_rv57` (dropped afterwards): t20 173/173, t21 91/91, t12 186/186, t15 146/146, t16 99/99, all with `--load`. t05 does not run on the combined schema of `load_all.py`, on the base either, so it says nothing about this draft. "Probe" means run against the loaded schema in a rolled-back transaction.

File references: `0057`, `0062`, `DS-36` are the drafts in `drafts/ds-intake/`.

## Round-2 items

| Item | State |
| --- | --- |
| R1 trust covers the normalized value only | Closed: raw text and evidence always served untrusted, strict normalizers (0057:98, 0057 rule 17) |
| R2 `code` shape | Closed: trusted only when it resolves to exactly one record; lab `shape_ok` |
| R3 fail-safe and auditable trust | Closed: the view reads the extraction's highest run (probe: the stale total is now untrusted); runs in the write's transaction; served trust and run number in `context_refs` (ADR-0050 rule 19 note, INV-642); flags only while pending (probe) |
| R4 no run on confirmation | Closed: the trigger kind is gone (probe) |
| R5 absent signature | Closed: quarantine only, unless the format declares the signature mandatory; one human task; the extraction ends `extracted` (probe) |
| R6 quarantine and limits | Key conflict, duplicates as an outcome and `e_invoice_superseded` closed. The limits: S1 |
| R7 adjacency | Closed: one cell, gap of 0.6 line height (lab). Nit 1 |
| R8 E2 taint | No free text from batch rows: closed. The tainted continuation: S2 |

## Should-fix

**S1. The quarantine cap drops real invoices without telling anyone.** 0057:96, 0057:237, t20 `mailbox_plan`.
- The cap (default 20) counts every quarantined record of a mailbox and day, also those of authenticated senders. Since R5, a regime whose format carries no signature quarantines every invoice, so the twenty-first invoice of an ordinary day is canceled.
- `canceled` is final and there is one extraction per attachment and purpose, so it cannot be requested again. No work item says it happened: the grouped item lists records, and a canceled part has none; `mailbox_intake_limit_reached` belongs to the other limit.
- Rule 7 allows the system only `pending → canceled`, but the signature is known only after the reader ran, when the record is no longer pending. The lab's plan decides it before the request, which the runner cannot do.
- The daily limit can no longer be reached: the XML parts it counts hit the cap of 20 first, and other parts of unauthenticated senders are stored anyway.
- Fix: the cap counts only records of unauthenticated messages. Beyond it the extraction is recorded as usual (`extracted`), is not imported, carries a check result `quarantine_limit_reached`, and is listed in one item for the mailbox owner, from which a person imports it. No system cancel is needed for it. Then either drop the daily limit or say what it still bounds.

**S2. The tainted continuation cannot read its own draft, and the lookup misses the routing.** 0062 rule 2 (continuation row), rule 3 (0062:40).
- A tainted continuation gets "that run's scope", which for an E2 run is the import batch. Under the literal scope (ADR-0050 rule 27) such a run reads the batch's rows only. The draft revision, its components, the work centers and the check queries are not reached from batch rows, so D6 to D8 are refused. The declaration two lines later gives continuations the scope kind `subject`.
- The start handler reads the audit records of the draft's commands. The subject is the bill of materials revision, but the release proposal also releases the routing revision. A routing drafted by a tainted run beside a clean bill of materials is not seen.
- Fix: a tainted continuation has scope `subject` (the draft revision and the rows reached from it), added to the grouped tainted-read question. The lookup covers every draft the proposal will release (bill of materials revision, routing revision, estimate). Say "tainted" means the writing run has a `tainted_at`, whenever it was set.

**S3. The override contradicts INV-644.** 0057:223, 0057:310, `invariants.csv` INV-644.
- `VerifyDocumentExtraction` now accepts a failed cross-field rule with a reason. INV-644 still says every result of the latest run passed, in the ADR and in the catalog, so every override is a violation.
- Fix: "passed, or is named in `rule_overrides` with a reason and is not `shape`".

## Nits

1. t20 `align`: the gap is `b.x0 − a.x1`, which is negative on a right-to-left line, so any distance passes there. Use the distance between the boxes.
2. DS-36: `rule_overrides` accepts an entry without a reason or naming `shape` (probe). It is the command's rule; say so beside the column or add a check.
3. 0057:96: `extracted` "means nothing needs a person", but an XML with a failed signature is now `extracted` while its record waits for a confirmation. Reword.
4. 0057 rule 25: the import runs "on behalf of the mailbox owner". Say what happens for an XML a person uploaded and requested.
5. The backlog does not list `DS-16-l10n_xx/settings.yaml`; DS-16 and the ADR do.
6. 0062 rule 2: several tainted writing runs with different scopes are not covered; S2's fix removes the case.
7. 0057:237: name the business date the two limits count by (the message's receipt).

## Builder decisions

- **Quarantine overflow cancels the extraction:** no, see S1.
- **Override allowed with a reason:** sound. Only cross-field rules, never `shape`, and it trusts nothing by itself; a confirmed value is trusted by its shape as before. It needs S3.
- **Taint lookup from the draft's audit records:** the right source (the handler reads it, not the agent), but incomplete and with the wrong scope, see S2.
- **`l10n_xx` file location:** fine. `design/DS-16-l10n_xx/settings.yaml` mirrors `DS-19-vietnam-tt99`, carries `test_fixture`, and DS-16 owns the test package.

## Confirmed sound

- Value trust is now narrow and checkable: normalized values only, closed shapes, codes and units only when resolved, at least one passed result in the extraction's highest run, vision values only after a person's confirmation, nothing from an extraction with hidden text or a failed or mismatched signature.
- Trust at read is deterministic and auditable: a pure function of append-only rows and flags fixed at recording, with what was served stored per step.
- Authenticity is separate from trust: quarantine, supplier confirmation, supersession, and a key conflict that never refuses a signed invoice.
- Core neutrality holds: no national rule in the core, no default policy, an absent signature treated by the package's declaration.
- Numbers come from code; the model sees no cost; alignment is exact, adjacent and within one cell.
- DDL (probes and lab): company keys, one root per path, type kept on correction, nothing appended to a final extraction, flags and signature fixed after recording, overrides only on a verified record, RLS on the eight DS-36 company tables.
- Catalogs: six work item kinds, the new error and check result codes, verbs and leaves present, no duplicates. Accepted ADRs are changed by notes only.
