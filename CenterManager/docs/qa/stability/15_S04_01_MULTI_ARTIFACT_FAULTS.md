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


## S04-01B continuation — verified local replay, then mandatory Git MAIN
The first pending-marker gate was deliberately fail-closed, but could leave an EXE unusable indefinitely after a power loss. The follow-on implementation uses `startup_install_replay.py`:
1. Before mutation, quiesce DB handles and save independently checksum-verified originals of SQLCipher DB plus WAL/SHM/journal, Employee attachments, manifest and version metadata in a sibling `startup-replay/<transaction-id>` folder. Write marker only after copies verify.
2. Next process checks the marker before any Git clone/fetch or runtime DB use. Reject old/malformed inventory or changed target paths. Verify **all** snapshots before touching any live file; replay idempotently if a previous replay itself was killed.
3. Remove the marker only when local technical restoration succeeds. Then continue the **ordinary** startup path: connect/fetch remote, verify accepted MAIN, replace runtime with MAIN, refresh sessions and record receipt. Replayed local bytes are never published and never authorize login offline.
4. Corruption, missing backups, untrusted paths or failed replay keep the marker and fail closed.

Tests cover process-restart replay, corruption refusal, runtime mismatch refusal, stale WAL removal, and unavailable Git after replay.

### Remaining release gates
- CI at the precise new head is NOT yet verified.
- The synthetic replay tests do not simulate a hard-killed Windows EXE during os.replace, or actual SQLCipher/WAL mutations. Perform process-kill UAT in a disposable runtime.
- A bare filesystem copy may capture an inconsistent database if another writer exists despite quiescing the local process; verify the WRITE authority guard and snapshot consistency on real SQLCipher fixtures.
- The preserved backup folder may grow; define retention/cleanup only after safe independent snapshot acceptance, never delete a pending recovery copy.
- The initial marker format 1 is intentionally not auto-replayed (no verified rollback inventory) and remains manual fail-closed.


### Follow-up hardening
- Added child-process `os._exit(71)` fixture to simulate actual loss of Python process state after writing a durable marker and partial live artifacts, then verify fresh parent replay.
- Added a centralized `_rollback_failed_install_all` so DB, attachments/metadata and Git rollback are all attempted even if an earlier restoration throws. Partial failure retains the marker and blocks the next startup.
- Exact-head CI validation remains required. This test does not claim Windows power-loss atomicity.


## CI #940 audit, Nov 3 2026
CI: https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41565581938 at `2fbd2e73`.
- Shard 2: `test_real_child_process_exit_preserves_replayable_snapshot` exited 1 instead of expected 71. The subprocess lacked pytest's source import path, causing `ModuleNotFoundError: No module named 'centermanager'` before any child capture or simulated crash. Corrected child bootstrap to place `Path.cwd()/src` on its import path (test-only).
- Shard 0: one independent setup error in existing `test_authorized_write_student_service_and_permission_floor`. `materialize_runtime_database_to_repository` called validation while a process-wide maintenance fence was active, yielding `RuntimeDatabaseMaintenanceError: Runtime database is temporarily unavailable during backup restore`, wrapped as `DatabaseArtifactSecurityError`. This test fixture predates S04 and does not execute startup replay. CI #930 passed this suite, so a shared-state order/leak or sporadic test environment gate remains a hypothesis, not a proven production defect. Do not disable SQLCipher validation or alter WRITE gates to make it pass. Reproduce on repeat CI and isolate the owning fixture before any fix.
- Shard 1: PASS.
- New head requires exact-SHA CI. Keep PR draft pending confirmed full-suite pass and real Windows SQLCipher UAT.


## CI #942 — repeating shard-0 global maintenance fence (Nov 3)
Run https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41569325528 at `bb2f214c`: shards 1 and 2 PASS, shard 0 has one error in `test_e1b2b_local_mutation_authority::test_authorized_write_student_service_and_permission_floor` **during the `reporting` fixture setup**. `materialize_runtime_database_to_repository` calls SQLCipher validation while `_runtime_db_maintenance` is already true and guarded DBAPI creation fails with `RuntimeDatabaseMaintenanceError`. This exception is wrapped by the artifact validator as a generic authentication error, but it is NOT evidence of an incorrect SQLCipher key.

The fixture `workspace` creates a new isolated temporary encrypted DB but production's runtime maintenance gate is process-global. A preceding fault test in the same long-lived pytest shard can leave it set. The test-only fixture boundary now checks the number of tracked native DBAPI connections is zero before resetting a stale gate. If connections remain, the test fails rather than hiding a real lock leak. No production gate, encryption or SQLCipher validator was changed.

Child subprocess import fix from prior commit is verified by shard 2 PASS. Validate exact-head repeat CI before considering QA gate complete.


## Nov 3 — maintenance root audit and SQLCipher/WAL UAT
- Repeated CI #940 and #942 shard 0 errors were `RuntimeDatabaseMaintenanceError` generated by the **process-global** `_runtime_db_maintenance` flag during fixture setup, subsequently wrapped in `DatabaseArtifactSecurityError`; it did **not** prove an incorrect workspace key. Test fixture isolation fixed CI #944 (all 3 shards PASS).
- A separate **confirmed production** fence lifecycle defect was found: `_check_interrupted_startup_install` called `session_module.quiesce_runtime_db()` then successfully replayed file backups and returned `True` without releasing the maintenance fence. The next Git/SQLCipher validation could then be refused. This path was not executed in shard 0, so it is **not confirmed as the historical CI shard-0 source**. The fix now releases maintenance only after a fully verified replay; failed replay remains fenced. Added positive/negative fence lifecycle tests.
- Added real encrypted SQLCipher + WAL recovery regression using disposable `workspace`, with committed WAL and `PRAGMA integrity_check` after verified restore. Added real separate-process `os._exit(71)` regression earlier.
- Actual UAT **on a copied operational Windows EXE/runtime has not been executed**. There is no real Windows EXE or operational runtime copy in this session. Windows CI uses synthetic fixtures. DO NOT describe the CI as passing an actual production-clone UAT.
- `tools/qa/s04_windows_exe_uat_preflight.ps1` is a read-only Windows clone preflight. It requires an explicit `S04_UAT_DISPOSABLE_CLONE.txt` marker, executable, database and local Git repo; refuses public GitHub/production remotes; hashes DB, WAL/SHM, manifest and Employee attachments for evidence.
- The script emits relative filenames, file lengths and checksums, never secret keys or decrypted SQL. It does not launch or kill any executable or write to DB. The operator must verify that the EXE does not override Git origin with bundled credentials/config before launching it.
- On a real disposable clone with an isolated synthetic local Git remote: capture preflight evidence; launch cloned EXE; kill it during each intended DB/install boundary; inspect recovery marker and backup copies; restart; confirm Git MAIN is fetched and authoritative before login; check SQLCipher integrity, WAL convergence, hashes and all attachment/manifest identity against that local remote. Repeat after corruption, missing remote and denied file writes. Record timestamps, EXE SHA and per-case logs.
- **Not ready for merge/deployment** until exact-head Windows CI passes and operational-clone UAT evidence exists. Limit live risk: never use the organization's active runtime, official Git remote, shared production token, or active student records in a fault-injection run.

### Additional Windows UAT reminder
The current production startup uses the underlying Git provider configuration; changing only the cloned local `repository/.git/config` may be insufficient if a configured repository URL overrides it. Audit application provider configuration and prohibit external network access for the UAT EXE before first launch.
