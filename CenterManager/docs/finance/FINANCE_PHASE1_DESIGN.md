# Finance Diagnostics Workspace — Phase 1 design proposal

**Status:** design for founder review, not an implemented UI or approval to mutate finance history. Phase 0A audit and Phase 0B D01/D02 detector are merged on `main_repos`. Phase 0C adds the bounded CSV export. No production database was inspected; anomaly counts below are intentionally unspecified.

## 1. First release: read-only evidence

The first workspace presents *candidate findings*, not accounting adjustments. It uses `FinanceDiagnosticsService.get_findings(as_of_date, rule_id, page, per_page)` with `finance.view` authorization. The service returns `OK` with an explicit zero count for a genuinely empty result, or `ERROR` with `DIAGNOSTICS_READ_FAILED`; the UI must never turn an error into a zero-balance or empty-success screen.

| Area | Display / interaction | Source and limit |
|---|---|---|
| Header | As-of date, UTC detection time, source version, refresh action | Page DTO. Date required; it is a payment-date cutoff, not a historical snapshot of edits made after that date. |
| Counts | D01 and D02 candidate counts, overall count | Counts in the same authorized read; severity labels `REVIEW`/`HIGH` describe review priority, not confirmed loss. |
| Table | Rule, priority, Income ID, Student/Class/Enrollment IDs, observed amount, payment date, short evidence | Server-side page `1..n`, size `1..100`; D01 then D02, ascending Income ID. No family names. |
| Detail | Persisted IDs, linked IDs, candidate count, guidance, false-positive note, as-of/detection/version | Existing finding DTO. Open the normal Income/Enrollment workflow through its authorized service/UI; do not edit in the detector. |
| Export | Selected rule and as-of date; explicit row limit/error | `export_findings_csv`, maximum 10,000 rows, no partial file; UTF-8 text and formula-safe cells. UI writes UTF-8 with BOM for spreadsheet compatibility after `OK` only. |

Rule filter is `D01`, `D02`, or all. Search by entity ID and additional filters are **not implemented** in Phase 0C; add server-side repository filters with count/page consistency before exposing controls. A client-side search of only the current page must not pretend to cover all findings.

### Suggested layout

1. Top bar: date selector, refresh, rule filter, export button; show `source_version` and detection time.
2. Counts: total, D01, D02; no money-impact sum because the observed payment amount is not an amount lost or owed.
3. Paginated table with clear `ERROR`, `EMPTY`, and `LIMIT_EXCEEDED` messages.
4. Detail panel with exact IDs and the existing review guidance; link to authorized transaction view if that route exists in the workspace.

## 2. Service and export contract

`get_findings` returns `FinanceFindingsPage` with `state`, `total_count`, `counts_by_rule`, `findings`, `as_of_date`, `detected_at`, and `source_version`. `export_findings_csv` returns `FinanceFindingsExport` with `state=OK|LIMIT_EXCEEDED|ERROR`, count metadata, and `csv_text` only on success. Invalid input raises `ValueError`; missing `finance.view` raises the established permission error. SQL reads are repository-owned and guarded by `PRAGMA query_only` within one session per call. Export counts first, rejects an oversized result, then reads bounded pages in that session. It does not silently cap the CSV; a short page or query failure returns `ERROR` without bytes.

CSV fields are rule, severity, entity type/ID, Student/Class/Enrollment and linked IDs, candidate count, observed amount, payment date, as-of date, detection time, source version, evidence, review guidance and false-positive note. It excludes names, contact details, free-form transaction notes, and SQL/log parameters. Text cells that could be interpreted as spreadsheet formulas are prefixed with a literal apostrophe. Export remains a set of *findings*, not a ledger or statement.

An export that exceeds 10,000 rows returns `LIMIT_EXCEEDED` and its count; the user should narrow the rule/date scope or request a separately designed streamed export. Neither a known short page nor a quiet cap is allowed. A single SQLAlchemy session does **not** guarantee a stable database snapshot under every SQLite driver transaction mode: concurrent writes between count and pages could change which rows are seen without creating a short page. The first UI release must label the export as a live diagnostic run, not a historical point-in-time ledger extract. If an auditable immutable export is required, define a dedicated read snapshot/transaction and concurrent-writer regression before release. The as-of cutoff filters payment dates but does not recreate old database state.

## 3. Deferred KPI and review workflow

| Requested feature | Gate before implementation |
|---|---|
| Total `OWED` and `PREPAID` | Batch accrual/payment projection by exact Enrollment, preserving separate signed balances, archived/withdrawn contracts, and unresolved tuition attribution. Existing `OutstandingService.get_outstanding_page` materializes all candidates and performs per-Enrollment work; do not wire it to a small diagnostics page. |
| Unmatched bank money | Bank statement source and approved reconciliation model (Phase 2). No bank transaction count can be measured today. |
| D03 period mismatch | Founder decision on comparison against posting-time versus current retroactive period definition. |
| D05 Settlement discrepancy | Approved explanation/review threshold; a nonzero explained difference may be valid. |
| Mark reviewed, note, assignment | Reviewer roles and retention policy, separate review-state table/migration, permission, audit event, concurrency/version handling. No status write on Income, Enrollment, or financial ledger. |
| Drill-down | Verify existing workspace navigation and permissions; do not bypass the Income/Enrollment services from UI. |

No migration is needed for the read-only first release. The later review-state workflow needs a forward migration keyed by stable rule, entity type/ID and source version, with reviewer, timestamp, note and revision; define behavior when evidence changes before writing it. Do not overload a finance transaction status to encode a review flag.

## 4. Acceptance and UAT gate for the UI PR

- Authorized `finance.view` user can page through D01/D02 and export a complete allowed result; an unauthorized user cannot invoke either service route.
- Empty, read failure and export limit appear as distinct states; no zero-balance claim is made on failure.
- Legitimate old debt after withdrawal/archive is absent from D02, while mismatched/reconciled links and unattributed Tuition have traceable IDs. VOIDED/deleted/non-Tuition/future payment rows are excluded.
- 250-row synthetic fixture uses bounded 100-row reads; a result over 10,000 is rejected without a partial file. Check CSV in Excel/LibreOffice for UTF-8 and formula safety.
- No finance ledger mutation, long-held WRITE lease, production-data baseline scan, or schema migration in this first UI PR. Manual EXE UAT and Windows CI are still required.

## 5. Follow-up order

1. Founder reviews the D01/D02 meaning and this UI proposal; implement the read-only workspace in a separate PR.
2. Design batched D04 accrual and exact Enrollment totals, with performance evidence and archived/credit/refund fixtures, before adding balance KPI.
3. Resolve D03/D05 policies; add their rules only after tests can distinguish legitimate history from defects.
4. Decide reviewer roles, retention and audit contract before adding review-state persistence.
