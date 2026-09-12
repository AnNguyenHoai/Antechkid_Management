from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "employee_admin_management_service.py"


def test_employee_admin_management_does_not_delete_through_session():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session.delete(" not in source


def test_employee_admin_management_deletes_through_repository_contract():
    source = SERVICE.read_text(encoding="utf-8")
    assert "repo.delete(registration)" in source
    assert "repo.delete(employee)" in source


def test_base_repository_exposes_transaction_scoped_delete():
    source = (
        ROOT / "src" / "centermanager" / "repositories" / "base.py"
    ).read_text(encoding="utf-8")
    assert "def delete(self, entity: T) -> T:" in source
    assert "self._session.delete(entity)" in source
