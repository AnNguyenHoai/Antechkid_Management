# RV-05 — Windows EXE recovery-to-new-WRITE release gate

**Issue:** #597 · **Priority:** P0 release blocker · **Target:** main_repos

## Automated evidence

`tests/test_rv05_recovery_to_new_write.py` uses a disposable real Git bare remote and an encrypted synthetic SQLCipher workspace. Client A commits LOCAL_UNACCEPTED locally, independent client B advances MAIN by ten commits, startup preserves A in a verified Recovery Case and installs authoritative MAIN, and a new WRITE owner publishes *only* NEW_AUTHORIZED_WRITE. The test asserts old local work never leaks into authoritative MAIN, original capture remains valid, pending reminder survives Finish/restart, and normal editing resumes without requiring acknowledgement.

**Passing this integration test alone is not release approval.** It cannot establish Windows packaged EXE process isolation, credential access, multiple physical workstations, old executable behavior or GitHub branch permission enforcement.

## Executable UAT matrix — record evidence per row

Run only on isolated **test Git repository** with disposable encrypted database and test accounts. Never simulate destructive crashes or mutate real tuition/finance data on production.

| ID | Action | Required evidence / pass condition |
| --- | --- | --- |
| UAT-01 | Launch packed EXE A, edit under WRITE, kill process with SQLCipher WAL/SHM live, restart | Backup includes all committed bytes; no partial WAL; no lost attachment; recovery case signed and pending |
| UAT-02 | Before/during/after Git publication kill EXE, including post-push lost ACK | Outcome classified VERIFIED or UNVERIFIED from independent Git proof; no double publish/assumed lost entries |
| UAT-03 | Client A unaccepted local data; client B pushes MAIN A+10 | A stored in immutable capture, new runtime matches A+10; remote commit stays unchanged by startup |
| UAT-04 | Close popup / Skip; restart multiple times | Pending reminder reappears; READ/WRITE allowed only when startup authority checks succeeded |
| UAT-05 | Click Đã kiểm tra with one of two pending cases; restart | Only selected case is ACKNOWLEDGED; other remains pending; neither backup deleted |
| UAT-06 | Verify case summary / export, inspect logging | No student/finance plaintext, password, database key, backup path; summary explicitly warns about UNKNOWN Change Log coverage |
| UAT-07 | Manual finance re-entry of suspected payment | Compare remote MAIN source records (receipt/reference/date/amount/student) before re-entry; no duplicate transaction or debt |
| UAT-08 | After verified recovery obtain a **new** remote WRITE session, edit and Finish | New lease/session verified; publish creates expected MAIN successor commit; old captured changes not replayed |
| UAT-09 | Two real Windows machines race for WRITE and queue/grace | At most one owner; stale owner cannot commit locally or release new owner, even after reconnect |
| UAT-10 | Old EXE with historic Git credentials starts after new client owns WRITE | Old EXE cannot push to authoritative MAIN; branch protection/credential enforcement independently proven |
| UAT-11 | Kill EXE during atomic install and repeat reboot | Interrupted-install marker replays fully or blocks; no mixture of new DB and old assets |
| UAT-12 | Revoke/change DPAPI user key, corrupt snapshot/manifest and fill storage | No data replacement or fake REVIEWED; original capture and marker retained; actionable error |
| UAT-13 | Large attachments, Windows junction/symlink and read-only files | Verified capture complete; untrusted path blocked; original files preserved on failure |
| UAT-14 | Git timeout / network loss during lock acquisition, publish and release | Fail closed with explicit UNKNOWN, no incorrect “nobody is writing”; no stale publication |
| UAT-15 | Restart EXE repeatedly with two reviewed and one pending case | Only pending case prompts; registry files remain signed and originals unchanged |

## Critical old-EXE enforcement limitation

An older executable that still holds an effective Git credential with direct permission to update authoritative MAIN **cannot be reliably prevented** by new-client local checks alone. A fresh local mutation gate, journal, version check or UI warning does not revoke that credential. **UAT-10 must prove server-side GitHub branch permissions/credential revocation** or the deployment remains **BLOCKED**. Do not assert stale-publisher fencing solely from simulated collaboration/session tests.

## Evidence template

For each UAT row record: `ID`, date/time and tester, Windows build, packed EXE hash/version, machine A/B, disposable Git remote and branch, pre/post MAIN OID, lock ref session/OID, recovery case ID (prefix only), masked logs/screenshots, exact action, expected vs observed, PASS/FAIL/BLOCKED, regression issue link.

Use a test repository with no reused production PAT; archive evidence in restricted project storage. Store no DPAPI secrets or student/finance PII in UAT artifacts.

## Release decision

- [ ] All required Windows pytest shards PASS for exact commit being released
- [ ] UAT-01 through UAT-15 evidence reviewed (or documented scoped exceptions approved)
- [ ] Old EXE direct-push protection proven at GitHub permission layer
- [ ] No critical regressions, unauthorized WRITE or data loss
- [ ] Founder explicitly signs off with build hash and evidence index

Until these are checked: **DO NOT MERGE AS A RELEASE APPROVAL / DO NOT CLOSE #597**. Use `Refs #597` in partial PRs. Add `Closes #597` only to the final PR after actual Windows EXE and cross-workstation evidence plus founder approval.


## Normal stale-local regression — A Finish → B Finish → A returns

`tests/test_rv05_clean_remote_advance.py` independently exercises **a normal successful collaboration**, not a Recovery incident:

1. Client A obtains WRITE, commits `A_FIRST` to encrypted SQLCipher and finishes with a verified `CLEAN` journal at Git MAIN M1.
2. Client B clones Git MAIN, adds `B_SECOND` to the *authoritative encrypted database*, updates its signed artifact identity and pushes a successor M2.
3. A is still at M1 locally, but its receipt is `CLEAN`. Normal startup verifies and installs M2; assert **no recovery case**, no pending review, correct SQLCipher rows.
4. A independently obtains a fresh WRITE, publishes `A_THIRD` at M3, and restarts. Verify MAIN/runtime contain all three accepted edits and the registry remains empty.

This is a regression guard against mistakenly treating **lagging local MAIN** as **unaccepted local work**. Production Git authentication, independently deployed old EXEs and two physical Windows workstations remain separate UAT requirements.
