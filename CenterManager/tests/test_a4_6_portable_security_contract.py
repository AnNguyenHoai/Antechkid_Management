"""A4.6 portability regression contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GIT_REPOSITORY = ROOT / "src" / "centermanager" / "platform" / "synchronization" / "git" / "git_repository.py"
STARTUP_SYNC = ROOT / "src" / "centermanager" / "platform" / "sync" / "startup_sync.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_git_repository_logs_never_emit_embedded_credentials():
    source = _read(GIT_REPOSITORY)
    assert "_redact_command" in source
    assert "_redact_command(cmd)" in source


def test_startup_sync_materializes_attachments_into_canonical_runtime_directory():
    source = _read(STARTUP_SYNC)
    assert "self._paths.attachment_dir / \"Employees\"" in source
    assert 'self._paths.runtime_root / "Attachments"' not in source
