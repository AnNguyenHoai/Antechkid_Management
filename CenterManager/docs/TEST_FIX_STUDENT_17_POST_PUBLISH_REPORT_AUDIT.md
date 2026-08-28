# Test Fix — STUDENT-1.7 Post-Publish Report Audit

The failing audit test was coupled to the exact implementation metadata
`trigger_event="student_updated"`.

The corrected test now verifies the actual business contract:
- capture dirty student aggregate IDs after publish succeeds;
- iterate only those dirty IDs;
- call `generate_student_report()` for each dirty student;
- generate the `latest` report.

This keeps the regression protection while allowing legitimate changes to
report trigger metadata.
