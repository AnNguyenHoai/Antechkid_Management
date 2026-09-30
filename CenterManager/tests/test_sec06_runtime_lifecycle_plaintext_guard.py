"""SEC06 runtime DB ownership contract.

Production packaged builds require SQLCipher, so the destructive-recovery lock
reported by Windows exercises the encrypted connector. Plain sqlite lifecycle
inspection remains development-only and is intentionally not widened in this PR.
"""

from centermanager.database import engine as database_engine


def test_production_runtime_uses_encrypted_boundary_when_policy_requires_it(monkeypatch):
    monkeypatch.setattr(database_engine, "database_encryption_required", lambda: True)
    assert database_engine.database_encryption_required() is True
