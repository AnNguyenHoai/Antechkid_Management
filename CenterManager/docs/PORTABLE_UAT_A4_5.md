# CenterManager Portable UAT — A4.5

## Mục tiêu

Xác nhận bản ZIP có thể được copy sang máy Windows khác và vẫn vận hành theo đúng hợp đồng:

`Release ZIP → CenterManager.exe + runtime + migrations + bundled Git`

Khi Git được cấu hình, **database trên Git là source of truth**.

## 1. Máy sạch

- [ ] Giải nén ZIP vào một thư mục mới.
- [ ] Không cài Python.
- [ ] Không cài Git hệ thống hoặc loại Git khỏi PATH.
- [ ] Chạy `CenterManager.exe`.
- [ ] Ứng dụng khởi động và hoàn tất first-run configuration.

## 2. Database source of truth

- [ ] Cấu hình Git repository dùng chung.
- [ ] Khởi động lần đầu và xác nhận repository được clone.
- [ ] Xác nhận `runtime/repository/database/center.db` tồn tại.
- [ ] Xác nhận `runtime/Database/center.db` được materialize từ repository.
- [ ] Tạo một local database khác biệt chỉ để kiểm thử.
- [ ] Khởi động lại khi Git vẫn được cấu hình.
- [ ] Xác nhận local database khác biệt bị thay thế bằng database từ Git.
- [ ] Nếu database authoritative trên repository không tồn tại hoặc không thể đồng bộ, ứng dụng phải từ chối startup thay vì dùng database local cũ.

## 3. Hai máy

### Máy A

- [ ] Khởi động từ bản ZIP sạch.
- [ ] Thực hiện một thay đổi dữ liệu hợp lệ.
- [ ] Publish/sync thành công.
- [ ] Xác nhận database trên repository đã nhận thay đổi.

### Máy B

- [ ] Copy cùng ZIP sang thư mục khác hoặc máy Windows khác.
- [ ] Không dùng lại runtime/database của Máy A.
- [ ] Cấu hình cùng Git repository.
- [ ] Khởi động ứng dụng.
- [ ] Xác nhận dữ liệu từ Máy A xuất hiện sau startup synchronization.

## 4. Restart

- [ ] Thoát ứng dụng bình thường.
- [ ] Khởi động lại.
- [ ] Xác nhận startup vẫn lấy database authoritative từ Git.
- [ ] Xác nhận dữ liệu hợp lệ vẫn hiện đầy đủ.

## 5. Portable contract

- [ ] Không cần Python để chạy.
- [ ] Không cần Git hệ thống để chạy Git synchronization.
- [ ] `git/cmd/git.exe` tồn tại trong package.
- [ ] Không có `src/`, `.git/`, `python.exe` hoặc database runtime trong release ZIP.

## Kết quả

Ghi lại:

- Windows version:
- Release ZIP:
- Git repository/branch:
- Máy A:
- Máy B:
- Kết quả first startup:
- Kết quả source-of-truth:
- Kết quả two-machine:
- Kết quả restart:
- Lỗi/log nếu có:
