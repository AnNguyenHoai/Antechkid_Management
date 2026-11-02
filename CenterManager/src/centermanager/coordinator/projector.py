"""Staging-only durable-outbox Git projector.

Only a separately provisioned coordinator worker can invoke this adapter. The
Git remote must independently deny ALL retired desktop write credentials.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from .authority import Authority, Candidate, CoordinatorError, Outbox


def _git(cwd, *args):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"},
    )
    if result.returncode:
        raise CoordinatorError("GIT_PROJECTION_FAILED")
    return result.stdout.strip()


def _remote_oid(cwd, branch):
    value = _git(cwd, "ls-remote", "origin", f"refs/heads/{branch}")
    return value.split()[0] if value else None


class GitProjector:
    """Serialize one repository outbox and reconcile ambiguous push ACK by OID.

    Projection is not the authority source; PostgreSQL accepted pointer/receipts
    remain authoritative even when this worker is unavailable.
    """
    def __init__(self, coordinator, store, *, remote, branch="main"):
        self.coordinator = coordinator
        self.store = store
        self.remote = str(remote)
        if branch != "main":
            raise CoordinatorError("UNSUPPORTED_PROJECTION_BRANCH")
        self.branch = branch

    def project_next(self, repository_id, *, after_push=None):
        with Session(self.coordinator.engine) as db, db.begin():
            # PostgreSQL row-lock keeps independent coordinator workers ordered.
            # SQLite is test-only and provides no multi-process fencing.
            authority = db.execute(select(Authority).where(
                Authority.repository_id == repository_id).with_for_update()).scalar_one_or_none()
            if authority is None:
                raise CoordinatorError("REPOSITORY_NOT_FOUND")
            event = db.execute(select(Outbox).where(
                Outbox.repository_id == repository_id,
                Outbox.projected.is_(False)).order_by(Outbox.revision).limit(1)
            ).scalar_one_or_none()
            if event is None:
                return None
            candidate = db.get(Candidate, event.candidate_id)
            if candidate is None or not candidate.verified or candidate.repository_id != repository_id:
                raise CoordinatorError("PROJECTION_CANDIDATE_INVALID")
            payload = self.store.read(repository_id, candidate.sha)
            if hashlib.sha256(payload).hexdigest() != candidate.sha:
                raise CoordinatorError("PROJECTION_CANDIDATE_INVALID")
            with tempfile.TemporaryDirectory(prefix="e1c-project-") as folder:
                root = Path(folder)
                _git(root, "init", "-b", self.branch)
                _git(root, "config", "user.name", "E1C Coordinator Projector")
                _git(root, "config", "user.email", "coordinator@example.invalid")
                _git(root, "remote", "add", "origin", self.remote)
                prior = _remote_oid(root, self.branch)
                if prior is not None:
                    _git(root, "fetch", "origin", self.branch)
                    _git(root, "checkout", "-B", self.branch, "FETCH_HEAD")
                else:
                    _git(root, "checkout", "-B", self.branch)
                marker = root / "e1c-projection.txt"
                if prior is not None and not marker.is_file():
                    raise CoordinatorError("PROJECTION_REMOTE_CONFLICT")
                if marker.is_file():
                    existing = marker.read_text(encoding="utf-8")
                    expected_marker = (
                        f"repository={repository_id}\\nrevision={event.revision}\\ncandidate={candidate.sha}\\n"
                    )
                    if existing == expected_marker:
                        event.projected = True
                        return {"revision": event.revision, "git_oid": prior, "reconciled": True}
                    old_revision = None
                    for line in existing.splitlines():
                        if line.startswith("revision="):
                            try:
                                old_revision = int(line.split("=", 1)[1])
                            except ValueError:
                                pass
                    if old_revision is not None and old_revision >= event.revision:
                        raise CoordinatorError("PROJECTION_OUT_OF_ORDER")
                path = root / "database"
                path.mkdir(exist_ok=True)
                (path / "center.db").write_bytes(payload)
                (root / "e1c-projection.txt").write_text(
                    f"repository={repository_id}\nrevision={event.revision}\ncandidate={candidate.sha}\n",
                    encoding="utf-8")
                _git(root, "add", "database/center.db", "e1c-projection.txt")
                _git(root, "commit", "--allow-empty", "-m", f"E1C accepted revision {event.revision}")
                intended = _git(root, "rev-parse", "HEAD")
                # Do not force update remote MAIN unless exact expected OID matches.
                lease = f"--force-with-lease=refs/heads/{self.branch}:{prior or ''}"
                result = subprocess.run(
                    ["git", "push", lease, "origin", f"HEAD:refs/heads/{self.branch}"],
                    cwd=root, text=True, capture_output=True, timeout=30,
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"},
                )
                # Even if ACK was lost, only the exact observed commit proves acceptance.
                observed = _remote_oid(root, self.branch)
                if observed != intended:
                    raise CoordinatorError("PROJECTION_REMOTE_CONFLICT")
                if after_push is not None:
                    after_push(intended)
            event.projected = True
            return {"revision": event.revision, "git_oid": intended}
