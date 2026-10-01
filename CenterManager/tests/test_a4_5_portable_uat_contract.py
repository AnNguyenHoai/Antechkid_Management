"""A4.5 portable release and clean-machine UAT contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "build_release.py"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "windows-prototype-release.yml"
APP = ROOT / "src" / "centermanager" / "app.py"
BOOTSTRAP = ROOT / "src" / "centermanager" / "platform" / "bootstrap" / "bootstrap_manager.py"
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
    app_source = _read(APP)
    bootstrap_source = _read(BOOTSTRAP)

    bootstrap_marker = app_source.index("if not bootstrap.run():")
    initialize_marker = app_source.index("initialize_runtime_database()")
    engine_marker = app_source.index("engine = create_production_engine(echo=False)")

    assert bootstrap_marker < initialize_marker < engine_marker
    assert "if not self._ensure_authoritative_runtime_database(paths):" in bootstrap_source
    assert "if not StartupSynchronization(provider).run():" in bootstrap_source


def test_startup_sync_requires_authoritative_database_before_success():
    source = _read(STARTUP_SYNC)

    apply_start = source.index("    def _apply_runtime_database")
    apply_end = source.index("    def ", apply_start + 8)
    apply_block = source[apply_start:apply_end]
    missing_marker = apply_block.index("if not repo_db.exists():")
    return_false = apply_block.index("return False", missing_marker)
    copy_marker = apply_block.index("with open(repo_db, 'rb')", return_false)
    assert missing_marker < return_false < copy_marker

    run_start = source.index("    def run(")
    apply_call = source.index("if not self._apply_runtime_database():", run_start)
    success_marker = source.index("Startup synchronization completed successfully", apply_call)
    assert apply_call < success_marker


def test_release_uat_is_explicit_about_two_machine_flow():
    source = _read(BUILDER)
    assert "second machine" in source
    assert "stale local database" in source
    assert "Restarting the executable" in source
