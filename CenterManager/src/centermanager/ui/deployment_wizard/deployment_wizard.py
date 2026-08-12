# -*- coding: utf-8 -*-
"""Deployment Bootstrap Wizard."""

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWizard, QApplication, QWidget

from centermanager.platform.deployment import (
    RepositoryManager,
    RuntimeValidator,
    DeploymentConfig,
)
from centermanager.ui.deployment_wizard.welcome_page import WelcomePage
from centermanager.ui.deployment_wizard.repository_page import RepositoryPage
from centermanager.ui.deployment_wizard.auth_page import AuthPage
from centermanager.ui.deployment_wizard.clone_page import ClonePage
from centermanager.ui.deployment_wizard.validation_page import ValidationPage

logger = logging.getLogger(__name__)


class DeploymentWizard(QWizard):
    """Wizard for first-time deployment setup."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("CenterManager - Deployment Setup")
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setFixedSize(600, 480)

        self._repo_manager = RepositoryManager()
        self._runtime_validator = RuntimeValidator()
        self._deployment_config = DeploymentConfig()

        self._setup_pages()

        self.setOption(QWizard.WizardOption.NoCancelButton, False)
        self.setButtonText(QWizard.WizardButton.FinishButton, "Finish")
        self.setButtonText(QWizard.WizardButton.NextButton, "Next →")
        self.setButtonText(QWizard.WizardButton.BackButton, "← Back")

    def _setup_pages(self) -> None:
        self.welcome_page = WelcomePage()
        self.repository_page = RepositoryPage()
        self.auth_page = AuthPage()
        self.clone_page = ClonePage()
        self.validation_page = ValidationPage()

        self.addPage(self.welcome_page)
        self.addPage(self.repository_page)
        self.addPage(self.auth_page)
        self.addPage(self.clone_page)
        self.addPage(self.validation_page)

    def save_config(self) -> None:
        """Save configuration from all pages (public method)."""
        # Repository page data
        url = self.repository_page.get_repository_url()
        branch = self.repository_page.get_branch()
        local_path = self.repository_page.get_local_path()
        if url:
            self._deployment_config.set("repository_url", url)
        if branch:
            self._deployment_config.set("branch", branch)
        if local_path:
            self._deployment_config.set("local_path", local_path)

        # Auth page data
        token = self.auth_page.get_token()
        if token:
            self._deployment_config.set("token", token)

    def accept(self) -> None:
        """Called when wizard is accepted (Finish clicked)."""
        # Save configuration from pages
        self.save_config()
        # Attempt deployment via clone page (which already did clone)
        # Validate final state
        if self._runtime_validator.is_healthy():
            super().accept()
        else:
            # Show error and stay
            self.validation_page.set_status(False, "Deployment validation failed. Please check configuration.")
            self.setCurrentPage(self.validation_page)