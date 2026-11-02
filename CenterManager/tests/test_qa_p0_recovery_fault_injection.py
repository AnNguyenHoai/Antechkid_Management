"""QA-P0 recovery fault injection against genuine isolated SQLCipher workspaces.

Reuses the established synthetic workspace from E1B-1. No production files,
credentials, collaboration refs or external remotes are touched.
"""
from pathlib import Path

import pytest

from tests.test_e1b1_durable_write_recovery import (
    workspace, begin, mutate, values, connect, git,  # noqa: F401
)
from centermanager.platform.write_recovery import RecoveryRequired


def _assert_live_and_protected(w):
    assert values(w.journal.database) == ["BASE", "LOCAL_UNACCEPTED"]
    with pytest.raises(RecoveryRequired):
        w.journal.assert_replaceable()


@pytest.mark.parametrize("failed_step", ["copy-ciphertext", "write-manifest", "verify-manifest"])
def test_failed_recovery_capture_does_not_destroy_previous_good_copy(
    workspace, monkeypatch, failed_step
):
    w = workspace
    begin(w)
    mutate(w)
    old = Path(w.journal.inspect()["last_capture"])
    w.journal.verify_capture(old)

    import centermanager.platform.write_recovery as module
    original_copy = module.shutil.copy2
    original_json = module._json
    original_verify = w.journal.verify_capture

    if failed_step == "copy-ciphertext":
        def copy(src, dst, *args, **kwargs):
            if Path(dst).name == "center.db" and "captures" in Path(dst).parts:
                raise OSError("QA synthetic disk full during ciphertext copy")
            return original_copy(src, dst, *args, **kwargs)
        monkeypatch.setattr(module.shutil, "copy2", copy)
    elif failed_step == "write-manifest":
        def write(path, data):
            if Path(path).name == "manifest.json":
                raise OSError("QA synthetic disk full during manifest fsync")
            return original_json(path, data)
        monkeypatch.setattr(module, "_json", write)
    else:
        def verify(path):
            if Path(path) != old:
                raise RecoveryRequired("QA synthetic capture verification failure")
            return original_verify(path)
        monkeypatch.setattr(w.journal, "verify_capture", verify)

    with pytest.raises((OSError, RecoveryRequired)):
        w.journal.preserve("qa-injected-failure")
    assert w.journal.inspect()["last_capture"] == str(old)
    original_verify(old)
    _assert_live_and_protected(w)


@pytest.mark.parametrize("remote_state", ["unavailable", "wrong-main"])
def test_ambiguous_publication_cannot_clean_live_database(workspace, remote_state):
    w = workspace
    begin(w)
    mutate(w)
    w.journal.update(status="PUBLISHING")
    # Do not accidentally count a mocked True response as accepted remote proof.
    class Provider:
        def get_local_main_commit(self):
            return w.base

        def observe_remote_main_commit(self):
            return None if remote_state == "unavailable" else "0" * 40

    with pytest.raises(RecoveryRequired):
        w.journal.published(Provider())
    assert w.journal.inspect()["status"] == "PUBLISHING"
    assert w.journal.inspect()["publication"] == "UNVERIFIED"
    _assert_live_and_protected(w)


def test_sqlcipher_integrity_and_foreign_keys_after_recovery_capture(workspace):
    w = workspace
    begin(w)
    mutate(w)
    capture = w.journal.preserve("qa-integrity")
    w.journal.verify_capture(capture)
    for dbpath in (w.journal.database, capture / "center.db"):
        conn = connect(dbpath, readonly=True)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
            assert conn.execute("SELECT value FROM recovery_items ORDER BY id").fetchall() == [
                ("BASE",), ("LOCAL_UNACCEPTED",)
            ]
        finally:
            conn.close()


def test_recovery_reconcile_wrong_remote_oid_preserves_unaccepted_sql(workspace):
    w = workspace
    begin(w)
    mutate(w)
    original = w.journal.inspect().copy()
    with pytest.raises(RecoveryRequired):
        w.journal.reconcile(
            base_oid=w.base,
            accepted_main=w.base,
            observe_main=lambda: "f" * 40,
        )
    assert w.journal.inspect() == original
    _assert_live_and_protected(w)
