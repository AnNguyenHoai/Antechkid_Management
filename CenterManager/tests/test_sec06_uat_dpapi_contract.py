from pathlib import Path


def test_uat_fixture_provisions_key_only_after_runtime_isolation():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    remove_config = 'for relative in ("runtime/Database", "runtime/repository", "runtime/Config")'
    initialize = "initialize_runtime_database()"
    assert remove_config in script
    assert initialize in script
    assert script.index(remove_config) < script.index(initialize)
    assert "DatabaseKeyStore()" in script
