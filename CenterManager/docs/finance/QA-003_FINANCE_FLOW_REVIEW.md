# QA-003 — Rà soát luồng dữ liệu Finance Workspace

- **Ngày:** 2026-11-04 · **Issue:** #564 · **Commit rà soát:** `main_repos` @ `7940d11`
- **Phương pháp:** đọc code (service → repository → UI), đối chiếu `FINANCE_WALLET_V2_DOMAIN_SPEC.md`, kiểm tra dữ liệu **giả** trong snapshot test cũ (`runtime/snapshots`, PO xác nhận là dữ liệu test). Không truy cập DB production. Không sửa code.
- **Phân loại:** **XN** = đã xác nhận bằng code (và dữ liệu test nếu có) · **GT** = giả thuyết mạnh, cần PO/dữ liệu thật kiểm chứng.

## 1. Luồng dữ liệu hiện tại (tóm tắt)

```
ExpenseFormDialog ──► ExpenseService.create/update ──► expenses (status, payment_method, payment_date, finance_period_id)
IncomeFormDialog  ──► IncomeService                ──► incomes  (amount có dấu, finance_period_start)
Hoàn học phí      ──► TuitionAdjustmentService.refund ──► incomes (amount ÂM, payment_period="REFUND")
                                   │ FinanceDataChanged
                                   ▼
FinanceWorkspaceShell._refresh_all_period_pages(period context dùng chung)
   ├─ Dashboard  : FinanceDashboardService.get_dashboard_data
   │     Thu  = Σ incomes ACTIVE (có dấu) theo finance_period_start + ngày ≤ hôm nay
   │     Chi  = Σ expenses status ∈ {"Completed","Paid"}, ngày trong kỳ ≤ hôm nay
   ├─ Expense list: list/sum_expenses (mặc định MỌI trạng thái, đến hết kỳ)
   ├─ Outstanding, Settlement (WalletService: cùng tập "realized" như Dashboard)
```

## 2. Các điểm bất thường

### F1 — [XN · Cao] Chi phí cũ lưu trạng thái tiếng Việt không được tính là "tiền ra" — *nhiều khả năng là nguyên nhân chính*

- `ExpenseRepository.REALIZED_STATUSES = ("Completed", "Paid")` (`repositories/expense_repository.py:18`). Dashboard, Cash/Bank Out, Net cash flow, Settlement và Wallet đều chỉ cộng hai giá trị này.
- Dữ liệu cũ chứa nhãn hiển thị thay vì giá trị chuẩn: dữ liệu test có các dòng `status = 'ĐÃ HOÀN TRẢ'` và `'CHƯA HOÀN TRẢ'`. Không có migration nào chuẩn hóa các giá trị này (đã tìm trong `migrations/versions/`).
- Hệ quả: dòng `ĐÃ HOÀN TRẢ` (đã chi thật) **bị loại khỏi tiền ra**. Ví dụ trong dữ liệu test: 3 dòng chi, tổng 12.050.000 VND, Dashboard tính **0 VND** tiền ra.
- Bộ lọc "ĐÃ HOÀN TRẢ" ở danh sách Chi gửi giá trị `Completed` nên cũng **không hiện** các dòng cũ; chỉ thấy chúng khi chọn "Tất cả".
- Cần kiểm chứng trên DB thật (người có quyền, qua công cụ được phép):
  `SELECT status, COUNT(*), SUM(amount) FROM expenses WHERE deleted_at IS NULL GROUP BY status;`
  Nếu có giá trị khác `Completed` / `Pending` / `Paid` → F1 đang ảnh hưởng số liệu thật.

### F2 — [XN · Cao] Tổng "Chi" ở danh sách và "Paid Expense" ở Dashboard dùng hai định nghĩa khác nhau

| | Danh sách Chi (mặc định) | Dashboard "Paid Expense" |
|---|---|---|
| Trạng thái | Tất cả (Pending + Completed + giá trị cũ) | Chỉ `Completed`/`Paid` |
| Khoảng ngày | Đầu kỳ → **cuối kỳ** | Đầu kỳ → **hôm nay** |

Không có dòng giải thích nào trên trang danh sách → người dùng thấy hai con số "tiền ra" khác nhau. (`ui/finance_workspace/expense_list_page.py:245`, `services/finance_dashboard_service.py:326`.)

### F3 — [XN · Cao, cần quyết định nghiệp vụ] Hoàn học phí không xuất hiện là "tiền ra"

- Hoàn tiền được ghi thành Income **âm** (`services/tuition_adjustment_service.py:223`, `amount=-value`).
- Dashboard cộng thẳng vào "Income Selected Period" → doanh thu bị giảm, còn "Paid Expense" và cột "Cash Out/Bank Out" **không có** khoản tiền đã trả lại phụ huynh.
- Số dư ví (thu − chi) vẫn đúng; sai ở cách trình bày dòng tiền vào/ra. Spec chưa định nghĩa cách hiển thị hoàn tiền trên Dashboard.

### F4 — [XN · Trung bình, nghiệp vụ] Nhãn "ĐÃ / CHƯA HOÀN TRẢ" không khớp ý nghĩa "đã chi / chưa chi"

- Form Chi chỉ có hai trạng thái: `ĐÃ HOÀN TRẢ → Completed (tính tiền ra)`, `CHƯA HOÀN TRẢ → Pending (không tính)`. "Hoàn trả" nghĩa là *đã trả lại cho người ứng tiền*, không phải *trung tâm đã chi*.
- Dữ liệu test có dòng `TÀI KHOẢN CÔNG TY` + `CHƯA HOÀN TRẢ` 10.000.000 VND: tiền đã ra từ tài khoản công ty nhưng không được tính là tiền ra.
- Alias ví: `TÀI KHOẢN CÁ NHÂN` được map sang ví **Cash** (`core/wallet.py:28`) — đây là giả định, chưa có quy tắc nghiệp vụ xác nhận.
- Dashboard gọi là "Paid Expense", danh sách gọi là "ĐÃ HOÀN TRẢ" → cùng một khái niệm, hai tên.

### F5 — [XN · Thấp] Bảng "Recent Expense" trên Dashboard có cả dòng Pending

KPI chỉ tính Completed nhưng bảng ngay bên dưới liệt kê cả Pending (và giá trị cũ) (`finance_dashboard_service.py:199`, không truyền `realized_only`). Bảng Thu thì chỉ có ACTIVE → hai bảng không cùng quy tắc.

### F6 — [XN · Trung bình] Kỳ tài chính của Thu và Chi được xác định khác nhau

- Thu lọc theo cột lưu sẵn `finance_period_start == đầu kỳ` (`repositories/income_repository.py:213`).
- Chi lọc theo `payment_date >= đầu kỳ`, **bỏ qua** `finance_period_id` (`repositories/expense_repository.py:69`).
- Nếu cấu hình kỳ bị sửa sau khi đã có dữ liệu, Thu và Chi của cùng một kỳ sẽ lệch nhau (liên quan F-21 trong `FINANCE_CURRENT_STATE_AUDIT.md`). Spec R2 yêu cầu dùng định danh kỳ như một thực thể.

### F7 — [XN · Thấp] Dashboard dùng đồng hồ hệ thống thay vì đồng hồ nghiệp vụ

`FinanceDashboardService._get_today_date()` dùng `date.today()`; Shell, form và kiểm tra ngày tương lai dùng `get_clock().today()`. Khi ngày nghiệp vụ được ghi đè (UAT/test), "hôm nay" của Dashboard khác phần còn lại.

### F8 — [GT · Trung bình] Giá trị mặc định ở tầng DB là `Pending`

`models/expense.py:20` đặt `default="Pending"`. Bất kỳ đường ghi nào bỏ qua `ExpenseService` (import, script, dữ liệu cũ) sẽ tạo chi phí **không tính tiền ra**. Chưa tìm thấy đường ghi như vậy trong code hiện tại; cần xác nhận khi xử lý F1.

### F9 — [XN · Thấp] Một alias ví lạ làm toàn bộ Dashboard báo "Error"

`WalletService.aggregate_wallet_rows` dừng hẳn khi gặp `payment_method` không nhận ra (thiết kế fail-closed để an toàn). Kết hợp F1 (dữ liệu cũ), một dòng sai có thể làm mất toàn bộ Dashboard thay vì chỉ cảnh báo. Không thay đổi được nếu không có quyết định của PO (an toàn vs hiển thị).

## 3. Kết luận về "tiền ra sai"

Khả năng cao nhất là **F1 + F4** (chi phí đã chi nhưng mang trạng thái cũ hoặc "CHƯA HOÀN TRẢ" nên bị loại), cộng với **F2** (người dùng so với tổng ở danh sách Chi) và **F3** (hoàn học phí không hiện là tiền ra). Cần chạy truy vấn ở F1 trên DB thật để khẳng định.

## 4. Đề xuất task (chờ PO duyệt)

| Đề xuất | Nội dung | Ưu tiên | Cần PO quyết định |
|---|---|---|---|
| BUG-002 | Migration chuẩn hóa `expenses.status` cũ (`ĐÃ HOÀN TRẢ`→`Completed`, `CHƯA HOÀN TRẢ`→`Pending`) + chặn giá trị ngoài tập cho phép | P1 | Có — với dòng `TÀI KHOẢN CÔNG TY` + `CHƯA HOÀN TRẢ` giữ Pending hay chuyển Completed? |
| FEAT-001 | Định nghĩa lại trạng thái Chi: "Đã chi" / "Kế hoạch – chưa chi"; tách "đã hoàn trả cho người ứng" thành trường riêng nếu cần | P1 | Có — mô hình nghiệp vụ |
| BUG-003 | Danh sách Chi hiển thị riêng "Đã chi (tính dòng tiền)" và "Chưa chi"; thống nhất khoảng ngày với Dashboard | P2 | Không |
| FEAT-002 | Hiển thị hoàn học phí như dòng tiền ra (KPI/biểu đồ) mà không đổi cách lưu sổ | P2 | Có — cách trình bày |
| BUG-004 | Chi lọc kỳ theo `finance_period_id` như spec R2 | P2 | Không |
| BUG-005 | Dashboard dùng `get_clock()`; bảng Recent Expense theo cùng quy tắc với KPI | P3 | Không |
