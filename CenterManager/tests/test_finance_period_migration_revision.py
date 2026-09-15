from pathlib import Path


def test_finance_period_migration_uses_unique_revision_and_current_head_parent():
    versions = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    finance_migrations = [
        path for path in versions.glob("*.py")
        if "finance_period" in path.name
    ]
    assert [path.name for path in finance_migrations] == ["1e10a018_finance_period.py"]

    content = finance_migrations[0].read_text(encoding="utf-8")
    assert 'revision = "1e10a018"' in content
    assert 'down_revision = "1e10a017"' in content
