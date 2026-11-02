# QA-S01 R2 — encrypted recovery continuation

Baseline: `main_repos` `43b8161c06edcd1dbb143dd5538dd1f9851b002a` (PR #538 merged).
PR #538 green branch CI #866: https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41422492544
**New R2 tests are NOT RUN as authored; require CI at exact branch HEAD.**

## Code-level observations
- `WriteRecoveryJournal.verify_capture` authenticates HMAC manifest and SHA-256 hashes of captured files; deliberate ciphertext tampering must raise `RecoveryRequired`.
- `WriteRecoveryJournal.assert_replaceable` forbids replacing data during OPEN/unaccepted state, independently of the original process object.
- `StartupSynchronization.run` must fail closed when unpublished committed SQLCipher data exists. Fixture uses synthetic encryption key and disposable local Git bare remote.

## New cases
1. `test_capture_ciphertext_tamper_is_rejected_without_changing_live_data`: encrypted capture is verified, then one ciphertext byte is tampered. Expected: verification rejected; original runtime SQLCipher rows preserved; replacement denied.
2. `test_new_journal_instance_blocks_startup_overwrite_of_committed_unpublished_data`: SQL commit without Git publish, reconstruct journal object (simulated restart), then trigger startup sync. Expected: OPEN journal survives and startup cannot overwrite committed rows.

Commands in `CenterManager`: `python -m pytest tests/test_qa_stability_s01_sqlcipher_recovery_r2.py -v`.
Real hard-kill Windows EXE recovery and two-PC staging remain **NOT RUN/BLOCKED**; these cases do not claim to simulate OS power failure.
No confirmed production defect; on FAIL preserve fixture logs and distinguish harness vs product behavior. No production code modifications. Release verdict remains provisional HOLD pending extended P0 testing.
