# Tuition V1 — Group B F-05/F-06/F-07 acceptance

**Repository:** AnNguyenHoai/Antechkid_Management
**Branch:** feat/tuition-v1-group-b-f05-f07
**Release state:** opt-in UI stays disabled; legacy historical Enrollment rows unchanged.

## F-05: Reschedule without repricing
- Activated monthly plan allocations are immutable per (original Session ID, original date, VND). Cross-month rescheduling changes the operational Session date but never its financial month, amount or Enrollment policy.
- A lesson moved before the opt-in boundary must not be re-billed using the old policy.
- An authorized RESCHEDULED outcome may reference a separate replacement makeup Session in the next month; that replacement must not demand another monthly plan or accrue a second fee.
- Regular SessionService cannot delete an already allocated monthly session, or reopen a cancelled monthly session without a separate audited finance reversal.
- Read model errors on missing/ambiguous allocated data instead of silently assigning fees.

## F-06: Explainable Tuition Detail
- Summary shows monthly gross allocated, amount waived for authorized no-makeup center cancellation, net monthly accrual, actual cash/settlement and signed outstanding/prepaid balance.
- Session table distinguishes the immutable original billing date from the current scheduled date, records per-session amount and waiver.
- For monthly Enrollment, `gross_accrued - recognized_discount = net_accrued`; recognized discount includes legacy historical discount plus approved monthly cancellation allowance. No new Income is posted for cancellation.
- If monthly evidence is incomplete the detail fails closed instead of reporting `No tuition configured` with zero accrued.

## F-07: Financial / recovery regression
- Isolated SQLAlchemy tests cover cross-month and backdated reschedules, no deletion/reopening of allocated lessons, authorized replacement makeup, tuition breakdown with waiver, Income and Outstanding parity, cancellation retry idempotency, and transactional rollback on outbox failure.
- CI runs the complete Windows pytest suite, 3 independent shards.
- Real SQLCipher restore, Git-only concurrent WRITE lease loss and packaged Windows EXE must be accepted in release UAT before turning on the feature; synthetic rollback regression does NOT prove real hardware recovery.

## Release decision
Group B **engineering** is complete only when all three Windows shards pass on the final branch HEAD and the PR contains the above regression evidence. This does not authorize enabling the global monthly billing feature flag. Merge requires founder approval.
