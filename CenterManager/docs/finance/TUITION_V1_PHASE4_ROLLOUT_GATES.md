# Tuition Engine V1 — Phase 4 rollout and acceptance gate

**Status: BLOCKED / NOT RELEASE READY.** This is a fail-closed release checklist, not approval for production activation.

## Authoritative invariants
- Git MAIN SQLCipher is the source of truth. Existing WRITE authority is mandatory for all mutations.
- Legacy Enrollment snapshot and TuitionAccrualService remain authoritative until explicit future-dated opt-in is approved per Enrollment.
- Quarterly payment represents one genuine receipt in Income; monthly earned tuition is distinct from cash received.
- Center cancellation with no makeup reduces the tuition obligation by the original allocation. If projected accrual already reflects that, never post another credit for the same cancellation.
- No automatic reinterpretation/backfill of historical data.

## Production preflight
1. Ensure all users have exited WRITE, synchronize approved Git MAIN.
2. Verify an encrypted backup using separate isolated SQLCipher copy; record checksum and MAIN OID; do not publish student details.
3. Reconcile Income, Wallet and Enrollment outstanding totals before any change.
4. Inspect schema version. Run migration exclusively through existing keyed startup/maintenance gate.
5. Ensure additive migration never updates legacy Enrollment, Income, Session or TuitionAdjustment rows.
6. Enforce read-only opt-in migration gate: reject uncertain historic tuition, unattributed payments, unresolved reconciliation, retroactive effective date, missing verified backup or WRITE authority.
7. Do not activate billing until all finance, outstanding, tuition detail and UI readers agree on the same effective policy.
8. Repeat aggregate reconciliation, restore exercise and Windows EXE operator UAT before release.

## Mandatory regression matrix
| Test | Required result |
| --- | --- |
| T01–T03 | 8/9/10 sessions sum exactly to monthly fee |
| T04 | Two classes sessions on same calendar day have distinct Session IDs |
| T05 | Mid-month enrolment bills only remaining original planned sessions |
| T06 | Student absence billed once, makeup does not rebill |
| T07 | Center cancel before charge waives original fee |
| T08 | Center cancel after payment increases prepaid by same fee |
| T09 | Duplicate cancel or retry cannot double-credit |
| T10 | Reschedule retains original amount and no duplicate charge |
| T11 | Quarterly prepayment creates one cash receipt, not three accruals |
| T12 | Closed accounting period cannot be altered |
| T13 | Archived/withdrawn/transferred Enrollment keeps history and balances |
| T14 | Lost WRITE lease and unauthorized DB mutations rejected |
| T15 | Crash/retry durable evidence and recovery outbox reconciled |
| T16 | All legacy balances unchanged by additive schema |
| T17 | Finance, Student Profile and Tuition Detail numbers reconcile |
| T18 | Windows EXE UAT confirms month/quarter, payment, cancellation UI |
| T19 | Encrypted backup restoration works |
| T20 | Finance permissions and audit trails correct |

## Remaining blockers
- Persisted monthly plan activation under authorized WRITE, concurrent version checking, permission, audit and outbox.
- Effective-dated Enrollment opt-in and shared policy selection for TuitionAccrualService, OutstandingService, TuitionDetailService, Wallet and Income.
- Idempotent charge/reversal commands for cancellation and reschedule, compatible with existing Income/TuitionAdjustment.
- Month/quarter quote and operator preview UI; correct handling of active and archived classes.
- Transactional SQLCipher tests, migration restore, multi-user conflict/retry, EXE UAT and report reconciliation.

CI green is necessary but insufficient. Keep master #615 open until every item is implemented and evidenced.
