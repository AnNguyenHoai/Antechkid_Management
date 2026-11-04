# CenterManager — Sprint 0.1 Developer Contract

**Sprint:** 0.1
**Name:** Project Foundation & Repository Bootstrap
**Project:** CenterManager
**Developer:** DeepSeek
**Technical Lead / Reviewer:** ChatGPT
**Product Owner:** An
**Status:** READY FOR DEVELOPMENT

---

# 1. Sprint Objective

Mục tiêu Sprint 0.1 là tạo **nền móng kỹ thuật ban đầu** cho dự án CenterManager.

Sprint này KHÔNG phát triển business feature.

Sau Sprint 0.1, project phải:

* Có cấu trúc source code chuẩn.
* Có Python environment rõ ràng.
* Có dependency management.
* Có application entry point.
* Có PySide6 application bootstrap.
* Có logging cơ bản.
* Có configuration loader cơ bản.
* Có test framework.
* Có project documentation nền tảng.
* Có thể chạy application skeleton thành công.

Sprint này phải giữ project nhỏ và sạch.

Không implement:

* Student management.
* Database schema nghiệp vụ.
* Login.
* PDF export.
* Excel export.
* Attachment management.
* Backup.
* Google Drive API.
* Attendance.
* Payment.
* Teacher management.

---

# 2. Product Context

CenterManager là desktop application dùng để quản lý thông tin học sinh cho một trung tâm giáo dục.

Quy mô ban đầu:

```text
~100 students
```

Có khả năng tăng lên vài trăm học sinh.

Application hoạt động theo mô hình:

```text
Desktop Application
        │
        ▼
     SQLite
        │
        ├── PDF Export
        ├── Excel Export
        └── Attachment
                │
                ▼
          Google Drive Sync
```

Google Drive Desktop chịu trách nhiệm đồng bộ filesystem.

CenterManager KHÔNG trực tiếp implement Google Drive API trong Version 1.

---

# 3. Deployment Contract

Deployment structure đã được Product Owner phê duyệt:

```text
CenterManager/
│
├── app.exe
│
├── Database/
│   └── center.db
│
├── Export/
│   ├── StudentProfile/
│   │   ├── HS001.pdf
│   │   └── HS002.pdf
│   │
│   └── Excel/
│       └── StudentList.xlsx
│
├── Attachment/
│   ├── HS001/
│   └── HS002/
│
├── Config/
│   ├── config.json
│   └── account.json
│
└── Backup/
```

Lưu ý:

Đây là **runtime/deployment structure**.

Source code development structure được tách riêng và định nghĩa bên dưới.

---

# 4. Technology Baseline

Các công nghệ đã được Technical Lead chốt:

| Component     | Technology           |
| ------------- | -------------------- |
| Language      | Python 3             |
| Desktop UI    | PySide6              |
| Database      | SQLite               |
| ORM           | SQLAlchemy           |
| PDF           | ReportLab            |
| Excel         | openpyxl             |
| Testing       | pytest               |
| Packaging     | PyInstaller          |
| Configuration | JSON                 |
| Cloud Sync    | Google Drive Desktop |

Developer KHÔNG được tự ý thay đổi technology stack.

Nếu phát hiện vấn đề kỹ thuật cần thay đổi stack:

```text
STOP
↓
Document reason
↓
Report Technical Lead
```

Không tự implement giải pháp thay thế.

---

# 5. Architecture Principles

Project phải tuân thủ các nguyên tắc sau.

## 5.1 Single Source of Truth

Trong Version 1:

```text
SQLite center.db
```

là nguồn dữ liệu nghiệp vụ duy nhất.

PDF và Excel chỉ là derived output.

---

## 5.2 UI Must Not Access Database Directly

Không được thiết kế:

```text
UI
 ↓
SQLite
```

Architecture phải hướng tới:

```text
UI
 ↓
Service
 ↓
Repository
 ↓
Database
```

Sprint 0.1 chưa cần implement Repository hoặc business Service thực tế.

Chỉ cần source structure hỗ trợ kiến trúc này.

---

## 5.3 Module-Based Architecture

Các business feature tương lai phải có khả năng được phát triển thành module độc lập.

Ví dụ:

```text
student
assessment
timeline
progress
attachment
```

Tương lai có thể thêm:

```text
attendance
payment
schedule
teacher
```

mà không cần rewrite Core.

---

## 5.4 Offline First

Application phải hoạt động khi:

```text
Internet unavailable
```

Internet không phải dependency để application chạy.

---

## 5.5 Filesystem Is External Storage

Các file lớn như:

```text
Image
Video
PDF
Project file
```

không được thiết kế để lưu binary trực tiếp vào SQLite.

Database tương lai chỉ lưu metadata/path khi cần.

---

## 5.6 Configuration Over Hardcoding

Không hardcode runtime path như:

```python
"C:/CenterManager/Database/center.db"
```

Runtime paths phải được resolve từ application root/configuration.

---

# 6. Required Source Structure

Developer phải tạo project skeleton theo hướng sau:

```text
CenterManager/
│
├── src/
│   └── centermanager/
│       │
│       ├── __init__.py
│       ├── app.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── logging.py
│       │   └── paths.py
│       │
│       ├── database/
│       │   └── __init__.py
│       │
│       ├── models/
│       │   └── __init__.py
│       │
│       ├── repositories/
│       │   └── __init__.py
│       │
│       ├── services/
│       │   └── __init__.py
│       │
│       ├── modules/
│       │   └── __init__.py
│       │
│       ├── ui/
│       │   ├── __init__.py
│       │   └── main_window.py
│       │
│       ├── export/
│       │   ├── __init__.py
│       │   ├── pdf/
│       │   │   └── __init__.py
│       │   └── excel/
│       │       └── __init__.py
│       │
│       └── utils/
│           └── __init__.py
│
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_paths.py
│   └── test_smoke.py
│
├── docs/
│   ├── PROJECT_CONTEXT.md
│   ├── ARCHITECTURE.md
│   └── DEVELOPMENT_GUIDE.md
│
├── runtime/
│   ├── Database/
│   ├── Export/
│   │   ├── StudentProfile/
│   │   └── Excel/
│   ├── Attachment/
│   ├── Config/
│   └── Backup/
│
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── .gitignore
├── README.md
└── run.py
```

Minor structural adjustments are allowed only if technically justified in the completion report.

Do NOT introduce unnecessary architectural layers.

---

# 7. Application Bootstrap

Create:

```text
run.py
```

which starts the application.

Expected flow:

```text
run.py
  ↓
centermanager.app
  ↓
QApplication
  ↓
MainWindow
```

Application must launch a minimal PySide6 window.

Example visual requirement:

```text
+--------------------------------------+
| CenterManager                        |
+--------------------------------------+
|                                      |
|       CenterManager                  |
|                                      |
|       Application initialized        |
|                                      |
+--------------------------------------+
```

This is only a bootstrap window.

Do NOT build Dashboard yet.

---

# 8. Path Management

Implement centralized path resolution.

Create:

```text
core/paths.py
```

The rest of the application should not construct runtime paths manually.

Expected conceptual interface:

```python
paths.database_dir
paths.export_dir
paths.student_profile_dir
paths.excel_export_dir
paths.attachment_dir
paths.config_dir
paths.backup_dir
```

The exact implementation is developer choice.

Requirements:

* Cross-platform path handling.
* Use `pathlib`.
* No absolute hardcoded paths.
* Runtime directories can be created automatically if missing.
* Must work from development environment.
* Architecture should remain compatible with future PyInstaller packaging.

---

# 9. Configuration System

Create:

```text
runtime/Config/config.json
```

Initial configuration should contain only meaningful foundation-level settings.

Example:

```json
{
    "application": {
        "name": "CenterManager",
        "version": "0.1.0"
    }
}
```

Implement:

```text
core/config.py
```

Responsibilities:

* Locate configuration.
* Load JSON.
* Validate basic structure.
* Provide configuration values to application.

Do NOT create a complex configuration framework.

Do NOT introduce Pydantic unless technically necessary and approved.

---

# 10. Logging

Create basic logging initialization.

Target future log location:

```text
runtime/Logs/
```

If Logs directory is introduced, update runtime structure/documentation accordingly.

Minimum requirements:

* Console logging.
* File logging.
* Timestamp.
* Log level.
* Module/logger name.
* UTF-8.

Application startup should generate messages similar to:

```text
INFO CenterManager starting
INFO Configuration loaded
INFO Runtime directories ready
INFO Main window initialized
```

Do not use `print()` for application diagnostics.

---

# 11. Dependency Management

Create:

```text
requirements.txt
```

containing runtime dependencies needed by the approved stack.

At Sprint 0.1 only install dependencies actually required or intentionally reserved as baseline dependencies.

Expected core dependencies include:

```text
PySide6
SQLAlchemy
reportlab
openpyxl
```

Development dependencies go into:

```text
requirements-dev.txt
```

At minimum:

```text
pytest
```

Do not add large libraries without justification.

---

# 12. Tests

pytest must be configured.

Minimum tests:

## test_paths.py

Verify:

* Runtime root resolves.
* Required directories can be created.
* Path API returns expected locations.

## test_config.py

Verify:

* Config loads.
* Application name exists.
* Application version exists.
* Invalid/missing config produces controlled behavior.

## test_smoke.py

Verify foundation modules can be imported without error.

Avoid tests that require interacting manually with the GUI.

A Qt smoke test may be added if it can run reliably without creating unnecessary dependencies.

---

# 13. Documentation

## PROJECT_CONTEXT.md

Must explain:

* What CenterManager is.
* Product goal.
* User model.
* Desktop-first philosophy.
* Google Drive role.
* PDF distribution concept.
* SQLite as Single Source of Truth.
* Current V1 scope.

---

## ARCHITECTURE.md

Must document:

```text
UI
 ↓
Services
 ↓
Repositories
 ↓
Database
```

and:

```text
SQLite
   │
   ├── PDF
   ├── Excel
   └── Attachment references
```

Also document responsibilities of:

* core
* database
* models
* repositories
* services
* modules
* ui
* export
* utils

---

## DEVELOPMENT_GUIDE.md

Must include:

* Environment setup.
* Dependency installation.
* How to run application.
* How to run tests.
* Coding rules.
* Architecture rules.
* Adding a future module.

---

# 14. README

README should allow another developer to clone the repository and quickly run:

```text
Create virtual environment
        ↓
Install dependencies
        ↓
Run tests
        ↓
Run CenterManager
```

Do not turn README into full architecture documentation.

Detailed architecture belongs in `/docs`.

---

# 15. Git Ignore

At minimum ignore:

```text
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/
dist/
build/
*.spec
```

Runtime-generated logs and temporary files should also be considered.

Do NOT blindly ignore the entire runtime structure if empty directory placeholders/config templates are needed by the repository.

---

# 16. Explicit Non-Goals

Developer MUST NOT implement during Sprint 0.1:

```text
Student model
Student CRUD
Student UI
Database schema
Database migration
Authentication
Admin account
Teacher account
PDF generation
Excel generation
Attachment handling
Backup implementation
Google Drive API
Attendance
Payment
Schedule
Dashboard
Search
Theme system
Installer
Production EXE
```

Empty architectural packages/directories for future features are allowed.

Business implementation is not.

---

# 17. Coding Rules

Use:

```text
Python type hints
pathlib
clear naming
small focused classes/functions
docstrings where useful
```

Avoid:

```text
God classes
global mutable state
hardcoded absolute paths
business logic inside UI
SQL inside UI
catch-all exception swallowing
premature abstraction
```

Follow:

```text
KISS
YAGNI
Single Responsibility
Separation of Concerns
```

Do not build infrastructure that Sprint 0.1 does not need.

---

# 18. Acceptance Criteria

Sprint 0.1 is considered technically complete only when all criteria below pass.

### AC-01

Fresh environment can install dependencies successfully.

### AC-02

Application starts using:

```bash
python run.py
```

### AC-03

Minimal CenterManager PySide6 window appears.

### AC-04

Runtime directory structure is automatically prepared.

### AC-05

Configuration loads successfully.

### AC-06

Logging works to console and file.

### AC-07

No hardcoded absolute runtime paths.

### AC-08

All automated tests pass.

Expected:

```bash
pytest
```

Result:

```text
PASS
```

### AC-09

Source structure follows architecture defined in this contract.

### AC-10

README setup instructions work from a clean environment.

### AC-11

PROJECT_CONTEXT.md exists and accurately describes product architecture.

### AC-12

ARCHITECTURE.md exists.

### AC-13

DEVELOPMENT_GUIDE.md exists.

### AC-14

No business features outside Sprint 0.1 scope have been implemented.

---

# 19. Definition of Done

Sprint is DONE only when:

```text
Implementation complete
        +
Tests pass
        +
Documentation complete
        +
Developer completion report submitted
        +
Technical Lead review PASS
```

Developer must NOT mark the project ready for Sprint 0.2 independently.

Technical Lead owns Sprint acceptance.

---

# 20. Required Developer Completion Report

After implementation, return a report using EXACTLY these sections:

## 1. Summary

Briefly describe what was implemented.

## 2. Files Created

List every newly created file.

## 3. Files Modified

List every modified existing file.

## 4. Architecture Decisions

List any implementation decisions not explicitly defined by this contract.

## 5. Deviations

List every deviation from this contract.

If none:

```text
None.
```

## 6. Dependencies

List installed runtime and development dependencies.

## 7. Test Results

Provide the actual command and result.

Example:

```text
pytest

12 passed
```

## 8. Application Run Result

Provide result of:

```text
python run.py
```

Confirm whether MainWindow launched successfully.

## 9. Known Issues

List known issues.

If none:

```text
None.
```

## 10. Sprint Acceptance Checklist

Developer self-check each AC:

```text
AC-01 PASS
AC-02 PASS
...
AC-14 PASS
```

---

# 21. Developer Instruction

Implement only what is defined in this contract.

Priority order:

```text
Correct architecture
      >
Working foundation
      >
Testability
      >
Code cleanliness
      >
UI appearance
```

Do not optimize UI appearance during this sprint.

Do not implement future features proactively.

If a requirement appears ambiguous and the choice could affect architecture, stop and report the ambiguity rather than making a large architectural assumption.

---

# END OF SPRINT 0.1 CONTRACT
