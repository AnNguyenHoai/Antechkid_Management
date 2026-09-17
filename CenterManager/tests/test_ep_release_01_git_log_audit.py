import logging
from pathlib import Path

from centermanager.core.logging import RedactingFormatter, redact_sensitive_text
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git.git_credentials import GitCredentials
from centermanager.platform.synchronization.git.git_status import GitStatus


def test_redacts_git_remote_and_windows_path():
    text = (
        r"clone https://user:secret@example.com/org/private.git "
        r"to D:\Sensitive\CenterManager\repository"
    )
    redacted = redact_sensitive_text(text)
    assert "example.com" not in redacted
    assert "secret" not in redacted
    assert "D:\\Sensitive" not in redacted
    assert "[REDACTED_URL]" in redacted
    assert "[REDACTED_PATH]" in redacted


def test_formatter_redacts_exception_traceback_content():
    secret = "github_pat_test_secret"
    try:
        raise RuntimeError(
            r"Git failed for https://token:secret@example.com/private.git "
            r"at C:\Users\An\repository"
            + f" token={secret}"
        )
    except RuntimeError:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="startup failed",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )

    rendered = RedactingFormatter("%(message)s").format(record)
    assert secret not in rendered
    assert "example.com" not in rendered
    assert "C:\\Users" not in rendered


def test_git_provider_status_does_not_expose_repository_path_or_raw_error():
    credentials = GitCredentials(
        repository_url="https://example.com/private.git",
        token="test-token",
        branch="main",
        username="test-user",
        email="test@example.com",
    )
    provider = GitProvider(Path(r"D:\Sensitive\repository"), credentials)
    provider._status = GitStatus.ERROR
    provider._last_error = "remote failed at D:\\Sensitive\\repository"

    status = provider.status()

    assert "repo_path" not in status
    assert status["last_error"] == "Git operation failed"
    assert "Sensitive" not in str(status)


def test_git_provider_source_contains_no_sensitive_runtime_logging():
    source = Path(
        "CenterManager/src/centermanager/platform/synchronization/git/git_provider.py"
    ).read_text(encoding="utf-8")
    assert "logger." not in source
    assert "'repo_path': str(self._repo_path)" not in source
    assert "result.stderr" in source
