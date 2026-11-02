"""E1C coordinator authority engine. Isolated from Windows runtime and production Git.

PostgreSQL is required for multi-instance deployments; SQLite is for local tests.
No desktop Git push credentials are accepted here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid
from sqlalchemy import (create_engine, String, Integer, DateTime, ForeignKey, Text,
                        UniqueConstraint, select)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session


class Base(DeclarativeBase):
    pass


class Authority(Base):
    __tablename__ = "e1c_authorities"
    repository_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    owner_session: Mapped[str | None] = mapped_column(String(128))
    owner_principal: Mapped[str | None] = mapped_column(String(128))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_sha: Mapped[str | None] = mapped_column(String(64))
    generation: Mapped[int] = mapped_column(Integer, default=0)


class Candidate(Base):
    __tablename__ = "e1c_candidates"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(128), index=True)
    submitted_by: Mapped[str] = mapped_column(String(128))
    sha: Mapped[str] = mapped_column(String(64))
    generation: Mapped[int] = mapped_column(Integer)
    identity: Mapped[str] = mapped_column(String(128))
    verified: Mapped[bool] = mapped_column(default=False)


class Receipt(Base):
    __tablename__ = "e1c_receipts"
    repository_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    principal: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[str] = mapped_column(Text)


class Audit(Base):
    __tablename__ = "e1c_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(String(128))
    revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))
    principal: Mapped[str] = mapped_column(String(128))
    session: Mapped[str | None] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("repository_id", "revision"),)


class Outbox(Base):
    __tablename__ = "e1c_outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[str] = mapped_column(String(128))
    revision: Mapped[int] = mapped_column(Integer)
    candidate_id: Mapped[str] = mapped_column(String(64))
    projected: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (UniqueConstraint("repository_id", "revision"),)


class CoordinatorError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Coordinator:
    def __init__(self, engine, *, lease_seconds=60):
        self.engine = engine
        self.lease_seconds = lease_seconds

    def create_schema_for_tests(self):
        """Use migrations for deployment, this helper is test-only."""
        Base.metadata.create_all(self.engine)

    def bootstrap(self, repo_id, accepted_sha=None):
        with Session(self.engine) as db, db.begin():
            if db.get(Authority, repo_id) is None:
                db.add(Authority(repository_id=repo_id, accepted_sha=accepted_sha))

    def state(self, repo_id):
        with Session(self.engine) as db:
            row = db.get(Authority, repo_id)
            if row is None:
                raise CoordinatorError("REPOSITORY_NOT_FOUND")
            return dict(epoch=row.epoch, revision=row.revision, owner_session=row.owner_session,
                        expires_at=row.expires_at.isoformat() if row.expires_at else None,
                        accepted_sha=row.accepted_sha, generation=row.generation)

    def register_candidate(self, repo_id, principal, candidate_id, ciphertext_sha,
                           generation, identity, verified=False):
        if len(ciphertext_sha) != 64 or len(identity) == 0:
            raise CoordinatorError("INVALID_CANDIDATE")
        with Session(self.engine) as db, db.begin():
            if db.get(Authority, repo_id) is None:
                raise CoordinatorError("REPOSITORY_NOT_FOUND")
            if db.get(Candidate, candidate_id):
                raise CoordinatorError("DUPLICATE_CANDIDATE")
            db.add(Candidate(id=candidate_id, repository_id=repo_id, submitted_by=principal,
                             sha=ciphertext_sha, generation=generation,
                             identity=identity, verified=verified))

    def command(self, repo_id, principal, request_id, action, **params):
        """Use one serialized transaction for authority change and receipt.

        Caller must authenticate and authorize principal outside this engine.
        In production use PostgreSQL primary; SELECT FOR UPDATE is not effective
        on SQLite, therefore SQLite must never be used for multi-client hosting.
        """
        if not principal or not request_id:
            raise CoordinatorError("INVALID_REQUEST")
        payload = dict(action=action, params=params)
        fingerprint = _hash(payload)
        with Session(self.engine) as db, db.begin():
            row = db.execute(select(Authority).where(
                Authority.repository_id == repo_id).with_for_update()).scalar_one_or_none()
            if row is None:
                raise CoordinatorError("REPOSITORY_NOT_FOUND")
            existing = db.get(Receipt, (repo_id, principal, request_id))
            if existing:
                if existing.request_hash != fingerprint:
                    raise CoordinatorError("IDEMPOTENCY_CONFLICT")
                return json.loads(existing.response)
            now = datetime.now(timezone.utc)
            expires = row.expires_at
            if expires is not None and expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            active = row.owner_session is not None and expires is not None and expires > now
            if action == "acquire":
                if active:
                    raise CoordinatorError("LEASE_HELD")
                if params.get("expected_revision") != row.revision:
                    raise CoordinatorError("REVISION_CONFLICT")
                row.epoch += 1
                row.owner_session = params["session_id"]
                row.owner_principal = principal
                row.expires_at = now + timedelta(seconds=self.lease_seconds)
            elif action in ("renew", "release", "publish"):
                if (not active or row.owner_session != params.get("session_id")
                        or row.owner_principal != principal or row.epoch != params.get("epoch")):
                    raise CoordinatorError("STALE_SESSION")
                if params.get("expected_revision") != row.revision:
                    raise CoordinatorError("REVISION_CONFLICT")
                if action == "renew":
                    row.expires_at = now + timedelta(seconds=self.lease_seconds)
                elif action == "release":
                    row.owner_session = None
                    row.owner_principal = None
                    row.expires_at = None
                else:
                    if row.accepted_sha != params.get("expected_accepted_sha"):
                        raise CoordinatorError("DATA_CONFLICT")
                    candidate = db.get(Candidate, params.get("candidate_id"))
                    if (candidate is None or not candidate.verified
                            or candidate.repository_id != repo_id
                            or candidate.submitted_by != principal
                            or candidate.generation <= row.generation):
                        raise CoordinatorError("INVALID_CANDIDATE")
                    row.accepted_sha = candidate.sha
                    row.generation = candidate.generation
                    db.add(Outbox(repository_id=repo_id, revision=row.revision + 1,
                                  candidate_id=candidate.id))
            elif action == "revoke":
                if not params.get("admin_authorized"):
                    raise CoordinatorError("FORBIDDEN")
                if (params.get("expected_revision") != row.revision
                        or params.get("expected_epoch") != row.epoch
                        or params.get("target_session_id") != row.owner_session):
                    raise CoordinatorError("REVISION_CONFLICT")
                row.epoch += 1
                row.owner_session = None
                row.owner_principal = None
                row.expires_at = None
            else:
                raise CoordinatorError("UNSUPPORTED_COMMAND")
            row.revision += 1
            result = dict(status="ACCEPTED", action=action, epoch=row.epoch,
                          revision=row.revision, accepted_sha=row.accepted_sha,
                          expires_at=row.expires_at.isoformat() if row.expires_at else None)
            db.add(Receipt(repository_id=repo_id, principal=principal, request_id=request_id,
                           request_hash=fingerprint, response=json.dumps(result)))
            db.add(Audit(repository_id=repo_id, revision=row.revision, action=action,
                         principal=principal, session=params.get("session_id"),
                         payload_hash=fingerprint))
            return result

    def get_receipt(self, repo_id, principal, request_id):
        with Session(self.engine) as db:
            item = db.get(Receipt, (repo_id, principal, request_id))
            return json.loads(item.response) if item else None
