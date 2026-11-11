# CENTERMANAGER — PRODUCT & SYSTEM REQUIREMENTS (CANONICAL INDEX)

**Document ID:** CM-REQ | **Version:** 1.0 | **Updated:** 2026-11-11
**Source baseline:** `main_coursefee` @ `cd61814c03c4224e54b51cf7fa8a57fd6db3b43e` (includes PR #651, #652, #653).
**Product:** AnTechKids CenterManager — Windows portable desktop; **current product: course-based tuition**.
**Paired document:** [CENTERMANAGER_BUSINESS_WORKFLOWS.md](CENTERMANAGER_BUSINESS_WORKFLOWS.md).

> **READ-FIRST RULE (mandatory for every maintenance / feature / QA task).** Before modifying ANY CenterManager implementation, developer or AI agent MUST read this requirements file and its paired workflows file; identify affected requirement IDs and workflow IDs; examine the cited domain specifications/current source and tests; write an impact/regression checklist; and only then edit. In the PR state whether each contract is preserved or changed intentionally. Never silently change a requirement to fit code. These documents are a **domain-level index and change-control contract**, not a replacement for the detailed approved specifications or actual migration/permission code.

## 0. Evidence, precedence, and interpretation

- **[CONFIRMED]** denotes an approved product decision or behavior directly evidenced in the current source/docs. **[CODE-OBSERVED]** documents implementation that may still contain defects. **[VERIFY]** marks behavior that needs integration/Windows UAT or explicit owner confirmation. **[PROPOSED]** is not permission to change production behavior.
- Priority: (1) explicit current PO decision, (2) approved current domain amendment, (3) approved domain specification, (4) assigned issue/accepted change, (5) architecture contract, (6) source and regression tests. Where two authorities disagree, document the conflict; do not improvise. Follow root `AGENTS.md` and `docs/AI_COLLABORATION_PROTOCOL.md`.
- Accounting `FINANCE_WALLET_V2_DOMAIN_SPEC.md` remains authoritative **except its superseded tuition-per-FinancePeriod sections**. `docs/finance/FINANCE_WALLET_V2_TUITION_BOUNDARY.md` explicitly supersedes those sections. Inspect `services/tuition_policy.py`, `tuition_accrual_service.py`, `outstanding_service.py` for current tuition policy.
- The **source branch** `main_coursefee` and the **private database Git branch** (currently `main`) are independent. No code may infer database schema/product identity or force a database branch from the source branch name. Do not import monthly-tuition migration assumptions from another product/repository.
- The earlier migrations/branch-guard regression after commit `a747672fef350b61e08d3b9f6264d7fe75c2f7cd` caused startup failures; the user confirmed an EXE rebuilt from that SHA worked. The current documentation baseline is later and includes the three narrowly scoped Student/Finance PRs. Before any release, verify packaged EXE source SHA, migration head, and actual encrypted DB compatibility.
- Current docs describe intent/contracts and code-read observations, **not** a proof that every screen, role or machine has passed production UAT. Do not claim CI/EXE acceptance from this document.

## 1. Product scope, actors, architecture

| ID | Requirement / non-negotiable contract | Source owner |
| --- | --- | --- |
| SYS-001 | Windows desktop, packaged portable EXE/ZIP with Python/PySide6 UI; runtime assets/config located by `core/paths.py`, without production data/secrets embedded in release. | `build_release.py`, `core/paths.py` |
| SYS-002 | Workspaces: Home, Student, Class/Teaching, Teacher, Employee, Finance, Administration; shared navigation/events. Each owns its domain; Home/dashboard is a read projection. | `ui/main_window.py`; `ui/*_workspace/*shell.py` |
| SYS-003 | UI calls services; services own orchestration/validation; repositories own queries/mutations via RepositoryProvider; models own persisted shapes. No SQL/transaction/financial formula in UI. | `docs/Bussiness/ARCHITECTURE_V2.md`, `repositories/provider.py` |
| SYS-004 | Roles are capability-based (Admin, Manager, teacher, employee/reception and configurable roles are functional examples; exact entitlements are configured, **not assumed**). Any mutation needs WRITE authority + permission + domain-state guard. UI hiding a button is not an authorization guarantee. | `models/permission.py`, `services/permission_service.py`, permission guards |
| SYS-005 | Personal data of children, parents and employees must be protected. Logs and exports must not leak tokens, passwords, database keys, unredacted Git remotes, or unnecessary sensitive paths. | `core/logging.py`, security services |
| SYS-006 | Core business state in encrypted SQLite/SQLCipher; schema via Alembic; attached documents stored as files plus metadata. No schema change without separate migration/backup/test plan. | `database/`, `migrations/`, `docs/DATABASE_DESIGN.md` |
| SYS-007 | History/audit remains interpretable: never silently rewrite old charges, ledger entries, enrollment contracts, archived records or payment provenance. | domain services and audit logs |
| SYS-008 | Finance/accounting aggregates must be complete, not computed from only a displayed page or arbitrary limit. Read operations must not implicitly mutate business data. | finance repositories/services |
| SYS-009 | Avoid speculative hosted coordinator, server, real-time multiwriter database merge or broad architecture refactor in normal maintenance. | configured Git-only policy |

## 2. Git-only collaboration, source of truth, security and lifecycle

| ID | Requirement |
| --- | --- |
| COL-001 | Private **database Git repository MAIN** is the authoritative accepted dataset. A downloaded/validated MAIN is used to materialize the **single active runtime DB**; previous unpublished local files are not alternative authorities. |
| COL-002 | Startup resolves configuration and SQLCipher/DPAPI key, authenticates Git remote identity, fetches/checks current MAIN and constructs runtime before login. Source and DB Git branch names remain independent. |
| COL-003 | Startup must protect unsent local artifacts before authoritative replacement; keep evidence and provide review notice. A historical Recovery case **by itself** is advisory, not an instruction to auto-publish or merge old data. Never discard an unverified local DB/WAL/attachment. |
| COL-004 | When MAIN cannot be authenticated or runtime SQLCipher/schema verified, do not silently treat stale local data as authoritative or grant WRITE. Any offline READ fallback is explicitly read-only, evidence-verified and subject to current platform guards. Security/integrity failures can still prevent safe startup; do not interpret “nonblocking Recovery notice” as license to bypass those gates. |
| COL-005 | Collaboration has READ and controlled WRITE/edit session. One accepted writer at a time via remote ownership/lease/queue/heartbeat; no parallel free-form multi-writer merging. |
| COL-006 | Start Editing verifies ownership, accepted MAIN identity and mutation admission before allowing domain writes. No UI role alone bypasses the lock. |
| COL-007 | Finish Editing atomically completes local transaction/capture checks and publishes via guarded Git/CAS; verify remote acceptance; release WRITE. Failed or uncertain publication retains recovery evidence. Never report unverified success. |
| COL-008 | Recover/review is a **manual reconciliation workflow**: show unresolved evidence on startup, allow Reviewed acknowledgment (suppresses the same notice) or Skip (remains pending). Do not automatically replay historical business changes or publish legacy databases. |
| COL-009 | Runtime credentials/database keys use machine/workstation protected provisioning (DPAPI and encrypted bundle as implemented); tokens never placed in source, docs, generic logs or build artifacts. |
| COL-010 | Git MAIN is data authority, **not** permission to overwrite another editor's work; independent remote OID/CAS and WRITE lease checks remain required. Do not introduce bypass paths from backup/admin/recovery routines. |
| COL-011 | Version numbers have distinct meanings: source release SemVer, runtime publication/version counter, Git commit OID and database Alembic revision. Never use one in place of another. A new client-only check cannot fence an old EXE retaining Git credentials. |
| COL-012 | Windows backup paths, long Vietnamese filenames, file locks, WAL/SHM, interrupted copies and checksum mismatch are release-relevant safety cases. Any backup workaround must preserve verification and originals; no “skip backup to unblock startup” fix. |

**Principal code:** `app.py`, `platform/bootstrap/`, `platform/sync/startup_sync.py`, `platform/synchronization/`, `platform/collaboration/`, `services/write_transaction.py`, `platform/write_recovery.py`. **Workflow:** WF-01 through WF-05 in paired document.

## 3. Student, family and learning profile

| ID | Requirement |
| --- | --- |
| STU-001 | Student has stable ID and human student code (typically `HS...`), names, optional DOB/gender/level/notes and lifecycle status. Parent/contact relationships are kept through Student/Parent services. |
| STU-002 | Student lifecycle distinguishes ACTIVE, ARCHIVED, and deletion/soft-delete. Archive does not erase student history, Enrollment, financial obligations or audit trail; restore/reactivate is explicit. |
| STU-003 | Operational Student List **defaults to ACTIVE**; Student Overview **defaults to ACTIVE**. User can explicitly choose All or Archived. Filter/clear semantics must be visible and consistent; this is a display filter, not a destructive data exclusion. |
| STU-004 | Historical financial/debt, reports and enrollment history must still include archived participants where business semantics require it; “Active default” must never secretly reduce accounting totals. |
| STU-005 | Student List search/filter/sort/pagination is server-backed; filter, count and displayed rows must have the same scope. Navigation to Student Detail preserves exact Student identity. |
| STU-006 | Student Detail includes related enrollments, attendance/learning history, assessments, notes/timeline and finance projections. Operations use owning services/read models rather than duplicate calculations. |
| STU-007 | Import accepts **.xlsx** template with header order: Code, Full Name, Preferred Name, Date of Birth, Gender, Status, Level, Notes. Prevalidate before mutation (headers, required name, code format/duplicates, status, date); present row-level preview/errors and require operator confirmation. No silent bulk overwrite. |
| STU-008 | Import can preserve a supplied valid unique Student code; absent code uses canonical generator. Existing codes are not overwritten; keep explicit duplicate/error report. The import **does not automatically create enrollments, tuition, debt or wallet entries**. [CODE-OBSERVED] Per-row creation may partly succeed after user confirmation if a runtime write fails; atomic all-or-nothing import is **not** promised. |
| STU-009 | Student export modes: **Filtered** (all matching server pages, not only visible page), **All ACTIVE** (excludes archived), and **Selected**. Stable sorting, visible scope, reasonable failure if records change mid-pagination. Excel/CSV uses UTF-8-compatible encoding as applicable. |
| STU-010 | Import/export must require correct permissions; export should work in authorized READ without acquiring WRITE, import requires WRITE and service permission. Avoid exposing student PII through logs or unauthorized paths. |
| STU-011 | Dashboard/Analytics/Overview are projections; totals and attendance are calculated from canonical services, not independently from only the page currently displayed. |
| STU-012 | Parents/guardians are linked records (contact, identity, relationship); avoid treating one parent contact as a unique Student identity or overwriting other students sharing a guardian. |

**Principal code:** `services/student_service.py`, `student_import_service.py`, `student_export_service.py`, `student_overview_service.py`, `repositories/student_repository.py`, `ui/student_workspace/`; **Workflows:** WF-06, WF-07.

## 4. Class, course, Enrollment, Session and teaching

| ID | Requirement |
| --- | --- |
| CLS-001 | Class includes identity/code, lifecycle, course/tuition contract and planned sessions, cadence, assigned teachers and enrolled students. No session/roster mutation on an archived class unless explicitly restored. |
| CLS-002 | Enrollment is a **separate historical contract identity** linking one Student to one Class for a session/date range. Do not identify tuition by Student+Class alone; repeated/withdrawn/rejoined Enrollments remain distinct. |
| CLS-003 | Enrollment start/end session, pricing preview, discount snapshot, effective range and overlapping-contract checks are handled by EnrollmentService. Entry mid-course uses eligible remaining course sessions, not month/FinancePeriod guesswork. |
| CLS-004 | Enrollment statuses/transitions (enroll, withdraw, complete, restore, freeze/resume if allowed) are validated; withdrawal boundary and historical eligibility affect roster and tuition. No arbitrary deletion of paid/owed history. |
| CLS-005 | Class archive requires finance-impact preview/confirmation where implemented; historic enrollments and outstanding debt remain collectible, with separate credit/refund handling. Archived class must not vanish from debt/financial history. |
| CLS-006 | Class teacher assignment and active teacher selection are controlled by Class/Teacher services; class detail links students, session schedule, teacher and attendance. |
| SES-001 | Session belongs to one Class and has session number/date/time/status/title; create/update/cancel/delete use SessionService and permitted state transitions. |
| SES-002 | Session completion and planned/enrollment session boundary determine which sessions can accrue tuition; a canceled session cannot be treated as a completed billable teaching session. |
| ATT-001 | Attendance is saved per student/session with valid roster based on Enrollment historical coverage, not simply current ACTIVE roster. Bulk per-session saves must preserve atomicity and service authorization. |
| ATT-002 | Attendance statuses (including present, absent, late, excused where supported) and missing-attendance fallback are interpreted by the **versioned BillableSessionPolicy**, not a UI rule. |
| ATT-003 | Attendance corrections on historical sessions obey eligibility, freeze/withdrawal and completed-session rules and must refresh student/class projections and relevant accruals. |
| TEA-001 | Teaching note, progress, assessment and student session feedback are separate domain concepts. Keep UI save/cancel semantics explicit; avoid unreviewed background writes/autosave. |
| TEA-002 | Student assessments/timeline/report generation are related but distinct: primary saved teaching state is authoritative; derived reports/events must not cause a committed write to appear failed merely from best-effort delivery failure. |

**Principal code:** `services/class_service.py`, `enrollment_service.py`, `session_service.py`, `attendance_service.py`, `tuition_policy.py`, `ui/class_workspace/`. **Workflows:** WF-08 through WF-12.

## 5. Course-based tuition, credit and debts — highest-impact domain

| ID | Requirement |
| --- | --- |
| TUI-001 | **This edition is COURSE-BASED**, not monthly or quarterly billing. A separate product/repository holds monthly tuition experiments. No automatic monthly charge schedule or monthly schema migration in this edition. |
| TUI-002 | FinancePeriod is an **accounting / settlement** period; NOT a course duration, Enrollment billing cycle, fee source, or session allocation calendar. Do not reintroduce superseded `Class.fee per FinancePeriod` formulas. |
| TUI-003 | Class course fee and planned sessions determine Enrollment agreed-course-fee snapshot and unit fee for the contract's effective session range; agreed fee override/discount is explicit and validated by EnrollmentService. |
| TUI-004 | Tuition accrual is by eligible **completed, billable sessions** as of cutoff using the Enrollment's stored policy version, with attendance-aware exceptions where configured. Do not charge uncompleted/center-canceled sessions as completed sessions. |
| TUI-005 | Tuition Income is attributable to an **exact Enrollment ID**. Payment date determines accounting FinancePeriod/wallet, while Enrollment ID determines academic tuition paid. These dimensions must not be conflated. |
| TUI-006 | Enrollment balance = accrued eligible tuition minus qualified payments and adjustments under canonical service rules. Distinguish **OWED**, **PREPAID**, **SETTLED**, unresolved/unconfigured pricing; never implicitly net across Students/Enrollments. |
| TUI-007 | Student withdrawal, archived Student/Class, course completion, repeat Enrollment and historical debt collection must preserve original contract/payment lineage. A withdrawn/archived Enrollment may still have collectable debt. |
| TUI-008 | Voided/deleted financial records, refunds, credits, fee amendments and paid advance adjustments must follow domain rules, keep audit/provenance and not silently rewrite historical accrual. |
| TUI-009 | Outstanding has multiple read scopes (open receivables, course balances, period activity); title/scope must clearly distinguish lifetime Enrollment balance from period cash movement. A period-scoped screen must not mislabel lifetime accrued/paid values as that period's new charge. |
| TUI-010 | A missing/unresolvable contract is an exception requiring explicit reconciliation, never assumed zero debt or “paid”. |
| TUI-011 | Any proposed tuition policy change requires impact tests for 8/9/10 monthly calendar sessions (as report periods only), mid-course joining, center cancellation, student absence/makeup, freeze, withdrawal, credits/refunds, cross-period prepayment and legacy contracts; do not implement monthly billing under this requirement. |

**Principal code:** `services/enrollment_service.py`, `tuition_policy.py`, `tuition_accrual_service.py`, `outstanding_service.py`, `income_service.py`, `tuition_adjustment_service.py`. **Workflows:** WF-13 through WF-16.

## 6. FinancePeriod, Income, Expense, Wallet, Settlement, attachments

| ID | Requirement |
| --- | --- |
| FIN-001 | All Finance views share an explicitly selected **canonical FinancePeriod** with exact start/end; selector identity is not merely month/year. Finance Dashboards, Income, Expense and Settlement use consistent period context. |
| FIN-002 | Realized ACTIVE Income and realized COMPLETED Expense belong to one FinancePeriod based on actual posting date and cannot be future-dated. PENDING/personal-advance Expense has a distinct policy. |
| FIN-003 | Canonical wallets are **CASH** and **BANK** for realized flows; normalize permitted aliases through owning services, never guess unknown historical methods. |
| FIN-004 | Finance transaction writes require collaboration WRITE, correct capability and period-not-closed guard. Posted/voided income and realized/pending Expense status have different wallet effects; mutation has audit trail. |
| FIN-005 | Settlement computes full expected balances by Wallet = opening + realized Income − realized Expense (+ explicit authorized adjustments/transfers, where supported), compares to entered actual, drafts/confirms/reopens with capability, reason and audit. CONFIRMED period closes normal realized ledger mutation. |
| FIN-006 | Pending personal expense and company-wallet reimbursement are separate states; no double counting personal advance as company outflow before reimbursement. Editing/reversing reimbursed historical rows must remain controlled. |
| FIN-007 | Finance dashboards, accounting reports, Wallet and Settlement must derive the same realized transaction definitions and complete aggregates; account period selection must not reprice course tuition. |
| FIN-008 | Finance Diagnostics is permission-gated (finance.view as current service contract); flags financial invariants/unknown legacy data. Diagnostics is **read-only** and never silently repairs ledger/DB. |
| FIN-009 | Each voucher is metadata in `finance_attachments` plus immutable PDF/PNG/JPG file in runtime/repository attachment tree; indexed by exact `INCOME` or `EXPENSE` transaction ID. Removing metadata is soft-delete; do not delete historical ledger transaction automatically. |
| FIN-010 | Income and Expense normal CSV export includes transaction identity and voucher count/filenames/SHA256, including multiple vouchers; no absolute local paths, binary data or unsafe spreadsheet formula execution. |
| FIN-011 | Separate ZIP-with-vouchers export contains `transactions.csv` plus real original PDF/image bytes under per-transaction paths. Resolve authorized stored locations, verify SHA256, prevent path traversal and report failure if a required voucher is absent/corrupt; do not claim incomplete ZIP success. |
| FIN-012 | CSV format cannot embed PDF/image bytes. A standalone CSV therefore contains **metadata only**; use ZIP to hand over actual evidence. ZIP export is a read-only action, available to permitted Finance readers without WRITE. |
| FIN-013 | Filtered CSV/ZIP export uses the same transaction scope as the UI (date/period/status/type/sort); downloads must not silently truncate long result sets. |
| FIN-014 | Financial history, archived Class/Student or closed FinancePeriod remains readable/exportable when authorized; historical ledger edits remain restricted. |

**Principal code:** `services/finance_period_service.py`, `income_service.py`, `expense_service.py`, `wallet_service.py`, `financial_settlement_service.py`, `finance_attachment_service.py`, `finance_csv_vouchers.py`, `repositories/finance_attachment_repository.py`, `ui/finance_workspace/`. **Workflows:** WF-17 through WF-22.

## 7. Teacher, Employee, shifts, reports, Admin

| ID | Requirement |
| --- | --- |
| HR-001 | Teacher records, class assignments, details and active/archived identity are managed by teacher/assignment services. Teacher workspace supports dashboard, list, detail and class navigation. |
| HR-002 | Employee workspace includes employee profile, employment state, private docs, expected schedule, attendance/working-time and work registration/review as permitted by role. |
| HR-003 | Self-service employee views may expose own information and authorized updates, but must not grant employee-wide HR administration. Work registrations/approvals require explicit roles and leave audit state. |
| HR-004 | Salary/hours/payment calculations must use their owning schedule/working-time/payroll service rules; avoid treating unapproved hours or planned shifts as paid/approved work. [VERIFY] Exact pay rates and payroll approval rules are configuration/operational decisions and require inspection before implementation. |
| REP-001 | Reports/analytics are read-oriented projections. Student study reports, session notes, assessments, attendance and finance reports must use canonical service data and respect permissions/history. |
| REP-002 | Report generation/export must not write core business state as a side effect of mere READ. Failure in best-effort derived report delivery after verified publish must be reported separately from successful core data publication. |
| ADM-001 | Admin Workspace owns Users, Roles & Permissions, system settings, Git configuration, Audit, System Operations, Diagnostics and Backup/Recovery. Pages have independent capability checks. |
| ADM-002 | Account/role/permission changes use PermissionService and audit; no global implicit Admin grant if custom account lacks a required capability. |
| ADM-003 | Provisioning/admin/backup operations must not bypass schema validation, Git authority, WRITE/CAS, SQLCipher identity, secret protection or Recovery review. |
| ADM-004 | Audit log is historic and permission restricted; timestamps, actor, action and relevant entity IDs are retained according to owning transaction's rules. |

**Principal code:** `ui/teacher_workspace/`, `ui/employee_workspace/`, `ui/admin_workspace/`, Employee/Teacher/Schedule/WorkingTime services, `services/report_service.py`, `models/permission.py`. **Workflows:** WF-23 through WF-28.

## 8. Regression/change-control matrix

| Change area | Must review | Minimum required evidence |
| --- | --- | --- |
| Student filters/import/export | STU-002..010, WF-06/07 | ACTIVE vs ARCHIVED, large page >250, selected vs filtered export, malformed XLSX, duplicate codes, READ/WRITE |
| Class/Enrollment/Session/Attendance | CLS-001..006, SES/ATT, TUI-003..010, WF-08..16 | midcourse join, withdrawal, archive with debt, session cancel, missing attendance, historical roster |
| Course tuition/outstanding | TUI-001..011, FIN-001/004, WF-13..16 | per-Enrollment accrual & paid, refund/credit, old debt, prepaid, cross-period |
| Finance/CSV/ZIP | FIN-001..014, WF-17..22 | closed period, no/one/many vouchers, missing/tampered bytes, path safety, large exports, permissions |
| Employee/teacher/report | HR/REP and WF-11/23..26 | self-role vs manager, registration approval, audit, report read-only |
| Git/Startup/Recovery/DB | COL-001..012, SYS-005..009, WF-01..05/27..28 | Git MAIN exact OID, single writer, offline READ, DPAPI, WAL, interruption, manual review, SQLCipher |
| Any schema change | SYS-006/007, COL-011, applicable domain spec | copy of encrypted DB; full Alembic lineage; forward migration; rollback & independent Windows EXE |
| Any release | ALL affected IDs | diff review, 3 Windows CI shards, source SHA + packaged migration, real EXE smoke on copy of database, Start/Finish Editing |

## 9. Mandatory developer/AI pre-change protocol

1. Read **this document and `CENTERMANAGER_BUSINESS_WORKFLOWS.md` first**, then `AGENTS.md`, current Issue/PR discussion and the relevant approved specialist domain spec. Never rely on old handovers alone.
2. Record: current HEAD SHA and **source branch**, exact target Git DB repo/branch (separately), package version, feature requirements and workflow IDs, user-visible before/after behavior.
3. Classify change: UI-only, read model/query, service/domain, persistence/migration, collaboration/recovery, credentials, release. Identify unrelated/high-risk boundaries explicitly **out of scope**.
4. Before coding, identify invariants, impacted files, caller chains, permission paths, mutation/READ paths, historical exceptions and tests. Resolve any conflict with source or superseded specs.
5. Create a focused branch/PR from the explicitly verified base SHA; **do not reset user-confirmed working source** to repair a small feature. Avoid speculative schema guards, Alembic stamps, migration lineage guesses and Git DB branch inference.
6. Add targeted tests, run Windows CI, inspect all changed paths, verify no unexpected `migrations/`, `database/`, `platform/sync/`, `write_recovery.py` changes, unless that domain was expressly authorized.
7. For high-impact domains run real EXE UAT on isolated copy of SQLCipher DB; verify login, READ, Start Editing, Finish Editing and subsequent restart.
8. Update these **two files in the same PR** if the accepted requirement/workflow actually changes. Include IDs and state `confirmed`, `code-observed`, `verify` or `proposed`; do not silently rewrite older approved decisions.
9. A PR is complete only after required CI, review, manual acceptance and human authorization. No merging speculative behavior to overcome a failed startup.

## 10. Detailed source references / disputed or non-current rules

- `docs/Bussiness/ARCHITECTURE_V2.md` — approved workspace ownership.
- `docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md` — Wallet/FinancePeriod/Settlement rules; **its tuition-per-period clause is superseded**.
- `docs/finance/FINANCE_WALLET_V2_TUITION_BOUNDARY.md` — approved academic vs accounting boundary.
- `docs/finance/FINANCE_CURRENT_STATE_AUDIT.md` — older source audit, inspect date and supersession before reuse.
- `docs/DATABASE_DESIGN.md`; `migrations/`; `models/` — exact storage schema, not inferred from this summary.
- `docs/Deployment_Docs/200_COLLABORATIVE_ARCHITECTURE.md` — concept-level; current Git-only startup path/source is decisive for exact failure handling.
- `docs/qa/stability/16_EXE_VERSION_FINANCE_PERIOD_STUDENT_TABLE_AUDIT.md` — historical unresolved risks, **not** acceptance that all proposals are deployed.
- Root `PRODUCT_CONTEXT.md` explicitly describes itself as draft and can refer to older `main_repos`; use versioned evidence rather than treating old status as current.
- **Unverified and not promised by this index:** exhaustive employee payroll policy, legal retention periods, old-EXE Git-side revocation, guaranteed all-or-nothing bulk student import, exact performance SLAs, hosted server/coordinator, monthly tuition.
