# CenterManager – Checklist phát hành

Dùng để xác nhận phiên bản đã sẵn sàng phát hành.

---

## 1. Kiểm tra mã nguồn
- [ ] Không còn debug print, TODO, FIXME.
- [ ] Tất cả test pass (`pytest`).
- [ ] Không còn lỗi linting.
- [ ] File `.gitignore` đầy đủ.

## 2. Xây dựng (Build)
- [ ] Script `build_release.py` chạy không lỗi.
- [ ] File `CenterManager.exe` được tạo trong `dist/CenterManager/`.
- [ ] Thư mục `runtime/` và `config/` được sao chép đúng.
- [ ] Kích thước file hợp lý (< 100 MB).

## 3. Kiểm thử trên máy sạch (không cài Python/Git)
- [ ] Ứng dụng khởi động được.
- [ ] Thư mục runtime được tạo tự động.
- [ ] Đăng nhập với admin mặc định thành công.
- [ ] Đổi mật khẩu thành công.
- [ ] Thêm một học sinh, xem danh sách.
- [ ] Thêm phụ huynh, chỉnh sửa, xóa.
- [ ] Thêm đánh giá.
- [ ] Tạo lớp học, giáo viên.
- [ ] Ghi danh học sinh vào lớp.
- [ ] Ghi nhận điểm danh.
- [ ] Tạo khoản thu/chi.
- [ ] Xuất báo cáo PDF.
- [ ] Vào chế độ WRITE, publish, kiểm tra phiên bản tăng.
- [ ] Khởi động lại, dữ liệu vẫn còn.

## 4. Kiểm tra cộng tác (Git)
- [ ] Cấu hình Git trong `config.json`.
- [ ] Kéo và push thành công.
- [ ] Lock hoạt động đúng (chỉ một người WRITE).

## 5. Tài liệu
- [ ] `README.md` đã cập nhật.
- [ ] `INSTALL.md`, `DEPLOYMENT.md`, `UPDATE.md`, `TROUBLESHOOTING.md` đã hoàn chỉnh.
- [ ] `RELEASE_CHECKLIST.md` đã được review.

## 6. Phân phối
- [ ] Tạo file ZIP từ thư mục `dist/CenterManager/`.
- [ ] Đặt tên file theo phiên bản: `CenterManager_v1.0.0.zip`.
- [ ] Tạo tag Git cho phiên bản (nếu dùng).
- [ ] Thông báo cho người dùng về bản phát hành mới.

---

**Ký xác nhận:**
- Người xây dựng: _________________
- Ngày: _________________
- Kết quả: [ ] PASS / [ ] FAIL