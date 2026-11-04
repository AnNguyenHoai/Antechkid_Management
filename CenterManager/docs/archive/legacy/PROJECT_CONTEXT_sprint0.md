# PROJECT_CONTEXT – CenterManager

## What is CenterManager?

CenterManager is a desktop application designed to manage student information for educational centers (e.g., language schools, tutoring centers, vocational training centers). It provides a single, offline‑first interface for administrators and staff to track student profiles, progress, attendance, payments, and more.

## Product Goal

To replace fragmented spreadsheets and paper records with a structured, locally‑stored database that is simple to deploy, fast to use, and requires minimal IT support. The application is built for small‑to‑medium centers (starting at ~100 students, scaling to several hundred) where data privacy, offline availability, and predictable cost are priorities.

## User Model

- **Primary users**: Center administrators, receptionists, and academic staff.
- **Secondary users**: Teachers (view‑only access to student lists and profiles).
- **No internet dependency**: All core operations work offline. Internet is used only for Google Drive file sync (via Google Drive Desktop) and optional updates.

## Desktop‑First Philosophy

CenterManager is a native desktop application (Windows, macOS, Linux). It is **not** a web application. All data is stored locally, and the UI is built with PySide6 (Qt) for responsiveness and native look‑and‑feel.

## Google Drive Role

Google Drive is used **only as an external sync mechanism** for attachments and exports. The application does **not** implement the Google Drive API directly in V1. Instead, we rely on **Google Drive Desktop** to synchronise the `Attachment/` and `Export/` folders with the user's Google Drive account. This keeps the application simple, avoids OAuth complexity, and leverages an existing reliable sync tool.

## PDF Distribution Concept

PDF exports (e.g., student profiles, class rosters) are generated on‑demand and saved to `Export/StudentProfile/`. These files can be shared via email, printed, or synced to Google Drive. They are **derived artefacts** – they do not affect the source of truth (SQLite).

## SQLite as Single Source of Truth

The database (`center.db`) is the **only authoritative source** for all business data. PDFs, Excel exports, and attachments are derived from or referenced by the database. This ensures consistency and makes backup simple (just copy the `.db` file plus the `Attachment/` folder).

## Current V1 Scope

Version 1 focuses on:

- Student CRUD (create, read, update, delete)
- Student profiles with contact information, enrollment dates, and notes
- Basic search and filtering
- PDF profile export (individual)
- Excel export (full list)
- Attachment management (upload/view files per student)
- Local backup (manual)

Deliberately out of scope for V1:

- Multi‑user authentication / roles
- Online payments
- Google Drive API integration
- Advanced reporting / dashboards
- Parent / student portal
- Mobile app

## Development Status

Sprint 0.1 (this baseline) provides only the **foundation**: project structure, paths, configuration, logging, and a minimal UI skeleton. Business features start in Sprint 0.2.