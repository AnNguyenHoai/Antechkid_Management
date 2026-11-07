"""Conservative, privacy-safe Recovery evidence classification (REC-05).

Classification is diagnostic only. It MUST NOT grant WRITE, mark a case
reviewed, discard local files, or imply that a changed business row was lost.
Older signed cases are classified in memory, never re-signed or rewritten.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


BUSINESS_CHANGE = "BUSINESS_CHANGE"
FILE_MISMATCH = "FILE_MISMATCH"
RECOVERY_UNCERTAIN = "RECOVERY_UNCERTAIN"
PUBLISHED_VERIFIED = "PUBLISHED_VERIFIED"
CLEAN = "CLEAN"


@dataclass(frozen=True)
class RecoveryAssessment:
    classification: str
    reason_code: str
    business_mutation_count: int | None = None

    @property
    def message(self) -> str:
        return {
            "CONFIRMED_UNPUBLISHED_MUTATION": (
                "Có thao tác nghiệp vụ chưa được MAIN xác nhận; cần đối chiếu thủ công."
            ),
            "FILE_BYTES_DIFFER": (
                "File DB/metadata hoặc WAL khác bản đã xác nhận; chưa kết luận có sửa dữ liệu nghiệp vụ."
            ),
            "PROVENANCE_INCOMPLETE": (
                "Trạng thái phiên cũ chưa được xác minh; không thể kết luận dữ liệu đã mất."
            ),
            "PUBLICATION_VERIFIED_COVERAGE_UNKNOWN": (
                "Đã xác minh publication lên Git MAIN; Change Log chưa đủ chứng minh mọi thay đổi."
            ),
            "ACCEPTED_CLEAN": "Đã xác minh trạng thái CLEAN của phiên hiện tại.",
        }[self.reason_code]


def classify_case(case: Mapping[str, object]) -> RecoveryAssessment:
    """Classify an authenticated Recovery Case, without opening DB or Git.

    The case's publication flag is a signed registry statement, not evidence
    that *all* local changes landed. Change-log coverage UNKNOWN is never
    interpreted as absence of business mutations. Older cases cannot be
    upgraded to a higher confidence from OID equality alone.
    """
    publication = case.get("publication")
    published = case.get("published_oid")
    observed = case.get("observed_main_oid")
    if publication == "VERIFIED" and isinstance(published, str) and published and published == observed:
        return RecoveryAssessment(PUBLISHED_VERIFIED, "PUBLICATION_VERIFIED_COVERAGE_UNKNOWN")
    return RecoveryAssessment(RECOVERY_UNCERTAIN, "PROVENANCE_INCOMPLETE")


def classify_mismatch(
    *,
    receipt_status: str | None,
    publication: str | None,
    db_hash_match: bool | None,
    wal_pending: bool | None,
    local_files_match: bool | None,
    git_clean: bool | None,
    confirmed_unpublished_business_mutations: int | None = None,
) -> RecoveryAssessment:
    """Diagnose a local discrepancy; no persisted changes or WRITE decisions.

    A mutation count is accepted ONLY from a caller that separately verified
    an unaccepted committed business event. Counts may not be inferred from
    a raw SQLite hash or an RV-02 mirror with UNKNOWN coverage.
    """
    if (
        type(confirmed_unpublished_business_mutations) is int
        and confirmed_unpublished_business_mutations > 0
    ):
        return RecoveryAssessment(
            BUSINESS_CHANGE,
            "CONFIRMED_UNPUBLISHED_MUTATION",
            confirmed_unpublished_business_mutations,
        )
    if any(value is False for value in (db_hash_match, local_files_match)) or wal_pending is True:
        return RecoveryAssessment(FILE_MISMATCH, "FILE_BYTES_DIFFER")
    if (receipt_status == "CLEAN" and publication == "VERIFIED"
            and db_hash_match is True and wal_pending is False
            and local_files_match is True and git_clean is True):
        return RecoveryAssessment(CLEAN, "ACCEPTED_CLEAN")
    return RecoveryAssessment(RECOVERY_UNCERTAIN, "PROVENANCE_INCOMPLETE")
