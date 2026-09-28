from pathlib import Path


def test_fixture_defaults_to_dry_run():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert 'parser.add_argument("--apply", action="store_true")' in script
    assert 'print("[DRY-RUN] No files changed.")' in script
