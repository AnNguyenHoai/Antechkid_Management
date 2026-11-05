# RV-01 — Measured Windows CI AST Inventory (2026-11-05)

Source workflow: [Pytest Suite run #41970659872](https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41970659872), shard 0. Artifact: `rv01-mutation-sites-41970659872` (`rv01-mutation-sites.json`); schema `rv-01-audit-static-v1`. Scanner: `CenterManager/tools/audit_recovery_mutations.py`. Snapshot: PR #598 head at `e34deffcf3460f1941dbdb1ae06d397892e994f1`, which differs from later changes only in RV-01 docs. Scanner step completed successfully and artifact was created; this fact does **not** assert all pytest shards finished.

## Actual scan output, not estimates

- Python files parsed under the declared services/repositories/ui/database/platform/events roots: **446**.
- Candidate call sites: **1,099**; Python parse errors: **0**.
- Category frequency:

| Category | Sites | Reviewer treatment |
| --- | ---: | --- |
| CONNECTION_REVIEW | 583 | Heavy false positives: Qt signal `*.clicked.connect`, etc.; only actual SQLCipher/SQLite connection opens are DB boundaries. |
| DATABASE_COMMIT | **137** | P0: trace the transaction owner and outbox point; **127 in 36 service files**, 7 database-level and 3 platform-level. |
| FILE_REPLACE_REVIEW | 91 | **51 `os.replace`** candidates represent possible atomic file installs; remaining generic `replace` includes datetime/string operations. |
| FILE_DELETE | 76 | Classify cleanup/rollback vs authoritative attachment deletes. |
| DATABASE_FLUSH | 74 | Most are within larger transactions; flush alone is not committed data. |
| FILE_COPY | 31 | Attachments, snapshots, Git working copies and bootstrap must be distinguished. |
| SQL_EXECUTE_REVIEW | 28 | Includes SELECT, retry-policy callbacks and true SQL; inspect target and SQL before classifying. |
| AUDIT_IN_TRANSACTION | **24** | Source calls to `record_in_session`, not 24 independently verified covered business commands. |
| SQL_MUTATION_LITERAL | 20 | Includes PRAGMA/schema/security checks; a lexical prefix is only a candidate, not evidence of changed business data. |
| FILE_WRITE | 11 | Config/Git/metadata and UI exports; exports may be derived artifacts. |
| FILE_DELETE_REVIEW | 9 | Many `list.remove` etc.; not assumed filesystem deletes. |
| AUDIT_POSSIBLY_SEPARATE | 6 | Includes PermissionService best-effort audit and an unrelated login `local.record`. |
| GIT_PUBLICATION | 5 | Review protected MAIN publishers and recovery publisher in existing E1B/E1C scope. |
| CONFIG_WRITE | 4 | Actual config save and deployment-wizard credential/config paths; do not mirror secrets. |

These frequencies sum to exactly 1,099. The scanner is intentionally recall-oriented and emits false positives. It is **not** a mutation-authority enforcement or a proof of successful recovery-log coverage.

## Highest-risk commit-site groups (127 service sites)

| Service module | Commit sites | Evidence / RV-02 ownership |
| --- | ---: | --- |
| `permission_service.py` | 14 | Security/admin account/role/password; best-effort post-commit audit; check legacy auth-only commits separately |
| `employee_schedule_service.py` | 12 | Direct rule/assignment commits and in-session audit for publish/freeze/reopen |
| `employee_work_registration_service.py` | 8 | In-session audit helper; verify each action and grouped IDs |
| `employee_working_time_service.py` | 7 | Booking/check-in/out, approval/lock; no matching in-session audit observed in examined service |
| `student_service.py` | 7 | Create/edit/archive/delete/profile: post-commit timeline event does not prove recovery completeness |
| `employee_service.py` | 6 | Employee writes plus specially authorized identity repair |
| `income_service.py` | 6 | Transaction-bound audit exists in inspected paths; add session/op/publish provenance |
| `enrollment_service.py` | 5 | Mixed conditional/partial transactional audit (ordinary ENROLLED without discount lacks specific CREATE audit) |
| `class_service.py`, `expense_service.py`, `session_service.py`, `teacher_service.py` | 4 each | Session completion changes derived tuition; class archive groups enrollments |
| `assessment_service.py`, `employee_admin_management_service.py`, `parent_service.py`, `session_note_service.py`, `student_highlight_service.py`, `student_note_service.py` | 3 each | Academic, admin, identity and freeform note changes; privacy-aware summaries |
| Remaining 18 service modules | 1–2 each | See downloadable full site artifact; finance/attachments/report/timeline/tuition/admin data reset classification is necessary |

Service count includes **timeline and report commits**, which must be classified DERIVED where proven. Database and platform commit calls include low-level connection wrappers, bootstrap, backup, snapshot and WAL checkpoint, not 10 independent user actions.

## Manual review rules, priority and release decision

1. For all **137 commit call sites**, identify runtime path and caller. Classify as BUSINESS, SECURITY, DERIVED, SYSTEM or CONNECTION_WRAPPER. Do not insert business outbox into database authorizer, WAL checkpoint, audit helper or report regeneration.
2. For the **24 transactional audit call sites**, confirm every public method path invokes the audit in the same committed transaction; the same service may contain both covered and uncovered operations.
3. For **file operations** (31 copy, 76 unlink, 51 `os.replace` plus other candidates), identify the authoritative attachments vs regenerable cache or rollback backup. File metadata and file bytes cannot be made a SQLCipher-only atomic transaction.
4. For **5 Git publish call sites**, check existing exact remote OID CAS and session fencing; these should not create independent business events.
5. SQL execute/flush inspection is needed for direct Core/raw SQL bypasses; static candidate count is not a substitute for the existing E1B-2B authority gate or runtime tests.
6. User-facing Recovery Report must explicitly say **potentially unaccepted**, never “lost”; legacy clients that did not write outbox get **coverage unknown**. The existing encrypted pre-execution mutation-intent log must not be presented as committed operations.

## RV-01 review outcome

**Evidence gate passed:** the static scan ran on a Windows GitHub runner, parsed all 446 configured Python files without syntax errors and produced a verifiable candidate artifact.

**Not yet proven:** every dynamic dispatch, SQL trigger, native DBAPI action, background callback, alternate DB provider and schema compatibility behavior. Privacy/retention and release acceptance still require review. The RV-01 design can be approved as input to RV-02 without pretending the entire application has committed-event coverage. Issue #593 remains OPEN until founder and CI/QA review criteria are satisfied.


## Preliminary owner-based triage of ALL 137 explicit commit calls

Using the full verified artifact (not just selected service snippets), the 137 explicit `commit()` call sites were classified once by containing file/function:

| Bucket | Commit sites | Treatment |
| --- | ---: | --- |
| **BUSINESS_CANDIDATE** | **116** | The key RV-02 transaction-bound outbox implementation/review queue; verify each path and actor. Includes privileged admin data reset, finance, academic and employee actions. |
| **SYSTEM_INFRASTRUCTURE** | **10** | 7 in `database/`, 3 in `platform/`; verify maintenance provenance, not user business events |
| **DERIVED_TIMELINE** | **5** | `timeline_service` (2), `class_timeline_service` (1), `teacher_timeline_service` (1), `expense_timeline_service` (1); these may still be stored, but are not the original business edit |
| **DERIVED_REPORT** | **2** | `report_service.delete_report()`; classify report metadata/file semantics before exclusion |
| **AUTH_LOGIN_SPECIAL** | **2** | `permission_service.authenticate_user()`; protected login uses local activity policy; legacy changes differ, no ordinary business event |
| **IDENTITY_REPAIR_SPECIAL** | **1** | `employee_service.get_current_employee()` with verified identity repair permit; classify maintenance vs business |
| **AUDIT_HELPER** | **1** | `audit_service.record()`, a separate log writer; its commit must not be double counted |
| **TOTAL** | **137** | Every explicit commit candidate in the artifact is allocated once; **this is a preliminary owner-based triage, not proof 116 paths are fully covered**. |

This reduces the **priority human review queue to 116 explicit business commit candidates** plus selected special/security/attachment paths. The remaining 962 non-commit candidates include **74 flush sites, 31 file copies, 51 explicit `os.replace`, 76 file unlink sites and 5 Git publisher references**, and must be reviewed under their separate safety contracts. In particular, many `connect` hits are GUI signal connections rather than SQLCipher connections.

### Verified distinction between direct and indirect audit calls

There are 24 syntactic `record_in_session()` sites. Some are **shared helpers**, e.g. `IncomeService._record_audit`, `ExpenseService._record_audit`, `EmployeeScheduleService._audit_week` and `EmployeeWorkRegistrationService._audit`. Thus a naive count of 24/116 is **not** a coverage percentage: one helper can cover many operations and other calls are conditional. Per-method branch tests and actual transaction relationships are mandatory in RV-02.

**Implementation acceptance criterion:** Every BUSINESS_CANDIDATE function either emits a same-transaction outbox event, has a source-proven in-session audited equivalent wired with session/op IDs, or is explicitly documented as an approved exception with test. The separate 10 infrastructure commit sites must never be instrumented as ordinary human edits.
