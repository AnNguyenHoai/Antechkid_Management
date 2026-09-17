from pathlib import Path

from centermanager.core.logging import redact_sensitive_text


ROOT = Path(__file__).resolve().parents[1]


def test_sensitive_git_url_is_redacted():
    secret = "ghp_exampleSecret123"
    redacted = redact_sensitive_text(
        f"remote https://{secret}@github.com/example/repo.git"
    )
    assert secret not in redacted
    assert "[REDACTED]@github.com/example/repo.git" in redacted


def test_common_github_token_is_redacted():
    secret = "github_pat_exampleSecret123"
    redacted = redact_sensitive_text(f"token={secret}")
    assert secret not in redacted
    assert "token=[REDACTED]" in redacted


def test_release_does_not_turn_git_configuration_into_log_content():
    source = (ROOT / "src/centermanager/core/logging.py").read_text(encoding="utf-8")
    assert "RedactingFormatter" in source
    assert "redact_sensitive_text" in source
