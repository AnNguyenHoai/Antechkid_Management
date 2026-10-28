"""P0 regression: Finish Editing must not bypass signed artifact publication."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from centermanager.services.write_transaction import WriteTransactionManager


def test_finish_materialization_uses_signed_publication(tmp_path):
    root = tmp_path / "runtime"
    repo = root / "repository"
    (repo / "database").mkdir(parents=True)
    (root / "database").mkdir(parents=True)
    (root / "database" / "center.db").write_bytes(b"stub")
    (repo / "manifest.json").write_text('{"runtime_version": 1}', encoding="utf-8")
    manager = WriteTransactionManager(SimpleNamespace())
    manager._pending_version = None
    paths = SimpleNamespace(database_dir=root / "database", runtime_root=root)
    published = repo / "database" / "center.db"

    with patch("centermanager.services.write_transaction.get_paths", return_value=paths), patch(
        "centermanager.services.write_transaction.materialize_runtime_database_to_repository",
        return_value=published,
    ) as secure_publish:
        assert manager._publish_database_and_manifest()
    secure_publish.assert_called_once_with()


def test_finish_rejects_secure_publication_failure(tmp_path):
    root = tmp_path / "runtime"
    (root / "repository" / "database").mkdir(parents=True)
    (root / "database").mkdir(parents=True)
    (root / "database" / "center.db").write_bytes(b"stub")
    manager = WriteTransactionManager(SimpleNamespace())
    paths = SimpleNamespace(database_dir=root / "database", runtime_root=root)
    with patch("centermanager.services.write_transaction.get_paths", return_value=paths), patch(
        "centermanager.services.write_transaction.materialize_runtime_database_to_repository",
        side_effect=RuntimeError("identity failed"),
    ):
        assert not manager._publish_database_and_manifest()
