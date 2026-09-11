from pathlib import Path


SOURCE = Path("src/centermanager/ui/admin_workspace/admin_employee_work_data_page.py")


def read_source():
    return SOURCE.read_text(encoding="utf-8")


def test_registration_period_page_constructor_has_no_permissioned_refresh():
    source = read_source()
    constructor = source.split("    def _setup(self):", 1)[0]

    assert "self._period_initialized = False" in constructor
    assert "self._set_default_period()" not in constructor
    assert "self.refresh()" not in constructor


def test_registration_period_page_initializes_period_only_when_refreshed():
    source = read_source()

    assert "if not self._period_initialized:" in source
    assert "self._set_default_period()" in source
    assert "with QSignalBlocker(self.year), QSignalBlocker(self.month):" in source
    assert "self._period_initialized = True" in source


def test_registration_period_load_remains_explicitly_permissioned():
    source = read_source()

    assert 'self._registration_service.get_period(year, month)' in source
    assert 'self._registration_service.list_all(year, month)' in source
    assert 'QMessageBox.warning(self, "Registration Period"' in source
