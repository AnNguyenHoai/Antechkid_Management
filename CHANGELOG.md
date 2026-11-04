# CHANGELOG — CenterManager

> Chỉ ghi các thay đổi đã được xác minh, tính từ khi khởi tạo hệ thống backlog. Lịch sử trước đó: Git log / PR của `main_repos` và các tài liệu sprint trong `CenterManager/docs/` (chưa kiểm chứng lại; `docs/CHANGELOG.md` dừng ở Sprint 0.5).

## [Unreleased]

### Changed
- 2026-11-04 — TECH-003: lưu trữ 74 báo cáo sprint và tài liệu lỗi thời vào `docs/archive/`, dọn gốc repo, cập nhật `docs/README.md` và `CenterManager/README.md`. (Issue #562) — chờ CI và PO nghiệm thu.
- 2026-11-04 — PO nghiệm thu TECH-001; ghi quyết định D-006 (giữ template runtime), D-007 (giữ 5 snapshot).
- 2026-11-04 — TECH-002: gỡ 792 file runtime giả và gitlink `runtime/repository` khỏi Git (file local giữ nguyên); bổ sung `.gitignore`; sửa test gitlink chạy sai đường dẫn, thêm test hồi quy. (Issue #558) — chờ CI và PO nghiệm thu.
- 2026-11-04 — Ghi nhận PO nghiệm thu SEC-001, QA-001; TECH-001 chờ nghiệm thu (default branch đã là `main_repos`); D-002 ACCEPTED. (Issue #556)

### Added
- 2026-11-04 — Khởi tạo hệ thống quản lý sản phẩm: `BACKLOG.md`, `PRODUCT_CONTEXT.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `CHANGELOG.md`. Chỉ tài liệu, **không thay đổi code ứng dụng**. (PR #555)

## Baseline đã audit — `main_repos` @ `ac9e96d` (2026-11-04, PR #554)
- Phiên bản: `1.0.0-rc1`.
- CI `Pytest Suite` run 41751812981: **3.176 passed, 7 skipped, 0 failed** (3 shard Windows).
