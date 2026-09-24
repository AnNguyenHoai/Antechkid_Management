from pathlib import Path


def test_finance_period_migrations_use_unique_revisions_and_current_chain():
    versions = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    finance_migrations = sorted(
        path for path in versions.glob("*.py")
        if "finance_period" in path.name or "financial_settlement" in path.name
    )
    assert [path.name for path in finance_migrations] == [
        "1e10a018_finance_period.py",
        "1e10a019_income_finance_period.py",
        "1e10a020_finance_period_integrity.py",
        "1e10a021_financial_settlement.py",
        "1e10a026_expense_finance_period.py",
        "1e10a027_add_income_finance_period_id.py",
    ]

    period_content = finance_migrations[0].read_text(encoding="utf-8")
    income_content = finance_migrations[1].read_text(encoding="utf-8")
    integrity_content = finance_migrations[2].read_text(encoding="utf-8")
    settlement_content = finance_migrations[3].read_text(encoding="utf-8")
    expense_content = finance_migrations[4].read_text(encoding="utf-8")
    income_fk_content = finance_migrations[5].read_text(encoding="utf-8")

    assert 'revision = "1e10a018"' in period_content
    assert 'down_revision = "1e10a017"' in period_content
    assert 'revision = "1e10a019"' in income_content
    assert 'down_revision = "1e10a018"' in income_content
    assert 'revision = "1e10a020"' in integrity_content
    assert 'down_revision = "1e10a019"' in integrity_content
    assert 'revision = "1e10a021"' in settlement_content
    assert 'down_revision = "1e10a020"' in settlement_content

    # FW2-02 extends the repository's current Alembic head after the unrelated
    # 1e10a022..1e10a025 migrations. The expense assignment migration is part
    # of the FinancePeriod contract even though its down_revision is the global
    # migration head rather than the previous finance-named migration.
    assert 'revision = "1e10a026"' in expense_content
    assert 'down_revision = "1e10a025"' in expense_content

    # FW2-03 adds the canonical FinancePeriod FK to Income directly after FW2-02.
    assert 'revision = "1e10a027"' in income_fk_content
    assert 'down_revision = "1e10a026"' in income_fk_content
