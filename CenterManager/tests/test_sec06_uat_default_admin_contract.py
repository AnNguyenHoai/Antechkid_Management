from pathlib import Path


def test_fixture_uses_production_seed_path_for_default_admin():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert "from centermanager.database.seed import seed_roles_and_permissions" in script
    assert "seed_roles_and_permissions(session)" in script
