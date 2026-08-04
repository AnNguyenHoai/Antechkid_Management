# -*- coding: utf-8 -*-
"""
Design System Components - Reusable UI components for CenterManager.
"""
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QLineEdit, QScrollArea, QStackedWidget,
    QComboBox, QSpinBox, QDateEdit, QCheckBox, QFormLayout
)

from centermanager.ui.design_system.tokens import (
    COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS, SHADOWS
)

# ===== StatisticCard =====
class StatisticCard(QFrame):
    """Statistic card with icon, label, and value."""

    def __init__(
        self,
        icon: str,
        label: str,
        value: str,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(icon, label, value)

    def _setup_ui(self, icon: str, label: str, value: str) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border-radius: {BORDER_RADIUS}px;
                border: 1px solid {COLORS['border']};
                padding: {SPACING['xs']}px {SPACING['sm']}px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(60)
        self.setMaximumHeight(72)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['xs'], SPACING['xs'], SPACING['xs'], SPACING['xs'])
        layout.setSpacing(2)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(SPACING['xs'])

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon']}px;")
        top_layout.addWidget(icon_label)

        label_label = QLabel(label)
        label_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['caption']}px;
            color: {COLORS['muted']};
            font-weight: 500;
            letter-spacing: 0.2px;
            text-transform: uppercase;
        """)
        top_layout.addWidget(label_label)
        top_layout.addStretch()

        layout.addLayout(top_layout)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 700;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(self.value_label)
        layout.addStretch()

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


# ===== InfoCard =====
class InfoCard(QFrame):
    """Card for displaying information with optional action."""

    def __init__(
        self,
        title: str,
        value: str,
        icon: Optional[str] = None,
        action_text: Optional[str] = None,
        action_callback: Optional[Callable] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(title, value, icon, action_text, action_callback)

    def _setup_ui(self, title: str, value: str, icon: Optional[str], action_text: Optional[str], action_callback: Optional[Callable]) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border-radius: {BORDER_RADIUS}px;
                border: 1px solid {COLORS['border']};
                padding: {SPACING['sm']}px {SPACING['md']}px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING['xs'])

        top_layout = QHBoxLayout()
        if icon:
            icon_label = QLabel(icon)
            icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon']}px;")
            top_layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body_small']}px;
            color: {COLORS['muted']};
            font-weight: 500;
        """)
        top_layout.addWidget(title_label)
        top_layout.addStretch()

        if action_text and action_callback:
            action_btn = QPushButton(action_text)
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['primary']};
                    border: none;
                    font-size: {TYPOGRAPHY['body_small']}px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    text-decoration: underline;
                }}
            """)
            action_btn.clicked.connect(action_callback)
            top_layout.addWidget(action_btn)

        layout.addLayout(top_layout)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body']}px;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(value_label)


# ===== ActivityCard =====
class ActivityCard(QFrame):
    """Activity item with icon, title, student, and time."""

    def __init__(
        self,
        icon: str,
        title: str,
        student_name: str,
        student_code: str,
        time: datetime,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(icon, title, student_name, student_code, time)

    def _setup_ui(self, icon: str, title: str, student_name: str, student_code: str, time: datetime) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                padding: {SPACING['xs']}px 0;
                border-bottom: 1px solid {COLORS['border_light']};
            }}
            QFrame:hover {{
                background: {COLORS['surface_hover']};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING['xs'], SPACING['xs'], SPACING['xs'], SPACING['xs'])
        layout.setSpacing(SPACING['sm'])

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon']}px;")
        icon_label.setFixedWidth(24)
        layout.addWidget(icon_label)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(SPACING['xs'])

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body']}px;
            font-weight: 500;
            color: {COLORS['text_primary']};
        """)
        content_layout.addWidget(title_label)

        sub_label = QLabel(f"{student_name} ({student_code})")
        sub_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['caption']}px;
            color: {COLORS['muted']};
        """)
        content_layout.addWidget(sub_label)

        layout.addLayout(content_layout)
        layout.addStretch()

        time_str = self._format_time(time)
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['caption']}px;
            color: {COLORS['muted_light']};
        """)
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(time_label)

    def _format_time(self, dt: datetime) -> str:
        now = datetime.now()
        if dt.date() == now.date():
            return f"Today {dt.strftime('%H:%M')}"
        elif (now - dt).days == 1:
            return f"Yesterday {dt.strftime('%H:%M')}"
        else:
            return dt.strftime("%d/%m/%Y %H:%M")


# ===== SectionHeader =====
class SectionHeader(QWidget):
    """Section header with title, optional subtitle, and optional action."""

    def __init__(
        self,
        title: str,
        subtitle: Optional[str] = None,
        action_text: Optional[str] = None,
        action_callback: Optional[Callable] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(title, subtitle, action_text, action_callback)

    def _setup_ui(self, title: str, subtitle: Optional[str], action_text: Optional[str], action_callback: Optional[Callable]) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING['sm'])
        layout.setSpacing(SPACING['sm'])

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['section_title']}px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body_small']}px;
                color: {COLORS['muted']};
            """)
            layout.addWidget(sub_label)

        layout.addStretch()

        if action_text and action_callback:
            action_btn = QPushButton(action_text)
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['primary']};
                    border: none;
                    font-size: {TYPOGRAPHY['body_small']}px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    text-decoration: underline;
                }}
            """)
            action_btn.clicked.connect(action_callback)
            layout.addWidget(action_btn)

# ===== StatusBadge =====
class StatusBadge(QLabel):
    """Status badge with color coding."""
    
    def __init__(self, status: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui(status)
    
    def _setup_ui(self, status: str) -> None:
        from centermanager.ui.design_system.tokens import BADGE_COLORS, TYPOGRAPHY, SPACING
        
        status_upper = status.upper()
        colors = BADGE_COLORS.get(status_upper, {"bg": "#f5f5f5", "text": "#616161"})
        
        self.setText(status_upper.capitalize())
        self.setStyleSheet(f"""
            QLabel {{
                background: {colors['bg']};
                color: {colors['text']};
                padding: 2px {SPACING['sm']}px;
                border-radius: 12px;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.3px;
            }}
        """)
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    
    def set_status(self, status: str) -> None:
        self._setup_ui(status)


# ===== Avatar =====
class Avatar(QLabel):
    """Circular avatar displaying initials."""
    
    def __init__(
        self,
        name: str,
        size: int = 36,
        font_size: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._size = size
        # Nếu không truyền font_size, tự động tính = size // 2
        self._font_size = font_size if font_size is not None else size // 2
        self._setup_ui()

    def _setup_ui(self) -> None:
        initials = self._get_initials(self._name)
        self.setText(initials)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(self._size, self._size)
        self.setStyleSheet(f"""
            QLabel {{
                background: {COLORS['primary']};
                color: white;
                font-size: {self._font_size}px;
                font-weight: 600;
                border-radius: {self._size // 2}px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _get_initials(self, name: str) -> str:
        parts = name.strip().split()
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][0].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def set_name(self, name: str) -> None:
        self._name = name
        self.setText(self._get_initials(name))


# ===== PrimaryButton =====
class PrimaryButton(QPushButton):
    """Primary action button."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: {BORDER_RADIUS}px;
                padding: {SPACING['sm']}px {SPACING['lg']}px;
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_dark']};
            }}
            QPushButton:pressed {{
                background: {COLORS['primary_dark']};
            }}
            QPushButton:disabled {{
                background: {COLORS['muted']};
            }}
        """)
        self.setFixedHeight(36)


# ===== SecondaryButton =====
class SecondaryButton(QPushButton):
    """Secondary action button."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: {BORDER_RADIUS}px;
                padding: {SPACING['sm']}px {SPACING['lg']}px;
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {COLORS['surface_hover']};
                border-color: {COLORS['muted']};
            }}
            QPushButton:pressed {{
                background: {COLORS['surface_pressed']};
            }}
        """)
        self.setFixedHeight(36)


# ===== DangerButton =====
class DangerButton(QPushButton):
    """Danger action button."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['danger']};
                border: 1px solid {COLORS['danger']};
                border-radius: {BORDER_RADIUS}px;
                padding: {SPACING['sm']}px {SPACING['lg']}px;
                background: white;
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: #fde0e0;
            }}
            QPushButton:pressed {{
                background: #fcc;
            }}
        """)
        self.setFixedHeight(36)


# ===== SearchBar =====
class SearchBar(QLineEdit):
    """Search bar with icon and clear button."""

    text_changed = Signal(str)

    def __init__(
        self,
        placeholder: str = "Search...",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str) -> None:
        self.setPlaceholderText(f"🔍 {placeholder}")
        self.setStyleSheet(f"""
            QLineEdit {{
                background: white;
                border: 1px solid {COLORS['border']};
                border-radius: 20px;
                padding: {SPACING['sm']}px {SPACING['lg']}px;
                font-size: {TYPOGRAPHY['body']}px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
                outline: none;
            }}
        """)
        self.setFixedHeight(36)
        self.textChanged.connect(self.text_changed.emit)


# ===== EmptyState =====
class EmptyState(QWidget):
    """Empty state with icon, title, and description."""

    def __init__(
        self,
        icon: str = "📭",
        title: str = "No data",
        description: str = "",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(icon, title, description)

    def _setup_ui(self, icon: str, title: str, description: str) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING['sm'])

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon_large']}px;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['section_title']}px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body']}px;
                color: {COLORS['muted']};
            """)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)


# ===== LoadingState =====
class LoadingState(QWidget):
    """Loading indicator."""

    def __init__(self, message: str = "Loading...", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui(message)

    def _setup_ui(self, message: str) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING['sm'])

        spinner = QLabel("⏳")
        spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner.setStyleSheet(f"font-size: {TYPOGRAPHY['icon_large']}px;")
        layout.addWidget(spinner)

        msg_label = QLabel(message)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body']}px;
            color: {COLORS['muted']};
        """)
        layout.addWidget(msg_label)


# ===== Breadcrumb =====
class Breadcrumb(QWidget):
    """Breadcrumb navigation."""

    item_clicked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._items = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        self._clear()
        for i, item in enumerate(items):
            if i > 0:
                sep = QLabel("›")
                sep.setStyleSheet(f"""
                    font-size: {TYPOGRAPHY['body_small']}px;
                    color: {COLORS['muted_light']};
                """)
                self.layout.addWidget(sep)

            if item.get('active', False):
                label = QLabel(item['label'])
                label.setStyleSheet(f"""
                    font-size: {TYPOGRAPHY['body_small']}px;
                    font-weight: 500;
                    color: {COLORS['text_primary']};
                """)
                self.layout.addWidget(label)
            else:
                btn = QPushButton(item['label'])
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                        font-size: {TYPOGRAPHY['body_small']}px;
                        color: {COLORS['primary']};
                    }}
                    QPushButton:hover {{
                        text-decoration: underline;
                    }}
                """)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, id=item['id']: self.item_clicked.emit(id))
                self.layout.addWidget(btn)

        self.layout.addStretch()

    def _clear(self) -> None:
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()


# ===== FilterBar =====
class FilterBar(QWidget):
    """Filter bar with dropdowns and inputs."""

    filter_changed = Signal(dict)

    def __init__(
        self,
        filters: List[Dict[str, Any]],
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._filters = filters
        self._widgets = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        for f in self._filters:
            key = f.get('key', f.get('label', '').lower().replace(' ', '_'))
            f_type = f.get('type', 'combo')

            if f_type == 'combo':
                combo = QComboBox()
                combo.addItems(['All'] + f.get('options', []))
                combo.setStyleSheet(f"""
                    QComboBox {{
                        border: 1px solid {COLORS['border']};
                        border-radius: {BORDER_RADIUS}px;
                        padding: {SPACING['xs']}px {SPACING['sm']}px;
                        font-size: {TYPOGRAPHY['body_small']}px;
                        min-width: 100px;
                    }}
                """)
                combo.currentTextChanged.connect(
                    lambda text, k=key: self._on_change(k, text if text != 'All' else '')
                )
                layout.addWidget(combo)
                self._widgets[key] = combo
            elif f_type == 'text':
                edit = QLineEdit()
                edit.setPlaceholderText(f.get('label', ''))
                edit.setStyleSheet(f"""
                    QLineEdit {{
                        border: 1px solid {COLORS['border']};
                        border-radius: {BORDER_RADIUS}px;
                        padding: {SPACING['xs']}px {SPACING['sm']}px;
                        font-size: {TYPOGRAPHY['body_small']}px;
                    }}
                """)
                edit.textChanged.connect(
                    lambda text, k=key: self._on_change(k, text)
                )
                layout.addWidget(edit)
                self._widgets[key] = edit
            elif f_type == 'number':
                spin = QSpinBox()
                spin.setRange(0, 999)
                spin.setSpecialValueText("Any")
                spin.setStyleSheet(f"""
                    QSpinBox {{
                        border: 1px solid {COLORS['border']};
                        border-radius: {BORDER_RADIUS}px;
                        padding: {SPACING['xs']}px {SPACING['sm']}px;
                        font-size: {TYPOGRAPHY['body_small']}px;
                    }}
                """)
                spin.valueChanged.connect(
                    lambda val, k=key: self._on_change(k, val if val > 0 else '')
                )
                layout.addWidget(spin)
                self._widgets[key] = spin

        layout.addStretch()

        clear_btn = QPushButton("✕ Clear")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['muted']};
                border: none;
                font-size: {TYPOGRAPHY['body_small']}px;
            }}
            QPushButton:hover {{
                color: {COLORS['text_primary']};
            }}
        """)
        clear_btn.clicked.connect(self._clear_all)
        layout.addWidget(clear_btn)

    def _on_change(self, key: str, value) -> None:
        self.filter_changed.emit(self.get_values())

    def get_values(self) -> Dict[str, Any]:
        result = {}
        for key, widget in self._widgets.items():
            if isinstance(widget, QComboBox):
                val = widget.currentText()
                result[key] = val if val != 'All' else ''
            elif isinstance(widget, QLineEdit):
                result[key] = widget.text()
            elif isinstance(widget, QSpinBox):
                val = widget.value()
                result[key] = val if val > 0 else ''
        return result

    def _clear_all(self) -> None:
        for widget in self._widgets.values():
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QSpinBox):
                widget.setValue(0)
        self.filter_changed.emit(self.get_values())


# ===== InfoPanel =====
class InfoPanel(QWidget):
    """Panel for displaying key-value information in a grid."""

    def __init__(
        self,
        items: List[Dict[str, str]],
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._items = items
        self._layout = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._layout = QFormLayout(self)
        self._layout.setSpacing(SPACING['sm'])
        self._layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for item in self._items:
            label = QLabel(item.get('label', ''))
            label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body_small']}px;
                color: {COLORS['muted']};
                font-weight: 500;
            """)
            value = QLabel(item.get('value', ''))
            value.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body']}px;
                color: {COLORS['text_primary']};
            """)
            self._layout.addRow(label, value)

    def update_value(self, label: str, new_value: str) -> None:
        for i in range(self._layout.rowCount()):
            item = self._layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if item and item.widget() and item.widget().text() == label:
                value_widget = self._layout.itemAt(i, QFormLayout.ItemRole.FieldRole).widget()
                if value_widget and isinstance(value_widget, QLabel):
                    value_widget.setText(new_value)
                    break

class AutoClearDoubleSpinBox(QDoubleSpinBox):
    """Double spin box that auto-clears zero on focus and restores on blur."""
    
    def __init__(self, prefix: str = "", suffix: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        if prefix:
            self.setPrefix(prefix)
        if suffix:
            self.setSuffix(suffix)
        self.setRange(0.01, 999999999.99)
        self.setDecimals(0)
        self.setValue(0.00)
        self.lineEdit().setPlaceholderText("0")
    
    def focusInEvent(self, event):
        if self.value() == 0:
            self.lineEdit().clear()
        else:
            self.lineEdit().selectAll()
        super().focusInEvent(event)
    
    def focusOutEvent(self, event):
        if self.lineEdit().text().strip() == "":
            self.setValue(0)
        super().focusOutEvent(event)