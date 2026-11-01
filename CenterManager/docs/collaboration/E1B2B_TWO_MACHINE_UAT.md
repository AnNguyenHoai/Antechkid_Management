# E1B-2B — Two-machine UAT checklist

Status: NOT EXECUTED. Use two **disposable** Windows workspaces A/B, a synthetic
SQLCipher key, and a dedicated test Git data repository. Never use production DB
or lock refs. Both machines must run the candidate build. Save version/SHA,
times, UI messages, journal inspection and accepted DB queries for every case.

| Step | Action | Required result |
| --- | --- | --- |
| 1 | A in READ, try Student/Finance writes through normal UI and a test-only direct service/DBAPI harness | Controls project READ; any persistence attempt is denied; queries/reports work |
| 2 | A Start Editing; create/update Student, attendance, enrollment and a normal Income | Authorized saves work; journal OPEN has A's exact session; existing Finance identity/history preserved |
| 3 | B requests WRITE and waits; attempt callback/bulk/raw writes on B | WAITING remains visible and no protected DML is admitted |
| 4 | A leaves keyboard/mouse alone for less than the existing idle timeout while worker renews | No crash/revocation inference; A can still save |
| 5 | Keep a committed WAL update and a worker transaction flushed but not committed on A. Disconnect A's test Git transport and trigger an actual renewal attempt | New statements and pending commit denied on uncertain authority; transaction RECOVERY_REQUIRED; no reset or remote force-release |
| 6 | Close the failed service session normally; inspect recovery data before restarting | Committed local work/base retained; encrypted intent evidence exists for the admitted pending SQL; values absent from plaintext logs/receipts |
| 7 | Reconnect A, then restart/retry editing | No automatic old-work adoption, overwrite, pull/reset or CLEAN transition; explicit recovery remains required |
| 8 | In a separate fresh case, let A's lease expire using the unchanged policies; after TTL/grace let B take WRITE | A's old raw/cached SQL/commit is denied after its validity boundary or a failed/mismatched observation; B owns its new exact session |
| 9 | B saves and Finish Editing, including dirty-student reports | One accepted core publication, read-only derived report generation, exact-session release, CLEAN only after unchanged E1B-1 proofs |
| 10 | Deliver an application-owned late callback after Finish | SQL denied; accepted rows unchanged; denial does not invent a dirty DB or hide real pending work |
| 11 | Use a renderer/file failure while core publish succeeds | Explicit report warning; successful core release/receipt rules retained; Admin can regenerate in READ |
| 12 | Try backup in READ, then restore/migrate while recovery is pending | Read snapshot works; pending replacement/migration is rejected; original DB/WAL/captures retained |
| 13 | Exercise clean authorized restore/installed-runtime schema barrier and a fresh bootstrap in isolated workspaces | Existing authorization + maintenance proofs work; handles drain before rename; bootstrap permit cannot write Student/Finance data |
| 14 | Refuse non-forced Cancel with dirty changes, then continue editing; separately exercise real 30-minute idle and explicit cancellation | Refused Cancel keeps valid editing; idle/cancel follow existing policies and retain unaccepted work; no new session silently adopts it |

Record PASS/FAIL per step and any recovery capture IDs. Do not mark this checklist
complete from CI. Do not use UAT to claim remote MAIN fencing, instant legacy-client
revocation or Admin emergency revoke; these remain E1C blockers.
