CENTERMANAGER
SPRINT 0.3-R1 — SERVICE SEMANTICS & CLEANUP

Do NOT implement GUI or new features.

1. Remove duplicate/dead _generate_student_code() implementation.
   Keep only the official session-based implementation.

2. Fix StudentService date_of_birth typing:
   use datetime.date, matching the Student model.

3. Fix partial-update semantics.

   Introduce a simple UNSET sentinel or equivalent.

   Required behavior:

   UNSET = field not supplied → preserve existing value
   None  = explicitly clear nullable field
   value = update field

   This must apply to nullable editable fields where clearing is meaningful,
   especially date_of_birth, preferred_name, gender, current_level, notes.

   full_name remains required and cannot be cleared.

4. Make transaction ownership explicit.

   StudentService must:
   - commit on success
   - rollback on exception
   - always close session

   Do not introduce a complex Unit-of-Work framework.

5. Replace deprecated datetime.utcnow() usage with a consistent UTC helper/strategy
   compatible with the project's naive-UTC SQLite timestamp policy.

6. Replace the current rollback test.

   The test must exercise a StudentService operation and prove that an exception
   during the service transaction leaves no partial committed data.

7. Add history-preservation regression test:

   Student + at least one historical child record
   → delete_student()
   → Student soft-deleted
   → child record still exists.

8. Add partial-clear tests, at minimum:

   existing preferred_name → update preferred_name=None → becomes NULL

   existing date_of_birth → update date_of_birth=None → becomes NULL

   update another field without supplying date_of_birth
   → date_of_birth remains unchanged.

9. Run full pytest.

Do NOT modify database schema.
Do NOT create migration.
Do NOT implement next-sprint functionality.