# ADR-0061 Barcodes: independent review, round 2 (2026-11-15)

Reviewed: a fresh copy of `docs/` at branch `ds-uom`, ec0c126, plus the revised `drafts/ds-barcode/apply_barcode.py` (54 writes over 33 files). Paths are relative to `docs/` after the apply script.

## Verdict: NOT YET

0 blocking, 1 should-fix, 6 nits. B1, S1 to S11 and the round-1 nits are all fixed and verified. The one should-fix is new, small, and comes from the S5 fix.

Labs, each on a fresh database: t19 166/166, t17 114/114, t14 83/83, t15 146/146 (`--load`); t01 16/16 and t05 62/62 on the standard load; t12 187/187.

## Should-fix

**S1. `barcode.sscc_reuse_months` is a regime setting with a core default, which ADR-0016 rule 10 does not allow without a note, and rule 12 may then block it.**
`adr/0061-barcodes.md:79`, `:249`; `adr/0016-localization-package-structure.md:50-52`.
- ADR-0016 rule 10: a regime setting with no row fails with `regime_configuration_missing`; its note says "one key has a core default" and names `documents.issuance_without_delay`. This would be a second one. No note is added, and rule 28 does not list ADR-0016 rule 10.
- ADR-0016 rule 12: an operation that reads an `unverified` regime setting fails in production with `regime_setting_unverified`, with no override. The ADR itself calls the 12 months unverified, so `DeleteBarcodeReservation` on a retired SSCC could never run in production, or the basis of a core default is undefined.
- The period is a GS1 rule, the same in every country, so nothing makes it a regime matter.

Fix: make it a company setting like the other `barcode.*` settings (default 12, flagged in open questions, as it already is). Otherwise add the note to ADR-0016 rule 10, state the default's basis against rule 12, and list it in rule 28.

## Nits

1. `Set` in the glossary is "replace a record's whole list of values in one command" (`spec/00-reading-guide.md:543`). `SetLotBarcode` and `SetSerialNumberBarcode` replace one value. I proposed these names in round 1; the reading is defensible (replace, not merge), but rule 10 says each verb keeps its existing meaning, so add "or one value" to the glossary intent, or make the barcode a field of the lot and serial update commands.
2. With the character check gone, the database accepts an empty lot or serial code (probe: `''` inserted). That was also true before this ADR; a `CHECK (code <> '')` on `lot` and `serial_number` costs nothing.
3. "Prefixes do not overlap" is held only by the command: the database accepts `8931` beside `8931234` (probe), and no invariant covers it. Add it to INV-621 or say it is a command rule.
4. EC-120's expected outcome is `must_reject:scan_unresolved|must_succeed`. DS-17 rule 22 defines `|` for outcomes that "depend on the actor"; here it is a sequence. Either say so in the description column only, or split it into two events.
5. Licence wording (`adr/0061-barcodes.md` rule 21; `adr/0002-core-technology-tools.md:33`): the claim is right, see below. Add that whoever distributes the worker image must ship Zint's licence text and offer its source, and write the CLI's licence as GPL-3.0-or-later if the build check confirms it.
6. A supplier's SSCC that comes back after the reuse period still answers `barcode_retired` until a person with level `full` deletes the reservation, once per pallet. Consider letting a new handling unit take a retired SSCC once the period has passed.

## Licence check (asked for)

- The core is AGPL-3.0 (`spec/18-license-governance.md:5`). ADR-0003 names no other licence.
- Running the Zint command-line program as a separate process is aggregation, not a combined work, so its GPL-3.0 does not reach the core and the core's AGPL does not reach Zint. Even linking would be allowed: GPL-3.0 section 13 and AGPL-3.0 section 13 permit combining the two.
- libzint (BSD-3-Clause), ZXing-C++ and the GS1 Syntax Engine (both Apache-2.0) may be used in an AGPL-3.0 work.
- I did not open Zint's source tree in this review; that the CLI is GPL-3.0 and the library BSD-3-Clause is from my own knowledge and matches the draft. The ADR already says "to verify at build".
- Spec 18's rule on plugins "running in the core's process" does not apply to a separate program.

## Round-1 findings, verified

| Finding | Check | Result |
| --- | --- | --- |
| B1 | Unique index `ux_barcode_numeric_padded`; t19 D47 from two connections | The second insert waits, then fails with `barcode_taken`; one row stays |
| S1 | Lab probe: legacy `123456789012` scanned as `]E0` + `0123456789012`; database probe: legacy `0123456789012` then `123456789012` | Resolves to the bin; the second code is refused |
| S2 | Lab probe: numeric lot `2511047` without identifier | Resolves with the item in context; `lot_needs_item` without one |
| S3 | Lab probes on `separator_suspect` | Not raised for a known lot, with a GS elsewhere, or with `decoder: wasm`; raised for an unknown value from a wedge and for a real lost GS; passes with `confirmed_as_read` |
| S4 | `numbering_barcode_invalid` in rule 9 and DS-04; INV-623 extended; `is_barcoded` in `document_check_row_change` | Probe: a change of `is_barcoded` is refused |
| S5 | `retired_owner_id`, revival in the trigger, `UpdateItemBarcode` | Probe: a bin goes back to its old code, twice; an item takes its deleted GTIN back; another item is refused; after a move the retired owner is the new item |
| S6 | Rule 18 and the ADR-0056 rule 13 note | No rounding; trailing zeros accepted; else `too_many_decimal_places`, an existing code |
| S7 | Names, glossary, verb catalog | No `ResolveBarcode`, `ReserveBarcode`, `ReleaseBarcode` or `AssignBarcode` left outside the options table; the verb catalog and ADR-0004 are unchanged; C10 accepts `Get`, `List`, `Evaluate`, `Render` |
| S8 | DDL and the ADR-0020 and ADR-0044 notes | Probe: `LOT 2026/11` is stored; INV-622 asks an internal barcode for codes that do not fit (10) or (21) |
| S9 | Rule 22, ADR-0002 note, open questions | BarcodeDetector limited to EAN/UPC and ITF; the device, Dictionary, Syntax Engine, SSCC period, prefix length and Zint items are all listed as open |
| S10 | Lab probe `(01)(17)(10)LOTA(21)S1` | One serial candidate carrying the lot |
| S11 | Table `gs1_company_prefix`, one generation prefix by a partial unique index | Probes: a second generating prefix and a three-digit prefix are refused |
| Nits | Legacy first character, flag immutability, `~` only in element strings, unlisted identifiers, Digital Link rightmost key, second GS1-128 symbol, `general_access` rows, EC order, glossary nouns, ADR-0056 status, unreadable candidates, check page, `gtin14`, invariant area | All present. Probe: a change of `is_legacy_barcode` is refused |

Builder decisions: the revival owner as `item_id` is sound, since a barcode names an item in a unit and `UpdateItemBarcode` covers the move. The plain database error for `is_legacy_barcode` is fine, as no command changes the flag. Prefix length 4 to 12 matches what I know of GS1 and is flagged unverified.

## Not verified

- The GS1 facts the ADR itself flags (predefined-length table and AI pairs against the current Dictionary, Digital Link key search, SSCC reuse period, prefix lengths) were not checked against GS1 documents here; they are carried as open questions.
- Row-level security is by the generated-policy convention and is not enabled by the lab load.

Cleanup done: database `nativeflows_lab_rv61` dropped, `/tmp/rv61` deleted; the repository and the drafts were not changed.
