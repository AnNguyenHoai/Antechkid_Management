"""REC-05: case summary must not claim phantom unpublished business edits."""
import json

import pytest

from centermanager.platform.recovery_change_classification import (
    BUSINESS_CHANGE, FILE_MISMATCH, RECOVERY_UNCERTAIN, PUBLISHED_VERIFIED,
    CLEAN, classify_case, classify_mismatch,
)
from centermanager.ui.recovery_cases_dialog import _summary


@pytest.mark.parametrize("published,observed,expected", [
    (None, "a" * 40, RECOVERY_UNCERTAIN),
    ("a" * 40, "b" * 40, RECOVERY_UNCERTAIN),
    ("a" * 40, "a" * 40, PUBLISHED_VERIFIED),
])
def test_verified_publication_is_not_the_same_as_lost_business_data(published, observed, expected):
    case = dict(
        case_id="x" * 64,
        status="ACKNOWLEDGED",
        publication="VERIFIED" if published else "UNVERIFIED",
        published_oid=published,
        observed_main_oid=observed,
        change_log_coverage="UNKNOWN",
        capture_ref="C:/private/student-name/database",
        write_session_id="secret-user-name",
    )
    before = json.dumps(case, sort_keys=True)
    assessment = classify_case(case)
    summary = _summary(case)
    assert assessment.classification == expected
    assert summary["recovery_classification"] == expected
    assert summary["business_mutation_count"] is None
    assert summary["change_log_coverage"] == "UNKNOWN"
    assert "chưa" in summary["note"].lower()
    assert "capture_ref" not in summary
    assert "write_session_id" not in summary
    assert "student-name" not in json.dumps(summary)
    assert json.dumps(case, sort_keys=True) == before


def test_equal_base_and_observed_oid_does_not_prove_local_clean():
    case = {
        "base_main_oid": "a" * 40,
        "observed_main_oid": "a" * 40,
        "publication": "UNVERIFIED",
        "change_log_coverage": "UNKNOWN",
    }
    assert classify_case(case).classification == RECOVERY_UNCERTAIN


def test_file_hash_mismatch_is_not_reported_as_business_mutation():
    evidence = dict(
        receipt_status="CLEAN", publication="VERIFIED",
        db_hash_match=False, wal_pending=False, local_files_match=True,
        git_clean=True,
    )
    result = classify_mismatch(**evidence)
    assert result.classification == FILE_MISMATCH
    assert result.business_mutation_count is None
    assert "chưa kết luận" in result.message


def test_wal_pending_without_business_evidence_is_file_mismatch():
    result = classify_mismatch(
        receipt_status="PUBLISHED", publication="VERIFIED",
        db_hash_match=True, wal_pending=True, local_files_match=True,
        git_clean=True,
    )
    assert result.classification == FILE_MISMATCH


def test_unknown_or_missing_provenance_never_implies_clean():
    result = classify_mismatch(
        receipt_status=None, publication=None,
        db_hash_match=None, wal_pending=None, local_files_match=None,
        git_clean=None,
    )
    assert result.classification == RECOVERY_UNCERTAIN


def test_clean_requires_all_proofs_and_no_wal():
    proof = dict(
        receipt_status="CLEAN", publication="VERIFIED",
        db_hash_match=True, wal_pending=False, local_files_match=True,
        git_clean=True, repository_match=True,
        head_accepted=True, head_upstream=True,
    )
    assert classify_mismatch(**proof).classification == CLEAN
    assert classify_mismatch(**{**proof, "git_clean": False}).classification == RECOVERY_UNCERTAIN
    assert classify_mismatch(**{**proof, "wal_pending": None}).classification == RECOVERY_UNCERTAIN
    assert classify_mismatch(**{**proof, "repository_match": False}).classification == RECOVERY_UNCERTAIN
    assert classify_mismatch(**{**proof, "head_upstream": False}).classification == RECOVERY_UNCERTAIN


def test_business_change_requires_explicit_confirmed_unpublished_events():
    proof = dict(
        receipt_status="OPEN", publication="UNVERIFIED",
        db_hash_match=False, wal_pending=True, local_files_match=False,
        git_clean=False,
    )
    assert classify_mismatch(**proof).classification == FILE_MISMATCH
    result = classify_mismatch(
        **proof, confirmed_unpublished_business_mutations=2,
    )
    assert result.classification == BUSINESS_CHANGE
    assert result.business_mutation_count == 2
    # A bool or zero can never accidentally be accepted as a count.
    assert classify_mismatch(
        **proof, confirmed_unpublished_business_mutations=True,
    ).classification == FILE_MISMATCH


def test_classifier_cannot_create_a_receipt_or_acknowledge_a_recovery_case():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "platform"
    source = (root / "recovery_change_classification.py").read_text(encoding="utf-8")
    assert "record_synchronized" not in source
    assert "record_verified" not in source
    assert "mark_reviewed" not in source
    assert "publish(" not in source
    assert "open(" not in source
