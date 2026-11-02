# Developer bug handoff
## Confirmed reproducible product defects
None confirmed in this QA branch at document creation. New fault-injection tests are not yet executed; no production changes authorized.
## Risk hypotheses awaiting proof
- A stale legacy publisher with remote push permissions may bypass app-side lock checks when MAIN OID has not changed. This is an acknowledged remote-authority limitation, **not** a reproduction on production GitHub.
- Crash during SQLCipher WAL/checkpoint, restore/maintenance and ambiguous ACK may expose recovery regressions; validate with encrypted synthetic workspace.
- Two-client Windows EXE lease/UI behavior remains unobserved in staging.
On FAIL: record pinned SHA, OS/runtime, deterministic reproducer, expected/actual, DB+WAL hash, journal, manifest, Git OIDs and test output before requesting scoped code fix.
