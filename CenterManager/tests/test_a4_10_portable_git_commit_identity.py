from pathlib import Path

from centermanager.platform.synchronization.git_commit_identity import (
    install_portable_git_commit_identity,
)


class _FakeProvider:
    def __init__(self):
        self._username = "Portable User"
        self._email = "portable@example.test"
        self.calls = []

    def _get_env(self):
        return {"BASE_ENV": "1"}

    def _run_git_command(self, args, *run_args, **run_kwargs):
        self.calls.append((list(args), dict(run_kwargs)))
        return "ok"


def _installed_provider():
    class Provider(_FakeProvider):
        pass

    install_portable_git_commit_identity(Provider)
    return Provider()


def test_commit_gets_process_local_author_and_committer_identity():
    provider = _installed_provider()

    assert provider._run_git_command(["commit", "-m", "message"]) == "ok"

    _, kwargs = provider.calls[-1]
    env = kwargs["env"]
    assert env["BASE_ENV"] == "1"
    assert env["GIT_AUTHOR_NAME"] == "Portable User"
    assert env["GIT_AUTHOR_EMAIL"] == "portable@example.test"
    assert env["GIT_COMMITTER_NAME"] == "Portable User"
    assert env["GIT_COMMITTER_EMAIL"] == "portable@example.test"


def test_commit_tree_preserves_existing_git_index_environment():
    provider = _installed_provider()
    supplied_env = {"GIT_INDEX_FILE": "isolated-index"}

    provider._run_git_command(["commit-tree", "abc123"], env=supplied_env)

    _, kwargs = provider.calls[-1]
    env = kwargs["env"]
    assert env["GIT_INDEX_FILE"] == "isolated-index"
    assert env["GIT_AUTHOR_NAME"] == "Portable User"
    assert env["GIT_COMMITTER_EMAIL"] == "portable@example.test"
    assert supplied_env == {"GIT_INDEX_FILE": "isolated-index"}


def test_non_commit_git_commands_do_not_receive_commit_identity():
    provider = _installed_provider()

    provider._run_git_command(["fetch", "origin", "main"])

    _, kwargs = provider.calls[-1]
    assert "env" not in kwargs


def test_portable_identity_implementation_never_uses_global_git_config():
    source = Path(
        "src/centermanager/platform/synchronization/git_commit_identity.py"
    ).read_text(encoding="utf-8")

    assert "git config --global" not in source
    assert '"GIT_AUTHOR_NAME"' in source
    assert '"GIT_COMMITTER_EMAIL"' in source
