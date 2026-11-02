"""Phase 3 disposable Git remote tests; never use user configuration/production."""
import subprocess
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from centermanager.coordinator.authority import Coordinator, CoordinatorError, Outbox
from centermanager.coordinator.storage import LocalCandidateStore
from centermanager.coordinator.projector import GitProjector


@pytest.fixture
def fixture(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'authority.db'}")
    authority = Coordinator(engine)
    authority.create_schema_for_tests()
    authority.bootstrap("repo", "0" * 64)
    store = LocalCandidateStore(tmp_path / "objects")
    import hashlib
    blob = b"encrypted-synthetic-candidate"
    digest = hashlib.sha256(blob).hexdigest()
    store.put("repo", blob, digest)
    authority.register_candidate("repo", "alice", "candidate-1", digest, 1,
                                 "synthetic", verified=True)
    grant = authority.command("repo", "alice", "grant", "acquire",
                              expected_revision=0, session_id="A")
    authority.command("repo", "alice", "publish-1", "publish",
                      session_id="A", epoch=grant["epoch"], expected_revision=1,
                      expected_accepted_sha="0"*64, candidate_id="candidate-1")
    projector = GitProjector(authority, store, remote=str(remote))
    yield authority, store, projector, remote, digest
    engine.dispose()


def git(remote, ref):
    return subprocess.run(["git", "--git-dir", str(remote), "rev-parse", ref],
                          text=True, capture_output=True, check=True).stdout.strip()


def test_projection_advances_remote_and_marks_outbox(fixture):
    authority, store, projector, remote, digest = fixture
    result = projector.project_next("repo")
    assert result["revision"] == 2
    assert git(remote, "refs/heads/main") == result["git_oid"]
    assert projector.project_next("repo") is None
    assert authority.state("repo")["accepted_sha"] == digest
    with Session(authority.engine) as db:
        assert db.execute(select(Outbox)).scalar_one().projected


def test_lost_ack_reconciles_without_duplicate_git_commit(fixture):
    authority, store, projector, remote, digest = fixture
    def lost_ack(_oid):
        raise RuntimeError("synthetic crash after remote accepted")
    with pytest.raises(RuntimeError, match="synthetic crash"):
        projector.project_next("repo", after_push=lost_ack)
    before = git(remote, "refs/heads/main")
    result = projector.project_next("repo")
    assert result["reconciled"] is True
    assert result["git_oid"] == before
    assert git(remote, "refs/heads/main") == before
    assert authority.state("repo")["accepted_sha"] == digest


def test_invalid_remote_advance_does_not_erase_accepted_pointer(fixture, tmp_path):
    authority, store, projector, remote, digest = fixture
    # Move external Git ref after E1C acceptance with an unrelated commit.
    rogue = tmp_path / "rogue"
    rogue.mkdir()
    def cmd(*args):
        subprocess.run(["git", *args], cwd=rogue, check=True, capture_output=True)
    cmd("init", "-b", "main")
    cmd("config", "user.name", "Rogue")
    cmd("config", "user.email", "rogue@example.invalid")
    (rogue / "rogue.txt").write_text("external", encoding="utf-8")
    cmd("add", ".")
    cmd("commit", "-m", "external")
    cmd("remote", "add", "origin", str(remote))
    cmd("push", "origin", "main")
    with pytest.raises(CoordinatorError, match="PROJECTION_REMOTE_CONFLICT"):
        projector.project_next("repo")
    assert authority.state("repo")["accepted_sha"] == digest
    with Session(authority.engine) as db:
        assert not db.execute(select(Outbox)).scalar_one().projected
