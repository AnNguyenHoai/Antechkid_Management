# -*- coding: utf-8 -*-
"""
SummaryWidget - grid of summary cards.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout

from centermanager.dto.student_summary_dto import StudentSummaryDTO
from centermanager.ui.summary.summary_card import SummaryCard


class SummaryWidget(QWidget):
    """Widget displaying summary cards in a grid layout."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def set_summary(self, dto: StudentSummaryDTO) -> None:
        """Clear and populate cards from DTO."""
        self._clear()

        cards = []

        # Current Level
        cards.append(SummaryCard("📚", "Current Level", dto.current_level or "-"))

        # Latest Assessment
        if dto.latest_assessment_title:
            score_str = "★" * (dto.latest_assessment_score or 0) + "☆" * (5 - (dto.latest_assessment_score or 0))
            cards.append(SummaryCard("📊", "Latest Assessment", score_str, dto.latest_assessment_date))
        else:
            cards.append(SummaryCard("📊", "Latest Assessment", "No assessment"))

        # Primary Contact
        if dto.primary_contact_name:
            cards.append(SummaryCard("👨‍👩‍👧", "Primary Contact", dto.primary_contact_name, dto.primary_contact_phone))
        else:
            cards.append(SummaryCard("👨‍👩‍👧", "Primary Contact", "No contact"))

        # Last Activity
        if dto.last_activity_title:
            cards.append(SummaryCard("⏱️", "Last Activity", dto.last_activity_title, dto.last_activity_time))
        else:
            cards.append(SummaryCard("⏱️", "Last Activity", "No activity"))

        # Learning Status
        cards.append(SummaryCard("🔵", "Status", dto.learning_status or "-"))

        # Age
        age_str = str(dto.age) if dto.age is not None else "-"
        cards.append(SummaryCard("🎂", "Age", age_str))

        # Assessment Count
        cards.append(SummaryCard("📊", "Assessments", str(dto.assessment_count)))

        # Timeline Count
        cards.append(SummaryCard("📅", "Timeline Events", str(dto.timeline_count)))

        # Parent Count
        cards.append(SummaryCard("👨‍👩‍👧", "Parents", str(dto.parent_count)))

        # Add cards to grid (3 columns)
        cols = 3
        for idx, card in enumerate(cards):
            row = idx // cols
            col = idx % cols
            self._layout.addWidget(card, row, col)

        # Stretch at bottom
        self._layout.setRowStretch(row + 1, 1)

    def _clear(self) -> None:
        """Remove all cards."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()