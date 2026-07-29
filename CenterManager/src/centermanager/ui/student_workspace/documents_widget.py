# -*- coding: utf-8 -*-
"""
DocumentsWidget - display and manage student documents.
"""
import os
import sys
import subprocess
from typing import Optional, List
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QDialogButtonBox
)

from centermanager.models.document import Document
from centermanager.services.student_document_service import StudentDocumentService
from centermanager.core.paths import get_paths
from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS


class DocumentCard(QFrame):
    def __init__(self, doc: Document, parent: Optional[QWidget] = None) -> None:
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
            QFrame:hover {
                background: #f5f5f5;
            }
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
        while parent and not isinstance(parent, DocumentsWidget):
            parent = parent.parent()
        if parent and hasattr(parent, '_delete_document'):
            parent._delete_document(self._doc.id)

    def mouseDoubleClickEvent(self, event) -> None:
        from centermanager.core.paths import get_paths
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


class DocumentsWidget(QWidget):
    document_changed = Signal()

    def __init__(self, doc_service: StudentDocumentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = doc_service
        self._student_id: Optional[int] = None
        self._documents: List[Document] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        header = QHBoxLayout()
        header.addStretch()
        self.upload_btn = QPushButton("+ Upload")
        self.upload_btn.setFixedHeight(32)
        self.upload_btn.clicked.connect(self._on_upload)
        header.addWidget(self.upload_btn)
        layout.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, SPACING['xs'], 0, 0)
        self.container_layout.setSpacing(SPACING['xs'])
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def set_student(self, student_id: int) -> None:
        self._student_id = student_id
        self._load_documents()

    def _load_documents(self) -> None:
        if self._student_id is None:
            return
        try:
            self._documents = self._service.get_documents_for_student(self._student_id)
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
            card = DocumentCard(doc)
            self.container_layout.addWidget(card)
        self.container_layout.addStretch()

    def _clear_container(self) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_upload(self) -> None:
        if self._student_id is None:
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if not file_path:
            return
        dialog = UploadDocumentDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            doc_type, description = dialog.get_data()
            try:
                from centermanager.services.student_service import StudentService
                from centermanager.database.engine import create_production_engine
                from sqlalchemy.orm import sessionmaker
                engine = create_production_engine()
                session_factory = sessionmaker(bind=engine)
                student_service = StudentService(session_factory)
                student = student_service.get_student(self._student_id)
                self._service.upload_document(
                    student_id=self._student_id,
                    student_code=student.student_code,
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
            self,
            "Confirm Delete",
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


class UploadDocumentDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Upload Document")
        self.setMinimumWidth(350)
        self.setModal(True)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.type_edit = QLineEdit()
        self.type_edit.setPlaceholderText("e.g., Enrollment Form")
        form.addRow("Document Type", self.type_edit)

        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional description")
        form.addRow("Description", self.desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return self.type_edit.text().strip() or None, self.desc_edit.text().strip() or None