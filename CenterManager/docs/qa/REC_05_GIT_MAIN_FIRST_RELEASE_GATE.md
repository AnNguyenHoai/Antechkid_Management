# REC-05 — Git MAIN First + Single Active DB + Recovery Log + Temporary Backup

## Nghiệm thu kiến trúc

1. Chỉ **một active database**: `runtime/Database/center.db`. Không sử dụng router hoặc `runtime-main-*`.
2. Quyền dữ liệu lấy từ Git MAIN có commit/OID quan sát độc lập. Giữ nguyên remote WRITE lease và publication CAS.
3. Trước khi cài MAIN, sao lưu có SHA-256 và xác minh **toàn bộ dữ liệu cũ**: DB/WAL/SHM, repo, attachments, metadata, Recovery journal/outbox/cases, logs liên quan.
4. Sau backup được xác minh, cho phép Git reset/cài MAIN nguyên tử. Archive không bao giờ được merge hoặc publish.
5. Sau SQLCipher, Alembic và Git verification, cấp receipt CLEAN/VERIFIED **mới** cho DB MAIN, không biến trạng thái Recovery cũ thành CLEAN; raw journal cũ vẫn nằm trong archive.
6. Recovery UI chỉ nhắc không modal, người dùng tự đối chiếu và nhập lại thay đổi chưa publish.
7. Với lỗi mạng: Offline READ theo cơ chế an toàn hiện tại; WRITE vẫn bị khóa.
8. Nếu không thể xác minh backup hoặc MAIN, giữ nguyên local và không cấp WRITE.

## Test tự động

- `test_rec02_single_main_backup.py`: lưu toàn bộ DB/WAL/log, lỗi hash, old journal hỏng, thiếu journal nhưng có business material.
- `test_rec03_single_main_acceptance.py`: receipt mới sau verified backup, từ chối remote OID lệch, archive bị sửa, kiểm tra đăng nhập chỉ sau receipt.
- `test_rec04_nonmodal_notice.py`: không modal, không auto-acknowledge, chỉ báo manual backups.
- `test_rec05_single_main_faults.py`: crash khi đang copy, disk-full khi seal receipt, remote MAIN thay đổi, không có multiple active runtime.
- `test_rv05_recovery_to_new_write.py`: Git bare remote + SQLCipher integration, local edit cũ không lên MAIN, Start Editing/Finish Editing phiên mới hoạt động.
- Toàn bộ Windows pytest shards trên HEAD mới nhất từng PR #610–#614 phải PASS.

## Windows EXE release gate — chưa xác nhận bằng CI đơn thuần

- [ ] Máy nhân viên có `db_present=False, business_material=True` boot MAIN rồi Start Editing/Finish Editing.
- [ ] Máy có journal `OPEN`, `PUBLISHING`, `RECONCILED`, corrupt JSON và raw WAL vẫn mở READ, xin WRITE sau backup, không mất data cũ.
- [ ] Hai máy cùng đọc MAIN; chỉ một máy giữ WRITE; stale client không publish được.
- [ ] Kill EXE khi sao lưu trước khi copy xong, khi cài DB, sau khi cài nhưng chưa seal receipt; restart an toàn.
- [ ] Disk full, antivirus file lock, Git auth revoked, OID race, sai khóa SQLCipher và identity: fail closed mà không ghi đè dữ liệu chưa backup.
- [ ] Xem lại backup/log và nhập lại một khoản Income/Expense/Student, sau đó Finish Editing; không có sửa đổi local cũ tự động xuất hiện trên MAIN.
- [ ] Review các file DPAPI/key, quyền truy cập thư mục manual-review và chính sách xóa backup sau khi người dùng xác nhận đã kiểm tra.

Không merge hoặc phát hành REC-02/03/04/05 chỉ dựa trên CI PASS khi các test Windows EXE trọng yếu chưa hoàn thành.
