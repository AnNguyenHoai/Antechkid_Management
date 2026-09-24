# CenterManager — Xử lý sự cố

Cập nhật: 2026-09-24

Mục tiêu của tài liệu này là xử lý sự cố **an toàn**, không làm mất dữ liệu hoặc phá collaboration state.

## 1. Ứng dụng không khởi động

### Thiếu Git executable

Nếu deployment không cấu hình collaboration, thiếu Git có thể chỉ khiến ứng dụng chạy local/offline tùy release/runtime contract.

Nếu deployment đã cấu hình collaboration, kiểm tra bundled Git/package integrity hoặc Git configuration theo hướng dẫn quản trị viên.

Không tự thay thế binary Git bằng file tải không rõ nguồn gốc.

### Không thể tạo/mở runtime database

Kiểm tra:

- thư mục cài đặt/runtime có quyền ghi;
- application không bị antivirus/backup tool khóa file;
- không có process CenterManager khác đang giữ resource ngoài protocol bình thường;
- disk còn dung lượng.

Không xóa `center.db` để thử sửa lỗi.

### Alembic/schema startup error

Dừng thao tác và lưu log. Không tự sửa bảng/schema bằng SQLite editor trên production data.

## 2. Lỗi đăng nhập

### Quên mật khẩu

Liên hệ quản trị viên hoặc sử dụng workflow quản trị/reset mật khẩu được application hỗ trợ.

**Không xóa database để reset admin.** Việc xóa `center.db` có thể làm mất toàn bộ dữ liệu local và trong collaborative deployment còn có thể tạo divergence với authoritative synchronized state.

### Tài khoản bị khóa / không có quyền

Liên hệ quản trị viên để kiểm tra user, role và permission/capability. Không sửa trực tiếp bảng user/role trong database.

## 3. Lỗi collaboration / synchronization

### Không vào được WRITE mode

Nguyên nhân có thể gồm:

- writer/edit session đang thuộc user/máy khác;
- collaboration state chưa refresh;
- synchronization chưa hoàn tất;
- credential/network/platform state lỗi.

Ưu tiên:

1. kiểm tra trạng thái trong UI/Diagnostics nếu có;
2. refresh/restart theo workflow bình thường;
3. kiểm tra network/Git credential nếu deployment có collaboration;
4. cung cấp log cho quản trị viên.

**Không xóa lock/metadata file thủ công** trừ khi đang thực hiện recovery procedure đã được review cho đúng version hiện tại. Collaboration metadata có protocol/lifecycle; xóa file tùy tiện có thể tạo hai writer hoặc mất consistency barrier.

### Startup synchronization thất bại

Nếu Git collaboration đã được cấu hình, synchronized repository state là authoritative. Application cố ý không fallback sang stale local DB.

Kiểm tra:

- network;
- repository URL;
- token/credential;
- bundled/system Git availability;
- repository access;
- log chi tiết.

Sửa nguyên nhân và chạy lại. Không bypass bằng cách xóa Git config chỉ để mở stale data nếu chưa có quyết định của quản trị viên.

### Publish/sync thất bại

Không tự `git reset`, `git push --force`, xóa `.git`, copy database qua lại hoặc resolve conflict bằng thao tác ad-hoc trên production runtime.

Thu thập log/trạng thái và thực hiện procedure recovery phù hợp với collaboration version hiện tại.

## 4. Dữ liệu không cập nhật trên UI

Có thể do:

- workspace chưa nhận refresh event/version change;
- đang ở READ mode;
- mutation bị permission/domain guard từ chối;
- synchronization chưa hoàn tất;
- filter/selected context đang trỏ sang dữ liệu/FinancePeriod khác.

Thử:

1. refresh workspace/application theo UI;
2. kiểm tra collaboration state;
3. kiểm tra permission/action feedback;
4. xác nhận filter/selected period/context;
5. xem log nếu dữ liệu vẫn không khớp.

Không kết luận “database mất dữ liệu” chỉ vì một projection chưa refresh.

## 5. Finance không cho sửa giao dịch

Đây có thể là hành vi đúng.

Kiểm tra:

- user có collaboration WRITE hay không;
- user có Finance capability cần thiết hay không;
- FinancePeriod có bị đóng bởi `Settlement.CONFIRMED` hay không;
- transaction có đang vi phạm future-date/canonical-period/domain rule hay không.

Không sửa trực tiếp database để bypass Finance guard.

## 6. Dữ liệu lịch sử Finance/Outstanding có trạng thái unresolved

Finance Wallet V2 cố ý không đoán dữ liệu lịch sử mơ hồ. Một số row pre-cutover có thể cần FW2-09 reconciliation thay vì tự động back-price/backfill.

Không tự gán FinancePeriod, Wallet hoặc tuition fee history nếu không có rule/provenance xác định.

## 7. Runtime directory / permission error

Đảm bảo application được giải nén vào vị trí có quyền ghi phù hợp. Không chạy production thường xuyên với Administrator chỉ để che một permission/path problem nếu có thể sửa deployment folder đúng cách.

## 8. Application chậm

Thu thập bằng chứng trước khi xóa dữ liệu:

- log;
- thời điểm/screen/workspace chậm;
- database size;
- sync duration/network state;
- query/test evidence nếu là môi trường development.

Có thể dọn các artifact/log/export cũ theo policy, nhưng không xóa database, migration state hoặc collaboration metadata như một bước tối ưu thông thường.

## 9. Thông tin cần gửi khi báo lỗi

Cung cấp:

- version/build nếu có;
- workspace/action đang thực hiện;
- timestamp gần đúng;
- screenshot/message lỗi;
- log từ runtime Logs theo path contract hiện tại;
- deployment đang local hay configured collaboration;
- Git/network status nếu lỗi synchronization.

Không gửi token/password/private key trong ticket hoặc chat.

## 10. Nguyên tắc recovery

Khi chưa chắc chắn:

> dừng mutation, giữ nguyên dữ liệu hiện có, backup/log trước, rồi mới recovery.

Không dùng các thao tác phá hủy (`delete DB`, `delete metadata`, `force push`, sửa trực tiếp SQLite) như troubleshooting mặc định.