# QA-P0-02 — 18 attack scenarios

Baseline main_repos SHA: `470b7385d60d776bde8e555396520a71fd99c9b9` (initial test snapshot). R1: isolated unprotected bare Git; R2: staging protected remote **NOT PROVIDED / BLOCKED**. Every test requires session/lock/main OIDs, Git exit code and local candidate SHA. All scenarios without direct automated coverage are NOT RUN.

| ID | Scenario | Reproduction/injection | Status |
|---|---|---|---|
| PUB-FENCE-001 | Expired WRITE owner | R1 direct push after lease/lock changes; R2 remote deny | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-002 | Same username old session | R1 direct push bypass; R2 exact-session rejection | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-003 | Legacy executable bypass | Legacy direct Git push; R2 old credential denied | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-004 | Direct Git without collaboration API | R1 direct push accepted; R2 denied | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-005 | Stale MAIN OID | Conflicting MAIN expected OID rejected; preserve candidate | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-006 | Stale lock current MAIN | R1 accepts FF direct push; R2 deny | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-007 | Concurrent publications | Deterministic barrier; only authorized candidate accepted in R2 | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-008 | Revoke vs publish | R2 coordinated CAS linearization proof | NOT RUN; R2 BLOCKED |
| PUB-FENCE-009 | Authority changes during push | R2 pre-receive owner check | NOT RUN; R2 BLOCKED |
| PUB-FENCE-010 | Renewal vs expiry vs publish | R2 final authority at commit point | NOT RUN; R2 BLOCKED |
| PUB-FENCE-011 | Lost push ACK | Reconcile exact observed remote OID; no duplicate | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-012 | Disconnected before/during/after push | Inject transport failures; UNKNOWN not SUCCESS | NOT RUN; R2 BLOCKED |
| PUB-FENCE-013 | Conflict after authority loss | No overwritten MAIN; preserve local | NOT RUN; R2 BLOCKED |
| PUB-FENCE-014 | Crash after accepted push | Restart recovery journal consistent | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-015 | Shared legacy credentials | R2 retired token denied by server | NOT RUN; R2 BLOCKED |
| PUB-FENCE-016 | READ client with Git token | R1 direct push accepted; R2 denied | R1 partial automated; R2 BLOCKED |
| PUB-FENCE-017 | Downgraded executable | R2 protocol version reject | NOT RUN; R2 BLOCKED |
| PUB-FENCE-018 | Replayed publication | R2 request-id/epoch idempotency | NOT RUN; R2 BLOCKED |

R1 tests: `tests/test_qa_p0_02_r1_git_attacks.py`. R1 intentionally expects direct push to succeed, demonstrating **lack of server authority enforcement** on that remote. Do not classify this behavior as security PASS. Tests that require real Windows EXE, encrypted database, process hard-kill or production-equivalent protected staging remain NOT RUN/BLOCKED. No secret-bearing remotes used.
