from pathlib import Path
from types import SimpleNamespace

import scripts.publish_production_database_remote as remote_cli


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.remote = "old"
        self.local = "old"

    def _run_git_command(self, args):
        self.calls.append(("git", tuple(args)))
        if args[:2] == ["ls-remote", "origin"]:
            return f"{self.remote}\trefs/heads/main"
        if args == ["rev-parse", "HEAD"]:
            return self.local
        if args[:2] == ["cat-file", "-e"]:
            return ""
        return ""

    def publish_only(self, message, user, expected_main_commit=None):
        self.calls.append(("publish", message, user, expected_main_commit))
        self.remote = "new"
        self.local = "new"
        return True

    def disconnect(self):
        self.calls.append(("disconnect",))


class FakeCollaboration:
    instances = []

    def __init__(self, **kwargs):
        self.calls = []
        self._is_writing = False
        FakeCollaboration.instances.append(self)

    def initialize(self, **kwargs):
        self.calls.append(("initialize", kwargs))

    def request_write(self, reason):
        self.calls.append(("request", reason))
        self._is_writing = True
        return SimpleNamespace(is_granted=True, result=SimpleNamespace(value="granted"), message="")

    def release_write(self):
        self.calls.append(("release",))
        self._is_writing = False
        return True

    def shutdown(self):
        self.calls.append(("shutdown",))


def _setup(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime" / "Database" / "center.db"
    repo_db = tmp_path / "runtime" / "repository" / "database" / "center.db"
    identity = repo_db.with_name(repo_db.name + ".identity.json")
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"encrypted")
    provider = FakeProvider()
    FakeCollaboration.instances.clear()

    monkeypatch.setattr(remote_cli, "get_database_path", lambda: runtime)
    monkeypatch.setattr(remote_cli, "database_encryption_required", lambda: True)
    monkeypatch.setattr(remote_cli, "_build_provider", lambda: (provider, "main", tmp_path / "runtime"))
    monkeypatch.setattr(remote_cli, "CollaborationManager", FakeCollaboration)

    def materialize():
        repo_db.parent.mkdir(parents=True, exist_ok=True)
        repo_db.write_bytes(b"encrypted")
        identity.write_text("{}", encoding="utf-8")
        return repo_db

    monkeypatch.setattr(remote_cli, "materialize_runtime_database_to_repository", materialize)
    monkeypatch.setattr(remote_cli, "validate_authoritative_repository_database", lambda: repo_db)
    return provider


def test_dry_run_does_not_build_provider_or_mutate(monkeypatch, tmp_path):
    runtime = tmp_path / "center.db"
    runtime.write_bytes(b"encrypted")
    monkeypatch.setattr(remote_cli, "get_database_path", lambda: runtime)
    monkeypatch.setattr(remote_cli, "database_encryption_required", lambda: True)
    monkeypatch.setattr(
        remote_cli,
        "_build_provider",
        lambda: (_ for _ in ()).throw(AssertionError("dry-run must not connect")),
    )
    assert remote_cli.main([]) == 0


def test_apply_requires_exact_confirmation(monkeypatch, tmp_path):
    runtime = tmp_path / "center.db"
    runtime.write_bytes(b"encrypted")
    monkeypatch.setattr(remote_cli, "get_database_path", lambda: runtime)
    monkeypatch.setattr(remote_cli, "database_encryption_required", lambda: True)
    assert remote_cli.main(["--apply", "--confirm", "WRONG"]) == 2


def test_apply_acquires_write_fences_forces_identity_and_publishes(monkeypatch, tmp_path):
    provider = _setup(monkeypatch, tmp_path)
    assert remote_cli.main(["--apply", "--confirm", remote_cli.CONFIRM]) == 0

    collab = FakeCollaboration.instances[-1]
    assert collab.calls[0][0] == "initialize"
    assert collab.calls[1][0] == "request"
    assert ("release",) in collab.calls

    assert ("git", ("add", "--force", remote_cli.IDENTITY_RELATIVE_PATH)) in provider.calls
    assert (
        "publish",
        remote_cli.COMMIT_MESSAGE,
        remote_cli.OPERATOR,
        "old",
    ) in provider.calls
    assert ("git", ("cat-file", "-e", "new:database/center.db.identity.json")) in provider.calls


def test_denied_write_does_not_materialize_or_publish(monkeypatch, tmp_path):
    provider = _setup(monkeypatch, tmp_path)

    class DeniedCollaboration(FakeCollaboration):
        def request_write(self, reason):
            self.calls.append(("request", reason))
            return SimpleNamespace(is_granted=False, result=SimpleNamespace(value="waiting"), message="busy")

    monkeypatch.setattr(remote_cli, "CollaborationManager", DeniedCollaboration)
    monkeypatch.setattr(
        remote_cli,
        "materialize_runtime_database_to_repository",
        lambda: (_ for _ in ()).throw(AssertionError("must not materialize without WRITE")),
    )
    assert remote_cli.main(["--apply", "--confirm", remote_cli.CONFIRM]) == 1
    assert not any(call[0] == "publish" for call in provider.calls)


def test_publication_failure_releases_write(monkeypatch, tmp_path):
    provider = _setup(monkeypatch, tmp_path)

    def fail_publish(*args, **kwargs):
        raise RuntimeError("push rejected")

    provider.publish_only = fail_publish
    assert remote_cli.main(["--apply", "--confirm", remote_cli.CONFIRM]) == 1
    collab = FakeCollaboration.instances[-1]
    assert ("release",) in collab.calls
    assert ("shutdown",) in collab.calls
