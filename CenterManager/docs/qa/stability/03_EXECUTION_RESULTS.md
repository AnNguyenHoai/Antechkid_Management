# Execution results — initial submission
Baseline: `7b6744eb4c95b850c994e38b7350053fcd11b87e`.
Historical handover: main_repos Windows CI #848 PASS at baseline, https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41408024538. This is historical baseline evidence only, not this new QA branch's test result.
Added: `tests/test_qa_stability_s01_wal_atomicity.py`, three new isolated tests; **NOT RUN** when this report was authored.
Commands (CenterManager working dir): `python -m pytest tests/test_qa_stability_s01_wal_atomicity.py -q`; `python -m pytest tests/test_qa_p0_recovery_fault_injection.py tests/test_e1b1_durable_write_recovery.py -q`.
New test execution at authoring: PASS 0 / FAIL 0 / SKIP 0 / NOT RUN 3. Existing tests: NOT RE-RUN in this QA branch.
2-Windows-client EXE UAT: BLOCKED, requires isolated staging remote and two provisioned Windows test clients. Production Git/real user data must never be used.
Do not update PASS count from old markdown or infer field deployment safety from GitHub CI. Record exact check SHA and jobs after CI completes.
