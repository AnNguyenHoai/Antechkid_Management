from pathlib import Path

import scripts.publish_production_database as publish_cli


def test_dry_run_does_not_publish(monkeypatch, tmp_path, capsys):
    runtime = tmp_path / "runtime" / "Database" / "center.db"
    repo = tmp_path / "runtime" / "repository" / "database" / "center.db"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"encrypted")

    monkeypatch.setattr(publish_cli, "get_database_path", lambda: runtime)
    monkeypatch.setattr(publish_cli, "authoritative_repository_database_path", lambda: repo)
    monkeypatch.setattr(publish_cli, "database_encryption_required", lambda: True)
    monkeypatch.setattr(
        publish_cli,
        "materialize_runtime_database_to_repository",
        lambda: (_ for _ in ()).throw(AssertionError("must not publish during dry run")),
    )

    assert publish_cli.main([]) == 0
    assert "[DRY-RUN]" in capsys.readouterr().out


def test_apply_requires_exact_typed_confirmation(monkeypatch, tmp_path):
    runtime = tmp_path / "center.db"
    runtime.write_bytes(b"encrypted")
    monkeypatch.setattr(publish_cli, "get_database_path", lambda: runtime)
    monkeypatch.setattr(
        publish_cli,
        "authoritative_repository_database_path",
        lambda: tmp_path / "repo" / "center.db",
    )
    monkeypatch.setattr(publish_cli, "database_encryption_required", lambda: True)

    assert publish_cli.main(["--apply", "--confirm", "WRONG"]) == 2


def test_apply_refuses_nonproduction_encryption_policy(monkeypatch, tmp_path):
    runtime = tmp_path / "center.db"
    runtime.write_bytes(b"plaintext")
    monkeypatch.setattr(publish_cli, "get_database_path", lambda: runtime)
    monkeypatch.setattr(
        publish_cli,
        "authoritative_repository_database_path",
        lambda: tmp_path / "repo" / "center.db",
    )
    monkeypatch.setattr(publish_cli, "database_encryption_required", lambda: False)

    assert publish_cli.main(["--apply", "--confirm", publish_cli.CONFIRM]) == 2


def test_apply_uses_security_boundary_and_postvalidates(monkeypatch, tmp_path, capsys):
    runtime = tmp_path / "runtime" / "Database" / "center.db"
    repo = tmp_path / "runtime" / "repository" / "database" / "center.db"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"encrypted")
    calls = []

    monkeypatch.setattr(publish_cli, "get_database_path", lambda: runtime)
    monkeypatch.setattr(publish_cli, "authoritative_repository_database_path", lambda: repo)
    monkeypatch.setattr(publish_cli, "database_encryption_required", lambda: True)

    def publish():
        calls.append("publish")
        repo.parent.mkdir(parents=True)
        repo.write_bytes(b"encrypted")
        return repo

    def validate():
        calls.append("validate")
        return repo

    monkeypatch.setattr(publish_cli, "materialize_runtime_database_to_repository", publish)
    monkeypatch.setattr(publish_cli, "validate_authoritative_repository_database", validate)

    assert publish_cli.main(["--apply", "--confirm", publish_cli.CONFIRM]) == 0
    assert calls == ["publish", "validate"]
    assert "Signed SEC-05 identity" in capsys.readouterr().out


def test_apply_reports_security_boundary_failure(monkeypatch, tmp_path, capsys):
    runtime = tmp_path / "center.db"
    runtime.write_bytes(b"encrypted")
    monkeypatch.setattr(publish_cli, "get_database_path", lambda: runtime)
    monkeypatch.setattr(
        publish_cli,
        "authoritative_repository_database_path",
        lambda: tmp_path / "repo" / "center.db",
    )
    monkeypatch.setattr(publish_cli, "database_encryption_required", lambda: True)
    monkeypatch.setattr(
        publish_cli,
        "materialize_runtime_database_to_repository",
        lambda: (_ for _ in ()).throw(RuntimeError("identity validation failed")),
    )

    assert publish_cli.main(["--apply", "--confirm", publish_cli.CONFIRM]) == 1
    assert "identity validation failed" in capsys.readouterr().out
