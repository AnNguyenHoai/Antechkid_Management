# QA-S01 R3 — Remote accepted publish / lost ACK / late SQL commit

**Pinned base:** `main_repos` `32356ca5df20f283a7d39acefaad2339a9de040e`, merge PR #539.
**Prior exact head CI:** PR #539 SHA `c71674a9de3526d106b0631ce17c730a6a04ddc0`, [CI #868 PASS](https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41426558926).
**This R3 branch:** NOT RUN at creation; do not infer success from earlier CI.

## Scope and expected behavior
- Uses existing `test_e1b1_durable_write_recovery.workspace`: synthetic SQLCipher key, isolated runtime and disposable local bare Git remote. Production remote, customer data and tokens are never accessed.
- `test_remote_accepted_but_ack_unknown_requires_exact_reobservation`: SQL commit; WAL-safe runtime materialization; pre-push recovery capture; PUBLISHING state; actual Git commit/push succeeds. After lost simulated ACK, a new journal instance must reject workspace overwrite. UNKNOWN observed remote OID cannot be marked published. Exact re-observation may move PUBLISHING -> PUBLISHED; release verification alone enables CLEAN. Validate SQLCipher PRAGMA integrity_check, foreign_key_check, and exact committed values in runtime and repository.
- `test_remote_accepted_but_local_changes_after_push_never_clean`: actual remote accepts snapshot, then another local SQLCipher commit occurs. Even with exact Git OID remote observation, runtime divergence must reject published receipt and keep PUBLISHING/UNVERIFIED, preserving additional local committed value.

## Execution
`cd CenterManager && python -m pytest tests/test_qa_stability_s01_lost_ack_r3.py -v`

Both tests newly submitted, **PASS 0 / FAIL 0 / NOT RUN 2** at authoring. The 'ACK lost' outcome here is simulated by deliberately withholding the successful response and re-observing Git; true process termination scenarios are covered separately by pre-existing E1B1 test_real_process_kill_and_restart and still require real packaged Windows UAT.

## Gate
Record workflow run, exact SHA, counts and any test harness defects before merge. No production bug is asserted without reproduction. SQLCipher/runtime DB preservation is P0; do not bypass journal/mutation gates to force green. Two independent Windows EXEs and remote staging remain BLOCKED/NOT RUN. No Coordinator or remote rights changes.

## CI #870 audit and correction
At head `124e220c7c9168fbc216b8dfbc1f2678be20cfa8`, CI https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41429877044 failed only `test_remote_accepted_but_ack_unknown_requires_exact_reobservation` on Windows shard 1 (1188 passed, 1 failed, 2 skipped). Failure was at the test's `pytest.raises(RecoveryRequired)` **after** successful `published()` verification. Source `WriteRecoveryJournal.assert_replaceable()` expressly admits a verified PUBLISHED receipt when exact runtime hash, local accepted files, repo identity/OID and clean Git state match; `released()` separately marks CLEAN. **QA assertion defect** rather than proven product failure. Commit `ae685148108a6211f0f6ed2f20715163107af489` updates the test to check `release=UNVERIFIED`, permitted replacement for already accepted data and later CLEAN after release. Fresh CI still required; do not mark PASS until confirmed.
