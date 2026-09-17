import logging

from centermanager.core.logging import redact_sensitive_text


def test_redacts_token_embedded_in_git_url():
    secret = "ghp_exampleSecret123"
    message = f"remote https://{secret}@github.com/example/repo.git"

    redacted = redact_sensitive_text(message)

    assert secret not in redacted
    assert "[REDACTED_URL]" in redacted


def test_redacts_github_pat_outside_url():
    secret = "github_pat_exampleSecret123"
    redacted = redact_sensitive_text(f"token={secret}")

    assert secret not in redacted
    assert "token=[REDACTED]" in redacted


def test_redacting_formatter_sanitizes_exception_text():
    from centermanager.core.logging import RedactingFormatter

    secret = "ghp_tracebackSecret123"
    try:
        raise RuntimeError(f"clone failed: https://{secret}@github.com/example/repo.git")
    except RuntimeError:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="startup failed",
            args=(),
            exc_info=None,
        )
        record.exc_info = __import__("sys").exc_info()

    rendered = RedactingFormatter("%(message)s").format(record)
    assert secret not in rendered
    assert "[REDACTED_URL]" in rendered
