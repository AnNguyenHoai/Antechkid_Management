# QA-P0-DB-COLLAB-01 — Risk-first test case catalog

**Status:** DESIGN ONLY / NOT RUN. Each test must use fresh synthetic records, independent local DB paths, dedicated test Git remote and preserved evidence. Expected properties are anchored in E1B-1/E1B-2B contracts and FINANCE_INVARIANTS.md; product edge cases need further source confirmation.

| ID | Priority | Preconditions / exact steps or injection | Expected independently verifiable outcome |
|---|---|---|---|
| DB-001 | P0 | WRITE with journal OPEN; insert student S001 and income I001 in one SQL transaction; kill process after flush before commit | Neither row committed; integrity and foreign key checks clean |
| DB-002 | P0 | Same data; kill immediately after successful SQL commit, before business callback | Both committed rows preserved in DB/WAL and protected from startup overwrite |
| DB-003 | P0 | Crash during checkpoint / snapshot preparation while -wal has committed frames | Original remains recoverable; incomplete snapshot not treated as verified |
| DB-004 | P0 | Inject ENOSPC during backup snapshot and during restore staging (separate runs) | Earlier valid backup and installed DB unchanged; explicit blocked status |
| DB-005 | P0 | Wrong SQLCipher key and separately truncated candidate copy | No automatic rekey, install, reset or pin; original DB remains intact |
| COL-001 | P0 | Two independent clients A/B barrier-synchronized at acquire; one eligible lease | At most one active valid WRITE; other WAITING/READ; no simultaneous DML |
| COL-002 | P0 | A owns lease; B direct repository SQLAlchemy, Core and raw DBAPI INSERT | Denials before persistence; no new records; remote unchanged |
| COL-003 | P0 | A lease renewal returns UNKNOWN while SQL statement in flight; subsequently commit | No commit after expiry/loss; recoverable journal and deterministic error |
| COL-004 | P0 | A old session shares username with B new exact session; A attempts release | B lease OID and session remain unchanged |
| COL-005 | P0 | A crashes holding WRITE; B queue waits through grace then handoff | Queue and lock consistent; A unpublished work recoverable; no unauthorized takeover |
| COL-006 | P0 | A old EXE/stale publisher attempts direct MAIN push after B authority, on isolated Git remote | Production-equivalent server authorization must reject stale publish; otherwise **release blocker** |
| PUB-001 | P0 | Commit+push successful at remote, inject lost ACK before local transition | Remote accepted OID reconciled; no duplicate transaction or blind push |
| PUB-002 | P0 | Kill after snapshot preparation, before push | Local unpublished data and journal retained; no false SUCCESS |
| PUB-003 | P0 | Simulate non-fast-forward and expired authority during retry | Remote not overwritten; original local edits preserved |
| PUB-004 | P0 | Push verified, then exact-session release fails or process dies | Journal remains reviewable; publication not falsely marked unaccepted |
| REC-001 | P0 | Kill at journal PREPARING/OPEN/PUBLISHING/PUBLISHED transitions (separate runs) | Reopen preserves evidence, never silently cleans or overwrites |
| REC-002 | P0 | Recovery retry twice on same preserved base against changing remote | Idempotent evidence, explicit conflict and no duplicate financial postings |
| AUTH-001 | P0 | READ, WAITING, UNKNOWN, STALE: invoke SQLAlchemy flush, bulk UPDATE, native DBAPI | All unauthorized DML fail closed; read queries still succeed |
| AUTH-002 | P0 | Valid WRITE: run long SQL transaction while renewal succeeds independently | No false deadlock; operation outcome follows lease validity |
| AUTH-003 | P0 | Use checkpoint/bootstrap/migration permit outside allowed lifecycle | No arbitrary Student/Finance write bypass |
| BUS-001 | P1 | S001 archive after attendance; view current month before/after two-device sync | Attendance denominator excludes ineligible archived/withdrawn roster as intended, history unchanged |
| BUS-002 | P0 | E001 withdrew, class archived, debt 100000 and payment 40000 | Exact enrollment remains OWED 60000 after publish/reopen; no cross-enrollment netting |
| BUS-003 | P0 | Tuition payment 120000 on 100000 obligation; archive and sync | PREPAID 20000 preserved, never auto-refunded |
| BUS-004 | P1 | Edit historical Income linked to withdrawn enrollment then publish/reopen | Original financial attribution remains stable unless explicitly changed with authorization |
| BUS-005 | P1 | Generate Student Report on Finish and separately simulate report write failure | No new authoritative SQL mutation after accepted publish; derived failures visible |
| BUS-006 | P1 | 10001 Income rows, query dashboard total with paging | Aggregate reflects all qualifying rows, no pagination truncation |

## Execution evidence format
For every ID record: exact test SHA, synthetic seed, preconditions, injection hook, steps, expected vs actual rows, DB/WAL SHA256 (note byte hashes may change during valid checkpoint), SQLCipher integrity and FK results, identity/generation, remote OIDs, lock/queue, journal status, logs, verdict PASS/FAIL/BLOCKED/NOT RUN and linked source lines. Count only actually executed cases.

## Sequencing
Execute COL-006 and PUB-001 before broader business regression; then DB-002/003/005, AUTH-001 and REC-001. Run real two-PC scenario before release signoff. Do not use production credentials or remote.
