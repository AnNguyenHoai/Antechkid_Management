import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_sec06_isolated_uat.py"
spec = importlib.util.spec_from_file_location("prepare_sec06_isolated_uat", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_initial_repository_manifest_matches_publish_contract(tmp_path):
    repo = tmp_path / "repository"
    repo.mkdir()

    manifest_path = module._write_initial_repository_manifest(repo)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest_path == repo / "manifest.json"
    assert manifest["runtime_version"] == 1
    assert manifest["published_by"] == "SEC06-UAT"
    assert manifest["published_at"]
    assert manifest["description"]


def test_safety_rejects_existing_target(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "CenterManager.exe").write_bytes(b"fixture")
    target = tmp_path / "existing-target"
    target.mkdir()
    remote = tmp_path / "remote.git"

    try:
        module._assert_safe(package, target, remote)
    except module.UATPreparationError as exc:
        assert "must not already exist" in str(exc)
    else:
        raise AssertionError("existing UAT target must be rejected")


def test_safety_rejects_missing_packaged_executable(tmp_path):
    package = tmp_path / "package"
    package.mkdir()

    try:
        module._assert_safe(package, tmp_path / "target", tmp_path / "remote.git")
    except module.UATPreparationError as exc:
        assert "CenterManager.exe" in str(exc)
    else:
        raise AssertionError("non-package source must be rejected")
