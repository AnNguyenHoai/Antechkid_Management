# -*- coding: utf-8 -*-
"""Regression coverage for deterministic Qt application lifecycle."""

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication


def test_suite_owns_qapplication_not_only_qcoreapplication():
    app = QCoreApplication.instance()
    assert isinstance(app, QApplication)
