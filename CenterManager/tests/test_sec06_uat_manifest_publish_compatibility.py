import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_sec06_isolated_uat.py"
spec = importlib.util.spec_from_file_location("prepare_sec06_isolated_uat_manifest", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def _canonical_manifest(runtime_version: int = 271) -> dict:
    return {
        "schema_version": 1,
        "runtime_version": runtime_version,
        "database_version": 1,
        "minimum_app_version": "1.0.0-rc1",
        "publisher": "CenterManager",
        "branch": "main",
        "created_at": "2026-09-28T00:00:00+00:00",
        "published_at": "2026-09-28T00:00:00+00:00",
    }


def test_uat_initial_manifest_preserves_packaged_release_version(tmp_path):
    package = tmp_path / "package"
    runtime = package / "runtime"
    runtime.mkdir(parents=True)
    source_manifest = _canonical_manifest(runtime_version=271)
    (runtime / "manifest.json").write_text(json.dumps(source_manifest), encoding="utf-8")

    canonical = module._load_canonical_package_manifest(package)
    repo = tmp_path / "repository"
    repo.mkdir()
    manifest_path = module._write_initial_repository_manifest(repo, canonical)
    published = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert published == source_manifest
    assert published["runtime_version"] == 271
    assert manifest_path == repo / "manifest.json"


def test_uat_initial_commit_stages_database_identity_and_canonical_manifest():
    script = SCRIPT.read_text(encoding="utf-8")
    assert '"database/center.db"' in script
    assert '"database/center.db.identity.json"' in script
    assert "manifest.name" in script
