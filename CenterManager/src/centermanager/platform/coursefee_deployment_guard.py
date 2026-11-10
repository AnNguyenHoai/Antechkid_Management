"""Strict deployment identity for the course/session tuition build.

Git configuration is machine-portable and may have been copied from another
CenterManager installation. Check it before clone/fetch/SQLCipher replacement.
An invalid target is a configuration failure, NEVER a Recovery admission gate.
"""
from __future__ import annotations


class CourseFeeDeploymentError(ValueError):
    """Selected Git database branch does not belong to this course-fee build."""


COURSEFEE_DATABASE_BRANCH = "main_coursefee"


def validate_coursefee_git_branch(branch: str) -> None:
    if not isinstance(branch, str) or branch.strip() != COURSEFEE_DATABASE_BRANCH:
        raise CourseFeeDeploymentError(
            "Course-fee edition requires an isolated Git DB branch named "
            "'main_coursefee'. Existing main/main_repos configs must not be "
            "reused; provision a dedicated branch with a compatible encrypted DB."
        )
