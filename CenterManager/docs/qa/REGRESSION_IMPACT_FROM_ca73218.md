# QA-P0-DB-COLLAB-01 — Preliminary regression impact audit

Status: IN PROGRESS / NO EXECUTED TEST EVIDENCE. Branch: `main_repos`; baseline `ca73218fc0c57dcd2e8c0a47a04e7b828bfcb312`. The GitHub compare endpoint reported **77 commits ahead** at audit time. Final target SHA, complete test execution and Windows multi-machine validation remain pending. Do not treat this document as release approval.

## Verified source-level coverage changes
The compare includes database/engine.py, guarded_dbapi.py, mutation_authority.py, mutation_permissions.py, session.py, write_recovery.py, collaboration_manager.py, git_synchronization_provider.py, write_transaction.py, report_service.py, attendance_service.py and finance services, plus dedicated E0/E1A/E1B tests. This is a dependency impact list, not a claim that every entry is defective.

## Highest priority architecture finding (QA-RISK-001)
The repository's `WRITE_AUTHORITY_FENCING_CONTRACT.md` explicitly labels remote publication fencing **PROPOSED / NOT IMPLEMENTED** and warns that credentials held by legacy clients may permit direct MAIN updates. A local DB mutation gate does not alone prove stale remote publishers are rejected. Required empirical gate: legacy/stale client attempts an ordinary push to an isolated authoritative remote after newer owner is granted; demonstrate server-side rejection without relying on cooperative client checks. Severity: P0 exposure; **not a reproduced defect**. The correct production mitigation requires separately approved remote enforcement; no live remote settings should be changed as part of QA.

## Related reliability gaps to validate
- Lost Git push acknowledgement after accepted publication, exact-session release, and recovery journal cleanup.
- Crash after local commit, before preservation receipt or journal transition; committed WAL frames remain recoverable.
- SQLCipher raw DBAPI / bulk DML mutation denial in READ, WAITING, UNKNOWN, suspended and stale session states.
- Startup DB replacement and restore fail closed against pending recovery evidence.
- Archived student/class attendance numerator and denominator, tuition balance and historical Income attribution survive synchronization.
- Local gates retain valid authority while worker renews on slow UI; loss notifications do not deadlock a DB commit.

## Coverage strategy
L1 deterministic state machine and gate tests; L2 real isolated SQLCipher database + WAL verification; L3 competing independent Git clients using isolated bare/test remote; L4 two Windows EXE processes and hard kill; L5 repeated randomized seed cycles. For each case capture initial/ending business record sets, `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, DB identity/generation, remote MAIN OID, lease ownership and recovery journal manifest. Never access production DB, Git remote, lease or student data.

## Release decision
**NOT VERIFIED / HOLD** until required fault-injection, real SQLCipher, two-client Git and Windows end-to-end cases are run with artifacts. No failures or PASS counts are claimed in this preliminary audit.
