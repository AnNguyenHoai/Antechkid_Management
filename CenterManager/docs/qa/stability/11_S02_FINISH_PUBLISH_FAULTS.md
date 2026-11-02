# QA-S02 R4 — Finish Editing publish transport failures

**Baseline:** `main_repos` `435b0526d4a6b0e7a132eac31675767494386411` (PR #543 merged).
**Prior CI:** PR #543 SHA `95ddea1509349a0292811e2a2cd43de7be8289aa` [#878 PASS](https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41472047106).

## Source audit
`WriteTransactionManager._publish` captures SQLCipher work before transport, updates journal to PUBLISHING, delegates to `_do_publish()`, and distinguishes false results from exceptions. The expected state after failure differs (FAILED versus RECOVERY_REQUIRED), but **neither may clear the unaccepted journal or committed data**.

## New cases
Two parameterized synthetic SQLCipher test cases invoke the *real* transaction `_publish` boundary, injecting (a) a false transport result and (b) an OSError from Git transport. Both must leave a verifiable PUBLISHING/UNVERIFIED journal, retain exact committed SQLCipher values and preserve unchanged remote MAIN OID. Repository and key are disposable.

Command: `cd CenterManager && python -m pytest tests/test_qa_stability_s02_finish_publish_faults.py -v`.

**At creation:** two cases NOT RUN. Await exact SHA Windows CI. This is a controlled transport failure at the transaction boundary; it is not proof of an actual network disconnect, physical Windows 2-PC operation or packaged UI liveness. No production changes, hosting, remote permission or Coordinator work. Real staging remains a release gate.
