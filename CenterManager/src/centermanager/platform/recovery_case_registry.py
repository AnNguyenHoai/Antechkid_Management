"""RV-03 durable review-case registry outside replaceable Git/runtime trees.

Only verified WriteRecoveryJournal captures can create a case. Cases do not
authorize a database replacement or WRITE: the existing journal reconcile,
runtime fence, remote MAIN observation and interrupted-install replay still
own those decisions. No DB merge, file replay, remote push or force release.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from centermanager.platform.write_recovery import RecoveryRequired, _json

_OID = re.compile(r"^[0-9a-fA-F]{40,64}$")
_CASE_ID = re.compile(r"^[0-9a-f]{64}$")
_REVIEW_STATES = {"PENDING_REVIEW", "ACKNOWLEDGED"}


class RecoveryCaseRegistry:
    def __init__(self, journal):
        self.journal = journal
        self.root = journal.root / "cases"

    def _key(self) -> bytes | None:
        from centermanager.database.encryption import (
            DatabaseKeyStore, database_encryption_required,
        )
        if database_encryption_required():
            # A missing/inaccessible DPAPI key must block startup continuation,
            # not produce an unsigned "verified" recovery case.
            return DatabaseKeyStore().load()
        return None  # Nonproduction, synthetic unencrypted test workspaces only.

    @staticmethod
    def _canonical(doc: dict) -> bytes:
        return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _signature(self, doc: dict, key: bytes | None) -> str:
        data = b"AnTechKids/RV-03/recovery-case/v1\0" + self._canonical(doc)
        if key is None:
            return hashlib.sha256(data).hexdigest()
        return hmac.new(key, data, hashlib.sha256).hexdigest()

    @staticmethod
    def _identity(document: dict, captured_db_sha: str) -> str:
        """Deterministic per incident: no user names or plaintext paths."""
        repository_id = document.get("repository_id")
        base = document.get("base_main_oid")
        if not repository_id or not base or not _OID.fullmatch(base):
            raise RecoveryRequired("Cannot identify recovery incident without verified repository and base OID.")
        incident = document.get("session_id") or ("legacy-" + captured_db_sha)
        raw = "\0".join((repository_id, base.lower(), incident)).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get(self, case_id: str) -> dict | None:
        if not _CASE_ID.fullmatch(case_id or ""):
            raise RecoveryRequired("Invalid Recovery Case ID.")
        path = self.root / (case_id + ".json")
        if not path.exists():
            return None
        try:
            signed = json.loads(path.read_text(encoding="utf-8"))
            signature = signed.pop("integrity", None)
            expected = self._signature(signed, self._key())
            if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
                raise ValueError("signature mismatch")
            if signed.get("case_id") != case_id or signed.get("status") not in _REVIEW_STATES:
                raise ValueError("case identity/status mismatch")
            return signed
        except Exception as exc:
            raise RecoveryRequired("Recovery Case registry is unreadable or inauthentic; startup blocked.") from exc

    def register_from_reconciled(self, *, observed_main_oid: str) -> dict:
        """Register case after an existing verified journal.reconcile(), before Git reset.

        Idempotent across interrupted startup and restart. Never overwrite a
        previous case, including an acknowledged one.
        """
        document = self.journal.inspect()
        if not document or document.get("status") != "RECONCILED":
            raise RecoveryRequired("Recovery Case requires an existing verified reconciled journal.")
        if (not _OID.fullmatch(observed_main_oid or "")
                or document.get("accepted_main_oid") != observed_main_oid):
            raise RecoveryRequired("Recovery Case MAIN does not match reconciled remote observation.")
        capture = document.get("last_capture")
        if not capture:
            raise RecoveryRequired("Recovery Case requires the preserved database and attachments.")
        verified = self.journal.verify_capture(capture)
        # The manifest is the existing authenticated proof: never accept a
        # recovery case built from a capture belonging to a different repo,
        # even if its ciphertext happens to be decryptable with the same key.
        manifest_journal = verified.get("journal") or {}
        captured_repository = manifest_journal.get("repository_id")
        if (captured_repository is not None
                and captured_repository != document.get("repository_id")):
            raise RecoveryRequired("Recovery Case capture belongs to a different repository.")
        if verified.get("journal", {}).get("base_main_oid") not in {
            document.get("base_main_oid"), None
        }:
            raise RecoveryRequired("Recovery Case capture belongs to another WRITE base.")
        db_sha = verified["files"].get("center.db")
        if not db_sha or not re.fullmatch("[a-f0-9]{64}", db_sha):
            raise RecoveryRequired("Recovery Case has no validated database fingerprint.")
        case_id = self._identity(document, db_sha)
        previous = self.get(case_id)
        if previous is not None:
            if (previous.get("base_main_oid") != document["base_main_oid"]
                    or previous.get("capture_db_sha256") != db_sha
                    or previous.get("repository_id") != document["repository_id"]):
                raise RecoveryRequired("Recovery Case identity collision; startup blocked.")
            # The remote may advance later; keep the exact MAIN observed when
            # the incident was initially isolated. Do not rewrite history.
            original_manifest = self.journal.verify_capture(previous["capture_ref"])
            if original_manifest.get("files", {}).get("center.db") != previous["capture_db_sha256"]:
                raise RecoveryRequired("Recovery Case original captured database fingerprint has changed.")
            return previous

        # Status from a failed/unknown publication must remain UNVERIFIED;
        # equality of a remote OID alone is not a proof that local edits landed.
        published_oid = document.get("published_oid")
        outcome = ("VERIFIED" if document.get("publication") == "VERIFIED"
                   and published_oid == observed_main_oid else "UNVERIFIED")
        entry = {
            "format": 1,
            "case_id": case_id,
            "status": "PENDING_REVIEW",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "repository_id": document["repository_id"],
            "write_session_id": document.get("session_id"),
            "base_main_oid": document["base_main_oid"],
            "observed_main_oid": observed_main_oid,
            "publication": outcome,
            "published_oid": published_oid if outcome == "VERIFIED" else None,
            "capture_ref": str(Path(capture).resolve()),
            "capture_db_sha256": db_sha,
            # RV-02 mirror is advisory. No captured outbox completeness proof
            # has been established here; RV-04 must not display COMPLETE.
            "change_log_coverage": "UNKNOWN",
        }
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = self.root / (case_id + ".json")
        key = self._key()
        signed = {**entry, "integrity": self._signature(entry, key)}
        # Exclusive creation: if another startup created the same case,
        # authenticate it instead of replacing it.
        try:
            with target.open("x", encoding="utf-8") as stream:
                import os
                os.chmod(target, 0o600)
                json.dump(signed, stream, sort_keys=True, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            existing = self.get(case_id)
            if existing is None:
                raise RecoveryRequired("Concurrent recovery case could not be verified.")
            return existing
        except Exception:
            # A half-written case must remain a blocker until manually
            # inspected; never delete potentially sole review evidence.
            raise
        return entry

    def list_cases(self) -> list[dict]:
        if not self.root.exists():
            return []
        cases = []
        for path in sorted(self.root.glob("*.json")):
            cases.append(self.get(path.stem))
        return cases
