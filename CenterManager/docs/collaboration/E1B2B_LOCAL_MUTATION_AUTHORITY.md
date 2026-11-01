# E1B-2B — Local mutation authority gate

Status: CURRENT — implementation under validation; Windows CI and human review required.
Base: `main_repos` `5793821adbab214b4e39937a475ad550a70f39f5` (merged #526).
Scope: application-owned local SQLCipher persistence. No production data/lock access,
new migration, remote publication policy, Admin revoke or time-policy change.

## Audited paths and resulting boundary

The E0 [call-site inventory](WRITE_MUTATION_BOUNDARY_INVENTORY.md) remains the
service/repository checklist. This audit re-scanned all `create_engine`,
`create_engine_for_path`, `create_production_engine`, native `connect`,
`commit`, `flush`, bulk and UI persistence call sites at the above base.

| Entry / path | Data and side effects | Admission / exception |
| --- | --- | --- |
| `app.main`, `database.session.create_session_factory`, `core.permissions` | Shared runtime SQLAlchemy sessions | Canonical runtime engine always wraps DBAPI; app binds its one transaction manager before exposing workspace actions |
| Student/Parent/Assessment/Progress/Product/Note/Attachment services, repositories | Authoritative aggregate rows, timeline and audit rows; attachment files | ORM DML and commit pass the same driver gate; existing service/resource rules remain |
| Class/Session/Enrollment/Freeze/Transfer/Attendance services | Authoritative academic/tuition identity and history, timeline, dirty-student events | Same boundary, including nested transactions and bulk operations |
| Income/Expense/FinancePeriod/Settlement/TuitionAdjustment services | Financial records, timeline/audit side effects | Same boundary and canonical capabilities; no accounting rule or history transformation |
| Employee/schedule/registration/time/document services | Authoritative employee records; legacy self-link repair is a write | Same gate; missing Employee repair cannot silently run in READ |
| PermissionService role/user/password administration | Authoritative account, role and credential rows; best-effort audit | Same gate. Verified own-password change has a narrow credential-verified context for the four existing password/reset columns; exact WRITE still required |
| `PermissionService.authenticate_user` | Previously changed login attempts, last-login and password hash before any WRITE identity | Runtime login is SQL-read-only. Encrypted workstation activity receipt handles throttling; persisted shared inactive/locked state is still checked. Legacy hash upgrade waits for authorized password change |
| `ReportService._generate`, AutoReportService, Finish callbacks | SQL reads plus rebuildable PDF and `.report.json` files | #526 behavior retained. No SQL business permit for rendering after publish; genuine external mutations still trigger E1B-1 preservation |
| `AuditService.record[_in_session]` | Authoritative audit INSERT | WRITE plus an initiating write capability; no audit exemption allowing READ SQL |
| `ConfigurationService`, GitConfigService, core config/secret store | Machine-local JSON, credentials and deployment settings, not SQL rows | Existing configuration/setup permissions and storage contracts; these are not permits to mutate SQLCipher. This task does not redesign filesystem preference authorization |
| SQLAlchemy `Session.flush/commit`, `Session.execute`, Core/raw connection and bulk APIs | Prepared DML, generated SQL, CTE DML, triggers | Native authorizer at every execution and driver commit; no Session-only bypass |
| `acquire_runtime_dbapi_connection`, `runtime_dbapi_connection` | Application-owned native handles | Return guarded adapter; registry retains native identity until native close succeeds |
| `create_engine_for_path(runtime, runtime_guarded=False)` | Historical low-level helper path | Runtime ownership captured at engine creation; false flag or later path-context changes cannot downgrade it |
| Installed-runtime migration / startup migration | Existing bundled Alembic chain and revision DML | Explicit thread-scoped migration permit, before DB transaction; pending recovery rejects startup maintenance. Installed migration consumes the pre-swap journal proof while the existing maintenance fence is held |
| Fresh initialize + `initialize_production_database.py` | New DB container, WAL configuration, initial users/roles/permissions | Separate initialize and narrow bootstrap permits. Bootstrap cannot write Student/Finance rows |
| WAL snapshot / recovery preservation | Checkpoint committed frames and copy ciphertext | Checkpoint-only permit under existing maintenance fence. No business DML, schema or rekey capability |
| BackupService snapshot/validate | Read-only source, encrypted disposable backup destination | Existing read/snapshot and native-handle fences retained; no WRITE needed to read a backup source |
| Backup restore, runtime install/startup sync | File swaps, sidecars, metadata and rollback copies | Existing restore authorization, RecoveryAuthority, journal replacement proof and quiesce/refresh remain. Pending/lost authority journal cannot be overwritten by these paths |
| Encryption conversion, clean-DB/upgrade/publish CLI tools | Explicit offline/staged file conversion and installation | Existing confirmation, replacement/journal and publication controls remain; canonical runtime conversion additionally refuses a bound application. These are trusted maintenance tools, never ordinary READ callbacks |
| Optional `ProtectedDomainGateway` service engine | Alternate SQLCipher path with SID-bound application tokens | Explicitly guarded, unbound writers fail closed. A service login token is not distributed WRITE. IPC authority forwarding is not implemented here; service mutation enablement remains blocked |
| `SystemOperationsService` diagnostics, lifecycle/security validation, upgrade snapshot sources | Integrity/schema reads | Read-only native opens; diagnostics cannot implicitly create a missing DB |

Read-only queries and repository/report projections continue without a business
permit. Unknown tables, DDL, ATTACH/DETACH, mutating extension functions,
rekey and persistence PRAGMAs are rejected on normal runtime WRITE handles.
Runtime `executescript` and autocommit mode changes are explicitly unsupported;
callers must use fenced statements and explicit commit. SQLAlchemy's standard
read functions and per-connection foreign-key enablement remain available.

## Permit lifecycle and validity

`MutationAuthorityGate` is a **consumer** of CollaborationManager observations,
not a second ownership authority. `is_writing=True` alone is never sufficient.

1. App binds the existing WriteTransactionManager. Default admission is closed.
2. Existing handoff verifies the accepted base; E1B-1 prepares an OPEN journal.
3. Explicit entry validates the existing remote lease outside database locks.
   The gate binds journal repository identity, local `.git/config` digest, exact
   session, database path and a process-local incarnation (not a remote epoch).
4. Only ACTIVE, verified, exact-session/owner observations with an OID refresh
   validity. Deadline is bounded by the existing 60-second lease, request-start
   monotonic time plus TTL, and the observed remaining lease. Slow requests
   cannot add validity. Successful existing renewal/observation feeds this consumer.
5. At statement admission and commit, check transaction state, suspension,
   incarnation, actor identity, canonical capability floor, current local journal
   and repository binding. No Git/network operation occurs here.
6. A failed renewal, UNKNOWN/GRACE/absent/different owner, expired observation or
   inconsistent journal stops admission and latches RECOVERY_REQUIRED. Reconnect
   or successful later observations cannot reopen that old work automatically.
7. Finish admits only its synchronous save thread, then closes admission before
   materialization/publish/reports. Cancel and release close it too. Old handles
   cannot adopt a new incarnation. Refusing a non-forced dirty cancel does not
   close an otherwise valid editing session.

The gate mutex serializes native statement/commit execution with loss
notification. The commit path never acquires the collaboration state mutex;
renewal can hold that mutex while delivering an observation without a lock
inversion. Recovery mode projection is queued through the existing EventBus so
UI handlers run after the database hook unwinds, including when storage of the
protection marker fails. SQLite itself still serializes concurrent writers. Native authorizer
installation is repeated per execution to invalidate cached prepared statements.

Canonical capabilities in `mutation_permissions.py` are a persistence **floor**,
not replacement row-level policy: aggregate side-effect tables accept the
initiating aggregate's write capability. Existing service validators, self/all
employee rules, the narrow EmployeeCapabilityPolicy compatibility rule, last-admin
rules and Finance invariants remain authoritative. Authenticated legacy Employee
self-link repair retains its existing service-verified identity predicate, with
a narrow lexical permit for that INSERT, and still requires exact WRITE.

No input-activity signal is used. The 20-second renewal, 60-second TTL,
600-second clock-skew grace and 30-minute idle policy are unchanged. A slow UI
with a renewing worker retains authority. If the worker cannot provide a valid
lease observation within the existing validity boundary, local persistence stops;
this does not force-release the remote lock.

## Maintenance permits

Permits are lexical, per-thread, exact-path and exact-incarnation. They expire
when their context exits; leaked handles cannot commit under a later context.

| Permit | Operations | Required proof |
| --- | --- | --- |
| initialize | Persistence PRAGMA for a fresh container | Initialization lifecycle, no bound editing transaction, journal replaceability |
| bootstrap | DML only on users, roles, permissions, role_permissions | Explicit first-run script and empty workspace checks; no bound collaboration |
| migration | Existing bundled DDL/revision/data migration | Startup before collaboration, or pre-swap replacement proof plus active installed-runtime maintenance fence |
| checkpoint | WAL checkpoint only | Active process maintenance fence; pending journal is allowed because preservation must remain possible |

Maintenance never admits an ordinary READ action as WRITE. Checkpoint permits
do not bypass pending work. No permit changes journal status to CLEAN.

## Denial and recoverability

On loss, the existing OPEN journal retains its base, key reference, signed
captures and unaccepted committed data. A protection marker records why authority
was lost; it is never an authority grant. No automatic reset, replacement,
checkpoint, remote release or journal cleanup happens inside DB hooks.

Before admitted business SQL runs, an AES-GCM encrypted intent receipt is fsynced
under the existing recovery root, outside runtime/Git. It records SQL, bound
parameters, session and incarnation. This preserves admitted in-flight intentions
even when a service subsequently rolls back/closes after denied commit. Production
uses the existing protected SQLCipher workspace key; plaintext development uses a
private local operational key. No row values/passwords are written in plaintext.

Receipts are evidence for explicit recovery, **not an automatically replayable
transaction log**: nondeterministic expressions, triggers, partial batches and
row-level business validation require manual reconciliation. ORM changes denied
before any DML are unauthorized attempted changes, not accepted database edits.
Existing committed DB/WAL remains protected independently of these receipts.

Runtime login activity is separate local operational telemetry, never a shared
credential/role authority or recovery-cleaning shortcut. Five failed attempts /
15-minute local lock behavior is retained; an authoritative persisted lock is
also respected. `users.last_login` and legacy-hash upgrades are no longer written
by READ login. Cross-machine centralized login throttling was not a reliable
publication mechanism and is outside this task.

## Validation and limits

`test_e1b2b_local_mutation_authority.py` uses synthetic SQLCipher files and local
bare Git repositories; it covers all 16 requested areas along with the existing
E1B-1 and E1B-2A suites. Fixtures stage schemas/data away from the live boundary;
legacy unmanaged-writer cases remain explicit to test defense-in-depth recovery.
Windows native ownership tests still assert that registry removal follows native
close, and do not require the public guarded handle to be the raw driver object.

| Requested case | Main evidence |
| --- | --- |
| 1, 13 authorized service / Finance / Student | authorized service + permission floor; Finance service; existing domain regression suite |
| 2, 3 READ / WAITING | matrix over service, ORM, DBAPI, bulk UPDATE and DELETE |
| 4, 5 lost before commit / uncertain renewal | flush → changed real-Git owner → denied commit; UNKNOWN/exception/renew-denied matrix |
| 6 old raw session | repeated cached statement after changed remote owner |
| 7, 8 bulk / DBAPI | Core UPDATE/DELETE, CTE, executemany, SQL COMMIT, savepoint RELEASE |
| 9 late callback | denied post-Finish service write with CLEAN receipt and unchanged accepted DB |
| 10 bootstrap/migration | real bundled Alembic chain plus account-only seed permit |
| 11 backup/restore | READ snapshot; pending restore/migration blocked; existing restore/Windows handle suites |
| 12 WAL/journal | committed WAL retained, denied uncommitted update captured as encrypted intent, recovery capture verified |
| 14 thread race | worker flush barrier → loss observation → worker commit denied |
| 15 reconnect | revoked/expired sessions cannot finish, recover or restart over pending work |
| 16 normal Finish/report | real SQLCipher/Git publication plus all #526 reporting scenarios |

See [two-machine UAT](E1B2B_TWO_MACHINE_UAT.md). Automated checks do not replace
that manual evidence. Windows CI status belongs to the PR/run, not this document.

## Explicit E1C release blockers

- No durable ownership epoch or atomic coupling between lock-ref authority and
  MAIN/data publication. E1C remote publication fencing is **not solved**.
- Offline/unmodified clients, arbitrary external SQLite/SQLCipher writers and
  deliberate Python/native-hook tampering are outside in-process enforcement.
  Their actual mutations still require E1B-1 recovery detection/preservation.
- No instant fencing after an undetected remote change inside a still-valid
  observation. The accepted local bound is the existing lease; failed/unknown
  observations stop admission immediately when delivered.
- Optional Windows broker needs explicit distributed WRITE authority forwarding
  before service-side mutations can be enabled; authentication/SID tokens alone
  must not authorize writes.
- Multi-client rollout/version floor, adversarial publication races, power-loss
  coverage, durable remote epoch and controlled emergency revoke prerequisites
  remain required. No Admin force-release or auto-merge is introduced.
