import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_sec06_isolated_uat.py"
spec = importlib.util.spec_from_file_location("prepare_sec06_isolated_uat", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def _canonical_manifest(runtime_version=271):
    return {
        "schema_version": 1,
        "runtime_version": runtime_version,
        "database_version": 1,
        "minimum_app_version": "0.1.0",
        "publisher": "CenterManager",
        "branch": "main",
        "created_at": "2026-09-29T00:00:00",
        "published_at": None,
    }


def test_initial_repository_manifest_preserves_packaged_runtime_contract(tmp_path):
    repo = tmp_path / "repository"
    repo.mkdir()
    canonical = _canonical_manifest(runtime_version=271)

    manifest_path = module._write_initial_repository_manifest(repo, canonical)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest_path == repo / "manifest.json"
    assert manifest == canonical
    assert manifest["runtime_version"] == 271
    assert set(manifest) == set(canonical)


def test_load_canonical_package_manifest_rejects_synthetic_minimal_manifest(tmp_path):
    package = tmp_path / "package"
    runtime = package / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "manifest.json").write_text(
        json.dumps({"runtime_version": 1}), encoding="utf-8"
    )

    try:
        module._load_canonical_package_manifest(package)
    except module.UATPreparationError as exc:
        assert "not canonical" in str(exc)
    else:
        raise AssertionError("minimal manifest must not be accepted for packaged UAT")


def test_load_canonical_package_manifest_accepts_release_contract(tmp_path):
    package = tmp_path / "package"
    runtime = package / "runtime"
    runtime.mkdir(parents=True)
    canonical = _canonical_manifest(runtime_version=271)
    (runtime / "manifest.json").write_text(
        json.dumps(canonical), encoding="utf-8"
    )

    loaded = module._load_canonical_package_manifest(package)

    assert loaded == canonical


def test_runtime_contract_validation_rejects_invalid_manifest(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    # RepositoryManager must see the same failure boundary as packaged startup.
    (runtime / "manifest.json").write_text(
        json.dumps({"runtime_version": 1}), encoding="utf-8"
    )

    try:
        module._validate_runtime_contract(tmp_path)
    except module.UATPreparationError as exc:
        assert "production runtime contract" in str(exc)
    else:
        raise AssertionError("invalid runtime manifest must fail fixture preparation")


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
