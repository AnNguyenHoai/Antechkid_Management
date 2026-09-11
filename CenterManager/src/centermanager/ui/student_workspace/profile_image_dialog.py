# -*- coding: utf-8 -*-
"""Dialog for uploading, previewing, and removing student profile image."""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QWidget, QFrame
)

from centermanager.services.student_service import StudentService
from centermanager.core.paths import get_paths

logger = logging.getLogger(__name__)


class ProfileImageDialog(QDialog):
    def __init__(
        self,
        student_service: StudentService,
        student_id: int,
        current_image_path: Optional[str],
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = student_service
        self._student_id = student_id
        self._current_image_path = current_image_path
        self._new_image_path: Optional[Path] = None

        self.setWindowTitle("Profile Image")
        self.setMinimumSize(400, 500)
        self.setModal(True)

        self._setup_ui()
        self._load_image()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Preview
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(200, 200)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #f5f5f5;
            }
        """)
        self.image_label.setScaledContents(True)
        layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.upload_btn = QPushButton("📷 Upload")
        self.upload_btn.clicked.connect(self._on_upload)
        btn_layout.addWidget(self.upload_btn)

        self.remove_btn = QPushButton("🗑️ Remove")
        self.remove_btn.clicked.connect(self._on_remove)
        btn_layout.addWidget(self.remove_btn)

        btn_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _load_image(self) -> None:
        """Load current image or show placeholder."""
        if self._current_image_path:
            full_path = get_paths().attachment_dir / self._current_image_path
            if full_path.exists():
                pixmap = QPixmap(str(full_path))
                if not pixmap.isNull():
                    self.image_label.setPixmap(pixmap.scaled(
                        200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))
                    return
        # Fallback: placeholder
        self.image_label.setText("📷\nNo Image")
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #f5f5f5;
                font-size: 24px;
                color: #999;
            }
        """)

    def _on_upload(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Profile Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.gif *.bmp)"
        )
        if not file_path:
            return

        try:
            # Validate image
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", "Invalid image file.")
                return
            if pixmap.width() < 100 or pixmap.height() < 100:
                QMessageBox.warning(self, "Error", "Image too small. Minimum 100x100.")
                return

            self._new_image_path = Path(file_path)
            self._service.set_profile_image(self._student_id, self._new_image_path)
            self._current_image_path = f"{self._service.get_student(self._student_id).profile_image_path}"
            self._load_image()
            QMessageBox.information(self, "Success", "Profile image updated.")
        except Exception as e:
            logger.exception("Failed to upload image")
            QMessageBox.critical(self, "Error", f"Failed to upload image: {str(e)}")

    def _on_remove(self) -> None:
        if not self._current_image_path:
            QMessageBox.information(self, "Info", "No image to remove.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            "Remove profile image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.set_profile_image(self._student_id, None)
                self._current_image_path = None
                self._load_image()
                QMessageBox.information(self, "Success", "Profile image removed.")
            except Exception as e:
                logger.exception("Failed to remove image")
                QMessageBox.critical(self, "Error", f"Failed to remove image: {str(e)}")