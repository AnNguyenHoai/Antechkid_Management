"""A4.5 portable release and clean-machine UAT contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "build_release.py"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "windows-prototype-release.yml"
APP = ROOT / "src" / "centermanager" / "app.py"
STARTUP_SYNC = ROOT / "src" / "centermanager" / "platform" / "sync" / "startup_sync.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_release_builder_is_valid_python():
    source = _read(BUILDER)
    compile(source, str(BUILDER), "exec")


def test_release_workflow_has_syntax_gate_before_build():
    source = _read(WORKFLOW)
    assert "python -m py_compile build_release.py run.py" in source


def test_configured_startup_never_creates_engine_before_authoritative_sync():
    source = _read(APP)
    sync_marker = source.index('logger.info("[STARTUP] Running startup synchronization...")')
    engine_marker = source.index("engine = create_production_engine(echo=False)")
    assert sync_marker < engine_marker


def test_startup_sync_requires_authoritative_database_before_success():
    source = _read(STARTUP_SYNC)
    missing_marker = source.index("if not repo_db.exists():")
    return_false = source.index("return False", missing_marker)
    success_marker = source.index("Startup synchronization completed successfully")
    assert missing_marker < return_false < success_marker


def test_release_uat_is_explicit_about_two_machine_flow():
    source = _read(BUILDER)
    assert "second machine" in source
    assert "stale local database" in source
    assert "Restarting the executable" in source
