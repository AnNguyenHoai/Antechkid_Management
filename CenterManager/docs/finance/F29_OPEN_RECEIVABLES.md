# F-29 — Outstanding receivables across archives and finance periods

Status: proposed implementation, synthetic CI and two-machine UAT pending.

## Root cause
The Outstanding workspace forwarded the selected finance period to `EnrollmentRepository.list_for_outstanding`. That query removes an enrollment whose end_date precedes the selected period. `OutstandingService._overlaps_period` repeated this exclusion. Archiving a class withdraws active enrollments and sets an end_date, so open debt from that class disappears when a later finance period is selected. The underlying Income/Enrollment ledger is not deleted.

## Read models
- `OPEN_RECEIVABLES` (new workspace default): all historically attributable Enrollment contracts with strictly positive configured accrued balance at an explicit as-of cutoff, regardless of archived student/class or WITHDRAWN/COMPLETED status. Excludes future enrollments. Keeps exact Enrollment identity, period_start/end null to avoid falsely attributing an old debt to the current month. No FinancePeriod configuration is needed.
- `PERIOD_ACTIVITY` (existing compatibility): unchanged existing financial period overlap filter, status filters, KPI semantics and CSV period fields. Used via workspace selector.
- The as-of cutoff is the selected view date; both accrual and payments are measured using the same date. Future repayments cannot erase historical as-of debt.
- Open receivables includes only configured positive balances; PREPAID/NO_TUITION_CONFIGURED require separate views or diagnostics and must not be misreported as collectible debts.
- The class filter and CSV use the same view mode as the paged table, so archived classes with debt are selectable.

## Safety
Read-only service/UI; no schema or financial history mutation; no journal/lease/authority logic change. Financial KPIs of OPEN_RECEIVABLES represent open debt rows, not total periodic revenue. Avoid comparing current period income and open debt KPIs as like-for-like values.

## Validation gates
- Synthetic regression for class/student archive, withdrawal, period rollover, as-of repayments and CSV/class filter.
- Full Windows pytest and manual fixture with archived class, two finance periods, signed SQLCipher database, prior and subsequent payments.
- Check historical Income/Enrollment attribution, reconciled enrollment chains and frozen tuition adjustments separately if real fixtures show anomalies.
- Do not auto-merge or use production data.
