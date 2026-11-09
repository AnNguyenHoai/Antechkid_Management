# Tuition V1 — Release Gate / Founder Manual Acceptance (November 2026)

**Scope:** PR #625, fresh encrypted SQLCipher database, business records re-entered from **01/11/2026**. This is a **candidate** and not an authorization to deploy. Do not alter `Antechkid_CenterManager_DatabaseOfficial` or Git-only WRITE/lease/CAS logic.

## Automated engineering evidence (must all be GREEN on the same final SHA)

- [ ] **Full Pytest Suite**: Windows shard 0/1/2 success. Record run URL, tested SHA, and test report artifacts.
- [ ] **Tuition V1 Production Fast Regression**: targeted finance, schema, UI, architecture, admin reset tests success. Record run URL and SHA.
- [ ] **Tuition V1 Production Candidate Windows EXE**: release ZIP built, RELEASE_MANIFEST source_commit matches SHA, no embedded `center.db`, `database_key.dpapi`, or `git_config.dpapi`. Record artifact name, SHA-256 and run URL.
- [ ] **Isolated SQLCipher bootstrap in Windows CI**: freshly generated `center.db` is encrypted; signed `center.db.identity.json`, canonical `manifest.json`, local Git main and READY state exist. Record run URL.
- [ ] Review the final PR diff for unintended changes to existing legacy classes, old database, WRITE/CAS, authentication/provisioning and finance; resolve critical observations.

**Current automated evidence:** The older PR #625 head `35b10423e9c8beeb9f3997b93bf174677c164d22` had 3/3 Windows pytest shards PASS (run #42600612061). New regression changes in commit `d4280a7026d5fee08c926694c133cf5fb03a83c8` require **new final-head CI verification**. Do not substitute older green checks or assume newly defined build workflows ran successfully.

## Founder-owned manual acceptance: isolated Windows environment, not production

Complete and attach *redacted* evidence to issue #623. Mark every item PASS/FAIL/NOT_RUN. Any FAIL or NOT_RUN blocks general release.

- [ ] Download the candidate ZIP for **the exact accepted commit**, verify `.sha256` and `RELEASE_MANIFEST.json` before extraction.
- [ ] Use a **clean Windows profile and short paths**; generate an isolated fresh SQLCipher workspace with `scripts/prepare_sec06_isolated_uat.py`, using a new local bare Git remote first. The directories must not exist before the command.
- [ ] Confirm the DB is encrypted, signed sidecar and canonical manifest exist, admin password-change flow operates, and no student/class/income history exists.
- [ ] Provision a **new PRIVATE empty GitHub database repo**, NOT the existing official database. Verify repository URL, branch `main`, DPAPI destination binding and fine-grained credential. Never upload keys, decrypted DBs or tokens as evidence.
- [ ] Create a class with policy **Theo tháng (lớp mới)**; generate complete original calendar and ACTIVATE the first November plan **before** entering that class's students/income/attendance. Repeat for a second class to confirm sequential initial setup.
- [ ] Verify a weekend class from 01/11/2026 has 9/8/10/8 lessons in Nov/Dec/Jan/Feb; planned session upper bound covers all 35 lessons; monthly fee is identical in all four plans.
- [ ] Register a learner with joining date **01/11/2026** (full November fee) and another **09/11/2026** (only six original remaining sessions). Confirm Tuition Detail and invoice quote amounts; do not substitute data-entry date for actual join date.
- [ ] Post one monthly and one three-month payment with actual historical payment dates. Verify exactly one Income per receipt and month-by-month accrual, Wallet/Outstanding/Tuition Detail/reports reconciled to paper/bank evidence.
- [ ] Exercise absence/makeup, centre cancellation without makeup before and after collection, reschedule across month boundary, retry/idempotency, archived/withdrawn classes and legacy policy isolation.
- [ ] On two actual Windows clients verify READ startup, acquire WRITE, Finish Editing/publish, restart, rejection of stale writer, backup/restore and crash/recovery. Verify Git MAIN reflects the latest authorized, nonduplicated business transactions.
- [ ] Reconcile opening balances and any obligations from the old system. A new empty DB does **not** extinguish historic debt or refunds. Capture signed founder acceptance **before** the first real production transaction.

## Evidence register

| Field | Value |
|---|---|
| Accepted source SHA | PENDING |
| Full pytest run URL / result | PENDING |
| Focused regression run URL / result | PENDING |
| EXE build run URL / artifact / SHA-256 | PENDING |
| Isolated encrypted bootstrap run URL | PENDING |
| Windows app version and runtime manifest | PENDING |
| UAT SQLCipher/finance evidence location (no PII/secrets) | PENDING |
| Two-client WRITE & recovery evidence | PENDING |
| Founder name/date and PASS approval | PENDING |

**Decision:** BLOCKED until all mandatory CI results match the final source SHA **and** all founder manual acceptance checks PASS. Only then review/merge PR #625 and authorize a controlled rollout. Do not pre-emptively mark #623 complete.

**Detailed procedure:** `docs/finance/TUITION_V1_PRODUCTION_FRESH_DB_RUNBOOK.md`; parent acceptance GitHub issue #623.
