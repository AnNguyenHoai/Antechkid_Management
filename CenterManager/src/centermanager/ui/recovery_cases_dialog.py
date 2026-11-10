"""RV-04 privacy-aware, post-login Recovery Case review UI.

The window may be opened only after normal startup and login have completed.
Case status is local evidence metadata, never a grant of WRITE authority.
"""
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QMessageBox, QFileDialog,
)

from centermanager.platform.recovery_case_registry import RecoveryCaseRegistry
from centermanager.platform.write_recovery import WriteRecoveryJournal
from centermanager.platform.recovery_change_classification import classify_case


def _summary(case):
    """Only authenticated, non-sensitive metadata. Never read SQLCipher rows."""
    assessment = classify_case(case)
    return {
        "case_id": case["case_id"],
        "status": case["status"],
        "created_at_utc": case.get("created_at_utc"),
        "reviewed_at_utc": case.get("reviewed_at_utc"),
        "publication": case.get("publication", "UNVERIFIED"),
        "change_log_coverage": case.get("change_log_coverage", "UNKNOWN"),
        "recovery_classification": assessment.classification,
        "recovery_reason_code": assessment.reason_code,
        "business_mutation_count": assessment.business_mutation_count,
        "base_main_oid": case.get("base_main_oid"),
        "observed_main_oid": case.get("observed_main_oid"),
        "note": (
            assessment.message + " "
            "Cần đối chiếu dữ liệu hiện tại trước khi nhập lại, "
            "đặc biệt các khoản thu, chi và công nợ."
        ),
    }


class RecoveryCasesDialog(QDialog):
    def __init__(self, parent=None, *, pending_only=False, registry=None, provider=None, permission_checker=None):
        super().__init__(parent)
        self._registry = registry or RecoveryCaseRegistry(WriteRecoveryJournal())
        self._pending_only = pending_only
        self._provider = provider
        self._permission_checker = permission_checker
        self.setWindowTitle("Recovery Case — Kiểm tra dữ liệu")
        self.setMinimumSize(650, 410)
        layout = QVBoxLayout(self)
        description = QLabel(
            "Các thay đổi được lưu trong bản recovery để đối chiếu thủ công. "
            "Danh sách này KHÔNG xác nhận thay đổi đã mất hay chưa có trên MAIN. "
            "Kiểm tra giao dịch thu/chi và công nợ trước khi nhập lại để tránh trùng."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self._list = QListWidget(self)
        layout.addWidget(self._list)
        self._details = QLabel(self)
        self._details.setWordWrap(True)
        self._details.setTextInteractionFlags(self._details.textInteractionFlags())
        layout.addWidget(self._details)

        actions = QHBoxLayout()
        self._review = QPushButton("Đã kiểm tra", self)
        self._review.clicked.connect(self._mark_reviewed)
        actions.addWidget(self._review)
        export = QPushButton("Xuất tóm tắt", self)
        export.clicked.connect(self._export)
        actions.addWidget(export)
        compare_button = QPushButton("Đối chiếu thu/chi với MAIN", self)
        compare_button.setEnabled(
            self._provider is not None
            and callable(self._permission_checker)
            and bool(self._permission_checker())
        )
        compare_button.clicked.connect(self._compare_finance)
        actions.addWidget(compare_button)
        skip = QPushButton("Skip / Để lần sau", self)
        skip.clicked.connect(self.reject)
        actions.addWidget(skip)
        layout.addLayout(actions)
        self._list.currentRowChanged.connect(self._update_selection)
        self._cases = []
        self._refresh()

    def _refresh(self):
        # Fail closed on unreadable evidence rather than presenting an empty list.
        cases = self._registry.list_cases()
        self._cases = [case for case in cases
                       if not self._pending_only or case["status"] == "PENDING_REVIEW"]
        self._list.clear()
        for case in self._cases:
            label = "Chưa kiểm tra" if case["status"] == "PENDING_REVIEW" else "Đã kiểm tra"
            self._list.addItem(
                f"{label}  |  {case.get('created_at_utc', '')[:10]}  |  "
                f"{case['case_id'][:12]}"
            )
        if self._cases:
            self._list.setCurrentRow(0)
        else:
            self._details.setText("Không có Recovery Case trong danh sách.")
            self._review.setEnabled(False)

    def _selected(self):
        index = self._list.currentRow()
        return self._cases[index] if 0 <= index < len(self._cases) else None

    def _update_selection(self, _row):
        case = self._selected()
        self._review.setEnabled(
            bool(case and case["status"] == "PENDING_REVIEW")
        )
        if case is None:
            self._details.setText("Không có Recovery Case được chọn.")
            return
        self._details.setText(
            f"Mã case: {case['case_id'][:16]}…\n"
            f"Trạng thái công bố: {case.get('publication', 'UNVERIFIED')}\n"
            f"Mức độ đầy đủ Change Log: {case.get('change_log_coverage', 'UNKNOWN')}\n"
            f"Phân loại: {classify_case(case).classification}\n"
            f"Lý do: {classify_case(case).message}\n"
            "Danh sách thao tác có thể không đầy đủ. "
            "Không suy đoán các khoản đã mất; liên hệ hỗ trợ kỹ thuật để kiểm tra backup."
        )

    def _mark_reviewed(self):
        case = self._selected()
        if not case or case["status"] != "PENDING_REVIEW":
            return
        confirmed = QMessageBox.question(
            self, "Xác nhận đã kiểm tra",
            "Anh/chị đã kiểm tra bản recovery và đối chiếu với dữ liệu hiện tại?\n"
            "Đánh dấu chỉ tắt nhắc nhở cho case này, KHÔNG nhập lại dữ liệu, "
            "không xóa backup và không xác nhận khoản nào đã mất.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            self._registry.mark_reviewed(case["case_id"])
            self._refresh()
        except Exception:
            QMessageBox.warning(
                self, "Không thể xác nhận",
                "Không xác minh/ghi được Recovery Case. Không đánh dấu đã kiểm tra. "
                "Hãy giữ nguyên dữ liệu recovery và liên hệ hỗ trợ kỹ thuật."
            )

    def _compare_finance(self):
        """On-demand privileged comparison, never part of startup or login."""
        case = self._selected()
        if not case or not callable(self._permission_checker) or not self._permission_checker():
            QMessageBox.warning(self, "Từ chối truy cập", "Cần quyền finance.view để đối chiếu dữ liệu.")
            return
        if self._provider is None:
            QMessageBox.warning(self, "Recovery", "Không có kết nối Git MAIN để kiểm chứng.")
            return
        confirmed = QMessageBox.question(
            self, "Xuất dữ liệu tài chính",
            "Báo cáo có số tiền và dữ liệu giao dịch nhạy cảm. "
            "Chỉ lưu ở vị trí an toàn, không gửi công khai. "
            "Báo cáo KHÔNG tự xác nhận khoản tiền nào đã mất. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất đối chiếu thu/chi", "recovery-finance-compare.json",
            "JSON (*.json)"
        )
        if not path:
            return
        try:
            from centermanager.platform.recovery_finance_compare import (
                compare_verified_case, render_report_json, write_secure_report,
            )
            report = compare_verified_case(
                self._registry, case["case_id"],
                provider=self._provider,
                can_view_finance=bool(self._permission_checker()),
            )
            write_secure_report(Path(path), render_report_json(report))
            QMessageBox.information(
                self, "Recovery",
                "Đã xuất kết quả đối chiếu. NOT_FOUND không có nghĩa là giao dịch bị mất; "
                "cần kiểm tra công nợ/ví trước khi nhập lại."
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Verified finance comparison unavailable")
            QMessageBox.warning(
                self, "Đối chiếu chưa khả dụng",
                "Không xác minh được backup, khóa SQLCipher hoặc MAIN hiện tại. "
                "Không xuất dữ liệu suy đoán; các bản backup được giữ nguyên."
            )

    def _export(self):
        if not self._cases:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất báo cáo Recovery Case", "recovery-case-summary.json",
            "JSON (*.json)"
        )
        if not path:
            return
        try:
            # Re-authenticate all entries immediately before exporting.
            cases = self._registry.list_cases()
            allowed = {x["case_id"] for x in self._cases}
            summaries = [_summary(case) for case in cases if case["case_id"] in allowed]
            Path(path).write_text(
                json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            QMessageBox.warning(
                self, "Xuất báo cáo thất bại",
                "Không thể xác minh case hoặc lưu tệp. Chưa xuất báo cáo."
            )


def show_pending_recovery_reminder(parent=None):
    registry = RecoveryCaseRegistry(WriteRecoveryJournal())
    if not registry.pending_cases():
        return
    dialog = RecoveryCasesDialog(parent, pending_only=True, registry=registry)
    dialog.exec()  # Closing/Skip never calls mark_reviewed.
