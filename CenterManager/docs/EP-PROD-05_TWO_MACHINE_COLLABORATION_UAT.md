# EP-PROD-05 — Two-machine Collaboration UAT

## Purpose

Validate the production collaboration contract on two independent Windows machines before Go-Live. This is a physical UAT gate: CI can validate the tooling and source contracts, but it cannot replace two clean runtime environments connected to the same real Git synchronization repository.

Base implementation for this gate is `main_repos@057c26206a10c67880c57ad80a78a10069a14f46`.

## Safety and evidence contract

- Use the same approved release ZIP and verify its distributed SHA-256 on both machines.
- Use a dedicated UAT Git repository or approved production-like repository. Do not experiment on live production data.
- Machine A and Machine B must use separate extracted release folders and separate `runtime/` trees.
- Git repository database remains the source of truth. A stale local runtime database is never authoritative.
- Use unique synthetic markers such as `UAT-PROD05-<UTC>-A` / `UAT-PROD05-<UTC>-B`; do not put real student, parent, employee, credential, token, or other sensitive data in UAT evidence.
- Store all captured evidence outside the source repository. Never commit runtime databases, credentials, logs containing secrets, or recovery snapshots.
- The evidence collector records hashes and bounded state only. It fingerprints the Git remote instead of storing the remote URL.
- A failed scenario is a failed production gate. Do not edit the checklist or evidence to convert a defect into PASS.

## Prerequisites

1. EP-PROD-04 Real Database Upgrade Gate has passed for the production-like database used to seed the release candidate.
2. The release ZIP, `.sha256`, `RELEASE_MANIFEST.json`, bundled MinGit, and source commit are approved.
3. Two Windows machines or two genuinely independent clean Windows environments are available.
4. Both machines can authenticate to the same UAT Git synchronization repository.
5. Keep `CenterManager/scripts/capture_two_machine_uat_evidence.ps1` as an operator tool outside the release folder. It is not part of the distributed application.
6. Create an evidence folder outside the repository, for example `D:\CenterManagerReleaseEvidence\EP-PROD-05`.

## Evidence capture

Run from PowerShell after each important observation:

```powershell
powershell -ExecutionPolicy Bypass -File .\capture_two_machine_uat_evidence.ps1 `
  -Role A `
  -Stage baseline `
  -ReleaseRoot "D:\CenterManager-UAT-A" `
  -OutputPath "D:\CenterManagerReleaseEvidence\EP-PROD-05\A-baseline.json"
```

Use `-Role B` on Machine B and change `-Stage` / `-OutputPath` for each checkpoint.

The collector records:

- release version and source commit from `RELEASE_MANIFEST.json`;
- machine fingerprint, not raw computer name;
- repository HEAD and clean/dirty count;
- SHA-256 fingerprint of the configured Git remote, not the URL itself;
- SHA-256 of `runtime/Database/center.db` and `runtime/repository/database/center.db`;
- whether runtime and authoritative database hashes match;
- bounded local collaboration lock state;
- recovery snapshot count and newest snapshot hash.

## Execution order

### 0. Baseline

- [ ] Extract the exact same approved release ZIP separately on A and B.
- [ ] Verify package checksum on both machines.
- [ ] Configure both to the same UAT Git repository.
- [ ] Start A and B independently and complete authoritative startup synchronization.
- [ ] Confirm both show the same expected seed data.
- [ ] Capture `A-baseline.json` and `B-baseline.json`.

### 1. A → B exact edit / publish / synchronization

- [ ] On A, acquire WRITE through the normal application flow.
- [ ] Change one safe UAT field to the unique marker `UAT-PROD05-<UTC>-A`.
- [ ] Finish/publish normally and confirm success.
- [ ] Capture `A-after-publish.json`.
- [ ] On B, synchronize/restart through the normal production path.
- [ ] Verify the exact marker and exact field value from A are visible on B.
- [ ] Capture `B-after-A-sync.json`.
- [ ] Confirm A and B authoritative/runtime database hashes converge.

### 2. B → A exact edit / publish / synchronization

- [ ] Repeat the previous scenario in the opposite direction using `UAT-PROD05-<UTC>-B`.
- [ ] Verify the exact B marker on A after synchronization/restart.
- [ ] Capture `B-after-publish.json` and `A-after-B-sync.json`.
- [ ] Confirm the repository HEAD and authoritative/runtime database hashes converge again.

### 3. Internet loss while READ / startup

- [ ] Put B in READ mode and stop the application.
- [ ] Make B's local runtime database intentionally stale using only approved synthetic UAT data.
- [ ] Disconnect B from the network or otherwise make the authoritative Git repository unavailable.
- [ ] Start CenterManager on B.
- [ ] Confirm startup fails closed instead of accepting the stale local database as authoritative.
- [ ] Restore network access and restart.
- [ ] Confirm authoritative synchronization succeeds and overwrites the stale runtime database.
- [ ] Capture `B-network-restored.json`.

### 4. Finish/publish failure and retry

- [ ] On A, acquire WRITE and make a unique synthetic change.
- [ ] Make the remote unavailable immediately before Finish/publish.
- [ ] Attempt Finish and confirm the application reports failure; it must not falsely report a successful publish.
- [ ] Confirm the unsafely unpublished change is not silently exposed as authoritative data on B.
- [ ] Capture `A-finish-failed.json`.
- [ ] Restore the remote and use the supported retry/recovery path.
- [ ] Finish/publish successfully exactly once.
- [ ] Synchronize B and verify the exact change appears once with no data loss or duplicate logical operation.
- [ ] Capture `A-finish-retried.json` and `B-after-finish-retry.json`.

### 5. Crash while holding WRITE

- [ ] On A, acquire WRITE and make a unique synthetic change.
- [ ] Force terminate CenterManager before normal Finish/release.
- [ ] Do not delete runtime collaboration or recovery files.
- [ ] Start B and confirm B cannot bypass A's still-valid remote lease to publish competing data.
- [ ] Restart A and verify the supported recovery/retry path is visible and preserves recoverable work.
- [ ] Complete recovery/Finish or explicitly discard through the supported application flow.
- [ ] Confirm both machines converge after synchronization.
- [ ] Capture `A-after-crash-restart.json` and `B-after-crash-recovery.json`.

### 6. Competing lease

- [ ] A acquires WRITE and keeps the lease valid.
- [ ] While A still owns the valid lease, B requests WRITE.
- [ ] Confirm B remains READ/waiting/rejected according to the current product UI and cannot publish.
- [ ] Confirm A can renew/maintain its valid lease.
- [ ] A finishes/releases normally.
- [ ] Confirm B can subsequently obtain WRITE only after the authoritative lease allows it.
- [ ] Capture evidence before and after the handoff.

### 7. Stale runtime fencing

- [ ] After a successful publish, stop B.
- [ ] Replace only B's local `runtime/Database/center.db` with an older approved UAT copy.
- [ ] Keep Git available and start B.
- [ ] Confirm startup rematerializes the authoritative repository database and the latest marker returns.
- [ ] Confirm runtime and repository database SHA-256 values match after startup.
- [ ] Capture `B-stale-runtime-repaired.json`.

### 8. Restart / retry stability

- [ ] Close both applications normally after all previous scenarios.
- [ ] Restart A and B independently.
- [ ] Confirm no phantom WRITE ownership, no false success, and no stale local-authoritative fallback.
- [ ] Confirm both machines show the same final UAT markers and authoritative state.
- [ ] Capture `A-final.json` and `B-final.json`.

### 9. Recovery snapshot evidence

- [ ] For a scenario that exercises failed Finish or crash recovery, confirm the expected recovery snapshot/evidence is created by the product's supported recovery path.
- [ ] Do not commit or attach the database snapshot to GitHub.
- [ ] Record only snapshot count/hash and the operator observation in restricted evidence.
- [ ] Confirm a successful recovery/retry does not leave the product in an ambiguous WRITE state.

## Scenario report

Create `scenario-report.json` in the restricted evidence folder. Every required scenario must be `PASS` before the gate can pass:

```json
{
  "task": "EP-PROD-05",
  "scenarios": [
    {"scenario": "a_to_b_publish_sync", "status": "PASS", "note": "exact marker observed"},
    {"scenario": "b_to_a_publish_sync", "status": "PASS", "note": "exact marker observed"},
    {"scenario": "internet_loss", "status": "PASS", "note": "startup failed closed; restored sync passed"},
    {"scenario": "finish_failure", "status": "PASS", "note": "no false publish; retry passed"},
    {"scenario": "crash_in_write", "status": "PASS", "note": "lease fenced; recovery passed"},
    {"scenario": "competing_lease", "status": "PASS", "note": "second writer fenced"},
    {"scenario": "stale_runtime", "status": "PASS", "note": "authoritative DB rematerialized"},
    {"scenario": "restart_retry", "status": "PASS", "note": "final state converged"},
    {"scenario": "recovery_snapshot", "status": "PASS", "note": "restricted recovery evidence captured"}
  ]
}
```

For the final steady-state captures, run the verifier from a controlled source checkout:

```bash
python scripts/verify_two_machine_collaboration_uat.py \
  --machine-a "D:\CenterManagerReleaseEvidence\EP-PROD-05\A-final.json" \
  --machine-b "D:\CenterManagerReleaseEvidence\EP-PROD-05\B-final.json" \
  --scenario-report "D:\CenterManagerReleaseEvidence\EP-PROD-05\scenario-report.json" \
  --output "D:\CenterManagerReleaseEvidence\EP-PROD-05\verification-report.json"
```

## Automated verification PASS contract

The verifier fails closed unless:

1. Both captures are EP-PROD-05 schema v1 and represent distinct roles A/B.
2. Release version and exact source commit match on both machines.
3. Both machines point to the same Git remote fingerprint.
4. Both repository HEADs converge.
5. Each runtime database hash equals its local authoritative repository database hash.
6. A and B authoritative database hashes converge.
7. All nine required physical UAT scenarios are present exactly once and are `PASS`.

The verifier intentionally does not claim that a hash proves UI behavior. Exact field/marker observations, failure messages, and recovery behavior remain physical operator observations recorded by the scenario report.

## Failure handling

If any scenario fails:

- mark it `FAIL` or `BLOCKED`, never `PASS`;
- keep the restricted evidence and reproduction sequence;
- classify environment/configuration failures separately from confirmed product defects;
- fix confirmed product defects in a separate implementation/regression commit or PR;
- rerun the affected scenario and final convergence gate after the fix.

## Completion gate

EP-PROD-05 passes only when the two-machine physical UAT is complete, all scenario statuses are `PASS`, the final machine captures converge, targeted regression passes, full regression passes, and the generated verification report says `PASSED`.
