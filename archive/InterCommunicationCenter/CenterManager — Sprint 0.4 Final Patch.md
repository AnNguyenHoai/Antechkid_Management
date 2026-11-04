# CenterManager — Sprint 0.4 Final Patch

**Status:** REQUIRED BEFORE FREEZE

Do NOT implement new features.

## 1. FIX — Nullable Date of Birth state

Current `StudentFormDialog` initializes:

```python
self._dob_null = True
```

but never changes it to `False` when the user selects/changes a date.

Fix the state handling.

Required behavior:

```text
Initial DOB
→ NULL

User selects a valid date
→ _get_dob() returns that date

User presses Clear
→ _get_dob() returns None

User selects another date after Clear
→ _get_dob() returns the new date
```

Do not save a dummy/default date when DOB is empty.

Ensure the UI visually distinguishes an empty DOB from a real `01/01/2000` value.

Keep the implementation simple.

---

## 2. ADD — DOB persistence test

Add a UI integration test:

```text
Open StudentFormDialog
Set DOB = 15/06/2015
Save
Reload Student through StudentService
Verify:

student.date_of_birth == date(2015, 6, 15)
```

Also retain test:

```text
Clear DOB
→ Save
→ date_of_birth is None
```

Test selecting a date after Clear as well.

---

## 3. FIX — StudentProfileDialog QMessageBox import

`StudentProfileDialog` calls:

```python
QMessageBox.warning(...)
QMessageBox.critical(...)
```

but `QMessageBox` is not imported.

Add the required import.

---

## 4. TEST — Profile error boundary

Add a focused test proving that opening a profile for a missing/deleted Student:

```text
does not crash with NameError
```

and follows the intended UI error handling path.

Avoid blocking the automated test on a modal MessageBox; monkeypatch the MessageBox call if necessary.

---

## 5. FIX — Do not expose unexpected exception details

Current Add Student unexpected error message includes:

```python
str(e)
```

Do not expose raw technical exception details in the UI.

Use a generic user-facing message.

Keep the real exception in application logs via:

```python
logger.exception(...)
```

Apply the same principle to profile loading.

---

## 6. IMPROVE — Deterministic age tests

Replace the weak:

```python
assert age >= 0
```

test with deterministic birthday-boundary tests.

Refactor the helper minimally if needed to make the reference date injectable/testable.

Cover:

```text
birthday already occurred
birthday today
birthday not yet occurred
DOB None
```

Do not introduce a clock framework/library.

---

## 7. ADD — Double-click wiring test

Add a focused test proving:

```text
StudentListPage row
      ↓
double-click handler
      ↓
StudentProfileDialog receives correct student_id
```

Do not use fragile screen coordinates.

Monkeypatching the dialog is acceptable.

---

## 8. Verify Add → Refresh

Ensure the existing implementation still satisfies:

```text
Add Student
→ Dialog Accepted
→ StudentListPage.refresh()
→ new student immediately visible
```

Add an automated test if practical.

Do not redesign the flow.

---

## 9. Full verification

Run:

```text
pytest
```

All tests must PASS in the development environment with PySide6 installed.

Automated tests must not modify:

```text
runtime/Database/center.db
```

---

## 10. Manual verification

Manually verify:

```text
1. Start application
2. Add Student
3. Enter a real DOB
4. Save
5. Open profile
6. DOB is correct
7. Age is correct
8. Add another Student without DOB
9. Profile shows no DOB
10. Search works
11. Close application
12. Reopen application
13. Both Students remain
```

---

## Non-goals

Do NOT implement:

```text
Edit Student
Delete Student
Restore Student
Parent UI
Assessment UI
Product UI
PDF
Excel
Dashboard
Authentication
Database migration redesign
```

No schema change.

No Alembic migration.

No Service-layer redesign.

# END OF PATCH
