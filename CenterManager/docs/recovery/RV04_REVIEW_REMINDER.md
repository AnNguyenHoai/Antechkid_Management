# RV-04 — Recovery Case reminder and manual-review workflow

Issue #596. Depends on merged RV-03 case registry.

## Operation

- After successful startup synchronization and login, MainWindow checks the signed Recovery Case registry. It opens a non-blocking-to-data-authority reminder dialog only if pending cases are present. No registration or remote Git writes are performed by the reminder.
- The user can inspect a safe case summary. Change Log coverage is UNKNOWN, so the UI **never** claims to list all missing operations or decrypt/reconcile old business records.
- **Skip** or closing the dialog makes no persisted changes; pending cases appear again after a later login/startup.
- **Đã kiểm tra** requires an explicit confirmation prompt and validates the immutable capture before atomically replacing the signed case metadata with ACKNOWLEDGED and a timestamp. Backup and case stay on disk; no DB, remote Git or mutation-authority state changes. Acknowledgement means *reviewed*, not *re-entered* or *missing from MAIN*.
- The **Khôi phục > Danh sách Recovery Case** menu gives a view of pending and reviewed cases. **Xuất tóm tắt** exports a restricted JSON report without backup paths, private records or raw SQLCipher contents.

## Privacy and finance

Never infer a financial transaction is missing solely from a Change Log/mirror entry. When manually re-entering, compare transaction ID, student/enrollment, amount, method and dates against MAIN before creating new income/expense or debt entries. A duplicate could change financial reports.

Only anonymized case IDs, publication proof states and OIDs are shown. No student names or finance details in app logs or the normal summary.

## Safety and release gates

- The reminder is shown only after normal successful startup and login; any unsafe startup replacement remains governed by RV-03 fail-closed preflight.
- UI does not bypass local WRITE gate, lock lease, Git MAIN CAS or publication authorization.
- Core tests: `tests/test_rv04_recovery_review.py` (review persistence, tamper protection, skip and cross-incident behavior).
- **Windows CI must pass**; run actual packaged EXE restart UAT for Skip / Reviewed / new incident; confirm unaccepted records remain intact and READ/WRITE works only after safe startup.
- Before closing #596, verify packaged Windows behavior for modal dialog accessibility, report export, account permissions, Windows DPAPI and two-client interaction. No CI-only release approval.
