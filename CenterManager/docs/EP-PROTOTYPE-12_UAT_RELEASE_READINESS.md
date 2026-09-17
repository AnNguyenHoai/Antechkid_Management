# EP-PROTOTYPE-12 — UAT & Release Readiness

## Purpose
Freeze the release-readiness gate for the completed prototype flow before manual UAT. This task does not add a new workspace or business capability; it verifies that the prototype contracts remain present together and that the repository has an explicit UAT checklist.

## Release-readiness contract

- EP-PROTOTYPE-01 through EP-PROTOTYPE-11 regression contracts remain in the test suite.
- `MainWindow` remains the single application-level routing owner.
- Existing workspace shells remain the integration surfaces.
- Operational persistence continues through existing services rather than UI code.
- The prototype remains additive and introduces no second navigation or persistence path.
- UAT is manual against the running application; CI remains source-driven and does not require a live desktop display.

## Manual UAT checklist

### Application shell
- [ ] Launch CenterManager successfully.
- [ ] Home Dashboard is displayed.
- [ ] Student, Teacher, Class, Finance, Employee, and Admin entries respect existing permissions.
- [ ] Return Home returns to the existing Home Dashboard and refreshes it.

### Student flow
- [ ] Open Student Workspace.
- [ ] Select a student and open Student Detail.
- [ ] Verify Enrollment, Attendance, Assessment, and Timeline are reachable.
- [ ] Verify student context remains correct between surfaces.

### Class and session flow
- [ ] Open Class Workspace and select a class.
- [ ] Verify schedule/session surface is reachable.
- [ ] Open a session.
- [ ] Verify Attendance and Teaching Overview are available.

### Finance flow
- [ ] Open Finance Workspace.
- [ ] Verify Dashboard, Income, Expense, and Outstanding surfaces.
- [ ] Verify existing permission boundaries remain enforced.

### Regression
- [ ] Run targeted EP-PROTOTYPE-12 tests.
- [ ] Run the full regression suite.
- [ ] Record manual UAT defects separately from prototype contract failures.

## Non-goals

- No visual redesign.
- No new business entities or CRUD semantics.
- No new routing framework.
- No new persistence layer.
- No replacement of existing workspace shells.
- No GUI automation requirement in CI.

## Completion gate

1. EP-PROTOTYPE-12 targeted tests pass.
2. Full regression suite passes.
3. Manual UAT checklist is ready for execution against the current build.
4. Any production defect discovered during UAT is handled as a separate fix.
