# -*- coding: utf-8 -*-
"""Clone page for Deployment Wizard."""

import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWizardPage, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QHBoxLayout, QTextEdit, QApplication
)

from centermanager.platform.deployment import RepositoryManager

logger = logging.getLogger(__name__)


class ClonePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Cloning Repository")
        self.setSubTitle("Please wait while the repository is being cloned...")

        self._clone_success = False
        self._repo_manager = None

        self._setup_ui()
        self.retry_btn.hide()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Initializing...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setPlaceholderText("Clone progress will be shown here...")
        layout.addWidget(self.log_text)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.clicked.connect(self._retry)
        btn_layout.addWidget(self.retry_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def initializePage(self):
        """Called when the page is shown. Start the clone process."""
        self._clone_success = False
        self.completeChanged.emit()

        wizard = self.wizard()
        if not hasattr(wizard, '_repo_manager'):
            self._log_error("Repository manager not found.")
            self._set_failed("Internal error: missing repository manager.")
            return

        # --- LƯU CẤU HÌNH TRƯỚC KHI CLONE ---
        if hasattr(wizard, 'save_config'):
            wizard.save_config()
        else:
            self._log_error("Wizard missing save_config method.")
            self._set_failed("Internal error: cannot save configuration.")
            return

        self._repo_manager = wizard._repo_manager
        self._start_clone()

    def _start_clone(self):
        self._set_running()
        self.retry_btn.hide()
        self.log_text.clear()

        def progress_callback(step, message, percent):
            self.status_label.setText(message)
            self.progress_bar.setValue(percent)
            self.log_text.append(message)
            QApplication.processEvents()

        try:
            result = self._repo_manager.clone_repository(progress_callback=progress_callback)
            if result:
                self._clone_success = True
                self.status_label.setText("✅ Clone completed successfully!")
                self.progress_bar.setValue(100)
                self.log_text.append("Repository cloned successfully.")
                self.retry_btn.hide()
            else:
                self._clone_success = False
                self.status_label.setText("❌ Clone failed.")
                self.progress_bar.setValue(0)
                self.log_text.append("ERROR: Clone returned False.")
                self.retry_btn.show()
        except Exception as e:
            logger.exception("Clone failed")
            self._clone_success = False
            self.status_label.setText(f"❌ Clone failed: {str(e)}")
            self.progress_bar.setValue(0)
            self.log_text.append(f"ERROR: {str(e)}")
            self.retry_btn.show()

        self.completeChanged.emit()

    def _set_running(self):
        self.status_label.setText("Cloning in progress...")
        self.progress_bar.setValue(0)
        self.retry_btn.hide()

    def _set_failed(self, message):
        self.status_label.setText(f"❌ {message}")
        self.progress_bar.setValue(0)
        self.retry_btn.show()
        self._clone_success = False
        self.completeChanged.emit()

    def _log_error(self, message):
        self.log_text.append(f"ERROR: {message}")

    def _retry(self):
        self._start_clone()

    def isComplete(self):
        return self._clone_success