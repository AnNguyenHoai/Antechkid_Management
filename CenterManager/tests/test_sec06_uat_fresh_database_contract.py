from pathlib import Path


def test_fixture_refuses_nonempty_runtime_before_initialization():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert "if db.exists() or key_store.bundle_path.exists():" in script
    assert "Isolated runtime was not empty before initialization" in script
