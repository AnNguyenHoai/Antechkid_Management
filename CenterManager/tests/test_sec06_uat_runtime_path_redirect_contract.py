from pathlib import Path


def test_fixture_redirects_runtime_paths_to_isolated_target():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert "redirected._project_root = target" in script
    assert 'redirected._runtime_root = target / "runtime"' in script
    assert "paths_module._paths = redirected" in script
