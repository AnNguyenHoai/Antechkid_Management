# -*- coding: utf-8 -*-
"""Optional accounting vouchers for Income/Expense (FEAT-004, PO decision D-009)."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QImage, QImageReader
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)

FILE_FILTER = "Chứng từ (*.pdf *.png *.jpg *.jpeg)"
MAX_IMAGE_EDGE = 1600
JPEG_QUALITY = 80
_SHRINK_THRESHOLD_BYTES = 1024 * 1024


def prepare_voucher_file(path: str) -> str:
    """Return a smaller copy of large photos; other files are returned as-is.

    Phone photos are typically 3-5 MB. Scaling to a 1600 px long edge at JPEG
    quality 80 keeps receipts legible at roughly 200-400 KB, which keeps the
    shared data repository small (QA-004). PDFs and small images are unchanged.
    """
    source = Path(path)
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return str(source)
    try:
        reader = QImageReader(str(source))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            return str(source)
        too_large = max(image.width(), image.height()) > MAX_IMAGE_EDGE
        if not too_large and source.stat().st_size <= _SHRINK_THRESHOLD_BYTES:
            return str(source)
        if too_large:
            image = image.scaled(
                MAX_IMAGE_EDGE, MAX_IMAGE_EDGE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        keep_png = image.hasAlphaChannel()
        suffix = ".png" if keep_png else ".jpg"
        target = Path(tempfile.mkdtemp(prefix="voucher_")) / f"{source.stem}{suffix}"
        if keep_png:
            ok = image.save(str(target), "PNG")
        else:
            ok = image.convertToFormat(QImage.Format.Format_RGB32).save(str(target), "JPG", JPEG_QUALITY)
        if not ok or target.stat().st_size >= source.stat().st_size:
            return str(source)
        return str(target)
    except Exception:
        logger.exception("Voucher image preparation failed; using original file")
        return str(source)


class VoucherAttachmentWidget(QGroupBox):
    """List/add/open/hide vouchers for one Income or Expense.

    ``entity_id is None`` (new record): selected files are kept as pending and
    uploaded by :meth:`commit_pending` after the record has been saved.
    """

    def __init__(
        self,
        attachment_service,
        entity_type: str,
        entity_id: Optional[int] = None,
        can_modify: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__("Chứng từ kế toán (tùy chọn)", parent)
        self._service = attachment_service
        self._entity_type = entity_type
        self._entity_id = entity_id
        self._can_modify = can_modify
        self._pending: List[tuple[str, str]] = []  # (prepared path, original name)
        self._attachments = []

        layout = QVBoxLayout(self)
        self.hint = QLabel("PDF, PNG, JPG · tối đa 5 MB/file · tối đa 5 file.", self)
        self.hint.setStyleSheet("color: #536479; font-size: 12px;")
        layout.addWidget(self.hint)
        self.list_widget = QListWidget(self)
        self.list_widget.setMaximumHeight(110)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._open_selected())
        layout.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        self.add_btn = QPushButton("Thêm chứng từ…", self)
        self.open_btn = QPushButton("Mở", self)
        self.remove_btn = QPushButton("Ẩn", self)
        for button in (self.add_btn, self.open_btn, self.remove_btn):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.add_btn.clicked.connect(self._choose_files)
        self.open_btn.clicked.connect(self._open_selected)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.reload()

    # ---- state -------------------------------------------------------------

    def _count(self) -> int:
        return len(self._attachments) + len(self._pending)

    def reload(self) -> None:
        self.list_widget.clear()
        self._attachments = []
        if self._entity_id is not None:
            try:
                self._attachments = list(self._service.list_attachments(self._entity_type, self._entity_id))
            except Exception as exc:
                logger.exception("Failed to load vouchers")
                self.hint.setText(f"Không tải được chứng từ: {exc}")
        for attachment in self._attachments:
            item = QListWidgetItem(f"{attachment.original_filename}  ({attachment.size_bytes / 1024:,.0f} KB)")
            item.setData(Qt.ItemDataRole.UserRole, ("saved", attachment))
            self.list_widget.addItem(item)
        for path, name in self._pending:
            item = QListWidgetItem(f"{name}  (chờ lưu)")
            item.setData(Qt.ItemDataRole.UserRole, ("pending", path))
            self.list_widget.addItem(item)
        self.add_btn.setEnabled(self._can_modify and self._count() < self._service.MAX_FILES_PER_RECORD)
        self.remove_btn.setEnabled(self._can_modify and self._count() > 0)
        self.open_btn.setEnabled(self._count() > 0)

    # ---- actions -----------------------------------------------------------

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn chứng từ", "", FILE_FILTER)
        if paths:
            self.add_files(paths)

    def add_files(self, paths) -> List[str]:
        """Validate and add files; returns user-facing error messages."""
        errors = []
        for path in paths:
            name = Path(path).name
            if self._count() >= self._service.MAX_FILES_PER_RECORD:
                errors.append(f"{name}: mỗi khoản tối đa 5 chứng từ.")
                continue
            prepared = prepare_voucher_file(path)
            try:
                self._service.inspect_file(prepared)
                if self._entity_id is None:
                    self._pending.append((prepared, name))
                else:
                    self._service.add_attachment(self._entity_type, self._entity_id, prepared, original_filename=name)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
            self.reload()
        if errors:
            QMessageBox.warning(self, "Chứng từ", "\n".join(errors))
        return errors

    def commit_pending(self, entity_id: int) -> List[str]:
        """Upload pending files after the record was saved."""
        self._entity_id = entity_id
        errors = []
        failed = []
        for path, name in list(self._pending):
            try:
                self._service.add_attachment(
                    self._entity_type, entity_id, path, original_filename=name
                )
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                failed.append((path, name))
        # FIN-04: never silently discard failed vouchers. A retry resumes
        # the original Income/Expense command using its stable submission key
        # and attempts only the remaining files.
        self._pending = failed
        self.reload()
        return errors

    def _selected(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _open_selected(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        kind, value = selected
        try:
            path = value if kind == "pending" else self._service.resolve_path(value)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as exc:
            QMessageBox.warning(self, "Chứng từ", str(exc))

    def _remove_selected(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        kind, value = selected
        if kind == "pending":
            self._pending = [(path, name) for path, name in self._pending if path != value]
            self.reload()
            return
        answer = QMessageBox.question(
            self, "Ẩn chứng từ",
            "Ẩn chứng từ này khỏi khoản? File vẫn được lưu trữ để đối soát.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.remove_attachment(value.id)
        except Exception as exc:
            QMessageBox.warning(self, "Chứng từ", str(exc))
        self.reload()


class VoucherAttachmentDialog(QDialog):
    """Stand-alone voucher manager (also for settled periods, D-009)."""

    def __init__(self, attachment_service, entity_type: str, entity_id: int,
                 title: str = "Chứng từ", can_modify: bool = True,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        self.widget = VoucherAttachmentWidget(
            attachment_service, entity_type, entity_id, can_modify=can_modify, parent=self
        )
        layout.addWidget(self.widget)
        close_btn = QPushButton("Đóng", self)
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        layout.addLayout(row)
