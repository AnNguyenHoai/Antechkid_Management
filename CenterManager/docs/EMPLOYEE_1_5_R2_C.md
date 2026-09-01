# EMPLOYEE 1.5-R2-C — Employee Work Registration UX

## Goal
Provide a clear self-service monthly work-registration experience for employees.

## Rules
- Registration is for the next month only.
- One monthly registration contains all availability blocks.
- DRAFT: employee can add, edit, delete, and submit.
- SUBMITTED: read-only until manager reopens it.
- ACCEPTED: locked; manager must reopen for corrections.
- Actual write actions remain protected by the existing global WRITE transaction.

## UX
- Monthly summary: month, status, availability block count, total hours, submission deadline.
- Clear state guidance for DRAFT, SUBMITTED, and ACCEPTED.
- Availability table remains the detail area.
- Add/Edit/Delete and Submit are enabled only when both WRITE mode and DRAFT status are true.
- Submit confirms that the complete monthly registration will become read-only.

## Acceptance Criteria
1. Employee can review next month's registration in one screen.
2. Employee can add/edit/delete availability only in DRAFT + WRITE.
3. Employee can submit the full month from the page.
4. After SUBMITTED, editing controls are disabled.
5. After ACCEPTED, editing controls remain disabled.
6. Existing service validation remains authoritative.
7. No CollaborationManager or remote-lock changes are required for this task.
