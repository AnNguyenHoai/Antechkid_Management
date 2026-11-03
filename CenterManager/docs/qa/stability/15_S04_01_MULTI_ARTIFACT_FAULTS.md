# QA-S04-01 — Startup multi-artifact consistency

Base: main_repos `07b11f52a5584ac943b91015b144c9c6e215a540` (merged PR #546).

## Verified source-level defect
`StartupSynchronization._apply_runtime_database` installs Git's SQLCipher DB first, then replaces Employee attachments by deleting the old directory and copying the new tree, then writes manifest and metadata/version.json in place. An exception halfway through the attachment copy or a truncated version.json can leave mixed generations. `run()` rolls back DB and Git, but does not roll back the attachment tree/manifest/metadata. A failed startup is blocked, yet the local workspace can remain inconsistent until a subsequent successful synchronization.

## Test contract
`tests/test_qa_s04_01_startup_multiartifact.py` uses disposable synthetic files and mocks the DB installer only to isolate multi-file coordination:
- happy path materializes Git MAIN DB + attachment + manifest + version.
- injected partial attachment copy must restore old snapshot.
- injected metadata write failure must restore old snapshot.

The two fault tests are `xfail(strict=True)` **by design**, documenting currently failing release gates. A green CI with these XFAILs does NOT mean the bugs are fixed. When production rollback is implemented, remove the xfail markers; XPASS will intentionally fail until the assertions are promoted to ordinary PASS tests.

## Recommended narrowly scoped fix
Stage Employee attachments, manifest and version JSON in temp siblings on their destination filesystem; preserve old bytes/trees until all DB and non-DB assets are installed, the SQLCipher sessions refresh, and `record_synchronized()` completes. On any error, roll back all artifacts (DB/WAL, attachments, manifest, version), and Git HEAD. Make sure temporary trees/rollback artifacts do not pollute journal fingerprint; fail closed if rollback itself fails.

## Gate
PR remains QA-only and draft; do not merge into production until fix PR removes strict XFAILs, exact-head CI passes and Windows packaged SQLCipher UAT validates all scenarios.


## S04-01A implementation after CI #919
- Added `_prepare_startup_assets()`: pre-stage Employee attachments and copy prior attachments/manifest/version files to sibling recovery storage before touching the runtime DB.
- Added `_rollback_startup_assets()` and `_finalize_startup_assets()`; ordinary copy/JSON errors now reverse non-DB materialization alongside SQLCipher DB rollback. Refresh/receipt failures in `run()` also initiate both rollbacks.
- Employee assets are copied completely into staging first, then moved into place using same-volume `os.replace` after the current mirror is removed. Backup remains available for exceptions.
- Removed the two `xfail(strict=True)` markers: partial attachments and partially-written metadata now have normal PASS requirements. Added manifest failure, staging failure and rollback coordination assertions.
- This implementation handles **caught exceptions**, not arbitrary process termination between renames. A persisted transaction marker and restart replay remains S04-01B, a release blocker. It must be tested with real Windows process kill and SQLCipher. Do not promote PR #547 to production on CI alone.


## S04-01B first safety gate — interrupted startup (after #925)
- Before changing the live runtime DB, startup now durably writes an external `runtime.write-recovery/startup-install.pending.json` marker with a transaction id, intended Git MAIN and DB path. It uses temp-file, flush/fsync, and atomic same-volume rename. The marker is outside the journal fingerprint.
- On a subsequent process start, a pending marker (including malformed/truncated content) blocks **before** repository clone/connect/fetch or any DB replacement. This prevents mixed-generation data from opening as a clean workspace.
- Once all install gates pass, the marker is removed only after DB and asset finalizers complete. When a normal caught exception triggers verified rollback of DB, assets and local Git HEAD, the marker can also be cleared. Any failed/incomplete rollback preserves the marker.
- Regression tests simulate a new EXE process with no in-memory transaction state, malformed marker and normal/incomplete rollback cleanup decisions.
- **Important limitation:** This is a durable *detection + fail-closed* gate, not autonomous restoration after a hard process kill. A persisted rollback inventory and Windows process-kill/restart UAT are still required to safely recover unattended. Do not delete the pending marker to bypass the gate; first preserve the entire runtime and sibling recovery folder and reconcile its generations.
- A successful Windows CI does not prove real process kill behavior, power-loss fsync durability or SQLCipher/WAL recovery.
