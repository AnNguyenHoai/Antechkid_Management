"""REC-03: fallback selects a new runtime only after Git MAIN acceptance."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "src" / "centermanager"


def test_isolated_recovery_path_requires_explicit_bootstrap_recovery_failure():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    bootstrap = (ROOT / "platform" / "bootstrap" / "bootstrap_manager.py").read_text(encoding="utf-8")
    assert 'if not getattr(bootstrap, "_recovery_blocked", False):' in app
    assert 'self._recovery_blocked = False' in bootstrap
    assert 'self._recovery_blocked = True' in bootstrap
    assert 'self._recovery_blocked = bool(getattr(startup, \'recovery_error\', None))' in bootstrap


def test_second_bootstrap_never_reuses_original_runtime_mutations():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "isolated_candidate = prepare_isolated_runtime(paths)" in app
    assert "instance_lock.unlock()" in app
    assert "paths._runtime_root = isolated_candidate.candidate" in app
    assert "bootstrap = BootstrapManager()" in app
    assert 'raise RuntimeError("Isolated Git MAIN could not be independently verified")' in app
    assert "accept_isolated_runtime(paths.project_root, isolated_candidate)" in app
    # New runtime accepted only after schema migration and its signed receipt.
    assert app.index("startup_journal.record_verified_fresh_install(") < app.index(
        "accept_isolated_runtime(paths.project_root, isolated_candidate)"
    )
    assert app.index("accept_isolated_runtime(paths.project_root, isolated_candidate)") < app.index(
        "login_dialog = LoginDialog("
    )


def test_isolated_boot_does_not_skip_remote_main_or_write_leases():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    startup = (ROOT / "platform" / "sync" / "startup_sync.py").read_text(encoding="utf-8")
    collab = (ROOT / "platform" / "collaboration" / "collaboration_manager.py").read_text(encoding="utf-8")
    assert "if not startup.run():" in (ROOT / "platform" / "bootstrap" / "bootstrap_manager.py").read_text(encoding="utf-8")
    assert "if not self._fetch_remote():" in startup
    assert "if not self._prepare_authoritative_startup_replacement():" in startup
    assert "request_write(" in collab
    assert "bootstrap.run()" in app
