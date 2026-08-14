# -*- coding: utf-8 -*-
"""Tests for GitConfigService."""

import pytest
import json
from pathlib import Path

from centermanager.services.git_config_service import GitConfigService, GitConfig, GitConfigValidationError
from centermanager.core.crypto import encrypt_git_config, decrypt_git_config


@pytest.fixture
def temp_config_path(tmp_path):
    config_file = tmp_path / "config.json"
    return config_file


def test_save_load_config(temp_config_path):
    """Test saving and loading Git configuration."""
    service = GitConfigService(temp_config_path)
    config = GitConfig(
        repository_url="https://github.com/test/repo.git",
        username="testuser",
        token="testtoken",
        branch="main",
        email="test@example.com"
    )

    # Save config
    assert service.save_config(config) is True
    assert temp_config_path.exists()

    # Load config
    loaded = service.load_config()
    assert loaded is not None
    assert loaded.repository_url == config.repository_url
    assert loaded.username == config.username
    assert loaded.token == config.token
    assert loaded.branch == config.branch
    assert loaded.email == config.email


def test_has_config(temp_config_path):
    """Test has_config method."""
    service = GitConfigService(temp_config_path)
    assert service.has_config() is False

    config = GitConfig(
        repository_url="https://github.com/test/repo.git",
        username="testuser",
        token="testtoken"
    )
    service.save_config(config)
    assert service.has_config() is True


def test_validate_bundle_valid(temp_config_path):
    """Test validating a valid bundle."""
    service = GitConfigService(temp_config_path)
    config = GitConfig(
        repository_url="https://github.com/test/repo.git",
        username="testuser",
        token="testtoken"
    )
    # Note: test_connection will fail because repo doesn't exist, but we're testing validation
    # We should mock test_connection or use a valid repo for testing.
    # For unit test, we'll mock test_connection to return True.
    import unittest.mock as mock
    with mock.patch.object(service, 'test_connection', return_value=True):
        bundle = encrypt_git_config(json.dumps(config.to_dict()))
        result = service.validate_bundle(bundle)
        assert result.success is True


def test_validate_bundle_invalid(temp_config_path):
    """Test validating an invalid bundle."""
    service = GitConfigService(temp_config_path)
    # Invalid bundle (not starting with ENC:v1:)
    result = service.validate_bundle("invalid")
    assert result.success is False
    assert "must start with 'ENC:v1:'" in result.message


def test_clear_config(temp_config_path):
    """Test clearing Git configuration."""
    service = GitConfigService(temp_config_path)
    config = GitConfig(
        repository_url="https://github.com/test/repo.git",
        username="testuser",
        token="testtoken"
    )
    service.save_config(config)
    assert service.has_config() is True

    service.clear_config()
    assert service.has_config() is False
    assert service.get_config() is None