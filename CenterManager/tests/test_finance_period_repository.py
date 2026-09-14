from datetime import date

from sqlalchemy.orm import sessionmaker

from centermanager.models.finance_period import FinancePeriod
from centermanager.repositories.finance_period_repository import FinancePeriodRepository


def test_finance_period_repository_round_trip(test_db):
    from centermanager.database.engine import create_engine_for_path

    engine = create_engine_for_path(test_db)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        repo = FinancePeriodRepository(session)
        period = repo.add(
            FinancePeriod(
                duration_months=4,
                status=FinancePeriod.STATUS_ACTIVE,
                effective_from=date(2026, 9, 1),
            )
        )
        session.commit()
        repo.refresh(period)

        assert period.id is not None
        assert repo.get_by_id(period.id).duration_months == 4
        assert repo.get_active(date(2026, 10, 1)).id == period.id
        assert repo.list_all()[0].id == period.id
        assert repo.exists_effective_from(date(2026, 9, 1)) is True
