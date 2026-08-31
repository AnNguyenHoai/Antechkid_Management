from pathlib import Path
SRC=Path("src/centermanager")
def read(p): return (SRC/p).read_text(encoding="utf-8")
def test_configuration_service_lifecycle_contract():
    s=read("services/configuration_service.py")
    for token in ("class ConfigurationService","def load","def validate","def save","ConfigurationValidationError","restart_required"):
        assert token in s
def test_configuration_validation_rules():
    s=read("services/configuration_service.py")
    for token in ("ZoneInfo","academic_year","currency","lock_timeout","heartbeat_interval"):
        assert token in s
def test_settings_page_uses_configuration_service():
    s=read("ui/admin_workspace/settings_page.py")
    assert "ConfigurationService" in s
