# tests/test_config.py
# -*- coding: utf-8 -*-
"""
Tests for configuration loader.
"""
import pytest
import json
from pathlib import Path

from centermanager.core.config import (
    load_config,
    save_config,
    init_config,
    get_config,
    _DEFAULT_CONFIG,
)
from centermanager.core.paths import get_paths
from tests.conftest import REAL_RUNTIME_PATH


def test_config_uses_default_when_missing(temp_runtime):
    """Test that load_config returns defaults when file is missing."""
    paths = get_paths()
    config_file = paths.config_file
    # ensure file does not exist
    if config_file.exists():
        config_file.unlink()
    data = load_config(config_file)
    assert data["application"]["name"] == "CenterManager"
    assert data["application"]["version"] == "0.1.0"


def test_config_save_and_load(temp_runtime):
    """Test that save_config writes a file that load_config can read."""
    paths = get_paths()
    config_file = paths.config_file
    config_file.parent.mkdir(parents=True, exist_ok=True)
    test_data = {"application": {"name": "TestApp", "version": "9.9.9"}}
    save_config(test_data, config_file)
    loaded = load_config(config_file)
    assert loaded["application"]["name"] == "TestApp"
    assert loaded["application"]["version"] == "9.9.9"


def test_init_config_creates_default_if_missing(temp_runtime):
    """Test that init_config creates default config if missing."""
    paths = get_paths()
    config_file = paths.config_file
    if config_file.exists():
        config_file.unlink()
    init_config()
    assert config_file.exists()
    loaded = load_config(config_file)
    assert loaded["application"]["name"] == "CenterManager"


def test_get_config_returns_config(temp_runtime):
    config = get_config()
    assert config.get("application.name") == "CenterManager"
    assert config.get("application.version") is not None


def test_config_get_with_dot_notation(clean_paths):
    config = get_config()
    assert config.get("application.name") == "CenterManager"
    assert config.get("application.nonexistent", "default") == "default"
    assert config.get("non.existent.key", None) is None


def test_config_raw_property(clean_paths):
    config = get_config()
    raw = config.raw
    assert raw is not config._data
    original_name = raw["application"]["name"]
    raw["application"]["name"] = "Hacked"
    assert raw["application"]["name"] == "Hacked"
    assert config.get("application.name") == original_name


def test_production_runtime_unchanged():
    from tests.conftest import REAL_RUNTIME_PATH
    config_file = REAL_RUNTIME_PATH / "Config" / "config.json"
    assert config_file.exists()
    with open(config_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert "application" in data
    assert "name" in data["application"]