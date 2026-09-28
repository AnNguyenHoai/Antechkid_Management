from pathlib import Path


def test_fixture_initial_generation_contains_sec05_identity_sidecar():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert "materialize_runtime_database_to_repository()" in script
    assert '"database/center.db.identity.json"' in script
    assert "validate_authoritative_repository_database()" in script
