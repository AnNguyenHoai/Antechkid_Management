"""Archived Class tuition collection: keep mutation restrictions, allow historic debt."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from centermanager.services.income_service import IncomeService, IncomeValidationError


def test_archived_class_name_is_resolved_read_only_without_class_service_guard():
    record = SimpleNamespace(id=17, name="K3_Python", deleted_at="archived")
    session = object()
    provider = Mock()
    provider.classes.return_value.get_by_id.return_value = record
    service = IncomeService.__new__(IncomeService)
    service._session_factory = lambda: _SessionContext(session)
    service._repository_provider = provider
    service._class_service = Mock()
    assert service._class_name_for_tuition(17) == "K3_Python"
    provider.classes.assert_called_once_with(session)
    provider.classes.return_value.get_by_id.assert_called_once_with(17)
    service._class_service.get_class.assert_not_called()


def test_missing_historical_class_is_validation_error():
    provider = Mock()
    provider.classes.return_value.get_by_id.return_value = None
    service = IncomeService.__new__(IncomeService)
    service._session_factory = lambda: _SessionContext(object())
    service._repository_provider = provider
    with pytest.raises(IncomeValidationError, match="was not found"):
        service._class_name_for_tuition(17)


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *_args):
        return False


def test_normal_income_and_credit_income_use_historical_class_name():
    import inspect
    from centermanager.services.income_service import IncomeService
    ordinary = inspect.getsource(IncomeService.create_income)
    credit = inspect.getsource(IncomeService.create_tuition_payment_with_credit)
    assert 'if income_type == "Tuition":' in ordinary
    assert 'class_name = self._class_name_for_tuition(class_id)' in ordinary
    assert 'self._class_service.get_class(class_id)' in ordinary
    assert 'class_name = self._class_name_for_tuition(class_id)' in credit
    assert "_resolve_tuition_enrollment(" in ordinary
    assert "_resolve_tuition_enrollment(" in credit


def test_finance_income_create_permission_remains_on_write_entry_point():
    from centermanager.services import income_service
    import inspect

    source = inspect.getsource(income_service.IncomeService)
    assert '@require_permission("finance.income.create")\n    def create_income(' in source
    assert '@require_permission("finance.income.create")\n    def create_tuition_payment_with_credit(' in source
    assert '@require_permission("finance.income.create")\n    def _class_name_for_tuition(' not in source
