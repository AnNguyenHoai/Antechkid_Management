# CenterManager – Hướng dẫn cài đặt

**Dành cho giáo viên và nhân viên**

---

## Yêu cầu hệ thống
- Windows 10/11 (64-bit)
- 2 GB RAM (khuyến nghị)
- 200 MB dung lượng trống
- **Không cần cài đặt thêm phần mềm nào khác** (Python, Git, v.v.)

---

## Các bước cài đặt

1. **Tải xuống** file ZIP từ quản trị viên (hoặc từ kho lưu trữ).
2. **Giải nén** vào thư mục bạn chọn (ví dụ `C:\CenterManager`).
3. **Chạy** file `CenterManager.exe` bằng cách nhấp đúp.
4. **Đăng nhập** bằng tài khoản được cấp.
   - Tài khoản mặc định: `admin` / `admin123` (đổi mật khẩu ngay lần đầu).
5. **Bắt đầu làm việc** – tất cả thư mục runtime sẽ được tạo tự động.

---

## Lần đầu chạy
- Ứng dụng tự động tạo các thư mục: `database`, `logs`, `reports`, `backup`, `cache`, `temp`, `metadata`.
- Nếu sử dụng tính năng cộng tác qua Git, quản trị viên sẽ cấu hình sẵn.

---

## Gỡ cài đặt
- Đơn giản: xóa thư mục giải nén. Dữ liệu nằm trong `runtime/database/center.db` – hãy sao lưu trước khi xóa.

---

## Hỗ trợ
- Xem `TROUBLESHOOTING.md` để xử lý sự cố.
- Liên hệ quản trị viên nếu cần thêm trợ giúp.