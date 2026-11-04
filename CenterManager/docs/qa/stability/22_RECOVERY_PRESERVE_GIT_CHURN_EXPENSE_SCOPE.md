# P0 Recovery Preserve Git Churn + Finance Expense Scope Audit

Date: 2026-11-04
Repository: AnNguyenHoai/Antechkid_Management
Base: main_repos a4bc87363defce161730cbfafd3952c73d23d28d

## User evidence / severity

Screenshots show the Windows EXE header: Mode RECOVERY, 'Inspect preserved local work before synchronization', and status 'Local recovery remains protected: Workspace changed during preservation. Retain all copies; retry with CenterManager stopped'. October 2026 Finance Dashboard shows Income 35,668,794 VND (24,968,794 Bank + 10,700,000 Cash) but Expense=0.

The supplied redacted 2026-11-03/04 CenterManager log proves:
- 2026-11-04 00:28:20 local authoritative repository MAIN commit created.
- 00:28:20-22 Git push MAIN succeeded: 'Push-only successful', 'Publish-only completed successfully'.
- 00:28:23-27 WriteRecoveryJournal.published() verified remote identity then preserve('published') raised at line 307: 'Workspace changed during preservation'.
- **Concurrently**, heartbeat/lease renewal started and fetched lock-main at 00:28:23-25, committed/pushed lock-main at 00:28:26-29; background Git operations mutate .git/FETCH_HEAD, remote refs, objects, logs and lock metadata. This is a narrow, evidence-grounded race, not proof local business data changed.
- WriteTransaction entered RECOVERY_REQUIRED and did not complete post-publish journal/lock release. Existing local work must remain protected.
- Earlier log 2026-11-03 ~15:33-15:38 had Finance diagnostics MutationAuthorityError from older installed EXE; this has separate PR and cannot be used to infer Expense history.
- User's EXE identifies itself as v1.0.0-rc1. A PR on the source tree does NOT change this already deployed binary.

## Safe remediation — code

The immutable preservation capture continues to copy and hash the whole repository, SQLCipher/WAL-complete DB, reports, attachments, export and metadata; it still validates copied captured bytes via its signed/HMAC manifest.

The before/after three-way equality check for **repository** treats Git's volatile transport/control metadata as live operations, not business worktree changes:
- Strictly checked: **every non-.git worktree file**, plus Git HEAD, index, config, packed-refs and business local refs/heads besides lock-main and queue-main.
- Exempt from temporal equality ONLY: other .git metadata such as FETCH_HEAD, object store additions, reflogs, remote tracking and collaboration lock/queue refs. These are still included and integrity-hashed in the captured artifact itself.
- All non-repository runtime roots (metadata, attachments, reports, exports) remain strictly checked.
- If critical files change, raise RecoveryRequired; log at most 8 relative paths only (no file contents, credentials, key or raw Git remote URL).

Unit tests use the isolated E1B-1 synthetic encrypted runtime/Git to reproduce lock-main and FETCH_HEAD changing during copy while verifying signed capture; any concurrent business file (manifest or repository center.db) modification must still fail closed.

## Expense analysis / safe presentation

ExpenseRepository.aggregate_realized_amounts_by_payment_method() filters soft-deleted rows and requires payment_date within selected window plus status Completed/Paid. A zero is **correct for cash outflow** if expenses in that month are only Pending; the screenshot and log do not contain the encrypted expense row data, so exact October paid/recorded/owed totals cannot yet be verified.

ExpenseFormDialog displays Completed as 'ĐÃ HOÀN TRẢ' and Pending as 'CHƯA HOÀN TRẢ'. The wording is reimbursement-specific; it can cause confusion when a founder pays an expense, while the company's actual wallet has not paid. **Do not silently change financial identity or equate unpaid expense obligations to company Cash Out.**

FinanceDashboardService now reads uncapped total recorded Expense and separate Pending expenses for exactly the same selected FinancePeriod date window, alongside its unchanged Completed/Paid-only outflow. The UI displays all three numerically to explain why Paid Expense can be 0 even when Expense records exist; no historical expense status, FinancePeriod attribution, wallet or settlement aggregation changes.

Acceptance: verify in a **read-only cloned production SQLCipher runtime** grouped counts/sums by status, payment_date, wallet and deleted_at for Oct 2026; match a row-level Expense CSV and check whether these rows are Pending or absent or outside period. No actual financial number is inferred from the screenshot.

## Critical release and recovery gates

1. Never drop or rename the existing .write-recovery directory or local center.db/WAL. Never force-push MAIN, auto-reconcile unknown unpublished work or release a remote WRITE lock without exact owner fencing.
2. Freeze the affected EXE; keep exact copies of the runtime directory, its sibling .write-recovery directory, credential/key reference protected on same host, and Git MAIN commit ID at the time of failure. This is a forensic backup step, not authorization to reset or overwrite.
3. Use the existing read-only recovery inspect command to examine journal status, base/main OIDs, publication state, verified capture manifests and any local unpublished SQLCipher changes. **Only a documented, operator-approved reconciliation** can resolve PUBLISHING/RECOVERY_REQUIRED.
4. Source fix only prevents a repeat false-positive. It does not automatically clear the *already blocked* user's recovery state; no release/auto-clean route is in this PR.
5. Exact-head Windows CI + actual EXE clone test: simulate lock renewal during post-publish capture, check valid journal can reach CLEAN and final lock released after successful Finish; concurrent real database/manifest mutation still triggers fail-closed RECOVERY.
6. Encrypted finance ledger read-only reconciliation before reclassifying expense amounts as an aggregation defect.

No changes to official production Git DB or any user's local runtime have been made by the PR.
