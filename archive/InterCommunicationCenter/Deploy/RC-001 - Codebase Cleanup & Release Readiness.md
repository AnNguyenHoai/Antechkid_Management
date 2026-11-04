# RC-001 - Codebase Cleanup & Release Readiness

Version: 1.0

Priority: 🔴 CRITICAL

Estimated Time: 3~5 Days

Owner: DeepSeek

Status: READY

---

# Background

CenterManager MVP has reached feature completion.

Completed Domains

✅ Authentication

✅ RBAC

✅ User Management

✅ Student Workspace

✅ Class Workspace

✅ Teaching Workspace

✅ Finance Workspace

✅ Reporting

The next objective is NOT adding new features.

The objective is to transform the current development codebase
into a stable Release Candidate.

This sprint focuses entirely on code quality,
project organization,
and release readiness.

No new business functionality should be introduced.

---

# Objectives

Prepare the codebase for Release Candidate (RC1).

Improve maintainability.

Reduce technical debt.

Standardize project structure.

Ensure the project is clean before packaging.

---

# PART 1 — Dead Code Audit

Review the entire project.

Identify

- Unused Services
- Unused Repositories
- Unused Models
- Unused Widgets
- Unused Dialogs
- Unused Commands
- Unused Helpers
- Legacy Utility Classes

Produce

Dead_Code_Report.md

The report must include

- File
- Reason
- Safe to Remove?
- Dependency Analysis

DO NOT delete immediately.

Submit report first.

---

# PART 2 — Debug Cleanup

Remove

print()

temporary debug logs

temporary startup traces

TODO comments that are already completed

obsolete FIXME

temporary exception handlers

temporary testing switches

Only keep

official application logging.

---

# PART 3 — Folder Structure Review

Review project layout.

Expected high-level structure

src/

resources/

runtime/

config/

docs/

tests/

scripts/

migrations/

Review

Folder responsibilities

Incorrect locations

Duplicate assets

Temporary files

Unused resources

Produce

Project_Structure_Review.md

---

# PART 4 — Import Cleanup

Review

Unused imports

Circular imports

Duplicate imports

Wildcard imports

Standardize import ordering.

Do not change behavior.

---

# PART 5 — Naming Review

Review consistency.

Examples

Service

Repository

Widget

Dialog

Workspace

ViewModel

DTO

Entity

Identify inconsistent naming.

Do NOT rename yet.

Produce recommendations.

---

# PART 6 — Runtime Directory

Prepare runtime layout.

runtime/

logs/

reports/

backup/

temp/

Ensure every folder is created automatically
if missing.

Never require manual creation.

---

# PART 7 — Configuration Review

Review

config/

settings

environment variables

default values

database paths

resource paths

No hard-coded absolute paths.

Everything should be configurable.

---

# PART 8 — Logging Review

Verify

Application Log

Error Log

Startup Log

Report Log

No debug information should appear
in Release mode.

Unhandled exceptions
must be logged.

---

# PART 9 — Release Checklist

Create

Release_Checklist.md

Include

Database

Permissions

Reports

RBAC

User Management

Teaching Workspace

Finance Workspace

Runtime

Configuration

Logging

Backup

Restore

Packaging

Installer

Pilot

---

# Deliverables

Dead_Code_Report.md

Project_Structure_Review.md

Release_Checklist.md

Cleanup Summary.md

---

# Acceptance Criteria

✔ No obsolete debug code.

✔ No unused imports.

✔ Runtime folders standardized.

✔ Logging standardized.

✔ Configuration reviewed.

✔ Dead code report completed.

✔ Release checklist completed.

✔ Build still passes.

✔ No business behavior changed.

---

# Constraints

Do NOT add new features.

Do NOT redesign UI.

Do NOT refactor business logic.

Do NOT modify database schema.

Only cleanup and documentation.

---

# Definition of Done

CenterManager source code is considered

Release Candidate Ready

when

the codebase is clean,

well organized,

fully documented,

and ready for packaging
without hidden technical debt.