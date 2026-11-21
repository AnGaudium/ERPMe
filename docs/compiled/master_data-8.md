Module: master_data    Chunk: 8 of 8    Source ADRs: ADR-0068, ADR-0069, ADR-0070, ADR-0074, ADR-0080
Build step(s): 0, 1, 2, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `master_data`, chunk 8

## Purpose

`master_data` owns the company's partners, products, items, organization and the reference catalogs every module reads
(ADR-0022.R2); it sits in layer 3, beside `ledger`, and imports neither `ledger` nor any layer-4 module. This chunk states
Incoterms and delivery methods, the commands, errors and catalogs of the logistics master data of ADR-0068, the business
unit dimension, the inspection points on the product, partner relationships, external IDs, custom fields, reasons, the
partner tax status and tax treatment tables, and the absence of `updated_by` columns. As owner of the rest it also carries
the invariants no other chunk's rules name, and sections 8 to 10. Document parties, the business unit derivation trace and
settings, analysis, and personal data catalogs are law of `sales`, `purchasing`, `ledger`, `query` and `audit`; their units
are traced `ref:`.

## Entities and tables

DDL: `docs/design/DS-20-master-data.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `incoterm` | Installation reference catalog of Incoterms, loaded from `incoterms.csv`; no `company_id`, no row-level security (R1401, R1402) | `code` (natural) | none | `master_data` |
| `delivery_method` | Company's delivery methods, with carrier and tracking link template (R1404) | `id`; unique `(company_id, code)` | `company` | `master_data` |
| `business_unit` | A line of business: an analysis dimension, not an entity; a tree per company (R1412-R1415) | `id`; unique `(company_id, code)` | `company`; `parent_id` | `master_data` |
| `partner_relationship` | Default ship-to, bill-to, payer, invoicing party and payee of a partner (R1434) | `id`; unique `(company_id, partner_id, related_partner_id, role)` | `partner` | `master_data` |
| `external_id_map` | Key of a record in another system, per source system and table (R1437) | `(company_id, source_system, table_name, external_key)` | `company` | `master_data` |
| `custom_field_definition` | Company-defined extra field of one target table (R1445) | `id`; unique `(company_id, target_table, code)` | `company` | `master_data` |
| `reason` | Cancel, reject, return, scrap, count-difference, block, other-receipt and other-issue reasons (R1452) | `id`; unique `(company_id, kind, code)` and `(company_id, id, kind)` | `company` | `master_data` |
| `storage_condition` | Company catalog of storage conditions an item may require (ADR-0023.R3); `code`, `name`, `is_active`; no rule of the module states more | `id`; unique `(company_id, code)` | `company` | `master_data` |
| `tax_treatment` | What a transaction is for tax, with its `directions` (`sale`, `purchase`); the matrix axis (R1461) | `id`; unique `(company_id, code)` | `company` | `master_data` |

Columns this chunk adds to tables whose rows stand in other chunks: `business_unit_id` on `product`, `cost_center`,
`project` and `site` (R1420); `inspection_points` on `product` (R1431); `custom_values` on `partner`, `product` and `item`
(R1448); `delivery_method_id`, `incoterm_code` and `incoterm_place` on `customer_profile` and `supplier_profile` (R1403,
R1405); `partner_tax_status_id` on `partner` (R1461; the `partner_tax_status` row stands in chunk 1); `UNIQUE (company_id, partner_id, id)` on `partner_address` and
`UNIQUE (company_id, id)` on `project` (R1460).

Reads: `payment_method_money_account` (owned by `cash`), `resource_group` (`production`), `journal_line`, `journal_entry`,
`derivation_trace` (`ledger`), `document`, the commercial and stock document headers and lines, `approval`,
`inspection_lot_line`, `audit_change`, `audit_record`, `document_version`, `tax_treatment_rule` (`tax`).

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateSite` | Leaf `site` (under `organization`); `master_data_change`; agents through change proposals | Site fields (ADR-0068.R1) | Writes `site` (R1408); `UpdateSite` has its row in chunk 7 | None stated | Not stated in this chunk (R1409 lists the site errors) |
| `CreatePaymentMethod`, `UpdatePaymentMethod` | Leaf `payment_method`; `master_data_change`; agents through change proposals | Payment method fields (ADR-0068.R15) | Writes `payment_method` (R1408) | None stated | None stated |
| `CreateDeliveryMethod`, `UpdateDeliveryMethod` | Leaf `delivery_method`; `master_data_change`; agents through change proposals | Delivery method fields | Writes `delivery_method` (R1404, R1408) | None stated | `partner_role_missing` |
| `ListSite`, `ListPaymentMethod`, `ListDeliveryMethod`, `ListIncoterm` | The leaves above; verb `List` at `read` | Filters | Queries (R1408) | None | None stated |
| `CreateBusinessUnit`, `UpdateBusinessUnit` | Leaf `organization`; `master_data_change`, `is_proposal_bound`; verbs at `edit` | Unit fields | Writes `business_unit` (R1412-R1419) | None stated | `business_unit_invalid`, `business_unit_in_use` |
| `ListBusinessUnit`, `GetBusinessUnit` | Leaf `organization`; level not stated for `Get` | Filters or ID | Queries (R1419) | None | None stated |
| `CreatePartnerRelationship`, `UpdatePartnerRelationship` | Leaf `partner`; `master_data_change`, change-tracked | Relationship fields | Writes `partner_relationship` (R1434, R1459) | None stated | None stated |
| `CreateReason`, `UpdateReason` | Leaf `reason`; `master_data_change`, change-tracked | Kind, code, name | Writes `reason` (R1452, R1459) | None stated | None stated |
| `CreateCustomFieldDefinition`, `UpdateCustomFieldDefinition` | Leaf `custom_field`; `master_data_change`, change-tracked | Definition fields | Writes `custom_field_definition` (R1445-R1447) | None stated | `custom_field_limit`, `custom_field_in_use` |
| `SetExternalId` | Leaf `data_import`; human or `integration` actor; level not stated | Company, source system, table, key, entity | Writes an `external_id_map` row; idempotent for an identical mapping (R1441) | None stated | `external_id_taken`, `external_id_conflict`, `external_id_table_invalid`, `external_id_source_reserved` |
| `ClearExternalId` | Leaf `data_import`; human or `integration` actor; level not stated | The mapping | Deletes an `external_id_map` row (R1441) | None stated | `external_id_table_invalid` |
| `ListPartnerRelationships`, `ListReasons`, `ListCustomFieldDefinitions`, `ListExternalIds`, `ResolveExternalId` | Leaves of the commands above; verb `List` at `read`; level not stated for `Resolve` | Filters; `ListCustomFieldDefinitions(target_table)` | Queries (R1440, R1450, R1459) | None | None stated |

Commands of ADR-0068.R23 owned by other modules: `SetPaymentMethodMoneyAccount`, `DeletePaymentMethodMoneyAccount`
(`cash`), `CreateResourceGroup`, `UpdateResourceGroup`, `ListResourceGroup` (`production`), `ListExpectedLandedCost`
(`inventory`).

Not commands: the functions `external_id_resolve` and `external_key_of` (R1440); the hook `business_unit_defaults`, which
`master_data` registers for `ledger` (R1426); the contract `master_data.contract` exposing `product.inspection_points`
(R1432).

Codes raised by the rules of this chunk outside the table: `custom_field_unknown`, `custom_field_invalid` and
`custom_field_required` by `Create` and `Update` of a target table (R1449); `reason_invalid` and `reason_required` by any
command that names a reason (R1453, R1457); `warehouse_site_fixed`, `resource_group_site_mismatch`,
`resource_group_activity_mismatch` and `payment_method_money_account_mismatch` (R1409); `business_unit_missing`
(precondition) and the check result `business_unit_default_unset` (R1430).

## Rules

### Incoterms and delivery methods

R1401. `incoterm` is an installation reference catalog owned by `master_data`, loaded from `incoterms.csv`. It has no `company_id` and no row-level security, like `currency` (ADR-0045.R1, ADR-0045.R14). Its key is the natural `code`, like `currency`'s, an exception to ADR-0006.R1 that a note there records; the three-letter codes are a stable published list, also UN/ECE Recommendation 5. Documents therefore carry `incoterm_code`, as they carry `currency`.
Source: ADR-0068.R18

R1402. The columns of `incoterm` are `code`, `version` (2020), `name`, `transport_scope` (`any` or `sea_inland_waterway`), `is_carriage_paid_by_seller`, `is_insurance_paid_by_seller`, `is_import_cleared_by_seller`, `risk_transfer_point` (text), `is_active` and `recorded_at`; the booleans take the `is_` form of ADR-0004.R13. The rows are EXW, FCA, CPT, CIP, DAP, DPU, DDP, FAS, FOB, CFR and CIF. A later edition retires rows by `is_active`, and old documents keep theirs.
Source: ADR-0068.R18

R1403. `quotation`, `sales_order`, `delivery` and `sales_invoice` on the sales side, and `purchase_order`, `goods_receipt` and `purchase_invoice` on the purchase side, carry `incoterm_code` and `incoterm_place`, the named place; a place requires a code. The profiles carry the defaults, and documents copy them as in ADR-0068.R15 (from the sold-to partner's `customer_profile` or the ordered-from partner's `supplier_profile`, ADR-0074.R4). Prints show "code place Incoterms version".
Source: ADR-0068.R19

R1404. `delivery_method` (company data, `master_data`, effect class `master_data_change`, change-tracked) has `code`, `name`, `kind` (`own_fleet`, `carrier`, `courier`, `customer_pickup` or `supplier_delivery`), `carrier_partner_id`, `tracking_url_template`, `is_active` and `recorded_at`. `carrier_partner_id` is set exactly for `carrier` and `courier`, and the partner holds the active `supplier` role (ADR-0019.R2), otherwise `partner_role_missing`. `tracking_url_template` is an `https` URL that contains `{tracking_number}`.
Source: ADR-0068.R21

R1405. `customer_profile` and `supplier_profile` carry `delivery_method_id`, and `sales_order` and `purchase_order` copy it. `delivery` and `goods_receipt` carry `delivery_method_id`, `carrier_partner_id`, `tracking_number` and `vehicle_registration`. The carrier is copied from the method and is changeable until posting, with the same role check. Like all content, the fields are fixed at posting (ADR-0009.R14).
Source: ADR-0068.R22, ADR-0068.R22.N1

R1406. The tracking link is computed by putting the URL-encoded number into the template, and is never stored. Freight charged to the customer stays a service-item line. There is no rate shopping and no carrier API in Phase 1; carrier integration is a later item on the `integrations` queue (backlog).
Source: ADR-0068.R22, ADR-0068.R22.N1

R1407. The delivery's address is its ship-to party (`ship_to_partner_id`, `ship_to_name`, `ship_to_address_id`, `ship_to_address`), which defaults from the customer's `partner_relationship` rows (ADR-0074.R1, ADR-0074.R3); the delivery has no `delivery_address` column. The carrier stays the delivery method's.
Source: ADR-0068.R22, ADR-0068.R22.N1

### Commands, errors and catalogs of the logistics master data

R1408. The commands and queries of ADR-0068 are all `master_data_change`, and agents reach them through change proposals. `master_data` owns `CreateSite`, `UpdateSite` (leaf `site`, ADR-0068 rules 1 to 3), `CreatePaymentMethod`, `UpdatePaymentMethod` (leaf `payment_method`, ADR-0068.R15), `CreateDeliveryMethod`, `UpdateDeliveryMethod` (leaf `delivery_method`, R1404) and the queries `ListSite`, `ListPaymentMethod`, `ListDeliveryMethod` and `ListIncoterm`. `cash` owns `SetPaymentMethodMoneyAccount` and `DeletePaymentMethodMoneyAccount` (leaf `payment_method_money_account`, ADR-0068.R16); `production` owns `CreateResourceGroup`, `UpdateResourceGroup` and `ListResourceGroup` (leaf `resource_group`; members are set by `UpdateWorkCenter`, ADR-0068.R12); `inventory` owns `ListExpectedLandedCost` (leaf `warehouse`, ADR-0068.R20).
Source: ADR-0068.R23

R1409. The errors of ADR-0068 (DS-04) are, as validation, `site_required`, `site_branch_mismatch`, `resource_group_site_mismatch`, `resource_group_activity_mismatch` and `payment_method_money_account_mismatch`, and, as precondition, `site_in_use` and `warehouse_site_fixed`. ADR-0068 adds no setting; the preset item of ADR-0068.R7 is a record default.
Source: ADR-0068.R24

R1410. The catalog rows of ADR-0068:
   - Authorization leaves: `site` (under `organization`), `payment_method`, `delivery_method`, `payment_method_money_account` (under `money_account`) and `resource_group` (under `production_structure`). Levels inherit from the parents, so no role-template rows are added.
   - Analysis dimensions: `site`, and `payment_method` on invoice lines.
   - Catalog files: `incoterms.csv`, and two `record_default` rows in `setting-presets.csv`.
   - DDL: `DS-20-master-data.sql` (`site`, `payment_method`, `incoterm`, `delivery_method`, and the warehouse, company and profile columns); `DS-22-09-42-commercial-inventory.sql` (document headers, `material_document_line`, `preliminary_price`); `DS-05-platform.sql` (`payment_method_money_account`, `payment.payment_method_id`); `DS-43-54-planning-production.sql` (`resource_group`, `work_center.resource_group_id`).
   Source: ADR-0068.R25

### Business units

R1411. A business unit splits a company's activity into lines of business. It is an analysis dimension, not a legal or organizational entity: no numbering, currency or books of its own. Every journal line has a nullable `business_unit_id` (ADR-0014.R9). Phase 1 reports profit and loss and gross margin per unit; a balance sheet per unit and the allocation of shared costs come later, on the same column (R1429).
Source: ADR-0069.D0

R1412. `business_unit` (owner `master_data`, company data, `master_data_change`, change-tracked; agents propose changes, ADR-0029.R2) has `id`, `company_id`, `code`, `name`, `parent_id`, `is_active` and `recorded_at` (`DS-20-master-data.sql`).
Source: ADR-0069.R1

R1413. A unit's `code` is unique in the company. It cannot change once a journal line, a master record, a document or the company default names the unit (`business_unit_invalid`), because group reporting matches units across companies by `code`.
Source: ADR-0069.R1

R1414. `parent_id` names a unit of the same company; the command refuses a cycle (`business_unit_invalid`). Any unit may receive postings; a roll-up sums a unit and its descendants.
Source: ADR-0069.R1

R1415. A business unit has no legal role, branch, numbering, currency or ledger. Branches stay the legal and tax unit (ADR-0009) and sites the physical one (ADR-0068).
Source: ADR-0069.R1

R1416. Master data, document headers and lines may name only an active unit of their company, otherwise `business_unit_invalid`. Reversal and closing lines copy the original line's unit even when the unit is no longer active; they are exempt from the active check, as from the requirement of ADR-0069.R14.
Source: ADR-0069.R2

R1417. Deactivation of a unit is refused with `business_unit_in_use` while an active cost center, product, open project, active site or `ledger.business_unit.default` names it, so derivation never meets an inactive default.
Source: ADR-0069.R2

R1418. A draft that names a unit deactivated since is refused at posting with `business_unit_invalid`.
Source: ADR-0069.R2

R1419. The commands and queries of business units are `CreateBusinessUnit` and `UpdateBusinessUnit` (`master_data_change`, `is_proposal_bound`), `ListBusinessUnit` and `GetBusinessUnit`, in module `master_data`, leaf `organization`.
Source: ADR-0069.R3

R1420. Nullable `business_unit_id` defaults, each naming an active unit of the same company, sit on `product` (`product.business_unit_id`), `cost_center` (`cost_center.business_unit_id`), `project` (`project.business_unit_id`, ADR-0045.R9) and `site` (`site.business_unit_id`, the table of ADR-0068). In the derivation, "the item's unit" is its product's unit, read through the item as item group and valuation class are (ADR-0018.R3): variants share a line of business. Item group is not used, because it drives revenue and cost accounts (ADR-0015.R7).
Source: ADR-0069.R7

R1421. Every commercial document header of ADR-0047 carries a nullable `business_unit_id` that a person or an agent sets: quotation, sales order, delivery, return from customer, sales invoice, sales return, credit and debit note, purchase request, purchase order, goods receipt, service receipt, return to supplier, purchase invoice, purchase return, and supplier credit and debit note.
Source: ADR-0069.R8

R1422. `Create<Type>` with `source_lines` copies the source header's unit into an empty header; it can be changed until posting. Sources with different units leave the header empty unless the command states one (ADR-0047.R2).
Source: ADR-0069.R8

R1423. The lines on which a person assigns an account carry an explicit `business_unit_id`: purchase invoice lines, payment `account` lines and general journal lines (ADR-0048.R15). Sales lines have no line unit in Phase 1: the product and the header decide, and a generic service product without a unit lets the header decide. An explicit unit on a document line is an input to the derivation: it is applied to the profit-and-loss lines that the document line produces, and the balance-sheet lines of the same posting carry none.
Source: ADR-0069.R8

R1424. The headers of `stock_count`, `scrap`, `internal_consumption`, `other_receipt` and `other_issue` (ADR-0075) may name a business unit like the other document headers, set by a person or an agent. `stock_transfer` has none, because it posts no profit-and-loss line.
Source: ADR-0069.R8.N1

R1425. `ledger` derives the unit at posting, inside the posting transaction, for every P&L line of the entry. The first match wins, in this order:
   1. the explicit unit of the document line;
   2. the unit of the line's item (its product); for a line whose cost object is a production order (issues, confirmations, receipts, settlement and variance lines) the item is the order's output product, so every P&L line of one order carries one unit and the production cost accounts net to zero per unit;
   3. the unit of the line's cost center;
   4. the unit of the line's project;
   5. the document header's unit;
   6. the unit of the site of the line's warehouse (a transit or goods-sent warehouse through its valuation warehouse, ADR-0068);
   7. `ledger.business_unit.default`, or none.
   Source: ADR-0069.R9

R1426. The posting module passes the explicit line unit and the header unit in its posting request. The other candidates come from master data through the hook `business_unit_defaults`, which `ledger` declares, `master_data` registers and `app` wires, because same-layer modules may not import each other and `ledger` and `master_data` share layer 3 (ADR-0022.R2). The hook is required.
Source: ADR-0069.R9

R1427. The function `ledger.contract.derive_business_unit` is pure. A conflict between candidates, such as an item unit that differs from the cost center's, is not an error: the first match wins and the trace keeps the losing values.
Source: ADR-0069.R9

R1428. In a CRM-only deployment `business_unit` lives in `master_data`, so quotations and sales orders carry a unit without `ledger`. The derivation and its settings `ledger.business_unit.default` and `ledger.business_unit.required_on_profit_and_loss` belong to `ledger` and are absent there.
Source: ADR-0069.R17

R1429. Later seams (backlog), which need no migration of posted lines: a balance sheet per unit (document splitting), where derivation extends to balance-sheet lines with splitting rules and `open_item` may gain the column; and the allocation of shared costs, by allocation documents that post P&L lines with explicit units.
Source: ADR-0069.R18

R1430. The catalog rows of ADR-0069:
   - Settings: `ledger.business_unit.default` and `ledger.business_unit.required_on_profit_and_loss` (owned by `ledger`, ADR-0069.R13).
   - Dimension: `business_unit`, beside ADR-0068's `site` and `payment_method`.
   - Errors (DS-04): `business_unit_missing` and `business_unit_in_use` (precondition), `business_unit_invalid` (validation).
   - Check result: `business_unit_default_unset`.
   - Authorization: the leaf `organization` also covers business units.
   - Invariants `INV-820` to `INV-823` and edge cases `EC-270` to `EC-273`.
   - DDL: `DS-20-master-data.sql` (the table and the master data defaults), `DS-06-universal-journal.sql` (journal columns), `DS-22-09-42-commercial-inventory.sql` (headers and purchase invoice lines), `DS-05-platform.sql` (payment lines), `DS-28-settings.sql` (value type `code`).
   Source: ADR-0069.R19

### Inspection points on the product

R1431. Inspection points are a closed set: `goods_receipt`, `in_process` (after a routing operation), `production_output`, `customer_return` and `stock_recheck`. `product.inspection_points` (`text[]`, default empty, a subset of the set) says per point whether the item is inspected; it replaces the boolean `is_inspection_required` (ADR-0023.R3), with the same meaning per point. The flag stays in `master_data` so that `inventory` and `production` decide the stock status at posting without reading `quality`.
Source: ADR-0070.R2

R1432. `master_data.contract` exposes the set. `inventory` posts `purchase_receipt` and `other_receipt` lines to `quality_inspection` when the set contains `goods_receipt` (ADR-0023.R7); `production` posts output to `quality_inspection` when it contains `production_output` (ADR-0034.R13); returns still arrive `blocked` (ADR-0023.R19); the lot creator of `quality` reads the set for every point.
Source: ADR-0070.R2

R1433. The upgrade sets the array to `{goods_receipt, production_output}` where `is_inspection_required` was true.
Source: ADR-0070.R2

### Partner relationships

R1434. `partner_relationship` (owner `master_data`, company data, change-tracked) holds the default parties of a partner: `partner_id`, `related_partner_id`, `role` (`ship_to`, `bill_to`, `payer`, `invoicing_party`, `payee`), an optional `address_id` of the related partner, `is_default` and `is_active`. It is unique per partner, related partner and role, with at most one default per partner and role.
Source: ADR-0074.R3

R1435. `Create<Type>` takes, for each role, the default relationship of the sold-to or ordered-from partner; a partner without one leaves the party unstated. The defaulting reads only `partner`, `partner_address` and `partner_relationship`, so `crm` and master data stay independent of the ledger, tax, inventory, cash and production.
Source: ADR-0074.R3

R1436. The party consequences of ADR-0074.R4 change accepted rules, each of which carries a note. `INV-49` and the open item identity of ADR-0026.R1 are unchanged: the open item's `partner_id` is the payer (receivables) or the invoicing party (payables), as the posting writes it.
Source: ADR-0074.R6

### External IDs

R1437. `external_id_map` (owner `master_data`) maps `(company_id, source_system, table_name, external_key)`, its primary key, to `entity_id`, and is unique on `(company_id, source_system, table_name, entity_id)`: one key per entity in a source system. `source_system` is a lower-case code (`^[a-z][a-z0-9_.-]{0,39}$`) such as a web shop, an EDI partner or a former system; the key is text of up to 200 characters. Rows are never updated.
Source: ADR-0074.R7

R1438. `external_id_map` is the import key map of ADR-0044.R5 (there named `import_key_map`). The draft batch keeps its provisional key map in the batch (staging), so an agent preparing a batch changes no company data; `RunImport` writes the rows in the transaction that creates the records. A batch names its source system: a field of `CreateImportBatch` and of the workbook header, added when DS-21's DDL is written (no import DDL exists yet).
Source: ADR-0074.R7

R1439. Integrations (actor `integration`) set and clear their own keys through the same commands, so a web shop's customer ID resolves to the partner without a column per system.
Source: ADR-0074.R7

R1440. `external_id_resolve(company, source_system, table, key)` returns the entity ID, and `external_key_of(company, source_system, table, entity)` the key; the queries `ResolveExternalId` and `ListExternalIds` call them. Commands still take IDs only (ADR-0006.R5): an agent resolves a key with the query, then sends the command.
Source: ADR-0074.R7

R1441. `SetExternalId` is idempotent for an identical mapping; it returns `external_id_taken` when the key names another entity and `external_id_conflict` when the entity has another key in that source system. `ClearExternalId` deletes a mapping; the deletion of a draft document deletes its mappings in the same transaction. Both use the leaf `data_import` (ADR-0054.R7). `table_name` must be a company table with an `id` (`external_id_table_invalid`).
Source: ADR-0074.R7

R1442. The target is polymorphic, so `INV-860` checks that it exists and is of the company. The natural keys that enforce a duplicate rule for one document type (`operation_confirmation.external_reference`, `purchase_invoice.external_document_key`, the inbound message and bank line keys) are not ID maps and stay.
Source: ADR-0074.R7

R1443. The source system `group` is reserved for the group key. Phase 1 keeps partners, products and items per company (ADR-0019.R1); where companies of one installation need the same master, a group key per record is stored through `external_id_map` with source system `group`, and a later distribution command copies a master and keeps it in step across those companies. Rows are never shared between companies, so no `(company_id, ...)` key changes later.
Source: ADR-0074.R7.N1, ADR-0074.R7.N2

R1444. Until the distribution command exists, `SetExternalId`, `CreateImportBatch` and an import workbook header that name the source system `group` are refused with `external_id_source_reserved` (validation, DS-04 error catalog; ADR-0044.R5). `external_id_map` carries `ck_external_id_map_source_system_reserved` as the database backstop; the distribution command, when it is designed, drops that check and becomes the only writer of `group` keys.
Source: ADR-0074.R7.N1, ADR-0074.R7.N2

### Custom fields

R1445. `custom_field_definition` (owner `master_data`, company data, `master_data_change`, change-tracked) holds, per company and `target_table`:
   - `code`, the key, matching `^[a-z][a-z0-9_]{0,39}$`, never changed;
   - `label`, in the company language, other languages in `data_translation` (ADR-0018.R17);
   - `data_type`: `text`, `integer`, `decimal`, `boolean`, `date` or `choice`;
   - `validation`, a `jsonb` object: `max_length` and `pattern` for text, `min`, `max` and `scale` for numbers, `choices` for choice;
   - `is_required`, an optional `field_class` (`cost` or `margin`, ADR-0017.R10, or `sensitive_personal`, ADR-0079.R11), `is_personal_data` and `is_active`.
   Source: ADR-0074.R8, ADR-0074.R8.N1

R1446. A field with `is_personal_data` true holds personal data: its values carry the personal label that the LLM gateway strips or routes (spec 17), and the erasure of the record clears them (ADR-0038.R4). `is_personal_data` has no default: the command states it, and `check` fails when a definition has no value. The setup agent proposes true for free-text and contact-like fields on partners. The keys of `custom_values` whose definition has `is_personal_data` true are catalog members by rule: one row of `personal-data-fields.csv` per table with `custom_values` stands for them (ADR-0079.R2).
Source: ADR-0074.R8, ADR-0074.R8.N1

R1447. A company has at most 30 active definitions per table (`custom_field_limit`): a design bound, not a policy.
Source: ADR-0074.R8

R1448. A `custom_values jsonb NOT NULL DEFAULT '{}'` column, with `jsonb_typeof = 'object'`, sits on the master tables `partner`, `product` and `item` and the document headers `quotation`, `sales_order`, `delivery`, `sales_invoice`, `purchase_order`, `goods_receipt`, `purchase_invoice` and `production_order`. Lines, the journal, stock and cash tables get none in Phase 1. `target_table` is held to that list by a CHECK, so adding a table is an ADR note and a column, never data.
Source: ADR-0074.R9

R1449. `Create` and `Update` of a target table validate `custom_values` against the table's definitions in the command layer: an unknown key is `custom_field_unknown`, a wrong value `custom_field_invalid`, a missing value of a required field `custom_field_required` (a field made required later is checked at the next `Update`, never retroactively). A retired field keeps its values, shows them and refuses a change. A decimal is a decimal string, never a float. The data type of a definition cannot change once a record carries a value (`custom_field_in_use`). On a document the column is content: it is written into the version, and posting freezes it.
Source: ADR-0074.R10

R1450. Every generated command and query schema that names a target table has `custom_values` as an object with the annotation `x-nativeflows-custom-values: "<table>"` (ADR-0022.R17; ADR-0040.R4); the generated files stay independent of any company. The renderer and agents read the company's fields through `ListCustomFieldDefinitions(target_table)`, which returns them with their field classes and translated labels (`x-nativeflows-field-class` per key), and a restricted actor loses a classed key like any other classed field.
Source: ADR-0074.R11

R1451. Not in Phase 1: a form builder, custom tables (the "tables" of spec 16 level 1), calculated fields, references to other records, custom fields on lines, indexes on `custom_values`, analysis measures or dimensions over custom values, and copying values from a source document to the next one (a person sets them).
Source: ADR-0074.R12

### Reasons

R1452. `reason` (owner `master_data`, company data, change-tracked) holds `kind` (`cancel`, `reject`, `return`, `scrap`, `count_difference`, `block`, and `other_receipt` and `other_issue` for the documents of ADR-0075.R11 and ADR-0075.R12), `code`, `name` (company language; others in `data_translation`) and `is_active`, unique per company, kind and code, and by `(company_id, id, kind)`. A column that takes one kind stores the kind beside the ID (`<column>_kind`, default and CHECK to that kind) and references `(company_id, id, kind)`, so the database holds the kind (the pattern of `price_list_kind`).
Source: ADR-0074.R13

R1453. The kind `block` has no consumer yet: it is reserved for partner and item blocks. Reasons are company data seeded by a package template if the package has one; the core seeds none. A command that names a reason takes an active one of its company and kind (`reason_invalid`); a missing reason that the company's setting requires is `reason_required` (R1457); deactivating a reason never touches a document that names it.
Source: ADR-0074.R13

R1454. The reason columns:
   - `document.canceled_reason_id` with `canceled_note`, for every type (`Cancel<Type>` takes both, optional); allowed only in state `canceled`.
   - `approval.reason` stays required text (ADR-0055.R9) and `approval` has `reject_reason_id`, allowed only on a rejection.
   - `return_reason_id` on the lines of `return_to_supplier`, `return_from_customer`, `sales_return` and `purchase_return`.
   - `scrap_reason_id`, kind `scrap`, on `production_issue_line`, `operation_confirmation` and `production_receipt`; the kind covers over-issue and component scrap too; `production_order_component` has none.
   - `scrap_line.scrap_reason_id` (required while `documents.reason_required.scrap` is true), `stock_count_line.difference_reason_id`, `other_receipt_line.reason_id` (kind `other_receipt`) and `other_issue_line.reason_id` (kind `other_issue`).
   - `inspection_lot_line.reason_id` (kinds `scrap` and `return`, for the dispositions `scrap` and `return_to_supplier`, which the quality executor copies to the line it drafts; ADR-0070.R15).
   - The existing CHECKs keep their meaning: a scrap reason needs a scrap quantity.
   Source: ADR-0074.R14

R1455. These stay as they are: the fixed system codes that logic reads (`closed_reason`, `credit_note.reason` and `debit_note.reason`, `open_item_collection.payment_block_reason`, `demand_supply_line.hold_reasons`, `planning_exception.reason`); a person's required free text (`work_case.cancel_reason`, `operation_time_log.cancel_reason`, `nonconformance.cancel_reason`, `taint_clearance.reason`, `approval.reason`, `period_unlock_request.reason`); `stop_reason` and `defect_code`, which are catalogs with their own columns; and `warehouse_task.shortage_reason` (a candidate for the `count_difference` kind later, an open question). The closed list of scrap reasons of the ADR-0064 mapping step is the company's active reasons of kind `scrap`.
Source: ADR-0074.R15

R1456. Whether a reason is required is policy: one company setting per kind (ADR-0063), boolean, scope `company`, leaf `reason`, direction `true_tighter`, with these core defaults:
   - `documents.reason_required.count_difference`: true.
   - `documents.reason_required.scrap`: true.
   - `documents.reason_required.return`: true.
   - `documents.reason_required.reject`: true.
   - `documents.reason_required.other_receipt`: true.
   - `documents.reason_required.other_issue`: true.
   - `documents.reason_required.cancel`: false.
   - `documents.reason_required.block`: false.
   Source: ADR-0074.R22

R1457. A missing required reason is `reason_required` (validation), checked by the command on the line or header that takes the reason: a count key with a difference, a scrap line, a production issue, confirmation or receipt with scrap, a return line, an other receipt or other issue line, a rejection, a cancel. The database keeps every reason column nullable, so the setting alone decides; loosening a setting does not touch documents already written. `settings.csv` carries the rows (ADR-0063.R29 note).
Source: ADR-0074.R22

### Change history, commands and DDL of ADR-0074

R1458. No table has `updated_by` or `updated_at`. Who changed what and when is recorded where the change is made: `audit_change` for the change-tracked tables (ADR-0038.R3), `document_version` for documents (ADR-0009.R9) and `audit_record` for every command (ADR-0038.R6); a reader who asks who last changed a record queries the audit rows. The `recorded_at` finding of the architecture overview is a separate matter.
Source: ADR-0074.R19

R1459. The commands of ADR-0074 are all `master_data_change` and change-tracked unless stated: `CreatePartnerRelationship` and `UpdatePartnerRelationship` (leaf `partner`); `CreateReason` and `UpdateReason` (leaf `reason`); `CreateCustomFieldDefinition` and `UpdateCustomFieldDefinition` (leaf `custom_field`); `SetExternalId` and `ClearExternalId` (leaf `data_import`, human or integration actor). The queries are `ListPartnerRelationships`, `ListReasons`, `ListCustomFieldDefinitions`, `ResolveExternalId` and `ListExternalIds`. They are registered in the command registry (ADR-0008) when the code is written; there is no separate catalog of commands. The leaves `reason` and `custom_field` sit under `master_data`, so the owner template has them at full; no other template gets them from ADR-0074.
Source: ADR-0074.R20

R1460. DDL: `partner_relationship`, `external_id_map` with its functions, `custom_field_definition` and `reason` in DS-20, all owned by `master_data`; the columns added by ADR-0074 rules 1 to 3, 9, 14, 16 and 17 (in DS-20, DS-22, DS-43, DS-05 and DS-06). `partner_address` gains `UNIQUE (company_id, partner_id, id)` and `project` gains `UNIQUE (company_id, id)`.
Source: ADR-0074.R21

### Partner tax status and tax treatment

R1461. `partner_tax_status` (on `partner.partner_tax_status_id`) says what a party is and is an input. `tax_treatment`, with the directions it applies to, says what a transaction is and is the matrix axis. Both are package templates copied into the company, as the item tax groups are, and a company may add its own (basis `company_decision`). The core seeds neither list: the derivation works on whatever codes the package and the company define. No `partner_tax_group` exists.
Source: ADR-0080.R1

## Invariants

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-823` | `business_unit_tree` | day | Every business unit's parent belongs to its company and the tree has no cycle; every active cost center, product, open project and active site, and `ledger.business_unit.default`, names an active business unit of the company. | R1414, R1417 |
| `INV-860` | `external_id_target_exists` | day | Every `external_id_map` row names an existing row of its table, of its company. | R1442 |
| `INV-861` | `reason_kind_matches_column` | day | Every reason reference names a reason of the kind its column takes, of the same company, and a canceled-reason or reject-reason column is set only in the state that allows it. | R1452, R1454 |
| `INV-862` | `custom_values_defined` | day | Every key of a `custom_values` object has a definition of its company and table, active or retired, and its value fits the definition's data type and validation. | R1448, R1449 |
| `INV-830` | `inspection_plan_revision_immutable` | day | No released `inspection_plan_revision` or its characteristics changed after `released_at`; at most one draft per plan; each quantitative characteristic has a unit and at least one limit, with lower <= target <= upper where set; each qualitative one has passing codes within its allowed codes. | ADR-0070.R4, ADR-0070.R5 |

Named by rules of this chunk, stated by their own modules or chunks: `INV-820`, `INV-821`, `INV-822` (`ledger`),
`INV-49`, `INV-863`, `INV-864`, `INV-83`, `INV-880`.

## Edge cases

| ID | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-264` | `carrier_on_delivery`: A delivery copies the carrier of its sales order's carrier method, the carrier is changed before posting, and the tracking link is shown; a carrier partner without an active supplier role is refused. | `must_succeed`; `must_reject:partner_role_missing` | R1404, R1405, R1406 |
| `EC-270` | `business_unit_conflict_first_match`: A delivery's cost-of-goods line for a product of unit A, from a site of unit B, on a sales order whose header names C: the line gets A with source `item`, and the entry's trace lists B and C as losing candidates. | `must_succeed` | R1425, R1427 |
| `EC-273` | `business_unit_expense_line`: A purchase invoice expense line with a cost center of unit A gets A with source `cost_center`; a second line with an explicit unit D gets D with source `line`. | `must_succeed` | R1423, R1425 |
| `EC-311` | `party_defaults_from_relationships`: A partner with one default ship-to and no payer relationship gets the ship-to on a new order and no payer; changing the default does not touch an existing order. | `must_succeed` | R1435 |
| `EC-313` | `external_id_reimport`: A web-shop customer imported twice with the same key updates the partner; a second key for the same partner in that source system is refused. | `must_succeed`; `must_reject:external_id_conflict` | R1437, R1441 |
| `EC-314` | `custom_field_required_and_retired`: A required custom field refuses a new order without a value; after it is retired, existing orders keep and show the value and refuse a change. | `must_succeed`; `must_reject:custom_field_required` | R1449 |
| `EC-315` | `custom_field_restricted_actor`: A custom field of class `cost` is absent from the responses, plans and events of an actor without the class. | `must_succeed` | R1450 |
| `EC-316` | `cancel_with_reason`: A quotation canceled with a reason of kind `cancel` and a note; a reason of another kind or an inactive one is refused. | `must_succeed`; `must_reject:reason_invalid` | R1453, R1454 |
| `EC-317` | `scrap_reason_needs_scrap`: A production receipt or confirmation with a scrap reason and no scrap quantity is refused. | `must_reject:validation_failed` | R1454 |
| `EC-330` | `reason_required_by_setting`: With the core defaults, a count difference, a scrap line or an other issue without a reason is refused and a cancel without one succeeds; after `documents.reason_required.scrap` is set false, the same scrap line posts. | `must_reject:reason_required`; `must_succeed` | R1456, R1457 |

`EC-270` and `EC-273` also stand in the `ledger` spec, whose rows state the same law (ADR-0069.R9 is co-primary).

Edge cases whose source rules are another module's (not restated): `EC-271`, `EC-272` (`ledger`), `EC-310`, `EC-312`,
`EC-318`, `EC-319`.

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `documents.reason_required.count_difference` | boolean | `company` | `true` | R1456, R1457 |
| `documents.reason_required.scrap` | boolean | `company` | `true` | R1454, R1456, R1457 |
| `documents.reason_required.return` | boolean | `company` | `true` | R1456, R1457 |
| `documents.reason_required.reject` | boolean | `company` | `true` | R1456, R1457 |
| `documents.reason_required.other_receipt` | boolean | `company` | `true` | R1456, R1457 |
| `documents.reason_required.other_issue` | boolean | `company` | `true` | R1456, R1457 |
| `documents.reason_required.cancel` | boolean | `company` | `false` | R1456, R1457 |
| `documents.reason_required.block` | boolean | `company` | `false` | R1456, R1457 |

Reads, settings owned by other modules that the units of this chunk name: `ledger.business_unit.default` and
`ledger.business_unit.required_on_profit_and_loss` (`ledger`, ADR-0069.R13; R1417, R1425, R1430); `tax.destination_party`
and `tax.services_place_of_supply` (`tax`, ADR-0074.R4.N1); `agents.company_daily_max_cost`,
`agents.installation_daily_max_cost`, `agents.internal_reserve_share` and `assist.max_cost_per_run` (ADR-0078.R7);
`work.bulk_review_max_items` (ADR-0077.R3).

Reads, settings of other modules that units of other chunks of `master_data` name without stating them: `agents.<agent_type>.wake_up_mode.<kind>`,
`analysis.pseudonymize_known_subjects`, `artifacts.<function_or_kind>.max_window_days`,
`auto_post.purchase_invoice.min_supplier_invoices`, `auto_post.purchase_invoice.price_tolerance_percent`,
`auto_post.purchase_invoice.quantity_tolerance_percent`, `auto_post.purchase_invoice.require_full_receipt`,
`data_processing.policy`, `intake.trust.<document_type>.<field>.require_confirmation`,
`intake.trust.<document_type>.min_passed_rules`, `intake.trust.ocr_min_confidence`, `ui.post_review_max_amount`,
`work_case.<kind>.mode`.

## UI annotations

None: the sources hold no ADR-0077 annotation for this module.

## Conflicts

CONFLICT ADR-0068.R22.N1: the delivery's address is its ship-to party of ADR-0074.R1 and ADR-0074.R3, replacing the interim delivery_address column; stated in R1407.
CONFLICT ADR-0068.R22: the delivery fields of the rule stand, but the delivery address follows ADR-0068.R22.N1 (ship-to party columns); R1405 to R1407 cite it.
CONFLICT ADR-0074.R7.N1: the note left the refusal error code to later DDL work; ADR-0074.R7.N2 names it external_id_source_reserved with its database check, stated in R1444.
CONFLICT ADR-0074.R8: is_personal_data has no default and the command must state it, and field_class may also be sensitive_personal, per ADR-0074.R8.N1, ADR-0079.R2 and the DDL; R1445 and R1446.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0068.R16 | ref: ADR-0068.R16 |
| ADR-0068.R18 | R1401, R1402 |
| ADR-0068.R19 | R1403 |
| ADR-0068.R21 | R1404 |
| ADR-0068.R22 | R1405-R1407 |
| ADR-0068.R22.N1 | R1405-R1407 |
| ADR-0068.R23 | R1408 |
| ADR-0068.R24 | R1409 |
| ADR-0068.R25 | R1410 |
| ADR-0069.D0 | R1411 |
| ADR-0069.R1 | R1412-R1415 |
| ADR-0069.R2 | R1416-R1418 |
| ADR-0069.R3 | R1419 |
| ADR-0069.R4 | ref: ADR-0069.R4 |
| ADR-0069.R7 | R1420 |
| ADR-0069.R8 | R1421-R1423 |
| ADR-0069.R8.N1 | R1424 |
| ADR-0069.R9 | R1425-R1427 |
| ADR-0069.R12 | ref: ADR-0069.R12 |
| ADR-0069.R13 | ref: ADR-0069.R13 |
| ADR-0069.R16 | ref: ADR-0069.R16 |
| ADR-0069.R17 | R1428 |
| ADR-0069.R18 | R1429 |
| ADR-0069.R19 | R1430 |
| ADR-0070.D0 | ref: ADR-0070.D0 |
| ADR-0070.R2 | R1431-R1433 |
| ADR-0072.R3 | ref: ADR-0072.R3 |
| ADR-0073.R14 | ref: ADR-0073.R14 |
| ADR-0073.R16 | ref: ADR-0073.R16 |
| ADR-0074.D0 | not applicable: summary table of the decisions that ADR-0074 rules 1 to 22 state |
| ADR-0074.R1 | ref: ADR-0074.R1 |
| ADR-0074.R3 | R1434, R1435 |
| ADR-0074.R4 | ref: ADR-0074.R4 |
| ADR-0074.R4.N1 | ref: ADR-0074.R4.N1 |
| ADR-0074.R6 | R1436 |
| ADR-0074.R7 | R1437-R1442 |
| ADR-0074.R7.N1 | R1443, R1444 |
| ADR-0074.R7.N2 | R1443, R1444 |
| ADR-0074.R8 | R1445-R1447 |
| ADR-0074.R8.N1 | R1445, R1446 |
| ADR-0074.R9 | R1448 |
| ADR-0074.R10 | R1449 |
| ADR-0074.R11 | R1450 |
| ADR-0074.R12 | R1451 |
| ADR-0074.R13 | R1452, R1453 |
| ADR-0074.R14 | R1454 |
| ADR-0074.R15 | R1455 |
| ADR-0074.R19 | R1458 |
| ADR-0074.R20 | R1459 |
| ADR-0074.R21 | R1460 |
| ADR-0074.R22 | R1456, R1457 |
| ADR-0075.R5.N1 | ref: ADR-0075.R5.N1 |
| ADR-0076.R3 | ref: ADR-0076.R3 |
| ADR-0076.R3.N1 | ref: ADR-0076.R3.N1 |
| ADR-0077.R3 | ref: ADR-0077.R3 |
| ADR-0078.R7 | ref: ADR-0078.R7 |
| ADR-0078.R7.N1 | ref: ADR-0078.R7.N1 |
| ADR-0078.R7.N2 | ref: ADR-0078.R7.N2 |
| ADR-0079.R1 | ref: ADR-0079.R1 |
| ADR-0079.R2 | ref: ADR-0079.R2 |
| ADR-0079.R9.N1 | ref: ADR-0079.R9.N1 |
| ADR-0079.R9.N2 | ref: ADR-0079.R9.N2 |
| ADR-0080.D0 | ref: ADR-0080.D0 |
| ADR-0080.R1 | R1461 |
| ADR-0080.R3 | ref: ADR-0080.R3 |
| ADR-0080.R3.N1 | ref: ADR-0080.R3.N1 |
| ADR-0080.R4.N1 | ref: ADR-0080.R4.N1 |
