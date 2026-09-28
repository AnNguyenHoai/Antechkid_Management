from pathlib import Path


def test_fixture_contains_source_runtime_guard():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert 'source_runtime = (ROOT / "runtime").resolve()' in script
    assert "target == source_runtime" in script
    assert "remote == source_runtime" in script
