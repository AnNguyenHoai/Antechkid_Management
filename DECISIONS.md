# DECISIONS — CenterManager

> Trạng thái: **PROPOSED** (chờ PO) · **ACCEPTED** · **REJECTED** · **SUPERSEDED**.

## D-001 — Bộ file quản lý sản phẩm ở gốc repo, tài liệu kỹ thuật giữ trong `CenterManager/docs/`
- **Ngày:** 2026-11-04 · **Trạng thái:** PROPOSED
- **Bối cảnh:** `CenterManager/docs/ARCHITECTURE.md` đang là tài liệu kỹ thuật hiện hành (2026-09-24); `PROJECT_CONTEXT.md` và `CHANGELOG.md` trong `docs/` đã lỗi thời.
- **Đề xuất:** `BACKLOG.md`, `PRODUCT_CONTEXT.md`, `ARCHITECTURE.md` (bản tóm tắt), `DECISIONS.md`, `CHANGELOG.md`, `TASKS/` ở gốc repo là lớp quản lý sản phẩm. Chi tiết kỹ thuật và hợp đồng domain vẫn ở `CenterManager/docs/` và có thẩm quyền trong phạm vi của chúng.

## D-002 — Quan hệ giữa `BACKLOG.md` và GitHub Issues
- **Ngày:** 2026-11-04 · **Trạng thái:** ACCEPTED (PO, 2026-11-04)
- **Quyết định:** `BACKLOG.md` là danh mục ưu tiên và trạng thái nghiệm thu. **Trước khi làm** một task phải tạo GitHub Issue (hợp đồng task theo `AGENTS.md`) và ghi số Issue vào backlog. **Làm xong** thì đóng Issue và cập nhật backlog.
- **Lưu ý:** Đóng Issue nghĩa là phần thực hiện đã hoàn tất; task chỉ chuyển DONE khi PO nghiệm thu rõ ràng.

## D-003 — Định hướng nền tảng: desktop hay web
- **Ngày:** 2026-11-04 · **Trạng thái:** PROPOSED — cần PO quyết định
- **Bối cảnh:** Project Instructions mô tả "Web Application"; sản phẩm là desktop PySide6 `1.0.0-rc1`.
- **Đề xuất tạm thời:** Giữ desktop. Giới hạn đồng bộ Git được chấp nhận và theo dõi ở `TECH-005`.

## D-004 — Chấp nhận giới hạn kiến trúc đồng bộ Git ở giai đoạn hiện tại
- **Ngày:** 2026-11-04 · **Trạng thái:** ACCEPTED (PO xác nhận trong hội thoại 2026-11-04)
- **Nội dung:** Repo dữ liệu phình theo thời gian, một máy ghi tại một thời điểm, phụ thuộc GitHub — được chấp nhận; xử lý sau qua `TECH-005`.

## D-005 — Dữ liệu trong repo nguồn là dữ liệu giả
- **Ngày:** 2026-11-04 · **Trạng thái:** ACCEPTED (PO xác nhận)
- **Nội dung:** Snapshot/attachment/config trong repo nguồn là dữ liệu test; dữ liệu thật ở repo private `Antechkid_CenterManager_DatabaseOfficial`. Không coi là sự cố lộ dữ liệu. Không rewrite lịch sử Git vì lý do bảo mật.
