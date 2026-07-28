# DATABASE_DESIGN – CenterManager

## Overview

CenterManager uses SQLite as its embedded database with SQLAlchemy ORM for data access. The design prioritizes:

- **Data preservation** – historical records are never deleted
- **Soft delete** – students can be marked inactive without losing data
- **Single source of truth** – all business data lives in SQLite
- **Relative paths** – attachments stored by reference, not content

## 8 Domain Tables

### 1. students (Core)
- `id` – Internal primary key (INTEGER, PK)
- `student_code` – Human-readable identifier (TEXT, NOT NULL, UNIQUE)
- `full_name` – Student's full name (TEXT, NOT NULL)
- `preferred_name` – Optional preferred name (TEXT, NULL)
- `date_of_birth` – Birth date (DATE, NULL)
- `gender` – Gender (TEXT, NULL)
- `status` – Current status, default 'ACTIVE' (TEXT)
- `current_level` – Current level/grade (TEXT, NULL)
- `notes` – Additional notes (TEXT, NULL)
- `deleted_at` – Soft delete timestamp (DATETIME, NULL)
- `created_at`, `updated_at` – Timestamps (DATETIME, NOT NULL)

### 2. parents
- Student-parent relationship (Student 1 — N Parent)
- `student_id` FK → students.id
- `relationship` – FATHER/MOTHER/GUARDIAN/OTHER
- `is_primary_contact` – Boolean, default False

### 3. enrollments
- Student enrollment history (Student 1 — N Enrollment)
- `student_id` FK → students.id
- Class/course/teacher info as text fields (no separate tables yet)

### 4. assessments
- Student assessment history (Student 1 — N Assessment)
- `student_id` FK → students.id
- `cycle_months` – 3, 6, etc. (integer, no DB constraint)
- Free-text fields for strengths, improvements, comments

### 5. timeline_events
- Student timeline history (Student 1 — N TimelineEvent)
- `student_id` FK → students.id
- `event_type` – LEARNING/PROJECT/ACHIEVEMENT/NOTE/LEVEL_CHANGE/OTHER

### 6. student_products
- Student project/product portfolio (Student 1 — N StudentProduct)
- `student_id` FK → students.id
- `url` – Web URL (Google Drive, Scratch, GitHub, etc.)

### 7. progress
- Student progress tracking (Student 1 — N Progress)
- `student_id` FK → students.id
- `category` – Skill/competency name
- `value` – Numeric score (0-100 concept, no DB constraint)

### 8. attachments
- File references for student documents (Student 1 — N Attachment)
- `student_id` FK → students.id
- `relative_path` – Only relative path, e.g., `HS023/photo.jpg`
- No actual file operations in this sprint

## Relationships Summary

| Parent | Child | Type | Preserve History |
|--------|-------|------|------------------|
| Student | Parent | 1:N | ✅ Yes |
| Student | Enrollment | 1:N | ✅ Yes |
| Student | Assessment | 1:N | ✅ Yes |
| Student | TimelineEvent | 1:N | ✅ Yes |
| Student | StudentProduct | 1:N | ✅ Yes |
| Student | Progress | 1:N | ✅ Yes |
| Student | Attachment | 1:N | ✅ Yes |

## Internal ID vs Student Code

- **id (INTEGER, PK)** – Internal database identity. Never exposed in UI as primary identifier.
- **student_code (TEXT, UNIQUE)** – Human-readable identifier. Visible in UI, used in exports/filenames.

## Soft Delete Strategy

- Students are soft-deleted by setting `deleted_at = NOW()`.
- `list_active()` queries filter: `deleted_at IS NULL`.
- Historical child records remain accessible for reporting/audit.

## Timestamp Strategy

- All tables use `created_at` and `updated_at`.
- **UTC** is used internally (via SQLite's current_timestamp).
- Formatting to local time/display strings belongs to UI/PDF layers.

## Attachment Path Strategy

- Only relative paths are stored in database.
- Example: `HS023/portfolio.pdf`
- Full path resolved at runtime: `runtime/Attachment/HS023/portfolio.pdf`
- No hardcoded absolute paths.

## Foreign Key Enforcement

- SQLite FK enforcement enabled via `PRAGMA foreign_keys = ON`.
- Tested: orphan records cannot be created.

## Migration Strategy

- Alembic manages schema evolution.
- Initial migration creates all 8 tables.
- `upgrade` and `downgrade` both supported.
- Migration tests run against temporary databases only.

## Repository Responsibility

- Repository = data access layer.
- Maps ORM queries to simple operations.
- Future business logic belongs to Service layer.
- Repository does NOT know about UI or business validation.