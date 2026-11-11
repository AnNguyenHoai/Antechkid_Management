"""Phase 4 gate tests using disposable package fixtures only."""
import json
from pathlib import Path

import pytest
from scripts.verify_startup_release import migration_digest, verify_package


SHA = "a" * 40


def _package(root):
    for name in (
        "CenterManager.exe", "AdminTools/GitProvisioningAdmin.exe",
        "git/cmd/git.exe", "migrations/env.py", "migrations/versions/v1.py",
        "alembic.ini",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"harmless synthetic release asset")
    manifest = {
        "platform": "windows-x64",
        "source_commit": SHA,
        "migration_sha256": migration_digest(root),
    }
    (root / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_disposable_release_package_passes_source_migration_gate(tmp_path):
    assert verify_package(_package(tmp_path), SHA)["source_commit"] == SHA


def test_release_rejects_wrong_source_commit(tmp_path):
    root = _package(tmp_path)
    with pytest.raises(RuntimeError, match="Source commit mismatch"):
        verify_package(root, "b" * 40)


def test_release_rejects_replaced_migration_after_manifest(tmp_path):
    root = _package(tmp_path)
    (root / "migrations/versions/v1.py").write_text("tampered")
    with pytest.raises(RuntimeError, match="migration tree"):
        verify_package(root, SHA)


@pytest.mark.parametrize("secret", [
    "runtime/Database/center.db",
    "runtime/Config/config.json",
    "runtime/Config/database_key.dpapi",
    "git/.git/config",
])
def test_release_rejects_secrets_and_git_metadata(tmp_path, secret):
    root = _package(tmp_path)
    path = root / secret
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not a real credential")
    with pytest.raises(RuntimeError, match="Sensitive runtime"):
        verify_package(root, SHA)


def test_build_script_verifies_package_before_archive():
    root = Path(__file__).resolve().parents[1]
    source = (root / "build_release.py").read_text(encoding="utf-8")
    assert source.index("verify_package(PACKAGE_ROOT, source_commit)") < source.index(
        "archive = Path(shutil.make_archive("
    )
    assert '"migration_sha256": migration_digest(PROJECT_ROOT)' in source
    assert "--add-data" in source
    assert '"migrations"' in source
