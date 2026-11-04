# -*- coding: utf-8 -*-
"""Startup retention for orphaned WRITE snapshots (TECH-008).

``WriteTransaction`` copies the runtime database to
``runtime/snapshots/pre_edit_*.db`` when an edit starts. The snapshot path is
only held in memory, so snapshots left behind by a crash, a FAILED transaction
or a RECOVERY_REQUIRED transaction are never reused after a restart.

This module prunes those orphans at startup, after the single-instance lock is
held and before any WRITE transaction can begin. It never prunes while the
WRITE recovery journal says local work may still need recovery.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

SNAPSHOT_PATTERN = "pre_edit_*.db"
DEFAULT_KEEP_SNAPSHOTS = 5

# Journal states in which no WRITE work is pending recovery.
_SETTLED_JOURNAL_STATUSES = frozenset({"CLEAN", "CANCELLED", "RECONCILED"})


def recovery_may_be_needed(journal_document: Optional[Mapping[str, Any]]) -> bool:
    """Return True unless the journal proves no recovery is pending."""
    if journal_document is None:
        return False
    if journal_document.get("mutation_authority_lost") and journal_document.get("status") != "RECONCILED":
        return True
    return journal_document.get("status") not in _SETTLED_JOURNAL_STATUSES


def prune_orphaned_snapshots(
    snapshots_dir: Optional[Path],
    journal_document: Optional[Mapping[str, Any]],
    keep: int = DEFAULT_KEEP_SNAPSHOTS,
) -> int:
    """Delete all but the ``keep`` newest orphaned snapshots.

    Returns the number of deleted files. Never raises: retention is a disk
    hygiene step and must not block startup.
    """
    if keep < 0:
        raise ValueError("keep must be >= 0")
    try:
        skip = recovery_may_be_needed(journal_document)
    except Exception:
        logger.exception("Snapshot retention could not evaluate the recovery journal")
        return 0
    if skip:
        logger.info("Snapshot retention skipped: WRITE recovery may be required")
        return 0
    if snapshots_dir is None:
        return 0
    try:
        snapshots_dir = Path(snapshots_dir)
        if not snapshots_dir.is_dir():
            return 0
        snapshots = [p for p in snapshots_dir.glob(SNAPSHOT_PATTERN) if p.is_file()]
        snapshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:  # never block startup on disk hygiene
        logger.exception("Snapshot retention could not list %s", snapshots_dir)
        return 0

    deleted = 0
    for snapshot in snapshots[keep:]:
        try:
            snapshot.unlink()
            deleted += 1
        except OSError:
            logger.exception("Snapshot retention could not delete %s", snapshot)
    if deleted:
        logger.info("Snapshot retention deleted %d orphaned snapshot(s), kept %d", deleted, min(keep, len(snapshots)))
    return deleted
