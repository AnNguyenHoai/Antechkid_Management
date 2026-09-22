# -*- coding: utf-8 -*-
"""ProfileWidget - unified student profile display."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from centermanager.models.student import Student
from centermanager.ui.students.helpers import calculate_age, format_date_for_display
from centermanager.ui.design_system import Badge, DetailRow, DetailSection
from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)
from centermanager.core.paths import get_paths


class ProfileWidget(QWidget):
    """Compact student identity and read-only detail surface."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._detail_rows: list[DetailRow] = []
        self._setup_ui()
        self.clear()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.profile_section = DetailSection(
            "Student profile",
            "Identity, learning context, and primary guardian contact.",
            parent=self,
        )
        layout.addWidget(self.profile_section)

        # Identity header
        header_widget = QWidget()
        header = QHBoxLayout(header_widget)
        header.setContentsMargins(0, SPACING["xs"], 0, SPACING["sm"])
        header.setSpacing(SPACING["lg"])

        self.image_label = QLabel()
        self.image_label.setObjectName("StudentProfileImage")
        self.image_label.setFixedSize(64, 64)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(True)
        header.addWidget(self.image_label)

        info = QVBoxLayout()
        info.setSpacing(SPACING["xs"])

        self.name_label = QLabel()
        self.name_label.setObjectName("StudentProfileName")
        self.name_label.setWordWrap(True)
        info.addWidget(self.name_label)

        code_status = QHBoxLayout()
        code_status.setSpacing(SPACING["sm"])
        self.code_label = QLabel()
        self.code_label.setObjectName("StudentProfileCode")
        code_status.addWidget(self.code_label)

        self.status_badge = Badge("")
        code_status.addWidget(self.status_badge)
        code_status.addStretch()
        info.addLayout(code_status)

        header.addLayout(info, 1)
        self.profile_section.add_widget(header_widget)

        # Details remain in a two-column desktop grid, but each cell uses the
        # canonical DetailRow pattern for consistent label/value hierarchy.
        details_widget = QWidget()
        self.details_grid = QGridLayout(details_widget)
        self.details_grid.setContentsMargins(0, SPACING["xs"], 0, 0)
        self.details_grid.setHorizontalSpacing(SPACING["xl"])
        self.details_grid.setVerticalSpacing(SPACING["xs"])
        self.details_grid.setColumnStretch(0, 1)
        self.details_grid.setColumnStretch(1, 1)
        self.profile_section.add_widget(details_widget)

        self.setStyleSheet(
            f"""
            QLabel#StudentProfileImage {{
                background-color: {COLORS["surface_hover"]};
                color: {COLORS["text_secondary"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                border-radius: {RADIUS["circle"]}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            QLabel#StudentProfileName {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["section_title"]}px;
                font-weight: {FONT_WEIGHTS["bold"]};
                border: none;
            }}
            QLabel#StudentProfileCode {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["medium"]};
                border: none;
            }}
            """
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def set_student(
        self,
        student: Student,
        primary_parent_name: str = "",
        primary_parent_phone: str = "",
    ) -> None:
        self.clear()
        if not student:
            return

        self._update_image(student)
        self.name_label.setText(student.full_name)
        self.code_label.setText(student.student_code)
        self.status_badge.set_status(student.status or "")

        details = [
            ("Preferred Name", student.preferred_name or "—"),
            ("Date of Birth", format_date_for_display(student.date_of_birth) or "—"),
            ("Age", str(calculate_age(student.date_of_birth)) if student.date_of_birth else "—"),
            ("Gender", student.gender or "—"),
            ("Current Level", student.current_level or "—"),
            ("Enrollment Date", format_date_for_display(student.enrollment_date) or "—"),
            ("Primary Parent", primary_parent_name or "—"),
            ("Contact", primary_parent_phone or "—"),
        ]

        for index, (label, value) in enumerate(details):
            row_widget = DetailRow(label, value, parent=self)
            self._detail_rows.append(row_widget)
            self.details_grid.addWidget(row_widget, index // 2, index % 2)

    def _update_image(self, student: Student) -> None:
        """Load profile image if it exists, otherwise show student initials."""
        if student.profile_image_path:
            full_path = get_paths().attachment_dir / student.profile_image_path
            if full_path.exists():
                pixmap = QPixmap(str(full_path))
                if not pixmap.isNull():
                    self.image_label.setPixmap(
                        pixmap.scaled(
                            64,
                            64,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    self.image_label.setText("")
                    return
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(self._initials(student.full_name))

    @staticmethod
    def _initials(name: str) -> str:
        parts = [part for part in (name or "").strip().split() if part]
        if not parts:
            return "—"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f"{parts[0][0]}{parts[-1][0]}".upper()

    def clear(self) -> None:
        while self.details_grid.count():
            item = self.details_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._detail_rows = []
        self.image_label.setText("—")
        self.image_label.setPixmap(QPixmap())
        self.name_label.setText("")
        self.code_label.setText("")
        self.status_badge.set_status("")
