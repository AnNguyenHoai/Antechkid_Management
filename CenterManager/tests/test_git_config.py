# -*- coding: utf-8 -*-
import pytest
import json
from pathlib import Path
from unittest.mock import patch

from centermanager.services.git_config_service import GitConfigService, GitConfig, GitConfigValidationError
from centermanager.core.crypto import encrypt_git_config


@pytest.fixture
def temp_config_path(tmp_path):
    return tmp_path / "config.json"


@patch.object(GitConfigService, 'test_connection', return_value=True)
def test_save_load_config(mock_connection, temp_config_path):
    service = GitConfigService(temp_config_path)
    config = GitConfig(
        repository_url="https://github.com/test/repo.git",
        username="testuser",
        token="testtoken",
        branch="main",
        email="test@example.com"
    )

    assert service.save_config(config) is True
    assert temp_config_path.exists()

    loaded = service.load_config()
    assert loaded is not None
    assert loaded.repository_url == config.repository_url
    assert loaded.username == config.username
    assert loaded.token == config.token
    assert loaded.branch == config.branch
    assert loaded.email == config.email


@patch.object(GitConfigService, 'test_connection', return_value=True)
def test_has_config(mock_connection, temp_config_path):
    service = GitConfigService(temp_config_path)
    assert service.has_config() is False

    config = GitConfig(
        repository_url="https://github.com/test/repo.git",
        username="testuser",
        token="testtoken"
    )
    service.save_config(config)
    assert service.has_config() is True


@patch.object(GitConfigService, 'test_connection', return_value=True)
def test_validate_bundle_valid(mock_connection, temp_config_path):
    service = GitConfigService(temp_config_path)
    config = GitConfig(
        repository_url="https://github.com/test/repo.git",
        username="testuser",
        token="testtoken"
    )
    bundle = encrypt_git_config(json.dumps(config.to_dict()))
    result = service.validate_bundle(bundle)
    assert result.success is True


def test_validate_bundle_invalid(temp_config_path):
    service = GitConfigService(temp_config_path)
    result = service.validate_bundle("invalid")
    assert result.success is False
    assert "Invalid bundle format. Must start with 'ENC:v1:'" in result.message


@patch.object(GitConfigService, 'test_connection', return_value=True)
def test_clear_config(mock_connection, temp_config_path):
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