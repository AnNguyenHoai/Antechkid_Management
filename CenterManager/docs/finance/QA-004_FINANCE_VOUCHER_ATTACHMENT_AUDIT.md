# QA-004 — Audit: đính kèm chứng từ cho khoản Thu/Chi

- **Ngày:** 2026-11-04 · **Issue:** #572 · **Commit audit:** `main_repos` @ `18b6826`
- **Yêu cầu PO:** khi thêm khoản thu/chi cần mục upload chứng từ phục vụ kế toán; đánh giá ảnh hưởng tới dung lượng DB và hiệu suất.
- **Phương pháp:** đọc code các luồng đính kèm hiện có, luồng ghi/đồng bộ Git, backup, snapshot. Không sửa code. **XN** = xác nhận bằng code · **GT** = giả thuyết cần kiểm chứng.

## 1. Kết luận ngắn

1. **Không được lưu file chứng từ vào SQLite (BLOB).** Mỗi lần ghi, ứng dụng chép toàn bộ DB làm snapshot và commit **nguyên file DB** lên repo Git dữ liệu. Nếu DB chứa ảnh/PDF, mỗi lần bấm Lưu sẽ đẩy lại toàn bộ chứng từ → repo phình theo *số lần ghi × dung lượng chứng từ*, ứng dụng chậm dần rõ rệt. Đây là rủi ro lớn nhất.
2. **Lưu file ngoài DB, DB chỉ giữ metadata** (vài trăm byte/chứng từ) → DB gần như không tăng; snapshot, backup, publish DB không bị ảnh hưởng.
3. **Repo Git dữ liệu vẫn sẽ tăng** theo tổng dung lượng chứng từ (Git giữ mọi file mãi mãi, xóa file không làm repo nhỏ lại). Cần nén ảnh, giới hạn kích thước, lưu file bất biến và đặt ngưỡng cảnh báo.
4. **Không dùng lại cơ chế đồng bộ của tài liệu nhân viên**: nó xóa và chép lại toàn bộ thư mục mỗi lần publish (chậm dần theo tổng dung lượng) và hiện đang có lỗi đường dẫn (F2) có thể làm mất tài liệu nhân viên trên repo.

## 2. Hiện trạng đính kèm trong hệ thống

| Loại | Nơi lưu file | DB lưu gì | Đồng bộ sang máy khác | Ghi chú |
|---|---|---|---|---|
| Tài liệu nhân viên | `runtime/Attachment/Employees/<mã>/<loại>/<uuid>_<tên>` | `employee_documents`: tên gốc, đường dẫn | Có — mỗi publish **xóa rồi chép lại toàn bộ** thư mục vào repo (`git_synchronization_provider.py:1146`) | Không giới hạn dung lượng/loại file |
| Tài liệu học sinh | `runtime/Attachment/<mã HS>/` | `documents`: đường dẫn | **Không** (nằm ngoài `runtime/repository`) | XN — chỉ có trên máy upload |
| Tài liệu giáo viên | `runtime/Attachment/teachers/<mã>/` | `teacher_documents` | **Không** | XN — như trên |

Không có model nào dùng BLOB (đã tìm `LargeBinary`/`BLOB` trong `models/`). Backup (`platform/backup/backup_service.py`) chỉ sao lưu DB, **không** sao lưu tệp đính kèm. Tệp đính kèm **không được mã hóa** (DB production dùng SQLCipher; tài liệu SEC-02 không đề cập đính kèm).

## 3. Phát hiện phụ (ngoài phạm vi chứng từ nhưng ảnh hưởng thiết kế)

### F1 — [XN · Trung bình] Tài liệu học sinh/giáo viên không đồng bộ giữa các máy
Lưu ở `runtime/Attachment/...`, không nằm trong repo dữ liệu và không có bước mirror. Máy khác thấy bản ghi trong DB nhưng không mở được file. (Kiến trúc cũ dựa vào Google Drive Desktop; cần PO xác nhận hiện còn dùng không.)

### F2 — [XN bằng code · Cao, chưa tái hiện] Tài liệu nhân viên có thể bị xóa khỏi repo khi publish
- Upload và tải về khi khởi động dùng thư mục **`runtime/Attachment/Employees`** (số ít — `employee_document_service.py:26`, `startup_sync.py:723`).
- Publish lại chép từ **`runtime/Attachments/Employees`** (số nhiều — `git_synchronization_provider.py:1152`), xóa thư mục đích trong repo trước.
- Nếu thư mục số nhiều không tồn tại → publish **xóa toàn bộ `Attachments/Employees` trong repo** ("repository mirror cleared"); máy khác khi khởi động sẽ xóa luôn bản local của họ. Nếu thư mục số nhiều còn sót từ bản cũ → publish đẩy lên nội dung cũ.
- Đề xuất task riêng **BUG-006 (P1)**; cần kiểm tra repo dữ liệu thật xem `Attachments/Employees` còn đầy đủ không trước khi sửa.

### F3 — [XN · Cao] Cơ chế khôi phục ghi (write recovery) băm toàn bộ tệp đính kèm nhiều lần mỗi lần ghi
- `WriteRecoveryJournal.fingerprint()` (`platform/write_recovery.py:258`) đọc và tính SHA-256 **mọi file** trong `runtime/repository` và `runtime/Attachment` (cả bản trong repo lẫn bản runtime).
- Được gọi qua `_local_files()` ở `published()`, `released()`, `record_synchronized()` và khi kiểm tra `assert_replaceable()` — tức nhiều lần trong mỗi lần ghi/đồng bộ.
- Hiện tại ít file nên không thấy chậm. Với ~0,3–0,6 GB chứng từ/năm (x2 vì có cả bản runtime và bản repo), mỗi lần ghi sẽ đọc lại hàng GB → **chậm dần theo thời gian**, đặc biệt trên ổ HDD.
- Hệ quả thiết kế: chứng từ phải là file **bất biến, đặt tên theo SHA-256** để cơ chế khôi phục có thể kiểm tra bằng tên + kích thước thay vì đọc lại nội dung. Việc này **chạm vào lớp write recovery** (vùng nhạy cảm) → cần PO duyệt riêng.

### F4 — [XN · Cao, đã tồn tại độc lập với chứng từ] Mỗi lần ghi tạo ít nhất 3 bản sao toàn bộ workspace và không bao giờ xóa
- `WriteRecoveryJournal.preserve()` (`platform/write_recovery.py:307`) chép **toàn bộ** `runtime/repository` (kể cả thư mục `.git` chứa mọi phiên bản DB đã tải về), DB, metadata, **tất cả tệp đính kèm**, Export, Reports vào `runtime.write-recovery/captures/<uuid>/`.
- Được gọi ở: bắt đầu sửa (`begin` → `preserve('base')`), trước publish (`write_transaction.py:871`), sau publish (`published` → `preserve('published')`), khi hủy, khi hòa giải → **≥ 3 bản sao mỗi lần bấm Lưu**.
- Theo hợp đồng E1B-1 (`docs/collaboration/E1B1_DURABLE_WRITE_RECOVERY.md:18`): *captures không bao giờ bị xóa tự động* → thư mục `runtime.write-recovery` tăng không giới hạn trên mọi máy.
- Với chứng từ: mỗi lần lưu sẽ chép lại toàn bộ chứng từ (bản runtime + bản repo) ×3. Ví dụ 0,5 GB chứng từ → ~3 GB ghi đĩa và giữ lại **mỗi lần lưu**. Không khả thi nếu không đổi.
- **Cần đo trên máy thật** (PowerShell, thư mục cạnh `runtime`):
  `"{0:N0} MB" -f ((Get-ChildItem .\runtime.write-recovery -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)`
- Đề xuất **TECH-011 (P1)**: (a) capture không chép `.git/objects` và file bất biến đặt tên theo SHA-256 (đã có sẵn trong repo/Git — chỉ ghi tham chiếu tên + kích thước); (b) chính sách giữ capture (ví dụ giữ capture của N phiên gần nhất và mọi capture của phiên chưa CLEAN). Điểm (b) **thay đổi hợp đồng an toàn E1B-1** → cần PO quyết định.
- **FEAT-003 phụ thuộc TECH-011**: chưa nên bật upload chứng từ trước khi xử lý F4.

## 4. Ảnh hưởng dung lượng & hiệu suất — chứng từ Thu/Chi

| Thành phần | Nếu lưu BLOB trong DB | Nếu lưu file ngoài DB (khuyến nghị) |
|---|---|---|
| Kích thước SQLite | + toàn bộ dung lượng chứng từ | + ~0,3 KB/chứng từ (10.000 chứng từ ≈ 3 MB) |
| Snapshot mỗi lần sửa (`runtime/snapshots`) | Chép cả chứng từ mỗi lần | Không đổi |
| Commit DB mỗi lần ghi | Đẩy lại toàn bộ chứng từ **mỗi lần ghi** | Không đổi |
| Repo Git dữ liệu | Tăng ≈ số lần ghi × tổng chứng từ | Tăng ≈ tổng chứng từ (mỗi file một lần) |
| Thời gian publish | Tăng tuyến tính, sẽ rất chậm | Chỉ thêm thời gian đẩy file mới |
| Máy mới clone | Chậm | Tải toàn bộ chứng từ hiện có (clone `--depth 1`) |
| Mã hóa | Có (SQLCipher) | Không, trừ khi bổ sung |

**Ước tính repo dữ liệu (chỉ chứng từ):**

| Chứng từ/tháng | Ảnh điện thoại không nén (~3 MB) | Nén còn ~250 KB (JPEG 1600px) / PDF scan |
|---|---|---|
| 100 | ~3,6 GB/năm | ~0,3 GB/năm |
| 300 | ~10,8 GB/năm | ~0,9 GB/năm |

GitHub chặn file > 100 MB và khuyến nghị giữ repo dưới ~1 GB (nên dưới 5 GB). Không nén thì vượt ngưỡng trong vài tháng; có nén thì khoảng 1–3 năm tùy khối lượng → **cần ngưỡng cảnh báo và kế hoạch dài hạn** (liên quan TECH-005).

## 5. Thiết kế đề xuất

1. **Bảng `finance_attachments`** (metadata): `id`, `entity_type` (`INCOME`/`EXPENSE`), `entity_id`, `original_filename`, `stored_path`, `mime_type`, `size_bytes`, `sha256`, `uploaded_by`, `uploaded_at`, `deleted_at`. Không có cột BLOB.
2. **Lưu file bất biến, đặt tên theo nội dung:** `repository/Attachments/Finance/<yyyy>/<mm>/<sha256>.<ext>`. Cùng file upload hai lần chỉ lưu một bản; file không bao giờ bị ghi đè → Git lưu đúng một lần.
3. **Đồng bộ tăng dần:** chỉ `git add` file mới của giao dịch đang ghi; không xóa/chép lại cả thư mục.
4. **Giới hạn đầu vào:** chỉ PDF/JPG/PNG; tối đa N MB/file và M file/giao dịch; ảnh tự thu nhỏ (~1600 px, JPEG ~80%) bằng Qt có sẵn — không thêm thư viện.
5. **Quy tắc nghiệp vụ:** thêm/xóa chứng từ theo quyền sửa Thu/Chi tương ứng; kỳ đã quyết toán chỉ xem; xóa chứng từ = xóa mềm metadata, giữ file để đối soát; khoản chi TK cá nhân có thể đính kèm cả chứng từ chi gốc và chứng từ hoàn trả.
6. **Giám sát:** trang Diagnostics hiện tổng dung lượng chứng từ và repo; cảnh báo ở 500 MB / 1 GB.
7. **Hiệu suất UI:** danh sách Thu/Chi chỉ hiện số lượng chứng từ (đếm theo lô, không tải file); file chỉ mở khi người dùng bấm xem.

## 6. Quyết định của PO (2026-11-04, D-009)

| # | Câu hỏi | Trả lời |
|---|---|---|
| 1 | Bắt buộc hay tùy chọn | **Tùy chọn** |
| 2 | Loại file, giới hạn | **PDF, PNG, JPG; 5 MB/file; tối đa 5 file/khoản** |
| 3 | Khối lượng | **100–200 chứng từ/tháng** → ~0,3–0,6 GB/năm nếu nén ảnh; ~3,6–7,2 GB/năm nếu không nén |
| 4 | Kỳ đã quyết toán | **Vẫn cho bổ sung** chứng từ (không đổi số tiền) |
| 5 | Mã hóa file | **Không** |
| 6 | Thời hạn lưu | **Vô thời hạn** → không xóa vật lý; xóa = ẩn (soft delete) |
| 7 | Đồng bộ tài liệu học sinh/giáo viên | **Có, theo quyền của tài khoản** |

Lưu ý cho câu 7: với repo dữ liệu dùng chung hiện tại, file đồng bộ sẽ **có mặt trên mọi máy**; "theo quyền" chỉ kiểm soát được việc **xem/mở trong ứng dụng**. Nếu cần máy không có quyền thì không có file, phải mã hóa hoặc tách repo — cần PO xác nhận.

Với 5 MB × 5 file và lưu vô thời hạn: repo dữ liệu sẽ vượt ~1 GB sau khoảng 2–3 năm dù đã nén → TECH-009 (giám sát) và TECH-005 (kiến trúc lưu trữ dài hạn) cần được lên lịch.

## 6b. Câu hỏi ban đầu

1. Chứng từ **bắt buộc** hay **tùy chọn** khi lưu khoản thu/chi? Bắt buộc với loại nào?
2. Loại file chấp nhận và giới hạn dung lượng mỗi file (đề xuất PDF/JPG/PNG, 5 MB, tối đa 5 file/giao dịch)?
3. Khối lượng ước tính: bao nhiêu chứng từ mỗi tháng?
4. Kỳ đã quyết toán: có cho bổ sung chứng từ không (không làm thay đổi số tiền)?
5. Có cần mã hóa file chứng từ như DB không (bảo vệ khi lộ repo/máy)? Đổi lại: phức tạp hơn, không mở trực tiếp bằng Explorer được.
6. Thời hạn lưu trữ và quy định xóa (cần kế toán xác nhận theo quy định lưu trữ chứng từ kế toán).
7. Tài liệu học sinh/giáo viên (F1): có cần đồng bộ giữa các máy không?

## 7. Task đề xuất

| Đề xuất | Nội dung | Ưu tiên |
|---|---|---|
| BUG-006 | Sửa lỗi đường dẫn `Attachment`/`Attachments` khi publish tài liệu nhân viên (F2); kiểm tra repo dữ liệu thật trước | P1 |
| FEAT-003 | Lưu trữ chứng từ Thu/Chi: bảng metadata, lưu file bất biến theo SHA-256, đồng bộ tăng dần, giới hạn & nén; write recovery kiểm tra file bất biến bằng tên + kích thước (F3) | P1 |
| FEAT-004 | UI đính kèm/xem chứng từ trong form và chi tiết Thu/Chi, hộp thoại Hoàn trả | P1 |
| TECH-009 | Giám sát dung lượng chứng từ/repo trong Diagnostics + ngưỡng cảnh báo | P2 |
| TECH-010 | Đồng bộ tài liệu nhân viên tăng dần thay vì xóa-chép toàn bộ mỗi publish | P2 |
| TECH-011 | Giới hạn bản sao khôi phục (captures): bỏ `.git/objects` + file bất biến, chính sách giữ (F4) | P1 |
| FEAT-005 | Đồng bộ tài liệu học sinh/giáo viên giữa các máy (nếu PO cần, F1) | P3 |
