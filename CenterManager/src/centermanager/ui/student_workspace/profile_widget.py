# -*- coding: utf-8 -*-
"""
ProfileWidget - unified student profile display.
Redesigned with better visual hierarchy and layout.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame, QSizePolicy
)

from centermanager.models.student import Student
from centermanager.ui.students.helpers import calculate_age, format_date_for_display
from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS
from centermanager.ui.design_system.components import Avatar, StatusBadge


class ProfileWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.clear()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['md'])

        # --- Header row: Avatar + Name/Code/Status ---
        header = QHBoxLayout()
        header.setSpacing(SPACING['lg'])
        
        self.avatar = Avatar("", size=56)
        self.avatar.setFixedSize(56, 56)
        header.addWidget(self.avatar)

        info = QVBoxLayout()
        info.setSpacing(SPACING['xs'])
        
        # Name
        self.name_label = QLabel()
        self.name_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['page_title']}px;
            font-weight: 700;
            color: {COLORS['text_primary']};
        """)
        info.addWidget(self.name_label)
        
        # Code + Status
        code_status = QHBoxLayout()
        code_status.setSpacing(SPACING['sm'])
        self.code_label = QLabel()
        self.code_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body']}px;
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

        # --- Separator ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {COLORS['border_light']}; height: 1px;")
        layout.addWidget(line)

        # --- Details grid (2 columns) ---
        self.details_grid = QGridLayout()
        self.details_grid.setSpacing(SPACING['sm'])
        self.details_grid.setContentsMargins(0, SPACING['sm'], 0, 0)
        self.details_grid.setColumnStretch(1, 1)
        self.details_grid.setColumnStretch(3, 1)
        layout.addLayout(self.details_grid)

    def set_student(self, student: Student, primary_parent_name: str = "", primary_parent_phone: str = "") -> None:
        self.clear()
        if not student:
            return

        self.avatar.set_name(student.full_name)
        self.name_label.setText(student.full_name)
        self.code_label.setText(student.student_code)
        self.status_badge.set_status(student.status or "")

        # Build details
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

        # Add to grid with label-value pairs
        row = 0
        col = 0
        for label, value in details:
            # Label
            lbl = QLabel(label + ":")
            lbl.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['caption']}px;
                color: {COLORS['text_muted']};
                font-weight: 500;
                letter-spacing: 0.2px;
            """)
            self.details_grid.addWidget(lbl, row, col * 2, 1, 1)

            # Value
            val = QLabel(value)
            val.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body']}px;
                color: {COLORS['text_primary']};
                font-weight: 500;
            """)
            val.setWordWrap(True)
            self.details_grid.addWidget(val, row, col * 2 + 1, 1, 1)

            col += 1
            if col >= 2:
                col = 0
                row += 1

    def clear(self) -> None:
        while self.details_grid.count():
            item = self.details_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.avatar.set_name("")
        self.name_label.setText("")
        self.code_label.setText("")
        self.status_badge.set_status("")