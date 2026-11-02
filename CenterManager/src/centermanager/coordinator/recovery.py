"""Coordinator acceptance evidence independent of Git MAIN projection.

A coordinator receipt must never be substituted for legacy WriteRecoveryJournal
.published(provider). This guard is opt-in and does not mutate runtime journals.
"""
from dataclasses import dataclass
import hashlib

from .client_adapter import CoordinatorTransportError


@dataclass(frozen=True)
class CoordinatorPublicationProof:
    request_id: str
    candidate_sha256: str
    accepted_revision: int
    epoch: int
    local_sha256: str


def verify_coordinator_publication(*, client, request_id, expected_candidate_sha,
                                   local_snapshot, expected_local_sha=None):
    """Verify exact server receipt and immutable local bytes without journal cleanup.

    Candidate hash MUST identify the same snapshot as the local preserved capture.
    Callers must retain E1B durable recovery captures on every mismatch/UNKNOWN.
    """
    if not request_id or not expected_candidate_sha:
        raise CoordinatorTransportError("INVALID_PUBLICATION_PROOF")
    payload = local_snapshot.read_bytes()
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected_candidate_sha or (expected_local_sha and observed != expected_local_sha):
        raise CoordinatorTransportError("LOCAL_SNAPSHOT_MISMATCH")
    accepted = client.reconcile(request_id, expected_sha=expected_candidate_sha)
    return CoordinatorPublicationProof(
        request_id=request_id, candidate_sha256=accepted.accepted_sha,
        accepted_revision=accepted.revision, epoch=accepted.epoch,
        local_sha256=observed
    )


def require_coordinator_journal_migration():
    """Explicit blocker until coordinator-native durable journal schema exists."""
    raise CoordinatorTransportError("COORDINATOR_JOURNAL_NOT_MIGRATED")
