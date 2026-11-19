# ADR-0074: Core data-structure additions

Status: proposed (2026-11-19) under ADR-0005 (builder Claude Sonnet 5.5).
Design items: DS-20 (master data), DS-22 (commercial documents), DS-05 (documents), DS-06 (journal), DS-21 (migration), DS-30 (UI), DS-43 (production). Related decisions: none new. Principles 6, 12, 13. ADR-0004, ADR-0006, ADR-0009, ADR-0011, ADR-0014, ADR-0017, ADR-0018, ADR-0019, ADR-0022, ADR-0026, ADR-0028, ADR-0029, ADR-0030, ADR-0038, ADR-0040, ADR-0041, ADR-0044, ADR-0047, ADR-0048, ADR-0049, ADR-0052, ADR-0054, ADR-0055, ADR-0058, ADR-0063, ADR-0064, ADR-0068, ADR-0071, ADR-0072.

## Decision

The author's decisions of 2026-11-19, from the coverage scan of the data structures (input of the step 0 review): five additions are made to the core before the review, because each is cheap now and touches every table or every document later. Two requests of the scan are declined (rules 18 and 19).

| Need | Today | Decision |
| --- | --- | --- |
| Who is invoiced, who pays, where the goods go | One partner and one address snapshot per header; `delivery.delivery_address` is an interim `jsonb` | Parties on documents, with defaults from `partner_relationship` (rules 1 to 6) |
| The ID of a record in another system | `import_key_map`, named in ADR-0044 and never defined | One table, `external_id_map`, with a lookup function (rule 7) |
| Company-defined extra fields | Deferred past Phase 1 with no seam | A definition table and a `custom_values jsonb` column on 11 tables (rules 8 to 12) |
| Cancel, reject, return, scrap and count reasons | Free text, or no reason at all | One `reason` catalog, referenced by foreign key; a company setting per kind says whether a reason is required (rules 13 to 15, 22) |
| A note on a document | None on any header | `note` on 17 document headers and on the journal entry (rules 16, 17) |
| Parallel ledgers | Not designed | Out of scope, the author's decision (rule 18) |
| `updated_by`, `updated_at` on every table | `recorded_at` only | Not added; change history stays with the audit rows (rule 19) |

### Rules

**1. Partner roles on commercial documents**

1. A sales document keeps `partner_id` as the **sold-to** party (the buyer: price list, salesperson, payment term, currency and print language come from its profile) and may name three more parties; a purchase document keeps `partner_id` as the **ordered-from** party and may name two.
   - **Customer side:** `ship_to` (where the goods go), `bill_to` (whose identity the invoice carries) and `payer` (who owes the money).
   - **Supplier side:** `invoicing_party` (who issued the invoice and carries the payable) and `payee` (who receives the payment).
   - **A party that is not stated is the next one up.** `ship_to` and `bill_to` fall back to the sold-to party; `payer` to the bill-to party; `invoicing_party` to the ordered-from party; `payee` to the invoicing party. A customer with one account therefore carries no new value on its documents.
   - **The columns.** Every party is `<role>_partner_id`, `<role>_name` and, for `ship_to`, `bill_to` and `invoicing_party`, `<role>_address_id` and `<role>_address` (a `jsonb` snapshot with the keys of `partner_address`); `bill_to` and `invoicing_party` also carry `<role>_tax_id`. They are the snapshot style of ADR-0028 rule 16: copied by `Create` and `Update`, part of the content, never changed by posting. A name exists exactly when the party is named (`ck_<table>_<role>`). The address is named by `(partner, address)` through the new key `UNIQUE (company_id, partner_id, id)` on `partner_address`, so an address of another partner is refused by the database.
2. The columns sit on:

   | Parties | Headers |
   | --- | --- |
   | `ship_to`, `bill_to`, `payer` | `quotation`, `sales_order` |
   | `ship_to` | `delivery` (replaces the interim `delivery_address`) |
   | `bill_to`, `payer` | `sales_invoice`, `sales_return`, `credit_note`, `debit_note` |
   | `invoicing_party`, `payee` | `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note` |

   Receipts, returns to suppliers, returns from customers and service receipts keep the one partner they have: a receipt is of what the ordered-from party delivered, whoever invoices it. A document made from another (an order to a delivery or an invoice, an invoice to its credit note) copies the parties of its source, which a person may change until posting.
3. `partner_relationship` (owner `master_data`, company data, change-tracked) holds the defaults: `partner_id`, `related_partner_id`, `role` (`ship_to`, `bill_to`, `payer`, `invoicing_party`, `payee`), an optional `address_id` of the related partner, `is_default` and `is_active`, unique per partner, related partner and role, and at most one default per partner and role. `Create<Type>` takes, for each role, the default relationship of the sold-to or ordered-from partner; a partner without one leaves the party unstated. It reads only `partner`, `partner_address` and itself, so `crm` and master data stay independent of the ledger, tax, inventory, cash and production.
4. **Which party each consequence uses.** The author's expectation held for every consequence checked; the purchase side follows the same split between who carries the liability and who is paid.

   | Consequence | Party |
   | --- | --- |
   | Open item and its partner, the receivable control line, matching, allocation proposals, dunning and its recipients, statements | `payer`, else `bill_to`, else sold-to |
   | Credit exposure, credit hold, `customer_profile.credit_limit` and `receivable_account_id` | the same party: exposure sums the open items, invoices in `issuing`, delivered-not-invoiced value and undelivered order value whose payer resolves to it |
   | Tax identity: the partner tax group read by the tax matrix, `tax_line.partner_tax_id`, the buyer identity of an e-invoice, the invoice's printed customer | `bill_to`, else sold-to |
   | Delivery address and the delivery note's addressee (the carrier stays the delivery method's, ADR-0068 rule 22) | `ship_to`, else sold-to |
   | `document.partner_id`, the owner scope, CRM links, INV-49 | sold-to, unchanged |
   | Price list, salesperson, payment term, currency, print language, minimum remaining shelf life | sold-to |
   | Purchases: payable open item and control line, the supplier-invoice natural key and duplicate check, input tax identity, three-way match | `invoicing_party`, else ordered-from |
   | Purchases: the payment's partner and the beneficiary's bank account (ADR-0028 rule 15) | `payee`, else the invoicing party |
   | Purchases: GR/IR, supplier price list, buyer, lead times | ordered-from |

5. **Checks.** A named party is an active partner of the company, and its address is one of its own (`party_invalid`). The party that carries the open item (payer, else bill-to, else sold-to; on purchases the invoicing party) must hold the `customer` or `supplier` role of the side, otherwise `partner_role_missing` (ADR-0047 rule 3). The check `partner_snapshot_stale` (ADR-0028 rule 16) reads every named party the same way. A `payee` that is not the invoicing party, and a `payer` that is not the bill-to party, change who is paid and who is chased: their relationship rows are changed only through change proposals when an agent acts (ADR-0029 rule 4, as bank accounts).
6. The consequences above change these accepted rules; each gets a note (see Documents updated). INV-49 and the open item identity of ADR-0026 rule 1 are unchanged: the open item's `partner_id` is simply the payer (receivables) or the invoicing party (payables), as the posting writes it.

**2. External and source-system IDs**

7. `external_id_map` (owner `master_data`) maps `(company_id, source_system, table_name, external_key)`, its primary key, to `entity_id`, and is unique on `(company_id, source_system, table_name, entity_id)`: one key per entity in a source system. `source_system` is a lower-case code (`^[a-z][a-z0-9_.-]{0,39}$`) such as a web shop, an EDI partner or a former system; the key is text of up to 200 characters. Rows are never updated.
   - **It replaces `import_key_map`** of ADR-0044 rule 5, which was named and never defined. The draft batch keeps its provisional key map in the batch (staging), so an agent preparing a batch changes no company data; `RunImport` writes the rows in the transaction that creates the records. A batch names its source system: a field of `CreateImportBatch` and of the workbook header, added when DS-21's DDL is written (no import DDL exists yet).
   - **Integrations** (actor `integration`) set and clear their own keys through the same commands, so a web shop's customer ID resolves to the partner without a column per system.
   - **Lookup.** `external_id_resolve(company, source_system, table, key)` returns the entity ID, and `external_key_of(company, source_system, table, entity)` the key; the queries `ResolveExternalId` and `ListExternalIds` call them. Commands still take IDs only (ADR-0006 rule 5): an agent resolves a key with the query, then sends the command.
   - **Commands.** `SetExternalId` is idempotent for an identical mapping, `external_id_taken` when the key names another entity, `external_id_conflict` when the entity has another key in that source system. `ClearExternalId` deletes a mapping; the deletion of a draft document deletes its mappings in the same transaction. Both use the leaf `data_import` (ADR-0054 rule 7). `table_name` must be a company table with an `id` (`external_id_table_invalid`).
   - **The target is polymorphic**, so INV-860 checks that it exists and is of the company.
   - **What stays.** The natural keys that enforce a duplicate rule for one document type (`operation_confirmation.external_reference`, `purchase_invoice.external_document_key`, the inbound message and bank line keys) are not ID maps and stay.

**3. Custom-field seam**

8. `custom_field_definition` (owner `master_data`, company data, `master_data_change`, change-tracked) holds, per company and target table, a `code` (the key; `^[a-z][a-z0-9_]{0,39}$`, never changed), a `label` (company language; other languages in `data_translation`, ADR-0018 rule 17), a `data_type` (`text`, `integer`, `decimal`, `boolean`, `date`, `choice`), `validation` (a `jsonb` object: `max_length` and `pattern` for text, `min`, `max` and `scale` for numbers, `choices` for choice), `is_required`, an optional `field_class` (`cost` or `margin`, ADR-0017 rule 10), `is_personal_data` and `is_active`. A field with `is_personal_data` true holds personal data: its values carry the personal label that the LLM gateway strips or routes (spec 17), and the erasure of the record clears them (ADR-0038). It is false by default, and the setup agent proposes true for free-text and contact-like fields on partners (chief architect, 2026-11-19). At most 30 active definitions per company and table (`custom_field_limit`): a design bound, not a policy, like the 12 detailed components of ADR-0072.
9. A `custom_values jsonb NOT NULL DEFAULT '{}'` column, with `jsonb_typeof = 'object'`, sits on the **master tables** `partner`, `product` and `item` and the **document headers** `quotation`, `sales_order`, `delivery`, `sales_invoice`, `purchase_order`, `goods_receipt`, `purchase_invoice` and `production_order`. Those are the tables a company most needs to extend; lines, the journal, stock and cash tables get none in Phase 1. `target_table` is held to the list by a CHECK, so adding a table is an ADR note and a column, never data.
10. **Validation is in the command layer.** `Create` and `Update` of a target table validate `custom_values` against the table's definitions: an unknown key is `custom_field_unknown`, a wrong value `custom_field_invalid`, a missing value of a required field `custom_field_required` (a field made required later is checked at the next `Update`, never retroactively). A retired field keeps its values, shows them and refuses a change. A decimal is a decimal string, never a float. The data type of a definition cannot change once a record carries a value (`custom_field_in_use`). On a document the column is content: it is written into the version, and posting freezes it.
11. **The generated schemas carry it** (ADR-0022 rule 17; ADR-0040 rule 4): every command and query schema that names a target table has `custom_values` as an object with the annotation `x-nativeflows-custom-values: "<table>"`. The generated files stay independent of any company. The renderer and agents read the company's fields through `ListCustomFieldDefinitions(target_table)`, which returns them with their field classes and translated labels (`x-nativeflows-field-class` per key), and a restricted actor loses a classed key like any other classed field.
12. **Not in Phase 1:** a form builder, custom tables (the "tables" of spec 16 level 1 stay after Phase 1), calculated fields, references to other records, custom fields on lines, indexes on `custom_values`, analysis measures or dimensions over custom values, and copying values from a source document to the next one (a person sets them).

**4. Reason catalogs**

13. `reason` (owner `master_data`, company data, change-tracked) holds `kind` (`cancel`, `reject`, `return`, `scrap`, `count_difference`, `block`, and `other_receipt` and `other_issue` for the documents of ADR-0075 rules 11 and 12), `code`, `name` (company language; others in `data_translation`) and `is_active`, unique per company, kind and code, and by `(company_id, id, kind)`. A column that takes one kind stores the kind beside the ID (`<column>_kind`, default and CHECK to that kind) and references `(company_id, id, kind)`, so the database holds the kind (the pattern of `price_list_kind`). The kind `block` has no consumer in this ADR: it is reserved for the partner and item blocks a later ADR adds. Reasons are company data seeded by a package template if the package has one; the core seeds none. A command that names a reason takes an active one of its company and kind (`reason_invalid`); a missing reason that the company's setting requires is `reason_required` (rule 22); deactivating a reason never touches a document that names it.
14. **What becomes a foreign key:**

    | Was | Becomes |
    | --- | --- |
    | `quotation.cancel_reason` (interim text) | `document.canceled_reason_id` with `canceled_note`, for every type (`Cancel<Type>` takes both, optional); allowed only in state `canceled` |
    | The comment of `approval.reason` | stays required text (ADR-0055 rule 9) and gains `reject_reason_id`, allowed only on a rejection |
    | (none) | `return_reason_id` on the lines of `return_to_supplier`, `return_from_customer`, `sales_return` and `purchase_return` |
    | `production_issue_line.reason_code`, `operation_confirmation.scrap_reason_code`, `production_receipt.scrap_reason_code` (text, "company data") | `scrap_reason_id`, kind `scrap`; the kind covers over-issue and component scrap too |
    | (new tables of ADR-0075) | `scrap_line.scrap_reason_id` (required) and `stock_count_line.difference_reason_id` |

    The scan counted four production tables; the DDL has three scrap-reason columns, and `production_order_component` has none. The existing CHECKs keep their meaning: a scrap reason needs a scrap quantity.
15. **What stays as it is:** the fixed system codes (`closed_reason`, `credit_note.reason` and `debit_note.reason`, `open_item_collection.payment_block_reason`, `demand_supply_line.hold_reasons`, `planning_exception.reason`), which logic reads; a person's required free text (`work_case.cancel_reason`, `operation_time_log.cancel_reason`, `nonconformance.cancel_reason`, `taint_clearance.reason`, `approval.reason`, `period_unlock_request.reason`); `stop_reason` and `defect_code`, which are catalogs with their own columns; `warehouse_task.shortage_reason` (a candidate for the `count_difference` kind later, an open question). The ADR-0064 mapping step's closed list of scrap reasons is the company's active reasons of kind `scrap`.

**5. Header notes**

16. `document` and `document_version` hold no note (the version content is canonical JSON of the header and lines), and no typed header has one. A `note text` column (at most 4,000 characters) is added to the headers `quotation`, `sales_order`, `purchase_request`, `purchase_order`, `goods_receipt`, `return_to_supplier`, `delivery`, `return_from_customer`, `service_receipt`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note`, `purchase_invoice`, `purchase_return`, `purchase_credit_note` and `purchase_debit_note`, and to the headers of ADR-0075. It is internal free text: content of the version, frozen at posting, untrusted for agents (ADR-0029), and printed only by a layout that names it (ADR-0049). Line `description` columns stay.
17. `journal_entry.note` (at most 4,000 characters) holds the note of the document, copied at posting, so reports read one place. The entry stays append-only. `payment`, `bank_statement` and the production headers keep no note in this ADR.

**Declined by the author, 2026-11-19**

18. **No parallel ledgers.** Phase 1 serves companies that keep their books under one accounting framework, and the author decided that a second ledger is out of scope. The journal gets no ledger column, no ledger in the keys of `journal_line` or `account_period_balance`, and no seam for one. A group that reports under another framework uses the group currency of ADR-0011 and the mapping of its reporting package.
19. **No `updated_by` or `updated_at` on every table.** Who changed what and when is recorded where the change is made: `audit_change` for the change-tracked tables (ADR-0038 rule 3), `document_version` for documents (ADR-0009 rule 9) and `audit_record` for every command (ADR-0038 rule 6). A reader who asks "who last changed this partner" queries the audit rows; a column on 380 tables would repeat them and cost a write each. The `recorded_at` finding of the architecture overview is a separate matter and is unchanged.

**Commands, leaves, catalogs and DDL**

20. Commands, all `master_data_change` and change-tracked unless stated: `CreatePartnerRelationship` and `UpdatePartnerRelationship` (leaf `partner`); `CreateReason` and `UpdateReason` (new leaf `reason`); `CreateCustomFieldDefinition` and `UpdateCustomFieldDefinition` (new leaf `custom_field`); `SetExternalId` and `ClearExternalId` (leaf `data_import`, human or integration actor). Queries: `ListPartnerRelationships`, `ListReasons`, `ListCustomFieldDefinitions`, `ResolveExternalId`, `ListExternalIds`. These are new names, registered in the command registry (ADR-0008) when the code is written; there is no separate catalog of commands. The two new leaves sit under `master_data`, so the owner template has them at full; no other template gets them in this ADR.
21. DDL: `partner_relationship`, `external_id_map` with its two functions, `custom_field_definition` and `reason` in DS-20; the columns of rules 1 to 3, 9, 14, 16 and 17 on the tables named, in DS-20, DS-22, DS-43, DS-05 and DS-06. Every new table is owned by `master_data`. `partner_address` and `project` gain `UNIQUE (company_id, partner_id, id)` and `UNIQUE (company_id, id)`.

**Reason requirement** (the chief architect's decision for the author, 2026-11-19)

22. Whether a reason is required is policy, so it is one company setting per kind (ADR-0063), boolean, scope `company`, leaf `reason`, direction `true_tighter`:

    | Setting | Core default | Why |
    | --- | --- | --- |
    | `documents.reason_required.count_difference` | true | a difference changes stock and value |
    | `documents.reason_required.scrap` | true | a write-off changes stock and value |
    | `documents.reason_required.return` | true | a return changes stock and value |
    | `documents.reason_required.reject` | true | a rejection needs an audit trail |
    | `documents.reason_required.other_receipt` | true | an unplanned receipt changes stock and value |
    | `documents.reason_required.other_issue` | true | an unplanned issue changes stock and value |
    | `documents.reason_required.cancel` | false | a canceled draft or pending document posted nothing |
    | `documents.reason_required.block` | false | no consumer in Phase 1 |

    A missing required reason is `reason_required` (validation), checked by the command on the line or header that takes the reason: a count key with a difference, a scrap line, a production issue, confirmation or receipt with scrap, a return line, an other receipt or other issue line, a rejection, a cancel. The database keeps every reason column nullable, so the setting alone decides; loosening a setting does not touch documents already written. The catalog `settings.csv` carries the eight rows (ADR-0063 rule 29 note).

## Context

The coverage scan of the data structures (a scan of the DDL against the structures of reference ERP systems) found 86 gaps; this ADR takes the five that the author put in scope, which were reported by several groups of the scan and cost more the later they are added:

- **Parties** were reported four times: one partner per header makes a head-office invoice, a separate payer or a warehouse delivery impossible, and credit exposure and tax identity follow the wrong partner.
- **External IDs** were reported by all four groups; ADR-0044 relies on a table nobody defined.
- **Custom fields** touch every table, schema and screen if added late.
- **Reasons** are free text in three places and absent elsewhere, so reports cannot group them and each later fix touches several tables.
- **Header notes** are the smallest and the cheapest before print layouts exist.

The other scan items stay for the step 0 review.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| A party table per document (rows of role, partner, address) | Any number of roles | Every consequence joins it; the snapshot rule is harder; the five roles are enough |
| Party columns on the header, null meaning the next party up (chosen) | Simple documents carry nothing new; the snapshot style is unchanged; the database holds the address key | About 90 party columns across the headers |
| Payer on the customer profile only | One column | Cannot differ by order; credit exposure per order impossible |
| A column `external_id` per table | Simple lookup | One system only; every table changes |
| One generic map (chosen) | Any system and table; no column | A polymorphic key, held by an invariant |
| Custom values in a side table per target | No column on the targets | A join for every read; the version content could not carry them |
| `custom_values jsonb` on chosen tables (chosen) | Part of the content and the version; one read | Validation is in the command layer; no index in Phase 1 |
| A custom field on every table | Complete | Touches lines, journal and stock for no need |
| Reason as a text column with a CHECK per company | None | A CHECK cannot be company data |
| One catalog with the kind in the key (chosen) | Company data, translatable, one place | A kind column beside each reference |
| A catalog per kind | No kind column | Six tables for one shape |
| A note in `document_version` content only | No column | Not queryable, not on the typed header the screens read |
| A `note` column on the headers (chosen) | Queryable; frozen with the content | One column on each header |

## Consequences

- **Sales and finance:** a customer can have a ship-to site, an invoicing head office and a paying group; credit is held against the payer; tax and the invoice follow the bill-to.
- **Purchasing:** the supplier that invoices and the party that is paid can differ from the one ordered from.
- **Integrations and migration:** one map and one lookup for every external system.
- **Companies:** their own fields on partners, products, items and the main documents, with a validated, translated, access-classed definition.
- **Reports:** cancel, return, scrap and count reasons group; a rejection has a reason beside its comment.
- **Build:** four small tables, two functions, about 130 columns added by a mechanical rule, 8 commands and 5 queries. Small-model friendly.
- **Accepted ADRs** carry notes at the rules named below; no rule is rewritten.
- **Revisit when:**
  - a company needs more than three parties per document, or a party per line;
  - a company needs custom fields on lines or stock, or an index on them;
  - a company must keep two accounting frameworks in one set of books (rule 18).

## Documents updated

- **ADRs** (notes tagged "ADR-0074, proposed 2026-11-19"): ADR-0009 rule 1; ADR-0014 rules 2 and 10; ADR-0018 rule 17; ADR-0019 rule 5; ADR-0022 rule 17; ADR-0026 rules 1 and 15; ADR-0028 rule 16; ADR-0030 rule 6; ADR-0034 rules 11 and 12; ADR-0040 rule 4; ADR-0041 rule 3; ADR-0044 rule 5; ADR-0047 rules 2, 3, 6, 8 and 18; ADR-0048 rules 8 and 19; ADR-0052 rule 18; ADR-0058 (user-defined fields); ADR-0064 (scrap reason list); ADR-0063 rule 29 (the eight settings); ADR-0068 rule 22; ADR-0071 rules 2 and 4.
- **Catalogs:** authorization-areas.csv (2), settings.csv (8, rule 22), invariants.csv (5), edge-cases.csv (11).
- **Design:** DS-20, DS-22-09-42, DS-43-54, DS-05 and DS-06 SQL; DS-04 (eleven error codes, `reason_required` among them); DS-16 and DS-17 (blocks and counts); the glossary (new rows only); the generated overview.
- **Lab:** `t27_partner_roles.py` and the lab README (findings); fixtures of `t14_commercial_inventory_ddl.py` (M5 expects 22 headers), `t16_planning_production_ddl.py` (N52 names a reason row) and `t17_uom.py` (D03 expects the four stock line tables).
- **Index and log:** docs/adr/README.md; docs/open-questions.md (the decisions of rules 18 and 19 marked decided; new questions); docs/runbook/step-log.md.

## Edge cases and invariants

**Invariants** (DS-16; block INV-860 to INV-864; first step with master data):

- **INV-860** `external_id_target_exists` (area `master_data`): every `external_id_map` row names an existing row of its table, of its company.
- **INV-861** `reason_kind_matches_column` (area `master_data`): every reason reference names a reason of the kind its column takes, of the same company, and a canceled-reason or reject-reason column is set only in the state that allows it.
- **INV-862** `custom_values_defined` (area `master_data`): every key of a `custom_values` object has a definition (active or retired) of its company and table, and its value fits the data type.
- **INV-863** `payer_is_open_item_partner` (area `receivables_payables`): the open item of a posted sales invoice, credit note or debit note belongs to its payer, else its bill-to party, else its sold-to partner; of a purchase document, to its invoicing party, else its ordered-from partner.
- **INV-864** `document_party_complete` (area `documents`): every named document party has its name; a tax ID, an address or an address key is held only with its party, and the address is one of the party's own; every party is a partner of the document's company; a party is named exactly when its name is.

**Edge cases** (DS-17; block EC-310 to EC-319, all taken, and EC-330):

- **EC-310** `invoice_head_office_and_payer`: an order with a ship-to site, a head-office bill-to party and a paying group: the delivery goes to the site, the invoice and its tax carry the head office, the open item and the credit exposure the group.
- **EC-311** `party_defaults_from_relationships`: a partner with one default ship-to and no payer relationship gets the ship-to on a new order and no payer; changing the default does not touch an existing order.
- **EC-312** `party_stale_snapshot`: a bill-to party's address changes after the order; posting the invoice warns with `partner_snapshot_stale` for that party.
- **EC-313** `external_id_reimport`: a web-shop customer imported twice with the same key updates the partner; a second key for the same partner in that system is `external_id_conflict`.
- **EC-314** `custom_field_required_and_retired`: a required custom field refuses a new order without a value; after it is retired, existing orders keep and show the value and refuse a change.
- **EC-315** `custom_field_restricted_actor`: a custom field of class `cost` is absent from the responses of an actor without the class.
- **EC-316** `cancel_with_reason`: a quotation canceled with a reason and a note; a reason of another kind is `reason_invalid`.
- **EC-317** `scrap_reason_needs_scrap`: a production receipt with a scrap reason and no scrap quantity is refused.
- **EC-318** `header_note_frozen`: a note written on a draft is part of its version and cannot change after posting; the journal entry carries a copy.
- **EC-319** `payee_change_by_proposal`: an agent that changes a supplier's payee relationship directly gets `proposal_required`; its proposal executes after a person approves.
- **EC-330** `reason_required_by_setting` (block EC-330 to EC-339, shared with ADR-0075's remaining documents): with the core defaults, a count difference, a scrap line or an other issue without a reason is refused with `reason_required` and a cancel without one succeeds; after `documents.reason_required.scrap` is set false, the same scrap line posts.
