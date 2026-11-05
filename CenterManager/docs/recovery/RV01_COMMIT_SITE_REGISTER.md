# RV-01 — Explicit Commit-Site Review Register

**Source:** verified Windows AST scan run 41970659872, `rv01-mutation-sites.json` (446 Python files, 1,099 candidates, 137 explicit commit calls, 0 parse errors). **Scope:** all explicit `commit()` syntactic sites identified by that scanner; dynamic/implicit commits, native DBAPI, SQLAlchemy Core mutating execute, bulk writes and file-only changes are separately tracked.

This is a **path + owning method review register**. Classification is based on source and validated method names, not automatic proof every branch emits a same-transaction Change Log. A future RV-02 runtime/CI coverage test must assert this per business method.

## A. Business/admin commit sites: 116, all enumerated

| Service | Explicit sites (line:method) | RV-02 treatment |
| --- | --- | --- |
| admin_data_reset | 240:reset | P0 privileged bulk reset; in-transaction audit present |
| assessment | 127:create_assessment, 231:update_assessment, 253:delete_assessment | P0 academic business event |
| attendance | 386:_save_session_attendance_atomic | P0 one grouped sheet operation |
| class | 239:create_class, 494:update_class, 629:archive_class, 658:restore_class | P0 class + multi-enrollment archive |
| employee_admin_management | 118:reopen_period, 170:delete_registration, 220:delete_employee | P1 existing transactional audit |
| employee_document | 181:upload | P0 file-first staged upload |
| employee_schedule | 162:add_rule, 191:update_rule, 203:delete_rule, 227:add_exception, 239:delete_exception, 465:add_week_assignment, 478:delete_week_assignment, 511:seed_week_from_registration, 550:seed_week_from_template, 576:publish_week, 592:freeze_week, 636:reopen_week_for_override | P1 partial transactional audit (week lifecycle only) |
| employee_service | 221:create_employee, 275:create_employee_with_account, 299:link_existing_user, 317:update_status, 351:update_employee | P1 staff and security-sensitive IDs |
| employee_work_registration | 91:create, 99:update, 109:delete, 118:submit_week, 124:accept, 130:reopen, 137:set_submission_deadline, 144:close_week | P1 transactional audit for inspected paths |
| employee_working_time | 98:create_booking, 106:check_in, 116:check_out, 127:update_booking, 136:delete_entry, 145:approve, 155:lock_month | P1 payroll/time data |
| enrollment_reconciliation | 239:mark_legitimate, 347:reconcile | P0 fee/contract data, existing audit |
| enrollment | 487:enroll, 593:freeze, 645:resume, 807:restore, 882:_transition | P0 conditional audit gaps |
| enrollment_transfer | 358:transfer | P0 group linked enrollment history |
| expense | 258:create_expense, 416:update_expense, 460:reimburse_expense, 490:delete_expense | P0 finance, existing audit |
| finance_attachment | 223:add_attachment, 250:remove_attachment | P0 attachment metadata audit present, file-before-commit |
| finance_period | 168:configure, 196:deactivate | P0 period reporting context |
| financial_settlement | 330:_save, 423:reopen | P0 pending verify all draft/confirm branches |
| income | 590:create_income, 749:create_tuition_payment_with_credit, 925:reconcile_tuition_enrollment, 1020:update_income, 1055:void_income, 1081:delete_income | P0 existing transactional audit, grouped tuition-credit event |
| parent | 122:create_parent, 219:update_parent, 246:delete_parent | P1 privacy |
| permission | 175:create_role, 197:update_role, 213:delete_role, 344:change_password, 367:create_user, 385:update_user_role, 404:delete_user, 416:set_user_active, 463:create_user_with_temp_password, 493:reset_user_password, 523:update_user, 535:unlock_user | P0 security metadata only; current best-effort audit after commit; mislabeled role change |
| session_note | 101:create_note, 184:update_note, 195:delete_note | P0 teaching progress; redact text |
| session | 140:create_session, 262:update_session, 286:cancel_session, 313:delete_session | P0 accrued tuition source |
| student_document | 68:upload_document, 96:delete_document | P0 file/DB atomicity |
| student_highlight | 35:create_highlight, 56:update_highlight, 66:delete_highlight | P1 teacher content; redact free text |
| student_note | 56:create_note, 99:update_note, 110:delete_note | P1 confidential note |
| student | 123:create_student, 182:archive_student, 214:activate_student, 256:set_profile_image, 349:update_student, 392:delete_student, 425:restore_student | P0 after-commit timeline gap; file ordering |
| teacher_assignment | 60:assign_teacher_to_class, 97:unassign_teacher_from_class | P1 direct commit |
| teacher_document | 89:upload_document, 136:delete_document | P1 file-first |
| teacher_service | 126:create_teacher, 267:update_teacher, 296:delete_teacher, 321:restore_teacher | P1 direct commit |
| tuition_adjustment | 247:refund, 299:credit_adjustment | P0 audited, monetary idempotency |

**Count invariant:** 30 business/admin service modules, **116 explicit commit call sites**. Note that `employee_service.get_current_employee:145` is excluded here as an authorized identity repair, and `permission_service.authenticate_user:301,314` as authentication maintenance. A single method can have multiple conditional commit paths, and nested operations can have additional implicit flushes.

## B. Explicit non-business commit sites: 21, all enumerated

| Class | File and line:method |
| --- | --- |
| SYSTEM (10) | `database/engine.py:450 initialize_runtime_database`; `database/guarded_dbapi.py:226 commit,250 __exit__`; `database/seed.py:131 seed_roles_and_permissions`; `database/session.py:211 session_scope`; `database/upgrade_gate.py:147 create_consistent_snapshot`; `database/wal_safety.py:65 _checkpoint_runtime_database`; `platform/backup/backup_service.py:153 _copy_encrypted_sqlite_snapshot`; `platform/protected_data_service/broker.py:113 create_backup`; `platform/workflow/publish_workflow.py:236 execute` |
| DERIVED TIMELINE (5) | `services/class_timeline_service.py:57 log_event`; `services/expense_timeline_service.py:48 log_event`; `services/teacher_timeline_service.py:57 log_event`; `services/timeline_service.py:67 log_event,84 delete_event` |
| REPORT (2) | `services/report_service.py:271 delete_report,284 delete_report` — only exclude after verifying regenerability |
| AUTH LOGIN (2) | `services/permission_service.py:301,314 authenticate_user` — security policy, not ordinary editing |
| IDENTITY REPAIR (1) | `services/employee_service.py:145 get_current_employee` — special mutation permit |
| AUDIT HELPER (1) | `services/audit_service.py:69 record` — a separate audit transaction, not business mutation |

**Classification caution:** `database/session.py:211 session_scope` is a *generic wrapper* that may commit a real business transaction by callers. It is not itself a business event, but RV-02 must trace every caller using that wrapper. Similarly `guarded_dbapi.py` intercepts SQL and records **intent**, not committed business operation.

## C. Raw SQL and filesystem must not be inferred from commit counts

- `repositories/admin_data_reset_repository.py:178` performs SQLAlchemy Core `execute(delete(table))`; the containing `services/admin_data_reset.py:240` owns the SQLCipher commit. This is one privileged grouped destructive operation, **not** one event for every table.
- `database/guarded_dbapi.py:121-196` writes encrypted *pre-execution mutation intents* to the recovery sibling; a statement may be rolled back. Never present those intents as committed changes.
- Finance, employee, student and teacher document paths can write filesystem bytes before metadata commit; outbox must carry safe file provenance and recovery capture must preserve bytes. A failed commit may leave orphan attachments.
- Five publication-related AST sites must honor existing exact session/OID fencing. A write under older commit A cannot be automatically published after MAIN reaches A+10.
- Config/deployment-wizard writes are file-only and may contain Git credentials; exclude secrets from business Change Log and review provenance separately.
- 583 generic `.connect` call sites are not evidence of 583 DB connections; many are PySide UI signal wiring.

## D. RV-01 handoff to RV-02 and acceptance

- **Verified:** AST scan completed on Windows with no parse errors; every **explicit** commit site is allocated once to an owner-based bucket above. Transactional audit gaps and common crash windows are documented.
- **Open safety gate for RV-02:** for every business method listed in A, produce tests proving domain event and mutation commit or rollback in the same SQLCipher transaction. Review non-commit mutating SQL, implicit ORM operations, triggers, native DBAPI and dynamic callbacks separately. No claim that user-visible Recovery Log is exhaustive until these gates pass.
- **Open design review:** require founder acceptance for privacy, log retention, schema/legacy EXE compatibility, startup nonblocking requirements and safe file provenance.
- **No production behavior changed in RV-01.** Avoid migrating user data until RV-02's regression gates exist.
