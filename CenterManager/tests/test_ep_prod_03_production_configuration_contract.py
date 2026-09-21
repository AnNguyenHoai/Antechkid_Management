import json
import sys
from pathlib import Path

from centermanager.core import config as config_module
from centermanager.core.version import get_application_version
from centermanager.platform.deployment.deployment_config import DEFAULT_DEPLOYMENT_CONFIG


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
CONFIG_SOURCE = ROOT / "src" / "centermanager" / "core" / "config.py"
PATHS_SOURCE = ROOT / "src" / "centermanager" / "core" / "paths.py"
ENGINE_SOURCE = ROOT / "src" / "centermanager" / "database" / "engine.py"


def test_prod_03_runtime_version_matches_canonical_version_file():
    expected = VERSION_FILE.read_text(encoding="utf-8").strip()
    assert get_application_version() == expected
    assert config_module._DEFAULT_CONFIG["application"]["version"] == expected
    assert '"version": "0.1.0"' not in CONFIG_SOURCE.read_text(encoding="utf-8")


def test_prod_03_stale_persisted_version_cannot_override_running_release(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "application": {"name": "OldName", "version": "0.1.0"},
                "collaboration": {"enabled": True, "machine_id": "test-machine"},
            }
        ),
        encoding="utf-8",
    )

    loaded = config_module.load_config(config_path)

    assert loaded["application"] == {
        "name": "CenterManager",
        "version": VERSION_FILE.read_text(encoding="utf-8").strip(),
    }
    assert loaded["collaboration"] == {"enabled": True, "machine_id": "test-machine"}


def test_prod_03_save_normalizes_release_identity_without_losing_operator_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_module.save_config(
        {
            "application": {"name": "tampered", "version": "dev"},
            "collaboration": {"enabled": False},
        },
        config_path,
    )

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["application"]["name"] == "CenterManager"
    assert saved["application"]["version"] == VERSION_FILE.read_text(encoding="utf-8").strip()
    assert saved["collaboration"] == {"enabled": False}


def test_prod_03_frozen_runtime_reads_release_manifest(monkeypatch, tmp_path):
    executable = tmp_path / "CenterManager.exe"
    executable.touch()
    manifest = {
        "application": "CenterManager",
        "version": VERSION_FILE.read_text(encoding="utf-8").strip(),
    }
    (tmp_path / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    assert get_application_version() == manifest["version"]


def test_prod_03_frozen_runtime_fails_closed_without_release_manifest(monkeypatch, tmp_path):
    executable = tmp_path / "CenterManager.exe"
    executable.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    try:
        get_application_version()
    except RuntimeError as exc:
        assert "Release manifest is missing" in str(exc)
    else:
        raise AssertionError("Frozen runtime must not invent a release version")


def test_prod_03_sensitive_deployment_values_are_not_baked_into_defaults():
    assert DEFAULT_DEPLOYMENT_CONFIG["repository_url"] == ""
    assert DEFAULT_DEPLOYMENT_CONFIG["token"] == ""
    assert DEFAULT_DEPLOYMENT_CONFIG["local_path"] == ""
    assert DEFAULT_DEPLOYMENT_CONFIG["git_executable"] == ""


def test_prod_03_portable_paths_and_database_remain_centralized_contracts():
    paths_source = PATHS_SOURCE.read_text(encoding="utf-8")
    engine_source = ENGINE_SOURCE.read_text(encoding="utf-8")

    assert 'self._runtime_root = self._project_root / "runtime"' in paths_source
    assert 'return get_paths().database_dir / "center.db"' in engine_source
    assert "Path.cwd()" not in paths_source
    assert "sqlite:///" not in engine_source
