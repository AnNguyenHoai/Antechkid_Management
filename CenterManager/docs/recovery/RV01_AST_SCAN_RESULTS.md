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
