# -*- coding: utf-8 -*-
"""Local Git repository hygiene for cross-machine Windows deployments."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def remove_windows_shell_metadata_from_git_refs(repo_path: Path) -> bool:
    """Remove only ``desktop.ini`` files that contaminate ``.git/refs``.

    Windows/cloud-synced folders can create ``desktop.ini`` under Git's refs
    hierarchy. Git then interprets the file as a ref and commands such as
    ``fetch`` fail with ``fatal: bad object refs/.../desktop.ini``.

    This helper is intentionally narrow: it never deletes arbitrary malformed
    refs and never touches files outside ``.git/refs``. If an identified
    ``desktop.ini`` cannot be removed, return ``False`` so callers can fail
    closed instead of continuing with a repository Git already considers
    corrupt.
    """
    refs_root = Path(repo_path) / ".git" / "refs"
    if not refs_root.exists():
        return True

    removed = 0
    failed = []
    try:
        candidates = [
            path
            for path in refs_root.rglob("*")
            if path.is_file() and path.name.casefold() == "desktop.ini"
        ]
    except OSError as exc:
        logger.error("Unable to inspect Git refs for OS metadata: %s", exc)
        return False

    for path in candidates:
        try:
            path.unlink()
            removed += 1
        except OSError as exc:
            failed.append(path)
            logger.error("Unable to remove OS metadata from Git refs at %s: %s", path, exc)

    if removed:
        logger.warning(
            "Removed %s Windows shell metadata file(s) from Git refs before synchronization",
            removed,
        )

    if failed:
        logger.error(
            "Git refs hygiene failed; %s Windows shell metadata file(s) remain",
            len(failed),
        )
        return False

    return True
