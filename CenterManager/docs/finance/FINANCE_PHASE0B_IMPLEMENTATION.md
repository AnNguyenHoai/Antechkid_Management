# Finance Phase 0B — attribution detector implementation

**Stacked base:** Phase 0A PR #517 at `ddc98cc645bc18904287b14cf1156a8976cc0189`. This PR adds no schema, UI, export or financial mutation. Once #517 is merged, retarget the 0B PR to `main_repos` and verify its diff/CI again.

## Delivered

- D01: ACTIVE, nondeleted Tuition Income up to an explicit as-of date with no Enrollment attribution. Candidate count includes canonical Enrollment contracts for the same student/class, including withdrawn/completed contracts; it is evidence, not an automatic match.
- D02: ACTIVE, nondeleted Tuition Income linked to a missing Enrollment, a different student/class, or an Enrollment reconciled into another. The finding carries persisted and linked IDs for review. A legitimate late payment to the exact withdrawn/archived Enrollment is not flagged.
- `FinanceDiagnosticsService.get_findings` requires `finance.view`, returns an explicit `OK` or `ERROR` state, stable D01-then-D02 and Income-ID ordering, counts per selected rule, at most 100 scalar rows per page, an as-of date and source version. Unknown rule/invalid paging is rejected before querying.
- The Income repository enables SQLite/SQLCipher `PRAGMA query_only` for the diagnostics session and resets it before returning the connection to the pool. The service uses `no_autoflush`, never commits, and returns a generic error code without SQL parameters or personal data when a read fails. This keeps connection access within the repository boundary.

## Deferred deliberately

**D04 OWED/PREPAID summary:** `OutstandingService.get_outstanding_page` currently materializes all candidate Enrollments and calls accrual/session and payment aggregation for each row before computing its separate OWED/PREPAID totals. Calling it from a small diagnostics page would bypass the bounded-query and no-N+1 gate. Phase 0B therefore does not expose a partial or misleading balance summary. Design a batched accrual projection or a separately budgeted background scan, preserving exact Enrollment attribution and unresolved-contract state, before adding D04.

D03 requires the retroactive accounting-period policy; D05 requires the Settlement explanation rule. D06–D10 retain the blocked/deferred status in `FINANCE_DIAGNOSTICS_RULE_CATALOG.md`. D01/D02 do not claim that any production record is anomalous.

## Verification gate

Synthetic tests cover missing/ambiguous attribution, mismatched and reconciled identity, missing linked contract, a legitimate withdrawn/archived payment, VOIDED/deleted/non-Tuition/future rows, pagination, permission denial, explicit read failure and connection reset. A 250-row fixture asserts one SQL page of 100 and a constant statement count. The logical Income snapshot is unchanged after reading, and an injected repository write is rejected by query-only mode. Full Windows CI and human review remain required.
