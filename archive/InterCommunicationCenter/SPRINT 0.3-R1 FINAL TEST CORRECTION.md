CENTERMANAGER
SPRINT 0.3-R1 FINAL TEST CORRECTION

Production implementation is accepted.

Do NOT modify StudentService behavior unless required by the tests below.

1. Replace the current transaction rollback test.

Current validation-error test does NOT prove rollback because no database
mutation occurs before the exception.

Create a test that:

- executes a StudentService write operation
- causes data to be added/flushed inside the transaction
- forces an exception before commit
- allows StudentService exception handling to execute rollback()
- verifies no partial data remains in the database

Recommended approach:

Monkeypatch StudentRepository.add() during create_student():

repo.add(student)
session.flush()
raise RuntimeError("Forced transaction failure")

Then verify:

service.create_student(...)
→ raises RuntimeError

and database contains no partially created Student.

The test must fail if StudentService rollback protection is broken.


2. Correct history-preservation regression test.

Current test uses Parent.

Parent is not a historical entity.

Use at least Assessment as the child record:

Student
+
Assessment
↓
service.delete_student()
↓
Student is soft deleted
Assessment still exists unchanged.

No production schema change.

No migration.

No GUI.

No new functionality.

Run full pytest after correction.