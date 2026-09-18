from pathlib import Path


def test_finance_period_migrations_use_unique_revisions_and_current_chain():
    versions = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    finance_migrations = sorted(
        path for path in versions.glob("*.py")
        if "finance_period" in path.name
    )
    assert [path.name for path in finance_migrations] == [
        "1e10a018_finance_period.py",
        "1e10a019_income_finance_period.py",
        "1e10a020_finance_period_integrity.py",
    ]

    period_content = finance_migrations[0].read_text(encoding="utf-8")
    income_content = finance_migrations[1].read_text(encoding="utf-8")
    integrity_content = finance_migrations[2].read_text(encoding="utf-8")
    assert 'revision = "1e10a018"' in period_content
    assert 'down_revision = "1e10a017"' in period_content
    assert 'revision = "1e10a019"' in income_content
    assert 'down_revision = "1e10a018"' in income_content
    assert 'revision = "1e10a020"' in integrity_content
    assert 'down_revision = "1e10a019"' in integrity_content
