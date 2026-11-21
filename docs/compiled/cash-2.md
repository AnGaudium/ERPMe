Module: cash    Chunk: 2 of 2    Source ADRs: ADR-0048, ADR-0051, ADR-0052, ADR-0059, ADR-0063, ADR-0065, ADR-0068
Build step(s): 1, 2, 3, 5, 6    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `cash` compiled spec, chunk 2: close jobs, reversals, dunning, catalog rows, bank matching agent, parameters, matching rules, auto-post, payment-method defaults

## Purpose

`cash` owns money accounts, cash and bank documents, bank statements and their matching, and collections (ADR-0048); it
is a layer 4 module. This chunk states the close jobs, reversals, dunning and the payment block, the catalog rows of
ADR-0048, the bank matching agent and its deterministic follow-up, the cascade's parameters and matching rules, the
auto-post conditions of the bank cascade, and the default money account per payment method. Money accounts, payment
documents, statements and the cascade itself are in chunk 1. Payment methods belong to `master_data`, policy rules to
`policy`, artifact lifecycles to `configuration`; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`. Chunk 1 carries the rows of `money_account`, `payment`, `payment_line`,
`bank_statement` and `bank_statement_line`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `open_item_collection` | Collection data of one open item: dunning level, last reminder, payment block and dispute (R206 to R208). Change-tracked, so `INV-98` reads the block at a posting. | `id`; unique `open_item_id` | `open_item` | `cash` |
| `payment_method_money_account` | The default money account per payment method, branch and currency (R256). Company data, change-tracked. | `id`; unique (`company_id`, `payment_method_id`, `branch_id`, `currency`) with `NULLS NOT DISTINCT` | `payment_method`, `money_account` | `cash` |

Defined by rule, without DDL: `partner_collection` (R206; DS-25), `prepaid_schedule` (R203) and `bank_matching_rule`
with its versions (ADR-0048.R9; R241, R244). `money_account_balance` is listed in chunk 1.

Reads: `open_item`, `payment_method`, `customer_profile`, `supplier_profile`, `branch`, `document`, `agent_run`, `policy_rule_version`, `parameter_set_version`, `journal_line`, `partner`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `RunBadDebtProvision` (job) | `system`; the document type's leaf is `provision_entry` (under `finance`); verb level not stated | Period | Posts a `provision_entry` (R202) | not stated | not stated |
| `RunPrepaidAmortization` (job) | `system`; the document type's leaf is `prepaid_amortization` (under `finance`, with prepaid schedules); verb level not stated | Period | Posts a `prepaid_amortization` per schedule (R204) | not stated | not stated |
| `RunDunning` | Leaf `dunning` (under `banking`); verb level not stated | Date | Proposes reminder drafts per customer (R211) | A completion event (name not stated) that carries per customer the level and the open item IDs (R212) | not stated |
| `RecordBankLineSuggestion` | The bank matching agent run, step `bank_matching.suggest`; effect class `other`, `is_draft_only`; area not stated | Tokens, name, purpose and run of one statement line | Stores them on the line, all `is_untrusted` (R223, R224) | `BankLineSuggestionRecorded` (IDs only) | not stated |
| `GetAutoPostShadowEvaluation` (query) | not stated | Document types, score floor, amount maximum, date range | Returns the shadow evidence of R227 under one `parameters_hash` (R228, R236) | None | not stated |
| `CreateBankMatchingRuleVersion` | The `cash` consumer of R230, or a person holding `edit` on the leaf `bank_statement`; draft-only; on no agent tool list | A rule version | Writes a `bank_matching_rule` version in `draft` (R244) | not stated | not stated |
| `CreateBankMatchingRule` | As `CreateBankMatchingRuleVersion`, in the same batch; effect class `master_data_change` | The rule's identity and owner | Creates the rule's identity (R244) | not stated | not stated |
| `SetPaymentMethodMoneyAccount`, `DeletePaymentMethodMoneyAccount` | Leaf `payment_method_money_account` (under `money_account`; levels inherit from the parent); effect class `master_data_change`; agents reach them through change proposals (ADR-0068.R23, ADR-0068.R25) | Method, branch, currency, money account | Sets or deletes the default row (R256, R258) | not stated | `payment_method_money_account_mismatch` |

Not registered commands of `cash`, besides the pure function `cash.match_bank_line` and the gateway checkers that
chunk 1 lists (parameters R234, checkers R253): the consumers of `crm`'s complaint
events (R209), of `BankLineSuggestionRecorded` (R225), of posted purchase invoices and payments with lines on
`prepaid_expense` (R203) and of posted matches that carried a `stable_payer_token` (R230); the evidence hook that
`policy` declares and `cash` registers (R227); the hook `auto_post_eligibility` (R237); the trigger
`trg_payment_line_payment_block` (R208).

Commands of other modules that these rules use: `EnablePolicyRule` (`policy`; `shadow_evidence_insufficient`,
`auto_post_evidence_outdated`), `SetArtifactVersionState` (`configuration`), `ListComplaint` (`crm`).

Codes bound to no named command of this chunk: `open_item_payment_blocked` (a settle line and `Post`, R208); the codes
of R216.

## Rules

### Close jobs

R201. `RunBadDebtProvision` and `RunPrepaidAmortization` are close jobs (ADR-0027.R8; ADR-0012.R13). Both are system jobs that post ordinary documents as `system`. The documents are reversible, and the jobs are idempotent per period.
Source: ADR-0048.R14

R202. `RunBadDebtProvision` (period) considers open `invoice` items on receivable accounts with control kind `receivable`, excluding employee advances, at their open company-currency amounts at the period end. Each item gets a percentage by days overdue from the regime setting `cash.bad_debt_provision.buckets`; the bands are flagged content of the localization package, `unverified`. The partner's open credits and advances are not netted (flagged). Items in dispute are listed for the accountant rather than skipped (flagged). The job posts the difference between the required allowance and the current balance of `bad_debt_allowance` as a `provision_entry`: an increase to `bad_debt_expense`, or a release.
Source: ADR-0048.R14

R203. A `prepaid_schedule` (journal line on `prepaid_expense`, total, first period, number of periods, target account, cost center) is created by a person. A `cash` consumer of posted purchase invoices and payments with lines on `prepaid_expense` drafts one for the person to confirm.
Source: ADR-0048.R14

R204. `RunPrepaidAmortization` (period) posts each period's share of a `prepaid_schedule` straight-line, the last period taking the rest, as a `prepaid_amortization`. The account comes from the schedule (ADR-0015.R5).
Source: ADR-0048.R14

### Reversals

R205. A payment, netting, write-off or settlement document may be reversed while no document that is not reversed or canceled refers to it (ADR-0009.R18, ADR-0009.R19). The reversal mirrors its lines exactly, realized differences and evidence methods included (ADR-0026.R11; `EC-52`). A bank statement line matched to the document returns to `unmatched` in the same transaction. The registry of ADR-0009.R19 lists these types.
Source: ADR-0048.R16

### Dunning, collection data and the payment block

R206. `cash` owns the side tables `open_item_collection` and `partner_collection` (ADR-0026.R1's side table). `open_item_collection` holds one row per open item that has collection data, keyed by the open item and tied to its company, with `dunning_level`, `last_reminder_date`, `is_payment_blocked`, `payment_block_reason`, `is_disputed` and `dispute_reason`; no row reads as level 0, no reminder, not blocked and not disputed. `partner_collection` holds the partner and `has_open_complaint`; it has no DDL (DS-25).
Source: ADR-0048.R17, ADR-0048.R17.N1

R207. In `open_item_collection`, `is_payment_blocked` needs `payment_block_reason`, which is `duplicate_review` (the block of ADR-0063.R27) or `manual` (interim); `is_disputed` needs `dispute_reason`; `dunning_level` is 0 exactly while `last_reminder_date` is empty.
Source: ADR-0048.R17, ADR-0048.R17.N1

R208. A settle line of a `cash_payment` or `bank_payment` that names a blocked item is refused with `open_item_payment_blocked` (trigger `trg_payment_line_payment_block`). `Post` of these types repeats the check, so a block set after the draft holds too. Receipts are not held. `GetAllocationProposal` and `RunDunning` skip blocked and disputed items. `INV-98` checks the block.
Source: ADR-0048.R17, ADR-0048.R17.N1

R209. A `cash` consumer of `crm`'s complaint events (DS-35) sets and clears `partner_collection.has_open_complaint`. The events are `ComplaintCreated`, `ComplaintUpdated`, `ComplaintClosed` and `ComplaintReopened`, with the complaint as subject and its ID, partner ID and state as payload. Under ADR-0004.R22, `CreateComplaint` emits `ComplaintCreated`; there is no `ComplaintOpened`, because the verb Open belongs to posting periods. `cash` never imports `crm`.
Source: ADR-0048.R17, ADR-0052.R21

R210. The order of complaint events does not matter: events of different complaints have no common order (ADR-0013.R3). On each event the consumer reads the partner's open complaints through the query `ListComplaint` and sets `has_open_complaint` to whether any exist. Complaints closed in either order leave the right flag (`INV-501`).
Source: ADR-0048.R17, ADR-0052.R21

R211. `RunDunning` (date) proposes reminder drafts per customer, for overdue items that are not blocked or disputed, by levels of days overdue: the company setting `cash.dunning.levels`, default 7, 30 and 60. Customers with an open complaint are skipped (spec 13).
Source: ADR-0048.R17

R212. Reminders are outbound message drafts. A person sends them, after the consent check (ADR-0019.R9). The drafts are `crm` outbound messages, made by `crm`'s consumer of the completion event of `RunDunning`, which carries per customer the level and the open item IDs; recipients are the contacts flagged `is_accounts_contact` (ADR-0052.R28). Interest on late payment comes later.
Source: ADR-0048.R17

### Catalog rows of ADR-0048

R213. The system account `currency_exchange_clearing` is a leaf under `asset`, not bilateral, with control kind `none`, and the core excludes it from revaluation. The localization package maps it to a technical account of its chart; that row is package content, `unverified`.
Source: ADR-0048.R20

R214. These transaction keys map to these system accounts. Each has a determination row in the localization package, whose account numbers are flagged package content, `unverified`; the regime alternatives leave those rows unchanged (ADR-0053.R6):
   - `bank_charge`: `administrative_expense`, with `financial_expense` as a regime alternative;
   - `cash_surplus`: `asset_surplus_pending`, with `non_operating_income` as a regime alternative;
   - `cash_shortage`: `asset_shortage_pending`, with `non_operating_expense` as a regime alternative;
   - `payment_difference_income`: `non_operating_income`;
   - `payment_difference_expense`: `non_operating_expense`;
   - `bad_debt_expense`: `administrative_expense`;
   - `bad_debt_allowance`: `receivable_allowance`;
   - `bad_debt_recovery`: `non_operating_income`;
   - `payable_release_income`: `non_operating_income`;
   - `currency_exchange_clearing`: `currency_exchange_clearing`.
   Source: ADR-0048.R20, ADR-0048.R20.N1

R215. The company declares the account of `bank_charge` at setup (author, 2026-11-15): setup shows the package's proposal, and the company confirms it or picks another. The choice is a company determination row with basis `company_decision` (ADR-0016.R6, ADR-0016.R7).
Source: ADR-0048.R20

R216. The error codes of ADR-0048 are `money_account_negative`, `money_account_kind_mismatch`, `overdraft_not_allowed`, `bank_statement_unbalanced`, `bank_statement_line_posted`, `netting_agreement_missing`, `manual_posting_to_control_account` and `write_off_above_limit`, with `money_transfer_currency_mismatch` and `money_account_line_not_allowed` (ADR-0048.R12.N1) and `open_item_payment_blocked` (ADR-0048.R17.N1).
Source: ADR-0048.R20

R217. The check results of ADR-0048 are `bank_statement_gap`, `settlement_rate_unusual` and `settlement_rate_unchecked`. Its work item kind is `bank_line_unmatched` (a note on ADR-0042.R18).
Source: ADR-0048.R20

R218. The company settings of ADR-0048 are `cash.bank_account_cooling_days`, `cash.small_difference_limit` and `cash.dunning.levels`. Its regime settings, which the localization package seeds `unverified`, are `cash.netting_requires_agreement`, `cash.bad_debt_provision.buckets` and the per-group value of `fx.document_rate.allowed`.
Source: ADR-0048.R20

R219. The invariants `INV-94`, `INV-95`, `INV-96` and `INV-97` are all first executable at step 6. The edge cases of ADR-0048 are `EC-72` to `EC-78`, in this order: a duplicate bank line without a reference; a payment arriving while its invoice is in `issuing`; an early-payment discount on a partial payment; a cash count with a shortage; a currency exchange between money accounts; a bad-debt provision across buckets followed by a write-off; an employee advance overspent and topped up before settlement. `edge-cases.csv` is authoritative. DS-17 adds the events `cash_counted`, `currency_exchanged` and `advance_settled` to its cash group; `EC-77` uses `period_closed`.
Source: ADR-0048.R20, ADR-0048.R20.N2

R220. The lab check `t08_cash.py` covers, as pure functions: the matching cascade (already-posted first, whole-token references within one partner, side and currency, partial references, shared accounts, subsets, and the same proposal for shuffled inputs); allocation proposals; discounts by the gross-up of ADR-0048.R7; provision buckets; company rules and a third-party reference; short tokens that are not references; the book rate (a backdated cash outflow refused by the floor, the same floor on a bank account, a backdated outflow emptying the balance and a reversed inflow both leaving no residual, overdraft refused in a foreign currency); cash count differences. The DS-06 changes run under the existing journal and opening tests. Not covered: tables, locks, consumers, statement readers, tax evidence.
Source: ADR-0048.R21

### Bank matching agent

R221. The bank matching workflow is triggered by a work item `bank_line_unmatched` (ADR-0048.R9), which the agent type declares. Runs act for the workflow owner (ADR-0050.R15). Its scope is `subject`: the statement line, which is outside content, so the run starts tainted (ADR-0050.R15). Its input is `bank_statement_line_overview` for that line, with `include_untrusted`. Step D1: the cascade already ran at import and found nothing, which is why the item exists.
Source: ADR-0051.R17

R222. Step L1 `read_description` runs on the seat classification with personal data, because descriptions are personal (ADR-0050.R9). Its output is `BankMatchingReadOutput`: `reference_tokens` (at most 5), `payer_name_text`, `stable_payer_token` and `purpose`, one of `invoice_payment`, `advance`, `refund`, `salary`, `tax`, `bank_charge`, `internal_transfer`, `loan`, `unknown`. Checks: every reference token is a whole token of the description and reference-shaped as R225 requires, or it is dropped; the payer name and the stable token are substrings of the description after folding, at least 3 characters long.
Source: ADR-0051.R17

R223. Step D2 `record_suggestion`: `RecordBankLineSuggestion` (module `cash`, effect class `other`, `is_draft_only`) stores the tokens, name, purpose and run on the line, all `is_untrusted`, and emits `BankLineSuggestionRecorded`, which carries IDs only (ADR-0013.R4). The step is `bank_matching.suggest`. The run then ends `drafted` or `no_action`. It never matches, posts or reads partners.
Source: ADR-0051.R17

R224. `RecordBankLineSuggestion` writes the `bank_statement_line` columns `suggested_reference_tokens`, `suggested_payer_name_text`, `suggested_stable_payer_token`, `suggested_purpose` and `suggestion_agent_run_id`. A `bank_charge` purpose read by the model never qualifies a line for the `bank_charge` rule class, and an `llm_suggestion` draft never auto-posts, whatever the settings (ADR-0063.R8, ADR-0063.R9).
Source: ADR-0051.R17, ADR-0051.R17.N1

### Deterministic follow-up and auto-post evidence

R225. A `cash` consumer of `BankLineSuggestionRecorded` runs `match_bank_line` once more, with the suggested tokens added as reference tokens at step 2 only, under step 2's guards: each token must be a whole token of the description and reference-shaped, at least four characters with a digit or the package's pattern for its invoice numbers (ADR-0048.R9), and all the items its tokens name must belong to one partner. If it finds items of exactly one partner, it drafts the receipt or payment as ADR-0048.R9 does, as `system` on behalf of the run's human (ADR-0013.R9), marked `match_basis` `llm_suggestion` and with no score. The draft carries the run as its origin, so it is tainted (ADR-0029.R8, ADR-0029.R12) and a person posts it (ADR-0043.R9, floors 3 and 5). Its data never returns to the run.
Source: ADR-0051.R18

R226. The guards of step 2 stay on the re-run: a suggested token counts only as a whole, reference-shaped token of the description. A reference the payer wrote in another form is not a whole token of the description, is refused, and the line stays for a person. The effect of a suggestion is therefore its stable payer token, which feeds the matching-rule proposals of R230, and its purpose classification, shown to the person who matches the line. The token re-run is one pure call, and the shadow comparator of R232 is defined on it. Whether the agent earns its cost in Phase 1 is an open question.
Source: ADR-0051.R18, ADR-0051.R18.N1

R227. Auto-post applies only to cascade matches with a score and no LLM contribution, under an enabled rule (ADR-0048.R9; ADR-0043.R14). Its shadow evidence is `GetAutoPostShadowEvaluation` (module `cash`; document types, score floor, amount maximum, date range): of the cascade's proposals at or above the floor and below the maximum in the range, the share that people posted unchanged. `EnablePolicyRule` for such a rule obtains that result through an evidence hook that `policy` declares and `cash` registers for its document types, wired by `app` (layer 6), so `policy` imports no layer-4 module. It stores the result and is rejected with `shadow_evidence_insufficient` unless the evidence covers the proposals that `auto_post.max_error_rate` requires (its default gives 300 proposals with at least 99% posted unchanged; ADR-0063.R10), over at least two statement months, with no proposal posted to another partner.
Source: ADR-0051.R18, ADR-0051.R18.N3

R228. The evidence counts only proposals made under one `parameters_hash` and names it with the parameter set's latest transition. A later parameter set version, demotion, rollback or invalidation marks the stored evidence outdated in its own transaction, and re-arming needs a new rule version with new evidence (R236 to R238). Evidence counts proposals of approved LLM-originated rules only while `cash.auto_post.accept_llm_originated_rules` is true (R248).
Source: ADR-0051.R18.N2, ADR-0051.R18.N3

R229. Every unattended posting goes through the auto-post gateway of ADR-0065, whose instances are the bank cascade (unchanged), the production import and the purchase invoice. The `llm_suggestion` drafts of R225 still never auto-post. `cash.auto_post.accept_llm_originated_rules` is not bounded false; its default is false (ADR-0065.R12, ADR-0065.R20).
Source: ADR-0051.R18.N4

### Rule proposals, gates and the shadow comparator

R230. When a person posts a document matched to a line that carried a `stable_payer_token`, or matches such a line by hand, a `cash` consumer writes a draft `bank_matching_rule` version (token to that partner) as R244 states, if the token appears in at least two of that partner's lines in the last 90 days and in no other partner's lines. The version copies an untrusted token, so it is written tainted, as a version derived from untrusted content (ADR-0029.R8, ADR-0029.R10), and a person approves it (ADR-0029.R5).
Source: ADR-0051.R19

R231. Human gates: a person posts the drafted document or matches the line, which resolves the item; a person approves rule versions.
Source: ADR-0051.R19

R232. Shadow comparator: a shadow run records its tokens but nothing persists, so no consumer runs. The comparator runs the pure `match_bank_line` on the line with the shadow tokens added at step 2, under the same guards as R225, and compares its proposal with the person's final match: equal when partner and settled items are equal. A proposal of nothing counts as different when the person matched the line to an invoice.
Source: ADR-0051.R19

R233. Failures of the bank matching run: with no usable token it writes a note and ends `no_action`. With the routing switch on, descriptions are personal and L1 cannot be sent, so every run ends `routing_blocked` (ADR-0050.R9).
Source: ADR-0051.R19

### Parameters of the bank cascade

R234. `cash.match_bank_line` declares these parameters (name: default, bounds):
   - `already_posted_window_days`: 5, 0 to 10 (step 1);
   - `subset_search_size`: 6, 1 to 8 (step 4; the upper bound limits the search);
   - `score_already_posted`: 95, 0 to 100;
   - `score_reference_exact`: 100, 0 to 100;
   - `score_reference_partial`: 80, 0 to 100;
   - `score_account_amount`: 90, 0 to 100;
   - `score_account_amount_tied`: 60, 0 to 60 (safety cap; a tied match never acts whatever its score);
   - `score_account_subset`: 70, 0 to 100;
   - `cap_company_rule`: 90, 0 to 90 (safety cap on a company rule's match in confirm mode, R241);
   - `cap_counterparty_unverified_exact`: 85, 0 to 85 (safety cap);
   - `cap_counterparty_unverified_partial`: 65, 0 to 65 (safety cap);
   - `cap_paid_by_third_party`: 60, 0 to 60 (safety cap);
   - `show_min_score`: 0, 0 to 100 (below it the cascade drafts nothing and the line stays for a person).
   Source: ADR-0059.R5

R235. Order constraints of the parameters: `score_reference_exact` > `score_reference_partial` > `score_account_subset`, and `score_account_amount` > `score_account_subset`. A step 3 match among several equal items is marked tied on its line and is never auto-posted, a hard rule of the cascade outside tuning. The cascade's act threshold is the score floor of the company's auto-post policy rule (ADR-0043.R14), which stays where posting authority lives, and stays off by default.
Source: ADR-0059.R5

R236. A cascade proposal records on its `bank_statement_line` the `match_parameters_hash`, the `match_function_version`, the `match_parameter_set_version_id` and the `match_parameter_state` in force (`core_default`, `assisted` or `active`), and `match_is_tied`. `GetAutoPostShadowEvaluation` counts only proposals made under one hash, which its result names.
Source: ADR-0059.R6

R237. The evidence that `EnablePolicyRule` stores names that hash and the parameter set's latest transition at that moment (null when it has none). Through the hook `auto_post_eligibility` (ADR-0059.R2), a `system` posting of a cascade draft gets `human_post` unless its line carries the evidenced hash, was proposed while the state in force was `active` or `core_default` (so assisted never acts, which the line itself shows), and is not tied, and the rule version's evidence is not marked outdated. A function release does not switch it off by itself (ADR-0059.R4).
Source: ADR-0059.R6

R238. A demotion, a rollback or an invalidation of the parameter set, and a re-evaluation below the thresholds (ADR-0059.R4), mark the stored evidence of every dependent auto-post rule version as outdated, in the same transaction, through the hook of ADR-0059.R2, without comparing times: `policy_rule_version.shadow_evidence_outdated_by` names the transition or the re-evaluation. A new parameter set version taking force does the same; raising the version already in force from `assisted` to `active` does not, because the pointer does not move. `EnablePolicyRule` refuses evidence that is outdated, or whose recorded latest transition is not the parameter set's latest (`auto_post_evidence_outdated`). Stored evidence is set once, so re-arming needs a new rule version with new evidence; a demotion back to an earlier hash never re-arms auto-post on old evidence.
Source: ADR-0059.R6

R239. The auto-post gateway's stored evidence names the checker version and the version of the decision table at its decision point. A change of the table version in force, its demotion or its rollback marks that evidence outdated through `artifact_in_force_changed`, in the same transaction, as for parameter sets (ADR-0065.R9, ADR-0065.R14).
Source: ADR-0059.R6.N1

### Matching passes and matching rules

R240. Bank, partner and item matching use deterministic rule passes, each marked `confirm` (its match may act when policy allows) or `suggest` (it drafts or proposes for a person, never acts). Ambiguity always suggests: a line that more than one pass or rule would give to different partners, a line that also names another partner's reference, or a tied match is drafted without acting.
Source: ADR-0059.R10

R241. Bank company rules (ADR-0048.R9) are artifacts of kind `matching_rule`: each `bank_matching_rule` version carries the lifecycle columns and `match_mode`. A rule names the partner only; steps 3 and 4 still find and score the items. In `assisted` the rule matches in suggest mode: it drafts with match basis `company_rule` and no score, so it is never auto-posted. In `active` it matches in confirm mode: steps 3 and 4 score the match, capped by `cap_company_rule`, and the counterparty caps of ADR-0048.R9 apply, because a description token is as untrusted as a reference.
Source: ADR-0059.R10

R242. An account rule maps a token to an account (a bank fee to the bank charges account, say); it has no open items for steps 3 and 4 and drafts the document to that account. In confirm mode it scores `cap_company_rule`, under the counterparty caps (with no partner, the unverified cap), only when its token is a whole, reference-shaped token of the description (the shape of ADR-0048.R9) and the amount's sign matches the account's natural side; otherwise it suggests without a score. More than one matching rule on a line, whatever their targets, suggests. Its lifecycle is that of a company rule, and its evidence is later lines that people posted to that account.
Source: ADR-0059.R10

R243. A draft under the unverified or third-party cap carries the flag of ADR-0048.R9 (`counterparty_unverified`, `paid_by_third_party`) and is never auto-posted, account rules included; so an account rule's draft with no partner owning the paying account is never auto-posted, except through the account-rule class `bank_charge` (R250 to R252). Where a partner owns the counterparty account, account-rule drafts are auto-posted only when the auto-post rule's evidence of R227 counts proposals of that basis (`company_rule_account`) among its proposals; otherwise they get `human_post`. The DDL check of `bank_statement_line.match_basis` does not list `company_rule_account`.
Source: ADR-0059.R10, ADR-0059.R10.N1

R244. One carrier for rule proposals: the consumer of R230 writes the rule as a `bank_matching_rule` version in `draft`, tainted, by the draft-only command `CreateBankMatchingRuleVersion`; no change proposal waits. A person holding `edit` on the leaf `bank_statement` may call it too, for a rule they write themselves (untainted); it is on no agent tool list. The rule's identity, with its owner, is created by `CreateBankMatchingRule` (effect class `master_data_change`) in the same batch. Its drafting window ends at the value date of the second qualifying line. The version becomes `backtested`, its evidence sufficient, once at least the declared minimum of later lines (default 1) carry the token and people matched every one of them to that partner (or posted them to that account). The only proposal is `SetArtifactVersionState`: approved, the rule starts in `assisted` (suggest mode) and reaches `active` (confirm mode) on live evidence.
Source: ADR-0059.R10, ADR-0051.R19.N1

R245. AI proposes rules and tolerances; people decide. The proposer, or the human its run acted for, is never the approver. An approved rule whose token an LLM read feeds a scored match, and so an auto-post, only under `cash.auto_post.accept_llm_originated_rules` (R247, R248).
Source: ADR-0059.R10, ADR-0059.R10.N1

R246. Bank matching in Phase 1: the LLM's contribution stays suggest-only (R221 to R225). Deterministic auto-post stays off by default and is enabled only through the evidence of R227, bound to the parameters by R236 to R238.
Source: ADR-0059.R25

### LLM-originated bank matching rules

R247. The setting `cash.auto_post.accept_llm_originated_rules` has scope company and default false. Its bounds are true and false, and enabling it is a loosening by proposal (ADR-0065.R12; author's decision of 2026-11-16 on tainted auto-post). Spec 03 rule 1 was reworded on 2026-11-21 (ADR-0065.R12).
Source: ADR-0063.R8, ADR-0063.R8.N1

R248. When `cash.auto_post.accept_llm_originated_rules` is true, the human approval of a matching rule version ends the LLM's contribution to the rule's later matches only if all of these hold; otherwise its drafts get `human_post`:
   - the token is a whole, reference-shaped token of the description, not generated;
   - the rule went live on independent evidence (at least 10 suggest-mode drafts, at least 99% posted unchanged, ADR-0059.R18);
   - its approver is neither its proposer nor the human the drafting run acted for;
   - the version records `origin` `llm_proposed`;
   - the auto-post rule's own evidence (ADR-0063.R10) counts proposals of that basis.
   Source: ADR-0063.R8, ADR-0063.R8.N1

R249. Hard, whatever the setting: `llm_suggestion` drafts never auto-post; an LLM-proposed rule is never approved by its proposer; the counterparty caps of ADR-0048.R9 still apply.
Source: ADR-0063.R8, ADR-0063.R8.N1

### Bank charges

R250. `bank_charge` is an account-rule class (R242). A `bank_charge` rule passes the counterparty check of ADR-0048.R9, instead of drafting under the unverified cap, when the line is a debit of the money account, carries a bank transaction code (`bank_statement_line.bank_transaction_code`, from the statement reader) listed in the money account's setting `cash.bank_charge.codes`, and names no counterparty account at all (`counterparty_account_number` is null). Its draft has match basis `bank_charge_rule` and is not flagged `counterparty_unverified`.
Source: ADR-0063.R9

R251. Auto-post of a `bank_charge` rule is per rule, default off; bank fees may auto-post, configurable. A rule version may enable it only with an `amount_max` at or below the company setting `cash.bank_charge.auto_post_ceiling` (default 0, which disables the class; no other core value, because an amount is currency-dependent). As a deterministic rule it is outside the floor of ADR-0063.R10; its evidence is at least `cash.bank_charge.min_evidence_lines` lines (default 6, bounds 3 to 50) over at least `cash.bank_charge.min_statement_months` statement months (default 3, bounds 1 to 12), every one posted unchanged to the rule's account. The owner still confirms auto-posts in batches before close (spec 03 rule 6; ADR-0043.R14).
Source: ADR-0063.R9

R252. Hard limits of `bank_charge` auto-post: never when open items also match the line; never when more than one rule matches it; never above `amount_max`; never from the LLM's purpose classification (`suggested_purpose` `bank_charge`). `INV-705` checks these gates.
Source: ADR-0063.R9

### The bank cascade as an auto-post gateway instance

R253. The bank cascade and the production import are instances of the auto-post gateway of ADR-0065, with `runner: own`, and keep their behavior. `cash` registers checkers for `bank_receipt`, `bank_payment`, `cash_receipt` and `cash_payment` (actor `system`, `accepts_tainted: false`) whose rules are the `auto_post_eligibility` conditions (ADR-0043.R14; R237) and the `bank_charge` gates (R250 to R252), with `GetAutoPostShadowEvaluation` as their evidence function. Their trigger stays the cascade (ADR-0048.R9; R227), their settings stay `cash.*` and `auto_post.max_error_rate`, and `llm_suggestion` drafts stay out (ADR-0063.R6).
Source: ADR-0065.R20

R254. `production` registers a gateway checker for `operation_confirmation` (actor `integration`, `accepts_tainted: false`) whose rules are those of ADR-0064.R25 (no check result at all, `production.mes_import.auto_post` true), with `GetProductionImportShadowEvaluation` as its evidence function. Its trigger stays `ImportOperationConfirmation`.
Source: ADR-0065.R20

R255. For the bank cascade and the production import, the gateway changes this: their decisions are written in the gateway's columns (ADR-0065.R6), and they share the hard rules of ADR-0065.R7 and the document-type suspension of ADR-0065.R16. The placeholder `<document_type>` of ADR-0065.R8 does not list them, so the generic settings do not apply to them.
Source: ADR-0065.R20

### Default money account per payment method

R256. `payment_method_money_account` (company data, owned by `cash`, effect class `master_data_change`, change-tracked) holds the default money account per payment method (ADR-0068.R15). Its fields are `payment_method_id`, `money_account_id`, `currency` (the money account's, held by a composite key) and an optional `branch_id`. The row is unique per (method, branch, currency), with `NULLS NOT DISTINCT`. `cash` owns it because `cash` is layer 4 and may reference `master_data`; the reverse would make the CRM-only profile depend on `cash`.
Source: ADR-0068.R16

R257. A payment drafted with a method takes the `payment_method_money_account` row for its document's branch and currency, else the row for its currency without a branch, else none. The money account then gives the payment type: `cash_*` or `bank_*` (ADR-0048.R3).
Source: ADR-0068.R16

R258. Kind check: a `cash` method maps to a `cash` money account, and every other method to a `bank` money account. An `offset` method has no row. A mismatch is refused with `payment_method_money_account_mismatch`.
Source: ADR-0068.R16

R259. The kind of a payment method only suggests. The payment document type and its line still decide `evidence_method` (ADR-0048.R18). `cash` suggests `cash`; `bank_transfer`, `cheque`, `direct_debit` and `e_wallet` suggest `bank_transfer`; `card` suggests `card`; `offset` makes the cash agent propose a partner netting (ADR-0048.R10) instead of a payment; `cash_on_delivery` and `other` suggest nothing.
Source: ADR-0068.R17

R260. The deterministic matching cascade (ADR-0048.R9) does not read the payment method. The cash agent may cite it in an explanation.
Source: ADR-0068.R17

## Invariants

- `INV-98` (day): no cash or bank payment settles an open item that was blocked for payment when the payment posted: at each posted settle line of a `cash_payment` or `bank_payment`, the change history of the item's `open_item_collection` row shows `is_payment_blocked` false. Protects R208.
- `INV-501` (day; area `crm`): when `cash`'s complaint consumer has no pending, running or held delivery, `partner_collection.has_open_complaint` is true exactly for the partners with an open complaint. Protects R209, R210.
- `INV-705` (day): every document posted by system from a `bank_charge` rule has a debit line whose bank transaction code its money account lists, no counterparty account, no open item matched, one matching rule, and an amount at most the rule's `amount_max`, itself at most the company ceiling on the posting date. Protects R250 to R252.

`INV-94`, `INV-95` and `INV-96` are stated in chunk 1. `INV-97` has area `ledger`.

## Edge cases

| Case | Name | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-82` | `bank_description_free_text_reference`: a bank line's description names an invoice in free text that the cascade cannot use; the suggestion leads to a tainted draft without a score, which an enabled auto-post rule does not post | `must_succeed` | R221 to R227 |
| `EC-163` | `bank_parameters_promoted_then_demoted`: a parameter set for the bank cascade drafted from three months is backtested on the next two, shadowed, promoted with frozen evidence, keeps auto-post off until new evidence under its hash, and is demoted to shadow by override drift a month later; the demotion marks the auto-post rule's evidence outdated, and `EnablePolicyRule` refuses it until a new rule version brings new evidence | `must_succeed` | R234 to R238; ADR-0059.R12 to ADR-0059.R21 |
| `EC-165` | `bank_token_rule_suggest_then_confirm`: a bank token rule is written as a draft version, waits for a later line, is approved into suggest mode by a second person, drafts without a score, and moves to confirm mode on live evidence with its score from steps 3-4; a line naming another partner's reference stays a suggestion | `must_succeed` | R240, R241, R244 |
| `EC-168` | `bank_account_rule`: a bank-fee token rule maps to the bank charges account; an outflow with the whole token drafts to that account at `cap_company_rule` under the unverified-counterparty cap, flagged `counterparty_unverified` and never auto-posted; an inflow with it only suggests, and more than one rule on a line suggests | `must_succeed` | R242, R243 |
| `EC-182` | `bank_charge_auto_post`: monthly fee lines with the configured code reach six over three months; the auto-post of a rule is enabled and the next fee posts by system; a fee above `amount_max` gets `human_post`; a fee line that also matches an open item is not auto-posted | `must_succeed` | R250 to R252 |
| `EC-183` | `llm_originated_rule_opt_in`: with the setting false a confirm-mode match of an LLM-proposed rule gets `human_post`; a proposal to enable it is refused with `setting_out_of_bounds` while its bound is false, and the match stays `human_post`; an `llm_suggestion` draft never posts by system. The catalog row predates ADR-0065.R12: the setting's bounds are true and false, so enabling it is a loosening by proposal (R247) | `must_reject:setting_out_of_bounds` or `must_succeed` (catalog row predates ADR-0065.R12) | R247 to R249 |
| `EC-184` | `wrong_auto_post_suspends`: a person reverses a document posted by system; the rule version's evidence is marked outdated, `auto_post_suspended` is raised, and the next match gets `human_post` | `must_succeed` | ADR-0063.R10 |
| `EC-263` | `payment_method_default_money_account`: a USD sales invoice with a `bank_transfer` method drafts a bank receipt on the USD money account set for the invoice's branch; an invoice with a `cash` method drafts a cash receipt on the cash money account without a branch row | `must_succeed` | R256 to R259 |

`EC-72` to `EC-78` are stated in chunk 1; `EC-77` also concerns R202. `EC-52` has area `receivables_payables`.

## Settings

| Key | Value type | Scope | Core default | Used by |
| --- | --- | --- | --- | --- |
| `cash.auto_post.accept_llm_originated_rules` | boolean (bounds `true`, `false`) | `company` | `false` | R228, R229, R245, R247, R248 |
| `cash.bank_charge.auto_post_ceiling` | amount (bounds `0..`) | `company` | `0` | R251 |
| `cash.bank_charge.codes` | `code_list` | `money_account` | `[]` | R250 |
| `cash.bank_charge.min_evidence_lines` | integer (bounds `3..50`) | `company` | `6` | R251 |
| `cash.bank_charge.min_statement_months` | integer (bounds `1..12`) | `company` | `3` | R251 |
| `cash.dunning.levels` | not stated (days overdue per level) | company | 7, 30 and 60 | R211, R218 |
| `cash.bad_debt_provision.buckets` | not stated (percentage by days overdue) | regime | not stated; the package bands are flagged `unverified` | R202, R218 |

`cash.dunning.levels` and `cash.bad_debt_provision.buckets` have no row in `settings.csv`; the rules define them. The rows of `cash.bank_account_cooling_days`, `cash.small_difference_limit` and `cash.netting_requires_agreement` (named by R218) are in chunk 1, with the same remark, and so is the read of `fx.document_rate.allowed`.

Reads: `auto_post.max_error_rate` (R227, R253), `production.mes_import.auto_post` (R254), `data_processing.policy`, `data_processing.never_send_fields`, `extensions.wasm_enabled`, `intake.duplicate.date_window_days`, `intake.duplicate.amount_tolerance_minor_units`, `intake.duplicate.number_normalization`, `intake.duplicate.near_outcome`.

## UI annotations

The sources hold no floorplan, title, facet, field annotation or tile of ADR-0077 for this module. The row of the work
item kind `bank_line_unmatched` is in chunk 1; R221 takes the kind as the trigger of the bank matching workflow.

## Conflicts

CONFLICT ADR-0048.R20: the keys `bank_charge`, `cash_surplus` and `cash_shortage` also list regime alternative accounts, as ADR-0048.R20.N1 and ADR-0053.R6 state; R214 gives the combined rows.
CONFLICT ADR-0051.R18: the fixed 300 proposals at 99% are the default of the setting `auto_post.max_error_rate` under ADR-0051.R18.N3 (ADR-0063.R10); R227 states the threshold through the setting.
CONFLICT ADR-0051.R18.N4: the note lifts the false bound of the LLM-originated setting and generalizes the Decision sentence to the gateway; ADR-0065.R12 and ADR-0065.R20 govern, stated in R229.
CONFLICT ADR-0051.R19: the consumer no longer drafts a change proposal that a person submits; ADR-0051.R19.N1 and ADR-0059.R10 make it a draft rule version, stated in R230 and R244.
CONFLICT ADR-0051.R19.N1: the note replaces the change proposal draft with a draft `bank_matching_rule` version written by `CreateBankMatchingRuleVersion`; it agrees with ADR-0059.R10 and is folded into R244.
CONFLICT ADR-0059.R10: its open questions on bank fee auto-post and on LLM-proposed rules are answered by ADR-0059.R10.N1 (ADR-0063.R8, ADR-0063.R9); R243 and R245 state the answers. Its basis `company_rule_account` is kept in R243 although the DDL check of `match_basis` lacks it.
CONFLICT ADR-0063.R8: the bound of false until spec 03 rule 1 is reworded, with `setting_out_of_bounds`, is lifted by ADR-0063.R8.N1 (ADR-0065.R12); R247 states bounds true and false, and the comparison with the bound of `extensions.wasm_enabled` is not restated. The description of the row `EC-183` of `edge-cases.csv` still describes the refusal under the false bound; its outcome already allows `must_succeed`, and its row here keeps the catalog text and says so.
CONFLICT ADR-0063.R8.N1: it calls the rewording of spec 03 rule 1 an open question; ADR-0065.R12 governs: the rewording was applied on 2026-11-21.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0048.R14 | R201-R204 |
| ADR-0048.R16 | R205 |
| ADR-0048.R17 | R206-R212 |
| ADR-0048.R17.N1 | R206-R208 |
| ADR-0048.R20 | R213-R219 |
| ADR-0048.R20.N1 | R214 |
| ADR-0048.R20.N2 | R219 |
| ADR-0048.R21 | R220 |
| ADR-0050.R9 | ref: ADR-0050.R9 |
| ADR-0050.R9.N1 | ref: ADR-0050.R9.N1 |
| ADR-0050.R9.N2 | ref: ADR-0050.R9.N2 |
| ADR-0050.R9.N3 | ref: ADR-0050.R9.N3 |
| ADR-0051.R17 | R221-R224 |
| ADR-0051.R17.N1 | R224 |
| ADR-0051.R18 | R225-R227 |
| ADR-0051.R18.N1 | R226 |
| ADR-0051.R18.N2 | R228 |
| ADR-0051.R18.N3 | R227, R228 |
| ADR-0051.R18.N4 | R229 |
| ADR-0051.R19 | R230-R233 |
| ADR-0051.R19.N1 | R244 |
| ADR-0052.R21 | R209, R210 |
| ADR-0058.R1 | ref: ADR-0058.R1 |
| ADR-0059.R5 | R234, R235 |
| ADR-0059.R6 | R236-R238 |
| ADR-0059.R6.N1 | R239 |
| ADR-0059.R10 | R240-R245 |
| ADR-0059.R10.N1 | R243, R245 |
| ADR-0059.R25 | R246 |
| ADR-0063.R8 | R247-R249 |
| ADR-0063.R8.N1 | R247-R249 |
| ADR-0063.R9 | R250-R252 |
| ADR-0063.R27 | ref: ADR-0063.R27 |
| ADR-0063.R27.N1 | ref: ADR-0063.R27.N1 |
| ADR-0065.R20 | R253-R255 |
| ADR-0068.R15 | ref: ADR-0068.R15 |
| ADR-0068.R16 | R256-R258 |
| ADR-0068.R17 | R259, R260 |
| ADR-0068.R23 | ref: ADR-0068.R23 |
| ADR-0068.R25 | ref: ADR-0068.R25 |
| ADR-0074.R17 | ref: ADR-0074.R17 |
