# -*- coding: utf-8 -*-
"""
TeacherDocumentsWidget - display and manage teacher documents.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDialogButtonBox
)

from centermanager.models.teacher_document import TeacherDocument
from centermanager.services.teacher_document_service import TeacherDocumentService
from centermanager.services.teacher_service import TeacherService
from centermanager.core.paths import get_paths
from centermanager.ui.design_system.tokens import COLORS, SPACING


class TeacherDocumentCard(QFrame):
    def __init__(self, doc: TeacherDocument, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._doc = doc
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: white;
                padding: 6px 10px;
                margin: 2px 0;
            }
            QFrame:hover { background: #f5f5f5; }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        header = QHBoxLayout()
        name_label = QLabel(doc.file_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(name_label)

        if doc.document_type:
            type_label = QLabel(doc.document_type)
            type_label.setStyleSheet("color: #888; font-size: 12px;")
            header.addWidget(type_label)

        header.addStretch()
        time_label = QLabel(doc.created_at.strftime("%d/%m/%Y"))
        time_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(time_label)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setStyleSheet("background: transparent; border: none; color: red; font-size: 14px;")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._delete)
        header.addWidget(self.delete_btn)
        layout.addLayout(header)

        if doc.description:
            desc = QLabel(doc.description)
            desc.setWordWrap(True)
            desc.setStyleSheet("font-size: 12px; color: #555;")
            layout.addWidget(desc)

    def _delete(self) -> None:
        parent = self.parent()
        while parent and not isinstance(parent, TeacherDocumentsWidget):
            parent = parent.parent()
        if parent and hasattr(parent, '_delete_document'):
            parent._delete_document(self._doc.id)

    def mouseDoubleClickEvent(self, event) -> None:
        file_path = get_paths().attachment_dir / self._doc.file_path
        if file_path.exists():
            try:
                if sys.platform == 'win32':
                    os.startfile(str(file_path))
                elif sys.platform == 'darwin':
                    subprocess.run(['open', str(file_path)])
                else:
                    subprocess.run(['xdg-open', str(file_path)])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open file: {e}")
        else:
            QMessageBox.warning(self, "File not found", f"File {self._doc.file_name} not found.")


class TeacherDocumentsWidget(QWidget):
    document_changed = Signal()

    def __init__(self, doc_service: TeacherDocumentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = doc_service
        self._teacher_id: Optional[int] = None
        self._documents: List[TeacherDocument] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        header = QHBoxLayout()
        title = QLabel("📎 Documents")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        self.upload_btn = QPushButton("+ Upload")
        self.upload_btn.setFixedHeight(32)
        self.upload_btn.clicked.connect(self._on_upload)
        header.addWidget(self.upload_btn)
        layout.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {COLORS['border_light']}; height: 1px;")
        layout.addWidget(line)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, SPACING['xs'], 0, 0)
        self.container_layout.setSpacing(SPACING['xs'])
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def set_teacher(self, teacher_id: int) -> None:
        self._teacher_id = teacher_id
        self._load_documents()

    def _load_documents(self) -> None:
        if self._teacher_id is None:
            return
        try:
            self._documents = self._service.get_documents_for_teacher(self._teacher_id)
        except Exception:
            self._documents = []
        self._update_ui()

    def _update_ui(self) -> None:
        self._clear_container()
        if not self._documents:
            empty = QLabel("No documents yet.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #999; padding: 20px;")
            self.container_layout.addWidget(empty)
            self.container_layout.addStretch()
            return

        for doc in self._documents:
            card = TeacherDocumentCard(doc)
            self.container_layout.addWidget(card)
        self.container_layout.addStretch()

    def _clear_container(self) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_upload(self) -> None:
        if self._teacher_id is None:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Document",
            "",
            "All Files (*.*)"
        )
        if not file_path:
            return

        # Ask for document type and description
        dialog = QDialog(self)
        dialog.setWindowTitle("Upload Document")
        dialog.setMinimumWidth(350)
        dialog.setModal(True)

        form = QFormLayout(dialog)
        type_edit = QLineEdit()
        type_edit.setPlaceholderText("e.g., CV, Contract")
        form.addRow("Document Type", type_edit)
        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("Optional description")
        form.addRow("Description", desc_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        doc_type = type_edit.text().strip() or None
        description = desc_edit.text().strip() or None

        try:
            # Get teacher code
            from centermanager.database.engine import create_production_engine
            from sqlalchemy.orm import sessionmaker
            from centermanager.repositories.teacher_repository import TeacherRepository

            engine = create_production_engine()
            session_factory = sessionmaker(bind=engine)
            with session_factory() as session:
                repo = TeacherRepository(session)
                teacher = repo.get_by_id(self._teacher_id)
                if teacher is None:
                    raise ValueError("Teacher not found")
                teacher_code = teacher.teacher_code

            self._service.upload_document(
                teacher_id=self._teacher_id,
                teacher_code=teacher_code,
                source_path=Path(file_path),
                file_name=Path(file_path).name,
                document_type=doc_type,
                description=description,
            )
            self._load_documents()
            self.document_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Upload Error", str(e))

    def _delete_document(self, document_id: int) -> None:
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete this document?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.delete_document(document_id)
                self._load_documents()
                self.document_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))