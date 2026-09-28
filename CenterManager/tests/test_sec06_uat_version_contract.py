import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_sec06_isolated_uat.py"
spec = importlib.util.spec_from_file_location("prepare_sec06_isolated_uat_version", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_initial_uat_generation_preserves_release_runtime_version(tmp_path):
    repo = tmp_path / "repository"
    repo.mkdir()
    canonical = {
        "schema_version": 1,
        "runtime_version": 271,
        "database_version": 1,
        "minimum_app_version": "1.0.0-rc1",
        "publisher": "CenterManager",
        "branch": "main",
        "created_at": "2026-09-28T00:00:00+00:00",
        "published_at": "2026-09-28T00:00:00+00:00",
    }

    path = module._write_initial_repository_manifest(repo, canonical)
    manifest = json.loads(path.read_text(encoding="utf-8"))

    assert manifest["runtime_version"] == canonical["runtime_version"]
    assert manifest == canonical


def test_initial_uat_commit_remains_identified_as_fixture_generation_one():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "SEC06 isolated UAT generation 1" in script
