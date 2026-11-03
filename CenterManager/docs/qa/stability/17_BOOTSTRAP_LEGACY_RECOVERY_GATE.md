# BOOT-LEGACY-01 — Windows EXE upgrade blocks before safe recovery

**Date:** 2026-11-03
**Repository:** `AnNguyenHoai/Antechkid_Management`
**Base:** `main_repos`, `b9f6d6dd59baff1c4ea36cf804fa11f2e9502e5c`
**Scope:** bootstrap sequencing only. No Git MAIN publication change and no forced local data discard.

## User-visible reproduction

On a packaged Windows client with an existing legacy runtime and no E1B WRITE receipt:

> WRITE recovery required: Legacy workspace has no recovery receipt and may contain local work. Preserve it and reconcile explicitly before synchronization.

The message is raised by `WriteRecoveryJournal.assert_replaceable(legacy=True)` at `platform/write_recovery.py:147-155`. Its refusal is **appropriate when attempted immediately before destructive workspace replacement**, but was called prematurely in `BootstrapManager.run()` before the client could connect, fetch Git MAIN, preserve local work and reconcile.

## Confirmed root cause

- `platform/bootstrap/bootstrap_manager.py::run()` called `require_replaceable(legacy=True)` before `_ensure_authoritative_runtime_database()`.
- `_ensure_authoritative_runtime_database()` invokes `StartupSynchronization.run()` which has a complete pre-reset sequence: fetch MAIN, independently observe exact OID, check mutation gate, check WRITE journal, preserve/reconcile local artifacts if needed, then install accepted Git MAIN.
- Consequently the safe legacy-upgrade recovery path was unreachable even when there was a valid Git MAIN and the runtime could be preserved.
- The same bootstrap path created default runtime and formerly overwrote an existing `manifest.json` when repository state was missing/invalid; that now only provisions a **missing** manifest, never overwrites a legacy manifest.

## Fix

1. Bootstrap reads/validates `journal.json` metadata only via `WriteRecoveryJournal(paths).inspect()`; unreadable/corrupt recovery metadata still blocks before provisioning or Git sync.
2. Remove **only** the early destructive-replacement gate. All real guards remain in `StartupSynchronization` and in local DB/Git replacement boundaries.
3. When provisioning a default runtime, preserve any pre-existing legacy `manifest.json`.
4. Regression coverage: no-receipt workspace proceeds to authoritative sync; malformed journal is refused before sync; preexisting manifest bytes are unchanged.

## Guarantees, limits and operator safety

- **Git MAIN remains the authoritative accepted database.** The local recovery capture is evidence, not a new authoritative database, not a WRITE grant, and not a publication attempt.
- Remote MAIN must be freshly fetched and independently verified before accepting any replacement. Invalid or unavailable Git still blocks.
- No direct local data deletion, silent overwrite, auto-publish, SQLCipher key bypass, lease bypass, or WRITE authority change occurs in this PR.
- **Important:** The fix does not promise every legacy workspace can be automatically reconciled. A dirty WAL, missing local Git base, unreadable SQLCipher, corrupted journal, or failed capture can still require manual recovery with the EXE stopped. Do not remove the runtime or `.write-recovery` merely to dismiss the warning.
- The source CLI shown by the old popup (`python -m centermanager.platform.write_recovery inspect`) is not generally runnable from an EXE-only release without the Python source/package and dependencies. The packaged app should display safer operator instructions rather than assuming that source CLI is available.
- This PR must pass the Windows pytest suite and a disposable Windows EXE/runtime upgrade UAT before merging. The user image proves the early-block popup but does not identify the exact packaged binary build SHA or whether Git runtime is otherwise clean.

## Validation cases

B01 upgrade/no journal, unchanged local DB: bootstrap calls Git startup preflight and publishes CLEAN local receipt only after verified accepted MAIN.

B02 upgrade/no journal, local DB differs from repo: verified preservation + explicit reconciliation record; no local-to-Git publish.

B03 no journal, WAL pending or SQLCipher busy: no silent discard; either validated recovery or fail-closed with preserved artifacts.

B04 unreadable `journal.json`: bootstrap blocks before any local overwrite.

B05 remote Git offline/OID UNKNOWN: startup refuses.

B06 original legacy manifest and DB remain untouched if startup fails prior to Git verification.

B07 Windows EXE packaged with local recovery and repro runtime copy: valid MAIN and capture allow login only after successful authoritative installation; mutation authorization remains read-only unless a separate WRITE grant is acquired.
