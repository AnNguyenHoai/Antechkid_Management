# -*- coding: utf-8 -*-
"""TECH-008: startup retention for orphaned pre-edit snapshots."""

import os
from pathlib import Path

import pytest

from centermanager.platform.snapshot_retention import (
    DEFAULT_KEEP_SNAPSHOTS,
    prune_orphaned_snapshots,
    recovery_may_be_needed,
)

ROOT = Path(__file__).resolve().parents[1]


def _make_snapshots(directory: Path, count: int) -> list:
    directory.mkdir(parents=True, exist_ok=True)
    created = []
    for index in range(count):
        path = directory / f"pre_edit_{index:02d}.db"
        path.write_bytes(b"snapshot")
        # Deterministic, strictly increasing modification times.
        os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))
        created.append(path)
    return created


def test_default_keep_is_five():
    assert DEFAULT_KEEP_SNAPSHOTS == 5


def test_prunes_to_the_five_newest_when_no_journal(tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    created = _make_snapshots(snapshots_dir, 8)

    deleted = prune_orphaned_snapshots(snapshots_dir, None)

    assert deleted == 3
    remaining = sorted(p.name for p in snapshots_dir.glob("pre_edit_*.db"))
    assert remaining == sorted(p.name for p in created[-5:])


def test_unrelated_files_are_never_touched(tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    _make_snapshots(snapshots_dir, 7)
    other = snapshots_dir / "keep_me.db"
    other.write_bytes(b"x")
    note = snapshots_dir / "pre_edit_note.txt"
    note.write_text("x", encoding="utf-8")

    prune_orphaned_snapshots(snapshots_dir, None)

    assert other.exists()
    assert note.exists()


def test_fewer_than_limit_keeps_everything(tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    created = _make_snapshots(snapshots_dir, 3)

    assert prune_orphaned_snapshots(snapshots_dir, None) == 0
    assert all(p.exists() for p in created)


def test_missing_directory_is_not_an_error(tmp_path):
    assert prune_orphaned_snapshots(tmp_path / "absent", None) == 0
    assert prune_orphaned_snapshots(None, None) == 0


@pytest.mark.parametrize("status", ["PREPARING", "OPEN", "PUBLISHING", "PUBLISHED", "POST_PUBLISH_PENDING"])
def test_pending_recovery_blocks_pruning(tmp_path, status):
    snapshots_dir = tmp_path / "snapshots"
    created = _make_snapshots(snapshots_dir, 8)

    assert prune_orphaned_snapshots(snapshots_dir, {"status": status}) == 0
    assert all(p.exists() for p in created)


def test_lost_write_authority_blocks_pruning_until_reconciled(tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    created = _make_snapshots(snapshots_dir, 8)

    assert prune_orphaned_snapshots(snapshots_dir, {"status": "CLEAN", "mutation_authority_lost": True}) == 0
    assert all(p.exists() for p in created)

    assert prune_orphaned_snapshots(snapshots_dir, {"status": "RECONCILED", "mutation_authority_lost": True}) == 3


@pytest.mark.parametrize("status", ["CLEAN", "CANCELLED", "RECONCILED"])
def test_settled_journal_allows_pruning(status):
    assert recovery_may_be_needed({"status": status}) is False


def test_unknown_journal_shape_is_treated_as_recovery_needed(tmp_path):
    snapshots_dir = tmp_path / "snapshots"
    created = _make_snapshots(snapshots_dir, 8)

    assert prune_orphaned_snapshots(snapshots_dir, object()) == 0
    assert all(p.exists() for p in created)


def test_bootstrap_runs_retention_after_journal_inspection():
    source = (ROOT / "src" / "centermanager" / "platform" / "bootstrap" / "bootstrap_manager.py").read_text(encoding="utf-8")
    inspect_at = source.index("journal_document = WriteRecoveryJournal(paths).inspect()")
    prune_at = source.index("prune_orphaned_snapshots(")
    detect_at = source.index("repo_state = self._repo_manager.detect()")
    assert inspect_at < prune_at < detect_at


def test_app_holds_instance_lock_before_bootstrap():
    source = (ROOT / "src" / "centermanager" / "app.py").read_text(encoding="utf-8")
    assert source.index("instance_lock.tryLock(0)") < source.index("bootstrap = BootstrapManager()")
