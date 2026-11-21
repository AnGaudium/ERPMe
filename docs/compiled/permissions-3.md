Module: permissions    Chunk: 3 of 4    Source ADRs: ADR-0054
Build step(s): 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `permissions` compiled spec, chunk 3: roles, role templates, assignments, owner scope, segregation rules and checks

## Purpose

This chunk states the part of `permissions` law on: company roles and the commands that change them, the seeded job-role templates, role assignments with record scope and owner scope, how the scopes combine, the rights of agents and integrations, the segregation rule catalog, the check on every change of rights and the check on one document. Users, sessions, the area tree, levels and the expansion of a role into permissions are in the earlier chunks; the small-company mode, delegations and the later amendments are in the last chunk. `permissions` holds no country-specific rule.

## Entities and tables

DDL: `docs/design/DS-15-access.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `role` | A company's role, blank or copied from a template (R401) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) unique | `company` | `permissions` |
| `role_assignment` | A role given to a user or an integration client for a period, with owner scopes and field classes (R430) | `id`; (`company_id`, `id`) unique | `company`, `role` | `permissions` |
| `role_assignment_scope` | One branch or one warehouse of an assignment's record scope (R431) | `id` | `role_assignment` | `permissions` |
| `company_segregation_rule` | Enablement of one row of `segregation-rules.csv` for a company (R472) | `id`; (`company_id`, `rule_code`) unique | `company` | `permissions` |

Reads: `role_level`, `role_permission`, `role_permission_hold`, `user_account`, `user_invitation`, `integration_client`, `delegation` (`permissions`, other chunks); `branch`, `warehouse`, `company`, `department`, `team`, `employee_profile` (`master_data`); `document`; `audit_record`; `work_item`; `open_item`; `agent_type`; the catalogs `authorization-areas.csv`, `authorization-verb-levels.csv`, `work-item-kinds.csv`.

## Commands and queries

Authorization leaves (catalog `authorization-areas.csv`, under `administration`): `role` (roles and assignments) and `segregation_rule` (segregation rules, conflicts, exceptions, reviews). The level of a verb is the catalog's (`Create`, `Update`: `edit`; `Enable`, `Disable`: `full`; `List`: `read`).

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateRole` | `human_only`, `master_data_change`; leaf `role` | blank, or a template to copy | Writes a `role` (R402-R404) | not stated | `grant_exceeds_own_rights` |
| `UpdateRole` | `human_only`, `master_data_change`; leaf `role` | name, levels, flags | Changes the role; its plan lists the permissions gained and lost; checked for every holder (R403, R480) | not stated | `grant_exceeds_own_rights`, `segregation_conflict` |
| `CreateRoleAssignment` | leaf `role`; nobody assigns to themselves | role, principal, owner scopes, field classes, validity, record scope | Writes `role_assignment` and `role_assignment_scope` rows (R430-R435) | not stated | `record_not_found`, `grant_exceeds_own_rights`, `role_assignment_invalid`, `segregation_conflict` |
| `UpdateRoleAssignment` | leaf `role` | not stated (an assignment ends by setting `valid_to`) | Changes the assignment (R432-R434) | not stated | `record_not_found`, `grant_exceeds_own_rights`, `last_owner_required`, `role_assignment_invalid`, `segregation_conflict` |
| `EnableSegregationRule` | `human_only`; leaf `segregation_rule` | rule code | Sets `is_enabled` in `company_segregation_rule`; checked for every user (R472, R480) | not stated | `segregation_conflict` |
| `DisableSegregationRule` | `human_only`; leaf `segregation_rule` | rule code | Clears `is_enabled` in `company_segregation_rule` (R472) | not stated | not stated |
| `ListSegregationConflict` | query, for owners and auditors; leaf `segregation_rule` | not stated | Lists the current conflicts per user (R484) | none | not stated |

Check result of the change-of-rights check in mode `warn`: `segregation_conflict_found` (R482). The dispatcher refuses a command on a document with `segregation_of_duties` (R490), a command outside the scope with `record_not_found` (R451) and an aggregating query without owner scope `branch` or `company` with `permission_denied` (R454); `EvaluateAnalysisPlan` (`query`) answers `analysis_not_permitted` (R456). Contract functions named by the rules, not registered commands: the organization resolver (R441), the related-documents function and the document-actors function (R490).

## Rules

### Roles

R401. Roles are company data in `role`: `code`, `name`, `template_code`, `basis`, `is_totp_required`, the suggested owner scopes (`suggested_owner_scope_read`, `suggested_owner_scope_edit`) and `is_active`.
Source: ADR-0054.R10

R402. `CreateRole` creates a role blank or copied from a template; `UpdateRole` changes its name, levels and flags. Both are `human_only`, `master_data_change`, change-tracked (ADR-0038.R3) and on no agent tool list.
Source: ADR-0054.R10

R403. No escalation: a person may create or change a role only when they hold every permission the role would gain, with a company-wide assignment; otherwise `grant_exceeds_own_rights`. The plan of `UpdateRole` lists the permissions gained and lost, so the role editor shows the effect before it is executed.
Source: ADR-0054.R10

R404. A copied template row keeps the template's basis; rows the company changes get the basis `company_decision` (ADR-0016.R12).
Source: ADR-0054.R10

R405. `template_code` stays when the company renames or edits the role. Through it the core finds "the owner role" or "the accountant role" (R425).
Source: ADR-0054.R10

### Role templates

R410. The core seeds the job-role templates `owner`, `chief_accountant`, `accountant`, `cashier`, `sales_clerk`, `sales_manager`, `buyer`, `purchasing_manager`, `warehouse_keeper`, `production_planner`, `shop_floor_lead`, `auditor`, `it_administrator` and `quality_inspector`, in the catalogs `role-templates.csv` (attributes) and `role-template-levels.csv` (levels per node). They stand in place of the list of ADR-0017.R5: `sales` is `sales_clerk` and `sales_manager`, `purchasing` is `buyer` and `purchasing_manager`, and `viewer` is `auditor`.
Source: ADR-0054.R11, ADR-0054.R11.N8

R411. Each template in short, then its suggested owner scope (read / edit):
- `owner`: `full` and approve everywhere (ADR-0017.R6 interim); company / company.
- `chief_accountant`: Finance and Banking `full`, with `cash_payment` and `bank_payment` at `edit` with approval and `partner_bank_account` at `read`; supplier invoices and sales corrections `full`; files statutory reports and tax returns; other areas `read`; policy administration; approves; company / company.
- `accountant`: Finance and Banking `post`, with `cash_payment` and `bank_payment` at `edit` with approval; posting periods and the chart `read`; `partner` `read`; invoices `post`; approves; company / company.
- `cashier`: cash documents and counts `post`; `bank_payment` `post`, other bank documents `read`; no reports; company / own.
- `sales_clerk`: quotations, orders and sales corrections `edit`; customers `edit`; `price_list` `edit`; own / own.
- `sales_manager`: Sales `post` and approve; `price_list` `read`; department / department.
- `buyer`: requests, orders and supplier invoices `edit`; suppliers `edit`; planning `edit`; `service_receipt` `post`; own / own.
- `purchasing_manager`: Purchasing `post` and approve, with `purchase_invoice` at `edit` with approval; planning `post`; department / department.
- `warehouse_keeper`: Inventory `post`; production issues and receipts `post`; orders `read`; `service_receipt` `post`; branch / branch.
- `production_planner`: Production `post`, with `can_approve` on `production_order`; Planning `full`; production structures `edit`; company / company.
- `shop_floor_lead`: confirmations, production issues and receipts `post`; production orders `read` (the shop-floor role of ADR-0034.R18); branch / branch.
- `auditor`: `read` everywhere, audit records included; nothing else; company / own.
- `it_administrator`: users, roles, assignments, delegations, organization and settings `full`; policy and segregation rules `read`; no Finance or Banking, no data import, no agent run bodies; company / company.
- `quality_inspector`: quality `post` with approval; inspection plans `edit`; inventory, products and production orders `read`; delegation of its own approvals `edit` (ADR-0070.R13); branch / branch.
Source: ADR-0054.R11, ADR-0054.R11.N1, ADR-0054.R11.N3, ADR-0054.R11.N8

R412. Approvers: the templates `owner`, `chief_accountant`, `accountant`, `sales_manager`, `purchasing_manager` and `production_planner` have `can_approve` in their areas. Each of them also has `edit` on `delegation`, so that a person can delegate their own approvals (ADR-0054.R21). `delegate_for_others` (`full` on `delegation`) stays with `owner` and `it_administrator`, who may delegate only what they hold themselves. ADR-0055's seeded stages name `accountant`, `chief_accountant` and `owner`; `production_planner` is a member of pool `mo`'s `standard` stage (interim, flagged for the author).
Source: ADR-0054.R11, ADR-0054.R11.N1, ADR-0054.R11.N3

R413. Every template except `auditor` has `edit` on `general_access`, which holds `ListAllowedCommand` (ADR-0040.R8), `CreateAttachment`, `CreateListExport` and `GetApprovalProgress`, each checked against its subject's or query's own permission (ADR-0054.R24.N1); `auditor` has `read` on it. Every template gets `edit` on `work_queue`.
Source: ADR-0054.R11, ADR-0054.R11.N2

R414. CRM levels: `sales_clerk` and `buyer` edit interactions and outbound drafts, and `sales_clerk` complaints; `sales_manager` and `purchasing_manager` post and approve outbound messages, and `sales_manager` closes complaints; `chief_accountant` posts and approves outbound messages (dunning reminders, ADR-0048.R17), `accountant` drafts them; `it_administrator` has `mailbox` `full`; `owner` has CRM `full`, `data_protection` included; `auditor` reads CRM.
Source: ADR-0054.R11

R415. Only `owner` holds `read_agent_run_bodies`: every other template sets `agent_run_bodies` to `none`, as ADR-0050.R20 intends. Only `owner` holds `UpdatePrintProfile` (ADR-0049.R26): every other template sets `print_profile` to `none`.
Source: ADR-0054.R11

R416. The `cashier` gets no report leaf. ADR-0049's book queries (`ListBookRow`, `RenderReport`) take the report code as a parameter, so a leaf cannot narrow them to the cash and bank books: `read` on `report_finance` would show every book and statement. The cashier sees cash through the cash documents and counts they hold; the cash book itself is read by an accountant. Revisit, with a report-code dimension, if cashiers need the book itself.
Source: ADR-0054.R11

R417. The `it_administrator` can assign only roles whose permissions they hold (R403; ADR-0017.R6), so finance roles are assigned by an owner. The template has no `data_import`, since imports post (ADR-0044), and no `start_agent` for any agent type: `role-template-levels.csv` sets each agent type leaf to `none` for it, because an IT administrator configures and operates the system but starts no business agent.
Source: ADR-0054.R11, ADR-0054.R11.N9

R418. The templates other than `owner` hold no both sides of a seeded segregation rule (R471). `owner` keeps every permission (R434), so its conflicts remain and the per-document check of R490 is its control. Payment reversals (`full`) stay with `owner`. `change_proposal` is on no side of a seeded segregation rule. Lab check `t12_access.py` checks that no other template holds both sides of a seeded rule.
Source: ADR-0054.R11, ADR-0054.R11.N3, ADR-0054.R11.N4, ADR-0054.R17.N1

R419. The levels that keep the templates free of conflicts, in `role-template-levels.csv` and `role-templates.csv`, with the seeded rule each avoids (interim, flagged with the template contents; open question):
- `accountant`: `partner` `read` (`partner_vs_purchase_invoice`); `cash_payment` and `bank_payment` `edit` with approval (`purchase_invoice_vs_payment`): an accountant drafts, submits and approves payments and does not post them.
- `chief_accountant`: `cash_payment` and `bank_payment` `edit` with approval (`purchase_invoice_vs_payment`); `partner_bank_account` `read` (`bank_account_vs_payment`), so partner bank accounts are the owner's by default, and a company may give them to a role without payment rights.
- `cashier`: `bank_payment` `post`: the cashier posts the payments accountants prepare (in Phase 1 a bank payment records a transfer made outside NativeFlows, ADR-0048.R3).
- `sales_manager`: `price_list` `read` (`price_list_vs_sales_approval`), and `sales_clerk`: `price_list` `edit`: price lists are maintained by the sales clerk, who approves nothing, while prices outside the list or below cost still reach the sales manager through policy (ADR-0043.R3).
- `purchasing_manager`: `purchase_invoice` `edit` with approval (`partner_vs_purchase_invoice`): accountants post supplier invoices.
Source: ADR-0054.R11.N3

R420. `change_proposal` levels: `sales_manager`, `purchasing_manager`, `production_planner` and `chief_accountant` have `edit` with `can_approve`, so they submit and approve change proposals (ADR-0055.R5.N1); for the chief accountant the approval flag Master data gave her stays. `accountant`, `sales_clerk` and `buyer` have `edit` without the approval flag, so the people who handle agent proposals in their area (bank matching rules, customer onboarding, purchase mapping) can submit them; approval stays with the `general` pool.
Source: ADR-0054.R11.N3, ADR-0054.R11.N4, ADR-0054.R11.N7

R421. Seed of `start_agent:<agent_type>`, at `edit` on the agent type's leaf, and with it the recommended workflow owner of each agent type (ADR-0050.R14), who is a holder of the same template: `quotation` and `customer_onboarding`: `sales_clerk`; `purchase_invoice` and `bank_matching`: `accountant`; `planning`: `production_planner`; `data_migration`: `owner`. `owner` holds every agent type through Administration `full`; `it_administrator` holds none (R417); `sales_manager` and `chief_accountant` do not hold these capabilities. A workflow owner must not be a planned approver of the agent's drafts, since the hard floor keeps that person from approving them: the people who approve quotations, onboarding proposals and mismatched supplier invoices are not their writers through a run. Lab check `t12_access.py` C28.
Source: ADR-0054.R11.N2, ADR-0054.R11.N5, ADR-0054.R11.N9

R422. Unit maintenance is on its own leaves under `product` (ADR-0056.R20 note): `product_unit` (`CreateProductUom`, `UpdateProductUom`, `CreateUom`, `UpdateUom`) and, below it, `uom_alias` (`CreateUomAlias`, `UpdateUomAlias`). In `role-template-levels.csv`, `purchasing_manager`, `chief_accountant` and `warehouse_keeper` have `product_unit` `edit`, which covers `uom_alias`; `accountant` has `uom_alias` `edit`, so the purchase invoice agent's workflow owner maintains unit aliases but not units or conversions. The rows carry no approval flag: no document type lies below these leaves, so the flag would add no command (ADR-0054.R9). The purchasing manager and the chief accountant approve change proposals and hold the target commands, so either can approve a unit or alias proposal (ADR-0055.R7; ADR-0043.R12); the accountant submits such proposals and approves none; the warehouse keeper approves nothing. No seeded segregation rule names these commands. `owner` keeps them through Master data `full`, and `auditor` reads. Lab check `t12_access.py` C28c and G53. Interim, flagged with the template contents (open question).
Source: ADR-0054.R11.N6

R423. Configuration levels, in `role-template-levels.csv`: `chief_accountant` has `company_setting` `edit`, `configuration` `full` and `automation` `full`; `sales_manager`, `purchasing_manager` and `production_planner` have `configuration` `edit` and `automation` `full`. So drafting a rule or decision table, creating its evidence (`CreateArtifactEvidence`) and submitting its activation (ADR-0058.R24) is open to the owner, the chief accountant and these managers; approving it, which needs `ApproveChangeProposal` and the target `SetArtifactVersionState` (declared minimum `full`), to the owner and the chief accountant. A loosening of a setting on the leaf `policy` (ADR-0063.R3) is submitted by the owner or the chief accountant and approved by the other, since `approver_is_submitter` and condition 5 of ADR-0055.R7 exclude the submitter and the writers. The IT administrator keeps `configuration` `full` without change proposals: it drafts and rolls back, but neither submits nor approves. No segregation rule changes. Lab check `t12_access.py` G54 to G56. Interim, flagged with the template contents (open question).
Source: ADR-0054.R11.N7

R424. The leaf `agent_assistant` holds `start_agent:assistant` at `edit`; the seed gives it to every template with UI access except `it_administrator` and `auditor`, and a company may withdraw it. The leaf `list_variant` under Administration holds `share_list_variant` at `edit`; `owner` and `it_administrator` hold it through Administration `full` (ADR-0077.R10a, ADR-0077.R13; lab check `t12_access.py` C28).
Source: ADR-0054.R11.N10

R425. Owner rules that name a template (ADR-0042.R7) resolve through `role.template_code`, never through role codes or names. `role:<template>` means the holders of the company's active roles with that `template_code`. `company_owner` means the holders of active roles with `template_code` `owner`; if there is none, the holders of a role with every permission of the template `owner` (R434 keeps one). When no active role has the template a `role:<template>` rule names, the item goes to `company_owner`. In `work-item-kinds.csv` the owner rule of the kinds `interaction_unmatched`, `sales_return_due`, `inbound_message_matched` and `complaint_open` is `role:sales_clerk` (ADR-0019.R15, ADR-0051.R30, ADR-0052.R20).
Source: ADR-0054.R11

R426. The template contents are defaults that the author may change (flagged; open question).
Source: ADR-0054.R11

### Role assignments

R430. `role_assignment` is company data and change-tracked. Columns: the role; `principal_kind` (`user` or `integration_client`) with the matching ID (`user_account_id` or `integration_client_id`); `owner_scope_read` and `owner_scope_edit` (users only); `field_classes` (ADR-0017.R10); `valid_from` and `valid_to` (business dates in the company's time zone, inclusive; an empty end is open); `granted_by_user_id`; `user_invitation_id`, the invitation the assignment names (R433, R435).
Source: ADR-0054.R12

R431. The record scope of an assignment is its `role_assignment_scope` rows, each a branch or a warehouse (ADR-0017.R9). None means the whole company.
Source: ADR-0054.R12

R432. The commands are `CreateRoleAssignment` and `UpdateRoleAssignment`. An assignment ends by setting `valid_to`; it is never deleted, so history shows who could do what on any date.
Source: ADR-0054.R12

R433. Only linked users or invitations: for a user not linked to the company (ADR-0054.R3), both commands answer `record_not_found`, unless the assignment names that user's pending or confirmed invitation in the company. So a company that still knows a former user's ID, from history, cannot give them rights again without a new invitation that the person confirms (`INV-231`).
Source: ADR-0054.R12

R434. ADR-0017.R6 holds: nobody assigns a permission they do not hold (`grant_exceeds_own_rights`) or assigns to themselves, and the last user with a role holding every permission of the template `owner` in a company keeps it (`last_owner_required`).
Source: ADR-0054.R12

R435. An assignment is in force when `valid_from` ≤ `clock.today` ≤ `valid_to`, the role and the principal are active, and the assignment is not pending: it names no invitation, or a `confirmed` one (ADR-0054.R3). An assignment naming a `pending` or `canceled` invitation grants nothing and counts nowhere.
Source: ADR-0054.R12

### Owner scope

R440. Owner scope values:
- `own`: documents whose owner employee is the user's employee, or whose creating user is the user;
- `team`: as `own`, plus documents whose owner employee is in one of the user's teams;
- `department`: as `own`, plus documents whose owner employee is under the user (R441);
- `branch`: every document inside the assignment's record scope, which must not be empty;
- `company`: every document of the company; the assignment must have no record scope.
Source: ADR-0054.R13

R441. "Under the user" means: employees of the user's own department; employees of every department in the subtree of a department the user manages; and employees whose chain of managers leads to the user. The organization resolver computes this set from current data on each request, so a transfer takes effect at once.
Source: ADR-0054.R13

R442. Queries, `Approve` and `Reject` use the read scope (`owner_scope_read`). Every other command uses the edit scope (`owner_scope_edit`). The edit scope may not be wider than the read scope: `own` fits under any scope, `team` under `team`, `branch` or `company`, `department` under `department`, `branch` or `company`, and `branch` under `branch` or `company`. Otherwise `role_assignment_invalid`; the database holds the pairs (`INV-221`).
Source: ADR-0054.R13

R443. Only user assignments carry owner scopes. Integration assignments have none; an agent run is bound by its human's owner scope (R460).
Source: ADR-0054.R13

### How the scopes combine

R450. Per assignment the filter is row-level security (company) AND record scope AND owner scope. Across assignments, a row is visible or editable when any assignment that grants the permission allows it (ADR-0017.R6).
Source: ADR-0054.R15

R451. Outside the scope, a command gets `record_not_found`, and a query leaves the row out with `is_scope_filtered: true` (ADR-0017.R9). The read-only layer's views apply the same filters (DS-33).
Source: ADR-0054.R15

R452. Master data is filtered by record scope only; owner scope applies to documents.
Source: ADR-0054.R15

R453. Everything that shows a document's data is filtered by that document's read scope, record and owner scope together, so no side path shows what the document list hides. Each owning ADR carries a note. This covers:
- its journal entry, journal lines and stock movements (ADR-0017.R9);
- work items whose subject is a document, or a line of one: visible only when the caller's read scope reaches the document, besides the conditions of ADR-0042.R10; the visibility function of ADR-0054.R2 applies it;
- the partner timeline: a document entry appears only when the caller's read scope reaches the document; otherwise it is left out with `is_scope_filtered` (ADR-0052.R18);
- audit queries: `ListAuditRecord` and `GetAuditRecord` show a record whose subject is a document only within that document's read scope (ADR-0038.R7);
- open items (`ListOpenItem`, ADR-0026.R15) and the partner statements listed from them: each open item follows its origin document;
- attachments linked to a document, and print files rendered from one: they follow the document (ADR-0038.R14; ADR-0049.R20);
- the live-update header (ADR-0040.R13): it also carries the subject document's `owner_employee_id` and `created_by_user_id`, as IDs, and a header is forwarded only when the session's read scope reaches the document, checked against the same cached assignments and organization set.
Source: ADR-0054.R15

R454. A query that totals over documents without returning them is registered `is_owner_scoped: false` (ADR-0008.R1.N1). This covers reports (DS-26; ADR-0049) and also non-report aggregates such as `GetPartnerExposure` (ADR-0026.R15) and aging totals over open items. It needs an assignment with owner scope `branch` or `company` for its permission; otherwise `permission_denied`. So totals never reveal documents outside a user's owner scope.
Source: ADR-0054.R15

R455. Row-level security stays company-only (ADR-0017.R19). Owner scope and record scope live in the dispatcher and the read-only layer.
Source: ADR-0054.R15

R456. `EvaluateAnalysisPlan` is owner-scoped per fact view: it aggregates only the rows each view's grants reach and flags `is_scope_filtered`, so its totals reveal no document outside the scope. A plan over a fact registered `is_owner_scoped: false` (`system_account_turnover`, `stock_overview`, `production_variance_overview`) needs an assignment with owner scope `branch` or `company`, else `analysis_not_permitted`. Member lookups return only members of a fact's rows within its scope (ADR-0060.R10, ADR-0060.R13, ADR-0060.R14).
Source: ADR-0054.R15.N1

### Agents and integrations

R460. An agent run's rights stay as ADR-0050.R31 states: its agent type's declared permissions intersected with the rights of the human it acts for, re-evaluated at every call. The declared permissions and the fixed tool list (ADR-0017.R11) are one set; the agent type also declares field classes (default none) and no record scope (ADR-0050.R12.N1). Agent types get no role assignments. The human's owner scope binds the run, as their record scope does (ADR-0050.R31.N1).
Source: ADR-0054.R16, ADR-0054.R16.N1

R461. Integrations keep ADR-0017.R13, with roles and record scope and no owner scope.
Source: ADR-0054.R16

R462. No role or level lets an agent approve (ADR-0017.R15), receive a delegation (ADR-0054.R21), or run a `human_only` command.
Source: ADR-0054.R16

### Segregation rules

R470. The catalog `segregation-rules.csv` has the columns `code`, `side_a` and `side_b` (lists of permissions), `document_relation`, `meaning` and `added_in`. Document relations:
- `none`: checked at assignment only;
- `referenced_order`: the side-B document has lines that reference lines of the side-A document;
- `settled_item`: the side-B document settles an open item that the side-A document created;
- `bank_account_used`: the side-B payment uses a partner bank account whose latest change the person wrote or approved.
Source: ADR-0054.R17

R471. Seeded rules, as code: side A; side B; relation:
- `bank_account_vs_payment`: maintain partner bank accounts; post or approve cash and bank payments; `bank_account_used`.
- `purchase_order_vs_goods_receipt`: create, change or approve purchase orders; post goods receipts; `referenced_order`.
- `purchase_invoice_vs_payment`: post or approve supplier invoices; post cash and bank payments; `settled_item`.
- `price_list_vs_sales_approval`: maintain price lists; approve quotations and sales orders; `none`.
- `partner_vs_purchase_invoice`: create or change partners; post supplier invoices; `none`.
- `role_administration_vs_posting`: change roles and assignments; post journal entries, payments and supplier invoices; `none`.
Source: ADR-0054.R17

R472. Company enablement is `company_segregation_rule` (rule code `rule_code`, `is_enabled`, `basis`). Every catalog rule is enabled at company setup. `EnableSegregationRule` and `DisableSegregationRule` are `human_only` and change-tracked.
Source: ADR-0054.R17

R473. Permissions cannot see "below cost", so `price_list_vs_sales_approval` separates maintaining prices from approving sales at all; the below-cost check itself stays a policy condition (ADR-0043.R3). CI checks that every permission in the catalog is registered.
Source: ADR-0054.R17

R474. Assignments of the `owner` template are exempt from the checks that keep mode `block` free of conflicts (R480, R483: the switch to `block`, `EnableSegregationRule` and every rights path; `INV-229`), because that template holds every permission (R434) and would otherwise make `block` impossible in any company. A user whose other assignments hold both sides is not exempt (lab t12, E5b and E5c).
Source: ADR-0054.R17.N2

R475. The exemption of R474 covers assignments only. The owner still meets the per-document check of R490: one person cannot act on both sides of a pair on one document. It never reaches approval eligibility: ADR-0055.R7, condition 7, applies to the owner on each document like anyone else, through the check of R490 for the rules with a document relation (`bank_account_vs_payment`, `purchase_order_vs_goods_receipt`, `purchase_invoice_vs_payment`). The rules with relation `none` (`price_list_vs_sales_approval`, `partner_vs_purchase_invoice`, `role_administration_vs_posting`) are checked at assignment only, for everyone, so they bar no one from approving a given document.
Source: ADR-0054.R17.N2, ADR-0054.R17.N3

### Check on every change of rights

R480. The check runs on every path that changes a person's effective rights: `CreateRoleAssignment`, `UpdateRoleAssignment`, `UpdateRole` (for every holder), `EnableUserAccount`, `CreateDelegation` (the substitute's own rights plus what is lent; approval delegation is the only kind, ADR-0054.R21.N1), `ConfirmUserInvitation` (the pending assignments), `ConfirmRolePermissionHold` (every holder of the role), `EnableSegregationRule` (for every user), and the re-expansion on upgrade (ADR-0054.R9).
Source: ADR-0054.R18

R481. A rule conflicts when the union of a user's permissions from assignments and delegations in force on any common day holds at least one permission of each side.
Source: ADR-0054.R18

R482. The company setting `permissions.segregation_assignment_mode`: `warn` gives the check result `segregation_conflict_found`; `block` gives the error `segregation_conflict`, except on upgrade, where the gain becomes a hold (ADR-0054.R9). Interim default `warn` (flagged), so that small teams can start.
Source: ADR-0054.R18

R483. Switching to `block` is refused with `segregation_conflict` while any current assignment or delegation conflicts, so `block` always starts from a clean state. With every path of R480 checked, no conflict exists while the mode is `block`, assignments of the `owner` template aside (R474; `INV-229`). Settings with the prefix `permissions.` belong to the leaf `segregation_rule` at level `full`, not to `company_setting`.
Source: ADR-0054.R18, ADR-0054.R17.N2

R484. `ListSegregationConflict` lists the current conflicts per user, for owners and auditors.
Source: ADR-0054.R18

### Check on one document

R490. At command time, for rules with a document relation: before a side-B permission runs on a document, the dispatcher asks the related-documents function for the documents linked by the rule's relation, and the document-actors function for who acted on them. If the acting human performed a side-A command on a related document, the command is refused with `segregation_of_duties`, with the rule and the related document in `details`. The same holds the other way round, A after B.
Source: ADR-0054.R19

R491. The acting human is the human actor, or the `on_behalf_of` of a non-human actor, and also the delegator when a substitute acts (ADR-0054.R21).
Source: ADR-0054.R19

R492. The per-document check applies in both assignment modes, and in simulation. ADR-0017.R16 and ADR-0055.R7 are separate and unchanged. The seeded rules `bank_account_vs_payment`, `purchase_invoice_vs_payment` and `purchase_order_vs_goods_receipt` make the minimum cast of a purchase-to-pay run with a mismatched supplier invoice these users: A (an accountant) drafts and posts the invoice; B, an eligible approver of the `po` pool's current stage other than A, who wrote it (ADR-0055.R7), approves it; C (a cashier) posts the payment, because `purchase_invoice_vs_payment` refuses A and B. Whoever last changed the supplier's bank account (by default the owner) may neither post nor approve that payment (`bank_account_vs_payment`); whoever wrote or approved the purchase order may not post its goods receipt (`purchase_order_vs_goods_receipt`), so a warehouse keeper does.
Source: ADR-0054.R19, ADR-0054.R19.N1

## Invariants

| Invariant | Statement | Check point | Protects |
| --- | --- | --- | --- |
| `INV-221` | Every user assignment with owner scope `branch` has a record scope and every one with `company` has none; the edit scope is not wider than the read scope; no other assignment has an owner scope. | day | R440, R442, R443 |
| `INV-229` | While `permissions.segregation_assignment_mode` is `block`, no user's permissions in force on any day, from assignments and delegations other than assignments of the `owner` template, hold both sides of an enabled segregation rule. | day | R474, R480-R483 |

`INV-231` (invitation confirmed before access; source ADR-0054.R3 and ADR-0054.R12) protects R433 and R435; its row is in the chunk that states ADR-0054.R3.

## Edge cases

| Edge case | Name | Case | Outcome |
| --- | --- | --- | --- |
| `EC-110` | `owner_scope_sales_clerk` | A sales clerk with owner scope `own` lists sales orders and sees only their own; their manager with scope `department` sees the department's, including those of a sub-department they manage (R440, R441). | `must_succeed` |
| `EC-111` | `buyer_posts_own_order_receipt` | A user who holds both the buyer and the warehouse keeper role writes a purchase order, then tries to post its goods receipt and is refused; another warehouse keeper posts it (R490). | `must_reject:segregation_of_duties`, then `must_succeed` |

## Settings

None: `settings.csv` holds no row for a key of this chunk. R482 names the company setting `permissions.segregation_assignment_mode` (values `warn` and `block`; interim default `warn`, flagged; leaf `segregation_rule` at level `full`, R483), which is absent from `settings.csv`.

## Conflicts

CONFLICT ADR-0054.R11: its notes add the template `quality_inspector`, change the general-access level and several template levels and replace the bullet on seeded conflicts; R410 to R424 state the result under ADR-0054.R11.N2, ADR-0054.R11.N3 and ADR-0054.R11.N8.
CONFLICT ADR-0054.R11.N2: its seed of `start_agent` for `sales_manager` and `chief_accountant` is replaced by ADR-0054.R11.N5, and the hold of `it_administrator` on every agent type by ADR-0054.R11.N9; R421 states the result.
CONFLICT ADR-0054.R11.N3: for every template except `owner` it replaces the rule's bullet on seeded conflicts and lowers the listed levels; R411, R418 and R419 state ADR-0054.R11.N3.
FALSE-POSITIVE ADR-0054.R11.N4: the word names segregation conflicts of templates; the note adds `change_proposal` levels and contradicts no other source.
CONFLICT ADR-0054.R11.N5: it replaces the agent seed of ADR-0054.R11.N2, and its mark "interim" is dropped because ADR-0054.R11.N9 confirms the rest of the interim seed; R421 states it without the mark.
CONFLICT ADR-0054.R11.N9: `it_administrator` holds no `start_agent`, against ADR-0054.R11.N2 and ADR-0054.R11.N5, which let it keep every agent type; R417 and R421 follow ADR-0054.R11.N9.
CONFLICT ADR-0054.R17.N2: the note on the catalog rule exempts `owner` assignments from the checks of ADR-0054.R18; R474 and R483 state the exemption.
CONFLICT ADR-0054.R18: its sentence that no conflict exists in mode `block` is narrowed by ADR-0054.R17.N2 to assignments other than those of the `owner` template; R483 states it so. Its path "`CreateDelegation` of both kinds" reads as the one kind left by ADR-0054.R21.N1, approval delegation; R480 states it.

## Trace

| Source | Where |
| --- | --- |
| ADR-0054.R10 | R401, R402, R403, R404, R405 |
| ADR-0054.R11 | R410, R411, R412, R413, R414, R415, R416, R417, R418, R425, R426 |
| ADR-0054.R11.N1 | R411, R412 |
| ADR-0054.R11.N2 | R413, R421 |
| ADR-0054.R11.N3 | R411, R412, R418, R419, R420 |
| ADR-0054.R11.N4 | R418, R420 |
| ADR-0054.R11.N5 | R421 |
| ADR-0054.R11.N6 | R422 |
| ADR-0054.R11.N7 | R420, R423 |
| ADR-0054.R11.N8 | R410, R411 |
| ADR-0054.R11.N9 | R417, R421 |
| ADR-0054.R11.N10 | R424 |
| ADR-0054.R12 | R430, R431, R432, R433, R434, R435 |
| ADR-0054.R13 | R440, R441, R442, R443 |
| ADR-0054.R15 | R450, R451, R452, R453, R454, R455 |
| ADR-0054.R15.N1 | R456 |
| ADR-0054.R16 | R460, R461, R462 |
| ADR-0054.R16.N1 | R460 |
| ADR-0054.R17 | R470, R471, R472, R473 |
| ADR-0054.R17.N1 | R418 |
| ADR-0054.R17.N2 | R474, R475, R483 |
| ADR-0054.R17.N3 | R475 |
| ADR-0054.R18 | R480, R481, R482, R483, R484 |
| ADR-0054.R19 | R490, R491, R492 |
| ADR-0054.R19.N1 | R492 |
