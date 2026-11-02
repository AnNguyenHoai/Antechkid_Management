# QA-S02 — Multi-client waiting queue lifecycle (first tranche)

Baseline: `main_repos` `1da4a9dda22b3160ff365a3b71d5a3518f580be4`, merge PR #540.
Earlier branch SHA `22ce639bdd0f5ea729937ca6b85c3f4fdb08e627` CI #872 PASS: https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41432362251.

## Tests
- Cancelled waiting client must vanish from three independently cloned runtimes' shared queue, including idempotent cancel; active remote WRITE owner session/ref must be unchanged.
- With two waiting clients, cancellation of the first must preserve the second client's request as queue head and must not revoke current WRITE.

Tests use existing `_seed_remote` and `_make_machine` fixtures with disposable local bare Git. No EXE, credentials or live Git repo.

Command: `cd CenterManager && python -m pytest tests/test_qa_stability_s02_queue_lifecycle.py -v`

New tests: **NOT RUN** at creation. Do not claim CI PASS until exact branch SHA checks finish.

## Remaining release gates
- Two independent *packaged Windows EXEs* on isolated remote staging: BLOCKED/NOT RUN.
- Lease expiry and grace, network outage at acquire/publish, stale same-username release, process crash/renewal, UI queue projection: retain as QA-S02 follow-up; older automated coverage exists but is not physical 2-PC evidence.
- No production changes. Report any FAIL as fixture/environment/product defect with remote lock/queue refs and DB/journal evidence before scoped dev handoff.
