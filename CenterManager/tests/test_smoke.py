# -*- coding: utf-8 -*-
"""
Smoke tests to verify that all foundation modules can be imported.
"""
import pytest


def test_import_core_paths():
    """Test that core.paths can be imported."""
    from centermanager.core import paths
    assert hasattr(paths, "get_paths")


def test_import_core_config():
    """Test that core.config can be imported."""
    from centermanager.core import config
    assert hasattr(config, "get_config")


def test_import_core_logging():
    """Test that core.logging can be imported."""
    from centermanager.core import logging
    assert hasattr(logging, "setup_logging")


def test_import_ui_main_window():
    """Test that ui.main_window can be imported."""
    from centermanager.ui import main_window
    assert hasattr(main_window, "MainWindow")


def test_import_app():
    """Test that app can be imported."""
    from centermanager import app
    assert hasattr(app, "main")


def test_import_all_packages():
    """Test that all module __init__.py files can be imported."""
    import centermanager
    import centermanager.core
    import centermanager.database
    import centermanager.models
    import centermanager.repositories
    import centermanager.services
    import centermanager.modules
    import centermanager.ui
    import centermanager.export
    import centermanager.export.pdf
    import centermanager.export.excel
    import centermanager.utils
    
    assert centermanager.__version__ == "0.1.0"