from types import SimpleNamespace

import scripts.migrate_production_repository_to_sqlcipher as migration_cli


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.remote = "old"
        self.local = "old"
        self.staged = "database/center.db\ndatabase/center.db.identity.json"

    def _run_git_command(self, args):
        self.calls.append(("git", tuple(args)))
        if args[:2] == ["ls-remote", "origin"]:
            return f"{self.remote}\trefs/heads/main"
        if args == ["diff", "--cached", "--name-only"]:
            return self.staged
        if args[:2] == ["commit", "-m"]:
            self.local = "new"
        if args == ["rev-parse", "HEAD"]:
            return self.local
        return ""

    def _push_only(self, expected_remote_commit=None):
        self.calls.append(("push_only", expected_remote_commit))
        self.remote = self.local

    def disconnect(self):
        self.calls.append(("disconnect",))


class FakeCollaboration:
    instances = []

    def __init__(self, **kwargs):
        self.calls = []
        self._is_writing = False
        FakeCollaboration.instances.append(self)

    def initialize(self, **kwargs): self.calls.append(("initialize", kwargs))
    def request_write(self, reason):
        self.calls.append(("request", reason)); self._is_writing = True
        return SimpleNamespace(is_granted=True, result=SimpleNamespace(value="granted"), message="")
    def release_write(self): self.calls.append(("release",)); self._is_writing = False; return True
    def shutdown(self): self.calls.append(("shutdown",))


def _setup(monkeypatch, tmp_path):
    repo_db = tmp_path / "runtime" / "repository" / "database" / "center.db"
    repo_db.parent.mkdir(parents=True)
    repo_db.write_bytes(b"plaintext")
    pin = tmp_path / "runtime" / "Config" / "authoritative_database_identity.json"
    pin.parent.mkdir(parents=True)
    pin.write_text("old-pin", encoding="utf-8")
    provider = FakeProvider()
    FakeCollaboration.instances.clear()

    monkeypatch.setattr(migration_cli, "authoritative_repository_database_path", lambda: repo_db)
    monkeypatch.setattr(migration_cli, "local_identity_state_path", lambda: pin)
    monkeypatch.setattr(migration_cli, "database_encryption_required", lambda: True)
    monkeypatch.setattr(migration_cli, "_build_provider", lambda: (provider, "main", tmp_path / "runtime"))
    monkeypatch.setattr(migration_cli, "CollaborationManager", FakeCollaboration)
    monkeypatch.setattr(migration_cli.DatabaseKeyStore, "load", lambda self: b"k" * 32)
    monkeypatch.setattr(migration_cli, "is_plaintext_sqlite_file", lambda path: True)
    monkeypatch.setattr(migration_cli, "encrypt_plaintext_database_in_place", lambda path, key: path.write_bytes(b"encrypted-preserved-data") or path)
    monkeypatch.setattr(migration_cli, "validate_database_artifact", lambda *a, **k: None)

    def first_identity(path, key):
        manifest = path.with_name(path.name + ".identity.json")
        manifest.write_text("{}", encoding="utf-8")
        return manifest

    monkeypatch.setattr(migration_cli, "_write_first_identity", first_identity)
    monkeypatch.setattr(migration_cli, "validate_and_pin_identity", lambda path, key: pin.write_text("new-pin", encoding="utf-8"))
    return provider, repo_db, pin


def test_dry_run_never_connects(monkeypatch, tmp_path):
    monkeypatch.setattr(migration_cli, "authoritative_repository_database_path", lambda: tmp_path / "center.db")
    monkeypatch.setattr(migration_cli, "database_encryption_required", lambda: True)
    monkeypatch.setattr(migration_cli, "_build_provider", lambda: (_ for _ in ()).throw(AssertionError("dry-run must not connect")))
    assert migration_cli.main([]) == 0


def test_apply_requires_exact_confirmation(monkeypatch, tmp_path):
    monkeypatch.setattr(migration_cli, "authoritative_repository_database_path", lambda: tmp_path / "center.db")
    monkeypatch.setattr(migration_cli, "database_encryption_required", lambda: True)
    assert migration_cli.main(["--apply", "--confirm", "WRONG"]) == 2


def test_migration_uses_fenced_remote_source_pushes_pair_then_replaces_pin(monkeypatch, tmp_path):
    provider, _, pin = _setup(monkeypatch, tmp_path)
    assert migration_cli.main(["--apply", "--confirm", migration_cli.CONFIRM]) == 0
    assert ("git", ("fetch", "origin", "main")) in provider.calls
    assert ("git", ("reset", "--hard", "old")) in provider.calls
    assert ("git", ("add", "--force", migration_cli.DB_RELATIVE_PATH, migration_cli.IDENTITY_RELATIVE_PATH)) in provider.calls
    assert ("push_only", "old") in provider.calls
    assert pin.read_text(encoding="utf-8") == "new-pin"
    assert ("release",) in FakeCollaboration.instances[-1].calls


def test_unexpected_staged_file_fails_before_push_and_preserves_old_pin(monkeypatch, tmp_path):
    provider, _, pin = _setup(monkeypatch, tmp_path)
    provider.staged += "\nAttachments/Employees/unrelated.bin"
    assert migration_cli.main(["--apply", "--confirm", migration_cli.CONFIRM]) == 1
    assert not any(call[0] == "push_only" for call in provider.calls)
    assert pin.read_text(encoding="utf-8") == "old-pin"
    assert ("release",) in FakeCollaboration.instances[-1].calls


def test_denied_write_never_resets_or_migrates(monkeypatch, tmp_path):
    provider, _, _ = _setup(monkeypatch, tmp_path)
    class DeniedCollaboration(FakeCollaboration):
        def request_write(self, reason):
            self.calls.append(("request", reason))
            return SimpleNamespace(is_granted=False, result=SimpleNamespace(value="waiting"), message="busy")
    monkeypatch.setattr(migration_cli, "CollaborationManager", DeniedCollaboration)
    assert migration_cli.main(["--apply", "--confirm", migration_cli.CONFIRM]) == 1
    assert not any(call == ("git", ("reset", "--hard", "old")) for call in provider.calls)
