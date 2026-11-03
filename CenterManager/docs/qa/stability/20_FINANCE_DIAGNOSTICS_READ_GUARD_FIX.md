# DIAG-READ-01 — Finance Diagnostics fails in packaged READ-mode SQLCipher

**Date:** 2026-11-03  
**Base:** `main_repos` `f20e5324f65960c7f7c6e9915534884420ef708a`  
**PR:** #552 — targeted production guard fix, regression tests, no historical data writes

## Symptom
User screenshots show Finance > Diagnostics: `Diagnostics backend ERROR`, `Unable to load data`, blank D01/D02 totals. The previous finance.view permission change did not resolve it. An `ERROR` means the result count is **unknown**, not zero.

## Reproducible production-only mismatch

1. `FinanceDiagnosticsService.get_findings` opens the session, then `IncomeRepository.query_only()`, which executes `PRAGMA query_only = ON`, read-only SELECT queries and `PRAGMA query_only = OFF` in a finally block.
2. Production creates `GuardedConnection` for its runtime SQLCipher database. `guarded_dbapi.GuardedConnection._authorizer` previously handled all value-bearing PRAGMAs outside the narrow read allowlist via `_require('pragma')`, requiring an explicit maintenance permit. READ-mode viewers do not have this system permit.
3. `query_only=ON` is a **connection-local protection**, not a business, schema or maintenance mutation. With the old guard, the pragma is wrongly rejected before any D01/D02 query.
4. FinanceDiagnosticsService catches the exception and returns a generic `DIAGNOSTICS_READ_FAILED`. The UI cannot distinguish this failure from other SQLCipher/schema errors. Previous diagnostics unit tests used ordinary SQLite with no guarded DBAPI; they missed the production-only discrepancy.
5. Separately verified with SQLite authorizer callback: query_only=ON yields `SQLITE_PRAGMA` with `arg1='query_only'`, `arg2='ON'`; query_only=OFF likewise yields `arg2='OFF'`.

## Fix
Allow exactly `query_only` with ON/OFF/1/0 at the **connection-local PRAGMA** guard branch. The driver-level DML, DDL, COMMIT/SAVEPOINT, checkpoint, foreign database attachment and unknown PRAGMA authorization paths remain unchanged. The `query_only=OFF` operation **does not grant WRITE**; it restores the previous default connection flag, and `GuardedConnection` still denies unauthorized DML.

## Tests / acceptance
- `test_finance_diagnostics_guarded_sqlcipher.py` reuses isolated E1B2A real encrypted SQLCipher + mutation gate fixture, without authorized WRITE: D01/D02 report returns `state=OK` and real zero counts for an empty Income dataset.
- Guarded DBAPI allows `query_only=ON`, read SELECTs, and `query_only=OFF` cleanup.
- Even after toggling, READ-mode INSERT/UPDATE and privileged PRAGMA journal_mode are rejected, and seeded Student data is unchanged.
- Error inside query_only context restores OFF before cleanup.
- **Pending:** exact-head Windows CI and disposable cloned Windows EXE runtime UAT. Do not claim the user screenshot has been resolved before testing that build.
- If ERROR persists after tested build, fetch sanitized `Finance diagnostics failed: <exception class>` log from client; audit schema/SQLCipher lifecycle separately. Do not clear DB or alter MAIN/WRITE lease.


## CI #1030 audit — pytest fixture wiring failure

GitHub Actions https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41655916661 at `58c2fe12` completed FAILED: Windows shard 0 PASS, shard 1 PASS, shard 2 **1219 passed, 2 skipped, 3 setup errors**. All three errors are in newly added `test_finance_diagnostics_guarded_sqlcipher.py`: the imported E1B-2A `reporting` fixture needs the E1B-1 `workspace` fixture, which was not imported into the new test module. Pytest reports `fixture 'workspace' not found` before opening a SQLCipher test runtime.

Fixed by explicitly registering `workspace` from `tests.test_e1b1_durable_write_recovery` alongside `reporting` from `tests.test_e1b2a_post_publish_consistency`. Production `GuardedConnection` and its mutation rules are unchanged by this CI fix. The three real SQLCipher regression tests have **not** yet been proved passing; exact-head CI is required.

No operational database or official Git MAIN was modified.
