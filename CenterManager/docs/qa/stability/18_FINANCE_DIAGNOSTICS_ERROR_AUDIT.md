# Finance Diagnostics — ERROR screen audit (2026-11-03)

**Base** `main_repos` at `0807e89f1a42dcb7e6ddd5207d96f9c2fe825ede`. **Scope:** source-only audit of a user screenshot, no production SQLCipher DB/logs. **No production changes.**

## Observed symptom
At Finance Workspace > Diagnostics, As of 03/11/2026, All findings, UI displays:
`Diagnostics backend ERROR`, `Unable to load data`, and `The diagnostic read failed. No finding count is available.` Summary counters are `—`, not zero. Bottom DataTable says `0 results` even in error state, which is misleading. The top Finance Period 01/11/2026–30/11/2026 is **not** used as a filter: this page explicitly sends only `as_of_date` and `rule_id`.

## Confirmed code path
1. `finance_diagnostics_page.py:148-175`: refresh dispatches a `QRunnable` with authorization snapshot into `QThreadPool.globalInstance()`.
2. `_ReadTask.run()` installs `CurrentUserContext(snapshot)`, then invokes `FinanceDiagnosticsService.get_findings`. Exception is reduced to class name only.
3. `finance_diagnostics_service.py:110-150`: permission guard, new Session, `IncomeRepository.query_only()` (PRAGMA query_only ON/OFF), counts D01 and D02, page read. Any internal exception is collapsed to `state=ERROR`, `error_code=DIAGNOSTICS_READ_FAILED`, and logs only its class name. Permission exceptions originating in the decorator occur *before* the service catches and similarly yield the same generic UI state.
4. `finance_diagnostics_page.py:190-205`: generic error view is used for denied capability, unexpected exception and SQL/database failure alike. The screen does not show whether the error is authorization, missing column/schema, SQLCipher connection failure or query failure.

## Confirmed policy inconsistency
`finance_workspace_shell.py::_has_finance_access` allows `user.has_permission("finance.view") OR user.is_admin`; meanwhile `FinanceDiagnosticsService.get_findings` and `_principal_snapshot` require the canonical `finance.view` capability. `AuthorizationService` does **not** implicitly grant FINANCE_VIEW to admin (it is neither ADMIN_ONLY nor in implicit-admin capabilities). Therefore an admin whose role was customized to lack `finance.view` **can enter the workspace but will receive this Diagnostics backend ERROR**. A standard seeded admin is assigned all permissions by `database/seed.py`, so this is a **conditional, proven source inconsistency**, not a confirmed explanation for this workstation.

## Other plausible causes (not confirmed by screenshot)
- SQLCipher unavailable or global runtime maintenance gate engaged on worker query: inspect diagnostic failure class in local log.
- Production database schema older than repository's Income/Enrollment columns used by D01/D02 (e.g., `reconciled_into_enrollment_id`, `deleted_at`); migration/release-state mismatch must be verified read-only.
- `PRAGMA query_only` fails at acquisition, query or restoration due to driver/connection lifecycle.
- Runtime user context changes while task runs; result is rejected by UI permission recheck (intentional revocation, needs differentiated status).

## Discriminating evidence (never upload raw DB or keys)
1. Find the line `Finance diagnostics failed: <exception class>` in client log immediately after pressing Refresh, and record date/time/build SHA. The class alone distinguishes broad failure domains but cannot identify exact SQL statement.
2. Compare account role's persisted `finance.view` grant with access to Finance Workspace.
3. With app in READ mode and on a **disposable clone**, run a privileged, read-only SQLCipher schema validation and D01/D02 query under the same session factory. Never modify authoritative MAIN to repair this screenshot.
4. Reproduce with an authorized finance user; if their report loads but admin fails, prioritize UI/capability mismatch. If all fail, inspect SQLCipher/schema/query lifecycle first.
5. Preserve the difference between `ERROR` and `OK, 0 findings`: never replace failure with empty successful result.

## Remediation design (not implemented in this audit)
- Authorize Finance Workspace entry with `AuthorizationService.allows(user, Capability.FINANCE_VIEW)` consistently; do not grant finance.view to every admin implicitly without an explicit policy change.
- Propagate only stable, non-PII diagnostic codes: `PERMISSION_DENIED`, `DATABASE_UNAVAILABLE`, `SCHEMA_INCOMPATIBLE`, `QUERY_FAILED`. Log diagnostic correlation IDs, cause class and stage, never raw SQL/parameters, student names or keys.
- The UI should render a distinct permission message and stable code/correlation ID, and disable Export CSV when the backend is unavailable. Bottom-row count should show unknown (not 0) in error state.
- Add Windows SQLCipher/worker-thread integration tests using cloned **synthetic** runtime for admin lacking finance.view, authorized finance role, schema missing one D02 column, maintenance fence error, query_only cleanup, and permission revocation while an async task is pending.

**Conclusion:** screenshot proves diagnostic read ERROR, not an empty list of anomalies or DB corruption. Exact root requires local exception-class evidence or isolated reproduction. No security gates, finance records, or Git MAIN have been changed.


## Founder-approved access policy — implemented

**Decision:** any active account holding the persisted `finance.view` capability may access Finance Workspace and Finance Diagnostics, regardless of role name. Role names such as `admin` and `finance` alone do not override a revoked or missing `finance.view`.

Changed `FinanceWorkspaceShell._has_finance_access` to use the same canonical `AuthorizationService.allows(user, Capability.FINANCE_VIEW)` check as `FinanceDiagnosticsService.get_findings` and `FinanceDiagnosticsPage._principal_snapshot`. This removes the conditional admin-only UI bypass. Added regression for permitted/denied admin, finance, teacher, reception, manager, plus inactive users.

This change **does not** alter WRITE, settlement, finance-period-admin permissions or automatically grant rights to any role. The default seeded admin remains authorized because it already has all persisted permissions. If the screenshot error occurs for an account with verified `finance.view`, this access-policy fix alone does NOT repair SQLCipher/schema/SQL query failures; inspect the sanitized client log.


## CI #1001 — architecture assertion remediation

Windows CI https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41606219009 at `9f9dfeac`: shard 1 and 2 PASS; shard 0 has **1 FAILED, 1033 passed, 3 skipped**. Only failure: `test_ep_prototype_08_finance_access_is_permission_gated` assumed that `FinanceWorkspaceShell._has_finance_access` must literally contain the string `finance.view`. The approved code instead calls `has_capability(Capability.FINANCE_VIEW)`, which resolves to the exact canonical finance.view grant and respects inactive/revoked accounts. The previous source-string test was obsolete, not evidence of a permission regression.

Updated the architecture assertion to accept the typed capability form as well as the legacy literal and to reject the former `or user.is_admin` bypass explicitly. Existing behavioral tests continue to assert allowed/revoked roles. Production permission code and SQLCipher/finance ledger remain unchanged by this CI fix. **Exact-head Windows CI still required** before merge.
