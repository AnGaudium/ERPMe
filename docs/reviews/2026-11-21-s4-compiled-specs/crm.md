# Review: compiled spec `crm` (S4)

Spec files: `specs/crm-1.md` (R1 to R23), `specs/crm-2.md` (R201 to R263), `specs/crm-3.md` (R401 to R472), linted
together. Index 30d5706. Reviewer: Claude Opus 5.5 (a different model from the compiler, Claude Fable 5.2), 2026-11-21.
Brief: `review-brief.md`. Assignment: spot check N=20, seed 3105, plus the erasure gate (ADR-0052.R7 against
ADR-0019.R10.N2 and ADR-0079.R7 with its notes) in full.

## Verdict

**FAIL: 2 BLOCKING, 1 SHOULD-FIX, 5 NOTE.** The 20 sampled units are all faithful, and all 18 CONFLICT resolutions are
right. The erasure gate is stated almost right: the spec carries ADR-0079.R7 and its notes into R7 and R20. But R7 leaves
out the clause that ties the marker to its idempotency record ("with that `id`"), and with it the session-company
condition. Separately, the command register (R441) still says "no flag" for the job and outcome commands that
ADR-0054.R8.N1 registers `is_internal_only`. This contradicts the spec's own tables in chunks 2 and 3, and no Conflicts
entry records it. The bar is 0/0, so the module does not pass.

## 1. Lint

`doc_lint.py specs/crm-1.md specs/crm-2.md specs/crm-3.md --module crm`: `LINT PASS findings=0`. Units 134, rules 72,
notes 61, R-numbers 158, trace rows 134. Retention: crm-1 93% (lowest ADR-0019.R12 12/23, ADR-0019.R9 8/10). These
units' replaced identifiers (`source`, `purpose`, `basis`) are left out on purpose, which is expected. crm-2 and crm-3
reach 100%. REVIEW LIST: CONFLICT 18, FALSE-POSITIVE 0, OPEN 0. SUPERSEDED RULES: 1 (ADR-0052.R18, "superseded by its own
text"). STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=20, seed 3105)

Population: the 84 source IDs whose trace `Where` holds R-numbers (all three chunks; `ref:` and `not applicable` rows
left out). The sample is `random.Random(3105).sample(sorted(ids), 20)`. For each sampled ID I read the whole rule with all
its notes, plus the units its Conflicts entry names.

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0052.R28.N1 | R423 | FAITHFUL |
| 2 | ADR-0052.R16 | R233-R236 | FAITHFUL |
| 3 | ADR-0029.R14.N3 | R18 | FAITHFUL (the "author rewords spec 03 rule 1" open item is closed by N4/N5, so it is rightly not restated) |
| 4 | ADR-0052.R25.N1 | R409 | FAITHFUL |
| 5 | ADR-0052.R9 | R204-R206 | FAITHFUL |
| 6 | ADR-0019.R15 | R14 | FAITHFUL (kind and owner per N1, N2; public domains per ADR-0052.R5) |
| 7 | ADR-0019.R17 | R16 | FAITHFUL |
| 8 | ADR-0052.R10 | R207-R209 | FAITHFUL |
| 9 | ADR-0052.R5 | R8 | FAITHFUL (deferral history and "this settles ADR-0019" are left out; they are not law) |
| 10 | ADR-0052.R18.N2 | R241 | FAITHFUL |
| 11 | ADR-0052.R2 | R3 | FAITHFUL ("DS-22's" sentence replaced per R2.N1) |
| 12 | ADR-0052.R25.N2 | R409 | FAITHFUL |
| 13 | ADR-0052.R30 | R434, R435 | FAITHFUL (reserved setting replaced per R30.N1) |
| 14 | ADR-0052.R12 | R216-R219 | FAITHFUL |
| 15 | ADR-0029.R14 | R18 | FAITHFUL (recommendation dropped per N6) |
| 16 | ADR-0052.R4 | R6 | FAITHFUL |
| 17 | ADR-0052.R20.N1 | R250 | FAITHFUL |
| 18 | ADR-0052.R29 | R432, R433 | FAITHFUL to the rule text; see crm-S1 for the catalog disagreement |
| 19 | ADR-0052.R13 | R220-R223 | FAITHFUL |
| 20 | ADR-0052.R20 | R249-R251 | FAITHFUL |

**Error rate: 0 of 20 (0%).** Both BLOCKING findings come from the erasure gate and section 6, not from the sample.

Reverse check: `random.Random(3105).sample(sorted(R-numbers), 10)` gave R437, R255, R219, R428, R13, R22, R237, R466,
R404 and R409. Each clause of these has a source in the cited units: ADR-0052.R31, R22, R12, R28, ADR-0027.R14,
ADR-0019.R20, ADR-0052.R17 with N1 and N2, ADR-0057.R25, ADR-0052.R25, and R25 with N1 and N2. One NOTE: R255's
generalization to every localization package (crm-N4).

## 3. Superseded rules, CONFLICT entries, false positives

- **SUPERSEDED ADR-0052.R18:** the resolution is right. No unit replaces the rule. The index flag comes from the words
  "superseded partners". R241 to R244 state the rule with N1 (read owner scope) and N2 (sold-to partner) folded in.
- **CONFLICT entries (18): all right.** Each one has the later accepted unit win, and each statement holds the
  superseding text:
  - ADR-0019.R9 → `lawful_basis`, `processing_purpose_id` (R19, R256).
  - ADR-0019.R10, ADR-0052.R7 → two erasure commands; marker per ADR-0079.R7 notes (R7, R20). See crm-B1 for a dropped
    clause inside that statement.
  - ADR-0019.R12 → ADR-0052.R6 and R13 (R9, R10).
  - ADR-0019.R14 → `provider_message_key`; a copy row instead of a skip (R12).
  - ADR-0019.R15 → `inbound_message_matched`, `role:sales_clerk` (R14).
  - ADR-0029.R14, N3, N5, N6 → scope not widened, one auto-post exception (R18).
  - ADR-0052.R2 → R2.N1 (R3).
  - ADR-0048.R17 → N1 DDL facts (R23).
  - ADR-0052.R24, R30.N1 → retention class `crm_interaction` (R263, R434).
  - ADR-0052.R11.N1, ADR-0057.R25 → `shop_floor_report` by ADR-0064.R27, which matches DDL `ck_mailbox_document_intake_purpose`
    (R210, R456).
  - ADR-0052.R28 → R28.N3 for searchable connectors (R429).
- **Missing CONFLICT entry:** ADR-0052.R32 against ADR-0054.R8.N1 (crm-B2).
- **FALSE-POSITIVE:** none listed.

## 4. Erasure gate, in full (ADR-0052.R7 against ADR-0019.R10.N2 and ADR-0079.R7 with N1 to N3)

I also read ADR-0038.R4 with N1 to N4, ADR-0079.R6, ADR-0052.R25 with N1 to N3, and the DDL (`erasure_marker_valid` in
DS-05, `crm_check_append_only` and its triggers in DS-35).

What the spec gets right (R7, R20, R410, Conflicts):
- There are two erasure commands, `EraseDataSubject` and `DestroyRetainedPersonalData`, with the same catalog-driven
  hooks, and either may blank append-only content. ADR-0019.R10's "the one command" is correctly replaced
  (ADR-0019.R10.N2).
- The erasure scope that each module's consumer opens through `audit.contract` sets the marker. The dispatcher no longer
  sets it for `EraseDataSubject` alone (ADR-0079.R7, N1).
- The idempotency record must have scope `EraseDataSubject` or `DestroyRetainedPersonalData`, be written in the same
  transaction rather than merely committed (N1 supersedes the "committed" wording), and belong to the row's company (N2).
- A changed column may take only an erasure result of ADR-0079.R6. N1 and ADR-0038.R4.N3 say so, and the DS-35 trigger
  calls `erasure_column_change_allowed`.
- The column lists of the erasure-only bullet match the DS-35 trigger arguments: subjects, bodies, addresses, names, raw
  `Message-ID`, sender authentication, failure reason, requester data, outcome note, `content_salt`, `erased_at`.
- The draft-delete gate and the processing log's own trigger are kept.
- The retention class `crm_interaction` replaces "a retention rule the author decides" (ADR-0052.R30.N1).

Defects: crm-B1 (below). NOTEs crm-N3 and crm-N5. SOURCE-1 and SOURCE-2.

## 5. Consistency with DDL and catalogs

- **Error codes:** every DS-04 error and check-result code in the spec appears in `DS-04-command-envelope.md`.
- **Work item kinds** (chunk 3 table): equal to `work-item-kinds.csv` rows of module `crm` in subject, owner, due and
  resolution. `e_invoice_quarantine_overflow` is correctly attributed to `tax`.
- **Work case kinds:** `customer_issue` and `customer_onboarding` match `work-case-kinds.csv`. `quote_request` is
  correctly `sales`.
- **Authorization leaves and verb levels:** match `authorization-areas.csv` and `authorization-verb-levels.csv`.
- **Invariants and edge cases:** INV-49, INV-98, INV-500 to INV-505, and EC-84 to EC-91, EC-99, EC-100, EC-137, EC-240
  and EC-241 match the catalogs verbatim.
- **Settings:** `settings.csv` has no `crm.` key and no `cash.dunning.levels`, as the spec says. The rows it lists under
  Reads for `agents.tainted_reference_reads` and `messaging.message_retention_days` match.
- **DDL:** these are present:
  - mailbox columns, including `document_intake_purpose` with `shop_floor_report` and quarantine limit default 20;
  - `processing_basis.lawful_basis` with the consent-evidence check and the current-basis unique index;
  - `contact.is_accounts_contact` (DS-20);
  - the append-only trigger lists.
  `partner_collection` has no DDL, which the spec states (R23).
- **Personal data catalog:** it disagrees with ADR-0052.R29 on `identity_proof_hash` (crm-S1, SOURCE-3).

## 6. Sections 2, 3, 5 to 8 (spot-read)

The spot-read found no invented authorization area, event, error code or setting. Every event in the tables is in
ADR-0052.R33, R12 or R10, or is a generated document event. The commands tables draw `is_internal_only` correctly from
ADR-0054.R8.N1 for the intake, probe, sender and scan commands, so they are right, but R441 contradicts them (crm-B2).

## Findings

### BLOCKING

**crm-B1:** `specs/crm-1.md:88`, R7, source ADR-0079.R7.N1 (also ADR-0079.R7.N2, ADR-0038.R4.N3).
- **Source:** the marker is valid only when `erasure_marker_valid()` finds an `idempotency_record` **with that `id`**
  (the marker's value), of an erasure scope, written in the same transaction. The consumer writes that record "of the
  originating command's type, keyed by that command's ID and the consumer's name" and sets the marker to the record's ID.
  The record must belong to the current company (`nativeflows.company_id`; null-company records only under
  `installation`) and also to the row's company. The DDL checks all of these (`id = $1`, session company, row company).
- **Spec:** "finds an `idempotency_record` of scope `EraseDataSubject` or `DestroyRetainedPersonalData` for the row's
  company, written in the same transaction". This drops the condition that the record is the one the marker names, and
  drops the session-company condition. Read literally, any erasure record in the transaction validates any marker value.
- **Fix:** write "finds the `idempotency_record` whose `id` is the marker, of scope `EraseDataSubject` or
  `DestroyRetainedPersonalData`, written in the same transaction, of the session's company and of the row's company
  (ADR-0079.R7.N1, N2; ADR-0038.R4.N3)".

**crm-B2:** `specs/crm-3.md:215` (R441, also lines 199-200 and 208) and `specs/crm-3.md:45` (`RecordPartnerTaxLookup`
row), source ADR-0052.R32 against ADR-0054.R8.N1.
- **Source:** ADR-0054.R8.N1 registers these as `is_internal_only` (no role holds them at any level, no REST, MCP or tool
  definition): `RecordInboundMessage`, `RecordMailboxIntakeOutcome`, `RecordMailboxAuthenticationCheck`,
  `RecordOutboundMessageOutcome`, `RecordPartnerTaxLookup`, `RunPartnerDuplicateScan` and
  `RunPartnerInsightComputation`. A declared `full` stays only for `RunMailboxIntake`.
- **Spec:** R441 says "Per command: ... no flag ... unless its line says otherwise". It gives
  `RunPartnerDuplicateScan`, `RunPartnerInsightComputation` and `RecordPartnerTaxLookup` "no flag", and it gives the
  `Record…` lines only "only for …". The chunk 3 row for `RecordPartnerTaxLookup` says "level not stated" with no
  `is_internal_only`. The chunk 2 table already says `is_internal_only` for the others, so the spec contradicts itself.
  ADR-0054.R8 is not traced and there is no Conflicts entry.
- **Fix:** add `is_internal_only` to those seven commands in R441 and in the `RecordPartnerTaxLookup` row (citing
  ADR-0054.R8.N1), trace ADR-0054.R8.N1 as `ref:`, and add `CONFLICT ADR-0052.R32: ADR-0054.R8.N1 governs ...`.

### SHOULD-FIX

**crm-S1:** `specs/crm-3.md:166`, R432, source ADR-0052.R29.N1 with `personal-data-fields.csv`.
- **Source:** the catalog wins over the R29 table. The catalog row `data_subject_request_content,identity_proof_hash`
  is `personal`, subject kind `requester`, condition `always`.
- **Spec:** keeps the ADR table line "hashes (including `identity_proof_hash`): internal". It states the
  precedence sentence but does not flag that this line is the one in disagreement.
- **Fix:** label `identity_proof_hash` personal per the catalog, and add a CONFLICT entry for ADR-0052.R29 naming the
  catalog row. The ADR side is SOURCE-3.

### NOTE

- **crm-N1:** `specs/crm-2.md:104`, R210. The statement includes `shop_floor_report` without naming ADR-0064.R27 inline.
  Only the Conflicts entry names it, whereas R456 does. Add "(the last value by ADR-0064.R27)".
- **crm-N2:** `specs/crm-3.md:215` and `specs/crm-2.md:53`. Once crm-B2 is fixed, align the two tables' wording.
- **crm-N3:** R7 and R401 to R411. R7 says that each module's consumer opens the erasure scope, while R401 to R411
  (ADR-0052.R25, "stays as this rule defines it") describe `crm`'s blanking as the effect of `EraseDataSubject` itself.
  The spec does not say which transaction blanks `crm`'s own rows, and R444 lists no `crm` consumer of
  `DataSubjectErased` or `PersonalDataDestructionDue`. This follows the sources (SOURCE-1). An open-question pointer
  would help the builder.
- **crm-N4:** `specs/crm-2.md:270`, R255. "The purposes a localization package seeds are flagged package content"
  generalizes ADR-0052.R22's `l10n_vn` sentence. It is true by ADR-0052.R24 (R263), but that rule is not cited here.
- **crm-N5:** R7. The spec could add the binding that ADR-0079.R7 gives: the scope is bound to the command's subject and
  due classes, so a consumer cannot rewrite another subject's or class's rows. It also leaves out ADR-0079.R7.N2/N3: the
  database does not prove who may erase; only `erasure_command_record()` writes erasure records. Both are `audit` law,
  so pointers suffice.

## SOURCE findings (do not count against the spec)

- **SOURCE-1:** ADR-0052.R25 (with N3) and R33 against ADR-0079.R7. ADR-0079.R7 says each module destroys its own tables
  in its consumer of `DataSubjectErased` or `PersonalDataDestructionDue`, in the consumer's transaction, under a marker
  from that consumer's record. ADR-0052.R33 registers no `crm` consumer of either event. But `DestroyRetainedPersonalData`
  must blank `crm` rows of class `crm_interaction` (ADR-0052.R7, R30.N1). The sources do not say whether `crm` blanks its
  own rows inside `EraseDataSubject` or in a consumer, and a `crm` consumer of `PersonalDataDestructionDue` is missing.
- **SOURCE-2:** ADR-0052.R7 draft deletes. The rule says "DS-36 checks that an idempotency record of a generated
  `Delete` command for that document exists in the same transaction". The delete branch of `crm_check_append_only`
  (DS-35) checks only `nativeflows.document_delete_id` and the document's `draft` state. No idempotency check exists.
- **SOURCE-3:** ADR-0052.R29 labels `identity_proof_hash` internal, while `personal-data-fields.csv` labels it
  `personal`/`always`. Per R29.N1 this is a defect of the ADR table, which no note corrects.
- **SOURCE-4:** ADR-0052.R32 carries no note for ADR-0054.R8.N1, so its table still shows "—" for seven commands that are
  now `is_internal_only`.
- **SOURCE-5 (minor):** INV-504 says erasure columns are "empty", but ADR-0079.R7.N1 also allows the token result
  `erased-<hex>`, and `erasure_column_change_allowed` admits it in `crm` columns. The invariant should say "hold an
  erasure result" or the `crm` hooks should be restricted to NULL or blank.
