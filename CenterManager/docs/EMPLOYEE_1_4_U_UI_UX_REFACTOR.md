# EMPLOYEE 1.4-U — Employee Workspace UI/UX Refactor

## Scope
- Embedded management Employee Profile remains a main-window page.
- Employee Profile is organized into Overview, Schedule, Attendance, and Documents tabs.
- Overview uses compact two-column information layout.
- Schedule and Attendance tables have usable minimum heights and stretch columns.
- Documents use a clearer file list with document type.
- Management profile has explicit in-window Back navigation.
- Global READ/WRITE state continues to control mutations.
- Self-service navigation retains Attendance and Work Registration as separate concepts.
- Attendance mutation controls remain management-only; employee self-service does not expose Book Time/Edit/Delete.

## UI contract
READ mode is presentation-oriented; WRITE mode enables permitted mutations. Protected service-layer authorization remains unchanged.
