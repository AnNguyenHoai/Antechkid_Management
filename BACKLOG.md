# BACKLOG — CenterManager

> Khởi tạo 2026-11-04 từ audit nhánh `main_repos` @ `ac9e96d`, cập nhật theo phản hồi PO cùng ngày.
> Chỉ PO được chuyển task sang **DONE**.
> Quy trình (D-002): trước khi làm task tạo GitHub Issue; làm xong đóng Issue và cập nhật backlog. Trạng thái DONE vẫn cần PO nghiệm thu.
> Lưu ý: bản audit đầu tiên chạy nhầm trên nhánh mặc định `main` (cũ, 2026-09-29). Các phát hiện sai do nhánh cũ đã được đóng ở mục "Đã đóng".

## Bảng tổng hợp — đang mở

| ID | Tiêu đề | Loại | Ưu tiên | Trạng thái | Phụ thuộc |
|---|---|---|---|---|---|
| TECH-002 | Đưa dữ liệu runtime giả ra khỏi Git | Maintenance | P2 | WAITING_PO (#558, PR #559) | — |
| TECH-008 | Dọn snapshot mồ côi trong `runtime/snapshots/` | Bug | P2 | WAITING_PO (#560, PR #561) | — |
| TECH-003 | Làm sạch & cập nhật hệ thống tài liệu | Maintenance | P2 | WAITING_PO (#562, PR #563) | — |
| QA-003 | Rà soát luồng dữ liệu Finance Workspace | QA | P1 | WAITING_PO (#564, PR #565) | — |
| FEAT-001 | Nguồn chi ví công ty / TK cá nhân + hoàn trả | Feature | P1 | WAITING_PO (#567, PR #569) | — |
| BUG-002 | Chuẩn hóa trạng thái/nguồn chi của chi phí cũ | Bug | P1 | WAITING_PO (#566, PR #569) | FEAT-001 |
| BUG-003 | Tách tổng Đã chi / chưa tính dòng tiền ở danh sách Chi | Bug | P2 | WAITING_PO (#568, PR #569) | FEAT-001 |
| FEAT-002 | Hiển thị hoàn học phí là tiền ra trên Dashboard | Feature | P2 | NEW — chờ PO duyệt | — |
| BUG-004 | Chi lọc kỳ theo `finance_period_id` (spec R2) | Bug | P2 | NEW — chờ PO duyệt | — |
| BUG-005 | Dashboard dùng đồng hồ nghiệp vụ; bảng Recent Expense cùng quy tắc KPI | Bug | P3 | NEW — chờ PO duyệt | — |
| QA-004 | Audit đính kèm chứng từ Thu/Chi (dung lượng & hiệu suất) | QA | P1 | WAITING_PO (#572) | — |
| BUG-006 | Tài liệu nhân viên có thể bị xóa khỏi repo khi publish (lệch `Attachment`/`Attachments`) | Bug | P1 | IN_REVIEW (#574, PR #575) | — |
| TECH-011 | Bản sao khôi phục (captures) tăng không giới hạn: ≥3 bản sao toàn bộ workspace mỗi lần lưu | Maintenance | P1 | IN_REVIEW (#576, PR #577) — D-010 | — |
| FEAT-003 | Lưu trữ chứng từ Thu/Chi (metadata + file bất biến + đồng bộ tăng dần) | Feature | P1 | READY (PO duyệt 2026-11-04) | BUG-006, TECH-011 |
| FEAT-004 | UI đính kèm/xem chứng từ Thu/Chi | Feature | P1 | ANALYZED | FEAT-003 |
| TECH-009 | Giám sát dung lượng chứng từ/repo + ngưỡng cảnh báo | Improvement | P2 | NEW | FEAT-003 |
| TECH-010 | Đồng bộ tài liệu nhân viên tăng dần | Improvement | P2 | NEW | BUG-006 |
| FEAT-005 | Đồng bộ tài liệu học sinh/giáo viên giữa các máy, xem theo quyền | Feature | P2 | ANALYZED — PO xác nhận cần (D-009) | FEAT-003 |
| TECH-005 | Giới hạn kiến trúc đồng bộ Git | Improvement | P3 | NEW — để sau theo PO | D-003 |
| TECH-006 | Tách các hàm quá dài | Refactor | P3 | NEW | — |
| TECH-007 | Thống nhất phiên bản Python (CI 3.10, ghi chú dev 3.14) | Maintenance | P3 | NEW | — |

## Bảng tổng hợp — đã đóng / chờ PO đóng

| ID | Tiêu đề | Trạng thái | Lý do |
|---|---|---|---|
| TECH-001 | Đồng bộ nhánh mặc định `main` với `main_repos` | DONE | Default branch = `main_repos`; PO accept 2026-11-04 |
| SEC-001 | Thu hồi GitHub token trong `config.json` | DONE | PO thu hồi token; PO accept 2026-11-04 |
| QA-001 | Ghi nhận baseline CI của `main_repos` | DONE | 3.176 passed / 7 skipped / 0 failed; PO accept 2026-11-04 |
| SEC-002 | Lộ dữ liệu cá nhân trên repo public | CANCELLED | PO xác nhận dữ liệu giả; repo dữ liệu thật private (đã kiểm tra) |
| SEC-003 | Bỏ khóa mã hóa hard-code | CANCELLED | Đã có trên `main_repos`: `DPAPI:v2`, `ENC:v1` chỉ còn để migrate |
| SEC-004 | Buộc đổi mật khẩu admin mặc định | CANCELLED | Đã có trên `main_repos` (`force_password_change=True`, log không chứa mật khẩu); PO đã đổi mật khẩu |
| BUG-001 | Thiếu `cryptography` trong requirements | CANCELLED | Đã có trên `main_repos` (`cryptography>=42.0.0`) |
| QA-002 | CI cho mỗi push/PR | CANCELLED | Đã có `pytest-suite.yml` (3 shard Windows) |

---

## TECH-001 — Đồng bộ nhánh mặc định `main` với `main_repos`

- **Type:** Maintenance · **Priority:** P1 · **Status:** DONE
- **Source:** Audit 2026-11-04
- **Business problem:** Nhánh mặc định `main` dừng ở `32cd46c` (2026-09-29) trong khi phát triển thực tế ở `main_repos`; clone mặc định lấy mã cũ.
- **Expected outcome:** Clone mặc định trả về mã đang phát triển.
- **Scope:** Phương án (A) — đổi default branch trên GitHub sang `main_repos`. PO đã thực hiện 2026-11-04.
- **Acceptance criteria:** `git clone` không chỉ định nhánh lấy được commit mới nhất của nhánh tích hợp.
- **Dependencies:** — · **Implementation reference:** GitHub Settings (PO thực hiện)
- **Verification evidence:** 2026-11-04: GitHub API `GET /repos/AnNguyenHoai/Antechkid_Management` trả `default_branch = main_repos`.
- **PO acceptance:** Accepted — PO, 2026-11-04
- **Notes:** Nhánh `main` cũ vẫn còn. Xóa nhánh là thao tác phá hủy, chỉ làm khi PO yêu cầu.

## TECH-002 — Đưa dữ liệu runtime giả ra khỏi Git

- **Type:** Maintenance · **Priority:** P2 · **Status:** WAITING_PO
- **Source:** Audit 2026-11-04 · PO duyệt 2026-11-04 · **Issue:** #558
- **Business problem:** `main_repos` track 795 file dưới `CenterManager/runtime/`: 771 snapshot `pre_edit_*.db` (~206 MB), `Config/config.json` + `Config/auto_report_state.json`, 17 heartbeat, 1 file CV mẫu, và một gitlink hỏng `runtime/repository` (mode 160000, không có `.gitmodules`). Dữ liệu giả (PO xác nhận).
- **Expected outcome:** Repo nguồn không còn trạng thái runtime của máy dev.
- **Scope (đã thu hẹp, xem Notes):** `git rm --cached` các file trên (không xóa lịch sử, không force-push); thêm `.gitignore` cho `runtime/repository/`, `runtime/snapshots/`, `runtime/attachments/`, `runtime/collaboration/heartbeat/`; sửa test gitlink đang chạy sai đường dẫn; thêm test hồi quy.
- **Acceptance criteria:** `git ls-files CenterManager/runtime` chỉ còn `manifest.json`, `metadata/version.json`, `collaboration/lock.json`; không còn gitlink; CI `Pytest Suite` xanh.
- **Dependencies:** — · **Implementation reference:** PR #559, merge `7940d11`
- **Verification evidence (local):** Chạy trực tiếp logic 2 test trên index đã stage: cả hai PASS. Test gitlink đã sửa phát hiện đúng gitlink trên trạng thái cũ (trước đây luôn pass vì `git ls-files` chạy sai thư mục). CI `main_repos` sau merge (`7940d11`, run 41760078859): success.
- **PO acceptance:** Chưa
- **Notes:**
  - Giữ lại `manifest.json`, `metadata/version.json`, `collaboration/lock.json` vì `build_release.py` copy chúng vào gói phát hành như template — PO quyết định giữ nguyên (D-006).
  - Phần "giới hạn snapshot" tách sang TECH-008 vì chạm vào luồng recovery.
  - Rewrite lịch sử để giảm dung lượng repo là việc riêng, cần PO ủy quyền.

## TECH-008 — Dọn snapshot mồ côi trong `runtime/snapshots/`

- **Type:** Bug · **Priority:** P2 · **Status:** WAITING_PO
- **Source:** Phân tích trong TECH-002 (2026-11-04) · PO duyệt 2026-11-04 · **Issue:** #560
- **Business problem:** Mỗi lần bắt đầu sửa dữ liệu, `WriteTransaction._create_snapshot()` copy toàn bộ DB vào `runtime/snapshots/`. Đường dẫn snapshot chỉ được giữ trong bộ nhớ (`self._snapshot_path`) và chỉ bị xóa khi publish thành công, hủy hoặc retry release thành công. Không bị xóa khi: ứng dụng bị tắt/crash trong lúc EDITING, giao dịch ở FAILED, hoặc RECOVERY_REQUIRED (cố ý giữ). Không có cơ chế dọn khi khởi động. Sau khi khởi động lại, không đoạn code nào đọc lại các snapshot cũ → chúng chỉ chiếm đĩa (máy dev đã tích 771 bản ~206 MB). Mỗi bản là bản sao đầy đủ DB nên dung lượng tăng theo kích thước DB thật.
- **Root cause:** Đã xác nhận bằng đọc code (`services/write_transaction.py`); chưa tái hiện bằng chạy thật.
- **Expected outcome:** Số snapshot trên đĩa có giới hạn mà không làm mất dữ liệu cần cho khôi phục.
- **Scope đề xuất:** Khi khởi động (trước khi có giao dịch nào), xóa snapshot không thuộc giao dịch đang hoạt động, **trừ khi** workspace đang ở trạng thái cần recovery; giữ tối đa N bản mới nhất (đề xuất N = 5) làm lưới an toàn.
- **Acceptance criteria:** Test: tạo nhiều snapshot mồ côi → khởi động → chỉ còn ≤ N; khi có recovery journal đang mở → không xóa gì; CI xanh.
- **Quyết định PO:** N = 5; không dọn khi đang cần khôi phục.
- **Dependencies:** — · **Implementation reference:** PR #561, merge `d2d9d7a`
- **Verification evidence:** Local: 17 test mới pass (stub import, không có PySide6). CI PR (run 41760277126) và CI `main_repos` sau merge (run 41763954959): success.
- **PO acceptance:** Chưa

## TECH-003 — Làm sạch & cập nhật hệ thống tài liệu

- **Type:** Maintenance · **Priority:** P2 · **Status:** WAITING_PO
- **Source:** PO, 2026-11-04 · **Issue:** #562
- **Business problem:** `CenterManager/docs/` có 270 file, 111 file nằm ngay thư mục gốc, phần lớn là báo cáo sprint/task. `docs/PROJECT_CONTEXT.md` (Sprint 0.1) và `docs/CHANGELOG.md` (Sprint 0.5) lỗi thời. Gốc repo có file tạm, bản dump repomix (~4,5 MB), DLL, thư mục prototype cũ.
- **Expected outcome:** Người mới biết ngay tài liệu nào là hiện hành; tài liệu lịch sử được lưu trữ riêng.
- **Đã làm:**
  - `git mv` 74 báo cáo sprint/task vào `docs/archive/sprint-reports/`; `docs/FINANCE/`, `docs/Software/`, Sprint 0.x context/changelog, `docs/config.json` (mẫu cũ có email cá nhân) vào `docs/archive/legacy/`.
  - `docs/PROJECT_CONTEXT.md`, `docs/CHANGELOG.md` thành file trỏ tới bản hiện hành ở gốc repo.
  - Cập nhật `docs/README.md` (thêm nhóm quản lý sản phẩm, bảo mật/vận hành, danh sách tài liệu bị test ghim đường dẫn, vị trí archive, quy tắc lưu báo cáo mới) và `CenterManager/README.md` (phiên bản, SQLCipher/DPAPI, Protected Data Service, CI 3 shard + baseline).
  - Gốc repo: xóa `TEMP_DOC4`, `TEMP_POST_PR182`, 2 `repomix-output.txt`; thêm `.gitignore` chặn repomix; chuyển `EP-FIN-11-REPORT.md`, `libcrypto-1_1-x64.dll`, `InterCommunicationCenter/`, `CenterManager_DeployDriveTest/`, `centermanager-redesign/`, `Note/` vào `archive/`.
  - Giữ nguyên vị trí mọi tài liệu mà test hoặc `AGENTS.md` tham chiếu.
- **Acceptance criteria:** `docs/` gốc chỉ còn tài liệu hiện hành + tài liệu bị test ghim; không có link Markdown tương đối gãy; `docs/README.md` có bản đồ + archive; CI xanh.
- **Dependencies:** — · **Implementation reference:** PR #563, merge `8581da6`
- **Verification evidence (local):** Kiểm tra link Markdown tương đối: 0 link gãy (trước và sau). 53 test đọc tài liệu chạy được không cần Qt: pass; 1 test lỗi do thiếu thư viện trong môi trường (không liên quan). CI `main_repos` sau merge (run 41763983314): success.
- **PO acceptance:** Chưa
- **Ngoài phạm vi:** viết lại nội dung `docs/ARCHITECTURE.md`, `Deployment_Docs/`, hợp đồng domain.

## QA-001 — Ghi nhận baseline CI của `main_repos`

- **Type:** QA · **Priority:** P2 · **Status:** DONE
- **Source:** Audit 2026-11-04
- **Business problem:** Cần một mốc kết quả test thật trước mọi thay đổi tiếp theo.
- **Scope:** Ghi kết quả workflow `Pytest Suite` cho `ac9e96d`.
- **Acceptance criteria:** Có số liệu thật, kèm link run; mỗi test fail (nếu có) có task tương ứng.
- **Dependencies:** — · **Implementation reference:** PR #555
- **Verification evidence:** Run [41751812981](https://github.com/AnNguyenHoai/Antechkid_Management/actions/runs/41751812981) (push `main_repos`, 2026-11-04 08:07, 16m58s) — kết luận `success`. Đọc từ log từng job:
  - shard 0: 1066 passed, 2 skipped
  - shard 1: 983 passed
  - shard 2: 1127 passed, 5 skipped
  - **Tổng: 3.176 passed, 7 skipped, 0 failed.** Không có test fail nên không phát sinh task.
- **Hạn chế:** Không tải được file JUnit XML (bộ lưu trữ artifact bị chặn từ phiên này), nên chưa liệt kê được lý do của 7 test skipped.
- **PO acceptance:** Accepted — PO, 2026-11-04 ("Accept SEC-001, QA-001")

## QA-003 — Rà soát luồng dữ liệu Finance Workspace

- **Type:** QA · **Priority:** P1 · **Status:** WAITING_PO
- **Source:** PO, 2026-11-04 ("dashboard đang sai thông tin cập nhật tiền ra") · **Issue:** #564
- **Business problem:** Số liệu tiền ra trên Dashboard Finance không đúng với thực tế.
- **Scope:** Rà soát luồng dữ liệu (không sửa code), liệt kê bất thường, đề xuất task.
- **Acceptance criteria:** Báo cáo phân loại rõ xác nhận / giả thuyết, có vị trí code; danh sách task đề xuất.
- **Implementation reference:** `CenterManager/docs/finance/QA-003_FINANCE_FLOW_REVIEW.md` (PR #565, merge `d776bac`)
- **Verification evidence:** 9 điểm bất thường (8 xác nhận bằng code, 1 giả thuyết). Nguyên nhân khả năng cao: chi phí mang trạng thái cũ `ĐÃ/CHƯA HOÀN TRẢ` không thuộc tập realized (`Completed`/`Paid`) nên bị loại khỏi tiền ra (F1, F4); tổng ở danh sách Chi dùng định nghĩa khác Dashboard (F2); hoàn học phí ghi là Income âm nên không hiện là tiền ra (F3). Dữ liệu test: 12.050.000 VND chi → Dashboard 0. **Chưa kiểm chứng trên DB thật** — cần chạy truy vấn trong báo cáo.
- **PO acceptance:** Chưa
- **Task phát sinh:** BUG-002, FEAT-001, BUG-003 (đã làm, PR #569); FEAT-002, BUG-004, BUG-005 (NEW, chờ PO duyệt).

## FEAT-001 — Nguồn chi ví công ty / TK cá nhân + hoàn trả

- **Type:** Feature · **Priority:** P1 · **Status:** WAITING_PO · **Issue:** #567
- **Source:** PO 2026-11-04 (từ QA-003 F4) · **Quyết định:** D-008
- **Business problem:** Trạng thái "ĐÃ/CHƯA HOÀN TRẢ" bị dùng như "đã chi/chưa chi" nên chi bằng tài khoản công ty có thể không được tính là tiền ra.
- **Expected outcome:** Chi bằng CASH/BANK CÔNG TY tính ngay vào tiền chi. Chi bằng TK CÁ NHÂN là CHƯA HOÀN TRẢ; khi công ty trả lại, chọn ví công ty + ngày hoàn trả → ĐÃ HOÀN TRẢ và tính vào tiền chi theo ngày hoàn trả.
- **Scope:** `Expense.funding_source`, `incurred_date`; `ExpenseService` (phân loại, chặn chuyển trạng thái sai, `reimburse_expense`); form Chi; danh sách Chi (nhãn, nút Hoàn trả); hộp thoại hoàn trả; cập nhật Domain Spec §6.
- **Acceptance criteria:** xem Issue #567.
- **Implementation reference:** PR #569, commit `b04a3e9`, merge `18b6826`
- **Verification evidence:** CI PR (run 41765228412): 3.211 passed, 7 skipped, 0 failed; 16/16 test mới trong `tests/test_fin_expense_funding_source.py` pass (service trên SQLite thật + migration Alembic thật). CI `main_repos` sau merge (run 41767126182): success — 3.211 passed, 7 skipped, 0 failed. Chưa kiểm thử thủ công trên ứng dụng Windows — cần PO kiểm tra 4 kịch bản: chi BANK CÔNG TY, chi TK CÁ NHÂN, Hoàn trả…, so tổng danh sách với Dashboard.
- **PO acceptance:** Chưa

## BUG-002 — Chuẩn hóa trạng thái/nguồn chi của chi phí cũ

- **Type:** Bug · **Priority:** P1 · **Status:** WAITING_PO · **Issue:** #566
- **Source:** QA-003 F1 · **Quyết định:** D-008 (chỉ sửa dữ liệu ở kỳ chưa quyết toán)
- **Scope:** Migration `1e10a043`. Dòng thuộc kỳ CONFIRMED giữ nguyên. Dòng "TK cá nhân + đã hoàn trả" cũ không có ví hoàn trả → dùng quy tắc alias sẵn có của hệ thống (CASH), **PO cần rà lại**. Chi công ty "Pending" cũ → để nguyên, cần xem thủ công.
- **Verification evidence:** Mô phỏng SQL trên SQLite: dòng kỳ đã chốt không đổi, chạy lại lần 2 không đổi thêm (idempotent). Test migration Alembic thật pass trên CI (run 41765228412). **Chưa chạy trên DB production** — sau khi cập nhật ứng dụng, PO cần rà lại: dòng TK cá nhân đã hoàn trả cũ (đã gán ví CASH) và dòng chi công ty `Pending` cũ (để nguyên, `funding_source` NULL). Implementation reference: PR #569.
- **PO acceptance:** Chưa

## BUG-003 — Tách tổng Đã chi / chưa tính dòng tiền ở danh sách Chi

- **Type:** Bug · **Priority:** P2 · **Status:** WAITING_PO · **Issue:** #568
- **Source:** QA-003 F2
- **Scope:** Danh sách Chi hiển thị thêm "Đã chi – tính vào dòng tiền (khớp Dashboard)" và "Chưa tính vào dòng tiền".
- **Verification evidence:** Test `test_list_cash_flow_total_matches_dashboard_definition` pass trên CI (run 41765228412). Implementation reference: PR #569.
- **PO acceptance:** Chưa

## FEAT-002 — Hiển thị hoàn học phí là tiền ra trên Dashboard

- **Type:** Feature · **Priority:** P2 · **Status:** NEW — chờ PO duyệt
- **Source:** QA-003 F3
- **Business problem:** Hoàn học phí được ghi là Income âm nên làm giảm "Income" thay vì hiện ở tiền ra / Cash Out / Bank Out.
- **Expected outcome:** Dashboard trình bày khoản hoàn như dòng tiền ra mà không đổi cách ghi sổ (số dư ví giữ nguyên).
- **Cần PO quyết định:** hiển thị hoàn tiền thành KPI riêng hay gộp vào "tiền ra".
- **Acceptance criteria / Implementation reference / Evidence:** — · **PO acceptance:** Chưa

## BUG-004 — Chi lọc kỳ theo `finance_period_id`

- **Type:** Bug · **Priority:** P2 · **Status:** NEW — chờ PO duyệt
- **Source:** QA-003 F6
- **Business problem:** Thu lọc kỳ theo kỳ đã lưu, Chi lọc theo khoảng `payment_date` → lệch nhau nếu cấu hình kỳ bị sửa sau khi có dữ liệu (spec R2).
- **Acceptance criteria:** Cùng một kỳ, Thu và Chi dùng chung định danh kỳ; test hồi quy khi đổi cấu hình kỳ.
- **Implementation reference / Evidence:** — · **PO acceptance:** Chưa

## BUG-005 — Dashboard dùng đồng hồ nghiệp vụ; bảng Recent Expense cùng quy tắc KPI

- **Type:** Bug · **Priority:** P3 · **Status:** NEW — chờ PO duyệt
- **Source:** QA-003 F5, F7
- **Business problem:** Dashboard dùng `date.today()` thay vì `get_clock()`; bảng Recent Expense có cả dòng chưa tính dòng tiền trong khi KPI thì không.
- **Acceptance criteria:** Dashboard theo `get_clock()`; bảng Recent Expense phân biệt rõ hoặc chỉ hiện dòng đã chi.
- **Implementation reference / Evidence:** — · **PO acceptance:** Chưa

## QA-004 — Audit đính kèm chứng từ Thu/Chi

- **Type:** QA · **Priority:** P1 · **Status:** WAITING_PO
- **Source:** PO, 2026-11-04 · **Issue:** #572
- **Business problem:** Kế toán cần chứng từ cho từng khoản thu/chi; cần đánh giá ảnh hưởng dung lượng DB và hiệu suất trước khi làm.
- **Implementation reference:** `CenterManager/docs/finance/QA-004_FINANCE_VOUCHER_ATTACHMENT_AUDIT.md`
- **Verification evidence:** Kết luận chính: không lưu BLOB trong SQLite (DB bị commit nguyên file mỗi lần ghi); lưu file ngoài DB, đặt tên theo SHA-256, đồng bộ tăng dần; ước tính repo tăng ~0,3–0,9 GB/năm nếu nén ảnh (100–300 chứng từ/tháng). Phát hiện phụ: F1 tài liệu học sinh/giáo viên không đồng bộ giữa các máy; F2 lệch đường dẫn có thể xóa tài liệu nhân viên khỏi repo khi publish (XN bằng code, chưa tái hiện).
- **PO acceptance:** Chưa · PO đã trả lời 7 câu hỏi (D-009). Bổ sung F3 (băm toàn bộ tệp mỗi lần ghi — PO duyệt sửa) và F4 (mỗi lần lưu tạo ≥3 bản sao toàn bộ workspace, không bao giờ xóa → TECH-011, chờ PO quyết định).

## BUG-006 — Tài liệu nhân viên có thể bị xóa khỏi repo khi publish

- **Type:** Bug · **Priority:** P1 · **Status:** IN_REVIEW · **Issue:** #574 · **PR:** #575
- **Source:** QA-004 F2
- **Business problem:** Upload/khởi động dùng `runtime/Attachment/Employees`; publish lại chép từ `runtime/Attachments/Employees` và xóa thư mục đích trong repo trước → có thể xóa toàn bộ tài liệu nhân viên trên repo dữ liệu.
- **Root cause:** Xác nhận bằng đọc code (`employee_document_service.py:26`, `startup_sync.py:723`, `git_synchronization_provider.py:1152`); chưa tái hiện trên máy thật.
- **Acceptance criteria:** Publish và khởi động dùng cùng một thư mục; test hồi quy: upload → publish → repo có file; không bao giờ xóa repo mirror khi nguồn không tồn tại.
- **Cần làm trước:** PO/người có quyền kiểm tra repo dữ liệu thật còn đủ `Attachments/Employees` không.
- **Verification evidence:** 4 test mới (`tests/test_bug_006_employee_attachment_publish_path.py`) pass trên logic trích xuất local; full suite chờ CI.
- **PO acceptance:** Chưa

## TECH-005 — Giới hạn kiến trúc đồng bộ Git

- **Type:** Improvement · **Priority:** P3 · **Status:** NEW — PO chấp nhận giới hạn, xử lý sau
- **Source:** Audit 2026-11-04, PO xác nhận
- **Business problem:** Mỗi lần ghi commit cả file DB → repo dữ liệu phình; chỉ một máy ghi tại một thời điểm; phụ thuộc GitHub.
- **Expected outcome (khi kích hoạt):** Báo cáo theo dõi dung lượng repo dữ liệu và ngưỡng cần hành động; so sánh phương án (gia cố Git sync / DB server / web).
- **Acceptance criteria:** Có ngưỡng cảnh báo được PO duyệt (ví dụ dung lượng repo hoặc thời gian publish).
- **Dependencies:** D-003. · **Implementation reference:** — · **Verification evidence:** — · **PO acceptance:** Chưa

## TECH-006 — Tách các hàm quá dài

- **Type:** Refactor · **Priority:** P3 · **Status:** NEW
- **Business problem:** Hàm > 200 dòng khó test, dễ hồi quy: `app.main` (381), `student_report_generator._build_pdf` (336), `ApplicationShell.__init__` (298), `write_handoff_runtime_sync_service._apply_runtime_update_with_permit` (233), `install_lock_acquisition_diagnostics` (204). Có 555 khối `except Exception` trong `src/`.
- **Scope:** Làm từng hàm qua Issue riêng, không đổi hành vi.
- **Acceptance criteria:** CI xanh trước/sau; không thay đổi hành vi người dùng.
- **Dependencies:** — · **Implementation reference:** — · **Verification evidence:** — · **PO acceptance:** Chưa

## TECH-007 — Thống nhất phiên bản Python

- **Type:** Maintenance · **Priority:** P3 · **Status:** NEW
- **Business problem:** CI và build dùng Python 3.10; `archive/Note/Note.md` (ghi chú cũ) hướng dẫn cài bằng Python 3.14; `DEVELOPMENT_GUIDE.md` đã ghi 3.10 → máy dev và bản phát hành có thể chạy khác nhau.
- **Scope:** Chọn một phiên bản, ghi vào README/CI.
- **Acceptance criteria:** CI và hướng dẫn dev cùng phiên bản; CI xanh.
- **Dependencies:** — · **Implementation reference:** — · **Verification evidence:** — · **PO acceptance:** Chưa

---

## SEC-001 — Thu hồi GitHub token trong `config.json` (DONE)

- **Type:** Maintenance · **Priority:** P0 · **Status:** DONE
- **Business problem:** `CenterManager/runtime/Config/config.json` (vẫn còn trên cả `main` và `main_repos`) chứa bundle `ENC:v1:` giải mã được bằng khóa legacy trong `core/crypto.py`; bên trong có một GitHub PAT `ghp_…`.
- **Verification evidence:** Audit giải mã để xác minh, không in giá trị token. PO xác nhận 2026-11-04 token đã thu hồi; token mới dùng DPAPI và lưu ở repo riêng. Audit không tự kiểm tra token còn hiệu lực hay không (không dùng thông tin xác thực của người khác).
- **PO acceptance:** Accepted — PO, 2026-11-04 ("Accept SEC-001, QA-001")
- **Notes:** File này sẽ được gỡ khỏi Git trong TECH-002.

## SEC-002, SEC-003, SEC-004, BUG-001, QA-002 — CANCELLED

Chi tiết lý do ở bảng "đã đóng". Bằng chứng: kiểm tra mã trên `main_repos` @ `ac9e96d` (`core/crypto.py`, `database/seed.py`, `requirements.txt`, `.github/workflows/pytest-suite.yml`) và xác nhận của PO ngày 2026-11-04.
