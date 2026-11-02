# QA-S02 R2 — grace waiting, handoff and stale release

Baseline: `main_repos` `af3ddb2dacac43cea932ed16778b4f5f9349e4c4`; PR #541 merged.
CI #874 on PR #541 head `37b5cf45193292b811a3ecb8adb89fcffc1ab3cc` PASS: https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41464485910

## Added cases
1. Old owner expires into clock-skew grace. Same-username waiter stays WAITING with a renewable remote queue request. At authorized handoff after grace, only new session is remote owner, stale old session cannot release the new lock using old OID/session.
2. Waiting cancellation during grace must remove the authoritative queue request first, then reset local transaction WAITING projection to IDLE, with prior owner OID/session unchanged.

Fixtures: existing `tests/test_e0_write_recovery_audit.py` fake monotonic clock and disposable bare Git remote. No real accounts, production WRITE lease, official DB, or tokens.

Run: `cd CenterManager && python -m pytest tests/test_qa_stability_s02_grace_stale_owner.py -v`.

**Evidence at authoring:** 2 new tests NOT RUN; await exact-head Windows CI. Existing tests cover related E1A scenarios but are not equivalent to new combinations and cannot be counted as these test PASS.

**Limitations:** clock-simulated collaboration is not real Windows 2-PC UAT; network failures, real process exit and packaged UI freeze still need independent evidence. No new coordinator, architecture change or product fix authorized. On FAIL, separate fixture defect from product behavior and record remote lock OID / queue state.
