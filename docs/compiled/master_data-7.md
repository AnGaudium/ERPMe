Module: master_data    Chunk: 7 of 8    Source ADRs: ADR-0061, ADR-0062, ADR-0063, ADR-0067, ADR-0068
Build step(s): 1, 2, 3, 4, 5, 9    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `master_data`, chunk 7

## Purpose

`master_data` owns the company's reference data: partners, products and items, units, warehouses, sites and the
organization (ADR-0022.R2), in layer 3. This chunk states the barcode commands, GS1 company prefixes, labels, capture and
scanner profiles of ADR-0061; the master data of the product engineering workflow (product code series, manufacturer part
numbers, category requirements) and its product code settings; the tainted item-candidate projection; unit-name and barcode
interpretation settings; record defaults of presets; sites, the site of a warehouse and the valuation level `site`; and
payment methods. Scan resolution, GS1 capture and site valuation costing are `inventory`'s, setting presets are `registry`'s,
and the workflow steps are `agents`'; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-20-master-data.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `gs1_company_prefix` | A GS1 company prefix of a company, with its generation flag and next item reference (R1208) | `id`, unique (`company_id`, `prefix`); exclusion `ex_gs1_company_prefix_overlap` | `company` | `master_data` |
| `code_series` | A master-data code sequence of record kind `product`, without fiscal year or branch (R1232) | `id`, unique nulls not distinct (`company_id`, `record_kind`, `product_category_id`) | `company`; `product_category` | `master_data` |
| `item_manufacturer_part` | A manufacturer's part number for an item (R1231) | `id`, unique (`company_id`, `id`), unique `uq_item_manufacturer_part` | `item` | `master_data` |
| `product_category_requirement` | A readiness requirement of a product category, rules as data (R1233) | `id`, unique nulls not distinct (`company_id`, `product_category_id`, `requirement`, `variant_attribute_id`, `classification_scheme_id`) | `product_category` | `master_data` |
| `site` | A site between the company and its warehouses (R1249) | `id`, unique (`company_id`, `code`), unique (`company_id`, `id`) | `company` | `master_data` |
| `payment_method` | A payment method of a company (R1260) | `id`, unique (`company_id`, `code`), unique (`company_id`, `id`) | `company` | `master_data` |

Columns this chunk's rules add to tables whose rows stand in other chunks: `warehouse.site_id` (R1251); `company.valuation_area_level` value `site` (R1257); `item_barcode.is_legacy_barcode` (R1202); the registry table `barcode` (R1207); `payment_method_id` on `customer_profile`, `supplier_profile` and the headers of R1261.

Reads: `item`, `item_barcode`, `barcode`, `uom`, `product_category`, `variant_attribute`, `classification_scheme`, `branch`, `working_calendar`, `business_unit`, `warehouse`, `company`, `lot`, `serial_number`, `bin`, `handling_unit`, `setting_value`, `setting_preset`, `material_document_line`, `preliminary_price`, `journal_line`, `quotation`, `sales_order`, `sales_invoice`, `purchase_order`, `purchase_invoice`, `payment`, `bill_of_materials_component`, `change_proposal_item`.

## Commands and queries

Authorization is the leaf of `authorization-areas.csv` and the verb level of `authorization-verb-levels.csv`; events are not stated by the sources of this chunk.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateItemBarcode` | leaf `product`; `master_data_change` | item, unit, `barcode` or `generate`, optional `is_legacy_barcode` | registers an item barcode, given or generated (R1202) | not stated | `uom_not_allowed`, `barcode_taken`, `barcode_format_invalid`, `barcode_prefix_reserved`, `gs1_prefix_required`, `barcode_reuse_period_running` |
| `UpdateItemBarcode` | leaf `product`; `master_data_change` | item barcode, item, unit | moves the barcode to another item or unit (R1203) | not stated | `uom_not_allowed` |
| `DeleteItemBarcode` | leaf `product`; `master_data_change` | item barcode | deletes the row; the code stays reserved (R1203) | not stated | not stated |
| `SetLotBarcode`, `SetSerialNumberBarcode` | leaf `warehouse`; `master_data_change` | the lot or serial, `barcode` or `generate: internal` | replaces its label code (R1204) | not stated | `barcode_taken`, `barcode_format_invalid` |
| `CreateBarcodeReservation` | leaf `product`; `master_data_change` | barcode, reason | reserves a code (R1205) | not stated | `barcode_taken` |
| `DeleteBarcodeReservation` | leaf `product`; `human_only`, declared minimum level `full` | barcode, reason | releases a reserved code (R1205) | not stated | `barcode_reuse_period_running` |
| `CreateGs1CompanyPrefix`, `UpdateGs1CompanyPrefix` | leaf `product`; `master_data_change` | prefix; the generation flag and `is_active` | maintains `gs1_company_prefix` (R1208, R1209) | not stated | `gs1_prefix_invalid` |
| `DeleteGs1CompanyPrefix` | leaf `product`; `master_data_change` | prefix | deletes an unused prefix (R1210) | not stated | `gs1_prefix_in_use` |
| `ListItemLabel` (query) | leaf `product` | item units, copies per unit | label rows with `barcode` objects (R1212) | none | not stated |
| `ListLotLabel`, `ListSerialLabel` (queries) | leaf `warehouse` | lots of an item; serials | label rows with `barcode` objects (R1212) | none | not stated |
| `CreateItemManufacturerPart`, `UpdateItemManufacturerPart` | leaf `product` at `edit`; `master_data_change`; proposals for agents | item, manufacturer name, part number | maintains `item_manufacturer_part` (R1231) | not stated | not stated |
| `SetProductCategoryRequirements` | leaf `master_data_group` at `edit`; `master_data_change` | category, requirements | replaces the category's `product_category_requirement` rows (R1233) | not stated | not stated |
| `ListItemCandidate` (query) | leaf `product`; declared tainted projection | typed match keys (code, barcode, normalized name) | at most 20 item rows per call (R1238) | none | `tainted_projection_cap_reached` |
| `UpdateSite` | leaf `site` (under `organization`); `master_data_change` | a site | changes a site (R1250, R1252) | not stated | `site_branch_mismatch`, `site_in_use` |

Not registered commands: `RunRetiredSsccCleanup`, the daily system job, registered `is_internal_only` with leaf `product`, which no level grants (R1205); the published package interface `TraceabilityCodeProvider` (R1219); the function `master_data.contract.site_of_warehouse` (R1251).

Checks of commands whose rows stand elsewhere: `CreateWarehouse` (`site_required`, `site_branch_mismatch`), `UpdateWarehouse` (`site_branch_mismatch`, `warehouse_site_fixed`), `CreateCompany` (the default site, an optional preset code; R1251, R1252, R1253, R1258). `EvaluateBarcode` sits under `general_access` (R1206). The leaf `payment_method` (under `master_data`) covers payment methods; the sources of this chunk name no payment method command.

Codes bound to no named command: `numbering_barcode_invalid` (R1207), `product_code_taken` and `product_code_immutable` (R1236), `unit_name_too_long` (R1242); check results `item_duplicate_suspected` (R1229) and `legacy_code_gtin_like` (R1226).

## Rules

### Barcode commands

R1201. Every barcode command is of effect class `master_data_change` unless stated, change-tracked, and runs in batches (ADR-0008). Each uses a verb in its existing meaning (ADR-0004 rule 20).
Source: ADR-0061.R10

R1202. `CreateItemBarcode` (item, unit, `barcode` or `generate`, optional `is_legacy_barcode`): the unit is the inventory unit or an active product unit of the item (`uom_not_allowed`, ADR-0056.R6). `generate: gtin13` takes the next item reference of the company's generation prefix (R1210) and computes the check digit. `generate: gtin14` with an indicator digit 1 to 8 builds a case GTIN from a GTIN-13 of the same item: the indicator, the GTIN-13's first 12 digits and a new check digit. `generate: internal` takes the item-unit prefix and counter. A GTIN maps to one item unit per company.
Source: ADR-0061.R10

R1203. `UpdateItemBarcode` (item barcode, item, unit) corrects which item or unit a barcode belongs to, such as a supplier GTIN linked to the wrong item; the code and its registry row stay. `DeleteItemBarcode` (item barcode) deletes the row; the code stays reserved for the item (ADR-0061.R7).
Source: ADR-0061.R10

R1204. `SetLotBarcode` and `SetSerialNumberBarcode` (the lot or serial, `barcode` or `generate: internal`) set its label code. They take the single-value form of Set, `Set<Record><Field>`, because no lot or serial update command carries the barcode as a field; the form replaces and never merges (ADR-0004 rule 20). A handling unit gets its barcode when it is created (`PackHandlingUnit`, a receipt, a migration import): a generated internal code, the SSCC of a supplier's label (ADR-0061.R17), or a legacy code. A bin changes its barcode with the bin's own update command (ADR-0023.R2), and takes a legacy code only when created by an import or a person.
Source: ADR-0061.R10

R1205. `CreateBarcodeReservation` (barcode, reason) and `DeleteBarcodeReservation` (barcode, reason; `human_only`, declared minimum level `full`) reserve and release a code (ADR-0061.R7). `CreateGs1CompanyPrefix`, `UpdateGs1CompanyPrefix` (the generation flag and `is_active`) and `DeleteGs1CompanyPrefix` maintain prefixes (R1208 to R1210). `RunRetiredSsccCleanup` is the daily system job of ADR-0061.R7, registered `is_internal_only` with leaf `product`, like `RunApprovalEscalation` (a note on ADR-0054 rule 24).
Source: ADR-0061.R10

R1206. Authorization leaves (ADR-0054):
   - under `product`: `CreateItemBarcode`, `UpdateItemBarcode`, `DeleteItemBarcode`, `CreateBarcodeReservation`, `DeleteBarcodeReservation`, `CreateGs1CompanyPrefix`, `UpdateGs1CompanyPrefix`, `DeleteGs1CompanyPrefix` and `ListItemLabel`, and `RunRetiredSsccCleanup`, which no level grants;
   - under `warehouse`: `SetLotBarcode`, `SetSerialNumberBarcode`, `ListLotLabel` and `ListSerialLabel`;
   - under `general_access`: `EvaluateBarcode`, which checks each candidate's own read permission (ADR-0061.R12).
   Source: ADR-0061.R10

R1207. Errors of the barcode commands: `barcode_taken` (any type in the company holds the code or its padded digits; `details` give the type and the owner's code when the caller may read it), `barcode_format_invalid`, `barcode_prefix_reserved`, `numbering_barcode_invalid`, `barcode_reuse_period_running`, `gs1_prefix_required`, `gs1_prefix_invalid` and `gs1_prefix_in_use`. Codes live in the registry table `barcode`.
Source: ADR-0061.R10

### GS1 company prefixes

R1208. GS1 is optional per company. Company prefixes are rows of `gs1_company_prefix`: `prefix` (4 to 12 digits), `is_active`, `is_generation_prefix` and `next_item_reference` (at least 0, default 0). A company may hold several prefixes, since a short licence runs out. At most one is the generation prefix, and it must be active (`ck_gs1_company_prefix_generation_active`); the database holds both.
Source: ADR-0061.R11

R1209. Prefixes of a company do not overlap (none starts another). An exclusion constraint on each prefix's range of 12-digit numbers (`ex_gs1_company_prefix_overlap`) holds it at every isolation level. The command reports a violation as `gs1_prefix_invalid`, as it does a prefix of invalid length; the exact valid length range is unverified.
Source: ADR-0061.R11

R1210. `generate: gtin13` needs a generation prefix with references left (`gs1_prefix_required`). An inactive prefix generates nothing new but stays the company's own, so the cleanup job of ADR-0061.R7 never deletes an SSCC under it. `DeleteGs1CompanyPrefix` is refused with `gs1_prefix_in_use` while any GTIN or SSCC of the registry, live or retired, lies under the prefix (its digits after the indicator or extension digit start with it); otherwise old prefixes are deactivated, not deleted. Resolution never depends on prefixes: every GTIN resolves through the registry.
Source: ADR-0061.R11

R1211. Company settings of barcodes: `barcode.gs_substitute` (default `~`), the wedge's GS substitute (ADR-0061.R2), and `barcode.prefix.<type>` (ADR-0061.R8). A company without a prefix works fully on internal codes and on the GTINs it receives from suppliers, which it registers with `CreateItemBarcode`.
Source: ADR-0061.R11

### Labels

R1212. Labels are print subjects over registered queries (ADR-0049.R25), rendered as PDF by the print worker from company templates. Existing subjects: bins (`ListBin`) and handling units (`GetHandlingUnit`). New subjects: `ListItemLabel` (item units, with copies per unit), `ListLotLabel` (lots of an item) and `ListSerialLabel` (serials, for receiving and for serials produced at a station, ADR-0034). Document prints of barcoded types get the derived field `document.barcode`.
Source: ADR-0061.R20

R1213. Each label row carries `barcode` objects computed by the core: `{symbology, data, human_readable}`. The template only places them, so it cannot build wrong GS1 data. The core ships neutral English templates for each subject (ADR-0049.R24). Symbologies and rendering are `reporting`'s (ADR-0061.R21).
Source: ADR-0061.R20

### Capture and scanner profiles

R1214. Camera capture in the PWA: until the scanner check page proves on a device that BarcodeDetector passes FNC1 and GS through, BarcodeDetector serves only the formats that need no identifier: EAN-13, EAN-8, UPC-A, UPC-E and ITF. That proof is a build-time verification on devices at step 9, not a design choice. Code 128, GS1-128, DataMatrix and QR go through a WebAssembly decoder based on ZXing-C++ (Apache-2.0), which reports the symbology identifier and FNC1 (`decoder: wasm`); it also serves every format where BarcodeDetector is missing (iOS, desktop Linux). The decoder and the GS1 Syntax Engine load on first use, outside ADR-0040's JavaScript budget, and DS-31 measures their size.
Source: ADR-0061.R22, ADR-0061.R26.N1

R1215. Camera UX: a target box, torch, the same value de-duplicated for 1.5 seconds, haptic and sound feedback with a distinct error tone, a tap to choose among several codes in view, and never an automatic submit while several codes are visible unless exactly one matches the expected type.
Source: ADR-0061.R22

R1216. Without an identifier from BarcodeDetector, the PWA sends `camera_format` (`ean_13`, `itf`, …), which stands in for the identifier; a leading or embedded GS marks GS1 data as in ADR-0061.R13 step 2. Keyboard wedge: scan screens keep one focused input with `inputmode="none"`. A scan is recognized by the AIM prefix `]`, the Enter suffix and timing (characters faster than a person types), and its `source` is `wedge`; slower input is `manual`. Every code field on desktop screens accepts wedge scans and resolves them with the field's expected type (a note on ADR-0040 rule 16).
Source: ADR-0061.R22

R1217. Scanner profiles: the core ships configuration for the supported rugged scanner families (a Zebra DataWedge profile, Honeywell and Datalogic setting codes): AIM symbology identifier on, GS replaced by `~`, Enter suffix, and the symbologies Code 128, GS1-128, DataMatrix, GS1 DataMatrix, QR, EAN/UPC and ITF on. DS-31 keeps a short list of tested devices.
Source: ADR-0061.R23

R1218. The PWA's scanner check page shows what arrives for each code of a GS1 test sheet the core ships as a PDF: the raw characters with control characters made visible, the identifier, the parsed elements and the resolution. It compares each code with the text the sheet encodes, so it detects a lost GS or identifier, a flipped case, and characters changed by a keyboard layout or an input method editor, and says what to change. It records whether BarcodeDetector on that device passes GS through (R1214).
Source: ADR-0061.R23

### Traceability-code hook

R1219. The core keeps GS1 keys, lots, serials and labels generic and depends on no country's rules. `TraceabilityCodeProvider` is a published package interface (ADR-0016.R17): `traceability_code(item, lot or serial, location, business date) -> {code, label_fields} | None`. When the company's package implements it, label subjects add the optional field `traceability`; when none does, nothing changes. Phase 1 ships no implementation.
Source: ADR-0061.R24

R1220. A country's traceability code or digital product passport is code of that country's localization package (for Vietnam `l10n_vn`) behind this hook, flagged package content with its basis `unverified` (ADR-0016.R6; ADR-0053), never core. Open question (DS-40).
Source: ADR-0061.R24

### Phasing, build placement and lab

R1221. After Phase 1:
   - ZPL templates as a second render target, and a local print agent or socket printing for thermal printers;
   - GS1 location and asset keys: (414) with (254) for bins, GRAI (8003), GIAI (8004), GDTI (253);
   - Digital Link generation (QR on consumer units), with a resolver; compressed Digital Link;
   - an offline scanning queue: idempotent commands queued on the device, validated against claimed-task snapshots and a registry subset, conflicts returned by the server (ADR-0023.R22);
   - SSCC assignment (extension digit, the generation prefix, a serial reference from a counter that never repeats) when a customer requires SSCC labels, earlier if a pilot needs it;
   - decoding of restricted circulation numbers with an embedded weight or price; until then they resolve like any registered GTIN;
   - serial range entry with a right, serial uniqueness per company as a product setting, and component-to-parent serial genealogy.
   Source: ADR-0061.R25

R1222. Build placement (proposed; the runbook and spec 11 are the author's): the registry, the trigger and the commands with master data at step 2; `nativeflows.gs1`, `EvaluateBarcode` and scan-to-confirm in the warehouse core at step 3; desktop capture on receipts and labels with the print worker at step 5; camera, wedge capture, profiles and the check page with the PWA at step 9.
Source: ADR-0061.R26

R1223. Build-time verifications, not design choices: the GS1 Application Identifier table and its lengths are generated from the GS1 Barcode Syntax Dictionary at build (ADR-0061.R1); BarcodeDetector's passing of FNC1 and GS is proved on devices at step 9 (R1214); the Zint licence is checked before the step 5 print worker (ADR-0061.R21). `barcode.sscc_reuse_months` stays flagged (ADR-0061.R7).
Source: ADR-0061.R26.N1

R1224. ADR-0061's invariants are the block `INV-620` to `INV-639`, area `master_data` (`INV-600` to `INV-619` belong to ADR-0056): `INV-620` (registry complete), `INV-621` (GS1 keys valid, padded codes unique, item barcode units), `INV-622` (internal and legacy formats, label codes), `INV-623` (barcoded document formats) and `INV-624` (prefixes disjoint). `INV-620` covers the barcodes of `item_barcode`, `bin`, `handling_unit`, `lot` and `serial_number` and the numbers of numbered `is_barcoded` documents; every other registry row is `internal`. Its edge cases are `EC-119` to `EC-129`, the last free codes of the block of ADR-0054: `EC-119` (a supplier carton label creates the lot with its expiry), `EC-120` (a wedge without GS substitution sends (10) before (17) and the scan stops with `separator_suspect`), `EC-129` (the person confirms the value as read and the receipt succeeds), `EC-121` (`barcode_taken` for a bin with an item barcode's code), `EC-122` (variable measures in kilograms and grams), `EC-123` (serials confirmed by their handling unit, a serial scanned twice refused), `EC-124` (`lot_needs_item`), `EC-125` (`barcode_retired` for an old bin label), `EC-126` (internal codes without a GS1 prefix, `gs1_prefix_required`), `EC-127` (a Digital Link received, nothing fetched) and `EC-128` (legacy codes migrated, `legacy_code_gtin_like`).
Source: ADR-0061.R27

R1225. ADR-0061 amends accepted rules by notes: ADR-0002 (the WebAssembly decoders in the frontend table, Zint in the backend table); ADR-0008 rule 3 (scan objects in payloads, resolved by the server); ADR-0009 rule 15 (`is_barcoded` types, reserved prefixes, the whole-number check); ADR-0016 rule 17 (`TraceabilityCodeProvider`); ADR-0018 rule 14 (normalized barcodes, the registry, the commands); ADR-0020 rule 17 (lot and serial codes kept as they come, their optional barcodes, the label rule); ADR-0023 rules 2, 6, 15 and 22 (bin and handling-unit barcodes in the registry, scan-to-confirm, serial capture, label subjects); ADR-0040 rules 16 and 20 (wedge scans in code fields; DS-31 builds on R1214 to R1218); ADR-0044 rule 3 (legacy codes load with `is_legacy_barcode`); ADR-0045 rule 13 (barcode checks of master data commands); ADR-0049 rules 24 and 25 (the `barcode` filter, the label subjects); ADR-0051 rule 15 (barcodes in intake resolve through `EvaluateBarcode`); ADR-0054 rules 24 and 25 (`EvaluateBarcode` in `general_access`, `RunRetiredSsccCleanup` registered `is_internal_only`, `EC-119` to `EC-129`); ADR-0056 rule 13 (a GS1 measure AI wins over the barcode's unit, never rounded).
Source: ADR-0061.R28

R1226. Catalog rows of ADR-0061:
   - errors: `barcode_taken` (conflict); `barcode_format_invalid`, `barcode_not_normalized`, `barcode_prefix_reserved`, `numbering_barcode_invalid`, `gs1_prefix_invalid`, `scan_mismatch`, `scan_unresolved`, `gs1_capture_conflict`, `serial_already_scanned` (validation); `gs1_prefix_required`, `gs1_prefix_in_use`, `barcode_reuse_period_running` (precondition); existing codes used: `too_many_decimal_places`, `uom_not_allowed`, `permission_denied`;
   - check results: `barcode_unknown`, `barcode_ambiguous`, `barcode_retired`, `lot_needs_item`, `serial_needs_item`, `gs1_invalid`, `scan_malformed`, `gs1_element_ignored`, `scan_heuristic_used`, `legacy_code_gtin_like`;
   - company settings: `barcode.gs_substitute` (`~`), `barcode.prefix.handling_unit` (`HU-`), `barcode.prefix.lot` (`L-`), `barcode.prefix.serial` (`SN-`), `barcode.prefix.item_unit` (`I-`), `barcode.sscc_reuse_months` (12, unverified);
   - `general_access` in `authorization-areas.csv` lists `EvaluateBarcode`;
   - invariants `INV-620` to `INV-624` and edge cases `EC-119` to `EC-129` (R1224); no work item kinds.
   Source: ADR-0061.R29

R1227. Lab check `t19_barcode.py`, pure part: GTIN-8, 12, 13 and 14 and SSCC check digits, valid and invalid; element strings with and without FNC1 and GS, predefined against variable length, the substitute, parentheses and control characters; date AIs with the century window and day 00; 310n decimals and units; required and forbidden pairs, repeated AIs, the separator trace and its exceptions; Digital Link parsing from the rightmost key; the internal code format and normalization; legacy codes (unique on padded digits, read before the guarded rules and as an EAN-13 and UPC-A fallback, `legacy_code_gtin_like`); retirement and return to the owner; the SSCC reuse period and the daily cleanup of supplier SSCCs; the resolution order and every typed issue, numeric lots without an identifier, and (01)(10)(21) as one serial; scan-to-confirm; serial capture; measures accepted with zero extra decimals and refused otherwise; the label rule for lot codes; GTIN-14 generation; the whole-number check of barcoded document formats.
Source: ADR-0061.R30

R1228. Lab check `t19_barcode.py` with `--load`, on all DDL from `load_all.py`: the registry, its indexes and triggers; the database refusing a code across types (a bin code equal to an item code), a wrong check digit, a value not normalized, an SSCC on a bin, a numeric code not marked legacy, a legacy code equal to a GTIN padded to 14 digits, the same collision from two connections at once, a change of `is_legacy_barcode` or `is_barcoded`, a second generation prefix, an overlapping prefix, and an empty lot or serial code; lot codes kept as they come; a removed barcode reserved, released, and revived for its own item or bin; an item barcode moved to another item; barcoded document numbers; a receipt scan creating the lot with its expiry and receiving one carton as 24 pieces with the ADR-0056 snapshot, and variable measures in kilograms and grams; `INV-620`.
Source: ADR-0061.R30

### Product engineering master data

R1229. D4 `propose_items` drafts one change proposal for every new item of a `product_engineering` run (`product_engineering.items`). Items are `CreateProduct` with its single item (ADR-0018.R2), or `CreateItem` for a variant of an existing product; each has a stable `change_proposal_item.id`, which drafts refer to (ADR-0062.R14). The category drives the defaults (ADR-0018.R3; `product_category` defaults) and the required attributes (`product_category_requirement`, ADR-0062.R11); a missing required attribute is listed in the proposal's evidence and checked again at release. The inventory unit is the category's default, else the unit the line states. The product's name is generated by code from the category's name and the attribute values in the category's attribute order, in the company's language; the person may edit it before submitting. Each item carries the candidates of D3 and L2 that the workflow rejected, with the reason (`no_match` from L2, a failed blocking attribute, a different unit kind, an attribute token that differs), and the server's own duplicate check on normalized name and attributes in its plan (check result `item_duplicate_suspected`).
Source: ADR-0062.R9

R1230. Numbering at execution: the proposal payload carries no code, and the model never composes one. Under `master_data.product_code.assignment` `sequence` (the default), the executing command issues the code from the company's `code_series` row for record kind `product` (one row per company, or per category with its short code as prefix; no fiscal year and no branch, unlike document series), moved only by the numbering lock helper (ADR-0008.R10), skipping any code already in use; simulation consumes no number. The defaults of `master_data.product_code.assignment` (`sequence`), `master_data.product_code.prefix_source` (`category_short_code`) and `master_data.product_code.pad_width` (6), per company and category, are this numbering (R1235).
Source: ADR-0062.R9, ADR-0062.R9.N1

R1231. `item_manufacturer_part`: item, `manufacturer_name` and `normalized_manufacturer_name` (case folded, whitespace collapsed), `part_number` and `normalized_part_number` (upper-cased, separators removed, letters and digits of any script), `is_active`; unique per company, normalized manufacturer and normalized part number (`uq_item_manufacturer_part`). `CreateItemManufacturerPart` and `UpdateItemManufacturerPart` are `master_data_change` at `edit` on `product`, proposals for agents.
Source: ADR-0062.R19

R1232. `code_series`: company, `record_kind` (`product`), optional `product_category_id`, `prefix`, `next_value` (at least 1) and `format` (containing `{counter:N}`); the product code sequence of R1230.
Source: ADR-0062.R19

R1233. `product_category_requirement`: category, `requirement` (`variant_attribute`, `dimensions`, `weights`, `barcode`, `supplier_item`, `bill_of_materials`, `routing`, `production_version`, `cost_estimate`, `classification`), `variant_attribute_id` set exactly for `variant_attribute` and `classification_scheme_id` exactly for `classification`, `is_active`, with company keys. Command `SetProductCategoryRequirements` is `master_data_change` at `edit` on `master_data_group`.
Source: ADR-0062.R19

R1234. The production data of the workflow (DS-43-54) is `production`'s: the proposal references on `bill_of_materials` and `bill_of_materials_component`, `routing_operation.is_setup_duration_stated` and `is_run_duration_stated`, `cost_estimate.production_version_id` and `previous_cost_estimate_id`, `cost_estimate_gap`, and the guards `production_release_readiness_guard` and `bill_of_materials_proposal_guard`. The keys from the proposal references to `change_proposal_item` (company, ID) are closed in `DS-36-document-intake.sql`, which loads after both files and adds `UNIQUE (company_id, id)` to `change_proposal_item`.
Source: ADR-0062.R19

R1235. Product codes, company settings with a per-category override:
   - `master_data.product_code.assignment`: `sequence`, `manual` or `sequence_or_manual`; default `sequence`, the `code_series` of R1230, gaps allowed;
   - `master_data.product_code.prefix_source`: `none` or `category_short_code`; default `category_short_code`, used when the category has a short code;
   - `master_data.product_code.pad_width`: default 6, bounds 0 to 12, the `{counter:N}` of the series format.
   Source: ADR-0063.R22

R1236. A product code is unique per company and never reused, also after deletion (`product_code_taken`); it is immutable once any document refers to it (`product_code_immutable`); no rule reads meaning from the prefix; it is issued at proposal execution, so an abandoned proposal burns no code.
Source: ADR-0063.R22

### Tainted projection of items

R1237. The registry attribute `tainted_projection` on a query's result model names the columns a tainted run receives (ADR-0050.R27; ADR-0062.R17; ADR-0029.R14). CI accepts only closed shapes (ID, code, unit, status, category, date, quantity) and `internal` names, never prices, costs, stock, partner columns, `personal` columns or free text.
Source: ADR-0063.R16

R1238. `ListItemCandidate` is the first declared projection, the query ADR-0062.R17 called `ResolveItemCandidates` (ADR-0004 rule 21 allows only `Get`, `List`, `Evaluate` and `Render` as query verbs): ID, code, name, unit, category and status of items, by typed match keys (code, barcode, normalized name), at most 20 rows per call and at most 10 calls per run; rows restricted to another partner are excluded. Beyond the call cap it returns `tainted_projection_cap_reached`.
Source: ADR-0063.R16

R1239. Setting `agents.tainted_reference_reads`, company with an optional per-agent-type value, `literal` or `declared_projections`, default `declared_projections`. An agent type version uses a projection only when it names the query on its tool list.
Source: ADR-0063.R16

R1240. Declared projections join the reference data of the literal scope (ADR-0050.R27, item 4) as the reading of spec 03 rule 1; the reading is decided. ADR-0050.R27 stays as written: declared projections are the only read beyond its items 1 to 3, and the readings (a) to (r) of the cited ADRs stand as readings of that rule. A workflow gets another tainted read only as a declared projection of a registered query, added by an ADR note (ADR-0050.R27.N5). The setting only narrows the reading back to the literal scope, so no setting widens the floor (ADR-0029.R14). The run stays tainted; projected calls are recorded in the step's `context_refs` with the projection version and the row count.
Source: ADR-0063.R16, ADR-0063.R16.N1

### Unit names and codes

R1241. Core unit names are translated by the core catalog; statutory names are supplied by a package per row with a basis (ADR-0056.R2). Regime settings, each with a core default: `documents.unit_name_max_length` (registered by ADR-0056.R18; unset in the core, meaning no limit), `documents.unit_name_source` (`statutory_then_translation`, the default, or `translation`) and `documents.e_invoice_unit_code_scheme` (`unece_rec20_21`, the default, or `none`). A package that uses another scheme supplies a mapping file from core unit codes to its codes; a company unit's scheme code is company data, added to DS-20 when the e-invoice add-on (DS-24) is designed.
Source: ADR-0063.R23

R1242. A statutory output never truncates a unit name silently: `unit_name_too_long` refuses it.
Source: ADR-0063.R23

### Barcode interpretation settings

R1243. Day 00, per date AI, company with a per-category override: `barcode.gs1.day00_policy.<expiry_ai>` for (12), (15), (16), (17), default `last_day` (the GS1 rule), and `barcode.gs1.day00_policy.<production_ai>` for (11), (13), default `first_day`; values `last_day`, `first_day`, `reject`. An earlier date is the more conservative reading, so `first_day` is tighter than `last_day` and `reject` tightest; a category of regulated goods may set `reject`.
Source: ADR-0063.R26

R1244. Best before: `barcode.gs1.best_before_fills_expiry`, per category, default false. While false, (15) is stored as the lot's `best_before_date` and does not fill `expiry_date` when (17) is absent; while true, (15) fills the expiry date when (17) is absent.
Source: ADR-0063.R26

R1245. Unknown AIs: `barcode.unknown_ai_policy`, company, `report_and_ignore` (default, `gs1_element_ignored`) or `reject`. Lost separator: `barcode.separator_suspect`, per scanner profile, `stop_and_confirm` (default) or `trust_transport`, the latter only for a profile proven by a test scan to send GS.
Source: ADR-0063.R26

R1246. Hard, never settings: check digits, the generated AI table, predefined lengths, the century window from the business date and the character sets. Digital Link URIs are never fetched; a retired code is never reassigned to another owner; each parse result stamps the policy values it used and `day_precision`.
Source: ADR-0063.R26

### Record defaults

R1247. Record defaults are not settings, and no master-data flag becomes a setting. Warehouses: `is_bin_managed` false (ADR-0031.R7, ADR-0031.R9, with `default_bin_id`) and `outbound_flow` `direct` (ADR-0023.R1) are the column defaults; a preset lists them so that the drift view and the setup flow show them. Bills of materials: the setup flow, and phase 2 of a migration (ADR-0044.R3), fill `consumption_method` `backflush_at_receipt` on new components where the source states none (ADR-0033; ADR-0034.R12), so the workshop records only production orders and output receipts.
Source: ADR-0067.R18

R1248. A record default fills a field only when the setup flow creates a record and the person leaves the field unchanged. After setup, forms and imports use the column defaults; a person sets the flag per record. `company.valuation_area_level` is set by `CreateCompany` and fixed after setup, so a preset applied later could never fill it: `CreateCompany` takes an optional preset code, and that preset's record defaults fill the fields the command leaves unset (R1258).
Source: ADR-0067.R18

### Sites

R1249. `site` is company data of `master_data`, effect class `master_data_change`, change-tracked; agents propose changes (ADR-0029.R2). Fields: `code` (unique per company), `name`, `kind`, nullable `branch_id`, `address` (the columns of `partner_address` as keys, like `branch`), nullable `working_calendar_id`, nullable `business_unit_id` (ADR-0069), `is_active` and `recorded_at`; the DDL also holds `is_tax_zone` (ADR-0080.R3).
Source: ADR-0068.R1

R1250. Site `kind` is `factory`, `distribution`, `store` or `office`: a label only, which no rule reads; the UI names the level after it ("Factory", "Store"). The identifier is `site`, not `plant`, because a site may also be a distribution centre, a store or an office. `working_calendar_id` is a record default: a new warehouse or work center of the site takes it when created without a calendar, and nothing reads it at run time. Deactivation is refused while an active warehouse names the site (`site_in_use`).
Source: ADR-0068.R1

R1251. Physical warehouses carry `site_id`, required (`ck_warehouse_site`). `transit` and `goods_sent` warehouses carry none: their site is the site of their `valuation_warehouse_id`. Every reader derives it through one function, `master_data.contract.site_of_warehouse`. `CreateWarehouse` without `site_id` takes the company's only active site; with several active sites it is refused with `site_required`.
Source: ADR-0068.R2

R1252. When a site has a `branch_id`, each of its physical warehouses has the same `branch_id`; `CreateWarehouse`, `UpdateWarehouse` and `UpdateSite` refuse a difference with `site_branch_mismatch`. A site without a branch leaves its warehouses' branches free. A warehouse's `site_id` changes only while the warehouse has no material document line (`warehouse_site_fixed`), because at level `site` the site is the valuation area; moving a stocked warehouse to another site is a new warehouse and a transfer.
Source: ADR-0068.R2

R1253. `CreateCompany` creates one site in the same transaction: code `MAIN`, the company's name, and a `kind` chosen in the setup flow (`distribution` when none is given). The migration that adds the table creates one such site per existing company and sets it on every physical warehouse. While a company has one active site, forms, lists and prints leave the site out, and commands default it (R1251); a second active site shows it everywhere. This follows from the data and needs no setting or preset item (ADR-0067).
Source: ADR-0068.R3

R1254. Branch and site stay independent. A branch is the legal, tax and numbering unit (ADR-0009.R15; ADR-0041.R11); a site is the physical and operational unit. They are linked only by the optional `site.branch_id`: a branch may span several sites, and a site lies in at most one branch.
Source: ADR-0068.R4

R1255. `journal_line` gets no `site_id`. Reports roll up warehouse to site through `warehouse.site_id` and `master_data.contract.site_of_warehouse`; `journal_line.warehouse_id` is nullable, so lines without a warehouse fall under the empty site member. The analysis catalog gains the dimension `site`, the parent of `warehouse` (ADR-0060).
Source: ADR-0068.R5

R1256. Recommended modelling, given by the setup agent and the guidance and enforced by nothing: one physical warehouse per site, with zones and bins (ADR-0023.R2) for raw materials, the production floor, finished goods and quality; several warehouses only when they need separate keepers, separate stock reports or separate accounts (the `warehouse` determinant, ADR-0015.R8).
Source: ADR-0068.R6

R1257. `company.valuation_area_level` takes `company`, `site` or `warehouse` (`ck_company_valuation_area_level`). With `site`, all physical warehouses of a site, together with the transit and goods-sent warehouses attached to them, form one valuation area. The level is set at setup, and ADR-0020.R16 holds unchanged. Recording and costing of the area are `inventory`'s (ADR-0068.R8, ADR-0068.R9).
Source: ADR-0068.R7

R1258. `CreateCompany` takes an optional preset code; the preset's record default fills `valuation_area_level` when the command leaves it unset, and the setup flow fills it from the preset's record default (ADR-0067.R18): `site` in `standard` and `company` in `quickflows`. `site` is the standard value because it equals level `warehouse` when each site has one physical warehouse, avoids a separate average and a valuation event per internal move when a site has several, and keeps two factories apart.
Source: ADR-0068.R7

R1259. CRM-only deployment profile: the `master_data` tables `site`, `payment_method`, `incoterm` and `delivery_method` reference no table of `ledger`, `cash`, `inventory`, `tax` or `production`. A site sits between the company and its warehouses; every physical warehouse belongs to one site, and the site of a production warehouse is the plant.
Source: ADR-0068.D0

### Payment methods

R1260. `payment_method` is company data of `master_data`, effect class `master_data_change`, change-tracked: `code` (unique per company), `name`, `kind`, `is_active` and `recorded_at`. Kinds: `cash`, `bank_transfer`, `card`, `e_wallet`, `cheque`, `direct_debit`, `cash_on_delivery`, `offset` or `other`. No posting rule, account determination or tax rule reads a payment method.
Source: ADR-0068.R15

R1261. `customer_profile.payment_method_id` and `supplier_profile.payment_method_id` hold the defaults. `quotation`, `sales_order`, `sales_invoice`, `purchase_order` and `purchase_invoice` carry `payment_method_id`: copied from the profile at creation and then from the source document (ADR-0047.R2), changeable while the document is a draft or by a change order, and printed. `payment.payment_method_id` records the method used; a payment drafted from an invoice copies the invoice's method. Its default money account lives in a `cash`-owned table, so `master_data`, `sales`, `purchasing` and `crm` never depend on `cash`.
Source: ADR-0068.R15, ADR-0068.D0

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source names a rule of this chunk first; `INV-620` to `INV-623` stand in the chunk of ADR-0061.R7 to ADR-0061.R9.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-624` | `gs1_prefixes_disjoint` | day | No two GS1 company prefixes of a company overlap (none starts another); at most one is the generation prefix, and it is active; no registry GTIN or SSCC under one of the company's prefixes outlives that prefix's row. | R1208, R1209, R1210 |
| `INV-810` | `valuation_area_matches_level` | day | Every `material_document_line` and `preliminary_price` row has `valuation_site_id` and `valuation_warehouse_id` both null at level `company`; at level `site` only `valuation_site_id`, equal to the site of the line's warehouse (for `transit` and `goods_sent`, the site of its valuation warehouse); at level `warehouse` only `valuation_warehouse_id`, equal to the line's physical warehouse or the physical warehouse it is attached to. Area `inventory`. | R1257, ADR-0068.R8 |
| `INV-812` | `site_branch_consistent` | day | Every physical warehouse has a site of its company and no `transit` or `goods_sent` warehouse has one; a physical warehouse whose site has a branch carries that branch. | R1251, R1252 |
| `INV-714` | `product_codes_stable` | day | Product codes are unique per company, never reused after deletion, and unchanged once any document refers to them. | R1235, R1236 |
| `INV-717` | `barcode_policy_stamped` | day | Every parse result records the day 00, unknown-AI and separator values it used, and no lot's expiry date was filled from (15) while `barcode.gs1.best_before_fills_expiry` read false for its category. | R1244, R1246 |

## Edge cases

Rows of `edge-cases.csv` whose source names a rule of this chunk first.

| ID | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-119` | `gs1_receipt_lot_expiry`: A supplier carton label in GS1-128 with (01), (17) and (10) is scanned at receipt: the carton GTIN gives item and unit, the lot is created with its expiry date, and one carton is received in the inventory unit. | `must_succeed` | R1224; ADR-0061.R13, ADR-0061.R17 |
| `EC-124` | `bare_lot_code_two_items`: A lot code that two items share is scanned on a search screen; the query returns `lot_needs_item` and no candidate. | `must_succeed` | R1224; ADR-0061.R13 |
| `EC-188` | `tainted_projection_read`: A tainted purchase invoice run lists item candidates through the projection (at most 20 rows, no prices); its eleventh call returns `tainted_projection_cap_reached`; with `agents.tainted_reference_reads` `literal` the call returns `tainted_read_out_of_scope`. | `must_reject:tainted_projection_cap_reached`, `must_succeed` | R1238, R1239 |
| `EC-191` | `day00_reject_category`: A category set to `reject` refuses a (17) with day 00 as `gs1_invalid` (`date`), while another category reads it as the month's last day. | `must_reject:gs1_invalid`, `must_succeed` | R1243 |
| `EC-193` | `product_code_manual_category`: A category with manual codes refuses a duplicate code with `product_code_taken`, and once a sales order refers to its item a code change returns `product_code_immutable`. | `must_reject:product_code_taken`, `must_succeed` | R1235, R1236 |
| `EC-260` | `site_internal_transfer_neutral`: At valuation level `site`, a transfer from a site's raw-materials warehouse to its production warehouse leaves the site's area value unchanged after period-end costing, while a transfer to a second site moves at the issuing site's average. | `must_succeed` | R1257; ADR-0068.R8, ADR-0068.R9 |
| `EC-261` | `second_site_requires_choice`: A one-site company creates a warehouse without naming a site and receives goods into it; after a second site is created, a warehouse created without a site is refused, and moving the stocked warehouse to the second site is refused. | `must_succeed`, `must_reject:site_required`, `must_reject:warehouse_site_fixed` | R1251, R1252 |
| `EC-263` | `payment_method_default_money_account`: A USD sales invoice with a `bank_transfer` method drafts a bank receipt on the USD money account set for the invoice's branch; an invoice with a `cash` method drafts a cash receipt on the cash money account without a branch row. | `must_succeed` | R1261 |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `master_data.product_code.assignment` | enum `sequence`, `manual`, `sequence_or_manual` | `company`, `product_category` | `sequence` | R1230, R1235 |
| `master_data.product_code.prefix_source` | enum `none`, `category_short_code` | `company`, `product_category` | `category_short_code` | R1230, R1235 |
| `master_data.product_code.pad_width` | integer, 0..12 | `company`, `product_category` | 6 | R1230, R1235 |
| `barcode.gs1.day00_policy.<expiry_ai>` | enum `last_day`, `first_day`, `reject` | `company`, `product_category` | `last_day` | R1046, R1243 |
| `barcode.gs1.day00_policy.<production_ai>` | enum `last_day`, `first_day`, `reject` | `company`, `product_category` | `first_day` | R1046, R1243 |
| `barcode.gs1.best_before_fills_expiry` | boolean | `company`, `product_category` | false | R1244 |
| `barcode.unknown_ai_policy` | enum `report_and_ignore`, `reject` | `company` | `report_and_ignore` | R1047, R1245 |
| `barcode.separator_suspect` | enum `stop_and_confirm`, `trust_transport` | `company`, `scanner_profile` | `stop_and_confirm` | R1034, R1245 |
| `documents.unit_name_max_length` | integer, 1..255 (area `documents`) | `regime` | unset | R852, R1002, R1241 |
| `documents.unit_name_source` | enum `statutory_then_translation`, `translation` (area `documents`) | `regime` | `statutory_then_translation` | R645, R851, R1241 |
| `documents.e_invoice_unit_code_scheme` | enum `unece_rec20_21`, `none` (area `documents`) | `regime` | `unece_rec20_21` | R645, R1241 |
| `agents.tainted_reference_reads` | enum `literal`, `declared_projections` (area `agents`) | `company`, `agent_type` | `declared_projections` | R1239, R1240 |

Named by rules but absent from `settings.csv`: `barcode.gs_substitute` (company, default `~`; R1029, R1211, R1226), `barcode.prefix.handling_unit` (`HU-`), `barcode.prefix.lot` (`L-`), `barcode.prefix.serial` (`SN-`), `barcode.prefix.item_unit` (`I-`) (R1081, R1211, R1226), and `barcode.sscc_reuse_months` (12, unverified, flagged; R1078, R1223, R1226).

## Conflicts

CONFLICT ADR-0061.R22: the open question on whether BarcodeDetector passes FNC1 and GS through is a build-time verification proved on devices at step 9, not a design choice (ADR-0061.R26.N1, stated in R1214).
CONFLICT ADR-0062.R9: the interim, flagged product code numbering is decided as the default of the product code settings (ADR-0062.R9.N1 and ADR-0063.R22, stated in R1230 and R1235).
CONFLICT ADR-0063.R16: the tainted projection reading, left open for confirmation, is decided; declared projections are the only read beyond items 1 to 3 of ADR-0050 rule 27 (ADR-0063.R16.N1, ADR-0050.R27.N5, stated in R1240).
CONFLICT ADR-0068.R1: the site field list gains the column `is_tax_zone` that the DDL holds, added by the later tax treatment rule ADR-0080.R3 (stated in R1249).

## Trace

| Source | Where |
| --- | --- |
| ADR-0061.R10 | R1201, R1202, R1203, R1204, R1205, R1206, R1207 |
| ADR-0061.R11 | R1208, R1209, R1210, R1211 |
| ADR-0061.R13 | ref: ADR-0061.R13 |
| ADR-0061.R14 | ref: ADR-0061.R14 |
| ADR-0061.R17 | ref: ADR-0061.R17 |
| ADR-0061.R17.N1 | ref: ADR-0061.R17.N1 |
| ADR-0061.R17.N2 | ref: ADR-0061.R17.N2 |
| ADR-0061.R20 | R1212, R1213 |
| ADR-0061.R21 | ref: ADR-0061.R21 |
| ADR-0061.R22 | R1214, R1215, R1216 |
| ADR-0061.R23 | R1217, R1218 |
| ADR-0061.R24 | R1219, R1220 |
| ADR-0061.R25 | R1221 |
| ADR-0061.R26 | R1222 |
| ADR-0061.R26.N1 | R1214, R1223 |
| ADR-0061.R27 | R1224 |
| ADR-0061.R28 | R1225 |
| ADR-0061.R29 | R1226 |
| ADR-0061.R30 | R1227, R1228 |
| ADR-0062.R5 | ref: ADR-0062.R5 |
| ADR-0062.R6 | ref: ADR-0062.R6 |
| ADR-0062.R7 | ref: ADR-0062.R7 |
| ADR-0062.R9 | R1229, R1230 |
| ADR-0062.R9.N1 | R1230 |
| ADR-0062.R11 | ref: ADR-0062.R11 |
| ADR-0062.R19 | R1231, R1232, R1233, R1234 |
| ADR-0062.R22 | ref: ADR-0062.R22 |
| ADR-0063.R3.N2 | ref: ADR-0063.R3.N2 |
| ADR-0063.R16 | R1237, R1238, R1239, R1240 |
| ADR-0063.R16.N1 | R1240 |
| ADR-0063.R17 | ref: ADR-0063.R17 |
| ADR-0063.R22 | R1235, R1236 |
| ADR-0063.R23 | R1241, R1242 |
| ADR-0063.R26 | R1243, R1244, R1245, R1246 |
| ADR-0063.R28 | ref: ADR-0063.R28 |
| ADR-0063.E.N1 | ref: ADR-0063.E.N1 |
| ADR-0064.R27 | ref: ADR-0064.R27 |
| ADR-0065.R19 | ref: ADR-0065.R19 |
| ADR-0067.R2 | ref: ADR-0067.R2 |
| ADR-0067.R3 | ref: ADR-0067.R3 |
| ADR-0067.R4 | ref: ADR-0067.R4 |
| ADR-0067.R6 | ref: ADR-0067.R6 |
| ADR-0067.R7 | ref: ADR-0067.R7 |
| ADR-0067.R9 | ref: ADR-0067.R9 |
| ADR-0067.R18 | R1247, R1248 |
| ADR-0067.R20 | ref: ADR-0067.R20 |
| ADR-0068.D0 | R1259, R1261 |
| ADR-0068.R1 | R1249, R1250 |
| ADR-0068.R2 | R1251, R1252 |
| ADR-0068.R3 | R1253 |
| ADR-0068.R4 | R1254 |
| ADR-0068.R5 | R1255 |
| ADR-0068.R6 | R1256 |
| ADR-0068.R7 | R1257, R1258 |
| ADR-0068.R8 | ref: ADR-0068.R8 |
| ADR-0068.R9 | ref: ADR-0068.R9 |
| ADR-0068.R15 | R1260, R1261 |
