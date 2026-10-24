# -*- coding: utf-8 -*-
"""Operational overview of active classes and their active students."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from centermanager.ui.design_system.foundation import (
    Button,
    ButtonVariant,
    ComponentSize,
    Input,
)
from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)

logger = logging.getLogger(__name__)


class ClassOverviewPage(QWidget):
    """Fast read-only view of active classes and current students."""

    class_selected = Signal(int)

    def __init__(self, class_service, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._class_service = class_service
        self._overview: list[dict] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        root.setSpacing(SPACING["md"])

        title = QLabel("Active Class Overview", self)
        title.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{TYPOGRAPHY['section_title']}px; "
            f"font-weight:{FONT_WEIGHTS['semibold']}; color:{COLORS['text_primary']};"
        )
        root.addWidget(title)

        subtitle = QLabel(
            "See active classes and their current students without opening each class.",
            self,
        )
        subtitle.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{TYPOGRAPHY['body']}px; "
            f"color:{COLORS['text_muted']};"
        )
        root.addWidget(subtitle)

        self.search_input = Input(
            "Search class, course, teacher, student code or student name...",
            size=ComponentSize.MEDIUM,
            clearable=True,
            parent=self,
        )
        self.search_input.setMinimumWidth(360)
        self.search_input.textChanged.connect(self._render)
        root.addWidget(self.search_input)

        self.summary_label = QLabel("", self)
        self.summary_label.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{TYPOGRAPHY['body_small']}px; "
            f"font-weight:{FONT_WEIGHTS['medium']}; color:{COLORS['text_secondary']};"
        )
        root.addWidget(self.summary_label)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget(self.scroll)
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.setContentsMargins(0, 0, SPACING["sm"], 0)
        self.cards_layout.setSpacing(SPACING["md"])
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

    def refresh(self) -> None:
        try:
            self._overview = list(self._class_service.get_active_class_overview())
            self._render()
        except Exception:
            logger.exception("Failed to load active class overview")
            self._overview = []
            self._render(error_message="Unable to load active classes.")

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _matches_class(item: dict, term: str) -> bool:
        if not term:
            return True
        haystacks = [
            item.get("class_name", ""),
            item.get("course", ""),
            " ".join(item.get("teachers") or []),
        ]
        if any(term in str(value).casefold() for value in haystacks):
            return True
        for student in item.get("students") or []:
            if term in str(student.get("student_code", "")).casefold():
                return True
            if term in str(student.get("full_name", "")).casefold():
                return True
        return False

    @staticmethod
    def _visible_students(item: dict, term: str) -> list[dict]:
        students = list(item.get("students") or [])
        if not term:
            return students
        class_matches = any(
            term in str(value).casefold()
            for value in (
                item.get("class_name", ""),
                item.get("course", ""),
                " ".join(item.get("teachers") or []),
            )
        )
        if class_matches:
            return students
        return [
            student
            for student in students
            if term in str(student.get("student_code", "")).casefold()
            or term in str(student.get("full_name", "")).casefold()
        ]

    def _render(self, _text: str = "", *, error_message: Optional[str] = None) -> None:
        self._clear_cards()

        if error_message:
            message = QLabel(error_message, self.container)
            message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message.setStyleSheet(
                f"padding:{SPACING['xl']}px; color:{COLORS['state_danger']}; "
                f"font-size:{TYPOGRAPHY['body']}px;"
            )
            self.cards_layout.addWidget(message)
            self.cards_layout.addStretch()
            self.summary_label.setText("")
            return

        term = self.search_input.text().strip().casefold()
        visible = [item for item in self._overview if self._matches_class(item, term)]
        total_students = sum(item.get("active_student_count", 0) for item in visible)
        self.summary_label.setText(
            f"{len(visible)} active class(es) · {total_students} active student(s)"
        )

        if not visible:
            message = QLabel("No active classes match the current search.", self.container)
            message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message.setStyleSheet(
                f"padding:{SPACING['xl']}px; color:{COLORS['text_muted']}; "
                f"font-size:{TYPOGRAPHY['body']}px;"
            )
            self.cards_layout.addWidget(message)
            self.cards_layout.addStretch()
            return

        for item in visible:
            self.cards_layout.addWidget(self._build_class_card(item, term))
        self.cards_layout.addStretch()

    def _build_class_card(self, item: dict, term: str) -> QFrame:
        card = QFrame(self.container)
        card.setObjectName("ClassOverviewCard")
        card.setStyleSheet(
            f"""
            QFrame#ClassOverviewCard {{
                background: {COLORS['surface_card']};
                border: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']}px;
            }}
            QLabel#ClassOverviewName {{
                color: {COLORS['text_primary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['card_title']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QLabel#ClassOverviewMeta {{
                color: {COLORS['text_muted']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
            }}
            QLabel#ClassOverviewStudent {{
                color: {COLORS['text_primary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body']}px;
                padding: {SPACING['xs']}px 0;
            }}
            """
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        layout.setSpacing(SPACING["sm"])

        header = QHBoxLayout()
        name = QLabel(item.get("class_name", ""), card)
        name.setObjectName("ClassOverviewName")
        header.addWidget(name, 1)

        count = item.get("active_student_count", 0)
        capacity = item.get("capacity")
        count_text = f"{count} students" if capacity is None else f"{count} / {capacity} students"
        count_label = QLabel(count_text, card)
        count_label.setObjectName("ClassOverviewMeta")
        header.addWidget(count_label)

        open_btn = Button(
            "Open class →",
            variant=ButtonVariant.GHOST,
            size=ComponentSize.SMALL,
            parent=card,
        )
        class_id = int(item["class_id"])
        open_btn.clicked.connect(
            lambda _checked=False, cid=class_id: self.class_selected.emit(cid)
        )
        header.addWidget(open_btn)
        layout.addLayout(header)

        meta_parts = []
        if item.get("course"):
            meta_parts.append(item["course"])
        if item.get("teachers"):
            meta_parts.append("Teacher: " + ", ".join(item["teachers"]))
        meta = QLabel(" · ".join(meta_parts) if meta_parts else "No course/teacher information", card)
        meta.setObjectName("ClassOverviewMeta")
        layout.addWidget(meta)

        students = self._visible_students(item, term)
        if not students:
            empty = QLabel("No active students.", card)
            empty.setObjectName("ClassOverviewMeta")
            layout.addWidget(empty)
        else:
            for student in students:
                code = student.get("student_code") or "—"
                full_name = student.get("full_name") or "Unnamed student"
                student_label = QLabel(f"{code}   {full_name}", card)
                student_label.setObjectName("ClassOverviewStudent")
                layout.addWidget(student_label)

        return card


__all__ = ["ClassOverviewPage"]
