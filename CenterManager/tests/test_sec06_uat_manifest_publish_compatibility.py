import json
from pathlib import Path


def test_uat_initial_manifest_starts_at_version_one():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert '"runtime_version": 1' in script
    assert 'repo / "manifest.json"' in script
    assert '"add",' in script
    assert '"database/center.db.identity.json",' in script
    assert "manifest.name" in script
