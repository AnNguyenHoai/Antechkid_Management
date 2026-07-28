CENTERMANAGER — SPRINT 0.2C FINAL PATCH

Do NOT implement new functionality.

1. Remove cascade="all" from ALL Student relationships.

No ORM destructive delete cascade.
No delete-orphan.

Historical child records must be protected.

2. Correct all SQL Date model typing:

Use datetime.date for:

Student.date_of_birth
Enrollment.start_date
Enrollment.end_date
Assessment.assessment_date
Assessment.period_start
Assessment.period_end
TimelineEvent.event_date
StudentProduct.completed_date

3. Student.date_of_birth must use SQLAlchemy Date, not DateTime.

4. Update initial migration accordingly:

students.date_of_birth must be sa.Date(), not sa.DateTime().

Because initial schema has not been released yet, update the initial migration rather than creating a second corrective migration.

5. Remove duplicate:

migrations/alembic.ini

Keep only root:

alembic.ini

6. Remove migration-test skip behavior.

If the production initial migration is missing, migration tests must FAIL, not SKIP.

7. Run full:

pytest

All tests must PASS.

8. Verify:

alembic upgrade head
alembic downgrade base

against disposable DB.

9. Do NOT implement any next-sprint feature.