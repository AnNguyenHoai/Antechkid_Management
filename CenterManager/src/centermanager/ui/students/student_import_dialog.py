# -*- coding: utf-8 -*-
"""
StudentImportDialog - dialog for importing students.
"""
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTextEdit, QProgressBar, QMessageBox
)

from centermanager.services.student_import_service import StudentImportService

logger = logging.getLogger(__name__)


class StudentImportDialog(QDialog):
    """Dialog for importing students from Excel."""

    def __init__(
        self,
        import_service: StudentImportService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = import_service
        self.setWindowTitle("Import Students")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        self._file_path: Optional[Path] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # File selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #666;")
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.browse_btn)
        layout.addLayout(file_layout)

        # Progress bar (for future)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Log area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Import log will appear here...")
        layout.addWidget(self.log_text)

        # Buttons
        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("Import")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._import)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _browse(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Excel File",
            "",
            "Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self._file_path = Path(file_path)
            self.file_label.setText(self._file_path.name)
            self.import_btn.setEnabled(True)
            self.log_text.clear()
            self.log_text.append(f"Selected: {self._file_path}")

    def _import(self) -> None:
        if not self._file_path or not self._file_path.exists():
            QMessageBox.warning(self, "Error", "File does not exist.")
            return

        self.import_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indeterminate

        try:
            success, errors, error_list = self._service.import_from_excel(self._file_path)
            self.log_text.clear()
            self.log_text.append(f"Import completed: {success} succeeded, {errors} failed.")
            if error_list:
                self.log_text.append("\n--- Errors ---")
                for err in error_list:
                    self.log_text.append(f"• {err}")
            else:
                self.log_text.append("All records imported successfully.")
            QMessageBox.information(
                self,
                "Import Summary",
                f"Imported {success} students.\n{errors} errors."
            )
        except Exception as e:
            logger.exception("Import failed")
            QMessageBox.critical(self, "Error", f"Import failed: {str(e)}")
        finally:
            self.progress.setVisible(False)
            self.import_btn.setEnabled(True)