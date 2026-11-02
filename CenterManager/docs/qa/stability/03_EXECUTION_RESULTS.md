# Execution results — initial submission
Baseline: `7b6744eb4c95b850c994e38b7350053fcd11b87e`.
Historical handover: main_repos Windows CI #848 PASS at baseline, https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41408024538. This is historical baseline evidence only, not this new QA branch's test result.
Added: `tests/test_qa_stability_s01_wal_atomicity.py`, three new isolated tests; **NOT RUN** when this report was authored.
Commands (CenterManager working dir): `python -m pytest tests/test_qa_stability_s01_wal_atomicity.py -q`; `python -m pytest tests/test_qa_p0_recovery_fault_injection.py tests/test_e1b1_durable_write_recovery.py -q`.
New test execution at authoring: PASS 0 / FAIL 0 / SKIP 0 / NOT RUN 3. Existing tests: NOT RE-RUN in this QA branch.
2-Windows-client EXE UAT: BLOCKED, requires isolated staging remote and two provisioned Windows test clients. Production Git/real user data must never be used.
Do not update PASS count from old markdown or infer field deployment safety from GitHub CI. Record exact check SHA and jobs after CI completes.

## CI #864 failure triage (2026-11-02)
Workflow: https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41418768520 ; tested head `ed8400c58aa2f313fd9dd2358c97547d786253e2`.
Windows shard 0 PASS, shard 2 PASS, shard 1 FAIL: **1071 passed, 3 failed, 2 skipped**. All 3 failures are new `test_qa_stability_s01_wal_atomicity.py` tests, all blocked at `system_mutation_permit('checkpoint')` with `MutationAuthorityError: Checkpoint requires the runtime maintenance fence`. Root cause: synthetic fixture monkeypatched session quiesce/refresh to no-op, violating the production maintenance fence contract. **Classified QA fixture defect, not a confirmed product/data-loss defect.**
Patch commit `9b89b60ab8246118eb2b77429e0f97972f8d52b4` wires the fixture to the actual runtime maintenance gate `begin_runtime_db_maintenance`/`end_runtime_db_maintenance` without disabling the security check. Await new SHA CI to verify; no PASS claimed yet.
