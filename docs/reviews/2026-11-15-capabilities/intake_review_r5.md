# Review r5: ADR-0057 Document intake and extraction; ADR-0062 Product engineering workflow

Date: 2026-11-15. Reviewer: independent (read-only). Tested on `/tmp` copies of `base-ds-uom` and `base-uom-sim`; the bases, the drafts and the repo were not changed.

## Verdict: ACCEPT

0 blocking, 0 should-fix, 3 nits. Round 4's S1 and S2 and its six nits are applied and hold.

## Lab

Fresh `nativeflows_lab_rv57` for every `--load`; no lock exhaustion occurred.

| Copy | Result |
| --- | --- |
| `base-ds-uom` + `apply_intake.py` (84 writes, 41 files) | t20 184/184, t21 93/93, t12 186/186, t15 146/146, t16 99/99; `check_package.py` on `DS-19-vietnam-tt99`, regime `tt99`: RESULT PASS (system Python; the lab venv has no `yaml`) |
| `base-uom-sim` + `apply_intake.py` (84 writes, 41 files) | Applies unchanged; t12 188/188, t20 184/184, t21 93/93 |

Not tested: that a failing anchor leaves the docs untouched. The script now collects every edit in memory and writes at the end, which I read but did not exercise with a broken anchor.

## Round-4 items

| Item | State |
| --- | --- |
| S1 authenticated is not partner | Closed. Non-XML parts are requested only for a message that is authenticated and matched to exactly one active partner; the cap counts quarantined records of messages not matched; the rationale for having no daily limit now holds. Rule 25, the ADR-0052 and ADR-0051 notes, DS-04, DS-35, EC-147 and the lab (`matched`, `mailbox_plan`, `after_read`) agree |
| S2 apply on `base-uom-sim` | Closed: shorter anchor, two passes |
| Nit 1 one record per file | Applied: `source_attachment_id` unique among incoming records; a second import returns the first |
| Nit 2 safe XML | Applied in the reader contract: no DTD, no external entity, no expansion, depth 64, size bound |
| Nit 3 blank reason | Applied; the database refuses it (lab X40d and a direct probe of the pattern) |
| Nits 4, 5 scope of a tainted continuation | Applied: the pairing is the draft estimate's two revision IDs; the list is closed and names what goes beyond ADR-0050 rule 25; impact evidence of a change is left to a person; item (o) says the same |
| Nit 6 overflow item | Applied: the owner imports or closes |

## The question on the partner

Can an unauthenticated sender reach "matched" through a seller tax ID written inside the XML? No.

- "Matched" is one thing only: the interaction's match of ADR-0052 rule 15, which runs only when sender authentication passed and needs exactly one active partner. The gate for reading non-XML parts and the cap both use it, and nothing else (lab `matched`).
- The tax ID inside an XML feeds only `partner_id`, which selects mapping rules. It does so only when the signature is `passed`, which needs a certificate whose subject is that seller. An unsigned, failed or mismatched XML naming a known supplier gives an empty `partner_id` (lab M05 and the cases after it).
- A stranger who forwards a supplier's genuine signed XML gets that record imported, which is correct: it is a real invoice to this company, and the buyer tax ID rule holds. The other parts of that message stay stored only, because the message is not matched.

## Nits

1. Suppliers often send e-invoices through a provider's mail server, so the message is not matched although the XML passes. Its PDF is then stored only and never linked as the rendering. Consider running the companion test (the invoice number as a token in the text layer, no OCR) for PDFs of a message whose XML passed, matched or not.
2. A message a person matches later with `MatchInteraction` gets no automatic request for its stored parts. Say that the person requests them from the message.
3. The decisions left to the author are unchanged and should be listed at acceptance: value trust, the reader run's reads and writes, the tainted catalog read, the scope of a tainted continuation (o), the vision seat and its provider, the gate for field-level personal values, the `l10n_vn` format annex, certificate mapping and policy values, and the product code series.

## Confirmed sound

- Value trust: normalized values only, closed shapes, codes and units only when resolved, the extraction's highest rule run, vision values only after a person's confirmation; what was served is stored per step.
- Authenticity apart from trust: four signature conditions, quarantine, supersession, key conflict, one record per file, a cap that loses nothing.
- Core neutrality: no national rule in the core, no default policy, signature treated by the package's declaration.
- Numbers from code; a tool-less tainted vision run behind a four-eyes permission; the model never sees a cost.
- ADR-0062: three entry points, exactly-one resolution, attribute tokens, proposal items by stable ID, binding with the unit snapshot, split setup and run flags, release blocked in command and database, approver other than the run's human, taint kept across continuations.
- DDL and catalogs load and check on both bases; accepted ADRs are changed by notes only.
