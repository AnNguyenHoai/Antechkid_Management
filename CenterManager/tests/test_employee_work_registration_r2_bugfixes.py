from datetime import date, time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.services.employee_work_registration_service import (
    EmployeeWorkRegistrationService,
    EmployeeWorkRegistrationValidationError,
)


class TestEmployeeWorkRegistrationR2Bugfixes:
    def test_overlap_ignores_blocks_on_different_dates(self):
        existing = SimpleNamespace(
            id=1,
            work_date=date(2026, 9, 1),
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        EmployeeWorkRegistrationService._overlap(
            [existing], date(2026, 9, 2), time(9, 0), time(12, 0)
        )

    def test_overlap_rejects_intersecting_blocks_on_same_date(self):
        existing = SimpleNamespace(
            id=1,
            work_date=date(2026, 9, 1),
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        with pytest.raises(EmployeeWorkRegistrationValidationError, match="overlaps"):
            EmployeeWorkRegistrationService._overlap(
                [existing], date(2026, 9, 1), time(11, 0), time(13, 0)
            )

    def test_reopen_returns_accepted_registration_to_draft(self):
        session = MagicMock()
        session.__enter__.return_value = session
        session_factory = MagicMock(return_value=session)
        registration = SimpleNamespace(
            status=EmployeeWorkRegistration.STATUS_ACCEPTED,
            submitted_at=object(),
            accepted_at=object(),
            accepted_by_user_id=123,
        )
        service = EmployeeWorkRegistrationService(session_factory)
        service._require_permission = MagicMock()
        service._period = MagicMock(return_value=SimpleNamespace(id=9))
        service._get_registration = MagicMock(return_value=registration)

        manager = SimpleNamespace(id=99)
        with patch(
            "centermanager.services.employee_work_registration_service.get_current_user",
            return_value=manager,
        ):
            result = service.reopen(7, 2026, 9)

        assert result is registration
        assert registration.status == EmployeeWorkRegistration.STATUS_DRAFT
        assert registration.submitted_at is None
        assert registration.accepted_at is None
        assert registration.accepted_by_user_id is None
        session.commit.assert_called_once()
