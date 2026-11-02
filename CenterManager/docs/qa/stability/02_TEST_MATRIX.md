# Stability test matrix
| ID | Severity | Fault/condition | Oracle | State |
|---|---|---|---|---|
| S01-WAL-01 | P0 | Snapshot after committed WAL, then edit runtime | Snapshot retains earlier committed rows; runtime retains later rows; integrity and FK checks | Automated added; CI pending |
| S01-WAL-02 | P0 | Copy snapshot raises OSError | Original DB reopenable; no residual snapshot | Automated added; CI pending |
| S01-WAL-03 | P0 | Atomic destination replace raises OSError | Old Git artifact unchanged; runtime data preserved | Automated added; CI pending |
| S01-CIPHER | P0 | Real encrypted SQLCipher commit, WAL, recovery snapshot | Cipher open, integrity/foreign keys, committed rows, capture hash | Existing `test_qa_p0_recovery_fault_injection.py`; re-run at branch SHA |
| S01-JOURNAL | P0 | Capture copy, manifest/fsync/verification failure | Previous capture remains; OPEN/PUBLISHING cannot clean | Existing E1B and QA P0 tests; re-run |
| S01-ACK | P0 | Remote accepted push, ACK lost | Verify exact accepted OID; unknown preserves journal | Existing QA P0 tests; re-run |
| S01-RESTORE | P0 | Crash/restart during maintenance and restore | No unverified DB replacement; signed identity/generation unchanged | Needs isolated Windows fault injection |
| S02-2PC | P0 | Two EXEs, same-name stale session, lease/grace, offline | One authorized writer; no stale release/false success | BLOCKED: 2 independent Windows staging clients unavailable |
| S03-DOMAIN | P1 | Student→Enrollment→Attendance→Debt→Archive, A-02/S-01 CSV | No finance/history mutation; full filtered export | NOT RUN |
| S04-UI | P1 | Git timeout, renewal, workspace churn, restart | No blocked Qt main thread/deadlock | NOT RUN |
|
No claim of SQLCipher coverage from synthetic SQLite WAL tests. Use disposable fixtures exclusively.
