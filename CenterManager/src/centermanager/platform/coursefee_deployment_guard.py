"""Validate the configured Git database branch, not the application source branch.

The EXE's source lives on `main_coursefee`, but workstations may legitimately
use an independently provisioned database repository with a branch named
`main` (or a different valid Git branch). Branch names do not prove the
database's billing model; Alembic/schema checks enforce that separately.
"""
from __future__ import annotations
import re


class CourseFeeDeploymentError(ValueError):
    """The Git database branch configuration is malformed or unsafe."""


# Conservative subset of valid Git ref component names. No URL/path/space
# injection, shell-looking fragments, or internal collaboration ref prefixes.
_SAFE_GIT_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\Z")


def validate_coursefee_git_branch(branch: str) -> None:
    """Reject malformed Git refs, not valid database branch names."""
    if (
        not isinstance(branch, str)
        or len(branch) > 200
        or not _SAFE_GIT_BRANCH.fullmatch(branch)
        or branch.startswith(("lock-", "queue-"))
        or branch.startswith("-")
        or branch.endswith((".", "/", ".lock"))
        or branch.startswith(".")
        or any(segment in ("", ".", "..") or segment.startswith(".")
               or segment.endswith(".lock") for segment in branch.split("/"))
        or ".." in branch
        or "@{" in branch
    ):
        raise CourseFeeDeploymentError(
            "Invalid Git database branch in workstation configuration. "
            "Provide a valid existing branch with the correct encrypted database. "
            "Database schema and tuition lineage will be validated separately."
        )
