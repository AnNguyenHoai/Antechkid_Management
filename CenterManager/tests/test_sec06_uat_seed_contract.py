from pathlib import Path


def test_uat_fixture_seeds_before_authoritative_publication():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    seed = "seed_roles_and_permissions(session)"
    publish = "repo_db = materialize_runtime_database_to_repository()"
    assert seed in script
    assert publish in script
    assert script.index(seed) < script.index(publish)
