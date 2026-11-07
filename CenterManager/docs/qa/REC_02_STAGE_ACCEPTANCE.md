# REC-02 — Git MAIN First, Single Active Database, Temporary Backup

## Chốt thiết kế
- Chỉ có một active runtime: `runtime/Database/center.db`.
- Git MAIN đã fetch và được quan sát độc lập mới được phép replace.
- Trước replace phải sao lưu có manifest SHA-256 và kiểm tra lại: database, WAL/SHM, repository, attachments, metadata và Recovery log/outbox/cases.
- Backup chỉ phục vụ review thủ công; không tự merge, publish hoặc restore vào MAIN.
- Nếu mất nguồn hoặc backup lỗi, startup từ chối replace; không xóa dữ liệu local.
- Không dọn snapshot/recovery trước khi bảo toàn.
- Repo/Git cũ chỉ được reset sau khi bản sao đạt kiểm tra.

## Gate
Windows CI: test_rec02_single_main_backup.py; full bootstrap/Git regression; no-DB + business-material; corrupt journal; symlink; rollback DB/WAL; PRECLONE; Git OID race. Cần Windows EXE UAT trước merge.