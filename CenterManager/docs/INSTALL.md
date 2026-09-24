# CenterManager — Hướng dẫn cài đặt

**Dành cho giáo viên và nhân viên**  
Cập nhật: 2026-09-24

## Yêu cầu hệ thống

- Windows 10/11 64-bit;
- quyền ghi vào thư mục cài đặt/runtime;
- không cần cài Python cho bản release;
- không cần cài Git riêng nếu package release đã bundle Git theo contract hiện tại.

## Cài đặt

1. Nhận file ZIP release từ quản trị viên.
2. Giải nén **toàn bộ** ZIP vào một thư mục có quyền ghi, ví dụ `C:\CenterManager` hoặc thư mục người dùng phù hợp.
3. Không chỉ copy riêng `CenterManager.exe`.
4. Không tự ý xóa/đổi tên các thư mục runtime, Git bundled hoặc migration assets đi cùng release.
5. Chạy `CenterManager.exe`.
6. Đăng nhập bằng tài khoản được cấp.

## Lần đầu chạy

CenterManager sử dụng runtime data theo contract của application paths. Các thư mục cụ thể có thể thay đổi theo release; không nên coi một danh sách thư mục cũ là API cố định.

Application sẽ tự:

- khởi tạo path/config/logging;
- bootstrap platform;
- xử lý collaboration configuration nếu có;
- materialize runtime database;
- nâng schema bằng Alembic;
- mở màn hình đăng nhập.

## Local/offline mode

Nếu máy **chưa có Git collaboration configuration hợp lệ**, ứng dụng có thể chạy ở local/offline mode với local runtime database.

Thiếu Git configuration không phải lỗi startup.

## Configured collaboration mode

Nếu deployment đã có Git collaboration configuration hợp lệ, startup synchronization là authoritative.

Trong trường hợp này:

- ứng dụng cần access repository/network/credential hợp lệ để synchronize;
- nếu authoritative startup synchronization thất bại, application sẽ dừng thay vì tự động dùng stale local database;
- người dùng nên báo quản trị viên thay vì tự xóa database/config để “chạy tạm”.

## Git bundled

Release có thể đóng gói Git/MinGit để người dùng không phải tự cài Git hệ thống. Không thay thế/xóa Git bundled trừ khi quản trị viên đang thực hiện quy trình update đã xác nhận.

## Sao lưu

Dữ liệu runtime là dữ liệu làm việc quan trọng.

- sử dụng chức năng/procedure backup do quản trị viên cung cấp;
- không copy/xóa riêng `center.db` khi application đang chạy;
- không dùng xóa database như cách reset mật khẩu hoặc sửa login;
- với collaborative deployment, backup/restore phải tính đến authoritative synchronized state.

## Gỡ cài đặt

Trước khi xóa thư mục application:

1. đóng CenterManager;
2. xác nhận dữ liệu cần thiết đã backup/synchronized theo deployment procedure;
3. sau đó mới xóa thư mục release.

Nếu không chắc deployment đang ở local mode hay collaborative mode, hỏi quản trị viên trước khi thao tác dữ liệu.