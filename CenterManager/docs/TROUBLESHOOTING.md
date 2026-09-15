# CenterManager – Xử lý sự cố

---

## 1. Ứng dụng không khởi động

### Lỗi: "Git executable not found"
- **Nguyên nhân:** Git không được cài đặt hoặc không nằm trong PATH, và không có portable Git trong thư mục `git/`.
- **Giải pháp:** Đặt file `git/git.exe` (Portable Git) vào thư mục giải nén hoặc cài đặt Git và thêm vào PATH.

### Lỗi: "Database file not found" / "Unable to create database"
- **Nguyên nhân:** Thiếu quyền ghi vào thư mục `runtime/database/`.
- **Giải pháp:** Cấp quyền ghi cho thư mục ứng dụng hoặc chạy với quyền administrator.

### Lỗi: "Permission denied" khi tạo thư mục
- **Nguyên nhân:** Ứng dụng không có quyền ghi vào thư mục cài đặt.
- **Giải pháp:** Di chuyển ứng dụng đến thư mục có quyền ghi (ví dụ `C:\Users\YourName\CenterManager`).

---

## 2. Lỗi đăng nhập

### Quên mật khẩu admin
- **Giải pháp:** Xóa file `runtime/database/center.db` và khởi động lại – ứng dụng sẽ tạo lại database với admin mặc định (`admin`/`admin123`). **Lưu ý:** Thao tác này xóa toàn bộ dữ liệu hiện có.

### Tài khoản bị khóa
- **Nguyên nhân:** Nhập sai mật khẩu quá 5 lần.
- **Giải pháp:** Chờ 15 phút hoặc nhờ admin mở khóa qua trang quản lý người dùng.

---

## 3. Lỗi cộng tác (Git)

### Không thể acquire WRITE lock
- **Nguyên nhân:** Có người khác đang giữ lock hoặc lock bị treo (stale).
- **Giải pháp:** Kiểm tra trạng thái lock trong `runtime/metadata/lock.json`. Nếu lock cũ (không có heartbeat), xóa file hoặc chờ timeout (60 giây). Hoặc sử dụng trang Diagnostics để xem trạng thái.

### Publish thất bại
- **Nguyên nhân:** Mạng không kết nối, token hết hạn, hoặc xung đột merge.
- **Giải pháp:** Kiểm tra kết nối mạng, kiểm tra token, và nếu xảy ra xung đột, cần giải quyết bằng tay (pull và merge). Hỗ trợ tự động sẽ được nâng cấp trong tương lai.

---

## 4. Lỗi dữ liệu

### Dữ liệu không hiển thị sau khi thêm/sửa
- **Nguyên nhân:** Có thể do chưa publish trong chế độ WRITE.
- **Giải pháp:** Nếu đang ở WRITE mode, hãy nhấn "Publish" để đồng bộ. Nếu ở READ mode, dữ liệu chỉ đọc, hãy yêu cầu WRITE.

### Mất dữ liệu sau khi khởi động lại
- **Nguyên nhân:** Database chưa được lưu hoặc bị ghi đè bởi Git pull.
- **Giải pháp:** Kiểm tra file `runtime/database/center.db` có tồn tại không. Nếu bị mất, khôi phục từ backup.

---

## 5. Lỗi runtime

### "Runtime directory not found" / "Unable to create directories"
- **Nguyên nhân:** Thiếu quyền ghi hoặc đường dẫn chứa ký tự đặc biệt.
- **Giải pháp:** Đảm bảo thư mục cài đặt có quyền ghi và đường dẫn chỉ chứa ký tự ASCII.

### Ứng dụng chạy chậm
- **Nguyên nhân:** Cơ sở dữ liệu lớn hoặc đồng bộ Git chậm.
- **Giải pháp:** Xóa các file log cũ trong `runtime/logs/`, sao lưu và xóa các báo cáo cũ trong `runtime/reports/`.

---

## 6. Liên hệ hỗ trợ

Nếu không khắc phục được, hãy liên hệ quản trị viên và cung cấp:
- File log: `runtime/logs/centermanager.log`
- Mô tả sự cố
- Các bước đã thực hiện