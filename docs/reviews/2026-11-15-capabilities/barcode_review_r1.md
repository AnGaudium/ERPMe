# ADR-0061 Barcodes: independent review, round 1 (2026-11-15)

Reviewed: branch `ds-uom` at ec0c126 plus `drafts/ds-barcode/apply_barcode.py` (53 writes over 34 files). Paths below are relative to `docs/` after the apply script; line numbers are those of the review copy.

## Verdict: NOT YET

1 blocking, 11 should-fix, 14 nits.

Labs on fresh databases: t19 139/139, t17 114/114, t14 83/83, t15 146/146 (all `--load`); t01 16/16 and t05 62/62 on the standard load (stubs + DS-20, DS-56, DS-06); t12 187/187. The findings below come from reading the design and from my own probes on the loaded DDL and on the lab functions; the labs do not cover them.

## Blocking

**B1. The legacy-code against GTIN collision is not held by the database under concurrent inserts.**
`design/DS-20-master-data.sql:812-817` (trigger `barcode_register`); `adr/0061-barcodes.md:85`; INV-621.
The check is `IF EXISTS (SELECT ...) THEN RAISE` followed by the INSERT. Two transactions that each see no conflicting row both commit. Reproduced on the loaded DDL: session 1 inserts the legacy item code `5000112637922`, session 2 inserts the GTIN `05000112637922`, both commit, and the registry holds both rows. The registry exists so that "a scan never means two things"; here an EAN-13 scan of the old label resolves to the other object. The plain cross-type case is safe (the primary key serializes it); only the padded comparison is not.
Fix: replace the EXISTS test by a unique expression index, `CREATE UNIQUE INDEX ux_barcode_numeric_padded ON barcode (company_id, lpad(barcode, 14, '0')) WHERE barcode ~ '^[0-9]{1,14}$'`, and map its violation to `barcode_taken`. It also closes S1. Add a two-connection check to t19.

## Should-fix

**S1. The legacy fallback misses UPC-A, and two numeric legacy codes may differ only by leading zeros.**
`adr/0061-barcodes.md:86` (promises a legacy code read "as EAN-13 or UPC-A still finds it") and `:118`; `lab/t19_barcode.py:459`.
The fallback looks the code up "in its scanned digits". With the AIM identifier on, which rule 23 ships as the profile, `]E0` carries UPC-A as 13 digits with a leading zero. Lab probe: legacy `123456789012` scanned as `]E0` + `0123456789012` gives `barcode_unknown`. The database also accepts legacy `0123456789012` and legacy `123456789012` side by side.
Fix: compare numeric legacy codes by their digits padded to 14 (the index of B1 makes that unique), and say so in rule 13 step 3.

**S2. A numeric lot or serial code scanned alone resolves only when the scanner sends an identifier.**
`adr/0061-barcodes.md:117` against `:120`; `lab/t19_barcode.py:385`.
Step 2 ends with "otherwise `barcode_unknown`" for data that starts with a digit and is not GS1, so step 5 is never reached. Lab probe with the task item in context: lot `2511047` with `]C0` resolves to the lot; without an identifier (every BarcodeDetector scan) it is `barcode_unknown`. Numeric lot codes are common.
Fix: in step 2, digit-leading data that fails as a GTIN and as an element string falls through to steps 4 and 5; `barcode_unknown` only after them.

**S3. `separator_suspect` blocks valid labels for good.**
`adr/0061-barcodes.md:47`; `lab/t19_barcode.py:217`.
The trace fires on any last variable element whose value ends with a valid predefined-length element. Lab measurement: 0.22 to 0.43 % of random numeric serials of 10 to 20 digits, and every date-coded lot such as `B11250101` or `SN17261231`. Rescanning never helps, so each such lot or serial must be typed at every step.
Fix: do not raise it when (a) the scan holds a GS elsewhere or came from a decoder that preserves FNC1, since the transport is then proven; or (b) the whole value is an existing lot or serial of the item, or the one the step expects. Otherwise keep the stop, and let the person confirm the value as read instead of typing it.

**S4. A barcoded document can fail to post on a raw check violation.**
`adr/0061-barcodes.md:92`; `design/DS-05-platform.sql:1463`; `design/DS-20-master-data.sql:754`.
Rule 9 validates only the prefix and its separator. The whole number is registered as an internal code, and `{branch_code}` and `{fiscal_year_code}` have no character rule. Probe: barcoded numbers `PO/HCM 01/2026/000007`, `PO/2026+/000007` and one longer than 48 characters all fail in the numbering transaction with `ck_barcode_format`. A company with such a branch code cannot post any purchase order.
Fix: validate the whole format when the numbering configuration is created or changed and when a branch or fiscal year code it uses is created or changed (literal characters, the codes, the total length), with a typed error. Also add `is_barcoded` to the immutable columns of `document_check_row_change` (`DS-05-platform.sql:1189`); rule 9 says it never changes and nothing holds it.

**S5. A retired code cannot return to its own owner, and what `ReleaseBarcode` may delete is unclear.**
`adr/0061-barcodes.md:76`, `:98`; `design/DS-20-master-data.sql:736-737`, `:800`.
- Probe: a bin changed from `R-01` to `R-01X` cannot be changed back; a GTIN deleted from the wrong item cannot be created on the right one. Both end in `barcode_pkey`. Linking a supplier GTIN to the wrong item is routine, and the only way out is a `human_only` command at level `full`. No command moves an item barcode to another item or unit.
- The DDL comment reads as if `ReleaseBarcode` deletes only rows without `retired_type`; rule 7 and the constraints section say a person releases retired codes; t19 D16 deletes a retired row.
- Rule 7 says "SSCCs are never reused, as GS1 requires", yet `ReleaseBarcode` may delete a retired SSCC. As far as I know GS1 requires no reallocation within one year (the survey says the same, line 334), so a supplier's SSCC may legitimately come back and would then be `barcode_retired`.

Fix: add `UpdateItemBarcode` (item, unit) for corrections; store `retired_owner_id` and let the trigger revive a row retired from the same type and owner; state that `ReleaseBarcode` deletes reserved and retired rows but never a company-issued SSCC; reword the GS1 sentence as ERPMe policy for its own SSCCs.

**S6. Rule 18 rounds a scanned measure, which ADR-0006 rule 14 and ADR-0056 rule 8 forbid.**
`adr/0061-barcodes.md:157`; `lab/t19_barcode.py:529`.
ADR-0056 rule 8: "An entered quantity with more decimals than its unit holds is rejected, never rounded (ADR-0006 rule 14)". Rule 18 rounds half up with `quantity_rounded`, and no note on either accepted rule says so. The ADR-0056 rule 13 note is silent on it.
Fix: accept a measure whose extra decimals are zero (`3105 0115600` is 1.156); reject the rest with the existing error, or add explicit notes to ADR-0006 rule 14 and ADR-0056 rule 8 that a measure AI is the one exception, and list them in rule 28.

**S7. Four verbs take a second meaning, against ADR-0004 rule 20.**
`adr/0061-barcodes.md:97-98`, `:110`, `:244`; `spec/00-reading-guide.md:527`, `:559`; `catalogs/authorization-verb-levels.csv:15`.
Rule 20: "A verb never takes a second meaning; a different action gets a different verb."
- `Reserve` is "hold stock for a demand line"; `ReserveBarcode` blocks a code.
- `Release` is "make a draft revision of master data effective"; `ReleaseBarcode` deletes a reserved code. Its verb level is `post`.
- `Assign` is "set the owner of a work item or task, or attach output serials"; `AssignBarcode` sets a label code.
- `Resolve` now has two glossary rows with two meanings, and the note sits on rule 21, not rule 20.

Fix: `CreateBarcodeReservation` and `DeleteBarcodeReservation` (declared minimum `full`, `human_only`); `SetLotBarcode` and `SetSerialNumberBarcode`, or a field of the lot and serial update commands. For the query, `EvaluateBarcode` fits the existing third query form ("computes a result from the inputs it is given and stores nothing") and removes the fourth form, the catalog row with two meanings and the C10 change. If `Resolve` stays, put the note on rule 20 and merge the two glossary rows.

**S8. The database check on lot and serial codes breaks migration and non-GS1 supplier lots.**
`design/DS-20-master-data.sql:676`, `:683`; `adr/0061-barcodes.md:81`; the ADR-0020 rule 17 note.
Every lot and serial code must now be 1 to 20 characters of GS1 character set 82. Probe: lot `LOT 2026/11` is refused. Old lots and suppliers' paper lot numbers with a space, a `#` or more than 20 characters cannot be stored, and ADR-0044 gains no path for them, while barcodes got the legacy path. The check is not needed: `lot.barcode` and `serial_number.barcode` exist exactly for a code that cannot go into (10) or (21).
Fix: drop the two checks to a label rule: a lot or serial whose code fits (10) or (21) is labelled with GS1 data, any other with its internal barcode. Keep `tracking_code_invalid` for control characters and length only, or apply the character set only to codes created by a GS1 capture.

**S9. BarcodeDetector behaviour with FNC1 and GS is unverified and not flagged.**
`adr/0061-barcodes.md:189-190` against `:116-117`; `open-questions.md` (barcode section).
The survey lists "BarcodeDetector GS1 FNC1 output on the target Android devices" as an open verification item. The ADR carries only the Vietnam item forward.
- Line 190 says a leading FNC1 or GS "or embedded GS" marks GS1 data; step 2 names only a leading GS.
- Line 116 promises a plain Code 128 starting with `01` is never parsed as GS1. On Chrome for Android, the main device, no identifier arrives, so that promise does not hold there, and every camera scan reports `scan_heuristic_used` with advice about a scanner prefix.

Fix: flag it in open questions and DS-31. Use BarcodeDetector only for formats that need no identifier (EAN/UPC, ITF) until the check page proves GS pass-through on a device, and the WebAssembly decoder for Code 128, DataMatrix and QR. Align step 2 with line 190. Also carry forward the survey's item on the predefined-length table and the AI pairs: rule 3 states pairs as fact, and t19 tests a hand-written table.

**S10. A label with (01), (10) and (21) is not specified, and the lab drops the serial.**
`adr/0061-barcodes.md:118`; `lab/t19_barcode.py:450`.
Step 3 names (01) with (10) and (01) with (21) apart. Lab probe: `(01)(17)(10)LOTA(21)S1` returns one lot candidate and no serial. A step that expects a serial would answer `scan_mismatch`.
Fix: one candidate of type `serial` that also carries the lot (the output schema has both fields), and a t19 check.

**S11. One immutable GS1 company prefix is a dead end.**
`adr/0061-barcodes.md:103`; `design/DS-04-command-envelope.md` rows `gs1_prefix_required` and `gs1_prefix_in_use`.
`gs1_prefix_required` also fires when "item references are used up", and the prefix can never change once used. A nine-digit prefix gives 1000 items; companies then license a second prefix.
Fix: a list of prefixes with one active for generation. A generated GTIN keeps its digits; only removing a prefix in use is refused.

## Nits

1. `adr/0061-barcodes.md:83` and INV-622 let a legacy code start with `-`, `.`, `/` or `_`; `DS-20-master-data.sql:755` requires a letter or digit first (probe: `-123` refused). The ADR-0044 note says "any other old code" loads; codes with a space, `+`, `$` or `%` (the Code 39 set) are refused. State the limit.
2. `is_legacy_barcode` "never changed" is not held: an UPDATE of the flag alone leaves the registry row at `is_legacy` false (probe), since the triggers fire on `UPDATE OF barcode` only (`DS-20-master-data.sql:823-830`).
3. `adr/0061-barcodes.md:35`: `~` "never occurs in real data", but it is a legal URI character. Apply the substitute only to data classified as an element string (`lab/t19_barcode.py:283` replaces it everywhere).
4. `adr/0061-barcodes.md:116`: say what an unlisted identifier means (`]I0`, `]E3`, `]C2`, `]Q2`, `]L0`); the lab treats it as plain data. `]I1` means ITF with a validated check digit, not ITF-14 as such.
5. `adr/0061-barcodes.md:63`: the parser takes the first primary-key segment. I believe the GS1 Syntax Engine searches from the right; a custom path such as `/00/01/{gtin}` would then split the two parsers. Not verified; confirm with the corpus. Say that compressed Digital Link URIs are not read.
6. `adr/0061-barcodes.md:177`: (00) with (02), (37) and (10) can exceed the 48 characters of one GS1-128 symbol. Say that the label splits into two symbols.
7. ADR-0002 note (`adr/0002-core-technology-tools.md:48`): the three tools are listed by the note, so they are allowed. Zint is a backend tool but the note sits under the frontend table; its Python binding is not named (I know of no official one); the ZXing-C++ licence (Apache-2.0) is not stated. Zint has its own GS1 linter and AI table, which may disagree with the pinned Dictionary.
8. `adr/0061-barcodes.md:239` says the ADR-0054 rule 25 note covers the t12 changes; the note names only the edge cases. `catalogs/authorization-areas.csv:102` and the ADR-0054 rule 24 table list the members of `general_access` without `ResolveBarcode`. t12 does not record `human_only` for `ReleaseBarcode`.
9. `catalogs/edge-cases.csv:122-131`: EC-119 to EC-128 sit after EC-131, and are borrowed from the block of ADR-0054.
10. Glossary nouns are missing for the new names (ADR-0004 rule 17): Barcode, Item label, Lot label, Serial label, Scan.
11. `adr/0061-barcodes.md:225`, `:305`: ADR-0056 is called "proposed"; it is accepted.
12. `adr/0061-barcodes.md:110-113`: say what the caller gets when every candidate is unreadable (`barcode_unknown`, so nothing leaks), and the same for `barcode_retired`.
13. `adr/0061-barcodes.md:191`, `:195`: a wedge under an input method editor or a non-US layout changes characters, not only case. The check page should detect it.
14. `adr/0061-barcodes.md:95`: `generate` offers `gtin13` and `internal` only; a case GTIN-14 must be typed with its own check digit. INV-620 to INV-623 have area `warehouse` while the table is in `master_data`.

## Confirmed sound

- Check digits: the rule, the three worked examples (`8931234567897`, `18931234567894`, `389312340000000005`) and `gs1_check_digit_valid`.
- The predefined-length list matches GS1 as I know it (00, 01 to 04, 11 to 19, 20, 31 to 36, 41); AI length by first two digits holds for the current AIs.
- The guard against a wrong AI table: generated from a pinned Dictionary, version in every parse result, generator failing on the two length assumptions, one corpus for server and PWA, server as authority.
- Century window (76 is 2076, 77 is 1977 in 2026); 310n decimals and units; the listed symbology identifiers; Digital Link qualifier order and never fetching.
- Day 00 and (15) as expiry are flagged as interim in open questions.
- Plain cross-type uniqueness is held by the primary key, also under concurrent inserts; retirement keeps the code; null-safe checks; `company_id` and composite key on `barcode`. Row-level security follows the file's generated-policy convention; the lab load enables it on no DS-20 table, so it is not tested here.
- Typed issues, server re-resolution of `raw`, scan-to-confirm with override fields, `lot_needs_item`; untrusted text marked.
- Variable measure through `convert_quantity` and `uom_not_allowed` agrees with ADR-0056 rules 6 and 13, apart from S6.
- Vietnam stays behind `TraceabilityCodeProvider`, flagged unverified; the examples name no real company.
- All 19 notes sit on the rules that rule 28 names; INV-620 to INV-623 and EC-119 to EC-128 do not collide; t12 C23b gives each of the 9 new names a leaf and a level; `ReleaseBarcode` resolves to `full`.

Cleanup done: database `erpme_lab_rv61` dropped, `/tmp/rv61` deleted; the repository and the drafts were not changed.
