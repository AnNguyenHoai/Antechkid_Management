# CenterManager

CenterManager là ứng dụng desktop vận hành trung tâm giáo dục của AnTechKids, được tổ chức theo mô hình **Workspace Platform** thay vì một màn hình quản lý học sinh đơn lẻ.

## Các workspace chính

Hiện tại hệ thống có các vùng nghiệp vụ như:

- Student Workspace;
- Class / Teaching Workspace;
- Employee / Teacher Workspace;
- Finance Workspace;
- Administration Workspace;
- Home / Application Shell và các projection/dashboard liên quan.

## Kiến trúc kỹ thuật

CenterManager hiện sử dụng:

- Python 3.10 làm baseline CI;
- PySide6 cho desktop UI;
- SQLite + SQLAlchemy 2.x;
- Alembic migration;
- Service / Repository architecture;
- repository-provider boundaries ở các khu vực đã chuẩn hóa;
- Platform layer cho bootstrap, runtime context, collaboration và synchronization;
- Git-backed synchronization/edit-session khi được cấu hình;
- pytest + architecture regression gates trên GitHub Actions.

Xem `docs/ARCHITECTURE.md` để biết kiến trúc implementation hiện tại.

## Chạy từ source

Từ thư mục `CenterManager/`:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python run.py
```

Xem `docs/DEVELOPMENT_GUIDE.md` để biết workflow phát triển đầy đủ.

## Cài đặt / triển khai

Bản production có thể được phân phối dưới dạng Windows application/package tùy release workflow.

Tài liệu liên quan:

- [Deployment](docs/DEPLOYMENT.md)
- [Development Guide](docs/DEVELOPMENT_GUIDE.md)
- [Current Architecture](docs/ARCHITECTURE.md)
- [Database Design](docs/DATABASE_DESIGN.md)
- [Workspace Architecture V2](docs/Bussiness/ARCHITECTURE_V2.md)

## Collaboration / dữ liệu runtime

CenterManager có thể chạy local/offline khi không có cấu hình Git collaboration hợp lệ. Khi Git collaboration được cấu hình, startup synchronization là một phần của authoritative runtime-data lifecycle; application không được tự động fallback sang stale local database nếu authoritative sync thất bại.

Git/collaboration infrastructure thuộc Platform layer, không thuộc business workspace.

## Finance

Finance Wallet V2 có domain contract riêng:

`docs/finance/FINANCE_WALLET_V2_DOMAIN_SPEC.md`

Domain Spec là source of truth cho FinancePeriod, Wallet, Income/Expense realized semantics, Outstanding, Settlement và Finance capability projection.

## Quy trình phát triển

Repository hiện dùng issue-driven development:

```text
Product / Architecture
        ↓
GitHub Issue
        ↓
Codex / Developer feature branch
        ↓
local tests + architecture gates
        ↓
Pull Request
        ↓
GitHub Actions
        ↓
independent review
        ↓
human review
        ↓
main_repos
```

Standing rules cho coding agents nằm tại root `AGENTS.md`.

Task-specific requirements nằm trong GitHub Issue; approved domain specs vẫn là business-rule source of truth.

## CI

`.github/workflows/pytest-suite.yml` chạy full pytest suite trên Windows/Python 3.10 cho push/PR vào `main_repos`, bao gồm architecture tests và test artifacts.

## License

Proprietary — internal AnTechKids project.