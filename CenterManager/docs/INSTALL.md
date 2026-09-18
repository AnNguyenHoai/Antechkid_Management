# CenterManager – Hướng dẫn cài đặt

**Dành cho giáo viên và nhân viên**

## Yêu cầu hệ thống

- Windows 10/11 (64-bit)
- 2 GB RAM (khuyến nghị)
- Không cần cài Python
- Không cần cài Git

## Các bước cài đặt

1. Tải file ZIP từ quản trị viên.
2. Giải nén **toàn bộ ZIP** vào thư mục bạn chọn, ví dụ `C:\CenterManager`.
3. Không xóa hoặc đổi tên thư mục `git` và `runtime`.
4. Chạy `CenterManager.exe`.
5. Đăng nhập bằng tài khoản được cấp.

## Lần đầu chạy

Ứng dụng tự tạo và sử dụng runtime data bên cạnh executable. Các thư mục runtime theo contract hiện tại gồm:

- `Database`
- `Export`
- `Attachment`
- `Config`
- `Backup`
- `Logs`
- `Reports`
- `Temp`
- `metadata`
- `collaboration`
- `snapshots`

Nếu chưa cấu hình Git, ứng dụng chạy ở local/offline mode; không cần dừng startup chỉ vì thiếu Git configuration.

## Git synchronization

Bản release đã đóng gói MinGit nên không cần cài Git riêng. Khi có Git configuration hợp lệ và mạng hoạt động, tính năng synchronization có thể sử dụng Git bundled trong package.

## Sao lưu và gỡ cài đặt

Dữ liệu làm việc nằm trong thư mục `runtime/`. Hãy dùng chức năng backup trước khi xóa thư mục ứng dụng.

Để gỡ cài đặt bản portable, đóng ứng dụng rồi xóa toàn bộ thư mục đã giải nén.
