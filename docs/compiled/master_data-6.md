Module: master_data    Chunk: 6 of 8    Source ADRs: ADR-0056, ADR-0057, ADR-0061
Build step(s): 4, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `master_data`, chunk 6

## Purpose

`master_data` owns partners, products, items, units, prices, organization and warehouse structures, and the barcode
registry; it sits in layer 3 (ADR-0022.R2). This chunk states the closing rules of units of measure (the amended rules,
catalog rows and lab check of ADR-0056), the extraction mapping rules of document intake, and the first part of barcodes
(ADR-0061 rules 1 to 9): the GS1 parser, check digits, dates and measures, Digital Link, the registry, internal and legacy
codes, and document barcodes. Document intake, analysis, automation and configuration units named here are owned by
other modules and traced `ref:`.

## Entities and tables

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `barcode` | One row per barcode of a company across every type; written by the trigger `barcode_register` (R1070-R1081) | `id` (`DEFAULT uuidv7()`); unique `uq_barcode_company_id_barcode` (`company_id`, `barcode`) | `company` | `master_data` |
| `extraction_mapping_rule` | A correction turned into a rule: label anchor, column header or unit text of a partner and purpose (R1010-R1013) | `id`; unique (`company_id`, `id`) | `partner` | `master_data` |

DDL: `docs/design/DS-20-master-data.sql` (`barcode`, its index `ux_barcode_numeric_padded`, the function
`barcode_normalize` and the trigger `barcode_register`); `docs/design/DS-36-document-intake.sql`
(`extraction_mapping_rule`).

Reads and constrains, with rows in other chunks or modules: `item_barcode` (`barcode`, `is_legacy_barcode`, `uom_id`),
`bin` (`barcode`, `is_legacy_barcode`), `handling_unit` (`barcode`, `is_legacy_barcode`), `lot` (`barcode`),
`serial_number` (`barcode`), `document` (`is_barcoded`), `numbering_configuration`, `gs1_company_prefix`, `partner`,
`partner_item`, `uom_alias`, `product` (`country_of_origin`).

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateExtractionMappingRule` | `master_data_change`, change-tracked; leaf `partner` at `edit`; agents and consumers only through a change proposal | partner, purpose, `rule_kind`, normalized source text, target field path or unit code, `is_active` | Creates an `extraction_mapping_rule` (R1011) | not stated | not stated |
| `UpdateExtractionMappingRule` | `master_data_change`, change-tracked; leaf `partner` at `edit`; agents and consumers only through a change proposal | the rule and its changed fields | Changes an `extraction_mapping_rule` (R1011) | not stated | not stated |

Not commands: the pure library `nativeflows.gs1` (R1021); the AFTER trigger `barcode_register` on each typed table
(R1073); a consumer of `ExtractionFieldCorrected` that drafts mapping-rule proposals (R1012). The barcode commands
`CreateBarcodeReservation`, `DeleteBarcodeReservation` and the job `RunRetiredSsccCleanup`, which the rules of this
chunk use, are registered by ADR-0061.R10.

Codes raised by the rules of this chunk, bound to no command here: `gs1_invalid` (reasons `ai_unknown`, `length`,
`format`, `check_digit`, `date`, `pair_required`, `pair_forbidden`, `repeated_differs`, `separator_suspect`),
`scan_malformed`, `barcode_not_normalized`, `barcode_taken`, `barcode_retired`, `barcode_reuse_period_running`,
`barcode_format_invalid`, `barcode_prefix_reserved`, `numbering_barcode_invalid`, `permission_denied`; check results
`gs1_element_ignored` and `legacy_code_gtin_like`. Unit codes catalogued by R1003 and R1004.

## Rules

### Units of measure: amended rules, catalog rows and lab check

R1001. Multiple units of measure amend accepted rules, each by a note at the end of the rule: ADR-0006 rules 11, 15 (the line snapshot and exactness; rounding modes by use); ADR-0016 rules 18, 19 (core translations of unit names and the package's statutory names); ADR-0018 rules 8 to 14 (unit names, retirement and catalogs; exact units for serials; item-level rows, surrogate key and resolution; the snapshot and the cumulative rule, with `quantity_rounds_to_zero` widened to forward parts; the proposed-unit order and defaults in any allowed unit; retire and replace, which replaces "cannot be removed or changed" with a way out; barcodes and packaging); ADR-0019 rule 6 (the partner item's unit proposes the line's unit); ADR-0020 rules 3, 18 (material lines carry the source line's inventory quantity; counts in several units); ADR-0023 rules 6, 14, 18 (handling units against packaging; the pick breakdown, the default pick unit and follow-up tasks for recomputed parts; count entry units); ADR-0024 rules 2, 6, 15, 18, 22 (the supplier order unit and container units; units in planning; lot sizing in the order unit, proposals rounded up; the planned order's order unit; request lines carry it); ADR-0030 rule 9 (imports resolve unit text through aliases); ADR-0033 rules 6, 7 (the component snapshot, the alignment of rule 6's text, issue multiples, scrap rounding and precision; the outputs' snapshot and their half-up rounding); ADR-0034 rules 8, 11 to 13 (posted lines keep their snapshot; issue, backflush and receipt lines carry the block); ADR-0041 rule 22 (the seam for quantity-based taxes and the customs unit); ADR-0044 rules 3, 9 (units first in phase 2, sales history in the inventory unit; opening stock lines carry the block); ADR-0045 rules 3, 4, 13 (price entries in any allowed unit and at a replacement, with the next-business-date remedy; `convert_quantity` in `find_price`; the unit command checks); ADR-0046 rule 15 (configured items' own units in the configured price); ADR-0047 rules 1, 2, 7, 8, 11, 13 to 15, 17, 20, 21 (the clearing's registration; follow-on units and copies; prices of returns and credits in another unit; the receipt tolerance on the ordered quantity; positions with the cumulative rule and the GR/IR rounding clearing; the match per inventory unit and the tolerance amount's unit; purchase return and credit lines with the block; promotion quantities; limits with the unit rounding tolerance; the clearing's posting); ADR-0049 rule 25 (the line's own unit and its name on prints); ADR-0051 rule 21 (D2 and D3 in units); ADR-0053 rule 16 (core translations and package statutory names of units).
Source: ADR-0056.R24

R1002. Units of measure add the catalogs `units.csv` (the core units) and `unit-conversions.csv` (the direct pairs), owner DS-20, version 0.1.0, listed in the catalogs README. A package's `i18n/<language>/unit_names.csv` is checked by `check_package.py` against `units.csv`: every core unit named once, with a basis; the `l10n_vn` draft is DS-19's and is flagged package content. The regime setting `documents.unit_name_max_length` bounds unit names on statutory outputs.
Source: ADR-0056.R25

R1003. Unit errors: `uom_retired`, `uom_kind_mismatch`, `serial_unit_not_exact`, `uom_conversion_conflict` and `uom_packaging_inconsistent` (validation); `uom_conversion_in_use` and `price_entry_starts_today` (precondition); `uom_not_allowed` is widened to units.
Source: ADR-0056.R25

R1004. Unit check results: `unit_inexact`, `unit_text_unresolved`, `product_uom_replaced`, `uom_factor_changed`, `part_quantity_recomputed`, `part_quantity_clamped`, `gr_ir_rounding_cleared`, `gr_ir_rounding_clearing_reversed`, `unit_name_too_long` and `unit_step_below_inventory_step`; `quantity_rounded` and `quantity_rounds_to_zero` are restated for units; `reversal_not_latest` notes that the GR/IR rounding clearing never counts.
Source: ADR-0056.R25

R1005. The document type `gr_ir_rounding_clearing` (module `purchasing`, internal, a consequence posting) has its authorization leaf under `purchasing`, and GR/IR gains the posting kind `rounding_clearing`.
Source: ADR-0056.R25

R1006. Units of measure hold the invariant block `INV-600` to `INV-619`: `INV-600` (unit block present and consistent), `INV-601` (cumulative parts), `INV-602` (stock only in the inventory unit), `INV-603` (line factor in force), `INV-604` (serial units exact) and `INV-605` (product units classified, area master data); `INV-606` (`unit_of_own_company`) checks the single-column unit keys (ADR-0017.R19.N4), and `INV-607` to `INV-619` are unused. Their edge cases are `EC-101` to `EC-109`, `EC-130` and `EC-131`. Each row stands with the rule its catalog source names.
Source: ADR-0056.R25

R1007. The lab check `t17_uom.py` tests as pure functions: `convert_quantity` resolution (item, product, global in both directions, no chaining, retired rows); exactness; the cumulative rule on the 7/3 bag, returns of a part, and random sequences of parts, whole and partial returns, reversals in any order and parts in other units; the unit rounding tolerance both ways, growing only by changes of the deviation (zero for exact units), parts of zero or less rejected with the smallest quantity that would post, the unit step warning, clamped parts, the per-posting growth of T and the gross-error bound on forward parts and returns, over 20,000 sequences with inventory units of 0 to 3 decimals and entered units of 0 to 2; money returns following their stock returns on the purchase and sales side; invoices sourced by the order line; the GR/IR rounding clearing fired, reversed by a later credit and fired again; provisional parts recomputed at Post and drafts re-resolved after a retirement; price entries, transitive packaging and item-level rows at a replacement; catalog rows; the fold table; the carton and g↔kg examples; `round_quantity` modes and scrap; the serial whole factor; the proposed-unit order; supplier minimum and multiple in the order unit; three-way match per inventory unit; the price-break example; packaging consistency; the issue multiple; alias normalization.
Source: ADR-0056.R26

R1008. With `--load`, on all DDL loaded by `load_all.py`, `t17_uom.py` tests: a purchase order in cartons, receipts in pieces, an invoice in cartons, and GR/IR at zero; the bag order with cumulative receipts; the unit block present on every quantity line table; the database refusing bad factors and snapshots; retirement and the default pick unit; retire and replace of a kg row on the same unit (old lines keep the old snapshot, new lines take the new factor, one active row); item barcodes unique per company; the clearing posting kind; `INV-603` over every line table, by level and time in force.
Source: ADR-0056.R26

### Extraction mapping rules

R1010. `extraction_mapping_rule` (owner `master_data`, company data, change-tracked) holds partner, purpose, `rule_kind`, the normalized source text, the target field path or unit code, and `is_active`. `rule_kind` is `label_anchor` (a label text that precedes a field), `column_header` (a spreadsheet header that means a field) or `unit_text` (unit text that means a unit; where ADR-0056 applies it is proposed as a `uom_alias` instead). A partner's item code is a `partner_item` proposal (ADR-0051.R2), not a mapping rule.
Source: ADR-0057.R24

R1011. `CreateExtractionMappingRule` and `UpdateExtractionMappingRule` are `master_data_change` at `edit` on the leaf `partner`. An agent or consumer proposes them through a change proposal (ADR-0029.R2). Mapping rules are data, level L2 of ADR-0059.R1 (artifact kind `extraction_mapping`).
Source: ADR-0057.R24

R1012. A consumer of `ExtractionFieldCorrected` drafts a mapping-rule proposal, and never submits it, when the same correction for the same partner, purpose and field appears in at least two verified extractions in 90 days and conflicts with no active rule. The proposal copies untrusted text, so its version is tainted (ADR-0029.R8); a person submits it and another approves it.
Source: ADR-0057.R24

R1013. The deterministic share of fields per partner and purpose (verified without a correction, from rungs 1 to 6) is a metric of the quality monitor (ADR-0051.R7).
Source: ADR-0057.R24

### Barcodes: scope, parser and element strings

R1020. Barcodes rest on one GS1 parser on the server, which is the authority; one registry of every barcode of a company; one query that says what a scanned string is; label capture and printing. The core depends on no country: a country's traceability codes or digital product passports plug into a generic package hook, and the Vietnamese one is flagged for `l10n_vn` (ADR-0053). ZPL and a print agent, GS1 location and asset keys, Digital Link generation, an offline queue and SSCC assignment come after Phase 1.
Source: ADR-0061.D0

R1021. `nativeflows.gs1` is a pure library of the core (no I/O, no clock: the business date is a parameter), used by every command and query that reads a scan.
Source: ADR-0061.R1

R1022. The AI table is generated by `nativeflows-dev generate` from the GS1 Barcode Syntax Dictionary file, vendored at a pinned release with its version, into `backend/generated/gs1/`; nobody edits it by hand. Each entry gives the AI, its title, its components (numeric `N` or alphanumeric `X`, fixed or variable length, minimum and maximum), whether it has a predefined length, its linters (check digit, date, character set, decimal position), and the AIs it requires or excludes.
Source: ADR-0061.R1

R1023. The version `gs1_syntax_dictionary_version` is part of every parse result, so a stored result names the table it used. A new Dictionary release is a pull request that regenerates the table and runs the corpus; it is reviewed once or twice a year. The generator fails when the Dictionary breaks an assumption of these rules: an AI whose length does not follow from its first two digits, or a predefined-length prefix whose entries disagree on length.
Source: ADR-0061.R1

R1024. One test corpus, GS1's syntax tests plus NativeFlows's cases, runs in CI against the server parser and against the PWA's GS1 Syntax Engine (WebAssembly, Apache-2.0), pinned to a release that embeds the same Dictionary version. The PWA's result is feedback only; the server parses the raw scan again and decides (ADR-0061.R16).
Source: ADR-0061.R1

R1025. The predefined-length list of R1027 and the AI pairs named in R1033 come from the 2026-11-15 survey and GS1 documents, not from the current Dictionary, and are unverified; the lab uses a hand-written subset. The generated table and the corpus decide: the table and its lengths are generated from the Dictionary at build, a build-time verification (ADR-0061.R26.N1).
Source: ADR-0061.R1

R1026. A GS1 barcode carries element strings: an AI of two to four digits followed by its data. The first two digits of an AI give its length; the parser reads that many digits and looks the AI up. An AI the table does not hold is `gs1_invalid` with reason `ai_unknown`.
Source: ADR-0061.R2

R1027. AIs whose first two digits are 00 (20 characters in total, AI included), 01, 02, 03 (16), 04 (18), 11 to 19 (8), 20 (4), 31 to 36 (10) and 41 (16) have a predefined length; the parser reads exactly that many characters and needs no separator. Every other AI is variable or not predefined and ends at the separator or at the end of the data. The generated table, not this list, is authoritative.
Source: ADR-0061.R2

R1028. FNC1 in the first position marks a GS1 symbol; scanners transmit it as the symbology identifier. FNC1 after an element is transmitted as GS (ASCII 29). A leading GS is dropped. A GS after a predefined-length element is tolerated. A variable-length element that is not last must end with GS; data longer than the AI's maximum is `gs1_invalid` with reason `length`.
Source: ADR-0061.R2

R1029. A keyboard wedge that cannot send ASCII 29 sends a substitute character, named by the company setting `barcode.gs_substitute` (default `~`). The parser maps it back to GS only in data classified as an element string (ADR-0061.R13), never in a Digital Link URI, where `~` is legal, nor in internal codes, whose format excludes it; GS1 character set 82 excludes it too. One trailing CR, LF, CR LF or Tab is the scanner's suffix and is removed. Any other control character is `scan_malformed`.
Source: ADR-0061.R2

R1030. Parentheses are human-readable only: data that contains `(01)` style parentheses is not an element string. Manual entry may use the human-readable form; the screen converts it before the command, and the command records `source: manual`. A raw scan holds at most 512 characters.
Source: ADR-0061.R2

### Barcodes: validation, check digits, dates and Digital Link

R1031. After splitting, the parser checks every element against the table and reports the first failure per element as `gs1_invalid` with `details.reason`: `format` (an `N` component holds a non-digit, or an `X` component holds a character outside GS1 character set 82, which is letters A–Z and a–z, digits, and `! " % & ' ( ) * + , - . / : ; < = > ? _`, or, where the table says so, outside character set `39`); `length` (a fixed component of the wrong length, or a variable one outside its bounds); `check_digit` (a key with a wrong check digit, R1040); `date` (an impossible date, or day 00 where the AI does not allow it, R1046).
Source: ADR-0061.R3

R1032. Further `gs1_invalid` reasons: `pair_required` (an AI without one of the AIs the table requires with it, for example (21) without (01) or (8006), or (37) without (02) or (8026)); `pair_forbidden` (AIs that the table excludes together, for example (01) and (02)); `repeated_differs` (one AI twice with different values; twice with the same value is accepted once).
Source: ADR-0061.R3

R1033. `separator_suspect`: the last element is variable-length and its value ends with characters that themselves parse completely as one or more valid predefined-length elements, at least a date or a key with a valid check digit (`LOT1717261130` as lot `LOT1` followed by (17) 261130), the trace of a wedge that dropped the GS. It is not raised when the transport is proven (the scan holds a GS after its first element, or came from the WebAssembly decoder, which reports FNC1 itself, `scan.decoder: wasm`), nor when the whole value is an existing lot or serial of the scanned item or the one the step expects.
Source: ADR-0061.R3

R1034. What a raised `separator_suspect` does is the setting `barcode.separator_suspect` per scanner profile: `stop_and_confirm` (default) stops the scan, and the screen lets the person confirm the value as read (`scan.confirmed_as_read: true` in the next call) instead of typing it; `trust_transport` serves a profile proven to send GS (ADR-0061.R26).
Source: ADR-0061.R3, ADR-0061.R3.N1

R1040. GTIN-8, GTIN-12, GTIN-13, GTIN-14, SSCC, GLN and GDTI use one check-digit rule: weight the data digits 3, 1, 3, 1, … from the rightmost data digit leftward; the check digit is (10 − sum mod 10) mod 10. With the fictional company prefix `8931234` and item reference `56789` (data digits `893123456789`) the sum is 133 and the GTIN-13 is `8931234567897`.
Source: ADR-0061.R4

R1041. Every GTIN is stored and compared as 14 digits, left-padded with zeros (`08931234567897`). (01) always carries 14 digits. The symbology a scan came in is kept in the parse result, never in the key.
Source: ADR-0061.R4

R1042. A case of the same item with indicator digit 1 has data digits `1893123456789` and check digit 4: `18931234567894`. The check digit changes with the indicator, so it is computed, never copied. The packaging level a GTIN stands for comes from `item_barcode`'s unit, never from the indicator digit alone; indicator 9 marks a variable-measure trade item.
Source: ADR-0061.R4

R1043. An SSCC has 18 digits: extension digit, company prefix, serial reference, check digit; with extension 3, the fictional prefix and serial reference `000000000` it is `389312340000000005`.
Source: ADR-0061.R4

R1044. A GS1 prefix tells which GS1 member organization issued the company prefix, not where the goods were made. No rule derives a country of origin, a tax treatment or a supplier from a GTIN or SSCC prefix; origin is the product's `country_of_origin` (ADR-0021.R13).
Source: ADR-0061.R4

R1045. Dates (AIs 11, 12, 13, 15, 16, 17 and the date part of others) are YYMMDD. The century follows the GS1 sliding window against the business date of the step, never the wall clock, so a replay gives the same date: with D = YY − (business year mod 100), D ≥ 51 means the previous century, D ≤ −50 the next century, otherwise the current one. In 2026, `76` is 2076 and `77` is 1977.
Source: ADR-0061.R5

R1046. Day 00 is accepted only where the table's date linter allows it. Its reading is the setting `barcode.gs1.day00_policy.<ai>` per company and product category, `last_day`, `first_day` or `reject`: by default the last day of the month for (12) due, (15) best before, (16) sell by and (17) expiry (`barcode.gs1.day00_policy.<expiry_ai>`), and the first day for (11) production and (13) packaging (`barcode.gs1.day00_policy.<production_ai>`). A day 00 read as a day records `day_precision: month` in the element.
Source: ADR-0061.R5, ADR-0061.R5.N1

R1047. Variable measures (310n to 369n): the fourth digit n is the number of decimals, 0 to 5, so `3102001156` is 11.56. The unit follows the AI. Phase 1 maps the AIs whose unit is a core unit (ADR-0056.R2): 310n net weight to `KGM`, 311n length to `MTR`, 314n area to `MTK`, 315n net volume to `LTR`, 316n net volume to `MTQ`. Other measures, such as 320n in pounds or 330n gross weight of a logistic unit, stay in the parse result and are reported as `gs1_element_ignored`; they never become a quantity. Counts (30) and (37) are integers. An AI the parser does not map follows `barcode.unknown_ai_policy`.
Source: ADR-0061.R5, ADR-0061.R5.N1

R1048. A GS1 Digital Link URI `https://{domain}/{optional path}/01/{gtin}[/22/{cpv}][/10/{lot}][/21/{serial}][?17=YYMMDD&3103=000500]` is another encoding of element strings. Its primary key is the rightmost path segment that is a primary key AI of the table (01, 00, 414, 8003, 8004, 8006 and the others the Dictionary marks) followed only by its qualifiers, in the table's order, so `/00/01/{gtin}` reads as (01). The GS1 Syntax Engine is believed to search the same way; the shared corpus confirms it (unverified).
Source: ADR-0061.R6

R1049. In a Digital Link URI the query string adds data attributes whose keys are numeric AIs; query keys that are not AIs are ignored. Segments are percent-decoded. A GTIN of 8, 12 or 13 digits is padded to 14. Alphabetic short names and compressed Digital Link URIs are not read in Phase 1. The elements go through R1031 to R1047 like an element string. The parser never opens the URI: no network on the scan path, and no following of a link printed by someone else. The domain is kept in the result as untrusted text and plays no part in resolution.
Source: ADR-0061.R6

### Barcode registry

R1070. `barcode` (DS-20, module `master_data`) has one row per barcode of a company: `id`, `company_id`, `barcode` (normalized), `barcode_type`, `encoding` (`gtin`, `sscc` or `internal`), `is_legacy` (R1083), `retired_type`, `retired_owner_id`, `retired_at`, `recorded_at`. Its primary key is `id` with `DEFAULT uuidv7()`, because a trigger writes its rows (ADR-0006.R1.N2); (`company_id`, `barcode`) is the unique constraint `uq_barcode_company_id_barcode`.
Source: ADR-0061.R7

R1071. `barcode_type` is `item_unit` (an `item_barcode` row: item and unit), `bin`, `handling_unit`, `lot`, `serial`, `document` (R1090) or `internal`: a reserved code with no owner, either retired from another type (`retired_type` and `retired_owner_id` set) or reserved by the company with `CreateBarcodeReservation`, for labels of an old system still in circulation or badges a later feature reads.
Source: ADR-0061.R7

R1072. Typed tables keep their barcodes: `item_barcode.barcode` (with its unit, which ADR-0056 proposes on a line), `bin.barcode`, `handling_unit.barcode`, and nullable `lot.barcode` and `serial_number.barcode` for internal labels. Each typed table keeps its own uniqueness; the registry adds uniqueness across types. The typed tables plus one registry keep the unit binding and the surrogate key of `item_barcode` and give the query one lookup.
Source: ADR-0061.R7

R1073. `barcode_register`, an AFTER trigger on each typed table, inserts the registry row when a barcode is set, so no command can forget it. It refuses a value not in normalized form (`barcode_not_normalized`) and a GTIN or SSCC with a wrong check digit. Commands insert only reserved rows (`CreateBarcodeReservation`) and delete only reserved or retired rows (`DeleteBarcodeReservation`).
Source: ADR-0061.R7

R1074. The unique constraint keeps one row per code. The unique index `ux_barcode_numeric_padded` on (`company_id`, the code padded to 14 digits) over every code of 1 to 14 digits keeps a GTIN and a numeric legacy code, or two numeric legacy codes, from meaning the same digits (`08931234567897` and legacy `8931234567897`; legacy `0123456789012` and `123456789012`). Two transactions that insert colliding codes at once cannot both commit: the second waits for the first and fails. The trigger maps both violations to `barcode_taken`.
Source: ADR-0061.R7

R1075. Normalized form: a GTIN is 14 digits, an SSCC 18 digits, an internal code upper case, a legacy code upper case and never padded (R1083). Commands store the normalized form in the typed table; scans are normalized the same way before the lookup, so `a-03-02` typed on a wedge with caps lock finds `A-03-02`.
Source: ADR-0061.R7

R1076. Allowed encodings: `item_unit` takes a GTIN or an internal code; `handling_unit` an SSCC or an internal code; `bin`, `lot`, `serial` and `document` an internal code; `internal` any.
Source: ADR-0061.R7

R1077. When a typed row is deleted or its barcode changes, the trigger turns the old registry row into `internal` with `retired_type`, `retired_owner_id` and `retired_at`. The owner is the item for an item barcode and the row itself for the other types. A retired code is never given to another object, so a stale label resolves to `barcode_retired`, never to a new owner. When the same type and owner set the code again (a bin's barcode changed and then changed back to its old code, a barcode deleted and re-created on the same item), the trigger revives the row.
Source: ADR-0061.R7

R1078. `DeleteBarcodeReservation` (`human_only`, declared minimum level `full`, with a reason) deletes one reserved or retired row, when the company knows that no label with that code survives. For a retired SSCC it waits until `barcode.sscc_reuse_months` have passed since retirement (`barcode_reuse_period_running`). The period is a GS1 rule, the same in every country, so it is a company setting like the other `barcode.*` settings, default 12 months, unverified against the current GS1 General Specifications and flagged (ADR-0061.R26.N1).
Source: ADR-0061.R7

R1079. The daily system job `RunRetiredSsccCleanup` (registered `is_internal_only`, so no role holds it and it has no REST endpoint or tool; ADR-0054) deletes every retired SSCC row whose period has passed and whose company prefix is not one of the company's own prefixes, active or not (ADR-0061.R11), so a supplier's pallet label may be received again without a person. An SSCC under the company's own prefixes is deleted only by a person with `DeleteBarcodeReservation`, and NativeFlows never reissues one itself (ADR-0061.R25).
Source: ADR-0061.R7

### Internal, legacy and document codes

R1080. Every barcode that is not a GS1 key is an internal code: one upper-case ASCII letter, then up to 47 characters from `A`–`Z`, `0`–`9`, `-`, `.`, `/` and `_` (`barcode_format_invalid`). The leading letter keeps internal codes apart from GTINs, SSCCs and element strings, which start with a digit, and from Digital Link URIs. Text in any language belongs on the human-readable line of a label (ADR-0061.R21).
Source: ADR-0061.R8

R1081. Generated codes take a type prefix from company settings: `barcode.prefix.handling_unit` (`HU-`), `barcode.prefix.lot` (`L-`), `barcode.prefix.serial` (`SN-`), `barcode.prefix.item_unit` (`I-`), followed by a counter taken through the numbering lock helper (ADR-0009.R15). A bin's barcode defaults to its code (ADR-0023.R2) when the code fits the format; otherwise the person gives one.
Source: ADR-0061.R8

R1082. Lot and serial codes are kept as they come: the database refuses only an empty code and puts no character rule on them, so migration and suppliers' paper lot numbers (`LOT 2026/11`, codes longer than 20 characters) are stored unchanged. A lot or serial code is unique per item (ADR-0020.R17), not per company, so it is not a barcode. A code of 1 to 20 characters of GS1 character set 82 is printed in (10) or (21); any other code is printed through the lot's or serial's own internal barcode, which the command that creates such a lot or serial generates (ADR-0061.R21).
Source: ADR-0061.R8

R1083. Labels of an old system stay readable after migration (ADR-0044; ADR-0056.R21). `item_barcode`, `bin` and `handling_unit` carry `is_legacy_barcode` (default false), set when the row is created; the database refuses a change. Only an import batch or a person may set it; an agent's payload with it is refused with `permission_denied`. A legacy code is 1 to 48 characters of `A`–`Z`, `0`–`9`, `-`, `.`, `/` and `_`, upper case, starting with a letter or a digit; an old code with other characters (a space, `+`, `$`, `%`) is refused, and migration lists it for relabelling.
Source: ADR-0061.R8

R1084. A legacy code is registered with encoding `internal` and `is_legacy`, under its owner's type, and is unique in the registry; it is never padded, never parsed as GS1 and never treated as a GTIN. When numeric, it may not equal a registered GTIN or another numeric legacy code once both are padded to 14 digits (`barcode_taken`, held by `ux_barcode_numeric_padded`). A new numeric legacy code of 8, 12, 13 or 14 digits that passes a GTIN check digit gives the check result `legacy_code_gtin_like`: a scanner reading it as EAN-13 or UPC-A still finds it (ADR-0061.R13), but a supplier GTIN with the same digits can never be registered. New internal codes always follow R1080; a legacy code only keeps existing labels.
Source: ADR-0061.R8

R1090. A document type may be registered `is_barcoded` (a registry flag of printable types). Phase 1: purchase orders, goods receipts, sales orders, deliveries, transfer orders and production orders. The barcode is the document number: `document.is_barcoded` is set from the flag at Create and `document_check_row_change` refuses any later change; when such a document is numbered, the trigger registers its number in upper case as type `document`.
Source: ADR-0061.R9

R1091. The number format of a barcoded type must start with `{prefix}` followed by a separator (`/`, `-` or `.`). That string (`PO/`) is reserved: no barcoded type's reserved string may start another's, and no barcode of another type may start with one (`barcode_prefix_reserved`, checked when a barcode is created and when a numbering configuration is created or changed).
Source: ADR-0061.R9

R1092. When a numbering configuration of a barcoded type is created or changed, and when a branch code or fiscal year code that such a format uses is created or changed, the command checks that every number the format can produce is an internal code: its literal characters and the codes it uses are in the internal character set (letters in either case, since the number is registered in upper case), and its longest number, with the counter at full width, has at most 48 characters (`numbering_barcode_invalid`, naming the part that fails). The default format `{prefix}/{fiscal_year_code}/{counter:6}` (ADR-0009.R16) satisfies it when the codes do.
Source: ADR-0061.R9

## Invariants

Statements are those of `invariants.csv`; this chunk holds the rows whose catalog source is first a rule of this chunk.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-620` | `barcode_registry_complete` | day | Every barcode held by `item_barcode`, `bin`, `handling_unit`, `lot` and `serial_number`, and every number of a numbered `is_barcoded` document, has exactly one registry row of its type with its normalized value and its owner's legacy flag; every registry row of those types has exactly one owner row; every other row has type `internal`, and a retired one names its type and owner. | R1071-R1077, R1090 |
| `INV-621` | `gs1_keys_valid` | day | Every GTIN in the registry has 14 digits and every SSCC 18, each with a valid GS1 check digit; no two registry codes of 1 to 14 digits are equal once padded to 14; and the unit of every `item_barcode` is the inventory unit or a product unit of its item. | R1040-R1043, R1074, ADR-0061.R10 |
| `INV-622` | `internal_and_label_codes` | day | Every internal code in the registry is one upper-case letter followed by at most 47 of A-Z 0-9 - . / _, and every legacy code 1 to 48 of them starting with a letter or digit; every lot or serial whose code is not 1 to 20 characters of GS1 character set 82 has its own internal barcode. | R1080, R1082, R1083 |
| `INV-623` | `document_barcode_formats` | day | No reserved prefix of a barcoded document type starts another's, no registry row of another type starts with one, and every number a barcoded type's format can produce with the company's current branch and fiscal year codes is an internal code of at most 48 characters. | R1091, R1092 |

Named by a rule of this chunk, with rows in other chunks: `INV-600` to `INV-605` (R1006, R1008).

## Edge cases

| ID | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-120` | `wedge_without_separator`: A wedge scanner without GS substitution sends a label with (10) before (17); the lot value ends with a valid (17) date, and the scan stops with `gs1_invalid` reason `separator_suspect`. | `must_reject:scan_unresolved` | R1033, R1034 |
| `EC-121` | `bin_code_equals_item_barcode`: A bin is created with a barcode that an item unit already holds; the registry refuses it. | `must_reject:barcode_taken` | R1072, R1074, ADR-0061.R10 |
| `EC-122` | `variable_measure_receipt`: A label with (01) indicator 9 and (3103) is received into an item kept in kilograms (identity) and into one kept in grams (through the catalog conversion); a (3105) measure with a non-zero fifth decimal is refused with `too_many_decimal_places`. | `must_succeed` | R1047, ADR-0061.R18, ADR-0056.R9 |
| `EC-125` | `old_bin_label_after_relabel`: A bin's barcode is changed; a worker scans the old label at the bin and gets `barcode_retired`, never another bin. | `must_reject:scan_unresolved` | R1077 |
| `EC-126` | `company_without_gs1_prefix`: A company without a GS1 company prefix labels items, lots and serials with internal codes and receives and picks by them; generating a GTIN is refused with `gs1_prefix_required`. | `must_succeed` | R1080, R1081, ADR-0061.R11 |
| `EC-127` | `digital_link_receipt`: A supplier item carries a GS1 Digital Link QR code with lot and expiry; the receipt captures them and no URL is fetched. | `must_succeed` | R1048, R1049 |
| `EC-128` | `legacy_codes_migrated`: Migration loads the old system's numeric bin and item labels as legacy codes; one item code passes a GTIN check digit and is listed with `legacy_code_gtin_like`; Code 128 scans of the bins and EAN-13 and UPC-A scans of the item codes resolve to their objects. | `must_succeed` | R1083, R1084, ADR-0061.R13, ADR-0044.R3 |
| `EC-129` | `separator_confirmed_as_read`: After the stop of `EC-120` the person checks the label and confirms the value as read (`scan.confirmed_as_read`); the receipt takes the lot as read and succeeds. | `must_succeed` | R1034 |

Named by a rule of this chunk, with rows in other chunks: `EC-101` to `EC-109`, `EC-130`, `EC-131` (R1006).

## Settings

No setting row stands in this chunk. `barcode.separator_suspect` (R1034), `barcode.gs1.day00_policy.<expiry_ai>` and
`barcode.gs1.day00_policy.<production_ai>` (R1046), `barcode.unknown_ai_policy` (R1047) and
`documents.unit_name_max_length` (R1002) have their rows in chunk 7, which also states the keys absent from
`settings.csv` that R1029, R1078 and R1081 name: `barcode.gs_substitute`, `barcode.sscc_reuse_months` and
`barcode.prefix.<type>`.

## Conflicts

CONFLICT ADR-0056.R25: the block's `INV-606` is no longer unused; ADR-0017.R19.N4 gives it to the check that a row names a core unit or a unit of its own company (`unit_of_own_company`); R1006 states it.
CONFLICT ADR-0061.R7: the DDL gives `barcode` the key `id uuid PRIMARY KEY DEFAULT uuidv7()` with the old natural key as `uq_barcode_company_id_barcode`, following ADR-0006.R1.N2; and the SSCC reuse period stays flagged by ADR-0061.R26.N1 (R1070, R1078).
CONFLICT ADR-0061.R1: the open check on the unverified predefined-length list and AI pairs is answered by ADR-0061.R26.N1, which makes the generated Dictionary table a build-time verification (R1025).

## Trace

| Source | Where |
| --- | --- |
| ADR-0056.R24 | R1001 |
| ADR-0056.R25 | R1002-R1006 |
| ADR-0056.R26 | R1007-R1008 |
| ADR-0057.R17 | ref: ADR-0057.R17 |
| ADR-0057.R17.N1 | ref: ADR-0057.R17.N1 |
| ADR-0057.R17.N2 | ref: ADR-0057.R17.N2 |
| ADR-0057.R24 | R1010-R1013 |
| ADR-0057.R26 | ref: ADR-0057.R26 |
| ADR-0057.R27 | ref: ADR-0057.R27 |
| ADR-0057.R31 | ref: ADR-0057.R31 |
| ADR-0058.R9 | ref: ADR-0058.R9 |
| ADR-0058.R9.N1 | ref: ADR-0058.R9.N1 |
| ADR-0059.R1 | ref: ADR-0059.R1 |
| ADR-0059.R1.N1 | ref: ADR-0059.R1.N1 |
| ADR-0059.R2 | ref: ADR-0059.R2 |
| ADR-0059.R4 | ref: ADR-0059.R4 |
| ADR-0059.R4.N1 | ref: ADR-0059.R4.N1 |
| ADR-0059.R16 | ref: ADR-0059.R16 |
| ADR-0059.R16.N1 | ref: ADR-0059.R16.N1 |
| ADR-0059.R16.N2 | ref: ADR-0059.R16.N2 |
| ADR-0060.R3 | ref: ADR-0060.R3 |
| ADR-0060.R5 | ref: ADR-0060.R5 |
| ADR-0060.R7 | ref: ADR-0060.R7 |
| ADR-0060.R10 | ref: ADR-0060.R10 |
| ADR-0060.R14 | ref: ADR-0060.R14 |
| ADR-0060.R16 | ref: ADR-0060.R16 |
| ADR-0060.R22 | ref: ADR-0060.R22 |
| ADR-0060.R26 | ref: ADR-0060.R26 |
| ADR-0061.D0 | R1020 |
| ADR-0061.R1 | R1021-R1025 |
| ADR-0061.R2 | R1026-R1030 |
| ADR-0061.R3 | R1031-R1034 |
| ADR-0061.R3.N1 | R1034 |
| ADR-0061.R4 | R1040-R1044 |
| ADR-0061.R5 | R1045-R1047 |
| ADR-0061.R5.N1 | R1046, R1047 |
| ADR-0061.R6 | R1048-R1049 |
| ADR-0061.R7 | R1070-R1079 |
| ADR-0061.R8 | R1080-R1084 |
| ADR-0061.R9 | R1090-R1092 |
