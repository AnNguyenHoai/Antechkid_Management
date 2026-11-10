"""Database Git branch names are independent of the source-code branch."""

import pytest

from centermanager.platform.coursefee_deployment_guard import (
    CourseFeeDeploymentError,
    validate_coursefee_git_branch,
)


@pytest.mark.parametrize("branch", ["main", "main_repos", "main_coursefee", "db/production"])
def test_accepts_valid_database_branches(branch):
    validate_coursefee_git_branch(branch)


@pytest.mark.parametrize(
    "branch",
    ["main ", " main", "", None, "lock-main", "queue-main",
     "../main", "db//main", ".hidden", "main.lock"],
)
def test_rejects_malformed_or_reserved_database_branches(branch):
    with pytest.raises(CourseFeeDeploymentError):
        validate_coursefee_git_branch(branch)
