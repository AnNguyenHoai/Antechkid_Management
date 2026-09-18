# -*- coding: utf-8 -*-
"""Portable Git commit identity boundary for CenterManager.

CenterManager must be able to create Git commits on a clean Windows machine
without relying on machine-global ``git config user.name/user.email``.  This
installer injects author/committer identity only into commit subprocesses.
"""

from typing import Any


_COMMIT_COMMANDS = {"commit", "commit-tree"}


def install_portable_git_commit_identity(provider_cls: Any) -> None:
    """Ensure commit operations have a deterministic process-local identity.

    The identity comes from the provider's configured ``username``/``email``
    values, which already default to ``CenterManager`` and
    ``centermanager@local``.  Environment variables are used instead of
    ``git config --global`` so no host-machine Git configuration is required or
    mutated.  Existing command-specific environment such as ``GIT_INDEX_FILE``
    is preserved.
    """
    if getattr(provider_cls, "_portable_git_commit_identity_installed", False):
        return

    original_run_git_command = provider_cls._run_git_command

    def run_git_command_with_identity(self, args, *run_args, **run_kwargs):
        command = str(args[0]).lower() if args else ""
        if command in _COMMIT_COMMANDS:
            supplied_env = run_kwargs.get("env")
            env = dict(supplied_env) if supplied_env is not None else self._get_env()

            name = str(getattr(self, "_username", "") or "CenterManager")
            email = str(getattr(self, "_email", "") or "centermanager@local")

            env["GIT_AUTHOR_NAME"] = name
            env["GIT_AUTHOR_EMAIL"] = email
            env["GIT_COMMITTER_NAME"] = name
            env["GIT_COMMITTER_EMAIL"] = email
            run_kwargs["env"] = env

        return original_run_git_command(self, args, *run_args, **run_kwargs)

    provider_cls._run_git_command = run_git_command_with_identity
    provider_cls._portable_git_commit_identity_installed = True
