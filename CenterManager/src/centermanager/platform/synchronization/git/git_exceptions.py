# -*- coding: utf-8 -*-
"""
Git exceptions.
"""


class GitError(Exception):
    """Base exception for Git operations."""
    pass


class GitRepositoryError(GitError):
    """Raised when repository operation fails."""
    pass


class GitAuthenticationError(GitError):
    """Raised when authentication fails."""
    pass


class GitPullError(GitError):
    """Raised when pull fails."""
    pass


class GitPushError(GitError):
    """Raised when push fails."""
    pass


class GitFetchError(GitError):
    """Raised when fetch fails."""
    pass


class GitCommitError(GitError):
    """Raised when commit fails."""
    pass


class GitConfigurationError(GitError):
    """Raised when Git configuration is invalid or missing."""
    pass


# ------------------------------------------------------------
# Aliases để tương thích với các module khác
# ------------------------------------------------------------
GitException = GitError
GitRepositoryNotFound = GitRepositoryError
GitAuthenticationFailed = GitAuthenticationError
GitPullFailed = GitPullError
GitPushFailed = GitPushError
GitMergeRequired = GitError          # không có lớp riêng, dùng chung
GitNetworkError = GitError
GitCorrupted = GitError