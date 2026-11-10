"""Advisory review queue for obsolete local WRITE state (Git MAIN is authoritative).

Never a WRITE permit, publication receipt, encrypted DB replay source, or
startup admission gate. Case acknowledgement only controls UI reminders.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import uuid


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    try:
        with temp.open("x", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class RecoveryReviewNotices:
    """Local metadata; not an authentication authority for the Git database."""

    def __init__(self, journal):
        self.journal = journal
        self.root = Path(journal.root) / "review-notices"

    def record(self, *, observed_main_oid: str) -> Path:
        """Snapshot the raw journal log before replacing it with a CLEAN receipt.

        Never inspect uncertain metadata to *grant* authority: accepted MAIN
        is authenticated elsewhere by StartupSynchronization. If this local
        logging operation fails, caller may still start READ, but must not
        overwrite the original WRITE journal with a new CLEAN receipt.
        """
        journal_path = Path(self.journal.journal)
        journal_bytes = journal_path.read_bytes() if journal_path.is_file() else b""
        # The same unpublished-local incident must keep its review state even
        # if unrelated writers advance Git MAIN. The remote revision is context
        # for the notice, not part of the incident identity.
        identity = hashlib.sha256(
            str(getattr(self.journal, "runtime",
                        Path(self.journal.root).with_name("runtime"))).encode("utf-8")
            + b"\\0" + journal_bytes
        ).hexdigest()
        self.root.mkdir(parents=True, exist_ok=True)
        archived = self.root / (identity + ".journal.json")
        if journal_bytes:
            if archived.exists():
                if hashlib.sha256(archived.read_bytes()).digest() != hashlib.sha256(journal_bytes).digest():
                    raise ValueError("Existing review journal differs from original")
            else:
                with archived.open("xb") as stream:
                    stream.write(journal_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
        path = self.root / (identity + ".json")
        if not path.exists():
            _atomic_json(path, {
                "format": 1,
                "id": identity,
                "status": "PENDING_REVIEW",
                "detected_at_utc": datetime.now(timezone.utc).isoformat(),
                "observed_main_oid": observed_main_oid,
                "journal_sha256": hashlib.sha256(journal_bytes).hexdigest(),
                "journal_file": archived.name if journal_bytes else None,
                "log_directory": str(self.journal.root),
                "note": "Recovery log is an index, not a complete financial replay.",
            })
        return path

    def validate_notice(self, path: Path) -> dict:
        path = Path(path)
        if path.parent.resolve() != self.root.resolve() or not path.name.endswith(".json") or path.name.endswith(".journal.json"):
            raise ValueError("Unexpected review notice location")
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("format") != 1 or data.get("id") != path.stem
                or data.get("status") not in ("PENDING_REVIEW", "ACKNOWLEDGED")):
            raise ValueError("Review notice malformed")
        journal_file = data.get("journal_file")
        if journal_file:
            if journal_file != data["id"] + ".journal.json":
                raise ValueError("Unexpected journal snapshot name")
            snap = path.parent / journal_file
            if (not snap.is_file() or hashlib.sha256(snap.read_bytes()).hexdigest()
                    != data["journal_sha256"]):
                raise ValueError("Review journal snapshot changed")
        return data

    def pending(self) -> list[dict]:
        if not self.root.exists():
            return []
        result = []
        for file in sorted(self.root.glob("*.json")):
            if file.name.endswith(".journal.json"):
                continue
            try:
                notice = self.validate_notice(file)
            except Exception:
                # Corrupt advisory logs must not block an authoritative startup.
                # They also must NOT be acknowledged as genuine.
                continue
            if notice["status"] == "PENDING_REVIEW":
                result.append(notice)
        return result

    def has_recorded_notices(self) -> bool:
        """A validated modern notice supersedes an old duplicate popup.

        Retain legacy case history in the Recovery menu; never auto-ack or
        delete a signed legacy case merely because the user reviewed the
        corresponding log in the newer UI.
        """
        if not self.root.is_dir():
            return False
        for path in self.root.glob("*.json"):
            if path.name.endswith(".journal.json"):
                continue
            try:
                self.validate_notice(path)
            except Exception:
                continue
            return True
        return False

    def covers_legacy_case(self, case: dict) -> bool:
        """Match a signed RV-03 case to its *own* journal session only.

        Never use 'any reviewed notice' as evidence to hide a different
        pending case. Malformed or unlinked notices cannot suppress reminders.
        """
        session_id = case.get("write_session_id")
        if not isinstance(session_id, str) or not session_id:
            return False
        if not self.root.is_dir():
            return False
        for path in self.root.glob("*.json"):
            if path.name.endswith(".journal.json"):
                continue
            try:
                notice = self.validate_notice(path)
                source = notice.get("journal_file")
                if not source:
                    continue
                document = json.loads((self.root / source).read_text(
                    encoding="utf-8"
                ))
                if (isinstance(document, dict)
                        and document.get("session_id") == session_id
                        and document.get("rv03_case_id") is not None
                        and document.get("rv03_case_id") == case.get("case_id")):
                    return True
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return False

    def acknowledge(self, case_id: str) -> None:
        if not isinstance(case_id, str) or len(case_id) != 64 or any(c not in "0123456789abcdef" for c in case_id):
            raise ValueError("Invalid review ID")
        path = self.root / (case_id + ".json")
        data = self.validate_notice(path)
        if data["status"] == "ACKNOWLEDGED":
            return
        data["status"] = "ACKNOWLEDGED"
        data["reviewed_at_utc"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(path, data)
