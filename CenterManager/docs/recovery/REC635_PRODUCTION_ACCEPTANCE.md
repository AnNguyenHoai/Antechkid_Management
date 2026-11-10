# Issue #635 — Production acceptance and runbook

**Status:** ENGINEERING HARDENING IN PROGRESS. A green Windows GitHub Actions
run is not the same as physical EXE/UAT acceptance. Do not close Issue #635
or advertise full disaster recovery until all gates below have evidence.

## Invariants

- Git remote MAIN remains authoritative and the only normal startup source.
- Startup/login must succeed with validated MAIN even with an old unreviewed
  recovery journal, an inaccessible/oversized old proof, or an unreadable log.
- Recovery evidence never grants WRITE, replays commands, pushes commits or
  mutates the source snapshot. No recovery file may be silently discarded.
- **Skip** leaves a notice pending; **Đã kiểm tra** acknowledges only that
  notice and does not delete preserved backup/evidence.
- A report is an observation, not a replay plan. Finance duplicates are NEVER
  automatically posted.

## Automated release gates (Windows GitHub Actions)

- [ ] All 3 Full Pytest Windows shards green at exactly the candidate head SHA
- [ ] Authentic HMAC manifest, tampered DB/WAL proof, wrong DPAPI key,
      missing capture and schema drift all result in unavailable/UNKNOWN
- [ ] Real Windows user-scoped DPAPI key round trip with SQLCipher DB and a
      detached, uncheckpointed WAL, with original DB/WAL hashes unchanged
- [ ] Clean MAIN checks for matching local/fetched/remote commit, signed DB
      identity and absence of dirty DB/identity working-tree edits
- [ ] No cross-generation numeric ID is accepted as student/enrollment/session
      identity without a stable crosswalk
- [ ] Startup proof >128 MiB is unavailable rather than synchronously hashed;
      original evidence stays intact
- [ ] Finance export denied without finance.view; no plaintext created on
      startup or canceled user action
- [ ] Snapshot SQLCipher connections are closed before temp cleanup on Windows

## Packaged Windows EXE / two-client acceptance (manual, real hardware)

Record release SHA, EXE hash, database identity/generation, local OS account,
test scenario ID, logs and redacted screenshots. Use disposable, fabricated
students and payments; never use production invoices or access tokens.

1. **Normal restart:** install candidate EXE on two PCs; verify accepted
   remote MAIN is installed and both READ without an old journal.
2. **Unpublished change on A:** create student + monthly enrollment, income,
   expense and session outcome on disposable DB while WRITE, then interrupt
   A before Finish Editing. Restart A. Git MAIN must win; old DB/WAL and
   review notice must survive; UI must open without waiting for Recovery.
3. **A Skip/Reviewed:** Skip then restart must remind; Reviewed then restart
   must suppress that case only. The capture remains intact both times.
4. **A authenticated comparison:** finance.view can export JSON by deliberate
   click. No other user can. Verify report OID equals the remote observed MAIN;
   identical receipt, changed amount, absent key, ambiguous reused ID,
   changed monthly outcome, and schema drift produce conservative statuses.
5. **B advances MAIN:** while A is viewing an old notice, B commits new MAIN.
   A must decline outdated comparison rather than use stale remote contents.
6. **Permissions:** start EXE under the same Windows account (DPAPI can read)
   and a different Windows account (DPAPI must fail securely without destroying
   captured ciphertext or blocking MAIN login).
7. **Crash boundaries:** kill A between old DB move, WAL move, signed proof
   creation and new MAIN install. Every restart must reach validated MAIN or
   provide an explicit original install integrity failure; evidence must never
   be silently reclassified verified.
8. **Large/long paths:** old DB >128 MiB must be retained without a long
   synchronous proof; deeply nested Vietnamese attachment paths must not
   corrupt the original evidence. Don't rely on PR #632 being merged.
9. **Finance duplicate safeguards:** manually try to re-enter an income from
   NOT_FOUND. Verify operating procedure forces checking idempotency,
   student/class identity, voucher, wallet and outstanding; no automatic entry.
10. **Performance:** measure time from app launch to login and time to enter
    READ for clean vs pending-recovery installations. Record comparison export
    separately (on-demand, may be slow); no startup regression accepted.

## Report scope, not a promise of debt reconstruction

- Compares authenticated idempotency-keyed ledger facts and opt-in monthly
  events. It does not implement authoritative balance reconstruction across
  all old and current tuition policies.
- The report may show day-aggregated monthly allocations, **not** proof that
  every session ID represents the same scheduled lesson.
- Wallet summary is only cash/bank transaction movement without opening balance.
- Outstanding remains UNKNOWN unless the existing canonical TuitionAccrual
  service can be executed against both isolated verified snapshots under
  corresponding schema and transaction policy. Do not introduce an ad-hoc
  formula or quietly interpret unresolved tuition as zero.
- A matching numeric FK in a newly created database is not a stable identity.
  Identical receipt money/date/method with unknown student attribution is
  UNKNOWN, not conclusively PRESENT_IDENTICAL.
- Old rollback generations without signed provenance remain UNAVAILABLE;
  do not fabricate a signature after the incident as retroactive proof.

## Completion criteria

Only mark Issue #635 complete when automated test output AND packaged Windows
two-PC evidence are attached, finance/tuition reviewers sign off on UNKNOWN
coverage, and no P0/P1 crash, startup blocker or duplicate cash posting remains.
Otherwise keep Issue #635 open with the exact remaining gate described.
