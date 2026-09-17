# EP-PROTOTYPE-13 — Manual UAT Execution

## Purpose
Execute the release-readiness UAT for the completed prototype flow using the current `main_repos` build. This task is a validation gate, not a feature-development task.

## UAT principle
- Manual UAT is performed against the running application.
- CI remains source-driven and does not require a live desktop session.
- UAT records observed behavior; it does not redefine product requirements.
- A confirmed production defect is fixed separately with its own regression test.

## Execution order
`Launch → Home → Student → Student Detail → Class → Session → Attendance + Teaching Overview → Assessment + Timeline → Finance → Return Home`

## Manual checklist

### Application shell
- [ ] Launch CenterManager successfully.
- [ ] Home Dashboard appears.
- [ ] Student, Teacher, Class, Finance, Employee, and Admin entries respect existing permissions.
- [ ] Return Home returns to the existing Home Dashboard and refreshes it.

### Student flow
- [ ] Student Workspace opens.
- [ ] Selecting a student opens Student Detail.
- [ ] Enrollment, Attendance, Assessment, and Timeline are reachable.
- [ ] Student identity/context remains correct across these surfaces.

### Class and session flow
- [ ] Class Workspace and selected Class Detail open.
- [ ] Schedule/session surface is reachable.
- [ ] A session can be opened.
- [ ] Session Attendance and Teaching Overview are available.

### Finance flow
- [ ] Finance Dashboard opens.
- [ ] Income, Expense, and Outstanding are reachable.
- [ ] Existing permission boundaries remain enforced.

### Regression
- [ ] EP-PROTOTYPE-13 targeted tests pass.
- [ ] Full regression suite passes.
- [ ] Any manual failure is classified as environment/data issue, existing behavior, or confirmed production defect.

## Defect handling
For a confirmed production defect, capture reproduction steps, expected behavior, actual behavior, relevant logs/traceback, a minimal regression test, and a separate fix PR. Do not modify the prototype contract merely to hide a production defect.

## Non-goals
- No new feature development.
- No visual redesign.
- No routing redesign.
- No persistence redesign.
- No broad refactoring during UAT.

## Completion gate
1. Manual checklist is executed against the current build.
2. Targeted and full regression suites pass.
3. Confirmed production defects have separate fixes/regression coverage.
4. Prototype can move into the next product-development phase.
