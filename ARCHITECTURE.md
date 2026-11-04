# ARCHITECTURE — Tóm tắt cho quản lý sản phẩm

> Khởi tạo 2026-11-04 từ audit nhánh `main_repos` @ `ac9e96d` (PR #554).
> **Tài liệu kỹ thuật chi tiết và có thẩm quyền:** `CenterManager/docs/ARCHITECTURE.md` (CURRENT, cập nhật 2026-09-24) và các tài liệu bảo mật/hợp đồng domain trong `CenterManager/docs/`. File này chỉ tóm tắt để lập backlog, không thay thế chúng.

## 1. Tổng quan

| Hạng mục | Hiện trạng |
|---|---|
| Loại ứng dụng | Desktop Windows (PySide6), phiên bản `1.0.0-rc1` |
| Dữ liệu | SQLite, SQLAlchemy 2.x, Alembic (45 file migration). Production bắt buộc **SQLCipher** |
| Bí mật | Khóa DB 256-bit bảo vệ bằng Windows DPAPI; cấu hình Git dạng `DPAPI:v2:` (định dạng `ENC:v1:` cũ chỉ còn để migrate) |
| Cô lập dữ liệu | SEC-02 Protected Data Service: dịch vụ Windows `AnTechKidsData` giữ DB/khóa/backup, ứng dụng gọi qua named pipe có xác thực |
| Đồng bộ đa máy | Repo GitHub dữ liệu riêng (private: `Antechkid_CenterManager_DatabaseOfficial`), khóa ghi qua nhánh lock, heartbeat |
| Phân quyền | RBAC theo capability, bcrypt, khóa sau nhiều lần đăng nhập sai, buộc đổi mật khẩu admin mặc định |
| Đóng gói | PyInstaller → ZIP portable kèm Git |
| CI | `pytest-suite.yml`: toàn bộ test trên Windows, 3 shard, chạy mỗi push/PR vào `main_repos`; `windows-prototype-release.yml` khi gắn tag |
| Quy mô | `src/`: 524 file / ~84k dòng · `tests/`: 564 file / ~2.700 hàm test (3.176 test case sau tham số hóa; CI ngày 2026-11-04: toàn bộ pass) · `docs/`: 270 file |

## 2. Phân lớp

UI (workspace) → Services / Policies / Read models → Repository provider → SQLAlchemy/Alembic → SQLite/SQLCipher.
Cross-cutting: bootstrap, auth, events, collaboration, synchronization, protected data service, write recovery.
Ranh giới phụ thuộc được ép bằng architecture tests trong `tests/`.

## 3. Quy trình phát triển hiện có

- GitHub Issue là hợp đồng task; PR là luồng review (`CenterManager/docs/AI_COLLABORATION_PROTOCOL.md`).
- Quy tắc cho agent lập trình: `AGENTS.md` (không code trực tiếp trên `main_repos`, nhánh feature, chạy test, PR về `main_repos`).
- Nhánh tích hợp thực tế: **`main_repos`**. Nhánh mặc định `main` dừng ở 2026-09-29 (xem `TECH-001`).

## 4. Giới hạn kiến trúc đã được PO thừa nhận

- Mỗi lần ghi commit cả file DB nhị phân → repo dữ liệu phình dần.
- Chỉ một máy giữ quyền ghi tại một thời điểm.
- Đồng bộ phụ thuộc GitHub; ai có quyền repo dữ liệu đọc được file DB (đã mã hóa SQLCipher ở production).
Theo dõi tại `TECH-005`.
