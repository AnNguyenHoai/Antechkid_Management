# Employee / Finance / Document Audit Fix

## 1. Finance permission log during login

### Root cause
`StudentFinancialWidget` and the legacy `FinancialWidget` could call
`IncomeService.list_incomes()` while the current user did not have
`finance.view`. The exception was caught and logged as a load failure, so a
normal authorization denial appeared as an application error in the log.

### Fix
Both widgets now check `finance.view` before calling finance-protected
services. Unauthorized users get an empty/hidden financial state without
invoking the protected service.

The Finance workspace itself remains route-protected.

## 2. Employee document storage

Employee documents are **filesystem files**, not database BLOBs.

Local runtime:

```text
runtime/Attachments/Employees/<EMPLOYEE_CODE>/<DOCUMENT_TYPE>/<UUID>_<filename>
```

The database stores only metadata and a runtime-relative path such as:

```text
Attachments/Employees/EMP-00001/CV/<UUID>_cv.pdf
```

The collaboration repository mirrors the same files:

```text
runtime/repository/Attachments/Employees/<EMPLOYEE_CODE>/<DOCUMENT_TYPE>/<UUID>_<filename>
```

### Cross-machine lifecycle

```text
Machine A
Upload
  -> runtime/Attachments/Employees
  -> DB metadata
  -> Finish Editing / Publish
  -> repository/Attachments/Employees
  -> git commit + push

Machine B
Startup/background sync
  -> fetch/reset repository
  -> repository/Attachments/Employees
  -> runtime/Attachments/Employees
  -> resolve stored relative path
  -> open local file
```

An uploaded file is therefore **local working state until the write
transaction is published**. This is intentional: document and database
changes cross the same collaboration boundary.

### Safety
- Absolute document paths are rejected for repository mapping.
- Runtime document paths are constrained to `runtime/Attachments`.
- Repository document paths are constrained to `runtime/repository`.
- Upload logs both runtime and repository-mirror target paths.
- `GitSynchronizationProvider.publish()` and `publish_only()` mirror Employee
  attachments before `git add -A`.
- Startup synchronization mirrors repository Employee attachments into the
  local runtime.

### Important operational implication

If a document exists in the database but has not been published, another
machine will not be able to open it. If it has been published but is missing
from the repository mirror, synchronization diagnostics should be checked
before attempting to open the file.
