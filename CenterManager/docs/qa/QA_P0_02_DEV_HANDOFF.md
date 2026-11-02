# QA-P0-02 — Developer security handoff

## QA-SEC-001 — Remote WRITE authority not enforceable by client-only MAIN CAS
Priority P0 (architectural risk); production exploit **NOT VERIFIED**.
Evidence: `WRITE_AUTHORITY_FENCING_CONTRACT.md` labels publication fencing PROPOSED / NOT IMPLEMENTED. `GitSynchronizationProvider` runs direct Git commands with client-held tokens. R1 automated test models old owner direct push after successor changes `lock-main` but leaves MAIN unchanged.

### Expected / actual
Expected: all unowned writers, including old executables and raw Git clients, rejected at authoritative remote update. Actual: in a Git remote accepting ordinary pushes, a stale client can fast-forward MAIN despite unrelated authority-ref transition. This is **expected R1 behavior**, pending CI execution; NOT proof of production GitHub settings.

### Developer remediation constraints
Design enforceable server-side ref authorization/central coordinator, deny direct MAIN write to old desktop tokens and version-gate legacy clients, rotate credentials as approved. Do not replace with only a new client-side check, second read of lease, UI disablement or MAIN-only CAS. Preserve existing recovery journal and encrypted local candidate. Infrastructure design and live setting changes require separate approval.

### Verification
Re-run `test_qa_p0_02_r1_git_attacks.py` to document bypass in R1; then independently show R2 denies same attack, including same username, expired/revoked/READ, old credentials and concurrent revoke/publish. Capture exact ref OIDs and Git exit codes. Do not merge until R2 evidence exists. No production fix implemented by QA.
