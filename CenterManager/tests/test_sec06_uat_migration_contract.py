from pathlib import Path


def test_fixture_migrates_schema_before_seeding():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    migration = script.index("upgrade_fresh_runtime_database_to_head()")
    seed = script.index("seed_roles_and_permissions(session)")
    assert migration < seed
