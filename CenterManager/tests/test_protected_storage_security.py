# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from centermanager.platform.protected_data_service.protocol import (
    PROTOCOL_VERSION,
    SERVICE_NAME,
    SERVICE_PIPE_NAME,
    SERVICE_SID,
    ProtectedDataOperation,
)
from centermanager.security.protected_storage import (
    ProtectedStorageConfigurationError,
    ProtectedStorageMode,
    assert_direct_database_access_allowed,
    get_protected_storage_layout,
    protected_storage_mode,
)


def test_protected_storage_defaults_to_transitional_mode():
    assert protected_storage_mode({}) is ProtectedStorageMode.TRANSITIONAL
    assert_direct_database_access_allowed({})


def test_enforced_mode_blocks_direct_gui_database_access():
    env = {"ANTECHKIDS_PROTECTED_STORAGE_MODE": "enforced"}
    with pytest.raises(ProtectedStorageConfigurationError, match="direct database access"):
        assert_direct_database_access_allowed(env)


def test_invalid_protected_storage_mode_fails_closed():
    env = {"ANTECHKIDS_PROTECTED_STORAGE_MODE": "unsafe"}
    with pytest.raises(ProtectedStorageConfigurationError, match="Unsupported"):
        protected_storage_mode(env)


def test_service_owned_layout_is_outside_desktop_runtime_tree():
    layout = get_protected_storage_layout({}, program_data=Path("C:/ProgramData"))
    assert layout.root == Path("C:/ProgramData/AnTechKids/CenterManager/Protected")
    assert layout.database_path == layout.root / "Database" / "center.db"
    assert layout.key_bundle_path == layout.root / "Key" / "database_key.dpapi"
    assert layout.service_name == SERVICE_NAME
    assert layout.service_sid == SERVICE_SID
    assert layout.pipe_name == SERVICE_PIPE_NAME


def test_service_protocol_never_exposes_raw_key_operation():
    assert PROTOCOL_VERSION == 1
    values = {operation.value for operation in ProtectedDataOperation}
    assert values == {"health", "validate_database", "create_backup"}
    assert all("key" not in value for value in values)


def test_acl_script_is_service_only_and_dry_run_by_default():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "prepare_protected_storage_acl.ps1").read_text(
        encoding="utf-8"
    )
    assert "[switch]$Apply" in script
    assert "if (-not $Apply)" in script
    assert "Assert-ServiceExists" in script
    assert "/inheritance:r" in script
    assert '"${serviceSid}:(OI)(CI)F"' in script
    assert '"SYSTEM:(OI)(CI)F"' in script
    assert '"BUILTIN\\Administrators:(OI)(CI)F"' in script
    assert '"Users:' not in script
    assert '"Authenticated Users:' not in script
