# Simulation observations: integrated design (ds-production, HEAD bd459d4), flows 1-11

Date: 2026-11-15. Simulator: `sim/` (flows 1-6 with the UoM scenario, and the new flows 7-11). Two runs on fresh databases
(`nativeflows_sim_final_a`, `nativeflows_sim_final_b`): 11 flows pass, 83/83 flow checks, 27/27 invariants, 17 LLM calls per run
(recorded fallback fixtures, `SIM_LLM=off`), and `compare_traces.py` finds 0 differences. The design repo was not edited.

## Design gaps found

1. **The payment hold has no table.** In flow 7 a near-duplicate invoice is posted under `intake.duplicate.near_outcome = review`,
   so its open item must be blocked for payment. ADR-0063 rule 27 and ADR-0048 name `open_item_collection.is_payment_blocked`, but
   no DDL defines `open_item_collection`. The simulation keeps a stub of it in `sim_stubs.sql`.
   *Fix:* add `open_item_collection` (open item, dunning level, last reminder, `is_payment_blocked`, `is_disputed`, dispute reason) to
   DS-06 or DS-22. Payment proposals and outgoing payments should then refuse a blocked item.
2. **Auto-post evidence does not record which settings it depends on.** ADR-0063 rule 3 says a loosening marks the evidence of
   "every enabled auto-post rule version ... that depends on the key" as outdated. `policy_rule_version` has `shadow_evidence` and
   `shadow_evidence_outdated_by`, but nothing records which setting keys the evidence was judged under; the lab uses an invented
   `depends_on` list. Flow 9 got by because `auto_post.max_error_rate` applies to every auto-post rule. Per-class keys such as
   `cash.bank_charge.*` or `production.confirmation.*` could not be resolved.
   *Fix:* `EnablePolicyRule` stores the keys and values in force inside the evidence (for example `shadow_evidence.settings`), or in a
   column `evidence_setting_keys text[]`. ADR-0063 rule 3 and ADR-0043 rule 14 should state it.
3. **A new rule and the new table it pins cannot be activated together.** In flow 9, `automation_rule_version_check_pins` refuses
   any move out of `draft` while the pinned decision table version is only `backtested`; this is ADR-0058 rule 20. The rule therefore
   cannot reach `backtested`, and cannot hold its replay evidence, until a first proposal has activated the table. The simulation
   activates both with one proposal and moves the rule draft -> backtested -> active inside the execution.
   *Fix:* allow a pin on a `backtested`/`shadow` table version while the rule is in draft, backtested or shadow. Require
   `assisted`/`active` only when the rule goes active. Let one proposal execute both, table first, under the `configuration_state` lock.
4. **Nobody can approve an automation activation with the DS-17 role templates.** Only `owner` (full) and `it_administrator` (full)
   hold leaf `configuration`. The it_administrator has no `change_proposal` right, and ADR-0058 rule 24 excludes the submitter and the
   drafter. A rule the owner drafts therefore has no eligible approver. The simulation gives `purchasing_manager` `configuration` edit,
   so she drafts and submits and the owner approves.
   *Fix:* give the business managers `configuration` edit in `role-template-levels.csv`, or give `it_administrator` approval on
   `change_proposal`.
5. **The chief accountant cannot submit a policy-setting loosening.** She holds `policy` at full but has only `read` on
   `change_proposal`, so for the policy leaf only the owner can submit and she approves (flow 9). This works, but it is backwards for
   the role that owns the policy area.
   *Fix:* give `chief_accountant` `change_proposal` edit, as the accountant has.

## Notes (not design gaps)

- **Lab mismatch.** The lab's reference `resolve()` in `t19_barcode.py` still fills the expiry date from (15) when (17) is absent.
  That is the old interim of ADR-0061 rule 17, which the rule's note and ADR-0063 rule 26 replaced. Flow 8 applies the setting
  (`best_before_fills_expiry = false`) through `t24_settings.receive_lot`. *Fix:* align `t19_barcode.resolve`.
- **`e_invoice_record` is still a simulation stub (DS-24 pending).** The quarantine, supersession and key-conflict columns of
  ADR-0057 rule 25 are not modelled. Flow 7 uses passed signatures only.
- **System auto-posting always needs confirmation.** `ck_policy_rule_version_loosening` requires `is_confirmation_required` for any
  non-human `allow` at post, so a system auto-post rule always carries a confirmation (ADR-0043 rule 3). This is consistent with
  ADR-0063 rule 10's "wrong confirmation of a system posting".
