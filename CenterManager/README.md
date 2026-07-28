# CenterManager

CenterManager là ứng dụng desktop quản lý học sinh cho các trung tâm giáo dục.

## Yêu cầu hệ thống
- Python 3.9+
- pip

## Cài đặt và chạy

1. Tạo virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/Mac
   .venv\Scripts\activate      # Windows
Cài đặt dependencies:

bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # (nếu phát triển)
Chạy ứng dụng:

bash
python run.py
Chạy tests:

bash
pytest
Cấu trúc thư mục chính
src/centermanager/: Mã nguồn chính

runtime/: Thư mục runtime (tự động tạo)

tests/: Các bài kiểm tra

docs/: Tài liệu dự án

Giấy phép
Proprietary



---

## 5. Sửa lỗi Markdown trong `docs/ARCHITECTURE.md`

**Nội dung thay thế** (loại bỏ các dòng `` thừa và sửa code fence):

```markdown
# ARCHITECTURE – CenterManager

## Layered Architecture

CenterManager follows a strict layered architecture to separate concerns and enable future extensibility.
┌─────────────────────────────────────────────────────────────┐
│ UI Layer │
│ (PySide6 Widgets/Views) │
│ main_window.py │
└───────────────────────────┬─────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Service Layer │
│ (Business Logic / Use Cases) │
│ services/.py │
└───────────────────────────┬─────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Repository Layer │
│ (Data Access / Query Builders) │
│ repositories/.py │
└───────────────────────────┬─────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│ Database Layer │
│ (SQLAlchemy ORM / SQLite Connection) │
│ database/.py, models/.py │
└─────────────────────────────────────────────────────────────┘



### Responsibilities

| Layer | Responsibility |
|-------|----------------|
| **UI** | Displays data, captures user input, delegates actions to Services. Never touches SQL or business logic directly. |
| **Services** | Implements use cases (e.g., "register student", "generate PDF", "export to Excel"). Orchestrates repositories. |
| **Repositories** | Provides a clean data access API. Encapsulates queries and transactions. Returns domain models or DTOs. |
| **Database / Models** | Defines SQLAlchemy ORM models. Manages connection and session lifecycle. |

## Data Flow – Export/Attachment
┌─────────────────────┐
│ SQLite (center.db) │
└──────────┬──────────┘
│
▼
┌─────────────────────┐
│ Service generates │
│ PDF / Excel file │
└──────────┬──────────┘
│
▼
┌───────────────────────────────────┐
│ File saved to runtime/Export/ │
└───────────────────────────────────┘
│
▼
┌───────────────────────────────────┐
│ Google Drive Desktop syncs to │
│ cloud (if configured) │
└───────────────────────────────────┘



Attachments follow a similar flow but are user‑uploaded files stored in `runtime/Attachment/{student_id}/`.

## Module‑Based Architecture

Business features are organised into **modules** under `src/centermanager/modules/`. Each module encapsulates its own UI, services, and repository dependencies as needed. This allows adding or removing features without impacting the core.

Example module structure (future):
modules/
├── student/
│ ├── init.py
│ ├── models.py
│ ├── services.py
│ ├── repositories.py
│ └── ui/
│ ├── list_view.py
│ └── detail_view.py
├── attendance/
│ └── ...
└── payment/
└── ...



## Offline‑First Design

- No external API calls are required for core functionality.
- All data is stored locally.
- Google Drive sync is **optional** and handled by an external process (Google Drive Desktop).

## Filesystem vs Database

| Data Type | Storage | Notes |
|-----------|---------|-------|
|  fields, numbers, dates | SQLite | All structured data |
| Images, videos, PDFs, project files | Filesystem (`runtime/Attachment/`) | Database stores relative path only |
| Exported PDFs, Excel files | Filesystem (`runtime/Export/`) | Derived, can be regenerated |

## Core Foundation (`core/`)

- `paths.py`: Centralised path resolution (pathlib, cross‑platform).
- `config.py`: JSON configuration loader.
- `logging.py`: Console + file logging (UTF‑8, rotation).

These are the only modules allowed to touch the filesystem for infrastructure purposes. Business modules must use the `core` APIs.

## Future Packaging

The `src/` structure is designed to be compatible with PyInstaller. The `run.py` script inserts `src/` into `sys.path` for development, but the final executable will bundle all Python code, while runtime paths remain relative to the executable (or a fixed user‑data directory).

## Database Layer

- **Engine**: SQLite with foreign key enforcement
- **ORM**: SQLAlchemy 2.0 with declarative models
- **Migration**: Alembic for schema version control
- **Session**: Con manager pattern (`session_scope`)
- **Test**: All database tests use isolated temporary databases

### Database Flow
Service
↓
Repository
↓
SQLAlchemy ORM
↓
SQLite (center.db)