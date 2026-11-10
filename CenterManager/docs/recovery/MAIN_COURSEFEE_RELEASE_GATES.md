# main_coursefee port — phase 4/5 release validation

BASELINE: `06ab884013f86aa331a6696340e5ac97029a3fe0`
SOURCE: `main_repos` audited at `1aa2b9cbdae58826421fcee3e1d33b9045ac22ed`

## PR chain (no direct main_repos merge)

- Phase 2: PR #638 (Recovery, Git MAIN-first, advisory only).
- Phase 3: PR #639 (Income/Expense retry, voucher, accounting logs).
- Phase 4/5: this QA PR (course-fee exclusion regression and release gates).

## NON-NEGOTIABLE

- Do not introduce `monthly_tuition_*` models, tables, services, UI, quotes, allocations, or monthly/quarterly Tuition Income payment flows.
- Alembic chain on this branch remains `1e10a045 -> 1e10a046` (FIN-03 only); do not graft revisions `1e10a046_monthly_tuition_opt_in`, `1e10a047_monthly_class_defaults`, `1e10a048_finance_submission_keys`.
- Fee and debt computations remain exclusively pre-existing legacy course/session tuition services.
- Git MAIN is sole authoritative DB. Recovery is a local log/manual review only; startup cannot be denied because of pending acknowledgement; no old DB or local mirror may be re-published automatically.
- Never mark a missing recovery key as a lost transaction; verify Income/Expense identity and voucher before manual entry.

## Gate A — CI

- [ ] Exactly the final SHA runs all 3 Windows Pytest shards and passes.
- [ ] Alembic upgrade/downgrade tests from pristine course-fee baseline.
- [ ] Income/Expense double-Save keyed retry produces exactly one row.
- [ ] Voucher failed upload retry attaches once and does not duplicate Income/Expense.
- [ ] Personal payment pending -> reimbursed moves company wallet once; cannot revert to Pending by Edit.
- [ ] Recovery authenticated old DB/WAL and pending review do not block validated Git MAIN READ.
- [ ] All original course-fee enrollment/outstanding/receipt/attendance tests pass.
- [ ] Static scan excludes monthly tuition imports/periods from modified modules.

## Gate B — Packaged Windows/dual-client UAT

- [ ] Clean EXE starts and fetches MAIN on PC A and PC B.
- [ ] Crash after un-published WRITE on A: A restarts on MAIN, retains old encrypted DB/WAL and review notice.
- [ ] Skip repeats the reminder on next launch; Reviewed suppresses only that incident.
- [ ] Finance VIEW and expense permissions limit report/export; deliberate user choice only.
- [ ] Normal course enrollment / partial tuition by session / refund and archived debt balances identical to pre-port baseline.
- [ ] Synthetic income and expense recorded, voucher added, manual retry made, no duplicate posted amount.
- [ ] Existing DB at migration head `1e10a045` upgrades to `1e10a046` and opens; no monthly tables appear.
- [ ] Fresh installation at head `1e10a046` opens; no monthly payment UI.
- [ ] Rollback/restore plan documented, with old original ciphertext and user DPAPI bundle preserved.

## Gate C — Release approval

Never merge the PR chain into `main_coursefee` until CI is green and a reviewer confirms physical Windows UAT. Resolve phase2/phase3 independently; merge in order #638 -> #639 -> QA. If any check fails, keep all PRs draft and record failing SHA/logs. Do not merge into `main_repos`.
