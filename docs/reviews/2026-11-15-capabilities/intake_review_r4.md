# Review r4: ADR-0057 Document intake and extraction; ADR-0062 Product engineering workflow

Date: 2026-11-15. Reviewer: independent (read-only). Tested on copies of `base-ds-uom` and `base-uom-sim`; neither base nor the drafts were changed.

## Verdict: NOT YET

0 blocking, 2 should-fix, 6 nits. Round 3's S1, S2 and S3 and its seven nits are applied and hold. One of the two remaining items is mechanical; the other is a wrong premise behind dropping the daily limit.

## Lab

Fresh `nativeflows_lab_rv57` for every `--load`; no "out of shared memory" occurred.

| Copy | Result |
| --- | --- |
| `base-ds-uom` + `apply_intake.py` (84 writes, 41 files) | t20 181/181, t21 93/93, t12 186/186, t15 146/146, t16 99/99; `check_package.py` on `DS-19-vietnam-tt99`, regime `tt99`: RESULT PASS (run with the system Python; the lab venv has no `yaml`) |
| `base-uom-sim` + `apply_intake.py` | Does not apply: see S2 |
| `base-uom-sim` + a temporary copy of the script with that one anchor shortened | Applies (84 writes, 41 files); t12 188/188, t20 181/181, t21 93/93 |

## Round-3 items

| Item | State |
| --- | --- |
| S1 quarantine cap | Closed as designed: decided after the read, counts only unauthenticated messages, the extraction stays `extracted` with `quarantine_limit_reached`, `e_invoice_quarantine_overflow` to the mailbox owner, nothing canceled, `pending → canceled` left for renderings only (0057:96, 0057:237; lab `after_read`). The premise of the dropped limit: S1 below |
| S2 tainted continuation | Closed: every draft the proposal releases, `tainted_at` whenever set, scope `subject`, open-question item (o). Nits 4 and 5 |
| S3 INV-644 | Closed, in the ADR and the catalog |
| Nits 1 to 7 | Applied: distance in either direction, the override entries checked by the database, `extracted` reworded, a person's upload path, the backlog row, the receipt date |

## Should-fix

**S1. "Authenticated" is not "partner", so nothing bounds an authenticated stranger.** 0057:236-238 ("No daily part limit"), ADR-0052 rules 14 and 15.
- Sender authentication passes for any sender whose own domain passes DMARC or DKIM (ADR-0052 rule 14). Matching the sender to a partner is a separate step (rule 15). The rationale says "authenticated senders are the company's partners"; they are not.
- With the daily limit gone and the cap counting unauthenticated messages only, anyone with a correctly set up domain or a freemail address can send any number of parts. Each PDF costs a local OCR run and a `document_extraction_review` item for the accountants; OCR is not an agent run, so no agent budget bounds it. Vision runs are bounded, but a stranger can spend the company's daily reader budget (USD 10, 300 runs) and leave real documents without it. Unsigned XML from such a sender is imported quarantined without any cap.
- Round 2's R6 asked to keep "authenticated senders" outside the limit; that wording was mine and was too loose.
- Fix: gate on the match, not on authentication alone. Non-XML parts are read automatically only when the message is authenticated and matched to exactly one active partner (ADR-0052 rule 15); otherwise they are stored only, as for unauthenticated senders. The quarantine cap counts records of messages that are not matched. Then the stated rationale is true and no other limit is needed. Adjust rule 25, the two ADR-0052 notes, EC-147 and the lab's `mailbox_plan` and `after_read`.

**S2. `apply_intake.py` does not apply to `base-uom-sim`.** `apply_intake.py:615`.
- The backlog edit of the DS-24 row anchors on `rule 20 note). | Spec |`. In `base-uom-sim` a UoM simulation note now follows that sentence, so the anchor is found 0 times and the script stops with an assertion, after it has already written 39 files.
- Fix: anchor on `([ADR-0051](../adr/0051-agent-workflows.md) rule 20 note).` alone and insert after it. With only that change the script applies and the labs pass on that base (table above). The appended UoM note itself (unit text on the record's lines stays untrusted) agrees with rule 17.

## Nits

1. Double import. A quarantined record holds no key, so two people importing the same listed extraction from the overflow item, or a manual `ImportEInvoiceRecord` on a file the route already imported, give two quarantined records of one file. The key check at confirmation lets only one through, so no invoice is doubled, but say "one incoming record per source attachment" and let the second import return the first.
2. Unauthenticated XML is now parsed without any limit. Add to the reader contract (rule 5) that XML readers resolve no DTD and no external entity and bound depth and expansion.
3. DS-36 `ck_document_extraction_rule_overrides` accepts a reason of blanks only (probe); the other cases are refused (missing or empty reason, `shape`, non-object entries, non-text values). Trim in the check or leave it to the command and say so.
4. 0062 rule 3: "the paired routing revision and estimate" is not defined. Say the pairing is the draft estimate's `bill_of_materials_revision_id` and `routing_revision_id`.
5. Open question (o): the list is closed, which is right, but it uses "recorded provenance" for child rows and for an estimate found by a reverse key, which ADR-0050 rule 25 uses only for IDs a row carries. Say so in (o), add the items of the components and the category requirements, and state that a tainted continuation of an engineering change leaves the impact evidence (where-used, open orders, stock) to a person.
6. The overflow item is resolved "when each listed extraction is imported or the owner closes it"; the catalog row names only `ImportEInvoiceRecord`.

## The points to check most closely

- **Can the overflow path lose an invoice?** No. The extraction is recorded, carries the check result, and is listed in one item per mailbox and receipt date for the owner, who holds `edit` on the leaf (checked when the purpose is set). A record with a passed signature never meets the cap.
- **Can it double-import?** Not by the system: the consumer reacts once to the recording, and the same bytes are the same attachment. By people, yes, as two quarantined records; only one can be confirmed (nit 1).
- **Dropping the daily limit:** sound for unauthenticated senders (non-XML stored only, XML a deterministic read, cap of 20 on quarantined records). Not sound for authenticated senders, because authentication does not make a partner and OCR is outside agent budgets (S1).
- **The `subject` scope boundary:** enumerated and put to the author; acceptable as an interim reading with nits 4 and 5.
- **The `rule_overrides` check:** holds for every case tried except a blank reason (nit 3).

## Confirmed sound

- Value trust, trust at read with stored served trust, signature conditions, quarantine, supersession and key conflict are unchanged from round 3 and still hold.
- Core neutrality, Principle 13, the tool-less tainted vision run and the permission gate are unchanged.
- The new work item kind, check result, settings and notes are consistent across the ADR, DS-04, DS-35, the catalogs and ADR-0052's note; no duplicate codes.
