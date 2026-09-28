from pathlib import Path


def test_uat_fixture_requires_explicit_confirmation():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert 'CONFIRM = "PREPARE-ISOLATED-SEC06-UAT"' in script
    assert "if not args.apply:" in script
    assert "if args.confirm != CONFIRM:" in script
