# Employee / Finance / Document Access Hardening

## Findings

1. Non-finance roles could still instantiate the Student Financial tab and call
   `IncomeService.list_incomes()`, which requires `finance.view`.
2. Employee self-service profile editing was not bound to the global WRITE
   transaction state. The dialog defaulted to editable even while the
   application was in READ mode.
3. Employee documents were stored only under `runtime/Attachments/Employees`.
   The database stored a relative path, but startup synchronization only copied
   the database and manifest. Therefore another machine could receive the DB
   record without receiving the physical document.

## Fix

- Financial tab is hidden for users without `finance.view`, and the financial
  widget does not call finance-protected services for those users.
- Employee self-service profile and CV/document actions now follow the global
  WRITE state. Service-level authorization remains the final boundary.
- Employee attachments remain local runtime materialized files, but are now
  synchronized as business data:
  - runtime: `runtime/Attachments/Employees/<employee_code>/...`
  - repository: `runtime/repository/Attachments/Employees/<employee_code>/...`
  - startup: repository -> runtime
  - publish: runtime -> repository before Git staging
- Repository remains the cross-machine source of truth; the database stores
  metadata/relative paths, not file bytes.

## Cross-machine flow

Machine A:
`Upload -> runtime/Attachments -> publish -> Git repository`

Machine B:
`startup sync -> Git repository/Attachments -> runtime/Attachments -> Open`

A document that has not been published is intentionally not available on a
fresh machine yet; it is local pending business data, equivalent to an
unpublished database change.
