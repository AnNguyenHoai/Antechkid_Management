# -*- coding: utf-8 -*-
"""Welcome page for Deployment Wizard."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWizardPage, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtGui import QPixmap, QFont


class WelcomePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to CenterManager")
        self.setSubTitle("Let's set up your first deployment")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo or icon
        icon_label = QLabel("🏫")
        icon_label.setStyleSheet("font-size: 64px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("CenterManager")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #1976d2;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "This wizard will help you clone the CenterManager data repository\n"
            "and configure the application for first-time use.\n\n"
            "You will need:\n"
            "• Repository URL (Git)\n"
            "• Personal Access Token (GitHub/GitLab)\n\n"
            "Contact your system administrator if you don't have these."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #333;")
        layout.addWidget(desc)

        layout.addStretch()