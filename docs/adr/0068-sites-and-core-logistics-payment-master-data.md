# ADR-0068: Sites and core logistics and payment master data

Status: accepted (2026-11-21) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5; proposed 2026-11-17) after three review rounds, the fixes verified by Claude Opus 5.5.
Design items: DS-20 (master data), DS-09 (inventory and costing), DS-22 (commercial documents), DS-25 (cash), DS-51 to DS-54 (production and planning), DS-04, DS-16 and DS-17. Related decisions: the chief architect's core master-data decisions of 2026-11-17 (site, payment method, Incoterms, delivery method, resource group). Principles 3, 6, 13. ADR-0004, ADR-0006, ADR-0009, ADR-0015, ADR-0019, ADR-0020, ADR-0021, ADR-0022, ADR-0023, ADR-0024, ADR-0029, ADR-0030, ADR-0033, ADR-0034, ADR-0035, ADR-0036, ADR-0045, ADR-0047, ADR-0048, ADR-0063, ADR-0067, ADR-0069.

## Decision

Five pieces of master data join the core. Each is small, and each closes a gap that customers would otherwise model by hand.

**Site.** A `site` (SAP: plant; Dynamics 365: site) sits between the company and its warehouses. Every physical warehouse belongs to one site. The company's valuation level gains `site`, so a factory with a raw-materials warehouse, a production floor and a finished-goods warehouse keeps one moving average, and two factories keep separate costs. The site of a production warehouse is the plant. Every company has one site from setup, and while it has only one, the UI hides the concept.

**Payment method** (`master_data`): a default on partner profiles, a header field on quotations, orders, invoices and payments. Its default money account lives in a `cash`-owned table, so `master_data`, `sales`, `purchasing` and `crm` never depend on `cash`.

**Incoterms:** an installation reference catalog with its natural code key. Documents carry the code and the named place. The effect is advisory only.

**Delivery method** (`master_data`): with an optional carrier, which is a supplier, and a tracking link. Deliveries and goods receipts carry the carrier, tracking number and vehicle registration.

**Resource group** (`production`): work centers that can stand in for each other, inside one site. Load is shown per group, and an operation may move to another member.

The CRM-only deployment profile holds: the four `master_data` tables reference no table of `ledger`, `cash`, `inventory`, `tax` or `production`.

### Rules

**Sites**

1. `site` (company data, `master_data`, effect class `master_data_change`, change-tracked; agents propose changes, ADR-0029 rule 2):
   - **Fields:** `code` (unique per company), `name`, `kind`, nullable `branch_id`, `address` (the columns of `partner_address` as keys, like `branch`), nullable `working_calendar_id`, nullable `business_unit_id` (defined by [ADR-0069](0069-business-unit-dimension.md)), `is_active` and `recorded_at`.
   - **Kind.** `factory`, `distribution`, `store` or `office`. It is a label only, and no rule reads it. The UI names the level after it ("Factory", "Store").
   - **Name.** The identifier is `site`, not `plant`, because a site may also be a distribution centre, a store or an office.
   - **Calendar.** `working_calendar_id` is a record default: a new warehouse or work center of the site takes it when it is created without a calendar. Nothing reads it at run time.
   - **Deactivation** is refused while an active warehouse names the site (`site_in_use`).
2. Warehouses (a note on [ADR-0020](0020-inventory-and-costing-model.md) rule 1):
   - **Physical warehouses** carry `site_id`, required. `transit` and `goods_sent` warehouses carry none: their site is the site of their `valuation_warehouse_id`. Every reader derives it through one function, `master_data.contract.site_of_warehouse`.
   - **Choosing the site.** `CreateWarehouse` without `site_id` takes the company's only active site. With several active sites, it is refused with `site_required`.
   - **Branch.** When a site has a `branch_id`, each of its physical warehouses has the same `branch_id`. `CreateWarehouse`, `UpdateWarehouse` and `UpdateSite` refuse a difference with `site_branch_mismatch`. A site without a branch leaves its warehouses' branches free.
   - **Fixed after posting.** A warehouse's `site_id` changes only while the warehouse has no material document line (`warehouse_site_fixed`), because at level `site` the site is the valuation area. Moving a stocked warehouse to another site is a new warehouse and a transfer.
3. The default site:
   - **At company creation.** `CreateCompany` creates one site in the same transaction: code `MAIN`, the company's name, and a `kind` chosen in the setup flow (`distribution` when none is given).
   - **Upgrade.** The migration that adds the table creates one such site per existing company and sets it on every physical warehouse.
   - **Hidden while single.** While a company has one active site, forms, lists and prints leave the site out, and commands default it (rule 2). A second active site shows it everywhere. This follows from the data, so it needs no setting or preset item (ADR-0067).
4. Branch and site stay independent. A branch is the legal, tax and numbering unit (ADR-0009 rule 15; [ADR-0041](0041-tax-engine.md) rule 11). A site is the physical and operational unit. They are linked only by the optional `site.branch_id`: a branch may span several sites, and a site lies in at most one branch.
5. Reporting:
   - **No journal column.** `journal_line` gets no `site_id`. Reports roll up warehouse to site through `warehouse.site_id` and rule 2's function. `journal_line.warehouse_id` is nullable, so lines without a warehouse fall under the empty site member. (review note, 2026-11-21)
   - **Analysis.** The analysis catalog gains the dimension `site`, which becomes the parent of `warehouse` ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md)).
6. Recommended modelling, given by the setup agent and the guidance, and enforced by nothing:
   - **One warehouse per site.** Use one physical warehouse per site, with zones and bins ([ADR-0023](0023-warehouse-management.md) rule 2) for raw materials, the production floor, finished goods and quality.
   - **When to split.** Split into several warehouses only when they need separate keepers, separate stock reports or separate accounts (the `warehouse` determinant, [ADR-0015](0015-account-determination.md) rule 8).

**Valuation by site**

7. `company.valuation_area_level` gains `site`, so its values are `company`, `site` and `warehouse` (a note on ADR-0020 rule 2 and ADR-0015 rule 8):
   - **The area.** With `site`, all physical warehouses of a site, together with the transit and goods-sent warehouses attached to them, form one valuation area.
   - **Fixed.** The level is still set at setup, and ADR-0020 rule 16 is unchanged.
   - **Preset.** `CreateCompany` takes an optional preset code; the preset's record default fills `valuation_area_level` when the command leaves it unset (review note, 2026-11-21). The setup flow fills it from the preset's record default ([ADR-0067](0067-quickflows-operating-presets.md) rule 18): `site` in `standard` and `company` in `quickflows`. `site` is the standard value for three reasons: it equals level `warehouse` when each site has one physical warehouse (rule 6); it avoids a separate average and a valuation event per internal move when a site has several; and it keeps two factories apart.
8. Recording the area. This is the detail the decisions left open.
   - **The columns.** A line records its area in two nullable columns: `valuation_site_id` (new, set at level `site`) and `valuation_warehouse_id` (unchanged, set at level `warehouse`). Both are null at level `company`, and at most one is set (`ck_material_document_line_valuation_area`).
   - **Where.** `material_document_line` and `preliminary_price` carry both. The unique key of `preliminary_price` covers both, with `NULLS NOT DISTINCT`.
   - **Who sets them.** The stock lock helper sets them from the company's level and the line's warehouse, and INV-810 checks the result. The costing job keys an area by the pair.
   - **Why not generalize `valuation_warehouse_id`.** A site is not a warehouse. Naming a site-level area by a warehouse key would need a representative warehouse, which would change if that warehouse closed.
   - **Why not a `valuation_area` table** with one `valuation_area_id`. It gives one non-null key, but the table must be kept in step with sites and warehouses, its rows are created on first posting, and every existing reference and lab would be renamed.
   - **What two typed columns give.** They are additive, they keep ADR-0020 rule 2's text true for level `warehouse`, and the database checks each foreign key.
9. Costing:
   - **The solve.** The exact solve over areas linked by transfers (ADR-0020 rule 12) is unchanged. At level `site` its nodes are sites.
   - **Transfers inside one area are value-neutral.** The period-end adjustment changes the issue and the receipt by the same amount, so the area's value does not change. `stock_value` still moves per warehouse, and each warehouse's inventory account still equals its stock value (ADR-0020 rule 6).
   - **Preliminary prices.** The fallbacks of ADR-0020 rule 11 read "the area" as the site.
   - **Accounts.** Account determination keeps its `warehouse` determinant. A site gets none.
   - **Lab.** A lab check covers both properties (Documents updated).

**Production and planning**

10. The plant is the site of the production warehouse (a note on [ADR-0033](0033-production-master-data.md) rule 11). This supersedes the Decision's "the production warehouse in place of a plant":
    - **No new columns.** Production versions, work centers and orders still name a production warehouse. `work_center` gets no `site_id`, because the site is derived through `production_warehouse_id`, so there is one source of truth.
11. Planning still runs per (item, warehouse) (ADR-0024 rule 1):
    - **Routes inside one site.** `CreateTransferRoute` may omit `lead_time_days` only when both warehouses lie in the same site, and the route then gets 0. Between sites the value stays required.
    - **Later.** Site-level pooled planning (SAP's plant-level MRP) is an open question for after Phase 1.

**Resource groups**

12. `resource_group` (company data, `production`, effect class `master_data_change`, change-tracked): `code`, `name`, `is_active` and `recorded_at`. `work_center.resource_group_id` is nullable.
    - **The mapping.** A work center with `capacity_units` already is a pool of identical machines or people: a Dynamics 365 resource group, or an SAP work center with pooled capacity. A resource group adds the level above: separate work centers that can stand in for each other.
    - **Members.** All members lie in one site, derived through their production warehouses (`resource_group_site_mismatch`). They record the same set of activity types in `work_center_activity` ([ADR-0033](0033-production-master-data.md) rule 12; `resource_group_activity_mismatch`). `UpdateWorkCenter` and the work center activity commands check both. To change a member's activity types, remove it from the group first. INV-811 checks the result.
    - **Inactive groups** take no new members. Their members stay grouped until they are removed.
13. Load:
    - **The primary work center.** Routing operations keep it ([ADR-0033](0033-production-master-data.md) rule 10).
    - **Load per group.** `ListWorkCenterLoad` ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 3) and `ListCapacityLoad` ([ADR-0036](0036-multi-level-mrp.md) rule 11) accept a resource group in place of a work center. They return the load and the available hours, each summed over the members, with each member's hours computed by ADR-0033 rule 11.
    - **Overload.** `capacity_overload` stays per work center, and its evidence adds the group's spare hours.
    - **Leveling.** `GetCapacityLevelingProposal` (ADR-0036 rule 12) may propose moving operations to a member with spare hours. A proposal is never applied without approval.
14. Moving an operation:
    - **When.** On a draft order ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 2), or by a change order on a released one (ADR-0034 rule 8, which already refuses moving a confirmed operation).
    - **Where to.** An internal operation's work center may change to another active member of its group, in the order's production warehouse (otherwise `work_center_outside_warehouse`, as for routings).
    - **What carries over.** The operation's standard values carry over: durations and activity quantities, as copied. Scheduling uses the target's calendar, `capacity_units`, `hours_per_day` and `efficiency_percent`.
    - **Cost.** Actual cost follows the work center on the operation when it is confirmed, with that work center's cost center and activity rates ([ADR-0035](0035-production-costing.md) rules 7, 14). A confirmed operation cannot move, so one operation's cost never splits across work centers.
    - **Moves outside the group** stay the ordinary edits of ADR-0034.
    - **Not Phase 1.** Named individual resources, such as a specific machine, operator or tool with its own calendar or skills, are not Phase 1. They are an open question with a seam: `capacity_units` already covers counting.

    Note ([ADR-0071](0071-work-orders-and-shop-floor-execution.md), proposed 2026-11-17): besides the change order that moves the planned work center (which, before start, also resets the execution work center), a WO not yet started moves inside its group by `TransferOperation` without a new version; "the work center on the operation when it is confirmed" is `operation_confirmation.work_center_id`, the execution work center (ADR-0071 rule 16).

**Payment methods**

15. `payment_method` (company data, `master_data`, effect class `master_data_change`, change-tracked): `code`, `name`, `kind`, `is_active` and `recorded_at`.
    - **Kinds:** `cash`, `bank_transfer`, `card`, `e_wallet`, `cheque`, `direct_debit`, `cash_on_delivery`, `offset` or `other`.
    - **No posting logic.** No posting rule, account determination or tax rule reads a payment method.
    - **Defaults.** `customer_profile.payment_method_id` and `supplier_profile.payment_method_id` hold the defaults.
    - **Headers.** `quotation`, `sales_order`, `sales_invoice`, `purchase_order` and `purchase_invoice` carry `payment_method_id`. It is copied from the profile at creation and then from the source document (ADR-0047 rule 2), changeable while the document is a draft or by a change order, and printed.
    - **Payments.** `payment.payment_method_id` records the method used. A payment drafted from an invoice copies the invoice's method.
16. `payment_method_money_account` (company data, owned by `cash`, effect class `master_data_change`, change-tracked) holds the default money account per method:
    - **Fields:** `payment_method_id`, `money_account_id`, `currency` (the money account's, held by a composite key) and an optional `branch_id`.
    - **Key.** The row is unique per (method, branch, currency), with `NULLS NOT DISTINCT`.
    - **Selection.** A payment drafted with a method takes the row for its document's branch and currency, else the row for its currency without a branch, else none. The money account then gives the payment type: `cash_*` or `bank_*` ([ADR-0048](0048-cash-bank-receivables-payables.md) rule 3).
    - **Kind check.** A `cash` method maps to a `cash` money account, and every other method to a `bank` money account. An `offset` method has no row. A mismatch is refused with `payment_method_money_account_mismatch`.
    - **Why `cash` owns it.** `cash` is layer 4 and may reference `master_data`. The reverse would make the CRM-only profile depend on `cash`.
17. The kind only suggests. The payment document type and its line still decide `evidence_method`, and [ADR-0048](0048-cash-bank-receivables-payables.md) rule 18 is unchanged.
    - **Suggestions:** `cash` suggests `cash`. `bank_transfer`, `cheque`, `direct_debit` and `e_wallet` suggest `bank_transfer`. `card` suggests `card`. `offset` makes the cash agent propose a partner netting (ADR-0048 rule 10) instead of a payment. `cash_on_delivery` and `other` suggest nothing.
    - **Matching.** The deterministic matching cascade (ADR-0048 rule 9) does not read the method. The cash agent may cite it in an explanation.

**Incoterms**

18. `incoterm` is an installation reference catalog owned by `master_data`:
    - **Source.** It is loaded from [incoterms.csv](../catalogs/incoterms.csv). It has no `company_id` and no row-level security, like `currency` ([ADR-0045](0045-master-data-and-price-lists.md) rules 1, 14).
    - **Key.** Its key is the natural `code`, like `currency`'s, an exception to [ADR-0006](0006-id-and-numeric-model.md) rule 1 that a note there records. The three-letter codes are a stable published list, also UN/ECE Recommendation 5. Documents therefore carry `incoterm_code`, as they carry `currency`.
    - **Columns:** `code`, `version` (2020), `name`, `transport_scope` (`any` or `sea_inland_waterway`), `is_carriage_paid_by_seller`, `is_insurance_paid_by_seller`, `is_import_cleared_by_seller`, `risk_transfer_point` (text), `is_active` and `recorded_at`.
    - **Boolean names.** The decision's names (`seller_pays_main_carriage` and so on) take ADR-0004 rule 13's `is_` form.
    - **Rows.** Eleven: EXW, FCA, CPT, CIP, DAP, DPU, DDP, FAS, FOB, CFR, CIF. A later edition retires rows by `is_active`, and old documents keep theirs.
19. Documents:
    - **Which.** `quotation`, `sales_order`, `delivery` and `sales_invoice` on the sales side; `purchase_order`, `goods_receipt` and `purchase_invoice` on the purchase side.
    - **Fields.** They carry `incoterm_code` and `incoterm_place`, the named place. A place requires a code.
    - **Defaults and copying.** The profiles carry the defaults, and documents copy them as in rule 15.
    - **Print.** Prints show "code place Incoterms version".
20. The effect is advisory only:
    - **Expected costs.** When a purchase's Incoterm leaves the main carriage or insurance to the buyer, the query `ListExpectedLandedCost` (`inventory`) lists its goods receipts that have no `freight` or `insurance` landed cost line ([ADR-0021](0021-landed-cost.md) rule 1). The purchase agent and the close task of ADR-0021 rule 14 show this list. It is not a check result, so it forces no plan review (ADR-0067 rule 12).
    - **Ownership.** [ADR-0030](0030-commercial-seams-and-imports.md) rule 8 reserves the owner axis but has no ownership-transfer default, so nothing reads the Incoterm there now. Ownership of goods in transit from the shipping point, when it is designed, takes the Incoterm as its input.
    - **Nothing else.** No posting rule, check result, tax rule or policy condition reads an Incoterm.

**Delivery methods**

21. `delivery_method` (company data, `master_data`, effect class `master_data_change`, change-tracked):
    - **Fields:** `code`, `name`, `kind` (`own_fleet`, `carrier`, `courier`, `customer_pickup` or `supplier_delivery`), `carrier_partner_id`, `tracking_url_template`, `is_active` and `recorded_at`.
    - **Carrier.** `carrier_partner_id` is set exactly for `carrier` and `courier`. The partner holds the active `supplier` role ([ADR-0019](0019-partners-and-crm-foundation.md) rule 2), otherwise `partner_role_missing`.
    - **Tracking.** `tracking_url_template` is an `https` URL that contains `{tracking_number}`.
22. Use:
    - **Defaults.** `customer_profile` and `supplier_profile` carry `delivery_method_id`, and `sales_order` and `purchase_order` copy it.
    - **Deliveries and receipts.** `delivery` and `goods_receipt` carry `delivery_method_id`, `carrier_partner_id`, `tracking_number` and `vehicle_registration`. The carrier is copied from the method and changeable until posting, with the same role check. Like all content, the fields are fixed at posting (ADR-0009 rule 14).
    - **The tracking link** is computed by putting the URL-encoded number into the template, and is never stored.
    - **Freight.** Freight charged to the customer stays a service-item line. There is no rate shopping and no carrier API in Phase 1. Carrier integration is a later item on the `integrations` queue (backlog).

    Note ([ADR-0074](0074-core-data-structure-additions.md), proposed 2026-11-19): the delivery's address is its ship-to party (`ship_to_partner_id`, `ship_to_name`, `ship_to_address_id`, `ship_to_address`), which replaces the interim `delivery_address` and defaults from the customer's `partner_relationship` rows (ADR-0074 rules 1 to 3).

**Commands, catalogs and checks**

23. Commands and queries (all `master_data_change`; agents reach them through change proposals):

    | Command or query | Module | Leaf | Notes |
    | --- | --- | --- | --- |
    | `CreateSite`, `UpdateSite` | `master_data` | `site` | Rules 1–3 |
    | `CreatePaymentMethod`, `UpdatePaymentMethod` | `master_data` | `payment_method` | Rule 15 |
    | `CreateDeliveryMethod`, `UpdateDeliveryMethod` | `master_data` | `delivery_method` | Rule 21 |
    | `SetPaymentMethodMoneyAccount`, `DeletePaymentMethodMoneyAccount` | `cash` | `payment_method_money_account` | Rule 16 |
    | `CreateResourceGroup`, `UpdateResourceGroup` | `production` | `resource_group` | Members are set by `UpdateWorkCenter` (rule 12) |
    | `ListSite`, `ListPaymentMethod`, `ListDeliveryMethod`, `ListIncoterm`, `ListResourceGroup` | owners above | as above | Queries |
    | `ListExpectedLandedCost` | `inventory` | `warehouse` | Rule 20 |

24. Errors (DS-04):
    - **Validation:** `site_required`, `site_branch_mismatch`, `resource_group_site_mismatch`, `resource_group_activity_mismatch` and `payment_method_money_account_mismatch`.
    - **Precondition:** `site_in_use` and `warehouse_site_fixed`.
    - **No settings.** This ADR adds no setting. The preset item of rule 7 is a record default.
25. Catalogs and DDL:
    - **Authorization leaves:** `site` (under `organization`), `payment_method`, `delivery_method`, `payment_method_money_account` (under `money_account`) and `resource_group` (under `production_structure`). Levels inherit from the parents, so no role-template rows are added.
    - **Analysis dimensions:** `site`, and `payment_method` on invoice lines.
    - **Catalog files:** a new [incoterms.csv](../catalogs/incoterms.csv), and two `record_default` rows in [setting-presets.csv](../catalogs/setting-presets.csv).
    - **DDL:** [DS-20-master-data.sql](../design/DS-20-master-data.sql) (`site`, `payment_method`, `incoterm`, `delivery_method`, and the warehouse, company and profile columns); [DS-22-09-42-commercial-inventory.sql](../design/DS-22-09-42-commercial-inventory.sql) (document headers, `material_document_line`, `preliminary_price`); [DS-05-platform.sql](../design/DS-05-platform.sql) (`payment_method_money_account`, `payment.payment_method_id`); [DS-43-54-planning-production.sql](../design/DS-43-54-planning-production.sql) (`resource_group`, `work_center.resource_group_id`).

## Context

- **The ask.** The author asked for an assessment of a factory level, with SAP as the reference, and for payment methods, Incoterms, delivery methods and resource groups from the start. The chief architect decided all five on 2026-11-17. This ADR writes them up and fills in their open details.
- **The gap a site closes.** ADR-0020 rule 2 offers valuation per company or per physical warehouse, and ADR-0033 used the production warehouse as the plant. A factory with several warehouses then gets either one average per warehouse, with a valuation event on every internal move, or one average for the whole company, which cannot keep two factories apart.
- **Practice.**
  - SAP values, plans and produces per plant, and its storage locations below the plant hold quantities only.
  - Dynamics 365 has sites above warehouses for the same reason.
  - SAP Business One and Odoo have no such level, so their users model multi-warehouse factories by hand.
  - Payment terms and payment methods are separate master data in SAP and Dynamics 365, and so are shipping conditions and Incoterms.
- **Constraints.**
  - Accepted ADRs change only by notes at rule ends.
  - The CRM-only deployment profile (decided 2026-11-17) forbids `crm` and the commercial master data from depending on `ledger`, `cash`, `inventory`, `tax` or `production`.
  - Settings and presets follow ADR-0063 and ADR-0067.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| `site` between company and warehouse, with valuation level `site` (chosen) | One average per factory; two factories apart; matches SAP and Dynamics 365 | A new level, hidden while there is one site |
| Keep the production warehouse as plant | No change | Forces one warehouse per factory, or per-warehouse averages |
| Area recorded as `valuation_site_id` next to `valuation_warehouse_id` (chosen) | Additive; typed keys; ADR-0020 text stays true | Two nullable columns, keyed as a pair |
| Generalize `valuation_warehouse_id` | One column | A site is not a warehouse; needs a representative warehouse |
| `valuation_area` table with `valuation_area_id` | One non-null key | A synchronized table; renames every reference |
| `work_center.site_id` | Direct filter | Two sources of truth with `production_warehouse_id` |
| `site_id` on `journal_line` | Site P&L without a warehouse | A new dimension for a need nobody has yet |
| Money-account default on `payment_method` (in `master_data`) | One table | `master_data` would depend on `cash`, breaking the CRM-only profile |
| Money-account default in `cash`, per method, branch and currency (chosen) | Profile kept; multi-currency defaults | One more small table |
| Incoterms as company data | Companies could edit them | They are a published standard; editing invites errors |
| Incoterms feeding postings or ownership | Automation | Accounting effect of a trade term is a legal reading; advisory first |
| Resource group with its own capacity | Pooled planning | Duplicates `capacity_units`; groups sum their members instead |

## Constraints that come with the decision

- **CRM-only profile.** `site`, `payment_method`, `delivery_method` and `incoterm` reference only `master_data` tables. The layer contract of ADR-0022 rule 2 already keeps `master_data` from importing layer-4 modules.
- **One source each.** The site of a work center or a transit warehouse is derived, never stored. Valuation columns are set only by the stock lock helper.
- **Advisory fields.** No posting, tax or policy code reads `payment_method.kind`, `incoterm_code` or `delivery_method.kind`. A CI grep keeps those reads out of `ledger`, `tax` and `policy`.
- **Small-model friendly.** Each table is plain company data with `code`, `name`, `kind` and `is_active`. Every check is one function or one constraint.

## Revisit when

- A customer needs a site P&L without warehouses, or record scope by site in role assignments (ADR-0017 rule 9).
- Pooled planning per site is wanted (rule 11's open question), or named individual resources are needed (rule 14).
- ICC publishes a new Incoterms edition. The key then becomes (`code`, `version`), or documents gain the version.
- Tracking numbers regularly arrive after posting. They would then go to a late-data table (ADR-0009 rule 14).
- A carrier integration is scheduled (backlog).

## Documents updated

- **ADRs** (notes tagged "ADR-0068, proposed 2026-11-17"):
  - [ADR-0015](0015-account-determination.md) rule 8;
  - [ADR-0019](0019-partners-and-crm-foundation.md) rule 3;
  - [ADR-0020](0020-inventory-and-costing-model.md) rules 1, 2, 3, 11;
  - [ADR-0021](0021-landed-cost.md) rule 14;
  - [ADR-0023](0023-warehouse-management.md) rule 2;
  - [ADR-0024](0024-planning.md) rule 3;
  - [ADR-0030](0030-commercial-seams-and-imports.md) rule 8;
  - [ADR-0033](0033-production-master-data.md) rules 11, 12;
  - [ADR-0034](0034-production-orders-and-shop-floor.md) rules 3, 8;
  - [ADR-0036](0036-multi-level-mrp.md) rules 11, 12;
  - [ADR-0045](0045-master-data-and-price-lists.md) rules 1, 14;
  - [ADR-0047](0047-commercial-documents-and-pricing.md) rule 2;
  - [ADR-0048](0048-cash-bank-receivables-payables.md) rule 3;
  - [ADR-0060](0060-agent-assisted-reporting-and-analysis.md) rule 34;
  - [ADR-0006](0006-id-and-numeric-model.md) rule 1;
  - [ADR-0067](0067-quickflows-operating-presets.md) rule 6, proposed, whose preset table gains the row directly.
- **Catalogs:**
  - [incoterms.csv](../catalogs/incoterms.csv) (new);
  - [authorization-areas.csv](../catalogs/authorization-areas.csv), [analysis-dimensions.csv](../catalogs/analysis-dimensions.csv) and [setting-presets.csv](../catalogs/setting-presets.csv);
  - [invariants.csv](../catalogs/invariants.csv) and [edge-cases.csv](../catalogs/edge-cases.csv);
  - the [catalogs README](../catalogs/README.md).
- **Design files:**
  - DS-20, DS-22-09-42, DS-05 and DS-43-54 (rule 25);
  - [DS-04-command-envelope.md](../design/DS-04-command-envelope.md) (errors);
  - [backlog.md](../design/backlog.md) (carrier integration).
- **Glossary:** rows for site, payment method, payment method money account, Incoterm, delivery method and resource group, in [00-reading-guide.md](../spec/00-reading-guide.md); the change to the existing valuation area row is left to the author (open questions).
- **The lab:** the site valuation lab is not written yet (recorded in [open-questions.md](../open-questions.md), S1 review section). It will check:
  - a transfer inside one site is value-neutral at level `site`;
  - the exact solve runs over sites;
  - INV-810. (review note, 2026-11-21)
- **Open questions:** site-level pooled planning; named individual resources.
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md).

## Edge cases and invariants

**Invariants** (DS-16; block INV-810 to INV-819, INV-810 to INV-812 taken):

- **INV-810** `valuation_area_matches_level` (area `inventory`, first step 3): every `material_document_line` and `preliminary_price` row has both valuation columns null at level `company`; at level `site`, only `valuation_site_id`, equal to the site of the line's warehouse (rule 2); and at level `warehouse`, only `valuation_warehouse_id`, equal to the line's physical warehouse or its attachment.
- **INV-811** `resource_group_members_consistent` (area `production`, first step: the production core step): the active members of a resource group lie in one site and record equal sets of activity types.
- **INV-812** `site_branch_consistent` (area `master_data`, first step 2): every physical warehouse has a site, and its branch equals its site's branch whenever the site has one. No transit or goods-sent warehouse has a site.

**Edge cases** (DS-17; block EC-260 to EC-269, EC-260 to EC-264 taken):

- **EC-260** `site_internal_transfer_neutral`: at level `site`, a transfer from the raw-materials warehouse to the production warehouse of one site changes no area value after costing, while a transfer to a second site moves at the issuing site's average.
- **EC-261** `second_site_requires_choice`: a company with one site creates a warehouse without naming the site. A second site is then created, and a warehouse created without a site is refused with `site_required`. Changing the site of a warehouse with postings is refused with `warehouse_site_fixed`.
- **EC-262** `resource_group_move_and_cost`: an unconfirmed operation moves by change order to another member of its group. Its confirmation is costed at the target's rates, and moving it again after confirmation is refused.
- **EC-263** `payment_method_default_money_account`: a USD sales invoice with method `bank_transfer` drafts a bank receipt on the USD account of the invoice's branch. With method `cash`, it drafts a cash receipt.
- **EC-264** `carrier_on_delivery`: a delivery copies the carrier of its order's `carrier` method, changes it before posting, and shows the tracking link. A carrier without the supplier role is refused with `partner_role_missing`.
