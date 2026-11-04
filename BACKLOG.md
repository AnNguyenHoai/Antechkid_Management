# BACKLOG — CenterManager

> Khởi tạo 2026-11-04 từ audit nhánh `main_repos` @ `ac9e96d`, cập nhật theo phản hồi PO cùng ngày.
> Chỉ PO được chuyển task sang **DONE**. Chưa task nào được duyệt triển khai.
> Lưu ý: bản audit đầu tiên chạy nhầm trên nhánh mặc định `main` (cũ, 2026-09-29). Các phát hiện sai do nhánh cũ đã được đóng ở mục "Đã đóng".

## Bảng tổng hợp — đang mở

| ID | Tiêu đề | Loại | Ưu tiên | Trạng thái | Phụ thuộc |
|---|---|---|---|---|---|
| TECH-001 | Đồng bộ nhánh mặc định `main` với `main_repos` | Maintenance | P1 | ANALYZED | — |
| TECH-002 | Đưa dữ liệu runtime giả ra khỏi Git & giới hạn snapshot | Maintenance | P2 | ANALYZED | TECH-001 |
| TECH-003 | Làm sạch & sắp xếp lại tài liệu (`docs/` 270 file, file tạm ở gốc repo) | Maintenance | P2 | ANALYZED | D-002 |
| QA-001 | Ghi nhận baseline CI của `main_repos` | QA | P2 | WAITING_PO | — |
| TECH-005 | Giới hạn kiến trúc đồng bộ Git | Improvement | P3 | NEW — để sau theo PO | D-003 |
| TECH-006 | Tách các hàm quá dài | Refactor | P3 | NEW | — |
| TECH-007 | Thống nhất phiên bản Python (CI 3.10, ghi chú dev 3.14) | Maintenance | P3 | NEW | — |

## Bảng tổng hợp — đã đóng / chờ PO đóng

| ID | Tiêu đề | Trạng thái | Lý do |
|---|---|---|---|
| SEC-001 | Thu hồi GitHub token trong `config.json` | WAITING_PO | PO báo đã thu hồi; chờ PO xác nhận đóng |
| SEC-002 | Lộ dữ liệu cá nhân trên repo public | CANCELLED | PO xác nhận dữ liệu giả; repo dữ liệu thật private (đã kiểm tra) |
| SEC-003 | Bỏ khóa mã hóa hard-code | CANCELLED | Đã có trên `main_repos`: `DPAPI:v2`, `ENC:v1` chỉ còn để migrate |
| SEC-004 | Buộc đổi mật khẩu admin mặc định | CANCELLED | Đã có trên `main_repos` (`force_password_change=True`, log không chứa mật khẩu); PO đã đổi mật khẩu |
| BUG-001 | Thiếu `cryptography` trong requirements | CANCELLED | Đã có trên `main_repos` (`cryptography>=42.0.0`) |
| QA-002 | CI cho mỗi push/PR | CANCELLED | Đã có `pytest-suite.yml` (3 shard Windows) |

---

## TECH-001 — Đồng bộ nhánh mặc định `main` với `main_repos`

- **Type:** Maintenance · **Priority:** P1 · **Status:** ANALYZED
- **Source:** Audit 2026-11-04
- **Business problem:** Nhánh mặc định `main` dừng ở `32cd46c` (2026-09-29) trong khi phát triển thực tế ở `main_repos` (PR #554, 2026-11-04). Ai clone mặc định — người hay AI — sẽ làm việc trên mã cũ hơn hơn 5 tuần. Chính bản audit đầu tiên đã bị dẫn sai vì điều này.
- **Expected outcome:** Clone mặc định trả về mã đang phát triển.
- **Scope (PO chọn 1):** (A) Đổi default branch trên GitHub sang `main_repos`; (B) fast-forward `main` lên `main_repos` và giữ đồng bộ; (C) xóa `main` nếu không còn dùng (phá hủy — cần PO ủy quyền).
- **Acceptance criteria:** `git clone` không chỉ định nhánh lấy được commit mới nhất của nhánh tích hợp.
- **Dependencies:** — · **Implementation reference:** — (thao tác GitHub Settings, PO thực hiện hoặc cấp quyền) · **Verification evidence:** — · **PO acceptance:** Chưa

## TECH-002 — Đưa dữ liệu runtime giả ra khỏi Git & giới hạn snapshot

- **Type:** Maintenance · **Priority:** P2 · **Status:** ANALYZED
- **Source:** Audit 2026-11-04
- **Business problem:** Trên `main_repos` vẫn track 795 file dưới `CenterManager/runtime/`: 771 snapshot `pre_edit_*.db` (~206 MB), `Config/config.json` (dù `.gitignore` đã chặn — file đã track từ trước nên vẫn còn), heartbeat, 1 file CV mẫu. Dữ liệu là giả (PO xác nhận) nên không phải sự cố bảo mật, nhưng làm repo nặng và tạo thói quen commit dữ liệu runtime.
- **Expected outcome:** Repo nguồn chỉ chứa source và fixture có chủ đích.
- **Scope:** `git rm --cached` các file runtime (không xóa lịch sử, không force-push); bổ sung `.gitignore` cho `runtime/snapshots/`, `runtime/collaboration/`, `runtime/attachments/`; kiểm tra luồng nào để snapshot không bị dọn và có cần chính sách giữ N bản.
- **Acceptance criteria:** `git ls-files CenterManager/runtime` chỉ còn placeholder được duyệt; CI xanh; test chứng minh số snapshot không tăng vô hạn.
- **Dependencies:** TECH-001 (để thay đổi vào đúng nhánh). · **Implementation reference:** — · **Verification evidence:** — · **PO acceptance:** Chưa
- **Notes:** Rewrite lịch sử để giảm dung lượng là việc riêng, cần PO ủy quyền.

## TECH-003 — Làm sạch & sắp xếp lại tài liệu

- **Type:** Maintenance · **Priority:** P2 · **Status:** ANALYZED (PO đã yêu cầu ghi vào backlog)
- **Source:** PO, 2026-11-04
- **Business problem:** `CenterManager/docs/` có 270 file, phần lớn là báo cáo từng sprint/task. Một số file "hiện hành" đã lỗi thời: `PROJECT_CONTEXT.md` (Sprint 0.1), `CHANGELOG.md` (dừng ở Sprint 0.5). Ở gốc repo có file tạm/không thuộc source: `TEMP_DOC4`, `TEMP_POST_PR182`, `EP-FIN-11-REPORT.md`, `repomix-output.txt` (2,1 MB; thêm 1 bản trong `CenterManager/`), `libcrypto-1_1-x64.dll`. Thư mục phụ: `InterCommunicationCenter/`, `CenterManager_DeployDriveTest/`, `centermanager-redesign/`, `Note/`.
- **Expected outcome:** Người mới biết ngay tài liệu nào là hiện hành; tài liệu lịch sử được lưu trữ riêng.
- **Scope:** Lập danh mục `docs/` theo nhóm (hiện hành / hợp đồng domain / lịch sử); chuyển báo cáo sprint vào `docs/archive/`; đánh dấu "Superseded" cho file lỗi thời; PO quyết định giữ/xóa từng file ở gốc repo; cập nhật đường dẫn trong `AGENTS.md` nếu có file di chuyển.
- **Acceptance criteria:** Có `docs/README.md` liệt kê tài liệu hiện hành; không còn file tạm ở gốc repo; các tham chiếu trong `AGENTS.md`/`AI_COLLABORATION_PROTOCOL.md` vẫn đúng; CI xanh (một số test có thể đọc file docs).
- **Dependencies:** D-002 (xác định vai trò bộ file gốc vs docs). · **Implementation reference:** — · **Verification evidence:** — · **PO acceptance:** Chưa

## QA-001 — Ghi nhận baseline CI của `main_repos`

- **Type:** QA · **Priority:** P2 · **Status:** WAITING_PO
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
- **Business problem:** CI và build dùng Python 3.10; `Note/Note.md` hướng dẫn cài bằng Python 3.14 → máy dev và bản phát hành có thể chạy khác nhau.
- **Scope:** Chọn một phiên bản, ghi vào README/CI.
- **Acceptance criteria:** CI và hướng dẫn dev cùng phiên bản; CI xanh.
- **Dependencies:** — · **Implementation reference:** — · **Verification evidence:** — · **PO acceptance:** Chưa

---

## SEC-001 — Thu hồi GitHub token trong `config.json` (WAITING_PO)

- **Type:** Maintenance · **Priority:** P0 · **Status:** WAITING_PO
- **Business problem:** `CenterManager/runtime/Config/config.json` (vẫn còn trên cả `main` và `main_repos`) chứa bundle `ENC:v1:` giải mã được bằng khóa legacy trong `core/crypto.py`; bên trong có một GitHub PAT `ghp_…`.
- **Verification evidence:** Audit giải mã để xác minh, không in giá trị token. PO xác nhận 2026-11-04 token đã thu hồi; token mới dùng DPAPI và lưu ở repo riêng. Audit không tự kiểm tra token còn hiệu lực hay không (không dùng thông tin xác thực của người khác).
- **PO acceptance:** Chờ PO xác nhận đóng task.
- **Notes:** File này sẽ được gỡ khỏi Git trong TECH-002.

## SEC-002, SEC-003, SEC-004, BUG-001, QA-002 — CANCELLED

Chi tiết lý do ở bảng "đã đóng". Bằng chứng: kiểm tra mã trên `main_repos` @ `ac9e96d` (`core/crypto.py`, `database/seed.py`, `requirements.txt`, `.github/workflows/pytest-suite.yml`) và xác nhận của PO ngày 2026-11-04.
