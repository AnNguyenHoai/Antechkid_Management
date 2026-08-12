# -*- coding: utf-8 -*-
"""
ProfileWidget - unified student profile display.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame, QSizePolicy
)

from centermanager.models.student import Student
from centermanager.ui.students.helpers import calculate_age, format_date_for_display
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.design_system.components import StatusBadge
from centermanager.core.paths import get_paths


class ProfileWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.clear()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['md'])

        # Header with image
        header = QHBoxLayout()
        header.setSpacing(SPACING['lg'])

        # Image label instead of Avatar
        self.image_label = QLabel()
        self.image_label.setFixedSize(64, 64)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ddd;
                border-radius: 32px;
                background: #f0f0f0;
            }
        """)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("📷")
        self.image_label.setScaledContents(True)
        header.addWidget(self.image_label)

        info = QVBoxLayout()
        info.setSpacing(SPACING['xs'])

        self.name_label = QLabel()
        self.name_label.setStyleSheet(f"""
            font-size: 22px;
            font-weight: 700;
            color: {COLORS['text_primary']};
        """)
        info.addWidget(self.name_label)

        code_status = QHBoxLayout()
        code_status.setSpacing(SPACING['sm'])
        self.code_label = QLabel()
        self.code_label.setStyleSheet(f"""
            font-size: 13px;
            color: {COLORS['text_muted']};
            font-weight: 500;
        """)
        code_status.addWidget(self.code_label)

        self.status_badge = StatusBadge("")
        code_status.addWidget(self.status_badge)
        code_status.addStretch()
        info.addLayout(code_status)

        header.addLayout(info)
        header.addStretch()
        layout.addLayout(header)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {COLORS['border_light']}; height: 1px;")
        layout.addWidget(line)

        # Details grid
        self.details_grid = QGridLayout()
        self.details_grid.setSpacing(SPACING['md'] + 4)
        self.details_grid.setContentsMargins(0, SPACING['sm'] + 4, 0, 0)
        self.details_grid.setColumnStretch(1, 1)
        self.details_grid.setColumnStretch(3, 1)
        layout.addLayout(self.details_grid)

    def set_student(self, student: Student, primary_parent_name: str = "", primary_parent_phone: str = "") -> None:
        self.clear()
        if not student:
            return

        # Set image
        self._update_image(student)

        self.name_label.setText(student.full_name)
        self.code_label.setText(student.student_code)
        self.status_badge.set_status(student.status or "")

        details = [
            ("Preferred Name", student.preferred_name or "-"),
            ("Date of Birth", format_date_for_display(student.date_of_birth)),
            ("Age", str(calculate_age(student.date_of_birth)) if student.date_of_birth else "-"),
            ("Gender", student.gender or "-"),
            ("Current Level", student.current_level or "-"),
            ("Enrollment Date", format_date_for_display(student.enrollment_date) or "-"),
            ("Primary Parent", primary_parent_name if primary_parent_name else "-"),
            ("Contact", primary_parent_phone if primary_parent_phone else "-"),
        ]

        row = 0
        col = 0
        for label, value in details:
            lbl = QLabel(label + ":")
            lbl.setStyleSheet(f"""
                font-size: 11px;
                color: {COLORS['text_muted']};
                font-weight: 500;
                letter-spacing: 0.2px;
            """)
            self.details_grid.addWidget(lbl, row, col * 2, 1, 1)

            val = QLabel(value)
            val.setStyleSheet(f"""
                font-size: 13px;
                color: {COLORS['text_primary']};
                font-weight: 500;
            """)
            val.setWordWrap(True)
            self.details_grid.addWidget(val, row, col * 2 + 1, 1, 1)

            col += 1
            if col >= 2:
                col = 0
                row += 1

        self.details_grid.setRowStretch(row, 1)

    def _update_image(self, student: Student) -> None:
        """Load profile image if exists."""
        if student.profile_image_path:
            full_path = get_paths().attachment_dir / student.profile_image_path
            if full_path.exists():
                pixmap = QPixmap(str(full_path))
                if not pixmap.isNull():
                    self.image_label.setPixmap(pixmap.scaled(
                        64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    ))
                    self.image_label.setText("")
                    return
        # Fallback
        self.image_label.setText("📷")
        self.image_label.setPixmap(QPixmap())

    def clear(self) -> None:
        while self.details_grid.count():
            item = self.details_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.image_label.setText("📷")
        self.image_label.setPixmap(QPixmap())
        self.name_label.setText("")
        self.code_label.setText("")
        self.status_badge.set_status("")