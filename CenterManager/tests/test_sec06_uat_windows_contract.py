from pathlib import Path


def test_fixture_requires_windows_dpapi():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert 'if os.name != "nt":' in script
    assert "requires Windows DPAPI" in script
