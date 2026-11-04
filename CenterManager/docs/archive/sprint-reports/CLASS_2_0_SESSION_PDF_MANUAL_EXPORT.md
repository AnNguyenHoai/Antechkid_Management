# CLASS-2.0 — SESSION PDF MANUAL EXPORT

## Scope

Manual export of one Class Session to a parent-group-friendly PDF.

## UI

Each row in Class Schedule provides:

- View
- Export PDF

Export is read-only and does not require WRITE collaboration mode.

## PDF contents

- Class
- Course
- Session number and title
- Date and time
- Assigned teachers
- Session status
- Lesson content/topic
- Teaching progress and class atmosphere
- General remark and next plan
- Homework
- Attendance summary

Individual student names and highlights are intentionally excluded because the PDF
is intended for a parent group.

## Artifact lifecycle

Exactly one artifact is kept for each session:

`runtime/Export/SessionReports/Class_<class_id>_<class_name>/Lesson_<session_number>_<lesson_name>/latest.pdf`

Generation uses a temporary file and atomic replacement, so a failed generation
does not destroy the previous valid `latest.pdf`.


## CLASS-2.1 refinement

After successful manual export, the user is shown an `Open Save Location` action.
The exact report folder is opened using the operating system's file manager.

Reports are grouped by both class and lesson/session:

`SessionReports/`
- `Class_<class_id>_<class_name>/`
  - `Lesson_<session_number>_<lesson_name>/`
    - `latest.pdf`

This keeps each class separate and makes lesson reports easy to locate manually.
