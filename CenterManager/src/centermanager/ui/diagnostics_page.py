# -*- coding: utf-8 -*-
"""
DiagnosticsPage - displays collaboration and system diagnostics.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy
)

from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.health import CollaborationHealthChecker
from centermanager.ui.design_system.tokens import COLORS, SPACING, TYPOGRAPHY

logger = logging.getLogger(__name__)


class DiagnosticsPage(QWidget):
    def __init__(
        self,
        collaboration_manager: CollaborationManager,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._collaboration_manager = collaboration_manager
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg'])
        layout.setSpacing(SPACING['md'])

        # Header
        header = QLabel("🔍 Diagnostics")
        header.setStyleSheet(f"font-size: {TYPOGRAPHY['page_title']}px; font-weight: 700;")
        layout.addWidget(header)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setFixedWidth(120)
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignRight)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setSpacing(SPACING['md'])
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        self._clear_container()
        try:
            diag = self._collaboration_manager.get_diagnostics()
            health = self._collaboration_manager.get_health()

            self._add_section("Health Status", self._format_health(health))
            self._add_section("Collaboration Mode", self._format_mode(diag))
            self._add_section("Lock Status", self._format_lock(diag))
            self._add_section("Session Info", self._format_session(diag))
            self._add_section("Git Status", self._format_git(diag))
            self._add_section("Heartbeat", self._format_heartbeat(diag))
            self._add_section("Platform", self._format_platform(diag))

        except Exception as e:
            logger.exception("Failed to refresh diagnostics")
            self._add_section("Error", f"<span style='color:red;'>Failed to load diagnostics: {e}</span>")

    def _clear_container(self) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_section(self, title: str, content: str) -> None:
        widget = QWidget()
        widget.setStyleSheet(f"""
            QWidget {{
                background: white;
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
                padding: {SPACING['md']}px;
            }}
        """)
        layout = QVBoxLayout(widget)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-weight: 600; font-size: {TYPOGRAPHY['body']}px;")
        layout.addWidget(title_label)

        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet(f"font-size: {TYPOGRAPHY['body_small']}px; color: {COLORS['text_secondary']};")
        layout.addWidget(content_label)

        self.container_layout.addWidget(widget)

    def _format_health(self, health) -> str:
        status = health.status.value if hasattr(health.status, 'value') else str(health.status)
        emoji = "✅" if status == "HEALTHY" else "⚠️" if status == "WARNING" else "🚨"
        return f"{emoji} Overall: {status}\nDetails: {health.details}"

    def _format_mode(self, diag: dict) -> str:
        mode = diag.get("mode", "UNKNOWN")
        user = diag.get("user", "Unknown")
        return f"Mode: {mode}\nUser: {user}"

    def _format_lock(self, diag: dict) -> str:
        lock = diag.get("lock", {})
        return (
            f"Locked: {lock.get('locked', False)}\n"
            f"Owner: {lock.get('owner', 'None')}\n"
            f"Session ID: {lock.get('session_id', 'None')}\n"
            f"Started: {lock.get('started_at', 'None')}\n"
            f"Last Heartbeat: {lock.get('last_heartbeat', 'None')}\n"
            f"Stale: {lock.get('is_stale', False)}"
        )

    def _format_session(self, diag: dict) -> str:
        session = diag.get("session", {})
        return (
            f"Active: {session.get('active', False)}\n"
            f"Owner: {session.get('owner', 'None')}\n"
            f"Session ID: {session.get('session_id', 'None')}"
        )

    def _format_git(self, diag: dict) -> str:
        git = diag.get("git", {})
        if git.get("state") == "disabled":
            return "Git synchronization not configured."
        return (
            f"State: {git.get('state', 'Unknown')}\n"
            f"Status: {git.get('status', 'Unknown')}\n"
            f"Branch: {git.get('branch', 'Unknown')}\n"
            f"Commit: {git.get('commit', 'Unknown')}\n"
            f"Last Error: {git.get('last_error', 'None')}"
        )

    def _format_heartbeat(self, diag: dict) -> str:
        hb = diag.get("heartbeat", {})
        if hasattr(hb, 'is_running'):
            # It's a HeartbeatStatus object
            return (
                f"Running: {hb.is_running}\n"
                f"Count: {hb.heartbeat_count}\n"
                f"Last: {hb.last_heartbeat}\n"
                f"Owner: {hb.owner}"
            )
        else:
            # Fallback for dict
            return (
                f"Running: {hb.get('is_running', False)}\n"
                f"Count: {hb.get('heartbeat_count', 0)}\n"
                f"Last: {hb.get('last_heartbeat', 'None')}\n"
                f"Owner: {hb.get('owner', 'None')}"
            )

    def _format_platform(self, diag: dict) -> str:
        return (
            f"Version: {diag.get('platform_version', 0)}\n"
            f"Deployment: {diag.get('deployment_profile', 'Standalone')}"
        )