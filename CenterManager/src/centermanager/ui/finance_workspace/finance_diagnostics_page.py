# -*- coding: utf-8 -*-
"""Read-only, bounded D01/D02 evidence in the Finance Workspace."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QDate, QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from centermanager.core.clock import get_clock
from centermanager.core.capabilities import Capability
from centermanager.core.current_user import CurrentUserContext, get_current_user
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.finance_diagnostics_service import FinanceDiagnosticsService
from centermanager.ui.design_system import SecondaryButton
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, TableDensity


class _Signals(QObject):
    finished = Signal(int, str, object, object)


class _ReadTask(QRunnable):
    """Carry only an authorization snapshot, never an ORM session, to a worker."""

    def __init__(self, generation, kind, service, principal, kwargs):
        super().__init__()
        self.generation = generation
        self.kind = kind
        self.service = service
        self.principal = principal
        self.kwargs = kwargs
        self.signals = _Signals()

    def run(self):
        try:
            with CurrentUserContext(self.principal):
                method = (self.service.get_findings if self.kind == "page"
                          else self.service.export_findings_csv)
                result = method(**self.kwargs)
            self.signals.finished.emit(self.generation, self.kind, result, None)
        except Exception as exc:
            # Do not include exception text: it may contain SQL parameters or PII.
            self.signals.finished.emit(self.generation, self.kind, None, type(exc).__name__)


def _principal_snapshot():
    user = get_current_user()
    if user is None:
        return None
    allowed = AuthorizationService.allows(user, Capability.FINANCE_VIEW)
    return SimpleNamespace(
        role=SimpleNamespace(name=getattr(getattr(user, "role", None), "name", None)),
        permissions=frozenset({"finance.view"} if allowed else ()),
        is_active=getattr(user, "is_active", True),
    )


class FinanceDiagnosticsPage(QWidget):
    """One live diagnostic run per filter/page, independent of accounting period."""

    PAGE_SIZE = 50

    def __init__(self, service: FinanceDiagnosticsService, parent=None):
        super().__init__(parent)
        self._service = service
        # The application pool outlives this page; closing a workspace must
        # not wait in QThreadPool's destructor for a large export to finish.
        self._pool = QThreadPool.globalInstance()
        self._generation = 0
        self._export_generation = 0
        self._tasks = set()
        self._findings = ()
        self._page = 1
        self._page_size = self.PAGE_SIZE
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])
        toolbar = QWidget(self)
        toolbar.setStyleSheet(
            f"background: {COLORS['surface_page']}; padding: {SPACING['sm']}px {SPACING['md']}px;"
            f"border-bottom: 1px solid {COLORS['border_default']};"
        )
        controls = QHBoxLayout(toolbar)
        controls.addWidget(QLabel("As of:"))
        self.as_of_edit = QDateEdit()
        self.as_of_edit.setCalendarPopup(True)
        self.as_of_edit.setDisplayFormat("dd/MM/yyyy")
        today = get_clock().today()
        self.as_of_edit.setDate(QDate(today.year, today.month, today.day))
        controls.addWidget(self.as_of_edit)
        controls.addWidget(QLabel("Rule:"))
        self.rule_combo = QComboBox()
        for label, value in (("All findings", None), ("D01", "D01"), ("D02", "D02")):
            self.rule_combo.addItem(label, value)
        controls.addWidget(self.rule_combo)
        self.refresh_btn = SecondaryButton("Refresh")
        controls.addWidget(self.refresh_btn)
        self.export_btn = SecondaryButton("Export CSV")
        controls.addWidget(self.export_btn)
        controls.addStretch()
        layout.addWidget(toolbar)

        self.summary_label = QLabel("Total: —  ·  D01: —  ·  D02: —")
        self.metadata_label = QLabel("As of: —  ·  Detected: —  ·  Source: —")
        self.note_label = QLabel("Observed Income amounts are evidence, not confirmed losses. Live diagnostic run.")
        for label in (self.summary_label, self.metadata_label, self.note_label):
            layout.addWidget(label)

        columns = [
            {"key": "rule", "label": "Rule / priority"},
            {"key": "income", "label": "Income ID"},
            {"key": "student", "label": "Student ID"},
            {"key": "class", "label": "Class ID"},
            {"key": "enrollment", "label": "Enrollment ID"},
            {"key": "amount", "label": "Observed amount"},
            {"key": "payment_date", "label": "Payment date"},
            {"key": "evidence", "label": "Evidence"},
        ]
        self.data_table = DataTable(
            columns, page_size=self.PAGE_SIZE, density=TableDensity.COMPACT,
            empty_title="No findings", empty_message="No D01/D02 candidates for this filter and date.",
        )
        layout.addWidget(self.data_table)
        self.detail_label = QLabel("Select a finding to inspect its persisted IDs and review guidance.")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        self.export_status = QLabel("")
        layout.addWidget(self.export_status)

        self.refresh_btn.clicked.connect(self.refresh)
        self.export_btn.clicked.connect(self._choose_export)
        self.rule_combo.currentIndexChanged.connect(self._filters_changed)
        self.as_of_edit.dateChanged.connect(self._filters_changed)
        self.data_table.page_requested.connect(self._page_requested)
        self.data_table.row_double_clicked.connect(self._show_detail)

    def _scope(self):
        return {
            "as_of_date": self.as_of_edit.date().toPython(),
            "rule_id": self.rule_combo.currentData(),
        }

    def _start(self, kind, kwargs):
        principal = _principal_snapshot()
        if kind == "page":
            self._generation += 1
            generation = self._generation
            self._findings = ()
            self.detail_label.setText("Select a finding to inspect its persisted IDs and review guidance.")
            self.summary_label.setText("Total: —  ·  D01: —  ·  D02: —")
            self.metadata_label.setText("Loading diagnostics…")
            self.data_table.set_loading(True)
        else:
            self._export_generation += 1
            generation = self._export_generation
            self.export_btn.setEnabled(False)
            self.export_status.setText("Exporting…")
        task = _ReadTask(generation, kind, self._service, principal, kwargs)
        task.signals.finished.connect(self._finished)
        self._tasks.add(task)
        self._pool.start(task)

    def refresh(self, **_context):
        self._start("page", {**self._scope(), "page": self._page, "per_page": self._page_size})

    def _filters_changed(self, *_args):
        self._page = 1
        self.refresh()

    def _page_requested(self, page, page_size):
        self._page = page
        self._page_size = min(page_size, 100)
        self.refresh()

    @staticmethod
    def _id(value):
        return "—" if value is None else str(value)

    def _finished(self, generation, kind, result, error):
        # A previous filter/page may finish after a later one was requested.
        self._tasks = {task for task in self._tasks if not (
            task.generation == generation and task.kind == kind
        )}
        if kind == "page":
            if generation != self._generation:
                return
            user = get_current_user()
            if user is None or not AuthorizationService.allows(user, Capability.FINANCE_VIEW):
                error = "PermissionDeniedError"
            if error or result is None or result.state != "OK":
                self.metadata_label.setText("Diagnostics backend ERROR")
                self.data_table.set_error(
                    "The diagnostic read failed. No finding count is available.",
                    retry_callback=self.refresh,
                )
                return
            self._findings = result.findings
            count_d01 = result.counts_by_rule.get("D01", 0)
            count_d02 = result.counts_by_rule.get("D02", 0)
            self.summary_label.setText(
                f"Total: {result.total_count:,}  ·  D01: {count_d01:,}  ·  D02: {count_d02:,}"
            )
            self.metadata_label.setText(
                f"As of: {result.as_of_date.isoformat()}  ·  "
                f"Detected UTC: {result.detected_at.isoformat()}  ·  Source: {result.source_version}"
            )
            rows = [{
                "rule": f"{f.rule_id} / {f.severity}", "income": f.entity_id,
                "student": self._id(f.student_id), "class": self._id(f.class_id),
                "enrollment": self._id(f.enrollment_id), "amount": str(f.observed_amount),
                "payment_date": f.payment_date.isoformat(), "evidence": f.evidence,
            } for f in result.findings]
            self.data_table.set_server_data(rows, result.total_count, result.page, result.per_page)
        else:
            if generation != self._export_generation:
                return
            self.export_btn.setEnabled(True)
            user = get_current_user()
            if user is None or not AuthorizationService.allows(user, Capability.FINANCE_VIEW):
                error = "PermissionDeniedError"
            if error or result is None or result.state == "ERROR":
                self.export_status.setText("Export ERROR: no file was created.")
            elif result.state == "LIMIT_EXCEEDED":
                self.export_status.setText(
                    f"Export LIMIT_EXCEEDED: {result.total_count:,} findings exceed 10,000. "
                    "Narrow the rule or as-of date. No file was created."
                )
            elif result.state == "OK" and result.csv_text is not None:
                try:
                    self._write_csv(self._export_path, result.csv_text)
                except OSError:
                    self.export_status.setText("Export ERROR: unable to save the CSV.")
                else:
                    self.export_status.setText(f"Export success: {result.total_count:,} findings saved.")
            else:
                self.export_status.setText("Export ERROR: no file was created.")

    def _show_detail(self, row):
        if not 0 <= row < len(self._findings):
            return
        f = self._findings[row]
        self.detail_label.setText(
            f"{f.rule_id} / {f.severity} · Income ID: {f.entity_id} · "
            f"Student ID: {self._id(f.student_id)} · Class ID: {self._id(f.class_id)} · "
            f"Enrollment ID: {self._id(f.enrollment_id)} · "
            f"Linked Student/Class IDs: {self._id(f.linked_student_id)}/{self._id(f.linked_class_id)} · "
            f"Canonical Enrollment ID: {self._id(f.canonical_enrollment_id)} · "
            f"Candidate Enrollments: {self._id(f.candidate_count)}\n"
            f"Evidence: {f.evidence}\nReview: {f.review_guidance}\n"
            f"Possible false positive: {f.false_positive_note}\n"
            f"As of: {f.as_of_date.isoformat()} · Detected UTC: {f.detected_at.isoformat()} · "
            f"Source: {f.source_version}"
        )

    def _choose_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Finance Diagnostics", "finance_diagnostics.csv", "CSV files (*.csv)",
        )
        if not path:
            return
        self._export_path = Path(path if path.lower().endswith(".csv") else path + ".csv")
        self._start("export", {**self._scope(), "max_rows": 10000})

    @staticmethod
    def _write_csv(path: Path, csv_text: str):
        """Only publish a complete BOM-encoded file after a successful result."""
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="",
                                             dir=path.parent, prefix=".finance-diagnostics-",
                                             suffix=".tmp", delete=False) as stream:
                temp_path = Path(stream.name)
                stream.write(csv_text)
            os.replace(temp_path, path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
