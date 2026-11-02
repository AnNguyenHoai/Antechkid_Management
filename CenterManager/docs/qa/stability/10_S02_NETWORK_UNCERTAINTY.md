# QA-S02 R3 — Git observation outage and durable recovery

Baseline: `main_repos` `6f446f2024ceaed316ec1effd0cf95139753ff1f` (merged #542).
Previous CI: [#876 PASS](https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41468437185), PR #542 head `d7f07df169dc26919500f05aba60ee9475c6d09e`.

## Injection and expected oracle
Three parametrized cases, using real synthetic SQLCipher workspace and disposable Git remote via E1B1 fixture.
1. Remote observation yields None: PUBLISHING remains UNVERIFIED; committed DB rows and prior verified capture survive newly constructed journal instance.
2. Remote observation yields mismatched OID: same fail-closed protections, no silent CLEAN.
3. Remote observation raises injected OSError: exception propagates, PUBLISHING journal remains durable, replacement denied.

Command: `cd CenterManager && python -m pytest tests/test_qa_stability_s02_network_uncertainty.py -v`.

**Status:** New 3 cases NOT RUN at authoring. Await exact SHA Windows CI before claiming PASS.

## Limits and release gates
These tests target the **journal verification boundary** after a SQL commit. They are not network fault injection against the full UI transaction, nor a real Git transport outage. They do not prove safe WRITE lock acquisition under lost network, lease/grace timing, or absence of UI freeze. Existing lock acquisition diagnostics tests cover separate errors; packaged Windows 2-PC staging is still BLOCKED/NOT RUN.

Do not modify production Git remote, credentials, real database or deploy Coordinator. Classify any failure as fixture/production issue with exact SHA and traceback.
