# -*- coding: utf-8 -*-
"""Static contract guards for the cross-machine WRITE handoff boundary."""

from pathlib import Path


def test_handoff_runtime_materialization_orders_quiesce_before_install_and_refresh():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "src"
        / "centermanager"
        / "platform"
        / "sync"
        / "write_handoff_runtime_sync_service.py"
    ).read_text(encoding="utf-8")

    quiesce = source.index("session_module.quiesce_runtime_db()")
    preserve_live = source.index("os.replace(runtime_db, previous_db)")
    install_authority = source.index("os.replace(staged_db, runtime_db)")
    hash_verify = source.index("installed_hash = _sha256(runtime_db)")
    refresh = source.index("self._refresh_db_sessions()")

    assert quiesce < preserve_live < install_authority < hash_verify < refresh
    assert 'runtime_db.with_name(runtime_db.name + "-wal")' in source
    assert 'runtime_db.with_name(runtime_db.name + "-shm")' in source
    assert "validate_authoritative_repository_database()" in source
