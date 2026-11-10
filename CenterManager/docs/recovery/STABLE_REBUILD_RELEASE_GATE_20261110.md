# Stable CourseFee reconstruction — release gate

Base: `06ab884013f86aa331a6696340e5ac97029a3fe0`.
Source release branch: `release/coursefee-stable-rebuild-20261110`.
Database repository branch: independently configured (existing production uses `main`).

## Included backports
- Windows console Unicode-safe logging.
- Student ACTIVE defaults, complete filtered export, ACTIVE-only Excel export.
- Voucher count / filename / SHA256 in Income and Expense CSV.

## Excluded regressions
- New `cf26a001` migration and unconditional `1e10a046` block.
- Source branch name mistakenly enforced as database branch.
- Automatic Alembic revision stamp/relabel from unproven schemas.
- New-schema idempotency and extensive Recovery rewrite until separately reviewed.

## Verification required before release
- [ ] Three Windows pytest shards PASS on the PR head.
- [ ] Package Windows EXE from this exact commit, inspect bundled Alembic head.
- [ ] Offline copy of real encrypted course-based DB opens read-only.
- [ ] Git MAIN fetch, startup, login, Start Editing and Finish Editing verified.
- [ ] CSV exported with and without vouchers, including multiple vouchers.
- [ ] Student filtering, paging and exports checked with archived records.
- [ ] Recovery remains advisory; Git MAIN remains authoritative.
- [ ] Existing course-based invoices and student balances unchanged.

Do not deploy or merge this back into the broken source branch by ordinary
merge: it would not remove the divergent unsafe commits.
