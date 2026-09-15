"""Regression coverage for working-time RepositoryProvider injection."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from centermanager.services.employee_working_time_service import EmployeeWorkingTimeService


def test_service_accepts_injected_repository_provider_without_constructing_default():
    provider = MagicMock()
    service = EmployeeWorkingTimeService(MagicMock(), repository_provider=provider)
    assert service._repository_provider is provider


def test_service_uses_default_provider_only_when_not_injected():
    provider = MagicMock()
    with patch("centermanager.services.employee_working_time_service.create_default_repository_provider", return_value=provider) as factory:
        service = EmployeeWorkingTimeService(MagicMock())

    factory.assert_called_once_with()
    assert service._repository_provider is provider
