"""A4.7 Git credential security regression contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT_DIR = ROOT / "src" / "centermanager" / "platform" / "synchronization" / "git"
GIT_REPOSITORY = GIT_DIR / "git_repository.py"
GIT_HELPER = GIT_DIR / "git_credential_helper.py"
GIT_CONFIG_SERVICE = ROOT / "src" / "centermanager" / "services" / "git_config_service.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_git_repository_never_embeds_token_in_remote_url():
    source = _read(GIT_REPOSITORY)
    assert 'f"{protocol}://{self._credentials.token}@{rest}"' not in source
    assert '"clone", self._credentials.repository_url' in source
    assert "GitCredentialHelper" in source


def test_git_config_connection_test_keeps_token_out_of_argv():
    source = _read(GIT_CONFIG_SERVICE)
    assert "auth_url" not in source
    assert '"ls-remote", config.repository_url, "HEAD"' in source
    assert "GitCredentialHelper" in source


def test_askpass_script_contains_no_secret_interpolation():
    source = _read(GIT_HELPER)
    assert "echo {self._token}" not in source
    assert "CENTERMANAGER_GIT_TOKEN" in source
    assert "CENTERMANAGER_GIT_USERNAME" in source


def test_git_errors_are_sanitized_before_logging_or_returning():
    source = _read(GIT_REPOSITORY)
    assert "_sanitize_text" in source
    assert 'value.replace(token, "***")' in source
    assert '"error": "Git operation failed"' in source
