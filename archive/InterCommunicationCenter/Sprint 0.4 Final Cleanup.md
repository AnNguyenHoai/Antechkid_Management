# CenterManager — Sprint 0.4 Final Cleanup

Production architecture is accepted.

Do NOT implement new features.

## 1. Fix StudentListPage error exposure

Current:

```python
except Exception as e:
    logger.exception("Failed to refresh student list")
    self.status_label.setText(
        f"Error loading students: {e}"
    )
```

must NOT expose raw exception details.

Change to generic user-facing text such as:

```text
Unable to load students.
```

Keep technical details only in:

```python
logger.exception(...)
```

Apply the same UI error-boundary principle already used by StudentFormDialog and StudentProfileDialog.

---

## 2. Correct DOB persistence tests

Tests must NOT manually call:

```python
dialog._on_date_changed()
```

after:

```python
dialog.dob_edit.setDate(...)
```

The test must rely on the real Qt:

```text
QDateEdit
   ↓ dateChanged signal
_on_date_changed()
```

Required regression:

```text
setDate(2015-06-15)
→ Save
→ StudentService reload
→ date_of_birth == date(2015, 6, 15)
```

Also retain:

```text
Set date
→ Clear
→ Save
→ None
```

and:

```text
Clear
→ Set new date
→ Save
→ new date
```

If signal wiring is removed, these tests should fail.

---

## 3. Fix deterministic age tests

Current monkeypatch targets:

```text
datetime.date
```

while the helper imports:

```python
from datetime import date
```

Correct the test strategy.

Preferred simple implementation:

```python
calculate_age(
    birth_date,
    reference_date=None
)
```

Production:

```text
reference_date=None
→ date.today()
```

Tests provide explicit reference date.

Required:

```text
DOB 2015-06-15
reference 2026-07-27
→ 11

DOB 2015-08-20
reference 2026-07-27
→ 10

DOB 2015-07-27
reference 2026-07-27
→ 11

DOB None
→ None
```

Do not introduce a clock/time library.

---

## 4. Correct Add → Refresh regression test

Current test manually calls:

```python
page.refresh()
```

after creating the student.

That does not prove production wiring.

Test the actual behavior:

```text
StudentListPage
   ↓
_on_add_clicked()
   ↓
StudentFormDialog returns Accepted
   ↓
StudentListPage.refresh()
   ↓
new row visible
```

Monkeypatching StudentFormDialog is acceptable.

The test itself must NOT manually call `page.refresh()` after the dialog returns.

---

## 5. Verification

Run full:

```text
pytest
```

All tests must PASS in the development environment with PySide6 installed.

Automated tests must not modify:

```text
runtime/Database/center.db
```

No schema changes.

No migration.

No Service redesign.

No new UI functionality.

# END OF SPRINT 0.4 FINAL CLEANUP
