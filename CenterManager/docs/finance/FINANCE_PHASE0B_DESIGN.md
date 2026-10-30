# Finance Phase 0B — read-only detector implementation gate

Phase 0A has documented the current domain, findings and candidate rules. Phase 0B may begin only after review of `FINANCE_INVARIANTS.md` and `FINANCE_DIAGNOSTICS_RULE_CATALOG.md`. It is a separate branch/PR from current `main_repos`, with no production database writes and no Finance UI.

## First thin slice

Implement D01 (unattributed Tuition) and D02 (linked Income identity mismatch), plus a bounded summary of OWED and PREPAID **if** current repository queries can produce it without N+1 reads. D03 requires an accounting-period history policy; D05 requires an exception-comment rule. Do not ship speculative duplicate/evidence/bank detectors.

## Service boundary

- `FinanceDiagnosticsService` checks `finance.view`, accepts an explicit `as_of_date`, rule filter, cursor/page size, and returns a result state `OK | ERROR` with total count and stable evidence IDs. It never acquires the collaboration WRITE lease.
- Repository-provider query methods own joins, counts and pagination. Read session must be query-only; no `flush`, `commit`, backfill or ORM dirty state. An exception is surfaced as ERROR with a safe diagnostic code, not zero findings.
- DTO: rule ID, severity, entity type/ID, related entity IDs, observed amount (optional), evidence summary, timestamp/as-of date, and policy status. No student/parent personal details in logs. Export is deferred to the UI phase unless separately scoped.
- A read-only result is not an accounting correction. Remediation links to existing authorized workflows and carries a false-positive note.

## Tests and acceptance

Synthetic fixtures cover matching and mismatching Enrollment IDs, archived/withdrawn old debt, two enrollments for one student/class, VOIDED and deleted receipts, missing legacy attribution, unresolved contract, and separate OWED/PREPAID. Assert permission denial and error versus empty behavior. Use a logical before/after business-state comparison and a query-only connection; SQLite/WAL byte hash alone is insufficient evidence of no mutation. Measure query count and response time on a documented fixture size before choosing page limits.

Deliver one focused PR, CI and review. Phase 1 UI can then consume only rules with verified precision and readable evidence. Review status/notes are a later write workflow with their own schema, permission and audit contract.
