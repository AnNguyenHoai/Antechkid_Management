# QA-P0-DB-COLLAB-01 — Initial execution report

Status: **NOT VERIFIED — RELEASE HOLD**.
Baseline: `ca73218fc0c57dcd2e8c0a47a04e7b828bfcb312`.
Target: `main_repos` at initial comparison, 77 commits ahead. **Exact target SHA must be pinned before formal execution.**

## New automated tests added

`tests/test_qa_p0_git_publication_fencing.py` contains two default real Git repository tests (independent clones and stale expected-OID CAS rejection) plus one opt-in P0 legacy direct-push denial release gate. The opt-in gate is deliberately expected to FAIL on an unprotected bare Git remote, illustrating absent server-side enforcement; it does not verify production GitHub settings. Commands:

```sh
python -m pytest tests/test_qa_p0_git_publication_fencing.py -v
ANTECHKIDS_QA_FENCING_GATE=1 python -m pytest tests/test_qa_p0_git_publication_fencing.py -v
```

On Windows PowerShell use `$env:ANTECHKIDS_QA_FENCING_GATE='1'` before the second invocation. These tests were **committed but NOT EXECUTED** in this session, so results are still NOT RUN.

## Additional recovery fault-injection coverage

Added `tests/test_qa_p0_recovery_fault_injection.py`: three capture failure stages (ciphertext copy, manifest write, capture verification), two ambiguous publication outcomes, one real SQLCipher integrity/foreign-key check on a verified capture, and one mismatched-remote reconciliation denial. These **7 parameterized cases are committed but have not been executed in this conversation**. They reuse E1B-1 synthetic encrypted workspace fixtures. No product fixes.

## QA continuation — Collaboration contention and mutation paths

Added `tests/test_qa_p0_collaboration_contention.py` with **8 parameterized test cases**: simultaneous 2/3/4-client acquisition using real isolated Git refs; stale same-username exact-session release rejection; and four post-loss SQLCipher mutation paths (service, ORM, bulk DML and raw guarded DBAPI). These are committed, **not yet executed** at the new head. Existing E1A/E1B2B tests cover related paths; these cases widen concurrency participant count and denial entry-point matrix. Every failing case must preserve full CI logs and remote ref evidence.

GitHub workflow **run #824** for commit `e747fdafa0cd6a5a6584543119191cd3f51d1570` completed with success. This does **not** establish PASS for the newly added cases at a later SHA.

## Counts
Automated fault-injection scenarios executed in this QA campaign: **0**.
PASS: **0**; FAIL: **0**; BLOCKED: **0**; NOT RUN: **24 designed scenarios**.

These zeroes do not describe existing project CI and must not be interpreted as passing the release gate.

## Confirmed audit observations
1. GitHub compare verified baseline ancestry of main_repos and files changed across persistence, collaboration, recovery, reporting and finance.
2. Source document `docs/collaboration/WRITE_AUTHORITY_FENCING_CONTRACT.md` explicitly states remote publication fencing is PROPOSED / NOT IMPLEMENTED; stale legacy publisher denial remains **unverified**, with P0 potential.
3. Source document `docs/collaboration/E1B2B_LOCAL_MUTATION_AUTHORITY.md` describes application-level DBAPI enforcement under validation, not a proof of production-wide denial.
4. E1B-1 document acknowledges unsaved in-memory forms are not recoverable after a hard process kill; distinguish this known product limitation from SQL-committed loss.

## Needed to complete
Pin target HEAD SHA, review code paths line-by-line, implement deterministic injection adapters and SQLCipher fixtures, execute test suite on isolated disposable test remote, execute two independent Windows clients and collect actual DB/remote/journal evidence. No product business logic modifications or live permission/remote changes are authorized. Do not merge this QA-only PR until reviewed.

## Recommendation
**HOLD release pending verified P0 isolation and replay tests.**
