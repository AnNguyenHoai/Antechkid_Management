# PRODUCT_CONTEXT — AnTechKids CenterManager

> Trạng thái: **DRAFT — chờ PO xác nhận** · Khởi tạo 2026-11-04 · Nguồn: audit `main_repos` @ `ac9e96d` + xác nhận của PO ngày 2026-11-04.
> `CenterManager/docs/PROJECT_CONTEXT.md` mô tả giai đoạn Sprint 0.1 và đã lỗi thời (xem `TECH-003`).

## 1. Sản phẩm

**CenterManager** là ứng dụng desktop Windows quản lý vận hành trung tâm giáo dục AnTechKids: học sinh – phụ huynh, lớp – buổi học – điểm danh, đánh giá và báo cáo học tập, giáo viên/nhân viên (lịch, giờ công, đăng ký ca), tài chính (thu – chi – công nợ – ví/finance wallet), phân quyền, backup/khôi phục. Nhiều máy dùng chung dữ liệu qua một repo GitHub dữ liệu private.

Phiên bản hiện tại: `1.0.0-rc1` (release candidate).

## 2. Người dùng

| Vai trò | Nhu cầu chính |
|---|---|
| Quản trị | Tài khoản, vai trò/quyền, cấu hình Git, backup/khôi phục, audit |
| Quản lý / Vận hành | Học sinh, phụ huynh, lớp, ghi danh, tài chính, báo cáo |
| Giáo viên | Buổi học, điểm danh, ghi chú, đánh giá, lịch & giờ công cá nhân |
| Nhân viên | Hồ sơ cá nhân, đăng ký ca, giờ làm |

(Danh sách vai trò chính thức cần PO xác nhận.)

## 3. Mục tiêu (đề xuất — chờ PO xác nhận)

1. Một nguồn dữ liệu thống nhất cho trung tâm quy mô nhỏ – vừa.
2. Nhiều nhân sự làm việc trên nhiều máy mà không mất dữ liệu.
3. Báo cáo học tập PDF cho phụ huynh.
4. Bảo vệ dữ liệu cá nhân của trẻ em, phụ huynh, nhân viên.

## 4. Sự thật đã được PO xác nhận (2026-11-04)

- Dữ liệu trong repo nguồn (`runtime/snapshots`, attachment, config) là **dữ liệu giả để test**.
- Dữ liệu thật nằm ở repo private `AnNguyenHoai/Antechkid_CenterManager_DatabaseOfficial` (audit xác nhận repo này không đọc được ẩn danh).
- GitHub token cũ đã được thu hồi; token hiện dùng DPAPI và lưu ở repo riêng.
- Mật khẩu admin mặc định đã được đổi.
- Giới hạn của kiến trúc đồng bộ Git được chấp nhận ở thời điểm hiện tại, xử lý sau.

## 5. Ràng buộc

- Windows, phát hành ZIP portable; production bắt buộc SQLCipher + DPAPI.
- Chi phí hạ tầng hiện tại 0 đồng; thay đổi phát sinh chi phí cần PO duyệt.
- Dữ liệu cá nhân trẻ em phải tuân thủ quy định bảo vệ dữ liệu cá nhân tại Việt Nam.

## 6. Câu hỏi mở cho PO

1. Quan hệ giữa `BACKLOG.md` và GitHub Issues (xem `D-002`).
2. Định hướng dài hạn desktop hay web (xem `D-003`) — Project Instructions đang mô tả "Web Application".
3. Các thư mục `InterCommunicationCenter/`, `CenterManager_DeployDriveTest/`, `centermanager-redesign/` còn cần giữ không?
