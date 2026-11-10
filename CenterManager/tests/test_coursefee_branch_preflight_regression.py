"""Regression tests for isolated CourseFee deployment identity.

The Git destination check must happen before any startup synchronization,
and a wrong-branch provisioning bundle must never be accepted.
"""

import pytest

from centermanager.platform.coursefee_deployment_guard import (
    CourseFeeDeploymentError,
    validate_coursefee_git_branch,
)


@pytest.mark.parametrize("branch", ["main", "main_repos", "main_coursefee ", " main_coursefee", "", None])
def test_coursefee_rejects_wrong_or_nonexact_branch(branch):
    with pytest.raises(CourseFeeDeploymentError):
        validate_coursefee_git_branch(branch)


def test_coursefee_accepts_exact_isolated_branch():
    validate_coursefee_git_branch("main_coursefee")
