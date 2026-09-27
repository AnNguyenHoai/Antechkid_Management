# -*- coding: utf-8 -*-
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import centermanager.database.seed as seed


class _EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _FakeSession:
    def __init__(self):
        self.added = []

    def query(self, *args, **kwargs):
        return _EmptyQuery()

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None


def test_fresh_admin_requires_password_change(monkeypatch):
    from centermanager.security import password as password_module

    monkeypatch.setattr(password_module, "hash_password", lambda value: "hashed")
    session = _FakeSession()
    admin_role = SimpleNamespace(id=7)

    seed._create_admin_user(session, admin_role)

    assert len(session.added) == 1
    admin = session.added[0]
    assert admin.username == "admin"
    assert admin.force_password_change is True


def test_production_initializer_direct_cli_dry_run_needs_no_pythonpath():
    center_root = Path(__file__).resolve().parents[1]
    script = center_root / "scripts" / "initialize_production_database.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(center_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "ModuleNotFoundError" not in completed.stderr
    assert "[DRY-RUN] No files changed." in completed.stdout
    assert "CREATE-PRODUCTION-DATABASE" in completed.stdout
